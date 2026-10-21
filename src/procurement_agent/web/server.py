"""A small HTTP layer over the bounded agent loop, from the standard library.

    python -m procurement_agent.web --review-date 2026-09-25

Why ``http.server`` and not a framework: ``pyproject.toml`` has no runtime
dependencies, the CI job installs nothing from the network, and a tagged
release has to be reproducible offline. A framework would cost all three to
save perhaps eighty lines. There is no build step for the page either: the
browser is handed the HTML, CSS and JavaScript as they are written.

What this layer does and does not do.

It does not decide anything. Every route ends in ``run_workflow()`` or in a
single catalogue tool, and the answer is whatever the loop returned. The web
layer formats; it never ranks, never totals and never picks a supplier.

It does not call a model. The loop is deterministic (KL-04), so a request here
is a few milliseconds of local work and a plain response is the right shape.
Extraction and policy retrieval, the two paths that do call Gemini, are not
exposed here yet.

It is not authenticated. The officer and the role come from the command line,
exactly as they do for ``agent.cli``, which is known limitation KL-02: these
are trusted inputs with no login behind them. The server therefore binds to
127.0.0.1 and says so at startup. Do not put this on a network interface and do
not use it with anything but the synthetic dataset.

Side effects are kept on POST. ``GET /api/requests`` scans and reads saved
state without touching it. Opening, approving and giving a rate are POSTs,
because each one resumes the loop and may write a checkpoint, a requisition or
a decision.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import socket
import sys
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, urlparse

from ..agent.checkpoint import DEFAULT_STATE_DIR, CheckpointStore, run_id_for
from ..agent.contract import ContractError
from ..agent.steps import (
    STEP_COMPARE,
    STEP_DRAFT,
    STOP_AWAITING_HUMAN,
    STOP_COMPLETED,
    STOP_NO_REORDER,
)
from ..agent.workflow import run_workflow
from ..decisions import (
    DEFAULT_DECISIONS_PATH,
    KIND_COMPARISON_APPROVED,
    KIND_RATE_GIVEN,
    KIND_REQUISITION_SENT,
    KIND_RUN_STOPPED,
    DecisionRefused,
    DecisionStore,
)
from ..tools.contract import ROLE_OFFICER, ROLES
from ..tools.dispatch import invoke

STATIC_DIR = Path(__file__).resolve().parent / "static"
SKU_PATTERN = re.compile(r"^AH-[A-Z]{2}-\d{3}$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_BODY = 64 * 1024

# What the inbox calls each state. The left column is what the loop reported;
# the right is what a person is shown. Nothing here invents a state the loop
# cannot produce.
STATE_NEEDS_YOU = "needs_you"
STATE_WAITING = "waiting"
STATE_BLOCKED = "blocked"
STATE_DONE = "done"
STATE_NOT_STARTED = "not_started"


class Settings:
    """Everything the handler needs that is not in the request itself."""

    def __init__(
        self,
        *,
        officer: str = "a.nakato",
        role: str = ROLE_OFFICER,
        review_date: str | None = None,
        inventory_path: str | None = None,
        suppliers_path: str | None = None,
        quotations_path: str | None = None,
        register_path: str | None = None,
        requisition_store: str | None = None,
        state_dir: str | None = None,
        decisions_path: str | None = None,
        run_log: str | None = None,
        tool_log: str | None = None,
        contract_path: str | None = None,
        record_trace: bool = True,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if role not in ROLES:
            raise ValueError(f"{role!r} is not a seeded role.")
        self.officer = officer
        self.role = role
        self.review_date = review_date
        self.inventory_path = inventory_path
        self.suppliers_path = suppliers_path
        self.quotations_path = quotations_path
        self.register_path = register_path
        self.requisition_store = requisition_store
        self.state_dir = state_dir if state_dir is not None else str(DEFAULT_STATE_DIR)
        self.run_log = run_log
        self.tool_log = tool_log
        self.contract_path = contract_path
        self.record_trace = record_trace
        self.clock = clock
        self.decisions = DecisionStore(
            decisions_path if decisions_path is not None else DEFAULT_DECISIONS_PATH,
            clock=clock,
        )

    def today(self) -> str:
        if self.review_date:
            return self.review_date
        now = self.clock() if self.clock else datetime.now(timezone.utc)
        return now.date().isoformat()

    def run_kwargs(self, sku: str | None) -> dict[str, Any]:
        return dict(
            sku=sku,
            officer_username=self.officer,
            caller_role=self.role,
            inventory_path=self.inventory_path,
            suppliers_path=self.suppliers_path,
            quotations_path=self.quotations_path,
            register_path=self.register_path,
            requisition_store=self.requisition_store,
            checkpoint_dir=self.state_dir,
            run_log=self.run_log,
            tool_log=self.tool_log,
            contract_path=self.contract_path,
            record_trace=self.record_trace,
            clock=self.clock,
        )


# ---------------------------------------------------------------- the scan


def scan_items(settings: Settings, review_date: str) -> dict[str, Any]:
    """The flagged items, read only. One catalogue call, no loop, no writes."""
    envelope = invoke(
        "check_reorder_need",
        {"review_date": review_date},
        caller_role=settings.role,
        allowed_tools=("check_reorder_need",),
        inventory_path=settings.inventory_path,
        suppliers_path=settings.suppliers_path,
        quotations_path=settings.quotations_path,
        register_path=settings.register_path,
        record_trace=False,
        clock=settings.clock,
    )
    return envelope


def saved_state(settings: Settings, review_date: str, sku: str) -> dict[str, Any] | None:
    """What a previous run left behind for this item, without resuming it."""
    store = CheckpointStore(settings.state_dir)
    return store.load(run_id_for(review_date, sku, settings.officer))


def request_state(saved: Mapping[str, Any] | None) -> tuple[str, str]:
    """Turn a saved checkpoint into the state and the line the inbox shows.

    Kept as a plain function of the checkpoint so it can be tested without a
    server, and so the mapping from what the loop produced to what a person
    reads lives in one place. The results a run completed are nested under
    ``results`` and keyed by step name; reading them from the top level looks
    like it works and silently reports every item as unstarted.
    """
    if not saved:
        return STATE_NOT_STARTED, "Not started"
    results = saved.get("results") or {}
    confirmations = saved.get("confirmations") or {}
    if results.get(STEP_DRAFT):
        return STATE_WAITING, "With the manager"
    stop = saved.get("stop_reason")
    if stop == STOP_COMPLETED:
        return STATE_DONE, "Done"
    if stop == STOP_NO_REORDER:
        return STATE_DONE, "Nothing needed"
    if stop in {"failed", "refused", "unauthorized", "no_progress", "max_iterations", "timeout"}:
        return STATE_BLOCKED, "Needs a decision"
    if results.get(STEP_COMPARE):
        if "comparison" in confirmations:
            return STATE_NEEDS_YOU, "Ready to send"
        return STATE_NEEDS_YOU, "Your approval"
    if saved.get("step") == STEP_COMPARE:
        return STATE_NEEDS_YOU, "Needs a rate"
    return STATE_WAITING, "Working on it"


def inbox(settings: Settings, review_date: str) -> dict[str, Any]:
    envelope = scan_items(settings, review_date)
    if envelope.get("status") not in {"ok", "no_result"}:
        return {
            "review_date": review_date,
            "ok": False,
            "errors": envelope.get("errors") or [],
            "items": [],
        }
    data = envelope.get("data") or {}
    items = []
    for item in data.get("items") or []:
        sku = item.get("sku")
        saved = saved_state(settings, review_date, sku) if sku else None
        state, label = request_state(saved)
        items.append({
            "sku": sku,
            "name": item.get("item_name"),
            "category": item.get("category"),
            "current_stock": item.get("current_stock"),
            "reorder_point": item.get("reorder_point"),
            "order_quantity": item.get("reorder_quantity"),
            "estimated_total_ugx": item.get("estimated_total_ugx"),
            "state": state,
            "state_label": label,
            # When a run last saved something for this item, or null if none has.
            # The inbox shows how long a thing has been sitting, and inventing
            # that from anything other than the checkpoint would be a lie.
            "updated_at": (saved or {}).get("saved_at"),
            "requisition_id": (saved or {}).get("draft", {}).get("requisition_id")
            if isinstance((saved or {}).get("draft"), dict) else None,
        })
    return {
        "review_date": review_date,
        "ok": True,
        "evaluated": data.get("evaluated_count", 0),
        "flagged": data.get("flagged_count", 0),
        "items": items,
    }


# ------------------------------------------------------------ one request


def chain_for(result_dict: Mapping[str, Any], officer: str) -> list[dict[str, Any]]:
    """The approval chain, derived from the run and nothing else.

    Three steps, because the loop has three: the agent compares, the officer
    approves the comparison, the manager signs off. Each one is done, current
    or waiting, and a step is never shown as done unless the run says so.
    """
    confirmations = result_dict.get("confirmations") or {}
    comparison = result_dict.get("comparison")
    draft = result_dict.get("draft")
    stop = result_dict.get("stop_reason")

    steps = [{
        "who": "Assistant",
        "what": "Compares the held quotations",
        "status": "done" if comparison else ("current" if stop not in {"failed", "refused"} else "blocked"),
        "when": None,
    }]
    approved = confirmations.get("comparison")
    steps.append({
        "who": officer,
        "what": "Approves the price",
        "status": "done" if approved else ("current" if comparison else "waiting"),
        "when": (approved or {}).get("at"),
    })
    steps.append({
        "who": "Manager",
        "what": "Signs off the spend",
        "status": "current" if draft else "waiting",
        "when": None,
    })
    return steps


def present(result_dict: Mapping[str, Any], settings: Settings) -> dict[str, Any]:
    """The payload the page reads. A view of the run, never a second opinion."""
    comparison = result_dict.get("comparison") or {}
    ranked = comparison.get("ranked") or []
    top = ranked[0] if ranked else None
    subject = result_dict.get("sku") or result_dict.get("run_id") or ""
    return {
        "run_id": result_dict.get("run_id"),
        "review_date": result_dict.get("review_date"),
        "sku": result_dict.get("sku"),
        "stop_reason": result_dict.get("stop_reason"),
        "stop_detail": result_dict.get("stop_detail"),
        "needs_human": result_dict.get("stop_reason") == STOP_AWAITING_HUMAN,
        "step": result_dict.get("step"),
        "iterations": result_dict.get("iterations"),
        "contract": result_dict.get("contract"),
        "resumed": result_dict.get("resumed"),
        "confirmations": result_dict.get("confirmations"),
        "chain": chain_for(result_dict, settings.officer),
        "ranked": ranked,
        "excluded": comparison.get("excluded") or [],
        "requirement": comparison.get("quotation_requirement"),
        "exchange_rate": comparison.get("exchange_rate"),
        "recommended": top,
        "draft": result_dict.get("draft"),
        "calls": result_dict.get("calls") or [],
        "decisions": settings.decisions.for_subject(subject) if subject else [],
    }


def open_request(settings: Settings, review_date: str, sku: str, **overrides: Any) -> dict[str, Any]:
    """Resume this item's run to wherever it stops, and present the result."""
    kwargs = settings.run_kwargs(sku)
    kwargs.update(overrides)
    result = run_workflow(review_date=review_date, **kwargs)
    payload = present(result.to_dict(), settings)
    _record_stop(settings, result, sku)
    return payload


