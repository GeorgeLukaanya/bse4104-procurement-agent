"""check_reorder_need — inventory-status tool. Read-only.

Requirement 1.4: reorder quantity is ``target_stock_level - current_stock``,
computed here, never stored. Requirement 1.5: an empty list is ``no_result``,
not an error.
"""

from __future__ import annotations

from typing import Any

from .contract import (
    CODE_DATA_INTEGRITY_ERROR,
    CODE_DATA_SOURCE_UNAVAILABLE,
    CODE_UNKNOWN_SKU,
    STATUS_FAILED,
    STATUS_INVALID_INPUT,
    STATUS_NO_RESULT,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    error,
)
import re

from .data import DataIntegrityError, DataUnavailable, load_inventory

ISO_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def check_reorder_need(
    payload: dict[str, Any],
    *,
    inventory_path: str | None = None,
    register_path: str | None = None,
) -> tuple[str, dict[str, Any] | None, list[dict[str, Any]], str | None]:
    # The payload is validated below, so the date is not trustworthy yet.
    # Pass it on only when it is shaped like one: a stock system is asked for a
    # position "as at" a date, and sending it rubbish would turn a bad request
    # from this caller into an unavailable-source error from that one.
    asked_for = payload.get("review_date") if isinstance(payload, dict) else None
    as_of = asked_for if isinstance(asked_for, str) and ISO_DATE_ONLY.match(asked_for) else None
    try:
        rows, fingerprint = load_inventory(inventory_path, register_path, as_of=as_of)
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

    requested = payload.get("skus")
    location = payload.get("location")
    include_sufficient = bool(payload.get("include_sufficient", False))
    by_sku = {row["sku"]: row for row in rows}

    errors: list[dict[str, Any]] = []
    if requested:
        unknown = [sku for sku in requested if sku not in by_sku]
        for sku in unknown:
            errors.append(
                error(
                    CODE_UNKNOWN_SKU,
                    f"{sku} is not in the inventory snapshot.",
                    field="skus",
                )
            )
        if errors:
            return STATUS_INVALID_INPUT, None, errors, fingerprint
        scan = [by_sku[sku] for sku in requested]
    else:
        scan = list(rows)

    if location:
        scan = [row for row in scan if row["location"] == location]

    items: list[dict[str, Any]] = []
    flagged = 0
    for row in scan:
        at_or_below = row["current_stock"] <= row["reorder_point"]
        if at_or_below:
            flagged += 1
        if at_or_below or include_sufficient:
            quantity = row["target_stock_level"] - row["current_stock"]
            if quantity < 0:
                quantity = 0
            items.append(
                {
                    "sku": row["sku"],
                    "item_name": row["item_name"],
                    "category": row["category"],
                    "unit_of_measure": row["unit_of_measure"],
                    "current_stock": row["current_stock"],
                    "reorder_point": row["reorder_point"],
                    "target_stock_level": row["target_stock_level"],
                    "reorder_quantity": quantity,
                    "estimated_unit_cost_ugx": row["unit_cost_ugx"],
                    "estimated_total_ugx": quantity * row["unit_cost_ugx"],
                    "location": row["location"],
                    "at_or_below_reorder_point": at_or_below,
                }
            )

    data = {
        "review_date": payload["review_date"],
        "evaluated_count": len(scan),
        "flagged_count": flagged,
        "no_reorder_required": flagged == 0,
        "items": items,
    }
    status = STATUS_NO_RESULT if flagged == 0 else STATUS_OK
    return status, data, [], fingerprint
