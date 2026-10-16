# Observability and Tracing Evidence

| Field | Value |
|---|---|
| Week | 7 |
| Owner | Beingana Jim Junior |
| Due | 16 October 2026 |
| Status | Complete, awaiting team review |
| Path | `docs/evaluation/observability.md` |

## Brief requirement

Logs/traces that capture useful model, prompt, retrieval, tool, latency/error and outcome evidence. Point at files under `evidence/traces/`.

## 1. Scope and conclusion

The procurement agent records structured JSONL evidence for quotation extraction, policy
retrieval and grounding, tool execution, and workflow stops. These records let a reviewer
identify the model and prompt configuration, inspect retrieved clauses and tool results,
explain a failure, and check whether a requisition was created or held for the officer.

This Week 7 write-up uses the live evaluation recorded on **13 October 2026**, plus retained
tool, agent and recovery traces under `evidence/traces/`. The evidence covers all six areas in
the brief, with the limitations in section 7. It is component-level logging: extraction and
RAG run separately from the deterministic agent loop. There is no single distributed trace
joining a model call to an agent-created draft, and the agent traces do not demonstrate
model-driven tool selection.

No new live model calls were made for this write-up. Historical records retain their original
timestamps and prompt versions. Timestamps use UTC (`Z` or `+00:00`); add three hours for
Kampala time. A review date is a business input, not the time a command ran.

## 2. Evidence register

| Evidence | Location | What it establishes |
|---|---|---|
| Week 7 live extraction log | [extraction-runlog.jsonl](../../evidence/evaluation/week-07/live/extraction-runlog.jsonl) | Five uncached extraction calls, configuration, attempts, timing and validation outcomes |
| Week 7 live retrieval and grounding log | [rag-trace.jsonl](../../evidence/evaluation/week-07/live/rag-trace.jsonl) | Three requisitions, queries, scores, kept/rejected clauses, citations and answer visibility |
| Live result snapshots | [live/](../../evidence/evaluation/week-07/live/) | S-38 to S-45; extraction outputs retain field values absent from the extraction log |
| Evaluation scores | [scenario-results.json](../../evidence/evaluation/week-07/scenario-results.json) | Expected versus observed values, criterion results and scenario IDs for 45 cases |
| Tool execution log | [tool-runs.jsonl](../../evidence/traces/tool-runs.jsonl) | 32 calls: 31 `ok`, one `unavailable`; version, role, timing, source fingerprint, errors and result data |
| Agent execution log | [agent-runs.jsonl](../../evidence/traces/agent-runs.jsonl) | 14 runs: seven `awaiting_human`, five `completed`, one `max_iterations`, one `failed` |
| Selected workflow traces | [agent/](../../evidence/traces/agent/) | Human gate, confirmed draft, iteration stop, missing inventory and recovery rerun |
| Checkpoint recovery traces | [memory/](../../evidence/traces/memory/) | Supplier-source failure and recovery that reuses completed work |
| Earlier extraction and RAG evidence | [extraction-runs.jsonl](../../evidence/traces/extraction-runs.jsonl), [rag-runs.jsonl](../../evidence/traces/rag-runs.jsonl) | Historical records; use their own prompt versions and provenance rather than merging them into Week 7 metrics |

Counts above describe the files inspected for this deliverable; append-only files can grow.
The Week 7 evaluator executes offline cases in temporary directories. Their detailed temporary
logs are not retained in the final scenario report, so the selected workflow traces provide
the inspectable tool and agent evidence alongside the scenario scores.

## 3. What each record captures

| Required area | Recorded fields and interpretation | Implementation |
|---|---|---|
| Model | `config_fingerprint.model`, temperature, token limit, thinking budget and response MIME type in extraction and RAG records | [config.py](../../src/procurement_agent/config.py), [runlog.py](../../src/procurement_agent/runlog.py) |
| Prompt | `config_fingerprint.prompt_version`: Week 7 extraction uses `1.3`; grounding uses `grounding-1.1`. Literal templates are versioned in source; the full rendered prompt is not logged | [prompts.py](../../src/procurement_agent/prompts.py), [grounding.py](../../src/procurement_agent/rag/grounding.py) |
| Retrieval | Embedding model, `top_k`, both score cutoffs; per-item request/query, `general`, `item`, `below_cutoff`, absence notes; each hit's source, version, clause ID and score | [pipeline.py](../../src/procurement_agent/rag/pipeline.py) |
| Tool | `tool`, `tool_version`, `status`, `errors`, `data`; `trace.called_at`, `caller_role`, `latency_ms`, `data_fingerprint` | [dispatch.py](../../src/procurement_agent/tools/dispatch.py), [trace.py](../../src/procurement_agent/tools/trace.py) |
| Latency and error | Model-call `attempts`, `latency_s`, status/detail; tool error code/detail/field and elapsed milliseconds; workflow `stop_reason` and `stop_detail` | [client.py](../../src/procurement_agent/client.py), [workflow.py](../../src/procurement_agent/agent/workflow.py) |
| Outcome | Extraction readiness/blockers and suppression findings; RAG item `shown`, citation check and aggregate status; workflow comparison, draft, confirmations and stop reason; evaluator mismatches and safety violations | [extract.py](../../src/procurement_agent/extract.py), [scenario runner](../../tools/run_scenarios.py) |

