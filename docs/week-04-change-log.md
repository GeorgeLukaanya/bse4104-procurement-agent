# Week 4 Change Log — Tool Catalogue and Schemas

**SME Procurement-Preparation Agent | Group Y**
Author: Lukaanya George | Issue #15 | 23 September 2026
Branch: `ft-week-4-tool-catalogue` | Pull request #52, merged 23 September 2026

> **What this document is.** A record of every change made under issue #15 and the
> reason for each, written so that any team member can check the work without reading
> the diff. It is a baseline, not a deliverable.
>
> It does **not** replace two things it overlaps with. The formal record of AI-assisted
> decisions is the Week 4 entry in [`AI-ENGINEERING-LOG.md`](AI-ENGINEERING-LOG.md),
> required by brief section 6. The Week 4 progress report is
> [`weekly-reports/week-04.md`](weekly-reports/week-04.md), issue #19, owned by Sekyeza
> Elroy Nunda — this document is input to it, not a substitute for it.

---

## Summary

My assigned deliverable was the Tool Catalogue and tool/API schemas. I delivered
that, and three things followed from it: the operational dataset the tools read did
not exist and was unassigned, so I created it; an amendment to the Requirements
Document became necessary; and the deliverable index disagreed with the issue
tracker, so I reconciled it.

Twenty-six files changed. Nothing under `src/` or `tests/` — implementation is
issues #16 and #17.

---

## 1. The deliverable

### `docs/architecture/tool-catalogue.md`

The Week 4 brief asks for at least two tools defined with purpose, input schema,
output schema, authorization and failure behaviour, one of which retrieves current
application data or creates a low-risk simulated side effect. I specified four, in
thirteen sections.

| Tool | Charter section 1 name | Side effect |
| ----- | ----- | ----- |
| `check_reorder_need` | inventory-status tool | none, read-only |
| `check_supplier_eligibility` | supplier-record tool | none, read-only |
| `compare_quotations` | deterministic comparison calculator | none, pure computation |
| `create_requisition_draft` | requisition-draft tool | writes one record, in DRAFT |

**Why these four.** Project Charter section 1 already named six tools the agent may
use, and section 7 caps the build at "two to four tools with explicit schemas,
permissions and failure behaviour." Choosing four from the named six adds contracts
to an agreed list rather than widening scope. Document conversion is deferred because
charter section 9 excludes scans and OCR. Quotation retrieval is folded into
`compare_quotations`, which already selects the offers held for an item; a separate
lookup would spend one of four slots on a function containing no decision.

**Why policy retrieval is not listed.** Charter section 1 does not name it among the
tools the agent may call, and Week 3 delivered it as a pipeline the officer invokes
directly. It stays outside the tool allow-list until Week 6 decides whether to expose
it through the MCP-style interface.

### `docs/architecture/schemas/` — eleven JSON Schema files

Eight tool schemas, one input and one output per tool, plus three data record shapes,
plus a README recording the dialect decision.

**Why separate files rather than inline.** The brief asks for input schema and output
schema as artefacts. A file a validator can load is a contract; a fenced block in a
Word-processed document is a picture of one. This also avoids repeating a defect the
project already has: the Normalised Quotation schema in `prompts/quotation-extraction-v1.md`
section 6 is currently mangled italic text with escaped underscores, because it passed
through Google Docs.

**Why JSON Schema draft 2020-12 is canonical, not the Gemini dialect.** The provider
uses an uppercase type vocabulary with `nullable` instead of union types. The existing
code already derives that from a Python structure in `schema.response_schema()`, so
the pattern is established: one canonical contract, mechanically projected to whatever
the provider wants. Rewriting the contract to suit the provider would tie the
specification to one vendor.

---

## 2. The dataset — created because it was unowned

### `knowledge/data/` — 48 SKUs, 8 suppliers, 36 quotations

**Why I built it.** Three of the four tools read operational records. Those records did
not exist. `.env.example` had declared `INVENTORY_DATA_PATH`, `QUOTATIONS_DATA_PATH`
and `SUPPLIERS_DATA_PATH` since Week 2, and Project Charter section 7 puts the dataset
in scope at "roughly forty to sixty SKUs, six to ten suppliers, and thirty to fifty
quotations." No weekly deliverable row and no GitHub issue from #8 to #40 assigned it
to anyone. Without it, two of my four tools had no data source and issue #16, the
working demonstration, was blocked.

