# Memory Design and Data Handling Note

| Field | Value |
|---|---|
| Week | 6 |
| Owner | Beingana Jim Junior |
| Due | 9 October 2026 |
| Version | 1.0 — 9 October 2026 |
| Status | Complete, awaiting team review |
| Path | `docs/architecture/memory-design.md` |

## 1. Purpose and justified use case

The [Project Charter, section 7](../requirements/project-charter.md) scopes one persistent-memory use case: **prior requisition outcomes and supplier performance notes as advisory context**. A weekly review can reuse a relevant observation without asking the officer to reconstruct last week's work. Memory supplies context for the officer's review; the current inventory, supplier register, quotations and policy remain the authoritative sources.

For the cement review, only Bugolobi Hardware Supplies remains eligible. A dated note that its last two deliveries arrived late helps the officer question the current lead time. A prior outcome shows that last week's draft also required a quotation-count exception. Neither record establishes current eligibility, supplier selection or approval. The officer still reviews the current comparison and confirms the draft.

This design follows the existing implementation rather than adding a new store or a new autonomous decision. The [working memory demonstration](working-memory.md) provides before/after evidence; the [state model](state-model.md) defines checkpoints and resume. Both are companion deliverables.

## 2. Memory and working state

| Information | Lifetime and storage | Purpose | Use in decisions |
|---|---|---|---|
| Ephemeral run state | RAM, `AgentState`; discarded when the command exits | Current step, tool results, budget and confirmations | Used by the current bounded workflow |
| Review checkpoint | `var/agent-state/<run_id>.json` | Resume the same review without repeating valid completed steps | Reused only after input fingerprints are checked; changed comparisons lose their confirmations |
| Persistent advisory memory | `var/memory/procurement-memory.jsonl` | Supplier observations and prior draft outcomes across reviews | Displayed alongside the result; never supplied to the planner, tools, ranking or requisition |
| Execution evidence | `evidence/traces/agent-runs.jsonl` and recorded examples | Explain what a run did and verify behaviour | Evidence, not a memory source for the planner |

`var/` is git-ignored. The evidence and fixture folders intentionally contain synthetic examples for assessment. There is no vector memory index, conversation history store or external memory service. Retrieval uses structured supplier identifiers and item SKU, avoiding similarity matches between lookalike supplier names.

## 3. What is stored and why

The memory file holds one JSON object per line. Both record types have a content-derived `MEM-` identifier, `kind`, source, recorded date and expiry date. The identifier supports lookup and deletion; it is not proof that a file has not been altered.

| Record | Stored fields | Justification |
|---|---|---|
| `supplier_note` | `id`, `kind`, `supplier_id`, `text`, `author`, `source: officer`, `recorded_on`, `expires_on` | Attribute a short observation to its author and supplier; show its age and control its useful lifetime |
| `prior_outcome` | `id`, `kind`, `sku`, `supplier_id`, `supplier_name`, `quotation_id`, `landed_cost_ugx`, `exception_required`, `excluded_suppliers`, `requisition_id`, `requisition_status: DRAFT`, `run_id`, `source: agent-run`, `recorded_on`, `expires_on` | Describe the current comparison's top-ranked offer and resulting draft, with provenance and any quotation-count exception |

A prior outcome records **ranked first**, not awarded. It stores no manager decision because that gate is not implemented. Its recorded date is the review date, not a separate write timestamp; a backdated review therefore creates a backdated outcome and expiry.

Notes must name a supplier identifier in `SUP-000` form, contain 1–280 characters after trimming and pass `guards.scan`. Identifier validation checks format, not existence in the supplier register. The officer is responsible for checking the referenced supplier and the accuracy of the observation. Keep notes factual, dated and limited to synthetic procurement information.

Do not store API keys, credentials, raw quotation or policy documents, full prompts or chat transcripts in memory. The current write methods have no fields for those artefacts, but free-text notes still require review. Supplier names, officer identifiers, prices and exceptions are included only where they explain the scoped task.

## 4. Write, retrieve and display lifecycle

