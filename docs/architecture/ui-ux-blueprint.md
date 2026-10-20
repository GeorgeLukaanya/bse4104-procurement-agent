# UI/UX Blueprint: the procurement assistant

| Field | Value |
|---|---|
| Status | Draft for team review. Nothing here is built in code yet. |
| Inspected at | `7802f56` on `main` |
| Owner | Sekyeza Elroy Nunda |
| Prototype | [SME Procurement Agent UI](https://www.figma.com/design/FO3o2dUg2QfOS1o6DkOVI5) (Figma). Start on the Cover page. |
| Purpose | Agree what the officer sees, and how the system talks to her, before any frontend code is written. |

## 1. Who this is for

Agnes Nakato buys for a hardware store in Nakawa. She runs ten to fifteen reorder
decisions a week, she is comfortable with a spreadsheet, and she is not a technical
specialist. The charter says so, and the interface has to take it seriously.

She should never need to know what a tool call is, what a stop reason is, or that there
is a contract file bounding the loop. She needs to know what is low, what it costs, and
what she is being asked to decide. Everything else is plumbing, and plumbing goes in the
wall.

Kenneth Ssali approves the spending. He sees one thing: a requisition, how its price was
reached, and two buttons.

## 2. What the codebase actually gives a UI

Five facts, established by reading the agent loop, the tool envelopes, the schemas and
the Week 8 limitations. Each one changed the design.

**There is no frontend, no HTTP API and no streaming.** No TypeScript, no `package.json`,
no FastAPI or Flask, no SSE or WebSocket code. Every entry point is a Python CLI:
`procurement_agent.agent.cli` for the loop, `procurement_agent.cli` for extraction,
`procurement_agent.rag.cli` for policy retrieval. A transport layer has to be built first.
That is section 8.

**The loop calls no model.** `planner.py` is deterministic, recorded as KL-04 in
[known-limitations.md](known-limitations.md), and a whole run finishes in milliseconds.
So the interface shows no thinking animation and no streamed reasoning, because there is
no thinking to show. It also never says the assistant judged anything: the ranking is
arithmetic, and the copy says so in those words.

**The slow work is outside the loop.** Extraction and policy retrieval are the only paths
that call Gemini, and they carry a 30 second deadline in `client.py`. KL-01 records a
clean quotation that timed out at 29.95 s. Progress and retry belong on those two screens
and nowhere else.

**A run cannot be paused.** `run_workflow()` runs to a stop reason and returns. There is
no interrupt hook. A gate is a stop followed by a new invocation against the saved
checkpoint, which is why the interface has no pause button and never implies one.

**One invocation handles one flagged item** (KL-05). `AgentState.flagged_item()` takes the
first unless a SKU was named. The week list says so plainly rather than implying a batch.

One more, and it is why this work exists. KL-02 records that `--role`, `--officer`,
`--confirm-comparison` and `--confirm-draft` are trusted command-line inputs with no login
behind them, and names the follow-up: "authenticated sessions, identity-bound
confirmations and server-side authorization". The confirmation moments in this design are
the security boundary, not decoration.

## 3. Scope against the charter

In scope, quoted: "a dedicated review screen in the system" for the Procurement Manager,
"two seeded user roles with simple authentication", "all notification is in-application".

Out of scope, quoted: "mobile applications", "multi-tenant support, self-service user
management, role administration and production deployment beyond a reproducible tagged
release".

So: desktop-first, 1440 wide, two roles, no admin screens, no phone layout.

## 4. The design

A sidebar, one content column, and a decision band that appears only when the system needs
an answer. No three-pane cockpit, no dashboard of tiles, no cards inside cards.

The sidebar is the only tinted region, which is what makes the rest of the screen read as
paper. It carries the week's work at the top and the records underneath, so the product is
visibly more than one workflow: Suppliers, Quotations, Policies and Activity are all
first-class places, even though only Activity is drawn.

The content column is 880 wide against a 1440 frame. That asymmetry is deliberate: a
measure you can actually read beats filling the glass.

### 4.1 How it speaks

This is the part that is easy to get wrong from inside a codebase, so it is written down
as a rule set on the Foundations page.

| Rule | We say | Not |
|---|---|---|
| Say what it means for them, not what the system did | Three items are low enough to order this week. | `check_reorder_need` returned 3 flagged items |
| Name what is in the way, and who can clear it | Ask whoever looks after the system to check the quotations file. | `DATA_INTEGRITY_ERROR` in `knowledge/data/quotations.json` |
| Ask, do not announce | Shall I prepare the requisition for Kampala Cement Depot? | Confirm the landed-cost comparison (gate 2) |
| Never claim a judgement the system did not make | They came out cheapest once delivery and VAT were counted. | I think this is the best supplier for you |
| Say what was not done | Nothing was saved and nothing was ordered. | Operation failed. |

### 4.2 Hidden, not removed

Every screen keeps a quiet line, "What I checked", that opens the real trail: the step it
stopped at, the file it read, the clause that applied, what was written and what was not.
Agnes never has to open it. Ssali can. An auditor can. Screen 7 shows it open, and it is
the only place in the interface where a file path appears.

This is the compromise that lets the interface be calm without being dishonest. The
technical trail is one click away, not deleted.

### 4.3 The decision moments

There are exactly three, and all three are places the loop already stops with
`awaiting_human`.

| The system stops | The screen asks | Backs |
|---|---|---|
| Comparison ready | Shall I prepare the requisition for Kampala Cement Depot? | `confirm_comparison` |
| Draft ready | Send this to Ssali for approval? | `confirm_draft` |
| A quotation is in USD | What rate are you using? | `exchange_rate_ugx_per_usd` |

Three rules hold for all of them. The officer never edits a figure on the way through: the
exchange rate is the only number she supplies, because the tool refuses to pick one. A
confirmation is an identity, not a checkbox, so the screen records who and when. And
changing a rate invalidates the comparison, because
`_drop_comparison_if_rate_changed()` drops the saved comparison, the draft and both
confirmations; screen 3 warns before she submits, in those words.

## 5. The screens

**Workspace**, seven frames for the officer:

1. **This week.** What the assistant found, the three items that need ordering, and what
   already happened today.
2. **Comparing an item.** The offers, the recommendation carrying the weight, the one set
   aside and why.
3. **A rate is needed.** The dollar quotation, the rate form, and the warning about what
   resubmitting costs.
4. **Ready to send.** The requisition in plain language: what, from whom, how much, why,
   and what is worth knowing.
5. **Sent for approval.** Confirmation, and the record of what happened.
6. **Activity.** Every decision kept, who made it, when. This is the database screen.
7. **Something went wrong.** A failure written for a person, with the technical trail open
   underneath for whoever fixes it.

**Manager**, two frames: what is waiting for Ssali, and one requisition with Approve or
Send back. Both carry a note on the canvas saying they are not wired, because no tool
writes a status past DRAFT.

The v1 pages are kept in the file, prefixed `v1 ·`, for comparison. They can be deleted
once the team has decided.

## 6. Components

Eight sets. Each one reads a real field.

| Component | Variants | Reads |
|---|---|---|
| `NavItem` | default, active, muted | Sidebar. The active row is a 2px rule and a tint, not a filled block. |
| `AssistantNote` | neutral, attention, problem, done | How the system speaks. One short paragraph, a small square mark, never an avatar. |
| `ItemRow` | needs review, in progress, waiting on you, ready, sent, issue | A flagged SKU, with the stock position written the way a person would say it. |
| `OfferRow` | recommended, alternative, alternative two, set aside | One row of `compare_quotations.data.ranked`, or an excluded quotation and its reason. |
| `DecisionBar` | waiting, done | The three decision moments. The only filled button in the interface. |
| `ActivityRow` | you, assistant, manager | One row of the decisions table. |
| `StatusPill` | draft, with the manager, approved, returned | Reserved for the requisition's own status and used nowhere else. |
| `MetaLine` | default, technical | Inside the "What I checked" disclosure. Where tool names and file paths live. |

Colour: a pale blue canvas, a tinted sidebar, white surfaces, blue-tinted neutrals so
nothing reads as flat grey, and one deep blue reserved for the active row, the
recommendation and the committing button. Four meaning colours, always with words beside
them, because a dot nobody can read is not an explanation.

Type: IBM Plex Sans for anything a person reads, IBM Plex Mono for money, dates,
identifiers and anything copied verbatim out of the system.

## 7. What to ask the team

1. Does the assistant sound like someone you would trust? The wording is the design here.
2. Is one accent colour and a pale blue canvas enough, or does the team want branding?
3. The sidebar lists Suppliers, Quotations and Policies, and none are drawn. Are they in
   scope, or is the weekly review the whole product?
4. The decisions table is a backend change nobody owns. Who takes it, and does it replace
   the checkpoint files or sit beside them?
5. The manager screens have nothing behind them. Do we build the tool, or demo the officer
   side only?
6. Does anything here contradict `agent-architecture.md`, `state-model.md`, the tool
   catalogue or the task contract? Those four win over this document.

## 8. Transport layer

The loop finishes in milliseconds, so the loop endpoints can be plain request and
response. Only extraction and policy retrieval need progress reporting, and a 30 second
request with a spinner is adequate before anyone reaches for SSE.

```
POST /session                 seeded role login, returns identity and role
POST /runs                    { review_date, sku? }            -> RunResult
POST /runs/{run_id}/confirm   { gate: "comparison" | "draft" } -> RunResult
POST /runs/{run_id}/rate      { ugx_per_usd, effective_date }  -> RunResult
GET  /runs/{run_id}                                            -> RunResult
GET  /decisions?since=...                                      -> Decision[]
```

`RunResult` is `AgentResult.to_dict()` unchanged. Server side each call is
`run_workflow()` with a `checkpoint_dir`, which is why confirming a gate is a new
invocation rather than a message to a waiting process. The frontend translates
`stop_reason` into the sentence the officer reads; the raw value stays in the payload for
the disclosure.

```ts
type StopReason = 'completed' | 'no_reorder_required' | 'awaiting_human'
                | 'max_iterations' | 'timeout' | 'unauthorized'
                | 'failed' | 'refused' | 'no_progress';

interface Decision {
  id: string; run_id: string;
  actor: string; role: 'PROCUREMENT_OFFICER' | 'PROCUREMENT_MANAGER' | 'AGENT';
  kind: 'rate_given' | 'comparison_approved' | 'requisition_sent'
      | 'approved' | 'sent_back';
  subject: string; detail: Record<string, unknown>;
  decided_at: string; supersedes: string | null;
}
```

## 9. The decisions table

Today a decision lives in a checkpoint file under `var/agent-state/` and a line in a JSONL
trace. That is why KL-03 records that local writes are not a transaction and have no
shared-writer lock, and why KL-10 records that memory, caches, requisitions and traces are
plain local files with no access control. The Activity screen is the argument for a real
table, and it is small.

```sql
CREATE TABLE decisions (
  id          TEXT PRIMARY KEY,
  run_id      TEXT NOT NULL,
  actor       TEXT NOT NULL,              -- a.nakato, k.ssali, AGENT
  role        TEXT NOT NULL,              -- PROCUREMENT_OFFICER | PROCUREMENT_MANAGER | AGENT
  kind        TEXT NOT NULL,              -- rate_given | comparison_approved | requisition_sent
                                          -- | approved | sent_back
  subject     TEXT NOT NULL,              -- REQ-2026-0043, or AH-CM-001
  detail      TEXT NOT NULL,              -- JSON: the figures as they stood at the time
  decided_at  TEXT NOT NULL,              -- ISO 8601, UTC, written once
  supersedes  TEXT REFERENCES decisions(id)
);
CREATE INDEX decisions_run ON decisions (run_id, decided_at);
CREATE INDEX decisions_subject ON decisions (subject, decided_at);
```

Three properties matter more than the columns.

**Append only.** A decision is never updated in place. When a rate changes and the
comparison is recomputed, the old approval is superseded by a new row rather than edited,
and `supersedes` says which. That is what makes the Activity screen worth trusting, and it
is the same discipline the requisition status model already has.

**`detail` holds the figures as they stood.** An approval that says only "approved" is
useless six weeks later when the quotation has expired and the prices have moved. The row
carries the landed cost, the supplier and the clause that applied at the moment of the
decision.

**SQLite, in the standard library.** `pyproject.toml` has zero runtime dependencies and
that is worth keeping. `sqlite3` ships with Python, gives us a real transaction around the
write that KL-03 says we do not have, and needs no service to run in a demo. Postgres is a
later problem, and the schema above moves across unchanged.

What it does not fix: KL-03 also covers the requisition store and the trace files, and
moving decisions alone does not make the whole write path transactional. It makes the one
record we show people trustworthy, which is the right first step.

## 10. Still open

**The manager's decision has no write path.** The charter requires an immutable record of
an approval or rejection, the status model stops at DRAFT and no tool writes beyond it. The
manager screens can be prototyped but not wired without a new tool, a contract entry and an
authorization test.

**Session authentication does not exist.** The charter asks for "simple authentication,
sufficient to attribute audit entries to an identity". A low bar, still a backend task
nobody owns, and the thing KL-02 names.

**In-application notification has no mechanism.** The week list covers the officer.
Telling Ssali that a requisition is waiting has nowhere to come from.

**Suppliers, Quotations and Policies are in the sidebar and not drawn.** Either they are
scope, or the sidebar is promising something we will not build. That is question 3.
