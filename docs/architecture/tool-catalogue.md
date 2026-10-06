# Tool Catalogue and Schemas

| Field | Value |
|---|---|
| Week | 4 |
| Owner | Lukaanya George |
| Due | 25 September 2026 |
| Status | Complete, awaiting team review |
| Path | `docs/architecture/tool-catalogue.md` |

## Brief requirement

Define at least two tools/functions with purpose, input schema, output schema, authorization and failure behaviour. At least one tool should retrieve current application data or perform a low-risk simulated side effect such as creating a draft record.

## Write-up

Version 1.2 | 6 October 2026 | Machine-readable companion: [`schemas/`](schemas/)

> **v1.2 (6 October 2026).** Adds `OUTPUT_SCHEMA_INVALID` to the shared error vocabulary and
> to all four output schemas. `dispatch.invoke` now checks every tool response against its output
> schema and discards a non-conforming one, as section 9 always required (closes FA-10). One
> limit: `create_requisition_draft` writes its record before the response is checked, so a
> non-conforming draft response is reported as failed but the record already in the store stays.

> **v1.1 (29 September 2026).** Worked examples in sections 6 and 7 corrected to match
> Requirement 4.6 and section 5: both Lakeview offers (QT-001 and QT-003) are excluded with
> `NAME_DISCREPANCY`, leaving one eligible cement offer. The v1.0 examples still ranked QT-001,
> and the draft justification still claimed three eligible quotations. No schema, rule or tool
> contract changed; `tool_version` stays `1.0`.

### 1. Scope

Four tools are specified. Project Charter section 7 puts "two to four tools with explicit
schemas, permissions and failure behaviour" in scope, and section 1 already named the set the
agent may use. Each tool below is one of those named tools, so the catalogue adds contracts to
an agreed list rather than widening it.

