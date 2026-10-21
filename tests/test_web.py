"""The HTTP layer. Runs offline, with no API key and no model call.

The page is only ever a view of what the loop returned, so most of these tests
assert that the layer passes a run through faithfully and refuses anything that
would let the browser ask for something the tools would not allow.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone

import pytest

from procurement_agent.web.server import (
    Settings,
    create_server,
    main,
    inbox,
    open_request,
    present,
    request_state,
)

REVIEW_DATE = "2026-09-25"
SKU = "AH-CM-001"


@pytest.fixture
def settings(tmp_path):
    return Settings(
        review_date=REVIEW_DATE,
        requisition_store=str(tmp_path / "requisitions.jsonl"),
        state_dir=str(tmp_path / "agent-state"),
        decisions_path=str(tmp_path / "decisions.sqlite3"),
        record_trace=False,
        clock=lambda: datetime(2026, 9, 25, 9, 14, tzinfo=timezone.utc),
    )


@pytest.fixture
def live(settings):
    """A real server on an ephemeral port, torn down after the test."""
    server = create_server(settings, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[0], server.server_address[1]
    base = f"http://{host}:{port}"

    def call(path, payload=None, method=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            base + path, data=data, method=method or ("POST" if data is not None else "GET"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
        return response.status, body

    try:
        yield call, base
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# ----------------------------------------------------------- the mapping


def test_an_unstarted_item_reads_as_not_started():
    state, label = request_state(None)
    assert state == "not_started"
    assert label == "Not started"


def test_a_comparison_waiting_on_the_officer_reads_as_needing_them():
    """A checkpoint nests completed steps under results, keyed by step name."""
    state, label = request_state({"results": {"compare": {"ranked": []}}, "confirmations": {}})
    assert state == "needs_you"
    assert label == "Your approval"


def test_a_confirmed_comparison_reads_as_ready_to_send():
    state, label = request_state({
        "results": {"compare": {"ranked": []}},
        "confirmations": {"comparison": {"by": "a.nakato", "at": "2026-09-25T09:14:00Z"}},
    })
    assert label == "Ready to send"


def test_a_written_draft_reads_as_with_the_manager():
    state, label = request_state({"results": {"draft": {"requisition_id": "REQ-2026-0043"}}})
    assert state == "waiting"
    assert label == "With the manager"


def test_a_top_level_result_is_not_mistaken_for_a_completed_step():
    """Reading the old shape looked like it worked and reported everything unstarted."""
    state, label = request_state({"comparison": {"ranked": []}, "draft": {"requisition_id": "X"}})
    assert label != "With the manager"
    assert label != "Your approval"


def test_a_failed_run_reads_as_needing_a_decision():
    state, label = request_state({"stop_reason": "failed"})
    assert state == "blocked"
    assert label == "Needs a decision"


# -------------------------------------------------------------- the scan


def test_the_inbox_lists_the_flagged_items_without_running_the_loop(settings, tmp_path):
    payload = inbox(settings, REVIEW_DATE)
    assert payload["ok"] is True
    assert payload["flagged"] == len(payload["items"])
    assert payload["evaluated"] >= payload["flagged"]
    assert any(item["sku"] == SKU for item in payload["items"])
    for item in payload["items"]:
        assert item["state"] == "not_started"
    # reading the inbox must not start anything
    assert not (tmp_path / "agent-state").exists()
    assert not (tmp_path / "requisitions.jsonl").exists()


def test_the_inbox_carries_the_numbers_the_tool_produced(settings):
    item = next(i for i in inbox(settings, REVIEW_DATE)["items"] if i["sku"] == SKU)
    assert item["order_quantity"] > 0
    assert item["current_stock"] <= item["reorder_point"]
    assert isinstance(item["estimated_total_ugx"], (int, float))


# ----------------------------------------------------------- one request


def test_opening_a_request_stops_for_the_officer(settings):
    payload = open_request(settings, REVIEW_DATE, SKU)
    assert payload["stop_reason"] == "awaiting_human"
    assert payload["needs_human"] is True
    assert payload["recommended"]["rank"] == 1
    assert payload["draft"] is None


def test_the_chain_never_shows_a_step_the_run_did_not_reach(settings):
    payload = open_request(settings, REVIEW_DATE, SKU)
    chain = {step["who"]: step["status"] for step in payload["chain"]}
    assert chain["Assistant"] == "done"
    assert chain[settings.officer] == "current"
    assert chain["Manager"] == "waiting"


def test_approving_records_the_decision_with_the_figures_as_they_stood(settings):
    opened = open_request(settings, REVIEW_DATE, SKU)
    recommended = opened["recommended"]
    settings.decisions.record(
        run_id=opened["run_id"], actor=settings.officer, role=settings.role,
        kind="comparison_approved", subject=SKU,
        detail={
            "supplier_name": recommended["supplier_name"],
            "landed_cost_ugx": recommended["landed_cost_ugx"],
        },
    )
    [row] = settings.decisions.for_subject(SKU)
    assert row["detail"]["landed_cost_ugx"] == recommended["landed_cost_ugx"]
    assert row["actor"] == settings.officer


def test_present_passes_the_contract_through_so_a_screenshot_is_auditable(settings):
    payload = open_request(settings, REVIEW_DATE, SKU)
    assert payload["contract"]["version"]
    assert payload["contract"]["path"].endswith(".json")
    assert payload["iterations"] >= 1


def test_present_never_invents_a_ranking(settings):
    """The layer formats. Every ranked row is the tool's, in the tool's order."""
    result = open_request(settings, REVIEW_DATE, SKU)
    ranks = [offer["rank"] for offer in result["ranked"]]
    assert ranks == sorted(ranks)
    assert result["recommended"] is result["ranked"][0]


# ------------------------------------------------------------ over HTTP


def test_the_session_route_admits_there_is_no_login(live):
    call, _ = live
    status, body = call("/api/session")
    assert status == 200
    payload = json.loads(body)
    assert payload["authenticated"] is False
    assert payload["role"] == "PROCUREMENT_OFFICER"


def test_the_page_and_its_assets_are_served(live):
    call, _ = live
    status, body = call("/")
    assert status == 200
    assert "Procurement requests" in body
    assert call("/static/app.css")[0] == 200
    assert call("/static/app.js")[0] == 200


def test_the_inbox_is_reachable_over_http(live):
    call, _ = live
    status, body = call("/api/requests?review_date=" + REVIEW_DATE)
    assert status == 200
    assert json.loads(body)["ok"] is True


def test_opening_and_approving_over_http_records_one_decision(live):
    call, _ = live
    status, body = call(f"/api/requests/{SKU}/open", {})
    assert status == 200
    assert json.loads(body)["needs_human"] is True

    status, body = call(f"/api/requests/{SKU}/approve", {})
    assert status == 200
    approved = json.loads(body)
    assert approved["confirmations"]["comparison"]["by"] == "a.nakato"

    status, body = call("/api/activity")
    rows = json.loads(body)["decisions"]
    assert [row["kind"] for row in rows] == ["comparison_approved"]
    assert rows[0]["detail"]["supplier_name"]


def test_the_inbox_reflects_an_approval_after_it_happens(live):
    """The state the inbox shows has to come off the checkpoint the run saved."""
    call, _ = live
    call(f"/api/requests/{SKU}/open", {})
    call(f"/api/requests/{SKU}/approve", {})
    items = json.loads(call("/api/requests?review_date=" + REVIEW_DATE)[1])["items"]
    item = next(i for i in items if i["sku"] == SKU)
    assert item["state"] == "needs_you"
    assert item["state_label"] == "Ready to send"


def test_sending_is_a_second_press_and_is_what_writes_the_draft(live, tmp_path):
    """The contract has two gates. Approving writes nothing; sending does."""
    call, _ = live
    call(f"/api/requests/{SKU}/open", {})
    approved = json.loads(call(f"/api/requests/{SKU}/approve", {})[1])
    assert approved["draft"] is None

    sent = json.loads(call(f"/api/requests/{SKU}/send", {})[1])
    assert sent["stop_reason"] == "completed"
    assert sent["draft"]["status"] == "DRAFT"
    assert sent["draft"]["approved_by"] is None

    kinds = [row["kind"] for row in json.loads(call("/api/activity")[1])["decisions"]]
    assert kinds == ["requisition_sent", "comparison_approved"]

    items = json.loads(call("/api/requests?review_date=" + REVIEW_DATE)[1])["items"]
    assert next(i for i in items if i["sku"] == SKU)["state_label"] == "With the manager"


def test_a_broken_contract_is_a_server_fault_not_the_browsers(tmp_path):
    """ContractError subclasses ValueError, so the order of the handlers matters."""
    broken = Settings(
        review_date=REVIEW_DATE,
        requisition_store=str(tmp_path / "requisitions.jsonl"),
        state_dir=str(tmp_path / "agent-state"),
        decisions_path=str(tmp_path / "decisions.sqlite3"),
        contract_path=str(tmp_path / "not-a-contract.json"),
        record_trace=False,
    )
    server = create_server(broken, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/api/requests/{SKU}/open"
        request = urllib.request.Request(url, data=b"{}", method="POST",
                                         headers={"Content-Type": "application/json"})
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(request, timeout=10)
        assert exc.value.code == 500
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_a_taken_port_is_an_error_and_not_a_cheerful_start(settings, live):
    """On Windows SO_REUSEADDR lets a second bind succeed on a held port.

    The server then prints that it is listening while the browser reaches
    whatever was there first, and the only symptom is a stranger's 404 body.
    """
    _, base = live
    port = int(base.rsplit(":", 1)[1])
    with pytest.raises(OSError):
        create_server(settings, host="127.0.0.1", port=port)


def test_the_cli_says_which_port_is_taken_instead_of_a_traceback(settings, live, capsys):
    _, base = live
    port = base.rsplit(":", 1)[1]
    code = main(["--port", port, "--no-trace"])
    assert code == 2
    message = capsys.readouterr().err
    assert "already" in message
    assert "--port" in message
    assert "Requests page on" not in message


def test_a_path_outside_static_is_refused(live):
    """The static route serves one flat directory and nothing above it."""
    call, _ = live
    for path in ["/static/../server.py", "/static/..%2Fserver.py", "/static/sub/dir.css"]:
        with pytest.raises(urllib.error.HTTPError) as exc:
            call(path)
        assert exc.value.code == 404


def test_an_unknown_route_is_a_plain_404(live):
    call, _ = live
    with pytest.raises(urllib.error.HTTPError) as exc:
        call("/api/orders")
    assert exc.value.code == 404


def test_a_sku_the_tools_would_refuse_never_reaches_them(live):
    call, _ = live
    with pytest.raises(urllib.error.HTTPError) as exc:
        call("/api/requests/NOT-A-SKU/open", {})
    assert exc.value.code == 400
    assert "not a SKU" in exc.value.read().decode("utf-8")


def test_a_bad_review_date_is_refused(live):
    call, _ = live
    with pytest.raises(urllib.error.HTTPError) as exc:
        call("/api/requests?review_date=yesterday")
    assert exc.value.code == 400


@pytest.mark.parametrize("payload", [
    {"ugx_per_usd": 0},
    {"ugx_per_usd": -1},
    {"ugx_per_usd": "3780"},
    {"ugx_per_usd": 3780, "effective_date": "soon"},
])
def test_a_rate_that_is_not_a_positive_number_is_refused(live, payload):
    """The tool will not pick a rate, so the page must not let a bad one through."""
    call, _ = live
    with pytest.raises(urllib.error.HTTPError) as exc:
        call(f"/api/requests/{SKU}/rate", payload)
    assert exc.value.code == 400


def test_no_response_can_carry_the_api_key(live, monkeypatch):
    """The loop never calls a model, and nothing here may echo the environment."""
    monkeypatch.setenv("GEMINI_API_KEY", "SECRET-KEY-VALUE")
    call, _ = live
    bodies = [
        call("/api/session")[1],
        call("/api/requests")[1],
        call(f"/api/requests/{SKU}/open", {})[1],
        call("/api/activity")[1],
    ]
    for body in bodies:
        assert "SECRET-KEY-VALUE" not in body
