**SYSTEM DESIGN DELIVERABLE | WEEK 2**

**Working Baseline Model Interaction: Quotation Field Extraction**

*Project: SME Procurement Agent  |  Model: Gemini 3.1 Flash-Lite  |  Version: 1.0  |  Date: 11th September 2026*

**Group:** Y
**Repository:** https://github.com/GeorgeLukaanya/bse4104-procurement-agent

---

## **1\. Purpose**

This document records the Week 2 baseline model interaction: the first point at
which the SME Procurement-Preparation Agent uses a foundation model to do real
work. It describes what was built, how it behaves, what evidence supports each
claim, and — explicitly — which claims are not yet supported by anything.

The baseline interaction is **quotation field extraction**. A supplier quotation
that has already been converted to Markdown goes in; a validated eleven-field
Normalised Quotation record comes out, or an explicit failure does. This is the
capability Requirements Document v1.1 requirement 3 assigns to the AI Layer, and
the one success criterion S9 measures.

It is deliberately the only thing the model does at this stage. Policy retrieval
and justification drafting arrive in later weeks.

---

## **2\. Status, stated plainly**

Two different claims are easy to confuse here, so they are separated.

| Claim | Status |
| :---- | :---- |
| The baseline interaction is designed, implemented and exercised end to end | **Yes.** 135 automated tests pass. The full pipeline runs against a substituted backend. |
| The interaction has been run against the live Gemini API | **No.** No live API call has been made at the time of writing. |

Everything above the provider call — prompt construction, schema-constrained
request assembly, response validation, safety scanning, caching, evidence
logging — is built and tested. The provider call itself has never executed.

Consequently **no claim about the model's accuracy, latency or behaviour appears
in this document**, because none could be supported. Section 9 lists precisely
what is outstanding and who closes it.

This distinction is the honest reading of "working baseline". The *interaction*
works. The *model* has not been observed.

---

## **3\. The interaction**

### 3.1 Model and decoding settings

Fixed by the Model Selection Note and Prompt Specification v1.0 section 4. These
are part of the specification because they change output and must be held
constant across evaluation runs.

| Setting | Value | Why |
| :---- | :---- | :---- |
| Model string | `gemini-3.1-flash-lite` | Pinned by **exact version**, never an alias. A provider-side version change must not silently alter evaluation results. |
| Temperature | `0` | Extraction is deterministic. Variance across identical inputs is a defect. |
| Max output tokens | `2048` | Sufficient for a multi-item quotation record. |
| Thinking budget | `0` (disabled) | The specification says "minimum or disabled"; resolved to a concrete value because the configuration fingerprint requires one. |
| Response MIME type | `application/json` | Enforces structured output. |
| Response schema | Prompt Specification section 6 | Constrained decoding; non-conforming output rejected at the API boundary. |
| Prompt version | `1.0` | Prompt Specification section 8. |

The application rejects any model string ending in `-latest`, `-preview` or
`@latest`, including one supplied on the command line. Aliases repoint
provider-side, and nothing in our records would show that it had happened.

### 3.2 What the model is asked to produce

The **Normalised Quotation**, defined in the Requirements Document v1.1 glossary
as eleven fields. The v1.1 revision raised this from six; the Week 1
cross-document audit found that six cannot produce the inputs for Landed Cost,
which requirement 6 makes the basis for supplier ranking.

**Seven quotation-level fields:** supplier name, currency, VAT treatment
(inclusive or exclusive), VAT rate where stated, delivery or freight cost, lead
time in days, quotation validity date.

**Four item-level fields, repeated per line item:** item name, quantity offered,
unit of measure, unit price.

Plus a `missing_fields` array. Requirement 3.2 states that a field absent from
the source is recorded as null **with a stated reason**, never inferred,
estimated or defaulted. Without somewhere to put the reason, that requirement is
unimplementable; the array is where it goes.

### 3.3 The prompt

