# Requirements Document

## Introduction

The SME Procurement Preparation Agent is a bounded agentic system that assists a
Procurement Officer in a small or medium Ugandan enterprise to convert a weekly
reorder review into a policy compliant purchase requisition ready for human
approval.

The system combines an AI layer (quotation parsing, policy retrieval, justification
drafting) with a deterministic layer (stock level arithmetic, vendor eligibility
checks, price comparison, approval routing). The system never issues a purchase
order, contacts a supplier, commits funds, or approves anything autonomously.

## Glossary

**Procurement_Officer**: The primary user who initiates the reorder review,
  uploads documents, and reviews the AI generated draft before it is routed for
  approval.
**Procurement_Manager**: The human approver who reviews, approves, or rejects the
  drafted purchase requisition.
**System**: The bounded agentic system comprising both the AI components and the
  deterministic components described in this document.
**AI_Layer**: The AI powered components of the System responsible for parsing
  unstructured documents, retrieving policy clauses, and drafting justifications.
**Deterministic_Layer**: The rule based, arithmetic, and routing components of the
  System that perform all calculations, eligibility checks, and workflow routing.
**Inventory_Snapshot**: A structured file (CSV or spreadsheet) uploaded by the
  Procurement_Officer that lists current stock levels, item names, and reorder
  thresholds for each item.
**Reorder_Threshold**: The minimum stock quantity for an item below which a
  reorder must be triggered, as defined in the Inventory_Snapshot.
**Supplier_Quotation**: An unstructured document (PDF or CSV) from a supplier
  containing item descriptions, unit prices, quantities, validity dates, and
  supplier identity.
**Normalised_Quotation**: A structured data record produced by the AI_Layer from a
  Supplier_Quotation, containing extracted fields: item name, unit price, quantity,
  currency, supplier name, and validity date.
**Approved_Vendor_List (AVL)**: The authoritative list of suppliers approved to
  receive orders from the enterprise, maintained outside the System.
**Blacklist**: The authoritative list of suppliers barred from receiving orders,
  maintained outside the System.
**Eligibility_Check**: The deterministic process that verifies a supplier is on
  the AVL and not on the Blacklist, and that the Supplier_Quotation validity date
  has not expired.
**Policy_Corpus**: The controlled, versioned collection of enterprise procurement
  policy documents used exclusively by the AI_Layer for retrieval augmented
  generation.
**Purchase_Requisition**: The formal output document produced by the System,
  comprising item details, recommended supplier, price comparison table, retrieved
  policy clauses, and AI drafted justification — submitted to the
  Procurement_Manager for approval.
**Approval_Record**: The immutable log entry created when a Procurement_Manager
  approves or rejects a Purchase_Requisition, capturing the decision, timestamp, and
  manager identity.

## Requirements

### Requirement 1: Weekly Reorder Review Initiation

**User Story:** As a Procurement Officer, I want to upload an Inventory Snapshot to
initiate the weekly reorder review, so that the System can identify which items need
to be reordered without manual calculation.

#### Acceptance Criteria

1. WHEN the Procurement_Officer uploads an Inventory_Snapshot file in CSV or
   spreadsheet (.xlsx, .ods) format, THE System SHALL accept the file, display a
   confirmation that the file has been received, and begin the reorder review within
   5 seconds.
2. IF the uploaded file is missing any required column (item name, current stock,
   reorder threshold), or contains non numeric values in the current stock or reorder
   threshold columns, THEN THE System SHALL reject the file and return a descriptive
   validation error that names each missing or invalid column and its expected data
   type.
3. IF the uploaded file contains no rows where current stock is strictly less than
   the reorder threshold, THEN THE System SHALL display a message stating that no
   items require reorder and terminate the review session without proceeding to
   quotation upload.
4. WHEN the reorder review is initiated with a valid file, THE Deterministic_Layer
   SHALL compare each item's current stock against its reorder threshold and produce
   a reorder list that includes, for each item: item name, current stock level,
   reorder threshold, and required reorder quantity.
5. IF a row in the uploaded file contains a negative value in the current stock or
   reorder threshold column, THEN THE System SHALL treat that row as invalid, exclude
   it from the reorder list, and include it in the validation error report alongside
   any missing column errors.

