"""Tests for named profile system: settings, profile_store, docker_runtime, cli."""

from __future__ import annotations

import argparse
from pathlib import Path

from fbox.config.profile_store import (
    delete_profile,
    get_default_profile_name,
    get_profile_names,
    get_profile_overrides,
    render_full_config,
    set_default_profile,
    upsert_profile,
)
from fbox.config.settings import (
    AppConfig,
    _config_from_dict,
    apply_overrides,
    load_config,
)
from fbox.containers.docker_runtime import build_resource_args

# ---------------------------------------------------------------------------
# settings.py tests
# ---------------------------------------------------------------------------


class TestConfigFromDict:
    def test_uses_defaults_for_missing_keys(self) -> None:
        config = _config_from_dict({})
        assert config.default_image == "ubuntu:24.04"
        assert config.memory_limit == ""
        assert config.pids_limit == 0

    def test_reads_provided_values(self) -> None:
        config = _config_from_dict({"memory_limit": "8g", "pids_limit": 256})
        assert config.memory_limit == "8g"
        assert config.pids_limit == 256

    def test_reads_all_base_fields(self) -> None:
        config = _config_from_dict(
            {
                "default_image": "alpine:3",
                "default_shell": "/bin/sh",
                "default_network": "none",
                "gpu_vendor": "nvidia",
                "root_mode": "host-user",
                "extra_mounts_readonly": False,
                "workspace_readonly": True,
                "tmpfs": "/tmp:rw,noexec,nosuid,size=512m",
                "memory_limit": "4g",
                "pids_limit": 100,
                "editor_command": "vim",
                "install_wrapper_path": "/usr/local/bin/fbox",
            }
        )
        assert config.default_image == "alpine:3"
        assert config.gpu_vendor == "nvidia"
        assert config.workspace_readonly is True
        assert config.memory_limit == "4g"
        assert config.pids_limit == 100


class TestApplyOverrides:
    def test_overrides_specific_fields(self) -> None:
        base = AppConfig(default_network="bridge", memory_limit="")
        result = apply_overrides(
            base, {"default_network": "none", "memory_limit": "4g"}
        )
        assert result.default_network == "none"
        assert result.memory_limit == "4g"

    def test_non_overridden_fields_stay_same(self) -> None:
        base = AppConfig(default_image="alpine:3", gpu_vendor="amd")
        result = apply_overrides(base, {"default_network": "none"})
        assert result.default_image == "alpine:3"
        assert result.gpu_vendor == "amd"

    def test_ignores_unknown_keys(self) -> None:
        base = AppConfig()
        # Unknown keys should not raise errors
        result = apply_overrides(base, {"nonexistent_key": "value"})
        assert result.default_image == base.default_image


class TestLoadConfigWithProfile:
    def _write_config(self, tmp_path: Path, content: str) -> Path:
        cfg = tmp_path / "config.toml"
        cfg.write_text(content, encoding="utf-8")
        return cfg

    def test_loads_base_config_without_profile(self, tmp_path: Path) -> None:
        cfg = self._write_config(
            tmp_path,
            """
default_image = "ubuntu:24.04"
default_network = "bridge"
memory_limit = "2g"
""",
        )
        config = load_config(cfg)
        assert config.default_network == "bridge"
        assert config.memory_limit == "2g"

    def test_loads_named_profile(self, tmp_path: Path) -> None:
        cfg = self._write_config(
            tmp_path,
            """
default_network = "bridge"
memory_limit = "2g"

[profiles.sandbox]
default_network = "none"
memory_limit = "4g"
pids_limit = 512
""",
        )
        config = load_config(cfg, profile="sandbox")
        assert config.default_network == "none"
        assert config.memory_limit == "4g"
        assert config.pids_limit == 512

    def test_profile_inherits_base_fields(self, tmp_path: Path) -> None:
        cfg = self._write_config(
            tmp_path,
            """
default_image = "myimage:latest"
default_network = "bridge"

[profiles.minimal]
default_network = "none"
""",
        )
        config = load_config(cfg, profile="minimal")
        # Overridden
        assert config.default_network == "none"
        # Inherited from base
        assert config.default_image == "myimage:latest"

    def test_uses_default_profile_from_config(self, tmp_path: Path) -> None:
        cfg = self._write_config(
            tmp_path,
            """
default_profile = "sandbox"
default_network = "bridge"

[profiles.sandbox]
default_network = "none"
""",
        )
        config = load_config(cfg)
        assert config.default_network == "none"

    def test_profile_none_skips_default(self, tmp_path: Path) -> None:
        cfg = self._write_config(
            tmp_path,
            """
default_profile = "sandbox"
default_network = "bridge"

[profiles.sandbox]
default_network = "none"
""",
        )
        config = load_config(cfg, profile="none")
        assert config.default_network == "bridge"

    def test_missing_profile_falls_back_to_base(self, tmp_path: Path) -> None:
        cfg = self._write_config(
            tmp_path,
            """
default_network = "host"
""",
        )
        config = load_config(cfg, profile="nonexistent")
        assert config.default_network == "host"

    def test_new_fields_memory_and_pids(self, tmp_path: Path) -> None:
        cfg = self._write_config(
            tmp_path,
            """
memory_limit = "8g"
pids_limit = 1000
""",
        )
        config = load_config(cfg)
        assert config.memory_limit == "8g"
        assert config.pids_limit == 1000


