"""CLI for the bounded agent."""

from __future__ import annotations

import json

from procurement_agent.agent import cli


def test_cli_handoff_without_confirmation(tmp_path, capsys):
    code = cli.main(
        [
            "--review-date",
            "2026-09-25",
            "--sku",
            "AH-CM-001",
            "--json",
            "--no-env-file",
            "--run-log",
            str(tmp_path / "agent.jsonl"),
            "--tool-log",
            str(tmp_path / "tools.jsonl"),
            "--store",
            str(tmp_path / "req.jsonl"),
            "--state-dir",
            str(tmp_path / "state"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_HANDOFF
    assert payload["stop_reason"] == "awaiting_human"
    assert payload["iterations"] == 3


def test_the_report_prints_on_a_default_windows_console(tmp_path, capsys):
    """cp1252 is the default console encoding on Windows, where the team works.

    A "->" arrow in the report raised UnicodeEncodeError on every real run,
    while pytest captured it as UTF-8 and saw nothing wrong.
    """
    cli.main(
        [
            "--review-date", "2026-09-25",
            "--sku", "AH-CM-001",
            "--no-env-file",
            "--run-log", str(tmp_path / "agent.jsonl"),
            "--tool-log", str(tmp_path / "tools.jsonl"),
            "--store", str(tmp_path / "req.jsonl"),
            "--state-dir", str(tmp_path / "state"),
            "--memory", str(tmp_path / "memory.jsonl"),
        ]
    )
    report = capsys.readouterr().out

    assert "check_reorder_need -> ok" in report
    report.encode("cp1252")


def test_cli_missing_exchange_rate_asks_for_one(tmp_path, capsys):
    code = cli.main(
        [
            "--review-date", "2026-09-25",
            "--sku", "AH-HT-001",
            "--no-env-file",
            "--run-log", str(tmp_path / "agent.jsonl"),
            "--tool-log", str(tmp_path / "tools.jsonl"),
            "--store", str(tmp_path / "req.jsonl"),
            "--no-state",
            "--no-memory",
        ]
    )
    report = capsys.readouterr().out
    assert code == cli.EXIT_HANDOFF
    assert "EXCHANGE_RATE_REQUIRED" in report
    assert "--exchange-rate" in report
    assert not (tmp_path / "req.jsonl").exists()


def test_cli_missing_quotations_reports_unavailable(tmp_path, capsys):
    code = cli.main(
        [
            "--review-date",
            "2026-09-25",
            "--sku",
            "AH-CM-001",
            "--quotations",
            str(tmp_path / "missing.json"),
            "--json",
            "--no-env-file",
            "--run-log",
            str(tmp_path / "agent.jsonl"),
            "--tool-log",
            str(tmp_path / "tools.jsonl"),
            "--store",
            str(tmp_path / "req.jsonl"),
            # Without this the run saves its checkpoint under the real
            # var/agent-state/, so the suite leaves a failed AH-CM-001 behind on
            # the developer's machine and anything reading saved state later
            # reports that item as stuck.
            "--state-dir",
            str(tmp_path / "agent-state"),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_STOP
    assert payload["stop_reason"] == "failed"
    assert payload["stop_detail"].startswith("DATA_SOURCE_UNAVAILABLE:")