### Requirement 2: Supplier Quotation Upload and Parsing

**User Story:** As a Procurement_Officer, I want to upload supplier quotations in
PDF or CSV format and have the System extract and normalise the data, so that I do
not have to manually transcribe figures from unstructured documents.

#### Acceptance Criteria

1. WHEN the Procurement_Officer uploads between 1 and 10 Supplier_Quotation files
   (each no larger than 5 MB) in PDF or CSV format, THE AI_Layer SHALL parse each
   file within 30 seconds per file and produce a Normalised_Quotation containing
   item name, unit price, quantity, currency, supplier name, and validity date.
2. IF a Supplier_Quotation file cannot be parsed (corrupted file, unsupported
   format, or missing mandatory fields), THEN THE AI_Layer SHALL flag that specific
   file as unparseable, display an error message that names the affected file and
   states the specific reason for failure (unsupported format, missing field, or
   corrupted content), and continue processing any remaining files in the batch.
3. WHEN at least one Supplier_Quotation file has been parsed successfully, THE
   System SHALL display all resulting Normalised_Quotation records to the
   Procurement_Officer for review before proceeding to eligibility checks.
4. WHILE the Procurement_Officer is reviewing Normalised_Quotation records, THE
   Procurement_Officer SHALL be able to correct any field in any Normalised_Quotation
   record, and the System SHALL not proceed to eligibility checks until the
   Procurement_Officer explicitly confirms the reviewed data.
5. IF a Supplier_Quotation contains items whose names do not case insensitively
   exactly match any item name on the current reorder list, THEN THE System SHALL
   include those items in the Normalised_Quotation and mark each one as not matching
   a current reorder requirement.

### Requirement 3: Supplier Eligibility Verification

**User Story:** As a Procurement_Officer, I want the System to automatically check
whether each quoted supplier is on the Approved_Vendor_List and not blacklisted, so
that ineligible suppliers are excluded from consideration without manual lookup.

#### Acceptance Criteria

1. WHEN the Procurement_Officer confirms the Normalised_Quotation records, THE
   Deterministic_Layer SHALL verify that each supplier is present on the
   Approved_Vendor_List and absent from the Blacklist before including that
   supplier's quotation in price comparison.
2. WHEN the Procurement_Officer confirms the Normalised_Quotation records, THE
   Deterministic_Layer SHALL verify that each quotation's validity date is on or
   after the current UTC date.
3. IF a supplier fails any eligibility check, THEN THE Deterministic_Layer SHALL
   mark that supplier's quotation as ineligible and exclude it from price comparison,
   recording one of the following specific reasons: AVL_ABSENT (supplier not on the
   Approved_Vendor_List), BLACKLISTED (supplier present on the Blacklist), or
   EXPIRED (validity date is before the current UTC date). IF a quotation fails
   multiple checks, all applicable reasons SHALL be recorded.
4. IF all submitted Supplier_Quotations fail eligibility checks, THEN THE System
   SHALL notify the Procurement_Officer, retain all Normalised_Quotation data in the
   current session, and halt the requisition workflow until the Procurement_Officer
   uploads at least one new Supplier_Quotation that passes eligibility checks.
5. WHEN eligibility checks are complete, THE System SHALL present the
   Procurement_Officer with a summary listing, for each supplier: eligibility status
   (eligible or ineligible) and, for ineligible suppliers, each recorded exclusion
   reason.

### Requirement 4: Price Comparison and Supplier Ranking

**User Story:** As a Procurement_Officer, I want the System to compare prices from
eligible suppliers and rank them, so that the lowest compliant price is clearly
identified without manual spreadsheet work.

#### Acceptance Criteria

1. WHEN at least two eligible Normalised_Quotations cover the same reorder item,
   THE Deterministic_Layer SHALL compute the total cost (unit price × quantity
   required to bring current stock up to the Reorder_Threshold) for each eligible
   supplier and rank them in ascending order of total cost. WHERE two suppliers have
   equal total cost, THE Deterministic_Layer SHALL rank them in ascending
   alphabetical order by supplier name.
