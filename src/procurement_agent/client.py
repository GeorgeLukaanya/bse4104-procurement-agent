"""Gemini transport with bounded retry.

The backend is an injectable protocol. Nothing above this module knows whether
it is talking to Google or to a stub, which is what lets the test suite run with
no API key and no network and consume no free-tier quota. The Model Selection
Note makes requests per day the binding constraint on the project, so a test
suite that spent quota would be a defect in its own right.

Retry policy follows the Model Selection Note, section 4: "An exponential
backoff retry mechanism is built into the API client to handle temporary rate
limits gracefully." Bounded, with jitter, and only for errors that can actually
succeed on a retry.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .config import ExtractionConfig, redact

# HTTP statuses worth retrying. 429 is the free-tier rate limit; 500 and 503 are
# provider-side transients. Everything else — 400 malformed request, 401/403 bad
# key, 404 unknown model — is a fault on our side that a retry cannot fix.
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 503})


class TransportError(RuntimeError):
    """Base class for every transport failure."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(redact(message))


class TransientError(TransportError):
    """A failure that a later attempt may succeed at: 500, 503, or a timeout."""


class RateLimitError(TransientError):
    """HTTP 429. Free-tier request quota exceeded."""

    def __init__(self, message: str, status_code: int | None = 429) -> None:
        super().__init__(message, status_code=status_code)


class TimeoutError_(TransientError):
    """The request did not complete in time."""


class PermanentError(TransportError):
    """A failure no retry can fix. Fails immediately rather than burning budget."""


class RetryBudgetExhausted(TransportError):
    """Every permitted attempt was made and all of them failed.

    Carries the last underlying error so the caller can report *why* it gave up
    — specifically, so a run defeated by rate limiting is reported as rate
    limiting rather than as a generic failure.
    """

    def __init__(self, message: str, attempts: int, last_error: TransportError) -> None:
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(message, status_code=last_error.status_code)

    @property
    def rate_limited(self) -> bool:
        return isinstance(self.last_error, RateLimitError)


@dataclass(frozen=True)
class CallResult:
    """One completed model call."""

    text: str
    attempts: int
    latency_s: float


