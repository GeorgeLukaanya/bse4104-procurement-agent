**SYSTEM DESIGN DELIVERABLE | WEEK 2**

**Model Selection Note: Foundation Model Evaluation**

*Project: SME Procurement Agent  |  Target Model: Gemini 3.1 Flash-Lite  |  Date: September 2026*

**1\. Model Selection and Capabilities**

For the SME Procurement Preparation Agent, Gemini 3.1 Flash-Lite through the Google generative API is selected as the primary baseline foundation model. The project requires pulling structured data from supplier quote documents, checking procurement policy rules and writing clear explanations for purchase requisitions. Gemini 3.1 Flash-Lite is built for low-latency execution and high-throughput processing while retaining a large context window. This speed makes it a solid candidate for extracting line items from Markdown quotes and handling prompt tasks without slowing down user interactions.

The model is pinned by exact model string in application configuration rather than referenced by an alias, so that a provider-side version change cannot silently alter evaluation results mid-project. The pinned string and its release status are recorded below, because a preview release carries both tighter rate limits and a deprecation risk inside our eight-week window.

| Property | Value |
| :---- | :---- |
| Pinned model string | gemini-3.1-flash-lite  |
| Release status | *Preview* |
| Context window | 1,048,576 tokens |
| Structured output support | Native support |
| Function calling support | Supported |

**2\. Model Evaluation and Constraints**

| Evaluation Metric | Free Tier Limit / Property | Architectural Decision |
| :---- | :---- | :---- |
| **Financial Cost** | $0.00 / month (Free Tier) | Eliminates API costs during the early prototype stage. |
| **Rate Limits & Quota** | *Pending measurement — see the measurement table below.* The provider no longer publishes per-model free-tier limits. | Agent loop turns are capped and the API client retries 429 with bounded exponential backoff. |
| **Model Locking** | Single model setup, pinned by exact version string (`gemini-3.1-flash-lite`) | Agent workflows target Gemini API schemas directly without dynamic multi-model routing. |
| **Latency Profile** | *Pending measurement — see the measurement table below.* | Acceptance criterion 3.1 sets a 30-second ceiling per quotation. The CLI reports measured median and worst case across live calls. |
| **Data Privacy** | Provider data logging active on the free tier | Strict rule: Only synthetic data is sent to protect privacy. |

Two of the rows above are deliberately left for measurement rather than estimation.

**Rate limits.** The provider no longer publishes per-model free-tier request limits in its API documentation, and instead directs developers to the live rate limit view in AI Studio, where the figures reflect the specific project. Any planning figure taken from a third-party article is unverifiable. The team records the actual values read from our own project, with the date read.

**Latency.** Recorded as a measured median and worst case across the synthetic quotation set, with the number of calls the measurement is based on, rather than as a vendor-typical range.

| Measurement | Value | Method |
| :---- | :---- | :---- |
| Requests per minute (free tier) | **Pending.** Not yet read. | AI Studio rate limit view for our own evaluation project; record the value and the date read |
| Tokens per minute (free tier) | **Pending.** Not yet read. | As above |
| Requests per day (free tier) | **Pending.** Not yet read. | As above |
| Median extraction latency | **Pending.** No live call has been made. | `python -m procurement_agent.cli fixtures/*.md` prints median and worst case across live calls; record the figure with *n* |
| Worst-case extraction latency | **Pending.** No live call has been made. | Same run, same command |

One consequence of the free tier is worth stating explicitly, because it changes how the team should plan. At an estimated five hundred model calls across the whole project, at roughly 1,400 input and 400 output tokens per call, total consumption stays under one million input tokens. At published paid rates that would cost under two United States dollars. **The binding constraint on this project is therefore request throughput, not token spend.** Evaluation runs should be planned against requests per day, and the daily quota resets at midnight Pacific time, which is mid-morning in Kampala, so a quota exhausted in an afternoon session will not clear until the following morning.

Rate limits also apply per provider project rather than per API key. Five keys created under one project share one quota. Each member therefore develops against their own project and key, while a single designated project is reserved for evaluation runs so that Week 7 results are produced under consistent conditions.

**3\. Practical Trade-Offs and System Design Fixes**

Using a lightweight model on the free tier comes with specific limits, particularly around request caps and data logging policies. The application architecture uses four straightforward design controls to address these boundaries:

**Deterministic Math Offloading:** To avoid rate limit waste and math errors, all arithmetic is calculated in Python code. This includes unit-of-measure normalisation, VAT application, delivery apportionment, currency conversion at the configured rate, and landed cost. The model extracts the inputs to these calculations and never performs them.

**Bounded Agent Loops:** The tool-calling loop is capped at a maximum iteration limit per run. Hard stop conditions prevent infinite loop traps.

**Document Caching with SHA-256:** Quotation text in Markdown is cached using document hashes. Identical file uploads skip API calls completely and reuse existing JSON records. This is what makes repeated evaluation runs affordable within the daily request quota, and it also makes them reproducible, because the same source file always produces byte-identical model input.

**Exclusive Use of Synthetic Data:** Because free API inputs can be logged by the provider, all supplier names, prices, items, and policies in the application are completely synthetic. This is a hard operating rule rather than a preference. No real supplier, client or commercial data may be sent through a free-tier key at any point in the project.

**4\. Baseline Integration and System Testing**

The Week 2 baseline integration is built and its offline behaviour is under test. Schema-constrained decoding is wired to the google-genai `response_schema` feature, and every response is additionally validated locally against the Normalised Quotation contract and rejected outright if it does not conform. An exponential backoff retry mechanism with jitter is built into the API client to handle temporary rate limits, bounded so that a non-retryable error fails immediately rather than consuming the retry budget.

Whether the model *in fact* produces schema-conformant output on our quotation set is **not yet established**, because no live call has been made. That claim is listed as pending below rather than asserted.

The evidence supporting these findings is recorded alongside the deliverable so that the claims are auditable:

| Claim | Supporting evidence |
| :---- | :---- |
| Reliable JSON Schema conformance | **Pending a live run.** The run log format exists and records every call at `evidence/traces/extraction-runs.jsonl`, with status, attempt count and the full configuration fingerprint. No live rows yet, so the counts of calls, conformant and rejected are all unknown. |
| Non-conforming output is rejected, not partially accepted | `src/procurement_agent/schema.py` validates the full contract with no salvage path; `tests/test_extract.py::test_non_conforming_output_is_rejected_not_partially_accepted`. Requirement 3.3. |
| Text parsing separated from numerical processing | Prompt Specification v1.0 section 5, plus the deterministic calculator's ownership of every displayed figure. Enforced by `tests/test_extract.py::test_package_performs_no_arithmetic_on_monetary_values`. |
| Exponential backoff handles rate limits | Exercised offline against a stub that returns 429: `tests/test_client.py::test_backoff_recovers_from_transient_rate_limiting` and `::test_backoff_gives_up_and_reports_rate_limiting_explicitly`. Behaviour against the *provider's* real 429 is untested. |
| Model string cannot drift provider-side | Pinned by exact version in `config.py`, which rejects any alias ending `-latest`, `-preview` or `@latest`; `tests/test_config_and_prompts.py::test_alias_model_strings_are_rejected`. |
| Extraction accuracy against the fixture set | **Pending a live run.** No model has read the fixtures. Success criterion S9 has no value yet. |

Where a figure is not yet available, it is marked as pending rather than estimated, and completed before submission.
  
