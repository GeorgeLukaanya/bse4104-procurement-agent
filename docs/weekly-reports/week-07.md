# Group Y Progress Report Week 7

**Course:** BSE4104 Emerging Trends in Software Engineering

**Group:** Y | **Week ending:** 16 October 2026 | **Version:** 1.1

**Owner:** Nannyombi Shakiran | **Prepared:** 20 October 2026

**Repository:** [Group Y procurement agent](https://github.com/GeorgeLukaanya/bse4104-procurement-agent)

**Tracker:** [Group Y ClickUp board](https://app.clickup.com/9012272120/v/s/90129079418)

## Introduction

Week 7 is the evaluation week: at least 30 scenarios, plus observability, guardrails, and a
failure catalogue. All four write-ups are merged. This report records the final scores, the
decisions that changed them, and what is left for Week 8.

## Tasks and contributions

| Deliverable | Evidence | Status | Assignee |
|---|---|---|---|
| 30+ scenario evaluation | Final run, 19 October: 45 scenarios, 44 pass, 1 fail, 0 safety violations. Every live call finished under 30 seconds. [Write-up](../evaluation/scenarios.md); [results](../../evidence/evaluation/week-07-final/scenario-results.json); [issue #31](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/31); [PR #72](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/72), [PR #78](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/78). | Complete; final run 19 Oct | Lukaanya George |
| Observability / tracing evidence | Merged. Logs cover extraction, retrieval, tools and workflow stops, using the retained 13 October live run. [Write-up](../evaluation/observability.md); [issue #32](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/32); [PR #75](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/75). | Complete, awaiting team review | Beingana Jim Junior |
| Guardrail implementation evidence | Merged. Eight guardrails, each enforced in code, with a recorded refusal. [Write-up](../evaluation/guardrails.md); [issue #33](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/33); [PR #74](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/74). | Complete, awaiting team review | Sekyeza Elroy Nunda |
| Failure catalogue | Nine genuine failures, all fixed and re-tested. [Write-up](../evaluation/failure-catalogue.md); [issue #34](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/34); [PR #76](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/76). | Complete, awaiting team review | Ainamani Jim Isaac |
| Week 7 progress report | This page. [Issue #35](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/35). | Draft for review | Nannyombi Shakiran |

Nannyombi Shakiran also fixed two scenario failures in [PR #73](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/73): S-09, a missing exchange rate, and S-12, a requisition compiled with no eligible supplier.

## Decisions

**Lukaanya George and Ainamani Jim Isaac swapped tasks.** On 13 October George took the scenario
evaluation (issue #31) and Jim Isaac took the failure catalogue (issue #34). The write-ups and
the deliverable table in `docs/README.md` use that assignment.

**The 13 October results were updated after the fixes, then replaced by one clean run.** The
first run scored 40 pass and 5 fail and did not change the code. After PR #73, that results file
was updated in place, so it mixed the original run with the S-09 and S-12 passes. On 19 October,
[PR #78](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/78) re-recorded all 45
scenarios as one run. The original 13 October live files stay in the repository, because the
observability write-up and the failure catalogue cite them.

## Results

The 19 October run, at commit `94e917c`, scored **44 pass out of 45**, with **0 safety
violations**. Every unauthorized and adversarial action was refused. No requisition went beyond
`DRAFT`. All eight live calls used Gemini, prompt v1.4, with no cache, and each finished under
30 seconds.

Every failure from 13 October now passes, including S-09 and S-12. S-41 keeps the source unit
`each`. S-44 and S-45, which had run for 83 seconds and 281 seconds, now finish inside the
ceiling. The failure catalogue lists the nine observed failures, FC-01 to FC-09, and each has a
passing re-test.

The one new failure is S-38. The clean quotation hit the 30-second deadline once, returned
`timeout` after 29.95 seconds, and produced no record. The same document had extracted correctly
in 6.5 seconds on 13 October.

## Challenges

**The 30-second deadline swaps a long hang for a visible timeout.** On 13 October one live call
ran for 281 seconds with no timeout. The deadline now stops a slow call and names the failure.
The cost showed up once, on S-38: an ordinary quotation can fail when the provider is slow, and
no time remains for a retry. The officer can rerun extraction. The Week 8 limitations register
does not treat S-38 as fixed.

## Plan for Week 8

Week 8 is due 23 October.

- Final engineering report, Nannyombi Shakiran, [issue #36](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/36). Not started. It should cite the 19 October run as the scenario score and keep the 13 October failures as history.
- Presentation deck and live demonstration, Ainamani Jim Isaac, [issue #37](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/37). Not started.
- Hardening and known limitations, Beingana Jim Junior, [issue #38](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/38). Complete locally on 20 October, awaiting team review. S-38 remains an open limitation.
- Final evaluation and evidence pack, Sekyeza Elroy Nunda, [issue #39](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/39). Not started.
- Tagged release and the Week 8 progress report, Lukaanya George, [issue #40](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/40). Not started.
