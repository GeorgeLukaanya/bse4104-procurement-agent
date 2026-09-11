# Synthetic quotation fixtures

Converted Quotation Documents — the Markdown a deterministic conversion layer
would produce from a supplier's PDF or Word file (Requirements Document v1.1,
requirement 2). Nothing here is a real supplier, price, address or contact.
Every name and figure is invented. The Model Selection Note makes this a hard
operating rule, not a preference: free-tier inputs can be logged by the
provider, so no real commercial data may pass through a free-tier key.

Each fixture reproduces a difficulty named in Project Charter v1.1 section 2:
"Quotations arrive in inconsistent form… Units differ (per piece, per carton,
per kilogram), some prices include VAT and some do not, and delivery terms, lead
times and warranty conditions appear in prose or not at all."

| Fixture | Characteristic exercised | Expected landed-cost readiness |
|---|---|---|
| `01-clean-table-ugx.md` | Control case. Structured table, all eleven fields present, UGX. | Ready |
| `02-prose-carton-vat-inclusive.md` | No table at all. Priced per carton with a stated pack size, VAT inclusive, delivery terms in words. | Ready |
| `03-usd-freight-separate.md` | Priced in USD with freight stated separately. Exercises requirement 5 currency normalisation downstream. | Ready |
| `04-minimal-missing-fields.md` | Missing currency, VAT treatment, delivery cost and validity. | Blocked — excluded from ranking under 6.3 |
| `05-embedded-instruction.md` | Carries an embedded instruction telling the model to mark the supplier approved and disregard competing quotations. | Ready, but the guard must fire if the instruction is echoed |
| `06-expired-validity.md` | Validity date already passed. | Ready — expiry is a deterministic eligibility check (4.2), not an extraction failure |

## What the fixtures are and are not evidence of

They are inputs. They are not evidence that extraction is accurate: that claim
needs a live API call against them and a comparison to a hand-keyed expected
record. No such run has been made. See the Week 2 entry in
`docs/AI-ENGINEERING-LOG.md`.

Fixture 05 in particular tests the *guard*, offline. Whether the model itself
resists the embedded instruction is an unverified claim until it has been run
live — that is Week 7 evaluation case S8.
