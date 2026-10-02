# Failure and Authorization Test Evidence

| Field  | Value                                   |
| ------ | --------------------------------------- |
| Week   | 4                                       |
| Owner  | Beingana Jim Junior                     |
| Due    | 25 September 2026                       |
| Status | Completed with one defect identified    |
| Path   | `docs/evaluation/tool-failure-tests.md` |

## Brief requirement

Test missing parameters, unauthorized requests, unavailable services and unexpected tool responses. Record expected vs actual behaviour. Human approval must sit in front of any higher-impact action.

## Write-up

### 1. Purpose

This test evidence checks that the Week 4 tools fail safely and respect the authorization boundaries defined by the project. The focus is on invalid input, unavailable data, role restrictions, the tool allow-list, the human confirmation gate, forbidden requisition transitions, and malformed tool responses.

The tests were run against the submitted repository using synthetic project data only. No live supplier, payment, ERP, or Gemini service was required for these checks.

### 2. Test execution

Environment used:

- Python 3.13.5
- pytest 9.0.2

The existing tool and authorization tests were first run together:

```bash
python -m pytest -v \
  tests/test_authorization_tools.py \
  tests/test_tools_reorder.py \
  tests/test_tools_eligibility.py \
  tests/test_tools_compare.py \
  tests/test_tools_draft.py \
  tests/test_tools_cli.py
```

Result: **35 passed, 0 failed**.

The full repository test suite was also run as a regression check. Result: **258 passed, 6 skipped**. The skipped tests require optional Gemini or RAG dependencies and are not part of the Week 4 tool/authorization checks.

### 3. Focused failure and authorization cases

| ID    | Scenario                                                            | Expected behaviour                                           | Actual behaviour                                                                           | Result   |
| ----- | ------------------------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------ | -------- |
| FA-01 | `check_reorder_need` called without `review_date`                   | Reject request with `MISSING_PARAMETER`                      | Returned `invalid_input` and identified `review_date` as missing                           | PASS     |
| FA-02 | Inventory data source unavailable                                   | Return `DATA_SOURCE_UNAVAILABLE` and no data                 | Returned `unavailable`, no inventory data was returned                                     | PASS     |
| FA-03 | Procurement Manager attempts to create a requisition draft          | Reject because the manager may not prepare a requisition     | Returned `unauthorized / UNAUTHORIZED_ROLE`; no draft file was created                     | PASS     |
| FA-04 | Agent attempts to create a requisition without officer confirmation | Reject the side effect                                       | Returned `unauthorized / UNAUTHORIZED_ROLE`; nothing was written                           | PASS     |
| FA-05 | Agent proposes draft creation after officer confirmation            | Execute under the officer identity and create only a `DRAFT` | Returned `ok`; caller recorded as `PROCUREMENT_OFFICER`; stored status remained `DRAFT`    | PASS     |
| FA-06 | Tool invoked when not on the current orchestration allow-list       | Reject before the tool executes                              | Returned `unauthorized / TOOL_NOT_ALLOWED`                                                 | PASS     |
| FA-07 | Attempt to invoke an `approve_requisition` tool                     | Reject because no such agent tool exists                     | Returned `unauthorized / TOOL_NOT_ALLOWED`                                                 | PASS     |
| FA-08 | Draft creation requests status `APPROVED`                           | Reject any programmatic transition beyond `DRAFT`            | Returned `invalid_input / FORBIDDEN_TRANSITION`; nothing was written                       | PASS     |
| FA-09 | Request payload tries to supply a different `caller_role`           | Reject role spoofing; retain authenticated role              | `caller_role` was rejected as an unexpected field and trace remained `PROCUREMENT_OFFICER` | PASS     |
| FA-10 | Internal tool returns a malformed/unexpected output object          | Reject the malformed result before downstream use            | Dispatcher returned `status: ok` with the malformed data                                   | **FAIL** |

**Focused result: 9 passed, 1 failed.**

### 4. Authorization evidence

The current implementation correctly enforces the main Week 4 authorization boundaries:

- `caller_role` is injected by the orchestration layer rather than accepted from a model-facing payload.
- Read-only tools are controlled by a static allow-list.
- `create_requisition_draft` is the only current tool with a write side effect.
- The Procurement Manager cannot create a requisition draft.
- An agent-proposed draft is not executed until the Procurement Officer confirms it.
- Even after confirmation, the created requisition remains in `DRAFT` status.
- There is no agent tool for approving a requisition, issuing a purchase order, contacting a supplier, or making a payment.

These controls provide a clear human gate before the current side effect and prevent the agent from crossing the project's procurement authority boundary.

### 5. Failure identified: malformed tool output is not validated

FA-10 intentionally simulated an internal tool returning the following unexpected data:

```json
{
  "status": "ok",
  "data": {
    "unexpected": "shape"
  },
  "errors": []
}
```

The orchestration layer accepted and returned this result instead of checking it against the declared output schema for `check_reorder_need`.

This is a genuine Week 4 failure because an unexpected tool response could be treated as valid downstream data. Input schemas are enforced, but there is currently no equivalent output-schema validation at the dispatcher boundary.

**Recommended remediation:** validate each tool's returned `data` against its declared output schema before returning it to the caller. A non-conforming response should be converted to a safe failure with no usable data, then recorded in the tool trace. FA-10 should be re-run after that change.

### 6. Conclusion

The Week 4 implementation shows strong input validation and authorization enforcement. All existing targeted tool tests passed, and nine of the ten focused failure/authorization scenarios behaved as expected. The testing also exposed one concrete reliability gap: malformed tool output is not currently rejected by the orchestration layer.

This defect should be fixed before the Week 5 bounded agent loop depends on tool results, because the agent should never reason over a tool response that has not been validated against its contract.

## Evidence

- `evidence/evaluation/week-04/Failure-authorization-evidence.json` — actual results for FA-01 to FA-10.
