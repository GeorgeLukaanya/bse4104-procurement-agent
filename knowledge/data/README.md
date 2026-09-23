# Operational data

Synthetic operational records for the fictional **Atlantic Hardware**. These are the
current-application data that the Week 4 tools read. The policy corpus under
[`knowledge/corpus/`](../corpus/) states the *rules*; this folder holds the *records* those
rules are applied to.

Do not commit restricted, personal, confidential or live supplier data. Do not send that data
to an external model.

| File | Records | Read by | Provenance |
|---|---|---|---|
| [`inventory.csv`](inventory.csv) | 48 SKUs | `check_reorder_need` | `DAT-001` |
| [`suppliers.json`](suppliers.json) | 8 suppliers | `check_supplier_eligibility` | `DAT-002` |
| [`quotations.json`](quotations.json) | 36 quotations | `compare_quotations` | `DAT-003` |

Full provenance for each file is recorded in [`../source-register.csv`](../source-register.csv),
alongside the corpus documents. The tool contracts these files satisfy are specified in
[`docs/architecture/tool-catalogue.md`](../../docs/architecture/tool-catalogue.md).

## Why this folder exists

`.env.example` has declared `INVENTORY_DATA_PATH`, `QUOTATIONS_DATA_PATH` and
`SUPPLIERS_DATA_PATH` since Week 2, and Project Charter section 7 puts "synthetic datasets of
roughly forty to sixty SKUs, six to ten suppliers, and thirty to fifty quotations" in scope. No
weekly deliverable row and no issue assigned that dataset to anyone, and two of the four Week 4
tools cannot be demonstrated without it. It was created with the tool catalogue so that the
contracts are specified against data that exists.

## Shapes

### `inventory.csv`

`sku, item_name, category, unit_of_measure, current_stock, reorder_point, target_stock_level,
unit_cost_ugx, location, last_counted`

Every row satisfies the Requirement 1.3 invariants: no negative quantity, and
`target_stock_level` strictly greater than `reorder_point`. Reorder quantity is never stored —
Requirement 1.4 derives it as `target_stock_level - current_stock` at call time.

Eleven SKUs sit at or below their reorder point, so a weekly review is non-trivial. Two are
deliberate edge cases: `AH-CM-001` is *exactly at* its reorder point, which "at or below" must
flag, and `AH-HT-002` is at zero stock.

Three of the flagged rows resolve to the quantities already used by
[`fixtures/requisitions/weekly-reorder.json`](../../fixtures/requisitions/weekly-reorder.json) —
120 bags of cement, 25 kg of binding wire and 40 safety helmets — so the Week 3 retrieval
fixture and this dataset describe the same review. That fixture's fourth item, diesel, is
deliberately absent from the catalogue and stays absent: it exercises the item-absence path.

### `suppliers.json`

Membership of this file **is** the Approved Vendor List of POL-002-C01. A supplier named on a
quotation but absent here resolves to `AVL_ABSENT`; `Victoria Trade Links` (`SUP-099`) exists
only in `quotations.json` for exactly that purpose.

`avl_status` is one of `ACTIVE`, `SUSPENDED`, `BLACKLISTED`. Per POL-002-C02 a suspension takes
precedence over an older approved status, which is why `status_effective_date` is carried
separately from `approval_date`.

The register seeds one supplier for each exclusion reason, and `SUP-007 Lakeview Building
Supplies` is deliberately named close to `SUP-002 Lakeview Building Materials` to exercise the
POL-002-C04 discrepancy rule. They are distinct entities and must never be merged.

### `quotations.json`

Quotation-level and item-level field names mirror the Normalised Quotation contract in
[`src/procurement_agent/schema.py`](../../src/procurement_agent/schema.py), so a record read
from this file and a record extracted from a document by the Week 2 pipeline have the same
shape. Provenance keys (`quotation_id`, `supplier_id`, `sku`, `source_document`,
`unit_conversion_factor`, `note`) are additional.

**No computed figure is stored.** There is no landed cost, no VAT amount, no converted total and
no rank. Requirement 6.1 assigns that arithmetic to the deterministic comparison at call time,
and storing a precomputed total would put a figure of unknown provenance in front of an
approver.

Six records carry a `source_document` pointing into `knowledge/corpus/quotations/`, so the same
offer can be reached either as a structured record or through document extraction. One of those
sources, `QUO-005`, contains an embedded instruction. It is held as **data, never as an
instruction**: nothing in a quotation may invoke a tool, per Requirement 14.5.

Seeded cases: an expired validity date (`QT-016`), an unstated VAT treatment (`QT-021`), a coil
with no stated weight (`QT-006`), a reel with no stated length (`QT-025`), a per-tonne price
with a stated conversion factor (`QT-002`), a VAT-inclusive carton price (`QT-012`), and a USD
offer with freight quoted separately (`QT-015`).
