"""Run the bounded weekly-reorder loop to a stop reason."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from ..tools.contract import (
    CODE_EXCHANGE_RATE_REQUIRED,
    ROLE_MANAGER,
    ROLE_OFFICER,
    STATUS_FAILED,
    STATUS_NO_RESULT,
    STATUS_OK,
    STATUS_UNAUTHORIZED,
    STATUS_UNAVAILABLE,
)
from ..memory.store import MemoryRefused, MemoryStore, advisory_block
from ..tools.dispatch import invoke
from .checkpoint import STEP_SOURCES, CheckpointStore, current_sources, restore, run_id_for
from .contract import DEFAULT_CONTRACT_PATH, AgentContract, load_contract
from .planner import DeterministicPlanner, Planner
from .state import AgentState
from .steps import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_TIMEOUT_S,
    STEP_COMPARE,
    STEP_DRAFT,
    STEP_ELIGIBILITY,
    STEP_SCAN,
    STOP_AWAITING_HUMAN,
    STOP_COMPLETED,
    STOP_FAILED,
    STOP_MAX_ITERATIONS,
    STOP_NO_REORDER,
    STOP_REFUSED,
    STOP_TIMEOUT,
    STOP_UNAUTHORIZED,
)
from .trace import AgentLog, DEFAULT_AGENT_LOG

Clock = Callable[[], datetime]


@dataclass
class AgentResult:
    stop_reason: str
    stop_detail: str
    iterations: int
    state: AgentState
    calls: list[dict[str, Any]] = field(default_factory=list)
    # Advisory memory shown beside the result; never an input to it.
    memory: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": "AGENT",
            "stop_reason": self.stop_reason,
            "stop_detail": self.stop_detail,
            "iterations": self.iterations,
            "step": self.state.step,
            "run_id": self.state.run_id,
            "resumed": self.state.resumed,
            "confirmations": self.state.confirmations,
            "review_date": self.state.review_date,
            "sku": self.state.sku,
            "caller_role": self.state.caller_role,
            # Which contract bounded this run, and that contract's name for how
            # it ended, so a trace can be read against the document.
            "contract": None if self.state.contract is None else {
                "path": self.state.contract.path,
                "version": self.state.contract.version,
                "iterations_per_item": self.state.contract.iterations_per_item,
                "wall_clock_seconds": self.state.contract.wall_clock_seconds,
                "stop_reason": self.state.contract.stop_reason_for(self.stop_reason),
            },
            "reorder": self.state.reorder,
            "eligibility": self.state.eligibility,
            "comparison": self.state.comparison,
            "draft": self.state.draft,
            "calls": [
                {
                    "tool": call.get("tool"),
                    "status": call.get("status"),
                    "errors": call.get("errors") or [],
                }
                for call in self.calls
            ],
            "memory": self.memory,
        }


def run_workflow(
    *,
    review_date: str,
    sku: str | None = None,
    officer_username: str = "a.nakato",
    caller_role: str = ROLE_OFFICER,
    confirm_comparison: bool = False,
    confirm_draft: bool = False,
    exchange_rate_ugx_per_usd: float | None = None,
    exchange_rate_effective_date: str | None = None,
    max_iterations: int | None = None,
    timeout_s: float | None = None,
    planner: Planner | None = None,
    officer_confirmed: bool = False,
    inventory_path: str | None = None,
    suppliers_path: str | None = None,
    quotations_path: str | None = None,
    register_path: str | None = None,
    requisition_store: str | None = None,
    corpus_dir: str | None = None,
    tool_log: str | None = None,
    run_log: str | None = None,
    record_trace: bool = True,
    clock: Clock | None = None,
    contract: AgentContract | None = None,
    contract_path: str | None = None,
    checkpoint_dir: str | None = None,
    fresh: bool = False,
    memory_path: str | None = None,
) -> AgentResult:
    # The contract is the floor: its limits apply unless this run was given a
    # flag or the machine sets an environment variable. A missing or malformed
    # contract stops the run, because an unbounded loop is the thing the
    # contract exists to prevent. The module defaults remain only as the shape
    # of the values, never as a silent fallback.
    active_contract = contract if contract is not None else load_contract(
        contract_path or DEFAULT_CONTRACT_PATH
    )
    limit = max_iterations if max_iterations is not None else _env_int(
        "AGENT_MAX_ITERATIONS", active_contract.iterations_per_item
    )
    budget = timeout_s if timeout_s is not None else _env_float(
        "AGENT_TIMEOUT_SECONDS", active_contract.wall_clock_seconds
    )
    started = time.perf_counter()
    state = AgentState(
        review_date=review_date,
        sku=sku,
        officer_username=officer_username,
        caller_role=caller_role,
        confirm_comparison=confirm_comparison,
        confirm_draft=confirm_draft,
        exchange_rate_ugx_per_usd=exchange_rate_ugx_per_usd,
        exchange_rate_effective_date=exchange_rate_effective_date,
        contract=active_contract,
    )
    active_planner = planner or DeterministicPlanner(
        quotations_path=quotations_path,
        register_path=register_path,
    )
    state.run_id = run_id_for(review_date, sku, officer_username)
    sources = dict(
        inventory_path=inventory_path,
        suppliers_path=suppliers_path,
        quotations_path=quotations_path,
        register_path=register_path,
    )
    run = _Run(
        store=CheckpointStore(checkpoint_dir) if checkpoint_dir else None,
        memory=MemoryStore(memory_path) if memory_path else None,
        run_log=run_log,
        record_trace=record_trace,
        clock=clock,
    )

    def finish(reason: str, detail: str) -> AgentResult:
        return _finish(state, reason, detail, run=run)

    if caller_role == ROLE_MANAGER:
        run.store = None  # no run starts, so nothing is saved
        return finish(
            STOP_UNAUTHORIZED,
            "PROCUREMENT_MANAGER does not operate the agent loop. "
            "Approval is a screen action, not a tool (POL-004-C03).",
        )

    if run.store is not None:
        if fresh:
            run.store.discard(state.run_id)
        saved = run.store.load(state.run_id)
        if saved is not None:
            state.resumed = restore(state, saved, current_sources(**sources))
            _adopt_exchange_rate(state, saved)
            _drop_comparison_if_rate_changed(state)
            if state.draft is not None:
                # The requisition already exists. Running again must not
                # compile a second one for the same review.
                run.completed_earlier = True
                return finish(
                    STOP_COMPLETED,
                    f"Already completed in an earlier run: {state.draft.get('requisition_id')} "
                    "is in DRAFT. No tool was called. Use --fresh to start a new run.",
                )
        # A gate passed in an earlier invocation stays passed for the same
        # comparison; restore() drops it if the comparison is recomputed.
        if "comparison" in state.confirmations:
            state.confirm_comparison = True
        if "draft" in state.confirmations:
            state.confirm_draft = True

    while state.iterations < limit:
        if time.perf_counter() - started > budget:
            return finish(STOP_TIMEOUT, f"Stopped after {budget:.0f}s (AGENT_TIMEOUT_SECONDS).")
        if state.step == STEP_DRAFT and state.comparison is not None:
            _record_confirmations(state, run)
        proposal = active_planner.propose(state)
        if proposal.kind == "stop":
            return finish(proposal.stop_reason or STOP_COMPLETED, proposal.detail or "")

        state.iterations += 1
        envelope = invoke(
            proposal.tool or "",
            proposal.payload or {},
            caller_role=caller_role,
            allowed_tools=state.current_allow_list(),
            officer_confirmed=officer_confirmed or state.confirm_draft,
            inventory_path=inventory_path,
            suppliers_path=suppliers_path,
            quotations_path=quotations_path,
            register_path=register_path,
            requisition_store=requisition_store,
            corpus_dir=corpus_dir,
            run_log=tool_log,
            record_trace=record_trace,
            clock=clock,
        )
        state.calls.append(envelope)
        status = envelope.get("status")
        data = envelope.get("data")

        if status == STATUS_UNAUTHORIZED:
            return finish(STOP_UNAUTHORIZED, _error_detail(envelope))
        if status in {STATUS_UNAVAILABLE, STATUS_FAILED}:
            return finish(STOP_FAILED, _error_detail(envelope))
        if status not in {STATUS_OK, STATUS_NO_RESULT}:
            # The contract classes a missing rate as NEEDS_HUMAN, not a refusal.
            # The compare step is not advanced, so the next run repeats it.
            if _error_code(envelope) == CODE_EXCHANGE_RATE_REQUIRED:
                return finish(
                    STOP_AWAITING_HUMAN,
                    _error_detail(envelope)
                    + " Re-run with --exchange-rate once the officer discloses one.",
                )
            return finish(STOP_REFUSED, _error_detail(envelope))

        completed_step = state.step
        if state.step == STEP_SCAN:
            state.reorder = data
            if not data or data.get("no_reorder_required"):
                return finish(
                    STOP_NO_REORDER,
                    "Nothing is at or below its reorder point. Requirement 1.5 ends the review.",
                )
            state.advance()
        elif state.step == STEP_ELIGIBILITY:
            state.eligibility = data
            state.advance()
        elif state.step == STEP_COMPARE:
            state.comparison = data
            state.advance()
        elif state.step == STEP_DRAFT:
            state.draft = data
            _note_sources(state, completed_step, sources, run)
            return finish(
                STOP_COMPLETED,
                "Requisition compiled in DRAFT. Further status changes are human actions.",
            )
        _note_sources(state, completed_step, sources, run)
        _save(state, run)

    return finish(
        STOP_MAX_ITERATIONS,
        f"Reached the iteration cap ({limit}). No further tool call was made.",
    )


@dataclass
class _Run:
    """Where this run's checkpoint, memory and trace go."""

    store: CheckpointStore | None
    memory: MemoryStore | None
    run_log: str | None
    record_trace: bool
    clock: Clock | None
    completed_earlier: bool = False

    def now(self) -> datetime:
        return self.clock() if self.clock is not None else datetime.now(timezone.utc)

    def stamp(self) -> str:
        return self.now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _note_sources(state: AgentState, step: str, sources: dict[str, Any], run: _Run) -> None:
    """Record which data a step's result came from, so a resume can check it."""
    if run.store is None:
        return
    now = current_sources(**sources)
    state.step_sources[step] = {name: now.get(name) for name in STEP_SOURCES[step]}


