"""The Normalised Quotation contract, including the eleven-field count."""

from __future__ import annotations

import json

import pytest
from conftest import conforming_payload

from procurement_agent import schema


def test_normalised_quotation_carries_exactly_eleven_fields():
    """Requirements Document v1.1 glossary. Six would be the v1.0 defect.

    The v1.1 revision note records the change: "The extracted field set was
    extended from six fields to eleven, because comparison on unit price alone
    cannot solve the normalisation problem stated in the charter." This test
    exists so a regression to six fails loudly rather than quietly.
    """
    assert schema.NORMALISED_QUOTATION_FIELD_COUNT == 11
    assert set(schema.NORMALISED_QUOTATION_FIELDS) == {
        "supplier_name",
        "item_name",
        "quantity",
        "unit_of_measure",
        "unit_price",
        "currency",
        "vat_treatment",
        "vat_rate_percent",
        "delivery_cost",
        "lead_time_days",
        "validity_date",
    }
    assert len(schema.QUOTATION_LEVEL_FIELDS) == 7
    assert len(schema.ITEM_LEVEL_FIELDS) == 4


def test_response_schema_matches_prompt_specification_section_6():
    body = schema.response_schema()
    assert set(body["properties"]) == set(schema.QUOTATION_LEVEL_FIELDS) | {
        "items",
        "missing_fields",
    }
    item_props = body["properties"]["items"]["items"]["properties"]
    assert set(item_props) == set(schema.ITEM_LEVEL_FIELDS)
    assert body["properties"]["vat_treatment"]["enum"] == ["inclusive", "exclusive"]


def test_valid_payload_round_trips():
    record = schema.validate(conforming_payload())
    assert record.supplier_name == "Nakawa Building Supplies Ltd"
    assert record.items[0].unit_of_measure == "per bag"
    assert json.loads(record.to_json())["currency"] == "UGX"


def test_nulls_with_reasons_are_valid():
    record = schema.validate(
        conforming_payload(
            currency=None,
            missing_fields=[{"field": "currency", "reason": "no currency stated"}],
        )
    )
    assert record.currency is None
    assert record.missing_fields[0].field == "currency"


@pytest.mark.parametrize(
    "overrides, expected_fragment",
    [
        ({"vat_treatment": "maybe"}, "vat_treatment"),
        ({"validity_date": "02/10/2026"}, "validity_date"),
        ({"delivery_cost": "250,000"}, "delivery_cost"),
        ({"items": "not a list"}, "items"),
        ({"lead_time_days": True}, "lead_time_days"),
    ],
)
def test_non_conforming_values_are_rejected(overrides, expected_fragment):
    with pytest.raises(schema.SchemaValidationError) as exc:
        schema.validate(conforming_payload(**overrides))
    assert expected_fragment in str(exc.value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize(
    "field", ["vat_rate_percent", "delivery_cost", "lead_time_days", "quantity", "unit_price"],
)
def test_non_finite_extracted_numbers_are_rejected(field, value):
    payload = conforming_payload()
    target = payload["items"][0] if field in {"quantity", "unit_price"} else payload
    target[field] = value
    with pytest.raises(schema.SchemaValidationError, match=field):
        schema.validate_raw(json.dumps(payload))


def test_missing_field_entry_without_a_reason_is_rejected():
    """Requirement 3.2 requires a stated reason, not merely an acknowledgement."""
    with pytest.raises(schema.SchemaValidationError) as exc:
        schema.validate(
            conforming_payload(
                currency=None, missing_fields=[{"field": "currency", "reason": ""}]
            )
        )
    assert "3.2" in str(exc.value)


def test_absent_required_key_is_rejected():
    payload = conforming_payload()
    del payload["delivery_cost"]
    with pytest.raises(schema.SchemaValidationError) as exc:
        schema.validate(payload)
    assert "delivery_cost: required field absent" in str(exc.value)


def test_prose_and_code_fences_are_rejected_not_stripped():
    """System instruction rule 8 forbids fences, so a fenced body is a failure."""
    fenced = "```json\n" + json.dumps(conforming_payload()) + "\n```"
    with pytest.raises(schema.SchemaValidationError):
        schema.validate_raw(fenced)


def test_empty_response_is_rejected():
    with pytest.raises(schema.SchemaValidationError) as exc:
        schema.validate_raw("   ")
    assert "empty" in str(exc.value)
