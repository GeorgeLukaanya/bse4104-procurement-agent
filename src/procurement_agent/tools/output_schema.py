"""Check a tool's response envelope against its published output schema.

FA-10 (docs/evaluation/tool-failure-tests.md): input was validated but output
was not, so a malformed tool result reached the caller as ``status: ok``.
Tool-catalogue section 9 promises the opposite. The agent loop reasons over
these results, so a result that does not match its contract must never be
handed on as data.

The schemas in ``docs/architecture/schemas/`` are the contract. The charter
fixes zero runtime dependencies, so this is a hand-written validator for the
JSON Schema subset those files use: type, const, enum, required, properties,
additionalProperties, items, oneOf, minimum, minItems, uniqueItems and
pattern. ``format``, ``description``, ``title`` and ``default`` are
annotations in draft 2020-12 and are not asserted. A keyword outside the
subset is an error rather than silently ignored, so a schema edit cannot
weaken the check without someone noticing.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "docs" / "architecture" / "schemas"

_ANNOTATIONS = {"$schema", "$id", "title", "description", "format", "default", "examples"}
_SUPPORTED = _ANNOTATIONS | {
    "type", "const", "enum", "required", "properties", "additionalProperties",
    "items", "oneOf", "minimum", "minItems", "uniqueItems", "pattern",
}


class SchemaUnavailable(RuntimeError):
    """The output schema for a tool could not be loaded."""


@lru_cache(maxsize=None)
def load(tool_name: str, schema_dir: str | None = None) -> dict[str, Any]:
    path = Path(schema_dir or SCHEMA_DIR) / f"{tool_name}.output.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SchemaUnavailable(f"{path}: {exc}") from exc


def _is_type(value: Any, name: str) -> bool:
    if name == "null":
        return value is None
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool) or (
            isinstance(value, float) and value.is_integer()
        )
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "string":
        return isinstance(value, str)
    if name == "array":
        return isinstance(value, list)
    if name == "object":
        return isinstance(value, dict)
    raise ValueError(f"unsupported type {name!r}")


def errors(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Every way ``value`` departs from ``schema``; empty means it conforms."""
    unknown = set(schema) - _SUPPORTED
    if unknown:
        return [f"{path}: schema uses unsupported keyword(s) {sorted(unknown)}"]

    found: list[str] = []

    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(value, name) for name in names):
            return [f"{path}: expected {'/'.join(names)}, got {type(value).__name__}"]
    if "const" in schema and value != schema["const"]:
        found.append(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        found.append(f"{path}: {value!r} is not one of {schema['enum']}")

    if "oneOf" in schema:
        matches = sum(1 for option in schema["oneOf"] if not errors(value, option, path))
        if matches != 1:
            found.append(f"{path}: matches {matches} of the oneOf options, expected exactly 1")

    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                found.append(f"{path}: missing required {key!r}")
        for key, item in value.items():
            if key in props:
                found.extend(errors(item, props[key], f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                found.append(f"{path}: unexpected field {key!r}")
            elif isinstance(schema.get("additionalProperties"), dict):
                found.extend(errors(item, schema["additionalProperties"], f"{path}.{key}"))

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            found.append(f"{path}: fewer than {schema['minItems']} items")
        if schema.get("uniqueItems"):
            seen = [json.dumps(item, sort_keys=True) for item in value]
            if len(seen) != len(set(seen)):
                found.append(f"{path}: items are not unique")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                found.extend(errors(item, schema["items"], f"{path}[{index}]"))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            found.append(f"{path}: {value} is below the minimum {schema['minimum']}")

    if isinstance(value, str) and "pattern" in schema:
        if not re.search(schema["pattern"], value):
            found.append(f"{path}: {value!r} does not match {schema['pattern']}")

    return found


def check(tool_name: str, envelope: dict[str, Any], schema_dir: str | None = None) -> list[str]:
    """Validate a whole response envelope for ``tool_name``."""
    return errors(envelope, load(tool_name, schema_dir))