def _record_confirmations(state: AgentState, run: _Run) -> None:
    for gate, given in (("comparison", state.confirm_comparison), ("draft", state.confirm_draft)):
        if given and gate not in state.confirmations:
            state.confirmations[gate] = {"by": state.officer_username, "at": run.stamp()}


def _save(state: AgentState, run: _Run) -> None:
    if run.store is not None and state.run_id:
        run.store.save(state, saved_at=run.stamp())


def _finish(state: AgentState, reason: str, detail: str, *, run: _Run) -> AgentResult:
    state.stop_reason = reason
    state.stop_detail = detail
    result = AgentResult(
        stop_reason=reason,
        stop_detail=detail,
        iterations=state.iterations,
        state=state,
        calls=list(state.calls),
    )
    if run.memory is not None:
        result.memory = _advise(state, run.memory)
        if reason == STOP_COMPLETED and state.draft is not None and not run.completed_earlier:
            _remember_outcome(state, run.memory)
    # State is kept on every stop, including failures, so a retry resumes
    # (Agent Task Contract section 5, TERMINAL with state kept).
    _save(state, run)
    if run.record_trace:
        record = result.to_dict()
        record["called_at"] = run.stamp()
        AgentLog(run.run_log or DEFAULT_AGENT_LOG).append(record)
    return result


