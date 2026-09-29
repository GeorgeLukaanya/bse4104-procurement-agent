"""The offline demo must never share the real cache or the evidence run log."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_demo():
    spec = importlib.util.spec_from_file_location("offline_demo", ROOT / "tools" / "offline_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _captured_args(monkeypatch, argv):
    demo = _load_demo()
    seen = {}

    def fake_main(args, backend=None):
        seen["args"] = list(args)
        return 0

    monkeypatch.setattr(demo.cli, "main", fake_main)
    demo.main(argv)
    return demo, seen["args"]


def _value(args, flag):
    return args[args.index(flag) + 1]


def test_defaults_point_away_from_real_cache_and_evidence(monkeypatch):
    demo, args = _captured_args(monkeypatch, ["--json"])
    assert Path(_value(args, "--cache-dir")) == demo.DEMO_CACHE_DIR
    assert Path(_value(args, "--run-log")) == demo.DEMO_RUN_LOG
    assert "evidence" not in Path(_value(args, "--run-log")).parts
    assert ".cache" not in Path(_value(args, "--cache-dir")).parts


def test_explicit_paths_are_respected(monkeypatch, tmp_path):
    log, cache = tmp_path / "log.jsonl", tmp_path / "c"
    _, args = _captured_args(
        monkeypatch, ["--json", "--run-log", str(log), "--cache-dir", str(cache)]
    )
    assert args.count("--run-log") == 1 and _value(args, "--run-log") == str(log)
    assert args.count("--cache-dir") == 1 and _value(args, "--cache-dir") == str(cache)


def test_real_run_writes_only_under_the_given_paths(tmp_path, capsys):
    demo = _load_demo()
    log, cache = tmp_path / "runs.jsonl", tmp_path / "cache"
    demo.main([
        str(ROOT / "fixtures" / "01-clean-table-ugx.md"),
        "--json", "--run-log", str(log), "--cache-dir", str(cache),
    ])
    capsys.readouterr()
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(rows) == 1
    assert any(cache.iterdir())
