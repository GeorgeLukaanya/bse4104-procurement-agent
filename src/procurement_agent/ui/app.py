"""Thin Streamlit view of the bounded weekly-reorder loop.

Buttons call ``run_workflow``. They do not call tools, do not approve, and
do not bypass the dispatcher. Confirmations are the same gates as the CLI
flags. There is still no login (KL-02).
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import streamlit as st

from procurement_agent.agent.contract import ContractError
from procurement_agent.agent.steps import STOP_AWAITING_HUMAN, STOP_COMPLETED, STOP_UNAUTHORIZED
from procurement_agent.agent.workflow import AgentResult, run_workflow
from procurement_agent.tools.contract import ROLE_MANAGER, ROLE_OFFICER
from procurement_agent.ui.view import (
    eligibility_rows,
    excluded_rows,
    load_sku_labels,
    memory_lines,
    ranked_rows,
    reorder_rows,
    repo_root,
    requirement_lines,
)

ROOT = repo_root()
os.chdir(ROOT)

DEMO_MEMORY = ROOT / "fixtures" / "memory" / "demo-memory.jsonl"
DEFAULT_REVIEW = date(2026, 9, 25)
CEMENT = "AH-CM-001"
OPERATOR_ROLES = (ROLE_OFFICER, ROLE_MANAGER)


def _ui_dir() -> Path:
    override = os.environ.get("PROCUREMENT_UI_DIR")
    return Path(override) if override else ROOT / "var" / "ui"

STOP_STYLE = {
    STOP_COMPLETED: "ok",
    STOP_AWAITING_HUMAN: "warning",
    STOP_UNAUTHORIZED: "error",
}


def _ui_paths() -> dict[str, str]:
    directory = _ui_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return {
        "checkpoint_dir": str(directory / "agent-state"),
        "requisition_store": str(directory / "requisitions.jsonl"),
        "tool_log": str(directory / "tool-runs.jsonl"),
        "run_log": str(directory / "agent-runs.jsonl"),
    }


def _memory_path(use_memory: bool) -> str | None:
    if not use_memory:
        return None
    dest = _ui_dir() / "memory.jsonl"
    if not dest.exists() and DEMO_MEMORY.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(DEMO_MEMORY.read_text(encoding="utf-8"), encoding="utf-8")
    return str(dest)


def _run(
    *,
    review_date: date,
    sku: str,
    role: str,
    officer: str,
    confirm_comparison: bool,
    confirm_draft: bool,
    exchange_rate: float | None,
    fresh: bool,
    use_memory: bool,
) -> AgentResult:
    paths = _ui_paths()
    return run_workflow(
        review_date=review_date.isoformat(),
        sku=sku,
        officer_username=officer.strip() or "a.nakato",
        caller_role=role,
        confirm_comparison=confirm_comparison,
        confirm_draft=confirm_draft,
        officer_confirmed=confirm_draft,
        exchange_rate_ugx_per_usd=exchange_rate,
        fresh=fresh,
        memory_path=_memory_path(use_memory),
        checkpoint_dir=paths["checkpoint_dir"],
        requisition_store=paths["requisition_store"],
        tool_log=paths["tool_log"],
        run_log=paths["run_log"],
    )


def _banner(result: AgentResult) -> None:
    kind = STOP_STYLE.get(result.stop_reason, "info")
    text = f"**{result.stop_reason}** — {result.stop_detail}"
    if kind == "ok":
        st.success(text)
    elif kind == "warning":
        st.warning(text)
    elif kind == "error":
        st.error(text)
    else:
        st.info(text)


def _show_result(result: AgentResult) -> None:
    _banner(result)
    left, mid, right = st.columns(3)
    left.metric("Iterations", f"{result.iterations}")
    mid.metric("Step", result.state.step)
    right.metric("Role", result.state.caller_role.replace("PROCUREMENT_", ""))
    if result.calls:
        st.caption("Calls this run: " + ", ".join(
            f"{call.get('tool')} → {call.get('status')}" for call in result.calls
        ))
    if result.state.resumed and result.state.resumed.get("restored"):
        kept = ", ".join(result.state.resumed.get("kept_steps") or [])
        st.caption(f"Resumed from checkpoint: {kept}")

    tabs = st.tabs(["Reorder", "Eligibility", "Comparison", "Draft", "Memory"])
    with tabs[0]:
        rows = reorder_rows(result.state.reorder)
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
        else:
            st.caption("No reorder result yet.")
    with tabs[1]:
        rows = eligibility_rows(result.state.eligibility)
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
        else:
            st.caption("No eligibility result yet.")
    with tabs[2]:
        ranked = ranked_rows(result.state.comparison)
        excluded = excluded_rows(result.state.comparison)
        for line in requirement_lines(result.state.comparison):
            st.write(line)
        if ranked:
            st.subheader("Ranked")
            st.dataframe(ranked, hide_index=True, width="stretch")
        if excluded:
            st.subheader("Excluded")
            st.dataframe(excluded, hide_index=True, width="stretch")
        if not ranked and not excluded:
            st.caption("No comparison yet.")
    with tabs[3]:
        draft = result.state.draft or {}
        if draft:
            st.write(f"**{draft.get('requisition_id')}**")
            st.write(f"Status: `{draft.get('status')}`")
            st.write(f"Created by: {draft.get('created_by')}")
            st.write(f"Human confirmation required: {draft.get('human_confirmation_required')}")
            st.write(
                "routed_to / approved_by / decision: "
                f"{draft.get('routed_to')} / {draft.get('approved_by')} / {draft.get('decision')}"
            )
            if draft.get("justification"):
                st.write(draft["justification"])
            issues = draft.get("unresolved_issues") or []
            if issues:
                st.write("Unresolved issues:")
                for issue in issues:
                    st.write(f"- {issue}")
        else:
            st.caption("No requisition written. Confirm the comparison and the draft to compile one.")
    with tabs[4]:
        notes = memory_lines(result.memory)
        if notes:
            st.caption("Advisory only. These notes did not change eligibility, cost or ranking.")
            for note in notes:
                st.write(f"- {note}")
        else:
            st.caption("No advisory memory on this run.")


def main() -> None:
    st.set_page_config(
        page_title="Weekly reorder review",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("Weekly reorder review")
    st.caption(
        "Operator view of the bounded agent. The model does not pick the next tool. "
        "Python computes every figure. The only write is a requisition in DRAFT."
    )
    st.info(
        "This is not a login and not the manager approval screen. "
        "Confirmations here are the same trusted flags as the command line (KL-02)."
    )

    skus = load_sku_labels()
    sku_ids = [sku for sku, _ in skus]
    default_index = sku_ids.index(CEMENT) if CEMENT in sku_ids else 0

    with st.sidebar:
        st.header("Review")
        review_date = st.date_input("Review date", value=DEFAULT_REVIEW)
        sku_label = st.selectbox(
            "SKU",
            options=skus,
            index=default_index,
            format_func=lambda item: item[1],
        )
        sku = sku_label[0]
        role = st.selectbox("Role", options=list(OPERATOR_ROLES), index=0)
        officer = st.text_input("Officer", value="a.nakato")
        rate_on = st.checkbox("Disclose UGX per 1 USD", value=False)
        exchange_rate = st.number_input("Exchange rate", min_value=1.0, value=3700.0, step=1.0) if rate_on else None
        use_memory = st.checkbox("Show advisory memory", value=True)
        st.caption("Memory is shown beside the result. It never decides.")

    result: AgentResult | None = st.session_state.get("result")

    run_col, confirm_col, fresh_col = st.columns(3)
    with run_col:
        run_clicked = st.button("Run review", type="primary", width="stretch")
    with confirm_col:
        confirm_clicked = st.button("Confirm table and compile DRAFT", width="stretch")
    with fresh_col:
        fresh_clicked = st.button("Start this review over", width="stretch")

    action: dict[str, Any] | None = None
    if run_clicked:
        action = {"confirm_comparison": False, "confirm_draft": False, "fresh": False}
    elif confirm_clicked:
        action = {"confirm_comparison": True, "confirm_draft": True, "fresh": False}
    elif fresh_clicked:
        action = {"confirm_comparison": False, "confirm_draft": False, "fresh": True}

    if action is not None:
        try:
            result = _run(
                review_date=review_date,
                sku=sku,
                role=role,
                officer=officer,
                confirm_comparison=action["confirm_comparison"],
                confirm_draft=action["confirm_draft"],
                exchange_rate=float(exchange_rate) if exchange_rate is not None else None,
                fresh=action["fresh"],
                use_memory=use_memory,
            )
            st.session_state["result"] = result
        except ContractError as exc:
            st.error(str(exc))
            result = None

    if role == ROLE_MANAGER:
        st.caption("The manager cannot operate the loop (POL-004-C03). Approval is a separate screen, which is not built.")

    if result is not None:
        _show_result(result)
    else:
        st.write("Choose a SKU and run the review. Cement (`AH-CM-001`) is the worked example from the report.")


if __name__ == "__main__":
    main()
