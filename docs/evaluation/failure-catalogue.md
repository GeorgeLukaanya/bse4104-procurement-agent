# Failure Catalogue

| Field | Value |
|---|---|
| Week | 7 |
| Owner | Ainamani Jim Isaac |
| Due | 16 October 2026 |
| Status | Complete; all fixes re-tested; awaiting team review |
| Path | `docs/evaluation/failure-catalogue.md` |

## Brief requirement

Record at least five genuine failures, their expected and actual behaviour, impact, remediation,
and re-test evidence. Hypothetical risks are excluded.

## 1. Result

This catalogue records **nine genuine failures** found across the project. All **nine are fixed
and re-tested**. Earlier failures are included because Week 7 consolidates and re-tests the
project's observed failures; they do not all have to originate in Week 7.

The targeted regression passed **13/13 tests**. The FC-08 and FC-09 follow-up produced a
**10/10 uncached live extraction regression**, a **3/3 live scenario rerun**,
**28/28 client and timeout tests**, and **511/511 tests** across the full local suite. Original
failed observations remain in the evidence and were not overwritten.

## 2. Summary

| ID | Failure | Category | Severity | Status | Re-test |
|---|---|---|---|---|---|
| FC-01 | Malformed tool output was accepted | Tool contract | High | Fixed | PASS |
| FC-02 | Prompt and configuration versions differed | Evaluation integrity | High | Fixed | PASS |
| FC-03 | Missing or tampered quotations were reported as no quotations | Error handling | Medium | Fixed | PASS |
| FC-04 | An ambiguous date was converted into a definite date | Model extraction | Medium | Fixed | PASS |
| FC-05 | Re-running a completed review created a duplicate requisition | State management | High | Fixed | PASS |
| FC-06 | A missing exchange rate produced the wrong terminal outcome | Workflow | Medium | Fixed | PASS |
| FC-07 | A requisition could be compiled with no eligible supplier | Safety rule | High | Fixed | PASS |
| FC-08 | Source unit `each` was changed to `unit` | Model extraction | Medium | Fixed | PASS |
| FC-09 | Live model calls could exceed 30 seconds | Reliability | High | Fixed | PASS |

## 3. Failure records

### FC-01 Malformed tool output was accepted

- **Found:** Week 4 test FA-10.
- **Expected / actual:** Invalid output should be rejected, but the dispatcher returned
  `status: ok` for `{"unexpected": "shape"}`.
- **Impact / cause:** The agent could use invalid data because only tool inputs were validated.
- **Remediation:** Pull Request 64 added output-schema validation; invalid output is discarded
  with `OUTPUT_SCHEMA_INVALID`, and a missing schema fails closed.
- **Re-test:** `test_fa10_malformed_output_is_discarded` passed.
- **Evidence:** [Week 4 failure test](tool-failure-tests.md) and
  [`Failure-authorization-evidence.json`](../../evidence/evaluation/week-04/Failure-authorization-evidence.json).

### FC-02 Prompt and configuration versions differed

- **Found:** Week 5, after the prompt changed to v1.2 while runtime configuration stayed at v1.1.
- **Expected / actual:** All version references should agree, but the agreement test failed and
  cached results risked being attributed to the wrong prompt.
- **Impact / cause:** Evaluation comparisons became unreliable because the version was maintained
  in several places and only partly updated.
- **Remediation:** Pull Request 64 aligned the configuration and tests. Prompt v1.4 is now used
  consistently, and its version changes the cache fingerprint.
- **Re-test:** Version-agreement, cache-invalidation, and log-fingerprint tests passed.
- **Evidence:** [Week 5 report](../weekly-reports/week-05.md) and
  [prompt evaluation](prompt-evaluation.md).

### FC-03 Missing or tampered quotations were reported as no quotations

- **Found:** Week 5 failure/recovery trace review.
- **Expected / actual:** Missing and tampered files should produce `DATA_SOURCE_UNAVAILABLE` and
  `DATA_INTEGRITY_ERROR`; both were instead converted into an empty quotation list.
- **Impact / cause:** The officer received a misleading explanation because the planner caught
  every loading exception and returned an empty list.
