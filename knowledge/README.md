# Knowledge

Corpus metadata and provenance for the controlled RAG source set.

Do not commit restricted, personal, confidential or live supplier data. Do not
send that data to an external model.

| File | Purpose |
|---|---|
| [`source-register.md`](source-register.md) | Human-readable corpus provenance register |
| [`data/`](data/) | Operational records read by the Week 4 tools — inventory, suppliers, quotations |

## Controlled corpus

All corpus files are synthetic academic test data for Atlantic Hardware. The detailed provenance for each file is recorded in [`source-register.csv`](source-register.csv).

| Source ID | File | Category | Description |
|---|---|---|---|
| POL-001 | [`POL-001.md`](corpus/policies/POL-001.md) | Policy | States how many quotations are needed for different purchase values. |
| POL-002 | [`POL-002.md`](corpus/policies/POL-002.md) | Policy | Explains which suppliers Atlantic Hardware may buy from. |
| POL-003 | [`POL-003.md`](corpus/policies/POL-003.md) | Policy | Explains how supplier quotations should be compared. |
| POL-004 | [`POL-004.md`](corpus/policies/POL-004.md) | Policy | Defines procurement roles and who may approve a requisition. |
| POL-005 | [`POL-005.md`](corpus/policies/POL-005.md) | Policy | Lists the information a valid quotation should contain. |
| PRO-001 | [`PRO-001.md`](corpus/procedures/PRO-001.md) | Procedure | Describes the weekly stock review and reorder process. |
| PRO-002 | [`PRO-002.md`](corpus/procedures/PRO-002.md) | Procedure | Explains how quotations are received, checked and stored. |
| PRO-003 | [`PRO-003.md`](corpus/procedures/PRO-003.md) | Procedure | Describes how quotations are compared and recommended. |
| PRO-004 | [`PRO-004.md`](corpus/procedures/PRO-004.md) | Procedure | Explains what to do when someone has a conflict of interest. |
| SPEC-001 | [`SPEC-001.md`](corpus/product-specifications/SPEC-001.md) | Product specification | Gives specifications for cement and masonry products. |
| SPEC-002 | [`SPEC-002.md`](corpus/product-specifications/SPEC-002.md) | Product specification | Gives specifications for hand tools and safety equipment. |
| SPEC-003 | [`SPEC-003.md`](corpus/product-specifications/SPEC-003.md) | Product specification | Gives specifications for electrical and plumbing products. |
| QUO-001 | [`QUO-001.md`](corpus/quotations/QUO-001.md) | Quotation | A complete quotation with prices in UGX. |
| QUO-002 | [`QUO-002.md`](corpus/quotations/QUO-002.md) | Quotation | A quotation with carton prices that include VAT. |
| QUO-003 | [`QUO-003.md`](corpus/quotations/QUO-003.md) | Quotation | A quotation in USD with a separate freight cost. |
| QUO-004 | [`QUO-004.md`](corpus/quotations/QUO-004.md) | Quotation | An incomplete quotation with missing information. |
| QUO-005 | [`QUO-005.md`](corpus/quotations/QUO-005.md) | Quotation | A quotation containing an unsafe embedded instruction. |
| QUO-006 | [`QUO-006.md`](corpus/quotations/QUO-006.md) | Quotation | A quotation whose validity date has expired. |
| REQ-001 | [`REQ-001.md`](corpus/requisitions/REQ-001.md) | Requisition | Shows the required parts of a draft purchase requisition. |
| REQ-002 | [`REQ-002.md`](corpus/requisitions/REQ-002.md) | Requisition | Explains how to write a procurement justification. |
| SUP-001 | [`SUP-001.md`](corpus/supplier-terms/SUP-001.md) | Supplier terms | Describes the products and terms offered by Kampala TradeWorks. |
| SUP-002 | [`SUP-002.md`](corpus/supplier-terms/SUP-002.md) | Supplier terms | Describes the products and terms offered by Lakeview Building Materials. |
| SUP-003 | [`SUP-003.md`](corpus/supplier-terms/SUP-003.md) | Supplier terms | Describes the products and terms offered by Nakasero Electrical and Plumbing. |
