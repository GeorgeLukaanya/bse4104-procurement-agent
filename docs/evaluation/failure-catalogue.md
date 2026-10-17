# Failure Catalogue

| Field | Value |
|---|---|
| Week | 7 |
| Owner | Lukaanya George |
| Due | 16 October 2026 |
| Status | FC-08 / FC-09 fixes and retests recorded, 17 October 2026 |
| Path | `docs/evaluation/failure-catalogue.md` |

## Brief requirement

At least five genuine failures with remediation and re-test evidence.

## FC-08 / FC-09 closure records

Remediation owner for both entries: **Beingana Jim Junior**. These are the two
targeted closure records; the broader catalogue brief above is unchanged.

| Failure | Cause and remediation | Required retest evidence | Status |
|---|---|---|---|
| **FC-08 — unit preservation** | Gemini replaced the source price basis `each` with generic `unit`. Prompt **v1.4** strengthens rule 2 with the exact “Each chair” case, preservation of explicit table units, no default units, and a source comparison before returning. Config, specification and cache version agree. | Full uncached ten-case live regression **10/10 PASS**; TC-04 returns exactly `each` (6.2720 s). Independent live S-41 also returns exactly `each` (5.9860 s). | **Fixed — 17 October 2026** |
| **FC-09 — model deadline** | The shared extraction/RAG client had no request timeout. It now passes the remaining budget to every Gemini request, disables SDK retries, limits application retries/backoff to **30 s overall**, rejects late responses, and returns/logs structured `timeout` results with real attempts and latency. | Combined live S-41 / S-44 / S-45 rerun **3/3 PASS**, at 5.9860 / 2.5054 / 25.1461 s. Client/timeout tests **28 passed**; full local suite **511 passed**. | **Fixed — 17 October 2026** |

See the [remediation write-up and reproduction commands](fc08-fc09-follow-up.md),
[field-by-field regression review](../../evidence/evaluation/week-07-fc08-fc09-v1.4/review-summary.json),
[combined live scenario results](../../evidence/evaluation/week-07-fc08-fc09-v1.4/scenario-results.json)
and [timeout tests](../../evidence/evaluation/week-07-fc08-fc09-v1.4/timeout-tests.txt).
The original failures and the initial remediation run are retained; no failed
observation was overwritten or counted as a pass. Review and remote CI remain
separate from these measured local retest results.
