# Working Demonstration of Tools

| Field | Value |
|---|---|
| Week | 4 |
| Owner | Nannyombi Shakiran |
| Due | 25 September 2026 |
| Status | Complete, awaiting team review |
| Path | `docs/architecture/working-tools.md` |

## Brief requirement

Write-up of a working demonstration of at least two tools/functions called through the application/orchestration layer. Link the code, a run example, and evidence in `evidence/`.

## Write-up

### What it does

Four deterministic tools now run through one orchestration entry point. None of them calls the model, and the model never calls one directly — `dispatch.invoke` does, with the caller's role injected from the session rather than from the payload.

| Tool | Charter name | Side effect |
|---|---|---|
| `check_reorder_need` | inventory-status | none |
| `check_supplier_eligibility` | supplier-record | none |
| `compare_quotations` | deterministic comparison calculator | none |
| `create_requisition_draft` | requisition-draft | one `DRAFT` record in a local store |

The brief asked for at least two tools, including one that retrieves current application data and one low-risk write. The first three read `knowledge/data/`. The fourth writes `var/requisitions.jsonl` (git-ignored) and nothing else: no supplier contact, no purchase order, no status beyond `DRAFT`.

Contracts are the JSON Schema files in [`schemas/`](schemas/), not this prose. Behaviour follows [`tool-catalogue.md`](tool-catalogue.md).

### How to run it

Python 3.10 or later, from the repository root. No API key, no network, no extra install beyond the package itself.

```bash
pip install -e ".[dev]"
python -m procurement_agent.tools.cli check_reorder_need \
    --review-date 2026-09-25 --sku AH-CM-001 --sku AH-HT-012 --json
python -m procurement_agent.tools.cli check_supplier_eligibility \
    --category "cement and masonry" --as-of 2026-09-25 \
    --supplier-id SUP-002 --supplier-id SUP-006 --supplier-id SUP-007 --json
python -m procurement_agent.tools.cli compare_quotations \
    --sku AH-CM-001 --quantity 120 --date 2026-09-25 --json
python -m procurement_agent.tools.cli create_requisition_draft \
    --file fixtures/tools/cement-draft.json --json
```

`procurement-tools` is the same command once the package is installed. `--role` injects `PROCUREMENT_OFFICER` (default), `PROCUREMENT_MANAGER` or `AGENT`. It is never read from the JSON. `--confirm` is the officer gate for an `AGENT` draft call.

Exit `0` on `ok` or `no_result`, `1` on a refusal, `2` on usage error or an unavailable data source.

### The orchestration layer

```
payload (schema only)
        │
        ▼
dispatch.invoke
  1. reject unknown role
  2. reject a tool off the step allow-list   → TOOL_NOT_ALLOWED
  3. reject manager / unconfirmed agent on create_requisition_draft
     → UNAUTHORIZED_ROLE; nothing written
  4. validate the request whole               → invalid_input, no salvage
  5. run the deterministic function
  6. scan the result with guards.scan
  7. append evidence/traces/tool-runs.jsonl
```

Until Week 5 owns a state machine, the CLI allow-list is the full catalogue. Tests pass a per-step list to prove `TOOL_NOT_ALLOWED` never enters the tool.

### Recorded run — 24 September 2026

Four calls, officer role, no model. The machine log is one JSON object per line in [`evidence/traces/tool-runs.jsonl`](../../evidence/traces/tool-runs.jsonl) (same append-only idiom as extraction and RAG). Readable copies of that run:

- [`01-check_reorder_need.json`](../../evidence/traces/tools/01-check_reorder_need.json)
- [`02-check_supplier_eligibility.json`](../../evidence/traces/tools/02-check_supplier_eligibility.json)
- [`03-compare_quotations.json`](../../evidence/traces/tools/03-compare_quotations.json)
- [`04-create_requisition_draft.json`](../../evidence/traces/tools/04-create_requisition_draft.json)

Data fingerprints match DAT-001 / DAT-002 / DAT-003 in the source register.

**Reorder.** Cement is exactly at its reorder point (150/150) and is flagged; spirit level is below. Quantities are computed here: 120 bags and 47 pieces.

**Eligibility.** SUP-002 and SUP-007 are both `NAME_DISCREPANCY` (Lakeview Building Materials / Lakeview Building Supplies). SUP-006 is `BLACKLISTED`. Nobody in that set is eligible.

