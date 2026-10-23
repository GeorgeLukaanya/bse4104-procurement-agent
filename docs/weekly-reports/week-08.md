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
| Final engineering report | Merged on release day. [Report](final-engineering-report.md); [PR #83](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/83) | Merged | Nannyombi Shakiran |
| Presentation deck and live demonstration | Twelve-slide deck in [`evidence/demo/`](../../evidence/demo/); [slide outline and demo script](../architecture/final-presentation.md); [issue #37](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/issues/37) | Added with the release | Ainamani Jim Isaac |

Nannyombi Shakiran also finished the Week 7 report ([PR #80](https://github.com/GeorgeLukaanya/bse4104-procurement-agent/pull/80)) and added an optional browser operator view (the `[ui]` extra) with the final report.

## Decisions

**Verify the code that ships, twice if it changes.** The release was first verified at
`0496a03`, including the full live evaluation. The final report then merged together with a new
optional operator view, so the release candidate `034257a` was verified again from a fresh clone:
the full suite with every extra, the offline scenarios and the dependency audit. The live run was
not repeated, because the extraction, retrieval, client, prompt, tool, agent and memory code is
identical between the two commits. Only the new `ui/` package and the version string differ.

**The live evaluation was re-run at the release commit.** Both Week 8 scenario runs (20 and 22
October) were offline only, and the evidence pack listed the missing live run as an open item.
The release check ran all 45 scenarios, including the 8 live Gemini calls, in a clean clone with
no local changes. This closes that item.

**Release checks run from a fresh clone, not a developer's checkout.** A clone of GitHub
`main`, a new virtual environment and only the documented commands. Results reflect what a marker
would see, not a machine with leftover state.

## Results

| Check (fresh clone, Python 3.14.7) | Commit | Result |
|---|---|---|
| Base install, `pytest` | `034257a` | 456 passed, 8 skipped (optional extras), 0 failed |
| All extras including `[ui]`, policy index built, `pytest` | `034257a` | 548 passed, 0 skipped, 0 failed |
| 37 offline scenarios | `034257a` | 37/37 pass, 0 safety violations |
| 45 scenarios including 8 live | `0496a03` | 45/45 pass, 0 safety violations; live median 2.39 s, worst 8.05 s |
| Agent run from the README | `0496a03` | Stops at Gate 2; on confirmation resumes from the checkpoint and compiles one DRAFT |

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

**`main` went red on release day.** PR #83 merged with failing checks. It had added the output of
a completed agent run to the seed memory file, which broke two memory tests, and it had also hit
the Pillow advisories. The release restores the seed file and carries the audit exception, so
`main` is green again once the release merges. The team rule remains: do not merge on red CI.

## Remaining work

- Presentation slide 9 quotes the 19 October figures (44/45 scenarios, 541 tests). The release
  check recorded 45/45 and 548; the slide can be updated before the panel.
- Limitations register KL-01 and evidence-pack item 3: their owners may cite the release run
  in `evidence/release/v1.0.0/scenarios/`.
- After the course: authentication, the manager review screen and a database, described in the
  [release notes](../../RELEASE_NOTES.md#deliberately-not-built), starting from the tagged
  release on a separate branch.
