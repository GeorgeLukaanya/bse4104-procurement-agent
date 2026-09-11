"""Pins the google-genai call and error shapes that GeminiBackend depends on.

The Model Integration Handover section 5 lists seven assumptions that were
written without the SDK installed. They were checked against google-genai
2.23.0 and all seven hold, so `GeminiBackend` needed no correction. These tests
exist so that a later SDK upgrade which *changes* one of them fails here, with
a name that says what broke, rather than silently.

The whole module skips when google-genai is absent. The SDK is an optional
extra precisely so the suite runs with no key, no network and no provider
library, and that must stay true.
"""

from __future__ import annotations

import pytest

from procurement_agent import client
from procurement_agent.config import ExtractionConfig
from procurement_agent.schema import response_schema

genai = pytest.importorskip("google.genai", reason="google-genai is an optional extra")
httpx = pytest.importorskip("httpx")

from google.genai import errors, types  # noqa: E402


def _api_error(status: int) -> Exception:
    """Build the exception the SDK itself would raise for `status`."""
    response = httpx.Response(
        status,
        json={"error": {"code": status, "status": "X", "message": "m"}},
        request=httpx.Request("POST", "http://example.invalid"),
    )
    try:
        errors.APIError.raise_for_response(response)
    except errors.APIError as exc:
        return exc
    raise AssertionError(f"the SDK did not raise for status {status}")


# --- the call shape ----------------------------------------------------------


def test_the_client_is_constructed_with_an_api_key_keyword():
    """Assumption 1: genai.Client(api_key=...)."""
    assert "api_key" in genai.Client.__init__.__annotations__


def test_generate_content_takes_model_contents_and_config():
    """Assumption 2: argument names and nesting."""
    import inspect

    parameters = inspect.signature(genai.models.Models.generate_content).parameters
    assert {"model", "contents", "config"} <= set(parameters)


def test_the_config_accepts_every_setting_the_prompt_specification_fixes():
    """Assumption 3: GenerateContentConfig carries all six decoding settings."""
    fields = types.GenerateContentConfig.model_fields
    for name in (
        "system_instruction",
        "temperature",
        "max_output_tokens",
        "response_mime_type",
        "response_schema",
        "thinking_config",
    ):
        assert name in fields, f"GenerateContentConfig no longer accepts {name}"


def test_the_response_schema_is_accepted_as_a_plain_dict():
    """Assumption 4: no conversion needed, so schema.py stays the single contract.

    If this ever fails, convert inside GeminiBackend — never in schema.py,
    which is also the validator.
    """
    config = types.GenerateContentConfig(
        response_schema=response_schema(),
        response_mime_type="application/json",
    )
    assert config.response_schema is not None


def test_thinking_config_accepts_a_budget():
    """Assumption 5: thinking_budget exists on this SDK."""
    assert "thinking_budget" in types.ThinkingConfig.model_fields
    assert types.ThinkingConfig(thinking_budget=0).thinking_budget == 0


def test_the_response_exposes_text():
    """Assumption 6: the body is at response.text, not nested under candidates."""
    assert "text" in dir(types.GenerateContentResponse)


def test_the_whole_config_builds_from_our_settings():
    """The six settings together, as GeminiBackend.generate assembles them."""
    config = ExtractionConfig()
    built = types.GenerateContentConfig(
        system_instruction="s",
        temperature=config.temperature,
        max_output_tokens=config.max_output_tokens,
        response_mime_type=config.response_mime_type,
        response_schema=response_schema(),
        thinking_config=types.ThinkingConfig(thinking_budget=config.thinking_budget),
    )
    assert built.temperature == 0
    assert built.max_output_tokens == 2048


# --- the error shape ---------------------------------------------------------
#
# Assumption 7, and the one with teeth: classify_error reads a status code off
# the exception to decide retryable versus permanent. If the SDK stops exposing
# `.code` as an int, a 429 classifies as permanent and the backoff that the
# Model Selection Note claims never runs.


def test_a_rate_limit_is_retryable():
    assert isinstance(client.classify_error(_api_error(429)), client.RateLimitError)


@pytest.mark.parametrize("status", [500, 503])
def test_server_errors_are_transient(status):
    assert isinstance(client.classify_error(_api_error(status)), client.TransientError)


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_are_permanent(status):
    """A bad key or an unreachable model must fail at once, not burn the budget."""
    assert isinstance(client.classify_error(_api_error(status)), client.PermanentError)


def test_the_sdk_still_exposes_an_integer_code():
    """The specific attribute classify_error depends on."""
    exc = _api_error(429)
    assert isinstance(exc.code, int)
    assert exc.code == 429
