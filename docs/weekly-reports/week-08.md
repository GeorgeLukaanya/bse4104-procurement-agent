# Group Y Progress Report Week 8

**Course:** BSE4104 Emerging Trends in Software Engineering

**Group:** Y | **Week ending:** 23 October 2026 | **Version:** 1.0

**Owner:** Lukaanya George | **Prepared:** 23 October 2026

**Repository:** [Group Y procurement agent](https://github.com/GeorgeLukaanya/bse4104-procurement-agent)

**Tracker:** [Group Y ClickUp board](https://app.clickup.com/9012272120/v/s/90129079418)

## Introduction

Week 8 is the hardening and release week. The aim was to fix critical defects, record the
limitations that remain, and ship a reproducible tagged release with an evidence pack. The
release is **v1.0.0**, tagged on the commit that merges this report. It was verified from a
fresh clone, including a full live evaluation: **45 of 45 scenarios pass, 0 safety
violations**.

## Tasks and contributions

| Deliverable | Evidence | Status | Assignee |
|---|---|---|---|
| Hardening and known limitations | Four reproduced high-severity defects fixed (W8-01 to W8-04) with 30 new regression tests; twelve remaining limitations recorded with priority and follow-up. [Write-up](../architecture/known-limitations.md); [PR #79](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/79) | Merged | Beingana Jim Junior |
| Final evaluation and evidence pack | Index of every claim, the file that supports it, and the commit. [Write-up](../evaluation/final-evidence-pack.md); [PR #81](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/81) | Merged | Sekyeza Elroy Nunda |
| Tagged release, README and run instructions | v1.0.0; [release notes](../../RELEASE_NOTES.md); README updated; fresh-clone verification and a full live evaluation at the release commit, [evidence](../../evidence/release/v1.0.0/) | Merged with this report | Lukaanya George |
| Week 8 progress report | This page. [Issue #40](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/40) | Merged with the release | Lukaanya George |
| Final engineering report | [Issue #36](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/36). Not in the repository when this report was written | Open | Nannyombi Shakiran |
| Presentation deck and live demonstration | [Issue #37](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/37) is closed; the deck is not stored in the repository (`final-presentation.md` is still the template) | Issue closed | Ainamani Jim Isaac |

Nannyombi Shakiran also finished the Week 7 report ([PR #80](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/80)).

## Decisions

**The tag carries the software, not every document.** The final engineering report was not
merged by release day. The tag was cut once the release documents merged, because the report
does not change what runs. Apart from the version string, no source, tool, contract or data file
differs from `0496a03`, the commit that every release check ran against.

**The live evaluation was re-run at the release commit.** Both Week 8 scenario runs (20 and 22
October) were offline only, and the evidence pack listed the missing live run as an open item.
The release check ran all 45 scenarios, including the 8 live Gemini calls, in a clean clone with
no local changes. This closes that item.

**Release checks run from a fresh clone, not a developer's checkout.** A clone of GitHub
`main`, a new virtual environment and only the documented commands. Results reflect what a marker
would see, not a machine with leftover state.

## Results

| Check (fresh clone of `0496a03`, Python 3.14.7) | Result |
|---|---|
| Base install, `pytest` | 452 passed, 7 skipped (optional extras), 0 failed |
| All extras, policy index built, `pytest` | 541 passed, 0 skipped, 0 failed |
| 45 scenarios including 8 live | 45/45 pass, 0 safety violations; live median 2.39 s, worst 8.05 s |
| Agent run from the README | Stops at Gate 2; on confirmation resumes from the checkpoint and compiles one DRAFT |

Every run of the 45-scenario evaluation recorded 0 safety violations. It went from 40/45 on 13
October to 44/45 on 19 October and 45/45 at the release. On the defect side: nine failures were
caught by the Week 7 catalogue and four more by Week 8 hardening, all fixed with regression
tests.

## Challenges

**One pass does not make the timeout go away.** S-38 timed out at 30 s on 19 October and passed
in 2.4 s at the release. That is free-tier provider variance, not a fix, so limitation KL-01
stands. The evaluation has a handful of live runs per scenario, not enough for a reliability
figure (KL-12).

**The specified product is bigger than the built one.** The charter and requirements describe a
manager review screen, authentication, an immutable audit log and Gates 4 and 5. None was built.
They are recorded in the limitations register and the release notes rather than rushed into a
week the charter reserves for hardening. Every run ends at `DRAFT`, so no unbuilt control can be
bypassed.

**A dependency advisory arrived on release day.** pip-audit reported 35 advisories in Pillow
12.3.0, fixed only in Pillow 13, which fastembed does not yet allow. The project never decodes an
image, so CI now ignores exactly those 35 IDs, recorded with the reason and a removal condition
in `.github/pip-audit-exceptions.txt`, and still fails on any other advisory. The exception is
listed in the [release notes](../../RELEASE_NOTES.md#known-security-exception).

**Deliverables outside the repository are hard to verify.** The presentation and, at the time of
writing, the final report are not in the repository. The deliverable index and the issues are
the only shared record of their state.

## Remaining work

- Final engineering report (#36): merge into `docs/weekly-reports/final-engineering-report.md`
  so the repository holds every deliverable.
- Presentation (#37): add the deck, or a link to it, to `docs/architecture/final-presentation.md`.
- Limitations register KL-01 and evidence-pack item 3: their owners may cite the release run
  in `evidence/release/v1.0.0/scenarios/`.
- After the course: the user interface, authentication and database described in the
  [release notes](../../RELEASE_NOTES.md#deliberately-not-built), starting from the tagged
  release on a separate branch.
