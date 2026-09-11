# **Requirements Document**

## **SME Procurement-Preparation Agent**

**Course:** BSE4104 Emerging Trends in Software Engineering 

**Group:** Y 

**Version:** 1.1 

## **Introduction**

The SME Procurement-Preparation Agent is a bounded agentic system that assists a Procurement Officer in a small or medium Ugandan enterprise to convert a weekly reorder review into a policy-compliant purchase requisition ready for human approval.

The system combines an AI layer (quotation field extraction, policy retrieval, justification drafting) with a deterministic layer (document conversion, stock level arithmetic, currency conversion, vendor eligibility checks, landed-cost comparison, approval routing). The system never issues a purchase order, contacts a supplier, commits funds, or approves anything autonomously.

## **Glossary**

**Procurement Officer.** The primary user who initiates the reorder review, uploads documents, reviews and confirms system output, and submits the requisition for approval.

**Procurement Manager.** The secondary user who reviews a routed Purchase Requisition through a dedicated review screen and records an approval or rejection decision. The Procurement Manager does not upload documents, initiate reviews or operate the agent loop.

**System.** The bounded agentic system comprising both the AI components and the deterministic components described in this document.

**AI Layer.** The AI-powered components responsible for extracting fields from converted quotation text, retrieving policy clauses, and drafting justifications.

**Deterministic Layer.** The rule-based, arithmetic and routing components that perform document conversion, all calculations, currency conversion, eligibility checks and workflow routing.

**Inventory Snapshot.** A structured file (.csv, .xlsx or .ods) uploaded by the Procurement Officer that lists, for each item, the item name, current stock, Reorder Point and Target Stock Level.

**Reorder Point.** The stock quantity at or below which an item must be reordered, as defined in the Inventory Snapshot.

**Target Stock Level.** The stock quantity an item should be restored to when reordered. Must be greater than the Reorder Point.

**Reorder Quantity.** Target Stock Level minus current stock, computed by the Deterministic Layer.

**Supplier Quotation.** An unstructured document (PDF or Word) from a supplier containing item descriptions, units, prices, quantities, VAT treatment, delivery terms, lead times, validity dates and supplier identity.

**Converted Quotation Document.** The Markdown representation of a Supplier Quotation produced deterministically by the Deterministic Layer, cached and versioned so that the same source file always yields the same model input.

**Normalised Quotation.** A structured record produced by the AI Layer from a Converted Quotation Document, containing: supplier name, item name, quantity offered, unit of measure, unit price, currency, VAT treatment (inclusive or exclusive), VAT rate where stated, delivery or freight cost, lead time in days, and validity date. Any field absent from the source is recorded as null with a reason, never inferred.

**Unit of Measure.** The basis on which a supplier quotes a price, for example per piece, per carton or per kilogram, together with the conversion factor to the enterprise's stocking unit.

**Configured Exchange Rate.** A single UGX-per-USD rate held in system configuration, with an effective date, applied deterministically to any USD-denominated quotation.

**Normalised Unit Cost.** The VAT-exclusive price per stocking unit in UGX, computed by the Deterministic Layer after applying the unit-of-measure conversion factor and, where required, the Configured Exchange Rate.

**Landed Cost.** The total UGX cost of satisfying a reorder item from one supplier, computed by the Deterministic Layer as (Normalised Unit Cost multiplied by Reorder Quantity) plus applicable VAT plus apportioned delivery or freight cost. Landed Cost is the basis for supplier ranking.

**Approved Vendor List (AVL).** The list of suppliers approved to receive orders, held as seeded reference data inside the system boundary and read-only to the agent.

**Blacklist.** The list of suppliers barred from receiving orders, held as seeded reference data inside the system boundary and read-only to the agent.

**Eligibility Check.** The deterministic process verifying that a supplier is on the AVL, is absent from the Blacklist, and that the quotation validity date has not passed.

**Policy Corpus.** The controlled, versioned collection of enterprise procurement policy documents used exclusively by the AI Layer for retrieval-augmented generation. Each document carries a name, a version and clause identifiers.

**Purchase Requisition.** The output document produced by the System, comprising item details, eligible supplier list, landed-cost comparison table per item, recommended supplier, retrieved policy clauses and confirmed justification.

**Requisition Status.** One of DRAFT, PENDING\_ROUTING, PENDING\_APPROVAL, APPROVED, REJECTED. Permitted transitions are DRAFT to PENDING\_ROUTING to PENDING\_APPROVAL to either APPROVED or REJECTED. No transition beyond DRAFT occurs without an explicit human action.

