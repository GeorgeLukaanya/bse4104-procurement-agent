"""The Failure Catalogue must point at things that exist, or it proves nothing."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "evidence" / "evaluation" / "week-07" / "failure-catalogue.json"

with CATALOGUE.open(encoding="utf-8") as handle:
    DATA = json.load(handle)
FAILURES = DATA["failures"]
ALLOWED = DATA["allowed"]


def test_ids_are_unique_and_sequential():
    ids = [f["id"] for f in FAILURES]
    assert ids == [f"FC-{n:02d}" for n in range(1, len(ids) + 1)]


def test_at_least_five_genuine_failures_are_fixed_and_retested():
    """The Week 7 brief: at least five genuine failures, re-tested after fixes."""
    assert sum(1 for f in FAILURES if f["status"] == "fixed") >= 5


@pytest.mark.parametrize("failure", FAILURES, ids=lambda f: f["id"])
def test_entry_uses_the_allowed_vocabulary(failure):
    assert failure["status"] in ALLOWED["status"]
    assert failure["category"] in ALLOWED["category"]
    assert failure["severity"] in ALLOWED["severity"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", failure["discovered_on"])
    for field in ("title", "how_found", "symptom", "root_cause", "owner", "residual_risk"):
        assert failure.get(field), f"{failure['id']} has no {field}"


@pytest.mark.parametrize("failure", FAILURES, ids=lambda f: f["id"])
def test_every_evidence_path_exists(failure):
    paths = list(failure["discovery_evidence"])
    if failure.get("retest"):
        paths += failure["retest"]["evidence"]
    assert paths, f"{failure['id']} cites no evidence of the failure"
    for path in paths:
        assert (ROOT / path).exists(), f"{failure['id']}: {path} does not exist"


@pytest.mark.parametrize(
    "failure", [f for f in FAILURES if f["status"] == "fixed"], ids=lambda f: f["id"]
)
def test_fixed_failures_name_a_fix_and_a_retest(failure):
    assert re.fullmatch(r"[0-9a-f]{7}", failure["remediation"]["commits"][0])
    assert isinstance(failure["remediation"]["pr"], int)
    retest = failure["retest"]
    assert retest["kind"] in ALLOWED["retest_kind"]
    assert retest["tests"], f"{failure['id']} has no re-test"
    if retest["kind"] == "live-recorded":
        assert retest["evidence"], f"{failure['id']} claims a live re-test with no evidence"


@pytest.mark.parametrize(
    "failure", [f for f in FAILURES if f["status"] == "open"], ids=lambda f: f["id"]
)
def test_open_failures_have_an_owner_and_a_next_step(failure):
    assert failure["remediation"] is None and failure["retest"] is None
    assert failure.get("next_step")


def _test_exists(node_id: str) -> bool:
    path, _, name = node_id.partition("::")
    source = (ROOT / path).read_text(encoding="utf-8")
    return re.search(rf"^def {re.escape(name)}\(", source, re.MULTILINE) is not None


@pytest.mark.parametrize(
    "node_id",
    sorted({t for f in FAILURES if f.get("retest") for t in f["retest"]["tests"]}),
)
def test_every_retest_names_a_real_test(node_id):
    assert _test_exists(node_id), f"{node_id} is not a test in the suite"


def test_the_retest_runner_reports_a_failing_test_as_fail():
    spec = importlib.util.spec_from_file_location("retest", ROOT / "tools" / "retest_failures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    outcome = module._run_tests(["tests/test_failure_catalogue.py::no_such_test"])
    assert outcome["result"] == "FAIL"
