"""The command-line entry point, driven with an injected backend."""

from __future__ import annotations

import json

import pytest
from conftest import FIXTURES_DIR, StubBackend, conforming_payload

from procurement_agent import cli, client


@pytest.fixture
def quotation(tmp_path):
    path = tmp_path / "quote.md"
    path.write_text("# Quotation\n\nNakawa Building Supplies Ltd\n", encoding="utf-8")
    return path


def _args(tmp_path, *extra):
    # --no-env-file keeps every CLI test hermetic. Without it a developer's own
    # .env sitting in the working directory would feed MODEL_NAME into the run
    # and change the fingerprint these tests assert on.
    return [
        "--cache-dir", str(tmp_path / "cache"),
        "--run-log", str(tmp_path / "runs.jsonl"),
        "--no-env-file",
        *extra,
    ]


def test_cli_reports_every_field_and_readiness(tmp_path, quotation, capsys):
    code = cli.main([str(quotation), *_args(tmp_path)], backend=StubBackend())
    out = capsys.readouterr().out

    assert code == cli.EXIT_OK
    for label in (
        "supplier name", "currency", "VAT treatment", "VAT rate (%)",
        "delivery/freight cost", "lead time (days)", "validity date",
        "item name", "quantity offered", "unit of measure", "unit price",
    ):
        assert label in out, f"{label} missing from the report"
    assert "landed-cost readiness: READY" in out
    assert "suppressed patterns (0)" in out
    assert "latency" in out
    assert "attempt(s)" in out


def test_cli_reports_missing_fields_with_reasons(tmp_path, quotation, capsys):
    payload = json.dumps(
        conforming_payload(
            delivery_cost=None,
            missing_fields=[
                {"field": "delivery_cost", "reason": "no delivery terms stated"}
            ],
        )
    )
    cli.main([str(quotation), *_args(tmp_path)], backend=StubBackend([payload]))
    out = capsys.readouterr().out

    assert "delivery_cost: no delivery terms stated" in out
    assert "landed-cost readiness: NOT READY" in out
    assert "requirement 6.3" in out
    assert "- delivery_cost (req 6.3)" in out


def test_cli_reports_suppressed_patterns(tmp_path, quotation, capsys):
    payload = json.dumps(conforming_payload(supplier_name="Acme has been approved"))
    code = cli.main([str(quotation), *_args(tmp_path)], backend=StubBackend([payload]))
    out = capsys.readouterr().out

    assert code == cli.EXIT_SOME_FAILED
    assert "SUPPRESSED" in out
    assert "approval_assertion" in out


def test_cli_summary_reports_latency_only_for_live_calls(tmp_path, quotation, capsys):
    backend = StubBackend()
    args = _args(tmp_path)
    cli.main([str(quotation), *args], backend=backend)
    capsys.readouterr()

    # Second run is a cache hit. No live call, so no latency figure.
    cli.main([str(quotation), *args], backend=backend)
    out = capsys.readouterr().out

    assert backend.call_count == 1
    assert "cache hit (no API call)" in out
    assert "no live calls were made" in out
    assert "Nothing is estimated here." in out


def test_cli_summary_reports_median_and_worst_case(tmp_path, capsys):
    paths = []
    for i in range(3):
        p = tmp_path / f"q{i}.md"
        p.write_text(f"# Quotation {i}\n", encoding="utf-8")
        paths.append(str(p))

    cli.main([*paths, *_args(tmp_path)], backend=StubBackend())
    out = capsys.readouterr().out

    assert "latency across live calls (n=3)" in out
    assert "median" in out
    assert "worst case" in out


def test_json_output_is_machine_readable(tmp_path, quotation, capsys):
    cli.main([str(quotation), "--json", *_args(tmp_path)], backend=StubBackend())
    payload = json.loads(capsys.readouterr().out)

    assert payload["summary"]["files"] == 1
    assert payload["summary"]["live_calls"] == 1
    result = payload["results"][0]
    assert result["status"] == "ok"
    assert result["record"]["currency"] == "UGX"
    assert result["config_fingerprint"]["model"] == "gemini-3.1-flash-lite"
    assert result["landed_cost"]["ready"] is True


