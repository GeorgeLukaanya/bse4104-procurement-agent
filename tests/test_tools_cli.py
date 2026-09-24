"""CLI wiring for the tool dispatcher."""

from __future__ import annotations

import json

from procurement_agent.tools import cli


def test_cli_reorder_json(tmp_path, capsys):
    code = cli.main(
        [
            "check_reorder_need",
            "--review-date",
            "2026-09-25",
            "--sku",
            "AH-CM-001",
            "--json",
            "--no-env-file",
            "--run-log",
            str(tmp_path / "runs.jsonl"),
        ]
    )
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == cli.EXIT_OK
    assert payload["status"] == "ok"
    assert payload["data"]["items"][0]["sku"] == "AH-CM-001"


def test_cli_draft_requires_a_file(capsys):
    code = cli.main(["create_requisition_draft", "--no-env-file"])
    err = capsys.readouterr().err
    assert code == cli.EXIT_USAGE
    assert "needs --file" in err
