# SME Procurement-Preparation Agent

**AI-Native & Agentic Engineering Capstone** under BSE4104 Emerging Trends in Software Engineering, Makerere University, College of Computing and Information Sciences

## What this is

A bounded agentic system that helps a procurement officer in a small or medium
Ugandan enterprise turn a weekly reorder review into a policy-compliant purchase
requisition, ready for a human manager to approve.

AI reads and normalises unstructured supplier quotations, retrieves applicable
procurement policy and drafts a written justification. Deterministic code performs
all arithmetic, eligibility checks and approval routing. The system never issues a
purchase order, contacts a supplier, commits funds or approves anything itself.

## Status

Week 1 of 8: problem framing and requirements.

## Repository layout

| Path | Contents |
|---|---|
| `docs/requirements/` | Project charter, user stories, AI boundary matrix |
| `docs/architecture/` | Architecture and context diagrams |
| `docs/weekly-reports/` | Weekly progress reports |
| `docs/evaluation/` | Evaluation plans and results |
| `prompts/` | Versioned prompt specifications |
| `knowledge/` | Corpus metadata and provenance — no restricted data |
| `src/` | Application source |
| `tests/` | Automated tests |
| `evidence/` | Traces, screenshots, demo recordings |

## Running it

Not yet runnable. Instructions land in Week 2 with the first model integration.

```bash
cp .env.example .env   # then fill in your own values
```

## Data

All data is synthetic and team-created. No real supplier, customer or financial
records are used anywhere in this project.

## Team

Group Y — BSE4104.

| Role | Member | GitHub |
|---|---|---|
| Project / Requirements Lead | Nannyombi Shakiran | [Shakiran-Nannyombi](https://github.com/Shakiran-Nannyombi) |
| Application / Integration Lead | Ainamani Jim Isaac | [Jimisaq](https://github.com/Jimisaq) |
| AI Engineering Lead | Beingana Jim Junior | [jim-junior](https://github.com/jim-junior) |
| Quality / Security Lead | Sekyeza Elroy Nunda | [NundaElroy](https://github.com/NundaElroy) |
| DevOps / Documentation Lead | Lukaanya George | [GeorgeLukaanya](https://github.com/GeorgeLukaanya) |

Roles rotate. Every member is accountable for explaining any part of the system.

## AI use declaration

AI tools are used for design, coding, testing, documentation and evaluation in this
project, as the course expects. Tools used and material AI-assisted decisions are
recorded in `docs/AI-ENGINEERING-LOG.md`. All generated code is reviewed and tested
before merge, and every team member can explain the work submitted under their name.

## Task board

ClickUp: [Group Y board](https://app.clickup.com/9012272120/v/s/90129079418)
