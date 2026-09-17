"""Corpus loading and clause chunking (RAG stage 1)."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from procurement_agent.rag.corpus import (
    INDEXED_FOLDERS,
    CorpusError,
    load_corpus,
    parse_front_matter,
    split_clauses,
)

ROOT = Path(__file__).resolve().parents[1]
REAL_CORPUS = ROOT / "knowledge" / "corpus"
REAL_REGISTER = ROOT / "knowledge" / "source-register.csv"

REGISTER_FIELDS = ["source_id", "version", "checksum_sha256", "file_path"]


# --- helpers -----------------------------------------------------------------


def _document(source_id="POL-900", version="1.0", clauses=None, title="Test Policy"):
    if clauses is None:
        clauses = [(f"{source_id}-C01", "First rule", "Rule one text.")]
    lines = [
        "---",
        f"source_id: {source_id}",
        f"title: {title}",
        "category: policy",
        f"version: {version}",
        "review_status: approved",
        "---",
        "",
        "> Synthetic academic test data. This document does not authorize purchasing.",
        "",
        f"# {title}",
        "",
    ]
    for clause_id, heading, text in clauses:
        lines += [f"## {clause_id} {heading}", "", text, ""]
    return "\n".join(lines)


def _write_corpus(tmp_path, documents, register_overrides=None, folder="policies"):
    """Write documents and a register whose checksums match them."""
    corpus = tmp_path / "corpus"
    for name in INDEXED_FOLDERS:
        (corpus / name).mkdir(parents=True, exist_ok=True)

    rows = []
    for source_id, text in documents.items():
        path = corpus / folder / f"{source_id}.md"
        path.write_text(text, encoding="utf-8", newline="\n")
        version = parse_front_matter(text)[0]["version"]
        rows.append(
            {
                "source_id": source_id,
                "version": version,
                "checksum_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "file_path": path.as_posix(),
            }
        )
    for row in rows:
        row.update((register_overrides or {}).get(row["source_id"], {}))

    register = tmp_path / "register.csv"
    with register.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGISTER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return corpus, register


# --- the real corpus ---------------------------------------------------------


def test_every_registered_document_in_an_indexed_folder_is_loaded():
    """Derived from the register, so adding a reviewed policy does not break this."""
    with REAL_REGISTER.open(encoding="utf-8", newline="") as handle:
        expected = {
            row["source_id"]
            for row in csv.DictReader(handle)
            if any(f"knowledge/corpus/{folder}/" in row["file_path"] for folder in INDEXED_FOLDERS)
        }

    clauses = load_corpus(REAL_CORPUS, REAL_REGISTER)

    assert expected, "the register lists no documents in the indexed folders"
    assert {c.source_id for c in clauses} == expected


def test_excluded_folders_never_reach_the_index():
    """Quotations carry the QUO-005 injection; supplier terms have no clause IDs."""
    prefixes = {c.source_id.split("-")[0] for c in load_corpus(REAL_CORPUS, REAL_REGISTER)}
    assert prefixes == {"POL", "PRO", "SPEC"}


def test_every_clause_carries_what_a_citation_needs():
    for clause in load_corpus(REAL_CORPUS, REAL_REGISTER):
        assert clause.clause_id.startswith(f"{clause.source_id}-C")
        assert clause.version
        assert clause.title
        assert clause.text


def test_a_real_clause_is_split_correctly():
    by_id = {c.clause_id: c for c in load_corpus(REAL_CORPUS, REAL_REGISTER)}
    clause = by_id["POL-001-C01"]

    assert clause.title == "Competitive Quotation Policy"
    assert clause.version == "1.0"
    assert clause.heading == "Low value purchases"
    assert clause.text.startswith("Purchases with an estimated total cost below UGX 500,000")
    assert "POL-001-C02" not in clause.text
    assert clause.citation == "Competitive Quotation Policy v1.0, POL-001-C01"


def test_file_paths_are_repository_relative_even_from_an_absolute_corpus_dir():
    """An absolute path would leak a home directory into every trace."""
    assert REAL_CORPUS.is_absolute()
    for clause in load_corpus(REAL_CORPUS, REAL_REGISTER):
        assert clause.file_path.startswith("knowledge/corpus/")
        assert clause.file_path.endswith(f"/{clause.source_id}.md")


def test_the_synthetic_data_notice_is_not_part_of_any_clause():
    for clause in load_corpus(REAL_CORPUS, REAL_REGISTER):
        assert "Synthetic academic test data" not in clause.text


# --- line endings ------------------------------------------------------------


def test_windows_line_endings_still_match_the_register(tmp_path):
    """Git on Windows checks the corpus out with CRLF; the register hashed LF."""
    text = _document()
    corpus, register = _write_corpus(tmp_path, {"POL-900": text})
    path = corpus / "policies" / "POL-900.md"
    path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))

    clauses = load_corpus(corpus, register)

    assert [c.clause_id for c in clauses] == ["POL-900-C01"]
    assert "\r" not in clauses[0].text


# --- the register ------------------------------------------------------------


def test_an_edited_document_is_rejected(tmp_path):
    """A clause nobody reviewed must not be indexed and cited."""
    corpus, register = _write_corpus(tmp_path, {"POL-900": _document()})
    path = corpus / "policies" / "POL-900.md"
    path.write_text(_document().replace("Rule one text.", "Rule one, quietly changed."))

    with pytest.raises(CorpusError, match="checksum"):
        load_corpus(corpus, register)


def test_an_unregistered_document_is_rejected(tmp_path):
    corpus, register = _write_corpus(tmp_path, {"POL-900": _document()})
    (corpus / "policies" / "POL-901.md").write_text(_document("POL-901"), encoding="utf-8")

    with pytest.raises(CorpusError, match="not in the source register"):
        load_corpus(corpus, register)


def test_a_version_disagreeing_with_the_register_is_rejected(tmp_path):
    corpus, register = _write_corpus(
        tmp_path, {"POL-900": _document()}, register_overrides={"POL-900": {"version": "2.0"}}
    )
    with pytest.raises(CorpusError, match="version"):
        load_corpus(corpus, register)


def test_a_missing_register_is_rejected(tmp_path):
    corpus, _ = _write_corpus(tmp_path, {"POL-900": _document()})
    with pytest.raises(CorpusError, match="register"):
        load_corpus(corpus, tmp_path / "nope.csv")


# --- document structure ------------------------------------------------------


def test_source_id_must_match_the_file_name(tmp_path):
    corpus, register = _write_corpus(tmp_path, {"POL-900": _document()})
    (corpus / "policies" / "POL-900.md").rename(corpus / "policies" / "POL-999.md")

    with pytest.raises(CorpusError, match="file name"):
        load_corpus(corpus, register)


def test_a_clause_from_another_document_is_rejected(tmp_path):
    """Otherwise its citation would name the wrong document."""
    text = _document(clauses=[("POL-123-C01", "Stray", "Copied from elsewhere.")])
    corpus, register = _write_corpus(tmp_path, {"POL-900": text})

    with pytest.raises(CorpusError, match="does not belong"):
        load_corpus(corpus, register)


def test_duplicate_clause_ids_are_rejected(tmp_path):
    text = _document(clauses=[("POL-900-C01", "A", "One."), ("POL-900-C01", "B", "Two.")])
    corpus, register = _write_corpus(tmp_path, {"POL-900": text})

    with pytest.raises(CorpusError, match="more than once"):
        load_corpus(corpus, register)


def test_a_document_with_no_clauses_is_rejected(tmp_path):
    corpus, register = _write_corpus(tmp_path, {"POL-900": _document(clauses=[])})

    with pytest.raises(CorpusError, match="no clause headings"):
        load_corpus(corpus, register)


def test_an_empty_clause_is_rejected(tmp_path):
    text = _document(clauses=[("POL-900-C01", "Empty", "")])
    corpus, register = _write_corpus(tmp_path, {"POL-900": text})

    with pytest.raises(CorpusError, match="no text"):
        load_corpus(corpus, register)


def test_front_matter_is_required():
    with pytest.raises(CorpusError, match="missing front matter"):
        parse_front_matter("# No front matter here")


def test_front_matter_must_carry_what_a_citation_needs():
    with pytest.raises(CorpusError, match="version"):
        parse_front_matter("---\nsource_id: POL-900\ntitle: T\n---\nbody")


def test_a_clause_runs_until_the_next_heading():
    body = "## POL-900-C01 One\n\nFirst.\n\n## POL-900-C02 Two\n\nSecond.\nMore second.\n"
    assert split_clauses(body, "POL-900") == [
        ("POL-900-C01", "One", "First."),
        ("POL-900-C02", "Two", "Second.\nMore second."),
    ]
