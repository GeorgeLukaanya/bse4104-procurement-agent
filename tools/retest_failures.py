#!/usr/bin/env python3
"""Re-test every fixed failure in the Week 7 Failure Catalogue.

    python tools/retest_failures.py

Reads evidence/evaluation/week-07/failure-catalogue.json, runs each fixed
failure's regression tests with pytest, and writes the outcome to
evidence/evaluation/week-07/retest-results.json and retest-results.txt.

No API key and no network. A failure whose fix was verified against the live
model ("live-recorded") keeps its recorded evidence; only its offline guard
tests are re-run here, and the report says so rather than implying a new live
call. Open failures are listed, not tested.

Exit 0 when every fixed failure's tests pass, 1 otherwise.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "evidence" / "evaluation" / "week-07" / "failure-catalogue.json"
RESULTS_JSON = CATALOGUE.with_name("retest-results.json")
RESULTS_TXT = CATALOGUE.with_name("retest-results.txt")

def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _run_tests(node_ids: list[str]) -> dict:
    # Counted from pytest's JUnit XML report, not its console output, which
    # depends on verbosity flags (the project sets addopts = "-q").
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.xml"
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
             f"--junitxml={report}", *node_ids],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
        if report.exists():
            for case in ET.parse(report).getroot().iter("testcase"):
                if case.find("failure") is not None:
                    counts["failed"] += 1
                elif case.find("error") is not None:
                    counts["error"] += 1
                elif case.find("skipped") is not None:
                    counts["skipped"] += 1
                else:
                    counts["passed"] += 1
    ok = proc.returncode == 0 and counts["passed"] == len(node_ids)
    return {
        "exit_code": proc.returncode,
        **counts,
        "result": "PASS" if ok else "FAIL",
        "summary": f"{counts['passed']}/{len(node_ids)} passed",
    }


def main() -> int:
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    run = {
        "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "commit": _git("rev-parse", "--short", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "python": platform.python_version(),
        "catalogue_version": catalogue.get("catalogue_version"),
        "network_used": False,
        "results": [],
    }
    all_pass = True
    for failure in catalogue["failures"]:
        entry = {"id": failure["id"], "title": failure["title"], "status": failure["status"]}
        if failure["status"] == "fixed":
            retest = failure["retest"]
            outcome = _run_tests(retest["tests"])
            entry.update(retest_kind=retest["kind"], tests=retest["tests"], **outcome)
            if retest["kind"] == "live-recorded":
                entry["live_evidence"] = retest["evidence"]
                entry["note"] = "Fix verified live earlier; offline guard tests re-run now."
            all_pass = all_pass and outcome["result"] == "PASS"
        else:
            entry.update(result="OPEN", owner=failure.get("owner"), next_step=failure.get("next_step"))
        run["results"].append(entry)

    RESULTS_JSON.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "Failure Catalogue re-test",
        f"recorded {run['recorded_at']}  commit {run['commit']} ({run['branch']})  python {run['python']}  network: none",
        "",
    ]
    for entry in run["results"]:
        if entry["status"] == "fixed":
            lines.append(f"{entry['id']}  {entry['result']:<4}  {entry['summary']:<22}  {entry['title']}")
            for test in entry["tests"]:
                lines.append(f"        {test}")
            if entry.get("live_evidence"):
                lines.append("        live evidence: " + ", ".join(entry["live_evidence"]))
        else:
            lines.append(f"{entry['id']}  OPEN  owner {entry['owner']}: {entry['title']}")
    fixed = [e for e in run["results"] if e["status"] == "fixed"]
    passed = sum(1 for e in fixed if e["result"] == "PASS")
    lines += ["", f"{passed}/{len(fixed)} fixed failures re-tested PASS; "
              f"{len(run['results']) - len(fixed)} open."]
    RESULTS_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
