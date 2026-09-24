"""check_supplier_eligibility — supplier-record tool. Read-only.

Every applicable exclusion reason is returned. A missing register never
reports anyone eligible (fail closed, POL-002-C01).
"""

from __future__ import annotations

from typing import Any

from .contract import (
    CODE_DATA_INTEGRITY_ERROR,
    CODE_DATA_SOURCE_UNAVAILABLE,
    CODE_INVALID_PARAMETER,
    STATUS_FAILED,
    STATUS_INVALID_INPUT,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    error,
)
from .data import DataIntegrityError, DataUnavailable, load_quotations, load_suppliers
from .names import names_match_exactly, similar_registered_names

REASON_AVL_ABSENT = "AVL_ABSENT"
REASON_BLACKLISTED = "BLACKLISTED"
REASON_SUSPENDED = "SUSPENDED"
REASON_OUT_OF_CATEGORY = "OUT_OF_CATEGORY"
REASON_EXPIRED = "EXPIRED"
REASON_NAME_DISCREPANCY = "NAME_DISCREPANCY"


def check_supplier_eligibility(
    payload: dict[str, Any],
    *,
    suppliers_path: str | None = None,
    quotations_path: str | None = None,
    register_path: str | None = None,
) -> tuple[str, dict[str, Any] | None, list[dict[str, Any]], str | None]:
    try:
        suppliers, fingerprint = load_suppliers(suppliers_path, register_path)
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

    quotations: list[dict[str, Any]] = []
    if payload.get("quotation_ids"):
        try:
            quotations, _ = load_quotations(quotations_path, register_path)
        except DataUnavailable as exc:
            return (
                STATUS_UNAVAILABLE,
                None,
                [error(CODE_DATA_SOURCE_UNAVAILABLE, str(exc))],
                fingerprint,
            )
        except DataIntegrityError as exc:
            return (
                STATUS_FAILED,
                None,
                [error(CODE_DATA_INTEGRITY_ERROR, str(exc))],
                fingerprint,
            )
        by_quote = {row.get("quotation_id"): row for row in quotations}
        missing = [qid for qid in payload["quotation_ids"] if qid not in by_quote]
        if missing:
            return (
                STATUS_INVALID_INPUT,
                None,
                [
                    error(
                        CODE_INVALID_PARAMETER,
                        f"{qid} is not a held quotation; expiry cannot be assessed.",
                        field="quotation_ids",
                    )
                    for qid in missing
                ],
                fingerprint,
            )

    category = payload["category"]
    as_of = payload["as_of_date"]
    results: list[dict[str, Any]] = []

    for supplier_id in payload.get("supplier_ids") or []:
        results.append(
            _assess(
                requested=supplier_id,
                matched_by="supplier_id",
                supplier=_by_id(suppliers, supplier_id),
                category=category,
                as_of=as_of,
                register=suppliers,
                quotations=_quotes_for_supplier(
                    quotations, payload.get("quotation_ids") or [], supplier_id=supplier_id
                ),
            )
        )
    for name in payload.get("supplier_names") or []:
        results.append(
            _assess(
                requested=name,
                matched_by="registered_name",
                supplier=_by_name(suppliers, name),
                category=category,
                as_of=as_of,
                register=suppliers,
                quotations=_quotes_for_supplier(
                    quotations, payload.get("quotation_ids") or [], supplier_name=name
                ),
            )
        )

    data = {
        "category": category,
        "as_of_date": as_of,
        "results": results,
    }
    return STATUS_OK, data, [], fingerprint


def assess_supplier(
    supplier: dict[str, Any] | None,
    *,
    requested: str,
    matched_by: str,
    category: str,
    as_of: str,
    register: list[dict[str, Any]],
    quotation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    quotations = [quotation] if quotation is not None else []
    return _assess(
        requested=requested,
        matched_by=matched_by,
        supplier=supplier,
        category=category,
        as_of=as_of,
        register=register,
        quotations=quotations,
    )


def _assess(
    *,
    requested: str,
    matched_by: str,
    supplier: dict[str, Any] | None,
    category: str,
    as_of: str,
    register: list[dict[str, Any]],
    quotations: list[dict[str, Any]],
) -> dict[str, Any]:
    reasons: list[str] = []
    similar: list[str] = []
    if supplier is None:
        reasons.append(REASON_AVL_ABSENT)
        similar = similar_registered_names(requested, register)
        if similar:
            reasons.append(REASON_NAME_DISCREPANCY)
        return {
            "requested": requested,
            "matched_by": "unmatched",
            "supplier_id": None,
            "registered_name": None,
            "avl_status": None,
            "approved_categories": [],
            "eligible": False,
            "exclusion_reasons": reasons,
            "similar_registered_names": similar,
        }

    supplier_id = supplier.get("supplier_id")
    registered_name = supplier.get("registered_name") or ""
    status = _status_on(supplier, as_of)
    approved = list(supplier.get("categories") or [])
    similar = similar_registered_names(
        registered_name, register, exclude_id=supplier_id
    )

    if status == "BLACKLISTED":
        reasons.append(REASON_BLACKLISTED)
    if status == "SUSPENDED":
        reasons.append(REASON_SUSPENDED)
    if category not in approved:
        reasons.append(REASON_OUT_OF_CATEGORY)
    if similar:
        reasons.append(REASON_NAME_DISCREPANCY)
    for quotation in quotations:
        validity = quotation.get("validity_date")
        if isinstance(validity, str) and validity < as_of:
            if REASON_EXPIRED not in reasons:
                reasons.append(REASON_EXPIRED)

    result = {
        "requested": requested,
        "matched_by": matched_by if supplier is not None else "unmatched",
        "supplier_id": supplier_id,
        "registered_name": registered_name,
        "avl_status": status,
        "approved_categories": approved,
        "eligible": not reasons,
        "exclusion_reasons": reasons,
        "similar_registered_names": similar,
    }
    if len(quotations) == 1:
        result["quotation_id"] = quotations[0].get("quotation_id")
    return result


def _status_on(supplier: dict[str, Any], as_of: str) -> str:
    recorded = supplier.get("avl_status") or "ACTIVE"
    effective = supplier.get("status_effective_date") or ""
    if recorded in {"SUSPENDED", "BLACKLISTED"}:
        if effective and as_of < effective:
            return "ACTIVE"
        return recorded
    return recorded


def _by_id(register: list[dict[str, Any]], supplier_id: str) -> dict[str, Any] | None:
    for supplier in register:
        if supplier.get("supplier_id") == supplier_id:
            return supplier
    return None


def _by_name(register: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for supplier in register:
        registered = supplier.get("registered_name") or ""
        if names_match_exactly(name, registered):
            return supplier
    return None


def _quotes_for_supplier(
    quotations: list[dict[str, Any]],
    quotation_ids: list[str],
    *,
    supplier_id: str | None = None,
    supplier_name: str | None = None,
) -> list[dict[str, Any]]:
    if not quotation_ids:
        return []
    wanted = set(quotation_ids)
    matched = []
    for row in quotations:
        if row.get("quotation_id") not in wanted:
            continue
        if supplier_id is not None and row.get("supplier_id") == supplier_id:
            matched.append(row)
        elif supplier_name is not None and names_match_exactly(
            supplier_name, row.get("supplier_name") or ""
        ):
            matched.append(row)
    return matched
