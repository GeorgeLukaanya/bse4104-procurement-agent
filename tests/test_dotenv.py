"""The .env reader and environment-sourced model configuration."""

from __future__ import annotations

import pytest
from conftest import StubBackend

from procurement_agent import cli
from procurement_agent.config import ExtractionConfig, load_api_key, load_model_name
from procurement_agent.dotenv import load_env_file, parse_env


@pytest.fixture
def quotation(tmp_path):
    path = tmp_path / "quote.md"
    path.write_text("# Quotation\n\nNakawa Building Supplies Ltd\n", encoding="utf-8")
    return path


# --- parsing -----------------------------------------------------------------


def test_parses_plain_assignments():
    assert parse_env("GEMINI_API_KEY=abc123\nMODEL_NAME=gemini-3.1-flash-lite") == {
        "GEMINI_API_KEY": "abc123",
        "MODEL_NAME": "gemini-3.1-flash-lite",
    }


def test_ignores_comments_and_blank_lines():
    text = "# a comment\n\nMODEL_NAME=x\n   \n# another\n"
    assert parse_env(text) == {"MODEL_NAME": "x"}


def test_accepts_the_export_prefix():
    """The same file is often sourced from a shell."""
    assert parse_env("export GEMINI_API_KEY=abc") == {"GEMINI_API_KEY": "abc"}


def test_strips_surrounding_quotes():
    assert parse_env('MODEL_NAME="gemini-3.1-flash-lite"') == {
        "MODEL_NAME": "gemini-3.1-flash-lite"
    }
    assert parse_env("MODEL_NAME='x'") == {"MODEL_NAME": "x"}


def test_a_hash_inside_a_key_is_not_a_comment():
    """A credential may contain '#'; only ' #' starts a trailing comment."""
    assert parse_env("GEMINI_API_KEY=ab#cd") == {"GEMINI_API_KEY": "ab#cd"}
    assert parse_env("GEMINI_API_KEY=abcd # trailing") == {"GEMINI_API_KEY": "abcd"}
    assert parse_env('GEMINI_API_KEY="ab # cd"') == {"GEMINI_API_KEY": "ab # cd"}


def test_a_value_may_contain_an_equals_sign():
    assert parse_env("GEMINI_API_KEY=a=b=c") == {"GEMINI_API_KEY": "a=b=c"}


def test_malformed_lines_are_skipped_not_raised():
    """One stray line must not stop a run that has what it needs."""
    assert parse_env("this is not an assignment\nMODEL_NAME=x\n9INVALID=y") == {
        "MODEL_NAME": "x"
    }


# --- loading -----------------------------------------------------------------


def test_a_missing_file_is_not_an_error(tmp_path):
    """.env is git-ignored and absent on a fresh clone."""
    assert load_env_file(tmp_path / "nope.env", env={}) == {}


def test_the_process_environment_wins_over_the_file(tmp_path):
    """An exported value is a deliberate act for this run; the file is a default."""
    env_file = tmp_path / ".env"
    env_file.write_text("MODEL_NAME=from-file", encoding="utf-8")

    env = {"MODEL_NAME": "from-shell"}
    applied = load_env_file(env_file, env=env)

    assert env["MODEL_NAME"] == "from-shell"
    assert applied == {}


