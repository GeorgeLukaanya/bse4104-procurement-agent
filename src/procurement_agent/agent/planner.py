"""Choose the next tool call. The planner proposes; dispatch executes.

The default planner is deterministic so the suite spends no quota. A
scripted planner is injectable for tests that need a malicious or
off-allow-list proposal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..tools.data import load_quotations
from .state import AgentState
from .steps import (
    STEP_COMPARE,
    STEP_DRAFT,
    STEP_ELIGIBILITY,
    STEP_SCAN,
    STOP_AWAITING_HUMAN,
    STOP_COMPLETED,
    STOP_FAILED,
    STOP_NO_REORDER,
)


@dataclass(frozen=True)
class Proposal:
    kind: str  # "call" or "stop"
    tool: str | None = None
    payload: dict[str, Any] | None = None
    stop_reason: str | None = None
    detail: str | None = None


class Planner(Protocol):
    def propose(self, state: AgentState) -> Proposal: ...


class DeterministicPlanner:
    """Charter order: scan → eligibility → compare → draft (propose or write)."""

    def __init__(
        self,
        *,
        quotations_path: str | None = None,
        register_path: str | None = None,
    ) -> None:
        self._quotations_path = quotations_path
        self._register_path = register_path

    def propose(self, state: AgentState) -> Proposal:
        if state.step == STEP_SCAN:
            payload: dict[str, Any] = {"review_date": state.review_date}
            if state.sku:
                payload["skus"] = [state.sku]
            return Proposal(kind="call", tool="check_reorder_need", payload=payload)
        if state.step == STEP_ELIGIBILITY:
            item = state.flagged_item()
            if item is None:
                return Proposal(
                    kind="stop",
                    stop_reason=STOP_NO_REORDER,
                    detail="Nothing is at or below its reorder point. Requirement 1.5 ends the review.",
                )
            supplier_ids = self._supplier_ids_for(item["sku"])
            if not supplier_ids:
                return Proposal(
                    kind="stop",
                    stop_reason=STOP_FAILED,
                    detail=f"No held quotations name {item['sku']}.",
                )
            return Proposal(
                kind="call",
                tool="check_supplier_eligibility",
                payload={
                    "category": item["category"],
                    "as_of_date": state.review_date,
                    "supplier_ids": supplier_ids,
                },
            )
        if state.step == STEP_COMPARE:
            item = state.flagged_item()
            if item is None:
                return Proposal(kind="stop", stop_reason=STOP_FAILED, detail="No flagged SKU to compare.")
            return Proposal(
                kind="call",
                tool="compare_quotations",
                payload={
                    "sku": item["sku"],
                    "reorder_quantity": item["reorder_quantity"],
                    "comparison_date": state.review_date,
                },
            )
        if state.step == STEP_DRAFT:
            if not state.confirm_comparison:
                return Proposal(
                    kind="stop",
                    stop_reason=STOP_AWAITING_HUMAN,
                    detail=(
                        "Landed-cost comparison is on the table. The officer must "
                        "confirm it before a requisition is compiled (Requirement 7.1 / gate 2)."
                    ),
                )
            if not state.confirm_draft:
                return Proposal(
                    kind="stop",
                    stop_reason=STOP_AWAITING_HUMAN,
                    detail=(
                        "A requisition draft is ready to compile. The officer must "
                        "confirm it before create_requisition_draft runs (Requirement 9.1)."
                    ),
                )
            return Proposal(
                kind="call",
                tool="create_requisition_draft",
                payload=_draft_payload(state),
            )
        return Proposal(kind="stop", stop_reason=STOP_COMPLETED, detail="No further catalogue step.")

    def _supplier_ids_for(self, sku: str) -> list[str]:
        try:
            quotations, _ = load_quotations(self._quotations_path, self._register_path)
        except Exception:
            return []
        ids: list[str] = []
        for row in quotations:
            if row.get("sku") != sku:
                continue
            supplier_id = row.get("supplier_id")
            if isinstance(supplier_id, str) and supplier_id not in ids:
                ids.append(supplier_id)
        return ids


class ScriptedPlanner:
    """Replay a fixed list of proposals. Used by tests."""

    def __init__(self, proposals: list[Proposal]) -> None:
        self._proposals = list(proposals)

    def propose(self, state: AgentState) -> Proposal:
        if not self._proposals:
            return Proposal(kind="stop", stop_reason=STOP_COMPLETED, detail="script exhausted")
        return self._proposals.pop(0)


def _draft_payload(state: AgentState) -> dict[str, Any]:
    item = state.flagged_item() or {}
    comparison = state.comparison or {}
    ranked = comparison.get("ranked") or []
    excluded = comparison.get("excluded") or []
    top = ranked[0] if ranked else {}
    issues = []
    for row in excluded:
        reasons = ", ".join(row.get("reasons") or [])
        issues.append(
            f"{row.get('quotation_id')} ({row.get('supplier_name')}): {reasons}."
        )
    requirement = comparison.get("quotation_requirement") or {}
    clause = requirement.get("clause") or "POL-001-C02"
    sku = item.get("sku") or state.sku
    qty = item.get("reorder_quantity")
    supplier = top.get("supplier_name") or "no eligible supplier"
    quote = top.get("quotation_id")
    extra = ""
    if requirement.get("exception_required"):
        extra = (
            f" {clause} is not satisfied "
            f"({requirement.get('eligible_count')} eligible of "
            f"{requirement.get('required_count')} required), so an exception "
            "would be required before the requisition proceeds."
        )
    justification = (
        f"{sku} is at or below its reorder point. "
        f"After eligibility exclusions, the lowest landed cost is {supplier}"
        f"{f' ({quote})' if quote else ''}.{extra}"
    )
    return {
        "review_date": state.review_date,
        "officer_username": state.officer_username,
        "items": [
            {
                "sku": sku,
                "reorder_quantity": qty,
                "comparison_reference": f"CMP-{state.review_date.replace('-', '')}-{sku}",
                "recommended_quotation_id": quote,
                "unresolved_issues": issues,
            }
        ],
        "policy_clauses": ["POL-001-C02", "POL-002-C04", "POL-003-C03"],
        "justification": justification,
    }
