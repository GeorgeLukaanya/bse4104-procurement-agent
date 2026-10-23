# Group Y Progress Report: Week 5

**Course:** BSE4104 Emerging Trends in Software Engineering
**Group:** Y | **Week ending:** 2 October 2026 | **Version:** 1.0
**Owner:** Beingana Jim Junior | **Prepared:** 9 October 2026
**Repository:** [Group Y procurement agent](https://github.com/GeorgeLukaanya/bse4104-procurement-agent)
**Tracker:** [Group Y ClickUp board](https://sharing.clickup.com/9012272120/l/h/5-901213426906-1/31d463956153cf6)

## Introduction

Week 5 focused on bounded agency: preparing one reorder item for a Purchase Requisition in `DRAFT`, with controlled tool selection, human hand-off and explicit stop limits. The team delivered an architecture, task contract, working workflow and three recorded runs. This report was completed after the 2 October deadline; later review fixes are identified separately below.

## Tasks and Individual Contributions

| Deliverable | Contribution and evidence | Status | Assignee |
|---|---|---|---|
| Agent architecture | Designed Sense/Context → Plan/Decide → Act/Tool → Observe → Stop/Re-plan, with phase allow-lists and human gates. [Diagram and implementation boundary](../architecture/agent-architecture.md). | Complete; awaiting team review | Lukaanya George |
| Agent task contract | Defined the goal, allowed actions, limits, stop conditions and known implementation gaps. [Contract, section 12](../requirements/agent-task-contract.md). | Complete; awaiting team review | Sekyeza Elroy Nunda |
| Working bounded workflow | Built deterministic planning over scan, eligibility, comparison and confirmed draft creation. [Working agent](../architecture/working-agent.md); [PR #60](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/60). | Implemented | Nannyombi Shakiran |
| Three execution traces | Recorded human hand-off, completed draft and iteration-limit halt. [Trace summary](../evaluation/execution-traces.md); [PR #63](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/63). | Three runs recorded; recovery follow-up below | Ainamani Jim Isaac |
| Week 5 report and prompt follow-up | Compiled this report; addressed rule 6 formatting and punctuation, synchronised prompt v1.3 and completed the live retest and ten-case regression. [Prompt specification](../../prompts/quotation-extraction-v1.md). | Report and evaluation complete; TC-04 follow-up | Beingana Jim Junior |

## Key Design Decisions

**Bound the workflow by contract.** The iteration limit is **8**, with a **120-second** timeout. Eight accommodates the designed five-action path, two re-checks after supplier-name clearance and one spare re-plan. The current four-tool implementation consumes four iterations on a completed run; the designed policy-retrieval and AI-justification phases are not yet connected.

**Keep authority at the tool boundary.** The planner proposes one permitted action at a time; the dispatcher checks the step allow-list, injected role, input schema, confirmation and output. The deterministic planner makes no model call. Comparing quotations does not award a supplier, and only the officer-confirmed write creates a requisition in `DRAFT`.

**Document the implementation boundary.** The architecture is a target design. Gemini planning, policy retrieval inside the loop, AI justification drafting and a separate justification gate are not demonstrated by these runs. Section 12 of the contract records the gaps rather than treating the diagram as proof of implementation.

## Results

The three Week 5 runs use the same cement reorder: 120 bags of `AH-CM-001`. Eligibility excludes two suppliers for `NAME_DISCREPANCY` and one for `BLACKLISTED`. The remaining quotation, QT-002, has landed cost **UGX 4,479,600**. Only one of three required eligible quotations remains, so the comparison exposes `INSUFFICIENT_QUOTATIONS` and an exception requirement.

Without confirmation, the agent stops after three calls at the human gate and creates no draft. With both confirmations, it creates `REQ-2026-001` in `DRAFT` after four calls; routing, approval and decision fields remain null. A deliberately reduced cap of one stops after the inventory check, with no eligibility, comparison or draft result. These runs establish controlled orchestration, not model-driven planning or broad performance.

## Challenges and Review Follow-up

**Malformed outputs (FA-10).** The Week 4 dispatcher accepted a malformed response. [PR #64](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/64) closed this on 6 October: every tool response is checked against its output schema, and invalid output is discarded with `OUTPUT_SCHEMA_INVALID`.

**Prompt version drift and red CI.** PR #62 updated the prompt to v1.2 while the cache configuration remained v1.1. This could reuse old answers under new prompt attribution. PR #64 aligned the configuration, example environment and tests. The current wording cleanup advances all three to v1.3. Future merges must wait for passing required CI; local tests alone do not establish that remote CI passed. The historical live evaluation remains **v1.1: 9/10**, with TC-07 failing ambiguous-date handling. The uncached v1.3 retest now passes TC-07, as does the full regression. The latter scores **9/10**, with TC-04 failing unit preservation (`unit` instead of `each`); all ten responses conform to the schema. Local tests: **365 passed, 3 skipped**.

**Failure/recovery and data errors.** The original third trace demonstrates a controlled stop, not recovery. Later [Week 6 failure and recovery evidence](../architecture/working-memory.md#4-run-state-resume-instead-of-repeat) records an unavailable supplier register followed by resume without repeating the scan. [PR #65](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/65) implements checkpoint persistence, closing contract gap 2. [PR #66](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/66) also fixes the planner's misleading “no quotations” response for a missing file, distinguishing unavailable data from an integrity failure. These are post-deadline fixes.

## Upcoming Tasks

Complete Week 6 state and memory documentation, access/retention rules and the MCP-style capability specification. Review the later recovery evidence now linked from the Week 5 trace write-up. Remediate and retest TC-04 without weakening its unit-preservation expectation. Carry forward the unbuilt policy and justification phases, Gemini planning, specific stop codes and `NO_PROGRESS` enforcement into integration and Week 7 evaluation.