**Comparison** of 120 bags of cement. The blacklisted lowest headline price (QT-004, UGX 29,800/bag) is excluded. Both Lakeview offers are excluded under Requirement 4.6 until the officer records clearance. The remaining ranked row is the per-tonne offer, converted with the factor stated on the quotation:

| Rank | Offer | Normalised unit (UGX) | VAT | Delivery | Landed |
|---|---|---|---|---|---|
| 1 | QT-002 Bugolobi Hardware Supplies | 31,000 | 669,600 | 90,000 | 4,479,600 |

POL-001-C02 needs three eligible quotations in this band. One remains, so the tool returns `ok` with `INSUFFICIENT_QUOTATIONS` and `exception_required: true`. It does not block: POL-001-C04 is a recorded exception for the manager, not a silent halt.

**Draft.** `REQ-2026-001` is written with `status: DRAFT`, `human_confirmation_required: true`, and `routed_to` / `approved_by` / `decision` all null. The unresolved Lakeview discrepancy is carried on the record rather than dropped.

### Tests

`tests/test_tools_*.py` and `tests/test_authorization_tools.py`. The suite still runs with no API key and no network. Cases that matter for the brief:

| Case | Expected | Where |
|---|---|---|
| Cement exactly at reorder point | flagged, quantity 120 | `test_tools_reorder.py` |
| Empty reorder list | `no_result`, not an error | `test_tools_reorder.py` |
| Missing snapshot / bad checksum | `unavailable` / `DATA_INTEGRITY_ERROR` | `test_tools_reorder.py` |
| Every exclusion reason | `NAME_DISCREPANCY`, `BLACKLISTED`, `SUSPENDED`, `OUT_OF_CATEGORY`, `AVL_ABSENT`, `EXPIRED` | `test_tools_eligibility.py` |
| Missing register | nobody reported eligible | `test_tools_eligibility.py` |
| Landed-cost arithmetic on QT-002 | 31,000 / 4,479,600 | `test_tools_compare.py` |
| Missing VAT treatment | excluded, field named, never imputed | `test_tools_compare.py` |
| USD offer, no rate | `EXCHANGE_RATE_REQUIRED` | `test_tools_compare.py` |
| Manager creates a draft | `UNAUTHORIZED_ROLE`, nothing written | `test_authorization_tools.py` |
| Agent without confirmation | refused; with `--confirm`, runs as officer | `test_authorization_tools.py` |
| Status `APPROVED` | `FORBIDDEN_TRANSITION`, nothing written | `test_tools_draft.py` |
| `caller_role` on the payload | `INVALID_PARAMETER`; the injected role wins | `test_authorization_tools.py` |

### Where this differs from the catalogue example

The catalogue's `compare_quotations` example ranks QT-001 (Lakeview Building Materials) and excludes only QT-003. Requirement 4.6 and section 5 of the same catalogue mark **both** lookalike names `NAME_DISCREPANCY` until the officer records clearance. The implementation follows 4.6 and the eligibility example: QT-001 is excluded too. The tonne conversion and the blacklist exclusion match the catalogue numbers exactly.

No recommendation field is emitted. Ranking is not awarding (POL-004-C04).

### Not this week

The tools are callable. They are not yet driven by a model tool-calling loop, a UI, or a Week 5 state model that would preserve a comparison so a retry skips it. Document conversion remains deferred. The updated architecture diagram is issue #18 and the failure-matrix write-up is issue #17; both can now run against this code.

### Code

| Path | Role |
|---|---|
| [`src/procurement_agent/tools/dispatch.py`](../../src/procurement_agent/tools/dispatch.py) | Orchestration: role, allow-list, confirmation gate |
| [`src/procurement_agent/tools/reorder.py`](../../src/procurement_agent/tools/reorder.py) | `check_reorder_need` |
| [`src/procurement_agent/tools/eligibility.py`](../../src/procurement_agent/tools/eligibility.py) | `check_supplier_eligibility` |
| [`src/procurement_agent/tools/compare.py`](../../src/procurement_agent/tools/compare.py) | `compare_quotations` |
| [`src/procurement_agent/tools/draft.py`](../../src/procurement_agent/tools/draft.py) | `create_requisition_draft` |
| [`src/procurement_agent/tools/cli.py`](../../src/procurement_agent/tools/cli.py) | Command line |
| [`evidence/traces/tool-runs.jsonl`](../../evidence/traces/tool-runs.jsonl) | Append-only machine log (one object per line) |
| [`evidence/traces/tools/`](../../evidence/traces/tools/) | Indented copies of the same recorded run |
