"""check_reorder_need against DAT-001."""

from __future__ import annotations

from procurement_agent.tools import invoke


def _call(tmp_path, payload, **kwargs):
    return invoke(
        "check_reorder_need",
        payload,
        caller_role="PROCUREMENT_OFFICER",
        run_log=str(tmp_path / "tool-runs.jsonl"),
        **kwargs,
    )


def test_flags_cement_exactly_at_reorder_point(tmp_path):
    result = _call(
        tmp_path,
        {"review_date": "2026-09-25", "skus": ["AH-CM-001", "AH-HT-012"]},
    )
    assert result["status"] == "ok"
    assert result["trace"]["data_fingerprint"] == "6ab934ebb697380b"
    items = {row["sku"]: row for row in result["data"]["items"]}
    cement = items["AH-CM-001"]
    assert cement["current_stock"] == 150
    assert cement["reorder_point"] == 150
    assert cement["at_or_below_reorder_point"] is True
    assert cement["reorder_quantity"] == 120
    assert cement["estimated_total_ugx"] == 120 * 32000
    assert items["AH-HT-012"]["reorder_quantity"] == 47
    assert result["data"]["flagged_count"] == 2


def test_empty_reorder_list_is_no_result_not_an_error(tmp_path):
    result = _call(tmp_path, {"review_date": "2026-09-25", "skus": ["AH-CM-003"]})
    assert result["status"] == "no_result"
    assert result["data"]["no_reorder_required"] is True
    assert result["data"]["flagged_count"] == 0
    assert result["errors"] == []


def test_missing_review_date_reads_nothing(tmp_path):
    result = _call(tmp_path, {"skus": ["AH-CM-001"]})
    assert result["status"] == "invalid_input"
    assert result["data"] is None
    assert result["errors"][0]["code"] == "MISSING_PARAMETER"
    assert result["errors"][0]["field"] == "review_date"


def test_every_unknown_sku_is_listed(tmp_path):
    result = _call(
        tmp_path,
        {"review_date": "2026-09-25", "skus": ["AH-ZZ-999", "AH-YY-001"]},
    )
    assert result["status"] == "invalid_input"
    codes = [item["code"] for item in result["errors"]]
    assert codes == ["UNKNOWN_SKU", "UNKNOWN_SKU"]


def test_malformed_sku_is_refused_whole(tmp_path):
    result = _call(tmp_path, {"review_date": "2026-09-25", "skus": ["CEMENT"]})
    assert result["status"] == "invalid_input"
    assert result["errors"][0]["code"] == "INVALID_PARAMETER"


def test_missing_snapshot_is_unavailable(tmp_path):
    result = _call(
        tmp_path,
        {"review_date": "2026-09-25"},
        inventory_path=str(tmp_path / "nope.csv"),
    )
    assert result["status"] == "unavailable"
    assert result["errors"][0]["code"] == "DATA_SOURCE_UNAVAILABLE"
    assert result["data"] is None


def test_checksum_mismatch_is_integrity_failure(tmp_path):
    mutated = tmp_path / "inventory.csv"
    mutated.write_text("sku,item_name\nAH-CM-001,tampered\n", encoding="utf-8")
    result = _call(
        tmp_path,
        {"review_date": "2026-09-25"},
        inventory_path=str(mutated),
    )
    assert result["status"] == "failed"
    assert result["errors"][0]["code"] == "DATA_INTEGRITY_ERROR"
