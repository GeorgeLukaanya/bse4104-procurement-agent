# Week 4 Team Brief — Tool Catalogue

**Group Y | 23 September 2026 | From: Lukaanya George (#15)**
Pull request #52 — `ft-week-4-tool-catalogue`, merged 23 September 2026

> **Read this first if you own a Week 4 to Week 8 deliverable.** It states what is
> ready, what each of you needs, and two changes that affect everyone. The full
> reasoning behind every change is in [`week-04-change-log.md`](week-04-change-log.md).

---

## What is ready

Issue #15, the Tool Catalogue and schemas, is done and up for review.

- **`docs/architecture/tool-catalogue.md`** — four tools defined with purpose, input
  schema, output schema, authorization and failure behaviour.
- **`docs/architecture/schemas/`** — eleven JSON Schema files, all validated.

The four tools are `check_reorder_need`, `check_supplier_eligibility`,
`compare_quotations` and `create_requisition_draft`. All four are named in Charter
section 1, and four is the section 7 ceiling.

## What I also had to build

**`knowledge/data/`** — 48 SKUs, 8 suppliers, 36 quotations.

This dataset was required by Charter section 7 but no deliverable row and no issue
assigned it to anyone. Three of the four tools read it, and issue #16 was blocked
without it. It is consistent with the existing corpus: same fictional business, same
categories, the three suppliers from SUP-001 to SUP-003, and the three flagged items
resolve to the same 120 bags, 25 kg and 40 helmets that the Week 3 fixture already used.

It is registered as DAT-001 to DAT-003 with checksums and marked **pending_review**.
Someone who is not me should read it before Week 7 depends on it.

---

## What each of you needs to know

### Shakiran — #16 is unblocked

The dataset exists now, so the working demonstration can proceed. Build against the
schema files, not against the prose.

Section 12 of the catalogue names the paths that switch on the dormant `tool-tests`
CI job with no workflow change:

- `src/procurement_agent/tools/`
- `tests/test_tools_<tool>.py`
- `tests/test_authorization_<area>.py`

Also: **I amended your Week 1 Requirements Document to v1.2.** Requirement 4 only.
Please review — details below.

### Jim Junior — #17 has a ready-made test list

Section 9 of the catalogue is a four-column matrix covering exactly the four categories
the brief names: missing parameters, unauthorized requests, unavailable services and
unexpected tool responses. Every cell states the expected status, error code and
behaviour, so the cases are already written.

### Jim Isaac — #18

The updated architecture diagram needs a tool layer between the orchestrator and the
data files. Sections 2 and 3 of the catalogue have the shape: the shared response
envelope, the role injection point and the allow-list boundary.

### Elroy — #19

The Week 4 progress report is yours on GitHub. Everything above is the material for it.

Separately: `docs/evaluation/prompt-evaluation.md` still says *"In progress — Actual
Behaviour and Result not yet filled"*, but the table is fully filled with live results
and a 90% pass rate. The matching row in `docs/README.md` says the same. Worth updating
both.

---

## Two changes that affect everyone

### 1. Requirements Document is now v1.2

Requirement 4 was narrower than the policy it enforces. Three changes, all inside
Requirement 4:

- **4.1** now names all four eligibility checks. It previously required only AVL
  presence and Blacklist absence, but POL-002-C02 also bars a suspended supplier and
  POL-002-C03 bars an out-of-category quotation.
- **4.3** gains `SUSPENDED` and `OUT_OF_CATEGORY`. Folding a suspension into
  `BLACKLISTED` would misstate it — POL-002-C02 treats suspension as reversible and
  blacklisting as not.
- **4.6** is new, covering POL-002-C04: similarly named businesses must not be assumed
  to be the same supplier.

An Amendment History section at the end of the document records each change and its
reason. Requirements 1 to 3 and 5 to 14, the Glossary and the Traceability table are
unchanged, so existing citations to v1.1 remain accurate.

### 2. Owners in `docs/README.md` now match the GitHub issues

The deliverable index disagreed with the tracker. Thirty owner cells were wrong across
Weeks 5, 6 and 7, in both the tables and the ClickUp copy lists, plus one in Week 3.
Week 8 already agreed.

**Please check your own rows for Weeks 5 to 8 — they may have moved.**

Going forward: if a row and its issue disagree, **the issue wins**. Change the assignee
on GitHub first, then update the file.

---

## Two things the group still needs to settle

**Week 3 ownership.** `week-03.md` lists different assignees from the tracker on three
of four rows, and it already carries its own note asking us to confirm against what each
member actually delivered. Git history is not conclusive, because stub-creation commits
make one person the top author of files whose content someone else wrote. Can the four
of you confirm who did what?

**`tools/offline_demo.py` writes to the real evidence log.** Running it appends rows to
`evidence/traces/extraction-runs.jsonl`, even though it prints a banner saying its
output is not evidence. That contradicts our own rule that the run log must not be
editable. It is a small fix, but the evidence log currently contains demo rows.

---

## Status of the week

| Deliverable | Owner | Issue | Status |
| ----- | ----- | ----- | ----- |
| Tool catalogue and schemas | Lukaanya George | #15 | Done, in review |
| Working demonstration of two tools | Nannyombi Shakiran | #16 | Unblocked |
| Failure / authorization test evidence | Beingana Jim Junior | #17 | Unblocked |
| Updated architecture diagram | Ainamani Jim Isaac | #18 | Not started |
| Week 4 progress report | Sekyeza Elroy Nunda | #19 | Not started |

The week is not complete until #16 lands. "Working demonstration of at least two tools"
is a stated deliverable, and Section 4 of the brief requires at least two explicit tools
by Week 8. A catalogue with nothing built against it does not satisfy it.
