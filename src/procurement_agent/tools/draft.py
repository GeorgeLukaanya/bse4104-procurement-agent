"""create_requisition_draft — the catalogue's one side effect.

Writes a DRAFT record to a local store and nothing else. Contacts nobody,
orders nothing, commits no funds. Requirement 14.3: no status other than
DRAFT is producible.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contract import (
    CODE_DATA_SOURCE_UNAVAILABLE,
    CODE_INVALID_PARAMETER,
    CODE_MISSING_COMPONENT,
    STATUS_INVALID_INPUT,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    error,
    isoformat_z,
)

DEFAULT_STORE = Path("var") / "requisitions.jsonl"
CLAUSE_HEADING = re.compile(r"^## (?P<clause_id>[A-Z]+-\d+-C\d+) ")
DEFAULT_CORPUS = Path("knowledge") / "corpus"
INDEXED_FOLDERS = ("policies", "procedures", "product-specifications")


def create_requisition_draft(
    payload: dict[str, Any],
    *,
    store_path: str | Path | None = None,
    corpus_dir: str | Path | None = None,
    now: datetime | None = None,
) -> tuple[str, dict[str, Any] | None, list[dict[str, Any]], str | None]:
    clause_errors = _unknown_clauses(payload.get("policy_clauses") or [], corpus_dir)
    if clause_errors:
        return STATUS_INVALID_INPUT, None, clause_errors, None

    missing_components = _missing_components(payload)
    if missing_components:
        return STATUS_INVALID_INPUT, None, missing_components, None

    path = Path(store_path) if store_path is not None else DEFAULT_STORE
    created_at = isoformat_z(now if now is not None else datetime.now(timezone.utc))
    year = payload["review_date"][:4]
    try:
        requisition_id = _next_id(path, year)
    except OSError:
        return (
            STATUS_UNAVAILABLE,
            None,
            [
                error(
                    CODE_DATA_SOURCE_UNAVAILABLE,
                    f"requisition store {path} could not be read; no identifier was issued.",
                )
            ],
            None,
        )

    unresolved: list[str] = []
    items_out: list[dict[str, Any]] = []
    for item in payload["items"]:
        unresolved.extend(item.get("unresolved_issues") or [])
        items_out.append(
            {
                "sku": item["sku"],
                "reorder_quantity": item["reorder_quantity"],
                "comparison_reference": item["comparison_reference"],
                "recommended_quotation_id": item.get("recommended_quotation_id"),
            }
        )

    record = {
        "requisition_id": requisition_id,
        "status": "DRAFT",
        "created_at": created_at,
        "created_by": payload["officer_username"],
        "review_date": payload["review_date"],
        "items": items_out,
        "policy_clauses": list(payload.get("policy_clauses") or []),
        "justification": payload["justification"],
        "unresolved_issues": unresolved,
        "human_confirmation_required": True,
        "routed_to": None,
        "approved_by": None,
        "decision": None,
    }

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError:
        return (
            STATUS_UNAVAILABLE,
            None,
            [
                error(
                    CODE_DATA_SOURCE_UNAVAILABLE,
                    f"requisition store {path} is unwritable; no identifier was issued.",
                )
            ],
            None,
        )

    return STATUS_OK, record, [], None


def _next_id(path: Path, year: str) -> str:
    highest = 0
    if path.exists():
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ident = record.get("requisition_id") or ""
                prefix = f"REQ-{year}-"
                if ident.startswith(prefix):
                    try:
                        highest = max(highest, int(ident[len(prefix) :]))
                    except ValueError:
                        continue
    return f"REQ-{year}-{highest + 1:03d}"


def _unknown_clauses(
    clause_ids: list[str],
    corpus_dir: str | Path | None,
) -> list[dict[str, Any]]:
    if not clause_ids:
        return []
    known = _clause_ids(corpus_dir)
    errors = []
    for clause_id in clause_ids:
        if clause_id not in known:
            errors.append(
                error(
                    CODE_INVALID_PARAMETER,
                    f"{clause_id} is not a clause in the policy corpus at the registered version.",
                    field="policy_clauses",
                )
            )
    return errors


def _clause_ids(corpus_dir: str | Path | None) -> set[str]:
    root = Path(corpus_dir) if corpus_dir is not None else DEFAULT_CORPUS
    found: set[str] = set()
    for folder in INDEXED_FOLDERS:
        directory = root / folder
        if not directory.is_dir():
            continue
        for path in directory.glob("*.md"):
            text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
            for line in text.split("\n"):
                match = CLAUSE_HEADING.match(line)
                if match:
                    found.add(match.group("clause_id"))
    return found


def _missing_components(payload: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if not payload.get("items"):
        errors.append(
            error(
                CODE_MISSING_COMPONENT,
                "items are required at compilation. Nothing was written.",
                field="items",
            )
        )
    if not (payload.get("justification") or "").strip():
        errors.append(
            error(
                CODE_MISSING_COMPONENT,
                "justification is required at compilation. Nothing was written.",
                field="justification",
            )
        )
    return errors
