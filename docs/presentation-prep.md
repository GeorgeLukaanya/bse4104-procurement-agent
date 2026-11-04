# Group Y Presentation Prep

BSE4104 capstone, SME Procurement-Preparation Agent. For the final presentation.
A crib sheet for the team on the day, not a graded deliverable. The deliverable
is [`final-presentation.md`](architecture/final-presentation.md).

[Repository](https://github.com/GeorgeLukaanya/bse4104-procurement-agent) ·
[Release v1.0.1](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/releases/tag/v1.0.1) ·
[ClickUp board](https://sharing.clickup.com/9012272120/l/h/5-901213426906-1/31d463956153cf6)

---

# Part 1. On the day

## Setup, on the presenting laptop

```bash
git pull
pip install -e ".[ui]"
PROCUREMENT_UI_DIR=$PWD/var/ui-demo procurement-ui --server.address=localhost
```

The `PROCUREMENT_UI_DIR` is what makes cement show "Not started" instead of a
half-finished review from rehearsal. The demo needs no internet and no API key.
Only extraction and RAG do, so bring a key only if you plan to show them.

## Who does what

| Part | Who | Backup |
|---|---|---|
| Pitch 1: problem, users, what it refuses to do | George | Ainamani Jim |
| Pitch 2: how it works, from the deck | Shakiran | Ainamani Jim |
| Architecture | Sekyeza | Ainamani Jim |
| Live demo | Shakiran | Jim Junior |
| Evidence: evaluation, tests, CI, release | George | Ainamani Jim |
| Slides | Ainamani Jim | Jim Junior |
| Q: AI, prompts, limitations | Jim Junior | Ainamani Jim |
| Q: RAG, Gemini, data | Sekyeza | Jim Junior |
| Q: traces, failure catalogue | Ainamani Jim | George |
| Q: evaluation, CI, state | George | Ainamani Jim |

**Order:** pitch (George, Shakiran) → architecture (Sekyeza) → demo (Shakiran) →
evidence (George) → questions.

**Rules.** Everyone learns the architecture script below. Hand over by name when
a question is not yours. Let the failures happen on screen and say so. One full
rehearsal.

---

# Part 2. What to say

## The architecture script, one minute, anyone can give it

> "It's a bounded agent, not an autonomous one. An officer starts a weekly
> reorder review. The agent runs four fixed steps: check stock, check supplier
> eligibility, compare landed costs, draft a requisition. It can only act
> through four tools.
>
> Every tool call goes through one door, the dispatcher. It checks who is
> asking, whether that tool is allowed at this step, and that the input and
> output are the right shape.
>
> The model is used at two edges only. Gemini reads supplier quotations into
> structured fields, and RAG finds the policy clause that applies. The
> arithmetic, eligibility rules and ranking are plain Python, so the same inputs
> always give the same answer. The loop itself calls no model.
>
> It stops twice for the officer: once to confirm the comparison, once before
> writing. The only thing it can ever write is a requisition in DRAFT. No
> purchase orders, no supplier contact, no payment."

Then point at the README architecture diagram.

## The demo, about three minutes

| # | Do this | They should see |
|---|---|---|
| 1 | Cement AH-CM-001, Start review | Stops for confirmation. Ranks QT-002, Bugolobi Hardware Supplies, UGX 4,479,600. Exclusions explained: two Lakeview name mismatches, Kireka blacklisted. Policy exception flagged, 1 of 3 required quotations eligible |
| 2 | Type the exception reason, confirm | REQ-2026-001 in DRAFT. Reopen it: no second draft is created |
| 3 | Safety helmet AH-HT-001 | A USD quotation, so it refuses to guess a rate and asks |
| 4 | Binding wire AH-CM-002 | No eligible offer, so nothing is written |
| 5 | Switch to manager role | Refused, POL-004-C03 |

Steps 3 to 5 are the real failures the brief asks for. Do not apologise for
them, they are the point.

## George's evidence segment, two minutes

1. `python tools/run_scenarios.py --output-dir var/eval-demo` live. No key, no
   internet. Ends 37/37, 0 safety violations. Say the 8 live scenarios ran at
   release: 45/45.
2. S-38, the one real failure found: a valid quotation that timed out at
   29.95 s. Kept as a limitation instead of raising the timeout.
3. PR #88 checks on GitHub: tests, Bandit, Semgrep, pip-audit, secrets.
4. `.semgrep/agent-safety.yml`: the build fails if anyone adds code to place
   orders, contact suppliers or commit funds.
5. Close on v1.0.1, verified from a fresh clone.

---

# Part 3. If asked

## Questions

| Question | Answer |
|---|---|
| Why not let the LLM pick the tool? | Predictability and audit. Money decisions need the same answer every time. The model reads documents; code decides. |
| What stops it buying something? | No tool can. Writes are DRAFT only, enforced in the dispatcher, and CI blocks purchase or payment code. |
| What if Gemini is down or wrong? | Extraction has a 30 s budget and fails visibly with no record created. Output is schema-checked and the officer checks it at the first gate. The loop does not need the model at all. |
| How do you know it works? | 45 scenarios, 554 tests, CI on every PR. 45/45 at release, 0 safety violations. |
| Biggest limitation? | No login: identity and confirmations are trusted flags (KL-02). Extraction and RAG are not wired into the loop (KL-04). |
| Why RAG and not policy in the prompt? | Citations. Every answer points to a specific clause and version, and invalid citations are withheld. |
| How does memory not leak into decisions? | It is displayed only. A test runs every decision with and without memory and requires identical results. A note saying a supplier is "cleared" does not clear a name discrepancy. |
| What if the data files are edited? | Every file is checksummed in the source register. A change is detected and a resumed review re-runs the steps that read it. |
| Where is the data from? | All synthetic, written by us. Only synthetic data ever reaches Gemini. |

## Limitations to own

| ID | Limitation |
|---|---|
| KL-01 | A valid quotation can time out (S-38). Kept the 30 s budget; the officer reruns extraction |
| KL-02 | No login. Role and confirmations are trusted inputs, not signed decisions |
| KL-03 | Local writes are not transactional; one process per store |
| KL-04 | Extraction and RAG have separate entry points; the loop uses a deterministic planner and template justification |
| KL-05 | One run, one flagged item; a review per SKU |
| KL-06 | The cost calculator handles the registered conventions and UGX/USD only |
| KL-07 | RAG evaluated on 12 documents and 45 clauses; a valid citation proves provenance, not every claim |
| KL-08 | Extraction takes converted Markdown; no PDF or OCR |
| KL-09 | Checkpoints are local files without tamper protection |

## Numbers, if you need the exact ones

| Figure | Value | Where it is recorded |
|---|---|---|
| Scenarios at release | 45/45, 0 safety violations | `evidence/release/v1.0.0/scenarios/` |
| Live latency at release | median 2.39 s, worst 8.05 s | same |
| Tests | 554 with all extras, 460 on a base install. None need a key or network | `evidence/release/v1.0.1/verification.txt` |
| Scenario history | 40/45 on 13 Oct, 44/45 on 19 Oct, 45/45 at release | `docs/weekly-reports/week-08.md` |
| Model | `gemini-3.1-flash-lite`, pinned exactly, 30 s budget, prompt v1.4 | `src/procurement_agent/config.py` |
| Contract limits | 8 iterations, 120 s, named stop reasons | `contracts/agent-task-contract.json` |

## Reference, only if pushed

- **Where AI is and is not.** Gemini reads quotations; RAG finds the clause.
  Stock arithmetic, eligibility, landed cost, ranking and the loop itself are
  plain Python. Memory is advisory and never reaches a decision.
- **Stopping points.** Gate 2 confirms the comparison. A second confirmation
  before anything is written. Hand-offs when it should not guess, for example a
  USD quotation with no rate (`EXCHANGE_RATE_REQUIRED`, POL-003-C01) or no
  eligible supplier (`MISSING_COMPONENT`). A manager role cannot run the loop
  (POL-004-C03).
- **State.** Each review has a checkpoint `AGT-<date>-<sku>-<officer>` recording
  checksums of the files it read. Re-running resumes and will not write a second
  requisition.
- **Quantity worked example.** Cement: 150 on hand, reorder point 150, target
  270, so order 120.
- **Stack.** Python, no required runtime dependencies, optional extras for RAG,
  Gemini and the UI. Local Qdrant with `BAAI/bge-small-en-v1.5`. Streamlit
  operator view calling the same workflow as the command line.

## George's answer to "what did you learn"

Pick two. The first plus one of your own is a strong answer.

- **Agentic does not mean the model is in charge.** Keeping the model at the
  edges and putting control flow, arithmetic and permissions in ordinary code
  behind one dispatcher is what makes it testable: the core needs no key.
- **Evaluation needs honesty.** The 45-scenario run found a real failure, S-38.
  We put it in the limitations register instead of raising the timeout to hide
  it.
- **CI as a guardrail, not just tests.** Custom Semgrep rules fail the build on
  purchase, supplier-contact or payment code. When pip-audit flagged 35 Pillow
  vulnerabilities that fastembed pins us to, we documented a reviewed exception
  rather than switching the check off.
- **Pin the model.** An alias like `-latest` can change under you between two
  evaluation runs and the results stop being comparable.
- **Resume is harder than it sounds.** A real bug had the offline demo writing
  into the live cache and evidence log; fixed by isolating demo state.

---

## Before you present: two corrections

1. **Done.** The README manager-approval claim is fixed on
   `ft/readme-architecture`. The diagrams now show approval happening outside
   this release, with a dashed border, and the caption warns not to promise a
   live approval. The branch still needs a PR.
2. **Open.** `docs/architecture/final-presentation.md` says **548 tests**. The
   release records **554**. Fix the slide before the panel.
