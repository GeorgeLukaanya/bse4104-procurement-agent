# AI Engineering Log

A concise record of material AI-assisted decisions and generated artefacts, as
required by section 6 of the project brief. Append entries; do not rewrite history.

## Tools declared

| Tool / model | Used for | Since |
|---|---|---|
| Claude Opus 5 (Claude Code) | Week 2 extraction package: design, implementation, tests, fixtures, documentation | 2026-09-11 |
| `gemini-3.1-flash-lite` (Google Gemini API) | Quotation field extraction at runtime — the system's own AI layer, not an authoring tool | 2026-09-11 |

## Entries

> Entry format: `### YYYY-MM-DD — [short title]`, newest last, with the four
> headings below. Established Week 2; the Week 1 rows were retrofitted to it.

### 2026-09-11 — Week 2 baseline: quotation field extraction package

- **Context:** Build the Week 2 baseline model interaction — a framework-free,
  importable Python package that extracts the eleven-field Normalised Quotation
  record from a Converted Quotation Document. No application framework was to be
  introduced, because Project Charter v1.1 has not chosen one and Week 2 must not
  force that decision.

- **AI contribution:** Claude Opus 5, run through Claude Code, produced the
  `procurement_agent` package (nine modules under `src/`), 132 tests under
  `tests/`, six synthetic quotation fixtures under `fixtures/`, this entry and
  the README rewrite. It also performed the specification discovery pass that
  identified which document versions were authoritative.

- **Human review:** Pending. Every claim below is traceable to a named clause in
  a project document, and the "unverified" section states plainly what has not
  been established. The extraction accuracy of the model itself has NOT been
  reviewed, because no live API call has been made.

- **Outcome:** Accepted into the repository as the Week 2 baseline, subject to
  the live-call verification listed at the end of this entry.

- **Deliverable produced:** `docs/architecture/working-baseline.md` —
  the Week 2 written deliverable, for the shared Google Docs folder. It separates
  two claims that are easy to conflate: the baseline *interaction* is built and
  exercised end to end (135 tests), while the *provider call* has never executed.
  No accuracy, latency or rate-limit figure appears in it, because none could be
  supported.

- **Handover produced:** `docs/architecture/model-integration-handover.md` — a briefing
  for whoever owns the Gemini API integration. It names the single seam
  (`GeminiBackend.generate()`), lists what is already built, and states plainly
  that the body of that method was written without the SDK installed and has
  never executed. Section 5 enumerates each assumption about the `google-genai`
  call shape that must be checked against the real library, so the integrator
  discovers them from a list rather than from a stack trace.

- **Documents amended:** `README.md` (setup, run and test instructions),
  `.env.example` (temperature `0.2`→`0`, max tokens `1024`→`2048`, both of which
  contradicted Prompt Specification section 4; pinned model string and
  `GEMINI_API_KEY` added), `docs/architecture/model-selection-note.md` (see below) and
  `prompts/quotation-extraction-v1.md` (a pointer from
  section 8 to its implementation in `prompts.py`, and the warning about bumping
  the version). **The Model Selection Note is a team deliverable and was edited;
  its author should review the change.** Section 2 asserted 15 RPM / 250,000 TPM
  / 1,000 RPD and a latency range as fact while the prose immediately below said
  those same figures were deliberately left for measurement. Applying the note's
  own stated policy — "Where a figure is not yet available, it is marked as
  pending rather than estimated" — every unmeasured figure is now marked pending,
  and the evidence table names the specific files and tests behind each claim
  that is established. No figure was invented to fill a gap.

#### Configuration used

| Setting | Value | Source |
|---|---|---|
| Pinned model string | `gemini-3.1-flash-lite` | Model Selection Note, "Pinned model string" |
| Prompt version | 1.0 | Prompt Specification section 8 |
| Temperature | 0 | Prompt Specification section 4 |
| Max output tokens | 2048 | Prompt Specification section 4 |
| Thinking budget | 0 (disabled) | Prompt Specification section 4, resolved — see ambiguities |
| Response MIME type | `application/json` | Prompt Specification section 4 |
| Response schema | Section 6 structure, via google-genai `response_schema` | Prompt Specification sections 4 and 6 |

