# Working RAG Pipeline

| Field | Value |
|---|---|
| Week | 3 |
| Owner | SEKYEZA ELROY |
| Due | 18 September 2026 |
| Status | Complete, awaiting team review |
| Path | `docs/architecture/working-rag-pipeline.md` |

## Brief requirement

Write-up of the working RAG pipeline: how a query is answered from the controlled corpus, how sources are shown in the response or trace, and how unsupported answers are handled. Point at the code and a short run example.

## Write-up

### What it does

The pipeline implements Requirement 7, *Procurement Policy Retrieval*. Given the items on a requisition, it finds the policy clauses that apply to each item, has Gemini explain them, and checks that every clause Gemini cites was actually retrieved for that item before anything is shown.

For example, a requisition for 120 bags of cement at UGX 4,140,000 comes back with the three-quotation rule for purchases between UGX 500,000 and 5,000,000 (POL-001-C02) and the rule that cement must be compared by the same grade and bag size (SPEC-001-C01), each cited by document, version and clause ID.

It follows the three stages in the [RAG architecture](rag-architecture.md).

### How to run it

**1. Install** (Python 3.10 or later, from the repository root)

```bash
pip install -e ".[rag,gemini,dev]"
```

`rag` installs Qdrant and FastEmbed; `gemini` installs the Gemini SDK.

**2. Add your API key.** Copy `.env.example` to `.env` and set `GEMINI_API_KEY`. The key is read from the environment only and never appears in output or traces.

**3. Build the index** (stage 1, run once, and again whenever a policy changes)

```bash
python -m procurement_agent.rag.ingest
```

The first run downloads the embedding model (about 70 MB) into `.cache/fastembed/`. After that it runs offline and takes about 3 seconds.

**4. Check a purchase** (stages 2 and 3)

One item:

```bash
python -m procurement_agent.rag.cli --item "120 bags of cement" --category "building materials" --total 4140000
```

A whole requisition, from a JSON file:

```bash
python -m procurement_agent.rag.cli --requisition fixtures/requisitions/weekly-reorder.json
```

Useful options:

| Option | Effect |
|---|---|
| `--json` | Print the full trace entry instead of the report |
| `--top-k N` | Clauses per search (default 5) |
| `--min-score` / `--item-min-score` | Cutoffs for general rules (0.50) and product specifications (0.58) |
| `--trace-log FILE` | Where the trace is appended (default `evidence/traces/rag-runs.jsonl`) |
| `--model STRING` | Override the pinned Gemini model |

Exit code 0 means every item can be shown, 1 means at least one was withheld, 2 means it could not run.

After `pip install`, the shorter `procurement-policy-ingest` and `procurement-policy` commands do the same thing, if Python's `Scripts` folder is on your `PATH`.

**5. Run the tests** (no key, no network, no model download)

```bash
pytest tests/test_rag_*.py
```

### How a query is answered

| Stage | Architecture box | What happens | Code |
|---|---|---|---|
| 1 | Canonical Policy Store | `knowledge/source-register.csv` holds each document's version and SHA-256 checksum | |
| 1 | Document Loader | Loads policies, procedures and product specifications. Refuses any document that is unregistered, has a different version, or was edited after review | [`corpus.py`](../../src/procurement_agent/rag/corpus.py) |
| 1 | Chunking + Metadata | One chunk per clause (`## POL-001-C02 ...`), carrying document name, version and clause ID. 45 clauses from 12 documents | [`corpus.py`](../../src/procurement_agent/rag/corpus.py) |
| 1 | Embedding Model | `BAAI/bge-small-en-v1.5` through FastEmbed, run locally | [`embedder.py`](../../src/procurement_agent/rag/embedder.py) |
| 1 | Vector Index | Qdrant on disk in `.cache/policy-index/`, with a manifest recording the model and a fingerprint of every clause | [`ingest.py`](../../src/procurement_agent/rag/ingest.py), [`index.py`](../../src/procurement_agent/rag/index.py) |
| 2 | Retrieval Query Builder | Per item: `Purchase of 120 bags of cement, category building materials, estimated total UGX 4,140,000` | [`retriever.py`](../../src/procurement_agent/rag/retriever.py) |
| 2 | Vector Search | Two searches per item, explained below | [`retriever.py`](../../src/procurement_agent/rag/retriever.py) |
| 3 | Prompt Builder + Gemini | Every item with its own clauses goes to `gemini-3.1-flash-lite` in one call, prompt version `grounding-1.1` | [`grounding.py`](../../src/procurement_agent/rag/grounding.py) |
| 3 | Citation Validator | Every cited clause must match, by document, version and clause ID, a clause retrieved for that item | [`citations.py`](../../src/procurement_agent/rag/citations.py) |
| 3 | Officer review | Each item is shown or withheld on its own, and the run is traced | [`pipeline.py`](../../src/procurement_agent/rag/pipeline.py), [`cli.py`](../../src/procurement_agent/rag/cli.py) |

