"""The loop is bounded by the contract file, not by constants in the code."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from procurement_agent.agent import workflow
from procurement_agent.agent.contract import (
    DEFAULT_CONTRACT_PATH,
    ContractError,
    load_contract,
)
from procurement_agent.agent.steps import ALLOW_LIST, DEFAULT_MAX_ITERATIONS

ROOT = Path(__file__).resolve().parents[1]
REAL_CONTRACT = ROOT / "contracts" / "agent-task-contract.json"


def _write(tmp_path, **overrides):
    payload = json.loads(REAL_CONTRACT.read_text(encoding="utf-8"))
    for dotted, value in overrides.items():
        section, _, key = dotted.partition(".")
        if key:
            payload[section][key] = value
        else:
            payload[section] = value
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# --- the committed contract --------------------------------------------------


def test_the_committed_contract_loads():
    contract = load_contract(REAL_CONTRACT)

    assert contract.version == "1.0"
    assert contract.iterations_per_item == 8
    assert contract.wall_clock_seconds == 120
    assert contract.caller_role == "AGENT"
    assert contract.goal.startswith("For one flagged reorder item")


def test_the_default_path_is_the_committed_contract():
    assert (ROOT / DEFAULT_CONTRACT_PATH).resolve() == REAL_CONTRACT.resolve()


def test_the_code_default_agrees_with_the_contract():
    """If these drift, the loop and the document disagree about its limit."""
    assert DEFAULT_MAX_ITERATIONS == load_contract(REAL_CONTRACT).iterations_per_item


def test_every_tool_the_loop_can_call_is_approved_by_the_contract():
    contract = load_contract(REAL_CONTRACT)
    for tools in ALLOW_LIST.values():
        for tool in tools:
            # check_reorder_need runs before the loop (architecture section 2),
            # so it is the one step not in the contract's action set.
            if tool == "check_reorder_need":
                continue
            assert contract.allows(tool), f"{tool} is not an approved action"


def test_the_write_tool_needs_confirmation_and_the_read_tools_do_not():
    contract = load_contract(REAL_CONTRACT)
    assert contract.requires_confirmation("create_requisition_draft")
    assert not contract.requires_confirmation("compare_quotations")


def test_prohibited_actions_are_named():
    never = load_contract(REAL_CONTRACT).never_in_the_loop
    assert "issue a purchase order" in never
    assert "approve" in never


def test_stop_reasons_map_to_what_the_code_produces():
    contract = load_contract(REAL_CONTRACT)
    assert contract.stop_reason_for("completed") == "DRAFT_CREATED"
    assert contract.stop_reason_for("max_iterations") == "ITERATION_LIMIT"
    assert contract.stop_reason_for("awaiting_human") == "AWAITING_HUMAN"
    assert contract.stop_reason_for("nonsense") is None


# --- a contract that cannot be trusted ---------------------------------------


def test_a_missing_contract_stops_the_run(tmp_path):
    """An unbounded loop is what the contract exists to prevent."""
    with pytest.raises(ContractError, match="no agent task contract"):
        load_contract(tmp_path / "nowhere.json")


def test_malformed_json_is_rejected(tmp_path):
    path = tmp_path / "contract.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ContractError, match="not valid JSON"):
        load_contract(path)


def test_an_unsupported_version_is_rejected(tmp_path):
    path = _write(tmp_path, contract_version="9.9")
    with pytest.raises(ContractError, match="contract_version"):
        load_contract(path)


@pytest.mark.parametrize("bad", [0, -1, "eight", 2.5, True])
def test_a_nonsense_iteration_limit_is_rejected(tmp_path, bad):
    path = _write(tmp_path, limits={"iterations_per_item": bad, "wall_clock_seconds": 120})
    with pytest.raises(ContractError, match="iterations_per_item"):
        load_contract(path)


def test_a_contract_approving_no_tools_is_rejected(tmp_path):
    path = _write(tmp_path, approved_actions={"tools": [], "control_actions": ["stop"]})
    with pytest.raises(ContractError, match="approves no tools"):
        load_contract(path)


@pytest.mark.parametrize("section", ["limits", "approved_actions", "goal", "planner"])
def test_a_missing_section_is_rejected(tmp_path, section):
    payload = json.loads(REAL_CONTRACT.read_text(encoding="utf-8"))
    payload.pop(section)
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ContractError, match=section):
        load_contract(path)


# --- the loop actually uses it -----------------------------------------------


def _run(tmp_path, **kwargs):
    return workflow.run_workflow(
        review_date="2026-09-25",
        sku="AH-CM-001",
        run_log=str(tmp_path / "agent.jsonl"),
        tool_log=str(tmp_path / "tools.jsonl"),
        requisition_store=str(tmp_path / "req.jsonl"),
        **kwargs,
    )


def test_the_loop_stops_at_the_contract_limit(tmp_path):
    """Lower the contract, and the run halts earlier. No flag, no env var."""
    path = _write(tmp_path, limits={"iterations_per_item": 1, "wall_clock_seconds": 120})

    result = _run(tmp_path, contract_path=str(path))

    assert result.iterations == 1
    assert result.stop_reason == "max_iterations"


def test_a_flag_still_overrides_the_contract(tmp_path):
    path = _write(tmp_path, limits={"iterations_per_item": 8, "wall_clock_seconds": 120})

    result = _run(tmp_path, contract_path=str(path), max_iterations=1)

    assert result.iterations == 1
    assert result.stop_reason == "max_iterations"


def test_the_trace_names_the_contract_that_bounded_the_run(tmp_path):
    result = _run(tmp_path, contract_path=str(REAL_CONTRACT))
    traced = result.to_dict()["contract"]

    assert traced["version"] == "1.0"
    assert traced["iterations_per_item"] == 8
    assert traced["stop_reason"] == "AWAITING_HUMAN"
    assert traced["path"].endswith("agent-task-contract.json")


def test_a_run_without_a_contract_fails_rather_than_running_unbounded(tmp_path):
    with pytest.raises(ContractError):
        _run(tmp_path, contract_path=str(tmp_path / "gone.json"))


def test_the_command_reports_a_missing_contract_without_a_traceback(tmp_path, capsys):
    from procurement_agent.agent import cli

    code = cli.main(
        [
            "--review-date", "2026-09-25",
            "--contract", str(tmp_path / "gone.json"),
            "--no-env-file",
            "--run-log", str(tmp_path / "agent.jsonl"),
            "--tool-log", str(tmp_path / "tools.jsonl"),
            "--store", str(tmp_path / "req.jsonl"),
        ]
    )

    assert code == cli.EXIT_STOP
    assert "no agent task contract" in capsys.readouterr().err
