"""Formatters for the optional operator view. Streamlit is not imported."""

from __future__ import annotations

from procurement_agent.ui.view import (
    eligibility_rows,
    excluded_rows,
    load_sku_labels,
    memory_lines,
    money,
    ranked_rows,
    reorder_rows,
    requirement_lines,
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
