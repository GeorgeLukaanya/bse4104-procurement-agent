"""Append-only record of every decision a person or the agent made.

Until now a decision lived in two places: a checkpoint file under
``var/agent-state/`` and a line in a JSONL trace. Neither is a record anyone
can be shown. Known limitation KL-03 says local writes are not a transaction
and have no shared-writer lock, and KL-10 says the traces are plain files with
no access control. This module is the first step out of that, for the one
record we put in front of a human: the Activity screen.

Three properties matter more than the columns.

Append only, and the database enforces it. Two triggers abort any UPDATE or
DELETE, so "we never edit a decision" is not a convention someone can forget.
A decision that stops being true is superseded by a later row that names it in
``supersedes``; the old row stays exactly as it was written.

``detail`` holds the figures as they stood. An approval that records only
"approved" is useless six weeks later when the quotation has expired and the
prices have moved. The row carries the landed cost, the supplier and the clause
that applied at the moment of the decision.

SQLite, from the standard library. ``pyproject.toml`` has no runtime
dependencies and that is worth keeping. This gives us a real transaction around
the write, which KL-03 records that we do not otherwise have, and needs no
service to run in a demo. Postgres is a later problem and this schema moves
across unchanged.

What this does not fix: the requisition store and the trace files are still
plain files, so the whole write path is not transactional yet. This makes the
record we show people trustworthy, which is the right first step and not the
last one.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from . import guards
from .tools.contract import ROLE_AGENT, ROLE_MANAGER, ROLE_OFFICER, ROLES

DEFAULT_DECISIONS_PATH = Path("var") / "decisions.sqlite3"

# What a decision can be. A new kind is a schema change and a conversation,
# not something a caller invents at the call site.
KIND_RATE_GIVEN = "rate_given"
KIND_COMPARISON_APPROVED = "comparison_approved"
KIND_REQUISITION_SENT = "requisition_sent"
KIND_APPROVED = "approved"
KIND_SENT_BACK = "sent_back"
KIND_RUN_STOPPED = "run_stopped"

KINDS = (
    KIND_RATE_GIVEN,
    KIND_COMPARISON_APPROVED,
    KIND_REQUISITION_SENT,
    KIND_APPROVED,
    KIND_SENT_BACK,
    KIND_RUN_STOPPED,
)

# Who may record which kind. The agent records what it did; it never records an
# approval, because approving is the one thing it must not do (POL-004-C03).
ALLOWED_KINDS = {
    ROLE_OFFICER: (KIND_RATE_GIVEN, KIND_COMPARISON_APPROVED, KIND_REQUISITION_SENT),
    ROLE_MANAGER: (KIND_APPROVED, KIND_SENT_BACK),
    ROLE_AGENT: (KIND_RUN_STOPPED,),
}

MAX_REASON = 500

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
  id          TEXT PRIMARY KEY,
  run_id      TEXT NOT NULL,
  actor       TEXT NOT NULL,
  role        TEXT NOT NULL,
  kind        TEXT NOT NULL,
  subject     TEXT NOT NULL,
  detail      TEXT NOT NULL,
  decided_at  TEXT NOT NULL,
  supersedes  TEXT REFERENCES decisions(id)
);
CREATE INDEX IF NOT EXISTS decisions_run ON decisions (run_id, decided_at);
CREATE INDEX IF NOT EXISTS decisions_subject ON decisions (subject, decided_at);

CREATE TRIGGER IF NOT EXISTS decisions_no_update
BEFORE UPDATE ON decisions
BEGIN
  SELECT RAISE(ABORT, 'decisions are append only: supersede the row instead');
END;

CREATE TRIGGER IF NOT EXISTS decisions_no_delete
BEFORE DELETE ON decisions
BEGIN
  SELECT RAISE(ABORT, 'decisions are append only: a decision is never removed');
END;
"""

Clock = Callable[[], datetime]
NewId = Callable[[], str]


