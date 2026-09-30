"""Command-line entry point for the Week 5 bounded agent.

    python -m procurement_agent.agent.cli --review-date 2026-09-25 --sku AH-CM-001
    python -m procurement_agent.agent.cli --review-date 2026-09-25 --sku AH-CM-001 \\
        --confirm-comparison --confirm-draft

Direct orchestration. No framework. The default planner proposes catalogue
tools in charter order; dispatch executes them. Gemini is not called.

Exit 0 on completed / no_reorder_required.
Exit 1 on awaiting_human (the officer must confirm and re-run).
Exit 2 on max_iterations, timeout, failure, unauthorized, or usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Sequence

from ..dotenv import DEFAULT_ENV_FILE, load_env_file
from ..tools.contract import ROLE_OFFICER, ROLES
from .steps import (
    DEFAULT_MAX_ITERATIONS,
    STOP_AWAITING_HUMAN,
    STOP_COMPLETED,
    STOP_NO_REORDER,
)
from .trace import DEFAULT_AGENT_LOG
from .workflow import run_workflow

EXIT_OK = 0
EXIT_HANDOFF = 1
EXIT_STOP = 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return int(exc.code or EXIT_STOP)

    if not args.no_env_file:
        env_path = args.env_file or DEFAULT_ENV_FILE
        if os.path.exists(env_path):
            load_env_file(env_path)

    result = run_workflow(
        review_date=args.review_date,
        sku=args.sku,
        officer_username=args.officer,
        caller_role=args.role,
        confirm_comparison=args.confirm_comparison,
        confirm_draft=args.confirm_draft,
        max_iterations=args.max_iterations,
        timeout_s=args.timeout,
        officer_confirmed=args.confirm_draft,
        inventory_path=args.inventory,
        suppliers_path=args.suppliers,
        quotations_path=args.quotations,
        register_path=args.register,
        requisition_store=args.store,
        tool_log=args.tool_log,
        run_log=args.run_log,
        record_trace=not args.no_trace,
    )

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_report(result))

    if result.stop_reason in {STOP_COMPLETED, STOP_NO_REORDER}:
        return EXIT_OK
    if result.stop_reason == STOP_AWAITING_HUMAN:
        return EXIT_HANDOFF
    return EXIT_STOP


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="procurement-agent",
        description="Run the bounded weekly-reorder workflow. No model is used.",
    )
    parser.add_argument("--review-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--sku", help="Restrict the scan to one SKU (AH-XX-000).")
    parser.add_argument("--officer", default="a.nakato")
    parser.add_argument("--role", choices=ROLES, default=ROLE_OFFICER)
    parser.add_argument(
        "--confirm-comparison",
        action="store_true",
        help="Officer has confirmed the landed-cost table (gate 2).",
    )
    parser.add_argument(
        "--confirm-draft",
        action="store_true",
        help="Officer has confirmed compilation of a DRAFT requisition (gate 3).",
    )
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--inventory")
    parser.add_argument("--suppliers")
    parser.add_argument("--quotations")
    parser.add_argument("--register")
    parser.add_argument("--store")
    parser.add_argument("--run-log", default=str(DEFAULT_AGENT_LOG))
    parser.add_argument("--tool-log")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-trace", action="store_true")
    parser.add_argument("--env-file")
    parser.add_argument("--no-env-file", action="store_true")
    return parser


def _report(result) -> str:
    lines = [
        f"stop:       {result.stop_reason}",
        f"detail:     {result.stop_detail}",
        f"iterations: {result.iterations} / {os.environ.get('AGENT_MAX_ITERATIONS', DEFAULT_MAX_ITERATIONS)}",
        f"step:       {result.state.step}",
        f"role:       {result.state.caller_role}",
    ]
    if result.calls:
        lines.append("calls:")
        for call in result.calls:
            lines.append(f"  - {call.get('tool')} → {call.get('status')}")
    if result.stop_reason == STOP_AWAITING_HUMAN:
        lines.append(
            "Re-run with --confirm-comparison and/or --confirm-draft after the officer reviews."
        )
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
