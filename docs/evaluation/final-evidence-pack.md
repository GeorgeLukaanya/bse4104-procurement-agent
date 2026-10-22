# Final Evaluation and Evidence Pack

| Field | Value |
|---|---|
| Week | 8 |
| Owner | Sekyeza Elroy Nunda |
| Due | 30 October 2026 |
| Status | Complete, awaiting team review |
| Path | `docs/evaluation/final-evidence-pack.md` |
| Indexed at | `263b7ae` on `main` |

## Brief requirement

Index the final evaluation dataset, traces, guardrail evidence, failure catalogue and demo artefacts so a marker can find them from this file.

## 1. What this file is

Every claim the project makes about itself is backed by a file in this
repository. This is the index of those files: what each one says, which commit
produced it, and the command that regenerates it. Nothing here is a new result.
If a figure in this table disagrees with the evidence it points at, the evidence
is right and this file is wrong.

Read section 6 before quoting any number. Two of them are narrower than they
look.

## 2. Verify it yourself

The whole suite runs offline, with no API key and no network:

```bash
pip install -e ".[dev]"
python -m pytest -q
```

That is 541 tests and it is the only check that needs nothing but the
repository. Re-running the scenario evaluation and the guardrail capture needs
the same, plus a key only for the eight live scenarios:

```bash
python tools/run_scenarios.py                 # the 37 offline scenarios
python tools/capture_guardrails.py --out /tmp/guardrails.txt
python tools/offline_demo.py                  # the extraction path, no key
```

## 3. The headline numbers and where they come from

| Claim | Figure | Evidence | Produced at |
|---|---|---|---|
| Scenario evaluation, full run including live | 45 scenarios, 44 pass, 1 fail | [`week-07-final/scenario-results.json`](../../evidence/evaluation/week-07-final/scenario-results.json) | `94e917c`, 19 Oct |
| Safety violations across that run | 0 | same file, `summary.safety_violations` | `94e917c` |
| Scenario re-run after the Week 8 fixes, offline only | 37 run, 37 pass, 8 not run | [`week-08-hardening/scenario-results.json`](../../evidence/evaluation/week-08-hardening/scenario-results.json) | `f13f2be`, 20 Oct |
| Automated tests | 541 passed | [`week-08-hardening/pytest.txt`](../../evidence/evaluation/week-08-hardening/pytest.txt) | `f13f2be` |
| Targeted regression tests for the Week 8 fixes | 79 passed | [`week-08-hardening/targeted-tests.txt`](../../evidence/evaluation/week-08-hardening/targeted-tests.txt) | `f13f2be` |
| Static security scan | [`bandit.txt`](../../evidence/evaluation/week-08-hardening/bandit.txt), [`bandit.json`](../../evidence/evaluation/week-08-hardening/bandit.json) | | `f13f2be` |
| Guardrails, eight of them, each pushed | runs A to R | [`week-07/guardrails.txt`](../../evidence/evaluation/week-07/guardrails.txt) | `5f54052`, 16 Oct |
| Offline scenario latency | median 0.0009 s, p95 0.0101 s | `week-07-final/scenario-results.json`, `summary.latency` | `94e917c` |
| Live scenario latency | median 2.34 s, p95 29.95 s | same | `94e917c` |

The p95 live figure is the failure, not a slow pass. See section 6.

## 4. The dataset

Everything is synthetic and team-authored. No real supplier, price or person
appears anywhere in it.

| What | Size | Where |
|---|---|---|
| Policy, procedure, specification and supplier-terms corpus | 23 documents | [`knowledge/corpus/`](../../knowledge/corpus/) |
| Inventory snapshot | 48 SKUs | [`knowledge/data/inventory.csv`](../../knowledge/data/inventory.csv) |
| Supplier register | 8 suppliers | [`knowledge/data/suppliers.json`](../../knowledge/data/suppliers.json) |
| Held quotations | 36 quotations | [`knowledge/data/quotations.json`](../../knowledge/data/quotations.json) |
| Quotation documents for extraction | 7 fixtures | [`fixtures/`](../../fixtures/) |
| Prompt evaluation cases | 10 cases | [`evaluation-cases/`](../../evaluation-cases/) |
| Scenario set | 45 scenarios | [`evaluation-cases/week-07/scenarios.json`](../../evaluation-cases/week-07/scenarios.json) |

The scenario set covers the six categories the charter asks for: 7 normal, 10
edge, 9 incorrect-information, 8 adversarial, 5 tool-failure and 6
unauthorized-action.

