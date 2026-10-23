"""Streamlit operator view. Skipped unless the [ui] extra is installed."""

from __future__ import annotations

import json
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


def _text(at: AppTest) -> str:
    return " ".join(item.value for item in at.markdown)


def test_queue_lists_flagged_items_and_opens_cement(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    text = _text(at)
    assert "Flagged this week (11)" in text
    assert "Portland cement" in text
    assert at.button(key="start")


def test_start_review_stops_at_gate_2(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    at.button(key="start").click().run()
    assert not at.exception, at.exception
    text = _text(at)
    assert "Your confirmation is needed" in text
    assert "UGX 4,479,600" in text
    assert "Policy exception needed" in text
    assert "blacklisted" in text
    # Confirm stays disabled until the officer writes the exception reason.
    assert at.button(key="confirm").disabled


def test_confirm_with_reason_writes_draft(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    at.button(key="start").click().run()
    at.text_area(key="reason-AH-CM-001").input("Lakeview names are being cleared.").run()
    assert not at.button(key="confirm").disabled
    at.button(key="confirm").click().run()
    assert not at.exception, at.exception
    text = _text(at)
    assert "Draft requisition REQ-2026-001 created" in text
    assert "Lakeview names are being cleared." in text
    saved = (tmp_path / "ui" / "exception-reasons.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(saved[-1])["run_id"] == "AGT-2026-09-25-AH-CM-001-a.nakato"


def test_usd_quotation_asks_for_a_rate(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    at.button(key="open-AH-HT-001").click().run()
    at.button(key="start").click().run()
    assert not at.exception, at.exception
    text = _text(at)
    assert "in US dollars" in text
    assert "QT-015" in text
    at.number_input[0].set_value(3700.0)
    at.button[[b.label for b in at.button].index("Use this rate and compare again")].click().run()
    assert not at.exception, at.exception
    assert "Your confirmation is needed" in _text(at)


def test_manager_is_refused(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    at.selectbox[0].select("PROCUREMENT_MANAGER").run()
    at.button(key="start").click().run()
    assert not at.exception, at.exception
    text = " ".join(item.value for item in at.error)
    assert "unauthorized" in text
    assert "POL-004-C03" in text
