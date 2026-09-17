"""Load the policy corpus and split it into citable clauses.

Stage 1 of the RAG architecture: document loader, then chunking with metadata.
One chunk is one clause. The corpus already marks every clause with a heading
such as ``## POL-001-C01 Low value purchases``, and requirement 7.4 requires
retrieved clauses to be shown by document name, document version and clause
identifier. Splitting anywhere else would produce chunks that cannot be cited.

Which folders are indexed
-------------------------
Only policies, procedures and product specifications. Requirement 7 retrieves
the rules that apply to the items being requisitioned, and those are the three
folders whose documents carry clause identifiers and state rules.

The rest of ``knowledge/corpus`` is left out on purpose:

* quotations are extraction inputs, reached through the quotation-retrieval
  tool, and QUO-005 carries a prompt injection that must never be handed to
  the model as policy context;
* supplier terms have no clause identifiers, so nothing in them can be cited,
  and supplier records have their own tool in the Project Charter;
* the requisition guides apply to every justification regardless of item, so
  they belong in the drafting prompt rather than in item-driven retrieval.

Why loading fails loudly
------------------------
This is a controlled corpus, and a citation is only worth something if the
clause it names is the clause that was registered and reviewed. Every document
is therefore checked against ``knowledge/source-register.csv``: it must be
registered, its version must agree with the register, and its content must
match the registered SHA-256. A mismatch raises rather than being skipped,
because an index silently built from an unreviewed edit would ground answers
in text nobody approved.

The checksum is taken over the file with line endings normalised to ``\\n``.
The register was computed that way, and Git on Windows (``core.autocrlf``)
checks the files out with ``\\r\\n``. Hashing the raw bytes would fail on every
Windows machine while passing in CI.
"""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_CORPUS_DIR = Path("knowledge") / "corpus"
DEFAULT_SOURCE_REGISTER = Path("knowledge") / "source-register.csv"

# Folder names under the corpus directory that are indexed. See module docstring.
INDEXED_FOLDERS = ("policies", "procedures", "product-specifications")

# Front-matter keys a document cannot be cited without.
REQUIRED_FRONT_MATTER = ("source_id", "title", "version")

_FRONT_MATTER_DELIMITER = "---"
_CLAUSE_HEADING = re.compile(r"^## (?P<clause_id>[A-Z]+-\d+-C\d+) (?P<heading>.+)$")


class CorpusError(ValueError):
    """Raised when the corpus cannot be loaded as registered and reviewed."""


@dataclass(frozen=True)
class Clause:
    """One citable clause. The unit that is embedded, retrieved and cited."""

    source_id: str
    title: str
    version: str
    category: str
    clause_id: str
    heading: str
    text: str
    file_path: str

    @property
    def citation(self) -> str:
        """Document name, version and clause identifier, as requirement 7.4 shows them."""
        return f"{self.title} v{self.version}, {self.clause_id}"


def load_corpus(
    corpus_dir: str | Path = DEFAULT_CORPUS_DIR,
    register_path: str | Path = DEFAULT_SOURCE_REGISTER,
    folders: Iterable[str] = INDEXED_FOLDERS,
) -> list[Clause]:
    """Load every clause from the indexed folders, verified against the register."""
    corpus_root = Path(corpus_dir)
    register = load_register(register_path)

    clauses: list[Clause] = []
    for folder in folders:
        directory = corpus_root / folder
        if not directory.is_dir():
            raise CorpusError(f"indexed folder {directory} does not exist")
        for path in sorted(directory.glob("*.md")):
            clauses.extend(load_document(path, register))

    _reject_duplicate_clause_ids(clauses)
    if not clauses:
        raise CorpusError(f"no clauses found under {corpus_root}")
    return clauses


def load_register(register_path: str | Path) -> dict[str, dict[str, str]]:
    """Read the source register, keyed by source_id."""
    path = Path(register_path)
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except FileNotFoundError as exc:
        raise CorpusError(f"source register {path} not found") from exc
    return {row["source_id"]: row for row in rows}


