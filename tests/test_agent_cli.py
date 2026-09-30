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
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_HANDOFF
    assert payload["stop_reason"] == "awaiting_human"
    assert payload["iterations"] == 3
