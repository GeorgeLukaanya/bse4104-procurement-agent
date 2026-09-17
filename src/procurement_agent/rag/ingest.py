"""Offline corpus preparation (RAG stage 1), and opening its result at runtime.

    python -m procurement_agent.rag.ingest

The architecture's first stage, run once and ahead of any purchase:

    Canonical Policy Store   knowledge/source-register.csv, the source of truth
    Policy Corpus            knowledge/corpus/{policies,procedures,product-specifications}
    Document Loader          corpus.load_corpus, verified against the register
    Chunking + Metadata      one chunk per clause, with document, version, clause ID
    Embedding Model          embedder.FastEmbedEmbedder
    Vector Index             Qdrant on disk, plus a manifest written here

Runtime retrieval then *opens* that index instead of embedding the corpus on
every request.

Why a manifest, and why runtime checks it
-----------------------------------------
A stored index can outlive the corpus it was built from. If a policy is revised
and reviewed after ingestion, an index that is simply reopened would keep
retrieving the old wording, and a citation to it would pass the citation
validator, because the validator trusts what retrieval supplied. Nothing would
look wrong.

So ingestion writes a manifest naming the embedding model and a fingerprint of
every indexed clause, and `open_index` reloads the corpus (cheap: no
embedding) and refuses an index whose fingerprint no longer matches. It also
refuses a missing index. Both surface as the architecture's "corpus
unavailable, pause, allow retry" branch: nothing is retrieved, and the message
says what to run.

The manifest is written last. If ingestion fails partway there is no manifest,
so a half-built index reads as not built rather than as usable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .corpus import (
    DEFAULT_CORPUS_DIR,
    DEFAULT_SOURCE_REGISTER,
    INDEXED_FOLDERS,
    Clause,
    CorpusError,
    load_corpus,
)
from .embedder import Embedder, EmbedderUnavailable, FastEmbedEmbedder
from .index import DEFAULT_COLLECTION, IndexError_, PolicyIndex

# Derived data, rebuilt by running ingest, so it lives in the git-ignored
# .cache directory beside the embedding model and the extraction cache.
DEFAULT_INDEX_DIR = Path(".cache") / "policy-index"
MANIFEST_NAME = "manifest.json"
MANIFEST_FORMAT = 1


class IndexNotBuilt(IndexError_):
    """No usable index exists at the given location."""


class StaleIndex(IndexError_):
    """The index no longer matches the corpus it is meant to represent."""


@dataclass(frozen=True)
class IndexManifest:
    format: int
    collection: str
    embedding_model: str
    corpus_fingerprint: str
    indexed_folders: list[str]
    documents: dict[str, str]
    clause_count: int
    built_at: str

    @classmethod
    def read(cls, path: Path) -> "IndexManifest":
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format") != MANIFEST_FORMAT:
            raise StaleIndex(
                f"index manifest format {data.get('format')!r} is not {MANIFEST_FORMAT}; "
                "run ingest again"
            )
        return cls(**data)

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")


def corpus_fingerprint(clauses: Sequence[Clause]) -> str:
    """SHA-256 over everything about the clauses that retrieval can return.

    Clause order does not matter; any change to an indexed clause's text,
    heading, title, version or identity does.
    """
    material = sorted(
        (c.source_id, c.version, c.clause_id, c.title, c.heading, c.category, c.text)
        for c in clauses
    )
    canonical = json.dumps(material, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ingest(
    embedder: Embedder,
    corpus_dir: str | Path = DEFAULT_CORPUS_DIR,
    register_path: str | Path = DEFAULT_SOURCE_REGISTER,
    index_dir: str | Path = DEFAULT_INDEX_DIR,
    folders: Sequence[str] = INDEXED_FOLDERS,
) -> IndexManifest:
    """Build the persisted index from the verified corpus and write its manifest."""
    index_path = Path(index_dir)
    manifest_path = index_path / MANIFEST_NAME

    clauses = load_corpus(corpus_dir, register_path, folders)

    index_path.mkdir(parents=True, exist_ok=True)
    # Removed first, written last: an interrupted build must not look usable.
    manifest_path.unlink(missing_ok=True)

    with PolicyIndex(location=str(index_path)) as index:
        index.build(clauses, embedder)

    documents: dict[str, str] = {}
    for clause in clauses:
        documents[clause.source_id] = clause.version

    manifest = IndexManifest(
        format=MANIFEST_FORMAT,
        collection=DEFAULT_COLLECTION,
        embedding_model=embedder.model_name,
        corpus_fingerprint=corpus_fingerprint(clauses),
        indexed_folders=list(folders),
        documents=dict(sorted(documents.items())),
        clause_count=len(clauses),
        built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    manifest.write(manifest_path)
    return manifest


def open_index(
    corpus_dir: str | Path = DEFAULT_CORPUS_DIR,
    register_path: str | Path = DEFAULT_SOURCE_REGISTER,
    index_dir: str | Path = DEFAULT_INDEX_DIR,
) -> tuple[PolicyIndex, IndexManifest]:
    """Open a persisted index after proving it still matches the corpus.

    The caller owns the returned index and must close it.
    """
    index_path = Path(index_dir)
    manifest_path = index_path / MANIFEST_NAME
    if not manifest_path.is_file():
        raise IndexNotBuilt(
            f"no policy index at {index_path}. Build it first with "
            "`python -m procurement_agent.rag.ingest`."
        )
    manifest = IndexManifest.read(manifest_path)

    clauses = load_corpus(corpus_dir, register_path, manifest.indexed_folders)
    current = corpus_fingerprint(clauses)
    if current != manifest.corpus_fingerprint:
        raise StaleIndex(_describe_drift(manifest, clauses))

    index = PolicyIndex(location=str(index_path), collection=manifest.collection)
    try:
        index.attach(manifest.embedding_model)
        if len(index) != manifest.clause_count:
            raise StaleIndex(
                f"the index holds {len(index)} clauses but its manifest records "
                f"{manifest.clause_count}; run ingest again"
            )
    except BaseException:
        index.close()
        raise
    return index, manifest


def _describe_drift(manifest: IndexManifest, clauses: Sequence[Clause]) -> str:
    now: dict[str, str] = {}
    for clause in clauses:
        now[clause.source_id] = clause.version
    added = sorted(set(now) - set(manifest.documents))
    removed = sorted(set(manifest.documents) - set(now))
    revised = sorted(
        doc for doc in set(now) & set(manifest.documents) if now[doc] != manifest.documents[doc]
    )
    parts = []
    if added:
        parts.append(f"added {', '.join(added)}")
    if removed:
        parts.append(f"removed {', '.join(removed)}")
    if revised:
        parts.append(f"new version of {', '.join(revised)}")
    what = "; ".join(parts) if parts else "clause text changed without a version change"
    return (
        f"the policy index is out of date: the corpus changed since it was built at "
        f"{manifest.built_at} ({what}). Run `python -m procurement_agent.rag.ingest` again."
    )


def main(argv: Sequence[str] | None = None, embedder: Embedder | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="procurement-policy-ingest",
        description="Build the policy vector index from the verified corpus (RAG stage 1).",
    )
    parser.add_argument("--index-dir", default=str(DEFAULT_INDEX_DIR),
                        help="where the index is written (default: %(default)s)")
    parser.add_argument("--corpus-dir", default=str(DEFAULT_CORPUS_DIR))
    parser.add_argument("--source-register", default=str(DEFAULT_SOURCE_REGISTER))
    args = parser.parse_args(argv)

    started = time.monotonic()
    try:
        embedder = embedder or FastEmbedEmbedder()
        manifest = ingest(embedder, args.corpus_dir, args.source_register, args.index_dir)
    except (CorpusError, EmbedderUnavailable, IndexError_) as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("No usable index was written.", file=sys.stderr)
        return 1

    print(f"indexed {manifest.clause_count} clauses from {len(manifest.documents)} documents "
          f"in {time.monotonic() - started:.1f}s")
    print(f"  folders         : {', '.join(manifest.indexed_folders)}")
    print(f"  documents       : "
          f"{', '.join(f'{doc} v{version}' for doc, version in manifest.documents.items())}")
    print(f"  embedding model : {manifest.embedding_model}")
    print(f"  fingerprint     : {manifest.corpus_fingerprint[:16]}...")
    print(f"  written to      : {Path(args.index_dir) / MANIFEST_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