**Approval Record.** The immutable log entry created when a Procurement Manager approves or rejects a Purchase Requisition, capturing the decision, rationale where applicable, timestamp and manager identity.

**Notification.** An in-application state change surfaced on a user's pending queue. No external channel (email, SMS) is in scope.

## 

## **Requirements**

### **1\. Weekly Reorder Review Initiation**

**User Story:** As a Procurement Officer, I want to upload an Inventory Snapshot to initiate the weekly reorder review, so that the System can identify which items need to be reordered without manual calculation.

**Acceptance Criteria**

1. WHEN the Procurement Officer uploads an Inventory Snapshot in .csv, .xlsx or .ods format, THE System SHALL accept the file, confirm receipt, and begin the reorder review within 5 seconds.  
2. IF the uploaded file is missing any required column (item name, current stock, reorder point, target stock level), or contains non-numeric values in any numeric column, THEN THE System SHALL reject the file and return a validation error naming each missing or invalid column and its expected data type.  
3. IF a row contains a negative value in any numeric column, or a Target Stock Level less than or equal to its Reorder Point, THEN THE System SHALL treat that row as invalid, exclude it from the reorder list, and include it in the validation error report.  
4. WHEN the reorder review is initiated with a valid file, THE Deterministic Layer SHALL flag every item whose current stock is **at or below** its Reorder Point, and SHALL produce a reorder list containing, for each flagged item: item name, current stock, reorder point, target stock level and computed Reorder Quantity.  
5. IF no item is at or below its Reorder Point, THEN THE System SHALL state that no items require reorder and terminate the review session without proceeding to quotation upload.

### **2\. Supplier Quotation Conversion**

**User Story:** As a Procurement Officer, I want uploaded quotation documents converted to clean text before any model reads them, so that extraction is reproducible and a document that cannot be read fails visibly rather than producing a guessed figure.

**Acceptance Criteria**

1. WHEN the Procurement Officer uploads between 1 and 10 Supplier Quotation files in PDF or Word format, each no larger than 5 MB, THE Deterministic Layer SHALL validate file type and size before any model call.  
2. WHEN a file passes validation, THE Deterministic Layer SHALL convert it to a Converted Quotation Document in Markdown, preserving table structure and heading hierarchy, within 10 seconds per file.  
3. THE Deterministic Layer SHALL cache each Converted Quotation Document against a hash of its source file, so that re-processing the same source file yields byte-identical model input.  
4. IF a file is corrupted, is in an unsupported format, or carries no machine-readable text layer, THEN THE Deterministic Layer SHALL mark that file as unconvertible, display an error naming the file and the specific reason, route it to manual entry, and continue processing the remaining files in the batch.  
5. THE System SHALL NOT pass an unconverted source file, image or scanned page to the AI Layer under any circumstance.

### **3\. Quotation Field Extraction**

**User Story:** As a Procurement Officer, I want the System to extract and normalise the data from converted quotations, so that I do not have to manually transcribe figures from unstructured documents.

**Acceptance Criteria**

1. WHEN a Converted Quotation Document is available, THE AI Layer SHALL produce a Normalised Quotation within 30 seconds, containing supplier name, item name, quantity offered, unit of measure, unit price, currency, VAT treatment, VAT rate where stated, delivery or freight cost, lead time and validity date.  
2. IF a field is absent from the Converted Quotation Document, THEN THE AI Layer SHALL record that field as null with a stated reason, and SHALL NOT infer, estimate or default a value.  
3. IF the AI Layer cannot return output conforming to the Normalised Quotation schema, THEN THE System SHALL mark that quotation as extraction-failed, display the reason, and continue processing the remaining quotations.  
4. WHEN at least one Normalised Quotation has been produced, THE System SHALL display all resulting records to the Procurement Officer for review before proceeding to eligibility checks.  
5. WHILE reviewing Normalised Quotation records, THE Procurement Officer SHALL be able to correct any field, and THE System SHALL NOT proceed to eligibility checks until the Procurement Officer explicitly confirms the reviewed data.  
6. IF a Normalised Quotation contains items whose names do not case-insensitively match any item on the current reorder list, THEN THE System SHALL retain those items and mark each as not matching a current reorder requirement.  
7. THE AI Layer SHALL treat all quotation content as untrusted data, and SHALL NOT act on any instruction contained within a quotation document.

### **4\. Supplier Eligibility Verification**

