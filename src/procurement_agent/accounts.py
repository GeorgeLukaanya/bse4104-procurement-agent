"""The workspace, its people, and their sessions, from the standard library.

A workspace is set up once, by whoever opens the page first: they name the
business and create their own account, and that account owns the workspace and
may add the other people. Nothing is seeded, because a system that invents a
company and two staff is a demonstration rather than a product.

Known limitation KL-02 says identity and confirmation are trusted command-line
inputs: ``--role`` and ``--officer`` are whatever the person starting the
process typed, with no login behind them, so an audit entry attributing a
decision to an officer attributes it to a flag. The charter asks for "two
seeded user roles with simple authentication, sufficient to attribute audit
entries to an identity". This module is that, for the web path.

What it is, in full, so nobody mistakes it for more than it is.

Passwords are stored as scrypt hashes with a per-user salt, never in the clear
and never reversibly. scrypt is in ``hashlib``, so this costs no dependency.
The work factor is deliberately on the slow side for a login, which is the
point of it.

A session token is 32 random bytes from ``secrets``. The database stores only
its SHA-256, so a copy of the file does not hand anyone a live session. The
cookie is HttpOnly and SameSite=Strict; it is not marked Secure because the
server runs on plain http on localhost, and that is the one place this is
allowed to run.

Failed logins are counted per username and the account refuses attempts for a
short time after too many. That is a speed bump against guessing, not a defence
against a serious attacker.

What it is not: there is no password reset, no change of password, no account
listing over HTTP, no lockout notification, no rate limit per source address,
and no transport security. The roles are fixed to the two the charter names.
This is enough to make an audit entry mean something on a single machine with
synthetic data. It is not enough to put anything real behind.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .tools.contract import ROLE_MANAGER, ROLE_OFFICER

DEFAULT_ACCOUNTS_PATH = Path("var") / "accounts.sqlite3"

# Only the two roles the charter seeds. A third is a charter change.
ACCOUNT_ROLES = (ROLE_OFFICER, ROLE_MANAGER)

SESSION_HOURS = 12
MIN_PASSWORD = 10

# scrypt. n is the work factor; 2**14 keeps a login around a tenth of a second
# on a laptop, which is slow enough to matter when guessing and fast enough not
# to be felt once.
SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32

MAX_FAILURES = 5
LOCKOUT_MINUTES = 5

SCHEMA = """
CREATE TABLE IF NOT EXISTS organisation (
  id         INTEGER PRIMARY KEY CHECK (id = 1),
  name       TEXT NOT NULL,
  locations  TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
  username      TEXT PRIMARY KEY,
  display_name  TEXT NOT NULL,
  role          TEXT NOT NULL,
  salt          BLOB NOT NULL,
  password_hash BLOB NOT NULL,
  created_at    TEXT NOT NULL,
  failures      INTEGER NOT NULL DEFAULT 0,
  locked_until  TEXT,
  is_owner      INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash  TEXT PRIMARY KEY,
  username    TEXT NOT NULL REFERENCES users(username),
  created_at  TEXT NOT NULL,
  expires_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions (username);
"""

Clock = Callable[[], datetime]


class AccountError(Exception):
    """Something was wrong with the account, and the caller may be told why."""


class SignInRefused(Exception):
    """The sign-in did not succeed.

    The message is deliberately the same whatever went wrong, because telling
    the person which half they got right is telling an attacker the same.
    """

    def __init__(self, message: str = "That username and password do not match.") -> None:
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_DKLEN,
    )


def generate_password() -> str:
    """A password for a seeded account, shown once and never stored in the clear."""
    return secrets.token_urlsafe(12)


class Accounts:
    """The two seeded roles, their passwords and their sessions."""

    def __init__(
        self,
        path: str | os.PathLike[str] | None = None,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else DEFAULT_ACCOUNTS_PATH
        self._clock = clock or _now
        self._ready = False

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        if not self._ready:
            connection.executescript(SCHEMA)
            self._migrate(connection)
            connection.commit()
            self._ready = True
        return connection

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        """Add what a database made by an earlier version does not have yet.

        CREATE TABLE IF NOT EXISTS leaves an existing table alone, columns and
        all, so a new column has to be asked for by name.
        """
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
        if "is_owner" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN is_owner INTEGER NOT NULL DEFAULT 0")

    # -- accounts ---------------------------------------------------------

    def create(self, *, username: str, display_name: str, role: str, password: str) -> dict[str, Any]:
        username = username.strip()
        if not username:
            raise AccountError("A username is required.")
        if role not in ACCOUNT_ROLES:
            raise AccountError(f"{role!r} is not one of the two seeded roles.")
        if len(password) < MIN_PASSWORD:
            raise AccountError(f"The password must be at least {MIN_PASSWORD} characters.")
        salt = secrets.token_bytes(16)
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    "INSERT INTO users (username, display_name, role, salt, password_hash, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (username, display_name or username, role, salt,
                     hash_password(password, salt), _stamp(self._clock())),
                )
        except sqlite3.IntegrityError as exc:
            raise AccountError(f"{username!r} already has an account.") from exc
        finally:
            connection.close()
        return {"username": username, "display_name": display_name or username, "role": role}

    def count(self) -> int:
        connection = self._connect()
        try:
            return int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])
        finally:
            connection.close()

    def get(self, username: str) -> dict[str, Any] | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT username, display_name, role FROM users WHERE username = ?", (username,)
            ).fetchone()
        finally:
            connection.close()
        return dict(row) if row else None

    # -- signing in -------------------------------------------------------

    def sign_in(self, username: str, password: str) -> tuple[str, dict[str, Any]]:
        """Check the password and open a session. Returns (token, user)."""
        now = self._clock()
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ?", (str(username).strip(),)
            ).fetchone()

            if row is None:
                # Spend the time anyway, so a missing account does not answer
                # faster than a wrong password and give itself away.
                hash_password(str(password), b"absent-account-salt")
                raise SignInRefused()

            locked_until = _parse(row["locked_until"])
            if locked_until and locked_until > now:
                raise SignInRefused(
                    "Too many wrong attempts. Try again in a few minutes."
                )

            candidate = hash_password(str(password), row["salt"])
            if not hmac.compare_digest(candidate, row["password_hash"]):
                failures = int(row["failures"]) + 1
                locked = _stamp(now + timedelta(minutes=LOCKOUT_MINUTES)) if failures >= MAX_FAILURES else None
                with connection:
                    connection.execute(
                        "UPDATE users SET failures = ?, locked_until = ? WHERE username = ?",
                        (0 if locked else failures, locked, row["username"]),
                    )
                raise SignInRefused()

            token = secrets.token_urlsafe(32)
            expires = now + timedelta(hours=SESSION_HOURS)
            with connection:
                connection.execute(
                    "UPDATE users SET failures = 0, locked_until = NULL WHERE username = ?",
                    (row["username"],),
                )
                connection.execute(
                    "INSERT INTO sessions (token_hash, username, created_at, expires_at) "
                    "VALUES (?, ?, ?, ?)",
                    (_token_hash(token), row["username"], _stamp(now), _stamp(expires)),
                )
            user = {
                "username": row["username"],
                "display_name": row["display_name"],
                "role": row["role"],
                "expires_at": _stamp(expires),
            }
        finally:
            connection.close()
        return token, user

    def session(self, token: str | None) -> dict[str, Any] | None:
        """Who this token belongs to, or None. Expired sessions are removed."""
        if not token:
            return None
        now = self._clock()
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT s.token_hash, s.expires_at, u.username, u.display_name, u.role "
                "FROM sessions s JOIN users u ON u.username = s.username "
                "WHERE s.token_hash = ?",
                (_token_hash(token),),
            ).fetchone()
            if row is None:
                return None
            expires = _parse(row["expires_at"])
            if expires is None or expires <= now:
                with connection:
                    connection.execute("DELETE FROM sessions WHERE token_hash = ?", (row["token_hash"],))
                return None
            return {
                "username": row["username"],
                "display_name": row["display_name"],
                "role": row["role"],
                "expires_at": row["expires_at"],
            }
        finally:
            connection.close()

    def sign_out(self, token: str | None) -> None:
        if not token:
            return
        connection = self._connect()
        try:
            with connection:
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
        finally:
            connection.close()

    def purge_expired(self) -> int:
        connection = self._connect()
        try:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM sessions WHERE expires_at <= ?", (_stamp(self._clock()),)
                )
            return cursor.rowcount or 0
        finally:
            connection.close()

    # -- the workspace ----------------------------------------------------

    def organisation(self) -> dict[str, Any] | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT name, locations, created_at FROM organisation WHERE id = 1"
            ).fetchone()
        finally:
            connection.close()
        return dict(row) if row else None

    def needs_setup(self) -> bool:
        """True until somebody has made the first account."""
        return self.count() == 0

    def set_up(
        self,
        *,
        organisation_name: str,
        people: Sequence[Mapping[str, str]],
        you: str,
        locations: str | None = None,
    ) -> dict[str, Any]:
        """Onboard a business: name it and provision its whole team at once.

        A reorder review needs somebody to prepare it and somebody to approve
        it, and the two must not be the same account, or the approval gate is
        decoration. So both roles are required here rather than left to be
        added later and forgotten.

        Refused once anybody has an account, so the route behind this cannot
        be used to add a second owner afterwards. The check and every insert
        share one transaction: either the business and all of its people
        exist, or none of them do, and two browsers racing on a first visit
        cannot both win.
        """
        organisation_name = organisation_name.strip()
        if not organisation_name:
            raise AccountError("The business needs a name.")
        if not people:
            raise AccountError("A business needs at least one person.")

        prepared: list[dict[str, Any]] = []
        seen: set[str] = set()
        for person in people:
            username = str(person.get("username") or "").strip()
            role = str(person.get("role") or "")
            password = str(person.get("password") or "")
            display_name = str(person.get("display_name") or "").strip()
            if not username:
                raise AccountError("Everyone needs a username.")
            if username in seen:
                raise AccountError(f"{username!r} is listed twice.")
            seen.add(username)
            if role not in ACCOUNT_ROLES:
                raise AccountError(f"{role!r} is not one of the two roles.")
            if len(password) < MIN_PASSWORD:
                raise AccountError(
                    f"{username}: the password must be at least {MIN_PASSWORD} characters."
                )
            salt = secrets.token_bytes(16)
            prepared.append({
                "username": username,
                "display_name": display_name or username,
                "role": role,
                "salt": salt,
                "password_hash": hash_password(password, salt),
            })

        roles = {person["role"] for person in prepared}
        missing = [role for role in ACCOUNT_ROLES if role not in roles]
        if missing:
            raise AccountError(
                "A business needs somebody who buys and somebody who approves. "
                f"Missing: {', '.join(missing)}."
            )
        if you not in seen:
            raise AccountError("Say which of these accounts is yours.")

        now = _stamp(self._clock())
        connection = self._connect()
        try:
            with connection:
                if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
                    raise AccountError("This workspace has already been set up.")
                connection.execute(
                    "INSERT INTO organisation (id, name, locations, created_at) VALUES (1, ?, ?, ?)",
                    (organisation_name, (locations or "").strip() or None, now),
                )
                connection.executemany(
                    "INSERT INTO users "
                    "(username, display_name, role, salt, password_hash, created_at, is_owner) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [
                        (person["username"], person["display_name"], person["role"],
                         person["salt"], person["password_hash"], now,
                         1 if person["username"] == you else 0)
                        for person in prepared
                    ],
                )
        except sqlite3.IntegrityError as exc:
            raise AccountError("This workspace has already been set up.") from exc
        finally:
            connection.close()

        return {
            "organisation": {"name": organisation_name, "locations": locations or None},
            "people": [
                {"username": person["username"], "display_name": person["display_name"],
                 "role": person["role"], "is_owner": person["username"] == you}
                for person in prepared
            ],
            "you": you,
        }

    def rename_organisation(self, name: str, locations: str | None = None) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise AccountError("The business needs a name.")
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    "UPDATE organisation SET name = ?, locations = ? WHERE id = 1",
                    (name, (locations or "").strip() or None),
                )
        finally:
            connection.close()
        return {"name": name, "locations": locations or None}

    # -- the people -------------------------------------------------------

    def people(self) -> list[dict[str, Any]]:
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT username, display_name, role, is_owner, created_at "
                "FROM users ORDER BY is_owner DESC, created_at ASC"
            ).fetchall()
        finally:
            connection.close()
        return [
            {**dict(row), "is_owner": bool(row["is_owner"])}
            for row in rows
        ]

    def owns_workspace(self, username: str) -> bool:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT is_owner FROM users WHERE username = ?", (username,)
            ).fetchone()
        finally:
            connection.close()
        return bool(row and row["is_owner"])


def _token_hash(token: str) -> str:
    """Only the hash is stored, so the file never holds a usable token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