2. WHEN only one eligible Normalised_Quotation exists for a reorder item, THE
   Deterministic_Layer SHALL record that supplier as the sole eligible option and
   display a note stating that competitive price comparison was not possible.
3. THE Deterministic_Layer SHALL perform all price arithmetic using the currency
   recorded in each Normalised_Quotation.
4. IF a Normalised_Quotation is denominated in a currency other than UGX, THEN THE
   Deterministic_Layer SHALL exclude that quotation from automated ranking, present
   it to the Procurement_Officer in a separate section showing the supplier name,
   item name, unit price, and original currency, and require the Procurement_Officer
   to confirm a manually converted UGX figure before that quotation is included in
   the comparison table.
5. WHEN the price comparison is complete, THE System SHALL display the ranked
   comparison table to the Procurement_Officer, showing for each eligible supplier:
   supplier name, unit price (UGX), required quantity, total cost (UGX), and
   eligibility status, before generating the justification.

### Requirement 5: Procurement Policy Retrieval

**User Story:** As a Procurement_Officer, I want the System to automatically
retrieve the relevant procurement policy clauses for the items being requisitioned,
so that the justification document cites the correct policy without manual policy
lookups.

#### Acceptance Criteria

1. WHEN the price comparison table is confirmed by the Procurement_Officer, THE
   AI_Layer SHALL query the Policy_Corpus using retrieval augmented generation within
   30 seconds and return the policy clauses relevant to the requisition item names,
   categories, and total costs present in the comparison table.
2. THE AI_Layer SHALL retrieve policy clauses exclusively from the Policy_Corpus and
   SHALL NOT use any knowledge source outside the Policy_Corpus when generating
   policy citations.
3. IF no relevant policy clauses are found in the Policy_Corpus for a given item
   name or category, THEN THE AI_Layer SHALL include an explicit statement in the
   policy retrieval results for that item — e.g., "No policy clause found for
   [item name / category]" — rather than omitting the item or fabricating a clause.
4. WHEN policy clauses are retrieved, THE System SHALL display the retrieved clauses
   to the Procurement_Officer, identifying each clause by document name, clause
   identifier, and document version before drafting the justification.
5. IF the Policy_Corpus is unavailable at retrieval time, THEN THE System SHALL
   notify the Procurement_Officer that policy retrieval has failed, halt the
   justification drafting step, and preserve the current price comparison table so
   that the Procurement_Officer can retry retrieval without repeating earlier steps.

### Requirement 6: Justification Drafting

**User Story:** As a Procurement_Officer, I want the System to draft a written
procurement justification that references the price comparison and relevant policy
clauses, so that I have a consistent, policy aligned starting point rather than
writing from scratch.

#### Acceptance Criteria

1. WHEN a confirmed price comparison table is available, THE AI_Layer SHALL draft a
   written justification that includes, at minimum: the name of the recommended
   supplier, the total cost basis for the recommendation (lowest total cost or sole
   eligible supplier), and references to applicable policy clauses by document name
   and clause identifier, or an explicit absence note for each item where no matching
   clause was found.
2. THE AI_Layer SHALL name the recommended supplier and state the total cost and the
   basis for selection (lowest total cost or sole eligible supplier) in a form that
   can be independently verified against the price comparison table.
3. THE AI_Layer SHALL NOT assert that a Purchase_Requisition is approved, that a
   supplier has been awarded a contract, or that funds have been committed in any
   generated text.
4. WHEN the draft justification is produced, THE Procurement_Officer SHALL be able
   to edit any part of the draft, and THE System SHALL not proceed to Purchase
   Requisition compilation until the Procurement_Officer explicitly confirms the
   draft.
5. IF the AI_Layer cannot produce a draft justification, THEN THE System SHALL
   notify the Procurement_Officer of the failure, preserve the current price
   comparison table and retrieved policy clauses, and allow the Procurement_Officer
   to retry without repeating earlier steps.

### Requirement 7: Purchase Requisition Compilation

**User Story:** As a Procurement_Officer, I want the System to compile all
components into a single Purchase_Requisition document, so that I can submit a
complete, standardised requisition to the Procurement_Manager for approval.

