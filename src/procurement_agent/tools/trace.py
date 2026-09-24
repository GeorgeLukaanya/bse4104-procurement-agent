"""Append-only tool call log. Same JSONL idiom as ``runlog.RunLog``.

The trace never carries an API key. Entries are one JSON object per line and
are never rewritten.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator, Mapping

DEFAULT_TOOL_LOG = Path("evidence") / "traces" / "tool-runs.jsonl"


class ToolLog:
    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_TOOL_LOG

    def append(self, envelope: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "component": "TOOL",
            "tool": envelope.get("tool"),
            "tool_version": envelope.get("tool_version"),
            "status": envelope.get("status"),
            "errors": envelope.get("errors") or [],
            "trace": envelope.get("trace") or {},
            "data": envelope.get("data"),
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def read(self) -> Iterator[dict[str, Any]]:
        try:
            handle = open(self.path, encoding="utf-8")
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
