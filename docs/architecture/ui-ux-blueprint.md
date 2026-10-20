# UI/UX Blueprint and Figma Prototype Plan

| Field | Value |
|---|---|
| Status | Draft for team review. Nothing here is built yet. |
| Inspected at | `7802f56` on `main` |
| Owner | Sekyeza Elroy Nunda |
| Purpose | Agree the screens and the interaction rules in Figma before any frontend code is written. |

## 1. What the codebase actually gives a UI

I read the agent loop, the tool envelopes, the schemas and the Week 8 limitations before
drawing anything. Five things are worth stating plainly, because a UI drawn without them
would show a system we do not have.

**There is no frontend, no HTTP API and no streaming.** The repository has no
TypeScript, no `package.json`, no FastAPI or Flask, and no SSE or WebSocket code. Every
entry point is a Python CLI: `procurement_agent.agent.cli` for the loop,
`procurement_agent.cli` for extraction, `procurement_agent.rag.cli` for policy
retrieval. A UI needs a transport layer built first. That is section 8.

**The loop calls no model, so there are no "thoughts" to stream.** `planner.py` is
deterministic and this is a recorded limitation, KL-04 in
[known-limitations.md](known-limitations.md). It proposes catalogue tools in charter
order and `dispatch.py` executes them. A whole run finishes in milliseconds. So the
familiar agent-UI pattern of a token-by-token reasoning stream has nothing to render
here. What we do have is better for an audit: a list of tool envelopes, each with a
status, errors, a latency and a data fingerprint. The trace panel shows calls, not
thinking.

**The slow, interesting work sits outside the loop.** Extraction and policy retrieval
are the parts that call Gemini, and they have their own commands and their own 30-second
deadline in `client.py`. KL-01 records a clean quotation that timed out at 29.95 s. Any
progress indicator or retry affordance belongs on those two screens, not on the loop.

**A run cannot be paused mid-flight.** `run_workflow()` runs to a stop reason and
returns. There is no interrupt hook. What exists instead is a checkpoint: the run saves
after each tool step under `var/agent-state/` and a later invocation resumes from it. So
human-in-the-loop here is "the run stops, the officer acts, the officer re-runs", not
"pause and inject". The UI must be honest about that, because a pause button that
secretly waits for the next invocation would be a lie about the state model.

**One invocation handles one flagged item.** KL-05. The scan can flag several SKUs, but
`AgentState.flagged_item()` takes the first unless a SKU was named. The queue screen has
to make that explicit rather than implying a batch run.

One more thing the UI is the named fix for. KL-02 says `--role`, `--officer`,
`--confirm-comparison` and `--confirm-draft` are trusted command-line inputs with no
login behind them, and its follow-up is "authenticated sessions, identity-bound
confirmations and server-side authorization". That is this work. The confirmation gates
are the security boundary, not decoration.

## 2. Scope check against the charter

The charter already assumes an application interface, so this is not new scope.

In scope and quoted: "a dedicated review screen in the system" for the Procurement
Manager, "two seeded user roles with simple authentication", and "all notification is
in-application".

Out of scope and quoted: "mobile applications", "multi-tenant support, self-service user
management, role administration and production deployment beyond a reproducible tagged
release".

So: a desktop-first web interface, two seeded roles, no admin screens, no mobile layout.
Figma frames are drawn at 1440 wide. We check it does not break at 1024, and we do not
design a phone.

## 3. Layout model

**Recommended: split workspace. A left rail for the review queue, a wide centre for the
step's own content, a right inspector for the run record.**

The reason is the shape of the task, not fashion. This workflow has four fixed steps in a
fixed order, scan then eligibility then compare then draft, and the officer's real job is
reading one wide table of landed costs and deciding whether to confirm it. A conversation
stream would make that table a scrollback entry that moves away from the officer while
they are comparing figures. A dashboard of tiles would bury it. The centre column holds
the current step at full width, the right inspector holds the trace, the citations and the
advisory memory, and the officer can collapse the inspector when they just want the table.

Two alternatives we should look at in Figma before settling, one frame each:

*Conversational stream with a side inspector.* Reads naturally and suits the eventual
model-written justification. Loses the wide table and makes a four-step state machine look
open-ended, which invites the officer to type instructions the system cannot accept.

*Step wizard.* Honest about the fixed order and the gates, and the simplest to build.
Feels heavy for an officer running fifteen of these a week, and makes going back to look
at the eligibility result awkward.