def _record_stop(settings: Settings, result: Any, sku: str) -> None:
    """Keep a row when a run ends somewhere a person has to deal with."""
    reason = result.stop_reason
    if reason in {"failed", "refused", "no_progress", "max_iterations", "timeout"}:
        try:
            settings.decisions.record(
                run_id=result.state.run_id or "",
                actor="AGENT",
                role="AGENT",
                kind=KIND_RUN_STOPPED,
                subject=sku,
                detail={"stop_reason": reason, "stop_detail": result.stop_detail},
            )
        except DecisionRefused:
            # Recording is a record, not a gate. A refused row never fails a run.
            pass


# -------------------------------------------------------------- the server


class Handler(BaseHTTPRequestHandler):
    server_version = "procurement-agent"
    sys_version = ""
    settings: Settings

    # -- plumbing ---------------------------------------------------------

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # The page loads nothing from anywhere else, so say so.
        self.send_header("Content-Security-Policy", "default-src 'self'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=None).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json({"error": message}, status)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY:
            raise ValueError("request body is too large")
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("body is not JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("body must be a JSON object")
        return parsed

    def _review_date(self, query: Mapping[str, list[str]]) -> str:
        value = (query.get("review_date") or [None])[0] or self.settings.today()
        if not ISO_DATE.match(value):
            raise ValueError("review_date must be YYYY-MM-DD")
        return value

    # -- static -----------------------------------------------------------

    def _not_found(self) -> None:
        self._error(HTTPStatus.NOT_FOUND, "no such file")

    def _static(self, path: str) -> None:
        name = path[len("/static/"):]
        if not name or "/" in name or "\\" in name or name.startswith("."):
            self._not_found()
            return
        target = STATIC_DIR / name
        try:
            resolved = target.resolve()
            resolved.relative_to(STATIC_DIR.resolve())
        except (OSError, ValueError):
            self._not_found()
            return
        if not resolved.is_file():
            self._not_found()
            return
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        self._send(HTTPStatus.OK, resolved.read_bytes(), content_type)

    # -- routes -----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        route = parsed.path
        query = parse_qs(parsed.query)
        try:
            if route in {"/", "/index.html"}:
                index = STATIC_DIR / "index.html"
                if not index.is_file():
                    self._error(HTTPStatus.NOT_FOUND, "the page is missing")
                    return
                self._send(HTTPStatus.OK, index.read_bytes(), "text/html; charset=utf-8")
                return
            if route.startswith("/static/"):
                self._static(route)
                return
            if route == "/api/session":
                self._json({
                    "officer": self.settings.officer,
                    "role": self.settings.role,
                    "review_date": self.settings.today(),
                    "authenticated": False,
                })
                return
            if route == "/api/requests":
                self._json(inbox(self.settings, self._review_date(query)))
                return
            if route == "/api/activity":
                limit = int((query.get("limit") or ["100"])[0])
                decisions = self.settings.decisions.recent(limit=limit)
                superseded = self.settings.decisions.superseded_ids()
                for row in decisions:
                    row["superseded"] = row["id"] in superseded
                self._json({"decisions": decisions})
                return
            self._error(HTTPStatus.NOT_FOUND, "no such route")
        except ContractError as exc:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
        except ValueError as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))

    def do_POST(self) -> None:  # noqa: N802
        match = re.match(
            r"^/api/requests/([A-Za-z0-9-]+)/(open|approve|send|rate)$", urlparse(self.path).path
        )
        if not match:
            self._error(HTTPStatus.NOT_FOUND, "no such route")
            return
        sku, action = match.group(1), match.group(2)
        if not SKU_PATTERN.match(sku):
            self._error(HTTPStatus.BAD_REQUEST, "that is not a SKU")
            return
        actions = {
            "open": self._open,
            "approve": self._approve,
            "send": self._send_to_manager,
            "rate": self._rate,
        }
        try:
            body = self._body()
            review_date = str(body.get("review_date") or self.settings.today())
            if not ISO_DATE.match(review_date):
                raise ValueError("review_date must be YYYY-MM-DD")
            self._json(actions[action](sku, review_date, body))
        except ContractError as exc:
            # A missing or malformed contract is our fault, not the browser's.
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
        except (DecisionRefused, ValueError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))

    # -- actions ----------------------------------------------------------

    def _open(self, sku: str, review_date: str, body: Mapping[str, Any]) -> dict[str, Any]:
        return open_request(self.settings, review_date, sku)

    def _approve(self, sku: str, review_date: str, body: Mapping[str, Any]) -> dict[str, Any]:
        """Gate 2. The officer accepts the comparison; nothing is written yet."""
        payload = open_request(self.settings, review_date, sku, confirm_comparison=True)
        recommended = payload.get("recommended") or {}
        self._record(sku, payload, KIND_COMPARISON_APPROVED, {
            "supplier_id": recommended.get("supplier_id"),
            "supplier_name": recommended.get("supplier_name"),
            "quotation_id": recommended.get("quotation_id"),
            "landed_cost_ugx": recommended.get("landed_cost_ugx"),
            "clause": (payload.get("requirement") or {}).get("clause"),
            "reason": body.get("reason"),
        })
        return payload

    def _send_to_manager(self, sku: str, review_date: str, body: Mapping[str, Any]) -> dict[str, Any]:
        """Gate 3, and the only call here that writes anything.

        Both confirmations are passed because the loop checks both, and a run
        that reaches this point has already recorded the first one. Sending is
        a separate press from approving because the contract has two gates and
        collapsing them in the interface would misreport the state model.
        """
        payload = open_request(
            self.settings, review_date, sku,
            confirm_comparison=True, confirm_draft=True,
        )
        draft = payload.get("draft") or {}
        if draft.get("requisition_id"):
            self._record(sku, payload, KIND_REQUISITION_SENT, {
                "requisition_id": draft.get("requisition_id"),
                "status": draft.get("status"),
                "landed_cost_ugx": (payload.get("recommended") or {}).get("landed_cost_ugx"),
            })
        return payload

    def _rate(self, sku: str, review_date: str, body: Mapping[str, Any]) -> dict[str, Any]:
        rate = body.get("ugx_per_usd")
        effective = str(body.get("effective_date") or review_date)
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or rate <= 0:
            raise ValueError("ugx_per_usd must be a positive number")
        if not ISO_DATE.match(effective):
            raise ValueError("effective_date must be YYYY-MM-DD")
        payload = open_request(
            self.settings, review_date, sku,
            exchange_rate_ugx_per_usd=float(rate),
            exchange_rate_effective_date=effective,
        )
        self._record(sku, payload, KIND_RATE_GIVEN, {
            "ugx_per_usd": float(rate), "effective_date": effective,
        })
        return payload

    def _record(self, sku: str, payload: Mapping[str, Any], kind: str, detail: dict[str, Any]) -> None:
        """Write the decision row, then put it back on the response."""
        row = self.settings.decisions.record(
            run_id=payload.get("run_id") or "",
            actor=self.settings.officer,
            role=self.settings.role,
            kind=kind,
            subject=sku,
            detail={k: v for k, v in detail.items() if v is not None},
        )
        if isinstance(payload, dict):
            payload.setdefault("decisions", []).append(row)


