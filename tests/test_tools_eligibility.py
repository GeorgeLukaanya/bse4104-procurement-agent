"""check_supplier_eligibility against DAT-002 and Requirement 4 v1.2."""

from __future__ import annotations

from procurement_agent.tools import invoke


def _call(tmp_path, payload, **kwargs):
    return invoke(
        "check_supplier_eligibility",
        payload,
        caller_role="PROCUREMENT_OFFICER",
        run_log=str(tmp_path / "tool-runs.jsonl"),
        **kwargs,
    )


def test_seeded_exclusion_reasons(tmp_path):
    result = _call(
        tmp_path,
        {
            "category": "cement and masonry",
            "as_of_date": "2026-09-25",
            "supplier_ids": ["SUP-002", "SUP-006", "SUP-007"],
        },
    )
    assert result["status"] == "ok"
    by_id = {row["supplier_id"]: row for row in result["data"]["results"]}
    assert by_id["SUP-002"]["exclusion_reasons"] == ["NAME_DISCREPANCY"]
    assert by_id["SUP-002"]["similar_registered_names"] == ["Lakeview Building Supplies"]
    assert by_id["SUP-006"]["exclusion_reasons"] == ["BLACKLISTED"]
    assert by_id["SUP-007"]["exclusion_reasons"] == ["NAME_DISCREPANCY"]
    assert by_id["SUP-007"]["similar_registered_names"] == ["Lakeview Building Materials"]
    assert all(row["eligible"] is False for row in result["data"]["results"])


def test_suspended_and_out_of_category_are_separate_reasons(tmp_path):
    result = _call(
        tmp_path,
        {
            "category": "cement and masonry",
            "as_of_date": "2026-09-25",
            "supplier_ids": ["SUP-005", "SUP-001"],
        },
    )
    by_id = {row["supplier_id"]: row for row in result["data"]["results"]}
    assert "SUSPENDED" in by_id["SUP-005"]["exclusion_reasons"]
    assert "OUT_OF_CATEGORY" in by_id["SUP-005"]["exclusion_reasons"]
    assert by_id["SUP-001"]["exclusion_reasons"] == ["OUT_OF_CATEGORY"]


def test_absent_supplier_is_the_answer_not_an_error(tmp_path):
    result = _call(
        tmp_path,
        {
            "category": "hand tools and safety equipment",
            "as_of_date": "2026-09-25",
            "supplier_ids": ["SUP-099"],
        },
    )
    assert result["status"] == "ok"
    row = result["data"]["results"][0]
    assert row["matched_by"] == "unmatched"
    assert "AVL_ABSENT" in row["exclusion_reasons"]
    assert row["eligible"] is False


def test_expired_quotation_is_recorded(tmp_path):
    result = _call(
        tmp_path,
        {
            "category": "hand tools and safety equipment",
            "as_of_date": "2026-09-25",
            "supplier_ids": ["SUP-001"],
            "quotation_ids": ["QT-016"],
        },
    )
    row = result["data"]["results"][0]
    assert "EXPIRED" in row["exclusion_reasons"]


def test_neither_identifier_list_is_missing_parameter(tmp_path):
    result = _call(
        tmp_path,
        {"category": "cement and masonry", "as_of_date": "2026-09-25"},
    )
    assert result["status"] == "invalid_input"
    assert result["errors"][0]["code"] == "MISSING_PARAMETER"


def test_unknown_category_is_refused(tmp_path):
    result = _call(
        tmp_path,
        {
            "category": "office stationery",
            "as_of_date": "2026-09-25",
            "supplier_ids": ["SUP-001"],
        },
    )
    assert result["status"] == "invalid_input"
    assert result["errors"][0]["code"] == "INVALID_PARAMETER"


def test_missing_register_reports_nobody_eligible(tmp_path):
    result = _call(
        tmp_path,
        {
            "category": "cement and masonry",
            "as_of_date": "2026-09-25",
            "supplier_ids": ["SUP-004"],
        },
        suppliers_path=str(tmp_path / "missing.json"),
    )
    assert result["status"] == "unavailable"
    assert result["data"] is None
    assert result["errors"][0]["code"] == "DATA_SOURCE_UNAVAILABLE"
