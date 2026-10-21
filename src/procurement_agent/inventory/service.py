"""The stock system, as its own process, for the agent to call.

    python -m procurement_agent.inventory --port 8020

A real deployment does not read the warehouse out of a file in its own source
tree. It asks whatever the business already runs, and that thing answers over
the network, is owned by somebody else, and changes between one question and
the next. This serves the ledger that way so the agent's data path is the same
shape it would be in production: a request, a timeout, a payload that might be
wrong, and no ability to reach in and fix it.

Three routes.

    GET  /api/stock?as_of=YYYY-MM-DD   the whole position on a date
    GET  /api/stock/{sku}?as_of=...    one item, with the movements behind it
    POST /api/movements                record a sale, a delivery or a count

The last one is what makes a demonstration possible: sell forty bags of cement,
re-run the review, and watch the item cross its reorder point. Without it the
simulation is just a different fixture.

Every snapshot carries a checksum of its own canonical form, and the caller
recomputes it. Be clear about what that is worth: it catches a truncated or
mangled response, not a service that lies, because anything that can forge the
rows can forge the checksum with them. The registered-file path keeps its
stronger guarantee, where the checksum lives somewhere the file's author does
not control. A remote source is a deliberate trade of that guarantee for a
realistic one, and the agent records which it used.

The service decides nothing. It reports stock and records what it is told.
Reorder arithmetic stays in check_reorder_need where it is tested.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import parse_qs, urlparse

from .ledger import (
    DEFAULT_LEDGER_PATH,
    MOVEMENT_KINDS,
    LedgerError,
    Movement,
    StockLedger,
    checksum,
)
from .simulate import build

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SKU_PATTERN = re.compile(r"^AH-[A-Z]{2}-\d{3}$")
MAX_BODY = 32 * 1024


class StockHandler(BaseHTTPRequestHandler):
    server_version = "stock-system"
    sys_version = ""
    ledger: StockLedger
    ledger_path: Path
    default_as_of: str

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    # -- plumbing ---------------------------------------------------------

    def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._drain()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _drain(self) -> None:
        if getattr(self, "_drained", False):
            return
        self._drained = True
        remaining = int(self.headers.get("Content-Length") or 0)
        while remaining > 0:
            chunk = self.rfile.read(min(remaining, 8192))
            if not chunk:
                break
            remaining -= len(chunk)

    def handle_one_request(self) -> None:
        self._drained = False
        super().handle_one_request()

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json({"error": message}, status)

    def _as_of(self, query: dict[str, list[str]]) -> str:
        value = (query.get("as_of") or [self.default_as_of])[0]
        if not ISO_DATE.match(value):
            raise ValueError("as_of must be YYYY-MM-DD")
        return value

    # -- routes -----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/health":
                self._json({"ok": True, "items": len(self.ledger.items),
                            "movements": len(self.ledger.movements)})
                return
            if parsed.path == "/api/stock":
                as_of = self._as_of(query)
                rows = self.ledger.snapshot(as_of)
                self._json({
                    "as_of": as_of,
                    "items": rows,
                    "checksum": checksum(rows),
                    "source": "stock-system",
                })
                return
            match = re.match(r"^/api/stock/([A-Za-z0-9-]+)$", parsed.path)
            if match:
                sku = match.group(1)
                if not SKU_PATTERN.match(sku) or sku not in self.ledger.items:
                    self._error(HTTPStatus.NOT_FOUND, "that is not a stocked item")
                    return
                as_of = self._as_of(query)
                [row] = [r for r in self.ledger.snapshot(as_of) if r["sku"] == sku]
                self._json({
                    "as_of": as_of,
                    "item": row,
                    "movements": self.ledger.history(sku, as_of),
                })
                return
            self._error(HTTPStatus.NOT_FOUND, "no such route")
        except (ValueError, LedgerError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/movements":
            self._error(HTTPStatus.NOT_FOUND, "no such route")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ValueError("that is too much to post")
            self._drained = True
            raw = self.rfile.read(length) if length > 0 else b"{}"
            body = json.loads(raw.decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("the body must be a JSON object")

            movement = Movement(
                sku=str(body.get("sku") or ""),
                on=str(body.get("on") or self.default_as_of),
                kind=str(body.get("kind") or ""),
                quantity=int(body.get("quantity") or 0),
                reference=str(body.get("reference") or ""),
            )
            self.ledger.record(movement)
            self.ledger.save(self.ledger_path)
            self._json({
                "recorded": movement.to_dict(),
                "level": self.ledger.level(movement.sku, movement.on),
            })
        except (LedgerError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))


class _Server(ThreadingHTTPServer):
    """Refuses a port something else already holds. See web/server.py."""

    allow_reuse_address = os.name != "nt"

    def server_bind(self) -> None:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def create_server(
    ledger: StockLedger,
    *,
    ledger_path: str | os.PathLike[str] | None = None,
    default_as_of: str = "2026-09-25",
    host: str = "127.0.0.1",
    port: int = 8020,
) -> ThreadingHTTPServer:
    handler = type("BoundStockHandler", (StockHandler,), {
        "ledger": ledger,
        "ledger_path": Path(ledger_path) if ledger_path else DEFAULT_LEDGER_PATH,
        "default_as_of": default_as_of,
    })
    return _Server((host, port), handler)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="stock-system",
        description="A simulated inventory system for the agent to call.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8020)
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER_PATH))
    parser.add_argument("--as-of", default="2026-09-25", help="the date used when a request omits one")
    parser.add_argument(
        "--seed-from", default="knowledge/data/inventory.csv",
        help="the registered snapshot to take opening balances from",
    )
    parser.add_argument("--opened-on", default="2026-07-01")
    parser.add_argument("--seed", default="ahumuza", help="which repeatable business to simulate")
    parser.add_argument("--rebuild", action="store_true", help="discard the ledger and simulate it again")
    args = parser.parse_args(list(argv) if argv is not None else None)

    path = Path(args.ledger)
    if args.rebuild or not path.exists():
        ledger = build(args.seed_from, opened_on=args.opened_on, until=args.as_of, seed=args.seed)
        ledger.save(path)
        print(
            f"Simulated {len(ledger.items)} items and {len(ledger.movements)} movements "
            f"from {args.opened_on} to {args.as_of}, seed {args.seed!r}.",
            file=sys.stderr,
        )
    else:
        ledger = StockLedger.load(path)

    try:
        server = create_server(
            ledger, ledger_path=path, default_as_of=args.as_of,
            host=args.host, port=args.port,
        )
    except OSError as exc:
        print(
            f"Could not start on {args.host}:{args.port}. Something else is using "
            f"that port ({exc.strerror or exc}). Try --port 8021.",
            file=sys.stderr,
        )
        return 2

    print(f"Stock system on http://{args.host}:{args.port}", file=sys.stderr)
    print(
        f"Point the agent at it with --inventory http://{args.host}:{args.port}/api/stock",
        file=sys.stderr,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