**Why two searches.** General rules (policies and procedures) apply to every purchase, so the top 5 are always kept above a low floor of 0.50. Product specifications apply only to particular goods, so they are kept only above 0.58. One cutoff cannot serve both: every query is phrased as a purchase, so purchases the corpus says nothing specific about still score 0.583 to 0.687 against the general rules, as high as purchases it does cover. Without a specification cutoff, a purchase of airline tickets was matched to the cement specification. Best specification scores do separate, which is where the 0.58 cutoff comes from. Measured over nine purchases:

| Purchase | Best specification score |
|---|---|
| Electrical cable, binding wire, PVC fittings, cement, safety helmets (covered by a specification) | 0.608 to 0.740 |
| Diesel, software licence, airline tickets, staff catering (not covered) | 0.483 to 0.571 |

**Why top 5.** Search finds the right topic but cannot tell which monetary band a figure falls in. For the cement purchase, the applicable clause POL-001-C02 ranked fourth, below the band for purchases over UGX 5,000,000. With 3 results it would have been lost. Choosing the band is left to Gemini, which must cite it.

**Why one Gemini call per requisition.** Requirement 7.1 allows 30 seconds, and the free tier limits requests per day. Items are still searched separately and answered separately inside the call.

### How sources are shown

In the report, every retrieved clause is listed under its item with its score, and every clause Gemini relies on is named in full:

```
    Competitive Quotation Policy v1.0, POL-001-C02
      The estimated total falls within the range for standard purchases.
```

Every run also appends one JSON line to `evidence/traces/rag-runs.jsonl`. It records, per item: the query, every retrieved clause with its score, clauses that fell below a cutoff, absence notes, Gemini's answer, the citation check result and any suppressed patterns. It also records the model, prompt version, attempts and latency. `--json` prints the same entry.

### How unsupported answers are handled

| Situation | What happens | Tested in |
|---|---|---|
| No product specification matches an item | The item carries *"No product specification in the Policy Corpus was found for ..."*, and Gemini is told not to supply one | `test_rag_retrieval.py` |
| Nothing at all matches any item | No Gemini call is made; the absence notes are the answer | `test_rag_pipeline.py` |
| Gemini cites a clause that was not retrieved for that item, including one retrieved for a different item, or an invented one | That item is withheld and the reason is shown, e.g. *"POL-009-C01 was cited but was not among the clauses supplied"*. Other items are still shown | `test_rag_citations.py`, `test_rag_pipeline.py` |
| Gemini cites the right clause at the wrong version or under the wrong document | Withheld | `test_rag_citations.py` |
| Gemini's summary names an unretrieved clause or document in its text | Withheld | `test_rag_citations.py` |
| Gemini asserts approval, supplier selection or a financial commitment | Suppressed under requirement 14.2, and the text is never written to the trace | `test_rag_pipeline.py` |
| Gemini returns malformed JSON or skips an item | Every item that needed the call is withheld; nothing is partly accepted | `test_rag_grounding.py` |
| No index, or a policy changed since ingestion | The command stops with *"run ingest"* and makes no call | `test_rag_ingest.py` |
| Rate limit or network failure | Bounded retries, then the affected items are withheld with the reason | `test_rag_pipeline.py` |

Withheld items keep their retrieved clauses in the output and the trace, so a retry does not need to search again.

### Run example

Recorded on 17 September 2026 against the live API with the sample requisition in [`fixtures/requisitions/weekly-reorder.json`](../../fixtures/requisitions/weekly-reorder.json). Full output: [`evidence/traces/rag-weekly-reorder-run.txt`](../../evidence/traces/rag-weekly-reorder-run.txt). Trace: the entry in [`evidence/traces/rag-runs.jsonl`](../../evidence/traces/rag-runs.jsonl). Index build: [`evidence/traces/rag-ingest-run.txt`](../../evidence/traces/rag-ingest-run.txt).

Item 1:

```
ITEM 1 of 4: 120 bags of cement
============================================================================
  category        : building materials
  estimated total : UGX 4,140,000

  retrieved clauses
    general rules
      0.616  Competitive Quotation Policy v1.0, POL-001-C03  (Higher value purchases)
      0.576  Competitive Quotation Policy v1.0, POL-001-C02  (Standard purchases)
      0.557  Competitive Quotation Policy v1.0, POL-001-C01  (Low value purchases)
      0.551  Quotation Evaluation Policy v1.0, POL-003-C01  (Requisition currency)
      0.528  Weekly Reorder Review Procedure v1.0, PRO-001-C03  (Collect current offers)
    item rules
      0.684  Cement and Masonry Product Specifications v1.0, SPEC-001-C01  (Cement)
      0.585  Cement and Masonry Product Specifications v1.0, SPEC-001-C03  (Substitution)

  explanation
    This purchase requires at least three comparable written quotations from
    eligible suppliers [POL-001-C02]. Any foreign-currency quotations must
    include the original currency and the approved exchange-rate reference
    [POL-003-C01]. The procurement officer must group items, check
    requirements, and assemble offers [PRO-001-C03]. Cement must be compared
    using the same strength grade and 50 kg bag size, with deterministic
    conversion for any prices per tonne [SPEC-001-C01], and any ambiguous
    alternatives require review [SPEC-001-C03].

  citation check  : PASSED, all 5 citation(s) name clauses supplied for this item
  item status     : OK
```

Item 4, which no specification covers:

```
ITEM 4 of 4: diesel for the delivery truck
    item rules
      (none kept)
    notes
      No product specification in the Policy Corpus was found for diesel for
      the delivery truck (fuel).

  explanation
    This purchase requires at least three comparable written quotations from
    eligible suppliers [POL-001-C02]. Foreign-currency quotations must
    include the original currency and exchange-rate reference [POL-003-C01],
    and the procurement officer must assemble offers [PRO-001-C03]. No
    product specification was found for this item in the Policy Corpus.
```

Result: all 4 items shown, every citation grounded, 1 model call, 1 attempt, **42.01 seconds**.

When the index is missing, the command stops before any call:

```
error: no policy index at .cache\does-not-exist. Build it first with `python -m procurement_agent.rag.ingest`.
```

### Known limitations

- **The 30-second limit in requirement 7.1 was not met on the recorded run.** The single Gemini call took 42.01 seconds on its first attempt. An earlier development run of the same requisition, not in the committed evidence, took 6.29 seconds. The time is spent at the provider, so it needs measuring across more runs before anything is concluded.
- **Gemini over-cites the currency rule.** POL-003-C01 concerns foreign-currency quotations, yet it was cited for all four UGX items, and the reasons given were vaguer than in single-item runs. Every citation was still grounded, so nothing unsupported was shown, but this is a precision problem for the 15-case evaluation to measure.
- **Specification cutoffs are borderline.** For binding wire, the cement (0.615) and electrical cable (0.602) specifications passed the 0.58 cutoff. Gemini did not cite them. The cutoffs come from nine purchases and should be tuned by the evaluation.
- **All four sample items fall in the same band** (UGX 500,000 to 5,000,000), so this run does not test band selection at the boundaries.
- **Items are entered by hand.** Requirement 7.1 takes them from the confirmed landed-cost comparison, which no one has built yet. The command line and requisition file stand in for it.
- **State is not kept across sessions.** Requirement 7.5 asks for the comparison table to be preserved for retry. A withheld item keeps its retrieved clauses within the run and the trace; persistent workflow state belongs to the Week 5 state model.
- **The documents disagree on when retrieval happens.** The Project Charter (workflow step 3) retrieves policy before extraction, from an estimated value band. Requirement 7.1 and the RAG architecture retrieve after the comparison is confirmed. This pipeline follows requirement 7.1.
- **The prohibited-pattern guard misses some phrasings,** such as *"Nakawa is selected as the supplier"*. It is shared with extraction in `guards.py`.

### Requirement 7 traceability

| Criterion | How it is met |
|---|---|
| 7.1 Clauses for item names, categories and landed cost, within 30 seconds | One search per item using all three. Latency is not yet within the limit reliably; see limitations |
| 7.2 Only the Policy Corpus | Prompt rule 1, plus the citation validator rejecting anything not retrieved |
| 7.3 Explicit statement when no clause is found for an item | Absence notes, per item |
| 7.4 Clauses shown by document name, version and clause ID | Report output and trace |
| 7.5 Corpus unavailable: notify, halt, allow retry | Missing or stale index stops the command with instructions; comparison-table preservation is pending the calculator |
