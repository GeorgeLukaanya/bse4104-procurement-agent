"""Append-only agent-run log. Same JSONL idiom as extraction and tools."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator, Mapping

DEFAULT_AGENT_LOG = Path("evidence") / "traces" / "agent-runs.jsonl"


class AgentLog:
    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_AGENT_LOG

    def append(self, record: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(dict(record), ensure_ascii=False, separators=(",", ":"))
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
