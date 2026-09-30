"""Mutable run state. Nothing here is persisted between process starts.

Week 6 owns the state model. This object lasts for one CLI invocation so a
retry of the command repeats completed steps, the same way the RAG pipeline
does not preserve state today.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .steps import STEP_SCAN, STEP_ORDER


@dataclass
class AgentState:
    review_date: str
    sku: str | None
    officer_username: str
    caller_role: str
    confirm_comparison: bool = False
    confirm_draft: bool = False
    step: str = STEP_SCAN
    iterations: int = 0
    stop_reason: str | None = None
    stop_detail: str | None = None
    reorder: dict[str, Any] | None = None
    eligibility: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None
    draft: dict[str, Any] | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def current_allow_list(self) -> tuple[str, ...]:
        from .steps import ALLOW_LIST

        return ALLOW_LIST[self.step]

    def advance(self) -> None:
        try:
            index = STEP_ORDER.index(self.step)
        except ValueError:
            return
        if index + 1 < len(STEP_ORDER):
            self.step = STEP_ORDER[index + 1]

    def flagged_item(self) -> dict[str, Any] | None:
        if not self.reorder:
            return None
        items = self.reorder.get("items") or []
        if self.sku:
            for item in items:
                if item.get("sku") == self.sku:
                    return item
        return items[0] if items else None
