# Group Y Progress Report Week 7

**Course:** BSE4104 Emerging Trends in Software Engineering

**Group:** Y | **Week ending:** 16 October 2026 | **Version:** 1.0

**Owner:** Nannyombi Shakiran | **Prepared:** 15 October 2026

**Repository:** [Group Y procurement agent](https://github.com/GeorgeLukaanya/bse4104-procurement-agent)

**Tracker:** [Group Y ClickUp board](https://app.clickup.com/9012272120/v/s/90129079418)

## Introduction

Week 7 is the evaluation week: a scenario set of at least 30 cases, observability evidence, guardrail evidence, and a failure catalogue. One of the five deliverables is merged. Three have not been started. This report records that position the day before the due date.

## Tasks and contributions

| Deliverable | Evidence | Status | Assignee |
|---|---|---|---|
| 30+ scenario evaluation | 45 scenarios (37 offline, 8 live): 42 pass, 3 fail, 0 safety violations. [Write-up](../evaluation/scenarios.md); [results](../../evidence/evaluation/week-07/scenario-results.json); [issue #31](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/31); [PR #72](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/72), merged 13 October. Two of the five failures were fixed in [PR #73](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/73), merged 15 October. | Complete, awaiting team review | Lukaanya George |
| Observability / tracing evidence | The write-up is still the empty template. [Issue #32](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/32). | Not started | Beingana Jim Junior |
| Guardrail implementation evidence | The write-up is still the empty template. [Issue #33](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/33). | Not started | Sekyeza Elroy Nunda |
| Failure catalogue | The write-up is still the empty template. [Issue #34](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/34) is assigned to Ainamani Jim Isaac. The docs index in this repository still names Lukaanya George. | Not started | Ainamani Jim Isaac |
| Week 7 progress report | This page. [Issue #35](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/35). | Draft for review | Nannyombi Shakiran |

No Week 7 issue has a ClickUp task URL yet. The board link above is the tracker the issues point at.

## Decisions

**The scenario evaluation and the failure catalogue were swapped.** On 13 October Lukaanya George took issue #31 and Ainamani Jim Isaac took issue #34. The scenario write-up records the reassignment. The GitHub assignees match that swap. The deliverable table in `docs/README.md` still lists George on the failure catalogue.

**The evaluation recorded failures before they were fixed.** PR #72, merged 13 October, reported 40 pass and 5 fail and did not change the code. [PR #73](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/73), merged 15 October, fixed two of them. A missing exchange rate now stops for the officer, who can supply `--exchange-rate`. Confirming both gates no longer compiles a requisition when no supplier is eligible. The merged record is 42 pass and 3 fail.

## Results

Every unauthorized and adversarial action in the 45 scenarios was refused. No requisition went beyond `DRAFT`. The eight live calls used Gemini. One of them, a single extraction attempt, took 281 seconds. The offline scenarios run in CI with no API key, and the suite fails if an offline outcome drifts from the recorded file.

Three failures remain in the merged record:

1. "Each chair" is still extracted as unit `unit` rather than `each` (S-41). This is the open FC-08 failure.
2. Three live calls exceeded the 30-second ceiling (S-41 at 31 seconds, S-44 at 83 seconds, S-45 at 281 seconds). The extraction client has no per-call timeout.

Both are with Beingana Jim Junior. S-09 and S-12, the missing exchange rate and the requisition compiled with no eligible supplier, were fixed in PR #73.

## Challenges

Three Week 7 write-ups are unstarted on the day before they are due: observability, guardrails, and the failure catalogue. The scenario results already name the failures the catalogue is supposed to record, so the catalogue has a source. It has no page yet. This report should be revised once those three pages exist.

## Plan for Week 8

Week 8 is due 23 October. The deliverables already on the tracker are:

- Final engineering report, 8–12 pages, Nannyombi Shakiran, [issue #36](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/36).
- Presentation deck and live demonstration, Ainamani Jim Isaac, [issue #37](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/37).
- Hardening and known limitations, Beingana Jim Junior, [issue #38](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/38).
- Final evaluation and evidence pack, Sekyeza Elroy Nunda, [issue #39](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/39).
- Tagged release and the Week 8 progress report, Lukaanya George, [issue #40](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/40).

The three missing Week 7 pages should exist before the final report cites them.