class _Server(ThreadingHTTPServer):
    """A server that refuses to start on a port somebody else already holds.

    ``http.server`` sets SO_REUSEADDR, which on Windows does not mean what it
    means on Unix: a second process may bind an address another process is
    already listening on, and which of them receives a given connection is
    undefined. The effect is worse than a crash. The server prints a cheerful
    "listening on 8000", the browser reaches the other program, and the only
    symptom is somebody else's 404 body.

    So reuse is off on Windows and the exclusive flag is set, which turns a
    port clash back into an error at bind time where it belongs.
    """

    allow_reuse_address = os.name != "nt"

    def server_bind(self) -> None:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def create_server(settings: Settings, *, host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"settings": settings})
    return _Server((host, port), handler)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="procurement-agent-web",
        description="Serve the procurement requests page. Localhost only, no login.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--review-date", default=None, help="YYYY-MM-DD, defaults to today")
    parser.add_argument("--officer", default="a.nakato")
    parser.add_argument("--role", choices=ROLES, default=ROLE_OFFICER)
    parser.add_argument("--inventory")
    parser.add_argument("--suppliers")
    parser.add_argument("--quotations")
    parser.add_argument("--register")
    parser.add_argument("--store")
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    parser.add_argument("--decisions", default=str(DEFAULT_DECISIONS_PATH))
    # Same escape hatch the agent CLI has: a demo should not be able to write
    # into the evidence traces the team has already committed.
    parser.add_argument("--run-log", default=None)
    parser.add_argument("--tool-log", default=None)
    parser.add_argument("--no-trace", action="store_true", help="record no trace at all")
    parser.add_argument("--contract", default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    settings = Settings(
        officer=args.officer,
        role=args.role,
        review_date=args.review_date,
        inventory_path=args.inventory,
        suppliers_path=args.suppliers,
        quotations_path=args.quotations,
        register_path=args.register,
        requisition_store=args.store,
        state_dir=args.state_dir,
        decisions_path=args.decisions,
        contract_path=args.contract,
        run_log=args.run_log,
        tool_log=args.tool_log,
        record_trace=not args.no_trace,
    )
    try:
        server = create_server(settings, host=args.host, port=args.port)
    except OSError as exc:
        print(
            f"Could not start on {args.host}:{args.port}. Something else is already "
            f"using that port ({exc.strerror or exc}). Pick another with --port 8010.",
            file=sys.stderr,
        )
        return 2
    print(f"Requests page on http://{args.host}:{args.port}", file=sys.stderr)
    print(
        f"Signed in as {settings.officer} ({settings.role}) because the command line says so. "
        "There is no login yet (KL-02), so keep this on localhost and on synthetic data.",
        file=sys.stderr,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
