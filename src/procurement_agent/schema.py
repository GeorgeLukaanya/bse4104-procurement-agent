"""The Normalised Quotation contract.

Field list is Requirements Document v1.1, glossary entry "Normalised Quotation":

    supplier name, item name, quantity offered, unit of measure, unit price,
    currency, VAT treatment (inclusive or exclusive), VAT rate where stated,
    delivery or freight cost, lead time in days, and validity date

Eleven fields. Prompt Specification v1.0 section 6 arranges the same eleven as
seven quotation-level fields plus four item-level fields repeated per line item,
alongside a `missing_fields` array that exists to satisfy requirement 3.2
("recorded as null with a stated reason, never inferred").

Validation here is total. Requirement 3.3 and the AI Boundary Matrix v1.1
failure-behaviour section both require that non-conforming output is "rejected
outright rather than partially accepted", so there is deliberately no salvage
path: no coercion of a string to a number, no dropping of a bad line item, no
returning of whatever parsed. A half-parsed quotation is indistinguishable from
a complete one downstream, which is exactly the failure this rule prevents.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

# --- The eleven fields of the Normalised Quotation -------------------------
#
# Named here so that the count is assertable in a test rather than implied by
# the shape of a dict. The v1.1 revision raised this from six to eleven; a
# regression to six would silently reintroduce the defect that the Week 1
# cross-document audit found.

QUOTATION_LEVEL_FIELDS: tuple[str, ...] = (
    "supplier_name",
    "currency",
    "vat_treatment",
    "vat_rate_percent",
    "delivery_cost",
    "lead_time_days",
    "validity_date",
)

ITEM_LEVEL_FIELDS: tuple[str, ...] = (
    "item_name",
    "quantity",
    "unit_of_measure",
    "unit_price",
)

NORMALISED_QUOTATION_FIELDS: tuple[str, ...] = QUOTATION_LEVEL_FIELDS + ITEM_LEVEL_FIELDS

NORMALISED_QUOTATION_FIELD_COUNT = len(NORMALISED_QUOTATION_FIELDS)  # 11

# Prompt Specification v1.0 section 6: "inclusive | exclusive | null".
VAT_TREATMENTS: tuple[str, ...] = ("inclusive", "exclusive")

# Prompt Specification v1.0 section 6: "YYYY-MM-DD | null".
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_TOP_LEVEL_KEYS = set(QUOTATION_LEVEL_FIELDS) | {"items", "missing_fields"}
_ITEM_KEYS = set(ITEM_LEVEL_FIELDS)


class SchemaValidationError(ValueError):
    """Model output did not conform to the Normalised Quotation contract.

    Requirement 3.3: the quotation is marked extraction-failed and the reason is
    displayed. Nothing is salvaged from the offending payload.
    """

    def __init__(self, message: str, violations: list[str] | None = None) -> None:
        self.violations = violations or [message]
        super().__init__(message)


@dataclass(frozen=True)
class MissingField:
    """One entry of the `missing_fields` array. Requirement 3.2."""

    field: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "reason": self.reason}


@dataclass(frozen=True)
class LineItem:
    """The four item-level fields, as stated in the source document.

    `unit_of_measure` is carried verbatim. Prompt Specification v1.0 section 3:
    "The model extracts the unit of measure as stated in the document. It does
    not convert between units and does not supply a conversion factor."
    """

    item_name: str | None
    quantity: float | None
    unit_of_measure: str | None
    unit_price: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_name": self.item_name,
            "quantity": self.quantity,
            "unit_of_measure": self.unit_of_measure,
            "unit_price": self.unit_price,
        }


@dataclass(frozen=True)
class NormalisedQuotation:
    """A validated Normalised Quotation record.

    Reaching this type means the payload conformed. It carries no computed
    figure of any kind — every value is as stated in the source document.
    """

    supplier_name: str | None
    currency: str | None
    vat_treatment: str | None
    vat_rate_percent: float | None
    delivery_cost: float | None
    lead_time_days: float | None
    validity_date: str | None
    items: tuple[LineItem, ...] = ()
    missing_fields: tuple[MissingField, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "supplier_name": self.supplier_name,
            "currency": self.currency,
            "vat_treatment": self.vat_treatment,
            "vat_rate_percent": self.vat_rate_percent,
            "delivery_cost": self.delivery_cost,
            "lead_time_days": self.lead_time_days,
            "validity_date": self.validity_date,
            "items": [item.to_dict() for item in self.items],
            "missing_fields": [mf.to_dict() for mf in self.missing_fields],
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# --- Response schema handed to the provider --------------------------------


def response_schema() -> dict[str, Any]:
    """The schema passed to the google-genai `response_schema` setting.

    Prompt Specification v1.0 section 4 records this as a decoding setting:
    "Constrained decoding, non-conforming output rejected at the API boundary."
    The local validator below is still authoritative; constrained decoding
    narrows what the model can emit, it does not remove our obligation to check.

    Nullable is used rather than omitting fields, because requirement 3.2 needs
    an explicit null to pair with a `missing_fields` reason. A field that is
    simply absent carries no reason with it.
    """
    return {
        "type": "OBJECT",
        "properties": {
            "supplier_name": {"type": "STRING", "nullable": True},
            "currency": {"type": "STRING", "nullable": True},
            "vat_treatment": {
                "type": "STRING",
                "nullable": True,
                "enum": list(VAT_TREATMENTS),
            },
            "vat_rate_percent": {"type": "NUMBER", "nullable": True},
            "delivery_cost": {"type": "NUMBER", "nullable": True},
            "lead_time_days": {"type": "NUMBER", "nullable": True},
            "validity_date": {"type": "STRING", "nullable": True},
            "items": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "item_name": {"type": "STRING", "nullable": True},
                        "quantity": {"type": "NUMBER", "nullable": True},
                        "unit_of_measure": {"type": "STRING", "nullable": True},
                        "unit_price": {"type": "NUMBER", "nullable": True},
                    },
                    "required": list(ITEM_LEVEL_FIELDS),
                },
            },
            "missing_fields": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "field": {"type": "STRING"},
                        "reason": {"type": "STRING"},
                    },
                    "required": ["field", "reason"],
                },
            },
        },
        "required": list(QUOTATION_LEVEL_FIELDS) + ["items", "missing_fields"],
    }


# --- Validation ------------------------------------------------------------


def _is_number(value: Any) -> bool:
    # bool is a subclass of int in Python; a JSON true is not a number here.
    return (
        isinstance(value, (int, float)) and not isinstance(value, bool)
        and (not isinstance(value, float) or math.isfinite(value))
    )


def _check_optional_string(
    value: Any, name: str, violations: list[str]
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        violations.append(f"{name}: expected string or null, got {type(value).__name__}")
        return None
    return value


def _check_optional_number(
    value: Any, name: str, violations: list[str]
) -> float | None:
    if value is None:
        return None
    if not _is_number(value):
        violations.append(f"{name}: expected finite number or null, got {type(value).__name__}")
        return None
    return float(value)


def parse_response(raw: str | bytes | bytearray) -> dict[str, Any]:
    """Decode the raw model response into a dict, or raise SchemaValidationError.

    Rule 7 of the system instruction forbids markdown code fences, so an
    unparseable payload is a conformance failure and is reported as one rather
    than being stripped and retried.
    """
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SchemaValidationError(f"response was not valid UTF-8: {exc}") from exc
    if not isinstance(raw, str):
        raise SchemaValidationError(
            f"response was {type(raw).__name__}, expected a JSON string"
        )
    text = raw.strip()
    if not text:
        raise SchemaValidationError("response was empty")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(f"response was not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SchemaValidationError(
            f"response root was {type(payload).__name__}, expected a JSON object"
        )
    return payload


def validate(payload: dict[str, Any]) -> NormalisedQuotation:
    """Validate a decoded payload against the Normalised Quotation contract.

    Raises SchemaValidationError listing every violation found. Nothing is
    returned partially: requirement 3.3 requires outright rejection.
    """
    if not isinstance(payload, dict):
        raise SchemaValidationError(
            f"payload was {type(payload).__name__}, expected a JSON object"
        )

    violations: list[str] = []

    unexpected = sorted(set(payload) - _TOP_LEVEL_KEYS)
    if unexpected:
        violations.append(f"unexpected top-level keys: {', '.join(unexpected)}")

    for name in QUOTATION_LEVEL_FIELDS:
        if name not in payload:
            violations.append(f"{name}: required field absent")
    for name in ("items", "missing_fields"):
        if name not in payload:
            violations.append(f"{name}: required field absent")

    supplier_name = _check_optional_string(
        payload.get("supplier_name"), "supplier_name", violations
    )
    currency = _check_optional_string(payload.get("currency"), "currency", violations)

    vat_treatment = _check_optional_string(
        payload.get("vat_treatment"), "vat_treatment", violations
    )
    if vat_treatment is not None and vat_treatment not in VAT_TREATMENTS:
        violations.append(
            f"vat_treatment: expected one of {', '.join(VAT_TREATMENTS)} or null, "
            f"got {vat_treatment!r}"
        )

    vat_rate_percent = _check_optional_number(
        payload.get("vat_rate_percent"), "vat_rate_percent", violations
    )
    delivery_cost = _check_optional_number(
        payload.get("delivery_cost"), "delivery_cost", violations
    )
    lead_time_days = _check_optional_number(
        payload.get("lead_time_days"), "lead_time_days", violations
    )

    validity_date = _check_optional_string(
        payload.get("validity_date"), "validity_date", violations
    )
    if validity_date is not None and not _ISO_DATE.match(validity_date):
        violations.append(
            f"validity_date: expected YYYY-MM-DD or null, got {validity_date!r}"
        )

    items: list[LineItem] = []
    raw_items = payload.get("items")
    if raw_items is None and "items" in payload:
        violations.append("items: expected an array, got null")
    elif "items" in payload:
        if not isinstance(raw_items, list):
            violations.append(
                f"items: expected an array, got {type(raw_items).__name__}"
            )
        else:
            for index, raw_item in enumerate(raw_items):
                label = f"items[{index}]"
                if not isinstance(raw_item, dict):
                    violations.append(
                        f"{label}: expected an object, got {type(raw_item).__name__}"
                    )
                    continue
                extra = sorted(set(raw_item) - _ITEM_KEYS)
                if extra:
                    violations.append(
                        f"{label}: unexpected keys: {', '.join(extra)}"
                    )
                for name in ITEM_LEVEL_FIELDS:
                    if name not in raw_item:
                        violations.append(f"{label}.{name}: required field absent")
                items.append(
                    LineItem(
                        item_name=_check_optional_string(
                            raw_item.get("item_name"), f"{label}.item_name", violations
                        ),
                        quantity=_check_optional_number(
                            raw_item.get("quantity"), f"{label}.quantity", violations
                        ),
                        unit_of_measure=_check_optional_string(
                            raw_item.get("unit_of_measure"),
                            f"{label}.unit_of_measure",
                            violations,
                        ),
                        unit_price=_check_optional_number(
                            raw_item.get("unit_price"), f"{label}.unit_price", violations
                        ),
                    )
                )

    missing: list[MissingField] = []
    raw_missing = payload.get("missing_fields")
    if raw_missing is None and "missing_fields" in payload:
        violations.append("missing_fields: expected an array, got null")
    elif "missing_fields" in payload:
        if not isinstance(raw_missing, list):
            violations.append(
                f"missing_fields: expected an array, got {type(raw_missing).__name__}"
            )
        else:
            for index, entry in enumerate(raw_missing):
                label = f"missing_fields[{index}]"
                if not isinstance(entry, dict):
                    violations.append(
                        f"{label}: expected an object, got {type(entry).__name__}"
                    )
                    continue
                name = entry.get("field")
                reason = entry.get("reason")
                if not isinstance(name, str) or not name.strip():
                    violations.append(f"{label}.field: expected a non-empty string")
                    continue
                if not isinstance(reason, str) or not reason.strip():
                    # Requirement 3.2 requires a stated reason. An entry without
                    # one does not satisfy the requirement, so it is a violation
                    # rather than something to fill in with a placeholder.
                    violations.append(
                        f"{label}.reason: expected a non-empty string; requirement "
                        "3.2 requires a stated reason for every null field"
                    )
                    continue
                missing.append(MissingField(field=name, reason=reason))

    if violations:
        raise SchemaValidationError(
            "output does not conform to the Normalised Quotation schema: "
            + "; ".join(violations),
            violations=violations,
        )

    return NormalisedQuotation(
        supplier_name=supplier_name,
        currency=currency,
        vat_treatment=vat_treatment,
        vat_rate_percent=vat_rate_percent,
        delivery_cost=delivery_cost,
        lead_time_days=lead_time_days,
        validity_date=validity_date,
        items=tuple(items),
        missing_fields=tuple(missing),
    )


def validate_raw(raw: str | bytes | bytearray) -> NormalisedQuotation:
    """parse_response followed by validate."""
    return validate(parse_response(raw))


# --- Landed cost readiness -------------------------------------------------
#
# Requirement 6.3: "IF a quotation lacks a field required to compute Landed Cost
# (unit of measure, VAT treatment, or delivery cost), THEN THE Deterministic
# Layer SHALL exclude it from automated ranking, present it separately, and
# state which field is missing."
#
# This package reports readiness. It does not compute landed cost, rank, or
# decide anything — requirement 6.6 forbids the AI layer from performing any
# arithmetic contributing to a displayed figure, and the calculator that owns
# that arithmetic is a separate deterministic component.
#
# Requirement 6.3 names three fields. Requirement 6.1 implies three more, and
# they are checked here and labelled with the clause they come from:
#
#   currency      6.1 applies the Configured Exchange Rate "where required",
#                 which cannot be decided without knowing the currency.
#   unit_price    6.1 computes Normalised Unit Cost from the quoted price.
#   vat_rate      6.1 computes "applicable VAT". Only checked when treatment is
#                 exclusive; an inclusive price needs no rate to be compared.
#
# `quantity` is deliberately NOT a blocker. Requirement 6.1 extends cost over
# the Reorder Quantity, which comes from the Inventory Snapshot (requirement 1),
# not from the supplier's quoted quantity offered.

LANDED_COST_CLAUSES: dict[str, str] = {
    "vat_treatment": "6.3",
    "delivery_cost": "6.3",
    "unit_of_measure": "6.3",
    "currency": "6.1",
    "unit_price": "6.1",
    "vat_rate_percent": "6.1",
}


@dataclass(frozen=True)
class LandedCostBlocker:
    """One field whose absence excludes this quotation from automated ranking."""

    field: str
    clause: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "clause": self.clause, "reason": self.reason}


@dataclass(frozen=True)
class LandedCostReadiness:
    """Whether the deterministic calculator has everything it needs."""

    ready: bool
    blockers: tuple[LandedCostBlocker, ...] = ()

    @property
    def blocking_fields(self) -> tuple[str, ...]:
        return tuple(b.field for b in self.blockers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "blockers": [b.to_dict() for b in self.blockers],
        }


def landed_cost_readiness(record: NormalisedQuotation) -> LandedCostReadiness:
    """Report which landed-cost inputs this record lacks, by name."""
    blockers: list[LandedCostBlocker] = []

    def block(name: str, reason: str) -> None:
        blockers.append(
            LandedCostBlocker(
                field=name, clause=LANDED_COST_CLAUSES[name], reason=reason
            )
        )

    if record.vat_treatment is None:
        block(
            "vat_treatment",
            "VAT treatment not stated, so an inclusive price cannot be "
            "distinguished from an exclusive one",
        )
    elif record.vat_treatment == "exclusive" and record.vat_rate_percent is None:
        block(
            "vat_rate_percent",
            "prices are VAT exclusive but no VAT rate is stated, so applicable "
            "VAT cannot be computed",
        )

    if record.delivery_cost is None:
        block(
            "delivery_cost",
            "delivery or freight cost not stated, so it cannot be apportioned "
            "into landed cost",
        )

    if record.currency is None:
        block(
            "currency",
            "currency not stated, so it cannot be determined whether the "
            "Configured Exchange Rate applies",
        )

    if not record.items:
        block("unit_price", "no line items were extracted, so there is no price")
        block("unit_of_measure", "no line items were extracted, so there is no unit")
    else:
        for index, item in enumerate(record.items):
            label = item.item_name or f"item {index + 1}"
            if item.unit_of_measure is None:
                block(
                    "unit_of_measure",
                    f"{label}: unit of measure not stated, so a per-carton price "
                    "cannot be normalised against a per-piece price",
                )
            if item.unit_price is None:
                block("unit_price", f"{label}: unit price not stated")

    return LandedCostReadiness(ready=not blockers, blockers=tuple(blockers))
