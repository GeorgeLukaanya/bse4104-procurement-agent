# SME Procurement-Preparation Agent

**AI-Native & Agentic Engineering Capstone** under BSE4104 Emerging Trends in Software Engineering, Makerere University, College of Computing and Information Sciences

## What this is

A bounded agentic system that helps a procurement officer in a small or medium
Ugandan enterprise turn a weekly reorder review into a policy-compliant purchase
requisition, ready for a human manager to approve.

AI reads and normalises unstructured supplier quotations, retrieves applicable
procurement policy and drafts a written justification. Deterministic code performs
all arithmetic, eligibility checks and approval routing. The system never issues a
purchase order, contacts a supplier, commits funds or approves anything itself.

## Status

**Week 8 of 8 — hardening and known limitations.**

The current command-line components are:

- **Quotation extraction** (Week 2) — takes a Converted Quotation Document in
  Markdown and returns a validated eleven-field Normalised Quotation record.
- **Policy retrieval** (Week 3) — retrieves applicable procurement policy clauses
  from a controlled 12-document, 45-clause corpus and grounds an answer in them,
  validating every citation against what was actually retrieved.
- **Procurement tools** (Week 4) — four deterministic functions
  (`check_reorder_need`, `check_supplier_eligibility`, `compare_quotations`,
  `create_requisition_draft`) called through `dispatch.invoke`. No model is
  involved. Write-up: [`docs/architecture/working-tools.md`](docs/architecture/working-tools.md).
- **Bounded agent** (Week 5) — sequences those tools for one weekly reorder
  review, with an eight-iteration default cap and officer confirmation before a DRAFT is
  written. Write-up: [`docs/architecture/working-agent.md`](docs/architecture/working-agent.md).
- **Persistent state and advisory memory** (Week 6) — resumes interrupted reviews,
  prevents ordinary completed-run duplicates and shows prior outcomes and supplier notes.
  Write-up: [`docs/architecture/working-memory.md`](docs/architecture/working-memory.md).

The agent-task contract and persistent state are implemented. Policy retrieval and
quotation extraction still run separately from the deterministic agent workflow;
model-written justification, document conversion and a user interface remain unbuilt.
See the [Week 8 hardening and limitations register](docs/architecture/known-limitations.md)
for fixes, verification evidence and the remaining deployment constraints.

There is deliberately **no application framework**. Django, FastAPI and Flask are
all absent, because the charter has not chosen one. The package is importable and
will be consumed by whatever interface the team picks later.

## Quick start

Requires Python 3.10 or newer. Week 8 hardening was verified on 3.11; 3.10 is
the floor declared in `pyproject.toml` but was not tested in this review.

```bash
git clone https://github.com/GeorgeLukaanya/bse4104-procurement-agent.git
cd bse4104-procurement-agent

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e ".[dev]"            # package + pytest
```

### Run the tests

The suite needs **no API key, no network and no provider SDK**. It injects a stub
backend, so it consumes none of the free-tier daily quota.

```bash
pytest
```

Tests that need optional extras are skipped unless those extras are installed:

```bash
pip install -e ".[dev,rag,gemini]"   # complete offline suite, including RAG and SDK checks
```

### See it run without a key

You do not need an API key to watch the whole pipeline work. This drives the
real CLI with a scripted backend:

```bash
python tools/offline_demo.py                            # all six fixtures
python tools/offline_demo.py --json                     # machine-readable
python tools/offline_demo.py fixtures/05-embedded-instruction.md
```

It exercises every step — cache, schema validation, the requirement 14.2 guard,
landed-cost readiness, the run log — and spends no quota.

**It is a demonstration of the pipeline, not of the model.** The records are
hand-written and the latency is a `sleep`. Nothing it prints is evidence about
`gemini-3.1-flash-lite`. It prints a banner saying so. Its cache and run log live
under `var/offline-demo/` (git-ignored), so it can never feed a live run or add
rows to `evidence/traces/`.

### What you should see

One block per file. A clean quotation:

