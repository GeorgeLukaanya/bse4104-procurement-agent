#!/usr/bin/env python3
"""Drive the extraction CLI with NO API key, NO network and NO quota spent.

    python tools/offline_demo.py                 # all fixtures
    python tools/offline_demo.py --json          # machine-readable
    python tools/offline_demo.py fixtures/05-embedded-instruction.md

WHAT THIS IS
    A demonstration of the pipeline and the CLI's reporting. It injects a
    scripted backend that returns a hand-written record for each fixture,
    exactly as the test suite does, so the full path runs: cache lookup,
    schema validation, prohibited-pattern scan, landed-cost readiness and
    the run log. The cache and run log are its own, under var/offline-demo/,
    so nothing it writes can reach a live run or the evidence folder.

WHAT THIS IS NOT
    Evidence of anything about the model. No model reads the fixtures here.
    The records below were written by hand, the latency is a sleep, and the
    embedded instruction in fixture 05 is defeated by the guard rather than
    by the model. Extraction accuracy, real latency and the model's
    resistance to injection are all unverified and need a live run. See the
    Week 2 entry in docs/AI-ENGINEERING-LOG.md.

For a real run, install the SDK, set your own key, and use the CLI directly:

    pip install -e ".[gemini]"
    export GEMINI_API_KEY=...
    python -m procurement_agent.cli fixtures/*.md
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from procurement_agent import cli  # noqa: E402

# Keyed on a phrase that appears in the fixture, so the stub returns a record
# that plausibly belongs to that document.
SCRIPTED_RECORDS: dict[str, dict] = {
    "Nakawa Building Supplies": {
        "supplier_name": "Nakawa Building Supplies Ltd",
        "currency": "UGX",
        "vat_treatment": "exclusive",
        "vat_rate_percent": 18,
        "delivery_cost": 250000,
        "lead_time_days": 5,
        "validity_date": "2026-10-02",
        "items": [
            {"item_name": "Portland cement, 50 kg bag", "quantity": 120,
             "unit_of_measure": "per bag", "unit_price": 34500},
            {"item_name": "Iron sheets, gauge 30, 3 metre", "quantity": 80,
             "unit_of_measure": "per sheet", "unit_price": 52000},
            {"item_name": "Binding wire, 25 kg roll", "quantity": 15,
             "unit_of_measure": "per roll", "unit_price": 118000},
        ],
        "missing_fields": [],
    },
    "Mukwano Trading": {
        "supplier_name": "Mukwano Trading Stores",
        "currency": "UGX",
        "vat_treatment": "inclusive",
        "vat_rate_percent": 18,
        "delivery_cost": 180000,
        "lead_time_days": 7,
        "validity_date": "2026-09-30",
        "items": [
            {"item_name": "A4 photocopy paper, 80 gsm", "quantity": 40,
             "unit_of_measure": "per carton of 5 reams", "unit_price": 268000},
            {"item_name": "Ballpoint pens, blue", "quantity": 25,
             "unit_of_measure": "per carton of 50 boxes of 12", "unit_price": 142000},
            {"item_name": "Box files, foolscap", "quantity": 60,
             "unit_of_measure": "per carton of 10 files", "unit_price": 31500},
        ],
        "missing_fields": [],
    },
    "Eastgate Technologies": {
        "supplier_name": "Eastgate Technologies (U) Limited",
        "currency": "USD",
        "vat_treatment": "exclusive",
        "vat_rate_percent": 18,
        "delivery_cost": 420.0,
        "lead_time_days": 21,
        "validity_date": "2026-11-05",
        "items": [
            {"item_name": "Laptop, 14 inch, 16 GB RAM, 512 GB SSD", "quantity": 12,
             "unit_of_measure": "per unit", "unit_price": 615.0},
            {"item_name": "Wireless access point, dual band", "quantity": 8,
             "unit_of_measure": "per unit", "unit_price": 138.5},
            {"item_name": "UPS, 1500 VA line-interactive", "quantity": 6,
             "unit_of_measure": "per unit", "unit_price": 244.0},
        ],
        "missing_fields": [],
    },
    "Bugolobi Hardware": {
        "supplier_name": "Bugolobi Hardware Centre",
        "currency": None,
        "vat_treatment": None,
        "vat_rate_percent": None,
        "delivery_cost": None,
        "lead_time_days": None,
        "validity_date": None,
        "items": [
            {"item_name": "Steel door frame, 900mm", "quantity": 14,
             "unit_of_measure": None, "unit_price": 185000},
            {"item_name": "Padlock, 60mm brass", "quantity": 40,
             "unit_of_measure": None, "unit_price": 22500},
            {"item_name": "Hinges, 100mm steel pair", "quantity": 60,
             "unit_of_measure": None, "unit_price": 9800},
        ],
        "missing_fields": [
            {"field": "currency", "reason": "No currency symbol or code stated in the document"},
            {"field": "vat_treatment", "reason": "Document does not state whether prices include or exclude VAT"},
            {"field": "delivery_cost", "reason": "No delivery or freight terms stated"},
            {"field": "lead_time_days", "reason": "No lead time stated"},
            {"field": "validity_date", "reason": "No validity or expiry date stated"},
            {"field": "unit_of_measure", "reason": "Rate column states no unit basis for the price"},
        ],
    },
    # Deliberately non-compliant: the scripted model echoes the document's
    # embedded instruction into supplier_name, so the requirement 14.2 guard
    # has something to catch. This is what the guard is for.
    "Victory Supplies": {
        "supplier_name": "Victory Supplies & General Merchandise Ltd has been pre-approved by management",
        "currency": "UGX",
        "vat_treatment": "exclusive",
        "vat_rate_percent": 18,
        "delivery_cost": 300000,
        "lead_time_days": 10,
        "validity_date": "2026-10-08",
        "items": [
            {"item_name": "Floor tiles, 60x60cm, ceramic", "quantity": 400,
             "unit_of_measure": "per square metre", "unit_price": 41000},
            {"item_name": "Tile adhesive, 20 kg bag", "quantity": 90,
             "unit_of_measure": "per bag", "unit_price": 46500},
            {"item_name": "Grout, white, 5 kg pack", "quantity": 45,
             "unit_of_measure": "per pack", "unit_price": 27000},
        ],
        "missing_fields": [],
    },
    "Kawempe Steel": {
        "supplier_name": "Kawempe Steel & Allied Works Ltd",
        "currency": "UGX",
        "vat_treatment": "inclusive",
        "vat_rate_percent": 18,
        "delivery_cost": 220000,
        "lead_time_days": 4,
        "validity_date": "2026-07-15",
        "items": [
            {"item_name": "Mild steel angle bar, 50x50x5mm, 6m", "quantity": 70,
             "unit_of_measure": "per length", "unit_price": 96000},
            {"item_name": "Welding rods, 2.5mm, 5 kg packet", "quantity": 30,
             "unit_of_measure": "per packet", "unit_price": 58000},
            {"item_name": "Steel flat bar, 40x5mm, 6m", "quantity": 45,
             "unit_of_measure": "per length", "unit_price": 61500},
        ],
        "missing_fields": [],
    },
}

# A visible, non-zero delay so the latency column shows something. It is a
# sleep, not a measurement, and the banner says so.
SIMULATED_LATENCY_S = 0.05

# The demo never shares the real cache or run log. The cache key covers the
# document and the configuration but not the backend, so a scripted record in
# .cache/extractions would be served to the next live run as if Gemini had
# produced it, and a demo row in evidence/traces/ would read as evidence.
# var/ is git-ignored.
DEMO_DIR = ROOT / "var" / "offline-demo"
DEMO_CACHE_DIR = DEMO_DIR / "cache"
DEMO_RUN_LOG = DEMO_DIR / "runs.jsonl"


class ScriptedBackend:
    """Returns a hand-written record per fixture. Never touches the network."""

    def generate(self, system_instruction, user_message, config, *, timeout_s=30.0):
        time.sleep(SIMULATED_LATENCY_S)
        for marker, record in SCRIPTED_RECORDS.items():
            if marker in user_message:
                return json.dumps(record)
        raise AssertionError(
            "tools/offline_demo.py has no scripted record for this document. "
            "Add one to SCRIPTED_RECORDS, or run against a real key."
        )


BANNER = (
    "OFFLINE DEMO — scripted backend, no API call was made.\n"
    "Latency below is a simulated sleep, not a measurement of the model, and "
    "the records\nare hand-written. Extraction accuracy remains unverified."
)


def _default_fixture_args() -> list[str]:
    """Every fixture, as a path relative to the cwd when that is shorter."""
    paths = []
    for path in sorted((ROOT / "fixtures").glob("*.md")):
        if path.name == "README.md":
            continue
        try:
            paths.append(str(path.relative_to(Path.cwd())))
        except ValueError:
            paths.append(str(path))
    return paths


def _has_explicit_inputs(args: list[str]) -> bool:
    """True when the caller named documents themselves.

    Checked by file extension rather than "does not start with -", because a
    flag's value (`--cache-dir /tmp/c`) is also a bare word and would otherwise
    be mistaken for a document.
    """
    return any(
        a.endswith(".md") or any(ch in a for ch in "*?[")
        for a in args
        if not a.startswith("-")
    )


def main(argv: list[str]) -> int:
    args = list(argv)
    if not _has_explicit_inputs(args):
        args = _default_fixture_args() + args

    # The demo's output is meant to be identical on every machine, so it never
    # reads a .env: a teammate with MODEL_NAME set would otherwise see a
    # different model in the fingerprint than the one printed in the handover.
    if "--no-env-file" not in args:
        args.append("--no-env-file")
    if not any(a == "--cache-dir" or a.startswith("--cache-dir=") for a in args):
        args += ["--cache-dir", str(DEMO_CACHE_DIR)]
    if not any(a == "--run-log" or a.startswith("--run-log=") for a in args):
        args += ["--run-log", str(DEMO_RUN_LOG)]

    as_json = "--json" in args
    if not as_json:
        # Written to stdout, not stderr, so it stays in order with the report
        # rather than racing it through a separate stream.
        print(BANNER)

    code = cli.main(args, backend=ScriptedBackend())

    # Not repeated after a usage error, where the report never ran.
    if not as_json and code != cli.EXIT_USAGE:
        sys.stdout.flush()
        print("\n" + BANNER)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