The model string is pinned by exact version and `config.py` rejects any string
ending in `-latest`, `-preview` or `@latest`, including one supplied via
`--model`. An alias would repoint provider-side between two evaluation runs and
nothing in the run log would show it.

#### Design decisions and why

1. **The cache key is the document hash AND the full configuration fingerprint.**
   Keying on the document alone would return a result produced under an older
   prompt version, or a different model, as though it came from the current one.
   Every accuracy figure computed from that cache would attribute one prompt's
   behaviour to another, silently. Success criterion S9 makes extraction accuracy
   a measured target, so this would corrupt the measurement the week exists to
   produce. Test: `test_changing_the_prompt_version_invalidates_the_cache`.

2. **Schema validation rejects outright; there is no salvage path.** Requirement
   3.3 and the AI Boundary Matrix v1.1 failure-behaviour section both require
   this. A payload with a good `supplier_name` and a bad `vat_treatment` yields
   nothing at all, not a partial record, because a half-parsed quotation is
   indistinguishable from a complete one downstream.

3. **The prohibited-pattern scan runs on every extraction**, even though the
   schema has no free-text field. Constrained decoding restricts shape, not
   content: `supplier_name` is a string and a string can carry an approval
   assertion. It is also the control that must already work before Week 6
   introduces justification drafting; a control first exercised on the week it
   becomes load-bearing has never been tested.

4. **Patterns are anchored on assertion verbs, not bare nouns.** "Approved Vendor
   List" is ordinary procurement vocabulary and a supplier may legitimately be
   called "Select Hardware Traders". Only a claim that something *has been*
   approved, awarded, selected or committed is prohibited. False positives would
   suppress legitimate quotations, so there is a test asserting that seven
   ordinary phrases do not trip the guard.

5. **Non-retryable errors fail immediately.** HTTP 429, 500, 503 and timeouts
   retry with bounded exponential backoff and full jitter; 400, 401, 403 and 404
   do not. Every wasted attempt is a request the free-tier daily quota cannot
   spare. Full jitter rather than a fixed delay because several quotations in one
   batch hit the same 429 simultaneously and would otherwise collide again.

6. **A rate-limited run is reported as rate-limited, by name.** Reporting it as a
   generic failure would make a quota problem look like a model problem and the
   team would debug the wrong thing. Failed runs are written to the run log
   exactly like successful ones — a failure that left no trace would make the
   daily request count look smaller than it was.

7. **The package performs no arithmetic.** No totalling, no VAT application, no
   unit or currency conversion, no landed cost, no ranking. Requirement 6.6 and
   the AI Boundary Matrix assign all of it to the deterministic calculator. There
   is a test asserting the extracted figures are exactly those the model
   returned.

8. **Latency is reported across live calls only.** A cache hit made no request
   and its near-zero elapsed time would drag the median down and misrepresent
   what the model costs. With no live calls, the CLI says so rather than printing
   a figure.

9. **A committed offline demo (`tools/offline_demo.py`).** Without an API key a
   teammate could run the tests but never see the pipeline work, and the brief
   requires that someone can clone, set up, run and test this without asking
   anyone. The demo drives the real CLI with a scripted backend. It prints a
   banner on entry and exit stating that no API call was made, the records are
   hand-written and the latency is a sleep — a demonstration that could be
   mistaken for a measurement would be worse than no demonstration.

10. **Suppression findings are carried through the cache.** Found by running
    the documented commands rather than by a test: the cache stores the record
    with its offending values already replaced, so re-scanning a cached record
    found nothing and the second run of an adversarial quotation reported `OK`.
    Requirement 14.2's suppression audit entry was lost on every run after the
    first — a quotation that was adversarial on Monday read as clean on Tuesday.
    The cache entry now carries the findings (category and field path, **without
    the excerpt**, which holds the prohibited text 14.2 keeps out of every record
    but the audit trail), and the cache format version was bumped to 2 so that
    v1 entries are re-extracted rather than trusted. Tests:
    `test_suppression_survives_a_cache_hit`,
    `test_prohibited_text_is_not_written_to_the_cache`,
    `test_a_stale_cache_format_is_ignored`.