1. **Officer records an observation.** `MemoryStore.add_note` checks the supplied role, supplier-id format, text length, prohibited assertions, date and requested retention, then appends a note. The CLI defaults to officer identity `a.nakato`; this is a supplied identity, not authentication.
2. **The workflow makes its current decisions.** Inventory, eligibility and comparison tools execute under their existing controls. Memory is absent from `AgentState` and is not read during planning or tool execution.
3. **At a stop, the workflow reads relevant memory.** `_finish` calls `_advise` after the tool calls. `relevant` selects records matching a supplier from the eligibility result or the reviewed SKU. It excludes records recorded after the review date and records already expired on that date, then orders newest first. This includes notes about excluded suppliers so the officer can understand discrepancies.
4. **The officer sees labelled context.** The result carries `advisory: true` and `influenced_decisions: false`, dates, identifiers and summaries. Note text is scanned again before display; prohibited approval, award or commitment assertions are replaced by a withholding message.
5. **A new completed draft is remembered.** After successful draft creation, `_remember_outcome` appends a prior outcome. Paused or failed runs write no outcome. Reusing an already-completed checkpoint does not append another outcome. A deliberately fresh run can produce another draft and outcome; this is not general deduplication.

Memory shown on the completion result is read before that run's new outcome is appended; later reviews can see the outcome. `--no-memory` disables advisory memory. A missing memory file gives an empty set, so lack of history does not determine the purchase.

## 5. Access and security boundary

| Operation | Intended actor | Existing enforcement |
|---|---|---|
| Read notes and outcomes | Officer, manager; agent may assemble advisory display | CLI accepts the catalogue roles. Store read methods have no role parameter; filesystem access is the actual read boundary |
| Add supplier note | Procurement Officer | `add_note` rejects `AGENT` and `PROCUREMENT_MANAGER` |
| Record prior outcome | Workflow acting as officer or agent after a newly completed draft | Store accepts officer/agent; workflow enforces successful completion. Manager is refused |
| Delete an individual record | Procurement Officer | `forget` checks officer role and memory-id format |
| Purge expired records | Officer or explicitly authorised housekeeping | **Gap:** `purge_expired` and its CLI path perform no role check |
| Read/write/reset checkpoint | Workflow for the same review, item and officer | Identity fields are matched on restore; CLI role and officer flags are trusted, and files remain readable to the local OS user |

All data is synthetic and local. There is no encryption at rest, authenticated login, enforced per-user filesystem isolation or remotely hosted memory. Supplying an officer role is not proof of identity. An OS user who can edit the file can bypass the CLI controls. Before extending the design to real records or multiple users, enforce authenticated roles at every entry point, restrict file access and audit maintenance actions.

Memory notes are untrusted data. The approval-pattern scan rejects some unsafe assertions; it is not a general prompt-injection detector. The stronger boundary is that no note reaches a model, tool argument or decision input. Even a note claiming that SUP-002 is the correct registered entity cannot clear `NAME_DISCREPANCY`; only the current supplier checks and officer process can resolve it. No memory operation grants approval, routes a requisition or contacts a supplier.

## 6. Retention, correction and deletion

