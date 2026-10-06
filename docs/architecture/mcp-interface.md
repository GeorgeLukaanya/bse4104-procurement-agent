# Integration or MCP-style Interface Specification

| Field | Value |
|---|---|
| Week | 6 |
| Owner | Nannyombi Shakiran |
| Due | 9 October 2026 |
| Status | Draft for review |
| Path | `docs/architecture/mcp-interface.md` |

## Brief requirement

Specify one external integration OR document one project capability as an MCP-style interface: capability, inputs, outputs, permissions and security boundary.

## Write-up

### 1. What this specifies

One project capability, **policy retrieval**, documented as an MCP-style interface under the name `retrieve_policy`. Given the items on a requisition and the totals the deterministic layer produced for them, it returns the policy clauses that apply to each item and a short explanation, with every citation checked against what was retrieved.

"MCP-style" means the capability is described the way a Model Context Protocol server describes a tool: a name, a description, an input schema, a result shape, and a stated permission for each caller. It does **not** mean a server exists. No JSON-RPC transport, `tools/list` endpoint or session handling is built, and this page does not claim one. What exists is the pipeline behind the interface ([`working-rag-pipeline.md`](working-rag-pipeline.md)); what this page adds is the contract a caller would meet, and the boundary that contract must hold.

| Part | Status |
|---|---|
| Retrieval, grounding, citation check, output guard, trace | Built, Week 3 (`src/procurement_agent/rag/`) |
| The interface contract (this page) | Specified |
| The wrapper that enforces it (envelope, input validation, role, allow-list) | **Not built.** Section 9 lists each gap |

### 2. Why this capability

The repository had already deferred this decision to this week, in three places:

- [`tool-catalogue.md`](tool-catalogue.md) section 1: "Week 6 may expose it through the MCP-style interface; until then it stays outside the allow-list."
- [`week-04-change-log.md`](../week-04-change-log.md): policy retrieval "stays outside the tool allow-list until Week 6 decides whether to expose it".
- The [Agent Task Contract](../requirements/agent-task-contract.md) lists `retrieve_policy` as an AI-layer step, built and not wired into the loop, and puts it in phase `COMPARISON_CONFIRMED`.

An external integration was the other option the brief allows. The project has none to document: the AI Boundary Matrix says no purchase-order, payment or supplier-contact interface shall exist, so there is no outbound system to integrate with. Policy retrieval is also the one capability with a model call behind it, which makes its security boundary the most worth writing down.

**It is not a fifth catalogue tool.** The charter caps the catalogue at four, and [`tool-catalogue.md`](tool-catalogue.md) section 13 says a policy-retrieval tool would need a charter amendment. The contract calls `retrieve_policy` an **AI-layer step**, and the closed action set is "4 tools + 2 AI-layer steps + `hand_off` + `stop`". This page follows the contract: the interface describes an AI-layer step, and the four-tool ceiling is untouched. Section 10 records this as a point for the team to confirm.

### 3. The capability

```json
{
  "name": "retrieve_policy",
  "description": "Find the procurement policy clauses that apply to each item on a requisition and explain them. Read-only. Uses only the registered Policy Corpus. Every citation in the answer is checked against the clauses retrieved for that item. Never approves, recommends a supplier, or changes a record.",
  "inputSchema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["items"],
    "properties": {
      "items": {
        "type": "array",
        "minItems": 1,
        "maxItems": 12,
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": ["item", "category", "estimated_total", "comparison_reference"],
          "properties": {
            "item": { "type": "string", "pattern": "^[^<>\\r\\n]{1,120}$" },
            "category": { "type": "string", "pattern": "^[^<>\\r\\n]{1,60}$" },
            "estimated_total": { "type": "number", "minimum": 0 },
            "currency": { "type": "string", "enum": ["UGX"], "default": "UGX" },
            "comparison_reference": { "type": "string", "pattern": "^CMP-[0-9]{8}-AH-[A-Z]{2}-[0-9]{3}$" }
          }
        }
      }
    }
  }
}
```