- **Remediation:** Pull Request 66 preserved and reported the real loading error.
- **Re-test:** Missing-file, tampered-file, and CLI-reporting tests passed.
- **Evidence:** [Working agent documentation](../architecture/working-agent.md) and
  [failure/recovery trace](execution-traces.md#trace-4-failure-and-recovery).

### FC-04 Ambiguous date was converted into a definite date

- **Found:** Week 2 live prompt evaluation TC-07.
- **Expected / actual:** Ambiguous `10/11/2026` should produce `null` with a reason, but prompt
  v1.1 returned `2026-11-10` without a warning.
- **Impact / cause:** The agent could invent a validity date because the prompt requested ISO
  formatting without prohibiting resolution of ambiguous dates.
- **Remediation:** Prompt v1.2 introduced the ambiguity rule, retained in later versions.
- **Re-test:** The uncached TC-07 rerun and complete v1.3 regression returned `null` with an
  ambiguity explanation.
- **Evidence:** [`TC-07-retest.json`](../../evidence/evaluation/week-05-v1.3/TC-07-retest.json)
  and [prompt evaluation](prompt-evaluation.md).

### FC-05 Re-running a completed review created a duplicate requisition

- **Found:** Week 5 state and recovery review.
- **Expected / actual:** The same completed review should not create another requisition, but two
  identical confirmed runs created two requisitions and repeated earlier work.
- **Impact / cause:** Duplicate purchasing work was possible because run state was not persistent.
- **Remediation:** Pull Request 65 added checkpoints, deterministic run IDs, safe resume, and
  completed-run duplicate prevention.
- **Re-test:** Duplicate-prevention and resume-after-handoff tests passed.
- **Evidence:** [Working-memory demonstration](../architecture/working-memory.md) and
  [`04-rerun-no-duplicate.json`](../../evidence/traces/memory/04-rerun-no-duplicate.json).

### FC-06 Missing exchange rate produced the wrong terminal outcome

- **Found:** Week 7 scenario S-09.
- **Expected / actual:** The agent should ask the officer for a missing rate, but it stopped as
  `refused` and offered no way to supply one.
- **Impact / cause:** A valid foreign-currency review could not continue because
  `EXCHANGE_RATE_REQUIRED` was terminal.
- **Remediation:** Pull Request 73 added an `awaiting_human` handoff and `--exchange-rate`, then
  persists and applies the supplied rate.
- **Re-test:** Handoff, continuation, and CLI guidance tests passed; S-09 now passes.
- **Evidence:** [Scenario evaluation](scenarios.md#4-results) and
  [`scenario-results.json`](../../evidence/evaluation/week-07/scenario-results.json).

### FC-07 Requisition could be compiled with no eligible supplier

- **Found:** Week 7 scenario S-12.
- **Expected / actual:** The workflow should halt without an eligible offer, but could compile a
  requisition naming “no eligible supplier.”
- **Impact / cause:** This crossed a procurement safety boundary because compilation did not
  require an eligible ranked offer.
- **Remediation:** Pull Request 73 added a `MISSING_COMPONENT` handoff before compilation when the
  eligible comparison is empty.
- **Re-test:** `test_no_eligible_supplier_halts_compilation` passed; S-12 writes nothing.
- **Evidence:** [Scenario evaluation](scenarios.md#4-results) and
  [`scenario-results.json`](../../evidence/evaluation/week-07/scenario-results.json).

### FC-08 Source unit `each` was changed to `unit`

- **Found:** Week 5 prompt v1.3 regression and Week 7 live scenario S-41.
- **Expected / actual:** “Each chair” should produce `unit_of_measure: "each"`; Gemini returned
  `unit_of_measure: "unit"`.
- **Impact / cause:** The normalized record changed the supplier's price basis because the prompt
  did not make exact unit preservation explicit enough.
- **Remediation:** Prompt v1.4 requires preservation of the stated price basis, includes the exact
  “Each chair” case, forbids a default unit, and checks output against the source.
- **Re-test:** The uncached ten-case regression passed 10/10; TC-04 returned `each` in 6.2720 s.
  Independent live S-41 returned `each` in 5.9860 s.
- **Status:** **Fixed.**
- **Evidence:** [Remediation write-up](fc08-fc09-follow-up.md),
  [regression review](../../evidence/evaluation/week-07-fc08-fc09-v1.4/review-summary.json), and
  [S-41 output](../../evidence/evaluation/week-07-fc08-fc09-v1.4/live/S-41.json).

### FC-09 Live model calls exceeded the 30-second limit

- **Found:** Week 7 live scenarios S-41, S-44, and S-45.
- **Expected / actual:** Calls should remain within 30 seconds, but took 31.11, 83.31, and
  280.86 seconds.
- **Impact / cause:** Users could wait several minutes because retries had no enforced request
  deadline and the workflow timer could not interrupt an active request.
- **Remediation:** The shared client now gives each request its remaining budget, disables SDK
  retries, bounds application retries and backoff to 30 seconds overall, rejects late responses,
  and logs a structured `timeout` result.
- **Re-test:** S-41/S-44/S-45 passed in 5.9860/2.5054/25.1461 s. All 28 client and timeout tests
  passed, followed by all 511 tests in the full local suite.
- **Status:** **Fixed.**
- **Evidence:** [Remediation write-up](fc08-fc09-follow-up.md),
  [live scenario results](../../evidence/evaluation/week-07-fc08-fc09-v1.4/scenario-results.json),
  and [timeout tests](../../evidence/evaluation/week-07-fc08-fc09-v1.4/timeout-tests.txt).

## 4. Re-test record

The targeted run covered FC-01, FC-02, FC-03, FC-05, FC-06, and FC-07 and returned
**13 passed, 0 failed**. FC-04 is supported separately by two recorded uncached live passes.

The FC-08 and FC-09 follow-up returned:

- Uncached live extraction regression: **10 passed, 0 failed**.
- Live S-41/S-44/S-45 rerun: **3 passed, 0 failed, 0 safety violations**.
- Client and timeout tests: **28 passed, 0 failed**.
- Full local suite: **511 passed, 0 failed**.

The [initial follow-up run](../../evidence/evaluation/week-07-fc08-fc09-v1.4/initial-run/review-summary.json)
is retained. It scored 9/10 because TC-06 safely timed out at 30.0003 s; this led to the return
margin in the final implementation. Review and remote CI remain separate from local results.

## 5. Engineering conclusions

The catalogue shows that the system must validate both sides of every contract, preserve real
infrastructure errors, persist enough state for safe recovery, and bound model behaviour with
deterministic validation, human review, and explicit deadlines.

The catalogue exceeds the required five genuine failures and provides remediation and re-test
evidence for all nine. There are no open failures in this catalogue; normal residual risks such as
model variability still require monitoring and human review during Week 8 hardening.