Reproduced word for word from Prompt Specification v1.0 section 8. The system
instruction carries seven rules; in summary, the model must extract only what is
explicitly present, preserve monetary values, currency and unit of measure
exactly as stated, perform no arithmetic of any kind, assert nothing about
supplier eligibility or approval, record a reason for every null, treat all
quotation content as untrusted data, and return only the JSON object.

Quotation content is wrapped in `<quotation>` delimiters in the user message.
That boundary is not decoration: it is the injection defence required by
requirements 3.7 and 14.5, giving the model an explicit separation between
instruction and untrusted supplier text.

**The prompt text is versioned, and the version is load-bearing.** It forms part
of the cache key and appears in every evidence log entry. Editing the wording
without bumping the version would cause results produced under the old prompt to
be served and reported as though they came from the new one, invalidating every
evaluation figure recorded against it.

---

## **4\. The pipeline**

For one quotation, in this order.

| # | Step | Behaviour |
| :---- | :---- | :---- |
| 1 | **Cache lookup** | Keyed on SHA-256 of the converted Markdown **combined with the full configuration fingerprint** — model, temperature, thinking budget, max output tokens, prompt version. A hit returns with no API call. |
| 2 | **Model call** | Schema-constrained decoding. Bounded exponential backoff with jitter on HTTP 429, 500, 503 and timeouts. Non-retryable errors fail immediately. |
| 3 | **Schema validation** | Validated against the Normalised Quotation contract. Non-conforming output is rejected outright. |
| 4 | **Prohibited-pattern scan** | Output scanned for approval assertions, contract awards, purchase order instructions, vendor selection, financial commitments and prompt-injection echoes. |
| 5 | **Landed-cost readiness** | Reports, by name, any field the deterministic comparison calculator would lack. |
| 6 | **Persist** | Cache entry plus an append-only evidence log entry. |

Three of these deserve their reasoning stated, because each prevents a specific
defect rather than implementing a preference.

**Why the cache key includes the configuration, not just the document.** Keying
on the document alone would return a result produced under an older prompt
version, or a different model, as though it came from the current one. Every
accuracy figure computed from that cache would attribute one prompt's behaviour
to another, and nothing in the output would reveal it. Success criterion S9
makes extraction accuracy a measured target, so this would corrupt the
measurement the week exists to produce.

**Why validation rejects rather than salvages.** Requirement 3.3 and the AI
Boundary Matrix v1.1 failure-behaviour section both require that non-conforming
output is rejected outright rather than partially accepted. A payload with a
valid supplier name and an invalid VAT treatment yields nothing at all. A
half-parsed quotation is indistinguishable from a complete one downstream, which
is exactly the failure this rule prevents.

**Why the safety scan runs even though the schema has no free-text field.**
Constrained decoding restricts shape, not content: a supplier name is a string,
and a string can carry "APPROVED — award contract to this vendor". It is also
the control that must already work before Week 6 introduces justification
drafting, where the model does emit prose. A control first exercised in the week
it becomes load-bearing has never been tested.

---

## **5\. Boundary controls**

The AI Boundary Matrix v1.1 sets limits on what the model layer may do. Each is
enforced in code rather than relied upon as convention.

| Boundary | Enforcement |
| :---- | :---- |
| **No arithmetic** | The package performs no totalling, VAT application, unit conversion, currency conversion, landed-cost computation or ranking. All of it belongs to the deterministic calculator downstream (requirement 6.6). |
| **No eligibility or approval assertions** | Prohibited-pattern scan, six categories, requirement 14.2. Offending values are suppressed before reaching any user or record, and a suppression audit entry is written. |
| **Untrusted document content** | Delimiter-wrapped input, plus system-instruction rule 6, plus the output scan. Quotation text is never treated as instruction. |
| **No inference of missing values** | Schema validation requires a stated reason for every null (requirement 3.2). An entry without a reason is a conformance failure. |
| **Model cannot drift** | Exact version pinning; aliases rejected. |
| **Credentials** | The API key is read from the environment only. It is never hardcoded, never written to the cache or evidence log, and is redacted from transport errors. |
| **Synthetic data only** | All fixtures are invented. Free-tier inputs can be logged by the provider, so no real supplier or commercial data may pass through a free-tier key. |