class DecisionRefused(ValueError):
    """The decision was not recorded, and the caller is told why."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return "DEC-" + uuid.uuid4().hex[:12]


class DecisionStore:
    """Every decision, in the order they were made. Nothing is ever changed."""

    def __init__(
        self,
        path: str | os.PathLike[str] | None = None,
        *,
        clock: Clock | None = None,
        new_id: NewId | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else DEFAULT_DECISIONS_PATH
        self._clock = clock or _now
        self._new_id = new_id or _new_id
        self._ready = False

    # -- connection -------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """One connection per operation, so the threaded server does not share one."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        if not self._ready:
            connection.executescript(SCHEMA)
            connection.commit()
            self._ready = True
        return connection

    # -- writing ----------------------------------------------------------

    def record(
        self,
        *,
        run_id: str,
        actor: str,
        role: str,
        kind: str,
        subject: str,
        detail: Mapping[str, Any] | None = None,
        supersedes: str | None = None,
    ) -> dict[str, Any]:
        """Append one decision. Returns the row exactly as it was written."""
        if role not in ROLES:
            raise DecisionRefused(f"{role!r} is not a seeded role.")
        if kind not in KINDS:
            raise DecisionRefused(f"{kind!r} is not a decision kind.")
        if kind not in ALLOWED_KINDS[role]:
            raise DecisionRefused(
                f"{role} may not record {kind!r}. "
                f"That role records {', '.join(ALLOWED_KINDS[role])}."
            )
        if not run_id.strip():
            raise DecisionRefused("run_id is required: a decision belongs to a review.")
        if not subject.strip():
            raise DecisionRefused("subject is required: a decision is about something.")

        payload = dict(detail or {})
        reason = payload.get("reason")
        if isinstance(reason, str):
            if len(reason) > MAX_REASON:
                raise DecisionRefused(f"reason is longer than {MAX_REASON} characters.")
            # A typed reason is untrusted text on its way into a record other
            # people read, so it is screened like a supplier note.
            findings = guards.scan({"text": reason})
            if findings:
                raise DecisionRefused(
                    "The reason reads as an approval or a commitment: "
                    + findings[0].description
                )

        row = {
            "id": self._new_id(),
            "run_id": run_id,
            "actor": actor,
            "role": role,
            "kind": kind,
            "subject": subject,
            "detail": payload,
            "decided_at": _stamp(self._clock()),
            "supersedes": supersedes,
        }

        connection = self._connect()
        try:
            if supersedes is not None:
                found = connection.execute(
                    "SELECT id FROM decisions WHERE id = ?", (supersedes,)
                ).fetchone()
                if found is None:
                    raise DecisionRefused(
                        f"{supersedes!r} is not a decision in this store, "
                        "so nothing can supersede it."
                    )
            with connection:
                connection.execute(
                    "INSERT INTO decisions "
                    "(id, run_id, actor, role, kind, subject, detail, decided_at, supersedes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row["id"], row["run_id"], row["actor"], row["role"], row["kind"],
                        row["subject"],
                        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                        row["decided_at"], row["supersedes"],
                    ),
                )
        finally:
            connection.close()
        return row

    # -- reading ----------------------------------------------------------

    def recent(self, *, limit: int = 100, since: str | None = None) -> list[dict[str, Any]]:
        """Newest first, which is the order the Activity screen reads in."""
        sql = "SELECT * FROM decisions"
        params: list[Any] = []
        if since:
            sql += " WHERE decided_at >= ?"
            params.append(since)
        sql += " ORDER BY decided_at DESC, rowid DESC LIMIT ?"
        params.append(max(1, int(limit)))
        return self._query(sql, params)

    def for_subject(self, subject: str) -> list[dict[str, Any]]:
        """Oldest first: this is the chain of what happened to one requisition."""
        return self._query(
            "SELECT * FROM decisions WHERE subject = ? ORDER BY decided_at ASC, rowid ASC",
            [subject],
        )

    def for_run(self, run_id: str) -> list[dict[str, Any]]:
        return self._query(
            "SELECT * FROM decisions WHERE run_id = ? ORDER BY decided_at ASC, rowid ASC",
            [run_id],
        )

    def superseded_ids(self) -> set[str]:
        """Rows that a later decision replaced. Still shown, marked as replaced."""
        rows = self._query(
            "SELECT supersedes AS id FROM decisions WHERE supersedes IS NOT NULL", []
        )
        return {row["id"] for row in rows if row.get("id")}

    def _query(self, sql: str, params: Iterable[Any]) -> list[dict[str, Any]]:
        connection = self._connect()
        try:
            rows = connection.execute(sql, tuple(params)).fetchall()
        finally:
            connection.close()
        out: list[dict[str, Any]] = []
        for row in rows:
            record = dict(row)
            if "detail" in record:
                try:
                    record["detail"] = json.loads(record["detail"])
                except (TypeError, json.JSONDecodeError):
                    record["detail"] = {}
            out.append(record)
        return out
