"""Append-only evidence log.

Requirement 13.1 requires each extraction result, each suppression and each
model call to be recorded with a timestamp and the component name. The Model
Selection Note additionally promises a retained run log as the evidence behind
its schema-conformance and backoff claims:

    "n extraction calls across the synthetic quotation set, n schema-conformant,
     n rejected. Run log retained in the repository."

Append-only, one JSON object per line. Never rewritten, never compacted: an
evidence log that can be edited in place is not evidence. A failed run is
recorded exactly like a successful one — a rate-limited run that left no trace
would make the daily quota look larger than it is and would hide the very
backoff behaviour the Note claims to have exercised.

THE API KEY IS NEVER WRITTEN HERE. Entries carry the configuration fingerprint,
which contains the model string and decoding settings and no credential.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DEFAULT_RUN_LOG = Path("evidence") / "traces" / "extraction-runs.jsonl"

COMPONENT = "AI_LAYER"

# Statuses. Requirement 3.3 names extraction-failed; the rest distinguish the
# ways a run can end so that the evidence log can be counted by outcome.
STATUS_OK = "ok"
STATUS_EXTRACTION_FAILED = "extraction_failed"
STATUS_SUPPRESSED = "suppressed"
STATUS_RATE_LIMITED = "rate_limited"
STATUS_CALL_FAILED = "call_failed"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class RunLogEntry:
    """One extraction attempt, successful or not."""

    source: str
    cache_key: str
    cache_hit: bool
    status: str
    attempts: int
    latency_s: float
    config_fingerprint: dict[str, Any]
    suppressed_patterns: list[dict[str, str]] = field(default_factory=list)
    landed_cost_blockers: list[dict[str, str]] = field(default_factory=list)
    landed_cost_ready: bool = False
    detail: str | None = None
    timestamp: str = field(default_factory=_now)
    component: str = COMPONENT

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "component": self.component,
            "source": self.source,
            "cache_key": self.cache_key,
            "cache_hit": self.cache_hit,
            "status": self.status,
            "attempts": self.attempts,
            "latency_s": round(self.latency_s, 4),
            "suppressed_patterns": self.suppressed_patterns,
            "landed_cost_ready": self.landed_cost_ready,
            "landed_cost_blockers": self.landed_cost_blockers,
            "detail": self.detail,
            "config_fingerprint": self.config_fingerprint,
        }


class RunLog:
    """A JSONL file opened in append mode for the duration of one write."""

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_RUN_LOG

    def append(self, entry: RunLogEntry) -> RunLogEntry:
        """Append one entry. Returns the entry so callers can report it."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry.to_dict(), ensure_ascii=False, separators=(",", ":"))
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return entry

    def read(self) -> Iterator[dict[str, Any]]:
        """Yield every entry. Malformed lines are skipped, not raised."""
        try:
            handle = open(self.path, "r", encoding="utf-8")
        except (FileNotFoundError, NotADirectoryError):
            return
        with handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def entries(self) -> list[dict[str, Any]]:
        return list(self.read())