```
========================================================================
fixtures/01-clean-table-ugx.md
========================================================================
status              : OK
source              : live call
latency             : 0.050s  (1 attempt(s))
cache key           : 8618c725991220cc…

quotation-level fields
  supplier name           : Nakawa Building Supplies Ltd
  currency                : UGX
  VAT treatment           : exclusive
  VAT rate (%)            : 18
  delivery/freight cost   : 250000
  lead time (days)        : 5
  validity date           : 2026-10-02

line items (3)
  [1]
      item name           : Portland cement, 50 kg bag
      quantity offered    : 120
      unit of measure     : per bag
      unit price          : 34500
  ...

missing fields (0)
suppressed patterns (0)
  (none — requirement 14.2 scan clean)

landed-cost readiness: READY
  all inputs present; eligible for automated ranking by the deterministic calculator
```

A quotation that cannot be ranked names every field it is missing, and why:

```
landed-cost readiness: NOT READY
  excluded from automated ranking and presented separately (requirement 6.3). Missing:
    - vat_treatment (req 6.3): VAT treatment not stated, so an inclusive price
      cannot be distinguished from an exclusive one
    - delivery_cost (req 6.3): delivery or freight cost not stated, so it cannot
      be apportioned into landed cost
    - currency (req 6.1): currency not stated, so it cannot be determined whether
      the Configured Exchange Rate applies
```

A quotation carrying an embedded instruction has the prohibited text removed
before it reaches the record:

```
status              : SUPPRESSED
  supplier name           : [SUPPRESSED: prohibited pattern, requirement 14.2]

suppressed patterns (1)
  [approval_assertion] at supplier_name
      approval asserted: …Ltd has been pre-approved by management
```

And the summary across the batch:

```
SUMMARY
========================================================================
  OK                  : 5
  SUPPRESSED          : 1
  cache hits          : 0

latency across live calls (n=6)
  median              : 0.050s
  worst case          : 0.050s
```

Run it a second time and every file is a cache hit, no call is made, and the
latency block says so rather than inventing a figure:

```
  cache hits          : 6

latency across live calls (n=0)
  no live calls were made in this run, so no latency figure is available.
  Nothing is estimated here.
```

Expected across the six fixtures: five `OK`, one `SUPPRESSED` (fixture 05), and
one `NOT READY` for landed cost (fixture 04). Exit code `1`, because not every
file came back clean — that is the correct result, not a failure to run.

### Run a real extraction

> **Wiring up the model for the first time?** Read
> [`docs/architecture/model-integration-handover.md`](docs/architecture/model-integration-handover.md)
> first. The body of `GeminiBackend.generate()` was written without the SDK
> installed and has never executed — that document lists exactly which lines are
> assumptions to check against the real library.

A live run needs the Gemini SDK and your own API key:

```bash
pip install -e ".[gemini]"

cp .env.example .env               # then fill in GEMINI_API_KEY
export GEMINI_API_KEY=...          # read from the environment only

python -m procurement_agent.cli fixtures/*.md
```

`procurement-extract fixtures/*.md` is installed as an equivalent console script.

Use your **own** provider project and key. The Model Selection Note records that
rate limits apply per project, not per key: five keys under one project share one
quota, and a quota exhausted in an afternoon session does not reset until
mid-morning Kampala time the next day.

With no key set, the CLI exits `2` and makes no request:

```
error: No API key found. Set one of GEMINI_API_KEY, GOOGLE_API_KEY, MODEL_API_KEY ...
No request was made. Set the key and re-run:
    export GEMINI_API_KEY=...
```

### Run policy retrieval

The Week 3 pipeline. It needs the `rag` extra, and the index must be built once
before the first query.

```bash
pip install -e ".[rag,gemini]"

python -m procurement_agent.rag.ingest        # build the index, ~3s after first run
```

The first ingest downloads the embedding model (about 70 MB) into
`.cache/fastembed/`. After that it is offline. The index lands in
`.cache/policy-index/` and is rebuilt whenever a corpus document changes — a
stale index is refused, not silently used.

Then query it, one item or a whole requisition:

```bash
python -m procurement_agent.rag.cli \
    --item "120 bags of cement" --category "building materials" --total 4140000

python -m procurement_agent.rag.cli --requisition fixtures/requisitions/weekly-reorder.json
```

