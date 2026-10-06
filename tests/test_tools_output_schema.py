"""FA-10: a tool response that breaks its output schema is discarded, not relayed."""

from __future__ import annotations

import json

import pytest

from procurement_agent.tools import contract, dispatch, invoke, output_schema

TOOLS = contract.ALL_TOOLS


@pytest.fixture(autouse=True)
def _fresh_schema_cache():
    output_schema.load.cache_clear()
    yield
    output_schema.load.cache_clear()


def _malformed(*args, **kwargs):
    # The exact shape FA-10 injected in the Week 4 failure tests.
    return "ok", {"unexpected": "shape"}, [], None


def test_fa10_malformed_output_is_discarded(tmp_path, monkeypatch):
    monkeypatch.setattr(dispatch.reorder_mod, "check_reorder_need", _malformed)
    log = tmp_path / "runs.jsonl"
    result = invoke(
        "check_reorder_need",
        {"review_date": "2026-09-25"},
        caller_role="PROCUREMENT_OFFICER",
        run_log=str(log),
    )
    assert result["status"] == "failed"
    assert result["data"] is None
    assert [e["code"] for e in result["errors"]] == ["OUTPUT_SCHEMA_INVALID"]
    assert "$.data" in result["errors"][0]["detail"]
    row = json.loads(log.read_text().splitlines()[-1])
    assert row["status"] == "failed" and row["data"] is None


def test_the_discard_envelope_itself_conforms(tmp_path, monkeypatch):
    monkeypatch.setattr(dispatch.reorder_mod, "check_reorder_need", _malformed)
    result = invoke(
        "check_reorder_need",
        {"review_date": "2026-09-25"},
        caller_role="PROCUREMENT_OFFICER",
        run_log=str(tmp_path / "runs.jsonl"),
    )
    assert output_schema.check("check_reorder_need", result) == []


def test_a_missing_schema_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(output_schema, "SCHEMA_DIR", tmp_path / "nowhere")
    result = invoke(
        "check_reorder_need",
        {"review_date": "2026-09-25", "skus": ["AH-CM-001"]},
        caller_role="PROCUREMENT_OFFICER",
        run_log=str(tmp_path / "runs.jsonl"),
    )
    assert result["status"] == "failed"
    assert result["data"] is None
    assert result["errors"][0]["code"] == "OUTPUT_SCHEMA_INVALID"


def test_a_real_call_still_conforms(tmp_path):
    result = invoke(
        "check_reorder_need",
        {"review_date": "2026-09-25", "skus": ["AH-CM-001"]},
        caller_role="PROCUREMENT_OFFICER",
        run_log=str(tmp_path / "runs.jsonl"),
    )
    assert result["status"] == "ok"
    assert output_schema.check("check_reorder_need", result) == []


@pytest.mark.parametrize("tool", TOOLS)
def test_schema_error_vocabulary_matches_the_code(tool):
    """Every CODE_* constant is a code the schema accepts, and nothing more."""
    schema = output_schema.load(tool)
    allowed = set(schema["properties"]["errors"]["items"]["properties"]["code"]["enum"])
    declared = {v for k, v in vars(contract).items() if k.startswith("CODE_")}
    assert declared == allowed


def test_unsupported_schema_keywords_are_reported_not_ignored():
    problems = output_schema.errors({"a": 1}, {"type": "object", "maxProperties": 0})
    assert problems and "unsupported" in problems[0]


@pytest.mark.parametrize(
    "value, schema, ok",
    [
        (None, {"type": ["string", "null"]}, True),
        (3, {"type": "integer", "minimum": 4}, False),
        (True, {"type": "integer"}, False),
        ("QT-002", {"type": "string", "pattern": "^QT-[0-9]{3}$"}, True),
        ("x", {"enum": ["a", "b"]}, False),
        ([1, 1], {"type": "array", "uniqueItems": True}, False),
        ({"a": 1}, {"type": "object", "additionalProperties": False}, False),
        ({}, {"type": "object", "required": ["a"]}, False),
        (1, {"oneOf": [{"type": "integer"}, {"type": "number"}]}, False),
    ],
)
def test_validator_keywords(value, schema, ok):
    assert (output_schema.errors(value, schema) == []) is ok
