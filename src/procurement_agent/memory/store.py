"""Persistent procurement memory: prior outcomes and supplier performance notes.

Charter section 7 scopes exactly one persistent-memory use case: "prior
requisition outcomes and supplier performance notes as advisory context".
This module is that use case and nothing wider.

Two kinds of record, one JSON object per line:

``prior_outcome``
    Written by the agent when a run compiles a requisition in DRAFT: which
    supplier the comparison ranked first for which item, the landed cost, and
    whether a POL-001-C04 exception was needed. It records what happened, not
    a judgement.

``supplier_note``
    Written by a Procurement Officer: a short, dated observation about a
    supplier, such as late deliveries or a confirmed registration detail.

Rules the code enforces, not just states:

- Advisory only. Memory is shown to the officer beside the comparison. It is
  never passed to the planner, to a tool, to the ranking or to the drafted
  requisition, so it cannot change eligibility, a landed cost, a rank or a
  status (AI Boundary Matrix; Requirement 14.3).
- Only a Procurement Officer writes or deletes a note. The agent writes only
  ``prior_outcome`` records, and only on a completed run. The manager may read.
- Notes are untrusted text. A note is length-limited and refused if it asserts
  an approval, an award or a commitment (``guards.scan``), and is screened
  again when displayed.
- Every record has an expiry date. Expired records are not shown and are
  removed by ``purge_expired``. ``forget`` deletes one record outright.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

from .. import guards
from ..tools.contract import ROLE_AGENT, ROLE_OFFICER

DEFAULT_MEMORY_PATH = Path("var") / "memory" / "procurement-memory.jsonl"

KIND_NOTE = "supplier_note"
KIND_OUTCOME = "prior_outcome"
KINDS = (KIND_NOTE, KIND_OUTCOME)

NOTE_RETENTION_DAYS = 365
OUTCOME_RETENTION_DAYS = 365
MAX_NOTE_CHARS = 280

_SUPPLIER_ID = re.compile(r"^SUP-[0-9]{3}$")
_MEMORY_ID = re.compile(r"^MEM-[0-9a-f]{10}$")


class MemoryRefused(ValueError):
    """A write or delete the rules above do not allow."""


def _iso(day: date) -> str:
    return day.isoformat()


def _parse_day(value: str) -> date:
    return date.fromisoformat(value)


def _new_id(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"MEM-{digest[:10]}"


class MemoryStore:
    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_MEMORY_PATH

    # ---- reading ---------------------------------------------------------

    def _all(self) -> list[dict[str, Any]]:
        try:
            handle = open(self.path, encoding="utf-8")
        except (FileNotFoundError, NotADirectoryError):
            return []
        records = []
        with handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict) and record.get("kind") in KINDS:
                    records.append(record)
        return records

    def records(self, *, as_of: str | None = None, include_expired: bool = False) -> list[dict[str, Any]]:
        day = _parse_day(as_of) if as_of else date.today()
        found = []
        for record in self._all():
            expires = record.get("expires_on")
            if not include_expired and expires and _parse_day(expires) < day:
                continue
            found.append(record)
        return found

    def relevant(
        self,
        *,
        supplier_ids: Iterable[str],
        sku: str | None,
        as_of: str,
    ) -> list[dict[str, Any]]:
        """Unexpired records about these suppliers or this item, newest first.

        Records dated after ``as_of`` are not shown: a review on 25 September
        does not see a note written on 1 October.
        """
        wanted = set(supplier_ids)
        day = _parse_day(as_of)
        found = []
        for record in self.records(as_of=as_of):
            recorded = record.get("recorded_on")
            if recorded and _parse_day(recorded) > day:
                continue
            if record.get("supplier_id") in wanted or (sku and record.get("sku") == sku):
                found.append(record)
        found.sort(key=lambda r: (r.get("recorded_on") or "", r.get("id") or ""), reverse=True)
        return found

    # ---- writing ---------------------------------------------------------

    def _append(self, record: dict[str, Any]) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        return record

    def _rewrite(self, records: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        os.replace(tmp, self.path)

    def add_note(
        self,
        *,
        supplier_id: str,
        text: str,
        author: str,
        role: str,
        recorded_on: str,
        retention_days: int = NOTE_RETENTION_DAYS,
    ) -> dict[str, Any]:
        if role != ROLE_OFFICER:
            raise MemoryRefused(f"{role} may not write supplier notes; only PROCUREMENT_OFFICER may.")
        if not _SUPPLIER_ID.match(supplier_id or ""):
            raise MemoryRefused(f"{supplier_id!r} is not a supplier identifier (SUP-000).")
        text = (text or "").strip()
        if not text:
            raise MemoryRefused("A note must not be empty.")
        if len(text) > MAX_NOTE_CHARS:
            raise MemoryRefused(f"A note is limited to {MAX_NOTE_CHARS} characters.")
        findings = guards.scan({"text": text})
        if findings:
            raise MemoryRefused(
                "A note may not assert an approval, award or commitment "
                f"(Requirement 14.2): {findings[0].description}."
            )
        if not 1 <= retention_days <= NOTE_RETENTION_DAYS:
            raise MemoryRefused(f"Retention must be 1 to {NOTE_RETENTION_DAYS} days.")
        day = _parse_day(recorded_on)
        body = {
            "kind": KIND_NOTE,
            "supplier_id": supplier_id,
            "text": text,
            "author": author,
            "source": "officer",
            "recorded_on": _iso(day),
            "expires_on": _iso(day + timedelta(days=retention_days)),
        }
        return self._append({"id": _new_id(body), **body})

    def record_outcome(
        self,
        *,
        role: str,
        run_id: str,
        sku: str,
        review_date: str,
        requisition_id: str | None,
        supplier_id: str | None,
        supplier_name: str | None,
        quotation_id: str | None,
        landed_cost_ugx: float | None,
        exception_required: bool,
        excluded_suppliers: list[str],
    ) -> dict[str, Any]:
        if role not in (ROLE_OFFICER, ROLE_AGENT):
            raise MemoryRefused(f"{role} does not compile requisitions, so writes no outcome.")
        day = _parse_day(review_date)
        body = {
            "kind": KIND_OUTCOME,
            "sku": sku,
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "quotation_id": quotation_id,
            "landed_cost_ugx": landed_cost_ugx,
            "exception_required": exception_required,
            "excluded_suppliers": excluded_suppliers,
            "requisition_id": requisition_id,
            "requisition_status": "DRAFT",
            "run_id": run_id,
            "source": "agent-run",
            "recorded_on": _iso(day),
            "expires_on": _iso(day + timedelta(days=OUTCOME_RETENTION_DAYS)),
        }
        return self._append({"id": _new_id(body), **body})

    def forget(self, memory_id: str, *, role: str) -> bool:
        if role != ROLE_OFFICER:
            raise MemoryRefused(f"{role} may not delete memory; only PROCUREMENT_OFFICER may.")
        if not _MEMORY_ID.match(memory_id or ""):
            raise MemoryRefused(f"{memory_id!r} is not a memory identifier.")
        records = self._all()
        kept = [r for r in records if r.get("id") != memory_id]
        if len(kept) == len(records):
            return False
        self._rewrite(kept)
        return True

    def purge_expired(self, *, as_of: str) -> int:
        day = _parse_day(as_of)
        records = self._all()
        kept = [
            r for r in records
            if not (r.get("expires_on") and _parse_day(r["expires_on"]) < day)
        ]
        removed = len(records) - len(kept)
        if removed:
            self._rewrite(kept)
        return removed


def summarise(record: Mapping[str, Any]) -> str:
    """One line for the officer. Note text is re-screened before display."""
    if record.get("kind") == KIND_NOTE:
        text = str(record.get("text") or "")
        if guards.scan({"text": text}):
            text = "[note withheld: it asserts an approval, award or commitment]"
        return f'{record.get("supplier_id")} note by {record.get("author")} on {record.get("recorded_on")}: "{text}"'
    exception = "; exception required" if record.get("exception_required") else ""
    cost = record.get("landed_cost_ugx")
    cost_text = f"UGX {cost:,.0f}" if isinstance(cost, (int, float)) else "no landed cost"
    return (
        f"{record.get('sku')} on {record.get('recorded_on')}: ranked first "
        f"{record.get('supplier_name') or record.get('supplier_id')} "
        f"({record.get('quotation_id')}), {cost_text}{exception}; "
        f"{record.get('requisition_id')} left in DRAFT"
    )


def advisory_block(records: list[Mapping[str, Any]], *, store_path: str) -> dict[str, Any]:
    """What the officer sees. Says plainly that it changed nothing."""
    return {
        "advisory": True,
        "influenced_decisions": False,
        "statement": (
            "Advisory context from memory. Eligibility, landed cost, ranking and "
            "the requisition were computed without it."
        ),
        "store": store_path,
        "records": [
            {
                "id": r.get("id"),
                "kind": r.get("kind"),
                "supplier_id": r.get("supplier_id"),
                "recorded_on": r.get("recorded_on"),
                "expires_on": r.get("expires_on"),
                "summary": summarise(r),
            }
            for r in records
        ],
    }