`procurement-policy` and `procurement-policy-ingest` are installed as equivalent
console scripts. Exit code is `0` when every item was shown, `1` when any answer
was withheld, `2` when the pipeline could not run.

Every answer cites document name, version and clause identifier, and a citation
that was not retrieved *for that item* is rejected even if the clause exists in
the corpus. When no clause matches, the pipeline says so rather than inventing a
rule.

## Run the tools (Week 4)

No API key. The role is injected by the CLI (`--role`, default
`PROCUREMENT_OFFICER`) and is never taken from the JSON payload.

```bash
python -m procurement_agent.tools.cli check_reorder_need \
    --review-date 2026-09-25 --sku AH-CM-001 --sku AH-HT-012 --json

python -m procurement_agent.tools.cli compare_quotations \
    --sku AH-CM-001 --quantity 120 --date 2026-09-25 --json

python -m procurement_agent.tools.cli create_requisition_draft \
    --file fixtures/tools/cement-draft.json --json
```

`procurement-tools` is the installed console script. Every call appends one line
to `evidence/traces/tool-runs.jsonl`. Drafts land in `var/requisitions.jsonl`
(git-ignored) with status `DRAFT` only. Write-up:
[`docs/architecture/working-tools.md`](docs/architecture/working-tools.md).

## Run the bounded agent (Week 5)

No API key. Direct orchestration over the four catalogue tools. The officer
starts the run; the loop stops on a named reason rather than running forever.

```bash
python -m procurement_agent.agent.cli \
    --review-date 2026-09-25 --sku AH-CM-001

python -m procurement_agent.agent.cli \
    --review-date 2026-09-25 --sku AH-CM-001 \
    --confirm-comparison --confirm-draft
```

`procurement-agent` is the installed console script. Exit `0` when a DRAFT is
written or nothing needs reordering, `1` when the officer must confirm, `2` on
a cap, failure or unauthorized start. Write-up:
[`docs/architecture/working-agent.md`](docs/architecture/working-agent.md).

Since Week 6 a re-run of the same review resumes from a checkpoint in
`var/agent-state/` instead of repeating steps (`--fresh` starts over), and
advisory memory from `var/memory/` is shown beside the result without changing
any decision (`--no-memory` hides it). `procurement-memory` adds, lists and
deletes supplier notes. Write-up:
[`docs/architecture/working-memory.md`](docs/architecture/working-memory.md).

### What a run produces

| Path | Contents | Tracked? |
|---|---|---|
| `.cache/extractions/*.json` | One entry per document+configuration pair | No, git-ignored |
| `evidence/traces/extraction-runs.jsonl` | Append-only extraction log, one JSON object per call | Yes — this is the evidence |
| `evidence/traces/tool-runs.jsonl` | Append-only tool log, one JSON object per call | Yes — this is the evidence |
| `evidence/traces/tools/*.json` | Indented copies of the recorded tool run | Yes — easier to read |
| `evidence/traces/agent-runs.jsonl` | Append-only agent log, one JSON object per run | Yes — this is the evidence |
| `evidence/traces/agent/*.json` | Indented copies of the recorded agent runs | Yes — easier to read |
| `var/requisitions.jsonl` | Local DRAFT store | No, git-ignored |

Clear the cache to force live calls: `rm -rf .cache` (or pass `--no-cache`).
Do not hand-edit the run log; an evidence log that can be edited is not evidence.

### CLI options

| Flag | Effect |
|---|---|
| `--json` | Emit machine-readable JSON instead of the report |
| `--no-cache` | Bypass the cache; every file makes a live call |
| `--model STRING` | Override the pinned model. Must be an exact version; an alias ending in `-latest` is rejected |
| `--cache-dir DIR` | Cache location (default `.cache/extractions`) |
| `--run-log FILE` | Run log location (default `evidence/traces/extraction-runs.jsonl`) |
| `--max-attempts N` | Bounded retry budget per file (default 4) |

Exit code is `0` only when every file produced a conforming, unsuppressed record.