**Why it is consistent with the existing corpus.** The dataset uses the same fictional
business, Atlantic Hardware; the same three product categories as SPEC-001 to SPEC-003;
and the three suppliers named in SUP-001 to SUP-003. The three flagged items resolve to
120 bags of cement, 25 kg of binding wire and 40 safety helmets — exactly the quantities
`fixtures/requisitions/weekly-reorder.json` already used in Week 3, so the Week 3
retrieval fixture and this dataset describe the same weekly review.

**Why no computed figure is stored.** There is no reorder quantity, no landed cost and
no rank anywhere in the data. Requirement 1.4 computes reorder quantity as target minus
current, and Requirement 6.1 computes landed cost, both at call time. A stored total
would put a figure of unknown provenance in front of an approver.

**Why each record exists.** The data seeds a case for every branch the tools specify:
eleven SKUs at or below reorder point, one exactly at it and one at zero stock; one
supplier per exclusion reason; a deliberate name collision between Lakeview Building
Materials and Lakeview Building Supplies; an expired offer; an unstated VAT treatment;
a coil with no weight and a reel with no length; a per-tonne price with a stated
conversion factor; and a USD offer with freight quoted separately.

**Provenance.** Registered as DAT-001 to DAT-003 in `knowledge/source-register.csv`
with real SHA-256 checksums, under the same permission basis as the corpus. Marked
`review_status: pending_review`, not `approved` — the corpus was human-reviewed on
17 September 2026, this was authored on 23 September 2026 and that review has not
happened.

---

## 3. Documents amended, and why each was necessary

### `docs/requirements/user-stories.md` — version 1.1 to 1.2

Requirement 4 was narrower than the policy it enforces. Three changes, all confined to
Requirement 4.

**4.1** required only AVL presence and Blacklist absence. POL-002-C02 also bars a
*suspended* supplier, and POL-002-C03 bars a quotation outside the supplier's approved
categories. The deterministic layer was always going to perform those checks; the
requirement did not say so. It now names all four.

**4.3** gained `SUSPENDED`, `OUT_OF_CATEGORY` and `NAME_DISCREPANCY`. The former
vocabulary of `AVL_ABSENT`, `BLACKLISTED` and `EXPIRED` cannot express the two additional
bars or the 4.6 clearance stop. (`NAME_DISCREPANCY` was added in PR #53 review, commit
`1c09848`, on 24 September — after this log was first written.)
Folding a suspension into `BLACKLISTED` would tell an approver something untrue:
POL-002-C02 treats a suspension as reversible on management record and a blacklisting
as not. Folding an out-of-category offer into either would hide that POL-002-C03 allows
it to proceed after Procurement Manager review.

**4.6** is new. POL-002-C04 requires the officer to resolve a discrepancy when a
supplier name differs between a quotation and the register, and states that staff must
not assume similarly named businesses are the same supplier. No requirement carried
that rule. The new criterion makes the system report a resemblance and stop, rather
than resolve it.

**Why an Amendment History section was added.** The document is cited as v1.1 in eleven
places, including `schema.py`, `__init__.py` and a test. All of those cite the glossary
or requirement 6.6, neither of which changed. The amendment note states that explicitly,
so a reader who finds a v1.1 citation knows it is still accurate. Only the two
references that assert the current governing version were updated.

### `docs/README.md` — owners reconciled with the issue tracker

The weekly deliverable index disagreed with the GitHub issues. Thirty owner cells were
wrong across Weeks 5, 6 and 7, in both the deliverable tables and the ClickUp copy
lists, plus one in Week 3. Week 8 already agreed.

**Why the tracker wins.** GitHub and ClickUp are what people actually work from. A
deliverable index that names a different owner produces two people who each believe the
other is doing a task. The header note now records the rule: if a row and its issue
disagree, the issue wins — change the assignee there, then update the file.

Verified mechanically: zero mismatches against issues #8 to #40, and zero disagreements
between the deliverable tables and the copy lists.

### `README.md` — brought up to date

It described the project as "Week 2 of 8 — quotation field extraction baseline" and
claimed that no live API call had been made. Both had stopped being true. The Week 2
evaluation records nine of ten cases passing with median latency 3.413 seconds, and the
Week 3 evaluation records thirteen of fifteen and a 42.01 second requisition.

