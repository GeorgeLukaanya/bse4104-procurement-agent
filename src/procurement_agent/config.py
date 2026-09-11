"""Model configuration and API key loading.

Every value here is fixed by specification, not by preference:

  * model string      Model Selection Note, "Pinned model string" row
  * temperature       Prompt Specification v1.0 section 4, decoding settings
  * max output tokens Prompt Specification v1.0 section 4, decoding settings
  * thinking budget   Prompt Specification v1.0 section 4, decoding settings
  * response mime     Prompt Specification v1.0 section 4, decoding settings
  * prompt version    Prompt Specification v1.0 section 8

The fingerprint of these values is part of the cache key. Changing any of them
must produce a different key, so that a result produced under one configuration
can never be returned as though it came from another.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, replace
from typing import Mapping

# Pinned by exact version. Never an alias.
#
# The Model Selection Note requires the model to be pinned by exact version
# string rather than referenced by an alias, "so that a provider-side version
# change cannot silently alter evaluation results mid-project". An alias such as
# `gemini-flash-latest` would repoint under us between two evaluation runs and
# the run log would not show it.
PINNED_MODEL = "gemini-3.1-flash-lite"

# Aliases that resolve provider-side. Rejected outright, including via --model.
FORBIDDEN_MODEL_SUFFIXES = ("-latest", "-preview", "@latest")

# Environment variable names searched, in order, for the API key.
API_KEY_ENV_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "MODEL_API_KEY")

# Environment variable names searched, in order, for the model string.
#
# An environment-supplied model is still validated by ExtractionConfig: the
# alias rejection in __post_init__ applies to it exactly as it applies to
# --model. Configurability here is about not editing source to change models,
# never about relaxing the pinning rule the Model Selection Note sets.
MODEL_ENV_VARS = ("MODEL_NAME", "GEMINI_MODEL")


class ConfigError(ValueError):
    """Raised when a configuration value violates the specification."""


class MissingAPIKeyError(RuntimeError):
    """Raised when no API key is present in the environment."""


@dataclass(frozen=True)
class ExtractionConfig:
    """Decoding configuration for one extraction run.

    Frozen: a run's configuration cannot drift mid-run, which would make its
    fingerprint a lie.
    """

    model: str = PINNED_MODEL

    # Prompt Specification v1.0 section 4: "Extraction is a deterministic task;
    # variability across identical inputs is a defect."
    temperature: float = 0.0

    # Prompt Specification v1.0 section 4: "Sufficient for a multi-item
    # quotation record."
    max_output_tokens: int = 2048

    # Prompt Specification v1.0 section 4 says "Minimum or disabled". Resolved
    # to 0 (disabled) because the fingerprint needs a concrete value; recorded
    # in docs/AI-ENGINEERING-LOG.md as a resolved ambiguity.
    thinking_budget: int = 0

    # Prompt Specification v1.0 section 4: "Enforces structured output."
    response_mime_type: str = "application/json"

    # Prompt Specification v1.0 section 8. Must be bumped whenever the literal
    # prompt text in prompts.py changes. See prompts.py for why.
    prompt_version: str = "1.0"

    def __post_init__(self) -> None:
        if not self.model or not self.model.strip():
            raise ConfigError("model string must not be empty")
        lowered = self.model.lower()
        for suffix in FORBIDDEN_MODEL_SUFFIXES:
            if lowered.endswith(suffix):
                raise ConfigError(
                    f"model {self.model!r} is an alias ending in {suffix!r}. "
                    "The Model Selection Note requires an exact pinned version "
                    "string so that a provider-side change cannot silently "
                    "alter evaluation results."
                )
        if self.temperature != 0:
            raise ConfigError(
                f"temperature must be 0, got {self.temperature}. Prompt "
                "Specification v1.0 section 4: extraction is deterministic and "
                "variance across identical inputs is a defect."
            )
        if self.max_output_tokens <= 0:
            raise ConfigError("max_output_tokens must be positive")
        if self.thinking_budget < 0:
            raise ConfigError("thinking_budget must not be negative")
        if not self.prompt_version.strip():
            raise ConfigError("prompt_version must not be empty")

    def with_model(self, model: str | None) -> "ExtractionConfig":
        """Return a copy pinned to `model`, or self when `model` is None."""
        if model is None:
            return self
        return replace(self, model=model)

    def fingerprint(self) -> dict[str, object]:
        """The full configuration fingerprint.

        Everything that can change model output appears here. This dict is
        written into the cache key, the cache entry and every run log entry, so
        that a recorded result is always attributable to the exact settings
        that produced it.
        """
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "thinking_budget": self.thinking_budget,
            "response_mime_type": self.response_mime_type,
            "prompt_version": self.prompt_version,
        }

    def fingerprint_digest(self) -> str:
        """A stable SHA-256 over the fingerprint, sorted so key order is fixed."""
        canonical = json.dumps(self.fingerprint(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_api_key(env: Mapping[str, str] | None = None) -> str:
    """Read the API key from the environment. Never from a file, never a literal.

    The key is returned to the transport and nowhere else. It is never placed in
    a cache entry, a run log entry, a fingerprint or an error message.
    """
    source = os.environ if env is None else env
    for name in API_KEY_ENV_VARS:
        value = source.get(name, "").strip()
        if value:
            return value
    raise MissingAPIKeyError(
        "No API key found. Set one of "
        + ", ".join(API_KEY_ENV_VARS)
        + " in the environment (see .env.example). The key is read from the "
        "environment only and is never written to the cache or the run log."
    )


def load_model_name(env: Mapping[str, str] | None = None) -> str | None:
    """Read the model string from the environment, or None when unset.

    Returns None rather than PINNED_MODEL so that a caller can tell "the
    environment asked for a model" apart from "nothing was configured" and
    apply its own precedence. The returned string is *not* validated here;
    ExtractionConfig validates it, so an alias is rejected by the same rule
    whatever route it arrived by.
    """
    source = os.environ if env is None else env
    for name in MODEL_ENV_VARS:
        value = source.get(name, "").strip()
        if value:
            return value
    return None


def redact(text: str, env: Mapping[str, str] | None = None) -> str:
    """Remove any configured API key from `text` before it is displayed or logged.

    A defence in depth: a provider error message can echo a request URL that
    carries the key as a query parameter.
    """
    source = os.environ if env is None else env
    out = text
    for name in API_KEY_ENV_VARS:
        value = source.get(name, "").strip()
        if value and value in out:
            out = out.replace(value, "***REDACTED***")
    return out
