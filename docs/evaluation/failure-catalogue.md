# Failure Catalogue

| Field | Value |
|---|---|
| Week | 7 |
| Owner | Ainamani Jim Isaac |
| Due | 16 October 2026 |
| Status | Complete; awaiting team review |
| Path | `docs/evaluation/failure-catalogue.md` |

## Brief requirement

Record at least five genuine failures, the expected and actual behaviour, their impact,
remediation, and re-test evidence. A failure is included only when it was observed in a recorded
evaluation, test, trace, or review; hypothetical risks are excluded.

## 1. Result

This catalogue records **nine genuine failures** found across the project: **seven fixed and
re-tested** and **two still open**. The catalogue uses failures from earlier weeks because Week 7
is the consolidation and re-test stage, not a requirement that every failure must first appear in
Week 7.

The latest targeted offline re-test was run on 16 October 2026 against the current branch. All
**13 selected regression tests passed**. The ambiguous-date failure also has two recorded live
Gemini re-tests under prompt v1.3. Open model failures are not presented as fixed.

## 2. Summary

| ID | Failure | Category | Severity | Status | Re-test |
|---|---|---|---|---|---|
| FC-01 | Malformed tool output was accepted as valid | Tool contract | High | Fixed | PASS |
| FC-02 | Prompt and configuration versions became inconsistent | Evaluation integrity | High | Fixed | PASS |
| FC-03 | Missing or tampered quotation data was reported as no quotations | Error handling | Medium | Fixed | PASS |
| FC-04 | An ambiguous date was converted into a definite date | Model extraction | Medium | Fixed | PASS |
| FC-05 | Re-running a completed review created a duplicate requisition | State management | High | Fixed | PASS |
| FC-06 | A missing exchange rate produced the wrong terminal outcome | Workflow | Medium | Fixed | PASS |
| FC-07 | A requisition could be compiled when no supplier was eligible | Safety rule | High | Fixed | PASS |
| FC-08 | The source unit `each` is changed to `unit` | Model extraction | Medium | Open | Still failing |
| FC-09 | Live model calls can exceed 30 seconds with no per-call timeout | Reliability | High | Open | Still failing |

## 3. Fixed failures and re-tests

### FC-01 Malformed tool output was accepted as valid

- **Found:** Week 4 failure and authorization test FA-10.
- **Expected:** A tool response that does not match its output schema must be rejected before the
  agent can use it.
- **Actual:** The dispatcher returned `status: ok` for `{"unexpected": "shape"}`.
- **Impact:** The agent could reason over invalid data and make later decisions on a broken tool
  contract.
- **Cause:** Requests were checked against input schemas, but tool responses were not checked
  against output schemas.
- **Remediation:** Pull Request 64 added output-schema validation in
  `src/procurement_agent/tools/output_schema.py`. Invalid output is discarded with
  `OUTPUT_SCHEMA_INVALID`, and a missing output schema fails closed.
- **Re-test:** `tests/test_tools_output_schema.py::test_fa10_malformed_output_is_discarded`
  passed on 16 October 2026.
- **Evidence:** [Week 4 failure test](tool-failure-tests.md) and
  [`Failure-authorization-evidence.json`](../../evidence/evaluation/week-04/Failure-authorization-evidence.json).

### FC-02 Prompt and configuration versions became inconsistent

- **Found:** Week 5 review after the extraction prompt was raised to v1.2 while the runtime
  configuration remained at v1.1.
- **Expected:** The prompt, configuration, cache key, environment example, and run log should
  identify the same prompt version.
- **Actual:** The mismatch caused a failing version-agreement test and risked attributing a cached
  answer to the wrong prompt.
- **Impact:** Evaluation evidence could be labelled with the wrong prompt version, making model
  comparisons unreliable.
- **Cause:** The version was maintained in more than one place and only one value was changed.
- **Remediation:** Pull Request 64 aligned the configuration and tests. Prompt v1.3 is now used
  consistently, and cache fingerprints change when the prompt version changes.
- **Re-test:** The prompt/config agreement, cache invalidation, and run-log fingerprint tests all
  passed on 16 October 2026.
- **Evidence:** [Week 5 progress report](../weekly-reports/week-05.md) and
  [prompt evaluation](prompt-evaluation.md).

### FC-03 Missing or tampered quotations were reported as no quotations

- **Found:** Week 5 review while preparing failure and recovery traces.
- **Expected:** A missing file should stop with `DATA_SOURCE_UNAVAILABLE`; a checksum mismatch
  should stop with `DATA_INTEGRITY_ERROR`.
