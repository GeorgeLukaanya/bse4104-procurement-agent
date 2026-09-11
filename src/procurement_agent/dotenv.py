"""Minimal `.env` reader.

`python-dotenv` is deliberately not used. pyproject declares
``dependencies = []`` because the Project Charter has not chosen an application
framework, and a convenience that reads eight lines of text does not justify
the first runtime dependency in the package.

Precedence, and why it runs this way round: **the process environment always
wins over the file.** A value already exported into the shell is a deliberate
act for this run; a value in `.env` is a stored default. If the file could
overwrite an export, then

    GEMINI_API_KEY=... python -m procurement_agent.cli fixtures/01.md

would silently use the key from the file instead, which is the opposite of
what anyone typing that expects. Pass ``override=True`` only when the caller
means "the file is authoritative".

Nothing here writes a value anywhere but ``os.environ``. The API key in
particular continues to reach the transport and nothing else: this module does
not log, print or return it in any summary. See ``config.load_api_key``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import MutableMapping

DEFAULT_ENV_FILE = Path(".env")

# `export KEY=value` is valid in a file people also source from a shell.
_EXPORT_PREFIX = "export "


def parse_env(text: str) -> dict[str, str]:
    """Parse `.env` text into a mapping. Malformed lines are skipped, not raised.

    A stray line in a config file should not stop a run that has everything it
    actually needs, so parsing is forgiving: a line with no ``=`` is ignored
    rather than treated as an error.
    """
    values: dict[str, str] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(_EXPORT_PREFIX):
            line = line[len(_EXPORT_PREFIX) :].lstrip()

        key, separator, value = line.partition("=")
        if not separator:
            continue

        key = key.strip()
        if not key or not _is_valid_key(key):
            continue

        values[key] = _clean_value(value)

    return values


def _is_valid_key(key: str) -> bool:
    """Accept the shell-variable shape and nothing else."""
    first = key[0]
    if not (first.isalpha() or first == "_"):
        return False
    return all(character.isalnum() or character == "_" for character in key)


def _clean_value(value: str) -> str:
    """Strip surrounding quotes, or an unquoted trailing comment.

    A quoted value is taken literally, so a ``#`` inside quotes survives. An
    unquoted value is cut at the first ` #`, which is how the same line would
    read in a shell. The space matters: a bare ``#`` can appear inside a
    credential and must not truncate it.
    """
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]

    comment_at = value.find(" #")
    if comment_at != -1:
        value = value[:comment_at]
    return value.strip()


def load_env_file(
    path: str | os.PathLike[str] = DEFAULT_ENV_FILE,
    env: MutableMapping[str, str] | None = None,
    override: bool = False,
) -> dict[str, str]:
    """Apply `path` to the environment and return only what was actually set.

    A missing file is not an error: `.env` is git-ignored and absent on a fresh
    clone, and the package is expected to run from exported variables alone.
    Returns the keys applied, so a caller can report *which* names came from
    the file without ever reading their values back out.
    """
    target = os.environ if env is None else env
    env_path = Path(path)

    try:
        text = env_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError:
        # Unreadable is treated as absent for the same reason: the run may not
        # need the file at all, and failing here would block that.
        return {}

    applied: dict[str, str] = {}
    for key, value in parse_env(text).items():
        if not override and target.get(key, "").strip():
            continue
        target[key] = value
        applied[key] = value

    return applied
