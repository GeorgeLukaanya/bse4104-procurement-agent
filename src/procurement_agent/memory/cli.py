"""Officer commands for procurement memory.

    python -m procurement_agent.memory.cli add-note --supplier SUP-004 \\
        --text "Last two cement deliveries arrived two days late." --on 2026-09-20
    python -m procurement_agent.memory.cli list [--supplier SUP-004] [--as-of 2026-09-25]
    python -m procurement_agent.memory.cli forget MEM-0123456789
    python -m procurement_agent.memory.cli purge-expired --as-of 2026-10-06

Only a Procurement Officer writes or deletes. The manager and the agent may
list. Exit 0 on success, 1 when the rules refuse the request, 2 on usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Sequence

from ..tools.contract import ROLE_OFFICER, ROLES
from .store import DEFAULT_MEMORY_PATH, NOTE_RETENTION_DAYS, MemoryRefused, MemoryStore, summarise

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return int(exc.code or EXIT_USAGE)

    store = MemoryStore(args.store)
    try:
        if args.command == "add-note":
            record = store.add_note(
                supplier_id=args.supplier,
                text=args.text,
                author=args.officer,
                role=args.role,
                recorded_on=args.on or date.today().isoformat(),
                retention_days=args.retention_days,
            )
            print(f"stored {record['id']} (expires {record['expires_on']})")
        elif args.command == "list":
            records = store.records(as_of=args.as_of, include_expired=args.include_expired)
            if args.supplier:
                records = [r for r in records if r.get("supplier_id") == args.supplier]
            if args.json:
                print(json.dumps(records, ensure_ascii=False, indent=2))
            else:
                for record in records:
                    print(f"[{record.get('id')}] {summarise(record)} (expires {record.get('expires_on')})")
                print(f"{len(records)} record(s) in {store.path}")
        elif args.command == "forget":
            if store.forget(args.memory_id, role=args.role):
                print(f"deleted {args.memory_id}")
            else:
                print(f"{args.memory_id} not found")
                return EXIT_REFUSED
        elif args.command == "purge-expired":
            removed = store.purge_expired(as_of=args.as_of or date.today().isoformat())
            print(f"purged {removed} expired record(s)")
    except MemoryRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    return EXIT_OK


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="procurement-memory",
        description="Read and maintain advisory procurement memory.",
    )
    parser.add_argument("--store", default=str(DEFAULT_MEMORY_PATH))
    parser.add_argument("--role", choices=ROLES, default=ROLE_OFFICER)
    parser.add_argument("--officer", default="a.nakato")
    sub = parser.add_subparsers(dest="command", required=True)

    note = sub.add_parser("add-note", help="record a supplier performance note")
    note.add_argument("--supplier", required=True, help="SUP-000")
    note.add_argument("--text", required=True)
    note.add_argument("--on", help="date observed, YYYY-MM-DD (default: today)")
    note.add_argument("--retention-days", type=int, default=NOTE_RETENTION_DAYS)

    listing = sub.add_parser("list", help="show unexpired records")
    listing.add_argument("--supplier")
    listing.add_argument("--as-of")
    listing.add_argument("--include-expired", action="store_true")
    listing.add_argument("--json", action="store_true")

    forget = sub.add_parser("forget", help="delete one record")
    forget.add_argument("memory_id")

    purge = sub.add_parser("purge-expired", help="delete every expired record")
    purge.add_argument("--as-of")
    return parser


if __name__ == "__main__":
    sys.exit(main())
