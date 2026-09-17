"""Offline ingestion (RAG stage 1) and the checks that guard its output at runtime."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("qdrant_client", reason='install with pip install -e ".[rag]"')

from rag_support import GroundedStubBackend, WordOverlapEmbedder  # noqa: E402

from procurement_agent.rag import cli, ingest as ingest_module  # noqa: E402
from procurement_agent.rag.corpus import INDEXED_FOLDERS, CorpusError, load_corpus  # noqa: E402
from procurement_agent.rag.index import IndexError_  # noqa: E402
from procurement_agent.rag.ingest import (  # noqa: E402
    MANIFEST_NAME,
    IndexNotBuilt,
    StaleIndex,
    corpus_fingerprint,
    ingest,
    open_index,
)
from procurement_agent.rag.retriever import RetrievalRequest, Retriever  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "knowledge" / "corpus"
REGISTER = ROOT / "knowledge" / "source-register.csv"


@pytest.fixture
def corpus_copy(tmp_path):
    """A private copy of the indexed corpus and register, safe to edit."""
    corpus = tmp_path / "corpus"
    for folder in INDEXED_FOLDERS:
        shutil.copytree(CORPUS / folder, corpus / folder)
    register = tmp_path / "register.csv"
    shutil.copy(REGISTER, register)
    return corpus, register


def _revise(corpus, register, source_id, old, new, version=None):
    """Edit a document and update the register as a reviewed change would."""
    path = next(corpus.rglob(f"{source_id}.md"))
    text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
    assert old in text
    text = text.replace(old, new)
    if version:
        text = text.replace("version: 1.0", f"version: {version}", 1)
    path.write_bytes(text.encode("utf-8"))

    with register.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0])
    for row in rows:
        if row["source_id"] == source_id:
            row["checksum_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if version:
                row["version"] = version
    with register.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


# --- building ----------------------------------------------------------------


def test_ingest_writes_a_manifest_describing_the_index(tmp_path):
    manifest = ingest(WordOverlapEmbedder(), CORPUS, REGISTER, tmp_path / "index")
    clauses = load_corpus(CORPUS, REGISTER)

    assert manifest.clause_count == len(clauses)
    assert manifest.embedding_model == "test/word-overlap"
    assert manifest.indexed_folders == list(INDEXED_FOLDERS)
    assert manifest.documents["POL-001"] == "1.0"
    assert manifest.corpus_fingerprint == corpus_fingerprint(clauses)

    on_disk = json.loads((tmp_path / "index" / MANIFEST_NAME).read_text())
    assert on_disk["clause_count"] == manifest.clause_count


def test_an_ingested_index_is_searchable_after_reopening(tmp_path):
    """Runtime retrieval uses the stored index; it never embeds the corpus."""
    ingest(WordOverlapEmbedder(), CORPUS, REGISTER, tmp_path / "index")

    query_embedder = WordOverlapEmbedder()
    index, manifest = open_index(CORPUS, REGISTER, tmp_path / "index")
    try:
        result = Retriever(index, query_embedder, min_score=-1, item_min_score=-1).retrieve(
            RetrievalRequest(item="cement", category="building materials"))
    finally:
        index.close()

    assert len(index) == manifest.clause_count
    assert result.found
    assert query_embedder.passage_calls == 0


def test_reingesting_replaces_the_index(tmp_path):
    ingest(WordOverlapEmbedder(), CORPUS, REGISTER, tmp_path / "index")
    manifest = ingest(WordOverlapEmbedder(), CORPUS, REGISTER, tmp_path / "index")

    index, _ = open_index(CORPUS, REGISTER, tmp_path / "index")
    index.close()
    assert len(index) == manifest.clause_count


def test_a_failed_ingest_leaves_no_usable_index(tmp_path):
    """The manifest is written last, so a half-built index reads as not built."""
    ingest(WordOverlapEmbedder(), CORPUS, REGISTER, tmp_path / "index")

    class Broken(WordOverlapEmbedder):
        def embed_passages(self, texts):
            raise RuntimeError("model crashed")

    with pytest.raises(RuntimeError):
        ingest(Broken(), CORPUS, REGISTER, tmp_path / "index")
    with pytest.raises(IndexNotBuilt):
        open_index(CORPUS, REGISTER, tmp_path / "index")


# --- guarding the stored index -----------------------------------------------


def test_a_missing_index_says_to_run_ingest(tmp_path):
    with pytest.raises(IndexNotBuilt, match="rag.ingest"):
        open_index(CORPUS, REGISTER, tmp_path / "nothing-here")


def test_a_reviewed_revision_after_ingest_makes_the_index_stale(tmp_path, corpus_copy):
    """Otherwise retrieval keeps serving, and citing, the superseded wording."""
    corpus, register = corpus_copy
    ingest(WordOverlapEmbedder(), corpus, register, tmp_path / "index")

    _revise(corpus, register, "POL-001", "at least three", "at least four", version="1.1")

    with pytest.raises(StaleIndex, match="new version of POL-001"):
        open_index(corpus, register, tmp_path / "index")


def test_a_text_change_without_a_version_bump_is_still_caught(tmp_path, corpus_copy):
    corpus, register = corpus_copy
    ingest(WordOverlapEmbedder(), corpus, register, tmp_path / "index")

    _revise(corpus, register, "SPEC-001", "50 kg bag", "25 kg bag")

    with pytest.raises(StaleIndex, match="without a version change"):
        open_index(corpus, register, tmp_path / "index")


def test_an_unreviewed_edit_is_refused_before_the_index_is_even_checked(tmp_path, corpus_copy):
    corpus, register = corpus_copy
    ingest(WordOverlapEmbedder(), corpus, register, tmp_path / "index")

    path = corpus / "policies" / "POL-001.md"
    path.write_text(path.read_text(encoding="utf-8").replace("three", "two"), encoding="utf-8")

    with pytest.raises(CorpusError, match="checksum"):
        open_index(corpus, register, tmp_path / "index")


def test_an_index_already_open_elsewhere_is_reported_clearly(tmp_path):
    ingest(WordOverlapEmbedder(), CORPUS, REGISTER, tmp_path / "index")
    held, _ = open_index(CORPUS, REGISTER, tmp_path / "index")
    try:
        with pytest.raises(IndexError_, match="open in another process"):
            open_index(CORPUS, REGISTER, tmp_path / "index")
    finally:
        held.close()


# --- the commands ------------------------------------------------------------


def test_the_ingest_command_reports_what_it_built(tmp_path, capsys):
    code = ingest_module.main(
        ["--index-dir", str(tmp_path / "index"), "--corpus-dir", str(CORPUS),
         "--source-register", str(REGISTER)],
        embedder=WordOverlapEmbedder(),
    )
    out = capsys.readouterr().out

    assert code == 0
    assert "indexed" in out and "clauses from 12 documents" in out
    assert "POL-001 v1.0" in out


def test_the_policy_command_stops_when_no_index_exists(tmp_path, capsys):
    backend = GroundedStubBackend()
    code = cli.main(
        ["--item", "cement", "--category", "building materials",
         "--index-dir", str(tmp_path / "missing"), "--corpus-dir", str(CORPUS),
         "--source-register", str(REGISTER), "--trace-log", str(tmp_path / "t.jsonl"),
         "--no-env-file"],
        backend=backend, embedder=WordOverlapEmbedder(),
    )

    assert code == cli.EXIT_USAGE
    assert "rag.ingest" in capsys.readouterr().err
    assert backend.calls == []
