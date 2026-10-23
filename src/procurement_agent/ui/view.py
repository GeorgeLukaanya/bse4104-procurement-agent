"""Format workflow results for the operator view. No Streamlit import."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..tools.data import DEFAULT_INVENTORY


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "knowledge" / "data").is_dir():
            return parent
    return Path.cwd()


def load_sku_labels(inventory_path: Path | None = None) -> list[tuple[str, str]]:
    path = inventory_path or (repo_root() / DEFAULT_INVENTORY)
    rows: list[tuple[str, str]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            sku = (row.get("sku") or "").strip()
            name = (row.get("item_name") or "").strip()
            if sku:
                rows.append((sku, f"{sku}  -  {name}" if name else sku))
    return rows


def money(value: Any) -> str:
    if value is None or value == "":
        return "-"
    number = float(value)
    if number.is_integer():
        return f"UGX {int(number):,}"
    return f"UGX {number:,.2f}"


def reasons(values: Any) -> str:
    if not values:
        return ""
    if isinstance(values, str):
        return values
    return ", ".join(str(item) for item in values)


def reorder_rows(reorder: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not reorder:
        return []
    rows = []
    for item in reorder.get("items") or []:
        rows.append(
            {
                "SKU": item.get("sku"),
                "Item": item.get("item_name"),
                "Stock": item.get("current_stock"),
                "Reorder point": item.get("reorder_point"),
                "Target": item.get("target_stock_level"),
                "Reorder qty": item.get("reorder_quantity"),
                "Unit": item.get("unit_of_measure"),
            }
        )
    return rows


def eligibility_rows(eligibility: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not eligibility:
        return []
    rows = []
    for item in eligibility.get("results") or []:
        rows.append(
            {
                "Supplier": item.get("registered_name") or item.get("requested"),
                "ID": item.get("supplier_id"),
                "Eligible": "yes" if item.get("eligible") else "no",
                "Status": item.get("avl_status") or "",
                "Reasons": reasons(item.get("exclusion_reasons")),
            }
        )
    return rows


def ranked_rows(comparison: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not comparison:
        return []
    rows = []
    for item in comparison.get("ranked") or []:
        rows.append(
            {
                "Rank": item.get("rank"),
                "Quotation": item.get("quotation_id"),
                "Supplier": item.get("supplier_name"),
                "Unit cost": money(item.get("normalised_unit_cost_ugx")),
                "VAT": money(item.get("vat_amount_ugx")),
                "Delivery": money(item.get("delivery_cost_ugx")),
                "Landed": money(item.get("landed_cost_ugx")),
            }
        )
    return rows


def excluded_rows(comparison: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not comparison:
        return []
    rows = []
    for item in comparison.get("excluded") or []:
        rows.append(
            {
                "Quotation": item.get("quotation_id"),
                "Supplier": item.get("supplier_name"),
                "Reasons": reasons(item.get("reasons")),
            }
        )
    return rows


def requirement_lines(comparison: dict[str, Any] | None) -> list[str]:
    if not comparison:
        return []
    req = comparison.get("quotation_requirement") or {}
    if not req:
        return []
    lines = [
        f"Band: {req.get('clause') or req.get('value_band')}",
        f"Required quotations: {req.get('required_count')}",
        f"Eligible remaining: {req.get('eligible_count')}",
    ]
    if req.get("exception_required"):
        lines.append("Exception required: yes (POL-001-C04). This does not block the draft.")
    if comparison.get("sole_eligible_option"):
        lines.append("Sole eligible option: yes.")
    return lines


def memory_lines(memory: dict[str, Any] | None) -> list[str]:
    if not memory:
        return []
    lines = []
    for record in memory.get("records") or []:
        ident = record.get("id") or ""
        summary = record.get("summary") or ""
        lines.append(f"{ident}: {summary}".strip(": "))
    return lines
