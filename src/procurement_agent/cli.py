"""Command-line entry point.

    python -m procurement_agent.cli fixtures/*.md

Framework-free by design. Project Charter v1.1 has not chosen an application
framework, and Week 2 must not force that decision — this CLI is one consumer of
the package, not the package's interface.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Iterable, Sequence

from . import __version__
from .cache import DEFAULT_CACHE_DIR, ExtractionCache
from .client import Backend, GeminiBackend, RetryPolicy
from .config import (
    API_KEY_ENV_VARS,
    ConfigError,
    ExtractionConfig,
    MissingAPIKeyError,
    load_api_key,
)
from .extract import ExtractionResult, Extractor
from .runlog import (
    DEFAULT_RUN_LOG,
    STATUS_EXTRACTION_FAILED,
    STATUS_OK,
    STATUS_RATE_LIMITED,
    STATUS_SUPPRESSED,
    RunLog,
)
from .schema import ITEM_LEVEL_FIELDS, QUOTATION_LEVEL_FIELDS

# Exit codes. 0 only when every file produced a conforming, unsuppressed record.
EXIT_OK = 0
EXIT_SOME_FAILED = 1
EXIT_USAGE = 2

_STATUS_LABEL = {
    STATUS_OK: "OK",
    STATUS_SUPPRESSED: "SUPPRESSED",
    STATUS_EXTRACTION_FAILED: "EXTRACTION-FAILED",
    STATUS_RATE_LIMITED: "RATE-LIMITED",
    "call_failed": "CALL-FAILED",
}

_FIELD_LABEL = {
    "supplier_name": "supplier name",
    "currency": "currency",
    "vat_treatment": "VAT treatment",
    "vat_rate_percent": "VAT rate (%)",
    "delivery_cost": "delivery/freight cost",
    "lead_time_days": "lead time (days)",
    "validity_date": "validity date",
    "item_name": "item name",
    "quantity": "quantity offered",
    "unit_of_measure": "unit of measure",
    "unit_price": "unit price",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        # prog is left to argparse so that both `python -m procurement_agent.cli`
        # and the `procurement-extract` console script name themselves correctly.
        description=(
            "Extract the eleven-field Normalised Quotation record from one or "
            "more Converted Quotation Documents (Markdown)."
        ),
        epilog=(
            "This tool performs no arithmetic. Unit normalisation, VAT, "
            "delivery apportionment, currency conversion, landed cost and "
            "ranking belong to the deterministic calculator downstream."
        ),
    )
    parser.add_argument("paths", nargs="*", metavar="FILE", help="Markdown quotation files")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a report")
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="bypass the cache entirely; every file makes a live call",
    )
    parser.add_argument(
        "--model",
        default=None,
        metavar="STRING",
        help=(
            "override the pinned model string. Must be an exact version; an "
            "alias ending in -latest is rejected."
        ),
    )
    parser.add_argument(
        "--cache-dir", default=str(DEFAULT_CACHE_DIR), metavar="DIR",
        help=f"cache directory (default: {DEFAULT_CACHE_DIR})",
    )
    parser.add_argument(
        "--run-log", default=str(DEFAULT_RUN_LOG), metavar="FILE",
        help=f"append-only run log (default: {DEFAULT_RUN_LOG})",
    )
    parser.add_argument(
        "--max-attempts", type=int, default=RetryPolicy.max_attempts, metavar="N",
        help="bounded retry budget per file (default: %(default)s)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


# --- rendering -------------------------------------------------------------


def _fmt(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def render(result: ExtractionResult, out) -> None:
    """Human-readable report for one file."""
    label = _STATUS_LABEL.get(result.status, result.status.upper())
    print(f"\n{'=' * 72}", file=out)
    print(f"{result.source}", file=out)
    print(f"{'=' * 72}", file=out)
    print(f"status              : {label}", file=out)

    source_note = "cache hit (no API call)" if result.cache_hit else "live call"
    print(f"source              : {source_note}", file=out)
    print(
        f"latency             : {result.latency_s:.3f}s  "
        f"({result.attempts} attempt(s))",
        file=out,
    )
    print(f"cache key           : {result.cache_key[:16]}…", file=out)

    if result.record is None:
        print(f"\n  reason: {result.detail}", file=out)
        return

    record = result.record
    displayed = result.record_dict or record.to_dict()

    print("\nquotation-level fields", file=out)
    for name in QUOTATION_LEVEL_FIELDS:
        print(f"  {_FIELD_LABEL[name]:<24}: {_fmt(displayed.get(name))}", file=out)

    items = displayed.get("items") or []
    print(f"\nline items ({len(items)})", file=out)
    if not items:
        print("  (none extracted)", file=out)
    for index, item in enumerate(items, start=1):
        print(f"  [{index}]", file=out)
        for name in ITEM_LEVEL_FIELDS:
            print(f"      {_FIELD_LABEL[name]:<20}: {_fmt(item.get(name))}", file=out)

    missing = displayed.get("missing_fields") or []
    print(f"\nmissing fields ({len(missing)})", file=out)
    if not missing:
        print("  (none reported)", file=out)
    for entry in missing:
        print(f"  {entry.get('field')}: {entry.get('reason')}", file=out)

    print(f"\nsuppressed patterns ({len(result.suppressions)})", file=out)
    if not result.suppressions:
        print("  (none — requirement 14.2 scan clean)", file=out)
    for finding in result.suppressions:
        print(f"  [{finding.category}] at {finding.field_path}", file=out)
        print(f"      {finding.description}: {finding.excerpt}", file=out)

    readiness = result.landed_cost
    state = "READY" if readiness.ready else "NOT READY"
    print(f"\nlanded-cost readiness: {state}", file=out)
    if readiness.ready:
        print(
            "  all inputs present; eligible for automated ranking by the "
            "deterministic calculator",
            file=out,
        )
    else:
        print(
            "  excluded from automated ranking and presented separately "
            "(requirement 6.3). Missing:",
            file=out,
        )
        for blocker in readiness.blockers:
            print(f"    - {blocker.field} (req {blocker.clause}): {blocker.reason}", file=out)


def render_summary(results: Sequence[ExtractionResult], out) -> None:
    print(f"\n{'=' * 72}", file=out)
    print("SUMMARY", file=out)
    print(f"{'=' * 72}", file=out)

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    for status, count in sorted(counts.items()):
        print(f"  {_STATUS_LABEL.get(status, status):<20}: {count}", file=out)

    hits = sum(1 for r in results if r.cache_hit)
    print(f"  {'cache hits':<20}: {hits}", file=out)

    # Latency across LIVE calls only. A cache hit made no request and its
    # near-zero elapsed time would drag the median down and misrepresent what
    # the model actually costs. These figures feed the Model Selection Note.
    live = [r.latency_s for r in results if r.used_live_call]
    print(f"\nlatency across live calls (n={len(live)})", file=out)
    if not live:
        print(
            "  no live calls were made in this run, so no latency figure is "
            "available. Nothing is estimated here.",
            file=out,
        )
        return
    print(f"  median              : {statistics.median(live):.3f}s", file=out)
    print(f"  worst case          : {max(live):.3f}s", file=out)
    print(
        "\n  These are measurements from this run only. They are the figures "
        "the\n  Model Selection Note's latency row requires; record them there "
        "with n.",
        file=out,
    )


# --- wiring ----------------------------------------------------------------


def _resolve_paths(raw: Iterable[str]) -> tuple[list[Path], list[str]]:
    """Expand and validate the given paths.

    A shell expands `fixtures/*.md` before we see it. When it does not — an
    unmatched glob, or a quoted argument — we expand it ourselves so the
    documented invocation works in either case.
    """
    resolved: list[Path] = []
    problems: list[str] = []
    for item in raw:
        path = Path(item)
        if any(ch in item for ch in "*?[") and not path.exists():
            matches = sorted(Path().glob(item))
            if not matches:
                problems.append(f"{item}: no files matched")
            resolved.extend(matches)
            continue
        if not path.exists():
            problems.append(f"{item}: no such file")
            continue
        if path.is_dir():
            problems.append(f"{item}: is a directory")
            continue
        resolved.append(path)
    return resolved, problems


def main(argv: Sequence[str] | None = None, backend: Backend | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out = sys.stdout

    if not args.paths:
        parser.print_usage(file=sys.stderr)
        print("error: at least one FILE is required", file=sys.stderr)
        return EXIT_USAGE

    paths, problems = _resolve_paths(args.paths)
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    if not paths:
        return EXIT_USAGE

    try:
        config = ExtractionConfig().with_model(args.model)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if backend is None:
        try:
            backend = GeminiBackend(api_key=load_api_key())
        except MissingAPIKeyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            print(
                "\nNo request was made. Set the key and re-run:\n"
                f"    export {API_KEY_ENV_VARS[0]}=...",
                file=sys.stderr,
            )
            return EXIT_USAGE
        except Exception as exc:  # noqa: BLE001 - surfaced to the user verbatim
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_USAGE

    extractor = Extractor(
        backend=backend,
        config=config,
        cache=ExtractionCache(args.cache_dir),
        run_log=RunLog(args.run_log),
        policy=RetryPolicy(max_attempts=args.max_attempts),
        use_cache=not args.no_cache,
    )

    results: list[ExtractionResult] = []
    for path in paths:
        # Requirement 3.3: a failure on one quotation does not stop the batch.
        try:
            results.append(extractor.extract_path(path))
        except OSError as exc:
            print(f"error: {path}: {exc}", file=sys.stderr)

    if args.json:
        live = [r.latency_s for r in results if r.used_live_call]
        payload = {
            "results": [r.to_dict() for r in results],
            "summary": {
                "files": len(results),
                "cache_hits": sum(1 for r in results if r.cache_hit),
                "live_calls": len(live),
                "median_latency_s": (
                    round(statistics.median(live), 4) if live else None
                ),
                "worst_latency_s": round(max(live), 4) if live else None,
            },
        }
        json.dump(payload, out, indent=2, ensure_ascii=False)
        out.write("\n")
    else:
        for result in results:
            render(result, out)
        render_summary(results, out)

    if not results:
        return EXIT_USAGE
    return EXIT_OK if all(r.ok for r in results) else EXIT_SOME_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
