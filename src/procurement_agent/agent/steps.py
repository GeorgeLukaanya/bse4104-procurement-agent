"""Step allow-lists and stop reasons for the bounded agent loop."""

from __future__ import annotations

# Charter §6 steps that this week can actually invoke as catalogue tools.
# Conversion and extraction already have their own CLIs; policy retrieval is
# not a catalogue tool (tool-catalogue.md §1).
STEP_SCAN = "scan"
STEP_ELIGIBILITY = "eligibility"
STEP_COMPARE = "compare"
STEP_DRAFT = "draft"

STEP_ORDER = (STEP_SCAN, STEP_ELIGIBILITY, STEP_COMPARE, STEP_DRAFT)

ALLOW_LIST = {
    STEP_SCAN: ("check_reorder_need",),
    STEP_ELIGIBILITY: ("check_supplier_eligibility",),
    STEP_COMPARE: ("compare_quotations",),
    STEP_DRAFT: ("create_requisition_draft",),
}

STOP_COMPLETED = "completed"
STOP_NO_REORDER = "no_reorder_required"
STOP_AWAITING_HUMAN = "awaiting_human"
STOP_MAX_ITERATIONS = "max_iterations"
STOP_TIMEOUT = "timeout"
STOP_UNAUTHORIZED = "unauthorized"
STOP_FAILED = "failed"
STOP_REFUSED = "refused"

DEFAULT_MAX_ITERATIONS = 6
DEFAULT_TIMEOUT_S = 120.0
