"""Format workflow results for the operator view. No Streamlit import."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

from ..agent.checkpoint import run_id_for
from ..tools.data import DEFAULT_INVENTORY, DEFAULT_QUOTATIONS, DEFAULT_REGISTER, load_inventory, load_quotations


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


# Plain-language versions of the tool reason codes. The code stays beside the
# sentence so the officer can still trace it to the policy.
PLAIN_REASONS = {
    "NAME_DISCREPANCY": "The supplier name on the quotation does not match the approved register exactly.",
    "BLACKLISTED": "The supplier is blacklisted on the approved vendor list.",
    "SUSPENDED": "The supplier is suspended on the approved vendor list.",
    "AVL_ABSENT": "The supplier is not on the approved vendor list.",
    "OUT_OF_CATEGORY": "The supplier is not approved for this category of item.",
    "EXPIRED": "The quotation had expired by the review date.",
    "INCOMPARABLE_QUOTATION": "The quotation is missing a figure needed to compare it.",
}

STATUS_NOT_STARTED = "Not started"
STATUS_CONFIRM = "Needs your confirmation"
STATUS_RATE = "Needs an exchange rate"
STATUS_NO_OFFER = "No eligible offer"
STATUS_DRAFT = "Draft created"
STATUS_NO_REORDER = "No reorder needed"
STATUS_REFUSED = "Not allowed for this role"
STATUS_STOPPED = "Stopped"

STEP_LABELS = (
    "Stock checked",
    "Suppliers checked",
    "Quotes compared",
    "Your confirmation",
    "Draft requisition",
)


def _data_paths() -> dict[str, Path]:
    root = repo_root()
    return {
        "inventory": root / DEFAULT_INVENTORY,
        "quotations": root / DEFAULT_QUOTATIONS,
        "register": root / DEFAULT_REGISTER,
    }


def flagged_items() -> list[dict[str, Any]]:
    """Items at or below their reorder point, in inventory order.

    Read from the registered snapshot for display only. The agent still
    re-checks stock through check_reorder_need when a review runs.
    """
    paths = _data_paths()
    rows, _ = load_inventory(paths["inventory"], paths["register"])
    items = []
    for row in rows:
        if row["current_stock"] <= row["reorder_point"]:
            items.append(
                {
                    "sku": row["sku"],
                    "item_name": row["item_name"],
                    "category": row["category"],
                    "unit": row["unit_of_measure"],
                    "current_stock": row["current_stock"],
                    "reorder_point": row["reorder_point"],
                    "to_order": max(row["target_stock_level"] - row["current_stock"], 0),
                }
            )
    return items


def quotations_for(sku: str, review_date: str) -> list[dict[str, Any]]:
    paths = _data_paths()
    quotations, _ = load_quotations(paths["quotations"], paths["register"])
    held = []
    for quote in quotations:
        if quote.get("sku") != sku:
            continue
        validity = quote.get("validity_date") or ""
        if validity and validity < review_date:
            state, tone = f"Expired on {_short_date(validity)}: not compared", "bad"
        elif (quote.get("currency") or "UGX") != "UGX":
            state, tone = f"Waiting for a rate ({quote.get('currency')})", "wait"
        else:
            state, tone = "Ready to compare", "ok"
        held.append(
            {
                "quotation_id": quote.get("quotation_id"),
                "supplier_name": quote.get("supplier_name"),
                "state": state,
                "tone": tone,
            }
        )
    return held


def _short_date(value: str) -> str:
    try:
        return date.fromisoformat(value).strftime("%-d %b")
    except ValueError:
        return value


def saved_status(checkpoint_dir: Path, review_date: str, sku: str, officer: str) -> str:
    """Queue status for one item, read from its checkpoint if it has one."""
    path = Path(checkpoint_dir) / f"{run_id_for(review_date, sku, officer)}.json"
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return STATUS_NOT_STARTED
    return status_for(saved.get("stop_reason"), saved.get("stop_detail"))


def status_for(stop_reason: str | None, stop_detail: str | None) -> str:
    detail = stop_detail or ""
    if stop_reason == "completed":
        return STATUS_DRAFT
    if stop_reason == "no_reorder_required":
        return STATUS_NO_REORDER
    if stop_reason in ("unauthorized", "refused"):
        return STATUS_REFUSED
    if stop_reason == "awaiting_human":
        if detail.startswith("EXCHANGE_RATE_REQUIRED"):
            return STATUS_RATE
        if detail.startswith("MISSING_COMPONENT"):
            return STATUS_NO_OFFER
        return STATUS_CONFIRM
    if stop_reason:
        return STATUS_STOPPED
    return STATUS_NOT_STARTED


def step_progress(
    reorder: dict[str, Any] | None,
    eligibility: dict[str, Any] | None,
    comparison: dict[str, Any] | None,
    confirmations: dict[str, Any] | None,
    draft: dict[str, Any] | None,
) -> list[bool]:
    """Which of the five operator steps are done, in STEP_LABELS order."""
    confirmed = bool((confirmations or {}).get("comparison")) or bool(draft)
    return [bool(reorder), bool(eligibility), bool(comparison), confirmed, bool(draft)]


def plain_exclusions(
    comparison: dict[str, Any] | None,
    eligibility: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Excluded quotations with a sentence per reason instead of a code."""
    if not comparison:
        return []
    similar = {
        item.get("supplier_id"): item.get("similar_registered_names") or []
        for item in (eligibility or {}).get("results") or []
    }
    rows = []
    for item in comparison.get("excluded") or []:
        codes = item.get("reasons") or []
        if isinstance(codes, str):
            codes = [codes]
        sentences = []
        for code in codes:
            sentence = PLAIN_REASONS.get(code, code)
            names = similar.get(item.get("supplier_id")) or []
            if code == "NAME_DISCREPANCY" and names:
                sentence += f" It is close to {', '.join(names)}."
            sentences.append(sentence)
        rows.append(
            {
                "quotation_id": item.get("quotation_id"),
                "supplier_name": item.get("supplier_name"),
                "codes": list(codes),
                "why": " ".join(sentences),
            }
        )
    return rows
