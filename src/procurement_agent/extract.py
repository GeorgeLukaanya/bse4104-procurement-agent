"""Orchestration.

One quotation, six steps, in this order:

  1. Cache lookup            keyed on document AND configuration fingerprint
  2. Model call              schema-constrained, bounded retry
  3. Schema validation       conform or be rejected outright (requirement 3.3)
  4. Prohibited-pattern scan requirement 14.2
  5. Landed cost readiness   requirement 6.3
  6. Persist                 cache entry and run log entry

This module performs no arithmetic on any monetary value. It counts attempts and
measures elapsed seconds; it never totals a price, applies VAT, converts a unit
or a currency, computes landed cost or ranks anything. Requirement 6.6 and the
AI Boundary Matrix v1.1 assign all of that to the deterministic calculator that
consumes this output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import guards, prompts, runlog, schema
from .cache import CacheEntry, ExtractionCache, document_digest
from .client import (
    Backend,
    CallResult,
    DeadlineExceeded,
    PermanentError,
    RetryBudgetExhausted,
    RetryPolicy,
    TransportError,
    TimeoutError_,
    call_with_retry,
)
from .config import ExtractionConfig
from .runlog import (
    STATUS_CALL_FAILED,
    STATUS_EXTRACTION_FAILED,
    STATUS_OK,
    STATUS_RATE_LIMITED,
    STATUS_SUPPRESSED,
    STATUS_TIMEOUT,
    RunLog,
    RunLogEntry,
)
from .schema import LandedCostReadiness, NormalisedQuotation


@dataclass(frozen=True)
class ExtractionResult:
    """The outcome of one extraction, successful or not."""

    source: str
    status: str
    cache_key: str
    cache_hit: bool
    attempts: int
    latency_s: float
    config_fingerprint: dict[str, Any]
    record: NormalisedQuotation | None = None
    record_dict: dict[str, Any] | None = None
    suppressions: tuple[guards.Suppression, ...] = ()
    landed_cost: LandedCostReadiness = field(
        default_factory=lambda: LandedCostReadiness(ready=False)
    )
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK

    @property
    def used_live_call(self) -> bool:
        """True when this result cost a request against the daily quota."""
        return not self.cache_hit and self.attempts > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "status": self.status,
            "cache_key": self.cache_key,
            "cache_hit": self.cache_hit,
            "attempts": self.attempts,
            "latency_s": round(self.latency_s, 4),
            "record": self.record_dict,
            "suppressed_patterns": [s.to_dict() for s in self.suppressions],
            "landed_cost": self.landed_cost.to_dict(),
            "detail": self.detail,
            "config_fingerprint": self.config_fingerprint,
        }


class Extractor:
    """Runs the pipeline for one Converted Quotation Document at a time.

    The backend is injected. Nothing here constructs a Gemini client, which is
    what lets the whole pipeline be exercised offline against a stub.
    """

    def __init__(
        self,
        backend: Backend,
        config: ExtractionConfig | None = None,
        cache: ExtractionCache | None = None,
        run_log: RunLog | None = None,
        policy: RetryPolicy | None = None,
        use_cache: bool = True,
    ) -> None:
        self.backend = backend
        self.config = config or ExtractionConfig()
        self.cache = cache if cache is not None else ExtractionCache()
        self.run_log = run_log if run_log is not None else RunLog()
        self.policy = policy or RetryPolicy()
        self.use_cache = use_cache

    # -- public API ---------------------------------------------------------

    def extract_path(self, path: str | Path) -> ExtractionResult:
        """Extract from a Converted Quotation Document on disk."""
        p = Path(path)
        markdown = p.read_text(encoding="utf-8")
        return self.extract(markdown, source=str(p))

    def extract(self, converted_markdown: str, source: str) -> ExtractionResult:
        key = self.cache.key_for(converted_markdown, self.config)
        fingerprint = self.config.fingerprint()

        # --- 1. Cache lookup -------------------------------------------------
        if self.use_cache:
            entry = self.cache.get(key)
            if entry is not None:
                return self._finish_from_cache(source, key, entry, fingerprint)

        # --- 2. Model call ---------------------------------------------------
        system_instruction = prompts.SYSTEM_INSTRUCTION
        user_message = prompts.build_user_message(converted_markdown)
        try:
            call: CallResult = call_with_retry(
                self.backend,
                system_instruction,
                user_message,
                self.config,
                policy=self.policy,
            )
        except DeadlineExceeded as exc:
            return self._finish_failure(
                source, key, fingerprint, STATUS_TIMEOUT, str(exc),
                attempts=exc.attempts, latency_s=exc.latency_s,
            )
        except RetryBudgetExhausted as exc:
            # Reported as rate limiting when that is what defeated it, rather
            # than as a generic failure. A silent give-up would make a quota
            # problem look like a model problem.
            status = STATUS_RATE_LIMITED if exc.rate_limited else STATUS_CALL_FAILED
            if isinstance(exc.last_error, TimeoutError_):
                status = STATUS_TIMEOUT
            return self._finish_failure(
                source, key, fingerprint, status, str(exc), attempts=exc.attempts,
                latency_s=exc.latency_s,
            )
        except PermanentError as exc:
            return self._finish_failure(
                source, key, fingerprint, STATUS_CALL_FAILED, str(exc), attempts=1
            )
        except TransportError as exc:  # pragma: no cover - defensive
            return self._finish_failure(
                source, key, fingerprint, STATUS_CALL_FAILED, str(exc), attempts=1
            )

        # --- 3. Schema validation -------------------------------------------
        # Requirement 3.3: non-conforming output is rejected outright. Nothing
        # is salvaged from the payload, not even the fields that did parse.
        try:
            record = schema.validate_raw(call.text)
        except schema.SchemaValidationError as exc:
            return self._finish_failure(
                source,
                key,
                fingerprint,
                STATUS_EXTRACTION_FAILED,
                str(exc),
                attempts=call.attempts,
                latency_s=call.latency_s,
            )

        record_dict = record.to_dict()

        # --- 4. Prohibited-pattern scan -------------------------------------
        suppressions = guards.scan(record_dict)
        if suppressions:
            record_dict = guards.suppress(record_dict, suppressions)

        # --- 5. Landed cost readiness ---------------------------------------
        readiness = schema.landed_cost_readiness(record)

        status = STATUS_SUPPRESSED if suppressions else STATUS_OK

        # --- 6. Persist ------------------------------------------------------
        if self.use_cache:
            self.cache.put(
                CacheEntry(
                    key=key,
                    document_sha256=document_digest(converted_markdown),
                    config_fingerprint=fingerprint,
                    record=record_dict,
                    attempts=call.attempts,
                    latency_s=call.latency_s,
                    # Excerpts are omitted deliberately: they carry the
                    # prohibited text, which 14.2 keeps out of every record
                    # except the audit trail.
                    suppressions=[
                        {
                            "category": s.category,
                            "description": s.description,
                            "field_path": s.field_path,
                        }
                        for s in suppressions
                    ],
                )
            )

        result = ExtractionResult(
            source=source,
            status=status,
            cache_key=key,
            cache_hit=False,
            attempts=call.attempts,
            latency_s=call.latency_s,
            config_fingerprint=fingerprint,
            record=record,
            record_dict=record_dict,
            suppressions=tuple(suppressions),
            landed_cost=readiness,
        )
        self._log(result)
        return result

    # -- internals ----------------------------------------------------------

    def _finish_from_cache(
        self,
        source: str,
        key: str,
        entry: CacheEntry,
        fingerprint: dict[str, Any],
    ) -> ExtractionResult:
        """Rebuild a result from a cache hit. No API call is made."""
        try:
            record = schema.validate(entry.record)
        except schema.SchemaValidationError as exc:
            # A cached entry that no longer validates is treated as a miss on
            # the next run rather than served; failing here keeps a stale
            # contract from re-entering the pipeline unnoticed.
            return self._finish_failure(
                source,
                key,
                fingerprint,
                STATUS_EXTRACTION_FAILED,
                f"cached entry failed revalidation: {exc}",
                attempts=0,
                cache_hit=True,
            )

        record_dict = record.to_dict()

        # The cached record already has its offending values replaced, so a
        # fresh scan of it would find nothing and the quotation would read as
        # clean. Replay the findings stored with the entry instead, and scan as
        # well in case a pattern was added to guards.py since the entry was
        # written.
        replayed = [
            guards.Suppression(
                category=item.get("category", "unknown"),
                description=item.get("description", ""),
                field_path=item.get("field_path", "<root>"),
                excerpt=guards.EXCERPT_NOT_RETAINED,
            )
            for item in entry.suppressions
        ]
        rescanned = guards.scan(record_dict)
        if rescanned:
            record_dict = guards.suppress(record_dict, rescanned)
        known = {(s.category, s.field_path) for s in replayed}
        suppressions = replayed + [
            s for s in rescanned if (s.category, s.field_path) not in known
        ]

        readiness = schema.landed_cost_readiness(record)
        status = STATUS_SUPPRESSED if suppressions else STATUS_OK

        result = ExtractionResult(
            source=source,
            status=status,
            cache_key=key,
            cache_hit=True,
            attempts=0,
            latency_s=0.0,
            config_fingerprint=fingerprint,
            record=record,
            record_dict=record_dict,
            suppressions=tuple(suppressions),
            landed_cost=readiness,
        )
        self._log(result)
        return result

    def _finish_failure(
        self,
        source: str,
        key: str,
        fingerprint: dict[str, Any],
        status: str,
        detail: str,
        attempts: int,
        latency_s: float = 0.0,
        cache_hit: bool = False,
    ) -> ExtractionResult:
        """A failed run is logged exactly like a successful one."""
        result = ExtractionResult(
            source=source,
            status=status,
            cache_key=key,
            cache_hit=cache_hit,
            attempts=attempts,
            latency_s=latency_s,
            config_fingerprint=fingerprint,
            detail=detail,
        )
        self._log(result)
        return result

    def _log(self, result: ExtractionResult) -> None:
        self.run_log.append(
            RunLogEntry(
                source=result.source,
                cache_key=result.cache_key,
                cache_hit=result.cache_hit,
                status=result.status,
                attempts=result.attempts,
                latency_s=result.latency_s,
                config_fingerprint=result.config_fingerprint,
                suppressed_patterns=[s.to_dict() for s in result.suppressions],
                landed_cost_blockers=[
                    b.to_dict() for b in result.landed_cost.blockers
                ],
                landed_cost_ready=result.landed_cost.ready,
                detail=result.detail,
            )
        )