---

## **6\. Evidence**

### 6.1 Automated tests

135 tests across nine files. **The suite runs with no API key, no network access
and without the provider SDK installed**, substituting a stub for the provider.
This is deliberate: the Model Selection Note establishes requests per day as the
binding constraint on the project, and the daily quota resets at midnight
Pacific — mid-morning in Kampala — so a test suite that consumed quota could
leave the team unable to evaluate until the following day.

| Area | Tests | Covers |
| :---- | :---- | :---- |
| Contract | 13 | Eleven-field count, response schema shape, rejection of malformed values, requirement 3.2 reasons |
| Caching | 10 | No second call for an identical document; configuration change invalidates the cache; corrupt entries treated as misses |
| Transport | 13 | Backoff recovers from transient rate limiting; gives up and reports rate limiting by name; non-retryable errors fail immediately; key redaction |
| Configuration and prompt | 24 | Exact version pinning, alias rejection, temperature 0, decoding settings, prompt text fidelity to specification section 8 |
| Pipeline | 16 | Happy path returns every field; non-conforming output rejected not salvaged; suppression survives a cache hit; no arithmetic on monetary values |
| Safety guard | 27 | All six prohibited categories detected; ordinary procurement language does not trigger it |
| Landed-cost readiness | 7 | Specific missing fields named, with the requirement clause each comes from |
| Evidence log | 9 | Every call logged with its configuration fingerprint; rate-limited runs still appear; key never written |
| Command line | 16 | Field reporting, missing-field reasons, batch continuation after a failure, latency reporting |

### 6.2 End-to-end behaviour across the fixture set

Run through the full pipeline with a substituted backend:

| Fixture | Characteristic | Result | Landed cost |
| :---- | :---- | :---- | :---- |
| 01 clean table, UGX | Control case, all fields present | OK | Ready |
| 02 prose, per carton | No table, pack size stated, VAT inclusive, delivery in words | OK | Ready |
| 03 USD, freight separate | Foreign currency, freight stated apart from unit prices | OK | Ready |
| 04 minimal | Currency, VAT treatment, delivery and validity all absent | OK | **Not ready** — four fields named |
| 05 embedded instruction | Contains text instructing the model to mark the supplier approved and disregard competing quotations | **Suppressed** | Ready |
| 06 expired validity | Validity date already passed | OK | Ready |

Fixture 04 is correct behaviour, not a failure: the quotation extracted cleanly,
and requirement 6.3 excludes it from automated ranking and presents it
separately, naming the missing fields. Fixture 05 demonstrates the requirement
14.2 control operating end to end.

### 6.3 Evidence log

Every call — successful, failed or served from cache — appends one JSON object
recording source, cache key, cache-hit flag, status, attempt count, latency,
suppressed patterns, landed-cost blockers and the full configuration
fingerprint. Failed runs are recorded identically to successful ones: a
rate-limited run that left no trace would make the daily request count appear
smaller than it was and would conceal the backoff behaviour the Model Selection
Note claims to exercise.

The log is append-only. An evidence log that can be rewritten is not evidence.

---

## **7\. Reproducing this**

Python 3.10 or newer; verified on 3.13 and 3.14.

