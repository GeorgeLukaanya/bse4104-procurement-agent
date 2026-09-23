# Tool schemas

Machine-readable contracts for the tools specified in
[`../tool-catalogue.md`](../tool-catalogue.md). The catalogue is the explanation; these files
are the contract a validator can enforce.

| Tool | Input | Output |
|---|---|---|
| `check_reorder_need` | [`check_reorder_need.input.json`](check_reorder_need.input.json) | [`check_reorder_need.output.json`](check_reorder_need.output.json) |
| `check_supplier_eligibility` | [`check_supplier_eligibility.input.json`](check_supplier_eligibility.input.json) | [`check_supplier_eligibility.output.json`](check_supplier_eligibility.output.json) |
| `compare_quotations` | [`compare_quotations.input.json`](compare_quotations.input.json) | [`compare_quotations.output.json`](compare_quotations.output.json) |
| `create_requisition_draft` | [`create_requisition_draft.input.json`](create_requisition_draft.input.json) | [`create_requisition_draft.output.json`](create_requisition_draft.output.json) |

Record shapes for the data the tools read:
[`inventory-record.json`](inventory-record.json) ·
[`supplier-record.json`](supplier-record.json) ·
[`quotation-record.json`](quotation-record.json).

## Dialect

JSON Schema draft 2020-12. These files are canonical.

The provider dialect is a projection of them, not a second contract. Gemini's `response_schema`
uses an uppercase type vocabulary (`"OBJECT"`, `"STRING"`, `"NUMBER"`, `"ARRAY"`) with
`nullable` in place of a union type, exactly as
[`schema.response_schema()`](../../../src/procurement_agent/schema.py) and
`rag.grounding.response_schema()` already write it. Where a function declaration is handed to
the model, it is derived from the input file here; the file is never rewritten to suit the
provider.

Every object sets `additionalProperties: false`. The package already rejects unexpected keys
rather than ignoring them, and a tool that quietly accepted an unknown field would give a
caller no signal that the field did nothing.

## Two deliberate omissions

**No `caller_role` in any input schema.** Authorization is not a parameter. The orchestration
layer injects the caller's role from the authenticated session, and it appears only in the
output `trace`. Requirement 14.5 treats document content as untrusted; if a role were a
model-facing field, text inside a quotation could ask for one.

**No computed figure in any record schema.** `inventory-record` has no reorder quantity and
`quotation-record` has no landed cost, because Requirements 1.4 and 6.1 compute both at call
time. A stored total would be a figure of unknown provenance in front of an approver.

## Checking them

```bash
pip install jsonschema
python - <<'EOF'
import glob, json
from jsonschema import Draft202012Validator as V
for path in sorted(glob.glob("docs/architecture/schemas/*.json")):
    V.check_schema(json.load(open(path)))
    print("ok", path)
EOF
```

`jsonschema` is a checking convenience and deliberately **not** a project dependency: the
charter fixes zero runtime dependencies, and the implementation validates by hand, as
[`schema.validate`](../../../src/procurement_agent/schema.py) already does.
