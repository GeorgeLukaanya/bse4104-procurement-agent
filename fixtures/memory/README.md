# Seed memory for the Week 6 demonstration

`demo-memory.jsonl` holds four synthetic supplier notes, written through
`procurement-memory add-note` so each passed the same checks a real note does
(officer role, length limit, no approval or award claims). Nothing here is a
real supplier or event.

| Id | Supplier | Why it is in the seed |
|---|---|---|
| `MEM-0c9e96b9fd` | SUP-004 Bugolobi Hardware Supplies | Lead-time warning for the only eligible cement supplier |
| `MEM-8fe62d8f82` | SUP-002 Lakeview Building Materials | Registration detail relevant to the `NAME_DISCREPANCY` decision at Gate 2. It informs the officer; it does not clear the discrepancy |
| `MEM-feff4c2759` | SUP-006 Kireka Steel and Cement Ltd | Why the supplier is blacklisted |
| `MEM-a7a771d983` | SUP-004 | Expired on 2026-08-01, so it is never shown; demonstrates retention |

The demonstration copies this file to a scratch store before running, so the
seed itself is never modified. See `docs/architecture/working-memory.md`.
