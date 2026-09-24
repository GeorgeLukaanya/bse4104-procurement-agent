"""Command-line entry point for the Week 4 tools.

    python -m procurement_agent.tools.cli check_reorder_need \\
        --review-date 2026-09-25 --sku AH-CM-001 --sku AH-HT-012

    python -m procurement_agent.tools.cli check_supplier_eligibility \\
        --category "cement and masonry" --as-of 2026-09-25 \\
        --supplier-id SUP-002 --supplier-id SUP-006 --supplier-id SUP-007

    python -m procurement_agent.tools.cli compare_quotations \\
        --sku AH-CM-001 --quantity 120 --date 2026-09-25

    python -m procurement_agent.tools.cli create_requisition_draft --file draft.json

No model is called. The role is injected here (default PROCUREMENT_OFFICER);
it is never read from the JSON payload. Exit 0 on ok/no_result, 1 on
invalid/unauthorized/failed, 2 on unavailable or usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Sequence

from ..dotenv import DEFAULT_ENV_FILE, load_env_file
from .contract import ALL_TOOLS, ROLE_OFFICER, ROLES, STATUS_NO_RESULT, STATUS_OK, STATUS_UNAVAILABLE
from .dispatch import invoke
from .trace import DEFAULT_TOOL_LOG

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return int(exc.code or EXIT_USAGE)

    if not args.no_env_file:
        env_path = args.env_file or DEFAULT_ENV_FILE
        if os.path.exists(env_path):
            load_env_file(env_path)

    try:
        payload = _payload(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    result = invoke(
        args.tool,
        payload,
        caller_role=args.role,
        officer_confirmed=args.confirm,
        inventory_path=args.inventory or os.environ.get("INVENTORY_DATA_PATH"),
        suppliers_path=args.suppliers or os.environ.get("SUPPLIERS_DATA_PATH"),
        quotations_path=args.quotations or os.environ.get("QUOTATIONS_DATA_PATH"),
        register_path=args.register,
        requisition_store=args.store,
        run_log=args.run_log,
        record_trace=not args.no_trace,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(_report(result))

    status = result["status"]
    if status in {STATUS_OK, STATUS_NO_RESULT}:
        return EXIT_OK
    if status == STATUS_UNAVAILABLE:
        return EXIT_USAGE
    return EXIT_REFUSED


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="procurement-tools",
        description="Call one catalogue tool through the orchestration layer. No model is used.",
    )
    parser.add_argument("tool", choices=ALL_TOOLS)
    parser.add_argument(
        "--role",
        choices=ROLES,
        default=ROLE_OFFICER,
        help="Injected session role. Never taken from the payload. Default: PROCUREMENT_OFFICER.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Officer confirmation gate for create_requisition_draft when --role AGENT.",
    )
    parser.add_argument("--json", action="store_true", help="Print the envelope as JSON.")
    parser.add_argument("--file", help="JSON object of tool input. Overrides flag-built payloads.")
    parser.add_argument("--review-date")
    parser.add_argument("--sku", action="append", dest="skus")
    parser.add_argument("--location")
    parser.add_argument("--include-sufficient", action="store_true")
    parser.add_argument("--category")
    parser.add_argument("--as-of")
    parser.add_argument("--supplier-id", action="append", dest="supplier_ids")
    parser.add_argument("--supplier-name", action="append", dest="supplier_names")
    parser.add_argument("--quotation-id", action="append", dest="quotation_ids")
    parser.add_argument("--quantity", type=int)
    parser.add_argument("--date")
    parser.add_argument("--rate", type=float, dest="exchange_rate")
    parser.add_argument("--rate-date")
    parser.add_argument("--inventory")
    parser.add_argument("--suppliers")
    parser.add_argument("--quotations")
    parser.add_argument("--register")
    parser.add_argument("--store", help="Requisition JSONL store (default var/requisitions.jsonl).")
    parser.add_argument("--run-log", default=str(DEFAULT_TOOL_LOG))
    parser.add_argument("--no-trace", action="store_true")
    parser.add_argument("--env-file")
    parser.add_argument("--no-env-file", action="store_true")
    return parser


def _payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.file:
        with open(args.file, encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("input file must contain a JSON object")
        return payload

    tool = args.tool
    if tool == "check_reorder_need":
        if not args.review_date:
            raise ValueError("check_reorder_need needs --review-date (or --file)")
        payload: dict[str, Any] = {"review_date": args.review_date}
        if args.skus:
            payload["skus"] = args.skus
        if args.location is not None:
            payload["location"] = args.location
        if args.include_sufficient:
            payload["include_sufficient"] = True
        return payload
    if tool == "check_supplier_eligibility":
        if not args.category or not args.as_of:
            raise ValueError("check_supplier_eligibility needs --category and --as-of")
        payload = {"category": args.category, "as_of_date": args.as_of}
        if args.supplier_ids:
            payload["supplier_ids"] = args.supplier_ids
        if args.supplier_names:
            payload["supplier_names"] = args.supplier_names
        if args.quotation_ids:
            payload["quotation_ids"] = args.quotation_ids
        return payload
    if tool == "compare_quotations":
        sku = args.skus[0] if args.skus else None
        comparison_date = args.date or args.as_of or args.review_date
        if not sku or args.quantity is None or not comparison_date:
            raise ValueError("compare_quotations needs --sku, --quantity and --date")
        payload = {
            "sku": sku,
            "reorder_quantity": args.quantity,
            "comparison_date": comparison_date,
        }
        if args.quotation_ids:
            payload["quotation_ids"] = args.quotation_ids
        if args.exchange_rate is not None:
            payload["exchange_rate_ugx_per_usd"] = args.exchange_rate
        if args.rate_date:
            payload["exchange_rate_effective_date"] = args.rate_date
        return payload
    raise ValueError(
        "create_requisition_draft needs --file pointing at a JSON object "
        "(review_date, officer_username, items, justification)"
    )


def _report(result: dict[str, Any]) -> str:
    lines = [
        f"tool:   {result['tool']} v{result['tool_version']}",
        f"status: {result['status']}",
        f"role:   {result['trace']['caller_role']}",
        f"took:   {result['trace']['latency_ms']} ms",
        f"hash:   {result['trace']['data_fingerprint']}",
    ]
    if result["errors"]:
        lines.append("errors:")
        for item in result["errors"]:
            field = f" ({item['field']})" if item.get("field") else ""
            lines.append(f"  - {item['code']}{field}: {item['detail']}")
    data = result.get("data")
    if not data:
        return "\n".join(lines)
    lines.append("data:")
    lines.append(json.dumps(data, ensure_ascii=False, indent=2))
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
