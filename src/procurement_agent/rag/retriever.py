"""Runtime retrieval (RAG stage 2).

Retrieval query builder, query embedding, vector search, then the step the
architecture draws as "no relevant clause found, return explicit absence note".

Two searches, not one
---------------------
The corpus holds two kinds of rule, and they answer different questions.

* **General rules** (policies and procedures) apply to every purchase. A
  quotation-count rule governs cement and airline tickets alike, so these are
  always returned, best `top_k` first, above only a low floor.
* **Item rules** (product specifications) apply to particular goods. They are
  kept only when they genuinely match the item, and when none do the result
  carries an explicit absence note for that item, which is what requirement
  7.3 asks for: "no policy clause was found for that item".

Why one search with one cutoff does not work
--------------------------------------------
Every query is phrased as a purchase, and every purchase is close to the
general purchasing rules. Measured with BAAI/bge-small-en-v1.5 over the 45
indexed clauses, using that real query phrasing:

==========================  ===========  =====================
Purchase                    Top score    Best specification
==========================  ===========  =====================
cement (catalogue)          0.684        0.684
binding wire (catalogue)    0.727        0.727
safety helmets (catalogue)  0.656        0.608
PVC pipe fittings (cat.)    0.693        0.693
electrical cable (cat.)     0.740        0.740
staff catering (not)        0.583        0.483
airline tickets (not)       0.658        0.508
software licence (not)      0.687        0.529
diesel fuel (not)           0.674        0.571
==========================  ===========  =====================

Top scores for goods the corpus says nothing specific about overlap entirely
with those it does, so no single cutoff separates them. Worse, with no cutoff
the airline-ticket purchase was offered the *cement* specification. Best
specification scores do separate: 0.608 and above for catalogue goods, 0.571
and below for the rest. `DEFAULT_ITEM_MIN_SCORE` sits in that gap, at 0.58
rather than its midpoint so that SPEC-001-C03 (substitution of grades and pack
sizes, 0.585 for the cement purchase) is kept.

These come from nine purchases and the gap is narrow. They are a starting
point for the 15-case RAG evaluation to confirm or move, not a finding.

An earlier calibration in this module reported unrelated queries at 0.40 to
0.45. That was measured on free-text questions ("what will the weather be")
rather than on the purchase phrasing `to_query` produces, and did not hold.

Why `top_k` is 5
----------------
For the cement purchase of UGX 4,140,000 the applicable clause, POL-001-C02
(UGX 500,000 to under 5,000,000), ranked below POL-001-C03 (5,000,000 and
over). Embeddings match the topic, quotation-count rules, but cannot place a
figure within a monetary band, so all bands arrive together and the adjacent
one can outscore the right one. A `top_k` of 3 lost C02; 5 keeps every band.
Choosing the band is left to the grounded generation step, which cites it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .embedder import Embedder
from .index import IndexError_, PolicyIndex, ScoredClause

GENERAL_CATEGORIES = ("policy", "procedure")
ITEM_CATEGORIES = ("product_specification",)

DEFAULT_TOP_K = 5
DEFAULT_MIN_SCORE = 0.50
DEFAULT_ITEM_MIN_SCORE = 0.58


class RetrievalError(ValueError):
    """Raised for a malformed retrieval request or retriever configuration."""


@dataclass(frozen=True)
class RetrievalRequest:
    """The procurement context a retrieval is for.

    In the architecture this comes from the confirmed landed-cost comparison.
    That calculator does not exist yet, so the fields are supplied directly.
    `estimated_total` must be a figure the deterministic layer produced: this
    module formats it and never computes it.
    """

    item: str
    category: str
    estimated_total: int | float | None = None
    currency: str = "UGX"

    def __post_init__(self) -> None:
        if not self.item.strip():
            raise RetrievalError("item must not be empty")
        if not self.category.strip():
            raise RetrievalError("category must not be empty")

    @property
    def total_text(self) -> str | None:
        """The total as shown to the embedder and the model, e.g. ``UGX 4,140,000``.

        `:,` adds thousands separators without rounding, so 8.5 stays 8.5.
        """
        if self.estimated_total is None:
            return None
        return f"{self.currency} {self.estimated_total:,}"

    def to_query(self) -> str:
        """The natural-language query that is embedded."""
        query = f"Purchase of {self.item.strip()}, category {self.category.strip()}"
        if self.total_text is not None:
            query += f", estimated total {self.total_text}"
        return query


@dataclass(frozen=True)
class RetrievalResult:
    """What was asked, what came back, what was kept, and what was absent."""

    request: RetrievalRequest
    query: str
    general: tuple[ScoredClause, ...]
    item: tuple[ScoredClause, ...]
    below_cutoff: tuple[ScoredClause, ...]
    top_k: int
    min_score: float
    item_min_score: float
    embedding_model: str
    policy_absence_note: str | None = None
    item_absence_note: str | None = None

    @property
    def clauses(self) -> tuple[ScoredClause, ...]:
        """Every kept clause: general rules first, then item rules."""
        return self.general + self.item

    @property
    def found(self) -> bool:
        return bool(self.clauses)

    @property
    def absence_notes(self) -> tuple[str, ...]:
        """The notes to show in place of missing rules, in display order."""
        return tuple(
            note for note in (self.policy_absence_note, self.item_absence_note) if note
        )


class Retriever:
    """Find the policy clauses that apply to one procurement request."""

    def __init__(
        self,
        index: PolicyIndex,
        embedder: Embedder,
        top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_MIN_SCORE,
        item_min_score: float = DEFAULT_ITEM_MIN_SCORE,
    ) -> None:
        if top_k < 1:
            raise RetrievalError("top_k must be at least 1")
        for name, value in (("min_score", min_score), ("item_min_score", item_min_score)):
            if not -1.0 <= value <= 1.0:
                raise RetrievalError(f"{name} is a cosine similarity, so it must be in [-1, 1]")
        self.index = index
        self.embedder = embedder
        self.top_k = top_k
        self.min_score = min_score
        self.item_min_score = item_min_score

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        if self.index.model_name is not None and self.index.model_name != self.embedder.model_name:
            # Vectors from two different models are not comparable. Qdrant
            # would still return results, confidently ranked and meaningless.
            raise IndexError_(
                f"index was built with {self.index.model_name!r} but the query "
                f"embedder is {self.embedder.model_name!r}"
            )

        query = request.to_query()
        vector = self.embedder.embed_query(query)

        general_hits = self.index.search(vector, self.top_k, GENERAL_CATEGORIES)
        item_hits = self.index.search(vector, self.top_k, ITEM_CATEGORIES)

        general = tuple(h for h in general_hits if h.score >= self.min_score)
        item = tuple(h for h in item_hits if h.score >= self.item_min_score)
        below_cutoff = tuple(
            [h for h in general_hits if h.score < self.min_score]
            + [h for h in item_hits if h.score < self.item_min_score]
        )

        subject = f"{request.item.strip()} ({request.category.strip()})"
        return RetrievalResult(
            request=request,
            query=query,
            general=general,
            item=item,
            below_cutoff=below_cutoff,
            top_k=self.top_k,
            min_score=self.min_score,
            item_min_score=self.item_min_score,
            embedding_model=self.embedder.model_name,
            policy_absence_note=(
                None if general
                else f"No procurement policy or procedure clause in the Policy Corpus was found for {subject}."
            ),
            item_absence_note=(
                None if item
                else f"No product specification in the Policy Corpus was found for {subject}."
            ),
        )
