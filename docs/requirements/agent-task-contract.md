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
| Stop-reason names | `DRAFT_CREATED`, `ITERATION_LIMIT`, `NO_PROGRESS` | `completed`, `max_iterations` | **The architecture's names**, with the mapping in section 7 |

Two consequences for other pages: the architecture doc says "no planner, loop or run state is
implemented yet", which PR #60 has overtaken, and `.env.example` carries
`AGENT_MAX_ITERATIONS=6`, which section 6 changes to 8.

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

Until the two unbuilt phases exist, a run goes `COMPARISON_CONFIRMED → JUSTIFICATION_CONFIRMED`
directly, and the justification is compiled from tool results rather than drafted. The trace
must record the skip, so no run claims a justification that was never drafted.

### 5. State

One checkpoint per completed phase, holding the fields in section 2. A retry resumes from the
last checkpoint and does not repeat completed steps. Requirements 7.5, 8.5 and 9.4 each require
this, and the AI Boundary Matrix says the workflow "pauses while preserving current state, so
that a retry does not repeat completed steps".

**This is not built.** `AgentState` lives for one CLI invocation, so today a retry repeats the
scan, the eligibility check and the comparison. The same gap exists in the RAG pipeline. It is
the Week 6 state model's job (#26). Until then, every hand-off costs the officer a full re-run,
which is acceptable only because the repeated steps are read-only and spend no model quota.

### 6. Limits, and why these numbers

| Limit | Value | Reason |
|---|---|---|
| Iterations per item | **8** | The happy path uses 5. Officer clearance of a `NAME_DISCREPANCY` costs 2 re-checks, giving 7. One spare re-plan. At 6 the loop would stop with `ITERATION_LIMIT` on the exact case Requirement 4.6 exists for |
| Wall clock | 120 s | Covers one RAG call, measured at 42.01 s in Week 3, plus one draft call. Waiting at a hand-off is not counted |
| Re-plans per failure kind | 1 | Retrying the same failure is looping, not recovery |
| Repeated identical action | 0 | Same action and arguments twice in a row is `NO_PROGRESS` |
| Model calls per run | ≤ 10 | One plan call per iteration plus the two AI-layer steps. The Model Selection Note makes requests per day the binding free-tier constraint |

`.env.example` must change from `AGENT_MAX_ITERATIONS=6` to `8`, with `DEFAULT_MAX_ITERATIONS`
in `agent/steps.py`.

### 7. Stop conditions

Every run ends with exactly one stop reason in the trace (Charter section 6, step 10). The
contract adopts the architecture's names; the implementation's current strings map onto them:

| Contract | Meaning | Current code |
|---|---|---|
| `DRAFT_CREATED` | Requisition written in `DRAFT` | `completed` |
| `NO_REORDER_NEEDED` | Nothing below its reorder point | `no_reorder_required` |
| `AWAITING_HUMAN` | Paused at a gate or a `NEEDS_HUMAN` outcome | `awaiting_human` |
| `OFFICER_DECLINED` | Officer refused at a gate | not implemented |
| `ITERATION_LIMIT` | Iteration budget spent | `max_iterations` |
| `TIMEOUT` | Wall clock spent | `timeout` |
| `NO_PROGRESS` | Same action and arguments twice | not implemented |
| `TOOL_NOT_ALLOWED`, `UNAUTHORIZED_ROLE`, `FORBIDDEN_TRANSITION`, `GUARD_SUPPRESSED` | Boundary refused; audit entry written (Requirement 14.4); never retried | `unauthorized`, `refused` |
| `DATA_SOURCE_UNAVAILABLE`, `DATA_INTEGRITY_ERROR`, `SERVICE_UNAVAILABLE`, `OUTPUT_SCHEMA_INVALID` | Failed with state kept | `failed` |

### 8. Human hand-off

Two gates are enforced today, and the officer passes them by re-running with `--confirm-comparison`
and `--confirm-draft`.

| Gate | When | Who | Status |
|---|---|---|---|
| Gate 2, comparison | Landed-cost table ready | Officer | Enforced |
| Gate 3, justification | Draft justification ready | Officer | Not built; collapsed into the draft confirmation |
| Draft confirmation | Before `create_requisition_draft` | Officer | Enforced; `AGENT` still needs it |

Findings that need the officer are batched into Gate 2, so the officer is interrupted once
rather than after every tool. The exception is a comparison with no eligible offer, which hands
off immediately because there is nothing to confirm. Approval, rejection, submission and routing
sit outside the loop and are unreachable from it.

### 9. Known gaps this contract records

1. **The planner is deterministic today.** This contract sets Gemini-proposes as the design; the
   loop does not call the model yet. The policy gate is identical either way, so the change is
   contained to the plan step.
2. **State does not survive a run** (section 5).
3. **FA-10 is open.** `dispatch.invoke` validates tool inputs but not tool outputs, and returns
   `status: ok` for a malformed result. The `OUTPUT_SCHEMA_INVALID` stop reason above cannot be
   raised until that is fixed, so this contract depends on it.
4. **Two phases are unbuilt**, and a run currently skips them.

### 10. Traceability

| Requirement | How this contract meets it |
|---|---|
| Charter section 6, steps 3 to 8 | Goal and phases, one run per flagged item |
| Charter section 6, step 10 | One stop reason per run, trace fields in section 2 |
| Requirement 4.6 | `NAME_DISCREPANCY` is a `NEEDS_HUMAN` hand-off; the iteration budget allows the re-checks it costs |
| Requirements 7.5, 8.5, 9.4 | Checkpoint resume required in section 5, recorded as not built |
| Requirement 14.2 | Guard suppression stops the run; suppressed text is never traced |
| Requirement 14.3 | No transition beyond `DRAFT`; `max_status: DRAFT` |
| Requirement 14.4 | Blocked actions stop the run and write an audit entry |
| AI Boundary Matrix | The loop sequences approved actions; it never decides eligibility, computes figures or approves |
