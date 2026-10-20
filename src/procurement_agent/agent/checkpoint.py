"""Persisted run state, so a re-run resumes instead of repeating steps.

Requirements 7.5, 8.5 and 9.4 and the Agent Task Contract (section 6) require
that a retry after a hand-off or a failure resumes from where the run stopped.
Before Week 6 the state lived for one command, so every re-run repeated the
scan, the eligibility check and the comparison.

One JSON file per run, under ``var/agent-state/`` (git-ignored). It is saved
after every tool step and at every stop. It holds working state only: tool
results the run already has, who passed which gate, the iteration count and
the stop reason. It holds no document text and nothing the run did not
produce.

A saved decision is reused only while the data it was computed from is
unchanged. A completed draft is retained as a record of an existing write,
even when those inputs change, so a resume cannot repeat that write.
Each step records the fingerprints of the files it read; on resume
they are recomputed, and the first step whose inputs changed, with every step
after it, runs again. A stale comparison is never carried forward, and a gate
confirmation given for an old comparison does not carry over to a new one.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from ..tools.data import DataIntegrityError, DataUnavailable, load_inventory, load_quotations, load_suppliers
from .state import AgentState
from .steps import STEP_COMPARE, STEP_DRAFT, STEP_ELIGIBILITY, STEP_ORDER, STEP_SCAN

CHECKPOINT_FORMAT = 1
DEFAULT_STATE_DIR = Path("var") / "agent-state"

# Which data files each step's result depends on. The planner reads the
# quotations to choose supplier identifiers, so eligibility depends on them too.
STEP_SOURCES: dict[str, tuple[str, ...]] = {
    STEP_SCAN: ("inventory",),
    STEP_ELIGIBILITY: ("suppliers", "quotations"),
    STEP_COMPARE: ("inventory", "suppliers", "quotations"),
    STEP_DRAFT: (),
}

_RESULT_FIELD = {
    STEP_SCAN: "reorder",
    STEP_ELIGIBILITY: "eligibility",
    STEP_COMPARE: "comparison",
    STEP_DRAFT: "draft",
}


def run_id_for(review_date: str, sku: str | None, officer_username: str) -> str:
    """One run per review, item and officer. The same review re-run finds it."""
    item = sku or "ALL"
    officer = re.sub(r"[^A-Za-z0-9_.-]", "_", officer_username)
    return f"AGT-{review_date}-{item}-{officer}"


def current_sources(
    *,
    inventory_path: str | None = None,
    suppliers_path: str | None = None,
    quotations_path: str | None = None,
    register_path: str | None = None,
) -> dict[str, str | None]:
    """Fingerprints of the data files as they are now. None if unreadable."""
    loaders = {
        "inventory": lambda: load_inventory(inventory_path, register_path),
        "suppliers": lambda: load_suppliers(suppliers_path, register_path),
        "quotations": lambda: load_quotations(quotations_path, register_path),
    }
    found: dict[str, str | None] = {}
    for name, load in loaders.items():
        try:
            _, fingerprint = load()
        except (DataUnavailable, DataIntegrityError, OSError, ValueError):
            fingerprint = None
        found[name] = fingerprint
    return found


class CheckpointStore:
    def __init__(self, directory: str | os.PathLike[str] | None = None) -> None:
        self.directory = Path(directory) if directory is not None else DEFAULT_STATE_DIR

    def path_for(self, run_id: str) -> Path:
        return self.directory / f"{run_id}.json"

    def load(self, run_id: str) -> dict[str, Any] | None:
        path = self.path_for(run_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            # An unreadable checkpoint is treated as absent: the run starts
            # fresh and repeats read-only steps, which is safe. It is never
            # partially trusted.
            return None
        if not isinstance(payload, dict) or payload.get("checkpoint_format") != CHECKPOINT_FORMAT:
            return None
        return payload

    def save(self, state: AgentState, *, saved_at: str) -> Path:
        path = self.path_for(state.run_id or "unnamed")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "checkpoint_format": CHECKPOINT_FORMAT,
            "run_id": state.run_id,
            "review_date": state.review_date,
            "sku": state.sku,
            "officer_username": state.officer_username,
            "contract_version": None if state.contract is None else state.contract.version,
            "step": state.step,
            "iterations": state.iterations,
            "stop_reason": state.stop_reason,
            "stop_detail": state.stop_detail,
            "results": {
                step: getattr(state, field)
                for step, field in _RESULT_FIELD.items()
                if getattr(state, field) is not None
            },
            "step_sources": state.step_sources,
            "confirmations": state.confirmations,
            "exchange_rate_ugx_per_usd": state.exchange_rate_ugx_per_usd,
            "exchange_rate_effective_date": state.exchange_rate_effective_date,
            "saved_at": saved_at,
        }
        # Write then rename, so a crash mid-write leaves the previous
        # checkpoint rather than half of a new one.
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        return path

    def discard(self, run_id: str) -> bool:
        try:
            self.path_for(run_id).unlink()
        except FileNotFoundError:
            return False
        return True


def restore(
    state: AgentState,
    checkpoint: Mapping[str, Any],
    now_sources: Mapping[str, str | None],
) -> dict[str, Any]:
    """Load still-valid results from ``checkpoint`` into ``state``.

    Returns a description of what was restored, which the trace carries.
    """
    for key in ("review_date", "sku", "officer_username"):
        if checkpoint.get(key) != getattr(state, key):
            return {"restored": False, "reason": f"checkpoint is for a different {key}"}

    results = checkpoint.get("results") or {}
    saved_sources = checkpoint.get("step_sources") or {}
    kept: list[str] = []
    invalid_from: str | None = None
    changed: list[str] = []
    for step in STEP_ORDER:
        if step not in results:
            break
        needed = STEP_SOURCES[step]
        recorded = saved_sources.get(step) or {}
        stale = [
            name for name in needed
            if recorded.get(name) is None or recorded.get(name) != now_sources.get(name)
        ]
        if stale:
            invalid_from = step
            changed = stale
            break
        kept.append(step)

    for step in kept:
        setattr(state, _RESULT_FIELD[step], results[step])
        state.step_sources[step] = dict(saved_sources.get(step) or {})

    # Completion is a fact about a side effect, not a cached decision. Source
    # changes invalidate calculations but cannot undo the requisition already
    # written. Only an explicit fresh run may compile another draft.
    if results.get(STEP_DRAFT) is not None:
        state.draft = results[STEP_DRAFT]

    confirmations = dict(checkpoint.get("confirmations") or {})
    if STEP_COMPARE not in kept:
        # A confirmation belongs to the comparison the officer saw. If that
        # comparison is being recomputed, the officer must confirm again.
        confirmations.pop("comparison", None)
        confirmations.pop("draft", None)
    state.confirmations = confirmations

    if kept:
        last = kept[-1]
        index = STEP_ORDER.index(last)
        state.step = STEP_ORDER[min(index + 1, len(STEP_ORDER) - 1)]
    if state.draft is not None:
        state.step = STEP_DRAFT
    # The iteration budget belongs to the run, not to one command. A resumed
    # run continues the count, even when nothing could be reused, so repeated
    # retries cannot reset the bound. --fresh starts a new run and a new count.
    state.iterations = int(checkpoint.get("iterations") or 0)

    report: dict[str, Any] = {
        "restored": bool(kept),
        "from_checkpoint_saved_at": checkpoint.get("saved_at"),
        "previous_stop_reason": checkpoint.get("stop_reason"),
        "kept_steps": kept,
        "restored_iterations": state.iterations,
    }
    if invalid_from is not None:
        report["recomputed_from"] = invalid_from
        report["changed_sources"] = changed
    return report