Regions in the recommended model:

| Region | Holds | Comes from |
|---|---|---|
| Left rail, 280 | Review date picker, flagged SKU queue, per-SKU run status | `check_reorder_need` data, one checkpoint per SKU |
| Centre, fluid | The active step: reorder list, eligibility result, landed-cost table, draft preview | the step's tool `data` |
| Right inspector, 360 | Run record, tool calls, policy citations, advisory memory | `AgentResult.to_dict()`, RAG citations, `advisory_block()` |
| Top bar | Signed-in identity and role, review date, stop state | session, `caller_role`, `stop_reason` |
| Bottom action bar | The one confirmation this step needs, and nothing else | the gate the loop is waiting on |

## 4. Agentic interaction design

### 4.1 Execution visibility

The right inspector lists one tile per tool call, in order, from `result.calls`. Each tile
carries the tool name, the status from the envelope, the latency in ms, and the data
fingerprint. Collapsed by default, expandable to the full request payload and response
`data`.

Statuses are already an enumeration in `tools/contract.py` and the UI must use those six
names rather than inventing its own: `ok`, `no_result`, `invalid_input`, `unauthorized`,
`unavailable`, `failed`. `no_result` is not a failure and must not be red. It means the
call was valid and nothing matched, which is an answer.

Above the tiles, a single run header: `stop_reason`, iterations used against the cap, the
contract path and version, and the contract's own name for how the run ended. All four are
already in `AgentResult.to_dict()` under `contract`. Showing the contract version is the
cheapest way to make a screenshot auditable.

The fingerprint deserves its own small treatment. When a resume reuses a saved step, the
response carries `resumed` with `kept_steps` and `recomputed_from`. The inspector marks
reused steps "restored from checkpoint" so the officer is never looking at a cached
eligibility result while believing it was just computed.

### 4.2 Human-in-the-loop gates

There are exactly two confirmations, plus one disclosure, and all three already exist in
the loop as reasons it stops with `awaiting_human`.

| Gate | The loop stops with | The screen asks for | Backs which flag |
|---|---|---|---|
| Comparison | "Landed-cost comparison is on the table..." | Confirm the landed-cost table | `confirm_comparison` |
| Draft | "A requisition draft is ready to compile..." | Confirm compilation of a DRAFT requisition | `confirm_draft` |
| Exchange rate | `EXCHANGE_RATE_REQUIRED` | The UGX per USD rate and its effective date | `exchange_rate_ugx_per_usd` |

Three rules for these, each one traceable to something the code enforces:

The officer cannot edit a number on the way through. The agent proposes and the officer
confirms or rejects, and the only figure the officer supplies is the exchange rate, because
the tool refuses to pick one. So the gate is a confirm or reject with a reason, never an
editable table.

A confirmation is an identity, not a checkbox. The POST that confirms carries the session,
and the server writes `confirmations[gate] = {by, at}`, which the loop already records.
The screen shows who confirmed and when, for both gates.

Changing the exchange rate invalidates the comparison. `_drop_comparison_if_rate_changed()`
drops the saved comparison, the draft and both confirmations, and sets the step back to
compare. The UI must warn before the officer submits a new rate, and must then visibly
clear the confirmed state, because silently keeping a tick next to a recomputed table would
be the worst bug we could ship here.

The manager never sees the loop. A manager role is refused by the loop before a checkpoint
is read or written, with "PROCUREMENT_MANAGER does not operate the agent loop. Approval is
a screen action, not a tool (POL-004-C03)." The manager's entire interface is the review
screen, and the status it writes is outside the agent's reach.

### 4.3 Error and edge states

Every one of these is a real stop reason or error code. The UI copy should quote the
`stop_detail` the loop produced rather than paraphrase it.

| State | Signal | What the screen does |
|---|---|---|
| Nothing to do | `no_reorder_required` | A plain, positive empty state. Not an error. |
| Waiting on the officer | `awaiting_human` | Show the gate card. Exit code 1 is this case. |
| Loop detected | `no_progress` | Explain the repeat was blocked and nothing further was called. Offer a fresh run. |
| Iteration cap | `max_iterations` | Show iterations against the cap and the contract version. |
| Time budget | `timeout` | Show seconds spent against the budget. |
| Refused | `refused`, with a code | Show the code and detail. `INSUFFICIENT_QUOTATIONS` and `INCOMPARABLE_QUOTATION` are the common ones. |
| Blocked by role or allow-list | `unauthorized`, `UNAUTHORIZED_ROLE` or `TOOL_NOT_ALLOWED` | State the rule that refused it. This is correct behaviour, so it reads as a boundary, not a crash. |
| Data tampered or missing | `failed`, `DATA_INTEGRITY_ERROR` or `DATA_SOURCE_UNAVAILABLE` | Hard stop. Name the file. No partial result shown. |
| Compilation halted | `MISSING_COMPONENT` | Say plainly that nothing was written. |
| Extraction timed out | the extraction command's 30 s deadline | Offer an explicit retry. Never show a partial record. KL-01. |