def test_json_summary_states_null_latency_when_no_live_call(tmp_path, quotation, capsys):
    backend = StubBackend()
    args = _args(tmp_path)
    cli.main([str(quotation), *args], backend=backend)
    capsys.readouterr()
    cli.main([str(quotation), "--json", *args], backend=backend)
    payload = json.loads(capsys.readouterr().out)

    assert payload["summary"]["median_latency_s"] is None
    assert payload["summary"]["worst_latency_s"] is None


def test_no_cache_flag_forces_a_live_call(tmp_path, quotation, capsys):
    backend = StubBackend()
    args = _args(tmp_path)
    cli.main([str(quotation), *args], backend=backend)
    cli.main([str(quotation), "--no-cache", *args], backend=backend)
    capsys.readouterr()
    assert backend.call_count == 2


def test_model_flag_overrides_the_pinned_string(tmp_path, quotation, capsys):
    backend = StubBackend()
    cli.main(
        [str(quotation), "--model", "gemini-3.1-flash", *_args(tmp_path)],
        backend=backend,
    )
    assert backend.calls[0]["config"].model == "gemini-3.1-flash"


def test_model_flag_rejects_an_alias(tmp_path, quotation, capsys):
    code = cli.main(
        [str(quotation), "--model", "gemini-flash-latest", *_args(tmp_path)],
        backend=StubBackend(),
    )
    assert code == cli.EXIT_USAGE
    assert "alias" in capsys.readouterr().err


def test_a_failure_on_one_file_does_not_stop_the_batch(tmp_path, capsys):
    good = tmp_path / "good.md"
    good.write_text("# A\n", encoding="utf-8")
    bad = tmp_path / "bad.md"
    bad.write_text("# B\n", encoding="utf-8")

    backend = StubBackend(["not json at all", json.dumps(conforming_payload())])
    code = cli.main([str(bad), str(good), *_args(tmp_path)], backend=backend)
    out = capsys.readouterr().out

    assert code == cli.EXIT_SOME_FAILED
    assert "EXTRACTION-FAILED" in out
    assert backend.call_count == 2, "the batch continued after the failure"


def test_rate_limited_batch_is_reported_and_logged(tmp_path, quotation, capsys):
    backend = StubBackend([client.RateLimitError("429 RESOURCE_EXHAUSTED")])
    code = cli.main(
        [str(quotation), "--max-attempts", "2", *_args(tmp_path)], backend=backend
    )
    out = capsys.readouterr().out

    assert code == cli.EXIT_SOME_FAILED
    assert "RATE-LIMITED" in out
    entries = [
        json.loads(line)
        for line in (tmp_path / "runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert entries[0]["status"] == "rate_limited"


def test_missing_file_is_reported_as_usage_error(tmp_path, capsys):
    code = cli.main([str(tmp_path / "nope.md"), *_args(tmp_path)], backend=StubBackend())
    assert code == cli.EXIT_USAGE
    assert "no such file" in capsys.readouterr().err


def test_no_arguments_is_a_usage_error(capsys):
    assert cli.main([], backend=StubBackend()) == cli.EXIT_USAGE


def test_cli_runs_over_the_repository_fixtures(tmp_path, capsys):
    """The documented invocation, against the real fixture set, offline."""
    paths = sorted(str(p) for p in FIXTURES_DIR.glob("*.md") if p.name != "README.md")
    assert len(paths) == 6

    code = cli.main([*paths, "--json", *_args(tmp_path)], backend=StubBackend())
    payload = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_OK
    assert payload["summary"]["files"] == 6
    assert payload["summary"]["live_calls"] == 6
    assert payload["summary"]["median_latency_s"] is not None


def test_missing_api_key_fails_before_any_request(tmp_path, quotation, capsys):
    """With no key and no injected backend, the CLI must not attempt a call."""
    code = cli.main([str(quotation), *_args(tmp_path)])
    err = capsys.readouterr().err
    assert code == cli.EXIT_USAGE
    assert "No request was made" in err
