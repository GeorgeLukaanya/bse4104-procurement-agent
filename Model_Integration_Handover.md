# **Model Integration Handover**

## **SME Procurement-Preparation Agent — Week 2 Extraction Baseline**

**Course:** BSE4104 Emerging Trends in Software Engineering
**Group:** Y
**Version:** 1.0
**Date:** Week 2 (11th September 2026)
**For:** the AI Engineering Lead (currently Beingana Jim Junior), or whoever
owns the Gemini API integration
**Status of the code described here:** built and tested offline; the provider
call itself is **unverified**

---

## 1. What this document is for

The Week 2 extraction package is complete except for one thing: nobody has made
a real API call. Every module is written and tested, but the tests inject a stub
in place of the provider, so the code path that actually talks to Google has
never executed.

This document tells you exactly where to plug the model in, what is already done
for you, what you must not change, and — most importantly — **which specific
lines are guesses that you need to check against the real SDK.**

Read section 5 before you write anything. It is the part that will cost you time
if you skip it.

---

## 2. Where the model connects

There is exactly **one seam**. The rest of the package never learns that Google
exists.

| What | Where |
|---|---|
| **The class you own** | `src/procurement_agent/client.py` → `class GeminiBackend` (line 228) |
| **The method you own** | `GeminiBackend.generate()` (line 249) — the only function in the repository that calls the provider |
| **The model string** | `src/procurement_agent/config.py` → `PINNED_MODEL` (line 32) |
| **The API key** | `src/procurement_agent/config.py` → `load_api_key()` (line 133) |
| **The response schema you send** | `src/procurement_agent/schema.py` → `response_schema()` (line 151) |
| **The prompt text you send** | `src/procurement_agent/prompts.py` → `SYSTEM_INSTRUCTION`, `USER_MESSAGE_TEMPLATE` |

Everything else — caching, validation, the safety guard, landed-cost readiness,
the run log, the CLI — sits above this seam and is already working.

### The contract you must satisfy

`GeminiBackend` is one implementation of a protocol (`client.py` line 84):

```python
class Backend(Protocol):
    def generate(
        self,
        system_instruction: str,
        user_message: str,
        config: ExtractionConfig,
    ) -> str:
        """Return the raw response text, or raise a TransportError subclass."""
```

That is the whole contract. Take three arguments, return the response body as a
**string of JSON**, or raise. Do not parse the JSON, do not validate it, do not
retry inside this method, do not log. All of that already happens above you.

---

## 3. What is already built

2,273 lines across nine modules, 135 tests passing.

| Module | Lines | Does | Verified? |
|---|---|---|---|
| `config.py` | 164 | Pinned model string, decoding settings, configuration fingerprint, API key loading from environment | Yes, offline |
| `schema.py` | 542 | The eleven-field Normalised Quotation contract; validation with no salvage path; landed-cost readiness | Yes, offline |
| `prompts.py` | 80 | Literal prompt text from Prompt Specification v1.0 section 8, word for word, versioned | Yes, offline |
| `client.py` | 284 | Transport, error taxonomy, bounded exponential backoff with jitter | Retry logic yes; **the provider call no** |
| `cache.py` | 165 | Content-addressed cache keyed on document **and** configuration fingerprint | Yes, offline |
| `guards.py` | 226 | Prohibited-pattern suppression, six categories (requirement 14.2) | Yes, offline |
| `runlog.py` | 114 | Append-only JSONL evidence log | Yes, offline |
| `extract.py` | 341 | Six-step pipeline orchestration | Yes, offline |
| `cli.py` | 342 | Command-line entry point | Yes, offline |

### The pipeline, in order

For one quotation:

1. **Cache lookup** — SHA-256 of the converted Markdown combined with the full
   configuration fingerprint (model, temperature, thinking budget, max output
   tokens, prompt version). A hit returns with **no API call**. The fingerprint
   is in the key deliberately: keying on the document alone would return a
   result produced under an older prompt version as though it came from the
   current one.
2. **Model call** — ← **this is your part**
3. **Schema validation** — conform or be rejected outright, no salvage
   (requirement 3.3).
4. **Prohibited-pattern scan** — requirement 14.2.
5. **Landed-cost readiness** — names the fields the deterministic calculator
   lacks (requirement 6.3).
6. **Persist** — cache entry plus a run log entry carrying the fingerprint.

### Decoding settings already wired

