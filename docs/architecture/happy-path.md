# The happy path, step by step

One review that goes all the way through to a requisition. Every figure below
comes from the recorded run in
[`evidence/traces/agent/02-completed-draft.json`](../../evidence/traces/agent/02-completed-draft.json)
and the Gate 2 stop in
[`05-recovery-rerun.json`](../../evidence/traces/agent/05-recovery-rerun.json).

```mermaid
sequenceDiagram
    autonumber
    actor Officer as Procurement officer
    participant Loop as Agent loop
    participant Door as Dispatcher
    participant Data as Governed data

    Officer->>Loop: start a review: AH-CM-001, 2026-09-25
    Note over Loop: A manager is refused here, before any read.<br/>An earlier checkpoint for this review resumes.

    Loop->>Door: check_reorder_need
    Note over Door: On every single call: who is asking,<br/>is this tool allowed at this step,<br/>are the input and output the right shape
    Door->>Data: read inventory
    Data-->>Door: rows, checksum verified
    Door-->>Loop: ok. 150 on hand, reorder point 150,<br/>target 270, so order 120

    Loop->>Door: check_supplier_eligibility
    Door->>Data: read suppliers and held quotations
    Door-->>Loop: ok. 1 eligible, 3 excluded:<br/>one blacklisted, two name discrepancies

    Loop->>Door: compare_quotations
    Door->>Data: read quotations, inventory, suppliers
    Door-->>Loop: ok. QT-002, Bugolobi Hardware Supplies,<br/>landed UGX 4,479,600. 1 of 3 required by POL-001-C02

    Loop-->>Officer: stops: awaiting_human.<br/>Gate 2, the comparison is on the table
    Note over Officer,Loop: Nothing has been written. The run is checkpointed and exits.
    Officer->>Loop: confirms the comparison, runs again
    Loop-->>Officer: stops: awaiting_human.<br/>a requisition is ready to compile
    Officer->>Loop: confirms the draft, runs again

    Loop->>Door: create_requisition_draft
    Note over Door: The only write in the catalogue, and it is<br/>refused without the officer's confirmation
    Door->>Data: append the requisition
    Door-->>Loop: ok. REQ-2026-001, status DRAFT
    Loop-->>Officer: stops: completed
    Note over Officer: routed_to, approved_by and decision are null.<br/>Approval happens outside this release.
```

## What the diagram is saying

**Four tool calls, and that is the whole happy path.** The cap is eight
iterations and 120 seconds, so there is room for a re-check without the loop
running away. Nothing in the sequence calls a model: the arithmetic, the
eligibility rules and the ranking are ordinary Python, so the same inputs give
the same answer every time.

**Everything goes through the dispatcher.** There is no second route to a tool.
It checks the caller's role, whether the tool is on the allow-list for the
current step, and the shape of the input and the output, then appends the
result envelope to the trace. A call that fails any of those checks comes back
as a named status rather than an exception.

**The two stops are real stops, not prompts.** The loop ends with
`awaiting_human`, writes a checkpoint and exits. The officer confirms and runs
it again, and the resumed run picks up at the draft step instead of repeating
the three reads. If a data file has changed in between, its checksum no longer
matches the source register and the steps that read it are re-run.

**It can only ever write a DRAFT.** `create_requisition_draft` leaves
`routed_to`, `approved_by` and `decision` null, and the output schema types all
three as `null`, so no tool can set them even in principle. A finished
requisition is handed over by hand.

See also: [system context](context-diagram.md),
[bounded agent](agent-architecture.md),
[tool catalogue](tool-catalogue.md),
[state model](state-model.md).