Changes: status rewritten for Week 4; a new section on running policy retrieval; the
real test figure, 223 passed and 6 skipped; the repository layout and module tables
extended for the RAG package, the datasets and the schemas; and "Not yet verified"
replaced with "Measured, and still unknown", carrying the real figures and the two
outstanding failures.

### Smaller amendments

| File | Change | Reason |
| ----- | ----- | ----- |
| `docs/AI-ENGINEERING-LOG.md` | New Week 4 entry | Brief section 6 requires a log of material AI-assisted decisions |
| `knowledge/source-register.md` | New section 7 | Records the datasets and why they are inert to the RAG index |
| `knowledge/source-register.csv` | Rows DAT-001 to DAT-003 | Provenance and checksums |
| `knowledge/README.md` | One row | Links the new data folder |
| `docs/architecture/model-integration-handover.md` | One line | v1.1 to v1.2 reference |
| `.gitignore` | Two entries | Local-only reference notes are not deliverables |

---

## 4. Verification performed

| Check | Result |
| ----- | ----- |
| All 11 schema files are valid JSON Schema draft 2020-12 | Pass |
| 48 inventory, 8 supplier and 36 quotation records validate against the record schemas | Pass, 0 errors |
| 4 input, 4 output and 2 failure examples validate against their schemas | Pass, 0 errors |
| All 14 JSON blocks in the catalogue parse | Pass |
| Embedded schema snippets match the schema files on properties and required fields | Pass |
| Landed-cost figures in the worked example recomputed in decimal arithmetic | Pass |
| Registered checksums match the files on disk | Pass |
| Owner rows against GitHub issues #8 to #40 | 0 mismatches |
| Relative links and in-page anchors across all changed documents | 0 broken |
| Existing test suite after the source-register additions | 223 passed, 6 skipped |

`jsonschema` was used for validation in a throwaway environment and is deliberately not
a project dependency. The charter fixes zero runtime dependencies and the implementation
is expected to validate by hand, as `schema.validate` already does.

---

## 5. Design decisions worth defending

**Authorization is not a parameter.** No input schema carries `caller_role`. The
orchestration layer injects it from the authenticated session and it appears only in
the output trace. Requirement 14.5 treats every quotation and policy document as
untrusted data; if a role were a model-facing field, text inside a quotation could ask
for one. `QUO-005` in the corpus is exactly that attack.

**The one side effect writes DRAFT and nothing else.** `create_requisition_draft`
accepts `status` only as the constant `DRAFT`, so that an attempt to set anything else
fails with `FORBIDDEN_TRANSITION` citing Requirement 14.3, rather than as a generic
unknown-field error. A refusal should name the rule it is enforcing.

**Fail closed, and fail whole.** An unreadable supplier register reports nobody
eligible, never everybody. No tool returns a partial result. This mirrors the
reject-do-not-salvage rule `schema.validate` already applies under Requirement 3.3.

**The catalogue is closed.** Section 8 lists twelve function names that must never
exist, cross-referenced to `.semgrep/agent-safety.yml`, which fails the build on any of
them. The prohibition is structural, not a runtime permission check.

---

## 6. Open items

**The tool count is at the charter ceiling.** Four is the section 7 upper bound. A
fifth tool needs a charter amendment.

**The datasets are not yet human-reviewed.** DAT-001 to DAT-003 are `pending_review`.
Someone other than their author should read them before the Week 7 evaluation depends
on them.

**`week-03.md` disagrees with the tracker on three of four rows.** It already carries
its own note asking for confirmation. Git authorship is not conclusive, because
stub-creation commits make one member the top author of files whose content another
member wrote. The team needs to settle it from memory of what was actually delivered.

**`tools/offline_demo.py` writes to the real evidence log.** Running it appends rows to
`evidence/traces/extraction-runs.jsonl` while printing a banner saying its output is not
evidence. This contradicts the README's own rule that the run log must not be editable.
A small fix, but it means the evidence log currently contains demo rows.

**Three tools have no implementation.** This deliverable is a contract, not a
demonstration. Issue #16 builds them and issue #17 tests their failure and
authorization behaviour; both are unblocked by the dataset.
