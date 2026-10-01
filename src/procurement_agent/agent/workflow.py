"""Run the bounded weekly-reorder loop to a stop reason."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from ..tools.contract import (
    ROLE_MANAGER,
    ROLE_OFFICER,
    STATUS_FAILED,
    STATUS_NO_RESULT,
    STATUS_OK,
    STATUS_UNAUTHORIZED,
    STATUS_UNAVAILABLE,
)
from ..tools.dispatch import invoke
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": "AGENT",
            "stop_reason": self.stop_reason,
            "stop_detail": self.stop_detail,
            "iterations": self.iterations,
            "step": self.state.step,
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
        }


def run_workflow(
    *,
    review_date: str,
    sku: str | None = None,
    officer_username: str = "a.nakato",
    caller_role: str = ROLE_OFFICER,
    confirm_comparison: bool = False,
    confirm_draft: bool = False,
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
        contract=active_contract,
    )
    active_planner = planner or DeterministicPlanner(
        quotations_path=quotations_path,
        register_path=register_path,
    )

    if caller_role == ROLE_MANAGER:
        return _finish(
            state,
            STOP_UNAUTHORIZED,
            "PROCUREMENT_MANAGER does not operate the agent loop. "
            "Approval is a screen action, not a tool (POL-004-C03).",
            run_log=run_log,
            record_trace=record_trace,
            clock=clock,
        )

    while state.iterations < limit:
        if time.perf_counter() - started > budget:
            return _finish(
                state,
                STOP_TIMEOUT,
                f"Stopped after {budget:.0f}s (AGENT_TIMEOUT_SECONDS).",
                run_log=run_log,
                record_trace=record_trace,
                clock=clock,
            )
        proposal = active_planner.propose(state)
        if proposal.kind == "stop":
            return _finish(
                state,
                proposal.stop_reason or STOP_COMPLETED,
                proposal.detail or "",
                run_log=run_log,
                record_trace=record_trace,
                clock=clock,
            )

        state.iterations += 1
        envelope = invoke(
            proposal.tool or "",
            proposal.payload or {},
            caller_role=caller_role,
            allowed_tools=state.current_allow_list(),
            officer_confirmed=officer_confirmed or confirm_draft,
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
            return _finish(
                state,
                STOP_UNAUTHORIZED,
                _error_detail(envelope),
                run_log=run_log,
                record_trace=record_trace,
                clock=clock,
            )
        if status in {STATUS_UNAVAILABLE, STATUS_FAILED}:
            return _finish(
                state,
                STOP_FAILED,
                _error_detail(envelope),
                run_log=run_log,
                record_trace=record_trace,
                clock=clock,
            )
        if status not in {STATUS_OK, STATUS_NO_RESULT}:
            return _finish(
                state,
                STOP_REFUSED,
                _error_detail(envelope),
                run_log=run_log,
                record_trace=record_trace,
                clock=clock,
            )

        if state.step == STEP_SCAN:
            state.reorder = data
            if not data or data.get("no_reorder_required"):
                return _finish(
                    state,
                    STOP_NO_REORDER,
                    "Nothing is at or below its reorder point. Requirement 1.5 ends the review.",
                    run_log=run_log,
                    record_trace=record_trace,
                    clock=clock,
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
            return _finish(
                state,
                STOP_COMPLETED,
                "Requisition compiled in DRAFT. Further status changes are human actions.",
                run_log=run_log,
                record_trace=record_trace,
                clock=clock,
            )

    return _finish(
        state,
        STOP_MAX_ITERATIONS,
        f"Reached the iteration cap ({limit}). No further tool call was made.",
        run_log=run_log,
        record_trace=record_trace,
        clock=clock,
    )


def _finish(
    state: AgentState,
    reason: str,
    detail: str,
    *,
    run_log: str | None,
    record_trace: bool,
    clock: Clock | None,
) -> AgentResult:
    state.stop_reason = reason
    state.stop_detail = detail
    result = AgentResult(
        stop_reason=reason,
        stop_detail=detail,
        iterations=state.iterations,
        state=state,
        calls=list(state.calls),
    )
    if record_trace:
        record = result.to_dict()
        moment = clock() if clock is not None else datetime.now(timezone.utc)
        record["called_at"] = moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        AgentLog(run_log or DEFAULT_AGENT_LOG).append(record)
    return result


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
