# AI BOUNDARY MATRIX

This matrix defines which responsibilities belong to the AI layer, which must remain deterministic, and which require human control. The goal is to use AI only where language understanding, retrieval, and drafting add value, while calculations, eligibility checks, routing, and procurement authority remain outside the model.

| Capability                                  | AI Responsibility                                                                                                       | Deterministic Software                                                   | Human Responsibility                                  |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ----------------------------------------------------- |
| Identify items below reorder threshold      | None                                                                                                                    | Compare stock levels against configured reorder thresholds               | Review resulting reorder list                         |
| Parse supplier quotations                   | Extract structured fields from quotation text, such as supplier, item, unit price, quantity, currency and validity date | Validate file type, required fields and output structure                 | Review and correct extracted values before proceeding |
| Supplier eligibility                        | None                                                                                                                    | Check Approved Vendor List, blacklist and quotation expiry               | Review eligibility results                            |
| Price comparison                            | May explain the comparison in natural language                                                                          | Calculate required quantities, total costs and ranking                   | Review the comparison                                 |
| Procurement policy                          | Retrieve and interpret relevant clauses from the controlled Policy Corpus                                               | Manage retrieval/indexing and validate that cited clauses exist          | Review retrieved clauses                              |
| Supplier recommendation                     | Explain why an eligible supplier is preferable using verified price and policy information                              | Provide validated ranking and supplier data                              | Decide whether to accept the recommendation           |
| Procurement justification                   | Draft a justification using confirmed comparison results and retrieved policy clauses                                   | Validate that figures and references used by the AI match system records | Edit and confirm the justification                    |
| Purchase requisition creation               | May contribute the drafted justification                                                                                | Compile requisition, assign identifier and route it                      | Procurement Officer confirms the draft                |
| Approval/rejection                          | None                                                                                                                    | Record and route the approval decision                                   | Procurement Manager approves or rejects               |
| Purchase order, payment or supplier contact | Not allowed                                                                                                             | No such agent tool or interface shall exist                              | Must happen outside the agent, if required            |
| Audit and traceability                      | AI actions may be recorded as part of the trace                                                                         | Record model calls, retrieval results, workflow events and failures      | Review audit evidence when necessary                  |

## Key AI Boundaries

The AI may:

- extract structured information from supplier quotations;
- retrieve relevant procurement-policy clauses
- reason about trade-offs using already validated system data;
- recommend an eligible supplier for human review
- draft a procurement justification.

The AI must not:

- calculate authoritative financial totals
- determine supplier eligibility
- invent missing quotation or policy information;
- bypass the controlled Policy Corpus
- approve or reject a requisition
- issue a purchase order
- contact suppliers
- initiate payments or commit funds
- modify supplier or inventory master records.

## Human Control

Human confirmation is deliberately placed at important stages of the workflow. The Procurement Officer reviews and confirms extracted quotation data, price comparison results, retrieved policy information, and the AI-generated justification. The Procurement Manager retains final authority to approve or reject the requisition. The agent cannot continue into purchasing or financial commitment after approval.

## Failure Behaviour

Where the AI is uncertain or unable to complete a task, it should fail explicitly rather than guess. For example:

- an unparseable quotation is flagged for manual handling
- missing quotation fields are reported rather than invented
- if no relevant policy clause is found, the system reports that none was found
- if the model or retrieval service fails, the workflow pauses while preserving the current state.

This keeps the agent bounded, inspectable, and consistent with the project's human-in-the-loop design.
