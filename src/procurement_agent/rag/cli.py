"""Command-line entry point for policy grounding.

One item:

    python -m procurement_agent.rag.cli --item "120 bags of cement" \\
        --category "building materials" --total 4140000

A whole requisition:

    python -m procurement_agent.rag.cli --requisition fixtures/requisitions/weekly-reorder.json

Opens the index that `procurement_agent.rag.ingest` built (RAG stage 1), runs
retrieval per item and one grounded generation call for the requisition
(stages 2 and 3), prints what the Procurement Officer would be shown, and
appends a trace entry. The corpus is not embedded here; if the index is missing
or out of date the command stops and says to run ingest.

Exit 0 when every item may be shown, 1 when any item was withheld, 2 when it
could not run (usage error, missing or stale index).

Until the landed-cost calculator exists, items are given on the command line or
in a requisition file. Each total must be a figure the deterministic layer
produced.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path
from typing import Sequence

from ..client import Backend, RetryPolicy
from ..config import ExtractionConfig, MissingAPIKeyError, load_api_key, load_model_name
from ..dotenv import DEFAULT_ENV_FILE, load_env_file
from . import grounding
from .corpus import DEFAULT_CORPUS_DIR, DEFAULT_SOURCE_REGISTER, CorpusError
from .embedder import Embedder, EmbedderUnavailable, FastEmbedEmbedder
from .index import IndexError_
from .ingest import DEFAULT_INDEX_DIR, open_index
from .pipeline import (
    DEFAULT_TRACE_LOG,
    REQUISITION_OK,
    REQUISITION_PARTIAL,
    REQUISITION_WITHHELD,
    STATUS_CALL_FAILED,
    STATUS_CITATION_INVALID,
    STATUS_GENERATION_FAILED,
    STATUS_NO_CLAUSES,
    STATUS_OK,
    STATUS_RATE_LIMITED,
    STATUS_SUPPRESSED,
    ItemOutcome,
    PolicyPipeline,
    RequisitionOutcome,
    TraceLog,
)
from .retriever import (
    DEFAULT_ITEM_MIN_SCORE,
    DEFAULT_MIN_SCORE,
    DEFAULT_TOP_K,
    RetrievalError,
    RetrievalRequest,
    Retriever,
)

EXIT_SHOWN = 0
EXIT_WITHHELD = 1
EXIT_USAGE = 2

_ITEM_LABEL = {
    STATUS_OK: "OK",
    STATUS_NO_CLAUSES: "NO CLAUSES FOUND",
    STATUS_SUPPRESSED: "SUPPRESSED",
    STATUS_CITATION_INVALID: "CITATION-INVALID",
    STATUS_GENERATION_FAILED: "GENERATION-FAILED",
    STATUS_RATE_LIMITED: "RATE-LIMITED",
    STATUS_CALL_FAILED: "CALL-FAILED",
}
_REQUISITION_LABEL = {
    REQUISITION_OK: "OK, every item can be shown",
    REQUISITION_PARTIAL: "PARTIAL, some items were withheld",
    REQUISITION_WITHHELD: "WITHHELD, no item can be shown",
}

_WIDTH = 76


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="procurement-policy",
        description="Find the policy clauses that apply to each item on a requisition and "
        "explain them, with every citation checked against what was retrieved for that item.",
    )
    single = parser.add_argument_group("one item")
    single.add_argument("--item", help='what is being bought, e.g. "120 bags of cement"')
    single.add_argument("--category", help='e.g. "building materials"')
    single.add_argument("--total", default=None,
                        help="estimated total from the deterministic layer, e.g. 4140000")
    single.add_argument("--currency", default="UGX")
    parser.add_argument("--requisition", metavar="FILE",
                        help='JSON file: {"items": [{"item", "category", "estimated_total", "currency"}]}')

    parser.add_argument("--json", action="store_true", help="emit the trace entry as JSON")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE,
                        help="cutoff for policies and procedures (default: %(default)s)")
    parser.add_argument("--item-min-score", type=float, default=DEFAULT_ITEM_MIN_SCORE,
                        help="cutoff for product specifications (default: %(default)s)")
    parser.add_argument("--model", default=None, help="override the pinned Gemini model")
    parser.add_argument("--max-attempts", type=int, default=RetryPolicy.max_attempts)
    parser.add_argument("--trace-log", default=str(DEFAULT_TRACE_LOG),
                        help="append-only trace (default: %(default)s)")
    parser.add_argument("--index-dir", default=str(DEFAULT_INDEX_DIR),
                        help="index built by ingest (default: %(default)s)")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--no-env-file", action="store_true")
    parser.add_argument("--corpus-dir", default=str(DEFAULT_CORPUS_DIR), help=argparse.SUPPRESS)
    parser.add_argument("--source-register", default=str(DEFAULT_SOURCE_REGISTER),
                        help=argparse.SUPPRESS)
    return parser


def _parse_total(raw: str | int | float | None) -> int | float | None:
    if raw is None or isinstance(raw, (int, float)):
        return raw
    cleaned = raw.replace(",", "").strip()
    try:
        return int(cleaned)
    except ValueError:
        return float(cleaned)


def load_requisition(path: str | Path) -> list[RetrievalRequest]:
    """Read a requisition file into item requests, rejecting anything malformed."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RetrievalError(f"requisition file {path} not found") from exc
    except json.JSONDecodeError as exc:
        raise RetrievalError(f"requisition file {path} is not valid JSON: {exc}") from exc

    entries = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(entries, list) or not entries:
        raise RetrievalError(f'requisition file {path} needs a non-empty "items" list')

    requests = []
    for position, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise RetrievalError(f"item {position} in {path} must be an object")
        try:
            requests.append(RetrievalRequest(
                item=str(entry.get("item", "")),
                category=str(entry.get("category", "")),
                estimated_total=_parse_total(entry.get("estimated_total")),
                currency=str(entry.get("currency", "UGX")),
            ))
        except ValueError as exc:  # includes RetrievalError
            raise RetrievalError(f"item {position} in {path}: {exc}") from exc
    return requests


