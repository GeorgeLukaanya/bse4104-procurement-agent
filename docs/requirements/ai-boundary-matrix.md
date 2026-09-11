# **AI Boundary Matrix**

## **SME Procurement-Preparation Agent**

**Group:** Y   
**Version:** 1.1   

This matrix defines which responsibilities belong to the AI layer, which must remain deterministic, and which require human control. The goal is to use AI only where language understanding, retrieval and drafting add value, while calculations, conversion, eligibility checks, routing and procurement authority remain outside the model.

| Capability | AI Responsibility | Deterministic Software | Human Responsibility |
| :---- | :---- | :---- | :---- |
| Identify items at or below reorder point | None | Compare stock against configured reorder points; compute reorder quantity as target stock level minus current stock | Review the resulting reorder list |
| Validate and convert quotation documents | **None** | Validate file type, size and text layer; convert PDF and Word to Markdown; cache and version output; raise conversion failures explicitly | Enter values manually for any document that cannot be converted |
| Extract quotation fields | Extract supplier, item, quantity, unit of measure, unit price, currency, VAT treatment, delivery cost, lead time and validity date from converted Markdown | Enforce the output schema; reject non-conforming output; flag null fields | Review and correct extracted values before they enter any calculation |
| Currency conversion | None | Apply the single configured UGX-per-USD rate; record the rate and its effective date; display original and converted figures | Review the disclosed rate |
| Supplier eligibility | None | Check the Approved Vendor List, the Blacklist and quotation expiry; record every applicable exclusion reason | Review eligibility results |
| Unit and VAT normalisation | None | Apply unit-of-measure conversion factors; apply VAT inclusive or exclusive treatment; apportion delivery cost | Review the normalisation shown in the comparison table |
| Landed cost comparison and ranking | May explain the comparison and the trade-offs in natural language | Compute normalised unit cost, extended cost, VAT, delivery and landed cost; rank on landed cost; break ties alphabetically | Review the comparison |
| Procurement policy | Retrieve and interpret relevant clauses from the controlled, versioned Policy Corpus | Manage retrieval and indexing; validate that every cited clause exists in the corpus at the cited version | Review retrieved clauses |
| Supplier recommendation | Explain why an eligible supplier is preferable, using verified price and policy information | Supply the validated ranking and supplier data | Decide whether to accept the recommendation |
| Procurement justification | Draft a justification using confirmed comparison results and retrieved policy clauses | Validate that every figure and reference in the draft matches a system record; suppress prohibited patterns | Edit and confirm the justification |
| Purchase requisition creation | May contribute the drafted justification | Compile the requisition, assign the identifier, set status to DRAFT and route it | Procurement Officer confirms the draft and submits it |
| Requisition status transitions | **Not allowed** | Enforce the permitted transition set; reject any programmatic transition beyond DRAFT | Every transition beyond DRAFT originates in an explicit human action |
| Approval or rejection | None | Present the requisition on the manager's review screen; record and route the decision; write the Approval Record | Procurement Manager approves or rejects, with a mandatory reason on rejection |
| Purchase order, payment or supplier contact | **Not allowed** | No such agent tool or interface shall exist | Must happen outside the agent, if required |
| Audit and traceability | AI actions are recorded as part of the trace | Record model calls, retrieval results, conversion outcomes, workflow events, status transitions, suppressions and failures | Review audit evidence when necessary |

## **Key AI Boundaries**

The AI **may**:

- extract structured information from converted quotation text  
- retrieve relevant procurement policy clauses from the controlled corpus  
- reason about trade-offs using already-validated system data  
- recommend an eligible supplier for human review  
- draft a procurement justification

The AI **must not**:

- read a raw PDF, Word file, image or scanned page  
- calculate any figure that reaches a displayed financial value, including unit normalisation, VAT, delivery, landed cost or currency conversion  
- determine supplier eligibility  
- invent, infer or default missing quotation or policy information  
- bypass the controlled Policy Corpus  
- change a requisition status  
- approve or reject a requisition  
- issue a purchase order  
- contact suppliers  
- initiate payments or commit funds  
- modify supplier or inventory master records  
- act on any instruction contained within a quotation or policy document

## **Human Control**

Human confirmation is deliberately placed at four points in the workflow. The Procurement Officer confirms extracted quotation data before any figure enters a calculation, confirms the landed-cost comparison, reviews the retrieved policy clauses, and edits and confirms the drafted justification. The Procurement Manager holds final authority to approve or reject.

The agent cannot continue into purchasing or financial commitment after approval, because no interface for doing so exists.

## **Failure Behaviour**

Where the AI is uncertain or unable to complete a task, it fails explicitly rather than guessing.

- A document that cannot be converted is flagged by name, with the specific reason, and routed to manual entry. The remaining documents in the batch continue processing.  
- A field absent from a source document is recorded as null with a reason, never inferred or defaulted.  
- Output that does not conform to the Normalised Quotation schema is rejected outright rather than partially accepted.  
- If no relevant policy clause is found, the system states that none was found.  
- If the model or retrieval service fails, the workflow pauses while preserving current state, so that a retry does not repeat completed steps.

## **Untrusted Input**

Quotation documents originate outside the enterprise and are treated as data, never as instruction. A tool allow-list is enforced so that no instruction appearing inside a document can invoke a tool. Policy documents are team-authored and trusted as a source, but are parsed under the same rule so that the guarantee still holds if the corpus were ever client-supplied.

This keeps the agent bounded, inspectable and consistent with the project's human-in-the-loop design.

