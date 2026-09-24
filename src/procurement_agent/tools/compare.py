"""compare_quotations — deterministic comparison calculator. Read-only.

Every figure is computed here. Requirement 6.6 forbids the model from
contributing any arithmetic. The tool ranks; it does not recommend.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .contract import (
    CODE_DATA_INTEGRITY_ERROR,
    CODE_DATA_SOURCE_UNAVAILABLE,
    CODE_EXCHANGE_RATE_REQUIRED,
    CODE_INSUFFICIENT_QUOTATIONS,
    CODE_INVALID_PARAMETER,
    CODE_UNKNOWN_SKU,
    STATUS_FAILED,
    STATUS_INVALID_INPUT,
    STATUS_NO_RESULT,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    error,
)
from .data import DataIntegrityError, DataUnavailable, load_inventory, load_quotations, load_suppliers
from .eligibility import assess_supplier

TWOPLACES = Decimal("0.01")

BANDS = (
    (500_000, "below_500k", "POL-001-C01", 1),
    (5_000_000, "500k_to_under_5m", "POL-001-C02", 3),
    (None, "5m_and_above", "POL-001-C03", 3),
)


def compare_quotations(
    payload: dict[str, Any],
    *,
    inventory_path: str | None = None,
    quotations_path: str | None = None,
    suppliers_path: str | None = None,
    register_path: str | None = None,
) -> tuple[str, dict[str, Any] | None, list[dict[str, Any]], str | None]:
    try:
        inventory, _ = load_inventory(inventory_path, register_path)
        quotations, fingerprint = load_quotations(quotations_path, register_path)
        suppliers, _ = load_suppliers(suppliers_path, register_path)
    except DataUnavailable as exc:
        return (
            STATUS_UNAVAILABLE,
            None,
            [error(CODE_DATA_SOURCE_UNAVAILABLE, str(exc))],
            None,
        )
    except DataIntegrityError as exc:
        return (
            STATUS_FAILED,
            None,
            [error(CODE_DATA_INTEGRITY_ERROR, str(exc))],
            None,
        )

    sku = payload["sku"]
    stock = next((row for row in inventory if row["sku"] == sku), None)
    if stock is None:
        return (
            STATUS_INVALID_INPUT,
            None,
            [error(CODE_UNKNOWN_SKU, f"{sku} is not in the inventory snapshot.", field="sku")],
            fingerprint,
        )

    by_id = {row.get("quotation_id"): row for row in quotations}
    requested_ids = payload.get("quotation_ids")
    if requested_ids:
        missing = [qid for qid in requested_ids if qid not in by_id]
        if missing:
            return (
                STATUS_INVALID_INPUT,
                None,
                [
                    error(
                        CODE_INVALID_PARAMETER,
                        f"{qid} is not a held quotation.",
                        field="quotation_ids",
                    )
                    for qid in missing
                ],
                fingerprint,
            )
        candidates = [by_id[qid] for qid in requested_ids]
    else:
        candidates = [row for row in quotations if row.get("sku") == sku]

    rate = payload.get("exchange_rate_ugx_per_usd")
    rate_date = payload.get("exchange_rate_effective_date")
    needs_rate = any(
        (row.get("currency") not in (None, "UGX"))
        and _would_be_considered(row, stock, suppliers, payload["comparison_date"])
        for row in candidates
    )
    if needs_rate and rate is None:
        return (
            STATUS_INVALID_INPUT,
            None,
            [
                error(
                    CODE_EXCHANGE_RATE_REQUIRED,
                    "A non-UGX offer is in scope and no exchange rate was supplied. "
                    "POL-003-C01 requires the rate to be disclosed; the tool will not pick one.",
                    field="exchange_rate_ugx_per_usd",
                )
            ],
            fingerprint,
        )

    ranked_rows: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    by_supplier_id = {row.get("supplier_id"): row for row in suppliers}

    for quotation in candidates:
        reasons, missing_fields, computed = _evaluate_offer(
            quotation,
            stock=stock,
            suppliers=suppliers,
            by_supplier_id=by_supplier_id,
            comparison_date=payload["comparison_date"],
            reorder_quantity=payload["reorder_quantity"],
            rate=rate,
        )
        if reasons:
            excluded.append(
                {
                    "quotation_id": quotation.get("quotation_id"),
                    "supplier_id": quotation.get("supplier_id"),
                    "supplier_name": quotation.get("supplier_name"),
                    "reasons": reasons,
                    "missing_fields": missing_fields,
                }
            )
            continue
        ranked_rows.append(computed)

    ranked_rows.sort(key=lambda row: (row["landed_cost_ugx"], row["supplier_name"]))
    for index, row in enumerate(ranked_rows):
        row["rank"] = index + 1
        row["tie_broken_on_supplier_name"] = False
    for index, row in enumerate(ranked_rows):
        if index == 0:
            continue
        previous = ranked_rows[index - 1]
        if row["landed_cost_ugx"] == previous["landed_cost_ugx"]:
            row["tie_broken_on_supplier_name"] = True

    estimated_value = payload["reorder_quantity"] * stock["unit_cost_ugx"]
    band, clause, required = _value_band(estimated_value)
    eligible_count = len(ranked_rows)
    satisfied = eligible_count >= required
    requirement = {
        "value_band": band,
        "clause": clause,
        "required_count": required,
        "eligible_count": eligible_count,
        "satisfied": satisfied,
        "exception_required": not satisfied,
    }

    exchange = None
    if rate is not None:
        exchange = {
            "ugx_per_usd": rate,
            "effective_date": rate_date or payload["comparison_date"],
        }

    data = {
        "sku": sku,
        "reorder_quantity": payload["reorder_quantity"],
        "comparison_date": payload["comparison_date"],
        "currency": "UGX",
        "exchange_rate": exchange,
        "ranked": ranked_rows,
        "excluded": excluded,
        "quotation_requirement": requirement,
        "sole_eligible_option": eligible_count == 1,
    }
    errors: list[dict[str, Any]] = []
    if not satisfied:
        remain = "remains" if eligible_count == 1 else "remain"
        errors.append(
            error(
                CODE_INSUFFICIENT_QUOTATIONS,
                f"{clause} requires {required} eligible quotations for this value band; "
                f"{eligible_count} {remain} after exclusions.",
            )
        )
    status = STATUS_NO_RESULT if eligible_count == 0 else STATUS_OK
    return status, data, errors, fingerprint


def _would_be_considered(
    quotation: dict[str, Any],
    stock: dict[str, Any],
    suppliers: list[dict[str, Any]],
    comparison_date: str,
) -> bool:
    """True when the offer is eligible enough that currency conversion would apply."""
    supplier = next(
        (row for row in suppliers if row.get("supplier_id") == quotation.get("supplier_id")),
        None,
    )
    assessed = assess_supplier(
        supplier,
        requested=quotation.get("supplier_id") or quotation.get("supplier_name") or "",
        matched_by="supplier_id",
        category=stock["category"],
        as_of=comparison_date,
        register=suppliers,
        quotation=quotation,
    )
    return assessed["eligible"]


def _evaluate_offer(
    quotation: dict[str, Any],
    *,
    stock: dict[str, Any],
    suppliers: list[dict[str, Any]],
    by_supplier_id: dict[str, dict[str, Any]],
    comparison_date: str,
    reorder_quantity: int,
    rate: float | None,
) -> tuple[list[str], list[str], dict[str, Any] | None]:
    supplier = by_supplier_id.get(quotation.get("supplier_id"))
    assessed = assess_supplier(
        supplier,
        requested=quotation.get("supplier_id") or "",
        matched_by="supplier_id",
        category=stock["category"],
        as_of=comparison_date,
        register=suppliers,
        quotation=quotation,
    )
    reasons = list(assessed["exclusion_reasons"])
    missing: list[str] = []

    items = quotation.get("items") or []
    line = items[0] if items else {}
    unit_price = line.get("unit_price")
    quoted_unit = line.get("unit_of_measure")
    vat_treatment = quotation.get("vat_treatment")
    delivery = quotation.get("delivery_cost")
    currency = quotation.get("currency")
    factor = quotation.get("unit_conversion_factor")
    stock_unit = stock["unit_of_measure"]

    if unit_price is None:
        missing.append("unit_price")
    if quoted_unit is None:
        missing.append("unit_of_measure")
    if vat_treatment is None:
        missing.append("vat_treatment")
    if delivery is None:
        missing.append("delivery_cost")
    if currency is None:
        missing.append("currency")
    if vat_treatment == "exclusive" and quotation.get("vat_rate_percent") is None:
        missing.append("vat_rate_percent")
    units_differ = (
        quoted_unit is not None
        and stock_unit is not None
        and _norm_unit(quoted_unit) != _norm_unit(stock_unit)
    )
    if units_differ and not factor:
        missing.append("unit_conversion_factor")

    if missing and "INCOMPARABLE_QUOTATION" not in reasons:
        reasons.append("INCOMPARABLE_QUOTATION")
    if reasons:
        return reasons, missing, None

    conversion = Decimal(str(factor)) if factor else Decimal("1")
    price = Decimal(str(unit_price)) / conversion
    if currency == "USD":
        price = price * Decimal(str(rate))
        delivery_ugx = Decimal(str(delivery)) * Decimal(str(rate))
    else:
        delivery_ugx = Decimal(str(delivery))

    vat_rate = quotation.get("vat_rate_percent")
    vat_fraction = Decimal(str(vat_rate or 0)) / Decimal("100")
    if vat_treatment == "inclusive" and vat_fraction > 0:
        net_unit = price / (Decimal("1") + vat_fraction)
        vat_unit = price - net_unit
    elif vat_treatment == "inclusive":
        net_unit = price
        vat_unit = Decimal("0")
    else:
        net_unit = price
        vat_unit = net_unit * vat_fraction

    qty = Decimal(reorder_quantity)
    extended = _money(net_unit * qty)
    vat_amount = _money(vat_unit * qty)
    delivery_amount = _money(delivery_ugx)
    landed = _money(extended + vat_amount + delivery_amount)

    computed = {
        "rank": 0,
        "quotation_id": quotation.get("quotation_id"),
        "supplier_id": quotation.get("supplier_id"),
        "supplier_name": quotation.get("supplier_name"),
        "original_currency": currency,
        "original_unit_price": unit_price,
        "unit_conversion_factor": factor,
        "normalised_unit_cost_ugx": float(_money(net_unit)),
        "extended_cost_ugx": float(extended),
        "vat_amount_ugx": float(vat_amount),
        "delivery_cost_ugx": float(delivery_amount),
        "landed_cost_ugx": float(landed),
        "lead_time_days": quotation.get("lead_time_days"),
        "validity_date": quotation.get("validity_date"),
        "tie_broken_on_supplier_name": False,
    }
    return [], missing, computed


def _value_band(estimated_ugx: float) -> tuple[str, str, int]:
    if estimated_ugx < 500_000:
        return "below_500k", "POL-001-C01", 1
    if estimated_ugx < 5_000_000:
        return "500k_to_under_5m", "POL-001-C02", 3
    return "5m_and_above", "POL-001-C03", 3


def _money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _norm_unit(value: str) -> str:
    text = value.strip().lower()
    if text.startswith("per "):
        text = text[4:]
    return text
