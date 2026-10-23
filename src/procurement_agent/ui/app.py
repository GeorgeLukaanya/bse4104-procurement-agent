"""Operator view of the bounded weekly-reorder loop.

One review queue, one item at a time, and the decision the officer owes in
the middle of the screen. Buttons call ``run_workflow``. They do not call
tools, do not approve, and do not bypass the dispatcher. Confirmations are the
same gates as the CLI flags. There is still no login (KL-02).

The exception reason the officer types is kept in the UI directory beside the
run, not inside the requisition: the draft already records that an exception
is required, and the reason travels with the review for the approver to read.
"""

from __future__ import annotations

import html
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st

from procurement_agent.agent.checkpoint import run_id_for
from procurement_agent.agent.contract import ContractError
from procurement_agent.agent.workflow import AgentResult, run_workflow
from procurement_agent.tools.contract import ROLE_MANAGER, ROLE_OFFICER
from procurement_agent.ui.view import (
    STATUS_CONFIRM,
    STATUS_DRAFT,
    STATUS_NO_OFFER,
    STATUS_NO_REORDER,
    STATUS_NOT_STARTED,
    STATUS_RATE,
    STATUS_REFUSED,
    STEP_LABELS,
    flagged_items,
    memory_lines,
    money,
    plain_exclusions,
    quotations_for,
    ranked_rows,
    repo_root,
    saved_status,
    status_for,
    step_progress,
)

ROOT = repo_root()
os.chdir(ROOT)

DEMO_MEMORY = ROOT / "fixtures" / "memory" / "demo-memory.jsonl"
DEFAULT_REVIEW = date(2026, 9, 25)
CEMENT = "AH-CM-001"
OPERATOR_ROLES = (ROLE_OFFICER, ROLE_MANAGER)
ROLE_NAMES = {ROLE_OFFICER: "Procurement Officer", ROLE_MANAGER: "Procurement Manager"}
STORE = "Atlantic Hardware, Nakawa Main Store"

UNIT_PLURAL = {"bag": "bags", "piece": "pcs", "pair": "pairs", "metre": "m", "kg": "kg"}

