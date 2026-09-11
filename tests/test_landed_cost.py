"""Landed-cost readiness. Requirement 6.3: name the specific missing field."""

from __future__ import annotations

from conftest import conforming_payload

from procurement_agent import schema


def readiness(**overrides):
    return schema.landed_cost_readiness(schema.validate(conforming_payload(**overrides)))


def test_complete_record_is_ready_for_ranking():
    result = readiness()
    assert result.ready is True
    assert result.blockers == ()


def test_record_missing_landed_cost_inputs_names_the_specific_fields():
    """A record missing several inputs reports every one of them, by name."""
    result = readiness(
        currency=None,
        vat_treatment=None,
        delivery_cost=None,
        items=[
            {
                "item_name": "Steel door frame",
                "quantity": 14,
                "unit_of_measure": None,
                "unit_price": 185000,
            }
        ],
        missing_fields=[
            {"field": "currency", "reason": "no currency stated"},
            {"field": "vat_treatment", "reason": "VAT treatment not stated"},
            {"field": "delivery_cost", "reason": "no delivery terms stated"},
            {"field": "unit_of_measure", "reason": "unit not stated"},
        ],
    )
    assert result.ready is False
    assert set(result.blocking_fields) == {
        "currency",
        "vat_treatment",
        "delivery_cost",
        "unit_of_measure",
    }
    for blocker in result.blockers:
        assert blocker.reason, "every blocker must state why it blocks"
        assert blocker.clause in {"6.1", "6.3"}


def test_the_three_fields_named_by_requirement_6_3_each_block_alone():
    assert readiness(vat_treatment=None).blocking_fields == ("vat_treatment",)
    assert readiness(delivery_cost=None).blocking_fields == ("delivery_cost",)
    assert readiness(
        items=[
            {
                "item_name": "Cement",
                "quantity": 1,
                "unit_of_measure": None,
                "unit_price": 34500,
            }
        ]
    ).blocking_fields == ("unit_of_measure",)


def test_exclusive_vat_without_a_rate_blocks_but_inclusive_does_not():
    """6.1 computes applicable VAT; an exclusive price needs the rate to do so."""
    assert readiness(vat_treatment="exclusive", vat_rate_percent=None).blocking_fields == (
        "vat_rate_percent",
    )
    assert readiness(vat_treatment="inclusive", vat_rate_percent=None).ready is True


def test_quantity_offered_is_not_a_landed_cost_blocker():
    """6.1 extends cost over the Reorder Quantity, which comes from inventory."""
    result = readiness(
        items=[
            {
                "item_name": "Cement",
                "quantity": None,
                "unit_of_measure": "per bag",
                "unit_price": 34500,
            }
        ]
    )
    assert result.ready is True


def test_no_line_items_blocks_on_price_and_unit():
    result = readiness(items=[])
    assert result.ready is False
    assert set(result.blocking_fields) == {"unit_price", "unit_of_measure"}


def test_readiness_serialises_for_the_run_log():
    payload = readiness(delivery_cost=None).to_dict()
    assert payload["ready"] is False
    assert payload["blockers"][0]["field"] == "delivery_cost"
    assert payload["blockers"][0]["clause"] == "6.3"