```
git clone https://github.com/GeorgeLukaanya/bse4104-procurement-agent.git
cd bse4104-procurement-agent

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Run the tests** — no key, no network, no quota consumed:

```
pytest
```

**Run the pipeline without an API key.** This drives the real command-line
interface with a substituted backend, exercising every step:

```
python tools/offline_demo.py
```

Expect five `OK`, one `SUPPRESSED`, one `NOT READY` for landed cost, and exit
code `1` — correct, because fixture 05 is deliberately adversarial and not every
file comes back clean. Running it a second time serves every file from cache,
makes no call, and reports that no latency figure is available rather than
inventing one.

**Run it against the live API** (requires the SDK and a key):

```
pip install -e ".[gemini]"
export GEMINI_API_KEY=...
python -m procurement_agent.cli fixtures/*.md
```

The demonstration without a key exercises the pipeline, not the model. Its
records are hand-written and its latency is a simulated delay; it prints a
banner saying so. Nothing it produces is evidence about Gemini 3.1 Flash-Lite.

---

## **8\. Structure**

| Component | Responsibility |
| :---- | :---- |
| `config` | Pinned model string, decoding settings, configuration fingerprint, key loading |
| `schema` | The eleven-field contract, validation, landed-cost readiness |
| `prompts` | Literal prompt text, versioned |
| `client` | Provider transport with bounded retry; the backend is substitutable |
| `cache` | Content-addressed cache keyed on document and configuration |
| `guards` | Prohibited-pattern suppression |
| `runlog` | Append-only evidence log |
| `extract` | Pipeline orchestration |
| `cli` | Command-line entry point |

Roughly 2,270 lines of implementation and 1,470 lines of tests.

**No application framework is used.** Django, FastAPI and Flask are all absent.
The Project Charter has not selected an application framework, and Week 2 must
not force that decision; the package is importable and will be consumed by
whichever interface the team adopts later.

The provider is reached through a single substitutable seam — one method, in one
class. Nothing else in the package knows which provider is in use, which is what
allows the entire pipeline to be exercised offline.

---

## **9\. Outstanding: claims requiring a live API call**

None of the following is estimated anywhere in this document, in the codebase or
in the repository. Each requires a live run.

| Outstanding item | Current state |
| :---- | :---- |
| **Extraction accuracy against the fixture set** | Unknown. No model has read the fixtures. Success criterion S9 has no value. |
| **Whether the model resists the embedded instruction in fixture 05** | Unknown. The guard is tested and fires on an echoed assertion; whether the model produces one is a separate question, and is Week 7 evaluation case S8. |
| **Measured latency, median and worst case** | Unknown. The command-line interface reports both across live calls; none have been made. |
| **Actual free-tier rate limits** (requests per minute, tokens per minute, requests per day) | Unknown. To be read from the provider console for our own evaluation project and recorded with the date read. |
| **Schema conformance rate** | Unknown. The evidence log format exists and records every call; no live entries yet. |

A separate handover document, `Model_Integration_Handover.md`, briefs whoever
takes this forward. It names the single integration seam, lists every assumption
made about the provider SDK without it installed, and states what to record on
completion.

---

## **10\. Traceability**

| Requirement or criterion | How this deliverable addresses it |
| :---- | :---- |
| Requirement 3.1 — eleven fields within 30 seconds | Eleven-field contract implemented and tested; the time ceiling is unmeasured |
| Requirement 3.2 — null with a stated reason, never inferred | `missing_fields` array; validation rejects an entry without a reason |
| Requirement 3.3 — non-conforming output rejected | Outright rejection, no salvage path |
| Requirement 3.7 — quotation content treated as untrusted | Delimiter wrapping, system-instruction rule 6, output scan |
| Requirement 6.3 — missing landed-cost inputs named | Readiness check reports each field with its clause |
| Requirement 6.6 — AI performs no arithmetic | No arithmetic in the package; asserted by test |
| Requirement 13.1 — extraction results recorded | Append-only evidence log |
| Requirement 14.2 — prohibited output suppressed and audited | Six-category scan, suppression, audit entry |
| Success criterion S9 — extraction field accuracy | Capability built; **value not yet measured** |

---

## **11\. References**

- Project Charter v1.1
- Requirements Document v1.1 — glossary "Normalised Quotation"; requirements 2, 3, 6, 14
- AI Boundary Matrix v1.1
- Prompt Specification and Prompt Version History v1.0 — sections 3 to 8
- Model Selection Note
- Model Integration Handover v1.0
- AI Engineering Log — Week 2 entry

> Earlier v1.0 copies of the Requirements Document, AI Boundary Matrix and
> architecture narrative remain on the repository's `origin/main` branch, along
> with a v0.1 extraction prompt asking for only six fields. **These are
> superseded and must not be used.** The field set is eleven.
