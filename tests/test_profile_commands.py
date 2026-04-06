"""Tests for fbox.cli.profile_commands."""

from __future__ import annotations

import io
from pathlib import Path

from fbox.cli.profile_commands import (
    _resolve_pid_or_name,
    cmd_profile_edit,
    cmd_profile_ls,
    cmd_profile_new,
    cmd_profile_rm,
    cmd_profile_set_default,
)
from fbox.config.settings import AppConfig


def _write_config(tmp_path: Path, content: str) -> Path:
    cfg = tmp_path / "config.toml"
    cfg.write_text(content.strip() + "\n", encoding="utf-8")
    return cfg


# ---------------------------------------------------------------------------
# _resolve_pid_or_name
# ---------------------------------------------------------------------------


def test_resolve_pid_or_name_by_pid() -> None:
    assert _resolve_pid_or_name(["a", "b", "c"], "2") == "b"


def test_resolve_pid_or_name_by_name() -> None:
    assert _resolve_pid_or_name(["sandbox", "llm"], "llm") == "llm"


def test_resolve_pid_or_name_out_of_range() -> None:
    assert _resolve_pid_or_name(["a"], "5") is None


def test_resolve_pid_or_name_unknown_name() -> None:
    assert _resolve_pid_or_name(["sandbox"], "missing") is None


# ---------------------------------------------------------------------------
# cmd_profile_set_default
# ---------------------------------------------------------------------------


def test_cmd_profile_set_default_by_name(tmp_path: Path, capsys) -> None:
    cfg = _write_config(
        tmp_path,
        """
default_profile = ""

[profiles.sandbox]
default_network = "none"
""",
    )

    result = cmd_profile_set_default(cfg, "sandbox")

    assert result == 0
    assert "sandbox" in capsys.readouterr().out


def test_cmd_profile_set_default_by_pid(tmp_path: Path, capsys) -> None:
    cfg = _write_config(
        tmp_path,
        """
default_profile = ""

[profiles.sandbox]
default_network = "none"
""",
    )

    result = cmd_profile_set_default(cfg, "1")

    assert result == 0


def test_cmd_profile_set_default_clears_with_none(tmp_path: Path, capsys) -> None:
    cfg = _write_config(tmp_path, 'default_profile = "sandbox"\n')

    result = cmd_profile_set_default(cfg, "none")

    assert result == 0
    assert "zurueckgesetzt" in capsys.readouterr().out


def test_cmd_profile_set_default_unknown_returns_1(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, 'default_profile = ""\n')

    result = cmd_profile_set_default(cfg, "nonexistent")

    assert result == 1


# ---------------------------------------------------------------------------
# cmd_profile_new
# ---------------------------------------------------------------------------


def test_cmd_profile_new_creates_profile(tmp_path: Path, monkeypatch, capsys) -> None:
    cfg = _write_config(tmp_path, 'default_profile = ""\n')
    inputs = iter(
        [
            "myprofile",
            "none",
            "bridge",
            "root",
            "none",
            "n",
            "n",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    monkeypatch.setattr(
        "fbox.cli.profile_commands.build_profile_interactively",
        lambda name, base, **kw: {"default_network": "none"},
    )

    result = cmd_profile_new(cfg, AppConfig())

    assert result == 0
    assert "myprofile" in capsys.readouterr().out


def test_cmd_profile_new_empty_name_returns_1(tmp_path: Path, monkeypatch) -> None:
    cfg = _write_config(tmp_path, 'default_profile = ""\n')
    monkeypatch.setattr("builtins.input", lambda _: "")

    result = cmd_profile_new(cfg, AppConfig())

    assert result == 1


def test_cmd_profile_new_duplicate_name_returns_1(tmp_path: Path, monkeypatch) -> None:
    cfg = _write_config(
        tmp_path,
        """
[profiles.sandbox]
default_network = "none"
""",
    )
    monkeypatch.setattr("builtins.input", lambda _: "sandbox")

    result = cmd_profile_new(cfg, AppConfig())

    assert result == 1


def test_cmd_profile_new_eof_returns_1(tmp_path: Path, monkeypatch) -> None:
    cfg = _write_config(tmp_path, 'default_profile = ""\n')
    monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(EOFError))

    result = cmd_profile_new(cfg, AppConfig())

    assert result == 1


# ---------------------------------------------------------------------------
# cmd_profile_edit
# ---------------------------------------------------------------------------


def test_cmd_profile_edit_updates_profile(tmp_path: Path, monkeypatch, capsys) -> None:
    cfg = _write_config(
        tmp_path,
        """
[profiles.sandbox]
default_network = "none"
""",
    )
    monkeypatch.setattr(
        "fbox.cli.profile_commands.build_profile_interactively",
        lambda name, base, **kw: {"default_network": "bridge"},
    )

    result = cmd_profile_edit(cfg, "sandbox", AppConfig())

    assert result == 0
    assert "sandbox" in capsys.readouterr().out


def test_cmd_profile_edit_by_pid(tmp_path: Path, monkeypatch) -> None:
    cfg = _write_config(
        tmp_path,
        """
[profiles.sandbox]
default_network = "none"
""",
    )
    monkeypatch.setattr(
        "fbox.cli.profile_commands.build_profile_interactively",
        lambda name, base, **kw: {},
    )

    result = cmd_profile_edit(cfg, "1", AppConfig())

    assert result == 0


def test_cmd_profile_edit_unknown_returns_1(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, 'default_profile = ""\n')

    result = cmd_profile_edit(cfg, "missing", AppConfig())

    assert result == 1


# ---------------------------------------------------------------------------
# cmd_profile_rm
# ---------------------------------------------------------------------------


def test_cmd_profile_rm_removes_profile(tmp_path: Path, capsys) -> None:
    cfg = _write_config(
        tmp_path,
        """
[profiles.sandbox]
default_network = "none"
""",
    )

    result = cmd_profile_rm(cfg, "sandbox")

    assert result == 0
    assert "sandbox" in capsys.readouterr().out


def test_cmd_profile_rm_by_pid(tmp_path: Path) -> None:
    cfg = _write_config(
        tmp_path,
        """
[profiles.sandbox]
default_network = "none"
""",
    )

    result = cmd_profile_rm(cfg, "1")

    assert result == 0


def test_cmd_profile_rm_unknown_returns_1(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, 'default_profile = ""\n')

    result = cmd_profile_rm(cfg, "missing")

    assert result == 1


# ---------------------------------------------------------------------------
# cmd_profile_ls
# ---------------------------------------------------------------------------


def test_cmd_profile_ls_lists_profiles(tmp_path: Path, monkeypatch, capsys) -> None:
    cfg = _write_config(
        tmp_path,
        """
default_profile = "sandbox"

[profiles.sandbox]
default_network = "none"
""",
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    result = cmd_profile_ls(cfg)

    assert result == 0
    output = capsys.readouterr().out
    assert "sandbox" in output
    assert "*" in output


def test_cmd_profile_ls_shows_default_marker_when_no_profiles(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    cfg = _write_config(tmp_path, 'default_profile = ""\n')
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    result = cmd_profile_ls(cfg)

    assert result == 0
    assert "[0] default" in capsys.readouterr().out