The CLI prints, per file: status, all eleven fields, line items, missing fields
with their reasons, suppressed patterns, landed-cost readiness, and latency with
attempt count. At the end it prints median and worst-case latency **across live
calls only** — cache hits made no request, and counting them would misrepresent
what the model costs. With no live calls it says so rather than printing a
figure.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `error: No API key found...` | Expected without a key. Either `export GEMINI_API_KEY=...`, or use `python tools/offline_demo.py` to run with no key at all. |
| `google-genai is not installed` | The SDK is an optional extra, so the tests can run without it. `pip install -e ".[gemini]"`. |
| `No module named procurement_agent` | The package was not installed, or the wrong virtualenv is active. Run `pip install -e ".[dev]"` from the repo root with `.venv` activated. |
| `pytest: command not found` | `pip install -e ".[dev]"` — pytest comes from the `dev` extra. |
| Exit code `1` on the fixtures | Correct. Fixture 05 is deliberately adversarial and comes back `SUPPRESSED`, so not every file is clean. |
| Everything is a cache hit and no call happens | Working as intended. `rm -rf .cache` or pass `--no-cache`. |
| A changed prompt seems to have no effect | The prompt version is part of the cache key. Bump `prompt_version` in `config.py` — see **Changing the prompt** below. |
| HTTP 429 during a live run | Free-tier quota. The client retries with bounded backoff and then reports `RATE-LIMITED` by name. The daily quota resets at midnight Pacific, mid-morning in Kampala. |

## Use it as a library

```python
from procurement_agent.client import GeminiBackend
from procurement_agent.config import ExtractionConfig, load_api_key
from procurement_agent.extract import Extractor

extractor = Extractor(
    backend=GeminiBackend(api_key=load_api_key()),
    config=ExtractionConfig(),          # pinned model, temperature 0, prompt v1.0
)

result = extractor.extract_path("fixtures/01-clean-table-ugx.md")
if result.ok:
    print(result.record.supplier_name, result.record.items[0].unit_price)
if not result.landed_cost.ready:
    print("excluded from ranking, missing:", result.landed_cost.blocking_fields)
```

Inject any object with a `generate(system_instruction, user_message, config)`
method as the backend to run offline. That method is the only place in the
repository that talks to the provider — see
[`docs/architecture/model-integration-handover.md`](docs/architecture/model-integration-handover.md).

## What the package does, in order

For one quotation:

1. **Cache lookup** — keyed on SHA-256 of the converted Markdown **combined with
   the full configuration fingerprint** (model, temperature, thinking budget, max
   output tokens, prompt version). A hit makes no API call. Keying on the
   document alone would return a result produced under an older prompt version as
   though it came from the current one.
2. **Model call** — schema-constrained decoding via the `response_schema` feature
   of google-genai, with bounded exponential backoff and jitter on 429, 500, 503
   and timeouts. Non-retryable errors fail immediately rather than burning the
   retry budget.
3. **Schema validation** — conform or be rejected outright. No salvage
   (requirement 3.3).
4. **Prohibited-pattern scan** — approval assertions, contract awards, purchase
   order instructions, vendor selection, financial commitments and
   prompt-injection echoes (requirement 14.2).
5. **Landed-cost readiness** — reports the specific fields the deterministic
   calculator is missing (requirement 6.3).
6. **Persist** — cache entry plus an append-only run log entry carrying the
   configuration fingerprint.

### The package performs no arithmetic

No totalling, no VAT application, no unit conversion, no currency conversion, no
landed cost, no ranking. All of that belongs to the deterministic calculator.
That calculator is now `src/procurement_agent/tools/compare.py` (Requirement 6.6).
The extraction package still does none of this arithmetic.

## Repository layout