def _supplier_ids(state: AgentState) -> list[str]:
    ids: list[str] = []
    for row in (state.eligibility or {}).get("results") or []:
        supplier_id = row.get("supplier_id")
        if isinstance(supplier_id, str) and supplier_id not in ids:
            ids.append(supplier_id)
    return ids


def _advise(state: AgentState, memory: MemoryStore) -> dict[str, Any]:
    """Read memory for the officer. Runs after every decision is already made."""
    records = memory.relevant(
        supplier_ids=_supplier_ids(state),
        sku=state.sku or (state.flagged_item() or {}).get("sku"),
        as_of=state.review_date,
    )
    return advisory_block(records, store_path=str(memory.path))


def _remember_outcome(state: AgentState, memory: MemoryStore) -> None:
    comparison = state.comparison or {}
    ranked = comparison.get("ranked") or []
    top = ranked[0] if ranked else {}
    requirement = comparison.get("quotation_requirement") or {}
    item = state.flagged_item() or {}
    try:
        memory.record_outcome(
            role=state.caller_role,
            run_id=state.run_id or "",
            sku=item.get("sku") or state.sku or "",
            review_date=state.review_date,
            requisition_id=(state.draft or {}).get("requisition_id"),
            supplier_id=top.get("supplier_id"),
            supplier_name=top.get("supplier_name"),
            quotation_id=top.get("quotation_id"),
            landed_cost_ugx=top.get("landed_cost_ugx"),
            exception_required=bool(requirement.get("exception_required")),
            excluded_suppliers=[
                row.get("supplier_id") for row in comparison.get("excluded") or []
                if row.get("supplier_id")
            ],
        )
    except MemoryRefused:
        # Memory is advisory; failing to record it never fails the run.
        pass


