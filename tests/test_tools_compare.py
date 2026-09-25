"""compare_quotations: every figure is computed here, never stored."""

from __future__ import annotations

from procurement_agent.tools import invoke


def _call(tmp_path, payload, **kwargs):
    return invoke(
        "compare_quotations",
        payload,
        caller_role="PROCUREMENT_OFFICER",
        run_log=str(tmp_path / "tool-runs.jsonl"),
        **kwargs,
    )


def test_cement_ranks_the_eligible_tonne_offer_and_excludes_the_rest(tmp_path):
    result = _call(
        tmp_path,
        {"sku": "AH-CM-001", "reorder_quantity": 120, "comparison_date": "2026-09-25"},
    )
    assert result["status"] == "ok"
    ranked = result["data"]["ranked"]
    excluded = {row["quotation_id"]: row for row in result["data"]["excluded"]}
    assert [row["quotation_id"] for row in ranked] == ["QT-002"]
    assert ranked[0]["normalised_unit_cost_ugx"] == 31000.0
    assert ranked[0]["extended_cost_ugx"] == 3720000.0
    assert ranked[0]["vat_amount_ugx"] == 669600.0
    assert ranked[0]["delivery_cost_ugx"] == 90000.0
    assert ranked[0]["landed_cost_ugx"] == 4479600.0
    assert ranked[0]["unit_conversion_factor"] == 20.0
    assert "NAME_DISCREPANCY" in excluded["QT-001"]["reasons"]
    assert "NAME_DISCREPANCY" in excluded["QT-003"]["reasons"]
    assert "BLACKLISTED" in excluded["QT-004"]["reasons"]
    assert result["data"]["sole_eligible_option"] is True
    assert result["data"]["quotation_requirement"]["clause"] == "POL-001-C02"
    assert result["data"]["quotation_requirement"]["satisfied"] is False
    assert result["errors"][0]["code"] == "INSUFFICIENT_QUOTATIONS"


def test_incomparable_offer_names_the_missing_field(tmp_path):
    result = _call(
        tmp_path,
        {"sku": "AH-HT-006", "reorder_quantity": 85, "comparison_date": "2026-09-25"},
    )
    excluded = {row["quotation_id"]: row for row in result["data"]["excluded"]}
    assert "INCOMPARABLE_QUOTATION" in excluded["QT-021"]["reasons"]
    assert "vat_treatment" in excluded["QT-021"]["missing_fields"]


def test_usd_offer_without_a_rate_is_refused(tmp_path):
    result = _call(
        tmp_path,
        {"sku": "AH-HT-001", "reorder_quantity": 40, "comparison_date": "2026-09-25"},
    )
    assert result["status"] == "invalid_input"
    assert result["errors"][0]["code"] == "EXCHANGE_RATE_REQUIRED"
    assert result["data"] is None


def test_usd_offer_converts_when_the_rate_is_disclosed(tmp_path):
    result = _call(
        tmp_path,
        {
            "sku": "AH-HT-001",
            "reorder_quantity": 40,
            "comparison_date": "2026-09-25",
            "quotation_ids": ["QT-015"],
            "exchange_rate_ugx_per_usd": 3700,
            "exchange_rate_effective_date": "2026-09-25",
        },
    )
    assert result["status"] in {"ok", "no_result"} or result["data"] is not None
    ranked = result["data"]["ranked"]
    assert ranked[0]["quotation_id"] == "QT-015"
    assert ranked[0]["original_currency"] == "USD"
    assert result["data"]["exchange_rate"]["ugx_per_usd"] == 3700


def test_zero_quantity_is_invalid(tmp_path):
    result = _call(
        tmp_path,
        {"sku": "AH-CM-001", "reorder_quantity": 0, "comparison_date": "2026-09-25"},
    )
    assert result["status"] == "invalid_input"
    assert result["errors"][0]["code"] == "INVALID_PARAMETER"


def test_unknown_sku_is_refused(tmp_path):
    result = _call(
        tmp_path,
        {"sku": "AH-ZZ-999", "reorder_quantity": 1, "comparison_date": "2026-09-25"},
    )
    assert result["status"] == "invalid_input"
    assert result["errors"][0]["code"] == "UNKNOWN_SKU"


def test_no_recommendation_field_is_emitted(tmp_path):
    result = _call(
        tmp_path,
        {"sku": "AH-CM-001", "reorder_quantity": 120, "comparison_date": "2026-09-25"},
    )
    assert "recommended_quotation_id" not in result["data"]
