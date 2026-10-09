# Three Execution Traces

| Field | Value |
|---|---|
| Week | 5 |
| Owner | Ainamani Jim Isaac |
| Due | 2 October 2026 |
| Status | Complete, awaiting team review |
| Path | `docs/evaluation/execution-traces.md` |

## Brief requirement

Capture at least three execution traces, including one failure/recovery case. Store raw traces under `evidence/traces/` and summarise them here.

## Write-up

### Purpose and scope

This document records executions of the Week 5 bounded procurement agent. Together they show
the normal human hand-off, successful creation of a purchase requisition in `DRAFT`, a
controlled stop at the iteration limit, and a failure followed by a recovery run. The raw JSON
evidence is preserved under
[`evidence/traces/agent/`](../../evidence/traces/agent/), while the append-only machine log is
[`agent-runs.jsonl`](../../evidence/traces/agent-runs.jsonl).

The runs use the deterministic offline planner. It proposes the catalogue tools in workflow
order and makes no Gemini API call. The evidence therefore demonstrates orchestration, tool
permissions, human gates and stop-limit behaviour; it does not claim to demonstrate
model-driven planning.

### Recorded scenario

All three runs use the same controlled scenario so their outcomes can be compared directly:

| Field | Value |
|---|---|
| Review date | 25 September 2026 |
| Item | `AH-CM-001` — Portland cement 42.5N, 50 kg bag |
| Caller | `PROCUREMENT_OFFICER` |
| Current / reorder / target stock | 150 / 150 / 270 bags |
| Computed reorder quantity | 120 bags |
| Planner | Deterministic offline planner; no model call |

The first three workflow stages are read-only: `check_reorder_need`,
`check_supplier_eligibility`, and `compare_quotations`. The fourth tool,
`create_requisition_draft`, is the only write and requires officer confirmation. Each tool call
consumes one iteration. The workflow records an explicit stop reason when it completes, pauses,
or reaches a limit.

### Summary

| Trace | Tool calls | Stop reason | Outcome |
|---|---:|---|---|
| [01 — human hand-off](../../evidence/traces/agent/01-awaiting-human.json) | 3 | `awaiting_human` | Comparison produced; no requisition created |
| [02 — completed draft](../../evidence/traces/agent/02-completed-draft.json) | 4 | `completed` | `REQ-2026-001` created with status `DRAFT` |
| [03 — iteration limit](../../evidence/traces/agent/03-max-iterations.json) | 1 | `max_iterations` | Safe halt after the inventory check; no draft created |
| [04 — missing inventory](../../evidence/traces/agent/04-failure-missing-inventory.json) | 1 | `failed` | Missing inventory reported as `DATA_SOURCE_UNAVAILABLE`; nothing written |
| [05 — recovery rerun](../../evidence/traces/agent/05-recovery-rerun.json) | 3 | `awaiting_human` | Real inventory restored; workflow reached the officer gate |

### Trace 1 — comparison held for the officer

The first run had no comparison or draft confirmation. The workflow performed three
iterations:

1. `check_reorder_need` found cement exactly at its reorder point and calculated a reorder of
   120 bags.
2. `check_supplier_eligibility` evaluated four suppliers. SUP-002 and SUP-007 were excluded for
   `NAME_DISCREPANCY`; SUP-006 was excluded as `BLACKLISTED`; SUP-004 remained eligible.
3. `compare_quotations` ranked QT-002 from Bugolobi Hardware Supplies. Its normalised unit cost
   was UGX 31,000 and its landed cost for 120 bags was UGX 4,479,600.

POL-001-C02 required three eligible quotations in this value band, but only one remained. The
comparison therefore carried `INSUFFICIENT_QUOTATIONS`, `exception_required: true`, and
`sole_eligible_option: true`. The agent stopped with `awaiting_human` at the draft step. Its
`draft` field is `null`, proving that the result was held for officer review rather than being
turned into a requisition automatically.

### Trace 2 — confirmed draft creation

The second run supplied the officer's comparison and draft confirmations. It repeated the three
read-only checks and then called `create_requisition_draft` in iteration four. The workflow
created `REQ-2026-001` and stopped with `completed`.

The record preserves the procurement boundary:

- Its status is `DRAFT`.
- `routed_to`, `approved_by`, and `decision` are all `null`.
- The justification states that only one of the three required quotations remained and that an
  exception is required before the requisition proceeds.