# ---------------------------------------------------------------------------
# profile_store.py tests
# ---------------------------------------------------------------------------


class TestProfileStore:
    def _write_config(self, tmp_path: Path, content: str) -> Path:
        cfg = tmp_path / "config.toml"
        cfg.write_text(content, encoding="utf-8")
        return cfg

    def test_get_profile_names_empty(self, tmp_path: Path) -> None:
        cfg = self._write_config(tmp_path, 'default_image = "ubuntu:24.04"\n')
        assert get_profile_names(cfg) == []

    def test_get_profile_names_with_profiles(self, tmp_path: Path) -> None:
        cfg = self._write_config(
            tmp_path,
            """
[profiles.sandbox]
default_network = "none"

[profiles.llm]
gpu_vendor = "amd"
""",
        )
        names = get_profile_names(cfg)
        assert "sandbox" in names
        assert "llm" in names

    def test_get_default_profile_name_empty(self, tmp_path: Path) -> None:
        cfg = self._write_config(tmp_path, 'default_image = "ubuntu:24.04"\n')
        assert get_default_profile_name(cfg) == ""

    def test_get_default_profile_name_set(self, tmp_path: Path) -> None:
        cfg = self._write_config(tmp_path, 'default_profile = "sandbox"\n')
        assert get_default_profile_name(cfg) == "sandbox"

    def test_get_profile_overrides(self, tmp_path: Path) -> None:
        cfg = self._write_config(
            tmp_path,
            """
[profiles.sandbox]
default_network = "none"
memory_limit = "4g"
""",
        )
        overrides = get_profile_overrides(cfg, "sandbox")
        assert overrides["default_network"] == "none"
        assert overrides["memory_limit"] == "4g"

    def test_get_profile_overrides_missing(self, tmp_path: Path) -> None:
        cfg = self._write_config(tmp_path, 'default_image = "ubuntu:24.04"\n')
        assert get_profile_overrides(cfg, "missing") == {}

    def test_upsert_profile_creates_new(self, tmp_path: Path) -> None:
        cfg = self._write_config(tmp_path, 'default_image = "ubuntu:24.04"\n')
        upsert_profile(cfg, "myprofile", {"default_network": "none"})
        names = get_profile_names(cfg)
        assert "myprofile" in names
        overrides = get_profile_overrides(cfg, "myprofile")
        assert overrides["default_network"] == "none"

    def test_upsert_profile_updates_existing(self, tmp_path: Path) -> None:
        cfg = self._write_config(
            tmp_path,
            """
[profiles.myprofile]
default_network = "bridge"
""",
        )
        upsert_profile(
            cfg, "myprofile", {"default_network": "none", "memory_limit": "8g"}
        )
        overrides = get_profile_overrides(cfg, "myprofile")
        assert overrides["default_network"] == "none"
        assert overrides["memory_limit"] == "8g"

    def test_delete_profile_removes_it(self, tmp_path: Path) -> None:
        cfg = self._write_config(
            tmp_path,
            """
[profiles.sandbox]
default_network = "none"
""",
        )
        delete_profile(cfg, "sandbox")
        assert "sandbox" not in get_profile_names(cfg)

    def test_delete_profile_clears_default_if_matches(self, tmp_path: Path) -> None:
        cfg = self._write_config(
            tmp_path,
            """
default_profile = "sandbox"

[profiles.sandbox]
default_network = "none"
""",
        )
        delete_profile(cfg, "sandbox")
        assert get_default_profile_name(cfg) == ""

    def test_set_default_profile(self, tmp_path: Path) -> None:
        cfg = self._write_config(
            tmp_path,
            """
[profiles.sandbox]
default_network = "none"
""",
        )
        set_default_profile(cfg, "sandbox")
        assert get_default_profile_name(cfg) == "sandbox"

    def test_file_missing_returns_empty(self, tmp_path: Path) -> None:
        cfg = tmp_path / "nonexistent.toml"
        assert get_profile_names(cfg) == []
        assert get_default_profile_name(cfg) == ""