Every data file is listed with a SHA-256 in
[`knowledge/source-register.csv`](../../knowledge/source-register.csv), and the
loaders refuse a file whose content no longer matches its registered checksum.
That is what scenario S-17 exercises.

## 5. The evidence, by kind

### 5.1 Scenario evaluation

| Run | Evidence | Read it with |
|---|---|---|
| Final, offline and live | [`week-07-final/`](../../evidence/evaluation/week-07-final/) with eight per-scenario live records in [`live/`](../../evidence/evaluation/week-07-final/live/) | [`scenarios.md`](scenarios.md) |
| Week 8 re-run, offline only | [`week-08-hardening/`](../../evidence/evaluation/week-08-hardening/) | [`known-limitations.md`](../architecture/known-limitations.md) |
| Earlier full run, kept for comparison | [`week-07/`](../../evidence/evaluation/week-07/) | [`scenarios.md`](scenarios.md) |

### 5.2 Traces

| Trace | Lines | What it shows |
|---|---|---|
| [`traces/agent-runs.jsonl`](../../evidence/traces/agent-runs.jsonl) | 14 | One record per bounded-agent run: stop reason, iterations, contract version |
| [`traces/tool-runs.jsonl`](../../evidence/traces/tool-runs.jsonl) | 32 | One record per catalogue tool call, with status, latency and data fingerprint |
| [`traces/extraction-runs.jsonl`](../../evidence/traces/extraction-runs.jsonl) | 6 | Model calls: prompt version, config fingerprint, cache hit, attempts |
| [`traces/rag-runs.jsonl`](../../evidence/traces/rag-runs.jsonl) | 1 | Retrieval: query, cutoff, clauses returned, absence notes |

Curated, readable copies of individual runs:

| Folder | Files | What they are for |
|---|---|---|
| [`traces/agent/`](../../evidence/traces/agent/) | 5 | The five agent outcomes: awaiting human, completed draft, iteration cap, failure, recovery |
| [`traces/tools/`](../../evidence/traces/tools/) | 4 | One clean envelope per catalogue tool |
| [`traces/memory/`](../../evidence/traces/memory/) | 9 | Memory before and after, resume, no-duplicate re-run, failure and recovery |

Read them with [`execution-traces.md`](execution-traces.md) and
[`observability.md`](observability.md).

### 5.3 Guardrail evidence

[`week-07/guardrails.txt`](../../evidence/evaluation/week-07/guardrails.txt) is
a single transcript of runs A to R, each pushing one guardrail and recording
what came back. It is deterministic: no key, no network, no model.

Read it with [`guardrails.md`](guardrails.md), which quotes the transcript
verbatim and maps each of the eight guardrails to the code that enforces it.
Section 6 of that document lists what is still open, including the one coverage
gap the evidence exposed.

Regenerate with:

```bash
python tools/capture_guardrails.py --out evidence/evaluation/week-07/guardrails.txt
```

### 5.4 Failure catalogue

[`failure-catalogue.md`](failure-catalogue.md) is the list of defects found and
what was done about each. Its supporting evidence:

| Evidence | What it covers |
|---|---|
| [`week-07-fc08-fc09-v1.4/`](../../evidence/evaluation/week-07-fc08-fc09-v1.4/) | FC-08 and FC-09, with the initial run and the run after the fix side by side |
| [`fc08-fc09-follow-up.md`](fc08-fc09-follow-up.md) | The write-up of that fix |
| [`week-05-v1.3/`](../../evidence/evaluation/week-05-v1.3/) | The prompt v1.3 regression, including the TC-07 retest |
| [`week-04/`](../../evidence/evaluation/week-04/) | Authorization failure evidence and its targeted tests |
| [`week-02/`](../../evidence/evaluation/week-02/) | The original ten prompt cases, three files each |
| [`week-08-hardening/before-fixes.txt`](../../evidence/evaluation/week-08-hardening/before-fixes.txt) | The failing state before the Week 8 fixes |

Related documents: [`tool-failure-tests.md`](tool-failure-tests.md),
[`prompt-evaluation.md`](prompt-evaluation.md),
[`rag-evaluation.md`](rag-evaluation.md).

### 5.5 Demo artefacts

This is the thin part of the pack and it is thin today.

