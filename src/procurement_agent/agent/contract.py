"""Load the Agent Task Contract, so the loop is bounded by the document.

`contracts/agent-task-contract.json` is the canonical contract, kept at the top
level so it is findable without reading the docs tree; the write-up at
`docs/requirements/agent-task-contract.md` explains the same values. The loop reads the file at startup
and takes its iteration cap, time budget and per-phase allow-list from it.

Why a file rather than constants
--------------------------------
A contract nobody loads is a document people can disagree with silently. The
architecture proposed 8 iterations, `.env.example` carried 6, and the code
carried 6; nothing failed, because no single place decided. With the file
loaded, changing a limit means changing the contract, and a test can assert the
code and the document agree.

JSON, not the YAML printed in the write-up: pyproject declares no runtime
dependencies, so there is no YAML parser, and `json` is in the standard library.

Precedence, highest first: an explicit argument (a CLI flag), then the
environment, then the contract. A flag is a deliberate act for one run; the
environment is a machine's setting; the contract is the team's decision and is
the floor nothing silently falls through.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CONTRACT_PATH = Path("contracts") / "agent-task-contract.json"
SUPPORTED_CONTRACT_VERSIONS = ("1.0",)


class ContractError(ValueError):
    """Raised when the contract is missing, unreadable or incomplete."""


@dataclass(frozen=True)
class AgentContract:
    """The values the loop is allowed to run under."""

    version: str
    goal: str
    caller_role: str
    iterations_per_item: int
    wall_clock_seconds: float
    replans_per_failure_kind: int
    model_calls_per_run_max: int
    planner_decides: str
    tools: tuple[str, ...]
    write_tools: tuple[str, ...]
    control_actions: tuple[str, ...]
    closed_action_set: bool
    stop_reasons: dict[str, tuple[str, ...]]
    implemented_as: dict[str, str]
    trace_names: dict[str, str]
    never_in_the_loop: tuple[str, ...]
    path: str

    def allows(self, tool_name: str) -> bool:
        """Whether `tool_name` is an approved action at all."""
        return tool_name in self.tools or tool_name in self.control_actions

    def requires_confirmation(self, tool_name: str) -> bool:
        return tool_name in self.write_tools

    def stop_reason_for(self, implemented: str) -> str | None:
        """The contract's name for a stop reason the code produced, when there is one.

        None where the code's string covers several contract names: `unauthorized`
        is both TOOL_NOT_ALLOWED and UNAUTHORIZED_ROLE, and naming one of them
        would put a guess in the trace. The architecture wants exactly one
        specific stop reason per run, so the trace keeps the code's string until
        the loop reports which it was.
        """
        return self.trace_names.get(implemented)


def load_contract(path: str | Path = DEFAULT_CONTRACT_PATH) -> AgentContract:
    """Read and check the contract. A malformed contract stops the run."""
    contract_path = Path(path)
    try:
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(
            f"no agent task contract at {contract_path}. The loop will not run "
            "without the limits it is bound by."
        ) from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"{contract_path} is not valid JSON: {exc}") from exc

    version = payload.get("contract_version")
    if version not in SUPPORTED_CONTRACT_VERSIONS:
        raise ContractError(
            f"{contract_path}: contract_version {version!r} is not one of "
            f"{', '.join(SUPPORTED_CONTRACT_VERSIONS)}"
        )

    limits = _section(payload, "limits", contract_path)
    actions = _section(payload, "approved_actions", contract_path)
    stops = _section(payload, "stop_conditions", contract_path)
    goal = _section(payload, "goal", contract_path)
    handoff = _section(payload, "human_handoff", contract_path)
    planner = _section(payload, "planner", contract_path)

    tools = tuple(tool["name"] for tool in actions.get("tools", []))
    write_tools = tuple(
        tool["name"] for tool in actions.get("tools", []) if tool.get("permission") == "write"
    )
    if not tools:
        raise ContractError(f"{contract_path}: the contract approves no tools")

    iterations = _positive_int(limits, "iterations_per_item", contract_path)
    seconds = _positive_number(limits, "wall_clock_seconds", contract_path)

    stop_reasons = {
        group: tuple(names)
        for group, names in stops.items()
        if isinstance(names, list)
    }

    return AgentContract(
        version=version,
        goal=str(goal.get("statement", "")),
        caller_role=str(goal.get("caller_role", "AGENT")),
        iterations_per_item=iterations,
        wall_clock_seconds=float(seconds),
        replans_per_failure_kind=int(limits.get("replans_per_failure_kind", 1)),
        model_calls_per_run_max=int(limits.get("model_calls_per_run_max", 0)),
        planner_decides=str(planner.get("decides", "deterministic")),
        tools=tools,
        write_tools=write_tools,
        control_actions=tuple(actions.get("control_actions", ())),
        closed_action_set=bool(actions.get("closed", True)),
        stop_reasons=stop_reasons,
        implemented_as=dict(stops.get("implemented_as", {})),
        trace_names=dict(stops.get("trace_name_for", {})),
        never_in_the_loop=tuple(handoff.get("never_in_the_loop", ())),
        path=contract_path.as_posix(),
    )


def _section(payload: dict[str, Any], key: str, path: Path) -> dict[str, Any]:
    section = payload.get(key)
    if not isinstance(section, dict):
        raise ContractError(f"{path}: missing or malformed {key!r} section")
    return section


def _positive_int(section: dict[str, Any], key: str, path: Path) -> int:
    value = section.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ContractError(f"{path}: limits.{key} must be a positive whole number")
    return value


def _positive_number(section: dict[str, Any], key: str, path: Path) -> float:
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ContractError(f"{path}: limits.{key} must be a positive number")
    return float(value)