Two display rules carried over from the backend. Advisory memory is shown beside the
result with its own statement that it changed nothing, and that statement must stay on
screen next to the records, not in a tooltip. And supplier notes are untrusted text that
`guards.scan` screens again at display time, so the memory panel renders text only, never
anything that could read as an instruction or an approval.

## 5. Figma frames to build

Eleven frames. Each one is a state the backend can actually produce, so each is testable
against a real run.

1. **Sign in.** Two seeded roles. No registration, no password reset, no role picker.
2. **Officer idle.** Review date chosen, scan not yet run. Empty queue, one primary action.
3. **No reorder required.** The `no_reorder_required` empty state.
4. **Queue populated.** Flagged SKUs in the rail, with the one-item-per-run rule visible.
5. **Eligibility result.** Per-supplier pass and fail with the clause that excluded each.
6. **Landed-cost comparison.** The main frame. Ranked table, excluded table, the
   `quotation_requirement` banner, the exchange-rate disclosure.
7. **Gate: confirm comparison.** Frame 6 with the action bar active.
8. **Gate: exchange rate required.** The disclosure form and the invalidation warning.
9. **Draft preview and gate: confirm compilation.** Items, policy clauses, justification,
   unresolved issues.
10. **Requisition compiled.** `REQ-...` in DRAFT, routed to the manager, read-only.
11. **Stopped.** One frame with variants for `no_progress`, `max_iterations`, `timeout`,
    `unauthorized` and `failed`.

Plus two for the manager: **review screen** and **decision recorded**.

Two frames to draw as comparison only, not to build: the conversational-stream variant and
the step-wizard variant from section 3.

## 6. Figma components and variants

| Component | Variants | Notes |
|---|---|---|
| `ToolCallTile` | ok, no_result, invalid_input, unauthorized, unavailable, failed; collapsed and expanded | Exactly the six envelope statuses. `no_result` is neutral, not red. |
| `StopBanner` | the nine stop reasons in `steps.py` | Each carries the detail string verbatim. |
| `GateCard` | comparison, draft, exchange-rate; pending, confirmed, rejected | Confirmed shows who and when. |
| `RankedRow` | rank 1, ranked, tie-broken | Columns are the real schema fields, landed cost is the emphasised one. |
| `ExcludedRow` | one reason, several reasons, missing fields | Reasons are clause-referenced strings from the tool. |
| `RequirementBanner` | satisfied, exception required, sole eligible option | Drives whether frame 9 shows the exception line. |
| `CitationChip` | clause, document, absence note | Clause IDs look like `POL-001-C02`. |
| `MemoryCard` | prior outcome, supplier note, empty | Always paired with the advisory statement. |
| `ResumeNotice` | restored, recomputed, fresh | Names the kept steps. |
| `QueueItem` | flagged, in progress, awaiting confirmation, drafted, stopped | One per SKU. |
| `IdentityChip` | officer, manager | Role is visible on every screen because it changes what is allowed. |
| `RunHeader` | running, stopped | Iterations against cap, contract path and version. |

No colour palette, type scale or component library exists in the repo, so the Figma file
starts the design system rather than inheriting one. Keep it small: one typeface, a four
step type scale, a neutral ramp, and semantic colours that map one-to-one onto the six
envelope statuses so a screenshot and a trace can be read side by side.

## 7. What to ask the team when the Figma link goes out

Ordered by how much a wrong answer would cost us.

1. The loop has no model in it (KL-04). Should the prototype draw the system we have, or
   the system the charter designs? I have drawn what we have.
2. Is "the run stops and the officer re-runs" acceptable as the HITL model, or do we want a
   server that holds the run open across a gate? That choice changes the transport layer,
   not the pixels.
3. One flagged item per invocation (KL-05). Do we show the queue honestly as one-at-a-time,
   or is per-item iteration coming in a later week?
