# Failure Catalogue

| Field | Value |
|---|---|
| Week | 7 |
| Owner | Ainamani Jim Isaac |
| Due | 16 October 2026 |
| Status | Complete for recorded failures; Week 7 scenario failures to be added |
| Path | `docs/evaluation/failure-catalogue.md` |

Reassigned from Lukaanya George to Ainamani Jim Isaac on 13 October 2026, in exchange for the
30+ scenario evaluation (#31). Sections 1–4 and 6–7 were drafted by Lukaanya George before the
reassignment; see issue #34.

## Brief requirement

At least five genuine failures with remediation and re-test evidence.

## Write-up

### 1. What this catalogue holds

**Twelve genuine failures: seven fixed and re-tested, five open.** A failure is catalogued only if
it was observed on this system: in a test, a recorded run or a review. A risk that might happen
is not a failure.

The catalogue is a file the test suite checks, not only this page:
[`evidence/evaluation/week-07/failure-catalogue.json`](../../evidence/evaluation/week-07/failure-catalogue.json).
`tests/test_failure_catalogue.py` fails the build if an entry points at a test that does not
exist or an evidence file that is missing, or if a fixed failure has no re-test. Section 6 shows
that check catching a deliberate break.

**Re-testing** is one command, with no API key and no network:

```bash
python tools/retest_failures.py
```

It runs every fixed failure's regression tests and records the outcome, with commit and date, in
[`retest-results.txt`](../../evidence/evaluation/week-07/retest-results.txt) and
[`retest-results.json`](../../evidence/evaluation/week-07/retest-results.json). Latest result:
**7 of 7 fixed failures PASS.**

**"Before" evidence.** Each failure has a record of the system actually failing. Five of those
records were made this week by running the pre-fix commit in a temporary `git worktree`; the
files are in [`week-07/before/`](../../evidence/evaluation/week-07/before/) and each names the
commit and command used. The other failures cite the evaluation or test that first found them.

### 2. Summary

| ID | Failure | Category | Severity | Status | Re-test |
|---|---|---|---|---|---|
| FC-01 | Malformed tool output relayed as `status: ok` | tool | high | fixed | 4/4 PASS |
| FC-02 | Prompt raised to v1.2 while the config stayed at v1.1 | evaluation integrity | high | fixed | 3/3 PASS |
| FC-03 | Offline demo served hand-written records to live runs | evaluation integrity | high | fixed | 3/3 PASS |
| FC-04 | Missing or tampered quotations file reported as "no quotations" | orchestration | medium | fixed | 3/3 PASS |
| FC-05 | Ambiguous date `10/11/2026` resolved instead of returned as null | model | medium | fixed | live re-test PASS; guard 1/1 PASS |
| FC-06 | Re-running a confirmed review compiled a second requisition | orchestration | high | fixed | 3/3 PASS |
| FC-07 | Agent report crashed on the default Windows console | portability | medium | fixed | 1/1 PASS |
| FC-08 | Unit `each` replaced with `unit` under prompt v1.3 (TC-04) | model | medium | open | — |
| FC-09 | Unrelated specifications kept for binding wire (RAG TC-02) | retrieval | low | open | — |
| FC-10 | Adjacent quotation-count band outranks the applicable one (RAG TC-10) | retrieval | medium | open | — |
| FC-11 | Foreign-currency clause cited on UGX-only items (RAG) | retrieval | low | open | — |
| FC-12 | Policy retrieval took 42.01 s against a 30 s ceiling | latency | medium | open | — |

### 3. Fixed failures

#### FC-01. Malformed tool output relayed as `status: ok`

- **Found:** 25 Sep, Week 4 failure test FA-10
  ([evidence](../../evidence/evaluation/week-04/Failure-authorization-evidence.json),
  [write-up](tool-failure-tests.md)).
- **Symptom:** a tool returning `{"unexpected": "shape"}` reached the caller as `ok`, so the agent
  could reason over data that broke its contract.
- **Root cause:** `dispatch.invoke` checked requests against their schemas but not responses,
  although catalogue section 9 required both.
- **Fix:** `343ed5f`, PR #64. Every response is checked against its output schema. A
  non-conforming one is discarded with `OUTPUT_SCHEMA_INVALID`, and a missing schema fails closed.
- **Re-test:** `test_fa10_malformed_output_is_discarded` and three companions. **PASS.**
- **Residual risk:** `create_requisition_draft` writes before its response is checked, so a bad
  draft response is reported as failed but the stored record remains.

#### FC-02. Prompt raised to v1.2 while the config stayed at v1.1

- **Found:** 6 Oct, Week 5 review. CI on `main` had been red since PR #62 merged on 2 Oct
  ([before](../../evidence/evaluation/week-07/before/FC-02-prompt-version.txt):
  `assert '1.2' == '1.1'`).
- **Symptom:** the cache key uses the config's version, so a run with the new prompt could be
  served a cached v1.1 answer and logged as v1.2. Results would be attributed to the wrong prompt.
- **Root cause:** the version was changed in one of two places, and the PR was merged while
  pytest failed.
- **Fix:** `a7a96de`, PR #64. Config, `.env.example` and the prompt document aligned, and the
  version tests read the version from one place, so a bump cannot half-land.
- **Re-test:** version agreement, cache invalidation on a version change, and run-log
  fingerprint. **PASS.**
- **Residual risk:** nothing technically blocks a merge while CI is red. It is a team rule.

#### FC-03. Offline demo served hand-written records to live runs

- **Found:** 23 Sep (demo rows in the evidence log, Week 4 change log), and 29 Sep (records in the
  real cache).
- **Symptom:** the [before run](../../evidence/evaluation/week-07/before/FC-03-demo-cache-contamination.txt)
  on `b1a6412` shows three things: the demo adds rows to `evidence/traces/extraction-runs.jsonl`;
  six files appear in `.cache/extractions`; and a later extraction, with the model backend set to
  fail if called, returns the demo's hand-written Nakawa record as `cache_hit: true` under the
  `gemini-3.1-flash-lite` fingerprint.
- **Root cause:** the cache key covers the document and configuration but not the backend, and
  the demo used the real cache and log.
- **Fix:** `4a8a3fc`, PR #59. The demo writes only to `var/offline-demo/`.
- **Re-test:** three `test_offline_demo.py` tests. **PASS.**
- **Residual risk:** machines that ran the demo earlier still hold contaminated cache entries
  until `rm -rf .cache/extractions`. The first six rows of `extraction-runs.jsonl` (13 Sep,
  latency 0.0551 s) are demo output and must not be cited as model evidence.

#### FC-04. Missing or tampered quotations file reported as "no quotations"

- **Found:** 6 Oct, Week 5 review
  ([before](../../evidence/evaluation/week-07/before/FC-04-swallowed-quotation-error.txt):
  `detail: No held quotations name AH-CM-001.`).
- **Root cause:** the planner wrapped the quotation load in `except Exception: return []`.
- **Fix:** `514b0d0`, PR #66 (Shakiran). The run stops with `DATA_SOURCE_UNAVAILABLE` or
  `DATA_INTEGRITY_ERROR` and the real cause.
- **Re-test:** missing file, tampered file, and the CLI report. **PASS.**
- **Residual risk:** the planner still reads the quotations file directly, outside `dispatch`
  and the tool trace.

#### FC-05. Ambiguous date resolved instead of returned as null (TC-07)

- **Found:** 13 Sep, Week 2 live prompt evaluation
  ([result](../../evidence/evaluation/week-02/TC-07-result.json)). Prompt v1.1 turned
  `10/11/2026` into `2026-11-10` and reported nothing missing.
- **Root cause:** rule 6 allowed rewriting dates without forbidding the resolution of a
  day/month order the document does not determine.
- **Fix:** prompt v1.2 (PR #62), then v1.3 (`e0ba3b0`, PR #69, Beingana).
- **Re-test:** live, on 9 Oct: the dedicated
  [TC-07 re-test](../../evidence/evaluation/week-05-v1.3/TC-07-retest.json) and the ten-case
  [regression](../../evidence/evaluation/week-05-v1.3/regression-results.json) both return null
  with an ambiguity reason. **PASS.** Live calls are not repeated here. Instead, a new offline
  guard, `test_ambiguous_date_rule_is_still_in_the_prompt`, fails if a future prompt drops the
  rule.
- **Residual risk:** two live passes, not a repeated-run reliability figure. The same v1.3
  regression introduced FC-08.

#### FC-06. Re-running a confirmed review compiled a second requisition

- **Found:** Week 5 review; Agent Task Contract gap 2, 1 Oct. The
  [before run](../../evidence/evaluation/week-07/before/FC-06-duplicate-requisition.txt) on
  `184f867` runs the same confirmed command twice and gets `REQ-2026-001` **and**
  `REQ-2026-002`, with every step repeated.
- **Root cause:** run state lasted one command, so nothing recorded that the review had already
  produced its requisition.
- **Fix:** `1697088`, PR #65. Checkpointed run state: a re-run resumes, reuses only results whose
  data is unchanged, keeps the iteration budget, and never compiles a second requisition
  ([write-up](../architecture/working-memory.md)).
- **Re-test:** no second requisition; resume after Gate 2; failure then recovery. **PASS.**
- **Residual risk:** `--fresh` deliberately starts a new run and can compile another requisition
  for the same review.

#### FC-07. Agent report crashed on the default Windows console

- **Found:** real runs on Windows, the team's platform (fix commit `6cba326`). The
  [before run](../../evidence/evaluation/week-07/before/FC-07-windows-console.txt) on `51b53e8`
  with a cp1252 console ends in `UnicodeEncodeError: … '→'`.
- **Root cause:** a `→` in console output. pytest captures output as UTF-8, so the suite never
  saw it.
- **Fix:** `6cba326`, PR #61 (Sekyeza). ASCII output, and a test that encodes the report as
  cp1252.
- **Re-test:** **PASS.**
- **Residual risk:** the other command-line tools are not yet tested under cp1252.

### 4. Open failures

Recorded so they are not lost. Each has an owner and a next step. None is fixed in this
deliverable.

| ID | Evidence | Owner | Next step |
|---|---|---|---|
| FC-08 | [v1.3 regression](../../evidence/evaluation/week-05-v1.3/regression-results.json): "Each chair" returned as unit `unit` | Beingana | Fix the unit-preservation wording, bump the prompt version, repeat the full ten-case regression |
| FC-09 | [RAG evaluation](rag-evaluation.md) F1 | Beingana | Raise the item cutoff or restrict item search by category; re-measure TC-02, TC-05, TC-06 |
| FC-10 | RAG evaluation F2 | Beingana | Choose the POL-001 band from `estimated_total` before search; keep `top_k` ≥ 5 until then |
| FC-11 | RAG evaluation F3 | Beingana | Cite POL-003-C01 only when a non-UGX figure is present; add a USD case |
| FC-12 | [Live run](../../evidence/traces/rag-weekly-reorder-run.txt), 42.01 s | Beingana | Measure latency over repeated runs in the Week 7 evaluation before changing Requirement 7.1 |

In every open retrieval failure, citation validation still withheld anything that was not
supplied. The errors are in precision, not fabrication.

### 5. Failures from the Week 7 scenario evaluation

*To be added from the 30+ scenario evaluation (#31) when its results are available.* Each
failure it finds becomes FC-13 onward, either fixed with a re-test or open with an owner, and
`tools/retest_failures.py` is run again.

### 6. Re-test record

From [`retest-results.txt`](../../evidence/evaluation/week-07/retest-results.txt):

```
FC-01  PASS  4/4 passed   Malformed tool output relayed as status ok
FC-02  PASS  3/3 passed   Prompt version raised to 1.2 while the config stayed at 1.1
FC-03  PASS  3/3 passed   Offline demo served hand-written records to live runs
FC-04  PASS  3/3 passed   Planner reported a missing or tampered quotations file as 'no quotations'
FC-05  PASS  1/1 passed   Ambiguous date 10/11/2026 resolved instead of returned as null
FC-06  PASS  3/3 passed   Re-running a confirmed review compiled a second requisition
FC-07  PASS  1/1 passed   Agent report crashed on the default Windows console
7/7 fixed failures re-tested PASS; 5 open.
```

**The catalogue check catches a broken catalogue.** Renaming one cited test and one evidence
file made `tests/test_failure_catalogue.py` fail on exactly those two entries
(`test_every_retest_names_a_real_test[…test_fa10_renamed_away]`,
`test_every_evidence_path_exists[FC-07]`). It passed again once they were restored.

### 7. Patterns

Four of the seven fixed failures had the same shape. These are the lessons for Week 8 hardening
and for the report.

1. **A change that lands in one place out of two** (FC-02, and the catalogue examples left at
   v1.0 in Week 4). Make one place authoritative and test the agreement.
2. **An exception that is caught too broadly** (FC-04). Every `except Exception` should name
   what it expects and report the cause.
3. **Shared state between a demonstration and the real system** (FC-03). It corrupted the
   evaluation evidence itself. Demonstrations write to their own paths.
4. **The test environment is not the user's environment** (FC-07, and FC-02 merged while CI was
   red). A green local run under UTF-8 proved nothing about a Windows console.

Three of the seven (FC-02, FC-03, FC-05) are about **trusting evaluation results**, not about
procurement behaviour. Because of them, the Week 7 evaluation needs to record, for every
model-backed result, the prompt version and `cache_hit` alongside it.