| Store | Retention | What happens today |
|---|---|---|
| Supplier notes | Default 365 days from `recorded_on`; officer may choose 1–365 | `expires_on` is stored. Normal reads hide the record only when the evaluation date is **later than** expiry; it remains visible on the expiry date |
| Prior outcomes | 365 days from the review date | Same expiry filtering; no configurable shorter outcome retention in the current method |
| Checkpoints | Target: 30 days after `saved_at`, per [state model, section 7](state-model.md#7-retention) | **Not implemented.** No automatic expiry; `--fresh` discards one checkpoint, or files can be removed manually |
| Committed synthetic traces and fixtures | Retained as project assessment evidence | Not deleted by memory commands |

Expiry filtering does not remove bytes. `procurement-memory purge-expired` rewrites the active store without records whose expiry is earlier than the supplied date. There is no scheduled purge. Run housekeeping with the actual maintenance date; a historical review date is for reproducing relevance, not for deciding today's deletion. `list --include-expired` deliberately exposes expired records still in the file.

`procurement-memory forget <id>` removes all entries with that identifier from the active file. A correction uses officer deletion followed by a new, dated note because there is no edit operation. Rewrites use a temporary file and atomic rename; appends are plain JSONL writes. There is no locking for simultaneous writers.

Deletion from the active memory file does not erase copies already embedded in run traces, fixtures, committed evidence or external backups. Memory deletion also leaves the source draft and checkpoint intact. The prototype has no backup-erasure workflow or deletion audit log, so this note does not claim complete erasure. A team-approved evidence-retention policy is needed before using non-synthetic data.

## 7. Evidence that memory helps without deciding

The [working memory demonstration](working-memory.md#2-before-and-after-memory-improves-the-task) records the same 120-bag cement review with memory off and on. The additional context explains late deliveries, a supplier-name discrepancy and a blacklist history. The comparison still ranks QT-002 at UGX 4,479,600 and requires the quotation-count exception.

| Evidence or test | Property established |
|---|---|
| [Before](../../evidence/traces/memory/01-before-no-memory.json) / [after](../../evidence/traces/memory/02-after-with-memory.json); `test_every_decision_is_identical_with_and_without_memory` | Eligibility, comparison, draft content, tool statuses and stop behaviour remain identical apart from volatile record identifiers/timestamps |
| `test_memory_is_read_only_after_every_tool_call` | All three read-only tools finish before memory is read |
| `test_a_clearance_note_does_not_clear_the_discrepancy` | A note cannot change supplier eligibility |
| [Next review](../../evidence/traces/memory/05-next-week-remembers.json); `test_a_completed_run_is_remembered_for_next_week` | A newly completed draft creates an outcome that a later review can retrieve |
| `test_an_incomplete_run_writes_no_memory` | A hand-off does not masquerade as a completed outcome |
| `test_expired_records_are_hidden_and_purged`, `test_forget_deletes_one_record_and_only_the_officer_may` | Expiry visibility, physical purge and individual deletion behave as specified |
| `test_a_note_written_after_the_review_is_not_shown_for_it` | Future observations do not enter a historical workflow review |
| `test_a_note_edited_by_hand_into_an_assertion_is_withheld_on_display` | Prohibited assertions are screened again at display |
| [Failure](../../evidence/traces/memory/06-failure-suppliers-missing.json) / [recovery](../../evidence/traces/memory/07-recovery-resumes.json); checkpoint tests | Working state survives a data failure and the resumed run avoids repeating valid completed steps |

Tests are in [`tests/test_memory.py`](../../tests/test_memory.py) and [`tests/test_agent_checkpoint.py`](../../tests/test_agent_checkpoint.py). On 9 October 2026 the full local suite passed with **365 passed, 3 skipped**, including these checks. The benefit demonstrated is additional relevant context and reusable state, not measured improvements in officer decision accuracy or latency.

## 8. Known gaps and follow-up

- Enforce the intended role restriction on expiry purge and replace supplied CLI identities with authentication before supporting multiple users.
- Implement the state model's 30-day checkpoint cleanup. Resetting a completed checkpoint can allow a new draft, so cleanup must preserve an independent completed-review/idempotency record before expiring that protection.
- Add full record validation on load. The loader skips invalid JSON and unknown kinds, but accepts recognised-kind dictionaries without validating every field; malformed dates, absent expiry or changed outcome figures are not reliably rejected.
- Handle unreadable stores and invalid records consistently. Missing memory is harmless; permission errors, malformed dates or write errors can currently propagate. Do not claim all memory failures are non-blocking.
- Define deletion auditing and treatment of trace copies, then add locking or transactional storage if simultaneous writers are introduced. Content-derived IDs and atomic rename alone do not establish integrity or prevent concurrent lost updates.

## 9. Traceability

| Source | Design consequence |
|---|---|
| Charter section 7 | One use case: prior outcomes and supplier notes as advisory context |
| AI Boundary Matrix; Requirements 14.2 and 14.3 | No memory-driven approval, award or financial commitment; screen assertions and retain human gates |
| Requirements 7.5, 8.5 and 9.4; task contract gap 2 | Persist working state separately; reuse only current results |
| Requirement 13.1 | Link outcomes to a run and drafts; preserve synthetic execution evidence |
| Week 6 brief | State what is stored, why, access, retention and deletion; demonstrate the advisory boundary |

Implementation references: [`memory/store.py`](../../src/procurement_agent/memory/store.py), [`memory/cli.py`](../../src/procurement_agent/memory/cli.py), [`agent/workflow.py`](../../src/procurement_agent/agent/workflow.py) and [`agent/checkpoint.py`](../../src/procurement_agent/agent/checkpoint.py).
