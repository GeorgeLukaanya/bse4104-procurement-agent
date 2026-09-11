# Group Y Progress Report: Week 1

**Course:** BSE4104 Emerging Trends in Software Engineering   
**Group:** Y   
**Week ending:** 4th September 2026   
**Version:** 1.1   
**Revised:** Week 2 (11th September 2026\)

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

> **Correction (v1.1):** The v1.0 table assigned the architecture diagram to Sekyeza Elroy Nunda and this progress report to Ainamani Jim, which contradicted the role definitions in Charter section 12\. Both documents now follow the charter roles, and a separate row has been added for the acceptance-criteria review carried out by the Quality and Security Lead. **This table must be confirmed against what each member actually delivered before submission.**

## **Upcoming tasks**

- Reconcile the Week 1 documents following the cross-document consistency audit and re-baseline the charter and requirements at v1.1.  
- Choose an accessible model and document its capability, cost, latency, privacy and access considerations.  
- Integrate the model into the application.  
- Create Prompt Specification v1.0 covering role, task, context, constraints, output format and failure behaviour.  
- Create at least ten test cases and record expected against actual behaviour.  
- Version at least two meaningful prompt iterations.

## **Challenges Faced and Mitigation**

**Parallel authorship produced divergent assumptions across documents.** The charter, requirements document, architecture narrative and boundary matrix were written concurrently by different members, which allowed the team to complete all Week 1 deliverables inside the week but also allowed the four documents to drift apart. A consistency audit at the start of Week 2 found six direct contradictions between documents, six defects against the team's own stated design, and five charter commitments with no requirement behind them.

The most consequential were that the requirements document ranked suppliers on unit price multiplied by quantity, which ignores the differing units, VAT treatment and delivery terms that the charter identifies as the core problem the project exists to solve; that the requirements document assigned document parsing to the AI layer, contradicting the AI boundary matrix; and that the charter described the approving manager as not using the system while the requirements document required the system to present requisitions to that manager and record their decisions.

**Mitigation.** All findings were documented in a written audit with a recommended resolution for each, the six genuine design decisions were settled as a group rather than resolved silently by whoever edited last, and the charter and requirements document were re-baselined at v1.1 with revision notes stating what changed and why. A traceability table mapping each success criterion to the requirements that cover it was added, which surfaced that success criterion S3 on document conversion had a numeric target but no acceptance criteria behind it, and that extraction accuracy had no success criterion at all. A cross-document consistency check is now a standing item at every re-baseline.

**Cost of the delay.** Reconciliation consumed the first part of Week 2\. This was accepted deliberately, on the basis that the Week 2 prompt specification and evaluation cases are written directly against the extraction schema in the requirements glossary, so carrying the defects forward would have embedded them in the code and the evaluation harness rather than in a document that is cheap to change.

## **Summary of Progress**

Week 1 produced the project charter, requirements document, AI boundary matrix, initial architecture and context diagram, repository scaffold, ClickUp board and this progress report. All planned deliverables were completed within the week.

The team's principal learning from Week 1 was that completing every artefact is not the same as producing a coherent specification. Reviewing the artefacts against one another exposed defects that reviewing each in isolation did not, and those defects sat in exactly the places where the documents were meant to agree with each other. Following the v1.1 reconciliation, the documents now provide a consistent baseline for Week 2 implementation.