4. Does the manager review screen belong in this prototype, given the charter names it but
   no code writes a status beyond DRAFT?
5. Split workspace, conversational stream or wizard. Vote on the three frames in section 3.
6. Are we confident every stop reason in section 4.3 has readable officer-facing copy? That
   copy is a deliverable, not a detail.
7. Does anything here contradict `agent-architecture.md`, `state-model.md`, the tool
   catalogue or the contract? Those four documents win over this one.

Review criteria to state in the Figma post: every frame maps to a stop reason or tool
status the backend can produce, no frame invites input the tools would refuse, no number on
screen is editable unless a tool asks for it, and role is visible wherever it changes what
is permitted.

## 8. Technical prerequisites

The prototype is drawable now. Building it needs a transport layer first, and that is a
separate decision for the team, not something to slip into a frontend branch.

The smallest honest version: a thin HTTP layer that wraps the existing commands and returns
`AgentResult.to_dict()` as it already stands, plus a session that carries the identity the
confirmations are bound to. The loop finishes in milliseconds, so the loop endpoints can be
plain request and response. Only extraction and policy retrieval need progress reporting,
and a 30-second request with a spinner is adequate before we reach for SSE.

Four endpoints and one session, in the shape the code already has:

```
POST /session                 seeded role login, returns identity and role
POST /runs                    { review_date, sku? }            -> RunResult
POST /runs/{run_id}/confirm   { gate: "comparison" | "draft" } -> RunResult
POST /runs/{run_id}/rate      { ugx_per_usd, effective_date }  -> RunResult
GET  /runs/{run_id}                                            -> RunResult
```

`RunResult` is `AgentResult.to_dict()`, unchanged. Server side, each of those calls is
`run_workflow()` with a `checkpoint_dir`, which is why confirming a gate is a new
invocation rather than a message to a waiting process.

The component interfaces that follow from the real schemas:

```ts
type ToolStatus = 'ok' | 'no_result' | 'invalid_input'
               | 'unauthorized' | 'unavailable' | 'failed';

type StopReason = 'completed' | 'no_reorder_required' | 'awaiting_human'
                | 'max_iterations' | 'timeout' | 'unauthorized'
                | 'failed' | 'refused' | 'no_progress';

type Role = 'PROCUREMENT_OFFICER' | 'PROCUREMENT_MANAGER' | 'AGENT';

interface ToolCall { tool: string; status: ToolStatus; errors: ToolError[]; }
interface ToolError { code: string; detail: string; field?: string; }

interface RankedQuotation {
  rank: number; quotation_id: string; supplier_id: string; supplier_name: string;
  original_currency: string; original_unit_price: number;
  normalised_unit_cost_ugx: number; extended_cost_ugx: number;
  vat_amount_ugx: number; delivery_cost_ugx: number; landed_cost_ugx: number;
  lead_time_days: number; validity_date: string;
  tie_broken_on_supplier_name: boolean;
}

interface RunResult {
  stop_reason: StopReason; stop_detail: string;
  iterations: number; step: string; run_id: string | null;
  caller_role: Role; review_date: string; sku: string | null;
  contract: { path: string; version: string; iterations_per_item: number;
              wall_clock_seconds: number; stop_reason: string | null } | null;
  resumed: { restored: boolean; kept_steps: string[];
             recomputed_from?: string; changed_sources?: string[] } | null;
  confirmations: Record<string, { by: string; at: string }>;
  reorder: ReorderResult | null;
  eligibility: EligibilityResult | null;
  comparison: ComparisonResult | null;
  draft: RequisitionDraft | null;
  calls: ToolCall[];
  memory: AdvisoryBlock | null;
}
```

Every field above is a field the backend already returns. Nothing in this blueprint needs
a change to the agent, the tools or the contract.

## 9. Open questions I could not settle from the code

The manager's decision has no write path. The charter requires an immutable audit record of
an approval or rejection, the status model stops at DRAFT, and no tool writes beyond it. So
the manager review screen can be prototyped but cannot be wired without a new tool, which
would need its own contract entry and its own authorization test.

Session authentication does not exist in any form. The charter says "simple authentication,
sufficient to attribute audit entries to an identity", which is a low bar, but it is still
a backend task nobody owns yet.

Notifications are specified as in-application and there is no notification store. The queue
screen covers the officer's case. The manager being told a requisition is waiting does not
have a mechanism.
