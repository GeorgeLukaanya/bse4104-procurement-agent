# Presentation Deck and Live Demonstration

| Field | Value |
|---|---|
| Week | 8 |
| Owner | Ainamani Jim Isaac |
| Due | 23 October 2026 |
| Status | Deck added; live demonstration script below |
| Path | `docs/architecture/final-presentation.md` |

## Brief requirement

12–15 minute presentation and live demonstration notes. Cover problem and AI justification, architecture progression, live end-to-end workflow, one evidence view, one real failure/recovery, guardrails and lessons. Store slides and demo recordings in `evidence/demo/`.

## Write-up

### Deck

[`evidence/demo/Group-Y-SME-Procurement-Agent-Panel-Presentation.pptx`](../../evidence/demo/Group-Y-SME-Procurement-Agent-Panel-Presentation.pptx),
prepared by Ainamani Jim Isaac. Twelve slides:

| # | Slide | Brief item |
|---|---|---|
| 1 | Title: a bounded agentic workflow for evidence-based reorder preparation | |
| 2 | Problem and scope | Problem |
| 3 | System objective and engineering contribution | AI justification |
| 4 | End-to-end workflow and demonstration sequence | Live workflow |
| 5 | Implemented architecture and system boundaries | Architecture |
| 6 | AI boundary and human control | Guardrails |
| 7 | Eight-week engineering progression | Architecture progression |
| 8 | Agent contract, limits and recovery | Failure and recovery |
| 9 | Evaluation design and final results | Evidence |
| 10 | Failure analysis and remediation: the 281 s call and the 30 s deadline | Real failure |
| 11 | Implemented scope and known gaps | Lessons |
| 12 | Conclusion | Lessons |

Slide 9 quotes the 19 October run (44/45 scenarios, 541 tests). The v1.0.0 release check
recorded **45/45 scenarios** and **548 tests** ([release notes](../../RELEASE_NOTES.md)). Both are
true for their dates; say which one is on screen.

### Live demonstration script

Synthetic data only, no API key needed, from a fresh install (`pip install -e ".[dev]"`, or
`".[dev,ui]"` for the browser view). Each step names the brief item it shows.

1. **End-to-end workflow.** Start the cement review. It scans, checks eligibility and compares,
   then stops at Gate 2 for the officer.
   ```bash
   procurement-agent --review-date 2026-09-25 --sku AH-CM-001 --fresh
   ```
   The same run is available in the browser with `procurement-ui`.
2. **Human control.** Confirm, and the run resumes from its checkpoint and compiles one
   requisition in `DRAFT`. Run it again to show that it does not compile a second one.
   ```bash
   procurement-agent --review-date 2026-09-25 --sku AH-CM-001 --confirm-comparison --confirm-draft
   ```
3. **Evidence view.** Open the trace of what the agent did, in
   `evidence/traces/agent-runs.jsonl` (stop reason, iterations, tool calls), or the recorded live
   evaluation in [`evidence/release/v1.0.0/scenarios/`](../../evidence/release/v1.0.0/scenarios/).
4. **Guardrails.** Run as the manager. The loop refuses to start, because approval is not a tool.
   ```bash
   procurement-agent --review-date 2026-09-25 --sku AH-CM-001 --role PROCUREMENT_MANAGER
   ```
5. **A real failure and recovery.** Show the 281 s extraction call from 13 October (slide 10;
   [failure catalogue](../evaluation/failure-catalogue.md), FC-09), the 30 s deadline that fixed
   it, and S-38, where that deadline later stopped one slow call visibly instead of hanging
   ([scenario write-up](../evaluation/scenarios.md)).

Fallback if the live demo fails: the recorded outputs in
[`evidence/release/v1.0.0/`](../../evidence/release/v1.0.0/) show the same steps.
