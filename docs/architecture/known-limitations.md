# Hardening and Known Limitations

| Field | Value |
|---|---|
| Week | 8 |
| Owner | Beingana Jim Junior |
| Due | 23 October 2026 |
| Status | Complete locally; awaiting team review |
| Reviewed | 20 October 2026 |
| Path | `docs/architecture/known-limitations.md` |

## Brief requirement

Review requirements, architecture, model/prompt behaviour, RAG, tools, agent limits, memory, tests, security and documentation. Record critical defects fixed and known limitations that remain.

## 1. Hardening result

Four high-impact defects were reproduced and fixed during this review: a completed review
could create another draft after its inputs changed; an unknown role could access or replace
its checkpoint; non-finite numbers could pass validation; and an unavailable output schema
could be discovered after a requisition had already been written.

The complete offline suite passed **541 tests**, including **30 new regression cases**.
The scenario rerun passed **37/37 offline scenarios**, with **0 recorded safety violations**;
the eight live scenarios were not rerun. Bandit passed at the repository's medium-and-above
severity threshold. These results support a supervised demonstration using synthetic data.
They do not establish readiness for real procurement or multiple concurrent users.

This review covers the local changes on top of base commit `f13f2be`, not a tagged release
or a remote CI run. The [verification record](../../evidence/evaluation/week-08-hardening/verification.json)
records the environment, commands and file hashes. Release tagging and the
[Week 8 team report](../weekly-reports/week-08.md) remain separate deliverables.

## 2. Critical defects fixed

All four records below describe reproduced defects, not hypothetical risks. The earlier
[failure catalogue](../evaluation/failure-catalogue.md) retains FC-01 to FC-09 and their
original evidence; these Week 8 identifiers are separate.

| ID / severity | Trigger and observed failure | Fix and verified result |
|---|---|---|
| W8-01 / High | Complete a confirmed review, then change an inventory, supplier or quotation fingerprint, or the supplied exchange rate/date. Resume could discard the saved draft and call the write tool again. | [`checkpoint.py`](../../src/procurement_agent/agent/checkpoint.py) retains the existing draft as a completed side effect even when cached calculations become stale. [`workflow.py`](../../src/procurement_agent/agent/workflow.py) checks completion before invalidating a comparison for a new rate. Five regression cases repeat each resume twice: the same draft is returned, zero tools run and exactly one requisition remains. |
| W8-02 / High | Resume a completed review with an unknown role. The saved draft was returned without reaching dispatch's role check. With `fresh=True`, the unknown caller could replace the checkpoint. | The workflow refuses unknown roles before checkpoint access, deletion or saving, and withholds advisory memory. Two regression cases verify `unauthorized`, no tool calls, no returned draft and byte-for-byte unchanged checkpoint contents. This enforces the seeded-role boundary; it does not authenticate a person. |
| W8-03 / High | Supply `NaN` or infinity as an exchange rate or extracted numeric field. Validation accepted non-finite values; calculation could raise an exception, and output validation could accept a non-finite number. | [`validate.py`](../../src/procurement_agent/tools/validate.py) rejects non-finite exchange rates before calculation; [`schema.py`](../../src/procurement_agent/schema.py) rejects them in all five extracted numeric fields; [`output_schema.py`](../../src/procurement_agent/tools/output_schema.py) rejects non-finite numeric outputs. Twenty-one regression cases cover both infinities and `NaN`, including existing rejection controls. |
| W8-04 / High | Invoke the draft tool while its output-schema file is missing or malformed. The dispatcher returned `OUTPUT_SCHEMA_INVALID`, but the requisition had already been appended. | [`dispatch.py`](../../src/procurement_agent/tools/dispatch.py) loads the output schema before invoking a tool. Two regression cases verify a structured failure and no requisition-store creation for either unavailable-schema condition. Successful responses still undergo output validation after execution. |

Tests are in [`test_agent_checkpoint.py`](../../tests/test_agent_checkpoint.py),
[`test_tools_compare.py`](../../tests/test_tools_compare.py),
[`test_tools_output_schema.py`](../../tests/test_tools_output_schema.py) and
[`test_schema.py`](../../tests/test_schema.py). Before the fixes, the first regression run
recorded **26 failures and 2 passes**; the separate schema-write reproduction recorded
**2 failures**. All 30 cases now pass. The two initial passes were negative-infinity
rejection controls, not unresolved failures.

## 3. Known limitations that remain

High means a constraint that must be resolved before using this prototype with real data or
shared users. Medium means a supported-use restriction or a reliability gap that still needs
explicit handling. Follow-up roles below identify the work needed; they are not new team
assignments or claims that an issue has been completed.