| Path | Contents |
|---|---|
| `src/procurement_agent/` | Extraction, RAG and tools packages |
| `tests/` | Test suite — runs with no key, no network, no quota |
| `fixtures/` | Synthetic quotation fixtures in Markdown |
| `tools/offline_demo.py` | Drive the CLI with no key, no network, no quota |
| `docs/README.md` | Week-by-week deliverable index, owners and ClickUp copy list |
| `docs/requirements/` | Charter, user stories, AI boundary matrix |
| `docs/architecture/` | Diagrams, model note, baseline, RAG and tools write-ups, tool catalogue, integration handover, CI map |
| `docs/architecture/schemas/` | JSON Schema contracts for the four tools and the data records |
| `docs/weekly-reports/` | Weekly progress reports |
| `docs/evaluation/` | Prompt and later-week evaluation tables |
| `docs/AI-ENGINEERING-LOG.md` | Material AI-assisted decisions, per brief section 6 |
| `prompts/` | Versioned prompt specifications |
| `evidence/` | Traces, screenshots, demo recordings |
| `knowledge/corpus/` | The controlled 22-document synthetic corpus |
| `knowledge/data/` | Operational records the tools read — inventory, suppliers, quotations |
| `knowledge/source-register.csv` | Provenance and SHA-256 for every corpus document and dataset |
| `evaluation-cases/` | Synthetic input documents for the prompt evaluation |

| Module | Responsibility |
|---|---|
| `config.py` | Pinned model string, decoding settings, fingerprint, key loading |
| `schema.py` | The eleven-field Normalised Quotation contract and landed-cost readiness |
| `prompts.py` | Literal prompt text from Prompt Specification section 8, versioned |
| `client.py` | Gemini transport with bounded retry; backend is injectable |
| `cache.py` | Content-addressed cache keyed on document **and** configuration |
| `guards.py` | Prohibited-pattern suppression |
| `runlog.py` | Append-only JSONL evidence log |
| `extract.py` | Pipeline orchestration |
| `cli.py` | Command-line entry point for extraction |
| `rag/corpus.py` | Load and verify the corpus against the register; split into citable clauses |
| `rag/embedder.py` | FastEmbed local embeddings, asymmetric query/passage |
| `rag/index.py` | Qdrant local-mode vector index over clauses |
| `rag/ingest.py` | Offline index build, manifest, staleness refusal |
| `rag/retriever.py` | Two-search retrieval with calibrated cutoffs |
| `rag/grounding.py` | Grounded generation, one call per requisition |
| `rag/citations.py` | Reject any citation not retrieved for that item |
| `rag/pipeline.py` | Retrieve → generate → scan → validate → trace |
| `rag/cli.py` | Command-line entry point for policy retrieval |
| `tools/dispatch.py` | Orchestration: injected role, allow-list, confirmation gate |
| `tools/reorder.py` | `check_reorder_need` |
| `tools/eligibility.py` | `check_supplier_eligibility` |
| `tools/compare.py` | `compare_quotations` — the landed-cost calculator |
| `tools/draft.py` | `create_requisition_draft` — DRAFT write only |
| `tools/cli.py` | Command-line entry point for the four tools |
| `agent/workflow.py` | Bounded reorder-to-DRAFT loop, iteration and timeout caps |
| `agent/planner.py` | Next-tool proposal (deterministic by default) |
| `agent/cli.py` | Command-line entry point for the agent |
| `agent/checkpoint.py` | Saves and restores run state so a re-run resumes |
| `memory/store.py` | Advisory memory: prior outcomes and supplier notes, retention, deletion |
| `memory/cli.py` | `procurement-memory` officer commands |

## Specification

The package is built against these documents. Where they say something specific,
they govern:

- Project Charter **v1.1** — `docs/requirements/project-charter.md`
- Requirements Document **v1.2** — `docs/requirements/user-stories.md`
- AI Boundary Matrix **v1.1** — `docs/requirements/ai-boundary-matrix.md`
- Prompt Specification **v1.4** — `prompts/quotation-extraction-v1.md`
- Model Selection Note — `docs/architecture/model-selection-note.md`
- Corpus Source Register **v1.0** — `knowledge/source-register.md`
- RAG architecture — `docs/architecture/rag-architecture.md`
- Tool Catalogue **v1.0** — `docs/architecture/tool-catalogue.md`
- Week-by-week index — `docs/README.md`

The prompt actually sent lives in `prompts.py` (eleven fields, version 1.4). The
17 October live regression passes all ten cases, including TC-04 unit preservation.
The shared Gemini client enforces a 30-second budget including retries, with a
structured `timeout` result when it cannot complete. See the
[FC-08 / FC-09 closure evidence](docs/evaluation/fc08-fc09-follow-up.md).
Historical v1.1 and v1.3 runs remain in the evaluation report.

