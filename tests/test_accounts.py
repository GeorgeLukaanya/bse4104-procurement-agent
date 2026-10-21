"""Accounts and sessions. No network, no key, and no password stored in the clear."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from procurement_agent.accounts import (
    MAX_FAILURES,
    MIN_PASSWORD,
    SESSION_HOURS,
    AccountError,
    Accounts,
    SignInRefused,
)

PASSWORD = "a-long-enough-password"
OFFICER = "PROCUREMENT_OFFICER"
MANAGER = "PROCUREMENT_MANAGER"


class Ticker:
    """A clock the test moves on purpose."""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now = self.now + timedelta(**kwargs)


@pytest.fixture
def clock():
    return Ticker(datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc))


@pytest.fixture
def accounts(tmp_path, clock):
    store = Accounts(tmp_path / "accounts.sqlite3", clock=clock)
    store.create(username="a.nakato", display_name="Agnes Nakato", role=OFFICER, password=PASSWORD)
    return store


def test_a_password_is_never_stored_in_the_clear(accounts):
    with sqlite3.connect(accounts.path) as connection:
        row = connection.execute("SELECT * FROM users").fetchone()
    stored = b"".join(value for value in row if isinstance(value, bytes))
    assert PASSWORD.encode("utf-8") not in stored
    for value in row:
        assert value != PASSWORD


def test_the_same_password_hashes_differently_for_two_people(accounts):
    accounts.create(username="b.okello", display_name="Brenda Okello", role=OFFICER, password=PASSWORD)
    with sqlite3.connect(accounts.path) as connection:
        hashes = [row[0] for row in connection.execute("SELECT password_hash FROM users")]
    assert len(hashes) == 2
    assert hashes[0] != hashes[1], "a per-user salt is what makes these differ"


def test_signing_in_returns_a_session(accounts):
    token, user = accounts.sign_in("a.nakato", PASSWORD)
    assert user["role"] == OFFICER
    assert user["display_name"] == "Agnes Nakato"
    assert accounts.session(token)["username"] == "a.nakato"


def test_the_stored_session_is_not_the_token(accounts):
    """A copy of the file must not hand anyone a live session."""
    token, _ = accounts.sign_in("a.nakato", PASSWORD)
    with sqlite3.connect(accounts.path) as connection:
        stored = connection.execute("SELECT token_hash FROM sessions").fetchone()[0]
    assert stored != token
    assert token not in stored


def test_a_wrong_password_is_refused(accounts):
    with pytest.raises(SignInRefused):
        accounts.sign_in("a.nakato", "not-the-password")


def test_an_unknown_user_and_a_wrong_password_say_the_same_thing(accounts):
    """Telling someone which half they got right tells an attacker the same."""
    with pytest.raises(SignInRefused) as wrong:
        accounts.sign_in("a.nakato", "not-the-password")
    with pytest.raises(SignInRefused) as missing:
        accounts.sign_in("nobody.here", PASSWORD)
    assert str(wrong.value) == str(missing.value)


def test_too_many_wrong_attempts_lock_the_account_for_a_while(accounts, clock):
    for _ in range(MAX_FAILURES):
        with pytest.raises(SignInRefused):
            accounts.sign_in("a.nakato", "not-the-password")

    # even the right password is refused while the lock holds
    with pytest.raises(SignInRefused) as exc:
        accounts.sign_in("a.nakato", PASSWORD)
    assert "Try again" in str(exc.value)

    clock.advance(minutes=6)
    token, _ = accounts.sign_in("a.nakato", PASSWORD)
    assert accounts.session(token) is not None


def test_a_good_sign_in_clears_the_failures(accounts):
    for _ in range(MAX_FAILURES - 1):
        with pytest.raises(SignInRefused):
            accounts.sign_in("a.nakato", "not-the-password")
    accounts.sign_in("a.nakato", PASSWORD)
    for _ in range(MAX_FAILURES - 1):
        with pytest.raises(SignInRefused):
            accounts.sign_in("a.nakato", "not-the-password")
    assert accounts.sign_in("a.nakato", PASSWORD)[0]


def test_a_session_expires(accounts, clock):
    token, _ = accounts.sign_in("a.nakato", PASSWORD)
    clock.advance(hours=SESSION_HOURS, minutes=1)
    assert accounts.session(token) is None


def test_an_expired_session_is_removed_not_merely_ignored(accounts, clock):
    token, _ = accounts.sign_in("a.nakato", PASSWORD)
    clock.advance(hours=SESSION_HOURS, minutes=1)
    accounts.session(token)
    with sqlite3.connect(accounts.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_signing_out_ends_that_session_only(accounts):
    first, _ = accounts.sign_in("a.nakato", PASSWORD)
    second, _ = accounts.sign_in("a.nakato", PASSWORD)
    accounts.sign_out(first)
    assert accounts.session(first) is None
    assert accounts.session(second) is not None


def test_a_made_up_token_is_nobody(accounts):
    assert accounts.session("not-a-real-token") is None
    assert accounts.session("") is None
    assert accounts.session(None) is None


def test_a_short_password_is_refused(accounts):
    with pytest.raises(AccountError) as exc:
        accounts.create(username="c.tumusiime", display_name="C", role=OFFICER, password="short")
    assert str(MIN_PASSWORD) in str(exc.value)


def test_only_the_two_seeded_roles_exist(accounts):
    with pytest.raises(AccountError) as exc:
        accounts.create(username="d.auma", display_name="D", role="ACCOUNTANT", password=PASSWORD)
    assert "seeded roles" in str(exc.value)


def test_a_username_is_claimed_once(accounts):
    with pytest.raises(AccountError) as exc:
        accounts.create(username="a.nakato", display_name="Someone Else", role=OFFICER, password=PASSWORD)
    assert "already has an account" in str(exc.value)


def test_seeding_creates_the_two_charter_roles_once(tmp_path, clock):
    store = Accounts(tmp_path / "accounts.sqlite3", clock=clock)
    created = store.seed()
    assert {account["role"] for account in created} == {OFFICER, MANAGER}
    assert all(len(account["password"]) >= MIN_PASSWORD for account in created)
    assert store.seed() == [], "a second start must not reseed"
    assert store.count() == 2


def test_a_seeded_password_works_and_is_not_recoverable(tmp_path, clock):
    store = Accounts(tmp_path / "accounts.sqlite3", clock=clock)
    [first] = [a for a in store.seed() if a["role"] == MANAGER]
    token, user = store.sign_in(first["username"], first["password"])
    assert user["role"] == MANAGER
    with sqlite3.connect(store.path) as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE username = ?", (first["username"],)
        ).fetchone()
    assert first["password"] not in str(row)


def test_purge_removes_only_what_has_expired(accounts, clock):
    old, _ = accounts.sign_in("a.nakato", PASSWORD)
    clock.advance(hours=SESSION_HOURS - 1)
    fresh, _ = accounts.sign_in("a.nakato", PASSWORD)
    clock.advance(hours=2)
    assert accounts.purge_expired() == 1
    assert accounts.session(old) is None
    assert accounts.session(fresh) is not None
