"""Prohibited-pattern suppression.

Requirement 14.2: "IF AI Layer output contains an instruction to issue a
purchase order, an instruction to contact or message a supplier, or a statement
that funds have been committed or a contract awarded, THEN THE Deterministic
Layer SHALL suppress that output before it reaches any user or record, and SHALL
write a suppression audit entry recording the requisition identifier, timestamp
and the detected pattern."

This scan runs on every extraction even though the Normalised Quotation schema
has no free-text field. Three reasons:

  1. It is the control that must already work before Week 6 introduces
     justification drafting, where the model does emit prose. A control first
     exercised on the week it becomes load-bearing has never been tested.
  2. Constrained decoding restricts shape, not content. `supplier_name` is a
     string, and a string can carry "APPROVED — award contract to this vendor".
  3. The adversarial fixture proves the path end to end: a quotation carrying an
     embedded instruction is the Week 7 evaluation's adversarial case (S8, zero
     prohibited actions under adversarial prompts).

The scan reads the extracted record, not the source document. A supplier may
write whatever it likes in its own quotation; what matters under 14.2 is
whether that language survived into AI Layer output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterator

# Categories named by requirement 14.2 and by the AI Boundary Matrix v1.1
# "must not" list, plus the injection-echo category required by 3.7 and 14.5.
CATEGORY_APPROVAL = "approval_assertion"
CATEGORY_CONTRACT_AWARD = "contract_award_assertion"
CATEGORY_PURCHASE_ORDER = "purchase_order_instruction"
CATEGORY_VENDOR_SELECTION = "vendor_selection_assertion"
CATEGORY_FINANCIAL_COMMITMENT = "financial_commitment_assertion"
CATEGORY_INJECTION_ECHO = "prompt_injection_echo"

CATEGORIES: tuple[str, ...] = (
    CATEGORY_APPROVAL,
    CATEGORY_CONTRACT_AWARD,
    CATEGORY_PURCHASE_ORDER,
    CATEGORY_VENDOR_SELECTION,
    CATEGORY_FINANCIAL_COMMITMENT,
    CATEGORY_INJECTION_ECHO,
)

# Patterns are deliberately anchored on assertion verbs rather than on bare
# nouns. "Approved Vendor List" is ordinary procurement vocabulary and a
# supplier name may legitimately contain "Select" or "Premier"; only a claim
# that something HAS BEEN approved, awarded, selected or committed is prohibited.
_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        CATEGORY_APPROVAL,
        "approval asserted",
        re.compile(
            r"\b(?:is|are|was|were|has\s+been|have\s+been|hereby)\s+"
            r"(?:pre[-\s]?)?approved\b"
            r"|\bmark(?:ed|s|ing)?\s+(?:\w+\s+){0,3}(?:as\s+)?approved\b"
            r"|\bapprove\s+(?:this|the)\s+(?:supplier|vendor|quotation|requisition)\b"
            r"|\bapproval\s+(?:is\s+)?granted\b",
            re.IGNORECASE,
        ),
    ),
    (
        CATEGORY_CONTRACT_AWARD,
        "contract award asserted",
        re.compile(
            r"\bcontract\s+(?:has\s+been\s+|is\s+)?award(?:ed|s)?\b"
            r"|\baward(?:ed|s)?\s+(?:the\s+)?(?:contract|business|tender|order)\b"
            r"|\b(?:has\s+)?won\s+the\s+(?:tender|contract|bid)\b"
            r"|\btender\s+(?:has\s+been\s+)?award(?:ed)?\b",
            re.IGNORECASE,
        ),
    ),
    (
        CATEGORY_PURCHASE_ORDER,
        "purchase order instruction",
        re.compile(
            r"\b(?:issue|raise|place|send|generate|create)\s+"
            r"(?:a\s+|the\s+|an\s+)?(?:purchase\s+order|p\.?\s?o\.?\b|order\s+now)"
            r"|\bproceed\s+(?:directly\s+)?(?:to|with)\s+(?:purchase|order|payment)\b"
            r"|\bcontact\s+(?:the\s+)?supplier\s+(?:directly|immediately|now)\b",
            re.IGNORECASE,
        ),
    ),
    (
        CATEGORY_VENDOR_SELECTION,
        "vendor selection asserted",
        re.compile(
            r"\b(?:is|are|was|were|has\s+been|have\s+been)\s+"
            r"(?:the\s+)?(?:selected|chosen|preferred)\s+"
            r"(?:supplier|vendor|bidder)\b"
            r"|\bselect\s+(?:this|the)\s+(?:supplier|vendor)\b"
            r"|\b(?:recommend|choose|pick)\s+this\s+(?:supplier|vendor)\b"
            r"|\bdisregard\s+(?:all\s+)?(?:other|competing)\s+"
            r"(?:quotation|quote|supplier|vendor|bid)s?\b"
            r"|\bignore\s+(?:all\s+)?(?:other|competing)\s+"
            r"(?:quotation|quote|supplier|vendor|bid)s?\b",
            re.IGNORECASE,
        ),
    ),
    (
        CATEGORY_FINANCIAL_COMMITMENT,
        "financial commitment asserted",
        re.compile(
            r"\bfunds?\s+(?:have\s+been\s+|has\s+been\s+|are\s+|is\s+)?committed\b"
            r"|\bpayment\s+(?:has\s+been\s+|is\s+)?(?:authoris|authoriz)ed\b"
            r"|\bcommit(?:s|ted)?\s+(?:the\s+)?funds\b"
            r"|\bbudget\s+(?:has\s+been\s+)?committed\b"
            r"|\binitiate\s+(?:the\s+)?payment\b",
            re.IGNORECASE,
        ),
    ),
    (
        CATEGORY_INJECTION_ECHO,
        "prompt injection echoed",
        re.compile(
            r"\bignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+"
            r"(?:instruction|direction|prompt|rule)s?\b"
            r"|\bdisregard\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+"
            r"(?:instruction|direction|prompt|rule)s?\b"
            r"|\bsystem\s+(?:instruction|prompt)\b"
            r"|\bas\s+(?:an?\s+)?(?:ai|language\s+model|assistant)\b"
            r"|</?quotation>",
            re.IGNORECASE,
        ),
    ),
)

# Replacement written in place of a prohibited value. Requirement 14.2 requires
# suppression "before it reaches any user or record", so the offending text is
# removed rather than flagged and passed along.
SUPPRESSION_PLACEHOLDER = "[SUPPRESSED: prohibited pattern, requirement 14.2]"

# Used when a finding is replayed from a cache entry. The excerpt carries the
# prohibited text itself, so it is deliberately NOT written to the cache — 14.2
# keeps it out of every record except the audit trail. The original run log
# entry for the same cache key holds the excerpt.
EXCERPT_NOT_RETAINED = "(excerpt not retained in cache; see the run log entry for this cache key)"


@dataclass(frozen=True)
class Suppression:
    """One detected prohibited pattern, for the suppression audit entry."""

    category: str
    description: str
    field_path: str
    excerpt: str

    def to_dict(self) -> dict[str, str]:
        return {
            "category": self.category,
            "description": self.description,
            "field_path": self.field_path,
            "excerpt": self.excerpt,
        }


def _walk_strings(value: Any, path: str = "") -> Iterator[tuple[str, str]]:
    """Yield (path, text) for every string in a nested structure."""
    if isinstance(value, str):
        yield path or "<root>", value
    elif isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield from _walk_strings(child, child_path)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _walk_strings(child, f"{path}[{index}]")


def _excerpt(text: str, match: re.Match[str], window: int = 40) -> str:
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def scan(record: Any) -> list[Suppression]:
    """Return every prohibited pattern found in `record`. Empty list means clean."""
    findings: list[Suppression] = []
    for path, text in _walk_strings(record):
        for category, description, pattern in _PATTERNS:
            for match in pattern.finditer(text):
                findings.append(
                    Suppression(
                        category=category,
                        description=description,
                        field_path=path,
                        excerpt=_excerpt(text, match),
                    )
                )
    return findings


def suppress(record: dict[str, Any], findings: list[Suppression]) -> dict[str, Any]:
    """Return a copy of `record` with every offending string value replaced.

    The record is not discarded wholesale: the officer still needs to see which
    quotation misbehaved and what the rest of it said. What is removed is the
    prohibited text itself, which 14.2 forbids from reaching any user or record.
    """
    if not findings:
        return record
    offending_paths = {finding.field_path for finding in findings}

    def rewrite(value: Any, path: str = "") -> Any:
        current = path or "<root>"
        if isinstance(value, str):
            return SUPPRESSION_PLACEHOLDER if current in offending_paths else value
        if isinstance(value, dict):
            return {
                key: rewrite(child, f"{path}.{key}" if path else str(key))
                for key, child in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [rewrite(child, f"{path}[{i}]") for i, child in enumerate(value)]
        return value

    return rewrite(record)