def _adopt_exchange_rate(state: AgentState, checkpoint: dict[str, Any]) -> None:
    """Keep a rate the officer already disclosed, unless this run supplies one."""
    if state.exchange_rate_ugx_per_usd is None and checkpoint.get("exchange_rate_ugx_per_usd") is not None:
        state.exchange_rate_ugx_per_usd = checkpoint["exchange_rate_ugx_per_usd"]
    if not state.exchange_rate_effective_date and checkpoint.get("exchange_rate_effective_date"):
        state.exchange_rate_effective_date = checkpoint["exchange_rate_effective_date"]


def _drop_comparison_if_rate_changed(state: AgentState) -> None:
    """A saved comparison belongs to the rate it was computed with."""
    comparison = state.comparison
    if comparison is None or not _rate_changed(
        comparison,
        state.exchange_rate_ugx_per_usd,
        state.exchange_rate_effective_date,
    ):
        return
    state.comparison = None
    state.draft = None
    state.step_sources.pop(STEP_COMPARE, None)
    state.step_sources.pop(STEP_DRAFT, None)
    state.confirmations.pop("comparison", None)
    state.confirmations.pop("draft", None)
    state.step = STEP_COMPARE
    if state.resumed is not None:
        kept = [
            step for step in (state.resumed.get("kept_steps") or [])
            if step not in {STEP_COMPARE, STEP_DRAFT}
        ]
        state.resumed["kept_steps"] = kept
        state.resumed["restored"] = bool(kept)
        state.resumed["recomputed_from"] = STEP_COMPARE
        state.resumed["changed_sources"] = ["exchange_rate"]


def _rate_changed(comparison: dict[str, Any], rate: float | None, rate_date: str | None) -> bool:
    exchange = comparison.get("exchange_rate") or None
    saved = None if not exchange else exchange.get("ugx_per_usd")
    if (saved is None) != (rate is None):
        return True
    if saved is not None and rate is not None and float(saved) != float(rate):
        return True
    if rate_date and exchange and exchange.get("effective_date") != rate_date:
        return True
    return False


def _error_code(envelope: dict[str, Any]) -> str | None:
    errors = envelope.get("errors") or []
    if not errors:
        return None
    return errors[0].get("code")


def _error_detail(envelope: dict[str, Any]) -> str:
    errors = envelope.get("errors") or []
    if not errors:
        return str(envelope.get("status"))
    first = errors[0]
    return f"{first.get('code')}: {first.get('detail')}"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 1 else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default
