# Group Y Progress Report Week 6

**Course:** BSE4104 Emerging Trends in Software Engineering

**Group:** Y | **Week ending:** 9 October 2026 | **Version:** 1.0

**Owner:** Ainamani Jim Isaac | **Prepared:** 9 October 2026

**Repository:** [Group Y procurement agent](https://github.com/GeorgeLukaanya/bse4104-procurement-agent)

**Tracker:** [Group Y ClickUp board](https://app.clickup.com/9012272120/v/s/90129079418)

## Introduction

Week 6 focused on state and memory: preserving a procurement review across commands, reusing
valid completed work, and showing prior procurement information as advisory context without
letting it control eligibility, ranking or approval. The team delivered a state model, a memory
design, a working demonstration with recorded evidence, and a draft MCP-style specification for
policy retrieval. The implementation also closed the Week 5 malformed-output defect and improved
the agent's reporting of unavailable or tampered quotation data.

## Tasks and Contributions

| Deliverable | Contribution and evidence | Status | Assignee |
|---|---|---|---|
| State model | Modelled ephemeral state, review checkpoints and long-lived evidence or memory; documented transitions, source fingerprints, retention and resume rules. [State model](../architecture/state-model.md); [issue #26](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/26); [PR #68](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/68). | Complete; awaiting team review | Sekyeza Elroy Nunda |
| Memory design and data handling | Defined the justified advisory-memory use case, stored fields, access, 365-day expiry and deletion rules. [Memory design](../architecture/memory-design.md); [issue #27](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/27). | Complete; awaiting team review | Beingana Jim Junior |
| Working memory and state demonstration | Implemented checkpoint persistence and advisory memory, then recorded before/after, resume, duplicate-prevention, next-week, failure and recovery evidence. [Working demonstration](../architecture/working-memory.md); [issue #28](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/28); [PR #65](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/65). | Complete; awaiting team review | Lukaanya George |
| MCP-style interface specification | Specified `retrieve_policy` inputs, outputs, permissions, failure behaviour and security boundary without adding a fifth catalogue tool. [Interface specification](../architecture/mcp-interface.md); [issue #29](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/29); [PR #67](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/67). | Draft for team review | Nannyombi Shakiran |
| Week 6 progress report | Compiled the week's implementation, evidence, decisions, gaps and Week 7 plan. [Issue #30](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/30). | Complete; awaiting team review | Ainamani Jim Isaac |

## Key Decisions

**Separate run state, memory and evidence.** In-process `AgentState` lasts for one command. A
checkpoint under `var/agent-state/` preserves one review, while
`var/memory/procurement-memory.jsonl` carries advisory supplier notes and prior outcomes across
reviews. Execution traces remain evidence and are not read as planning memory.

**Reuse results only while their sources are unchanged.** Each completed step records SHA-256
fingerprints for the files it used. On resume, the first step with changed input and every later
step are recomputed. A changed comparison also invalidates its human confirmations. This avoids
applying an old approval to new prices or supplier information.

**Keep memory advisory.** Supplier notes and prior outcomes are displayed to the officer but are
not passed to the planner, tool dispatcher, eligibility rules, quotation ranking or requisition.
Current registered data and policy remain authoritative. Memory records expire after 365 days
and can be listed, deleted or purged through the memory CLI.

**Specify policy retrieval as an AI-layer interface.** The MCP-style document keeps
`retrieve_policy` outside the four-tool catalogue. It is read-only and would be permitted only
after comparison confirmation. The document is a specification, not evidence that the interface
is already wired into the agent loop.

## Implementation and Results

PR #65 added atomic JSON checkpoints, deterministic run identifiers, cumulative iteration
accounting and source-aware resume. It also added structured advisory memory. The recorded
demonstration shows seven cases: no-memory baseline, memory displayed without changing the
decision, resume after Gate 2, no duplicate draft on rerun, memory available in the next review,
supplier-data failure, and recovery after restoration.

The completed-run checkpoint prevents a repeated command from creating a second requisition.
When source data changes, stale downstream results are discarded. The failure/recovery evidence
shows that an unavailable supplier register stops safely and that a later run can reuse only the
still-valid inventory result before recomputing eligibility and comparison.

PR #64 added output-schema validation at the dispatcher boundary, closing FA-10: malformed tool
data is now discarded as `OUTPUT_SCHEMA_INVALID`. PR #66 distinguishes a missing quotation file
from a valid empty result and reports unavailable or integrity-failed data accurately. The current
automated suite passes **365 tests**.

## Challenges and Open Gaps

**Retention enforcement is incomplete.** The state model sets checkpoint retention at 30 days,
but no housekeeping command currently removes expired checkpoint files. Manual deletion or
`--fresh` is required. Memory expiry has a purge command, but automatic scheduling is outside the
current single-machine scope.

**The MCP-style capability is not implemented.** The existing RAG pipeline is callable from its
own CLI, but `retrieve_policy` is not yet available through the agent's phase allow-list or shared
tool envelope. Total-to-comparison validation, strict request limits, role injection and complete
withholding of citation-invalid answers remain specification gaps.

**The bounded loop is still incomplete.** Gemini planning, policy retrieval inside the loop and
AI justification drafting remain unbuilt or unwired. The deterministic planner continues to be
the offline default.

**TC-04 unit preservation still fails.** The quotation-extraction prompt was updated to v1.3
during the week. TC-07 now passes, but the ten-case regression remains 9/10 because TC-04
returned `unit` instead of preserving the source value `each`. A fresh uncached live retest on
9 October 2026 completed successfully in 5.1088 seconds and again returned `unit`; all other
fields were correct. This is a Week 2 prompt-evaluation issue carried into the Week 5 follow-up,
not a core Week 6 state or memory deliverable, but it remains unresolved.

## Plan for Week 7

- Run the required 30-plus evaluation scenarios across happy paths, failures, authorization and
  recovery cases.
- Produce observability evidence and confirm that traces contain the required identifiers,
  decisions, failures and stop reasons without secrets.
- Complete the failure catalogue and verify guardrail behaviour against the implemented loop.
- Address the MCP specification's highest-risk gaps before wiring policy retrieval into the
  agent: comparison-bound totals, withheld invalid answers, input limits and phase authorization.
- Add or schedule checkpoint-retention cleanup and test expiry behaviour.
- Retest TC-04 without weakening the requirement to preserve the source unit exactly.