- **Actual:** Both conditions were reduced to an empty list and reported as though no quotation
  named the requested item.
- **Impact:** The officer received the wrong explanation and could not distinguish absent data
  from a legitimate empty result.
- **Cause:** The planner caught every quotation-loading exception and returned an empty list.
- **Remediation:** Pull Request 66 preserved and reported the actual loading error instead of
  replacing it with an empty result.
- **Re-test:** The missing-file, tampered-file, and CLI-reporting tests all passed on
  16 October 2026.
- **Evidence:** [Working agent documentation](../architecture/working-agent.md) and the
  [failure/recovery trace](execution-traces.md#trace-4-failure-and-recovery).

### FC-04 Ambiguous date was converted into a definite date

- **Found:** Week 2 live prompt evaluation, TC-07.
- **Expected:** `10/11/2026` should be returned as `null` with a reason because the source does not
  establish whether the month or day comes first.
- **Actual:** Prompt v1.1 returned `2026-11-10` and reported no missing field.
- **Impact:** The system could silently invent a quotation-validity date and treat an expired or
  invalid quotation as usable.
- **Cause:** The prompt required ISO date formatting but did not forbid resolving ambiguous
  numeric dates.
- **Remediation:** Prompt v1.2 introduced an ambiguity rule; v1.3 retained and clarified it.
- **Re-test:** A dedicated uncached live TC-07 re-test and the complete v1.3 regression both
  returned `null` with an ambiguity explanation. **PASS.**
- **Evidence:** [`TC-07-retest.json`](../../evidence/evaluation/week-05-v1.3/TC-07-retest.json),
  [`regression-results.json`](../../evidence/evaluation/week-05-v1.3/regression-results.json),
  and [prompt evaluation](prompt-evaluation.md).

### FC-05 Re-running a completed review created a duplicate requisition

- **Found:** Week 5 review against the state and recovery requirements.
- **Expected:** Re-running the same completed procurement review must not create another
  requisition.
- **Actual:** Before persistent state was added, two identical confirmed runs created
  `REQ-2026-001` and `REQ-2026-002` and repeated every earlier step.
- **Impact:** Duplicate requisitions could create duplicate work or lead to duplicate purchasing
  if a human later submitted both records.
- **Cause:** Run state existed only for one command and did not record that the review had already
  produced its draft.
- **Remediation:** Pull Request 65 added checkpointed run state, deterministic run identifiers,
  source-aware resume, and completed-run duplicate prevention.
- **Re-test:** Completed-run duplicate prevention and resume-after-handoff tests passed on
  16 October 2026.
- **Evidence:** [Working-memory demonstration](../architecture/working-memory.md) and
  [`04-rerun-no-duplicate.json`](../../evidence/traces/memory/04-rerun-no-duplicate.json).

### FC-06 Missing exchange rate produced the wrong terminal outcome

- **Found:** Week 7 scenario S-09.
- **Expected:** When a non-UGX quotation has no exchange rate, the agent should pause, explain
  that a rate is required, and let the officer provide one.
- **Actual:** The original scenario stopped as `refused`, and the command line had no way to
  supply the missing rate.
- **Impact:** A valid foreign-currency procurement review could not continue even with authorized
  human input.
- **Cause:** The workflow treated `EXCHANGE_RATE_REQUIRED` as terminal and did not carry an
  officer-provided rate through state and comparison.
- **Remediation:** Pull Request 73 added an `awaiting_human` hand-off and the `--exchange-rate`
  input, persists the rate in state, and resumes comparison safely.
- **Re-test:** The missing-rate hand-off, supplied-rate continuation, and CLI guidance tests all
  passed on 16 October 2026. S-09 now passes.
- **Evidence:** [Scenario evaluation](scenarios.md#4-results) and
  [`scenario-results.json`](../../evidence/evaluation/week-07/scenario-results.json).

### FC-07 Requisition could be compiled when no supplier was eligible

- **Found:** Week 7 scenario S-12.
- **Expected:** Requirement 9.4 requires the workflow to halt when no eligible offer remains,
  even if confirmation flags are supplied.
- **Actual:** The original workflow could compile a requisition whose supplier was recorded as
  “no eligible supplier.”
- **Impact:** This crossed a core procurement safety boundary by preparing a transaction with no
  eligible supplier.
- **Cause:** The planner reached draft compilation without checking that the comparison contained
  an eligible ranked offer.
- **Remediation:** Pull Request 73 added a `MISSING_COMPONENT` hand-off before draft compilation
  when the eligible comparison is empty.
- **Re-test:** `tests/test_agent_workflow.py::test_no_eligible_supplier_halts_compilation` passed
  on 16 October 2026. S-12 now passes and nothing is written.
- **Evidence:** [Scenario evaluation](scenarios.md#4-results) and
  [`scenario-results.json`](../../evidence/evaluation/week-07/scenario-results.json).

## 4. Open failures

### FC-08 Source unit `each` is changed to `unit`

- **Found:** Week 5 prompt v1.3 regression and reproduced by Week 7 live scenario S-41.
- **Expected:** The phrase “Each chair” should produce `unit_of_measure: "each"`.
- **Actual:** Gemini returned `unit_of_measure: "unit"`.
- **Impact:** The normalized record differs from the supplier's quotation. Unit-basis changes can
  affect comparison, ordering, and audit accuracy.
- **Current control:** A Procurement Officer reviews extracted quotation data before later gates.
- **Required remediation:** Strengthen the unit-preservation instruction or add deterministic
  source-to-output validation, bump the prompt version, and repeat the full ten-case live
  regression.
- **Status:** **Open.** It must not be marked fixed until the live regression preserves `each`.
- **Evidence:** [`S-41.json`](../../evidence/evaluation/week-07/live/S-41.json) and the
  [v1.3 prompt evaluation](prompt-evaluation.md#week-5-review-follow-up--9-october-2026-v13).

### FC-09 Live model calls exceed the 30-second limit

- **Found:** Week 7 live scenarios S-41, S-44, and S-45.
- **Expected:** Requirement 7.1 sets a maximum of 30 seconds for a model call.
- **Actual:** The calls took 31.11, 83.31, and 280.86 seconds. S-45 was one attempt lasting about
  281 seconds.
- **Impact:** A user can wait several minutes without control returning, and the agent's
  120-second workflow budget cannot stop a model call that is already in progress.
- **Cause:** The extraction client retries timeout errors but does not enforce a timeout on each
  network call. The agent timer is checked only between iterations.
- **Required remediation:** Add a per-call timeout to the Gemini client, keep retry behaviour
  inside the total request budget, return a structured timeout failure, and re-run the three
  live scenarios plus timeout unit tests.
- **Status:** **Open.** No code fix or passing re-test exists yet.
- **Evidence:** [Scenario evaluation](scenarios.md#6-failures-found),
  [`S-41.json`](../../evidence/evaluation/week-07/live/S-41.json),
  [`S-44.json`](../../evidence/evaluation/week-07/live/S-44.json), and
  [`S-45.json`](../../evidence/evaluation/week-07/live/S-45.json).

## 5. Re-test record

The following targeted command was run on 16 October 2026 using the project virtual environment:

```bash
.venv/bin/python -m pytest -q \
  tests/test_tools_output_schema.py::test_fa10_malformed_output_is_discarded \
  tests/test_config_and_prompts.py::test_prompt_version_matches_the_config \
  tests/test_cache.py::test_changing_the_prompt_version_invalidates_the_cache \
  tests/test_runlog.py::test_every_call_is_written_with_its_configuration_fingerprint \
  tests/test_agent_workflow.py::test_missing_quotations_file_is_unavailable \
  tests/test_agent_workflow.py::test_tampered_quotations_file_is_integrity_failure \
  tests/test_agent_cli.py::test_cli_missing_quotations_reports_unavailable \
  tests/test_agent_checkpoint.py::test_a_completed_run_never_compiles_a_second_requisition \
  tests/test_agent_checkpoint.py::test_handoff_then_confirm_resumes_without_repeating_reads \
  tests/test_agent_workflow.py::test_usd_quote_without_a_rate_hands_off \
  tests/test_agent_workflow.py::test_a_disclosed_rate_is_applied_and_the_run_continues \
  tests/test_agent_cli.py::test_cli_missing_exchange_rate_asks_for_one \
  tests/test_agent_workflow.py::test_no_eligible_supplier_halts_compilation
```

Result: **13 passed, 0 failed**. FC-04's remediation is supported separately by its two recorded
uncached live passes. FC-08 and FC-09 remain open and were not converted into artificial passes.

## 6. Engineering conclusions

The failures show four recurring lessons:

1. Validate both sides of every contract: inputs and outputs.
2. Do not convert infrastructure errors into legitimate empty business results.
3. Persist enough workflow state to prevent duplicate side effects and support safe recovery.
4. Keep model behaviour bounded by deterministic validation, human review, and explicit timeouts.

The catalogue exceeds the required five genuine failures and includes remediation and re-test
evidence for every entry marked fixed. Remaining failures are visible, assigned a concrete next
step, and carried into Week 8 hardening.