## Changing the prompt

The literal prompt text in `prompts.py` matches Prompt Specification section 8
word for word. Changing it **without bumping `prompt_version` in `config.py`
invalidates every evaluation result recorded against the old version** — the
version is part of the cache key and of every run log entry, so results produced
under the old wording would be served and reported as though they came from the
new one.

To change it: edit the text, bump the version, add a row to the Prompt Version
History table in `prompts/quotation-extraction-v1.md` naming the evaluation case
that forced the change, and re-run the evaluation set.

## Security and data

- The API key is read from the environment only. It is never hardcoded, never
  written to the cache or the run log, and is redacted from transport errors.
  `.env` is git-ignored; verify with `git check-ignore -v .env`.
- All data is synthetic and team-created. No real supplier, customer or financial
  records are used anywhere in this project. The Model Selection Note makes this
  a hard operating rule: free-tier inputs can be logged by the provider.
- Quotation content is untrusted. It is wrapped in `<quotation>` delimiters in
  the user message so the model has an explicit boundary between instruction and
  data, and output is scanned for prohibited patterns on the way back.

## Measured, and still unknown

Live calls have been made. These figures are recorded, not estimated:

| Measure | Result | Source |
|---|---|---|
| Prompt case pass rate (v1.4) | 10 of 10 — 100% | `docs/evaluation/fc08-fc09-follow-up.md` |
| Schema conformance | 10 of 10 — 100% | same |
| Extraction latency (v1.4) | median 3.2218s, worst 15.6125s | same |
| RAG case pass rate | 13 of 15 | `docs/evaluation/rag-evaluation.md` |
| RAG requisition latency | 42.01s on one Gemini call | `evidence/traces/rag-weekly-reorder-run.txt` |

**FC-08 and FC-09 are fixed as of 17 October 2026.** TC-04 and S-41 both return
exactly `each`. S-41, S-44 and S-45 passed together at 5.9860s, 2.5054s and
25.1461s. The client now enforces the 30-second ceiling across attempts and waits;
timeouts withhold the model result and retain the error and elapsed time in the
logs. The full local suite passed 511 tests, including 28 client/timeout tests.
The older RAG measurements above remain historical observations. A passing run
does not establish repeated-run provider reliability.

Still unknown:

- Actual free-tier rate limits (RPM, TPM, RPD) for our project — read them from the
  AI Studio rate limit view and record the date
- Whether the tool contracts hold in implementation — no tool is built yet

See `docs/AI-ENGINEERING-LOG.md`.

## Team

Group Y — BSE4104.

| Role | Member | GitHub |
|---|---|---|
| Project / Requirements Lead | Nannyombi Shakiran | [Shakiran-Nannyombi](https://github.com/Shakiran-Nannyombi) |
| Application / Integration Lead | Ainamani Jim Isaac | [Jimisaq](https://github.com/Jimisaq) |
| AI Engineering Lead | Beingana Jim Junior | [jim-junior](https://github.com/jim-junior) |
| Quality / Security Lead | Sekyeza Elroy Nunda | [NundaElroy](https://github.com/NundaElroy) |
| DevOps / Documentation Lead | Lukaanya George | [GeorgeLukaanya](https://github.com/GeorgeLukaanya) |

Roles rotate. Every member is accountable for explaining any part of the system.

## AI use declaration

AI tools are used for design, coding, testing, documentation and evaluation in this
project, as the course expects. Tools used and material AI-assisted decisions are
recorded in `docs/AI-ENGINEERING-LOG.md`. All generated code is reviewed and tested
before merge, and every team member can explain the work submitted under their name.

## Task board

ClickUp: [Group Y board](https://app.clickup.com/9012272120/v/s/90129079418)

Weekly deliverables, owners and GitHub paths: [`docs/README.md`](docs/README.md). Copy the ClickUp list from that file onto the board, one list per week.

## CI

Every push and pull request runs GitHub Actions: pytest, Bandit, Semgrep, pip-audit, a secrets check, and a check that the branch contains latest `main`. Read [`docs/architecture/ci.md`](docs/architecture/ci.md) for what each job means and how to run the same commands locally.
