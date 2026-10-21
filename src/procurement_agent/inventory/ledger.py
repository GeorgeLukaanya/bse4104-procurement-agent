"""A stock position that moves, kept as a ledger rather than as a number.

The dataset the project ships is a snapshot: forty-eight rows with a
`current_stock` column, registered and checksummed. It is exactly right for
evaluating the agent, because every run sees the same figures. It is also not
how a business holds stock. Nothing in it ever moves, so a review on the 25th
and a review in December agree, and the agent is reading a fixture rather than
asking a system.

This module is the other half: the stock position as a business actually keeps
it, and the thing the agent can call.

The design decision that matters is that a level is not stored. What is stored
is an opening balance per item and an append-only ledger of movements: goods
issued when something is sold or used, goods received when a delivery lands,
and adjustments when a physical count disagrees with the book. The level at a
date is derived by replaying the ledger up to that date.

That is worth the extra work for three reasons. It makes "as at" a real
question, which is what a weekly review asks and what a snapshot cannot answer.
It makes the number explainable: an officer who doubts a figure can be shown
the movements behind it rather than asked to trust a cell. And it makes the
history immutable in the same way the decisions table is, so a correction is a
new row rather than an edit of the past.

Nothing here decides anything. It reports stock. Reorder points are read from
the item record and compared by `check_reorder_need`, which is where that
arithmetic belongs and where it is already tested.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

DEFAULT_LEDGER_PATH = Path("var") / "stock-ledger.jsonl"

# What a movement can be. An issue takes stock out, a receipt puts it in, and
# an adjustment sets the difference a count found. Nothing else moves stock.
ISSUE = "issue"
RECEIPT = "receipt"
ADJUSTMENT = "adjustment"
MOVEMENT_KINDS = (ISSUE, RECEIPT, ADJUSTMENT)

# The columns check_reorder_need expects, in the order the register's CSV has
# them. A snapshot from here has to be indistinguishable from one read off disk.
SNAPSHOT_FIELDS = (
    "sku",
    "item_name",
    "category",
    "unit_of_measure",
    "current_stock",
    "reorder_point",
    "target_stock_level",
    "unit_cost_ugx",
    "location",
    "last_counted",
)

ISO = "%Y-%m-%d"


class LedgerError(ValueError):
    """The movement or the item was refused, and the caller is told why."""


def _as_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), ISO).date()
    except ValueError as exc:
        raise LedgerError(f"{value!r} is not a date in YYYY-MM-DD form.") from exc


@dataclass(frozen=True)
class Item:
    """What the business stocks. These values change rarely and by hand."""

    sku: str
    item_name: str
    category: str
    unit_of_measure: str
    reorder_point: int
    target_stock_level: int
    unit_cost_ugx: int
    location: str
    opening_stock: int
    opened_on: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sku": self.sku,
            "item_name": self.item_name,
            "category": self.category,
            "unit_of_measure": self.unit_of_measure,
            "reorder_point": self.reorder_point,
            "target_stock_level": self.target_stock_level,
            "unit_cost_ugx": self.unit_cost_ugx,
            "location": self.location,
            "opening_stock": self.opening_stock,
            "opened_on": self.opened_on,
        }


@dataclass(frozen=True)
class Movement:
    """One thing that happened to the stock of one item on one day."""

    sku: str
    on: str
    kind: str
    quantity: int
    reference: str = ""

    def __post_init__(self) -> None:
        if self.kind not in MOVEMENT_KINDS:
            raise LedgerError(f"{self.kind!r} is not a movement kind.")
        _as_date(self.on)
        if self.kind in (ISSUE, RECEIPT) and self.quantity <= 0:
            raise LedgerError("An issue or a receipt moves a positive quantity.")
        if self.kind == ADJUSTMENT and self.quantity == 0:
            raise LedgerError("An adjustment of nothing is not a movement.")

    @property
    def effect(self) -> int:
        """What this does to the level: out, in, or the signed correction."""
        if self.kind == ISSUE:
            return -self.quantity
        return self.quantity

    def to_dict(self) -> dict[str, Any]:
        return {
            "sku": self.sku, "on": self.on, "kind": self.kind,
            "quantity": self.quantity, "reference": self.reference,
        }


@dataclass
class StockLedger:
    """Items, their opening balances, and everything that moved since."""

    items: dict[str, Item] = field(default_factory=dict)
    movements: list[Movement] = field(default_factory=list)

    # -- building ---------------------------------------------------------

    def add_item(self, item: Item) -> None:
        if item.sku in self.items:
            raise LedgerError(f"{item.sku} is already stocked.")
        self.items[item.sku] = item

    def record(self, movement: Movement) -> Movement:
        if movement.sku not in self.items:
            raise LedgerError(f"{movement.sku} is not stocked here.")
        if _as_date(movement.on) < _as_date(self.items[movement.sku].opened_on):
            raise LedgerError(
                f"{movement.sku}: {movement.on} is before the opening balance was taken."
            )
        self.movements.append(movement)
        return movement

    # -- reading ----------------------------------------------------------

    def level(self, sku: str, as_of: str | date) -> int:
        """The book level for one item, by replaying its movements."""
        if sku not in self.items:
            raise LedgerError(f"{sku} is not stocked here.")
        when = _as_date(as_of)
        total = self.items[sku].opening_stock
        for movement in self.movements:
            if movement.sku == sku and _as_date(movement.on) <= when:
                total += movement.effect
        # A business can oversell on paper; the book catches up at the next
        # count. Reporting a negative would be a lie about what is on the floor.
        return max(0, total)

    def last_counted(self, sku: str, as_of: str | date) -> str:
        """When the book last agreed with a physical count."""
        when = _as_date(as_of)
        counted = self.items[sku].opened_on
        for movement in self.movements:
            if (movement.sku == sku and movement.kind == ADJUSTMENT
                    and _as_date(movement.on) <= when):
                counted = max(counted, movement.on)
        return counted

    def history(self, sku: str, as_of: str | date | None = None) -> list[dict[str, Any]]:
        when = _as_date(as_of) if as_of else None
        return [
            movement.to_dict() for movement in self.movements
            if movement.sku == sku and (when is None or _as_date(movement.on) <= when)
        ]

    def snapshot(self, as_of: str | date) -> list[dict[str, Any]]:
        """The stock position as at a date, in the shape the tools read."""
        when = _as_date(as_of)
        rows = []
        for sku in sorted(self.items):
            item = self.items[sku]
            rows.append({
                "sku": item.sku,
                "item_name": item.item_name,
                "category": item.category,
                "unit_of_measure": item.unit_of_measure,
                "current_stock": self.level(sku, when),
                "reorder_point": item.reorder_point,
                "target_stock_level": item.target_stock_level,
                "unit_cost_ugx": item.unit_cost_ugx,
                "location": item.location,
                "last_counted": self.last_counted(sku, when),
            })
        return rows

    # -- persistence ------------------------------------------------------

    def save(self, path: str | os.PathLike[str] | None = None) -> Path:
        """One JSON object per line: the items first, then the movements.

        Append-only in spirit and in use. Rewriting the file is how an item's
        standing details change, which is rare and deliberate; a movement is
        never edited, only offset by another.
        """
        target = Path(path) if path is not None else DEFAULT_LEDGER_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps({"record": "item", **item.to_dict()}, sort_keys=True)
                 for item in (self.items[sku] for sku in sorted(self.items))]
        lines += [json.dumps({"record": "movement", **movement.to_dict()}, sort_keys=True)
                  for movement in self.movements]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> "StockLedger":
        target = Path(path) if path is not None else DEFAULT_LEDGER_PATH
        ledger = cls()
        try:
            text = target.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise LedgerError(f"{target} has no stock ledger in it.") from exc
        for number, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LedgerError(f"{target} line {number} is not JSON.") from exc
            kind = row.pop("record", None)
            if kind == "item":
                ledger.add_item(Item(**row))
            elif kind == "movement":
                ledger.movements.append(Movement(**row))
            else:
                raise LedgerError(f"{target} line {number}: unknown record {kind!r}.")
        return ledger

    @classmethod
    def from_snapshot_csv(
        cls,
        path: str | os.PathLike[str],
        *,
        opened_on: str,
    ) -> "StockLedger":
        """Start a ledger from the project's registered snapshot.

        The team's dataset becomes the opening balance, so a simulated system
        begins where the evaluation dataset does rather than from figures
        nobody has reviewed.
        """
        text = Path(path).read_text(encoding="utf-8").replace("\r\n", "\n")
        ledger = cls()
        for raw in csv.DictReader(text.splitlines()):
            ledger.add_item(Item(
                sku=(raw.get("sku") or "").strip(),
                item_name=(raw.get("item_name") or "").strip(),
                category=(raw.get("category") or "").strip(),
                unit_of_measure=(raw.get("unit_of_measure") or "").strip(),
                reorder_point=int(raw["reorder_point"]),
                target_stock_level=int(raw["target_stock_level"]),
                unit_cost_ugx=int(raw["unit_cost_ugx"]),
                location=(raw.get("location") or "").strip(),
                opening_stock=int(raw["current_stock"]),
                opened_on=opened_on,
            ))
        if not ledger.items:
            raise LedgerError(f"{path} has no items in it.")
        return ledger


# How each field is written for hashing. Without this the two sides disagree
# over nothing: the service holds a unit cost as 32000 and the loader parses
# the same figure to 32000.0, JSON writes them differently, and a sound
# position looks corrupted.
_WHOLE = ("current_stock", "reorder_point", "target_stock_level")


def canonical(rows: Sequence[Mapping[str, Any]]) -> str:
    """One text for a snapshot, so two machines agree on its checksum."""
    normalised = []
    for row in rows:
        out: dict[str, Any] = {}
        for name in SNAPSHOT_FIELDS:
            value = row[name]
            if name in _WHOLE:
                out[name] = int(value)
            elif name == "unit_cost_ugx":
                out[name] = float(value)
            else:
                out[name] = str(value)
        normalised.append(out)
    return json.dumps(normalised, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def checksum(rows: Sequence[Mapping[str, Any]]) -> str:
    return hashlib.sha256(canonical(rows).encode("utf-8")).hexdigest()


def fingerprint(rows: Iterable[Mapping[str, Any]]) -> str:
    """The first sixteen characters, matching what the tool envelope carries."""
    return checksum(list(rows))[:16]