From Prompt Specification v1.0 section 4. You should not need to change any of
these; if the SDK rejects one, raise it with the team rather than quietly
altering it.

| Setting | Value |
|---|---|
| Model | `gemini-3.1-flash-lite` (exact version, never an alias) |
| Temperature | `0` |
| Max output tokens | `2048` |
| Thinking budget | `0` (spec says "minimum or disabled"; resolved to 0) |
| Response MIME type | `application/json` |
| Response schema | `schema.response_schema()` |

---

## 4. Integration steps

```bash
# 1. Set up. Python 3.10+; verified on 3.13 and 3.14.
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # package + pytest, no SDK yet

# 2. Confirm the offline path works BEFORE you change anything.
#    Neither of these needs a key, a network or the SDK.
pytest                             # expect: 135 passed
python tools/offline_demo.py       # expect: 5 OK, 1 SUPPRESSED, exit code 1

# 3. Install the SDK (an optional extra — the tests do not need it)
pip install -e ".[gemini]"

# 4. Your OWN project and key. Rate limits apply per provider project, not per
#    key: five keys under one project share one quota.
cp .env.example .env
export GEMINI_API_KEY=...

# 5. Now the real thing — start with ONE file, not the whole set
python -m procurement_agent.cli fixtures/01-clean-table-ugx.md

# 6. Only when that works, run the set
python -m procurement_agent.cli fixtures/*.md
```

Start with one file. The free tier's binding constraint is requests per day, and
a loop of failing calls against six fixtures burns quota you cannot get back
until the daily reset (midnight Pacific, mid-morning in Kampala).

### What step 2 should print

```
fixtures/01-clean-table-ugx.md              status: OK           landed-cost READY
fixtures/02-prose-carton-vat-inclusive.md   status: OK           landed-cost READY
fixtures/03-usd-freight-separate.md         status: OK           landed-cost READY
fixtures/04-minimal-missing-fields.md       status: OK           landed-cost NOT READY
fixtures/05-embedded-instruction.md         status: SUPPRESSED   landed-cost READY
fixtures/06-expired-validity.md             status: OK           landed-cost READY

  OK: 5    SUPPRESSED: 1    cache hits: 0
```

**Exit code `1` is correct here**, not a failure. Fixture 05 is deliberately
adversarial and comes back `SUPPRESSED`, so not every file is clean. The CLI
exits `0` only when every file produced a conforming, unsuppressed record.

Run it a second time and every file is a cache hit, no call is made, and the
latency block says so rather than inventing a figure:

```
  cache hits          : 6

latency across live calls (n=0)
  no live calls were made in this run, so no latency figure is available.
  Nothing is estimated here.
```

Other forms of the offline demo, useful while you are iterating:

```bash
python tools/offline_demo.py --json                              # machine-readable
python tools/offline_demo.py fixtures/05-embedded-instruction.md # one file
rm -rf .cache                                                    # force fresh runs
```

The demo prints a banner stating that no API call was made. The records in it
are hand-written and its latency is a `sleep`. It demonstrates the **pipeline**,
never the model.

### CLI flags

Both `python -m procurement_agent.cli` and the installed `procurement-extract`
console script take these:

| Flag | Effect |
|---|---|
| `--json` | Machine-readable output instead of the report |
| `--no-cache` | Bypass the cache; every file makes a live call |
| `--model STRING` | Override the pinned model. Exact version only; an alias ending `-latest` is rejected |
| `--cache-dir DIR` | Cache location (default `.cache/extractions`) |
| `--run-log FILE` | Run log location (default `evidence/traces/extraction-runs.jsonl`) |
| `--max-attempts N` | Bounded retry budget per file (default 4) |

While iterating against the live API, `--cache-dir` and `--run-log` pointed at a
scratch directory keep your experiments out of the committed evidence log.

---

## 5. What is unverified — read this before you start

**The body of `GeminiBackend.generate()` was written without the SDK installed.**
It has never run. It is a good-faith reconstruction of the `google-genai` call
shape, and the following specific things are assumptions you must check against
the real library and the real API:

| Assumption in the code | What to check |
|---|---|
| `genai.Client(api_key=...)` is the constructor | Client construction may differ by SDK version |
| `client.models.generate_content(model=..., contents=..., config=...)` | Argument names and nesting |
| `types.GenerateContentConfig(...)` accepts `system_instruction` | Some versions take it elsewhere, or want a `Content` object rather than a bare string |
| `response_schema=` accepts a **plain dict** in the uppercase OpenAPI style (`{"type": "OBJECT", ...}`) | It may require a `types.Schema`, or a Python type/TypedDict. If it rejects the dict, convert in `GeminiBackend`, **not** in `schema.py` — `schema.py` is the contract and is used by the validator too |
| `types.ThinkingConfig(thinking_budget=0)` exists and `gemini-3.1-flash-lite` supports it | Thinking config may not apply to this model at all. If it errors, that is a real finding — record it and tell the team before removing it |
| `response.text` holds the body | May be nested under candidates/parts |
| Errors expose `.status_code`, `.code` or `.http_status` | `classify_error()` (line 127) reads these to decide retryable vs permanent. If the SDK raises a different shape, **fix the mapping** — otherwise a 429 will be classified as permanent and fail instantly instead of backing off |

**`gemini-3.1-flash-lite` is pinned from the Model Selection Note. Confirm the
string is valid and the model is reachable on the free tier** before assuming a
failure is a code bug. A 404 on the model name will surface as a `PermanentError`
and fail immediately, which is correct behaviour but looks like a crash.

### Claims nobody can make yet

Do not let these into a report until you have measured them:

- **Extraction accuracy against the fixtures.** No model has read them. Success
  criterion S9 has no value.
- **Whether the model resists the embedded instruction in `fixtures/05`.** The
  *guard* is tested and fires; whether the model emits an approval assertion in
  the first place is untested. That is Week 7 evaluation case S8.
- **Measured latency**, median and worst case.
- **Actual free-tier rate limits** (RPM, TPM, RPD) for our project.
- **Schema conformance rate.**

---

## 6. Constraints you must not break

These come from project documents, not from preference. Each has a test that
will fail if you break it.

1. **The model string stays pinned by exact version.** `config.py` rejects
   anything ending `-latest`, `-preview` or `@latest`, including via `--model`.
   An alias would repoint provider-side between two evaluation runs and nothing
   in the run log would show it. *(Model Selection Note; test:
   `test_alias_model_strings_are_rejected`)*
2. **Temperature stays 0.** Extraction is deterministic; variance across
   identical inputs is a defect. `config.py` raises if it is anything else.
   *(Prompt Specification section 4)*
3. **The API key is read from the environment only.** Never hardcode it, never
   log it, never commit it. It must not reach the cache or the run log.
   *(test: `test_the_api_key_never_reaches_the_run_log`)*
4. **The prompt text is not edited without bumping `prompt_version`.** The
   version is part of the cache key and of every run log entry. Editing the text
   while leaving the version invalidates every evaluation result recorded
   against it. *(see `prompts.py` header)*
5. **No arithmetic anywhere in this package.** No totalling, VAT, unit or
   currency conversion, landed cost or ranking. Those belong to the
   deterministic calculator downstream. *(Requirement 6.6, AI Boundary Matrix
   v1.1; test: `test_package_performs_no_arithmetic_on_monetary_values`)*
6. **Quotation content stays wrapped in `<quotation>` delimiters** in the user
   message. That boundary is the injection defence. *(Requirements 3.7 and 14.5)*
7. **Synthetic data only.** Free-tier inputs can be logged by the provider. No
   real supplier, client or commercial data through a free-tier key, ever.
   *(Model Selection Note, section 3)*

---

## 7. How to know your integration is correct

**Nothing in the package above `GeminiBackend` should need to change.** If you
find yourself editing `extract.py`, `schema.py` or `cache.py` to make the call
work, stop — the seam is probably being bypassed.

Check, in this order:

1. `pytest` still passes, 135 tests. The suite must keep running with no key and
   no network; if you made the SDK a hard import, you have broken this.
2. `python tools/offline_demo.py` still gives 5 `OK`, 1 `SUPPRESSED`.
3. One live file returns `status: OK` with eleven fields populated.
4. A second run of the same file says `cache hit (no API call)` and makes no
   request.
5. `evidence/traces/extraction-runs.jsonl` has one row per call, each carrying
   the configuration fingerprint.
6. `fixtures/04` comes back `NOT READY` naming its missing fields.
7. `fixtures/05` comes back `SUPPRESSED` **if** the model echoed the embedded
   instruction — and `OK` if the model ignored it, which is the better outcome.
   Either way, record which happened: that is evaluation case S8.

