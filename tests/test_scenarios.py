"""The Week 7 scenario evaluation: dataset shape, and offline results that stay true."""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATASET = json.loads((ROOT / "evaluation-cases" / "week-07" / "scenarios.json").read_text(encoding="utf-8"))
RECORDED = json.loads(
    (ROOT / "evidence" / "evaluation" / "week-07" / "scenario-results.json").read_text(encoding="utf-8")
)
SCENARIOS = DATASET["scenarios"]


def _runner():
    spec = importlib.util.spec_from_file_location("run_scenarios", ROOT / "tools" / "run_scenarios.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_at_least_thirty_scenarios_covering_every_category():
    assert len(SCENARIOS) >= 30
    counts = Counter(s["category"] for s in SCENARIOS)
    assert set(counts) == set(DATASET["categories"])
    assert min(counts.values()) >= 5, counts


def test_ids_are_unique_and_sequential():
    assert [s["id"] for s in SCENARIOS] == [f"S-{n:02d}" for n in range(1, len(SCENARIOS) + 1)]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s["id"])
def test_scenario_is_well_formed(scenario):
    assert scenario["mode"] in ("offline", "live")
    assert scenario["expect"], "a scenario must state what it expects"
    assert set(scenario["criteria"]) <= set(DATASET["criteria"])
    assert {"task_completion", "safety"} <= set(scenario["criteria"])
    assert scenario["source"], "a scenario must name the requirement it tests"


def test_the_recorded_run_covers_every_scenario_and_includes_live():
    assert RECORDED["live"] is True
    assert [r["id"] for r in RECORDED["results"]] == [s["id"] for s in SCENARIOS]
    assert RECORDED["summary"]["not_run"] == 0


def test_offline_outcomes_still_match_the_recorded_evaluation():
    """A fix or a regression changes an outcome; re-run tools/run_scenarios.py --live then."""
    recorded = {r["id"]: r["result"] for r in RECORDED["results"] if r["mode"] == "offline"}
    now = {r["id"]: r["result"] for r in _runner().run(live=False)["results"] if r["mode"] == "offline"}
    changed = {sid: (recorded[sid], now[sid]) for sid in recorded if recorded[sid] != now[sid]}
    assert not changed, f"outcome changed since the recorded evaluation (recorded, now): {changed}"


def test_no_scenario_recorded_a_safety_violation():
    assert RECORDED["summary"]["safety_violations"] == 0
