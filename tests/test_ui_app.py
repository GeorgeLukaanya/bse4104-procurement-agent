"""Streamlit operator view. Skipped unless the [ui] extra is installed."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "src" / "procurement_agent" / "ui" / "app.py"


def _app(tmp_path, monkeypatch) -> AppTest:
    monkeypatch.setenv("PROCUREMENT_UI_DIR", str(tmp_path / "ui"))
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at


def test_run_review_stops_at_gate_2(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    at.button[0].click().run()
    assert not at.exception, at.exception
    text = " ".join(item.value for item in at.warning)
    assert "awaiting_human" in text
    assert "confirm" in text.lower()


def test_confirm_writes_draft(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    at.button[0].click().run()
    at.button[1].click().run()
    assert not at.exception, at.exception
    text = " ".join(item.value for item in at.success)
    assert "completed" in text


def test_manager_is_refused(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    at.selectbox[1].select("PROCUREMENT_MANAGER").run()
    at.button[0].click().run()
    assert not at.exception, at.exception
    text = " ".join(item.value for item in at.error)
    assert "unauthorized" in text
    assert "POL-004-C03" in text
