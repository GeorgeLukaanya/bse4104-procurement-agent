# State Model

| Field | Value |
|---|---|
| Week | 6 |
| Owner | Sekyeza Elroy Nunda |
| Due | 9 October 2026 |
| Status | Complete, awaiting team review |
| Path | `docs/architecture/state-model.md` |

## Brief requirement

Model workflow/session state explicitly: states, transitions, what is stored per run, and what is discarded when a run ends.

## Write-up

### 1. Overview

A weekly review is not one command. The officer starts it, the loop stops at a gate, the officer
confirms, and the run continues later. Until Week 6 nothing survived between those commands, so
every continuation repeated the scan, the eligibility check and the comparison. PR #65 added a
checkpoint, and this document models what it holds, when it is written, what is reused and what
is thrown away.

The checkpoint is working state only: results the run already produced, who passed which gate,
the iteration count and the stop reason. It holds no quotation text, no policy text and nothing
the run did not compute itself.

### 2. Storage

| | |
|---|---|
| Location | `var/agent-state/<run_id>.json`, one file per run |
| Tracked in git | No, `var/` is git-ignored |
| Written | After every tool step, and at every stop |
| Format | JSON, `checkpoint_format: 1`. A file of another format version is ignored rather than guessed at |

**The run identifier is deterministic**, not random:

```
AGT-<review_date>-<sku or ALL>-<officer_username>
AGT-2026-09-25-AH-CM-001-a.nakato
```

That is what makes a continuation find its own checkpoint. The same review, item and officer
produce the same name every time, so the officer re-runs the same command and the loop picks up
where it stopped. A different item or a different officer is a different run with its own file.
Characters outside `A-Za-z0-9_.-` in the username are replaced, so the identifier is always a
safe filename.

**Writes are atomic.** The checkpoint is written to `<run_id>.json.tmp` and then renamed over
the real file, so a crash mid-write leaves the previous checkpoint intact rather than half of a
new one. The memory store does the same.

There is no database. Every store in the project is a file: the checkpoint here, the traces and
memory in section 3, the requisition store, and the policy index. This suits one officer running
one review at a time on one machine, which is the system as scoped. It would not survive two
officers writing at once, or a container whose filesystem is wiped on restart. Each store is
already behind a small class (`CheckpointStore`, `MemoryStore`, `TraceLog`), so moving to SQLite
later means replacing those classes and not the loop.

### 3. Three tiers of state

| Tier | Lives for | Where | Holds | Discarded |
|---|---|---|---|---|
| **Ephemeral** | One command | RAM (`AgentState`) | The current step, the planner's proposal, elapsed time, the in-flight tool envelope, the loaded contract | When the process exits |
| **Medium-lived, session** | One review of one item | `var/agent-state/<run_id>.json` | `run_id`, `review_date`, `sku`, `officer_username`, `contract_version`, `step`, `iterations`, `stop_reason`, `stop_detail`, `results{scan, eligibility, compare, draft}`, `step_sources`, `confirmations`, `saved_at` | `--fresh`, manual deletion, or the retention rule in section 7 |
| **Long-lived, persistent** | The project | `evidence/traces/agent-runs.jsonl` (append-only run history) and `var/memory/procurement-memory.jsonl` (prior outcomes and supplier notes) | What happened, for evidence and advisory context | Traces never. Memory notes expire after 365 days and are removed by `procurement-memory purge-expired` |

The two long-lived files answer different questions. A trace says what one run did and is
evidence. Memory says what previous runs found, is advisory only, and is shown to the officer
beside the comparison; it never reaches the planner, a tool or the ranking.

### 4. Code steps and contract phases

The loop runs four steps. The [Agent Task Contract](../requirements/agent-task-contract.md)
names seven phases. They line up like this:

| Code step | Contract phase it serves | Tool | Note |
|---|---|---|---|
| `scan` | Before the loop | `check_reorder_need` | The contract puts this before `FRAMED`: it runs once per review and opens one run per flagged item |
| `eligibility` | `FRAMED` → `ELIGIBILITY_CHECKED` | `check_supplier_eligibility` | |
| `compare` | `ELIGIBILITY_CHECKED` → `COMPARED` | `compare_quotations` | Stops at Gate 2 |
| (hand-off) | `COMPARED` → `COMPARISON_CONFIRMED` | none | The officer confirms; not an action the loop can take |
| — | `COMPARISON_CONFIRMED` → `POLICY_RETRIEVED` | `retrieve_policy` | **Not wired in.** The RAG pipeline exists but the loop does not call it |
| — | `POLICY_RETRIEVED` → `DRAFTED` | `draft_justification` | **Not built** |
| (hand-off) | `DRAFTED` → `JUSTIFICATION_CONFIRMED` | none | Gate 3, not built; collapsed into the draft confirmation |
| `draft` | `JUSTIFICATION_CONFIRMED` → `DRAFT_CREATED` | `create_requisition_draft` | Officer confirmation required |

