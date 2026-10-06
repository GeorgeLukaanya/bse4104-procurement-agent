# Agent Task Contract

| Field | Value |
|---|---|
| Week | 5 |
| Owner | Sekyeza Elroy Nunda |
| Due | 2 October 2026 |
| Status | Complete, awaiting team review |
| Path | `docs/requirements/agent-task-contract.md` |

## Brief requirement

Define one task that benefits from multi-step decision making: goal, tools, state, maximum iterations, stop conditions and human hand-off/approval conditions.

## Write-up

### 1. What this document decides

The [Agent Architecture](../architecture/agent-architecture.md) designs the loop and says its
limits are proposals that this contract fixes, and that where the two disagree the contract
wins. The [working agent](../architecture/working-agent.md) describes what is built today.
They currently disagree in five places. This contract settles each one.

| Open value | Architecture | Built today | **This contract** |
|---|---|---|---|
| Who chooses the next action | Gemini proposes, orchestrator disposes | Deterministic planner, no model in the loop | **Gemini proposes, code enforces.** The deterministic planner stays as the offline default |
| Phases in scope | 7, including policy retrieval and justification | 4: scan, eligibility, compare, draft | **All 7 are in the contract**; two are marked not built |
| Iterations per item | 8 proposed | 6 | **8** |
| State on retry | Resumes from a checkpoint | In memory; a retry repeats completed steps | **Resume is required**; not built, and it is a named gap |
| Stop-reason names | `DRAFT_CREATED`, `ITERATION_LIMIT`, `NO_PROGRESS` | `completed`, `max_iterations` | **The architecture's names**, with the mapping in section 8 |

Two consequences for other pages, both since applied: the architecture doc no longer says the
loop is unbuilt (its section 9 now compares the design with the build), and `.env.example` carries
`AGENT_MAX_ITERATIONS=8`.

### 2. The contract

The contract is a file the loop loads, not a block of text in this page:
**[`contracts/agent-task-contract.json`](../../contracts/agent-task-contract.json)**. It is
canonical. `agent/contract.py` reads it at startup and takes the iteration cap, the time budget
and the approved action set from it, so a limit changes in the contract rather than in code.
This page explains the same values; if the two ever disagree, the file is what actually runs.

A missing or malformed contract stops the run with exit code 2. An unbounded loop is the thing
the contract exists to prevent, so there is no silent fallback to a default.

Precedence for any one run, highest first: a command-line flag, then an environment variable,
then the contract.

```bash
# Run under a different contract, for example while proposing new limits
python -m procurement_agent.agent.cli --review-date 2026-10-01 --contract contracts/proposed.json
```

Each run's report and trace name the contract that bound it:

```
iterations: 3 / 8
contract:   contracts/agent-task-contract.json v1.0, stop AWAITING_HUMAN
```

Sections 3 to 8 below explain each part of the file. `tests/test_agent_contract.py` holds the
code to it, including that `DEFAULT_MAX_ITERATIONS` equals the contract's limit and that every
tool the loop can call is an approved action.

### 3. Why this task needs a loop

A fixed script cannot do it safely, because the next correct action depends on what the last
one returned. Eligibility can leave zero, one or several suppliers: zero means there is nothing
to compare, one means POL-001-C04 needs an exception reason, and a `NAME_DISCREPANCY` means the
officer must decide first (Requirement 4.6). A comparison can return `INSUFFICIENT_QUOTATIONS`
or `EXCHANGE_RATE_REQUIRED`, each needing a different next step. The loop decides which approved
action comes next, when to ask the officer and when to stop. It never decides eligibility,
computes a figure, changes a status or approves anything.

### 4. Phases

| Phase | Forward action | Next phase | Built |
|---|---|---|---|
| `FRAMED` | `check_supplier_eligibility` | `ELIGIBILITY_CHECKED` | Yes |
| `ELIGIBILITY_CHECKED` | `compare_quotations` | `COMPARED` | Yes |
| `COMPARED` | hand-off, Gate 2 | `COMPARISON_CONFIRMED` | Yes |
| `COMPARISON_CONFIRMED` | `retrieve_policy` | `POLICY_RETRIEVED` | Pipeline built, not wired in |
| `POLICY_RETRIEVED` | `draft_justification` | `DRAFTED` | No |
| `DRAFTED` | hand-off, Gate 3 | `JUSTIFICATION_CONFIRMED` | No |
| `JUSTIFICATION_CONFIRMED` | `create_requisition_draft` after confirmation | `DRAFT_CREATED`, stop | Yes |