11. **The provider SDK is imported lazily.** The whole test suite runs with no API
   key, no network and `google-genai` not installed, injecting a stub backend.
   The Model Selection Note makes requests per day the binding constraint, and
   the daily quota resets at midnight Pacific — mid-morning in Kampala — so a
   suite that spent quota could leave the team unable to evaluate until the next
   day.

#### Specification ambiguities resolved

| Ambiguity | Resolution |
|---|---|
| Prompt Specification section 4 gives the thinking budget as "Minimum or disabled", not a number. | Set to `0` (disabled). The configuration fingerprint needs a concrete value or it cannot distinguish two runs. Revisit if measured accuracy suffers. |
| Requirement 6.3 names three landed-cost blockers (unit of measure, VAT treatment, delivery cost), but 6.1 needs more to compute anything. | Both are checked, and every blocker is reported with the clause it comes from. The 6.1 additions are `currency`, `unit_price`, and `vat_rate_percent` *only when* treatment is exclusive. `quantity` is deliberately **not** a blocker: 6.1 extends cost over the Reorder Quantity, which comes from the Inventory Snapshot, not from the supplier's quoted quantity. |
| Requirement 14.2 says suppress "that output" without saying whether the whole record or the offending value is withheld. | The offending string values are replaced with a placeholder and the rest of the record survives. The officer still needs to see which quotation misbehaved and what the rest of it said. |
| The Model Selection Note states 15 RPM / 250,000 TPM / 1,000 RPD as fact in section 2, then says immediately below that those figures are to be measured, not estimated, because the provider no longer publishes them. | Treated as **unmeasured**. The Model Selection Note now marks those figures pending. No rate limit figure is encoded anywhere in the package, this log, or the README. |
| Prompt Specification section 8 runs rules 4 and 5 together on one line. | A Markdown export artefact, not a semantic difference. Rendered as eight separate numbered rules in v1.1 (date notation is rule 6); a test asserts the literal prompt text. |
| Where the AI Boundary Matrix and Requirements Document existed in two versions. | The tree holds one copy of each: Requirements `docs/requirements/user-stories.md`, AI Boundary Matrix `docs/requirements/ai-boundary-matrix.md`. Both use the eleven-field schema. |

#### Claims that remain unverified

These require a live API call and have **not** been made. Nothing below is
estimated, and no figure has been written into any project document in place of
a measurement.

- **Extraction accuracy against the fixtures.** Unknown. No model has read the
  fixtures. Whether `gemini-3.1-flash-lite` correctly extracts eleven fields from
  prose layout, per-carton pricing or a VAT-inclusive quote is untested. Success
  criterion S9 has no value yet.
- **Whether the model resists the embedded instruction in fixture 05.** Untested.
  The *guard* is tested and fires on an approval assertion, but whether the model
  emits one is a separate question and is Week 7 evaluation case S8.
- **Measured latency, median and worst case.** Unknown. The CLI reports live-call
  latency when live calls are made; none have been. The Model Selection Note's
  latency row is still pending.
- **Actual free-tier rate limits** (RPM, TPM, RPD) for this project. Unknown.
  Must be read from the AI Studio rate limit view for our own project and
  recorded with the date read, as the Note itself requires.
- **Schema conformance rate.** Unknown. The Note promises "n extraction calls,
  n schema-conformant, n rejected" from a retained run log. The run log format
  exists and is written on every call; no live rows exist yet.

### 2026-09-23 — Week 4 tool catalogue, schemas and operational datasets