---

## 8. What to record when you are done

Several documents have figures marked **Pending** waiting on your run. Fill them
in with measurements, never estimates.

| Document | What it needs |
|---|---|
| `docs/week2/Model_Selection_Note.md` — measurement table | RPM, TPM, RPD read from the AI Studio rate limit view **for our own project**, with the date read |
| Same, same table | Median and worst-case extraction latency, with *n*. The CLI prints both across live calls |
| Same, evidence table | Count of extraction calls, how many schema-conformant, how many rejected — from the run log |
| `docs/week2/Prompt_Specification_And_Prompt_Version_History.md` — version history | The `Result` cell for v1.0, against the ten-case evaluation table |
| `docs/AI-ENGINEERING-LOG.md` | A dated entry: what you changed in `GeminiBackend`, which assumptions in section 5 above turned out wrong, and what you measured |

Commit the run log. It is the evidence behind the Model Selection Note's
conformance and backoff claims, and an evidence log that is regenerated rather
than accumulated is not evidence.

---

## 9. If you get stuck

| Symptom | Likely cause |
|---|---|
| `google-genai is not installed` | `pip install -e ".[gemini]"` — it is an optional extra so the tests can run without it |
| `error: No API key found` | `export GEMINI_API_KEY=...`, or use `tools/offline_demo.py` to work without one |
| Fails instantly on a 429 instead of retrying | `classify_error()` is not recognising the SDK's exception shape. Fix the mapping in `client.py`, and add a test |
| Retries four times on a bad API key | Same function, opposite direction — an auth error is being classified as transient |
| A prompt change appears to do nothing | The prompt version is part of the cache key. Bump `prompt_version`, or pass `--no-cache` |
| Everything is a cache hit | Working as designed. `rm -rf .cache` or `--no-cache` |
| `RATE-LIMITED` after several attempts | Daily quota. Resets midnight Pacific, mid-morning Kampala. The run is still in the run log |

---

## 10. Reference

- Requirements Document **v1.1** — `docs/week1/User_Stories_And_Acceptance_Criteria.md`
  (glossary "Normalised Quotation"; requirements 2, 3, 6, 14)
- AI Boundary Matrix **v1.1** — `docs/week1/Ai_Boundary_Matrix.md`
- Project Charter **v1.1** — `docs/week1/Project_Charter.md`
- Prompt Specification **v1.0** — `docs/week2/Prompt_Specification_And_Prompt_Version_History.md`
- Model Selection Note — `docs/week2/Model_Selection_Note.md`
- Working Baseline Model Interaction — `docs/week2/Working_Baseline_Model_Interaction.md`
- Week 2 engineering log entry — `docs/AI-ENGINEERING-LOG.md`
- Setup, running and troubleshooting — `README.md`

### Stale copies on `origin/main` — read before you pick up a file

`origin/main` still carries the pre-audit versions of several documents. After a
merge, the repository will contain both generations side by side. **Do not build
against these:**

| Stale file on `origin/main` | Superseded by |
|---|---|
| `docs/prompts/quotation-extraction-v1.txt` | `src/procurement_agent/prompts.py` and Prompt Specification v1.0 section 8 |
| `docs/requirements/requirements.md` (v1.0) | `docs/week1/User_Stories_And_Acceptance_Criteria.md` (v1.1) |
| `docs/ai-matrix-boundaries/ai-matrix.md` (v1.0) | `docs/week1/Ai_Boundary_Matrix.md` (v1.1) |
| `docs/architecture/architecture.md` (v1.0) | `docs/week1/Initial_Architecture_Context_Diagram.md` (v1.1) |

**`docs/prompts/quotation-extraction-v1.txt` is the one most likely to catch
you.** It is the v0.1 prompt and it asks for **six** fields — supplier, item,
quantity, unit price, currency, validity date. That is precisely the defect the
Week 1 cross-document audit found: six fields cannot produce the inputs for
Landed Cost, which Requirements Document v1.1 makes the basis for supplier
ranking. A supplier quoting per carton, VAT exclusive, with high freight would
outrank a cheaper one and the system would report it as the better option.

The prompt you send is the one in `prompts.py`. It is eleven fields. Do not copy
text out of that `.txt` file.

The team should decide whether to delete these stale files or mark them
superseded; until that happens, this table is the guide.