| Expected | State |
|---|---|
| [`evidence/demo/`](../../evidence/demo/) | Empty except for `.gitkeep`. No recording, no deck. |
| [`evidence/screenshots/`](../../evidence/screenshots/) | One image, `smoke-test-of-the-live-model-evaluation.png` |
| [`final-presentation.md`](../architecture/final-presentation.md) | Not started |
| [`final-engineering-report.md`](../weekly-reports/final-engineering-report.md) | Not started |

What exists in place of a recording is a demonstration anyone can run:

```bash
python tools/offline_demo.py                                    # extraction, no key
python -m procurement_agent.agent.cli --review-date 2026-09-25 --sku AH-CM-001
python -m procurement_agent.rag.cli --query "minimum quotations"
```

Section 7 says who owns closing this.

## 6. What a marker should not conclude

Three things in this pack are narrower than they appear, and reading them
otherwise would overstate the project.

**The 37 of 37 in the Week 8 re-run is not a second full pass.** It ran the
offline scenarios only; the eight live ones were not run. The full run of all
45, the only one that includes live model calls, is the 19 October one, and it
scored 44.

**The Week 8 results include uncommitted work.** Its own
[`verification.json`](../../evidence/evaluation/week-08-hardening/verification.json)
says so in a field put there for the purpose: `working_tree_changes_included` is
true, and the note reads "These results include the uncommitted Week 8 changes
identified by the file hashes below; they are not a clean-commit or remote CI
result." The file hashes are listed so the claim can be checked. The scenario
runner reports the base commit `f13f2be`, which is not the tree that was run.

**One scenario fails and it is not fixed.** S-38, a clean UGX quotation on the
live path, returned `timeout` after 29.95 s against a 30 second budget, with no
record produced. It is recorded as KL-01 in
[`known-limitations.md`](../architecture/known-limitations.md), the evidence is
[`week-07-final/live/S-38.json`](../../evidence/evaluation/week-07-final/live/S-38.json),
and the handling is to report the failure and let the officer re-run rather than
extend the deadline or treat a missing record as usable. Nothing in this pack
claims S-38 passes.

Two smaller notes. The live latency p95 of 29.95 s is that timeout, so it
describes the failure rather than typical performance; the median of 2.34 s is
the figure to quote for a live call. And `python -m pytest` reports 541 tests on
`main` today, which is the same number the Week 8 evidence recorded.

## 7. What is still open

| Gap | Owner | Needed for |
|---|---|---|
| No demo recording or deck in `evidence/demo/` | Ainamani Jim Isaac | [`final-presentation.md`](../architecture/final-presentation.md) |
| Final engineering report not started | Nannyombi Shakiran | [`final-engineering-report.md`](../weekly-reports/final-engineering-report.md) |
| Live scenarios not re-run since 19 October | whoever holds a key | A clean 45-scenario run at a tagged commit |
| Week 8 evidence produced from a dirty tree | Beingana Jim Junior | A re-run at a clean commit would retire the caveat in section 6 |
| S-38 unresolved | model integration | KL-01 |

A single clean run of all 45 scenarios at the tagged release commit, with no
working-tree changes, would close the first, third and fourth of those at once
and is the highest-value thing left in this pack.

## 8. Where every other document fits

| Document | What it establishes |
|---|---|
| [`scenarios.md`](scenarios.md) | The 45-scenario evaluation and its results |
| [`guardrails.md`](guardrails.md) | Eight guardrails, the code that enforces each, and what is open |
| [`failure-catalogue.md`](failure-catalogue.md) | Defects found, fixed and re-tested |
| [`observability.md`](observability.md) | What is traced and what a trace proves |
| [`execution-traces.md`](execution-traces.md) | Three runs read line by line |
| [`tool-failure-tests.md`](tool-failure-tests.md) | How each tool fails, and that it fails closed |
| [`prompt-evaluation.md`](prompt-evaluation.md) | Prompt versions and the ten cases |
| [`rag-evaluation.md`](rag-evaluation.md) | Retrieval cutoffs, grounding and citation checks |
| [`known-limitations.md`](../architecture/known-limitations.md) | What is still wrong, with KL numbers |
| [`agent-task-contract.md`](../requirements/agent-task-contract.md) | The limits the loop runs under |
| [`ai-boundary-matrix.md`](../requirements/ai-boundary-matrix.md) | What the model decides and what the code decides |

## 9. Secrets

No API key appears anywhere in `evidence/`. The key is read from the
environment only, never written to a cache entry, a run log, a fingerprint or an
error message, and `config.redact()` strips it from anything displayed. A scan
of the whole evidence tree for a key-shaped string finds nothing.