- **Context:** Week 4 requires at least two tools defined with purpose, input schema, output
  schema, authorization and failure behaviour, with at least one retrieving current application
  data or creating a low-risk simulated side effect (issue #15). Two constraints shaped the
  work before any writing began. Project Charter section 1 had already named the six tools the
  agent may use and section 7 caps the build at four, so the catalogue had to draw from that
  list rather than invent one. And the operational data those tools read did not exist:
  `.env.example` had declared `INVENTORY_DATA_PATH`, `QUOTATIONS_DATA_PATH` and
  `SUPPLIERS_DATA_PATH` since Week 2, but `knowledge/data/` was empty, no code read those
  variables, and no weekly row or issue assigned the dataset to anyone.

- **AI contribution:** Claude Opus 5, run through Claude Code, produced
  `docs/architecture/tool-catalogue.md`, the eleven JSON Schema files and README under
  `docs/architecture/schemas/`, the three synthetic datasets and README under `knowledge/data/`,
  the `DAT-001` to `DAT-003` register rows, and this entry. It also carried out the discovery
  pass that found the charter tool list, the unowned dataset and the ownership divergence
  recorded below.

- **Human review:** Pending. Owner review has not happened, and the three datasets are
  registered as `pending_review` rather than `approved` for that reason — the corpus documents
  were human-reviewed on 17 September 2026 and these were not. Every figure in the worked
  examples was computed and checked rather than written by hand, and every schema and example
  was validated mechanically (see below), but no one has yet read the data for plausibility as
  procurement records.

- **Outcome:** Accepted into the repository as the Week 4 tool contract, subject to owner
  review. Issues #16 (working demonstration) and #17 (failure and authorization evidence) were
  blocked on the missing dataset and are now unblocked.

#### Decisions taken

- **Four tools, not six.** `check_reorder_need`, `check_supplier_eligibility`,
  `compare_quotations` and `create_requisition_draft`, all named in charter section 1. Document
  conversion is deferred because charter section 9 excludes scans and OCR; quotation retrieval
  is folded into `compare_quotations` rather than spending one of four slots on a lookup.
- **Policy retrieval is not a tool.** Charter section 1 does not name it, and Week 3 delivered
  it as a pipeline the officer invokes. It stays outside the allow-list until Week 6 decides.
- **One side effect only, and it writes `DRAFT`.** `create_requisition_draft` accepts `status`
  solely as the constant `DRAFT`, so that an attempt to set anything else fails with
  `FORBIDDEN_TRANSITION` citing Requirement 14.3 rather than a generic schema error.
- **`caller_role` is in no input schema.** Authorization is injected by the orchestration layer
  from the authenticated session. Requirement 14.5 treats document content as untrusted, and a
  role that were model-facing could be requested by text inside a quotation.
- **The datasets were created because nobody owned them.** Charter section 7 puts them in
  scope; no deliverable row or issue claimed them. They are consistent with the existing corpus
  — same fictional business, same three categories, the three suppliers named in SUP-001 to
  SUP-003 — and the three fixture items in `fixtures/requisitions/weekly-reorder.json` resolve
  to exactly 120 bags, 25 kg and 40 helmets against the new inventory.

#### Verification performed

| Check | Result |
|---|---|
| All 11 schema files are valid JSON Schema draft 2020-12 | Pass |
| 48 inventory, 8 supplier and 36 quotation records validate against the record schemas | Pass, 0 errors |
| 4 tool input examples and 4 output examples validate against their schemas | Pass, 0 errors |
| 2 failure-response examples validate against their output schemas | Pass, 0 errors |
| All 14 JSON blocks in the catalogue parse | Pass |
| Embedded input-schema snippets match the schema files on properties and `required` | Pass |
| Landed-cost figures in the worked example recomputed in decimal arithmetic | Pass |
| Existing test suite after the `source-register.csv` additions | Pass |

`jsonschema` was used for validation inside a throwaway environment and is deliberately **not**
a project dependency; the charter's zero-runtime-dependency rule stands, and the implementation
is expected to validate by hand as `schema.validate` already does.

#### Raised for the team

- **Two exclusion reasons extend Requirement 4.** It names `AVL_ABSENT`, `BLACKLISTED` and
  `EXPIRED`. `check_supplier_eligibility` also returns `SUSPENDED` and `OUT_OF_CATEGORY`,
  because POL-002-C02 and POL-002-C03 bar both and folding either into `BLACKLISTED` would tell
  an approver something untrue. Needs a Requirements Document amendment.
- **`docs/README.md` disagreed with the issue tracker.** Its Week 4 table named different
  owners from GitHub issues #15 to #19. The Week 4 rows were corrected to match the tracker;
  Weeks 5 to 8 diverge the same way and were left for the group.
- **A fifth tool needs a charter amendment.** Four is the section 7 ceiling.