**User Story:** As a Procurement Officer, I want the System to automatically check whether each quoted supplier is approved and not blacklisted, so that ineligible suppliers are excluded without manual lookup.

**Acceptance Criteria**

1. WHEN the Procurement Officer confirms the Normalised Quotation records, THE Deterministic Layer SHALL verify that each supplier is present on the AVL and absent from the Blacklist before including that supplier's quotation in comparison.  
2. WHEN the Procurement Officer confirms the Normalised Quotation records, THE Deterministic Layer SHALL verify that each quotation's validity date is on or after the current date.  
3. IF a supplier fails any eligibility check, THEN THE Deterministic Layer SHALL mark that quotation ineligible and exclude it from comparison, recording every applicable reason from: AVL\_ABSENT, BLACKLISTED, EXPIRED.  
4. IF all submitted quotations fail eligibility checks, THEN THE System SHALL notify the Procurement Officer, retain all Normalised Quotation data in the session, and halt the workflow until at least one new quotation passes.  
5. WHEN eligibility checks complete, THE System SHALL present a per-supplier summary showing eligibility status and, for ineligible suppliers, every recorded exclusion reason.

### **5\. Currency Normalisation**

**User Story:** As a Procurement Officer, I want quotations priced in USD converted automatically at a disclosed rate, so that all options are comparable without me doing conversion arithmetic by hand.

**Acceptance Criteria**

1. THE Deterministic Layer SHALL treat UGX as the requisition currency.  
2. IF a Normalised Quotation is denominated in USD, THEN THE Deterministic Layer SHALL convert it to UGX using the Configured Exchange Rate, and SHALL record the original figure, the original currency, the rate applied and the rate's effective date against that quotation.  
3. THE System SHALL display both the original-currency figure and the converted UGX figure wherever a converted quotation appears in the comparison table or the Purchase Requisition.  
4. IF a Normalised Quotation is denominated in a currency other than UGX or USD, THEN THE System SHALL mark it out of scope, exclude it from comparison, and state the reason.  
5. THE Procurement Officer SHALL NOT be required or permitted to enter a converted figure manually.

### **6\. Landed Cost Comparison and Supplier Ranking**

**User Story:** As a Procurement Officer, I want eligible suppliers compared on a common basis that accounts for units, VAT and delivery, so that the genuinely cheapest compliant option is identified rather than the one with the lowest headline price.

**Acceptance Criteria**

1. WHEN eligible Normalised Quotations exist for a reorder item, THE Deterministic Layer SHALL compute, for each: Normalised Unit Cost (applying the unit-of-measure conversion factor and, where required, the Configured Exchange Rate), extended cost for the Reorder Quantity, applicable VAT, apportioned delivery or freight cost, and Landed Cost.  
2. WHEN at least two eligible quotations cover the same reorder item, THE Deterministic Layer SHALL rank them in ascending order of Landed Cost. WHERE two suppliers have equal Landed Cost, THE Deterministic Layer SHALL rank them in ascending alphabetical order by supplier name.  
3. IF a quotation lacks a field required to compute Landed Cost (unit of measure, VAT treatment, or delivery cost), THEN THE Deterministic Layer SHALL exclude it from automated ranking, present it separately, and state which field is missing.  
4. WHEN only one eligible quotation exists for a reorder item, THE Deterministic Layer SHALL record that supplier as the sole eligible option and note that competitive comparison was not possible.  
5. WHEN comparison completes, THE System SHALL display the ranked table per item, showing for each eligible supplier: supplier name, quoted unit price and unit of measure, normalised unit cost (UGX), reorder quantity, VAT, delivery cost, Landed Cost (UGX) and lead time, before the justification is drafted.  
6. THE AI Layer SHALL NOT perform any arithmetic contributing to a displayed figure in this table.

### **7\. Procurement Policy Retrieval**

**User Story:** As a Procurement Officer, I want the System to retrieve the relevant procurement policy clauses for the items being requisitioned, so that the justification cites correct policy without manual lookup.

**Acceptance Criteria**

1. WHEN the comparison table is confirmed by the Procurement Officer, THE AI Layer SHALL query the Policy Corpus and return clauses relevant to the item names, categories and Landed Cost values in the table, within 30 seconds.  
2. THE AI Layer SHALL retrieve policy clauses exclusively from the Policy Corpus and SHALL NOT use any knowledge source outside it when generating policy citations.  
3. IF no relevant clause is found for an item or category, THEN THE AI Layer SHALL state explicitly that no policy clause was found for that item, rather than omitting it or fabricating a clause.  
4. WHEN clauses are retrieved, THE System SHALL display them to the Procurement Officer identified by document name, document version and clause identifier, before drafting begins.  
5. IF the Policy Corpus is unavailable, THEN THE System SHALL notify the Procurement Officer, halt drafting, and preserve the comparison table so that retrieval can be retried without repeating earlier steps.

