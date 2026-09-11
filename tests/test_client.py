"""Bounded retry. Transient failures recover; permanent ones fail immediately."""

from __future__ import annotations

import json

import pytest
from conftest import StubBackend, conforming_payload

from procurement_agent import client
from procurement_agent.config import ExtractionConfig

CONFIG = ExtractionConfig()
BODY = json.dumps(conforming_payload())


def _call(backend, policy=None, sleeps=None):
    recorded = sleeps if sleeps is not None else []
    return client.call_with_retry(
        backend,
        "system",
        "user",
        CONFIG,
        policy=policy or client.RetryPolicy(base_delay_s=0.01, max_delay_s=0.04),
        sleep=recorded.append,
        rand=lambda: 1.0,
    )


def test_backoff_recovers_from_transient_rate_limiting():
    """Two 429s then success. The run succeeds and reports three attempts."""
    backend = StubBackend(
        [
            client.RateLimitError("429 RESOURCE_EXHAUSTED"),
            client.RateLimitError("429 RESOURCE_EXHAUSTED"),
            BODY,
        ]
    )
    sleeps: list[float] = []
    result = _call(backend, sleeps=sleeps)

    assert result.text == BODY
    assert result.attempts == 3
    assert len(sleeps) == 2
    assert sleeps[1] > sleeps[0], "delay must grow exponentially between attempts"


def test_backoff_gives_up_and_reports_rate_limiting_explicitly():
    """The budget is bounded, and exhaustion names rate limiting as the cause.

    Reporting this as a generic failure would make a quota problem look like a
    model problem, and the team would debug the wrong thing.
    """
    backend = StubBackend([client.RateLimitError("429 RESOURCE_EXHAUSTED")])
    with pytest.raises(client.RetryBudgetExhausted) as exc:
        _call(backend, policy=client.RetryPolicy(max_attempts=3, base_delay_s=0.01))

    assert exc.value.rate_limited is True
    assert exc.value.attempts == 3
    assert backend.call_count == 3
    assert "rate limited" in str(exc.value)


@pytest.mark.parametrize("status", [500, 503])
def test_server_errors_are_retried(status):
    backend = StubBackend([client.TransientError(f"{status} error", status_code=status), BODY])
    result = _call(backend)
    assert result.attempts == 2


def test_timeouts_are_retried():
    backend = StubBackend([TimeoutError("request timed out"), BODY])
    result = _call(backend)
    assert result.attempts == 2


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_non_retryable_errors_fail_immediately(status):
    """A bad key or an unknown model must not spend the retry budget.

    Every wasted attempt is a request the free-tier daily quota cannot spare.
    """
    backend = StubBackend([client.PermanentError(f"{status} error", status_code=status)])
    with pytest.raises(client.PermanentError):
        _call(backend, policy=client.RetryPolicy(max_attempts=5, base_delay_s=0.01))
    assert backend.call_count == 1, "a permanent error must not be retried"


def test_classify_maps_status_codes_onto_the_taxonomy():
    class Err(Exception):
        def __init__(self, code):
            self.status_code = code
            super().__init__(f"http {code}")

    assert isinstance(client.classify_error(Err(429)), client.RateLimitError)
    assert isinstance(client.classify_error(Err(503)), client.TransientError)
    assert isinstance(client.classify_error(Err(500)), client.TransientError)
    assert isinstance(client.classify_error(Err(400)), client.PermanentError)
    assert isinstance(client.classify_error(Err(401)), client.PermanentError)


def test_unknown_errors_are_treated_as_permanent():
    assert isinstance(client.classify_error(ValueError("???")), client.PermanentError)


def test_retry_delays_are_bounded_and_jittered():
    policy = client.RetryPolicy(base_delay_s=1.0, max_delay_s=4.0)
    assert policy.delay_for(1, rand=lambda: 1.0) == 1.0
    assert policy.delay_for(2, rand=lambda: 1.0) == 2.0
    assert policy.delay_for(9, rand=lambda: 1.0) == 4.0, "delay must be capped"
    assert policy.delay_for(3, rand=lambda: 0.25) == pytest.approx(1.0), "jitter applies"


def test_api_key_is_redacted_from_transport_errors(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "SECRET-KEY-VALUE")
    err = client.PermanentError("401 from https://api?key=SECRET-KEY-VALUE")
    assert "SECRET-KEY-VALUE" not in str(err)
    assert "REDACTED" in str(err)
