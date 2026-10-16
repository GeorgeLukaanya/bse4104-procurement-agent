"""Record what each guardrail does when it is pushed, as evidence.

    python tools/capture_guardrails.py                 # print
    python tools/capture_guardrails.py --out FILE      # write the transcript

Every check here provokes a refusal and prints what came back. Nothing is
asserted; the transcript is the evidence and `docs/evaluation/guardrails.md`
reads it. The scenario suite (`tools/run_scenarios.py`) decides pass or fail.

No API key, no network and no model: every guardrail below is deterministic,
which is the point of them.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from procurement_agent import guards  # noqa: E402
from procurement_agent.agent import cli as agent_cli  # noqa: E402
from procurement_agent.tools.dispatch import invoke  # noqa: E402

DRAFT_REQUEST = {
    "review_date": "2026-09-25",
    "officer_username": "a.nakato",
    "items": [{"sku": "AH-CM-001", "reorder_quantity": 120, "comparison_reference": "QT-002"}],
    "justification": "Sole eligible supplier for cement; POL-001-C04 exception recorded.",
}


def _envelope(label: str, result: dict) -> str:
    errors = "; ".join(f"{e['code']}: {e['detail']}" for e in result.get("errors") or []) or "none"
    written = "none" if not result.get("data") else result["data"].get("requisition_id", "(data)")
    return f"{label}\n  status : {result['status']}\n  errors : {errors}\n  written: {written}\n"


def authorization(store: Path) -> str:
    """Who may call the one tool that writes."""
    out = []
    out.append(_envelope(
        "A. PROCUREMENT_MANAGER calls the write tool",
        invoke("create_requisition_draft", DRAFT_REQUEST, caller_role="PROCUREMENT_MANAGER",
               record_trace=False, requisition_store=str(store))))
    out.append(_envelope(
        "B. AGENT calls it without the officer's confirmation",
        invoke("create_requisition_draft", DRAFT_REQUEST, caller_role="AGENT",
               record_trace=False, requisition_store=str(store))))
    approved = {**DRAFT_REQUEST, "status": "APPROVED"}
    out.append(_envelope(
        "C. AGENT, confirmed, asks for status APPROVED",
        invoke("create_requisition_draft", approved, caller_role="AGENT", officer_confirmed=True,
               record_trace=False, requisition_store=str(store))))
    out.append(_envelope(
        "D. PROCUREMENT_OFFICER, confirmed, valid request",
        invoke("create_requisition_draft", DRAFT_REQUEST, caller_role="PROCUREMENT_OFFICER",
               officer_confirmed=True, record_trace=False, requisition_store=str(store))))
    return "\n".join(out)


def allow_list(store: Path) -> str:
    """The write tool is on the catalogue but not on this step's allow-list."""
    out = [_envelope(
        "E. write tool proposed while the loop is on the scan step",
        invoke("create_requisition_draft", DRAFT_REQUEST, caller_role="AGENT",
               allowed_tools=("check_reorder_need",), officer_confirmed=True,
               record_trace=False, requisition_store=str(store)))]
    out.append(_envelope(
        "F. a capability the catalogue forbids outright",
        invoke("issue_purchase_order", {}, caller_role="PROCUREMENT_OFFICER", record_trace=False)))
    return "\n".join(out)


def output_guard() -> str:
    """Requirement 14.2: a prohibited claim is suppressed before anyone sees it."""
    sentence = "The supplier has been approved and the contract is awarded."
    findings = guards.scan({"summary": sentence})
    found = ", ".join(f"{f.category} at {f.field_path}" for f in findings) or "none"
    return (f"G. output guard on a drafted sentence\n  input  : {sentence}\n"
            f"  caught : {found}\n")


def _run_agent(workspace: Path, *extra: str) -> str:
    args = [
        "--review-date", "2026-09-25", "--sku", "AH-CM-001", "--no-env-file",
        "--state-dir", str(workspace / "state"),
        "--run-log", str(workspace / "agent.jsonl"),
        "--tool-log", str(workspace / "tools.jsonl"),
        "--store", str(workspace / "requisitions.jsonl"),
        "--quotations", str(workspace / "quotations.json"),
        "--register", str(workspace / "register.csv"),
        *extra,
    ]
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        agent_cli.main(args)
    return buffer.getvalue()


def _keep(report: str, *prefixes: str) -> str:
    wanted = [line for line in report.splitlines()
              if line.startswith(prefixes) or line.startswith("  - ")]
    return "\n".join(f"  {line}" for line in wanted)


def loop_limits(workspace: Path) -> str:
    """Caps and gates, through the real command."""
    out = ["H. iteration cap set to 1",
           _keep(_run_agent(workspace, "--max-iterations", "1"), "stop:", "detail:", "iterations:"),
           "",
           "I. default run reaches the comparison and stops for the officer",
           _keep(_run_agent(workspace), "stop:", "detail:", "iterations:"),
           "",
           "J. same review run again: completed steps are not repeated",
           _keep(_run_agent(workspace), "stop:", "iterations:", "resumed:", "calls:")]
    return "\n".join(out) + "\n"


def tampered_source(workspace: Path) -> str:
    """An unreviewed edit to a registered data file is refused outright."""
    quotations = workspace / "quotations.json"
    payload = json.loads(quotations.read_text(encoding="utf-8"))
    row = next(r for r in payload["quotations"] if r["quotation_id"] == "QT-002")
    row["items"][0]["unit_price"] += 50_000
    quotations.write_text(json.dumps(payload, indent=2), encoding="utf-8", newline="\n")
    return ("K. the quotations file is edited, the register is not\n"
            + _keep(_run_agent(workspace), "stop:", "detail:", "calls:") + "\n")


def reviewed_change(workspace: Path) -> str:
    """A reviewed change re-runs only the steps that read the changed file."""
    quotations = workspace / "quotations.json"
    register = workspace / "register.csv"
    text = quotations.read_text(encoding="utf-8").replace("\r\n", "\n")
    rows = list(csv.DictReader(register.open(encoding="utf-8", newline="")))
    for row in rows:
        if row["source_id"] == "DAT-003":
            row["checksum_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    with register.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return ("L. the same change, now registered as reviewed\n"
            + _keep(_run_agent(workspace), "stop:", "iterations:", "resumed:", "calls:") + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record guardrail behaviour as evidence.")
    parser.add_argument("--out", default=None, help="write the transcript to this file")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory() as temporary:
        workspace = Path(temporary)
        shutil.copy(ROOT / "knowledge" / "data" / "quotations.json", workspace / "quotations.json")
        shutil.copy(ROOT / "knowledge" / "source-register.csv", workspace / "register.csv")
        store = workspace / "scratch-requisitions.jsonl"

        sections = [
            f"Guardrail evidence, recorded {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
            "No API key, no network, no model. Every guardrail below is deterministic.",
            "",
            "--- authorization -------------------------------------------------",
            authorization(store),
            "--- tool allow-list -----------------------------------------------",
            allow_list(store),
            "--- output guard --------------------------------------------------",
            output_guard(),
            "--- loop limits and gates -----------------------------------------",
            loop_limits(workspace),
            "--- source integrity and invalidation ------------------------------",
            tampered_source(workspace),
            reviewed_change(workspace),
        ]
    # The scratch directory is a different random path on every machine and on
    # every run. Redacted so the committed transcript stays comparable.
    transcript = "\n".join(sections).replace(str(workspace), "<workspace>")

    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(transcript, encoding="utf-8", newline="\n")
        print(f"wrote {path}")
    else:
        print(transcript)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