### **8\. Justification Drafting**

**User Story:** As a Procurement Officer, I want the System to draft a written justification referencing the comparison and the relevant policy clauses, so that I have a consistent, policy-aligned starting point rather than writing from scratch.

**Acceptance Criteria**

1. WHEN a confirmed comparison table is available, THE AI Layer SHALL draft a justification containing at minimum: the recommended supplier, the Landed Cost basis for the recommendation (lowest Landed Cost or sole eligible supplier), any material trade-off such as a longer lead time, and references to applicable policy clauses by document name, version and clause identifier, or an explicit absence note.  
2. THE AI Layer SHALL state every figure in a form independently verifiable against the comparison table, and SHALL NOT introduce a figure not present in that table.  
3. THE AI Layer SHALL NOT assert that a Purchase Requisition is approved, that a supplier has been awarded a contract, or that funds have been committed.  
4. WHEN the draft is produced, THE Procurement Officer SHALL be able to edit any part of it, and THE System SHALL NOT proceed to compilation until the Procurement Officer explicitly confirms the draft.  
5. IF the AI Layer cannot produce a draft, THEN THE System SHALL notify the Procurement Officer, preserve the comparison table and retrieved clauses, and allow retry without repeating earlier steps.

### **9\. Purchase Requisition Compilation**

**User Story:** As a Procurement Officer, I want the System to compile all components into a single Purchase Requisition, so that I can submit a complete, standardised document to the Procurement Manager.

**Acceptance Criteria**

1. WHEN the Procurement Officer confirms the draft justification, THE System SHALL compile a Purchase Requisition in status DRAFT containing: per reorder item, the item name, current stock, reorder point, target stock level and reorder quantity; the eligible supplier list; the Landed Cost comparison table; the recommended supplier; the retrieved policy clauses; and the confirmed justification.  
2. WHEN a Purchase Requisition is compiled, THE System SHALL assign a unique requisition identifier and record the Procurement Officer's authenticated username and the compilation timestamp.  
3. WHERE the requisition covers multiple reorder items, THE System SHALL produce a separate comparison section per item within the single document.  
4. IF any required component is absent at confirmation, THEN THE System SHALL halt compilation, name the missing component or components, and preserve session state so the Procurement Officer can complete the missing step.  
5. THE System SHALL NOT issue a purchase order, contact any supplier, or commit any funds as part of or after compilation.

### **10\. Approval Routing**

**User Story:** As a Procurement Officer, I want the compiled requisition routed to the Procurement Manager, so that the handoff follows the correct approval chain without manual forwarding.

**Acceptance Criteria**

1. WHEN the Procurement Officer submits a compiled requisition, THE Deterministic Layer SHALL move it to PENDING\_ROUTING, then to PENDING\_APPROVAL, and surface it on the Procurement Manager's pending queue within 10 seconds.  
2. THE Deterministic Layer SHALL route requisitions only to the Procurement Manager role as configured in the approval routing table. IF no Procurement Manager is configured, THEN THE System SHALL halt routing, notify the Procurement Officer of the missing approver configuration, and hold the requisition in PENDING\_ROUTING.  
3. WHEN routing completes, THE System SHALL lock the requisition against modification until a decision is recorded.  
4. WHEN routing completes, THE System SHALL notify the Procurement Officer in-application that the requisition is awaiting review, within 10 seconds.  
5. THE System SHALL NOT send any notification through an external channel.

### **11\. Manager Approval or Rejection**

**User Story:** As a Procurement Manager, I want to review, approve or reject a Purchase Requisition with a recorded rationale, so that all procurement decisions are documented and traceable for audit.

**Acceptance Criteria**

