"""Orchestration layer: inject role, enforce the allow-list, call one tool.

The model never calls a tool. This module is the only application entry
point. ``caller_role`` is taken from the authenticated session, not from
the payload. A name that appears inside a quotation matches nothing.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

from .. import guards
from . import compare as compare_mod
from . import draft as draft_mod
from . import eligibility as eligibility_mod
from . import output_schema
from . import reorder as reorder_mod
from .contract import (
    ALL_TOOLS,
    CODE_OUTPUT_SCHEMA_INVALID,
    CODE_TOOL_NOT_ALLOWED,
    CODE_UNAUTHORIZED_ROLE,
    ROLE_AGENT,
    ROLE_MANAGER,
    ROLE_OFFICER,
    ROLES,
    STATUS_FAILED,
    STATUS_INVALID_INPUT,
    STATUS_UNAUTHORIZED,
    envelope,
    error,
    utcnow,
)
from .trace import ToolLog
from .validate import (
    validate_compare_input,
    validate_draft_input,
    validate_eligibility_input,
    validate_reorder_input,
)

VALIDATORS = {
    "check_reorder_need": validate_reorder_input,
    "check_supplier_eligibility": validate_eligibility_input,
    "compare_quotations": validate_compare_input,
    "create_requisition_draft": validate_draft_input,
}

TOOLS = tuple(ALL_TOOLS)

# A tool is reachable only from the static list for the current step.
# Until Week 5 owns a state machine, the CLI passes the full catalogue for
# an officer session and the tests pass a step list explicitly.
DEFAULT_ALLOW_LIST = ALL_TOOLS


def invoke(
    tool_name: str,
    payload: Mapping[str, Any] | None,
    *,
    caller_role: str,
    allowed_tools: Sequence[str] | None = None,
    officer_confirmed: bool = False,
    inventory_path: str | None = None,
    suppliers_path: str | None = None,
    quotations_path: str | None = None,
    register_path: str | None = None,
    requisition_store: str | None = None,
    corpus_dir: str | None = None,
    run_log: str | None = None,
    clock: Callable[[], datetime] | None = None,
    record_trace: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    called_at = (clock or utcnow)()
    allow = tuple(allowed_tools) if allowed_tools is not None else DEFAULT_ALLOW_LIST
    request = dict(payload or {})

    def finish(
        status: str,
        data: Mapping[str, Any] | None,
        errors: Sequence[Mapping[str, Any]],
        fingerprint: str | None,
        role: str = caller_role,
    ) -> dict[str, Any]:
        latency_ms = int(round((time.perf_counter() - started) * 1000))
        result = envelope(
            tool_name if tool_name in ALL_TOOLS else tool_name,
            status,
            data=data,
            errors=errors,
            caller_role=role,
            latency_ms=latency_ms,
            data_fingerprint=fingerprint,
            called_at=called_at,
        )
        if data is not None:
            findings = guards.scan(data)
            if findings:
                result["data"] = guards.suppress(dict(data), findings)
        if record_trace:
            ToolLog(run_log).append(result)
        return result

    if caller_role not in ROLES:
        return finish(
            STATUS_UNAUTHORIZED,
            None,
            [
                error(
                    CODE_UNAUTHORIZED_ROLE,
                    f"{caller_role!r} is not a seeded role.",
                )
            ],
            None,
        )

    if tool_name not in ALL_TOOLS:
        return finish(
            STATUS_UNAUTHORIZED,
            None,
            [
                error(
                    CODE_TOOL_NOT_ALLOWED,
                    f"{tool_name} is not on the tool allow-list.",
                )
            ],
            None,
        )

    if tool_name not in allow:
        return finish(
            STATUS_UNAUTHORIZED,
            None,
            [
                error(
                    CODE_TOOL_NOT_ALLOWED,
                    f"{tool_name} is not on the orchestration allow-list for this step.",
                )
            ],
            None,
        )

    if tool_name == "create_requisition_draft":
        if caller_role == ROLE_MANAGER:
            return finish(
                STATUS_UNAUTHORIZED,
                None,
                [
                    error(
                        CODE_UNAUTHORIZED_ROLE,
                        "PROCUREMENT_MANAGER may not create a requisition. "
                        "POL-004-C03 separates preparation from approval. Nothing was written.",
                    )
                ],
                None,
            )
        if caller_role == ROLE_AGENT and not officer_confirmed:
            return finish(
                STATUS_UNAUTHORIZED,
                None,
                [
                    error(
                        CODE_UNAUTHORIZED_ROLE,
                        "AGENT may propose create_requisition_draft but the call "
                        "executes only after the officer confirms it. Requirement 9.1. "
                        "Nothing was written.",
                    )
                ],
                None,
            )
        # Confirmed agent call executes under the officer's identity.
        if caller_role == ROLE_AGENT and officer_confirmed:
            caller_role = ROLE_OFFICER

    validator = VALIDATORS[tool_name]
    input_errors = validator(request)
    if input_errors:
        return finish(STATUS_INVALID_INPUT, None, input_errors, None, role=caller_role)

    if tool_name == "check_reorder_need":
        status, data, errors, fingerprint = reorder_mod.check_reorder_need(
            request,
            inventory_path=inventory_path,
            register_path=register_path,
        )
    elif tool_name == "check_supplier_eligibility":
        status, data, errors, fingerprint = eligibility_mod.check_supplier_eligibility(
            request,
            suppliers_path=suppliers_path,
            quotations_path=quotations_path,
            register_path=register_path,
        )
    elif tool_name == "compare_quotations":
        status, data, errors, fingerprint = compare_mod.compare_quotations(
            request,
            inventory_path=inventory_path,
            quotations_path=quotations_path,
            suppliers_path=suppliers_path,
            register_path=register_path,
        )
    else:
        status, data, errors, fingerprint = draft_mod.create_requisition_draft(
            request,
            store_path=requisition_store,
            corpus_dir=corpus_dir,
            now=called_at,
        )

    # FA-10: the response is checked against the tool's output schema before
    # anyone sees it. A non-conforming result is discarded, not relayed, and
    # the step fails visibly (tool-catalogue section 9). A schema that cannot
    # be loaded fails closed for the same reason.
    candidate = envelope(
        tool_name,
        status,
        data=data,
        errors=errors,
        caller_role=caller_role,
        latency_ms=0,
        data_fingerprint=fingerprint,
        called_at=called_at,
    )
    try:
        problems = output_schema.check(tool_name, candidate)
    except output_schema.SchemaUnavailable as exc:
        problems = [f"output schema unavailable: {exc}"]
    if problems:
        shown = "; ".join(problems[:5])
        more = f" (+{len(problems) - 5} more)" if len(problems) > 5 else ""
        return finish(
            STATUS_FAILED,
            None,
            [
                error(
                    CODE_OUTPUT_SCHEMA_INVALID,
                    f"{tool_name} returned a response that does not conform to its "
                    f"output schema; it was discarded. {shown}{more}",
                )
            ],
            None,
            role=caller_role,
        )
    return finish(status, data, errors, fingerprint, role=caller_role)