def test_override_lets_the_file_win_when_asked(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("MODEL_NAME=from-file", encoding="utf-8")

    env = {"MODEL_NAME": "from-shell"}
    load_env_file(env_file, env=env, override=True)

    assert env["MODEL_NAME"] == "from-file"


def test_the_file_fills_a_variable_that_is_unset(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=abc123\n", encoding="utf-8")

    env: dict[str, str] = {}
    applied = load_env_file(env_file, env=env)

    assert env["GEMINI_API_KEY"] == "abc123"
    assert applied == {"GEMINI_API_KEY": "abc123"}
    assert load_api_key(env) == "abc123"


def test_an_empty_exported_value_is_treated_as_unset(tmp_path):
    """`GEMINI_API_KEY=` in an exported shell must not mask the file's value."""
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=real", encoding="utf-8")

    env = {"GEMINI_API_KEY": "   "}
    load_env_file(env_file, env=env)

    assert env["GEMINI_API_KEY"] == "real"


# --- model configurability ---------------------------------------------------


def test_load_model_name_returns_none_when_nothing_is_configured():
    """None, not PINNED_MODEL, so a caller can tell 'unset' from 'chosen'."""
    assert load_model_name({}) is None


def test_load_model_name_prefers_model_name_over_gemini_model():
    env = {"MODEL_NAME": "first", "GEMINI_MODEL": "second"}
    assert load_model_name(env) == "first"


def test_an_environment_model_is_still_validated():
    """Configurability must not become a way around the pinning rule."""
    from procurement_agent.config import ConfigError

    from_env = load_model_name({"MODEL_NAME": "gemini-flash-latest"})
    with pytest.raises(ConfigError, match="alias"):
        ExtractionConfig().with_model(from_env)


# --- end to end through the CLI ----------------------------------------------


def _base_args(tmp_path):
    return [
        "--cache-dir", str(tmp_path / "cache"),
        "--run-log", str(tmp_path / "runs.jsonl"),
    ]


def test_cli_reads_the_model_from_an_env_file(tmp_path, quotation, capsys):
    env_file = tmp_path / ".env"
    env_file.write_text("MODEL_NAME=gemini-3.1-flash\n", encoding="utf-8")
    backend = StubBackend()

    cli.main(
        [str(quotation), *_base_args(tmp_path), "--env-file", str(env_file)],
        backend=backend,
    )

    assert backend.calls[0]["config"].model == "gemini-3.1-flash"


def test_the_model_flag_beats_the_env_file(tmp_path, quotation, capsys):
    env_file = tmp_path / ".env"
    env_file.write_text("MODEL_NAME=from-file-model\n", encoding="utf-8")
    backend = StubBackend()

    cli.main(
        [
            str(quotation),
            *_base_args(tmp_path),
            "--env-file", str(env_file),
            "--model", "gemini-3.1-flash",
        ],
        backend=backend,
    )

    assert backend.calls[0]["config"].model == "gemini-3.1-flash"


def test_no_env_file_ignores_the_file_entirely(tmp_path, quotation, capsys):
    env_file = tmp_path / ".env"
    env_file.write_text("MODEL_NAME=from-file-model\n", encoding="utf-8")
    backend = StubBackend()

    cli.main(
        [
            str(quotation),
            *_base_args(tmp_path),
            "--env-file", str(env_file),
            "--no-env-file",
        ],
        backend=backend,
    )

    assert backend.calls[0]["config"].model == "gemini-3.1-flash-lite"


def test_an_alias_in_the_env_file_is_rejected(tmp_path, quotation, capsys):
    """The alias rule applies whatever route the model string arrives by."""
    env_file = tmp_path / ".env"
    env_file.write_text("MODEL_NAME=gemini-flash-latest\n", encoding="utf-8")

    code = cli.main(
        [str(quotation), *_base_args(tmp_path), "--env-file", str(env_file)],
        backend=StubBackend(),
    )

    assert code == cli.EXIT_USAGE
    assert "alias" in capsys.readouterr().err


def test_the_env_file_model_reaches_the_fingerprint(tmp_path, quotation, capsys):
    """A model chosen in .env must be recorded, not just used."""
    import json

    env_file = tmp_path / ".env"
    env_file.write_text("MODEL_NAME=gemini-3.1-flash\n", encoding="utf-8")

    cli.main(
        [str(quotation), "--json", *_base_args(tmp_path), "--env-file", str(env_file)],
        backend=StubBackend(),
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["results"][0]["config_fingerprint"]["model"] == "gemini-3.1-flash"


def test_the_api_key_from_an_env_file_never_reaches_the_output(
    tmp_path, quotation, capsys
):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_API_KEY=sk-secret-value-9999\nMODEL_NAME=gemini-3.1-flash\n",
        encoding="utf-8",
    )

    cli.main(
        [str(quotation), "--json", *_base_args(tmp_path), "--env-file", str(env_file)],
        backend=StubBackend(),
    )

    captured = capsys.readouterr()
    assert "sk-secret-value-9999" not in captured.out
    assert "sk-secret-value-9999" not in captured.err
    assert "sk-secret-value-9999" not in (tmp_path / "runs.jsonl").read_text()
