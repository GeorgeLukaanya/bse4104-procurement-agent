# Documentation index

Course folders are the source of truth. Each week has five deliverables — one owned file per teammate. Do not add a second copy under a `weekN` folder.

ClickUp board: [Group Y](https://app.clickup.com/9012272120/v/s/90129079418)

## Folders

| Path | What belongs here |
|---|---|
| [`docs/requirements/`](requirements/) | Charter, user stories, AI boundary matrix, agent task contract |
| [`docs/architecture/`](architecture/) | Diagrams, model note, baseline/RAG/tools/agent/memory write-ups, [CI map](architecture/ci.md), [tool schemas](architecture/schemas/) |
| [`docs/weekly-reports/`](weekly-reports/) | Week 1–8 progress reports and the final engineering report |
| [`docs/evaluation/`](evaluation/) | Prompt, RAG, tool, agent and final evaluation evidence |
| [`docs/AI-ENGINEERING-LOG.md`](AI-ENGINEERING-LOG.md) | Material AI-assisted decisions |
| [`docs/week-04-change-log.md`](week-04-change-log.md) | Week 4: what changed under #15 and why — team baseline |
| [`docs/week-04-team-brief.md`](week-04-team-brief.md) | Week 4: handover brief, what each owner needs |
| [`prompts/`](../prompts/) | Versioned prompt specifications |
| [`knowledge/`](../knowledge/) | Corpus metadata and provenance, and the operational [datasets](../knowledge/data/) the tools read — no restricted data |
| [`evidence/`](../evidence/) | Traces, screenshots, demo recordings |

Working code stays in `src/` and `tests/`. The markdown file for a “working …” deliverable is the write-up, not a second implementation.

## Owners

| Role | Member | GitHub |
|---|---|---|
| Project / Requirements Lead | Nannyombi Shakiran | [Shakiran-Nannyombi](https://github.com/Shakiran-Nannyombi) |
| Application / Integration Lead | Ainamani Jim Isaac | [Jimisaq](https://github.com/Jimisaq) |
| AI Engineering Lead | Beingana Jim Junior | [jim-junior](https://github.com/jim-junior) |
| Quality / Security Lead | Sekyeza Elroy Nunda | [NundaElroy](https://github.com/NundaElroy) |
| DevOps / Documentation Lead | Lukaanya George | [GeorgeLukaanya](https://github.com/GeorgeLukaanya) |

Due dates are the Friday of each teaching week.

> **Owners follow the GitHub issues.** Every week below was reconciled against issues [#15](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/15)–[#40](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/40) on 23 September 2026. Weeks 4 to 7 had owners that did not match the tracker; Week 8 already agreed. If a row and its issue ever disagree again, **the issue wins** — change the assignee there, then update this file.

## Week 1 — 4 September 2026 — done

| Deliverable | Path | Owner | Status |
|---|---|---|---|
| Project charter | [`docs/requirements/project-charter.md`](requirements/project-charter.md) | Lukaanya George | Done |
| User stories and acceptance criteria | [`docs/requirements/user-stories.md`](requirements/user-stories.md) | Nannyombi Shakiran | Done |
| AI boundary matrix | [`docs/requirements/ai-boundary-matrix.md`](requirements/ai-boundary-matrix.md) | Beingana Jim Junior | Done |
| Architecture / context diagram | [`docs/architecture/context-diagram.md`](architecture/context-diagram.md) | Ainamani Jim Isaac | Done |
| Week 1 progress report | [`docs/weekly-reports/week-01.md`](weekly-reports/week-01.md) | Lukaanya George | Done |

## Week 2 — 11 September 2026

| Deliverable | Path | Owner | Status |
|---|---|---|---|
| Working baseline model interaction | [`docs/architecture/working-baseline.md`](architecture/working-baseline.md) | Ainamani Jim Isaac | Done (write-up) |
| Model selection note | [`docs/architecture/model-selection-note.md`](architecture/model-selection-note.md) | Beingana Jim Junior | Done |
| Prompt specification | [`prompts/quotation-extraction-v1.md`](../prompts/quotation-extraction-v1.md) | Nannyombi Shakiran | Done |
| 10-case prompt evaluation | [`docs/evaluation/prompt-evaluation.md`](evaluation/prompt-evaluation.md) | Sekyeza Elroy Nunda | In progress — fill Actual/Result |
| Week 2 progress report | [`docs/weekly-reports/week-02.md`](weekly-reports/week-02.md) | Lukaanya George | Not started |

## Week 3 — 18 September 2026

| Deliverable | Path | Owner | Status |
|---|---|---|---|
| Corpus / source register | [`knowledge/source-register.md`](../knowledge/source-register.md) | Nannyombi Shakiran | Done (write-up) |
| RAG architecture diagram | [`docs/architecture/rag-architecture.md`](architecture/rag-architecture.md) | Beingana Jim Junior | Done |
| Working RAG pipeline | [`docs/architecture/working-rag-pipeline.md`](architecture/working-rag-pipeline.md) | Beingana Jim Junior | Done |
| 15-case RAG evaluation | [`docs/evaluation/rag-evaluation.md`](evaluation/rag-evaluation.md) | Sekyeza Elroy Nunda | Done (write-up) |
| Week 3 progress report | [`docs/weekly-reports/week-03.md`](weekly-reports/week-03.md) | Lukaanya George | Not started |

## Week 4 — 25 September 2026

| Deliverable | Path | Owner | Status |
|---|---|---|---|
| Tool catalogue and schemas | [`docs/architecture/tool-catalogue.md`](architecture/tool-catalogue.md) + [`schemas/`](architecture/schemas/) | Lukaanya George | Complete, awaiting team review |
| Working demonstration of two tools | [`docs/architecture/working-tools.md`](architecture/working-tools.md) | Nannyombi Shakiran | Not started |
| Failure / authorization test evidence | [`docs/evaluation/tool-failure-tests.md`](evaluation/tool-failure-tests.md) | Beingana Jim Junior | Not started |
| Updated architecture diagram | [`docs/architecture/architecture.md`](architecture/architecture.md) | Ainamani Jim Isaac | Not started |
| Week 4 progress report | [`docs/weekly-reports/week-04.md`](weekly-reports/week-04.md) | Sekyeza Elroy Nunda | Not started |

## Week 5 — 2 October 2026

| Deliverable | Path | Owner | Status |
|---|---|---|---|
| Agent architecture diagram | [`docs/architecture/agent-architecture.md`](architecture/agent-architecture.md) | Lukaanya George | Not started |
| Agent task contract | [`docs/requirements/agent-task-contract.md`](requirements/agent-task-contract.md) | Sekyeza Elroy Nunda | Not started |
| Working bounded agent workflow | [`docs/architecture/working-agent.md`](architecture/working-agent.md) | Nannyombi Shakiran | Not started |
| Three execution traces | [`docs/evaluation/execution-traces.md`](evaluation/execution-traces.md) | Ainamani Jim Isaac | Not started |
| Week 5 progress report | [`docs/weekly-reports/week-05.md`](weekly-reports/week-05.md) | Beingana Jim Junior | Not started |

## Week 6 — 9 October 2026

| Deliverable | Path | Owner | Status |
|---|---|---|---|
| State model | [`docs/architecture/state-model.md`](architecture/state-model.md) | Sekyeza Elroy Nunda | Not started |
| Memory design and data handling | [`docs/architecture/memory-design.md`](architecture/memory-design.md) | Beingana Jim Junior | Not started |
| Working memory / state demonstration | [`docs/architecture/working-memory.md`](architecture/working-memory.md) | Lukaanya George | Not started |
| MCP-style interface specification | [`docs/architecture/mcp-interface.md`](architecture/mcp-interface.md) | Nannyombi Shakiran | Not started |
| Week 6 progress report | [`docs/weekly-reports/week-06.md`](weekly-reports/week-06.md) | Ainamani Jim Isaac | Not started |

## Week 7 — 16 October 2026

| Deliverable | Path | Owner | Status |
|---|---|---|---|
| 30+ scenario evaluation | [`docs/evaluation/scenarios.md`](evaluation/scenarios.md) | Ainamani Jim Isaac | Not started |
| Observability / tracing evidence | [`docs/evaluation/observability.md`](evaluation/observability.md) | Beingana Jim Junior | Not started |
| Guardrail implementation evidence | [`docs/evaluation/guardrails.md`](evaluation/guardrails.md) | Sekyeza Elroy Nunda | Not started |
| Failure catalogue | [`docs/evaluation/failure-catalogue.md`](evaluation/failure-catalogue.md) | Lukaanya George | Not started |
| Week 7 progress report | [`docs/weekly-reports/week-07.md`](weekly-reports/week-07.md) | Nannyombi Shakiran | Not started |

## Week 8 — 23 October 2026

| Deliverable | Path | Owner | Status |
|---|---|---|---|
| Final engineering report | [`docs/weekly-reports/final-engineering-report.md`](weekly-reports/final-engineering-report.md) | Nannyombi Shakiran | Not started |
| Presentation deck and live demonstration | [`docs/architecture/final-presentation.md`](architecture/final-presentation.md) | Ainamani Jim Isaac | Not started |
| Hardening and known limitations | [`docs/architecture/known-limitations.md`](architecture/known-limitations.md) | Beingana Jim Junior | Not started |
| Final evaluation / evidence pack | [`docs/evaluation/final-evidence-pack.md`](evaluation/final-evidence-pack.md) | Sekyeza Elroy Nunda | Not started |
| Tagged release + Week 8 progress report | [`README.md`](../README.md) run instructions + [`docs/weekly-reports/week-08.md`](weekly-reports/week-08.md) | Lukaanya George | Not started |

## ClickUp copy list

Create one list per week on the Group Y board. Each row already has a GitHub issue; paste the ClickUp task URL into that issue once you create it.

Issues: [https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues)

### Week 2 — due 11 Sep 2026

- Fill 10-case prompt evaluation Actual/Result — Sekyeza Elroy Nunda — `docs/evaluation/prompt-evaluation.md` — [#8](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/8)
- Write Week 2 progress report — Lukaanya George — `docs/weekly-reports/week-02.md` — [#9](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/9)

### Week 3 — due 18 Sep 2026

- Corpus / source register — Nannyombi Shakiran — `knowledge/source-register.md` — [#10](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/10)
- RAG architecture diagram — Beingana Jim Junior — `docs/architecture/rag-architecture.md` — [#11](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/11)
- Working RAG pipeline — Beingana Jim Junior — `docs/architecture/working-rag-pipeline.md` — [#12](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/12)
- 15-case RAG evaluation — Sekyeza Elroy Nunda — `docs/evaluation/rag-evaluation.md` — [#13](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/13)
- Week 3 progress report — Lukaanya George — `docs/weekly-reports/week-03.md` — [#14](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/14)

### Week 4 — due 25 Sep 2026

- Tool catalogue and schemas — Lukaanya George — `docs/architecture/tool-catalogue.md` — [#15](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/15)
- Working demonstration of two tools — Nannyombi Shakiran — `docs/architecture/working-tools.md` — [#16](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/16)
- Failure / authorization test evidence — Beingana Jim Junior — `docs/evaluation/tool-failure-tests.md` — [#17](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/17)
- Updated architecture diagram — Ainamani Jim Isaac — `docs/architecture/architecture.md` — [#18](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/18)
- Week 4 progress report — Sekyeza Elroy Nunda — `docs/weekly-reports/week-04.md` — [#19](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/19)

### Week 5 — due 2 Oct 2026

- Agent architecture diagram — Lukaanya George — `docs/architecture/agent-architecture.md` — [#20](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/20)
- Agent task contract — Sekyeza Elroy Nunda — `docs/requirements/agent-task-contract.md` — [#21](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/21)
- Working bounded agent workflow — Nannyombi Shakiran — `docs/architecture/working-agent.md` — [#22](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/22)
- Three execution traces — Ainamani Jim Isaac — `docs/evaluation/execution-traces.md` — [#23](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/23)
- Week 5 progress report — Beingana Jim Junior — `docs/weekly-reports/week-05.md` — [#24](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/24)

### Week 6 — due 9 Oct 2026

- State model — Sekyeza Elroy Nunda — `docs/architecture/state-model.md` — [#26](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/26)
- Memory design and data handling — Beingana Jim Junior — `docs/architecture/memory-design.md` — [#27](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/27)
- Working memory / state demonstration — Lukaanya George — `docs/architecture/working-memory.md` — [#28](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/28)
- MCP-style interface specification — Nannyombi Shakiran — `docs/architecture/mcp-interface.md` — [#29](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/29)
- Week 6 progress report — Ainamani Jim Isaac — `docs/weekly-reports/week-06.md` — [#30](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/30)

### Week 7 — due 16 Oct 2026

- 30+ scenario evaluation — Ainamani Jim Isaac — `docs/evaluation/scenarios.md` — [#31](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/31)
- Observability / tracing evidence — Beingana Jim Junior — `docs/evaluation/observability.md` — [#32](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/32)
- Guardrail implementation evidence — Sekyeza Elroy Nunda — `docs/evaluation/guardrails.md` — [#33](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/33)
- Failure catalogue — Lukaanya George — `docs/evaluation/failure-catalogue.md` — [#34](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/34)
- Week 7 progress report — Nannyombi Shakiran — `docs/weekly-reports/week-07.md` — [#35](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/35)

### Week 8 — due 23 Oct 2026

- Final engineering report — Nannyombi Shakiran — `docs/weekly-reports/final-engineering-report.md` — [#36](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/36)
- Presentation deck and live demonstration — Ainamani Jim Isaac — `docs/architecture/final-presentation.md` — [#37](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/37)
- Hardening and known limitations — Beingana Jim Junior — `docs/architecture/known-limitations.md` — [#38](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/38)
- Final evaluation / evidence pack — Sekyeza Elroy Nunda — `docs/evaluation/final-evidence-pack.md` — [#39](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/39)
- Tagged release + Week 8 progress report — Lukaanya George — `README.md` + `docs/weekly-reports/week-08.md` — [#40](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/40)
