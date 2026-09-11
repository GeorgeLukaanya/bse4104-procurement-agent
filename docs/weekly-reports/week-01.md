# Group Y Progress Report: Week 1

**Course:** BSE4104 Emerging Trends in Software Engineering   
**Group:** Y   
**Week ending:** 4th September 2026   
**Version:** 1.1   

## **Introduction**

This report summarises the team's Week 1 progress on the SME Procurement-Preparation Agent, a bounded agentic system intended to help a procurement officer in a small or medium Ugandan trading business complete a weekly reorder review and prepare a policy-compliant purchase requisition for manager approval.

During the week the team clarified the problem context, defined the target users, established scope and constraints, documented user stories and acceptance criteria, designed the initial architecture and context diagram, and agreed the AI boundaries that guide implementation.

## **Tasks**

| Task | Description | Status | Assignee |
| :---- | :---- | :---- | :---- |
| Project charter | Documented the problem statement, target users, AI value, scope, assumptions, constraints, success criteria, risks and team ownership for the eight-week project. | Done | Lukaanya George |
| User stories and acceptance criteria | Defined the main user goals and wrote acceptance criteria covering reorder review, quotation parsing, supplier eligibility, price comparison, policy retrieval, justification drafting, requisition compilation, approval routing, audit logging and safety-boundary enforcement. | Done | Nannyombi Shakiran |
| AI boundary matrix | Separated AI-supported activities from deterministic and human-controlled responsibilities, keeping calculations, eligibility checks, approvals, purchase orders, payments and supplier contact outside the AI layer. | Done | Beingana Jim Junior |
| Initial architecture and context diagram | Created the initial system context showing the procurement officer, procurement manager, data store, Gemini API and the agent within the project boundary. | Done | Ainamani Jim Isaac |
| Acceptance-criteria and boundary review | Reviewed acceptance criteria against the stated AI boundaries and safety constraints. | Done | Sekyeza Elroy Nunda |
| GitHub and ClickUp setup | Created the shared GitHub repository and set up ClickUp for task tracking and coordination. | Done | Lukaanya George |
| Week 1 progress report | Compiled the weekly progress report summarising completed deliverables, responsibilities, challenges, mitigation actions and the baseline for the following week. | Done | Lukaanya George |

## **Upcoming tasks**

- Choose an accessible model and document its capability, cost, latency, privacy and access considerations.  
- Integrate the model into the application.  
- Create Prompt Specification v1.0 covering role, task, context, constraints, output format and failure behaviour.  
- Create at least ten test cases and record expected against actual behaviour.  
- Version at least two meaningful prompt iterations.

## **Challenges Faced and Mitigation**

Week 1 artefacts were written in parallel. The mitigation in use is a single glossary (Charter section 13 and the Requirements glossary) and a consistency check before each weekly freeze, so later weeks implement one schema and one set of AI boundaries.

## **Summary of Progress**

Week 1 produced the project charter, requirements document, AI boundary matrix, initial architecture and context diagram, repository scaffold, ClickUp board and this progress report. All planned deliverables were completed within the week. The documents share one user model, one Normalised Quotation schema and one boundary matrix, which is the baseline Week 2 implementation uses.