#### Acceptance Criteria

1. WHEN the Procurement_Officer confirms the draft justification, THE System SHALL
   compile a Purchase_Requisition containing: item name, required quantity, and
   current stock level for each reorder item; the eligible supplier list; the price
   comparison table; the recommended supplier; the retrieved policy clauses; and the
   confirmed draft justification.
2. WHEN a Purchase_Requisition is compiled, THE System SHALL assign a unique
   requisition identifier to the document at the time of compilation.
3. WHEN a Purchase_Requisition is compiled, THE System SHALL record the
   Procurement_Officer's authenticated username and the UTC timestamp of compilation
   in the Purchase_Requisition.
4. THE System SHALL NOT issue a purchase order, contact any supplier, or commit any
   funds as part of or after compiling the Purchase_Requisition.
5. IF any required component (reorder item details, eligible supplier list, price
   comparison table, recommended supplier, or confirmed draft justification) is
   absent when the Procurement_Officer confirms, THEN THE System SHALL halt
   compilation, display a message identifying the missing component(s), and preserve
   the current session state so the Procurement_Officer can complete the missing
   step.

### Requirement 8: Approval Routing to Procurement Manager

**User Story:** As a Procurement_Officer, I want the compiled Purchase_Requisition
to be automatically routed to the Procurement_Manager for approval, so that the
handoff follows the correct approval chain without manual forwarding.

#### Acceptance Criteria

1. WHEN a Purchase_Requisition is compiled, THE Deterministic_Layer SHALL route the
   requisition to the designated Procurement_Manager and notify the
   Procurement_Manager of the pending requisition within 10 seconds.
2. THE Deterministic_Layer SHALL route Purchase_Requisitions only to the
   Procurement_Manager role as configured in the System's approval routing table.
   IF the routing table contains no configured Procurement_Manager, THEN THE System
   SHALL halt routing, notify the Procurement_Officer that routing has failed due to
   a missing approver configuration, and preserve the compiled Purchase_Requisition
   in a pending routing state.
3. WHEN routing completes successfully, THE System SHALL lock the compiled
   Purchase_Requisition against modification until the Procurement_Manager records
   an approval or rejection decision.
4. WHEN the Purchase_Requisition is routed, THE System SHALL notify the
   Procurement_Officer that the requisition has been submitted and is awaiting
   manager review within 10 seconds of routing completion.
5. IF the routing action fails at execution time (e.g., notification delivery
   error), THEN THE System SHALL log the failure, notify the Procurement_Officer of
   the routing error, and retain the compiled Purchase_Requisition in a
   pending routing state so that routing can be retried without re compiling.

### Requirement 9: Manager Approval or Rejection

**User Story:** As a Procurement_Manager, I want to review, approve, or reject a
Purchase_Requisition with a recorded rationale, so that all procurement decisions
are documented and traceable for audit purposes.

#### Acceptance Criteria

1. WHEN a Purchase_Requisition enters pending review state, THE System SHALL present
   the full Purchase_Requisition to the Procurement_Manager, including item details,
   price comparison table, retrieved policy clauses, recommended supplier, and draft
   justification.
2. WHEN the Procurement_Manager approves a Purchase_Requisition, THE System SHALL
   create an Approval_Record capturing the requisition identifier, the
   Procurement_Manager's authenticated username, the decision (approved), and the
   UTC timestamp.
3. WHEN the Procurement_Manager selects reject, THE System SHALL require the
   Procurement_Manager to provide a non empty, non whitespace rejection reason before
   the rejection is accepted. WHEN a valid rejection reason is submitted, THE System
   SHALL create an Approval_Record capturing the requisition identifier, the
   Procurement_Manager's authenticated username, the decision (rejected), the
   rejection reason, and the UTC timestamp.
4. IF the Procurement_Manager approves a Purchase_Requisition, THE System SHALL NOT
   automatically issue a purchase order, contact any supplier, or commit any funds.
5. WHEN a rejection Approval_Record is created, THE System SHALL notify the
   Procurement_Officer of the rejection decision and include the rejection reason
   within 30 seconds, so that the Procurement_Officer can initiate a revised
   requisition workflow.