**What the planner is given.** A compact summary of status codes, counts and identifiers from
the checkpoint, and nothing else. No quotation or policy text reaches it, so an instruction
embedded in a supplier document has nothing to act through (Requirement 14.5).

`hand_off` and `stop` are allowed in every phase. Gates 2 and 3 are hand-offs, not actions: the
loop cannot confirm on the officer's behalf. `retrieve_policy` and `draft_justification` are
AI-layer steps rather than catalogue tools, so the charter's four-tool ceiling holds and policy
retrieval stays off the tool allow-list until Week 6. After the officer clears a
`NAME_DISCREPANCY` or supplies an exchange rate, the loop may re-run the read-only checks that
the change invalidated: `check_supplier_eligibility`, then `compare_quotations`.

One loop run opens per flagged item, at `FRAMED`. The officer starts the weekly review and
`check_reorder_need` runs once before the loop; Gate 1, confirming extracted quotation data,
also sits before it. Gates 4 and 5, submit and approve, sit after it and are unreachable from
inside it.

Until the two unbuilt phases exist, a run goes `COMPARISON_CONFIRMED → JUSTIFICATION_CONFIRMED`
directly, and the justification is compiled from tool results rather than drafted. The trace
must record the skip, so no run claims a justification that was never drafted.

### 5. Outcome classes

Every observation is given exactly one class, deterministically. The model proposes actions; it
never classifies its own result.

| Class | Triggers | Loop behaviour |
|---|---|---|
| `PROGRESS` | `ok` or `no_result` that satisfies the phase | Advance the phase, save the checkpoint, next iteration |
| `RECOVERABLE` | `invalid_input` from model-proposed arguments; first guard suppression in a draft; model still rate-limited after the client's bounded retries | Re-plan once, within budget. A second failure of the same kind is terminal |
| `NEEDS_HUMAN` | `NAME_DISCREPANCY`; `INSUFFICIENT_QUOTATIONS`; `sole_eligible_option`; `EXCHANGE_RATE_REQUIRED`; no eligible offer; a withheld citation or no clause found; Gates 2 and 3; confirmation before `create_requisition_draft` | Pause with the reason and the options. State is preserved; the officer resolves and the loop resumes, or declines and the run stops with `OFFICER_DECLINED` |
| `TERMINAL`, state kept | `DATA_SOURCE_UNAVAILABLE`, `DATA_INTEGRITY_ERROR`, model or Policy Corpus unavailable, output fails its schema | Stop. A retry resumes from the checkpoint without repeating earlier steps (Requirements 7.5, 8.5, 9.4) |
| `TERMINAL`, boundary | `TOOL_NOT_ALLOWED`, `UNAUTHORIZED_ROLE`, `FORBIDDEN_TRANSITION`, second guard suppression | Stop, show a blocked-action error, write an audit entry (Requirement 14.4). Never retried |
| `TERMINAL`, limit | `ITERATION_LIMIT`, `TIMEOUT`, `NO_PROGRESS` | Stop and record the limit reached |

### 6. Run state

A checkpoint is written after every Observe step, holding:

| Field | Holds |
|---|---|
| `run_id`, `sku`, `review_date`, `officer_username` | Which review, which item, whose |
| `phase` | Where the loop is |
| `results` | Each completed step's envelope, keyed by phase, with a `data_fingerprint` |
| `confirmations` | Gate 2 and Gate 3 decisions, clearances and exception reasons, with who and when |
| `iterations`, `elapsed_s`, `replans` | Budget accounting |
| `pending_handoff` | What the officer is being asked, if anything |
| `stop_reason` | Set once, on the final iteration |

For Week 5 this is a JSON file per run under `var/agent-state/`, which is git-ignored. The Week
6 state model decides its permanent form. The checkpoint is **required and not yet built**: that
is a build status, not a design choice, and `TERMINAL`, state kept, depends on it.