| Tool | Charter section 1 name | Reads | Writes |
|---|---|---|---|
| [`check_reorder_need`](#4-check_reorder_need) | inventory-status tool | `knowledge/data/inventory.csv` | nothing |
| [`check_supplier_eligibility`](#5-check_supplier_eligibility) | supplier-record tool | `knowledge/data/suppliers.json` | nothing |
| [`compare_quotations`](#6-compare_quotations) | deterministic comparison calculator | `knowledge/data/quotations.json` | nothing |
| [`create_requisition_draft`](#7-create_requisition_draft) | requisition-draft tool | the requisition store | one record, in `DRAFT` |

Three retrieve current application data. The fourth is the low-risk simulated side effect the
brief asks for: it writes a draft record to a local store and does nothing else.

Two of the six named tools are deliberately not specified this week. **Document conversion** is
excluded because charter section 9 puts OCR, scans and photographs out of scope and the
conversion layer belongs with the Week 5 orchestration work. **Quotation retrieval** is folded
into `compare_quotations`, which already selects the offers held for a SKU; a separate lookup
would spend one of the four slots on a function with no decision in it.

Policy retrieval is not listed here because it is not a tool. Week 3 delivered it as a pipeline
the officer invokes directly ([`working-rag-pipeline.md`](working-rag-pipeline.md)), and
charter section 1 does not name it among the tools the agent may call. Week 6 may expose it
through the MCP-style interface; until then it stays outside the allow-list.

### 2. Common contract

Every tool is a deterministic Python function. None of them calls the model, and the model
never calls one directly — the orchestration layer does, on the model's proposal.

**One envelope for every response.** Each tool returns the same outer shape, so a caller can
handle success, refusal and failure without knowing which tool ran.

```json
{
  "tool": "check_reorder_need",
  "tool_version": "1.0",
  "status": "ok",
  "data": { },
  "errors": [],
  "trace": {
    "called_at": "2026-09-25T08:14:02Z",
    "caller_role": "PROCUREMENT_OFFICER",
    "latency_ms": 11,
    "data_fingerprint": "6ab934ebb697380b"
  }
}
```

`status` is one of `ok`, `no_result`, `invalid_input`, `unauthorized`, `unavailable`, `failed`.
The string-constant vocabulary follows `ItemOutcome.status` in
[`rag/pipeline.py`](../../src/procurement_agent/rag/pipeline.py) rather than introducing an
enum type the package does not use anywhere else.

**`no_result` is not a failure.** An empty reorder list is the correct answer to a week in which
nothing is low. Requirement 1.5 ends the review there, and conflating it with an error would
make a normal week look broken.

**Reject, do not salvage.** A request that does not conform is refused whole. No value is
coerced, no bad element is dropped, and no partial result is returned. This is the rule
`schema.validate` already applies to model output under Requirement 3.3, and the reasoning
carries over: a half-answered tool call is indistinguishable downstream from a complete one.

**Every applicable error, not the first.** `errors` is a list because Requirement 4 requires
every applicable exclusion reason to be recorded, and because a caller that fixes one problem
per round trip is a caller that makes four round trips.

**Errors name the cause, never a repaired value.** POL-005-C02 forbids supplying a term the
supplier did not state, and the same discipline applies to a request: the tool says which field
was wrong and why, and stops.

| Code | Raised when |
|---|---|
| `MISSING_PARAMETER` | A required field is absent |
| `INVALID_PARAMETER` | A field is present but malformed or out of range |
| `UNKNOWN_SKU` | The SKU is not in the inventory snapshot |
| `UNKNOWN_SUPPLIER` | A supplier identifier does not resolve |
| `UNAUTHORIZED_ROLE` | The caller's role may not invoke this tool |
| `TOOL_NOT_ALLOWED` | The tool was not on the orchestration allow-list for this step |
| `DATA_SOURCE_UNAVAILABLE` | A data file could not be read |
| `DATA_INTEGRITY_ERROR` | A data file was read but failed its registered checksum |
| `INSUFFICIENT_QUOTATIONS` | Fewer eligible offers than POL-001 requires for the value band |
| `INCOMPARABLE_QUOTATION` | An offer lacks a field landed cost needs |
| `EXCHANGE_RATE_REQUIRED` | A non-UGX offer is in scope and no rate was supplied |
| `MISSING_COMPONENT` | A requisition component required at compilation is absent |
| `FORBIDDEN_TRANSITION` | A status beyond `DRAFT` was requested |
| `OUTPUT_SCHEMA_INVALID` | A tool's response did not conform to its output schema and was discarded (raised by the orchestration layer, not by a tool) |

Codes are SCREAMING_SNAKE, matching the `AVL_ABSENT` / `BLACKLISTED` / `EXPIRED` vocabulary
Requirement 4 already fixes.

**Integrity before use.** Each data-backed tool verifies the file it reads against the SHA-256
in [`knowledge/source-register.csv`](../../knowledge/source-register.csv) and records that hash
as `data_fingerprint`. The corpus loader already refuses an unregistered or altered document;
operational records get the same treatment, so a figure in front of an approver can be traced
to a reviewed file.

**Every call is traced.** Tool calls append to `evidence/traces/tool-runs.jsonl` under
`COMPONENT = "TOOL"`, in the same append-only JSONL idiom as `runlog.RunLog` and
`rag.pipeline.TraceLog`. The trace never carries an API key; `config.redact` already exists for
that.

**Output is scanned before the model sees it.** Tool results pass through `guards.scan` and
`guards.suppress` ([`guards.py`](../../src/procurement_agent/guards.py)) on the way back, as
`Extractor` and `PolicyPipeline` already do. A supplier note copied from a document is content,
and content that asserts an approval or an award is suppressed rather than relayed.

### 3. Authorization

Two seeded roles plus the agent itself. The delegation rules are POL-004, not an invention of
this document.

| Tool | `PROCUREMENT_OFFICER` | `PROCUREMENT_MANAGER` | `AGENT` | Basis |
|---|---|---|---|---|
| `check_reorder_need` | Call | Call | Call | POL-004-C01; read-only |
| `check_supplier_eligibility` | Call | Call | Call | POL-004-C01; read-only |
| `compare_quotations` | Call | Call | Call | POL-004-C01; read-only |
| `create_requisition_draft` | Call | Refused | Propose only | POL-004-C01, POL-004-C03 |

Three rules do the work.

**The agent proposes; the officer creates.** `AGENT` may assemble a `create_requisition_draft`
call and put it in front of the officer, but the call executes under the officer's identity
after the officer confirms it. Requirement 9.1 makes compilation follow the officer's
confirmation of the justification, and this is where the human approval gate sits — before the
only tool with a side effect.

**The manager cannot create.** POL-004-C03 separates duties: the person preparing a requisition
must not record the approval, and the approver must not prepare the requisition. A
`create_requisition_draft` call under `PROCUREMENT_MANAGER` returns `UNAUTHORIZED_ROLE`. The
manager's own actions — approve, reject — are not tools at all and have no entry here, by
Requirement 14.1.

**The role is injected, never supplied.** `caller_role` appears in no input schema. The
orchestration layer takes it from the authenticated session and it surfaces only in the output
trace. Requirement 14.5 treats every quotation and policy document as untrusted data, and a
role that were a model-facing parameter could be requested by text inside one of them.

Alongside that, the allow-list of Requirement 14.5: a tool is reachable only from a static list
held by the orchestration layer for the current step. A name appearing in document content
matches nothing, and a call for a tool outside the list for that step returns
`TOOL_NOT_ALLOWED` without reaching the tool.

### 4. `check_reorder_need`

**Purpose.** Identify every stocked item at or below its reorder point for a weekly review, and
compute how much to order. This is the step that starts the workflow: PRO-001-C02 has the
officer review items at or below the recorded reorder point, and Requirement 1.4 makes the
flagging and the arithmetic deterministic so the officer never does it by hand.

**Side effects.** None. Read-only.

**Authorization.** All three roles. Reading a stock position commits nothing.

**Input schema** — [`schemas/check_reorder_need.input.json`](schemas/check_reorder_need.input.json)

```json
{
  "type": "object",
  "required": ["review_date"],
  "additionalProperties": false,
  "properties": {
    "review_date": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" },
    "skus": { "type": "array", "items": { "type": "string", "pattern": "^AH-[A-Z]{2}-[0-9]{3}$" } },
    "location": { "type": ["string", "null"], "enum": ["Nakawa Main Store", "Kireka Branch", null] },
    "include_sufficient": { "type": "boolean", "default": false }
  }
}
```

**Output schema** — [`schemas/check_reorder_need.output.json`](schemas/check_reorder_need.output.json).
The envelope of section 2 with a `data` object carrying `review_date`, `evaluated_count`,
`flagged_count`, `no_reorder_required` and an `items` array. Each item repeats the snapshot
figures and adds two computed ones:

- `reorder_quantity` — `target_stock_level - current_stock`, per Requirement 1.4. Never stored
  in the snapshot; always computed here.
- `estimated_total_ugx` — `reorder_quantity × unit_cost_ugx`. This selects the POL-001 value
  band and nothing else. It is explicitly **not** a price, because no supplier has quoted yet.

**Failure behaviour.**

| Condition | `status` | Code | Behaviour |
|---|---|---|---|
| `review_date` absent | `invalid_input` | `MISSING_PARAMETER` | Nothing read. Names the field. |
| `review_date` malformed, or a SKU fails its pattern | `invalid_input` | `INVALID_PARAMETER` | Whole request refused; no partial scan. |
| A requested SKU is not in the snapshot | `invalid_input` | `UNKNOWN_SKU` | Every unknown SKU is listed, not just the first. |
| `inventory.csv` missing or unreadable | `unavailable` | `DATA_SOURCE_UNAVAILABLE` | No cached or assumed stock figure is substituted. |
| Checksum does not match the register | `failed` | `DATA_INTEGRITY_ERROR` | Refuses to read an unreviewed edit, as the corpus loader does. |
| A row breaks a Requirement 1.3 invariant | `failed` | `DATA_INTEGRITY_ERROR` | Names the row and the invariant. The snapshot is rejected whole. |
| Nothing is at or below its reorder point | `no_result` | — | `no_reorder_required: true`. Requirement 1.5 ends the review; this is a normal week, not an error. |

**Example.** Cement sits exactly at its reorder point, which "at or below" must catch.

```json
{ "review_date": "2026-09-25", "skus": ["AH-CM-001", "AH-HT-012"] }
```

```json
{
  "tool": "check_reorder_need",
  "tool_version": "1.0",
  "status": "ok",
  "data": {
    "review_date": "2026-09-25",
    "evaluated_count": 2,
    "flagged_count": 2,
    "no_reorder_required": false,
    "items": [
      {
        "sku": "AH-CM-001",
        "item_name": "Portland cement 42.5N 50 kg bag",
        "category": "cement and masonry",
        "unit_of_measure": "bag",
        "current_stock": 150,
        "reorder_point": 150,
        "target_stock_level": 270,
        "reorder_quantity": 120,
        "estimated_unit_cost_ugx": 32000,
        "estimated_total_ugx": 3840000,
        "location": "Nakawa Main Store",
        "at_or_below_reorder_point": true
      },
      {
        "sku": "AH-HT-012",
        "item_name": "Spirit level 600 mm",
        "category": "hand tools and safety equipment",
        "unit_of_measure": "piece",
        "current_stock": 18,
        "reorder_point": 20,
        "target_stock_level": 65,
        "reorder_quantity": 47,
        "estimated_unit_cost_ugx": 42000,
        "estimated_total_ugx": 1974000,
        "location": "Nakawa Main Store",
        "at_or_below_reorder_point": true
      }
    ]
  },
  "errors": [],
  "trace": {
    "called_at": "2026-09-25T08:14:02Z",
    "caller_role": "PROCUREMENT_OFFICER",
    "latency_ms": 11,
    "data_fingerprint": "6ab934ebb697380b"
  }
}
```

**Traceability.** Requirement 1.2–1.5 · PRO-001-C01, PRO-001-C02 · success criterion S2.

### 5. `check_supplier_eligibility`

**Purpose.** Decide whether a supplier may be considered for a given category on a given date,
and record every reason it may not. POL-002 sets three separate bars — Approved Vendor List
membership, current status, and category — and Requirement 4 adds quotation expiry. Combining
them in one deterministic answer is what keeps an ineligible supplier out of a comparison
regardless of price.

**Side effects.** None. Read-only.

**Authorization.** All three roles. The tool reports; it does not admit or exclude anyone from
the register, and it cannot change a status.

**Input schema** — [`schemas/check_supplier_eligibility.input.json`](schemas/check_supplier_eligibility.input.json)

```json
{
  "type": "object",
  "required": ["category", "as_of_date"],
  "anyOf": [{ "required": ["supplier_ids"] }, { "required": ["supplier_names"] }],
  "additionalProperties": false,
  "properties": {
    "category": { "type": "string", "enum": ["cement and masonry", "hand tools and safety equipment", "electrical and plumbing"] },
    "as_of_date": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" },
    "supplier_ids": { "type": "array", "items": { "type": "string", "pattern": "^SUP-[0-9]{3}$" } },
    "supplier_names": { "type": "array", "items": { "type": "string", "minLength": 1 } },
    "quotation_ids": { "type": "array", "items": { "type": "string", "pattern": "^QT-[0-9]{3}$" } }
  }
}
```

`supplier_names` exists because a quotation carries a printed name, not an identifier. Names are
matched **exactly**. A close match is reported in `similar_registered_names`, marked
`NAME_DISCREPANCY`, and excluded from comparison until officer clearance is recorded:
POL-002-C04 puts that judgement with the officer, and the register deliberately holds Lakeview
Building Materials and Lakeview Building Supplies as separate entities to exercise it.

**Output schema** — [`schemas/check_supplier_eligibility.output.json`](schemas/check_supplier_eligibility.output.json).
One `results` entry per requested supplier, each with `eligible` and an `exclusion_reasons`
array drawn from:

| Reason | Basis |
|---|---|
| `AVL_ABSENT` | Not in the supplier register at all. POL-002-C01. |
| `BLACKLISTED` | `avl_status` is `BLACKLISTED`. POL-002-C02. |
| `SUSPENDED` | `avl_status` is `SUSPENDED` on `as_of_date`. POL-002-C02. |
| `OUT_OF_CATEGORY` | Category not among the supplier's approved categories. POL-002-C03. |
| `EXPIRED` | A supplied quotation's validity date precedes `as_of_date`. POL-005-C03. |
| `NAME_DISCREPANCY` | The supplier name closely resembles another AVL supplier and clearance is not yet recorded. POL-002-C04. |

All applicable reasons are returned. A supplier that is both suspended and out of category
reports both, because an officer who fixes one and retries should not discover the second on the
next round trip.

**Failure behaviour.**

| Condition | `status` | Code | Behaviour |
|---|---|---|---|
| Neither `supplier_ids` nor `supplier_names` | `invalid_input` | `MISSING_PARAMETER` | States that one of the two is required. |
| `category` not a known category | `invalid_input` | `INVALID_PARAMETER` | Refused. An unknown category cannot be checked against POL-002-C03. |
| A `quotation_ids` entry does not resolve | `invalid_input` | `INVALID_PARAMETER` | Named. Expiry cannot be assessed against an offer that is not held. |
| `suppliers.json` unreadable | `unavailable` | `DATA_SOURCE_UNAVAILABLE` | **No supplier is reported eligible.** Absence of the register is never read as approval. |
| Checksum mismatch | `failed` | `DATA_INTEGRITY_ERROR` | Refused. |
| Supplier absent from the register | `ok` | — | Not an error. `eligible: false` with `AVL_ABSENT` — that is the answer. |

The fourth row is the one that matters. A tool that failed open here would let an unknown
supplier through whenever a file was missing, which is precisely the case POL-002-C01 exists to
prevent.

**Example.** One blacklisted supplier and two lookalike names awaiting clearance.

```json
{ "category": "cement and masonry", "as_of_date": "2026-09-25", "supplier_ids": ["SUP-002", "SUP-006", "SUP-007"] }
```

```json
{
  "tool": "check_supplier_eligibility",
  "tool_version": "1.0",
  "status": "ok",
  "data": {
    "category": "cement and masonry",
    "as_of_date": "2026-09-25",
    "results": [
      {
        "requested": "SUP-002",
        "matched_by": "supplier_id",
        "supplier_id": "SUP-002",
        "registered_name": "Lakeview Building Materials",
        "avl_status": "ACTIVE",
        "approved_categories": ["cement and masonry"],
        "eligible": false,
        "exclusion_reasons": ["NAME_DISCREPANCY"],
        "similar_registered_names": ["Lakeview Building Supplies"]
      },
      {
        "requested": "SUP-006",
        "matched_by": "supplier_id",
        "supplier_id": "SUP-006",
        "registered_name": "Kireka Steel and Cement Ltd",
        "avl_status": "BLACKLISTED",
        "approved_categories": ["cement and masonry"],
        "eligible": false,
        "exclusion_reasons": ["BLACKLISTED"],
        "similar_registered_names": []
      },
      {
        "requested": "SUP-007",
        "matched_by": "supplier_id",
        "supplier_id": "SUP-007",
        "registered_name": "Lakeview Building Supplies",
        "avl_status": "ACTIVE",
        "approved_categories": ["cement and masonry"],
        "eligible": false,
        "exclusion_reasons": ["NAME_DISCREPANCY"],
        "similar_registered_names": ["Lakeview Building Materials"]
      }
    ]
  },
  "errors": [],
  "trace": {
    "called_at": "2026-09-25T08:14:09Z",
    "caller_role": "PROCUREMENT_OFFICER",
    "latency_ms": 4,
    "data_fingerprint": "7ec4874dfd26415e"
  }
}
```

**Traceability.** Requirement 4.1–4.6 · POL-002-C01 to C04, POL-005-C03 · success criteria S6, S7.

### 6. `compare_quotations`

**Purpose.** Put every offer for one item on a common basis and rank it by landed cost. This is
the tool the charter calls the deterministic comparison calculator, and it exists because
Requirement 6.6 forbids the model from contributing any arithmetic to a displayed figure.
POL-003-C04 is the reason it ranks but does not choose: the lowest price does not automatically
determine the preferred offer.

**Side effects.** None. Pure computation over held records.

**Authorization.** All three roles. Ranking is not awarding, and POL-004-C04 is explicit that a
comparison is not a purchase order.

**Input schema** — [`schemas/compare_quotations.input.json`](schemas/compare_quotations.input.json)

```json
{
  "type": "object",
  "required": ["sku", "reorder_quantity", "comparison_date"],
  "additionalProperties": false,
  "properties": {
    "sku": { "type": "string", "pattern": "^AH-[A-Z]{2}-[0-9]{3}$" },
    "reorder_quantity": { "type": "integer", "exclusiveMinimum": 0 },
    "comparison_date": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" },
    "quotation_ids": { "type": "array", "items": { "type": "string", "pattern": "^QT-[0-9]{3}$" } },
    "exchange_rate_ugx_per_usd": { "type": "number", "exclusiveMinimum": 0 },
    "exchange_rate_effective_date": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" }
  }
}
```

**Output schema** — [`schemas/compare_quotations.output.json`](schemas/compare_quotations.output.json).
Three parts, and the split is the point.

- `ranked` — comparable, eligible offers in ascending landed cost. Ties break on supplier name,
  ascending alphabetical, per Requirement 6.2.
- `excluded` — every offer that did not make the table, each with all its reasons and the named
  missing field where one applies. Requirement 6.3 presents these separately rather than
  dropping them, so the officer can see what was set aside and why.
- `quotation_requirement` — the POL-001 competition check for the value band, with
  `exception_required` set when the required count was not met.

Each ranked row carries the whole derivation, not just the answer: `original_currency`,
`original_unit_price`, `unit_conversion_factor`, `normalised_unit_cost_ugx`,
`extended_cost_ugx`, `vat_amount_ugx`, `delivery_cost_ugx`, `landed_cost_ugx`. POL-003-C03
requires VAT and delivery to be visible separately, and an approver who can only see a total
cannot check it.

**`normalised_unit_cost_ugx` is always net of VAT.** A VAT-inclusive price is divided down to
its net equivalent before comparison, and the VAT is shown in its own column. Comparing an
inclusive price against an exclusive one directly is the arithmetic error the charter's problem
statement describes, and it is designed out here rather than warned about.

**No recommendation is emitted.** There is no `recommended_quotation_id` in this output. The
model may explain the trade-offs in prose — the AI Boundary Matrix permits exactly that — but
the ranking is the tool's whole contribution.

**Failure behaviour.**

| Condition | `status` | Code | Behaviour |
|---|---|---|---|
| `sku` or `reorder_quantity` absent | `invalid_input` | `MISSING_PARAMETER` | Nothing computed. |
| `reorder_quantity` zero or negative | `invalid_input` | `INVALID_PARAMETER` | Refused; there is no cost of ordering nothing. |
| SKU not in the snapshot | `invalid_input` | `UNKNOWN_SKU` | Refused. The stocking unit is unknown, so nothing can be normalised. |
| A non-UGX offer is in scope, no rate supplied | `invalid_input` | `EXCHANGE_RATE_REQUIRED` | Refused. POL-003-C01 requires the rate to be disclosed; the tool will not pick one. |
| An offer lacks VAT treatment, delivery or a conversion factor | `ok` | — | Excluded with `INCOMPARABLE_QUOTATION` and the field named. The rest still rank, per Requirement 6.3. |
| Fewer eligible offers than POL-001 requires | `ok` | `INSUFFICIENT_QUOTATIONS` | Table still returned, `satisfied: false`, `exception_required: true`. POL-001-C04 needs a recorded reason and Manager approval — the tool reports, it does not block. |
| Exactly one eligible offer | `ok` | — | `sole_eligible_option: true`. Requirement 6.4 records that competitive comparison was not possible. |
| No eligible offer at all | `no_result` | — | Empty `ranked`, populated `excluded`. |
| `quotations.json` unreadable or checksum mismatch | `unavailable` / `failed` | `DATA_SOURCE_UNAVAILABLE` / `DATA_INTEGRITY_ERROR` | No partial ranking. |

Two rows deserve emphasis. An incomparable offer is **excluded, not repaired** — the missing
VAT treatment on `QT-021` is named, never assumed, per POL-005-C02. And an insufficient count
is reported rather than enforced: blocking the workflow would make the POL-001-C04 exception
path unreachable.

**Example.** Cement, 120 bags. The blacklisted offer and both unresolved name-discrepancy offers
drop out, and the per-tonne offer is comparable only because its conversion factor is stated.
This matches the recorded run in
[`03-compare_quotations.json`](../../evidence/traces/tools/03-compare_quotations.json).

```json
{ "sku": "AH-CM-001", "reorder_quantity": 120, "comparison_date": "2026-09-25" }
```

```json
{
  "tool": "compare_quotations",
  "tool_version": "1.0",
  "status": "ok",
  "data": {
    "sku": "AH-CM-001",
    "reorder_quantity": 120,
    "comparison_date": "2026-09-25",
    "currency": "UGX",
    "exchange_rate": null,
    "ranked": [
      {
        "rank": 1,
        "quotation_id": "QT-002",
        "supplier_id": "SUP-004",
        "supplier_name": "Bugolobi Hardware Supplies",
        "original_currency": "UGX",
        "original_unit_price": 620000,
        "unit_conversion_factor": 20.0,
        "normalised_unit_cost_ugx": 31000.00,
        "extended_cost_ugx": 3720000.00,
        "vat_amount_ugx": 669600.00,
        "delivery_cost_ugx": 90000,
        "landed_cost_ugx": 4479600.00,
        "lead_time_days": 7,
        "validity_date": "2026-10-24",
        "tie_broken_on_supplier_name": false
      }
    ],
    "excluded": [
      {
        "quotation_id": "QT-001",
        "supplier_id": "SUP-002",
        "supplier_name": "Lakeview Building Materials",
        "reasons": ["NAME_DISCREPANCY"],
        "missing_fields": []
      },
      {
        "quotation_id": "QT-003",
        "supplier_id": "SUP-007",
        "supplier_name": "Lakeview Building Supplies",
        "reasons": ["NAME_DISCREPANCY"],
        "missing_fields": []
      },
      {
        "quotation_id": "QT-004",
        "supplier_id": "SUP-006",
        "supplier_name": "Kireka Steel and Cement Ltd",
        "reasons": ["BLACKLISTED"],
        "missing_fields": []
      }
    ],
    "quotation_requirement": {
      "value_band": "500k_to_under_5m",
      "clause": "POL-001-C02",
      "required_count": 3,
      "eligible_count": 1,
      "satisfied": false,
      "exception_required": true
    },
    "sole_eligible_option": true
  },
  "errors": [
   {
      "code": "INSUFFICIENT_QUOTATIONS",
      "detail": "POL-001-C02 requires 3 eligible quotations for this value band; 1 remains after exclusions."
   }
  ],
  "trace": {
    "called_at": "2026-09-25T08:15:31Z",
    "caller_role": "PROCUREMENT_OFFICER",
    "latency_ms": 23,
    "data_fingerprint": "7ffed0c12482d5a7"
  }
}
```

Three offers are excluded for two different policy reasons: one for `BLACKLISTED`, and both
Lakeview offers for `NAME_DISCREPANCY`, because Requirement 4.6 bars *each* side of a
resemblance until the officer records clearance — neither is presumed to be the "real" one.
Only one offer remains, so the tool reports `INSUFFICIENT_QUOTATIONS` and
`sole_eligible_option: true` without blocking. The blacklisted one had the lowest headline price in the set at UGX 29,800
per bag, which is exactly the kind of false winner a spreadsheet sorted by price would miss.

**Traceability.** Requirement 5, Requirement 6.1–6.6 · POL-001-C01 to C04, POL-003-C01 to C04,
SPEC-001-C01, SPEC-001-C02, SPEC-003-C01 · success criteria S1, S2.

### 7. `create_requisition_draft`

**Purpose.** Compile the confirmed components into a purchase requisition in `DRAFT`. This is
the catalogue's one side effect, and the brief's low-risk simulated write: a record appears in
the local requisition store and nothing else happens anywhere.

**Side effects.** Writes one requisition record with status `DRAFT`. Contacts nobody, orders
nothing, commits no funds.

**Authorization.** `PROCUREMENT_OFFICER` only.

- `AGENT` may **propose** the call. It executes under the officer's identity once the officer
  confirms, per Requirement 9.1. This is the human approval gate, and it sits before the only
  tool in the catalogue that writes anything.
- `PROCUREMENT_MANAGER` is refused with `UNAUTHORIZED_ROLE`. POL-004-C03 separates preparation
  from approval; a manager who drafted the requisition would later be approving their own work.

**Input schema** — [`schemas/create_requisition_draft.input.json`](schemas/create_requisition_draft.input.json)

```json
{
  "type": "object",
  "required": ["review_date", "officer_username", "items", "justification"],
  "additionalProperties": false,
  "properties": {
    "review_date": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" },
    "officer_username": { "type": "string", "minLength": 1 },
    "status": { "const": "DRAFT", "default": "DRAFT" },
    "items": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["sku", "reorder_quantity", "comparison_reference"],
        "additionalProperties": false,
        "properties": {
          "sku": { "type": "string", "pattern": "^AH-[A-Z]{2}-[0-9]{3}$" },
          "reorder_quantity": { "type": "integer", "exclusiveMinimum": 0 },
          "comparison_reference": { "type": "string" },
          "recommended_quotation_id": { "type": ["string", "null"] },
          "unresolved_issues": { "type": "array", "items": { "type": "string" } }
        }
      }
    },
    "policy_clauses": { "type": "array", "items": { "type": "string", "pattern": "^[A-Z]+-[0-9]{3}-C[0-9]{2}$" } },
    "justification": { "type": "string", "minLength": 1 }
  }
}
```

**`status` is present only so that misuse has a name.** It accepts the single value `DRAFT`. Any
other value is a schema violation reported as `FORBIDDEN_TRANSITION` rather than as a generic
unknown-field error, because Requirement 14.3 permits no programmatic transition beyond `DRAFT`
and a refusal should say which rule it is enforcing. Omitting the field entirely is the normal
case.

**Output schema** — [`schemas/create_requisition_draft.output.json`](schemas/create_requisition_draft.output.json).
The created record, carrying the REQ-001 required sections. Four fields are fixed by contract
and cannot hold anything else:

| Field | Value | Why |
|---|---|---|
| `status` | `"DRAFT"` | Requirement 14.3. No other value is producible. |
| `human_confirmation_required` | `true` | The draft advances only when a human submits it. |
| `routed_to` | `null` | Routing is a human action, Requirement 10.1. |
| `approved_by`, `decision` | `null` | POL-004-C02. Only the Manager decides, and not through a tool. |

**Failure behaviour.**

| Condition | `status` | Code | Behaviour |
|---|---|---|---|
| Any required field absent | `invalid_input` | `MISSING_PARAMETER` | **Nothing is written.** Names every missing field. |
| `status` set to anything but `DRAFT` | `invalid_input` | `FORBIDDEN_TRANSITION` | Nothing written. Cites Requirement 14.3. |
| Called as `PROCUREMENT_MANAGER` | `unauthorized` | `UNAUTHORIZED_ROLE` | Nothing written. Cites POL-004-C03. |
| Called by `AGENT` without officer confirmation | `unauthorized` | `UNAUTHORIZED_ROLE` | Nothing written. The confirmation is the gate. |
| Tool not on the allow-list for this step | `unauthorized` | `TOOL_NOT_ALLOWED` | Refused before the tool is entered. |
| A required component is absent at compilation | `invalid_input` | `MISSING_COMPONENT` | Halts, names the component, preserves session state so the officer can complete it. Requirement 9.4. |
| A cited clause is not in the corpus at that version | `invalid_input` | `INVALID_PARAMETER` | Refused. A requisition must not cite a clause that cannot be produced. |
| Requisition store unwritable | `unavailable` | `DATA_SOURCE_UNAVAILABLE` | No identifier is issued, so no gap appears in the sequence. |

Every failure row writes nothing. A partially written requisition is worse than none, because it
would appear in the store as a real one.

**Example.** The officer confirms and the draft is created — with the unresolved supplier-name
discrepancy carried on the record rather than quietly dropped.

```json
{
  "review_date": "2026-09-25",
  "officer_username": "a.nakato",
  "items": [
    {
      "sku": "AH-CM-001",
      "reorder_quantity": 120,
      "comparison_reference": "CMP-2026-0925-001",
      "recommended_quotation_id": "QT-002",
      "unresolved_issues": ["QT-003 is from Lakeview Building Supplies, a different entity from Lakeview Building Materials. POL-002-C04 discrepancy not yet resolved."]
    }
  ],
  "policy_clauses": ["POL-001-C02", "POL-002-C04", "POL-003-C03"],
  "justification": "Cement is at its reorder point at the Nakawa Main Store. After eligibility exclusions, one comparable offer remains (Bugolobi Hardware Supplies, QT-002). POL-001-C02 is not satisfied, so an exception would be required before the requisition proceeds."
}
```

```json
{
  "tool": "create_requisition_draft",
  "tool_version": "1.0",
  "status": "ok",
  "data": {
    "requisition_id": "REQ-2026-014",
    "status": "DRAFT",
    "created_at": "2026-09-25T08:22:47Z",
    "created_by": "a.nakato",
    "review_date": "2026-09-25",
    "items": [
      {
        "sku": "AH-CM-001",
        "reorder_quantity": 120,
        "comparison_reference": "CMP-2026-0925-001",
        "recommended_quotation_id": "QT-002"
      }
    ],
    "policy_clauses": ["POL-001-C02", "POL-002-C04", "POL-003-C03"],
    "justification": "Cement is at its reorder point at the Nakawa Main Store. After eligibility exclusions, one comparable offer remains (Bugolobi Hardware Supplies, QT-002). POL-001-C02 is not satisfied, so an exception would be required before the requisition proceeds.",
    "unresolved_issues": ["QT-003 is from Lakeview Building Supplies, a different entity from Lakeview Building Materials. POL-002-C04 discrepancy not yet resolved."],
    "human_confirmation_required": true,
    "routed_to": null,
    "approved_by": null,
    "decision": null
  },
  "errors": [],
  "trace": {
    "called_at": "2026-09-25T08:22:47Z",
    "caller_role": "PROCUREMENT_OFFICER",
    "latency_ms": 8,
    "data_fingerprint": null
  }
}
```

And the refusal, when something asks for a status beyond `DRAFT`:

```json
{
  "tool": "create_requisition_draft",
  "tool_version": "1.0",
  "status": "invalid_input",
  "data": null,
  "errors": [
    {
      "code": "FORBIDDEN_TRANSITION",
      "field": "status",
      "detail": "status must be DRAFT; \"APPROVED\" was requested. Requirement 14.3 permits no programmatic transition beyond DRAFT. Nothing was written."
    }
  ],
  "trace": {
    "called_at": "2026-09-25T08:31:02Z",
    "caller_role": "AGENT",
    "latency_ms": 1,
    "data_fingerprint": null
  }
}
```

**Traceability.** Requirement 9.1–9.5, Requirement 10.1, Requirement 14.1, 14.3 · POL-004-C01 to
C04, REQ-001 · success criteria S7, S8.

### 8. Tools that must never exist

The catalogue is closed. Requirement 14.1 and the AI Boundary Matrix row for purchase orders,
payment and supplier contact both say the same thing: "No such agent tool or interface shall
exist." This is not a permission that is withheld at runtime — the function is absent.

The prohibition is enforced in CI, not only in prose.
[`.semgrep/agent-safety.yml`](../../.semgrep/agent-safety.yml) fails the build on the definition
of any function named:

| Category | Names |
|---|---|
| Purchase orders | `issue_purchase_order`, `create_purchase_order`, `send_purchase_order`, `place_order` |
| Supplier contact | `contact_supplier`, `email_supplier`, `message_supplier`, `send_supplier_message` |
| Financial commitment | `commit_funds`, `initiate_payment`, `disburse`, `book_financial_commitment` |

Adding one to satisfy a demo would turn the build red. The rules were written in Week 2 in
anticipation of this week, and they pass today because the functions do not exist.

Three further capabilities are absent by design rather than by rule name. **No tool approves or
rejects**: the manager's decision is a screen action, POL-004-C02, and giving it a tool would
put an approval one function call away from the agent. **No tool edits a master record**: the
inventory snapshot and supplier register are read-only to every tool here, so an eligibility
problem cannot be solved by changing the register. **No tool moves a requisition beyond
`DRAFT`**, which is why `create_requisition_draft` names `FORBIDDEN_TRANSITION` rather than
silently ignoring a status it will not honour.

### 9. Failure behaviour across the catalogue

The Week 4 brief names four categories to test. Each has a defined behaviour in every tool, so
this table doubles as the test matrix for the failure and authorization evidence
([`../evaluation/tool-failure-tests.md`](../evaluation/tool-failure-tests.md), issue #17).

| Tool | Missing parameters | Unauthorized requests | Unavailable services | Unexpected tool responses |
|---|---|---|---|---|
| `check_reorder_need` | `MISSING_PARAMETER` on absent `review_date`; nothing read | Allow-listed for all roles; `TOOL_NOT_ALLOWED` when off the step's list | `DATA_SOURCE_UNAVAILABLE`; no assumed stock figure | Snapshot failing a Requirement 1.3 invariant is rejected whole as `DATA_INTEGRITY_ERROR` |
| `check_supplier_eligibility` | `MISSING_PARAMETER` when neither identifier list is given | As above | `DATA_SOURCE_UNAVAILABLE`; **no supplier reported eligible** | A malformed register entry fails the read rather than defaulting a status |
| `compare_quotations` | `MISSING_PARAMETER` on `sku` or `reorder_quantity` | As above | `DATA_SOURCE_UNAVAILABLE`; no partial ranking | An offer missing a landed-cost field is excluded with the field named, never imputed |
| `create_requisition_draft` | `MISSING_PARAMETER`, and `MISSING_COMPONENT` at compilation; nothing written | `UNAUTHORIZED_ROLE` for the Manager and for an unconfirmed agent call; `FORBIDDEN_TRANSITION` for any status beyond `DRAFT` | `DATA_SOURCE_UNAVAILABLE`; no identifier issued, no sequence gap | A response that does not conform to its output schema is discarded, not relayed |

Four behaviours hold across all of them.

**Fail closed.** Every unavailable-service row denies rather than permits. An unreadable
supplier register reports nobody eligible; it does not report everybody eligible.

**Fail whole.** No tool returns a partial result. This mirrors the "reject, do not salvage" rule
`schema.validate` applies to model output under Requirement 3.3.

**Validate the response, not only the request.** The orchestration layer checks every tool
response against its output schema before relaying it. A tool that returned an unexpected shape
is treated exactly as a model that returned non-conforming JSON: the result is discarded and the
step fails visibly.

**A refusal states its rule.** Every code above maps to a numbered requirement or a clause
identifier, so an officer reading a refusal can see which rule produced it, and the Week 7
adversarial cases can assert on the reason rather than on the failure alone.

### 10. Data dependencies

Three of the four tools read operational records. Those records did not exist before this week:
`.env.example` had declared `INVENTORY_DATA_PATH`, `QUOTATIONS_DATA_PATH` and
`SUPPLIERS_DATA_PATH` since Week 2, but `knowledge/data/` was empty and no code read those
variables. Charter section 7 puts the dataset in scope; no weekly deliverable row and no issue
assigned it. It was created alongside this catalogue so the contracts specify against data that
exists.

| File | Records | Read by | Register ID | Record schema |
|---|---|---|---|---|
| [`knowledge/data/inventory.csv`](../../knowledge/data/inventory.csv) | 48 SKUs | `check_reorder_need` | `DAT-001` | [`inventory-record.json`](schemas/inventory-record.json) |
| [`knowledge/data/suppliers.json`](../../knowledge/data/suppliers.json) | 8 suppliers | `check_supplier_eligibility` | `DAT-002` | [`supplier-record.json`](schemas/supplier-record.json) |
| [`knowledge/data/quotations.json`](../../knowledge/data/quotations.json) | 36 quotations | `compare_quotations` | `DAT-003` | [`quotation-record.json`](schemas/quotation-record.json) |

This meets the charter's figures of forty to sixty SKUs, six to ten suppliers and thirty to
fifty quotations. Provenance is registered in the same
[`source-register.csv`](../../knowledge/source-register.csv) as the corpus, under the same
permission basis and checksum rule; shapes and seeded cases are documented in
[`knowledge/data/README.md`](../../knowledge/data/README.md).

**Review status is `pending_review`, not `approved`.** The corpus documents were human-reviewed
on 17 September 2026. These three files were authored on 23 September 2026 and that review has
not happened, so they are marked pending rather than approved.

Two properties of the data matter to the contracts. **No computed figure is stored** — no
reorder quantity, no landed cost, no rank — because Requirements 1.4 and 6.1 compute all of them
at call time and a stored total would carry unknown provenance. And the records **seed a case
for every branch** the tools specify: eleven SKUs at or below reorder point including one
exactly at it and one at zero stock; a supplier for each exclusion reason; a deliberate
name-collision pair; an expired offer; an unstated VAT treatment; a coil with no weight and a
reel with no length; a per-tonne price with a stated conversion factor; and a USD offer with
freight quoted separately.

### 11. Traceability

| Tool | Requirements | Policy clauses | Success criteria |
|---|---|---|---|
| `check_reorder_need` | 1.2, 1.3, 1.4, 1.5 | PRO-001-C01, PRO-001-C02 | S2 |
| `check_supplier_eligibility` | 4.1, 4.2, 4.3, 4.4 | POL-002-C01 to C04, POL-005-C03 | S6, S7 |
| `compare_quotations` | 5, 6.1 to 6.6 | POL-001-C01 to C04, POL-003-C01 to C04, SPEC-001-C01, SPEC-001-C02, SPEC-003-C01 | S1, S2 |
| `create_requisition_draft` | 9.1 to 9.5, 10.1, 14.1, 14.3 | POL-004-C01 to C04, REQ-001 | S7, S8 |
| Allow-list and role injection (section 3) | 12, 14.5 | POL-004-C01, POL-004-C03 | S8 |
| Prohibited tools (section 8) | 14.1, 14.2 | POL-004-C04 | S8 |

S2, S7 and S8 are the charter's hard gates: zero financial arithmetic errors, zero requisitions
beyond `DRAFT` without human action, zero prohibited actions under adversarial prompts. Every
tool above traces to at least one of them.

### 12. For the implementers

Naming that activates existing CI with no workflow change. The `tool-tests` job in
[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) already watches
`src/**/tools/**`, `src/**/*tool*`, `tests/test_tools*.py` and `tests/test_authorization*.py`,
and is inert only because no such file exists.

| Artefact | Path |
|---|---|
| Tool package | `src/procurement_agent/tools/` |
| Tool tests | `tests/test_tools_<tool>.py` |
| Authorization tests | `tests/test_authorization_<area>.py` |
| Trace log | `evidence/traces/tool-runs.jsonl` |

Reusable seams already in the package: `guards.scan` and `guards.suppress` for output scanning;
`ExtractionConfig.fingerprint_digest()` for provenance; the `runlog.RunLog` JSONL idiom for the
trace; `dotenv.load_env_file` for the data-path variables; and the `ValueError` / `RuntimeError`
split the existing error classes follow, where a usage error subclasses `ValueError` and an
environmental one subclasses `RuntimeError`. The charter's zero-runtime-dependency rule holds:
these schemas are shaped so a hand-written validator can enforce them, exactly as
`schema.validate` does today, and `jsonschema` stays a checking convenience rather than a
dependency.

### 13. Open items

**The tool count is at the charter ceiling.** Four tools is the upper bound in charter section
7. Adding a fifth — a policy-retrieval tool, or the deferred document-conversion tool — needs a
charter amendment, not just a new file here.

**Requirement 4 was amended to match this tool. Resolved.** Requirement 4 named only
`AVL_ABSENT`, `BLACKLISTED` and `EXPIRED`, which cannot express the suspension bar in
POL-002-C02 or the category bar in POL-002-C03. Requirements Document **v1.2** (23 September
2026) widens 4.1 to name all four checks, adds `SUSPENDED` and `OUT_OF_CATEGORY` to the 4.3
vocabulary, and adds 4.6 for the POL-002-C04 name-resemblance rule this tool reports through
`similar_registered_names` and enforces through `NAME_DISCREPANCY` exclusion until officer
clearance is recorded. See the Amendment History in
[`user-stories.md`](../requirements/user-stories.md).

**The datasets are not yet human-reviewed.** `DAT-001` to `DAT-003` are `pending_review`.
Someone other than their author should check them before the Week 7 evaluation depends on them.

**`docs/README.md` disagreed with the issue tracker.** The Week 4 table named different owners
from GitHub issues #15 to #19. The Week 4 rows are corrected in this branch to match the tracker.
**Resolved (29 September 2026).** The index rows for Weeks 5 to 8 were reconciled in commit
`e93a8af`, and the per-file Owner headers of the Week 5 to 7 stubs now match the index and issues
#20 to #35.

**Three tools have no implementation yet.** This document is a contract, not a demonstration.
The working demonstration is issue #16 and the failure and authorization evidence is issue #17;
both are now unblocked by the datasets in section 10.
