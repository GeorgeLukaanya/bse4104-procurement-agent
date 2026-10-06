"""Shared envelope, roles and error codes for every tool.

The vocabulary follows tool-catalogue.md section 2. Status strings match
``ItemOutcome.status`` in the RAG pipeline rather than introducing an enum
the package does not use anywhere else.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

TOOL_VERSION = "1.0"

STATUS_OK = "ok"
STATUS_NO_RESULT = "no_result"
STATUS_INVALID_INPUT = "invalid_input"
STATUS_UNAUTHORIZED = "unauthorized"
STATUS_UNAVAILABLE = "unavailable"
STATUS_FAILED = "failed"

STATUSES = (
    STATUS_OK,
    STATUS_NO_RESULT,
    STATUS_INVALID_INPUT,
    STATUS_UNAUTHORIZED,
    STATUS_UNAVAILABLE,
    STATUS_FAILED,
)

CODE_MISSING_PARAMETER = "MISSING_PARAMETER"
CODE_INVALID_PARAMETER = "INVALID_PARAMETER"
CODE_UNKNOWN_SKU = "UNKNOWN_SKU"
CODE_UNKNOWN_SUPPLIER = "UNKNOWN_SUPPLIER"
CODE_UNAUTHORIZED_ROLE = "UNAUTHORIZED_ROLE"
CODE_TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"
CODE_DATA_SOURCE_UNAVAILABLE = "DATA_SOURCE_UNAVAILABLE"
CODE_DATA_INTEGRITY_ERROR = "DATA_INTEGRITY_ERROR"
CODE_INSUFFICIENT_QUOTATIONS = "INSUFFICIENT_QUOTATIONS"
CODE_INCOMPARABLE_QUOTATION = "INCOMPARABLE_QUOTATION"
CODE_EXCHANGE_RATE_REQUIRED = "EXCHANGE_RATE_REQUIRED"
CODE_MISSING_COMPONENT = "MISSING_COMPONENT"
CODE_FORBIDDEN_TRANSITION = "FORBIDDEN_TRANSITION"
CODE_OUTPUT_SCHEMA_INVALID = "OUTPUT_SCHEMA_INVALID"

ROLE_OFFICER = "PROCUREMENT_OFFICER"
ROLE_MANAGER = "PROCUREMENT_MANAGER"
ROLE_AGENT = "AGENT"
ROLES = (ROLE_OFFICER, ROLE_MANAGER, ROLE_AGENT)

# Read-only tools. create_requisition_draft is the exception: officer only,
# and an agent call executes only after the officer confirms it.
READ_ONLY_TOOLS = (
    "check_reorder_need",
    "check_supplier_eligibility",
    "compare_quotations",
)
WRITE_TOOLS = ("create_requisition_draft",)
ALL_TOOLS = READ_ONLY_TOOLS + WRITE_TOOLS

COMPONENT = "TOOL"

CATEGORIES = (
    "cement and masonry",
    "hand tools and safety equipment",
    "electrical and plumbing",
)
LOCATIONS = ("Nakawa Main Store", "Kireka Branch")

SKU_PATTERN = r"^AH-[A-Z]{2}-[0-9]{3}$"
SUPPLIER_ID_PATTERN = r"^SUP-[0-9]{3}$"
QUOTATION_ID_PATTERN = r"^QT-[0-9]{3}$"
ISO_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
CLAUSE_ID_PATTERN = r"^[A-Z]+-[0-9]{3}-C[0-9]{2}$"

Clock = Callable[[], datetime]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(moment: datetime) -> str:
    """UTC timestamp with a trailing Z, matching the catalogue examples."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def error(code: str, detail: str, field: str | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"code": code, "detail": detail}
    if field is not None:
        entry["field"] = field
    return entry


def envelope(
    tool: str,
    status: str,
    *,
    data: Mapping[str, Any] | None,
    errors: Sequence[Mapping[str, Any]],
    caller_role: str,
    latency_ms: int,
    data_fingerprint: str | None,
    called_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "tool": tool,
        "tool_version": TOOL_VERSION,
        "status": status,
        "data": None if data is None else dict(data),
        "errors": [dict(item) for item in errors],
        "trace": {
            "called_at": isoformat_z(called_at or utcnow()),
            "caller_role": caller_role,
            "latency_ms": max(0, int(latency_ms)),
            "data_fingerprint": data_fingerprint,
        },
    }
