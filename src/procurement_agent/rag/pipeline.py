"""The policy grounding pipeline, end to end, for a whole requisition.

Retrieve, generate, scan, validate, record:

1. **Retrieve** clauses for each item separately, or explicit absence notes.
2. **Generate** one grounded explanation per item in a single call, sending
   only the items that kept at least one clause. An item with nothing kept is
   answered by its notes alone. If no item kept anything, no request is spent.
3. **Scan** each item's answer for prohibited assertions (requirement 14.2,
   the extraction guard reused).
4. **Validate** each item's citations against *that item's* retrieval, so a
   clause supplied for another item does not count.
5. **Record** one trace entry for the requisition, whatever the outcome.

Each item is shown or withheld on its own. A cement answer that cites a rule
it was never given does not hide a correct answer for binding wire; it is
withheld with its reason while the rest are shown. The requisition reports
whether all, some or none of its items can be shown, so nothing downstream
mistakes a partial result for a complete one.

When an answer is withheld, the retrieved clauses and the reason are still
returned and traced, so the officer can see what was found and why.

This is *not* the architecture's "pause workflow, preserve state, allow retry"
branch. Nothing is kept between runs: a retry repeats retrieval and the model
call. The AI Boundary Matrix and Requirement 7.5 require a retry that skips
completed steps, which needs the Week 5 state model. The diagram also routes a
citation failure and an unavailable corpus to that one branch. Here they
differ: an unavailable corpus stops before any call (`ingest.open_index`),
while a citation failure withholds only its own item.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .. import guards
from ..client import (
    Backend, DeadlineExceeded, RetryBudgetExhausted, RetryPolicy,
    TimeoutError_, TransportError,
)
from ..config import ExtractionConfig
from .citations import CitationReport, validate_citations
from .grounding import (
    GroundedAnswer,
    GroundingError,
    generate_grounded_answer,
    grounding_config,
)
from .index import ScoredClause
from .retriever import RetrievalError, RetrievalRequest, RetrievalResult, Retriever

DEFAULT_TRACE_LOG = Path("evidence") / "traces" / "rag-runs.jsonl"
COMPONENT = "RAG"

# Item statuses.
STATUS_OK = "ok"
STATUS_NO_CLAUSES = "no_clauses"
STATUS_SUPPRESSED = "suppressed"
STATUS_CITATION_INVALID = "citation_invalid"
STATUS_GENERATION_FAILED = "generation_failed"
STATUS_RATE_LIMITED = "rate_limited"
STATUS_CALL_FAILED = "call_failed"
STATUS_TIMEOUT = "timeout"

# Item outcomes whose content may be shown to the officer as it stands.
SHOWABLE_STATUSES = (STATUS_OK, STATUS_NO_CLAUSES)

# Requisition statuses.
REQUISITION_OK = "ok"
REQUISITION_PARTIAL = "partial"
REQUISITION_WITHHELD = "withheld"


@dataclass(frozen=True)
class ItemOutcome:
    """What one requisition item produced."""

    ref: str
    status: str
    retrieval: RetrievalResult
    answer: GroundedAnswer | None = None
    citation_report: CitationReport | None = None
    suppressions: tuple[guards.Suppression, ...] = ()
    detail: str | None = None

    @property
    def shown(self) -> bool:
        return self.status in SHOWABLE_STATUSES

    def to_dict(self) -> dict[str, Any]:
        """A suppressed answer's text is never written: requirement 14.2 removes
        a prohibited value "before it reaches any user or record"."""
        retrieval = self.retrieval
        request = retrieval.request
        answer = None
        if self.answer is not None and self.status != STATUS_SUPPRESSED:
            answer = {
                "summary": self.answer.summary,
                "applicable_clauses": [
                    {"source_id": c.source_id, "version": c.version,
                     "clause_id": c.clause_id, "reason": c.reason}
                    for c in self.answer.citations
                ],
            }
        return {
            "ref": self.ref,
            "status": self.status,
            "shown": self.shown,
            "request": {
                "item": request.item,
                "category": request.category,
                "estimated_total": request.estimated_total,
                "currency": request.currency,
            },
            "retrieval": {
                "query": retrieval.query,
                "general": [_hit(h) for h in retrieval.general],
                "item": [_hit(h) for h in retrieval.item],
                "below_cutoff": [_hit(h) for h in retrieval.below_cutoff],
                "absence_notes": list(retrieval.absence_notes),
            },
            "answer": answer,
            "citation_check": None if self.citation_report is None else {
                "valid": self.citation_report.valid,
                "problems": [
                    {"kind": p.kind, "reference": p.reference, "detail": p.detail}
                    for p in self.citation_report.problems
                ],
            },
            "suppressed_patterns": [
                {"category": s.category, "field_path": s.field_path}
                for s in self.suppressions
            ],
            "detail": self.detail,
        }


@dataclass(frozen=True)
class RequisitionOutcome:
    """Everything one run produced, whether or not it succeeded."""

    items: tuple[ItemOutcome, ...]
    config: ExtractionConfig
    attempts: int = 0
    latency_s: float | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    )

    @property
    def status(self) -> str:
        shown = sum(item.shown for item in self.items)
        if shown == len(self.items):
            return REQUISITION_OK
        return REQUISITION_PARTIAL if shown else REQUISITION_WITHHELD

    @property
    def shown(self) -> bool:
        """True only when every item may be shown."""
        return self.status == REQUISITION_OK

    def to_dict(self) -> dict[str, Any]:
        """The trace entry, and the CLI's JSON output. Never carries the API key."""
        first = self.items[0].retrieval
        return {
            "timestamp": self.timestamp,
            "component": COMPONENT,
            "status": self.status,
            "item_count": len(self.items),
            "items_shown": sum(item.shown for item in self.items),
            "retrieval_settings": {
                "embedding_model": first.embedding_model,
                "top_k": first.top_k,
                "min_score": first.min_score,
                "item_min_score": first.item_min_score,
            },
            "items": [item.to_dict() for item in self.items],
            "attempts": self.attempts,
            "latency_s": None if self.latency_s is None else round(self.latency_s, 4),
            "config_fingerprint": self.config.fingerprint(),
        }


