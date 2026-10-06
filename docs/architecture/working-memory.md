# Working Memory / State Demonstration

| Field | Value |
|---|---|
| Week | 6 |
| Owner | Lukaanya George |
| Due | 9 October 2026 |
| Status | Complete, awaiting team review |
| Path | `docs/architecture/working-memory.md` |

## Brief requirement

Write-up showing that memory improves a legitimate task without silently controlling critical decisions. Link the code and a before/after run.

## Write-up

### What this demonstrates

Two things the Week 5 agent could not do.

1. **Persistent memory.** Charter section 7 scopes exactly one memory use case: *"prior
   requisition outcomes and supplier performance notes as advisory context."* The agent now shows
   both beside the comparison at Gate 2. **Memory changes no decision:** eligibility, landed cost,
   ranking and the requisition are byte-for-byte the same with and without it, and a test proves
   it.
2. **Persisted run state.** A re-run of the same review now resumes from a checkpoint instead of
   repeating every step. This closes gap 2 of the
   [Agent Task Contract](../requirements/agent-task-contract.md) and meets Requirements 7.5, 8.5
   and 9.4: *"preserve … so that retrieval can be retried without repeating earlier steps."*

The formal state model (#26, Sekyeza) and the Memory Design and Data Handling Note (#27,
Beingana) are separate deliverables. This page shows the working code. Section 7 lists the record
shapes they describe.

### 1. How to run it

No API key and no network. The demonstration uses the real CLI against the registered datasets.

```bash
pip install -e ".[dev]"
cp fixtures/memory/demo-memory.jsonl var/memory/procurement-memory.jsonl   # seed notes

# Before: memory switched off
procurement-agent --review-date 2026-09-25 --sku AH-CM-001 --no-memory --fresh

# After: same review, memory on (the default)
procurement-agent --review-date 2026-09-25 --sku AH-CM-001 --fresh

# Officer confirms at Gate 2: the run resumes and calls only the draft tool
procurement-agent --review-date 2026-09-25 --sku AH-CM-001 --confirm-comparison --confirm-draft

# Officer maintains memory
procurement-memory add-note --supplier SUP-004 --text "Confirmed 7-day lead time by phone."
procurement-memory list
procurement-memory forget MEM-0c9e96b9fd
procurement-memory purge-expired
```

New agent options: `--state-dir` (default `var/agent-state/`), `--no-state`, `--fresh`,
`--memory` (default `var/memory/procurement-memory.jsonl`) and `--no-memory`. Both stores are
under `var/`, which git ignores.

### 2. Before and after: memory improves the task

The task is the Gate 2 decision the officer faces for 120 bags of cement on 25 September. Only
one eligible offer remains (QT-002, Bugolobi Hardware Supplies, UGX 4,479,600). The two Lakeview
offers are excluded for `NAME_DISCREPANCY`, the cheapest offer is from a blacklisted supplier,
and POL-001-C04 needs an exception reason. The officer must decide whether to confirm.

**Before** ([`01-before-no-memory.json`](../../evidence/traces/memory/01-before-no-memory.json)),
the officer sees the comparison and nothing else.

**After** ([`02-after-with-memory.json`](../../evidence/traces/memory/02-after-with-memory.json)),
the same comparison, plus:

```
memory:     3 advisory record(s); did not change any decision
  - [MEM-0c9e96b9fd] SUP-004 note by a.nakato on 2026-09-10: "Last two cement deliveries arrived
    two days after the quoted lead time. Confirm the 7-day lead time before relying on it."
  - [MEM-8fe62d8f82] SUP-002 note by a.nakato on 2026-08-28: "Registered entity is Lakeview
    Building Materials Ltd, Ntinda. It is not the same business as Lakeview Building Supplies;
    check the letterhead and TIN on any quotation."
  - [MEM-feff4c2759] SUP-006 note by a.nakato on 2026-06-15: "Placed on the Blacklist in June
    2026 after short-weight cement bags on two deliveries."
```

Each record bears on the decision in front of the officer:

| Record | What it adds | What it does **not** do |
|---|---|---|
| SUP-004 lead-time note | The only eligible supplier has run late twice; worth a phone call before relying on a 7-day lead time | Change SUP-004's rank or landed cost |
| SUP-002 registration note | The evidence the officer needs to resolve the `NAME_DISCREPANCY` under Requirement 4.6 | Clear the discrepancy. SUP-002 stays excluded until the officer records clearance |
| SUP-006 blacklist note | Why the cheapest offer is barred, ready for the exception reason | Remove or reinstate SUP-006 |
| Last week's outcome (from the second week on) | What the agent ranked first last time, and that an exception was needed then too | Carry last week's choice forward |

Field by field, `reorder`, `eligibility`, `comparison`, `draft`, the stop reason, the iteration
count and every tool status are equal between the two runs.

**The following week remembers.** When the officer completes the run, the agent records the
outcome. The review on 2 October
([`05-next-week-remembers.json`](../../evidence/traces/memory/05-next-week-remembers.json)) shows
it:

```
  - [MEM-9cc6ddb6f1] AH-CM-001 on 2026-09-25: ranked first Bugolobi Hardware Supplies (QT-002),
    UGX 4,479,600; exception required; REQ-2026-001 left in DRAFT
```

### 3. Why memory cannot silently control a decision

Labels are not enough, so each guarantee is enforced in code and covered by a test in
[`tests/test_memory.py`](../../tests/test_memory.py).

| Guarantee | How it is enforced | Test |
|---|---|---|
| Memory is read only after every decision is made | It is read once, in `_finish`, after the last tool call. It is not on `AgentState`, so the planner never sees it, and no tool takes it as input | `test_memory_is_read_only_after_every_tool_call` checks the order: tool, tool, tool, then memory |
| Decisions are identical with and without memory | — | `test_every_decision_is_identical_with_and_without_memory` |
| A note cannot clear an exclusion | Eligibility is computed only from the supplier register | `test_a_clearance_note_does_not_clear_the_discrepancy` |
| It says what it is | Every result carries `"advisory": true` and `"influenced_decisions": false`, and the report prints "did not change any decision" | the same tests |
| Memory cannot assert authority | A note claiming approval, award or commitment is refused at write time (`guards.scan`), and screened again at display in case the file was edited by hand | `test_notes_that_assert_authority…`, `test_a_note_edited_by_hand…` |
| Only the officer writes | `AGENT` and `PROCUREMENT_MANAGER` cannot add or delete notes. The agent writes only an outcome, and only on a completed run | `test_only_the_officer_writes_notes`, `test_an_incomplete_run_writes_no_memory` |
| No hindsight | A record dated after the review date is not shown for that review | `test_a_note_written_after_the_review_is_not_shown_for_it` |

### 4. Run state: resume instead of repeat

The checkpoint is saved after every tool step and at every stop, under
`var/agent-state/<run_id>.json`. The `run_id` is the review date, the item and the officer, so
re-running the same review finds it.

| Run | Evidence | What happened |
|---|---|---|
| Stop at Gate 2 | [`02`](../../evidence/traces/memory/02-after-with-memory.json) | 3 tool calls; checkpoint saved |
| Officer confirms | [`03`](../../evidence/traces/memory/03-resume-after-gate-2.json) | Scan, eligibility and comparison restored. **1 call** (`create_requisition_draft`). Iterations 4 / 8, because the budget spans re-runs |
| Same command again | [`04`](../../evidence/traces/memory/04-rerun-no-duplicate.json) | "Already completed: REQ-2026-001 is in DRAFT." **0 calls.** Before Week 6, re-running this command would have compiled a second requisition |
| Supplier register missing | [`06`](../../evidence/traces/memory/06-failure-suppliers-missing.json) | Stops `failed`, `DATA_SOURCE_UNAVAILABLE`, after 2 calls; state kept |
| Register restored, re-run | [`07`](../../evidence/traces/memory/07-recovery-resumes.json) | Resumes at eligibility. The scan is **not** repeated: 2 calls |

Three rules keep resuming safe:

- **A stale result is never reused.** Each step records fingerprints of the files it read
  (inventory, suppliers, quotations). On resume they are recomputed, and the first step whose
  inputs changed, with every step after it, runs again.
