# Group Y Progress Report: Week 4

**Course:** BSE4104 Emerging Trends in Software Engineering
**Group:** Y
**Week ending:** 25th September 2026
**Version:** 1.1
**Repository:** [https://github.com/GeorgeLukaanya/bse4104-procurement-agent](https://github.com/GeorgeLukaanya/bse4104-procurement-agent)

## Introduction

This report summarises Week 4 progress on the SME Procurement-Preparation Agent. The weekly focus was tools and function calling: giving the application a small set of deterministic functions it can call through a controlled orchestration layer, with explicit schemas, authorization rules and failure behaviour.

The week delivered four working tools behind a single dispatch entry point. Three read current application data (inventory, supplier register and quotations) and one performs the low-risk simulated side effect the brief asks for, writing a requisition in DRAFT to a local store. None of the tools calls the model and the model cannot call a tool directly. The caller's role is injected from the session, the only write sits behind an officer confirmation gate, and no tool exists that can approve, order, pay or contact a supplier.

## Tasks

| Task | Description | Status | Assignee |
| :---- | :---- | :---- | :---- |
| Tool catalogue and schemas | Specified four tools drawn from the list already named in Charter section 1: check\_reorder\_need, check\_supplier\_eligibility, compare\_quotations and create\_requisition\_draft. Defined a common response envelope, a shared error-code vocabulary, a role-by-tool authorization matrix, input and output JSON Schemas, and failure behaviour for every tool. Recorded the tools that must never exist and the CI rule enforcing that. Created the three operational datasets the tools read (48 SKUs, 8 suppliers, 36 quotations) and registered them with checksums. | Done | Lukaanya George |
| Working demonstration of tools | Implemented all four tools and the dispatch.invoke orchestration entry point, which rejects unknown roles, enforces the step allow-list and confirmation gate, validates the request whole, runs the function, scans the result with guards.scan and appends a trace. Added a command-line interface and recorded a four-call run on 24 September with data fingerprints matching the source register. | Done | Nannyombi Shakiran |
| Failure and authorization test evidence | Ran the existing tool and authorization tests and the full regression suite, then ten focused scenarios covering missing parameters, unavailable data, role restrictions, the allow-list, the confirmation gate, forbidden transitions, role spoofing and a malformed tool response. Recorded expected against actual behaviour and one root-caused failure. | Done | Beingana Jim Junior |
| Updated architecture diagram | Extended the architecture to show the bounded orchestrator, tool allow-list, role check, schema checks and output guards, the four deterministic tools, the project data stores and the five human-approval gates. Stated explicitly that the diagram is the approved target, not a claim that every connection is implemented. | Done | Ainamani Jim Isaac |
| Week 4 progress report | Compiled this report. | Done | Sekyeza Elroy Nunda |

## Key Design Decisions

Four decisions shape how the tool layer behaves and are recorded because later weeks depend on them.

**The role is injected, never supplied.** caller\_role appears in no input schema. The orchestration layer takes it from the authenticated session and it surfaces only in the output trace. Quotations and policy documents are untrusted content and a role that was a model-facing parameter could be requested by text inside one of them. FA-09 confirms that a payload attempting to supply a different role is rejected and the injected role stands.

**The agent proposes; the officer creates.** create\_requisition\_draft is the only tool with a side effect, and it is where the human gate sits. The agent may assemble the call, but it executes only after the Procurement Officer confirms it, and then under the officer's identity. The Procurement Manager is refused outright, because POL-004-C03 separates preparing a requisition from approving it. Even a confirmed call can only produce a DRAFT; any other requested status is refused as FORBIDDEN\_TRANSITION rather than silently ignored.

**Fail closed and fail whole.** A non-conforming request is refused entirely, with every applicable error listed and no value coerced or repaired. An unreadable supplier register reports nobody eligible rather than everybody. An empty reorder list returns no\_result, not an error, because a week in which nothing is low is a normal week. An insufficient quotation count is reported with exception\_required: true rather than blocking the workflow, so the POL-001-C04 exception path stays reachable.

**The tools rank; they do not recommend.** compare\_quotations returns the full landed-cost derivation for every ranked offer, and every excluded offer with its reasons, but emits no recommended quotation. Ranking is not awarding (POL-004-C04), and the model's role is limited to explaining trade-offs in prose. The prohibited capabilities (purchase orders, supplier contact, financial commitment) are absent by design and enforced in CI by .semgrep/agent-safety.yml, so adding one would fail the build.

## Challenges Faced and Mitigation

**Malformed tool output is not validated.** FA-10 simulated a tool returning an object of the wrong shape, and the dispatcher passed it through with status: ok. Input schemas are enforced, but there is no equivalent output-schema check at the dispatcher boundary, even though section 9 of the tool catalogue specifies one. An unexpected response could therefore reach downstream steps as if it were valid data.

*Mitigation.* Validate every tool's data against its declared output schema inside dispatch.invoke before returning it, convert a non-conforming response into a failed result with no usable data, record it in the trace, and re-run FA-10. This must land before the Week 5 agent loop starts reasoning over tool results.

**The catalogue's worked examples contradicted its own rule on lookalike supplier names.** Version 1.0 of the catalogue, published on 23 September, treated Lakeview Building Materials and Lakeview Building Supplies as eligible and left the resemblance to the officer. During PR #53 review on 24 September, section 5, the exclusion-reason table and the schemas were changed to exclude both with NAME\_DISCREPANCY until the officer records clearance, as Requirement 4.6 (v1.2) requires. The worked examples were only half-updated: the comparison example still ranked QT-001, and the draft justification still claimed three eligible quotations. The document version also stayed at 1.0, so a reader working from the earlier text could not tell it had changed. The implementation follows 4.6: on the recorded run only one eligible cement offer remains and the comparison returns INSUFFICIENT\_QUOTATIONS.

*Mitigation.* The catalogue is now at version 1.1, with both examples matching the recorded run. No rule, schema or tool contract changed. When a rule changes, every worked example that exercises it must change in the same commit, and the document version must move.

**The operational datasets have not been human-reviewed.** Inventory, supplier and quotation data did not exist before this week, although the environment variables pointing to them had been declared since Week 2 and no deliverable had been assigned them. They were created alongside the catalogue so the contracts could be specified against real records, and are registered as DAT-001 to DAT-003 with status pending\_review.

*Mitigation.* Someone other than the author should review them before the Week 7 evaluation relies on them. Each tool already verifies its data file against the registered SHA-256, so any change made during review will be caught and must be re-registered.

**The architecture shows five human gates; one is implemented.** The officer confirmation before create\_requisition\_draft is enforced and tested. Confirming extracted data, confirming the comparison, submitting the requisition and the manager's decision are specified but not yet built. Until the Week 5 state machine exists, the CLI allow-list is the full catalogue; per-step restriction is proven only in tests.

*Mitigation.* This is stated in the diagram's own implementation-boundary section, avoiding the problem from Week 3 where the diagram was read as a description of the code. The remaining gates belong to the Week 5 state model.

**Parallel authorship produced divergence for the third week running.** The lookalike-name contradiction arose because a rule was amended after the catalogue was published, while the implementation and other write-ups were being written against it. The per-file Owner headers of the Week 5 to 7 stubs also still named different owners from the issue tracker, even though the documentation index had been reconciled.

*Mitigation.* The Week 3 recommendation stands and is now more pressing: the consistency check should run on a week's specifications before implementation begins. The Week 5 to 7 stub headers have been aligned with the tracker.

## Results

All 35 existing tool and authorization tests passed. The full repository suite passed 258 tests with no failures. The number skipped depends on which optional Gemini or RAG dependencies are installed (6 in the tester's environment, 2 on a local re-run on 29 September); skipped tests are outside the Week 4 scope. Nine of the ten focused failure and authorization scenarios behaved as expected. The one failure, FA-10, is the output-validation gap described above.

The recorded run on 24 September exercised all four tools under the officer role with no model call. Cement, sitting exactly at its reorder point, was flagged with a computed quantity of 120 bags. The blacklisted offer with the lowest headline price (QT-004, UGX 29,800 per bag) was excluded on status alone, as POL-002-C02 requires and as a comparison sorted by price would have missed. The per-tonne offer was converted using the factor stated on the quotation and ranked at a landed cost of UGX 4,479,600, with VAT and delivery shown separately. The draft was written as REQ-2026-001 in DRAFT, with routing and approval fields null and the unresolved supplier-name discrepancy carried on the record rather than dropped.

## Upcoming Tasks

Add output-schema validation at the dispatcher and re-run FA-10. Arrange an independent review of DAT-001 to DAT-003. Build the Week 5 bounded agent loop and state machine, including per-step allow-lists, the remaining human gates, and the state preservation required by Requirement 7.5. Note that the tool count is now at the charter ceiling of four, so any additional tool, such as policy retrieval or document conversion, requires a charter amendment.

Carried over from Week 3 and still to be confirmed closed: tuning the item cutoff, adding a non-UGX evaluation case and band-boundary cases, measuring latency across more runs, resolving the retrieval-ordering contradiction between the charter and Requirement 7.1 (the updated diagram follows Requirement 7.1, but the charter has not been amended), and closing the v1.1 prompt-history row.

## Summary of Progress

All five Week 4 deliverables were completed. The application now has four deterministic tools behind a single orchestration entry point, with injected roles, a closed allow-list, a human confirmation gate in front of the only side effect, and no path by which the agent can approve, order, pay or contact a supplier.

The main learning echoes Week 3\. Every existing tool test passed, and the week could easily have been reported as clean. The one real defect came from testing what the contract promised rather than what the code happened to do: the catalogue said responses would be validated, and nobody had checked that they were. A green suite shows that the tests pass. It does not show that the tests cover every promise in the specification.
