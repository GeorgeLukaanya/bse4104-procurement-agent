"""Authorization: injected role, allow-list, officer confirmation gate."""

from __future__ import annotations

from procurement_agent.tools import invoke

DRAFT = {
    "review_date": "2026-09-25",
    "officer_username": "a.nakato",
    "items": [
        {
            "sku": "AH-CM-001",
            "reorder_quantity": 120,
            "comparison_reference": "CMP-001",
        }
    ],
    "justification": "Officer-confirmed comparison for cement at reorder point.",
}


def test_manager_cannot_create_a_requisition(tmp_path):
    result = invoke(
        "create_requisition_draft",
        DRAFT,
        caller_role="PROCUREMENT_MANAGER",
        requisition_store=str(tmp_path / "req.jsonl"),
        run_log=str(tmp_path / "runs.jsonl"),
    )
    assert result["status"] == "unauthorized"
    assert result["errors"][0]["code"] == "UNAUTHORIZED_ROLE"
    assert result["trace"]["caller_role"] == "PROCUREMENT_MANAGER"
    assert not (tmp_path / "req.jsonl").exists()


def test_unconfirmed_agent_call_is_refused(tmp_path):
    result = invoke(
        "create_requisition_draft",
        DRAFT,
        caller_role="AGENT",
        officer_confirmed=False,
        requisition_store=str(tmp_path / "req.jsonl"),
        run_log=str(tmp_path / "runs.jsonl"),
    )
    assert result["status"] == "unauthorized"
    assert result["errors"][0]["code"] == "UNAUTHORIZED_ROLE"
    assert not (tmp_path / "req.jsonl").exists()


def test_confirmed_agent_call_runs_as_the_officer(tmp_path):
    result = invoke(
        "create_requisition_draft",
        DRAFT,
        caller_role="AGENT",
        officer_confirmed=True,
        requisition_store=str(tmp_path / "req.jsonl"),
        run_log=str(tmp_path / "runs.jsonl"),
    )
    assert result["status"] == "ok"
    assert result["trace"]["caller_role"] == "PROCUREMENT_OFFICER"
    assert result["data"]["created_by"] == "a.nakato"


def test_tool_off_the_step_allow_list_never_enters_the_tool(tmp_path):
    result = invoke(
        "check_reorder_need",
        {"review_date": "2026-09-25"},
        caller_role="PROCUREMENT_OFFICER",
        allowed_tools=("compare_quotations",),
        run_log=str(tmp_path / "runs.jsonl"),
    )
    assert result["status"] == "unauthorized"
    assert result["errors"][0]["code"] == "TOOL_NOT_ALLOWED"
    assert result["data"] is None


def test_role_in_the_payload_is_ignored(tmp_path):
    result = invoke(
        "check_reorder_need",
        {"review_date": "2026-09-25", "caller_role": "PROCUREMENT_MANAGER", "skus": ["AH-CM-003"]},
        caller_role="PROCUREMENT_OFFICER",
        run_log=str(tmp_path / "runs.jsonl"),
    )
    assert result["status"] in {"ok", "no_result", "invalid_input"}
    # additionalProperties: caller_role on the payload is refused, not honoured.
    assert result["status"] == "invalid_input"
    assert result["errors"][0]["code"] == "INVALID_PARAMETER"
    assert result["trace"]["caller_role"] == "PROCUREMENT_OFFICER"


def test_read_only_tools_accept_all_seeded_roles(tmp_path):
    for role in ("PROCUREMENT_OFFICER", "PROCUREMENT_MANAGER", "AGENT"):
        result = invoke(
            "check_reorder_need",
            {"review_date": "2026-09-25", "skus": ["AH-CM-003"]},
            caller_role=role,
            run_log=str(tmp_path / "runs.jsonl"),
        )
        assert result["status"] == "no_result"
        assert result["trace"]["caller_role"] == role


def test_unknown_tool_name_is_not_allowed(tmp_path):
    result = invoke(
        "approve_requisition",
        {},
        caller_role="PROCUREMENT_MANAGER",
        run_log=str(tmp_path / "runs.jsonl"),
    )
    assert result["status"] == "unauthorized"
    assert result["errors"][0]["code"] == "TOOL_NOT_ALLOWED"
