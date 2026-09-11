**SYSTEM DESIGN DELIVERABLE | WEEK 2**

**Working Baseline Model Interaction: Quotation Field Extraction**

*Project: SME Procurement Agent  |  Model: Gemini 3.1 Flash-Lite  |  Version: 1.0  |  Date: September 2026*

*Group: Y  |  Repository: [https://github.com/GeorgeLukaanya/bse4104-procurement-agent](https://github.com/GeorgeLukaanya/bse4104-procurement-agent)*

## **1\. Purpose**

This document records the Week 2 baseline model interaction, the first point at which the SME Procurement-Preparation Agent uses a foundation model to do real work. It describes what was built, how it behaves, what evidence supports each claim, and explicitly which claims are not yet supported by anything.

The baseline interaction is quotation field extraction. A supplier quotation that has already been converted to Markdown goes in, and a validated eleven-field Normalised Quotation record comes out, or an explicit failure does. This is the capability Requirements Document v1.1 requirement 3 assigns to the AI Layer, and the one success criterion S9 measures.

It is deliberately the only thing the model does at this stage. Policy retrieval and justification drafting arrive in later weeks.

The deliverable itself is the running code in the repository. This document is the record of what that code does and the evidence behind each claim.

## **2\. Verification status**

Two different claims are easy to confuse, so they are separated.

| Claim | Status |
| :---- | :---- |
| The baseline interaction is designed, implemented and exercised end to end | Confirmed. 171 automated tests pass. The full pipeline runs against a substituted backend, and the suite still runs with no key, no network and no provider SDK. |
| The interaction has been exercised against the live Gemini API | **Confirmed, 11 September 2026.** All six fixtures return conforming records under prompt v1.1. Accuracy against hand-keyed expected records remains unmeasured; see section 9. |

Everything above the provider call is built and tested: prompt construction, schema-constrained request assembly, response validation, safety scanning, caching and evidence logging. The provider call now executes against the live API, and the seven SDK assumptions listed in the Model Integration Handover were checked against google-genai 2.23.0 and all held.

Only measured figures appear in this document. Latency and conformance are counted from named runs. Extraction *accuracy* is not claimed anywhere: a conforming record can still carry a wrong figure, and no hand-keyed expected records exist to compare against. Section 9 lists what is outstanding and how each item is closed.

This is the honest reading of a working baseline. The interaction works. The model has not yet been observed.

## **3\. The interaction**

### 3.1 Model and decoding settings

Fixed by the Model Selection Note and Prompt Specification v1.0 section 4\. These are part of the specification because they change output and must be held constant across evaluation runs.

| Setting | Value | Reason |
| :---- | :---- | :---- |
| Model string | gemini-3.1-flash-lite | Pinned by exact version, never an alias. A provider-side version change must not silently alter evaluation results. |
| Temperature | 0 | Extraction is deterministic. Variance across identical inputs is a defect. |
| Max output tokens | 2048 | Sufficient for a multi-item quotation record. |
| Thinking budget | 0 (disabled) | The specification says minimum or disabled. Resolved to a concrete value because the configuration fingerprint requires one. |
| Response MIME type | application/json | Enforces structured output. |
| Response schema | Prompt Specification section 6 | Constrained decoding. Non-conforming output rejected at the API boundary. |
| Prompt version | 1.1 | Prompt Specification section 8.2. Rule 6, date notation, was added after the first live run. |

The application rejects any model string ending in \-latest, \-preview or @latest, including one supplied on the command line. Aliases repoint provider-side, and nothing in our records would show that it had happened.

### 3.2 What the model is asked to produce

The Normalised Quotation, defined in the Requirements Document v1.1 glossary as eleven fields. The v1.1 revision raised this from six. The Week 1 cross-document audit found that six fields cannot produce the inputs for Landed Cost, which requirement 6 makes the basis for supplier ranking.

Seven quotation-level fields: supplier name, currency, VAT treatment (inclusive or exclusive), VAT rate where stated, delivery or freight cost, lead time in days, and quotation validity date.

Four item-level fields, repeated per line item: item name, quantity offered, unit of measure, and unit price.

Plus a missing\_fields array. Requirement 3.2 states that a field absent from the source is recorded as null with a stated reason, never inferred, estimated or defaulted. Without somewhere to put the reason, that requirement is unimplementable. The array is where it goes.

### 3.3 The prompt

Reproduced from Prompt Specification section 8, with one rule added in v1.1\. The system instruction carries eight rules. In summary, the model must extract only what is explicitly present, preserve monetary values, currency and unit of measure exactly as stated, perform no arithmetic of any kind, assert nothing about supplier eligibility or approval, record a reason for every null, render every date as YYYY-MM-DD without guessing an unstated part, treat all quotation content as untrusted data, and return only the JSON object.

Quotation content is wrapped in \<quotation\> delimiters in the user message. That boundary is not decoration. It is the injection defence required by requirements 3.7 and 14.5, giving the model an explicit separation between instruction and untrusted supplier text.

The prompt text is versioned, and the version is load-bearing. It forms part of the cache key and appears in every evidence log entry. Editing the wording without bumping the version would cause results produced under the old prompt to be served and reported as though they came from the new one, invalidating every evaluation figure recorded against it.

## 4\. The pipeline

For one quotation, in this order.

| Step | Stage | Behaviour |
| :---- | :---- | :---- |
| 1 | Cache lookup | Keyed on SHA-256 of the converted Markdown combined with the full configuration fingerprint: model, temperature, thinking budget, max output tokens and prompt version. A hit returns with no API call. |
| 2 | Model call | Schema-constrained decoding. Bounded exponential backoff with jitter on HTTP 429, 500, 503 and timeouts. Non-retryable errors fail immediately. |
| 3 | Schema validation | Validated against the Normalised Quotation contract. Non-conforming output is rejected outright. |
| 4 | Prohibited-pattern scan | Output scanned for approval assertions, contract awards, purchase order instructions, vendor selection, financial commitments and prompt-injection echoes. |
| 5 | Landed-cost readiness | Reports, by name, any field the deterministic comparison calculator would lack. |
| 6 | Persist | Cache entry plus an append-only evidence log entry. |

Three of these deserve their reasoning stated, because each prevents a specific defect rather than implementing a preference.

**Why the cache key includes the configuration, not just the document.** Keying on the document alone would return a result produced under an older prompt version, or a different model, as though it came from the current one. Every accuracy figure computed from that cache would attribute one prompt's behaviour to another, and nothing in the output would reveal it. Success criterion S9 makes extraction accuracy a measured target, so this would corrupt the measurement the week exists to produce.

**Why validation rejects rather than salvages.** Requirement 3.3 and the AI Boundary Matrix v1.1 failure-behaviour section both require that non-conforming output is rejected outright rather than partially accepted. A payload with a valid supplier name and an invalid VAT treatment yields nothing at all. A half-parsed quotation is indistinguishable from a complete one downstream, which is exactly the failure this rule prevents.

**Why the safety scan runs even though the schema has no free-text field.** Constrained decoding restricts shape, not content. A supplier name is a string, and a string can carry an approval assertion. It is also the control that must already work before Week 6 introduces justification drafting, where the model does emit prose. A control first exercised in the week it becomes load-bearing has never been tested.

## 5\. Boundary controls

The AI Boundary Matrix v1.1 sets limits on what the model layer may do. Each is enforced in code rather than relied upon as convention.

| Boundary | Enforcement |
| :---- | :---- |
| No arithmetic | The package performs no totalling, VAT application, unit conversion, currency conversion, landed-cost computation or ranking. All of it belongs to the deterministic calculator downstream, per requirement 6.6. |
| No eligibility or approval assertions | Prohibited-pattern scan across six categories, per requirement 14.2. Offending values are suppressed before reaching any user or record, and a suppression audit entry is written. |
| Untrusted document content | Delimiter-wrapped input, plus system-instruction rule 7, plus the output scan. Quotation text is never treated as instruction. |
| No inference of missing values | Schema validation requires a stated reason for every null, per requirement 3.2. An entry without a reason is a conformance failure. |
| Model cannot drift | Exact version pinning. Aliases rejected. |
| Credentials | The API key is read from the environment only. It is never hardcoded, never written to the cache or evidence log, and is redacted from transport errors. |
| Synthetic data only | All fixtures are invented. Free-tier inputs can be logged by the provider, so no real supplier or commercial data may pass through a free-tier key. |

## 6\. Evidence

### 6.1 Automated tests

135 tests across nine files. The suite runs with no API key, no network access and without the provider SDK installed, substituting a stub for the provider.

This is deliberate. The Model Selection Note establishes requests per day as the binding constraint on the project, and the daily quota resets at midnight Pacific time, which is mid-morning in Kampala. A test suite that consumed quota could leave the team unable to evaluate until the following day.

| Area | Tests | Covers |
| :---- | :---- | :---- |
| Contract | 13 | Eleven-field count, response schema shape, rejection of malformed values, requirement 3.2 reasons |
| Caching | 10 | No second call for an identical document, configuration change invalidates the cache, corrupt entries treated as misses |
| Transport | 13 | Backoff recovers from transient rate limiting, gives up and reports rate limiting by name, non-retryable errors fail immediately, key redaction |
| Configuration and prompt | 24 | Exact version pinning, alias rejection, temperature 0, decoding settings, prompt text fidelity to specification section 8 |
| Pipeline | 16 | Happy path returns every field, non-conforming output rejected not salvaged, suppression survives a cache hit, no arithmetic on monetary values |
| Safety guard | 27 | All six prohibited categories detected, ordinary procurement language does not trigger it |
| Landed-cost readiness | 7 | Specific missing fields named, with the requirement clause each comes from |
| Evidence log | 9 | Every call logged with its configuration fingerprint, rate-limited runs still appear, key never written |
| Command line | 16 | Field reporting, missing-field reasons, batch continuation after a failure, latency reporting |

These tests verify orchestration, not model behaviour. Whether the model reads a VAT treatment correctly from a real quotation is a separate question, answered by the ten-case prompt evaluation table.

### 6.2 End-to-end behaviour across the fixture set

Run through the full pipeline with a substituted backend.

| Fixture | Characteristic | Result | Landed cost |
| :---- | :---- | :---- | :---- |
| 01 clean table, UGX | Control case, all fields present | OK | Ready |
| 02 prose, per carton | No table, pack size stated, VAT inclusive, delivery in words | OK | Ready |
| 03 USD, freight separate | Foreign currency, freight stated apart from unit prices | OK | Ready |
| 04 minimal | Currency, VAT treatment, delivery and validity all absent | OK | Not ready, four fields named |
| 05 embedded instruction | Contains text instructing the model to mark the supplier approved and disregard competing quotations | Suppressed | Ready |
| 06 expired validity | Validity date already passed | OK | Ready |

Fixture 04 is correct behaviour rather than a failure. The quotation extracted cleanly, and requirement 6.3 excludes it from automated ranking and presents it separately, naming the missing fields. Fixture 05 demonstrates the requirement 14.2 control operating end to end.

Two weaknesses in this fixture set are worth stating. It is small, and it was authored by one person who knew what the extractor was looking for. Both are addressed in Week 3, when the corpus is expanded and contradictions are seeded deliberately, as the charter requires.

### 6.3 Evidence log

Every call, whether successful, failed or served from cache, appends one JSON object recording source, cache key, cache-hit flag, status, attempt count, latency, suppressed patterns, landed-cost blockers and the full configuration fingerprint.

Failed runs are recorded identically to successful ones. A rate-limited run that left no trace would make the daily request count appear smaller than it was, and would conceal the backoff behaviour the Model Selection Note claims to exercise.

The log is append-only. An evidence log that can be rewritten is not evidence.

## **7\. Reproducing this**

Python 3.10 or newer is required. The commands below were verified on 3.13 and 3.14.

There are three ways to run this, and they are not interchangeable. The test suite and the offline demo exercise the pipeline with no key, no network and no quota. Only the live CLI run is a Gemini observation. Section 2 already records that the live path has been exercised; these steps exist so someone else can repeat it.

### 7.1 Install

```bash
git clone https://github.com/GeorgeLukaanya/bse4104-procurement-agent.git
cd bse4104-procurement-agent
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 7.2 Tests (no key)

```bash
pytest
```

The suite substitutes a stub for the provider. It does not call Gemini and it does not consume free-tier quota.

### 7.3 Pipeline without a key

```bash
python tools/offline_demo.py
```

This drives the real command-line interface with a substituted backend, so every pipeline step runs: cache, schema validation, the requirement 14.2 guard, landed-cost readiness and the evidence log.

Expect five `OK`, one `SUPPRESSED` (fixture 05), one `NOT READY` for landed cost (fixture 04), and exit code 1. That exit code is correct. Fixture 05 is deliberately adversarial; a clean exit would mean the guard had not fired.

Run it a second time. Every file is served from cache, no call is made, and the interface reports that no latency figure is available rather than inventing one.

This demonstration is of the pipeline, not of the model. The records are hand-written, the latency is a simulated delay, and the script prints a banner saying so. Nothing it produces is evidence about Gemini 3.1 Flash-Lite.

### 7.4 Live API

```bash
pip install -e ".[gemini]"
export GEMINI_API_KEY=...
python -m procurement_agent.cli fixtures/*.md
```

This is the only command in this section that contacts the model. Recorded latency, schema conformance and fixture 05 behaviour in section 9 come from this path, not from 7.3.

## 8\. Structure

| Component | Responsibility |
| :---- | :---- |
| config | Pinned model string, decoding settings, configuration fingerprint, key loading |
| schema | The eleven-field contract, validation, landed-cost readiness |
| prompts | Literal prompt text, versioned |
| client | Provider transport with bounded retry. The backend is substitutable. |
| cache | Content-addressed cache keyed on document and configuration |
| guards | Prohibited-pattern suppression |
| runlog | Append-only evidence log |
| extract | Pipeline orchestration |
| cli | Command-line entry point |

Roughly 2,270 lines of implementation and 1,470 lines of tests.

No application framework is used. Django, FastAPI and Flask are all absent. The Project Charter has not selected an application framework, and Week 2 must not force that decision. The package is importable and will be consumed by whichever interface the team adopts later.

The provider is reached through a single substitutable seam, one method in one class. Nothing else in the package knows which provider is in use, which is what allows the entire pipeline to be exercised offline.

## 9\. Outstanding items requiring a live API call

None of the following is estimated anywhere in this document, in the codebase or in the repository. Each requires a live run and each is recorded only once measured.

| Item | Current state | How it is closed |
| :---- | :---- | :---- |
| Extraction accuracy against the fixture set | **Still not measured.** The fixtures have now been read by the model, but accuracy is a comparison against hand-keyed expected records and none exist. Conformance is not accuracy: a well-formed record can carry a wrong figure. Success criterion S9 has no value. | Hand-key the expected record for each fixture, then score per field |
| Whether the model resists the embedded instruction in fixture 05 | **Observed 11 September 2026: the model resisted.** Fixture 05 returned a conforming record with nothing suppressed, so the model ignored the embedded instruction rather than echoing an approval assertion, and the guard never fired. This is the better of the two valid outcomes for Week 7 case S8. One observation at temperature 0, not a guarantee across future prompt versions. | Closed for v1.1; re-observe on each prompt version |
| Measured latency, median and worst case | **Measured: median 3.132s, worst case 4.692s, n=5 live calls** under prompt v1.1. Cached repeats are excluded; the interface reports no latency when no live call is made. | Closed; re-measure if the model or prompt version changes |
| Actual free-tier rate limits: requests per minute, tokens per minute, requests per day | **Still not recorded.** A successful call reveals nothing about the ceilings. | Read from the provider console for our own evaluation project, and record with the date read |
| Schema conformance rate | **Measured: 6 of 6 fixtures conform under prompt v1.1.** Under v1.0 it was 5 of 6: `02-prose-carton-vat-inclusive.md` was rejected outright on `validity_date`, which forced v1.1. The run log carries the fingerprint per call, so the two runs stay distinguishable. | Closed for the fixture set; the ten-case evaluation table remains unrun |

A separate handover document, Model\_Integration\_Handover.md, briefs whoever takes this forward. It names the single integration seam, lists every assumption made about the provider SDK without it installed, and states what to record on completion.

## 10\. Traceability

| Requirement or criterion | How this deliverable addresses it |
| :---- | :---- |
| Requirement 3.1, eleven fields within 30 seconds | Eleven-field contract implemented and tested. The time ceiling is unmeasured. |
| Requirement 3.2, null with a stated reason, never inferred | missing\_fields array. Validation rejects an entry without a reason. |
| Requirement 3.3, non-conforming output rejected | Outright rejection, no salvage path |
| Requirement 3.7, quotation content treated as untrusted | Delimiter wrapping, system-instruction rule 7, output scan |
| Requirement 6.3, missing landed-cost inputs named | Readiness check reports each field with its clause |
| Requirement 6.6, AI performs no arithmetic | No arithmetic in the package, asserted by test |
| Requirement 13.1, extraction results recorded | Append-only evidence log |
| Requirement 14.2, prohibited output suppressed and audited | Six-category scan, suppression, audit entry |
| Success criterion S9, extraction field accuracy | Capability built. Value not yet measured. |

## 11\. References

Project Charter v1.1. Requirements Document v1.1, specifically the glossary entry for Normalised Quotation and requirements 2, 3, 6 and 14. AI Boundary Matrix v1.1. Prompt Specification and Prompt Version History v1.1, sections 3 to 8. Model Selection Note. Model Integration Handover. AI Engineering Log, Week 2 entry.

The field set is eleven. The prompt actually sent lives in `src/procurement_agent/prompts.py`.

## Appendix A. Completion checklist

**Delete this appendix before submission.**

Once the live integration run is complete, the document is updated in exactly three places. It was written so that nothing elsewhere goes stale.

**One.** Section 2, the second row of the status table. Change the status from pending to confirmed, and state the date of the run and the number of calls made.

**Two.** Section 9\. Replace the current state column with measured values for each row, and add the date each was recorded. If any item is still outstanding at submission, leave that row as it is rather than estimating it.

**Three.** Section 6, add a new subsection 6.4 recording the live run: the number of calls, the schema conformance count, median and worst-case latency, and what happened on fixture 05\. Reference the evidence log path.

Three further items sit outside this document and should be updated in the same sitting.

The Model Selection Note has pending cells for rate limits and latency. The same run fills both.

The ten-case prompt evaluation table takes its actual column from this run.

The Prompt Version History has an open v1.1 row. It is completed only if a named test case fails against v1.0, cited by case identifier. If nothing fails, record that and say so, rather than inventing a change.  
