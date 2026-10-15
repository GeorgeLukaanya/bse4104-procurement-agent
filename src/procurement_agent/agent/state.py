"""Mutable run state for one bounded-agent run.

The object itself lasts for one invocation. When a checkpoint directory is
given, ``checkpoint.py`` saves it after every tool step and restores it on the
next invocation of the same review, so a re-run resumes instead of repeating
completed steps (Requirements 7.5, 8.5, 9.4; Agent Task Contract section 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contract import AgentContract
from .steps import STEP_SCAN, STEP_ORDER


@dataclass
class AgentState:
    review_date: str
    sku: str | None
    officer_username: str
    caller_role: str
    confirm_comparison: bool = False
    confirm_draft: bool = False
    # Set when the officer discloses a rate for a non-UGX quotation (POL-003-C01).
    # None means the officer has not supplied one.
    exchange_rate_ugx_per_usd: float | None = None
    exchange_rate_effective_date: str | None = None
    step: str = STEP_SCAN
    iterations: int = 0
    stop_reason: str | None = None
    stop_detail: str | None = None
    reorder: dict[str, Any] | None = None
    eligibility: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None
    draft: dict[str, Any] | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)
    # The contract this run was bound by, carried so the trace can name it.
    contract: AgentContract | None = None
    # Week 6 run state. run_id names the checkpoint; step_sources holds the
    # data fingerprints each completed step read, so a resume can tell whether
    # a saved result is still current; confirmations records who passed which
    # gate and when; resumed describes what a resume restored, or None.
    run_id: str | None = None
    step_sources: dict[str, dict[str, str | None]] = field(default_factory=dict)
    confirmations: dict[str, dict[str, Any]] = field(default_factory=dict)
    resumed: dict[str, Any] | None = None

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
