"""Hand-written input checks. ``jsonschema`` is not a runtime dependency.

Reject, do not salvage: a request that does not conform is refused whole.
Every applicable error is returned, never only the first.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .contract import (
    CATEGORIES,
    CLAUSE_ID_PATTERN,
    CODE_FORBIDDEN_TRANSITION,
    CODE_INVALID_PARAMETER,
    CODE_MISSING_PARAMETER,
    ISO_DATE_PATTERN,
    LOCATIONS,
    QUOTATION_ID_PATTERN,
    SKU_PATTERN,
    SUPPLIER_ID_PATTERN,
    error,
)

_SKU = re.compile(SKU_PATTERN)
_SUPPLIER = re.compile(SUPPLIER_ID_PATTERN)
_QUOTATION = re.compile(QUOTATION_ID_PATTERN)
_DATE = re.compile(ISO_DATE_PATTERN)
_CLAUSE = re.compile(CLAUSE_ID_PATTERN)


def is_iso_date(value: Any) -> bool:
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _unexpected_keys(payload: dict[str, Any], allowed: set[str]) -> list[dict[str, Any]]:
    errors = []
    for key in payload:
        if key not in allowed:
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    f"{key!r} is not an accepted field; additional properties are refused.",
                    field=key,
                )
            )
    return errors


def _require_object(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        return []
    return [
        error(
            CODE_INVALID_PARAMETER,
            "request must be a JSON object",
        )
    ]


def validate_reorder_input(payload: Any) -> list[dict[str, Any]]:
    errors = _require_object(payload)
    if errors:
        return errors
    errors.extend(
        _unexpected_keys(payload, {"review_date", "skus", "location", "include_sufficient"})
    )
    if "review_date" not in payload:
        errors.append(
            error(CODE_MISSING_PARAMETER, "review_date is required.", field="review_date")
        )
    elif not is_iso_date(payload["review_date"]):
        errors.append(
            error(
                CODE_INVALID_PARAMETER,
                "review_date must be YYYY-MM-DD.",
                field="review_date",
            )
        )
    if "skus" in payload:
        errors.extend(_string_array(payload["skus"], "skus", _SKU, "AH-XX-000"))
    if "location" in payload:
        location = payload["location"]
        if location is not None and location not in LOCATIONS:
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    "location must be Nakawa Main Store, Kireka Branch, or null.",
                    field="location",
                )
            )
    if "include_sufficient" in payload and not isinstance(payload["include_sufficient"], bool):
        errors.append(
            error(
                CODE_INVALID_PARAMETER,
                "include_sufficient must be a boolean.",
                field="include_sufficient",
            )
        )
    return errors


def validate_eligibility_input(payload: Any) -> list[dict[str, Any]]:
    errors = _require_object(payload)
    if errors:
        return errors
    errors.extend(
        _unexpected_keys(
            payload,
            {"category", "as_of_date", "supplier_ids", "supplier_names", "quotation_ids"},
        )
    )
    if "category" not in payload:
        errors.append(error(CODE_MISSING_PARAMETER, "category is required.", field="category"))
    elif payload["category"] not in CATEGORIES:
        errors.append(
            error(
                CODE_INVALID_PARAMETER,
                "category is not a known product category.",
                field="category",
            )
        )
    if "as_of_date" not in payload:
        errors.append(
            error(CODE_MISSING_PARAMETER, "as_of_date is required.", field="as_of_date")
        )
    elif not is_iso_date(payload["as_of_date"]):
        errors.append(
            error(
                CODE_INVALID_PARAMETER,
                "as_of_date must be YYYY-MM-DD.",
                field="as_of_date",
            )
        )
    has_ids = "supplier_ids" in payload
    has_names = "supplier_names" in payload
    if not has_ids and not has_names:
        errors.append(
            error(
                CODE_MISSING_PARAMETER,
                "one of supplier_ids or supplier_names is required.",
                field="supplier_ids",
            )
        )
    if has_ids:
        errors.extend(_string_array(payload["supplier_ids"], "supplier_ids", _SUPPLIER, "SUP-000"))
    if has_names:
        errors.extend(_name_array(payload["supplier_names"], "supplier_names"))
    if "quotation_ids" in payload:
        errors.extend(
            _string_array(payload["quotation_ids"], "quotation_ids", _QUOTATION, "QT-000")
        )
    return errors


def validate_compare_input(payload: Any) -> list[dict[str, Any]]:
    errors = _require_object(payload)
    if errors:
        return errors
    errors.extend(
        _unexpected_keys(
            payload,
            {
                "sku",
                "reorder_quantity",
                "comparison_date",
                "quotation_ids",
                "exchange_rate_ugx_per_usd",
                "exchange_rate_effective_date",
            },
        )
    )
    if "sku" not in payload:
        errors.append(error(CODE_MISSING_PARAMETER, "sku is required.", field="sku"))
    elif not isinstance(payload["sku"], str) or not _SKU.fullmatch(payload["sku"]):
        errors.append(
            error(CODE_INVALID_PARAMETER, "sku must match AH-XX-000.", field="sku")
        )
    if "reorder_quantity" not in payload:
        errors.append(
            error(
                CODE_MISSING_PARAMETER,
                "reorder_quantity is required.",
                field="reorder_quantity",
            )
        )
    else:
        quantity = payload["reorder_quantity"]
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    "reorder_quantity must be a positive integer; there is no cost of ordering nothing.",
                    field="reorder_quantity",
                )
            )
    if "comparison_date" not in payload:
        errors.append(
            error(
                CODE_MISSING_PARAMETER,
                "comparison_date is required.",
                field="comparison_date",
            )
        )
    elif not is_iso_date(payload["comparison_date"]):
        errors.append(
            error(
                CODE_INVALID_PARAMETER,
                "comparison_date must be YYYY-MM-DD.",
                field="comparison_date",
            )
        )
    if "quotation_ids" in payload:
        errors.extend(
            _string_array(payload["quotation_ids"], "quotation_ids", _QUOTATION, "QT-000")
        )
    if "exchange_rate_ugx_per_usd" in payload:
        rate = payload["exchange_rate_ugx_per_usd"]
        if not isinstance(rate, (int, float)) or isinstance(rate, bool) or rate <= 0:
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    "exchange_rate_ugx_per_usd must be a number greater than zero.",
                    field="exchange_rate_ugx_per_usd",
                )
            )
    if "exchange_rate_effective_date" in payload and not is_iso_date(
        payload["exchange_rate_effective_date"]
    ):
        errors.append(
            error(
                CODE_INVALID_PARAMETER,
                "exchange_rate_effective_date must be YYYY-MM-DD.",
                field="exchange_rate_effective_date",
            )
        )
    return errors


def validate_draft_input(payload: Any) -> list[dict[str, Any]]:
    errors = _require_object(payload)
    if errors:
        return errors
    errors.extend(
        _unexpected_keys(
            payload,
            {
                "review_date",
                "officer_username",
                "status",
                "items",
                "policy_clauses",
                "justification",
            },
        )
    )
    for field in ("review_date", "officer_username", "items", "justification"):
        if field not in payload:
            errors.append(
                error(CODE_MISSING_PARAMETER, f"{field} is required.", field=field)
            )
    if "review_date" in payload and not is_iso_date(payload["review_date"]):
        errors.append(
            error(
                CODE_INVALID_PARAMETER,
                "review_date must be YYYY-MM-DD.",
                field="review_date",
            )
        )
    if "officer_username" in payload:
        name = payload["officer_username"]
        if not isinstance(name, str) or not name.strip():
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    "officer_username must be a non-empty string.",
                    field="officer_username",
                )
            )
    if "justification" in payload:
        text = payload["justification"]
        if not isinstance(text, str) or not text.strip():
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    "justification must be a non-empty string.",
                    field="justification",
                )
            )
    if "status" in payload and payload["status"] != "DRAFT":
        errors.append(
            error(
                CODE_FORBIDDEN_TRANSITION,
                f'status must be DRAFT; {payload["status"]!r} was requested. '
                "Requirement 14.3 permits no programmatic transition beyond DRAFT. "
                "Nothing was written.",
                field="status",
            )
        )
    if "items" in payload:
        errors.extend(_draft_items(payload["items"]))
    if "policy_clauses" in payload:
        errors.extend(
            _string_array(payload["policy_clauses"], "policy_clauses", _CLAUSE, "POL-000-C00")
        )
    return errors


def _draft_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        return [
            error(
                CODE_INVALID_PARAMETER,
                "items must be a non-empty array.",
                field="items",
            )
        ]
    errors: list[dict[str, Any]] = []
    allowed = {
        "sku",
        "reorder_quantity",
        "comparison_reference",
        "recommended_quotation_id",
        "unresolved_issues",
    }
    for index, item in enumerate(items):
        prefix = f"items[{index}]"
        if not isinstance(item, dict):
            errors.append(
                error(CODE_INVALID_PARAMETER, f"{prefix} must be an object.", field=prefix)
            )
            continue
        for key in item:
            if key not in allowed:
                errors.append(
                    error(
                        CODE_INVALID_PARAMETER,
                        f"{prefix}.{key} is not an accepted field.",
                        field=f"{prefix}.{key}",
                    )
                )
        for required in ("sku", "reorder_quantity", "comparison_reference"):
            if required not in item:
                errors.append(
                    error(
                        CODE_MISSING_PARAMETER,
                        f"{prefix}.{required} is required.",
                        field=f"{prefix}.{required}",
                    )
                )
        sku = item.get("sku")
        if "sku" in item and (not isinstance(sku, str) or not _SKU.fullmatch(sku)):
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    f"{prefix}.sku must match AH-XX-000.",
                    field=f"{prefix}.sku",
                )
            )
        quantity = item.get("reorder_quantity")
        if "reorder_quantity" in item and (
            not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0
        ):
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    f"{prefix}.reorder_quantity must be a positive integer.",
                    field=f"{prefix}.reorder_quantity",
                )
            )
        reference = item.get("comparison_reference")
        if "comparison_reference" in item and (
            not isinstance(reference, str) or not reference.strip()
        ):
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    f"{prefix}.comparison_reference must be a non-empty string.",
                    field=f"{prefix}.comparison_reference",
                )
            )
        rec = item.get("recommended_quotation_id")
        if rec is not None and (
            not isinstance(rec, str) or (rec != "" and not _QUOTATION.fullmatch(rec))
        ):
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    f"{prefix}.recommended_quotation_id must be QT-000 or null.",
                    field=f"{prefix}.recommended_quotation_id",
                )
            )
        issues = item.get("unresolved_issues")
        if issues is not None and (
            not isinstance(issues, list) or any(not isinstance(x, str) for x in issues)
        ):
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    f"{prefix}.unresolved_issues must be an array of strings.",
                    field=f"{prefix}.unresolved_issues",
                )
            )
    return errors


def _string_array(
    value: Any,
    field: str,
    pattern: re.Pattern[str],
    example: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        return [
            error(
                CODE_INVALID_PARAMETER,
                f"{field} must be a non-empty array.",
                field=field,
            )
        ]
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str) or not pattern.fullmatch(item):
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    f"{field}[{index}] must match {example}.",
                    field=field,
                )
            )
            continue
        if item in seen:
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    f"{field} values must be unique; {item!r} was repeated.",
                    field=field,
                )
            )
        seen.add(item)
    return errors


def _name_array(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        return [
            error(
                CODE_INVALID_PARAMETER,
                f"{field} must be a non-empty array.",
                field=field,
            )
        ]
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    f"{field}[{index}] must be a non-empty string.",
                    field=field,
                )
            )
            continue
        if item in seen:
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    f"{field} values must be unique; {item!r} was repeated.",
                    field=field,
                )
            )
        seen.add(item)
    return errors