The limits (12 items, 120 and 60 characters) are proposals. Twelve covers a weekly review: eleven SKUs are at or below reorder point in the seeded inventory. The character limits let a descriptive name fit and a pasted paragraph not.

### 4. Inputs

| Field | Meaning | Source it must come from |
|---|---|---|
| `item` | What is being bought, e.g. `120 bags of cement` | The flagged inventory item and the confirmed reorder quantity |
| `category` | Product category | The flagged item |
| `estimated_total` | The figure the policy band is chosen from | **The confirmed comparison**, never typed or inferred |
| `currency` | UGX only | Comparison output |
| `comparison_reference` | Which comparison the total came from, e.g. `CMP-20260925-AH-CM-001` | The run state |

**What a caller cannot set.** `caller_role`, the retrieval depth (`top_k`), the two score cutoffs, the model, the prompt, the corpus path, the index path and the API key are not inputs. The command-line tool exposes some of them for the team's own evaluation; the interface does not. A caller that could lower a cutoff could pull in clauses the evaluation did not measure, and a caller that could name a corpus path could point retrieval at an unregistered document. `caller_role` follows the rule in [`tool-catalogue.md`](tool-catalogue.md) section 3: it is injected from the session and appears only in the trace.

**Why `item` and `category` are character-limited.** The prompt builder writes both into the model's message as `Item: <text>` inside an `<item ref="...">` block (`grounding.build_user_message`). Text containing `<`, `>` or a line break could close that block and open another. Excluding those characters removes the route without trying to sanitise free text.

**Why `estimated_total` is tied to a comparison.** The model picks the applicable value band by comparing the total with the thresholds in the clauses. In the recorded run the model's own reason for citing POL-001-C02 is "The estimated total falls within the range for standard purchases". The bands are real rules: POL-001-C01 asks for one quotation below UGX 500,000, POL-001-C02 for three between UGX 500,000 and under UGX 5,000,000, and POL-001-C03 for three plus a documented comparison from UGX 5,000,000. An understated total therefore changes which quotation-count rule the officer is shown, which is a financial control. The interface must check `estimated_total` against the comparison named by `comparison_reference` and refuse a mismatch with `INVALID_PARAMETER`. This is the single most important rule in the spec, and it is not built (section 9). Note that `comparison_reference` is not a stored identifier today: the agent's planner derives it from the review date and SKU (`CMP-20260925-AH-CM-001`) when it compiles a draft, so the check would resolve it to the comparison held in that run's checkpoint.

### 5. Outputs

The result uses the catalogue's envelope ([`tool-catalogue.md`](tool-catalogue.md) section 2), so a caller handles this capability the way it handles the four tools.

```json
{
  "tool": "retrieve_policy",
  "tool_version": "1.0",
  "status": "ok",
  "data": { "requisition_status": "ok", "items": [ ] },
  "errors": [],
  "trace": {
    "called_at": "2026-10-06T08:14:02Z",
    "caller_role": "AGENT",
    "latency_ms": 42011,
    "data_fingerprint": "<first 16 hex of the index manifest's corpus_fingerprint>"
  }
}
```

The values show the shape only. The interface is not built, so this is not a recorded call; the recorded run is in the worked example below.

Each entry of `data.items`:

| Field | Meaning |
|---|---|
| `ref` | Position of the item in the request, `"1"`, `"2"`, ... |
| `status` | `ok`, `no_clauses`, `suppressed`, `citation_invalid`, `generation_failed`, `rate_limited` or `call_failed` (the pipeline's own vocabulary) |
| `shown` | `true` only for `ok` and `no_clauses`. Content for any other item is withheld |
| `retrieval.general`, `retrieval.item` | Kept clauses: `clause_id`, `source_id`, `version`, `title`, `heading`, `score`. Clause text is not returned |
| `retrieval.absence_notes` | Explicit notes where no clause of a kind was found. Under Requirement 7.3 this is the answer, not an error |
| `answer` | `{ summary, applicable_clauses[ {source_id, version, clause_id, reason} ] }` when `shown`, otherwise `null` |
| `citation_check` | `{ valid, problems[] }` |

`data.requisition_status` is `ok` (every item shown), `partial` (some withheld) or `withheld` (none shown), as `RequisitionOutcome.status` already computes it.

**Mapping to the envelope.** Withheld items map to the shared error vocabulary, with the item named in the error.

| Situation | Envelope `status` | Code |
|---|---|---|
| Every item shown, including notes-only items | `ok` | none |
| Some items withheld | `ok`, `requisition_status: partial` | one error per withheld item |
| No item shown | `failed` | the withheld items' codes |
| Index not built | `unavailable` | `DATA_SOURCE_UNAVAILABLE` |
| Index stale, or a corpus document edited after registration | `failed` | `DATA_INTEGRITY_ERROR` |
| Model rate-limited or call failed | `unavailable` | `SERVICE_UNAVAILABLE` |
| Answer asserted something prohibited | withheld item | `GUARD_SUPPRESSED` |
| A citation names a clause not retrieved for that item | withheld item | `CITATION_INVALID` |
| Model answer malformed | withheld item | `GENERATION_FAILED` |

`GUARD_SUPPRESSED` and `SERVICE_UNAVAILABLE` are already named in the Agent Task Contract. `CITATION_INVALID` and `GENERATION_FAILED` are new. All four would join the catalogue's shared code table.

**Worked example, from the recorded run.** One line in [`rag-runs.jsonl`](../../evidence/traces/rag-runs.jsonl), made on 17 September 2026, holds four items answered in one model call (42.01 s, one attempt, model `gemini-3.1-flash-lite`, prompt `grounding-1.1`). Two of its items show both ends of the contract.

| | `120 bags of cement`, UGX 4,140,000 | `diesel for the delivery truck`, UGX 1,000,000 |
|---|---|---|
| General rules kept | POL-001-C03 (0.616), POL-001-C02 (0.576), POL-001-C01 (0.557), POL-003-C01 (0.551), PRO-001-C03 (0.528) | POL-001-C03 (0.652), POL-001-C02 (0.636), POL-001-C01 (0.621), POL-003-C01 (0.607), PRO-001-C03 (0.583) |
| Item rules kept | SPEC-001-C01 (0.684), SPEC-001-C03 (0.585) | none; best candidate 0.557 is below the 0.58 cutoff |
| Absence note | none | "No product specification in the Policy Corpus was found for diesel for the delivery truck (fuel)." |
| Clauses cited | POL-001-C02, POL-003-C01, PRO-001-C03, SPEC-001-C01, SPEC-001-C03 | POL-001-C02, POL-003-C01, PRO-001-C03 |
| Item `status`, `shown` | `ok`, `true` | `ok`, `true` |

Both stayed in the same `requisition_status: ok`. The diesel answer says in its summary that no specification was found and does not supply one.

The cement total in that run, UGX 4,140,000, was a stand-in from [`fixtures/requisitions/weekly-reorder.json`](../../fixtures/requisitions/weekly-reorder.json), written before the calculator existed. The landed cost the calculator now produces for the same cement is UGX 4,479,600. Both fall in the same POL-001-C02 band, which is why the cited rule does not change.

### 6. Permissions

The capability is read-only. The roles and the injected-role rule come from [`tool-catalogue.md`](tool-catalogue.md) section 3, and the basis is POL-004-C01 (read-only calls are open to all three roles).

| Caller | `retrieve_policy` | Basis |
|---|---|---|
| `PROCUREMENT_OFFICER` | Call | Read-only. The AI Boundary Matrix lists reviewing retrieved clauses as an officer responsibility |
| `PROCUREMENT_MANAGER` | Call | Read-only. Reviewing a requisition on screen needs the clauses behind it |
| `AGENT` | Call, **only in phase `COMPARISON_CONFIRMED`**, after Gate 2 | Contract section 4; the totals come from a comparison the officer confirmed |

Three rules sit beside the table.

1. **The role is injected, never supplied.** `caller_role` appears in no input schema.
2. **A static allow-list per phase.** From any other phase, a call returns `TOOL_NOT_ALLOWED` and never reaches the pipeline. A name written inside a document matches nothing (Requirement 14.5).
3. **No write path.** The capability appends one trace line and nothing else. It cannot create or change a requisition, a status, a supplier record or an inventory record, and no role can ask it to.

### 7. Security boundary

The boundary is a set of limits, each held by a mechanism. The last column says whether that mechanism exists today.

| Limit | How it is held | Today |
|---|---|---|
| Only the registered corpus is read | The loader refuses an unregistered document, a different version, or one edited after review (SHA-256 against `source-register.csv`). The index manifest carries a `corpus_fingerprint`; a mismatch is `StaleIndex` and nothing is retrieved | Built (`corpus.py`, `ingest.open_index`) |
| The model sees only what it needs | The message holds the item name, category, total, and the clause text retrieved for that item. No quotation text, supplier name, run state or other item's clauses | Built (`grounding.build_user_message`) |
| Documents are data, not instructions | System rule 8 tells the model to ignore instructions inside clause text. The corpus is team-authored and checksummed, so planting an instruction means editing a registered file, which fails the load | Built |
| The model cannot approve, award or recommend | System rule 6, then `guards.scan` over the summary and every citation reason. A hit marks the item `suppressed`; its text is never returned and never traced | Built (`pipeline._judge`) |
| A citation must be real *and* retrieved | `validate_citations` checks document, version and clause ID against that item's retrieval, and checks every identifier mentioned in the summary | Built (`citations.py`) |
| Withheld content does not reach the caller | A withheld item returns `answer: null` | **Not built.** `ItemOutcome.to_dict` nulls the answer only for `suppressed`. A `citation_invalid` item still carries the answer text the check rejected (the other withheld statuses never have one) |
| The total cannot be chosen by the caller | `estimated_total` checked against `comparison_reference` | **Not built** |
| Caller text cannot break the prompt | `item` and `category` pattern excludes `<`, `>` and line breaks | **Not built.** `RetrievalRequest` only rejects empty strings |
| Cost and speed are bounded | One model call per requisition, retried within a bounded budget (4 attempts by default); decoding pinned (temperature 0, 2048 output tokens); caller cannot raise `top_k` or change a cutoff; at most 12 items | Partly built: the single call, the retry bound and pinned decoding exist. The item cap and removal of caller-set retrieval options are interface work |
| Secrets stay out | The key is read from the environment only; the trace carries a config fingerprint, never the key (`config.redact`) | Built |
| Nothing prohibited exists | The twelve banned function names fail CI through `.semgrep/agent-safety.yml`. This interface adds none | Built |
| Only the right caller can reach it | Role injection and the phase allow-list | **Not built** for this capability |

**What is not specified.** The page does not define a transport. Today a call is an in-process function call. If the capability were ever served over a socket or a process boundary, the role would have to come from an authenticated session, never from the request body; an unauthenticated listener would break the first rule in section 6. That is future work, and the team should not read this page as approval to expose it.

### 8. Failure behaviour

The four categories from [`tool-catalogue.md`](tool-catalogue.md) section 9, applied to this capability. Fail closed, and fail per item rather than blending a bad answer into good ones.

| Category | Behaviour |
|---|---|
| Missing parameters | `MISSING_PARAMETER` naming the field. Nothing is retrieved and no model call is spent |
| Unauthorized requests | `UNAUTHORIZED_ROLE` for an unknown role; `TOOL_NOT_ALLOWED` off the phase's list. Neither reaches the pipeline |
| Unavailable services | Index missing: `DATA_SOURCE_UNAVAILABLE`, with the instruction to run ingest. Stale index or edited corpus: `DATA_INTEGRITY_ERROR`. Model unavailable: `SERVICE_UNAVAILABLE`, and items with no clauses still stand on their notes. A rate limit that outlasts the client's bounded retries is the same code. No answer is produced from memory |
| Unexpected responses | A malformed or incomplete model answer is rejected whole: `GENERATION_FAILED`, with no salvage (Requirement 3.3). A non-conforming result would be discarded by the output-schema check that `dispatch.invoke` applies to the four tools (FA-10), once this capability has an output schema (gap 4) |

Item isolation matters here. A cement answer that cites a clause it was not given is withheld on its own; the binding-wire answer in the same call is still shown. This is a deliberate Week 3 choice, and section 10 notes where it meets the catalogue's "fail whole" rule.

### 9. Built and not built

Everything in section 7 marked "Not built" is the work between this page and a working interface. In the order it should be done:

| # | Gap | Why it matters |
|---|---|---|
| 1 | `estimated_total` is not checked against a comparison | A caller can move the cited quotation rule by changing a number |
| 2 | A `citation_invalid` item still carries its answer text in `to_dict` | The officer could be shown text the citation check rejected |
| 3 | `item` and `category` are not character-limited | Free text is written into the model's message |
| 4 | No envelope, no output schema, no role injection, no phase allow-list for `retrieve_policy` | It is callable by anyone who imports it, and `dispatch.invoke` has no output schema to check its result against |
| 5 | The retrieval options are caller-settable on the command line | Fine for evaluation, wrong for an interface |
| 6 | `estimated_total` is optional in `RetrievalRequest` | Without it the model cannot choose a band |
| 7 | Four error codes are not in the catalogue's vocabulary | A caller cannot assert on them yet |
| 8 | The agent loop does not call it (`wired_into_loop: false`) | The capability is reachable from the officer's command line only |

No code is changed by this page. Gaps 1 to 4 are small and testable, and they are the first thing a build of this interface should do.

### 10. Points for the team

1. **Is exposing `retrieve_policy` through this interface compatible with the four-tool ceiling?** This page says yes, because the contract calls it an AI-layer step and the catalogue's section 13 concerns a *tool*. If the team reads the ceiling more strictly, the capability stays an officer-run pipeline and this page becomes a specification for later.
2. **Partial results.** The catalogue says no tool returns a partial result. This page lets one request return `ok` with `requisition_status: partial`, on the reasoning that "fail whole" applies to a request, that each item here is either whole or withheld, and that `compare_quotations` already returns `ok` with an error attached (`INSUFFICIENT_QUOTATIONS`). If the team prefers one withheld item to fail the whole call, the officer loses the answers that were fine.
3. **Clause text.** The response carries clause identifiers and the model's summary, not the clause wording. The officer's review of retrieved clauses (AI Boundary Matrix) is easier with the text beside the summary. A read-only lookup of one clause by identifier would give that, as a second interface rather than a change to this one. It is out of scope here.
4. **Which total drives the band.** The architecture says the total must be "a figure the deterministic layer produced" and does not say which. Three figures exist for the same cement: the reorder estimate (UGX 3,840,000 from `check_reorder_need`), the stand-in in the Week 3 fixture (UGX 4,140,000) and the landed cost of the ranked offer (UGX 4,479,600). All three sit in the POL-001-C02 band, so nothing changed here. An item whose estimate is just under UGX 500,000 and whose landed cost is just over would get a different quotation rule depending on the choice. The team should name one. Landed cost is the better-founded figure, since it is the one the officer confirms at Gate 2, but when nothing ranks there is no landed cost and the reorder estimate would be the fallback.

### 11. Traceability

| Element | Source |
|---|---|
| Retrieval from a controlled, versioned corpus; citations validated | AI Boundary Matrix "Procurement policy"; Requirement 7 |
| No clause found is an explicit note, not an error | Requirement 7.3 |
| No bypass of the Policy Corpus | AI Boundary Matrix, "must not" list |
| Documents are untrusted data; allow-list | Requirement 14.5 |
| Prohibited assertions removed before use | Requirement 14.2 |
| Read-only calls open to all roles; role injected | POL-004-C01; [`tool-catalogue.md`](tool-catalogue.md) section 3 |
| One model call per requisition | `contracts/agent-task-contract.json`, `limits.model_calls_per_iteration` |
| Quotation count set by value band | POL-001-C01 to C03 |
| Four-tool ceiling | Project Charter section 7; [`tool-catalogue.md`](tool-catalogue.md) section 13 |
| Pipeline behind the interface | [`working-rag-pipeline.md`](working-rag-pipeline.md); [`rag-architecture.md`](rag-architecture.md) |
