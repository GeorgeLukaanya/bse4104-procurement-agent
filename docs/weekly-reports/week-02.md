# Group Y Progress Report: Week 2

**Course:** BSE4104 Emerging Trends in Software Engineering  
**Group:** Y  
**Project:** SME Procurement-Preparation Agent  
**Week ending:** 11th September 2026  
**Version:** 1.0  

**GitHub:** [https://github.com/GeorgeLukaanya/bse4104-procurement-agent](https://github.com/GeorgeLukaanya/bse4104-procurement-agent)  
**ClickUp:** [Group Y board](https://sharing.clickup.com/9012272120/l/h/5-901213426906-1/31d463956153cf6)

## **Introduction**

This report summarises the team's Week 2 progress. Week 1 defined the problem, users, eleven-field Normalised Quotation, and AI boundaries. Week 2 was the first week the system used a foundation model to do real work.

The baseline interaction is quotation field extraction. A supplier quotation that has already been converted to Markdown goes in, and a validated eleven-field record comes out, or an explicit failure does. The model does not retrieve policy or draft a justification yet. Those arrive in later weeks.

## **Tasks**

| Task | Description | Status | Assignee |
| :---- | :---- | :---- | :---- |
| Model selection note | Selected Gemini 3.1 Flash-Lite, pinned by exact model string, and recorded cost, privacy, access and (where measured) latency. Free-tier rate limits are still unread from the provider console. | Done | Beingana Jim Junior |
| Working baseline model interaction | Built a framework-free `procurement_agent` package: prompt construction, schema-constrained call, validation, safety scan, cache and evidence log. Exercised offline with a substituted backend, then against the live API on 11 September 2026. | Done | Ainamani Jim Isaac |
| Prompt specification | Specified the extraction prompt, decoding settings and version history. Live prompt text is in `src/procurement_agent/prompts.py`. | Done | Nannyombi Shakiran |
| Prompt version v1.1 | After the first live run, added date-notation rule 6 so dates are returned as YYYY-MM-DD without guessing a missing part. | Done | Nannyombi Shakiran |
| 10-case prompt evaluation | Wrote ten cases covering missing fields, ambiguous dates, irrelevant text, prompt injection and empty input. Actual Behaviour and Result columns are not yet filled. | In progress | Sekyeza Elroy Nunda |
| Week 2 progress report | Compiled this report against the Week 2 objectives, decisions, remaining gaps and the Week 3 plan. | Done | Lukaanya George |

## **Key engineering decisions**

- **Pinned model, no aliases.** The application uses `gemini-3.1-flash-lite` only. Strings ending `-latest`, `-preview` or `@latest` are rejected so a provider-side alias cannot silently change evaluation results.
- **No application framework.** Django, FastAPI and Flask stay out. The charter has not chosen one, and Week 2 must not force that choice. The package is importable for whatever interface comes later.
- **Tests consume no quota.** The suite and `tools/offline_demo.py` substitute a backend. The Model Selection Note treats requests per day as the binding constraint; a test suite that called Gemini could stall the team until the Pacific-midnight reset.
- **Cache key includes configuration.** Hits are keyed on the document hash plus model, temperature, thinking budget, max tokens and prompt version. A prompt edit without a version bump would serve old results as if they came from the new wording.
- **Reject, do not salvage.** Non-conforming model output is discarded in full. A half-parsed quotation would look complete downstream.
- **Arithmetic stays out of the model.** Totals, VAT, unit conversion, currency conversion and landed cost belong to deterministic code. The model extracts stated values only.

## **Upcoming tasks (Week 3)**

- Assemble a controlled corpus and record provenance in `knowledge/source-register.md`.
- Draw the RAG architecture (ingestion, chunking, indexing, retrieval, source grounding).
- Implement a working RAG pipeline with unsupported-answer handling.
- Run a 15-case RAG evaluation, including deliberately unanswerable questions, and record at least three retrieval failures.
- Fill the Week 2 prompt-evaluation Actual/Result columns (carried over).
- Write the Week 3 progress report.

## **Challenges Faced and Mitigation**

The first live run under prompt v1.0 returned five conforming fixtures out of six. Fixture `02-prose-carton-vat-inclusive.md` was rejected on `validity_date`: the document states expiry in words, the model returned `30th September 2026`, and the schema requires YYYY-MM-DD. That is a specification gap, not a model or validator fault. Mitigation: prompt v1.1 adds an explicit date-notation rule. Under v1.1 all six fixtures conform. Median live latency was 3.132 seconds (worst case 4.692 seconds, n=5), inside the 30-second ceiling in requirement 3.1.

The ten-case evaluation table and success criterion S9 are still open. Conformance is not accuracy: a well-formed record can carry a wrong figure, and no hand-keyed expected records exist yet. Mitigation: Elroy fills Actual/Result against v1.1 next; expected records for the fixture set are keyed before S9 is scored. No accuracy figure is claimed in this report.

Free-tier rate limits were not read from the project console this week. Until they are recorded, evaluation runs stay batched, cached, and split across personal development projects versus one designated evaluation project.

## **Summary of Progress**

Week 2 produced a running extraction baseline, a model selection note, Prompt Specification v1.1, six synthetic fixtures, an append-only evidence log, and this report. The live API path is confirmed for the fixture set under v1.1. The 10-case prompt evaluation remains the unfinished Week 2 deliverable. Week 3 starts from that baseline and adds a grounded corpus and RAG, without treating the offline demo as evidence about Gemini.
