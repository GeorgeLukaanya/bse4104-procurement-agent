"""Bounded agent workflow. No API key, no network."""

from __future__ import annotations

from procurement_agent.agent import run_workflow
from procurement_agent.agent.planner import Proposal, ScriptedPlanner
from procurement_agent.agent.steps import (
    STOP_AWAITING_HUMAN,
    STOP_COMPLETED,
    STOP_MAX_ITERATIONS,
    STOP_NO_REORDER,
    STOP_UNAUTHORIZED,
)


def _run(tmp_path, **kwargs):
    kwargs.setdefault("review_date", "2026-09-25")
    kwargs.setdefault("sku", "AH-CM-001")
    kwargs.setdefault("run_log", str(tmp_path / "agent-runs.jsonl"))
    kwargs.setdefault("tool_log", str(tmp_path / "tool-runs.jsonl"))
    kwargs.setdefault("requisition_store", str(tmp_path / "requisitions.jsonl"))
    return run_workflow(**kwargs)


def test_stops_for_officer_after_comparison(tmp_path):
    result = _run(tmp_path)
    assert result.stop_reason == STOP_AWAITING_HUMAN
    assert result.iterations == 3
    assert result.state.comparison is not None
    assert result.state.draft is None
    assert not (tmp_path / "requisitions.jsonl").exists()


def test_officer_confirms_through_to_draft(tmp_path):
    result = _run(tmp_path, confirm_comparison=True, confirm_draft=True)
    assert result.stop_reason == STOP_COMPLETED
    assert result.state.draft["status"] == "DRAFT"
    assert result.state.draft["human_confirmation_required"] is True
    assert result.state.draft["routed_to"] is None
    stored = (tmp_path / "requisitions.jsonl").read_text(encoding="utf-8")
    assert "DRAFT" in stored
    assert "APPROVED" not in stored


def test_no_reorder_ends_the_review(tmp_path):
    result = _run(tmp_path, sku="AH-CM-003")
    assert result.stop_reason == STOP_NO_REORDER
    assert result.iterations == 1
    assert result.state.eligibility is None


def test_iteration_cap_halts_without_writing(tmp_path):
    result = _run(tmp_path, max_iterations=1, confirm_comparison=True, confirm_draft=True)
    assert result.stop_reason == STOP_MAX_ITERATIONS
    assert result.iterations == 1
    assert not (tmp_path / "requisitions.jsonl").exists()


def test_manager_cannot_run_the_loop(tmp_path):
    result = _run(tmp_path, caller_role="PROCUREMENT_MANAGER")
    assert result.stop_reason == STOP_UNAUTHORIZED
    assert result.iterations == 0
    assert result.calls == []


def test_proposal_off_the_step_allow_list_is_refused(tmp_path):
    planner = ScriptedPlanner(
        [
            Proposal(
                kind="call",
                tool="create_requisition_draft",
                payload={
                    "review_date": "2026-09-25",
                    "officer_username": "a.nakato",
                    "items": [
                        {
                            "sku": "AH-CM-001",
                            "reorder_quantity": 120,
                            "comparison_reference": "CMP-X",
                        }
                    ],
                    "justification": "should not write",
                },
            )
        ]
    )
    result = _run(tmp_path, planner=planner, confirm_draft=True)
    assert result.stop_reason == STOP_UNAUTHORIZED
    assert result.calls[0]["errors"][0]["code"] == "TOOL_NOT_ALLOWED"
    assert not (tmp_path / "requisitions.jsonl").exists()
