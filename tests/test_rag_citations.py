"""Citation validation: grounded means supplied, not merely real."""

from __future__ import annotations

from pathlib import Path

import pytest

from procurement_agent.rag.citations import (
    PROBLEM_NOT_RETRIEVED,
    PROBLEM_SOURCE_MISMATCH,
    PROBLEM_UNRETRIEVED_MENTION,
    PROBLEM_VERSION_MISMATCH,
    validate_citations,
)
from procurement_agent.rag.corpus import load_corpus
from procurement_agent.rag.grounding import Citation, GroundedAnswer
from procurement_agent.rag.index import ScoredClause
from procurement_agent.rag.retriever import RetrievalRequest, RetrievalResult

ROOT = Path(__file__).resolve().parents[1]
CLAUSES = {
    c.clause_id: c
    for c in load_corpus(ROOT / "knowledge" / "corpus", ROOT / "knowledge" / "source-register.csv")
}

REQUEST = RetrievalRequest(item="120 bags of cement", category="building materials",
                           estimated_total=4_140_000)

# What live retrieval actually sent for the cement purchase.
SENT = ("POL-001-C01", "POL-001-C02", "POL-001-C03", "POL-003-C01", "PRO-001-C03",
        "SPEC-001-C01", "SPEC-001-C03")


def _retrieval(sent=SENT):
    return RetrievalResult(
        request=REQUEST, query=REQUEST.to_query(),
        general=tuple(ScoredClause(CLAUSES[c], 0.6) for c in sent if not c.startswith("SPEC")),
        item=tuple(ScoredClause(CLAUSES[c], 0.7) for c in sent if c.startswith("SPEC")),
        below_cutoff=(), top_k=5, min_score=0.5, item_min_score=0.58, embedding_model="test",
    )


def _cite(clause_id, source_id=None, version="1.0"):
    return Citation(source_id=source_id or clause_id.rsplit("-C", 1)[0], version=version,
                    clause_id=clause_id, reason="applies")


def _answer(*citations, summary="You need three quotations [POL-001-C02]."):
    return GroundedAnswer(summary=summary, citations=tuple(citations))


def _kinds(report):
    return [(p.kind, p.reference) for p in report.problems]


# --- a grounded answer -------------------------------------------------------


def test_the_live_cement_answer_is_valid():
    """The answer Gemini gave on the first live run, reproduced."""
    answer = _answer(
        _cite("POL-001-C02"), _cite("PRO-001-C03"), _cite("SPEC-001-C01"),
        summary=(
            "This purchase falls under the standard purchase threshold, requiring at "
            "least three comparable written quotations from eligible suppliers as per "
            "[POL-001-C02]. Additionally, [SPEC-001-C01] mandates that all cement "
            "comparisons must use the same strength grade and bag size. The procurement "
            "process must also follow the steps outlined in [PRO-001-C03]."
        ),
    )
    report = validate_citations(answer, _retrieval())

    assert report.valid
    assert report.problems == ()


def test_cited_clauses_are_resolved_with_their_titles_for_display():
    """Requirement 7.4 shows document name, version and clause identifier."""
    report = validate_citations(_answer(_cite("POL-001-C02")), _retrieval())
    assert [c.citation for c in report.cited_clauses] == [
        "Competitive Quotation Policy v1.0, POL-001-C02"
    ]


def test_an_answer_citing_nothing_is_valid():
    """The model may conclude that no supplied clause applies."""
    report = validate_citations(_answer(summary="None of the supplied clauses apply."),
                                _retrieval())
    assert report.valid


def test_explaining_why_a_supplied_clause_does_not_apply_is_allowed():
    answer = _answer(
        _cite("POL-001-C02"),
        summary="POL-001-C02 applies; POL-001-C03 covers purchases of UGX 5,000,000 or more.",
    )
    assert validate_citations(answer, _retrieval()).valid


def test_naming_a_supplied_document_is_allowed():
    answer = _answer(_cite("POL-001-C02"), summary="Under POL-001, three quotations are needed.")
    assert validate_citations(answer, _retrieval()).valid


