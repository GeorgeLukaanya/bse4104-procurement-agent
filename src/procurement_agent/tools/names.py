"""POL-002-C04 name resemblance. Exact match vs close match.

Names on a quotation are matched exactly against the register. A close
match is reported, never resolved: staff must not assume similarly named
businesses are the same supplier, and the officer records clearance
before comparison. Until that clearance exists, both sides of a pair
are marked ``NAME_DISCREPANCY``.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_LEGAL_SUFFIX = re.compile(r"\b(?:ltd|limited|inc|llc|plc|co|company)\b\.?", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")

# Seeded pair in DAT-002: "Lakeview Building Materials" / "Lakeview Building
# Supplies". First-two-token identity catches that without merging unrelated
# "... Supplies" names. SequenceMatcher is the backstop for other close pairs.
SIMILARITY_FLOOR = 0.82


def normalize_name(name: str) -> str:
    stripped = _LEGAL_SUFFIX.sub(" ", name.lower())
    stripped = _NON_ALNUM.sub(" ", stripped)
    return " ".join(stripped.split())


def names_match_exactly(left: str, right: str) -> bool:
    return normalize_name(left) == normalize_name(right) and bool(normalize_name(left))


def names_are_similar(left: str, right: str) -> bool:
    if names_match_exactly(left, right):
        return False
    a = normalize_name(left)
    b = normalize_name(right)
    if not a or not b:
        return False
    tokens_a = a.split()
    tokens_b = b.split()
    if len(tokens_a) >= 2 and len(tokens_b) >= 2 and tokens_a[:2] == tokens_b[:2]:
        return True
    return SequenceMatcher(None, a, b).ratio() >= SIMILARITY_FLOOR


def similar_registered_names(name: str, register: list[dict], *, exclude_id: str | None = None) -> list[str]:
    """Other AVL names close enough to be confused with ``name``."""
    found: list[str] = []
    for supplier in register:
        other_id = supplier.get("supplier_id")
        other_name = supplier.get("registered_name") or ""
        if exclude_id is not None and other_id == exclude_id:
            continue
        if names_are_similar(name, other_name):
            found.append(other_name)
    return found
