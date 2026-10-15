"""Week 6 run state: a re-run resumes, and only from results that are still current."""

from __future__ import annotations

import json

from procurement_agent.agent import run_workflow
from procurement_agent.agent import workflow as workflow_mod
from procurement_agent.agent.checkpoint import CheckpointStore, run_id_for
from procurement_agent.agent.steps import (
    STOP_AWAITING_HUMAN,
    STOP_COMPLETED,
    STOP_FAILED,
    STOP_MAX_ITERATIONS,
)

RUN_ID = run_id_for("2026-09-25", "AH-CM-001", "a.nakato")


def _run(tmp_path, **kwargs):
    kwargs.setdefault("review_date", "2026-09-25")
    kwargs.setdefault("sku", "AH-CM-001")
    kwargs.setdefault("run_log", str(tmp_path / "agent-runs.jsonl"))
    kwargs.setdefault("tool_log", str(tmp_path / "tool-runs.jsonl"))
    kwargs.setdefault("requisition_store", str(tmp_path / "requisitions.jsonl"))
    kwargs.setdefault("checkpoint_dir", str(tmp_path / "state"))
    return run_workflow(**kwargs)


def _tools(result):
    return [call["tool"] for call in result.calls]


def test_handoff_then_confirm_resumes_without_repeating_reads(tmp_path):
    first = _run(tmp_path)
    assert first.stop_reason == STOP_AWAITING_HUMAN
    assert _tools(first) == ["check_reorder_need", "check_supplier_eligibility", "compare_quotations"]

    second = _run(tmp_path, confirm_comparison=True, confirm_draft=True)
    assert second.stop_reason == STOP_COMPLETED
    assert _tools(second) == ["create_requisition_draft"]
    assert second.iterations == 4  # 3 carried over + 1, against the same budget
    assert second.state.resumed["kept_steps"] == ["scan", "eligibility", "compare"]
    assert set(second.state.confirmations) == {"comparison", "draft"}


def test_a_completed_run_never_compiles_a_second_requisition(tmp_path):
    _run(tmp_path, confirm_comparison=True, confirm_draft=True)
    again = _run(tmp_path, confirm_comparison=True, confirm_draft=True)
    assert again.stop_reason == STOP_COMPLETED
    assert again.calls == []
    assert "Already completed" in again.stop_detail
    lines = (tmp_path / "requisitions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


def test_a_rate_supplied_on_resume_reruns_only_the_comparison(tmp_path):
    waiting = _run(tmp_path, sku="AH-HT-001")
    assert waiting.stop_reason == STOP_AWAITING_HUMAN
    assert "EXCHANGE_RATE_REQUIRED" in waiting.stop_detail

    rated = _run(tmp_path, sku="AH-HT-001", exchange_rate_ugx_per_usd=3700)
    assert rated.stop_reason == STOP_AWAITING_HUMAN
    assert _tools(rated) == ["compare_quotations"]
    assert rated.state.comparison["exchange_rate"]["ugx_per_usd"] == 3700
    assert rated.state.draft is None


def test_failure_then_recovery_resumes_at_the_failed_step(tmp_path):
    failed = _run(tmp_path, suppliers_path=str(tmp_path / "missing-suppliers.json"))
    assert failed.stop_reason == STOP_FAILED
    assert "DATA_SOURCE_UNAVAILABLE" in failed.stop_detail
    assert _tools(failed) == ["check_reorder_need", "check_supplier_eligibility"]
    assert CheckpointStore(tmp_path / "state").load(RUN_ID)["stop_reason"] == STOP_FAILED

    recovered = _run(tmp_path)
    assert recovered.stop_reason == STOP_AWAITING_HUMAN
    assert recovered.state.resumed["kept_steps"] == ["scan"]
    assert _tools(recovered) == ["check_supplier_eligibility", "compare_quotations"]


def test_changed_data_recomputes_from_the_first_affected_step(tmp_path, monkeypatch):
    _run(tmp_path, confirm_comparison=True)  # stops waiting for the draft confirmation

    real = workflow_mod.current_sources

    def quotations_changed(**kwargs):
        found = real(**kwargs)
        found["quotations"] = "0000000000000000"
        return found

    monkeypatch.setattr(workflow_mod, "current_sources", quotations_changed)
    resumed = _run(tmp_path, confirm_draft=True)
    assert resumed.state.resumed["kept_steps"] == ["scan"]
    assert resumed.state.resumed["recomputed_from"] == "eligibility"
    assert resumed.state.resumed["changed_sources"] == ["quotations"]
    # The officer confirmed the old comparison, not this one, so Gate 2 is asked again.
    assert resumed.stop_reason == STOP_AWAITING_HUMAN
    assert "comparison" not in resumed.state.confirmations
    assert resumed.state.draft is None


def test_the_iteration_budget_spans_re_runs(tmp_path):
    first = _run(tmp_path, max_iterations=2)
    assert first.stop_reason == STOP_MAX_ITERATIONS
    second = _run(tmp_path, max_iterations=2)
    assert second.stop_reason == STOP_MAX_ITERATIONS
    assert second.calls == []


def test_fresh_discards_the_checkpoint(tmp_path):
    _run(tmp_path)
    again = _run(tmp_path, fresh=True)
    assert again.state.resumed is None
    assert len(again.calls) == 3


def test_an_unreadable_checkpoint_is_ignored_not_trusted(tmp_path):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / f"{RUN_ID}.json").write_text("{not json", encoding="utf-8")
    result = _run(tmp_path)
    assert result.state.resumed is None
    assert len(result.calls) == 3


def test_checkpoint_holds_working_state_only(tmp_path):
    _run(tmp_path)
    saved = json.loads((tmp_path / "state" / f"{RUN_ID}.json").read_text(encoding="utf-8"))
    assert set(saved) == {
        "checkpoint_format", "run_id", "review_date", "sku", "officer_username",
        "contract_version", "step", "iterations", "stop_reason", "stop_detail",
        "results", "step_sources", "confirmations", "saved_at",
        "exchange_rate_ugx_per_usd", "exchange_rate_effective_date",
    }
    assert set(saved["results"]) == {"scan", "eligibility", "compare"}


def test_without_a_checkpoint_dir_nothing_is_saved(tmp_path):
    result = run_workflow(
        review_date="2026-09-25",
        sku="AH-CM-001",
        run_log=str(tmp_path / "a.jsonl"),
        tool_log=str(tmp_path / "t.jsonl"),
        requisition_store=str(tmp_path / "r.jsonl"),
    )
    assert result.state.resumed is None
    assert not (tmp_path / "state").exists()


def test_retries_that_reuse_nothing_still_spend_the_budget(tmp_path):
    missing = str(tmp_path / "missing-inventory.csv")
    for _ in range(3):
        last = _run(tmp_path, inventory_path=missing, max_iterations=2)
    assert last.stop_reason == STOP_MAX_ITERATIONS
    assert last.calls == []