# Status colour per queue state: (text, background).
TONE = {
    STATUS_CONFIRM: ("#8A5A00", "#FFF4E0"),
    STATUS_RATE: ("#8A5A00", "#FFF4E0"),
    STATUS_NO_OFFER: ("#A33A3A", "#FBEAEA"),
    STATUS_REFUSED: ("#A33A3A", "#FBEAEA"),
    STATUS_DRAFT: ("#1E7A3E", "#E6F3EA"),
    STATUS_NO_REORDER: ("#1E7A3E", "#E6F3EA"),
    STATUS_NOT_STARTED: ("#5B6470", "#EEF1F4"),
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&display=swap');
body, .stApp, .stMarkdown, .stButton button, label, input, textarea, [data-testid="stCaptionContainer"] {
  font-family: 'Public Sans', system-ui, sans-serif;
}
.stApp { background: #F4F5F7; }
.block-container { padding-top: 1.2rem; max-width: 1480px; }
header[data-testid="stHeader"] { background: transparent; }
.op-head { display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:12px;
  background:#FFFFFF; border:1px solid #DDE1E6; border-radius:12px; padding:14px 20px; }
.op-head h1 { margin:0; font-size:20px; font-weight:700; color:#1B1F24; padding:0; }
.op-head .sub { font-size:14px; color:#5B6470; margin-top:2px; }
.op-chip { display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border-radius:999px;
  background:#EEF1F4; font-size:14px; color:#1B1F24; }
.op-card { background:#FFFFFF; border:1px solid #DDE1E6; border-radius:12px; padding:20px 22px; margin-bottom:16px; }
.op-card h2 { margin:0 0 4px; font-size:17px; font-weight:700; color:#1B1F24; padding:0; }
.op-card p { margin:6px 0 0; font-size:15px; line-height:1.5; color:#39414A; }
.op-wait { border:2px solid #E8A33A; }
.op-done { border:2px solid #1E7A3E; }
.op-bad { border:2px solid #A33A3A; }
.op-label { font-size:12px; color:#5B6470; }
.op-item { display:flex; flex-wrap:wrap; justify-content:space-between; gap:16px; }
.op-item h1 { margin:4px 0 0; font-size:26px; font-weight:700; padding:0; color:#1B1F24; }
.op-figs { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:24px; text-align:right; }
.op-fig { font-size:20px; font-weight:600; color:#1B1F24; }
.op-fig.accent { font-weight:700; color:#0B6B6B; }
.op-steps { list-style:none; margin:0 0 16px; padding:0; display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:8px; }
.op-steps li { display:flex; flex-direction:column; gap:6px; font-size:13px; font-weight:600; color:#1B1F24; }
.op-steps .bar { height:6px; border-radius:999px; background:#DDE1E6; }
.op-steps .done .bar { background:#1E7A3E; }
.op-steps .now .bar { background:#E8A33A; }
.op-steps .note { font-size:12px; font-weight:400; color:#5B6470; }
.op-grid { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:12px; margin-top:14px; }
.op-box { border-radius:10px; padding:14px 16px; background:#F7F8FA; }
.op-box.warn { background:#FFF4E0; }
.op-box .big { font-size:22px; font-weight:700; margin-top:4px; color:#1B1F24; }
.op-box .small { font-size:13px; color:#39414A; margin-top:4px; line-height:1.45; }
.op-pill { display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:600; }
.op-list { margin:8px 0 0; padding-left:20px; font-size:15px; line-height:1.55; color:#1B1F24; }
.op-why { display:flex; flex-direction:column; gap:8px; margin-top:8px; }
.op-why div { padding:10px 12px; border-radius:8px; background:#F7F8FA; font-size:14px; line-height:1.45; }
.op-code { font-size:12px; color:#5B6470; }
.op-dl { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:16px; margin-top:14px; }
.op-dl dd { margin:4px 0 0; font-size:15px; font-weight:600; color:#1B1F24; }
.op-path { list-style:none; margin:12px 0 0; padding:0; display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:8px; }
.op-path li { display:flex; flex-direction:column; gap:6px; font-size:13px; font-weight:600; }
.op-path .bar { height:6px; border-radius:999px; background:#DDE1E6; }
.op-path .done .bar { background:#1E7A3E; }
.op-path .note { font-size:12px; font-weight:400; color:#5B6470; }
.op-qhead { font-size:15px; font-weight:700; margin:4px 0 8px; color:#1B1F24; }
.op-qstatus { font-size:12px; font-weight:600; margin:-6px 0 10px 4px; }
div[class*="st-key-queue-"] button { justify-content:flex-start; text-align:left; background:#FFFFFF;
  border:1px solid #DDE1E6; border-radius:10px; min-height:52px; color:#1B1F24; }
div[class*="st-key-queue-"] button > div { justify-content:flex-start; }
div[class*="st-key-queue-"] button p { font-size:14px; text-align:left; }
div[class*="st-key-queue-"] button[kind="primary"] { background:#E6F2F2; border:2px solid #0B6B6B; color:#1B1F24; }
.stButton button { min-height:46px; border-radius:8px; font-weight:600; }
[data-testid="stExpander"] { background:#FFFFFF; border-radius:12px; }
</style>
"""


def _ui_dir() -> Path:
    override = os.environ.get("PROCUREMENT_UI_DIR")
    return Path(override) if override else ROOT / "var" / "ui"


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


def _reasons_path() -> Path:
    return _ui_dir() / "exception-reasons.jsonl"


def _save_reason(run_id: str, sku: str, officer: str, reason: str) -> None:
    path = _reasons_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "run_id": run_id,
        "sku": sku,
        "by": officer,
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reason": reason,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _saved_reason(run_id: str | None) -> str | None:
    if not run_id:
        return None
    found = None
    try:
        lines = _reasons_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if record.get("run_id") == run_id:
            found = record.get("reason")
    return found


def _run(
    *,
    review_date: date,
    sku: str,
    role: str,
    officer: str,
    confirm_comparison: bool = False,
    confirm_draft: bool = False,
    exchange_rate: float | None = None,
    rate_date: date | None = None,
    fresh: bool = False,
    use_memory: bool = True,
) -> AgentResult:
    paths = _ui_paths()
    return run_workflow(
        review_date=review_date.isoformat(),
        sku=sku,
        officer_username=officer,
        caller_role=role,
        confirm_comparison=confirm_comparison,
        confirm_draft=confirm_draft,
        officer_confirmed=confirm_draft,
        exchange_rate_ugx_per_usd=exchange_rate,
        exchange_rate_effective_date=rate_date.isoformat() if rate_date else None,
        fresh=fresh,
        memory_path=_memory_path(use_memory),
        checkpoint_dir=paths["checkpoint_dir"],
        requisition_store=paths["requisition_store"],
        tool_log=paths["tool_log"],
        run_log=paths["run_log"],
    )


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _qty(item: dict[str, Any]) -> str:
    unit = item.get("unit") or ""
    return f"{item['to_order']} {UNIT_PLURAL.get(unit, unit)}".strip()


def _pill(status: str) -> str:
    fg, bg = TONE.get(status, ("#5B6470", "#EEF1F4"))
    return f'<span class="op-pill" style="color:{fg};background:{bg}">{_e(status)}</span>'


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def _header(review_date: date, officer: str, role: str) -> None:
    _html(
        f"""<div class="op-head"><div><h1>Weekly reorder review</h1>
<div class="sub">{_e(STORE)} · review of {review_date.strftime('%-d %B %Y')}</div></div>
<div class="op-chip">&#128100; {_e(officer)} · {_e(ROLE_NAMES.get(role, role))}</div></div>"""
    )
    st.write("")


def _queue(items: list[dict[str, Any]], statuses: dict[str, str], selected: str | None) -> str | None:
    waiting = sum(1 for s in statuses.values() if s in (STATUS_CONFIRM, STATUS_RATE))
    _html(f'<div class="op-qhead">Flagged this week ({len(items)})</div>')
    if waiting:
        st.caption(f"{waiting} waiting on you")
    clicked = None
    for item in items:
        sku = item["sku"]
        status = statuses.get(sku, STATUS_NOT_STARTED)
        marker = "▸ " if sku == selected else ""
        with st.container(key=f"queue-{sku}"):
            if st.button(
                f"{marker}**{item['item_name']}**  ·  {_qty(item)}",
                key=f"open-{sku}",
                width="stretch",
                type="primary" if sku == selected else "secondary",
            ):
                clicked = sku
        fg, _ = TONE.get(status, ("#5B6470", ""))
        _html(f'<div class="op-qstatus" style="color:{fg}">● {_e(status)}</div>')
    return clicked


def _item_card(item: dict[str, Any]) -> None:
    _html(
        f"""<div class="op-card op-item"><div>
<div class="op-label">{_e(item['sku'])} · {_e(item['category'].capitalize())}</div>
<h1>{_e(item['item_name'])}</h1></div>
<div class="op-figs">
<div><div class="op-label">On hand</div><div class="op-fig">{item['current_stock']}</div></div>
<div><div class="op-label">Reorder point</div><div class="op-fig">{item['reorder_point']}</div></div>
<div><div class="op-label">To order</div><div class="op-fig accent">{_e(_qty(item))}</div></div>
</div></div>"""
    )


def _stepper(result: AgentResult | None) -> None:
    if result is None:
        done = [False] * len(STEP_LABELS)
    else:
        state = result.state
        done = step_progress(state.reorder, state.eligibility, state.comparison, state.confirmations, state.draft)
    current = next((i for i, flag in enumerate(done) if not flag), None)
    parts = []
    for index, label in enumerate(STEP_LABELS):
        if done[index]:
            css, note = "done", "Done"
        elif index == current and result is not None:
            css, note = "now", "Waiting on you" if result.stop_reason == "awaiting_human" else "Stopped here"
        else:
            css, note = "", "Not yet"
        parts.append(f'<li class="{css}"><span class="bar"></span>{_e(label)}<span class="note">{note}</span></li>')
    _html(f'<ol class="op-steps" aria-label="Progress">{"".join(parts)}</ol>')


def _decision(result: AgentResult, item: dict[str, Any], officer: str) -> dict[str, Any] | None:
    comparison = result.state.comparison or {}
    ranked = comparison.get("ranked") or []
    req = comparison.get("quotation_requirement") or {}
    exception = bool(req.get("exception_required"))
    first = ranked[0] if ranked else {}
    boxes = []
    if first:
        boxes.append(
            f"""<div class="op-box"><div class="op-label">Ranked first on landed cost</div>
<div class="big">{_e(money(first.get('landed_cost_ugx')))}</div>
<div class="small">{_e(first.get('supplier_name'))} ({_e(first.get('quotation_id'))}). {_e(_qty(item))} at
{_e(money(first.get('normalised_unit_cost_ugx')))} each, VAT {_e(money(first.get('vat_amount_ugx')))},
delivery {_e(money(first.get('delivery_cost_ugx')))}.</div></div>"""
        )
    if exception:
        boxes.append(
            f"""<div class="op-box warn"><div class="op-label">Policy exception needed</div>
<div class="big">{req.get('eligible_count')} of {req.get('required_count')} quotations eligible</div>
<div class="small">{_e(req.get('clause'))} asks for {req.get('required_count')} quotations in this value band.
Going ahead needs an exception (POL-001-C04). The draft records this; it does not block it.</div></div>"""
        )
    _html(
        f"""<div class="op-card op-wait"><h2>Your confirmation is needed</h2>
<p>The agent compared every eligible quotation and stopped before writing anything. Check the table below,
then confirm. Confirming records your name and the time and compiles a requisition in DRAFT.
Nothing is ordered, sent to a supplier or approved.</p>
<div class="op-grid">{''.join(boxes)}</div></div>"""
    )
    reason = ""
    if exception:
        reason = st.text_area(
            "Reason for the exception (required)",
            key=f"reason-{item['sku']}",
            placeholder="For example: the two Lakeview quotations are on hold until their supplier names are cleared.",
            help="Kept with this review for the approver. Press Ctrl+Enter or click away to save the text.",
        )
    ready = bool(reason.strip()) or not exception
    left, right = st.columns([3, 2])
    with left:
        confirm = st.button(
            "Confirm comparison and compile draft",
            key="confirm",
            type="primary",
            width="stretch",
            disabled=not ready,
        )
    with right:
        over = st.button("Start this item over", key="fresh", width="stretch")
    if exception and not ready:
        st.caption("Write the reason for the exception to enable Confirm.")
    st.caption(
        "To bring an excluded supplier back in, clear its name in the supplier register first. "
        "This screen does not change the register."
    )
    if confirm:
        return {"confirm": True, "reason": reason.strip()}
    if over:
        return {"fresh": True}
    return None


def _rate_panel(result: AgentResult, item: dict[str, Any], review_date: date) -> dict[str, Any] | None:
    held = quotations_for(item["sku"], review_date.isoformat())
    usd = [q for q in held if q["tone"] == "wait"]
    names = ", ".join(f"{q['quotation_id']} from {q['supplier_name']}" for q in usd) or "A quotation"
    _html(
        f"""<div class="op-card op-wait"><h2>{"One quotation is" if len(usd) < 2 else "Some quotations are"} in US dollars</h2>
<p>{_e(names)} is priced in USD. The comparison will not guess a rate (POL-003-C01). Enter the rate your
finance team uses, and the comparison runs again with it shown on every converted figure.</p></div>"""
    )
    with st.form("rate-form", border=False):
        left, right = st.columns(2)
        with left:
            rate = st.number_input("UGX per 1 USD", min_value=1.0, value=None, step=1.0, placeholder="Current rate")
        with right:
            effective = st.date_input("Rate effective date", value=review_date)
        submitted = st.form_submit_button("Use this rate and compare again", type="primary")
    tone = {"ok": "#1E7A3E", "wait": "#8A5A00", "bad": "#A33A3A"}
    rows = "".join(
        f"""<div style="display:flex;justify-content:space-between;gap:8px"><span><strong>{_e(q['quotation_id'])}</strong>
{_e(q['supplier_name'])}</span><span style="font-weight:600;color:{tone[q['tone']]}">{_e(q['state'])}</span></div>"""
        for q in held
    )
    _html(f'<div class="op-card"><h2>Quotations held for this item</h2><div class="op-why">{rows}</div></div>')
    if submitted:
        if not rate:
            st.error("Enter the rate before comparing again.")
            return None
        return {"rate": float(rate), "rate_date": effective}
    return None


def _draft_panel(result: AgentResult, item: dict[str, Any], next_item: dict[str, Any] | None) -> dict[str, Any] | None:
    draft = result.state.draft or {}
    comparison = result.state.comparison or {}
    ranked = comparison.get("ranked") or []
    first = ranked[0] if ranked else {}
    lines = []
    req = comparison.get("quotation_requirement") or {}
    reason = _saved_reason(result.state.run_id)
    if req.get("exception_required"):
        text = (
            f"Policy exception: only {req.get('eligible_count')} of {req.get('required_count')} required "
            f"quotations was eligible (POL-001-C04)"
        )
        lines.append(text + (f". Your reason: “{reason}”" if reason else ""))
    lines.extend(draft.get("unresolved_issues") or [])
    if draft.get("policy_clauses"):
        lines.append("Cited clauses: " + ", ".join(draft["policy_clauses"]))
    supplier = f"{first.get('supplier_name')} ({first.get('quotation_id')})" if first else "-"
    _html(
        f"""<div class="op-card op-done"><h2>Draft requisition {_e(draft.get('requisition_id'))} created</h2>
<p>It is saved as a draft. Nothing has been ordered, sent to a supplier or approved.</p>
<dl class="op-dl">
<div><dt class="op-label">Item</dt><dd>{_e(_qty(item))} of {_e(item['item_name'])}</dd></div>
<div><dt class="op-label">Supplier ranked first</dt><dd>{_e(supplier)}</dd></div>
<div><dt class="op-label">Landed cost</dt><dd>{_e(money(first.get('landed_cost_ugx')))}</dd></div>
<div><dt class="op-label">Status</dt><dd><span class="op-pill" style="background:#EEF1F4">{_e(draft.get('status'))}</span></dd></div>
</dl></div>
<div class="op-card"><h2>Travelling with the draft</h2>
<ul class="op-list">{''.join(f'<li>{_e(line)}</li>' for line in lines)}</ul></div>
<div class="op-card"><h2>What happens next</h2>
<p>Submitting the draft to the Procurement Manager for approval is a separate, human step and is not part of this release.</p>
<ol class="op-path">
<li class="done"><span class="bar"></span>Draft compiled<span class="note">Done, by {_e(draft.get('created_by'))}</span></li>
<li><span class="bar"></span>Submit for approval<span class="note">You, when ready</span></li>
<li><span class="bar"></span>Approve or reject<span class="note">Procurement Manager</span></li>
</ol></div>"""
    )
    left, right = st.columns(2)
    action = None
    with left:
        if next_item is not None and st.button(
            f"Next item: {next_item['item_name']}", key="next", type="primary", width="stretch"
        ):
            action = {"open": next_item["sku"]}
    with right:
        if st.button("Back to review queue", key="back", width="stretch"):
            action = {"open": None}
    return action


def _stopped_panel(result: AgentResult, status: str) -> dict[str, Any] | None:
    detail = result.stop_detail or ""
    if status == STATUS_NO_OFFER:
        title, body, css = (
            "No eligible offer for this item",
            "Every quotation held for this item was excluded, so no requisition can be compiled. "
            "Nothing was written. Ask for new quotations from approved suppliers, then start this item over.",
            "op-bad",
        )
    elif status == STATUS_REFUSED:
        title, body, css = "This role cannot run the review", detail, "op-bad"
    elif status == STATUS_NO_REORDER:
        title, body, css = "No reorder needed", detail, "op-done"
    else:
        title, body, css = "The review stopped", detail, "op-bad"
    _html(f'<div class="op-card {css}"><h2>{_e(title)}</h2><p>{_e(body)}</p></div>')
    if status != STATUS_REFUSED and st.button("Start this item over", key="fresh"):
        return {"fresh": True}
    return None


def _comparison(result: AgentResult) -> None:
    comparison = result.state.comparison
    if not comparison:
        return
    _html('<div class="op-card" style="margin-bottom:6px"><h2>Landed-cost comparison</h2>'
          '<p>Unit cost after unit conversion, plus VAT and delivery. Python computes every figure.</p></div>')
    ranked = ranked_rows(comparison)
    if ranked:
        st.dataframe(ranked, hide_index=True, width="stretch")
    excluded = plain_exclusions(comparison, result.state.eligibility)
    if excluded:
        rows = "".join(
            f"""<div><strong>{_e(row['quotation_id'])}</strong> {_e(row['supplier_name'])}<br>{_e(row['why'])}
<span class="op-code"> ({_e(', '.join(row['codes']))})</span></div>"""
            for row in excluded
        )
        _html(f'<div class="op-card"><h2>Not compared, and why</h2><div class="op-why">{rows}</div></div>')


def _side(result: AgentResult | None) -> None:
    notes = memory_lines(result.memory) if result is not None else []
    body = (
        "".join(f"<li>{_e(note)}</li>" for note in notes)
        if notes
        else "<li>No notes from earlier reviews for this item.</li>"
    )
    _html(
        f"""<div class="op-card"><h2>From earlier reviews</h2>
<p style="font-size:13px">Advisory only. These notes did not change eligibility, cost or ranking.</p>
<ul class="op-list" style="font-size:14px">{body}</ul></div>"""
    )
    if result is None:
        return
    with st.expander("What the agent did"):
        st.caption(f"Run `{result.state.run_id}` · {result.iterations} iterations this run")
        st.caption(f"Stopped with `{result.stop_reason}`: {result.stop_detail}")
        for call in result.calls:
            st.caption(f"{call.get('tool')} → {call.get('status')}")
        if result.state.resumed and result.state.resumed.get("restored"):
            kept = ", ".join(result.state.resumed.get("kept_steps") or [])
            st.caption(f"Resumed from the saved review: {kept}")


def main() -> None:
    st.set_page_config(page_title="Weekly reorder review", layout="wide", initial_sidebar_state="collapsed")
    _html(CSS)

    with st.sidebar:
        st.header("Session")
        review_date = st.date_input("Review date", value=DEFAULT_REVIEW)
        role = st.selectbox(
            "Role", options=list(OPERATOR_ROLES), index=0, format_func=lambda r: ROLE_NAMES.get(r, r)
        )
        officer = st.text_input("Officer", value="a.nakato").strip() or "a.nakato"
        use_memory = st.checkbox("Show notes from earlier reviews", value=True)
        st.caption(
            "There is no login (KL-02). Confirmations here are the same trusted flags as the command line. "
            "This is not the manager approval screen."
        )

    _header(review_date, officer, role)

    items = flagged_items()
    by_sku = {item["sku"]: item for item in items}
    if "sku" not in st.session_state:
        st.session_state["sku"] = CEMENT if CEMENT in by_sku else (items[0]["sku"] if items else None)
    results: dict[str, AgentResult] = st.session_state.setdefault("results", {})
    scope = f"{review_date.isoformat()}|{officer}|{role}"

    def held(sku: str) -> AgentResult | None:
        return results.get(f"{scope}|{sku}")

    def act(sku: str, **kwargs: Any) -> None:
        try:
            results[f"{scope}|{sku}"] = _run(
                review_date=review_date, sku=sku, role=role, officer=officer, use_memory=use_memory, **kwargs
            )
        except ContractError as exc:
            st.session_state["error"] = str(exc)

    checkpoint_dir = Path(_ui_paths()["checkpoint_dir"])
    statuses = {}
    for item in items:
        mine = held(item["sku"])
        statuses[item["sku"]] = (
            status_for(mine.stop_reason, mine.stop_detail)
            if mine is not None
            else saved_status(checkpoint_dir, review_date.isoformat(), item["sku"], officer)
        )

    queue_col, work_col, side_col = st.columns([1.15, 2.9, 1.25], gap="medium")

    with queue_col:
        opened = _queue(items, statuses, st.session_state["sku"])
    if opened is not None:
        st.session_state["sku"] = opened
        if statuses.get(opened) != STATUS_NOT_STARTED:
            act(opened)
        st.rerun()

    sku = st.session_state["sku"]
    result = held(sku) if sku else None

    with work_col:
        if st.session_state.get("error"):
            st.error(st.session_state.pop("error"))
        if sku is None or sku not in by_sku:
            done = sum(1 for s in statuses.values() if s == STATUS_DRAFT)
            _html(
                f"""<div class="op-card"><h2>Review queue</h2><p>{len(items)} items are at or below their reorder
point this week. {done} have a draft requisition. Choose an item on the left.</p></div>"""
            )
        else:
            item = by_sku[sku]
            _item_card(item)
            _stepper(result)
            action = None
            if result is None:
                _html(
                    f"""<div class="op-card"><h2>Ready to review</h2><p>The agent will check stock, check each
supplier against the approved list, and compare landed costs. It stops and asks you before it writes
anything. Run <code>{_e(run_id_for(review_date.isoformat(), sku, officer))}</code>.</p></div>"""
                )
                if st.button("Start review", key="start", type="primary"):
                    action = {}
            else:
                status = status_for(result.stop_reason, result.stop_detail)
                if role == ROLE_MANAGER or status == STATUS_REFUSED:
                    st.error(f"**{result.stop_reason}**: {result.stop_detail}")
                if status == STATUS_CONFIRM:
                    action = _decision(result, item, officer)
                elif status == STATUS_RATE:
                    action = _rate_panel(result, item, review_date)
                elif status == STATUS_DRAFT:
                    pending = [
                        other for other in items
                        if other["sku"] != sku and statuses.get(other["sku"]) not in (STATUS_DRAFT, STATUS_NO_REORDER)
                    ]
                    action = _draft_panel(result, item, pending[0] if pending else None)
                elif status != STATUS_REFUSED:
                    action = _stopped_panel(result, status)
                _comparison(result)

            if action is not None:
                if "open" in action:
                    st.session_state["sku"] = action["open"]
                    if action["open"] and statuses.get(action["open"]) != STATUS_NOT_STARTED:
                        act(action["open"])
                elif action.get("confirm"):
                    act(sku, confirm_comparison=True, confirm_draft=True)
                    if action.get("reason"):
                        _save_reason(run_id_for(review_date.isoformat(), sku, officer), sku, officer, action["reason"])
                elif action.get("fresh"):
                    act(sku, fresh=True)
                elif "rate" in action:
                    act(sku, exchange_rate=action["rate"], rate_date=action["rate_date"])
                else:
                    act(sku)
                st.rerun()

    with side_col:
        _side(result)


if __name__ == "__main__":
    main()