1. WHEN a requisition enters PENDING\_APPROVAL, THE System SHALL present the full requisition to the Procurement Manager through the review screen, including item details, Landed Cost comparison, retrieved policy clauses, recommended supplier and justification.  
2. THE review screen SHALL be read-and-decide only. THE Procurement Manager SHALL NOT be able to edit requisition content, upload documents or initiate a reorder review.  
3. WHEN the Procurement Manager approves, THE System SHALL move the requisition to APPROVED and create an Approval Record capturing the requisition identifier, the manager's authenticated username, the decision and the timestamp.  
4. WHEN the Procurement Manager selects reject, THE System SHALL require a non-empty, non-whitespace rejection reason before accepting the rejection, then move the requisition to REJECTED and create an Approval Record capturing the identifier, username, decision, reason and timestamp.  
5. IF a requisition is approved, THEN THE System SHALL NOT automatically issue a purchase order, contact any supplier or commit any funds. The only automated actions permitted are writing the Approval Record and notifying the Procurement Officer.  
6. WHEN a rejection is recorded, THE System SHALL notify the Procurement Officer of the decision and reason within 30 seconds so that a revised requisition can be initiated.

### **12\. Authentication and Roles**

**User Story:** As a Procurement Manager, I want every action attributed to an identified user, so that the audit trail is meaningful.

**Acceptance Criteria**

1. THE System SHALL provide two seeded roles, Procurement Officer and Procurement Manager, each with credentials configured at deployment.  
2. THE System SHALL require authentication before any workflow action, and SHALL record the authenticated username on every audit entry.  
3. THE System SHALL restrict the reorder review, upload, confirmation and submission actions to the Procurement Officer role, and the approval and rejection actions to the Procurement Manager role.  
4. THE System SHALL NOT provide self-service registration, role administration or multi-tenant separation, which are out of scope.

### **13\. Audit Trail and Record Keeping**

**User Story:** As a Procurement Manager, I want all requisition activity recorded in an immutable audit log, so that the enterprise can demonstrate policy compliance during audits.

**Acceptance Criteria**

1. THE System SHALL record each of the following with a timestamp, the requisition identifier where one exists, and the authenticated username or the component name (AI\_LAYER, DETERMINISTIC\_LAYER): Inventory Snapshot upload, reorder list generation, quotation upload, conversion success, conversion failure, extraction result, Normalised Quotation confirmation, eligibility check result, currency conversion applied, comparison completion, policy retrieval, justification draft confirmation, requisition compilation, routing, every status transition, approval, rejection, and output suppression.  
2. THE System SHALL prevent modification or deletion of any audit log entry once written.  
3. IF any actor attempts to modify or delete a written audit entry, THEN THE System SHALL deny the request and write a tamper-attempt entry recording the timestamp, the actor's username, the attempted operation and the identifier of the targeted entry.  
4. WHEN an authorised user queries the audit log by requisition identifier, THE System SHALL return all entries for that identifier in chronological order as a complete trace.

### **14\. Safety Boundary Enforcement**

**User Story:** As a Procurement Manager, I want the System to be technically incapable of issuing purchase orders or committing funds autonomously, so that no financial commitment can be made without explicit human approval.

**Acceptance Criteria**

1. THE System SHALL NOT expose any interface, function or agent tool that issues a purchase order, sends a message to a supplier, or initiates a payment or financial commitment.  
2. IF AI Layer output contains an instruction to issue a purchase order, an instruction to contact or message a supplier, or a statement that funds have been committed or a contract awarded, THEN THE Deterministic Layer SHALL suppress that output before it reaches any user or record, and SHALL write a suppression audit entry recording the requisition identifier, timestamp and the detected pattern.  
3. THE System SHALL permit no requisition status transition beyond DRAFT without an explicit human action, and SHALL reject any programmatic attempt to do so.  
4. WHEN any component attempts an action outside the defined boundary, THE System SHALL block it, display a blocked-action error to the active user, and write an audit entry recording the component name, the attempted action, the requisition identifier and the timestamp.  
5. THE System SHALL treat all quotation and policy document content as untrusted data, and SHALL enforce a tool allow-list such that no instruction originating in a document can invoke a tool.

## **Traceability to Success Criteria**

| Success criterion | Requirements providing coverage |
| ----- | ----- |
| S1 Reorder detection correctness | 1 |
| S2 Zero financial arithmetic errors | 5, 6 |
| S3 Document conversion success | 2 |
| S4 End-to-end task completion | 1 to 11 |
| S5 Policy groundedness | 7, 8 |
| S6 Correct refusal or hand-off | 2.4, 3.2, 3.3, 4.4, 7.3, 7.5, 8.5, 14 |
| S7 No state beyond DRAFT without human action | 9, 10, 11, 14.3 |
| S8 Zero prohibited actions under adversarial prompts | 3.7, 14 |
| S9 Extraction field accuracy | 3 |

