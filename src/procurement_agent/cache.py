"""Content-addressed extraction cache.

The Model Selection Note names caching as one of four design controls:
"Identical file uploads skip API calls completely and reuse existing JSON
records. This is what makes repeated evaluation runs affordable within the
daily request quota, and it also makes them reproducible."

THE KEY IS NOT THE DOCUMENT HASH ALONE.

The key is SHA-256 over the converted Markdown *combined with the full
configuration fingerprint* — model string, temperature, thinking budget, max
output tokens and prompt version. Keying on the document alone would return a
result produced under an older prompt version, or a different model, as though
it came from the current one. Every evaluation figure computed from that cache
would then be attributing one prompt's behaviour to another, and nothing in the
output would show it. Requirement 3 makes extraction accuracy a measured success
criterion (S9), so silently mixing configurations corrupts the measurement the
week exists to produce.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import ExtractionConfig

DEFAULT_CACHE_DIR = Path(".cache") / "extractions"

# Bumped when the on-disk entry layout changes, so old entries are ignored
# rather than misread.
# v2 added `suppressions`. A v1 entry carried only the already-suppressed
# record, so replaying it looked clean and lost the requirement 14.2 audit
# entry; v1 entries are therefore ignored rather than read.
CACHE_FORMAT_VERSION = 2


def document_digest(converted_markdown: str) -> str:
    """SHA-256 of the Converted Quotation Document.

    Requirement 2.3 caches converted Markdown against a hash of its source file
    so that "re-processing the same source file yields byte-identical model
    input". This is the hash of that byte-identical input.
    """
    return hashlib.sha256(converted_markdown.encode("utf-8")).hexdigest()


def cache_key(converted_markdown: str, config: ExtractionConfig) -> str:
    """SHA-256 over the document digest AND the configuration fingerprint."""
    material = json.dumps(
        {
            "cache_format": CACHE_FORMAT_VERSION,
            "document_sha256": document_digest(converted_markdown),
            "config": config.fingerprint(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CacheEntry:
    """A stored extraction, with the configuration that produced it."""

    key: str
    document_sha256: str
    config_fingerprint: dict[str, Any]
    record: dict[str, Any]
    attempts: int
    latency_s: float
    # Prohibited patterns found when this record was first extracted, WITHOUT
    # their excerpts. The record above already has the offending values
    # replaced, so without this the guard would find nothing on a cache hit and
    # the quotation would read as clean (requirement 14.2's audit entry would
    # be lost on every run after the first).
    suppressions: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cache_format": CACHE_FORMAT_VERSION,
            "key": self.key,
            "document_sha256": self.document_sha256,
            "config_fingerprint": self.config_fingerprint,
            "record": self.record,
            "attempts": self.attempts,
            "latency_s": self.latency_s,
            "suppressions": self.suppressions,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CacheEntry":
        return cls(
            key=payload["key"],
            document_sha256=payload["document_sha256"],
            config_fingerprint=payload["config_fingerprint"],
            record=payload["record"],
            attempts=int(payload.get("attempts", 0)),
            latency_s=float(payload.get("latency_s", 0.0)),
            suppressions=list(payload.get("suppressions") or []),
        )


class ExtractionCache:
    """A directory of JSON entries, one per cache key."""

    def __init__(self, directory: str | os.PathLike[str] | None = None) -> None:
        self.directory = Path(directory) if directory is not None else DEFAULT_CACHE_DIR

    def key_for(self, converted_markdown: str, config: ExtractionConfig) -> str:
        return cache_key(converted_markdown, config)

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> CacheEntry | None:
        """Return the stored entry, or None on a miss or an unreadable entry."""
        path = self._path(key)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, NotADirectoryError):
            return None
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            # A corrupt entry is a miss, not a crash. The cost of a miss is one
            # API call; the cost of trusting a corrupt entry is a wrong record.
            return None
        if not isinstance(payload, dict):
            return None
        if payload.get("cache_format") != CACHE_FORMAT_VERSION:
            return None
        if payload.get("key") != key:
            return None
        try:
            entry = CacheEntry.from_dict(payload)
        except (KeyError, TypeError, ValueError):
            return None
        return entry

    def put(self, entry: CacheEntry) -> Path:
        """Write an entry atomically.

        Written to a temporary file in the same directory and then renamed, so
        an interrupted run cannot leave a half-written entry that a later run
        would read as a hit.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(entry.key)
        text = json.dumps(entry.to_dict(), indent=2, ensure_ascii=False)
        handle, tmp_name = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp_name, path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        return path