### Requirement 10: Audit Trail and Record Keeping

**User Story:** As a Procurement_Manager, I want all requisition activity to be
recorded in an immutable audit log, so that the enterprise can demonstrate
compliance with procurement policy during audits.

#### Acceptance Criteria

1. THE System SHALL record each of the following events in the audit log with a UTC
   timestamp, the unique requisition identifier, and the authenticated username of
   the acting user (or the component name — AI_Layer or Deterministic_Layer — for
   automated events): Inventory_Snapshot upload, reorder list generation,
   Supplier_Quotation upload, Normalised_Quotation confirmation, eligibility check
   result, price comparison completion, policy retrieval, justification draft
   confirmation, Purchase_Requisition compilation, routing, approval, and rejection.
2. THE System SHALL prevent modification or deletion of any audit log entry after it
   has been written.
3. WHEN an audit log entry is written, THE System SHALL include the unique
   requisition identifier so that all events listed in criterion 1 that share the
   same requisition identifier can be retrieved together in chronological order as a
   complete trace.
4. IF any actor attempts to modify or delete a written audit log entry, THEN THE
   System SHALL deny the request and write a tamper attempt log entry recording the
   UTC timestamp, the actor's authenticated username, the event type attempted
   (modify or delete), and the identifier of the targeted audit log entry.
5. WHEN an authorised user queries the audit log by requisition identifier, THE
   System SHALL return all audit log entries for that requisition identifier in
   chronological order.

### Requirement 11: Safety Boundary Enforcement

**User Story:** As a Procurement_Manager, I want the System to be technically
incapable of issuing purchase orders or committing funds autonomously, so that no
financial commitment can be made without explicit human approval.

#### Acceptance Criteria

1. THE System SHALL NOT expose any interface, function, or agent action that issues
   a purchase order, sends a message to a supplier, or initiates a payment or
   financial commitment.
2. IF the AI_Layer generates output text that contains any of the following
   prohibited patterns — an instruction to issue a purchase order, an instruction to
   contact or message a supplier, or a statement that funds have been committed or a
   contract has been awarded — THEN THE Deterministic_Layer SHALL suppress that
   output before it is presented to any user or written to any record, and SHALL
   write a suppression audit log entry recording the requisition identifier,
   UTC timestamp, and a description of the detected prohibited pattern.
3. WHEN a Purchase_Requisition is approved by the Procurement_Manager, THE System
   SHALL take no automated action other than writing the Approval_Record audit log
   entry and sending the rejection or approval notification to the
   Procurement_Officer.
4. WHEN any component of the System attempts an action outside the defined boundary
   (requisition preparation and routing only), THE System SHALL block the action,
   display a blocked action error message to the active user, and write an audit log
   entry recording the component name, description of the attempted action,
   requisition identifier, and UTC timestamp.

### Requirement 12: Currency and Multi Item Requisition Support

**User Story:** As a Procurement_Officer, I want the System to handle requisitions
covering multiple reorder items and quotations in Ugandan Shillings (UGX), so that
the full weekly reorder list is processed in a single workflow.

#### Acceptance Criteria

1. WHEN an Inventory_Snapshot contains multiple items below their reorder
   thresholds, THE System SHALL generate a single reorder list covering all such
   items and process them within a single requisition workflow.
2. THE Deterministic_Layer SHALL treat UGX as the default requisition currency and
   SHALL display all price comparison figures in UGX for quotations that have been
   confirmed or converted to UGX.
3. IF a Supplier_Quotation is denominated in a currency other than UGX, THEN THE
   System SHALL exclude that quotation from the automated price comparison table,
   display it to the Procurement_Officer in a separate section identifying the
   supplier name, item name, unit price, and original currency, and require the
   Procurement_Officer to supply a UGX converted figure before that quotation is
   included in the comparison.
4. WHEN the Purchase_Requisition covers multiple reorder items, THE System SHALL
   produce a separate price comparison section for each item within the single
   requisition document, each section showing eligible suppliers, unit price (UGX),
   required quantity, total cost (UGX), and recommended supplier for that item.