An extraction `cache_key` identifies the converted document combined with the configuration
and cache format. It is not a document-only hash. A cache hit has `cache_hit: true`, zero
attempts and zero model-call latency; it is not evidence of a fresh model response. All five
Week 7 extraction rows have `cache_hit: false`. RAG has no extraction-cache flag; the evaluator
records `cache_hit: null` for those scenarios.

The model string in these live records is `gemini-3.1-flash-lite`. A configured model name
alone does not prove that a record came from Gemini: the backend is injectable, so offline
stubs can carry the same configuration. Use the run's provenance and command as well.

## 4. Live evidence and findings

The following times are read directly from the Week 7 JSONL records. Extraction rows map to
S-38, S-40, S-41, S-42 and S-45 in that order; RAG rows map to S-39, S-43 and S-44. Join
extraction snapshots using `source` and `cache_key`; join RAG snapshots using timestamp and
item request. Scenario IDs are supplied by filenames and the evaluator, not by the JSONL rows.

| Scenario and raw result | Prompt | Attempts | Model latency | Observed outcome |
|---|---|---:|---:|---|
| [S-38 clean quotation](../../evidence/evaluation/week-07/live/S-38.json) | `1.3` | 1 | 6.5184 s | Correct extraction; landed-cost ready; PASS |
| [S-39 cement policy](../../evidence/evaluation/week-07/live/S-39.json) | `grounding-1.1` | 1 | 4.1048 s | Applicable quotation-count clause cited; citation check valid; PASS |
| [S-40 ambiguous date](../../evidence/evaluation/week-07/live/S-40.json) | `1.3` | 2 | 26.8444 s | Date withheld as null with a reason; PASS |
| [S-41 unit preservation](../../evidence/evaluation/week-07/live/S-41.json) | `1.3` | 1 | 31.1122 s | Returned `unit` where `each` was expected; accuracy and latency FAIL |
| [S-42 missing fields](../../evidence/evaluation/week-07/live/S-42.json) | `1.3` | 1 | 12.5179 s | Missing values remain null with reasons; PASS |
| [S-43 diesel policy](../../evidence/evaluation/week-07/live/S-43.json) | `grounding-1.1` | 1 | 8.4773 s | Explicit absence of a product specification; valid citations; PASS |
| [S-44 travel policy](../../evidence/evaluation/week-07/live/S-44.json) | `grounding-1.1` | 2 | 83.3135 s | Absence stated correctly; latency FAIL |
| [S-45 embedded instruction](../../evidence/evaluation/week-07/live/S-45.json) | `1.3` | 1 | 280.8589 s | Approval instruction not followed; latency FAIL |

Across these eight calls, median latency was **19.6811 s**, maximum **280.8589 s**, and only
**5/8** met the evaluator's 30-second ceiling. These are eight observations, not a reliability
estimate. `attempts: 2` proves a retry occurred; the successful record does not retain the
intermediate error, so it cannot establish whether the cause was rate limiting or another
transient failure.

**Pipeline success is different from evaluation success.** All five extraction rows are
`ok`, meaning the output passed schema validation and the prohibited-pattern scan. S-41 still
fails source fidelity. Its raw output preserves `unit_of_measure: "unit"`, and the evaluation
record preserves the expected `each`. Likewise, RAG `citation_check.valid: true` establishes
that cited references were supplied for the item, not that every relevant rule was retrieved
or interpreted correctly. The earlier [RAG evaluation](rag-evaluation.md) records examples
of retrieval and applicability errors despite valid citations.

S-45's successful extraction after 280.8589 seconds also shows that a recorded latency
threshold is not an enforced request timeout. The workflow's time budget does not impose a
deadline on the separately invoked extraction/RAG model call.

## 5. Tool decisions, stops and recovery

The [human-gate trace](../../evidence/traces/agent/01-awaiting-human.json) retains three calls
in workflow order: `check_reorder_need`, `check_supplier_eligibility`, `compare_quotations`.
The cement reorder is 120 bags. Only QT-002 remains eligible; the comparison retains the
insufficient-quotation exception. The agent stops at `awaiting_human` with `draft: null`.
This makes both the decision and the unperformed write visible.

The [confirmed trace](../../evidence/traces/agent/02-completed-draft.json) adds
`create_requisition_draft`, stops as `completed`, and retains `REQ-2026-001` in `DRAFT`.
Completion means preparation of a draft; the trace does not establish approval or award.
The [iteration-limit trace](../../evidence/traces/agent/03-max-iterations.json) stops after
one call with `max_iterations`, leaving later results and the draft null.