- **A confirmation belongs to the comparison it confirmed.** If the comparison is recomputed,
  Gate 2 is asked again (`test_changed_data_recomputes_from_the_first_affected_step`).
- **The iteration budget belongs to the run**, not to one command, so retrying cannot reset the
  bound of 8 (`test_the_iteration_budget_spans_re_runs`, `test_retries_that_reuse_nothing…`).
  `--fresh` starts a new run.

An unreadable checkpoint is ignored, never partly trusted. The checkpoint holds working state
only: tool results the run already produced, gate confirmations, counts and the stop reason. It
holds no document text.

### 5. What is stored, who may access it, and for how long

The data-handling note (#27) is the authority. This is what the code does today.

| | Run checkpoint | Supplier note | Prior outcome |
|---|---|---|---|
| Where | `var/agent-state/<run_id>.json` | `var/memory/procurement-memory.jsonl` | same file |
| Written by | The loop, after each step | `PROCUREMENT_OFFICER` only | The loop, on a completed run only |
| Read by | The same review's next run | Officer, manager, agent (display only) | same |
| Contents | Tool results, confirmations, counts, stop reason | Supplier id, ≤ 280 characters of text, author, date | Item, top-ranked supplier and offer, landed cost, exception flag, excluded suppliers, requisition id in DRAFT |
| Retention | Until `--fresh` or deleted. **No expiry yet** (see section 8) | 365 days, shorter if set | 365 days |
| Deletion | `--fresh`, or delete the file | `procurement-memory forget <id>` (officer only); `purge-expired` | same |

The deletion and refusal transcript is
[`memory-cli.txt`](../../evidence/traces/memory/memory-cli.txt). All records are synthetic.

### 6. Tests

`tests/test_agent_checkpoint.py` (10 tests) and `tests/test_memory.py` (18 tests). No API key.
The full suite passes.

### 7. Shapes for the state model and the data-handling note

So that #26 and #27 can describe what exists:

- **Checkpoint**: the fields `checkpoint_format`, `run_id`, `review_date`, `sku`,
  `officer_username`, `contract_version`, `step`, `iterations`, `stop_reason`, `stop_detail`,
  `results{scan, eligibility, compare, draft}`, `step_sources{step: {inventory, suppliers,
  quotations}}`, `confirmations{comparison, draft: {by, at}}`, `saved_at`.
- **Steps** move `scan → eligibility → compare → draft`. The checkpoint stores the next step to
  run. A completed run keeps `draft` and never runs again.
- **Memory record**: `id`, `kind` (`supplier_note` or `prior_outcome`), `supplier_id`,
  `recorded_on`, `expires_on` and `source`, plus `text` and `author` for a note, or the outcome
  fields for an outcome.

### 8. Limits

- **The gates are command-line flags**, as in Week 5. There is no screen and no authentication;
  `--role` and `--officer` are trusted.
- **An outcome records the DRAFT, not the manager's decision.** Gate 5 is not built, so memory
  cannot yet say whether a past requisition was approved or rejected.
- **Checkpoints do not expire.** They need a retention rule, which is the state model's decision.
- **Memory is a plain local file.** It is not encrypted and has no access control beyond the
  operating system. That is acceptable for synthetic data, and not for real supplier data.
- **The stop codes are still coarse**: `failed` covers several contract reasons (contract
  gap 5).

### Code

| Path | Role |
|---|---|
| [`src/procurement_agent/agent/checkpoint.py`](../../src/procurement_agent/agent/checkpoint.py) | Save, restore and invalidate run state |
| [`src/procurement_agent/agent/workflow.py`](../../src/procurement_agent/agent/workflow.py) | Resume, confirmations, memory read after decisions, outcome write |
| [`src/procurement_agent/memory/store.py`](../../src/procurement_agent/memory/store.py) | Memory records, rules, retention, deletion |
| [`src/procurement_agent/memory/cli.py`](../../src/procurement_agent/memory/cli.py) | `procurement-memory` officer commands |
| [`fixtures/memory/demo-memory.jsonl`](../../fixtures/memory/demo-memory.jsonl) | Synthetic seed notes |
| [`evidence/traces/memory/`](../../evidence/traces/memory/) | Recorded runs, readable reports, CLI transcript |