def load_document(path: str | Path, register: dict[str, dict[str, str]]) -> list[Clause]:
    """Parse one corpus document into clauses after checking it against the register."""
    path = Path(path)
    raw = path.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")

    front_matter, body = parse_front_matter(text, path)
    source_id = front_matter["source_id"]

    if source_id != path.stem:
        raise CorpusError(
            f"{path}: source_id {source_id!r} does not match the file name {path.stem!r}"
        )
    _verify_against_register(path, source_id, front_matter["version"], text, register)

    # The register's repository-relative path, not `path`. A path taken from
    # the filesystem is absolute whenever the caller passed an absolute corpus
    # directory, which would put one developer's home directory into every
    # trace and make the same clause look different on each machine.
    registered_path = register[source_id].get("file_path") or path.as_posix()

    clauses = [
        Clause(
            source_id=source_id,
            title=front_matter["title"],
            version=front_matter["version"],
            category=front_matter.get("category", ""),
            clause_id=clause_id,
            heading=heading,
            text=clause_text,
            file_path=registered_path,
        )
        for clause_id, heading, clause_text in split_clauses(body, source_id, path)
    ]
    if not clauses:
        raise CorpusError(f"{path}: no clause headings found, so nothing in it can be cited")
    return clauses


def parse_front_matter(text: str, path: str | Path = "<text>") -> tuple[dict[str, str], str]:
    """Split ``key: value`` front matter from the body.

    Deliberately not YAML. The corpus uses flat ``key: value`` pairs only, and
    parsing them needs no dependency; pyproject declares none.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != _FRONT_MATTER_DELIMITER:
        raise CorpusError(f"{path}: missing front matter")
    try:
        end = next(
            i for i, line in enumerate(lines[1:], start=1)
            if line.strip() == _FRONT_MATTER_DELIMITER
        )
    except StopIteration as exc:
        raise CorpusError(f"{path}: front matter is not closed") from exc

    front_matter: dict[str, str] = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if separator:
            front_matter[key.strip()] = value.strip()

    missing = [key for key in REQUIRED_FRONT_MATTER if not front_matter.get(key)]
    if missing:
        raise CorpusError(f"{path}: front matter lacks {', '.join(missing)}")
    return front_matter, "\n".join(lines[end + 1 :])


def split_clauses(body: str, source_id: str, path: str | Path = "<text>") -> list[tuple[str, str, str]]:
    """Return ``(clause_id, heading, text)`` for each clause heading in `body`.

    Text before the first clause heading (the synthetic-data notice and the
    document title) belongs to no clause and is dropped. A clause runs until
    the next clause heading or the end of the document.
    """
    sections: list[tuple[str, str, list[str]]] = []
    for line in body.split("\n"):
        match = _CLAUSE_HEADING.match(line.rstrip())
        if match:
            clause_id = match.group("clause_id")
            if not clause_id.startswith(f"{source_id}-C"):
                raise CorpusError(
                    f"{path}: clause {clause_id} does not belong to {source_id}; "
                    "a citation to it would name the wrong document"
                )
            sections.append((clause_id, match.group("heading").strip(), []))
        elif sections:
            sections[-1][2].append(line)

    result = []
    for clause_id, heading, lines in sections:
        clause_text = "\n".join(lines).strip()
        if not clause_text:
            raise CorpusError(f"{path}: clause {clause_id} has no text")
        result.append((clause_id, heading, clause_text))
    return result


def _verify_against_register(
    path: Path,
    source_id: str,
    version: str,
    normalised_text: str,
    register: dict[str, dict[str, str]],
) -> None:
    entry = register.get(source_id)
    if entry is None:
        raise CorpusError(f"{path}: {source_id} is not in the source register")

    if entry.get("version") != version:
        raise CorpusError(
            f"{path}: front matter says version {version} but the register says "
            f"{entry.get('version')}"
        )

    actual = hashlib.sha256(normalised_text.encode("utf-8")).hexdigest()
    if actual != entry.get("checksum_sha256"):
        raise CorpusError(
            f"{path}: content does not match the registered checksum. The document "
            "was edited after review; update the register once the change is reviewed."
        )


def _reject_duplicate_clause_ids(clauses: list[Clause]) -> None:
    seen: set[str] = set()
    for clause in clauses:
        if clause.clause_id in seen:
            raise CorpusError(f"clause {clause.clause_id} appears more than once")
        seen.add(clause.clause_id)