A retry resumes from the
last checkpoint and does not repeat completed steps. Requirements 7.5, 8.5 and 9.4 each require
this, and the AI Boundary Matrix says the workflow "pauses while preserving current state, so
that a retry does not repeat completed steps".

**This is not built.** `AgentState` lives for one CLI invocation, so today a retry repeats the
scan, the eligibility check and the comparison. The same gap exists in the RAG pipeline. It is
the Week 6 state model's job (#26). Until then, every hand-off costs the officer a full re-run,
which is acceptable only because the repeated steps are read-only and spend no model quota.

### 7. Limits, and why these numbers

| Limit | Value | Reason |
|---|---|---|
| Iterations per item | **8** | The happy path uses 5. Officer clearance of a `NAME_DISCREPANCY` costs 2 re-checks, giving 7. One spare re-plan. At 6 the loop would stop with `ITERATION_LIMIT` on the exact case Requirement 4.6 exists for |
| Wall clock | 120 s | Covers one RAG call, measured at 42.01 s in Week 3, plus one draft call. Waiting at a hand-off is not counted |
| Re-plans per failure kind | 1 | Retrying the same failure is looping, not recovery |
| Repeated identical action | 0 | Same action and arguments twice in a row is `NO_PROGRESS`. **Not enforced yet**, so execution traces (#23) must not claim it |
| Model calls per run | ≤ 10 | One plan call per iteration plus the two AI-layer steps. The Model Selection Note makes requests per day the binding free-tier constraint |

Two accounting rules go with these. Time spent waiting at a hand-off is not counted against the
wall clock, because the officer's thinking time is not the agent's. Model retries happen inside
one iteration through `client.call_with_retry`, so they do not consume the iteration budget.

The action set is closed: four catalogue tools, two AI-layer steps, `hand_off` and `stop`. The
twelve prohibited names in tool-catalogue section 8 stay blocked in CI.

`.env.example` and `DEFAULT_MAX_ITERATIONS` in `agent/steps.py` are changed from 6 to 8 by this
contract, which supersedes the value `.env.example` has carried since Week 2.

### 8. Stop conditions

Every run ends with exactly one stop reason in the trace (Charter section 6, step 10). The
contract adopts the architecture's names; the implementation's current strings map onto them:

| Contract | Meaning | Current code |
|---|---|---|
| `DRAFT_CREATED` | Requisition written in `DRAFT` | `completed` |
| `NO_REORDER_NEEDED` | Nothing below its reorder point. Decided by `check_reorder_need` before any loop starts | `no_reorder_required` |
| `AWAITING_HUMAN` | Paused at a gate or a `NEEDS_HUMAN` outcome | `awaiting_human` |
| `OFFICER_DECLINED` | Officer refused at a gate | not implemented |
| `ITERATION_LIMIT` | Iteration budget spent | `max_iterations` |
| `TIMEOUT` | Wall clock spent | `timeout` |
| `NO_PROGRESS` | Same action and arguments twice | not implemented |
| `TOOL_NOT_ALLOWED`, `UNAUTHORIZED_ROLE`, `FORBIDDEN_TRANSITION`, `GUARD_SUPPRESSED` | Boundary refused; audit entry written (Requirement 14.4); never retried | `unauthorized`, `refused` |
| `DATA_SOURCE_UNAVAILABLE`, `DATA_INTEGRITY_ERROR`, `SERVICE_UNAVAILABLE`, `OUTPUT_SCHEMA_INVALID` | Failed with state kept | `failed` |

Three of the code's strings cover several contract names: `unauthorized` is both
`TOOL_NOT_ALLOWED` and `UNAUTHORIZED_ROLE`, `refused` covers two, `failed` covers four. The
architecture wants exactly one specific stop reason per run, so where the mapping is ambiguous
the trace records the code's string and no contract name rather than guessing. Reporting the
specific reason is a loop change, listed in section 12.

### 9. Human hand-off

Two gates are enforced today, and the officer passes them by re-running with `--confirm-comparison`
and `--confirm-draft`.

| Gate | Phase | Who | Status |
|---|---|---|---|
| Gate 2, comparison | `COMPARED` | Officer | Enforced |
| Gate 3, justification | `DRAFTED` | Officer | Not built; collapsed into the draft confirmation |
| Draft confirmation (not numbered) | Inside `JUSTIFICATION_CONFIRMED` | Officer | Enforced; `AGENT` still needs it |

Gate 1, confirming extracted quotation data, sits before the loop: the Week 4 tools read records
the officer has already confirmed. Gates 4 and 5, submit and approve or reject, sit after it.
Neither is reachable from inside the loop.

**Who writes the requisition.** `AGENT` may propose `create_requisition_draft`, but the
confirmed call executes under `PROCUREMENT_OFFICER`; `dispatch` swaps the identity once the
officer confirms (Requirement 9.1). The trace records the officer on that step.

Gate 2 is reached by any of these, which are the `NEEDS_HUMAN` triggers from section 5:

| Trigger | Meaning |
|---|---|
| `NAME_DISCREPANCY` | A quoted supplier name does not match the registered one (Requirement 4.6) |
| `INSUFFICIENT_QUOTATIONS` | Fewer comparable offers than the value band requires |
| `sole_eligible_option` | One eligible supplier, so POL-001-C04 needs a recorded exception reason |
| `EXCHANGE_RATE_REQUIRED` | A foreign-currency offer with no approved rate |

A withheld citation, or no clause found during `retrieve_policy`, is also `NEEDS_HUMAN`.

On a hand-off the state is preserved: the officer resolves it and the loop resumes, or declines
and the run stops with `OFFICER_DECLINED`.

Findings that need the officer are batched into Gate 2, so the officer is interrupted once
rather than after every tool. The exception is a comparison with no eligible offer, which hands
off immediately because there is nothing to confirm. Approval, rejection, submission and routing
sit outside the loop and are unreachable from it.

### 10. Worked example: cement, 120 bags

Real data, from `knowledge/data/` and the Week 4 tools. `AH-CM-001`, Portland cement 42.5N
50 kg bag, sits exactly at its reorder point of 150 on 25 September 2026, so
`check_reorder_need` flags it with a reorder quantity of 120 and one loop run opens.

Eligibility for category *cement and masonry* returns four suppliers: `SUP-006` Kireka Steel
and Cement Ltd is `BLACKLISTED`; `SUP-002` Lakeview Building Materials and `SUP-007` Lakeview
Building Supplies each return `NAME_DISCREPANCY`, being near-identical registered names;
`SUP-004` Bugolobi Hardware Supplies is eligible.

**Happy path, 5 iterations.**

| # | Phase | Action | Result | Class |
|---|---|---|---|---|
| 1 | `FRAMED` | `check_supplier_eligibility` | One eligible supplier; the two discrepancies are held for Gate 2 | `PROGRESS` |
| 2 | `ELIGIBILITY_CHECKED` | `compare_quotations` | `QT-002` only, landed **UGX 4,479,600**. `INSUFFICIENT_QUOTATIONS`, `sole_eligible_option: true` | `NEEDS_HUMAN`, Gate 2 |
| 3 | `COMPARISON_CONFIRMED` | `retrieve_policy` | Clauses such as POL-001-C02, POL-002-C04, POL-003-C03 | `PROGRESS` |
| 4 | `POLICY_RETRIEVED` | `draft_justification` | A draft citing only the retrieved clauses | `NEEDS_HUMAN`, Gate 3 |
| 5 | `JUSTIFICATION_CONFIRMED` | `create_requisition_draft` | Requisition written in `DRAFT` | stop, `DRAFT_CREATED` |

At Gate 2 the officer confirms the comparison and records a POL-001-C04 exception reason,
because the value band `500k_to_under_5m` requires three comparable quotations under POL-001-C02
and only one eligible offer exists. At Gate 3 the officer edits and confirms the justification.
After each, the loop resumes from its checkpoint.

**Alternative path, 7 iterations.** At Gate 2 the officer clears Lakeview Building Materials
instead, so the loop re-runs `check_supplier_eligibility` and then `compare_quotations`. Two
offers now rank, the requirement is still unmet at three, so the run returns to Gate 2 before
continuing to `DRAFT_CREATED`. Seven iterations, which is why the limit is 8 and not 6.

### 11. Trace

One row per iteration, written to `evidence/traces/agent-runs.jsonl`. Envelope statuses are the
catalogue's (`ok`, `no_result`, `invalid_input`, `unauthorized`, `unavailable`, `failed`) and the
class is one of section 5's. There are no ad-hoc statuses.

```json
{"run_id": "AGT-2026-0925-001", "sku": "AH-CM-001", "review_date": "2026-09-25",
 "officer_username": "a.nakato", "contract": {"path": "contracts/agent-task-contract.json",
 "version": "1.0"}, "iterations": 5, "elapsed_s": 61.4, "replans": 0,
 "stop_reason": "DRAFT_CREATED",
 "confirmations": {
   "gate_2_comparison": {"by": "a.nakato", "at": "2026-09-25T09:14:02Z",
                         "exception_reason": "Sole eligible supplier for cement; POL-001-C04"},
   "gate_3_justification": {"by": "a.nakato", "at": "2026-09-25T09:21:40Z", "edited": true}},
 "steps": [
  {"iteration": 1, "phase": "FRAMED", "caller_role": "AGENT",
   "action": "check_supplier_eligibility", "status": "ok", "class": "PROGRESS"},
  {"iteration": 2, "phase": "ELIGIBILITY_CHECKED", "caller_role": "AGENT",
   "action": "compare_quotations", "status": "ok", "errors": ["INSUFFICIENT_QUOTATIONS"],
   "class": "NEEDS_HUMAN", "handoff": {"gate": 2,
   "reason": "sole_eligible_option; 1 of 3 required quotations (POL-001-C02)"}},
  {"iteration": 3, "phase": "COMPARISON_CONFIRMED", "caller_role": "AGENT",
   "action": "retrieve_policy", "status": "ok", "class": "PROGRESS"},
  {"iteration": 4, "phase": "POLICY_RETRIEVED", "caller_role": "AGENT",
   "action": "draft_justification", "status": "ok", "class": "NEEDS_HUMAN",
   "handoff": {"gate": 3, "reason": "Officer edits and confirms the justification"}},
  {"iteration": 5, "phase": "JUSTIFICATION_CONFIRMED", "caller_role": "PROCUREMENT_OFFICER",
   "action": "create_requisition_draft", "status": "ok", "class": "PROGRESS",
   "requisition_id": "REQ-2026-001", "status_written": "DRAFT"}]}
```

`caller_role` is `AGENT` for the loop's own steps. `create_requisition_draft` executes under
`PROCUREMENT_OFFICER`, after confirmation, because the write belongs to the officer.

### 12. Known gaps this contract records

1. **The planner is deterministic today.** This contract sets Gemini-proposes as the design; the
   loop does not call the model yet. The policy gate is identical either way, so the change is
   contained to the plan step.
2. **State does not survive a run** (section 6).
3. **FA-10 is closed (6 October 2026).** `dispatch.invoke` now checks every tool response
   against its output schema and discards a non-conforming one with `OUTPUT_SCHEMA_INVALID`, so
   that stop reason can now be raised. It still surfaces as the code's coarse `failed` (gap 5).
4. **Two phases are unbuilt**, and a run currently skips them.
5. **Stop reasons are coarser in code than in this contract.** `unauthorized`, `refused` and
   `failed` each cover several contract names, so a trace cannot yet name which one applied.
6. **`NO_PROGRESS` is not enforced**, so the repeated-action limit is a rule without a check
   behind it.

### 13. Traceability

| Requirement | How this contract meets it |
|---|---|
| Charter section 6, steps 3 to 8 | Goal and phases, one run per flagged item |
| Charter section 6, step 10 | One stop reason per run, trace fields in section 11 |
| Requirement 4.6 | `NAME_DISCREPANCY` is a `NEEDS_HUMAN` hand-off; the iteration budget allows the re-checks it costs |
| Requirements 7.5, 8.5, 9.4 | Checkpoint resume required in section 6, recorded as not built |
| Requirement 14.2 | Guard suppression stops the run; suppressed text is never traced |
| Requirement 14.3 | No transition beyond `DRAFT`; `max_status: DRAFT` |
| Requirement 14.4 | Blocked actions stop the run and write an audit entry |
| AI Boundary Matrix | The loop sequences approved actions; it never decides eligibility, computes figures or approves |