def _requests_from_args(args: argparse.Namespace) -> list[RetrievalRequest]:
    if args.requisition and args.item is not None:
        raise RetrievalError("give either --requisition or --item, not both")
    if args.requisition:
        return load_requisition(args.requisition)
    if args.item is None or args.category is None:
        raise RetrievalError("give --item and --category, or --requisition FILE")
    return [RetrievalRequest(item=args.item, category=args.category,
                             estimated_total=_parse_total(args.total), currency=args.currency)]


def main(
    argv: Sequence[str] | None = None,
    backend: Backend | None = None,
    embedder: Embedder | None = None,
) -> int:
    args = build_parser().parse_args(argv)

    if not args.no_env_file:
        load_env_file(args.env_file)

    try:
        requests = _requests_from_args(args)
        config = ExtractionConfig().with_model(args.model or load_model_name())
        retry = RetryPolicy(max_attempts=args.max_attempts)
    except ValueError as exc:  # includes RetrievalError and ConfigError
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    try:
        index, _manifest = open_index(args.corpus_dir, args.source_register, args.index_dir)
    except (CorpusError, IndexError_) as exc:
        # The architecture's "corpus unavailable" branch: nothing is retrieved,
        # no request is spent, and the message says how to retry.
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    try:
        embedder = embedder or FastEmbedEmbedder()
        retriever = Retriever(index, embedder, top_k=args.top_k,
                              min_score=args.min_score, item_min_score=args.item_min_score)
        backend = backend or grounding.gemini_backend(load_api_key())
        pipeline = PolicyPipeline(retriever, backend, config=config, policy=retry,
                                  trace=TraceLog(args.trace_log))
        outcome = pipeline.run(requests)
    except MissingAPIKeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("\nNo request was made. Put GEMINI_API_KEY in .env and re-run.", file=sys.stderr)
        return EXIT_USAGE
    except (EmbedderUnavailable, IndexError_, RetrievalError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    finally:
        index.close()

    if args.json:
        print(json.dumps(outcome.to_dict(), indent=2, ensure_ascii=False))
    else:
        render(outcome, sys.stdout)
    return EXIT_SHOWN if outcome.shown else EXIT_WITHHELD


def render(outcome: RequisitionOutcome, out) -> None:
    def line(text: str = "") -> None:
        print(text, file=out)

    first = outcome.items[0].retrieval
    line(f"REQUISITION: {len(outcome.items)} item(s) | top {first.top_k} per search | "
         f"cutoffs general {first.min_score}, item {first.item_min_score}")
    line(f"             {first.embedding_model}")

    for item in outcome.items:
        _render_item(item, len(outcome.items), line)

    line()
    line("=" * _WIDTH)
    shown = sum(item.shown for item in outcome.items)
    line(f"requisition    : {_REQUISITION_LABEL[outcome.status]} ({shown} of {len(outcome.items)})")
    timing = "" if outcome.latency_s is None else f", {outcome.latency_s:.2f}s"
    calls = "no model call" if outcome.attempts == 0 else f"1 model call, {outcome.attempts} attempt(s){timing}"
    line(f"               : {calls}")


def _render_item(item: ItemOutcome, total: int, line) -> None:
    retrieval = item.retrieval
    request = retrieval.request

    def wrapped(text: str, indent: str = "  ") -> None:
        for chunk in textwrap.wrap(text, _WIDTH, initial_indent=indent, subsequent_indent=indent):
            line(chunk)

    line()
    line("=" * _WIDTH)
    line(f"ITEM {item.ref} of {total}: {request.item}")
    line("=" * _WIDTH)
    line(f"  category        : {request.category}")
    line(f"  estimated total : {request.total_text or '(not given)'}")

    line()
    line("  retrieved clauses")
    for label, hits in (("general rules", retrieval.general), ("item rules", retrieval.item)):
        line(f"    {label}")
        if not hits:
            line("      (none kept)")
        for hit in hits:
            line(f"      {hit.score:.3f}  {hit.clause.citation}  ({hit.clause.heading})")
    if retrieval.absence_notes:
        line("    notes")
        for note in retrieval.absence_notes:
            wrapped(note, indent="      ")

    line()
    if item.status == STATUS_NO_CLAUSES:
        line("  No clauses were kept for this item. The notes above are its answer.")
    elif item.answer is not None and item.status != STATUS_SUPPRESSED:
        line("  explanation")
        if not item.shown:
            line("  ** WITHHELD from the Procurement Officer; shown here for the trace only **")
        wrapped(item.answer.summary, indent="    ")
        line()
        line("  applicable clauses")
        resolved = {c.clause_id: c for c in (item.citation_report.cited_clauses
                                             if item.citation_report else ())}
        for citation in item.answer.citations:
            clause = resolved.get(citation.clause_id)
            name = clause.citation if clause else (
                f"{citation.source_id} v{citation.version}, {citation.clause_id} (NOT GROUNDED)"
            )
            line(f"    {name}")
            wrapped(citation.reason, indent="      ")

    report = item.citation_report
    if report is not None:
        line()
        if report.valid:
            line(f"  citation check  : PASSED, all {len(item.answer.citations)} citation(s) "
                 "name clauses supplied for this item")
        else:
            line("  citation check  : FAILED")
            for problem in report.problems:
                wrapped(f"- {problem.detail}", indent="      ")

    line(f"  item status     : {_ITEM_LABEL.get(item.status, item.status.upper())}")
    if item.detail and item.status != STATUS_CITATION_INVALID:
        wrapped(f"detail: {item.detail}", indent="    ")


if __name__ == "__main__":
    raise SystemExit(main())
