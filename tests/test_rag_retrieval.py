"""Embedding, indexing and retrieval (RAG stages 1 and 2), fully offline.

Qdrant runs in local in-memory mode, so no server and no network. The embedder
is a word-overlap fake, so no model is downloaded. Score thresholds used here
suit the fake; the production cutoff is measured against the real model and
documented in retriever.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("qdrant_client", reason='install with pip install -e ".[rag]"')

from rag_support import WordOverlapEmbedder  # noqa: E402

from procurement_agent.rag.corpus import load_corpus  # noqa: E402
from procurement_agent.rag.embedder import FastEmbedEmbedder, clause_passage  # noqa: E402
from procurement_agent.rag.index import IndexError_, PolicyIndex  # noqa: E402
from procurement_agent.rag.retriever import (  # noqa: E402
    DEFAULT_ITEM_MIN_SCORE,
    DEFAULT_MIN_SCORE,
    DEFAULT_TOP_K,
    GENERAL_CATEGORIES,
    ITEM_CATEGORIES,
    RetrievalError,
    RetrievalRequest,
    Retriever,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def clauses():
    return load_corpus(ROOT / "knowledge" / "corpus", ROOT / "knowledge" / "source-register.csv")


@pytest.fixture
def embedder():
    return WordOverlapEmbedder()


@pytest.fixture
def index(clauses, embedder):
    built = PolicyIndex()
    built.build(clauses, embedder)
    return built


CEMENT = RetrievalRequest(
    item="120 bags of cement", category="building materials", estimated_total=4_140_000
)


# --- defaults ----------------------------------------------------------------


def test_defaults_are_the_measured_values():
    """Measured against the real model; see the table in retriever.py."""
    assert DEFAULT_TOP_K == 5
    assert DEFAULT_MIN_SCORE == 0.50
    assert DEFAULT_ITEM_MIN_SCORE == 0.58


# --- the query ---------------------------------------------------------------


def test_the_query_carries_item_category_and_total():
    assert CEMENT.to_query() == (
        "Purchase of 120 bags of cement, category building materials, "
        "estimated total UGX 4,140,000"
    )


def test_a_decimal_total_is_formatted_not_rounded():
    """This module formats figures and never changes them."""
    request = RetrievalRequest(item="USB drives", category="electronics",
                               estimated_total=212.5, currency="USD")
    assert request.to_query().endswith("estimated total USD 212.5")


def test_the_total_is_optional():
    request = RetrievalRequest(item="cement", category="building materials")
    assert "estimated total" not in request.to_query()


@pytest.mark.parametrize("field", ["item", "category"])
def test_empty_request_fields_are_rejected(field):
    values = {"item": "cement", "category": "building materials", field: "  "}
    with pytest.raises(RetrievalError, match=field):
        RetrievalRequest(**values)


# --- the index ---------------------------------------------------------------


def test_the_clause_passage_names_its_subject():
    """SPEC-001-C01's body never says "cement"; only its heading does."""
    by_id = {c.clause_id: c for c in load_corpus(ROOT / "knowledge" / "corpus",
                                                 ROOT / "knowledge" / "source-register.csv")}
    passage = clause_passage(by_id["SPEC-001-C01"])
    assert "Cement" in passage
    assert passage.startswith("Cement and Masonry Product Specifications. Cement.")


def test_every_clause_is_indexed_once(index, clauses):
    assert len(index) == len(clauses)


def test_a_rebuild_replaces_rather_than_duplicates(index, clauses, embedder):
    index.build(clauses, embedder)
    hits = index.search(embedder.embed_query("cement"), top_k=len(clauses) * 2)
    assert len(hits) == len(clauses)


def test_search_returns_complete_citable_clauses(index, clauses, embedder):
    """The payload round-trips, so what the model sees is exactly what was indexed."""
    originals = {c.clause_id: c for c in clauses}
    for hit in index.search(embedder.embed_query("quotation"), top_k=5):
        assert hit.clause == originals[hit.clause.clause_id]


def test_results_are_best_first_and_capped_at_top_k(index, embedder):
    hits = index.search(embedder.embed_query("cement bag strength grade"), top_k=3)
    assert len(hits) == 3
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)


def test_searching_before_building_is_an_error(embedder):
    unbuilt, vector = PolicyIndex(), embedder.embed_query("cement")
    with pytest.raises(IndexError_, match="not been built"):
        unbuilt.search(vector, top_k=5)


def test_an_empty_index_is_refused(embedder):
    unbuilt = PolicyIndex()
    with pytest.raises(IndexError_, match="empty"):
        unbuilt.build([], embedder)


# --- retrieval ---------------------------------------------------------------


def _open(index, embedder, **kwargs):
    """A retriever with every cutoff disabled unless a test sets one."""
    settings = {"min_score": -1.0, "item_min_score": -1.0, **kwargs}
    return Retriever(index, embedder, **settings)


def test_the_two_searches_never_mix_categories(index, embedder):
    result = _open(index, embedder).retrieve(CEMENT)

    assert result.general and result.item
    assert {h.clause.category for h in result.general} <= set(GENERAL_CATEGORIES)
    assert {h.clause.category for h in result.item} <= set(ITEM_CATEGORIES)


def test_the_category_filter_runs_inside_the_search(index, embedder):
    """top_k counts matching clauses, so a filtered search still fills up."""
    hits = index.search(embedder.embed_query("quotation"), top_k=5, categories=ITEM_CATEGORIES)
    assert len(hits) == 5
    assert all(h.clause.category == "product_specification" for h in hits)


