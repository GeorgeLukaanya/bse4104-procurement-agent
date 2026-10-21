"""The simulated stock system. Offline, no key, and the same figures every run."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from procurement_agent.inventory.ledger import (
    ADJUSTMENT,
    ISSUE,
    RECEIPT,
    Item,
    LedgerError,
    Movement,
    StockLedger,
    checksum,
)
from procurement_agent.inventory.service import create_server
from procurement_agent.inventory.simulate import build, deliver, trade, velocity
from procurement_agent.tools.data import DataIntegrityError, DataUnavailable, load_inventory

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "knowledge" / "data" / "inventory.csv"
OPENED = "2026-07-01"
REVIEW = "2026-09-25"
SKU = "AH-CM-001"


@pytest.fixture
def ledger():
    one = StockLedger()
    one.add_item(Item(
        sku=SKU, item_name="Portland cement 42.5N 50 kg bag",
        category="cement and masonry", unit_of_measure="bag",
        reorder_point=150, target_stock_level=270, unit_cost_ugx=32000,
        location="Nakawa Main Store", opening_stock=200, opened_on=OPENED,
    ))
    return one


# ------------------------------------------------------------- the ledger


def test_a_level_is_derived_from_the_movements(ledger):
    ledger.record(Movement(SKU, "2026-07-10", ISSUE, 40))
    ledger.record(Movement(SKU, "2026-07-12", RECEIPT, 100))
    ledger.record(Movement(SKU, "2026-07-20", ISSUE, 30))
    assert ledger.level(SKU, "2026-07-09") == 200
    assert ledger.level(SKU, "2026-07-10") == 160
    assert ledger.level(SKU, "2026-07-12") == 260
    assert ledger.level(SKU, "2026-07-31") == 230


def test_the_same_ledger_answers_differently_on_different_dates(ledger):
    """The whole point: a snapshot cannot answer an as-at question."""
    ledger.record(Movement(SKU, "2026-08-01", ISSUE, 120))
    assert ledger.snapshot("2026-07-31")[0]["current_stock"] == 200
    assert ledger.snapshot("2026-08-01")[0]["current_stock"] == 80


def test_a_level_is_never_reported_negative(ledger):
    """A business can oversell on paper. The floor cannot hold minus forty."""
    ledger.record(Movement(SKU, "2026-07-10", ISSUE, 240))
    assert ledger.level(SKU, "2026-07-10") == 0


def test_an_adjustment_moves_the_level_and_the_count_date(ledger):
    ledger.record(Movement(SKU, "2026-07-28", ADJUSTMENT, -3, "stock count"))
    assert ledger.level(SKU, "2026-07-28") == 197
    assert ledger.last_counted(SKU, "2026-07-28") == "2026-07-28"
    assert ledger.last_counted(SKU, "2026-07-27") == OPENED


def test_a_movement_for_something_not_stocked_is_refused(ledger):
    with pytest.raises(LedgerError) as exc:
        ledger.record(Movement("AH-ZZ-999", "2026-07-10", ISSUE, 1))
    assert "not stocked" in str(exc.value)


def test_a_movement_before_the_opening_balance_is_refused(ledger):
    """It would silently rewrite a figure somebody counted."""
    with pytest.raises(LedgerError):
        ledger.record(Movement(SKU, "2026-06-30", ISSUE, 5))


@pytest.mark.parametrize("kind,quantity", [(ISSUE, 0), (RECEIPT, -5), (ADJUSTMENT, 0)])
def test_a_movement_of_nothing_is_refused(kind, quantity):
    with pytest.raises(LedgerError):
        Movement(SKU, "2026-07-10", kind, quantity)


def test_a_ledger_survives_being_written_and_read(ledger, tmp_path):
    ledger.record(Movement(SKU, "2026-07-10", ISSUE, 40))
    ledger.save(tmp_path / "ledger.jsonl")
    again = StockLedger.load(tmp_path / "ledger.jsonl")
    assert again.snapshot(REVIEW) == ledger.snapshot(REVIEW)


def test_the_snapshot_matches_the_shape_the_tools_read(ledger):
    [row] = ledger.snapshot(REVIEW)
    assert set(row) == {
        "sku", "item_name", "category", "unit_of_measure", "current_stock",
        "reorder_point", "target_stock_level", "unit_cost_ugx", "location", "last_counted",
    }


# ---------------------------------------------------------- the simulator


def test_the_same_seed_gives_the_same_business_every_time():
    """An evaluation that cannot be repeated says nothing."""
    first = build(str(SNAPSHOT), opened_on=OPENED, until=REVIEW, seed="ahumuza")
    second = build(str(SNAPSHOT), opened_on=OPENED, until=REVIEW, seed="ahumuza")
    assert first.snapshot(REVIEW) == second.snapshot(REVIEW)
    assert checksum(first.snapshot(REVIEW)) == checksum(second.snapshot(REVIEW))


def test_a_different_seed_gives_a_different_business():
    one = build(str(SNAPSHOT), opened_on=OPENED, until=REVIEW, seed="ahumuza")
    other = build(str(SNAPSHOT), opened_on=OPENED, until=REVIEW, seed="kigo")
    assert one.snapshot(REVIEW) != other.snapshot(REVIEW)


def test_nothing_sells_on_a_sunday(ledger):
    movements = trade(ledger.items.values(), start="2026-07-05", end="2026-07-05")
    assert movements == [], "2026-07-05 is a Sunday"


def test_a_delivery_only_lands_after_the_item_ran_low():
    """The business reorders, but never instantly. That gap is the agent's job.

    Checked at the day the order was placed, not the day it arrived: a monthly
    count can lift the level back above the reorder point in between, and the
    delivery still turns up because it was already ordered.
    """
    from datetime import date, timedelta

    from procurement_agent.inventory.simulate import lead_days, reaction_days

    ledger = build(str(SNAPSHOT), opened_on=OPENED, until=REVIEW)
    receipts = [m for m in ledger.movements if m.kind == RECEIPT]
    assert receipts, "a business that never restocks empties every shelf in a quarter"

    for receipt in receipts:
        item = ledger.items[receipt.sku]
        wait = reaction_days("ahumuza", receipt.sku) + lead_days("ahumuza", receipt.sku)
        ordered_on = date.fromisoformat(receipt.on) - timedelta(days=wait)
        assert ledger.level(receipt.sku, ordered_on) <= item.reorder_point, (
            f"{receipt.sku}: a delivery landed on {receipt.on} but the level on "
            f"{ordered_on}, when it would have been ordered, was above the reorder point"
        )
        assert ordered_on >= date.fromisoformat(OPENED)


def test_a_business_that_never_reorders_empties_its_shelves():
    """The other extreme, kept available for exercising the tail of the flow."""
    ledger = build(str(SNAPSHOT), opened_on=OPENED, until=REVIEW, restock=False)
    assert all(movement.kind != RECEIPT for movement in ledger.movements)
    early = sum(row["current_stock"] for row in ledger.snapshot("2026-07-15"))
    late = sum(row["current_stock"] for row in ledger.snapshot(REVIEW))
    assert late < early


def test_a_delivery_puts_it_back(ledger):
    ledger.record(Movement(SKU, "2026-07-10", ISSUE, 180))
    assert ledger.level(SKU, "2026-07-10") == 20
    ledger.record(deliver(SKU, 250, "2026-07-14", "REQ-2026-0043"))
    assert ledger.level(SKU, "2026-07-14") == 270


def test_a_faster_moving_item_has_a_higher_velocity():
    slow = velocity("ahumuza", "AH-HT-012", 20)
    fast = velocity("ahumuza", "AH-HT-012", 400)
    assert fast > slow


def test_trading_forward_takes_items_through_their_reorder_point():
    """If nothing ever crossed, there would be nothing for the agent to find."""
    ledger = build(str(SNAPSHOT), opened_on=OPENED, until=REVIEW)
    rows = ledger.snapshot(REVIEW)
    low = [row for row in rows if row["current_stock"] <= row["reorder_point"]]
    assert low, "a simulated quarter should leave something needing an order"
    assert len(low) < len(rows), "and should not leave everything needing one"


# ------------------------------------------------------------ the service


@pytest.fixture
def stock_service(tmp_path):
    ledger = build(str(SNAPSHOT), opened_on=OPENED, until=REVIEW)
    server = create_server(
        ledger, ledger_path=tmp_path / "ledger.jsonl",
        default_as_of=REVIEW, host="127.0.0.1", port=0,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", ledger
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def get(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def post(url, payload):
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def test_the_service_reports_a_position_with_its_checksum(stock_service):
    base, ledger = stock_service
    payload = get(f"{base}/api/stock?as_of={REVIEW}")
    assert payload["as_of"] == REVIEW
    assert payload["checksum"] == checksum(ledger.snapshot(REVIEW))
    assert len(payload["items"]) == len(ledger.items)


def test_the_service_shows_the_movements_behind_a_figure(stock_service):
    base, _ = stock_service
    payload = get(f"{base}/api/stock/{SKU}?as_of={REVIEW}")
    assert payload["item"]["sku"] == SKU
    assert payload["movements"], "an officer who doubts the number can be shown why"
    assert all(movement["on"] <= REVIEW for movement in payload["movements"])


def test_asking_about_an_unstocked_item_is_a_404(stock_service):
    base, _ = stock_service
    with pytest.raises(urllib.error.HTTPError) as exc:
        get(f"{base}/api/stock/AH-ZZ-999")
    assert exc.value.code == 404


def test_a_sale_recorded_now_changes_the_position(stock_service):
    """This is what makes a demonstration possible rather than another fixture."""
    base, _ = stock_service
    before = get(f"{base}/api/stock/{SKU}?as_of={REVIEW}")["item"]["current_stock"]
    recorded = post(f"{base}/api/movements", {
        "sku": SKU, "on": REVIEW, "kind": ISSUE, "quantity": 40, "reference": "counter sales",
    })
    assert recorded["level"] == before - 40
    after = get(f"{base}/api/stock/{SKU}?as_of={REVIEW}")["item"]["current_stock"]
    assert after == before - 40


def test_a_nonsense_movement_is_refused(stock_service):
    base, _ = stock_service
    for payload in [
        {"sku": SKU, "kind": "stolen", "quantity": 5},
        {"sku": "AH-ZZ-999", "kind": ISSUE, "quantity": 5},
        {"sku": SKU, "kind": ISSUE, "quantity": 0},
    ]:
        with pytest.raises(urllib.error.HTTPError) as exc:
            post(f"{base}/api/movements", payload)
        assert exc.value.code == 400


# ------------------------------------------- the agent reading the service


def test_the_loader_reads_a_position_off_the_service(stock_service):
    """The same rows and the same kind of fingerprint as a file would give."""
    base, ledger = stock_service
    rows, fingerprint = load_inventory(f"{base}/api/stock", as_of=REVIEW)
    assert rows == [
        {**row, "current_stock": row["current_stock"]} for row in ledger.snapshot(REVIEW)
    ]
    assert len(fingerprint) == 16
    assert fingerprint == checksum(ledger.snapshot(REVIEW))[:16]


def test_the_loader_asks_about_the_date_it_was_given(stock_service):
    """Two dates, two positions. A snapshot file would answer the same twice."""
    base, ledger = stock_service
    early, early_print = load_inventory(f"{base}/api/stock", as_of="2026-07-15")
    late, late_print = load_inventory(f"{base}/api/stock", as_of=REVIEW)
    assert early_print != late_print
    moved = [
        row["sku"] for row, later in zip(early, late)
        if row["current_stock"] != later["current_stock"]
    ]
    assert moved, "ten weeks of trading should have moved something"
    assert each_matches(early, ledger.snapshot("2026-07-15"))
    assert each_matches(late, ledger.snapshot(REVIEW))


def each_matches(loaded, expected):
    return [row["current_stock"] for row in loaded] == [
        row["current_stock"] for row in expected
    ]


def test_a_stock_system_that_cannot_be_reached_is_unavailable_not_guessed():
    with pytest.raises(DataUnavailable):
        load_inventory("http://127.0.0.1:9/api/stock", as_of=REVIEW)


def test_a_position_that_does_not_match_its_checksum_is_refused(tmp_path):
    """Catches a mangled response. It cannot catch a service that lies."""
    import http.server

    rows = build(str(SNAPSHOT), opened_on=OPENED, until=REVIEW).snapshot(REVIEW)
    rows[0]["current_stock"] += 1  # the payload no longer matches what it claims
    body = json.dumps({"as_of": REVIEW, "items": rows, "checksum": "0" * 64}).encode("utf-8")

    class Liar(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # noqa: A003
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Liar)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(DataIntegrityError) as exc:
            load_inventory(f"http://127.0.0.1:{server.server_address[1]}/api/stock", as_of=REVIEW)
        assert "checksum" in str(exc.value)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_the_registered_file_still_works_untouched():
    """Adding a second source must not change what the first one does."""
    rows, fingerprint = load_inventory()
    assert len(rows) == 48
    assert len(fingerprint) == 16
