# Release notes — v1.0.0

**SME Procurement-Preparation Agent · Group Y · BSE4104 · 23 October 2026**

The final course release. It prepares a weekly reorder review up to a purchase requisition in
`DRAFT`. Every status change beyond `DRAFT`, every approval and every purchase stays with a human.
Run instructions are in the [README](README.md). The evidence index for markers is the
[final evaluation and evidence pack](docs/evaluation/final-evidence-pack.md).

## What is in this release

| Capability | Week | Write-up |
|---|---|---|
| Quotation field extraction with Gemini (prompt v1.4), schema validation, guards, 30 s deadline | 2, 7 | [prompt evaluation](docs/evaluation/prompt-evaluation.md) |
| Policy retrieval over a controlled 12-document, 45-clause corpus, with citation validation | 3 | [RAG pipeline](docs/architecture/working-rag-pipeline.md) |
| Four deterministic tools behind one dispatcher: role injection, allow-list, input and output schema checks | 4 | [tools](docs/architecture/working-tools.md) |
| Bounded agent: per-step allow-list, 8-iteration cap, officer gates, contract loaded at runtime | 5 | [agent](docs/architecture/working-agent.md), [contract](docs/requirements/agent-task-contract.md) |
| Checkpointed run state (resume, no duplicate requisitions) and advisory memory | 6 | [memory and state](docs/architecture/working-memory.md), [state model](docs/architecture/state-model.md) |
| 45-scenario evaluation, guardrail evidence, observability, failure catalogue | 7 | [scenarios](docs/evaluation/scenarios.md), [guardrails](docs/evaluation/guardrails.md), [failures](docs/evaluation/failure-catalogue.md) |
| Hardening: four reproduced high-severity defects fixed, limitations register | 8 | [hardening and limitations](docs/architecture/known-limitations.md) |

## Verified at release

Every check below ran in a **fresh clone of `0496a03`** with no local changes, on Python 3.14.7.
The release tag adds only documentation, evidence and the version number (`1.0.0` in
`pyproject.toml` and `procurement_agent/__init__.py`); apart from that string, no source, tool,
contract or data file differs from `0496a03`. The raw output is in
[`evidence/release/v1.0.0/`](evidence/release/v1.0.0/).

| Check | Result |
|---|---|
| `pip install -e ".[dev]"`, then `pytest` | **452 passed**, 7 skipped (the optional extras), 0 failed |
| `pip install -e ".[dev,rag,gemini]"`, policy index built, then `pytest` | **541 passed**, 0 skipped, 0 failed |
| All 45 scenarios **including the 8 live Gemini scenarios** | **45/45 pass, 0 safety violations**; every live call ≤ 8.1 s (median 2.39 s) |
| Agent run as in the README: stop at Gate 2, then confirm | Resumes from the checkpoint and compiles one DRAFT (4/8 iterations) |
| Offline demo, no API key | Runs; writes only to `var/offline-demo/` |

This run closes item 3 of the evidence pack ("live scenarios not run since 19 October"). It also
updates the evidence behind limitation KL-01: the clean quotation S-38, which timed out at 30 s on
19 October, passed in 2.4 s here. Free-tier latency varies between runs, so the 30 s deadline can
still be reached; KL-01 still stands as a limitation.

## Evaluation history

| Run | Scenarios | Result | Evidence |
|---|---|---|---|
| 13 Oct, first full run | 45 | 40 pass, 5 genuine failures found | [`week-07/`](evidence/evaluation/week-07/) |
| 19 Oct, after the S-09/S-12 and FC-08/FC-09 fixes | 45 | 44 pass (S-38 timeout) | [`week-07-final/`](evidence/evaluation/week-07-final/) |
| 20 and 22 Oct, after hardening (offline) | 37 | 37 pass | [`week-08-hardening/`](evidence/evaluation/week-08-hardening/), [`week-08-clean/`](evidence/evaluation/week-08-clean/) |
| **23 Oct, release** | **45** | **45 pass** | [`release/v1.0.0/scenarios/`](evidence/release/v1.0.0/scenarios/) |

Safety violations were 0 in every run.

## Deliberately not built

These are specified in the charter and requirements but out of reach in eight weeks. They are
recorded, with their risks, in the [limitations register](docs/architecture/known-limitations.md):

- **No user interface, authentication or database.** Gates are command-line flags; `--role` and
  `--officer` are trusted (KL-02). Storage is local JSON/JSONL with no transactions or locking
  (KL-03, KL-09, KL-10).
- **Gates 4 and 5 are not built** (submit, routing, manager approval and the Approval Record).
  Every run ends at `DRAFT`.
- **The designed AI workflow is not fully integrated** (KL-04). The planner is deterministic;
  extraction and policy retrieval run as separate commands; the justification is compiled from
  a template.
- **No document conversion or OCR.** Extraction starts from converted Markdown (KL-08).
- **Synthetic data only.** The free-tier model key must not receive real supplier data.

## Known minor issue

The offline demo labels its scripted record `source: live call`, because to the extraction
command it is a cache miss with one attempt. The demo's banner states that no API call was made.

## Team

Nannyombi Shakiran, Ainamani Jim Isaac, Beingana Jim Junior, Sekyeza Elroy Nunda,
Lukaanya George. Task board: [ClickUp](https://app.clickup.com/9012272120/v/s/90129079418).
