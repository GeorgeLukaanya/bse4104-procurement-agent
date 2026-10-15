# Working Bounded Agent Workflow

| Field | Value |
|---|---|
| Week | 5 |
| Owner | Nannyombi Shakiran |
| Due | 2 October 2026 |
| Status | Complete, awaiting team review |
| Path | `docs/architecture/working-agent.md` |

## Brief requirement

Write-up of the implemented bounded agent workflow (direct orchestration or a framework). Link the code, stop-limit behaviour, and how a run is started and halted.

## Write-up

### What it does

One goal-directed workflow: take a weekly reorder review to a purchase requisition in `DRAFT`, then stop. Direct orchestration — no LangGraph, no FastAPI, no application framework. The charter has not chosen one.

A **planner proposes** the next catalogue tool. **`dispatch.invoke` executes it.** Gemini never calls a tool. The default planner is deterministic so a run spends no API quota and the test suite cannot hit the free-tier limit. The agent task contract (issue #21) is a separate Week 5 document; this implementation follows Charter §6 steps that already have catalogue tools.

| Step | Allow-list | Human gate |
|---|---|---|
| `scan` | `check_reorder_need` | none (read-only) |
| `eligibility` | `check_supplier_eligibility` | none (read-only) |
| `compare` | `compare_quotations` | none (read-only); the table is then held for the officer |
| `draft` | `create_requisition_draft` | officer confirmation required |

Conversion, extraction and policy retrieval stay on their own CLIs. Policy is not a catalogue tool ([`tool-catalogue.md`](tool-catalogue.md) §1). Justification text is compiled from tool results, not drafted by Gemini.

### How to start and halt a run

```bash
pip install -e ".[dev]"

# Start. Stops after the comparison for the officer to review (exit 1).
python -m procurement_agent.agent.cli \
    --review-date 2026-09-25 --sku AH-CM-001

# Continue after the officer confirms the table and the draft (exit 0).
python -m procurement_agent.agent.cli \
    --review-date 2026-09-25 --sku AH-CM-001 \
    --confirm-comparison --confirm-draft

# A USD quotation with no rate stops for the officer (exit 1). Re-run with the rate.
python -m procurement_agent.agent.cli \
    --review-date 2026-09-25 --sku AH-HT-001 \
    --exchange-rate 3700 --exchange-rate-date 2026-09-25
```

What that prints (no `--json`):

```
stop:       awaiting_human
detail:     Landed-cost comparison is on the table. The officer must confirm it before a requisition is compiled (Requirement 7.1 / gate 2).
iterations: 3 / 8
contract:   contracts/agent-task-contract.json v1.0, stop AWAITING_HUMAN
step:       draft
role:       PROCUREMENT_OFFICER
calls:
  - check_reorder_need -> ok
  - check_supplier_eligibility -> ok
  - compare_quotations -> ok
Re-run with --confirm-comparison and/or --confirm-draft after the officer reviews.
```

After both confirms:

```
stop:       completed
detail:     Requisition compiled in DRAFT. Further status changes are human actions.
iterations: 4 / 8
contract:   contracts/agent-task-contract.json v1.0, stop DRAFT_CREATED
step:       draft
role:       PROCUREMENT_OFFICER
calls:
  - check_reorder_need -> ok
  - check_supplier_eligibility -> ok
  - compare_quotations -> ok
  - create_requisition_draft -> ok
```

`procurement-agent` is the same command once the package is installed. `--role` injects the session role; it is never read from a payload. `PROCUREMENT_MANAGER` cannot start the loop.

| Exit | Meaning |
|---|---|
| 0 | `completed` (DRAFT written) or `no_reorder_required` |
| 1 | `awaiting_human` — re-run with the matching `--confirm-*` flag, or with `--exchange-rate` when the stop names `EXCHANGE_RATE_REQUIRED` |
| 2 | `max_iterations`, `timeout`, `failed`, `unauthorized`, `refused`, or usage error |

Halt is always explicit. The loop does not run until an exception. Every stop reason is written on the result and on `evidence/traces/agent-runs.jsonl`.

### Stop limits

| Limit | Default | Source |
|---|---|---|
| Maximum iterations | 8 | Fixed by the [Agent Task Contract](../requirements/agent-task-contract.md) section 6; `.env.example` `AGENT_MAX_ITERATIONS`; override `--max-iterations` |
| Wall-clock timeout | 120s | `AGENT_TIMEOUT_SECONDS`; override `--timeout` |
| Step allow-list | one tool per step | [`steps.py`](../../src/procurement_agent/agent/steps.py) |
| Write gate | `create_requisition_draft` | Officer `--confirm-draft`; AGENT still needs that confirmation |

Each successful or refused tool call consumes one iteration. A stop proposal from the planner does not. Hitting the cap writes nothing beyond `DRAFT` that was already written on an earlier confirmed run; a cap in the first steps writes nothing.

### Recorded runs — 29 September 2026

Three starts of the same cement review, officer role, no model.

| File | Stop | Iterations | What happened |
|---|---|---|---|
| [`01-awaiting-human.json`](../../evidence/traces/agent/01-awaiting-human.json) | `awaiting_human` | 3 | Scan, eligibility, compare. Draft not compiled. |
| [`02-completed-draft.json`](../../evidence/traces/agent/02-completed-draft.json) | `completed` | 4 | Both confirms set. `REQ-2026-001` in `DRAFT`. |
| [`03-max-iterations.json`](../../evidence/traces/agent/03-max-iterations.json) | `max_iterations` | 1 | Cap 1: reorder ran, then halt. Nothing written. |

Machine log: [`evidence/traces/agent-runs.jsonl`](../../evidence/traces/agent-runs.jsonl) (one object per line, same idiom as extraction and tools).

On the completed run the comparison still has one eligible offer (QT-002) after `NAME_DISCREPANCY` and `BLACKLISTED` exclusions. The draft carries those unresolved issues. Status is `DRAFT`; `routed_to`, `approved_by` and `decision` are null.

### Tests

`tests/test_agent_workflow.py` and `tests/test_agent_cli.py`. No API key.

| Case | Expected |
|---|---|
| Default cement run | `awaiting_human`, 3 calls, no requisition file |
| Both confirms | `completed`, status `DRAFT` only |
| SKU above reorder point | `no_reorder_required` after one call |
| `--max-iterations 1` | `max_iterations`, nothing written |
| Manager role | `unauthorized`, zero calls |
| Planner proposes `create_requisition_draft` on the scan step | `TOOL_NOT_ALLOWED`, nothing written |
| Missing quotations file | `failed`, `DATA_SOURCE_UNAVAILABLE` (same code as a missing inventory file) |
| Tampered quotations checksum | `failed`, `DATA_INTEGRITY_ERROR` |
| USD quotation, no rate (`AH-HT-001`) | `awaiting_human`, `EXCHANGE_RATE_REQUIRED`, nothing written. `--exchange-rate` supplies the rate on the re-run |
| No eligible supplier (`AH-CM-002`), both confirms | `awaiting_human`, `MISSING_COMPONENT`, nothing written (Requirement 9.4) |

### Not this week

The loop follows the [Agent Task Contract](../requirements/agent-task-contract.md), which it loads at startup: an 8-iteration cap, a 120 s timeout and a closed action set. Tool responses are checked against their output schemas before the loop sees them (FA-10, fixed 6 October 2026). Still to do, as recorded in the contract's section 12: the Gemini planner (the deterministic planner is the default; `Planner.propose` is the seam), the `retrieve_policy` and `draft_justification` phases, a persisted checkpoint so a retry resumes rather than repeating steps (Week 6, #26), `NO_PROGRESS`, and per-reason stop codes. The Model Selection Note makes request throughput the binding constraint, which is why the model planner is not the default.

Supplier IDs for the eligibility step are still resolved in the planner from the quotations file, because `compare_quotations` is not on that step's allow-list. A missing or tampered file now stops as `failed` with `DATA_SOURCE_UNAVAILABLE` or `DATA_INTEGRITY_ERROR`, the same codes `dispatch.invoke` returns when inventory cannot be read. That read is not a catalogue call and does not appear in `tool-runs.jsonl`; routing it through `compare_quotations` would run the calculator before eligibility.

Two differences from the contract are recorded in [`agent-architecture.md`](agent-architecture.md) section 9, not changed here: `check_reorder_need` counts as an iteration, and the default role is `PROCUREMENT_OFFICER` (`--role AGENT` is the contract's loop identity).

The recorded runs above were made on 29 September, before the contract raised the cap from 6 to 8. The stop reasons and iteration counts are unchanged under the new cap.

### Code

| Path | Role |
|---|---|
| [`src/procurement_agent/agent/workflow.py`](../../src/procurement_agent/agent/workflow.py) | Loop, caps, stop reasons |
| [`src/procurement_agent/agent/planner.py`](../../src/procurement_agent/agent/planner.py) | Next-tool proposal |
| [`src/procurement_agent/agent/steps.py`](../../src/procurement_agent/agent/steps.py) | Allow-lists |
| [`src/procurement_agent/agent/cli.py`](../../src/procurement_agent/agent/cli.py) | Start / halt |
| [`src/procurement_agent/tools/dispatch.py`](../../src/procurement_agent/tools/dispatch.py) | Executes every proposed call |