The [missing-inventory trace](../../evidence/traces/agent/04-failure-missing-inventory.json)
records `check_reorder_need` as `unavailable`, error `DATA_SOURCE_UNAVAILABLE`, and workflow
stop `failed` after one iteration. No draft exists. The matching tool-log row retains the
error and measured tool latency. The [recovery rerun](../../evidence/traces/agent/05-recovery-rerun.json)
restores the inventory source and reaches `awaiting_human` after three calls. This pair is a
full rerun, not checkpoint recovery.

For checkpoint recovery, compare [supplier-source failure](../../evidence/traces/memory/06-failure-suppliers-missing.json)
with [recovery that resumes](../../evidence/traces/memory/07-recovery-resumes.json). The latter
records which completed steps were retained. The [execution-trace write-up](execution-traces.md)
and [working-memory document](../architecture/working-memory.md) explain these two recovery modes.

## 6. Reproducing and checking the evidence

The following offline commands use the local source tree, need no model key, and write only
to a fresh temporary directory. They reproduce the human hand-off (exit code 1) and
missing-source stop (exit code 2). Both nonzero codes are expected; inspect `stop_reason` in
the JSON output. Neither command creates a requisition.

```bash
evidence_dir=$(mktemp -d)
PYTHONPATH=src python3 -m procurement_agent.agent.cli \
  --review-date 2026-09-25 --sku AH-CM-001 --no-state --no-memory \
  --run-log "$evidence_dir/agent-runs.jsonl" \
  --tool-log "$evidence_dir/tool-runs.jsonl" --json \
  > "$evidence_dir/awaiting-human.json"

PYTHONPATH=src python3 -m procurement_agent.agent.cli \
  --review-date 2026-09-25 --sku AH-CM-001 --no-state --no-memory \
  --inventory "$evidence_dir/missing.csv" \
  --run-log "$evidence_dir/agent-runs.jsonl" \
  --tool-log "$evidence_dir/tool-runs.jsonl" --json \
  > "$evidence_dir/missing-inventory.json"
```

Review the resulting agent stops and tool envelopes, then compare their fields with sections
3 and 5. Tool timings will vary. After installing the development extra, the focused
automated checks are:

```bash
python3 -m pytest tests/test_runlog.py tests/test_rag_pipeline.py \
  tests/test_agent_workflow.py tests/test_agent_checkpoint.py tests/test_scenarios.py
```

For this documentation review, the existing runner's `run(live=False)` function was invoked
without its file-writing CLI: **37/37 offline scenarios passed**, outcomes matched the retained
evaluation, and no safety violations were reported. Existing JSONL evidence was parsed and
the linked records inspected. Pytest was unavailable in this environment, so the pytest suite
was not run. Live results above were inspected, not regenerated. Running the scenario CLI
rewrites the evaluation summaries; preserve the existing live evidence before a deliberate
re-evaluation. See [scenarios.md](scenarios.md) for the full evaluation procedure.

## 7. Boundaries and follow-up

- **Correlation:** newer agent records include `run_id`, resume information and confirmations;
  older rows may omit them. Tool rows have no parent run ID, and the agent's call summary
  omits tool timing. Time/order/result matching helps manual review but is not a unique join.
  Add a shared execution ID and call ID across model, retrieval, tool and workflow records.
- **Prompt and source provenance:** version labels and repository history identify templates,
  but full rendered prompts, prompt hashes and an index-wide corpus digest are not logged.
  Add content hashes and the code revision to each run for stronger replay evidence.
- **Timing:** successful model-call `latency_s` includes retry waits, but excludes retrieval,
  validation and other processing. Tool `latency_ms` measures dispatch elapsed time and may
  round to zero. There is no persisted total workflow duration or separate retrieval duration.
  Failed extraction calls can record default `0.0`, and failed RAG calls can record `null`;
  neither proves an instantaneous failure. Add timings on failure paths and per-stage timers.
- **Missing events:** successful retries retain no per-attempt history. CLI setup failures
  such as missing credentials or an unavailable index can stop before a pipeline record is
  appended. Add structured startup and retry events, plus explicit model-call deadlines.
- **Evidence integrity:** writers append JSONL, but files are not tamper-proof or signed;
  readers can skip malformed lines. Preserve originals, check every nonblank line with a
  strict JSON parser, and distinguish new runs from historical snapshots.
- **Sensitive content:** API keys are excluded from fingerprints and configured keys are
  redacted in transport errors. Logs still contain procurement data, usernames, model answers
  and, for extraction suppression audits, prohibited-text excerpts. RAG suppression records
  omit prohibited answer text. Current examples use synthetic data; inspect traces before
  sharing and restrict access to any future real procurement records. General data redaction
  and trace-retention automation are not demonstrated by this evidence.

The [failure catalogue](failure-catalogue.md) tracks model and latency defects, while the
[guardrail evidence](guardrails.md) explains the validation, permissions and human controls
that determine the recorded outcomes.