So four steps cover five of the seven phases, and a run currently goes from a confirmed
comparison straight to the draft. The checkpoint stores the code step, not the contract phase,
because the step is what the loop resumes on. When the two missing phases are built, the
checkpoint gains their results and this table is what has to change with it.

### 5. Transitions

```
start ──▶ scan ──▶ eligibility ──▶ compare ──▶ [Gate 2] ──▶ draft ──▶ DRAFT_CREATED
            │           │             │                        │
            └───────────┴─────────────┴────────────────────────┴──▶ stop with a reason
```

Every step ends in one of three ways: it advances, it hands off to the officer, or it stops the
run with a reason. The checkpoint records which, so the next command knows what it is resuming.

### 6. Resume, and when a saved result is thrown away

A saved result is reused only while the data it was computed from is unchanged.

**Fingerprints.** Each step records the SHA-256 of every file it read, in `step_sources`:

| Step | Depends on |
|---|---|
| `scan` | `inventory` |
| `eligibility` | `suppliers`, `quotations` |
| `compare` | `inventory`, `suppliers`, `quotations` |
| `draft` | nothing; it compiles results the run already holds |

`eligibility` depends on the quotations because the planner reads them to choose which suppliers
to check.

**On resume** the fingerprints are recomputed. The first step whose inputs changed is re-run, and
so is every step after it. A stale comparison is never carried forward into a requisition.

**Confirmations follow their comparison.** A Gate 2 confirmation belongs to the table the officer
actually saw. If the comparison is being recomputed, the `comparison` and `draft` confirmations
are dropped and the officer is asked again. Confirming a landed-cost table and then quietly
applying that confirmation to a different one would defeat the gate.

**The iteration budget is cumulative.** The contract's limit of 8 belongs to the run, not to one
command. A resumed run restores its count, so three commands of three iterations each stop at
the limit rather than giving the loop 24.

**A completed run stays completed.** If the checkpoint already holds a draft, re-running returns
the existing requisition and calls no tool, so the same review cannot compile a second
requisition. `--fresh` is the deliberate way to start over.

`--no-state` turns checkpointing off entirely, which is what the tests use.

### 7. Retention

| Rule | Value |
|---|---|
| Checkpoint retention | **30 days** after `saved_at` |
| Enforced by | Nothing yet. **Target specification**, not implemented |
| Manual removal today | `--fresh` for one review, or deleting files under `var/agent-state/` |
| Planned | A housekeeping command that prunes checkpoints older than 30 days, in the shape of `procurement-memory purge-expired` |

Thirty days is chosen because a weekly review that has not been finished within a month is
abandoned, not paused, and its prices and supplier statuses are stale anyway. The rule applies
only to checkpoints. Traces are evidence and are never pruned; memory notes keep their own
365-day expiry.

Until the housekeeping command exists, checkpoints accumulate. They are small, git-ignored and
hold no document text, so the cost is disk space rather than risk.

### 8. Contract Gap 2: resolved

The Agent Task Contract recorded as Gap 2 that state did not survive a run, which made the
contract's `TERMINAL`, state kept, class unfulfillable: it promises a retry that resumes from
the checkpoint, and there was no checkpoint.

**Resolved by PR #65.** Checkpoints persist, resume works, and the contract's `run_state` block
is now `built: true`. Requirements 7.5, 8.5 and 9.4 each ask for a retry that does not repeat
completed steps, and the fingerprint rule in section 6 is what makes that safe rather than
merely fast.

### 9. Traceability

| Requirement | How this model meets it |
|---|---|
| 7.5, 8.5, 9.4 | A retry resumes from the checkpoint and repeats only steps whose inputs changed |
| 9.1 | The draft confirmation is stored with who and when, and is dropped if the comparison it belongs to is recomputed |
| 13.1 | Every run appends to `evidence/traces/agent-runs.jsonl`, which is never pruned |
| 14.3 | A completed run returns its existing requisition rather than compiling another |
| Charter section 7 | Persistent memory is limited to prior outcomes and supplier notes, advisory only |
| Agent Task Contract section 6 | The checkpoint fields and the cumulative iteration budget are the contract's run-state block |
