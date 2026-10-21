"""The decisions table. Append only, and the database is what enforces it."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from procurement_agent.decisions import (
    KIND_APPROVED,
    KIND_COMPARISON_APPROVED,
    KIND_RATE_GIVEN,
    KIND_RUN_STOPPED,
    DecisionRefused,
    DecisionStore,
)


def _store(tmp_path, **kwargs):
    moments = iter([
        datetime(2026, 9, 25, 9, 10, tzinfo=timezone.utc),
        datetime(2026, 9, 25, 9, 14, tzinfo=timezone.utc),
        datetime(2026, 9, 25, 9, 16, tzinfo=timezone.utc),
        datetime(2026, 9, 25, 11, 2, tzinfo=timezone.utc),
    ])
    counter = iter(f"DEC-{index:012d}" for index in range(1, 50))
    kwargs.setdefault("clock", lambda: next(moments))
    kwargs.setdefault("new_id", lambda: next(counter))
    return DecisionStore(tmp_path / "decisions.sqlite3", **kwargs)


def _approve(store, **overrides):
    payload = dict(
        run_id="AGT-2026-09-25-AH-CM-001-a.nakato",
        actor="a.nakato",
        role="PROCUREMENT_OFFICER",
        kind=KIND_COMPARISON_APPROVED,
        subject="AH-CM-001",
        detail={"supplier_name": "Kampala Cement Depot", "landed_cost_ugx": 10018600},
    )
    payload.update(overrides)
    return store.record(**payload)


def test_a_decision_is_written_and_read_back_whole(tmp_path):
    store = _store(tmp_path)
    written = _approve(store)
    [read] = store.for_subject("AH-CM-001")
    assert read["id"] == written["id"]
    assert read["actor"] == "a.nakato"
    assert read["kind"] == KIND_COMPARISON_APPROVED
    assert read["decided_at"] == "2026-09-25T09:10:00Z"
    # the figures as they stood survive the round trip
    assert read["detail"]["landed_cost_ugx"] == 10018600
    assert read["detail"]["supplier_name"] == "Kampala Cement Depot"


def test_an_update_is_refused_by_the_database(tmp_path):
    """Append only has to be enforced, not merely intended."""
    store = _store(tmp_path)
    _approve(store)
    with sqlite3.connect(store.path) as connection:
        with pytest.raises(sqlite3.IntegrityError) as exc:
            connection.execute("UPDATE decisions SET actor = 'someone.else'")
    assert "append only" in str(exc.value)


def test_a_delete_is_refused_by_the_database(tmp_path):
    store = _store(tmp_path)
    _approve(store)
    with sqlite3.connect(store.path) as connection:
        with pytest.raises(sqlite3.IntegrityError) as exc:
            connection.execute("DELETE FROM decisions")
    assert "append only" in str(exc.value)
    assert len(store.for_subject("AH-CM-001")) == 1


def test_a_replaced_decision_is_superseded_not_edited(tmp_path):
    """A rate given twice leaves two rows, and the first still says what it said."""
    store = _store(tmp_path)
    first = store.record(
        run_id="AGT-1", actor="a.nakato", role="PROCUREMENT_OFFICER",
        kind=KIND_RATE_GIVEN, subject="AH-CM-001",
        detail={"ugx_per_usd": 3700.0},
    )
    second = store.record(
        run_id="AGT-1", actor="a.nakato", role="PROCUREMENT_OFFICER",
        kind=KIND_RATE_GIVEN, subject="AH-CM-001",
        detail={"ugx_per_usd": 3780.0}, supersedes=first["id"],
    )
    rows = store.for_subject("AH-CM-001")
    assert [row["id"] for row in rows] == [first["id"], second["id"]]
    assert rows[0]["detail"]["ugx_per_usd"] == 3700.0
    assert store.superseded_ids() == {first["id"]}


def test_superseding_something_that_does_not_exist_is_refused(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(DecisionRefused) as exc:
        _approve(store, supersedes="DEC-nope")
    assert "nothing can supersede it" in str(exc.value)


def test_the_agent_may_not_record_an_approval(tmp_path):
    """POL-004-C03: approving is the one thing the agent must never do."""
    store = _store(tmp_path)
    with pytest.raises(DecisionRefused) as exc:
        store.record(
            run_id="AGT-1", actor="AGENT", role="AGENT",
            kind=KIND_APPROVED, subject="REQ-2026-0043",
        )
    assert "may not record" in str(exc.value)
    assert store.recent() == []


def test_the_officer_may_not_record_the_managers_approval(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(DecisionRefused):
        _approve(store, kind=KIND_APPROVED, subject="REQ-2026-0043")


def test_the_agent_may_record_that_it_stopped(tmp_path):
    store = _store(tmp_path)
    row = store.record(
        run_id="AGT-1", actor="AGENT", role="AGENT",
        kind=KIND_RUN_STOPPED, subject="AH-CM-001",
        detail={"stop_reason": "failed"},
    )
    assert row["role"] == "AGENT"


def test_a_reason_claiming_an_award_is_refused(tmp_path):
    """A typed reason is untrusted text on its way into a record people read."""
    store = _store(tmp_path)
    with pytest.raises(DecisionRefused) as exc:
        store.record(
            run_id="AGT-1", actor="k.ssali", role="PROCUREMENT_MANAGER",
            kind="sent_back", subject="REQ-2026-0043",
            detail={"reason": "Kampala Cement Depot is approved and the contract is awarded."},
        )
    assert "approval or a commitment" in str(exc.value)
    assert store.recent() == []


def test_an_ordinary_reason_is_kept(tmp_path):
    """The screen is only useful if a real reason gets through."""
    store = _store(tmp_path)
    row = store.record(
        run_id="AGT-1", actor="k.ssali", role="PROCUREMENT_MANAGER",
        kind="sent_back", subject="REQ-2026-0043",
        detail={"reason": "Get a third quotation before I sign this off."},
    )
    assert row["detail"]["reason"].startswith("Get a third")


def test_an_overlong_reason_is_refused(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(DecisionRefused) as exc:
        store.record(
            run_id="AGT-1", actor="k.ssali", role="PROCUREMENT_MANAGER",
            kind="sent_back", subject="REQ-2026-0043",
            detail={"reason": "x" * 501},
        )
    assert "longer than" in str(exc.value)


def test_an_unknown_role_or_kind_is_refused(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(DecisionRefused):
        _approve(store, role="ACCOUNTANT")
    with pytest.raises(DecisionRefused):
        _approve(store, kind="ordered_it")


def test_a_decision_must_belong_to_a_run_and_a_subject(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(DecisionRefused):
        _approve(store, run_id="  ")
    with pytest.raises(DecisionRefused):
        _approve(store, subject="")


def test_recent_reads_newest_first(tmp_path):
    store = _store(tmp_path)
    first = _approve(store)
    second = _approve(store, subject="AH-HT-014")
    assert [row["id"] for row in store.recent()] == [second["id"], first["id"]]