def test_a_cement_purchase_retrieves_the_cement_specification(index, embedder):
    """Membership, not rank. The word-overlap fake is too crude to rank well;
    ranking quality belongs to the real model and to the RAG evaluation."""
    result = _open(index, embedder).retrieve(CEMENT)

    assert result.found
    assert result.absence_notes == ()
    assert "SPEC-001-C01" in [h.clause.clause_id for h in result.item]


def test_general_rules_survive_when_no_item_rule_matches(index, embedder):
    """An airline ticket still needs quotations; it just has no specification."""
    request = RetrievalRequest(item="return flights to Nairobi", category="travel",
                               estimated_total=3_000_000)
    result = _open(index, embedder, item_min_score=0.99).retrieve(request)

    assert result.found
    assert result.general
    assert result.item == ()
    assert result.policy_absence_note is None
    assert result.item_absence_note == (
        "No product specification in the Policy Corpus was found for "
        "return flights to Nairobi (travel)."
    )
    assert result.absence_notes == (result.item_absence_note,)


def test_when_nothing_matches_both_absence_notes_are_given(index, embedder):
    """Requirement 7.3: say no clause was found, never omit or invent one."""
    request = RetrievalRequest(item="matooke and groundnut sauce", category="catering")
    result = _open(index, embedder, min_score=0.99, item_min_score=0.99).retrieve(request)

    assert not result.found
    assert result.clauses == ()
    assert result.absence_notes == (
        "No procurement policy or procedure clause in the Policy Corpus was found "
        "for matooke and groundnut sauce (catering).",
        "No product specification in the Policy Corpus was found for "
        "matooke and groundnut sauce (catering).",
    )


def test_clauses_under_the_cutoff_are_kept_for_the_trace(index, embedder):
    """Evaluation needs to see what nearly matched, to tune the cutoffs."""
    result = _open(index, embedder, min_score=0.99, item_min_score=0.99).retrieve(CEMENT)

    assert not result.found
    assert len(result.below_cutoff) == 2 * DEFAULT_TOP_K
    assert all(hit.score < 0.99 for hit in result.below_cutoff)


def test_each_search_has_its_own_cutoff(index, embedder):
    everything = _open(index, embedder).retrieve(CEMENT)
    general_middle = everything.general[2].score
    item_middle = everything.item[2].score

    result = _open(index, embedder, min_score=general_middle,
                   item_min_score=item_middle).retrieve(CEMENT)

    assert all(h.score >= general_middle for h in result.general)
    assert all(h.score >= item_middle for h in result.item)
    assert len(result.general) + len(result.item) + len(result.below_cutoff) == 2 * DEFAULT_TOP_K


def test_general_rules_are_listed_before_item_rules(index, embedder):
    result = _open(index, embedder).retrieve(CEMENT)
    assert result.clauses == result.general + result.item


def test_the_result_records_how_it_was_produced(index, embedder):
    result = Retriever(index, embedder, top_k=4, min_score=0.1,
                       item_min_score=0.2).retrieve(CEMENT)

    assert result.query == CEMENT.to_query()
    assert result.top_k == 4
    assert result.min_score == 0.1
    assert result.item_min_score == 0.2
    assert result.embedding_model == "test/word-overlap"


def test_a_query_embedder_that_differs_from_the_index_is_refused(index):
    """Vectors from two models are not comparable, yet Qdrant would still rank them."""
    mismatched = Retriever(index, WordOverlapEmbedder(model_name="some/other-model"))
    with pytest.raises(IndexError_, match="built with"):
        mismatched.retrieve(CEMENT)


@pytest.mark.parametrize("kwargs, message", [
    ({"top_k": 0}, "top_k"),
    ({"min_score": 1.5}, "min_score"),
    ({"item_min_score": -2}, "item_min_score"),
])
def test_invalid_retriever_settings_are_rejected(index, embedder, kwargs, message):
    with pytest.raises(RetrievalError, match=message):
        Retriever(index, embedder, **kwargs)


# --- the FastEmbed adapter, with no model loaded -----------------------------


class _FakeFastEmbedModel:
    """Mimics TextEmbedding: generators of array-likes, separate query/passage paths."""

    def __init__(self):
        self.calls = []

    def passage_embed(self, texts):
        self.calls.append(("passage", list(texts)))
        return (_ArrayLike([1, 0]) for _ in texts)

    def query_embed(self, texts):
        self.calls.append(("query", list(texts)))
        return (_ArrayLike([0, 1]) for _ in texts)


class _ArrayLike:
    def __init__(self, values):
        self._values = values

    def __iter__(self):
        return iter(self._values)


def test_fastembed_adapter_uses_the_query_path_for_queries():
    """bge models expect a query instruction that passage embedding omits."""
    model = _FakeFastEmbedModel()
    embedder = FastEmbedEmbedder(model=model)

    assert embedder.embed_query("cement") == [0.0, 1.0]
    assert embedder.embed_passages(["a", "b"]) == [[1.0, 0.0], [1.0, 0.0]]
    assert model.calls == [("query", ["cement"]), ("passage", ["a", "b"])]


def test_fastembed_adapter_returns_plain_floats():
    vector = FastEmbedEmbedder(model=_FakeFastEmbedModel()).embed_query("x")
    assert all(type(value) is float for value in vector)