def _hit(hit: ScoredClause) -> dict[str, Any]:
    clause = hit.clause
    return {
        "clause_id": clause.clause_id,
        "source_id": clause.source_id,
        "version": clause.version,
        "title": clause.title,
        "heading": clause.heading,
        "score": round(hit.score, 4),
    }


class TraceLog:
    """Append-only JSONL, one entry per requisition, as `runlog.RunLog` is for extraction."""

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_TRACE_LOG

    def append(self, outcome: RequisitionOutcome) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(outcome.to_dict(), ensure_ascii=False, separators=(",", ":"))
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")


class PolicyPipeline:
    def __init__(
        self,
        retriever: Retriever,
        backend: Backend,
        config: ExtractionConfig | None = None,
        policy: RetryPolicy | None = None,
        trace: TraceLog | None = None,
    ) -> None:
        self.retriever = retriever
        self.backend = backend
        self.config = grounding_config(config)
        self.policy = policy
        self.trace = trace

    def run(self, requests: Sequence[RetrievalRequest]) -> RequisitionOutcome:
        """Ground every item on one requisition. Items keep their input order."""
        if not requests:
            raise RetrievalError("a requisition needs at least one item")
        outcome = self._run(requests)
        if self.trace is not None:
            self.trace.append(outcome)
        return outcome

    def _run(self, requests: Sequence[RetrievalRequest]) -> RequisitionOutcome:
        retrievals = {
            str(position): self.retriever.retrieve(request)
            for position, request in enumerate(requests, start=1)
        }
        to_ground = {ref: r for ref, r in retrievals.items() if r.found}

        if not to_ground:
            return RequisitionOutcome(self._items(retrievals, {}), self.config)

        try:
            call = generate_grounded_answer(self.backend, to_ground, self.config, self.policy)
        except DeadlineExceeded as exc:
            return self._failed(retrievals, to_ground, STATUS_TIMEOUT, str(exc),
                                exc.attempts, exc.latency_s)
        except RetryBudgetExhausted as exc:
            status = STATUS_RATE_LIMITED if exc.rate_limited else STATUS_CALL_FAILED
            if isinstance(exc.last_error, TimeoutError_):
                status = STATUS_TIMEOUT
            return self._failed(retrievals, to_ground, status, str(exc),
                                exc.attempts, exc.latency_s)
        except TransportError as exc:  # includes PermanentError
            return self._failed(retrievals, to_ground, STATUS_CALL_FAILED, str(exc), 1)
        except GroundingError as exc:
            return self._failed(retrievals, to_ground, STATUS_GENERATION_FAILED, str(exc), 1)

        judged = {
            ref: self._judge(ref, retrieval, call.answers[ref])
            for ref, retrieval in to_ground.items()
        }
        return RequisitionOutcome(
            self._items(retrievals, judged), call.config,
            attempts=call.attempts, latency_s=call.latency_s,
        )

    def _judge(self, ref: str, retrieval: RetrievalResult, answer: GroundedAnswer) -> ItemOutcome:
        # Both checks always run, so the trace records every problem with an
        # answer rather than stopping at the first.
        suppressions = tuple(guards.scan({
            "summary": answer.summary,
            "applicable_clauses": [c.reason for c in answer.citations],
        }))
        report = validate_citations(answer, retrieval)

        if suppressions:
            status, detail = STATUS_SUPPRESSED, "the answer asserted something prohibited (requirement 14.2)"
        elif not report.valid:
            status, detail = STATUS_CITATION_INVALID, "; ".join(p.detail for p in report.problems)
        else:
            status, detail = STATUS_OK, None
        return ItemOutcome(ref, status, retrieval, answer=answer, citation_report=report,
                           suppressions=suppressions, detail=detail)

    def _items(
        self,
        retrievals: dict[str, RetrievalResult],
        judged: dict[str, ItemOutcome],
    ) -> tuple[ItemOutcome, ...]:
        return tuple(
            judged.get(ref) or ItemOutcome(ref, STATUS_NO_CLAUSES, retrieval)
            for ref, retrieval in retrievals.items()
        )

    def _failed(
        self,
        retrievals: dict[str, RetrievalResult],
        to_ground: dict[str, RetrievalResult],
        status: str,
        detail: str,
        attempts: int,
        latency_s: float | None = None,
    ) -> RequisitionOutcome:
        """The call failed: every item that needed it fails; notes-only items still stand."""
        failed = {ref: ItemOutcome(ref, status, retrievals[ref], detail=detail) for ref in to_ground}
        return RequisitionOutcome(self._items(retrievals, failed), self.config,
                                  attempts=attempts, latency_s=latency_s)
