"""The policy pipeline and its command line, end to end and offline.

Every way a requisition or an item can end is exercised: shown, nothing found,
withheld for an ungrounded citation, suppressed, malformed, and failed in
transport. Each run must still leave one trace entry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("qdrant_client", reason='install with pip install -e ".[rag]"')

from rag_support import GroundedStubBackend, WordOverlapEmbedder  # noqa: E402

from procurement_agent.client import DeadlineExceeded, PermanentError, RateLimitError, RetryPolicy  # noqa: E402
from procurement_agent.rag import cli  # noqa: E402
from procurement_agent.rag.corpus import load_corpus  # noqa: E402
from procurement_agent.rag.index import PolicyIndex  # noqa: E402
from procurement_agent.rag.ingest import MANIFEST_NAME, ingest  # noqa: E402
from procurement_agent.rag.pipeline import (  # noqa: E402
    REQUISITION_OK,
    REQUISITION_PARTIAL,
    REQUISITION_WITHHELD,
    STATUS_CALL_FAILED,
    STATUS_CITATION_INVALID,
    STATUS_GENERATION_FAILED,
    STATUS_NO_CLAUSES,
    STATUS_OK,
    STATUS_RATE_LIMITED,
    STATUS_SUPPRESSED,
    PolicyPipeline,
    TraceLog,
)
from procurement_agent.rag.retriever import RetrievalError, RetrievalRequest, Retriever  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "knowledge" / "corpus"
REGISTER = ROOT / "knowledge" / "source-register.csv"
SAMPLE_REQUISITION = ROOT / "fixtures" / "requisitions" / "weekly-reorder.json"

CEMENT = RetrievalRequest(item="120 bags of cement", category="building materials",
                          estimated_total=4_140_000)
WIRE = RetrievalRequest(item="binding wire coils", category="building materials",
                        estimated_total=900_000)
HELMETS = RetrievalRequest(item="40 safety helmets", category="safety equipment",
                           estimated_total=800_000)

INVENTED = [{"source_id": "POL-009", "version": "1.0", "clause_id": "POL-009-C01", "reason": "r"}]


@pytest.fixture(scope="module")
def index():
    built = PolicyIndex()
    built.build(load_corpus(CORPUS, REGISTER), WordOverlapEmbedder())
    return built


def _pipeline(index, backend, tmp_path, cutoff=-1.0, top_k=5):
    retriever = Retriever(index, WordOverlapEmbedder(), top_k=top_k,
                          min_score=cutoff, item_min_score=cutoff)
    return PolicyPipeline(
        retriever, backend,
        policy=RetryPolicy(max_attempts=2, base_delay_s=0.0, max_delay_s=0.0),
        trace=TraceLog(tmp_path / "trace.jsonl"),
    )


def _trace(tmp_path):
    return [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]


# --- a whole requisition -----------------------------------------------------


def test_every_item_is_grounded_in_one_call_and_traced_once(index, tmp_path):
    backend = GroundedStubBackend()
    outcome = _pipeline(index, backend, tmp_path).run([CEMENT, WIRE, HELMETS])

    assert len(backend.calls) == 1
    assert outcome.status == REQUISITION_OK
    assert outcome.shown
    assert [item.ref for item in outcome.items] == ["1", "2", "3"]
    assert [item.retrieval.request.item for item in outcome.items] == [
        CEMENT.item, WIRE.item, HELMETS.item
    ]
    assert all(item.status == STATUS_OK for item in outcome.items)

    [entry] = _trace(tmp_path)
    assert entry["component"] == "RAG"
    assert entry["status"] == "ok"
    assert entry["item_count"] == 3
    assert entry["items_shown"] == 3
    assert entry["items"][0]["request"]["estimated_total"] == 4_140_000
    assert entry["items"][0]["citation_check"] == {"valid": True, "problems": []}
    assert entry["config_fingerprint"]["prompt_version"] == "grounding-1.1"


def test_each_item_is_searched_separately(index, tmp_path):
    outcome = _pipeline(index, GroundedStubBackend(), tmp_path).run([CEMENT, HELMETS])
    queries = [item.retrieval.query for item in outcome.items]
    assert queries == [CEMENT.to_query(), HELMETS.to_query()]


def test_an_empty_requisition_is_refused(index, tmp_path):
    pipeline = _pipeline(index, GroundedStubBackend(), tmp_path)
    with pytest.raises(RetrievalError, match="at least one item"):
        pipeline.run([])


# --- items shown or withheld on their own ------------------------------------


def test_one_ungrounded_item_does_not_hide_the_others(index, tmp_path):
    backend = GroundedStubBackend(per_item={"1": {"citations": INVENTED}})
    outcome = _pipeline(index, backend, tmp_path).run([CEMENT, WIRE])

    assert outcome.status == REQUISITION_PARTIAL
    assert not outcome.shown
    cement, wire = outcome.items
    assert cement.status == STATUS_CITATION_INVALID
    assert "POL-009-C01" in cement.detail
    assert wire.status == STATUS_OK
    assert _trace(tmp_path)[0]["items_shown"] == 1


def test_a_clause_supplied_for_another_item_does_not_count(index, tmp_path):
    """Rule 3: never cite a clause that was not supplied for that item."""
    probe = GroundedStubBackend()
    _pipeline(index, probe, tmp_path, top_k=1).run([CEMENT, HELMETS])
    only_helmets = sorted(probe.supplied_for("2") - probe.supplied_for("1"))
    if not only_helmets:
        pytest.skip("the fake embedder supplied both items the same clauses")
    borrowed = only_helmets[0]
    citation = [{"source_id": borrowed.rsplit("-C", 1)[0], "version": "1.0",
                 "clause_id": borrowed, "reason": "r"}]

    backend = GroundedStubBackend(per_item={"1": {"citations": citation}})
    cement, helmets = _pipeline(index, backend, tmp_path, top_k=1).run([CEMENT, HELMETS]).items

    assert cement.status == STATUS_CITATION_INVALID
    assert borrowed in cement.detail
    assert helmets.status == STATUS_OK


def test_an_item_with_nothing_kept_is_answered_by_its_notes_alone(index, tmp_path):
    """No call at all when no item kept anything; the notes are the whole answer."""
    backend = GroundedStubBackend()
    outcome = _pipeline(index, backend, tmp_path, cutoff=0.99).run([CEMENT, HELMETS])

    assert backend.calls == []
    assert outcome.status == REQUISITION_OK
    assert outcome.attempts == 0
    assert all(item.status == STATUS_NO_CLAUSES for item in outcome.items)
    assert len(_trace(tmp_path)[0]["items"][0]["retrieval"]["absence_notes"]) == 2


def test_a_prohibited_assertion_is_suppressed_and_never_recorded(index, tmp_path):
    """Requirement 14.2: removed before it reaches any user or record."""
    backend = GroundedStubBackend(per_item={"2": {"summary": "The supplier has been approved."}})
    outcome = _pipeline(index, backend, tmp_path).run([CEMENT, HELMETS])

    assert outcome.items[0].status == STATUS_OK
    assert outcome.items[1].status == STATUS_SUPPRESSED
    entry = _trace(tmp_path)[0]["items"][1]
    assert entry["answer"] is None
    assert entry["suppressed_patterns"][0]["category"] == "approval_assertion"
    assert "has been approved" not in (tmp_path / "trace.jsonl").read_text()


def test_suppression_outranks_a_citation_problem_but_both_are_recorded(index, tmp_path):
    backend = GroundedStubBackend(summary="The supplier has been approved under POL-009.")
    [item] = _pipeline(index, backend, tmp_path).run([CEMENT]).items

    assert item.status == STATUS_SUPPRESSED
    assert not item.citation_report.valid


# --- the call failing --------------------------------------------------------


def test_a_malformed_answer_withholds_every_item_that_needed_it(index, tmp_path):
    outcome = _pipeline(index, GroundedStubBackend(raw="not json"), tmp_path).run([CEMENT, WIRE])
    assert outcome.status == REQUISITION_WITHHELD
    assert {item.status for item in outcome.items} == {STATUS_GENERATION_FAILED}


def test_a_permanent_transport_error_is_a_call_failure(index, tmp_path):
    outcome = _pipeline(index, GroundedStubBackend(error=PermanentError("bad key")),
                        tmp_path).run([CEMENT])
    assert outcome.items[0].status == STATUS_CALL_FAILED
    assert outcome.attempts == 1


def test_exhausted_rate_limit_retries_are_reported_as_rate_limited(index, tmp_path):
    outcome = _pipeline(index, GroundedStubBackend(error=RateLimitError("429")),
                        tmp_path).run([CEMENT])
    assert outcome.items[0].status == STATUS_RATE_LIMITED
    assert outcome.attempts == 2
    assert _trace(tmp_path)[0]["items"][0]["status"] == "rate_limited"


def test_timeout_withholds_answer_and_preserves_latency_in_trace(index, tmp_path):
    backend = GroundedStubBackend(error=DeadlineExceeded("30s deadline", 2, 30.0))
    outcome = _pipeline(index, backend, tmp_path).run([CEMENT])
    assert outcome.status == REQUISITION_WITHHELD
    assert outcome.items[0].status == "timeout"
    assert outcome.items[0].answer is None
    assert outcome.attempts == 2
    assert outcome.latency_s == 30.0
    [entry] = _trace(tmp_path)
    assert entry["items"][0]["status"] == "timeout"
    assert entry["latency_s"] == 30.0


def test_every_run_appends_rather_than_overwrites(index, tmp_path):
    pipeline = _pipeline(index, GroundedStubBackend(), tmp_path)
    pipeline.run([CEMENT])
    pipeline.run([CEMENT, WIRE])
    assert [e["item_count"] for e in _trace(tmp_path)] == [1, 2]


# --- the command line --------------------------------------------------------


def _common(tmp_path, *extra):
    """Arguments shared by every CLI test, against an index ingested once."""
    index_dir = tmp_path / "index"
    if not (index_dir / MANIFEST_NAME).exists():
        ingest(WordOverlapEmbedder(), CORPUS, REGISTER, index_dir)
    return [
        "--index-dir", str(index_dir),
        "--min-score", "-1", "--item-min-score", "-1",
        "--corpus-dir", str(CORPUS), "--source-register", str(REGISTER),
        "--trace-log", str(tmp_path / "trace.jsonl"),
        "--no-env-file",
        *extra,
    ]


def _one_item(tmp_path, *extra):
    return _common(tmp_path, "--item", "120 bags of cement", "--category", "building materials",
                   "--total", "4,140,000", *extra)


def _run(args, backend=None):
    return cli.main(args, backend=backend or GroundedStubBackend(), embedder=WordOverlapEmbedder())


def test_the_cli_shows_one_item(tmp_path, capsys):
    code = _run(_one_item(tmp_path))
    out = capsys.readouterr().out

    assert code == cli.EXIT_SHOWN
    assert "ITEM 1 of 1: 120 bags of cement" in out
    assert "estimated total : UGX 4,140,000" in out
    assert "citation check  : PASSED" in out
    assert "requisition    : OK, every item can be shown (1 of 1)" in out


def test_the_cli_grounds_a_requisition_file(tmp_path, capsys):
    backend = GroundedStubBackend()
    code = _run(_common(tmp_path, "--requisition", str(SAMPLE_REQUISITION)), backend)
    out = capsys.readouterr().out

    assert code == cli.EXIT_SHOWN
    assert len(backend.calls) == 1
    assert "ITEM 1 of 4: 120 bags of cement" in out
    assert "ITEM 4 of 4: diesel for the delivery truck" in out
    assert "(4 of 4)" in out


def test_the_cli_exits_1_when_any_item_is_withheld(tmp_path, capsys):
    backend = GroundedStubBackend(per_item={"2": {"citations": INVENTED}})
    code = _run(_common(tmp_path, "--requisition", str(SAMPLE_REQUISITION)), backend)
    out = capsys.readouterr().out

    assert code == cli.EXIT_WITHHELD
    assert "PARTIAL, some items were withheld (3 of 4)" in out
    assert "(NOT GROUNDED)" in out


def test_the_cli_json_output_is_the_trace_entry(tmp_path, capsys):
    _run(_one_item(tmp_path, "--json"))
    printed = json.loads(capsys.readouterr().out)
    assert printed == _trace(tmp_path)[0]


@pytest.mark.parametrize("args, message", [
    ([], "give --item and --category, or --requisition FILE"),
    (["--item", "cement"], "give --item and --category"),
    (["--item", "  ", "--category", "x"], "item must not be empty"),
    (["--item", "cement", "--category", "x", "--requisition", "r.json"], "not both"),
])
def test_usage_errors(tmp_path, capsys, args, message):
    assert _run(_common(tmp_path, *args)) == cli.EXIT_USAGE
    assert message in capsys.readouterr().err


@pytest.mark.parametrize("content, message", [
    ("not json", "not valid JSON"),
    ('{"items": []}', "non-empty"),
    ('[{"item": "cement"}]', "non-empty"),
    ('{"items": ["cement"]}', "item 1 in"),
    ('{"items": [{"item": "cement", "category": ""}]}', "category must not be empty"),
])
def test_a_malformed_requisition_file_is_a_usage_error(tmp_path, capsys, content, message):
    path = tmp_path / "requisition.json"
    path.write_text(content, encoding="utf-8")
    assert _run(_common(tmp_path, "--requisition", str(path))) == cli.EXIT_USAGE
    assert message in capsys.readouterr().err


def test_the_api_key_never_reaches_output_or_trace(tmp_path, capsys):
    secret = "AQ.secret-key-that-must-not-leak-1234"
    env_file = tmp_path / ".env"
    env_file.write_text(f"GEMINI_API_KEY={secret}\n", encoding="utf-8")
    args = [a for a in _one_item(tmp_path, "--json") if a != "--no-env-file"]

    _run([*args, "--env-file", str(env_file)])
    captured = capsys.readouterr()

    assert secret not in captured.out
    assert secret not in captured.err
    assert secret not in (tmp_path / "trace.jsonl").read_text()


@pytest.mark.parametrize("raw, expected", [
    ("4140000", 4_140_000), ("4,140,000", 4_140_000), ("8.5", 8.5), (None, None), (900000, 900000),
])
def test_totals_are_parsed_without_changing_them(raw, expected):
    assert cli._parse_total(raw) == expected