class TestRenderFullConfig:
    def test_renders_default_profile_key(self) -> None:
        result = render_full_config({}, {}, "sandbox")
        assert 'default_profile = "sandbox"' in result

    def test_renders_empty_default_profile(self) -> None:
        result = render_full_config({}, {}, "")
        assert 'default_profile = ""' in result

    def test_renders_base_values(self) -> None:
        result = render_full_config(
            {"default_network": "none", "pids_limit": 512}, {}, ""
        )
        assert 'default_network = "none"' in result
        assert "pids_limit = 512" in result

    def test_renders_profile_sections(self) -> None:
        result = render_full_config(
            {},
            {"sandbox": {"default_network": "none", "workspace_readonly": True}},
            "",
        )
        assert "[profiles.sandbox]" in result
        assert 'default_network = "none"' in result
        assert "workspace_readonly = true" in result

    def test_round_trips_through_tomllib(self, tmp_path: Path) -> None:
        import tomllib

        content = render_full_config(
            {"default_image": "alpine:3", "pids_limit": 100},
            {"sandbox": {"default_network": "none"}},
            "sandbox",
        )
        cfg = tmp_path / "config.toml"
        cfg.write_text(content, encoding="utf-8")
        with cfg.open("rb") as fh:
            payload = tomllib.load(fh)
        assert payload["default_profile"] == "sandbox"
        assert payload["default_image"] == "alpine:3"
        assert payload["pids_limit"] == 100
        assert payload["profiles"]["sandbox"]["default_network"] == "none"


# ---------------------------------------------------------------------------
# docker_runtime.py tests
# ---------------------------------------------------------------------------


class TestBuildResourceArgs:
    def test_empty_when_no_limits(self) -> None:
        config = AppConfig(memory_limit="", pids_limit=0)
        assert build_resource_args(config) == []

    def test_memory_limit_added(self) -> None:
        config = AppConfig(memory_limit="4g", pids_limit=0)
        args = build_resource_args(config)
        assert "--memory" in args
        assert "4g" in args

    def test_pids_limit_added(self) -> None:
        config = AppConfig(memory_limit="", pids_limit=512)
        args = build_resource_args(config)
        assert "--pids-limit" in args
        assert "512" in args

    def test_both_limits_added(self) -> None:
        config = AppConfig(memory_limit="8g", pids_limit=1024)
        args = build_resource_args(config)
        assert "--memory" in args
        assert "8g" in args
        assert "--pids-limit" in args
        assert "1024" in args


# ---------------------------------------------------------------------------
# CLI parsing tests for profile subcommands
# ---------------------------------------------------------------------------


class TestProfileSubcommandParsing:
    def _parse(self, argv: list[str]) -> argparse.Namespace:
        import sys

        from fbox.cli.main import _build_parser, _resolve_positionals

        old = sys.argv
        sys.argv = ["fbox"] + argv
        try:
            parser = _build_parser()
            raw = parser.parse_args()
            return _resolve_positionals(parser, raw)
        finally:
            sys.argv = old

    def test_profile_ls(self) -> None:
        args = self._parse(["profile", "ls"])
        assert args.profile_cmd == ("ls",)

    def test_profile_bare(self) -> None:
        args = self._parse(["profile"])
        assert args.profile_cmd == ("ls",)

    def test_profiles_bare(self) -> None:
        args = self._parse(["profiles"])
        assert args.profile_cmd == ("ls",)

    def test_pf_bare(self) -> None:
        args = self._parse(["pf"])
        assert args.profile_cmd == ("ls",)

    def test_profile_default(self) -> None:
        args = self._parse(["profile", "default", "sandbox"])
        assert args.profile_cmd == ("default", "sandbox")

    def test_profiles_default(self) -> None:
        args = self._parse(["profiles", "default", "sandbox"])
        assert args.profile_cmd == ("default", "sandbox")

    def test_profile_new(self) -> None:
        args = self._parse(["profile", "new"])
        assert args.profile_cmd == ("new",)

    def test_profile_edit(self) -> None:
        args = self._parse(["profile", "edit", "llm"])
        assert args.profile_cmd == ("edit", "llm")

    def test_profile_rm(self) -> None:
        args = self._parse(["profile", "rm", "sandbox"])
        assert args.profile_cmd == ("rm", "sandbox")

    def test_commit_command(self) -> None:
        args = self._parse(["commit"])
        assert args.commit is True

    def test_dash_p_sets_profile(self) -> None:
        args = self._parse(["/tmp/project", "-p", "llm"])
        assert args.profile == "llm"
        assert args.target == "/tmp/project"

    def test_no_profile_flag_defaults_to_none(self) -> None:
        args = self._parse(["/tmp/project"])
        assert args.profile is None
