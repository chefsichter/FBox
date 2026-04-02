"""
Settings - Load and resolve global fbox configuration and filesystem paths

Architecture:
    ┌─────────────────────────────────────────┐
    │  settings.py                            │
    │  ┌───────────────────────────────────┐  │
    │  │  AppConfig defaults              │  │
    │  │  → image, GPU, mounts, shell     │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  XDG path resolution             │  │
    │  │  → config.toml, state JSON       │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  TOML loading                     │  │
    │  │  → AppConfig instance             │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from fbox.config.settings import load_config

    config = load_config()
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

APP_DIR_NAME = "fbox"
CONFIG_FILE_NAME = "config.toml"
STATE_FILE_NAME = "containers.json"
DEFAULT_IMAGE = "ubuntu:24.04"
DEFAULT_SHELL = "/bin/bash"
DEFAULT_EDITOR = "code --wait"
DEFAULT_CONTAINER_PREFIX = "fbox"
DEFAULT_PROFILE_KEY = "default_profile"
DEFAULT_WRAPPER_PATH = (
    "~/.local/bin/fbox.cmd" if sys.platform == "win32" else "~/.local/bin/fbox"
)
EXAMPLE_CONFIG_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "fbox.example.toml"
)


@dataclass(slots=True)
class AppConfig:
    default_image: str = DEFAULT_IMAGE
    default_shell: str = DEFAULT_SHELL
    default_network: str = "bridge"
    gpu_vendor: str = "none"
    root_mode: str = "root"
    extra_mounts_readonly: bool = True
    workspace_readonly: bool = False
    container_tmpfs_size: str = ""
    build_tmpfs: str = "/build-tmp:rw,exec,nosuid"
    memory_limit: str = ""
    pids_limit: int = 0
    extra_flags: list = field(default_factory=list)
    editor_command: str = ""
    install_wrapper_path: str = field(default_factory=lambda: DEFAULT_WRAPPER_PATH)

    @property
    def run_as_root(self) -> bool:
        return self.root_mode == "root"


def get_config_file() -> Path:
    return get_xdg_config_home() / APP_DIR_NAME / CONFIG_FILE_NAME


def get_state_file() -> Path:
    return get_xdg_state_home() / APP_DIR_NAME / STATE_FILE_NAME


def get_xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))


def get_xdg_state_home() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))


def _config_from_dict(payload: dict) -> AppConfig:
    """Build an AppConfig from a flat dict, using dataclass defaults for missing."""
    defaults = AppConfig()
    return AppConfig(
        default_image=str(payload.get("default_image", defaults.default_image)),
        default_shell=str(payload.get("default_shell", defaults.default_shell)),
        default_network=str(payload.get("default_network", defaults.default_network)),
        gpu_vendor=str(payload.get("gpu_vendor", defaults.gpu_vendor)),
        root_mode=str(payload.get("root_mode", defaults.root_mode)),
        extra_mounts_readonly=bool(
            payload.get("extra_mounts_readonly", defaults.extra_mounts_readonly)
        ),
        workspace_readonly=bool(
            payload.get("workspace_readonly", defaults.workspace_readonly)
        ),
        container_tmpfs_size=str(
            payload.get("container_tmpfs_size", defaults.container_tmpfs_size)
        ),
        build_tmpfs=str(payload.get("build_tmpfs", defaults.build_tmpfs)),
        memory_limit=str(payload.get("memory_limit", defaults.memory_limit)),
        pids_limit=int(payload.get("pids_limit", defaults.pids_limit)),
        extra_flags=list(payload.get("extra_flags", defaults.extra_flags)),
        editor_command=str(payload.get("editor_command", defaults.editor_command)),
        install_wrapper_path=str(
            payload.get("install_wrapper_path", defaults.install_wrapper_path)
        ),
    )


def _apply_overrides(base: AppConfig, overrides: dict) -> AppConfig:
    """Return a new AppConfig with fields from overrides applied on top of base."""
    # Collect current values from base
    base_dict: dict = {}
    for f in fields(base):
        base_dict[f.name] = getattr(base, f.name)
    # Apply overrides
    for key, value in overrides.items():
        if key in base_dict:
            base_dict[key] = value
    return AppConfig(**base_dict)


def load_config(
    config_path: Path | None = None, profile: str | None = None
) -> AppConfig:
    path = config_path or get_config_file()
    if not path.exists():
        return AppConfig()
    with path.open("rb") as handle:
        payload = tomllib.load(handle)

    # Build base config from top-level fields (ignoring profiles and default_profile)
    base_payload = {
        k: v for k, v in payload.items() if k not in ("profiles", DEFAULT_PROFILE_KEY)
    }
    base = _config_from_dict(base_payload)

    # Determine which profile to use
    if profile is None:
        profile = str(payload.get(DEFAULT_PROFILE_KEY, ""))

    # "none" means explicitly no profile
    if not profile or profile == "none":
        return base

    profiles = payload.get("profiles", {})
    if profile not in profiles:
        return base

    overrides = profiles[profile]
    return _apply_overrides(base, overrides)


def resolve_editor_command(config: AppConfig) -> str:
    if config.editor_command:
        return config.editor_command
    return os.environ.get("VISUAL") or os.environ.get("EDITOR") or DEFAULT_EDITOR
