# 15-case RAG Evaluation

**SME Procurement-Preparation Agent | Group Y**  
Version 1.0 | 18 September 2026  
Pipeline: Requirement 7 policy retrieval (`src/procurement_agent/rag/`)  
Index: `BAAI/bge-small-en-v1.5`, top 5, general cutoff 0.50, item cutoff 0.58  
Corpus: 12 indexed documents, 45 clauses (`knowledge/source-register.md`)

## 1. Purpose

This evaluation checks whether the RAG pipeline retrieves the right clauses, states absence instead of inventing a rule, and withholds ungrounded citations. It covers answerable, partially answerable and deliberately unanswerable questions, and records at least three retrieval or grounding failures with causes.

A case **Passes** when every expected clause is retrieved (or the expected absence note is returned), no out-of-corpus specification is treated as a hit, and any generation step cites only clauses supplied for that item. It **Fails** when a wrong specification is kept, a required clause is missing, an absence is not stated, or a citation is ungrounded.

## 2. Method

Three evidence sources. The case table says which one applies.

| Source | What it measures | Where it lives |
|---|---|---|
| Live requisition, 17 September 2026 | Retrieval + Gemini 3.1 Flash-Lite + citation check, one call, 42.01 s | [`evidence/traces/rag-weekly-reorder-run.txt`](../../evidence/traces/rag-weekly-reorder-run.txt), [`fixtures/requisitions/weekly-reorder.json`](../../fixtures/requisitions/weekly-reorder.json) |
| Retrieval calibration, same embedder | Best overall score and best specification score for nine purchases | Table in [`retriever.py`](../../src/procurement_agent/rag/retriever.py) |
| Citation tests, offline | Grounding of supplied, missing, invented, wrong-version and injection mentions | [`tests/test_rag_citations.py`](../../tests/test_rag_citations.py) |

Generation was not re-run for cases that have only calibration scores. Those cases judge retrieval only.

Query form (Requirement 7.1): `Purchase of {item}, category {category}, estimated total {currency amount}`.

## 3. Cases

| Case | Kind | Question / request | Expected | Actual | Result |
|---|---|---|---|---|---|
| TC-01 | Answerable | 120 bags of cement, building materials, UGX 4,140,000. Which quotation-count and cement comparison rules apply? | Keep POL-001-C02 (standard band) and SPEC-001-C01. Cite only supplied clauses. Do not invent a cement rule. | Live. General: POL-001-C03 0.616, **C02 0.576**, C01 0.557, POL-003-C01 0.551, PRO-001-C03 0.528. Item: **SPEC-001-C01 0.684**, SPEC-001-C03 0.585. Gemini cited C02, C01-spec, C03-spec, POL-003-C01, PRO-001-C03. Citation check passed. | Pass |
| TC-02 | Answerable | 25 kg binding-wire coils, building materials, UGX 900,000. Which comparison rule applies to coils? | Keep SPEC-001-C02 (coil weight). Do not keep cement or cable specifications. | Live. SPEC-001-C02 0.727 was first, but SPEC-001-C01 (cement) 0.615 and SPEC-003-C01 (cable) 0.602 were also kept (≥ 0.58). Gemini cited C02 and did not cite the extras. Citation check passed. | Fail |
| TC-03 | Answerable | 40 safety helmets, safety equipment, UGX 800,000. Which protective-equipment rules apply? | Keep SPEC-002-C02 (helmets per piece / rating). | Live. Item: SPEC-002-C02 0.608, SPEC-002-C03 0.584. Gemini cited both plus POL-001-C02. Citation check passed. | Pass |
| TC-04 | Partial | Diesel for the delivery truck, fuel, UGX 1,000,000. Which product specification applies? | General quotation rules may apply. No product specification. Explicit absence note. Do not attach a cement or cable spec. | Live. General rules kept. Item rules none. Note: *No product specification in the Policy Corpus was found for diesel for the delivery truck (fuel).* Gemini restated the note. Citation check passed. | Pass |
| TC-05 | Answerable | Electrical cable, electrical, catalogue purchase. Is there a matching specification? | Best specification score ≥ 0.58, on SPEC-003 (cable / metre). | Calibration: best specification **0.740**. Above the item cutoff. | Pass |
| TC-06 | Answerable | PVC pipe fittings, plumbing. Is there a matching specification? | Best specification score ≥ 0.58, on SPEC-003 (fittings). | Calibration: best specification **0.693**. | Pass |
| TC-07 | Partial | Return flights to Nairobi, travel, UGX 3,000,000. Is there a product specification? | General rules may apply. Specification score &lt; 0.58 and an absence note. Must not retrieve SPEC-001 (cement). | Calibration: best specification **0.508**, below 0.58. Without the item cutoff, this purchase was offered the cement specification. | Pass |
| TC-08 | Partial | Software licence, IT. Is there a product specification? | Same as TC-07. | Calibration: best specification **0.529**. | Pass |
| TC-09 | Partial | Staff catering. Is there a product specification? | Same as TC-07. | Calibration: best specification **0.483**. | Pass |
| TC-10 | Answerable | Same cement purchase as TC-01. Retrieval must rank the applicable monetary band first. | For UGX 4,140,000, POL-001-C02 should outrank POL-001-C03 (≥ 5,000,000). | Live. C03 scored **0.616**, C02 **0.576**. Embeddings match the quotation-count topic, not the figure. `top_k` 5 still kept C02; Gemini cited the right band. | Fail |
| TC-11 | Unanswerable (item) | Goods the catalogue does not cover: diesel (TC-04). Must the model invent a fuel specification? | Absence note. No invented SPEC-* citation. | Live diesel run: no item clauses, note shown, Gemini did not invent a fuel spec. | Pass |
| TC-12 | Unanswerable (grounding) | For the cement purchase, cite POL-002-C01 (Approved Vendor List). That clause exists but was not retrieved. | Reject: not among clauses supplied for the item. | Offline: `validate_citations` reports `not_retrieved` for POL-002-C01. The item would be withheld. | Pass |
| TC-13 | Unanswerable (grounding) | Cite POL-009-C01 (does not exist). | Reject invented clause. | Offline: `not_retrieved` for POL-009-C01. | Pass |
| TC-14 | Unanswerable (grounding) | Cite POL-001-C02 at version 2.0 (register is 1.0). | Reject version mismatch; do not resolve the clause. | Offline: `version_mismatch`; cited_clauses empty. | Pass |
| TC-15 | Unanswerable (grounding) | Ground the answer in QUO-005 (adversarial quotation, not indexed). | Reject any mention of QUO-005. | Offline: `unretrieved_mention` for QUO-005. | Pass |

