# Group-Y-01 Progress Report Week 1

## Introduction

This report summarises the team’s Week 1 progress on the **SME Procurement-Preparation Agent**, a bounded agentic system intended to help a procurement officer in a small or medium Ugandan trading business complete a weekly reorder review and prepare a policy-compliant purchase requisition for manager approval.

During the week, the team clarified the problem context, defined the target users, established the scope and constraints, documented user stories and acceptance criteria, designed the initial architecture/context diagram, and agreed on the AI boundaries that will guide implementation.

## Tasks

The table below summarises the Week 1 tasks, their purpose, completion status, and assigned team member.

| Task | Description | Status | Assignee |
|---|---|---|---|
| Project charter | Documented the problem statement, target users, AI value, system scope, assumptions, constraints, success criteria, risks, and team ownership for the eight-week project. | Done | Lukaanya George |
| User stories and acceptance criteria | Defined the main user goals and wrote acceptance criteria covering reorder review, quotation parsing, supplier eligibility, price comparison, policy retrieval, justification drafting, requisition compilation, approval routing, audit logging, and safety-boundary enforcement. | Done | Nannyombi Shakiran |
| AI boundary matrix | Separated AI-supported activities from deterministic and human-controlled responsibilities, ensuring that calculations, supplier eligibility checks, approvals, purchase orders, payments, and supplier contact remain outside the AI layer. | Done | Beingana Jim Junior |
| Initial architecture/context diagram | Created the initial system context showing the procurement officer, approving manager, data store, Gemini API/foundation model, and the SME Procurement-Preparation Agent within the project boundary. | Done | Sekyeza Elroy Nunda |
| GitHub and ClickUp setup | Created the shared GitHub repository and set up ClickUp for project task tracking and coordination. | Done | Lukaanya George |
| Week 1 progress report | Compiled the weekly progress report by summarising completed deliverables, responsibilities, challenges, mitigation actions, and the baseline for the next week of work. | Done | Ainamani Jim |

## Upcoming Tasks

- Choose an accessible model and document its capability, cost, latency, privacy, and access considerations.
- Integrate the model into your application.
- Create **Prompt Specification v1.0**: role, task, context, constraints, output format, and failure behaviour.
- Create at least **10 test cases** and record expected vs actual behaviour.
- Version at least **two meaningful prompt iterations**.

## Challenges Faced and Mitigation

- None

## Summary of Progress

Overall, Week 1 was completed successfully. The team produced the project charter, requirements document, AI boundary matrix, initial architecture/context diagram, repository scaffold, ClickUp setup, and this weekly progress report. These artefacts establish a strong baseline for Week 2, where the team can begin turning the documented scope and requirements into implementation tasks.
