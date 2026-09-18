# Corpus Source Register

**SME Procurement-Preparation Agent | Group Y**  
Version 1.0 | 18 September 2026  
Machine-readable companion: [`source-register.csv`](source-register.csv)  
Corpus root: [`corpus/`](corpus/)

## 1. Purpose

This register records the controlled document set used for policy retrieval, quotation extraction and evaluation. It states what each source is, where it lives, on what basis it may be used, and which sources are eligible for the RAG index.

The charter specifies a versioned corpus of ten to fifty documents covering procurement policy, supplier terms and process notes. This set contains **23** documents, all team-authored synthetic records for the fictional Kampala distributor **Atlantic Hardware**.

No live supplier, personal, restricted or confidential information is included. Documents are authorised solely as academic test data for this project.

## 2. Provenance model

Every source is identified by a stable `source_id` (for example `POL-001`). Provenance is stored in three places that must agree:

| Store | Role |
|---|---|
| YAML front matter on each Markdown file | Identity, version, review status, intended use |
| `knowledge/source-register.csv` | Canonical register: path, licence, verifier, SHA-256 |
| This document | Human-readable index, indexing rules and seeded evaluation defects |

`src/procurement_agent/rag/corpus.py` loads a document only if it is registered, its version matches the CSV, and its content hash matches the registered checksum. A mismatch is an error, not a skip: an index built from an unreviewed edit would ground answers in text that was never approved.

Checksums are SHA-256 of the file with line endings normalised to `\n`, so a Windows checkout with `core.autocrlf` does not invalidate a reviewed hash.

Permission basis for every row: team-created synthetic data authorised for this academic project. Review of the current files was completed on 17 September 2026; verifier names and checksums are in the CSV.

## 3. Indexing boundary

Only **policies**, **procedures** and **product specifications** are embedded (12 documents, 45 citable clauses). Those folders state rules that apply to items on a requisition, and every clause is marked with a heading of the form `## POL-001-C02 …`. Requirement 7 (policy retrieval) uses that set.

The remaining 11 documents stay on this register and in the repository, but are not embedded:

| Category | Reason |
|---|---|
| Quotations | Extraction inputs. QUO-005 carries a prompt-injection payload that must not be supplied as policy context. |
| Supplier terms | No clause identifiers, so nothing in them can be cited. Supplier records are reached through a dedicated tool. |
| Requisition guides | Apply to every justification regardless of item; they belong in the drafting prompt, not item-driven retrieval. |

## 4. Register

| ID | Title | Category | Path | Version |
|---|---|---|---|---|
| POL-001 | Competitive Quotation Policy | policy | `knowledge/corpus/policies/POL-001.md` | 1.0 |
| POL-002 | Approved Supplier Policy | policy | `knowledge/corpus/policies/POL-002.md` | 1.0 |
| POL-003 | Quotation Evaluation Policy | policy | `knowledge/corpus/policies/POL-003.md` | 1.0 |
| POL-004 | Delegation of Procurement Authority | policy | `knowledge/corpus/policies/POL-004.md` | 1.0 |
| POL-005 | Quotation Completeness and Validity Policy | policy | `knowledge/corpus/policies/POL-005.md` | 1.0 |
| PRO-001 | Weekly Reorder Review Procedure | procedure | `knowledge/corpus/procedures/PRO-001.md` | 1.0 |
| PRO-002 | Quotation Receipt and Filing Procedure | procedure | `knowledge/corpus/procedures/PRO-002.md` | 1.0 |
| PRO-003 | Quotation Comparison Procedure | procedure | `knowledge/corpus/procedures/PRO-003.md` | 1.0 |
| PRO-004 | Conflict of Interest Disclosure Procedure | procedure | `knowledge/corpus/procedures/PRO-004.md` | 1.0 |
| SPEC-001 | Cement and Masonry Product Specifications | product_specification | `knowledge/corpus/product-specifications/SPEC-001.md` | 1.0 |
| SPEC-002 | Hand Tools and Safety Equipment Specifications | product_specification | `knowledge/corpus/product-specifications/SPEC-002.md` | 1.0 |
| SPEC-003 | Electrical and Plumbing Product Specifications | product_specification | `knowledge/corpus/product-specifications/SPEC-003.md` | 1.0 |
| QUO-001 | Clean Table UGX Quotation | quotation | `knowledge/corpus/quotations/QUO-001.md` | 1.0 |
| QUO-002 | Carton VAT Inclusive Quotation | quotation | `knowledge/corpus/quotations/QUO-002.md` | 1.0 |
| QUO-003 | USD Freight Separate Quotation | quotation | `knowledge/corpus/quotations/QUO-003.md` | 1.0 |
| QUO-004 | Minimal Quotation with Missing Fields | quotation | `knowledge/corpus/quotations/QUO-004.md` | 1.0 |
| QUO-005 | Adversarial Embedded Instruction Quotation | quotation | `knowledge/corpus/quotations/QUO-005.md` | 1.0 |
| QUO-006 | Expired Validity Quotation | quotation | `knowledge/corpus/quotations/QUO-006.md` | 1.0 |
| REQ-001 | Purchase Requisition Draft Template | requisition | `knowledge/corpus/requisitions/REQ-001.md` | 1.0 |
| REQ-002 | Procurement Justification Writing Guide | requisition | `knowledge/corpus/requisitions/REQ-002.md` | 1.0 |
| SUP-001 | Kampala TradeWorks Supplier Terms | supplier_terms | `knowledge/corpus/supplier-terms/SUP-001.md` | 1.0 |
| SUP-002 | Lakeview Building Materials Supplier Terms | supplier_terms | `knowledge/corpus/supplier-terms/SUP-002.md` | 1.0 |
| SUP-003 | Nakasero Electrical and Plumbing Supplier Terms | supplier_terms | `knowledge/corpus/supplier-terms/SUP-003.md` | 1.0 |

Origin, dates, licence, verifier and checksum for each row are in `knowledge/source-register.csv`.

## 5. Seeded evaluation defects

A uniformly clean corpus would not expose retrieval or extraction failures. The following defects are present by design:

| Defect | Location | Policy it exercises |
|---|---|---|
| Mixed VAT treatment | QUO-001 exclusive; QUO-002 inclusive; QUO-003 exclusive; QUO-006 inclusive | POL-003-C03 |
| Mixed units of measure | QUO-002 cartons/reams/boxes; SPEC-001 tonne vs 50 kg bag; coil weight | POL-003-C02 |
| Mixed currency | QUO-003 USD with freight stated separately | POL-003-C01 |
| Missing commercial fields | QUO-004 omits VAT, validity, delivery and unit of measure | POL-005-C01, POL-005-C02 |
| Expired validity | QUO-006 valid until 15 July 2026 | POL-005-C03 |
| Embedded instruction | QUO-005 | Quotation text is untrusted data, never policy |
| Coverage gap | Specifications cover cement, tools, electrical and plumbing only | Deliberately unanswerable retrieval cases |

## 6. Limitations

- Twenty-three documents are sufficient for current retrieval and extraction evaluation. They are not the later inventory (forty to sixty SKUs) or quotation (thirty to fifty) datasets.
- Supplier-term files describe fictional vendors. They do not confer Approved Vendor List status.
- An edit to a reviewed file requires a new checksum and a version bump in both the Markdown front matter and the CSV, or loading fails.
- Restricted, personal or live commercial data must not be added to this folder.