| ID / priority | Limitation and evidence | Current handling and required follow-up |
|---|---|---|
| KL-01 / Medium | **A valid quotation can time out.** The latest recorded full live evaluation, on 19 October, scored **44/45**: clean quotation S-38 returned `timeout` after 29.95 s with no record. See [S-38 evidence](../../evidence/evaluation/week-07-final/live/S-38.json) and [scenario evaluation](../evaluation/scenarios.md#6-failure-found-in-the-final-run). | Keep the 30-second overall model budget required by the project. Report the failure and let the officer explicitly rerun extraction. Do not extend the deadline or treat a missing record as usable. Model-integration follow-up: measure repeated uncached runs and provide an explicit retry interaction. This Week 8 review does **not** claim S-38 is fixed. |
| KL-02 / High | **Identity and confirmation are trusted command-line inputs.** `--role`, `--officer`, `--confirm-comparison` and `--confirm-draft` are not backed by login or a signed review decision. [`agent/cli.py`](../../src/procurement_agent/agent/cli.py) supplies them directly. | Use a trusted operator and synthetic data only. Unknown-role refusal and the allow-list remain enforced. Interface/security follow-up: authenticated sessions, identity-bound confirmations and server-side authorization before real use. |
| KL-03 / High | **Local writes are not a transaction and have no shared-writer lock.** [`tools/draft.py`](../../src/procurement_agent/tools/draft.py) scans for the next ID and then appends; checkpoints, logs and memory are written separately. Concurrent processes can race. A crash after the append but before saving completion can leave a draft without its checkpoint. | Run one process per store. Inspect the requisition store before recovery after an interrupted write. W8-01 protects ordinary resume with an intact completed checkpoint; it does not provide crash-safe, global idempotency. Storage follow-up: a transactional store, unique run/idempotency keys and recovery tests. |
| KL-04 / High | **The full designed AI workflow is not integrated.** [`planner.py`](../../src/procurement_agent/agent/planner.py) is deterministic, uses registered quotations, compiles template justification and inserts a fixed clause list. Extraction and RAG have separate entry points; the loop does not perform fresh policy grounding or model-written justification. See the [contract phase table](../requirements/agent-task-contract.md#4-phases). | Run extraction and policy retrieval separately and require officer review. Do not describe the loop's clause list as a fresh RAG result. Agent/RAG follow-up: wire validated extraction, policy retrieval and justification review into persisted phases and human gates. |
| KL-05 / Medium | **A workflow invocation processes one flagged item.** The scan can return many items, but [`AgentState.flagged_item()`](../../src/procurement_agent/agent/state.py) returns the first when no SKU is specified. The planner drafts only that item. | Run a separate review with `--sku` for each flagged item. Agent follow-up: explicit per-item iteration and a reviewed multi-item requisition flow. A successful run without `--sku` does not mean every flagged item was processed. |
| KL-06 / Medium | **The calculator supports the registered fixture conventions.** [`compare.py`](../../src/procurement_agent/tools/compare.py) reads the first quotation line, uses explicit conversion factors and implements UGX/USD conversion. Full validation of arbitrary imported supplier/quotation records, other currencies, multi-line matching and freight allocation is absent. | Use the reviewed datasets and disclosed rates/conversion factors. Tool/data follow-up: complete import validation and reject unsupported currency and line-item conventions before accepting external records. Finite-number checks do not prove every business value is sensible. |
| KL-07 / Medium | **Retrieval and citation checks have limited scope.** The controlled index contains 12 documents and 45 clauses. A citation matching a retrieved source/version/clause proves provenance, not that every summary claim follows from it. The cutoffs were evaluated on a small synthetic set. See [working RAG](working-rag-pipeline.md). | State missing specifications, withhold invalid citations and have the officer check the cited text. RAG follow-up: broaden the reviewed corpus, test retrieval recall and assess whether generated claims are supported. Re-ingest after approved corpus changes. |
| KL-08 / Medium | **Extraction accepts converted Markdown, and valid structure does not prove factual accuracy.** PDF/image conversion and OCR are absent. Prompt v1.4 and deterministic validation constrain the output but cannot guarantee every supplier value is copied correctly. [`extract.py`](../../src/procurement_agent/extract.py) accepts schema-conforming model output. | Prepare Markdown manually and compare all extracted fields with the quotation at Gate 1. Model/data follow-up: conversion provenance, source-field checks and broader real-document evaluation. The current guard uses text patterns and cannot recognize every adversarial paraphrase. |
| KL-09 / High | **Saved state is a trusted local file.** [`CheckpointStore.load()`](../../src/procurement_agent/agent/checkpoint.py) checks JSON and the format marker, but does not fully validate nested results or authenticate their contents. Changed contract/policy versions are not a general checkpoint-invalidation key. State files have no expiry. | Restrict filesystem access, retain checkpoints during recovery and use synthetic data. Reconcile existing drafts before deleting a checkpoint or using `--fresh`/`--no-state`, since these bypass ordinary duplicate prevention. State/security follow-up: strict checkpoint validation, version-aware invalidation, retention and tamper protection. Source-register hashes detect edits relative to the register; they are not signatures. |
| KL-10 / High | **Memory, caches, requisitions and traces are plain local files.** There is no application-level encryption, shared-user access control or automatic trace rotation. Memory expiry filters display; physical removal requires a purge. See [memory handling](working-memory.md#5-what-is-stored-who-may-access-it-and-for-how-long). | Keep synthetic records, protect the working directory and keep secrets out of tracked files. Data/security follow-up: access policy, encryption where required, deletion/backup rules and scheduled retention enforcement. Advisory memory remains separate from eligibility, arithmetic and ranking. |
| KL-11 / Medium | **Execution limits are not complete process isolation.** The workflow checks elapsed time between synchronous steps and starts a new timer on each invocation; only iterations accumulate across resumes. The model watchdog bounds the caller's wait but cannot forcibly terminate its worker thread. See [`workflow.py`](../../src/procurement_agent/agent/workflow.py) and the [deadline follow-up](../evaluation/fc08-fc09-follow-up.md). | Keep bounded invocations and avoid concurrent stalled requests. Runtime follow-up: cancellation-aware operations, cumulative active-time accounting and resource limits under load. Do not assume the workflow timer interrupts a disk operation already in progress. |
| KL-12 / Medium | **Evaluation and installation are not reliability guarantees.** Tests use synthetic data and stub model responses; the eight recorded live scenarios provide only a small sample. Dependencies have minimum versions without a checked-in lockfile. Python 3.10 is declared but was not tested in this review. | Preserve local evidence and the historical live failures. Release/evaluation follow-up: a reproducible dependency set, supported-version CI, repeated live runs and load/recovery tests. Remote CI, Semgrep and a dependency vulnerability audit were not run by this review. |

These limitations constrain deployment. The absence of purchase-order issuance, supplier
contact, contract award, financial commitment and programmatic approval is an intentional
[AI boundary](../requirements/ai-boundary-matrix.md), not missing functionality to enable.
The only requisition status the tool writes is `DRAFT`.

## 4. Verification and review coverage

| Check on 20 October 2026 | Result | Evidence |
|---|---|---|
| Reproduce W8-01 to W8-03 before changing implementation | 26 failed, 2 passed | [Initial regression](../../evidence/evaluation/week-08-hardening/before-fixes.txt) |
| Reproduce W8-04 before moving the schema check | 2 failed | [Schema-write reproduction](../../evidence/evaluation/week-08-hardening/before-schema-fix.txt) |
| Targeted checkpoint, comparison, output-schema and extraction-schema tests | 79 passed | [Targeted results](../../evidence/evaluation/week-08-hardening/targeted-tests.txt) |
| Full suite with `dev`, `rag` and `gemini` extras, Python 3.11 | 541 passed; no skips | [Full results](../../evidence/evaluation/week-08-hardening/pytest.txt) |
| Offline scenario rerun | 37 passed; 8 live scenarios not run; 0 recorded safety violations | [Scenario results](../../evidence/evaluation/week-08-hardening/scenario-results.json) |
| Bandit, repository medium-and-above severity gate | Passed | [Scan report](../../evidence/evaluation/week-08-hardening/bandit.json) |
| Installed dependency compatibility | Passed | [Verification record](../../evidence/evaluation/week-08-hardening/verification.json) |

Requirements and architecture were checked against the implemented phases and intentional
action boundaries. Model/prompt and RAG review used the extraction/citation tests and existing
live evidence. Tools, authorization, agent limits and memory were covered by the full suite
and offline scenarios. Storage review identified the transaction, trust and retention limits
above. The README now describes the implemented contract/state and links this register;
historical evidence has not been overwritten or relabelled as a Week 8 pass.

Reproduce from the repository root in an activated environment:

```bash
pip install -e ".[dev,rag,gemini]" "bandit[toml]"
python -m pytest
python -m pytest tests/test_agent_checkpoint.py tests/test_tools_compare.py tests/test_tools_output_schema.py tests/test_schema.py
python tools/run_scenarios.py --output-dir var/week-08-recheck
python -m bandit -r src -c pyproject.toml -ll -q
```

Installation requires network access. The tests and offline scenarios need no API key,
network calls or embedding-model download. Use a new scenario-output directory so a recheck
does not overwrite the recorded evidence. Remote CI, team review and release approval remain
outstanding; local passes are not represented as those approvals.