- The two name discrepancies and the blacklisted quotation remain visible under
  `unresolved_issues`.

The trace demonstrates successful preparation, not approval or award. No purchase order was
issued, no supplier was contacted, and no funds were committed.

### Trace 3 — controlled limit stop

The third run deliberately set the maximum iteration count to one. The agent completed
`check_reorder_need`, advanced to the eligibility step, and then stopped with
`max_iterations`. Its stop detail states that the cap was reached and no further tool call was
made.

The `eligibility`, `comparison`, and `draft` fields are all `null`. This trace demonstrates a
configured limit stop: the workflow does not attempt to finish the procurement task after its
execution budget is exhausted. It is not presented as the brief's failure/recovery case.

### Trace 4 — missing inventory failure and recovery

This paired run closes the failure/recovery gap identified in review. The failure run
deliberately pointed the inventory input at `knowledge/data/missing.csv`:

- `check_reorder_need` returned `unavailable` with `DATA_SOURCE_UNAVAILABLE`;
- the workflow stopped as `failed` after one iteration;
- `reorder`, `eligibility`, `comparison`, and `draft` were all `null`; and
- no requisition was written.

The recovery run used the registered inventory file. It completed the reorder, eligibility,
and comparison steps, then stopped as `awaiting_human` after three iterations. The recovered
result again calculated 120 bags, retained QT-002 at UGX 4,479,600 landed cost, and created no
draft before officer confirmation.

This recovery is a **full rerun**, not a checkpoint resume. The two commands use `--no-state`
to reproduce the Week 5 behaviour accurately: checkpoint and resume support had not yet been
built during Week 5 and was introduced later as Week 6 work.

Evidence:

- [04-failure-missing-inventory.json](../../evidence/traces/agent/04-failure-missing-inventory.json)
- [05-recovery-rerun.json](../../evidence/traces/agent/05-recovery-rerun.json)

### How the evidence was generated

The recorded outcomes can be reproduced from the repository root after installing the package:

```bash
pip install -e ".[dev]"

# Human hand-off
python -m procurement_agent.agent.cli \
  --review-date 2026-09-25 --sku AH-CM-001 --json

# Confirmed draft
python -m procurement_agent.agent.cli \
  --review-date 2026-09-25 --sku AH-CM-001 \
  --confirm-comparison --confirm-draft --json

# Controlled stop
python -m procurement_agent.agent.cli \
  --review-date 2026-09-25 --sku AH-CM-001 \
  --max-iterations 1 --json

# Failure: missing inventory
python -m procurement_agent.agent.cli \
  --review-date 2026-09-25 --sku AH-CM-001 \
  --inventory knowledge/data/missing.csv --no-state --no-memory --json

# Recovery: full rerun with the registered inventory file
python -m procurement_agent.agent.cli \
  --review-date 2026-09-25 --sku AH-CM-001 \
  --no-state --no-memory --json
```

The CLI passes each proposed action to `dispatch.invoke`, which enforces the current step's
allow-list and the caller's role. Individual tool calls are appended to
[`tool-runs.jsonl`](../../evidence/traces/tool-runs.jsonl). When the workflow reaches a stop
condition, it records the collected results, iteration count, calls, and stop reason in
`agent-runs.jsonl`. The three numbered files are indented copies selected for human review.

### Findings

The traces provide evidence that:

- a comparison cannot silently cross the officer confirmation gate;
- the only side effect produces a requisition in `DRAFT`;
- exclusions and policy exceptions remain visible to the reviewer;
- an iteration cap prevents unbounded execution; and
- an unavailable inventory source fails safely and succeeds on a full rerun after restoration;
- every run ends with an explicit, auditable stop reason.

### Limitations and follow-up

- The default planner is deterministic. A Gemini-backed planner is required before the project
  can claim model-driven action selection.
- The recorded traces cover one cement scenario; they are not broad performance evidence.
- The Week 5 recovery evidence is a full rerun and repeats earlier work. Checkpoint/resume
  behaviour was added later as part of Week 6 and is not claimed by these two new traces.
- Policy retrieval and AI justification drafting are not yet wired into this loop.

Automated coverage for these behaviours is in `tests/test_agent_workflow.py` and
`tests/test_agent_cli.py`.
