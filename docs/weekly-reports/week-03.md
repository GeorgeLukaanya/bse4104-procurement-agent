# Group Y Progress Report: Week 3

**Course:** BSE4104 Emerging Trends in Software Engineering 
**Group:** Y 
**Week ending:** 18th September 2026 
**Version:** 1.0 
**Repository:** [https://github.com/GeorgeLukaanya/bse4104-procurement-agent](https://github.com/GeorgeLukaanya/bse4104-procurement-agent)

## Introduction

This report summarises Week 3 progress on the SME Procurement-Preparation Agent. The weekly focus was context engineering and retrieval-augmented generation: making the application answer from a controlled, traceable knowledge source rather than from model memory.

The week delivered a working policy retrieval pipeline implementing Requirement 7\. Given the items on a requisition, it retrieves the policy clauses that apply to each item, has the model explain them, and verifies that every clause cited was actually retrieved for that item before anything is displayed. A citation the model did not receive causes that item to be withheld.

## Tasks

| Task | Description | Status | Assignee |
| :---- | :---- | :---- | :---- |
| Corpus and Source Register | Assembled 23 team-authored synthetic documents for the fictional Kampala distributor, covering policy, procedure, product specification, quotation, requisition and supplier terms. Recorded provenance across three stores that must agree: YAML front matter, a canonical CSV register carrying licence, verifier and SHA-256, and the human-readable register document. Defined the indexing boundary and seeded evaluation defects deliberately. | Done | Ainamani Jim Isaac |
| RAG architecture diagram | Produced the three-stage architecture covering offline corpus preparation, runtime retrieval and grounded generation with review. | Done | Beingana Jim Junior |
| Working RAG pipeline | Implemented ingestion, clause-level chunking with metadata, local embedding, vector indexing, retrieval, grounded generation and citation validation. Twelve documents and 45 citable clauses are indexed. Every run appends a trace entry recording retrieved clauses with scores, absence notes, the model answer, the citation result and any suppressions. | Done | Sekyeza Elroy Nunda |
| 15-case RAG evaluation | Built and ran 15 cases spanning answerable, partially answerable and deliberately unanswerable questions, including grounding attacks using a real but unretrieved clause, an invented clause, a version mismatch and the adversarial quotation. Recorded results and three root-caused failures. | Done | Nannyombi Shakiran |
| Week 3 progress report | Compiled this report. | Done | Lukaanya George |

> **Action required:** Assignees follow the role definitions in Charter section 12\. Confirm against what each member actually delivered before submission.

## Key Design Decisions

Three decisions departed from the initial design and are recorded because they change how the pipeline behaves.

**Two searches per item, not one.** General rules apply to every purchase and are kept above a low floor. Product specifications apply only to particular goods and are kept above a higher one. A single cutoff cannot serve both, because every query is phrased as a purchase, so goods the corpus says nothing about still score as highly against the general rules as goods it covers. Without a separate specification cutoff, a purchase of airline tickets was matched to the cement specification. The two thresholds come from measurement across nine purchases.

**Five results per search rather than three.** Retrieval finds the right topic but cannot place a monetary figure in a band. On the cement purchase, the applicable quotation-count clause ranked fourth, below the band for higher-value purchases. With three results it would have been lost. Band selection is left to the model, which must then cite it.

**One model call per requisition.** Items are searched separately and answered separately inside a single call, which respects the free-tier daily request limit while keeping per-item grounding intact.

## Challenges Faced and Mitigation

**Three retrieval and grounding failures were found and root-caused.** Unrelated specifications were kept for binding wire, because the item cutoff sits in a narrow gap and binding wire shares a document with cement. The adjacent quotation-count band outranked the applicable one on three separate purchases, because the bands share wording and the embedder cannot place a figure. The foreign-currency clause was cited on all four UGX items, because it is retrieved for every purchase and the model read it as generally applicable.

*Mitigation.* All three are precision problems rather than grounding failures: every citation on the live run was in the supplied set, so nothing unsupported was shown. The follow-ups are recorded with the cases they affect: raise or category-restrict the item cutoff, keep five results until band selection is deterministic, and tighten the grounding prompt so the currency clause is cited only when a non-UGX figure is present.

**Requirement 7.1 sets a 30-second ceiling, and the recorded run took 42.01 seconds.** The time is spent at the provider, on a single call. An earlier development run of the same requisition took 6.29 seconds, so the variance is wide and one measurement is not a conclusion.

*Mitigation.* Recorded as a known limitation rather than written off. Latency needs measuring across more runs before the ceiling is either met or renegotiated.

**The implementation diverges from the architecture diagram in four places.** The diagram routes both validation failure and corpus unavailability to a single pause-and-preserve-state box. The implementation treats them differently: a stale index stops the command before any call, whereas a citation failure withholds only the affected item and lets the rest of the requisition through. Per-item withholding was chosen so that one ungrounded citation for cement does not hide a correctly grounded answer for binding wire.

*Mitigation.* Divergences were raised in team review and passed to the diagram's owner, and the pipeline write-up documents each one explicitly rather than leaving the diagram to be read as authoritative. One item is a genuine gap rather than a design choice: state is not preserved between runs, so a retry repeats the search and the model call. Requirement 7.5 and the AI Boundary Matrix both require it, and it belongs to the Week 5 state model.

**A new cross-document contradiction was found.** The Project Charter retrieves policy before extraction, from an estimated value band. Requirement 7.1 and the architecture diagram retrieve after the comparison is confirmed. The pipeline follows Requirement 7.1.

*Mitigation.* Recorded and scheduled for resolution at the next re-baseline. This is the second week running that parallel authorship has produced divergent assumptions, which suggests the standing consistency check introduced after Week 1 needs to run before a week's implementation rather than after it.

## Results

Thirteen of fifteen cases passed. Both failures are retrieval precision problems in the answerable set, and neither produced an ungrounded answer. All four partial cases returned the expected absence note rather than an invented rule, and all five grounding guards held: a real but unretrieved clause, an invented clause, a version mismatch and a mention of the adversarial quotation were each rejected.

On the live requisition, all four items were shown and every citation was grounded.

## Upcoming Tasks

Tune the item cutoff and re-measure the affected cases. Add an evaluation case carrying a non-UGX total, which the current set lacks. Add cases at the monetary band boundaries, since all four sample items fall inside a single band. Measure latency across more runs. Resolve the retrieval-ordering contradiction between the charter and Requirement 7.1. Close the outstanding v1.1 row in the prompt version history carried over from Week 2\. Begin the Week 4 deliverables.

## Summary of Progress

All five Week 3 deliverables were completed. The application now answers from a controlled corpus with per-clause provenance, states absence rather than inventing a rule, and withholds any item whose citation cannot be traced to a clause it was actually given.

The week's main learning concerned what an evaluation is for. Every case that exercised the grounding guards passed, and it would have been easy to report the week as a clean result. The two failures came from asking a different question: not whether the model cited something it was not given, but whether the right clauses were retrieved in the first place. A citation check passing on a run where unrelated specifications were retrieved is luck rather than a guarantee, and recording it as a pass would have hidden a real defect behind a green result.  
