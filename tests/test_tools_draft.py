"""create_requisition_draft writes DRAFT and nothing else."""

from __future__ import annotations

import json

from procurement_agent.tools import invoke

DRAFT = {
    "review_date": "2026-09-25",
    "officer_username": "a.nakato",
    "items": [
        {
            "sku": "AH-CM-001",
            "reorder_quantity": 120,
            "comparison_reference": "CMP-2026-0925-001",
            "recommended_quotation_id": "QT-002",
            "unresolved_issues": [
                "QT-003 is from Lakeview Building Supplies, a different entity "
                "from Lakeview Building Materials. POL-002-C04 discrepancy not yet resolved."
            ],
        }
    ],
    "policy_clauses": ["POL-001-C02", "POL-002-C04", "POL-003-C03"],
    "justification": (
        "Cement is at its reorder point at the Nakawa Main Store. "
        "The lowest eligible landed cost after exclusions is Bugolobi Hardware Supplies."
    ),
}


def _call(tmp_path, payload, **kwargs):
    return invoke(
        "create_requisition_draft",
        payload,
        caller_role=kwargs.pop("caller_role", "PROCUREMENT_OFFICER"),
        officer_confirmed=kwargs.pop("officer_confirmed", False),
        requisition_store=str(tmp_path / "requisitions.jsonl"),
        run_log=str(tmp_path / "tool-runs.jsonl"),
        **kwargs,
    )


def test_officer_creates_a_draft_and_nothing_beyond(tmp_path):
    result = _call(tmp_path, DRAFT)
    assert result["status"] == "ok"
    data = result["data"]
    assert data["status"] == "DRAFT"
    assert data["human_confirmation_required"] is True
    assert data["routed_to"] is None
    assert data["approved_by"] is None
    assert data["decision"] is None
    assert data["requisition_id"].startswith("REQ-2026-")
    assert data["unresolved_issues"]
    stored = (tmp_path / "requisitions.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(stored) == 1
    assert json.loads(stored[0])["status"] == "DRAFT"


def test_second_draft_increments_the_identifier(tmp_path):
    first = _call(tmp_path, DRAFT)
    second = _call(tmp_path, DRAFT)
    assert first["data"]["requisition_id"] == "REQ-2026-001"
    assert second["data"]["requisition_id"] == "REQ-2026-002"


def test_status_beyond_draft_writes_nothing(tmp_path):
    payload = dict(DRAFT)
    payload["status"] = "APPROVED"
    result = _call(tmp_path, payload)
    assert result["status"] == "invalid_input"
    assert result["errors"][0]["code"] == "FORBIDDEN_TRANSITION"
    assert result["data"] is None
    assert not (tmp_path / "requisitions.jsonl").exists()


def test_unknown_clause_is_refused(tmp_path):
    payload = dict(DRAFT)
    payload["policy_clauses"] = ["POL-999-C01"]
    result = _call(tmp_path, payload)
    assert result["status"] == "invalid_input"
    assert result["errors"][0]["code"] == "INVALID_PARAMETER"
    assert not (tmp_path / "requisitions.jsonl").exists()


def test_missing_required_field_writes_nothing(tmp_path):
    payload = dict(DRAFT)
    del payload["justification"]
    result = _call(tmp_path, payload)
    assert result["status"] == "invalid_input"
    assert result["errors"][0]["code"] == "MISSING_PARAMETER"
    assert not (tmp_path / "requisitions.jsonl").exists()