class Backend(Protocol):
    """The transport seam. Implemented by GeminiBackend and by test stubs."""

    def generate(
        self,
        system_instruction: str,
        user_message: str,
        config: ExtractionConfig,
    ) -> str:
        """Return the raw response text, or raise a TransportError subclass."""
        ...


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded exponential backoff with full jitter.

    Full jitter (`uniform(0, computed_delay)`) rather than a fixed delay,
    because several quotations in one batch hit the same 429 at the same moment
    and would otherwise retry in lockstep and collide again.
    """

    max_attempts: int = 4
    base_delay_s: float = 0.5
    max_delay_s: float = 8.0
    jitter: bool = True

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay_s < 0:
            raise ValueError("base_delay_s must not be negative")
        if self.max_delay_s < self.base_delay_s:
            raise ValueError("max_delay_s must not be below base_delay_s")

    def delay_for(self, attempt: int, rand: Callable[[], float] = random.random) -> float:
        """Delay before the attempt following `attempt` (1-based)."""
        raw = min(self.base_delay_s * (2 ** (attempt - 1)), self.max_delay_s)
        if not self.jitter:
            return raw
        return raw * rand()


def classify_error(exc: BaseException) -> TransportError:
    """Map an arbitrary SDK exception onto our retryable/permanent taxonomy.

    The google-genai SDK is not imported here. Classification reads a status
    code off the exception if it exposes one, and otherwise falls back to the
    exception type, so the mapping holds without a hard dependency on the SDK
    being installed.
    """
    if isinstance(exc, TransportError):
        return exc

    if isinstance(exc, TimeoutError):
        return TimeoutError_(f"request timed out: {exc}")

    status = None
    for attribute in ("status_code", "code", "http_status"):
        value = getattr(exc, attribute, None)
        if isinstance(value, int):
            status = value
            break
    if status is None:
        response = getattr(exc, "response", None)
        value = getattr(response, "status_code", None)
        if isinstance(value, int):
            status = value

    message = f"{type(exc).__name__}: {exc}"

    if status == 429:
        return RateLimitError(message)
    if status in RETRYABLE_STATUS_CODES:
        return TransientError(message, status_code=status)
    if status is not None:
        return PermanentError(message, status_code=status)

    lowered = str(exc).lower()
    if "timed out" in lowered or "timeout" in lowered:
        return TimeoutError_(message)
    if "429" in lowered or "resource_exhausted" in lowered or "rate limit" in lowered:
        return RateLimitError(message)
    if "503" in lowered or "unavailable" in lowered:
        return TransientError(message, status_code=503)
    if "500" in lowered or "internal error" in lowered:
        return TransientError(message, status_code=500)

    # Unknown shape. Treated as permanent so an unrecognised fault fails fast
    # instead of spending the retry budget on something a retry cannot fix.
    return PermanentError(message)


def call_with_retry(
    backend: Backend,
    system_instruction: str,
    user_message: str,
    config: ExtractionConfig,
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    rand: Callable[[], float] = random.random,
) -> CallResult:
    """Call `backend`, retrying bounded-exponentially on transient failures.

    `sleep`, `monotonic` and `rand` are injected so the test suite can exercise
    backoff without spending wall-clock time on it.

    Latency is measured across the whole call including waits, because that is
    what a user experiences and what acceptance criterion 3.1's 30-second
    ceiling is measured against.
    """
    policy = policy or RetryPolicy()
    started = monotonic()
    last_error: TransportError | None = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            text = backend.generate(system_instruction, user_message, config)
        except BaseException as exc:  # noqa: BLE001 - re-raised after classification
            error = classify_error(exc)
            if isinstance(error, PermanentError):
                # Fail immediately. Retrying a bad API key or an unknown model
                # spends requests that the free-tier daily quota cannot spare.
                raise error from exc
            last_error = error
            if attempt == policy.max_attempts:
                break
            sleep(policy.delay_for(attempt, rand=rand))
            continue
        return CallResult(
            text=text, attempts=attempt, latency_s=monotonic() - started
        )

    assert last_error is not None
    kind = "rate limited" if isinstance(last_error, RateLimitError) else "transient"
    raise RetryBudgetExhausted(
        f"gave up after {policy.max_attempts} attempt(s); last failure was "
        f"{kind}: {last_error}",
        attempts=policy.max_attempts,
        last_error=last_error,
    )


class GeminiBackend:
    """google-genai transport, constructed lazily.

    The SDK is imported inside __init__ rather than at module scope so that
    importing this package — and therefore running the test suite — does not
    require google-genai to be installed.
    """

    def __init__(self, api_key: str, client: Any | None = None) -> None:
        if client is not None:
            self._client = client
            return
        try:
            from google import genai  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise PermanentError(
                "google-genai is not installed. Install it with "
                "`pip install google-genai`, or inject a backend for offline use."
            ) from exc
        self._client = genai.Client(api_key=api_key)

    def generate(
        self,
        system_instruction: str,
        user_message: str,
        config: ExtractionConfig,
    ) -> str:
        from google.genai import types  # type: ignore[import-not-found]

        from .schema import response_schema

        try:
            response = self._client.models.generate_content(
                model=config.model,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=config.temperature,
                    max_output_tokens=config.max_output_tokens,
                    response_mime_type=config.response_mime_type,
                    response_schema=response_schema(),
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=config.thinking_budget
                    ),
                ),
            )
        except BaseException as exc:  # noqa: BLE001 - classified for the retry loop
            raise classify_error(exc) from exc

        text = getattr(response, "text", None)
        if not text:
            # An empty body is a conformance problem, not a transport one, and
            # is surfaced as such rather than retried.
            raise PermanentError(
                "provider returned an empty response body; nothing to validate"
            )
        return text
