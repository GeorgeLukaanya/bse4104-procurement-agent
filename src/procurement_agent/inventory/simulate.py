"""Make the stock move, the same way every time.

A simulated stock system is only useful if it is reproducible. An evaluation
that cannot be repeated says nothing, and a demonstration that shows different
figures to two people in the same room is worse than no demonstration. So
nothing here uses a random number generator: every movement is derived from a
SHA-256 of the seed, the SKU and the date. The same three inputs give the same
day's trade on any machine, forever, and changing the seed gives a different
but equally repeatable business.

What it models, and what it deliberately does not.

Items sell at different rates. A bag of cement moves faster than a spirit
level, so each SKU gets a velocity from its own hash, and a faster mover is
also more erratic. Trade is heavier at the end of the week and there is none on
Sunday, which is what a Kampala hardware counter looks like.

Deliveries arrive late, and that lateness is the whole reason the agent has
anything to find. A business does reorder, so a simulation where nothing is
ever replaced drains every shelf to zero inside a quarter and tells you
nothing. What it does not do is reorder instantly: an item crosses its reorder
point, somebody notices a few days later, and the delivery lands a few days
after that. A snapshot taken on any given Monday therefore catches whatever
crossed during that window, which is exactly the work the weekly review exists
to do.

Pass `restock=False` to model a business that never reorders at all. Every
shelf ends up empty, which is useful for exercising the tail of the flow and
useless for anything else.

A physical count happens monthly and disagrees with the book by a little, which
is where `last_counted` comes from and why it is not simply the start date.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Iterable, Sequence

from .ledger import ADJUSTMENT, ISSUE, RECEIPT, Item, Movement, StockLedger, _as_date

# Sunday is closed. Saturday is the busiest day on the counter.
WEEKDAY_WEIGHT = (0.9, 0.9, 1.0, 1.1, 1.3, 1.6, 0.0)

COUNT_DAY = 28  # a physical count near the end of each month


def _digits(*parts: str) -> int:
    """A stable number from the inputs, standing in for a dice roll."""
    joined = "|".join(parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(joined).digest()[:8], "big")


def _unit(*parts: str) -> float:
    """The same, as a fraction between 0 and 1."""
    return _digits(*parts) / float(1 << 64)


def velocity(seed: str, sku: str, target_stock_level: int) -> float:
    """How many units a day this item moves, on average.

    Scaled to the target stock level, because a business holds more of what it
    sells more of: the target is the clearest statement it has made about how
    fast an item turns.

    The divisor is how many days of cover the target represents, and it is
    calibrated rather than guessed. At thirty days the shelves drain faster
    than any reasonable reorder can refill them and the whole catalogue ends
    up empty, which tells you nothing. At a hundred and twenty, with the
    spread below giving the fastest movers nearer sixty, a quarter of trading
    leaves six to twelve items of forty-eight below their reorder point and
    none at zero. That is the same shape as the registered dataset, which has
    eleven of forty-eight flagged, and it is a plausible hardware distributor.
    """
    spread = 0.4 + 1.6 * _unit(seed, "velocity", sku)
    return max(0.2, (target_stock_level / 120.0) * spread)


def demand(seed: str, sku: str, day: date, average: float) -> int:
    """What went out on one day. Lumpy, because real counters are."""
    weight = WEEKDAY_WEIGHT[day.weekday()]
    if weight == 0.0:
        return 0
    roll = _unit(seed, "demand", sku, day.isoformat())
    # Most days sit near the average; one day in eight is a big order that
    # takes several times the usual. That lumpiness is what drives an item
    # through its reorder point between two weekly reviews.
    if roll > 0.875:
        multiplier = 2.5 + 3.0 * _unit(seed, "bulk", sku, day.isoformat())
    else:
        multiplier = 0.3 + 1.4 * roll
    return int(round(average * weight * multiplier))


def reaction_days(seed: str, sku: str) -> int:
    """How long this business takes to notice an item needs ordering."""
    return 2 + _digits(seed, "notice", sku) % 6


def lead_days(seed: str, sku: str) -> int:
    """How long the supplier then takes to deliver it."""
    return 2 + _digits(seed, "lead", sku) % 7


def _count_drift(seed: str, item: Item, day: date) -> Movement | None:
    """What a physical count found, when one happened."""
    if day.day != COUNT_DAY:
        return None
    drift = _digits(seed, "count", item.sku, day.isoformat()) % 5
    if not drift:
        return None
    direction = -1 if _unit(seed, "shrink", item.sku, day.isoformat()) < 0.7 else 1
    return Movement(
        sku=item.sku, on=day.isoformat(), kind=ADJUSTMENT,
        quantity=direction * drift, reference="stock count",
    )


def _trade_one(
    item: Item,
    first: date,
    last: date,
    seed: str,
    count_drift: bool,
    restock: bool,
) -> list[Movement]:
    """One item's movements, with its level tracked so reordering can happen."""
    average = velocity(seed, item.sku, item.target_stock_level)
    notice = reaction_days(seed, item.sku)
    lead = lead_days(seed, item.sku)

    movements: list[Movement] = []
    level = item.opening_stock
    arriving: dict[date, int] = {}
    on_order = False

    day = first
    while day <= last:
        landing = arriving.pop(day, 0)
        if landing:
            movements.append(Movement(
                sku=item.sku, on=day.isoformat(), kind=RECEIPT,
                quantity=landing, reference="goods received",
            ))
            level += landing
            on_order = False

        # You cannot sell off a shelf what is not on it. Capping the day's
        # issue at what is there also keeps the running level here identical
        # to the one StockLedger derives by replaying: without it the
        # simulator clamps each day while the ledger sums first and clamps
        # once, and the two quietly disagree about any item that ran out.
        quantity = min(demand(seed, item.sku, day, average), level)
        if quantity > 0:
            movements.append(Movement(
                sku=item.sku, on=day.isoformat(), kind=ISSUE,
                quantity=quantity, reference="counter sales",
            ))
            level -= quantity

        drift = _count_drift(seed, item, day) if count_drift else None
        if drift is not None:
            movements.append(drift)
            level = max(0, level + drift.effect)

        # Somebody notices, eventually, and orders enough to fill back up.
        if restock and not on_order and level <= item.reorder_point:
            on_order = True
            arriving[day + timedelta(days=notice + lead)] = max(
                1, item.target_stock_level - level
            )

        day += timedelta(days=1)
    return movements