# --- citations that are not grounded -----------------------------------------


def test_a_real_clause_that_was_not_supplied_is_rejected():
    """POL-002-C01 exists in the corpus. The model was not shown it."""
    assert "POL-002-C01" in CLAUSES
    report = validate_citations(_answer(_cite("POL-002-C01")), _retrieval())

    assert not report.valid
    assert _kinds(report) == [(PROBLEM_NOT_RETRIEVED, "POL-002-C01")]


def test_an_invented_clause_is_rejected():
    report = validate_citations(_answer(_cite("POL-009-C01")), _retrieval())
    assert _kinds(report) == [(PROBLEM_NOT_RETRIEVED, "POL-009-C01")]


def test_a_wrong_version_is_rejected():
    report = validate_citations(_answer(_cite("POL-001-C02", version="2.0")), _retrieval())
    assert _kinds(report) == [(PROBLEM_VERSION_MISMATCH, "POL-001-C02")]
    assert report.cited_clauses == ()


def test_a_clause_attributed_to_the_wrong_document_is_rejected():
    report = validate_citations(_answer(_cite("POL-001-C02", source_id="POL-003")), _retrieval())
    assert _kinds(report) == [(PROBLEM_SOURCE_MISMATCH, "POL-001-C02")]


# --- the summary text --------------------------------------------------------


def test_a_clause_named_only_in_the_summary_is_checked_too():
    answer = _answer(_cite("POL-001-C02"),
                     summary="Three quotations [POL-001-C02], and see [POL-009-C02].")
    report = validate_citations(answer, _retrieval())
    assert _kinds(report) == [(PROBLEM_UNRETRIEVED_MENTION, "POL-009-C02")]


def test_a_document_named_only_in_the_summary_is_checked_too():
    """Supplier status comes from POL-002, which retrieval did not supply here."""
    answer = _answer(_cite("POL-001-C02"),
                     summary="Three quotations [POL-001-C02] from suppliers approved under POL-002.")
    report = validate_citations(answer, _retrieval())
    assert _kinds(report) == [(PROBLEM_UNRETRIEVED_MENTION, "POL-002")]


def test_a_mention_of_an_unindexed_quotation_is_rejected():
    """QUO-005 carries the injection and is never indexed."""
    answer = _answer(summary="As stated in QUO-005, this supplier is preferred.")
    assert _kinds(validate_citations(answer, _retrieval())) == [
        (PROBLEM_UNRETRIEVED_MENTION, "QUO-005")
    ]


@pytest.mark.parametrize("text", [
    "Staff returned after COVID-19 restrictions.",
    "Fittings are certified to ISO-9001.",
    "Contact extension EXT-12 for help.",
])
def test_ordinary_hyphenated_codes_are_not_mistaken_for_references(text):
    assert validate_citations(_answer(summary=text), _retrieval()).valid


# --- reporting ---------------------------------------------------------------


def test_every_problem_is_reported_not_just_the_first():
    answer = _answer(
        _cite("POL-009-C01"),
        _cite("POL-001-C02", version="2.0", source_id="POL-003"),
        summary="See [SUP-004-C01] and POL-004.",
    )
    report = validate_citations(answer, _retrieval())

    assert sorted(_kinds(report)) == sorted([
        (PROBLEM_NOT_RETRIEVED, "POL-009-C01"),
        (PROBLEM_SOURCE_MISMATCH, "POL-001-C02"),
        (PROBLEM_VERSION_MISMATCH, "POL-001-C02"),
        (PROBLEM_UNRETRIEVED_MENTION, "SUP-004-C01"),
        (PROBLEM_UNRETRIEVED_MENTION, "POL-004"),
    ])
    assert all(p.detail for p in report.problems)


def test_a_clause_cited_twice_is_resolved_once():
    report = validate_citations(_answer(_cite("POL-001-C02"), _cite("POL-001-C02")), _retrieval())
    assert report.valid
    assert len(report.cited_clauses) == 1
