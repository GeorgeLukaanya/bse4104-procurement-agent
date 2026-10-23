"""Formatters for the optional operator view. Streamlit is not imported."""

from __future__ import annotations

from procurement_agent.ui.view import (
    STATUS_CONFIRM,
    STATUS_DRAFT,
    STATUS_NO_OFFER,
    STATUS_NOT_STARTED,
    STATUS_RATE,
    eligibility_rows,
    excluded_rows,
    flagged_items,
    load_sku_labels,
    memory_lines,
    money,
    plain_exclusions,
    quotations_for,
    ranked_rows,
    reorder_rows,
    requirement_lines,
    saved_status,
    status_for,
    step_progress,
)


def test_sku_list_includes_cement():
    labels = dict(load_sku_labels())
    assert "AH-CM-001" in labels
    assert "Portland cement" in labels["AH-CM-001"]


def test_reorder_and_eligibility_rows():
    reorder = {
        "items": [
            {
                "sku": "AH-CM-001",
                "item_name": "Portland cement 42.5N 50 kg bag",
                "current_stock": 150,
                "reorder_point": 150,
                "target_stock_level": 270,
                "reorder_quantity": 120,
                "unit_of_measure": "bag",
            }
        ]
    }
    eligibility = {
        "results": [
            {
                "registered_name": "Bugolobi Hardware Supplies",
                "supplier_id": "SUP-004",
                "eligible": True,
                "avl_status": "ACTIVE",
                "exclusion_reasons": [],
            },
            {
                "registered_name": "Kireka Steel and Cement Ltd",
                "supplier_id": "SUP-006",
                "eligible": False,
                "avl_status": "BLACKLISTED",
                "exclusion_reasons": ["BLACKLISTED"],
            },
        ]
    }
    rows = reorder_rows(reorder)
    assert rows[0]["SKU"] == "AH-CM-001"
    assert rows[0]["Reorder qty"] == 120
    elig = eligibility_rows(eligibility)
    assert elig[0]["Eligible"] == "yes"
    assert elig[1]["Eligible"] == "no"
    assert elig[1]["Reasons"] == "BLACKLISTED"


def test_comparison_tables_match_cement_example():
    comparison = {
        "ranked": [
            {
                "rank": 1,
                "quotation_id": "QT-002",
                "supplier_name": "Bugolobi Hardware Supplies",
                "normalised_unit_cost_ugx": 31000.0,
                "vat_amount_ugx": 669600.0,
                "delivery_cost_ugx": 90000.0,
                "landed_cost_ugx": 4479600.0,
            }
        ],
        "excluded": [
            {
                "quotation_id": "QT-004",
                "supplier_name": "Kireka Steel and Cement Ltd",
                "reasons": ["BLACKLISTED"],
            }
        ],
        "quotation_requirement": {
            "clause": "POL-001-C02",
            "required_count": 3,
            "eligible_count": 1,
            "exception_required": True,
        },
        "sole_eligible_option": True,
    }
    ranked = ranked_rows(comparison)
    assert ranked[0]["Quotation"] == "QT-002"
    assert ranked[0]["Landed"] == "UGX 4,479,600"
    assert excluded_rows(comparison)[0]["Reasons"] == "BLACKLISTED"
    lines = requirement_lines(comparison)
    assert any("POL-001-C02" in line for line in lines)
    assert any("Exception required" in line for line in lines)


def test_memory_lines_are_advisory_summaries():
    notes = memory_lines(
        {
            "records": [
                {"id": "MEM-1", "summary": "SUP-004 late deliveries"},
            ]
        }
    )
    assert notes == ["MEM-1: SUP-004 late deliveries"]
    assert memory_lines(None) == []
    assert money(None) == "-"


def test_flagged_items_match_the_scan():
    items = {item["sku"]: item for item in flagged_items()}
    assert len(items) == 11
    assert items["AH-CM-001"]["to_order"] == 120
    assert items["AH-HT-001"]["to_order"] == 40


def test_quotations_for_helmet_show_usd_and_expired():
    held = {q["quotation_id"]: q for q in quotations_for("AH-HT-001", "2026-09-25")}
    assert held["QT-015"]["tone"] == "wait"
    assert held["QT-016"]["tone"] == "bad"
    assert held["QT-013"]["tone"] == "ok"


def test_status_for_stop_reasons(tmp_path):
    assert status_for(None, None) == STATUS_NOT_STARTED
    assert status_for("completed", "") == STATUS_DRAFT
    assert status_for("awaiting_human", "EXCHANGE_RATE_REQUIRED: ...") == STATUS_RATE
    assert status_for("awaiting_human", "MISSING_COMPONENT: ...") == STATUS_NO_OFFER
    assert status_for("awaiting_human", "Landed-cost comparison is on the table.") == STATUS_CONFIRM
    assert saved_status(tmp_path, "2026-09-25", "AH-CM-001", "a.nakato") == STATUS_NOT_STARTED
    (tmp_path / "AGT-2026-09-25-AH-CM-001-a.nakato.json").write_text(
        '{"stop_reason": "completed", "stop_detail": ""}', encoding="utf-8"
    )
    assert saved_status(tmp_path, "2026-09-25", "AH-CM-001", "a.nakato") == STATUS_DRAFT


def test_step_progress_and_plain_exclusions():
    assert step_progress({"items": []}, {"results": []}, {"ranked": []}, {}, None) == [True, True, True, False, False]
    assert step_progress({}, {}, {}, {"comparison": {"by": "a.nakato"}}, {"status": "DRAFT"})[3:] == [True, True]
    rows = plain_exclusions(
        {"excluded": [{"quotation_id": "QT-001", "supplier_id": "SUP-002", "supplier_name": "Lakeview",
                       "reasons": ["NAME_DISCREPANCY"]}]},
        {"results": [{"supplier_id": "SUP-002", "similar_registered_names": ["Lakeview Building Supplies"]}]},
    )
    assert rows[0]["codes"] == ["NAME_DISCREPANCY"]
    assert "does not match the approved register" in rows[0]["why"]
    assert "Lakeview Building Supplies" in rows[0]["why"]
