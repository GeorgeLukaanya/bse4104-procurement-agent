"""Shared fixtures. The whole suite runs with NO API key and NO network.

The Model Selection Note makes requests per day the binding constraint on this
project ("The binding constraint on this project is therefore request
throughput, not token spend"), and the daily quota resets at midnight Pacific,
which is mid-morning in Kampala. A test suite that spent quota could leave the
team unable to run an evaluation until the next day, so no test here may make a
real call. Every test injects a stub backend.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from procurement_agent.cache import ExtractionCache  # noqa: E402
from procurement_agent.client import (  # noqa: E402
    Backend,
    PermanentError,
    RateLimitError,
    TransientError,
)
from procurement_agent.config import ExtractionConfig  # noqa: E402
from procurement_agent.extract import Extractor  # noqa: E402
from procurement_agent.runlog import RunLog  # noqa: E402

FIXTURES_DIR = ROOT / "fixtures"


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    """Guarantee no key is visible to any test, so nothing can call out.

    The model variables are cleared for a different reason: they are not a
    safety risk, but a developer with MODEL_NAME exported would otherwise see
    the fingerprint assertions fail against their own shell rather than against
    the pinned default.
    """
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "MODEL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    for name in ("MODEL_NAME", "GEMINI_MODEL"):
        monkeypatch.delenv(name, raising=False)


def conforming_payload(**overrides):
    """A complete, schema-conforming Normalised Quotation payload."""
    payload = {
        "supplier_name": "Nakawa Building Supplies Ltd",
        "currency": "UGX",
        "vat_treatment": "exclusive",
        "vat_rate_percent": 18,
        "delivery_cost": 250000,
        "lead_time_days": 5,
        "validity_date": "2026-10-02",
        "items": [
            {
                "item_name": "Portland cement, 50 kg bag",
                "quantity": 120,
                "unit_of_measure": "per bag",
                "unit_price": 34500,
            }
        ],
        "missing_fields": [],
    }
    payload.update(overrides)
    return payload


class StubBackend:
    """A scripted transport. Records every call; never touches the network.

    `responses` is a list of either a string (returned as the response body) or
    an exception instance (raised). Each call consumes the next element; the
    last element repeats once exhausted.
    """

    def __init__(self, responses=None):
        if responses is None:
            responses = [json.dumps(conforming_payload())]
        self.responses = list(responses)
        self.calls: list[dict] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def generate(self, system_instruction, user_message, config):
        self.calls.append(
            {
                "system_instruction": system_instruction,
                "user_message": user_message,
                "config": config,
            }
        )
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        item = self.responses[index]
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.fixture
def stub_backend():
    return StubBackend()


@pytest.fixture
def workspace(tmp_path):
    """Isolated cache and run log, so tests never touch the repository's own."""
    return {
        "cache": ExtractionCache(tmp_path / "cache"),
        "run_log": RunLog(tmp_path / "runs.jsonl"),
    }


@pytest.fixture
def make_extractor(workspace):
    def _make(backend, config=None, **kwargs):
        return Extractor(
            backend=backend,
            config=config or ExtractionConfig(),
            cache=workspace["cache"],
            run_log=workspace["run_log"],
            **kwargs,
        )

    return _make


@pytest.fixture
def run_log(workspace):
    return workspace["run_log"]


@pytest.fixture
def extraction_cache(workspace):
    return workspace["cache"]