def trade(
    items: Iterable[Item],
    *,
    start: str | date,
    end: str | date,
    seed: str = "ahumuza",
    count_drift: bool = True,
    restock: bool = True,
) -> list[Movement]:
    """Every movement between two dates, derived and not drawn at random."""
    first, last = _as_date(start), _as_date(end)
    if last < first:
        raise ValueError("the end of the period is before its start")
    movements: list[Movement] = []
    for item in items:
        movements.extend(_trade_one(item, first, last, seed, count_drift, restock))
    return movements


def deliver(sku: str, quantity: int, on: str | date, reference: str = "") -> Movement:
    """A delivery landing. Nothing here creates one on its own."""
    return Movement(
        sku=sku, on=_as_date(on).isoformat(), kind=RECEIPT,
        quantity=int(quantity), reference=reference or "goods received",
    )


def build(
    snapshot_csv: str,
    *,
    opened_on: str,
    until: str,
    seed: str = "ahumuza",
    restock: bool = True,
) -> StockLedger:
    """A stock system seeded from the project's dataset and traded forward."""
    ledger = StockLedger.from_snapshot_csv(snapshot_csv, opened_on=opened_on)
    for movement in trade(
        ledger.items.values(), start=opened_on, end=until, seed=seed, restock=restock,
    ):
        ledger.record(movement)
    return ledger
