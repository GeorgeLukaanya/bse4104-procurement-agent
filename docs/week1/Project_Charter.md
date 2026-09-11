# **Project Charter**

## **SME Procurement-Preparation Agent**

**Course:** BSE4104 Emerging Trends in Software Engineering   
**Group:** Y   
**Members:** Sekyeza Elroy Nunda, Lukaanya George, Ainamani Jim Isaac, Beingana Jim Junior, Nannyombi Shakiran   
**Version:** 1.1   
**Baselined:** Week 1, revised Week 2 (11th September 2026\)   
**Repository:** [https://github.com/GeorgeLukaanya/bse4104-procurement-agent.git](https://github.com/GeorgeLukaanya/bse4104-procurement-agent.git)

## **1\. Proposal Statement**

Our system helps a procurement officer in a small or medium Ugandan trading business complete a weekly reorder review that ends in a policy-compliant purchase requisition ready for manager approval.

AI is used to extract structured quotation data from converted documents, retrieve applicable procurement policies, reason about trade-offs between comparable offers, and draft the written justification. Deterministic software is responsible for converting source documents to Markdown, performing reorder-point arithmetic, computing normalised unit cost and landed cost, applying the configured exchange rate, performing supplier eligibility checks, classifying by budget threshold, numbering requisitions, and routing approvals.

The agent may use a document-conversion tool, an inventory-status tool, a quotation-retrieval tool, a supplier-record tool, a deterministic comparison calculator and a requisition-draft tool, but may not issue purchase orders, contact suppliers, commit funds, award business to a supplier, alter master records, or mark any requisition as approved.

We will build and evaluate the system using a team-created synthetic dataset of inventory records, supplier quotations, and supplier profiles, together with a small corpus of team-authored procurement policy documents.

## **2\. Problem and Context**

Small and medium enterprises in Uganda run procurement on a spreadsheet and a phone. A procurement officer notices when stock runs low, requests quotations from known suppliers, compares them, and prepares a requisition for the proprietor to approve. Every step is manual.

Reorder detection is reactive. Stock levels sit in an irregularly updated spreadsheet, so shortages are usually noticed by a salesperson at the counter rather than in advance, producing stockouts on fast movers and overstocking on slow ones.

Quotations arrive in inconsistent form: a PDF from one supplier, a typed price list from another, a Word document from a third. Units differ (per piece, per carton, per kilogram), some prices include VAT and some do not, and delivery terms, lead times and warranty conditions appear in prose or not at all.

Comparison is therefore slow and error-prone. Normalising three quotations for six items onto a common basis is arithmetic done by hand under time pressure, and the resulting comparison is rarely written down.

Policy compliance is inconsistent. Rules such as obtaining at least three quotations above a stated value, or sourcing only from suppliers on the approved register, exist but are applied from memory.

The justification is the weakest artefact of all. The approver receives a supplier name and a total, with little record of why that option was preferred, which makes review superficial and later audit difficult.

## **3\. Target Users**

**Primary user: Procurement Officer.** Responsible for stock availability and requisition preparation. Comfortable with spreadsheets, not a technical specialist. Handles roughly five to fifteen reorder decisions per week across dozens of SKUs, and is time-constrained. The officer initiates every run of the system.

**Secondary user: Procurement Manager.** Holds financial authority. Reviews the compiled requisition and records an approval or rejection decision through a dedicated review screen in the system. The manager does not operate the agent loop, does not upload documents and does not initiate reviews, but is a system user, because the approval decision must be captured as an immutable audit record rather than reported second-hand.

> **Revision note (v1.1):** In v1.0 the manager was described as not using the system at all. That was incompatible with the approval and audit requirements, which depend on the system capturing the decision directly. The manager is now a secondary user with a read-and-decide interface only.

## **4\. Where AI Adds Value, and Where It Must Not Decide**

AI is justified here for three specific reasons.

**Unstructured input.** Quotations are natural-language documents with no shared schema. Extracting a comparable structure (item, quantity, unit of measure, unit price, VAT treatment, delivery cost, lead time, validity period) resists conventional parsing and suits a language model well.

**Policy grounding.** Which rules apply depends on requisition value, item category and supplier status. Retrieving the relevant clauses and applying them to a concrete case is a retrieval and reasoning task.

**Written justification.** The comparison summary that makes review meaningful is a generation task with a clear evaluation criterion: every factual claim must trace to a computed figure or a retrieved clause.

What AI must not do matters equally.

- No arithmetic affecting a financial figure is performed by the model. Reorder quantities, normalised unit costs, extended totals, VAT, delivery costs, landed cost and currency conversion are computed in code and passed to the model as facts.  
- No supplier is awarded business. The agent ranks options and states trade-offs, but the recommendation is advisory, and the requisition is created in DRAFT status only.  
- No financial commitment of any kind is made. This boundary is not a limitation we tolerate; it is the design.

## **5\. Document Conversion Layer**

Supplier quotations arrive as PDF and Word files, and passing these directly to a foundation model is both unreliable and expensive. Native PDF and image handling consumes substantially more tokens than plain text, which matters under the free-tier quota we expect to work within, and multimodal extraction failures tend to surface as plausible but wrong values rather than as errors.

The system therefore converts every source document to Markdown deterministically before any model call. Conversion is library work, not model work: PDF text-layer extraction and Word document parsing, producing Markdown that preserves table structure and heading hierarchy. The model then reads clean text.

Three consequences follow, and all three are deliberate.

- A document that cannot be converted fails loudly at a known point in the pipeline and is handed to the officer for manual entry. It does not become a guessed figure inside a requisition.  
- Converted Markdown is cached and versioned, so the same input produces the same model input on every evaluation run. This makes the Week 7 evaluation reproducible.  
- Token cost per quotation drops sharply, which is what allows a thirty-scenario evaluation set to run repeatedly within free-tier limits.

Scanned documents, photographs and CSV price lists are out of scope for the quotation path. Conversion is limited to PDF and Word files carrying a machine-readable text layer. A scanned quotation is routed to manual entry rather than to OCR.

> **Revision note (v1.1):** The Requirements Document v1.0 admitted CSV quotations. CSV is structured data requiring no model extraction, and admitting it would have removed the justification for the AI layer on this path. CSV and spreadsheet formats remain valid for the Inventory Snapshot only.

## **6\. Primary End-to-End Workflow**

One workflow is in scope, extended progressively through Weeks 2 to 7\.

1. **Trigger.** The officer starts a reorder review for a category or date and supplies an Inventory Snapshot.  
2. **Deterministic scan.** Code identifies SKUs at or below their reorder point, with current stock, target stock level, consumption rate and cover days, and computes the reorder quantity for each.  
3. **Candidate framing.** The agent reviews flagged items, retrieves policy rules for the estimated value band, and determines what is required (minimum quotation count, approved-supplier constraint).  
4. **Conversion.** Source quotation documents are converted to Markdown deterministically, with failures raised explicitly and routed to manual entry.  
5. **Extraction.** The agent extracts a normalised structure from each converted quotation.  
6. **Deterministic comparison.** A calculator applies the configured exchange rate where needed, then computes normalised unit cost, extended totals, VAT and landed cost per option. The model receives results, not raw arithmetic.  
7. **Reasoning and drafting.** The agent produces a comparison summary, a ranked recommendation with stated trade-offs, and a policy-compliance note.  
8. **Validation.** Guardrails confirm that every quoted figure matches a computed value, that cited policy clauses exist in the corpus, and that supplier eligibility passed.  
9. **Human approval gate.** The requisition is compiled and routed to the manager. It cannot progress without an explicit human action outside the agent's control.  
10. **Logging.** The full trace (converted inputs, retrieved documents, tool calls, decisions, iteration count, stop reason) is persisted as evidence.

Steps 3 to 8 form the bounded agent loop delivered in Week 5, with a maximum iteration limit and explicit stop conditions.

### Requisition status model

The requisition moves through an enumerated set of states, and no transition beyond DRAFT occurs without a human action.

DRAFT → PENDING\_ROUTING → PENDING\_APPROVAL → APPROVED or REJECTED

The agent may create and modify a requisition only in DRAFT. Transition to PENDING\_ROUTING requires the officer's explicit confirmation. Transition to APPROVED or REJECTED requires the manager's explicit decision. Success criterion S7 is evaluated against this list.

## **7\. Scope**

### In scope

The single reorder-to-requisition workflow above. A deterministic conversion layer for text-layer PDF and Word documents, with caching and versioning of converted output. A versioned corpus of ten to fifty documents covering procurement policy, supplier terms and process notes. Synthetic datasets of roughly forty to sixty SKUs (each with a reorder point and a target stock level), six to ten suppliers, and thirty to fifty quotations, with a subset rendered as unstructured documents to exercise extraction. Two to four tools with explicit schemas, permissions and failure behaviour. One persistent-memory use case covering prior requisition outcomes and supplier performance notes as advisory context. Two seeded user roles with simple authentication, sufficient to attribute audit entries to an identity. A thirty-scenario evaluation set spanning normal, edge, incorrect-information, adversarial, tool-failure and unauthorised-action cases.

### Out of scope

Any real supplier, money, inventory or live ERP integration. Supplier award, negotiation, payment, goods receipt or invoice matching. OCR, scanned documents, photographs and handwriting. CSV or spreadsheet quotations. Multi-currency handling beyond a single configured UGX and USD rate. Demand forecasting or reorder-point optimisation. External notification channels such as email or SMS; all notification is in-application. Multi-tenant support, self-service user management, role administration and production deployment beyond a reproducible tagged release. Mobile applications.

## **8\. Assumptions**

- All data is synthetic and team-created, so no data-authorisation dependency exists.  
- Reorder points and target stock levels are configured per SKU and treated as given.  
- Reorder quantity is the target stock level minus current stock.  
- Quotations are already in the system's possession; solicitation is out of scope.  
- A single approver role is modelled, without delegation or multi-level chains.  
- Prices are in UGX. A single configured UGX-per-USD rate is applied deterministically to any USD quotation, and both the original figure and the applied rate are disclosed in the comparison table and the requisition.  
- Source quotation documents carry a machine-readable text layer.  
- A Gemini free tier will support the anticipated evaluation volume, given the conversion layer's token reduction. The binding constraint is request throughput rather than token cost.  
- The reference organisation is a fictional Kampala hardware and building-supplies distributor of roughly twenty-five staff, two locations and four hundred SKUs, of which forty to sixty are modelled.

## **9\. Constraints**

Eight weeks, with the system frozen for hardening in Week 8\. Model spend is confined to a free or minimal tier, which constrains context size, evaluation-run frequency and rate of iteration. Public, synthetic or team-created data only, which is a hard rule rather than a preference, because free-tier submissions may be used by the model provider to improve its products.

Five members with mixed prior exposure to LLM APIs, retrieval and evaluation tooling, so some capability must be built during the project. Every member must own identifiable weekly tasks and be able to explain the whole system, which limits how narrowly work can be divided.

## **10\. Success Criteria**

| ID | Criterion | Target |
| :---- | :---- | :---- |
| S1 | Reorder detection correctness (deterministic), evaluated at and around the reorder point | 100 percent, no missed or spurious flags |
| S2 | Financial arithmetic errors in output | Zero |
| S3 | Document conversion success on text-layer sources | 95 percent or above, failures raised explicitly |
| S4 | End-to-end task completion on normal scenarios | 80 percent or above |
| S5 | Groundedness, every policy claim traceable to a retrieved clause | 90 percent or above |
| S6 | Correct refusal or hand-off on out-of-boundary requests | 100 percent |
| S7 | Requisitions reaching any state beyond DRAFT without human action | Zero |
| S8 | Prohibited actions attempted or executed under adversarial prompts | Zero |
| S9 | Quotation extraction field accuracy against the synthetic quotation set, scored per field | 90 percent or above overall, 100 percent on unit price and unit of measure |

S2, S7 and S8 are hard gates. Any failure is a defect, not a score.

> **Revision note (v1.1):** S9 was added. Extraction is the core AI capability and the Week 2 baseline, and v1.0 had no measurable target for it. A model that reliably misreads unit prices would have passed every v1.0 criterion.

## **11\. Key Risks**

| Risk | Impact | Response |
| :---- | :---- | :---- |
| Model fabricates or miscomputes a financial figure | High, invalidates the core artefact | All figures computed deterministically and validated against model output before display |
| Conversion silently mangles a quotation table | High, corrupts extraction downstream | Converted Markdown retained and diffable, extraction confidence flagged, officer confirms before a figure enters a requisition |
| Extraction misreads unit of measure or VAT treatment | High, produces a wrong ranking that looks correct | S9 scored per field, officer review step before comparison, normalisation shown explicitly in the comparison table |
| Free-tier request quota exhausted mid-evaluation | Medium, stalls Week 7 | Conversion layer reduces per-call tokens, converted output cached, evaluation runs batched and scheduled, separate development and evaluation projects |
| Prompt injection through quotation text | High | Quotation content treated as untrusted data, tool allow-list enforced, injection scenarios in the Week 7 evaluation set |
| Synthetic corpus too uniform to expose real failures | Medium | Contradictions, gaps, mixed units, mixed VAT treatment and expired quotations seeded deliberately during Week 3 |
| Scope creep toward a general procurement platform | High, threatens completion | The out-of-scope list is binding, and changes require a documented charter revision |
| Documents drifting apart under parallel authorship | Medium, produces unimplementable requirements | Cross-document consistency check at each re-baseline, as performed for v1.1 |

## **12\. Team and Ownership**

| Role | Member | Week 1 ownership |
| :---- | :---- | :---- |
| Project and Requirements Lead | Nannyombi Shakiran | Charter, user stories and acceptance criteria |
| Application and Integration Lead | Ainamani Jim Isaac | Architecture and context diagram, repository scaffold |
| AI Engineering Lead | Beingana Jim Junior | AI Boundary Matrix, model access setup |
| Quality and Security Lead | Sekyeza Elroy Nunda | Acceptance-criteria review, boundary definitions |
| DevOps and Documentation Lead | Lukaanya George | ClickUp board, repository structure, weekly progress report |

Roles rotate across the project. Every member is accountable for explaining any part of the system.

> **Action required:** This table and the Week 1 Progress Report task table disagreed in v1.0 on two rows, the architecture diagram and the weekly progress report. Both documents have been aligned to the role definitions above. Confirm this reflects who actually did the work before submission.

## **13\. Terminology**

To keep the documents consistent, the following terms are used throughout and are defined once in the Requirements Document glossary.

| Term used | Terms replaced |
| :---- | :---- |
| Reorder Point | reorder threshold |
| Procurement Manager | approving manager |
| Landed Cost | total cost |
| DRAFT, PENDING\_ROUTING, PENDING\_APPROVAL, APPROVED, REJECTED | draft, pending review state, pending routing state, DRAFT\_PENDING\_APPROVAL |

## **Approval**

Baselined at v1.0 for Week 1 submission. Re-baselined at v1.1 following a cross-document consistency audit conducted at the start of Week 2, which reconciled contradictions between the charter and the requirements document. Material changes to scope, boundaries or success criteria will continue to be recorded as versioned revisions with a stated rationale.  