Kinds: **Answerable** = catalogue goods with a specification. **Partial** = general rules exist, no item specification. **Unanswerable** = no matching item rule, or a citation the item was not given.

## 4. Retrieval and grounding failures

At least three genuine failures. Passing the citation check does not cancel a retrieval miss.

### F1. Unrelated specifications kept for binding wire (TC-02)

**Cause.** Item cutoff 0.58 sits in a narrow gap. Binding wire is in SPEC-001 with cement, and the query is a building-materials purchase, so SPEC-001-C01 (0.615) and SPEC-003-C01 (0.602) clear the cutoff.

**Effect.** The model is shown cement and cable rules for wire. On this run it did not cite them. That is luck, not a guarantee.

**Follow-up.** Raise the item cutoff, or restrict item search to the requested category, and re-measure TC-02, TC-05 and TC-06.

### F2. Adjacent quotation-count band outranks the applicable one (TC-10)

**Cause.** `POL-001-C01/C02/C03` share wording. The embedder cannot place UGX 4,140,000 in a band. C03 ranked above C02 on cement, helmets and diesel.

**Effect.** A `top_k` of 3 would have dropped C02 on the cement purchase. Generation chose the right band this time.

**Follow-up.** Keep `top_k` ≥ 5 until band selection is deterministic (for example, filter by `estimated_total` before search).

### F3. Foreign-currency rule cited on UGX items (live run, TC-01–TC-04)

**Cause.** POL-003-C01 is retrieved for every purchase (scores 0.551–0.616) because every query is a requisition. Gemini treated “applies to all purchase requisitions regarding currency” as a reason to cite it on UGX-only items.

**Effect.** Every citation was still in the supplied set, so nothing unsupported was shown. Precision is wrong: the clause is about foreign-currency quotations.

**Follow-up.** Tighten the grounding prompt so POL-003-C01 is cited only when a non-UGX figure is present, and add a case with a USD total.

### Related observations (not counted as extra failures)

- Requirement 7.1 allows 30 seconds. The recorded requisition took **42.01 s** on one Gemini call. An earlier uncommitted run of the same file took 6.29 s. Provider latency, not retrieval.
- SPEC-001-C03 scored 0.585 on cement, 0.005 above the item cutoff. The gap used to set 0.58 is thin.

## 5. Summary

| Set | n | Pass | Fail |
|---|---|---|---|
| Answerable catalogue goods | 6 | 4 (TC-01, TC-03, TC-05, TC-06) | 2 (TC-02 extra specs; TC-10 band rank) |
| Partial / no specification | 4 | 4 (TC-04, TC-07, TC-08, TC-09) | 0 |
| Unanswerable / grounding guards | 5 | 5 (TC-11–TC-15) | 0 |
| **Total** | **15** | **13** | **2** |

Citation validation held on the live requisition (4 of 4 items shown, every citation supplied). The item cutoff prevented the airline-ticket → cement match (TC-07). The two fails and F3 are precision problems: extra neighbours in the item search, band ranking, and over-citation of the currency clause.

Offline suite for this layer: `pytest tests/test_rag_*.py` (no API key, no network, no model download).
