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
import tomllib
from dataclasses import dataclass
from pathlib import Path

APP_DIR_NAME = "fbox"
CONFIG_FILE_NAME = "config.toml"
STATE_FILE_NAME = "containers.json"
DEFAULT_IMAGE = "ubuntu:24.04"
DEFAULT_SHELL = "/bin/bash"
DEFAULT_EDITOR = "code --wait"
DEFAULT_CONTAINER_PREFIX = "fbox"
EXAMPLE_CONFIG_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "fbox.example.toml"
)


@dataclass(slots=True)
class AppConfig:
    default_image: str = DEFAULT_IMAGE
    default_shell: str = DEFAULT_SHELL
    default_network: str = "bridge"
    allow_all_gpus: bool = True
    root_mode: str = "root"
    extra_mounts_readonly: bool = True
    workspace_readonly: bool = False
    container_tmpfs_size: str = ""
    editor_command: str = ""
    install_wrapper_path: str = "~/.local/bin/fbox"

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


def load_config(config_path: Path | None = None) -> AppConfig:
    path = config_path or get_config_file()
    if not path.exists():
        return AppConfig()
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    return AppConfig(
        default_image=str(payload.get("default_image", DEFAULT_IMAGE)),
        default_shell=str(payload.get("default_shell", DEFAULT_SHELL)),
        default_network=str(payload.get("default_network", "bridge")),
        allow_all_gpus=bool(payload.get("allow_all_gpus", True)),
        root_mode=str(payload.get("root_mode", "root")),
        extra_mounts_readonly=bool(payload.get("extra_mounts_readonly", True)),
        workspace_readonly=bool(payload.get("workspace_readonly", False)),
        container_tmpfs_size=str(payload.get("container_tmpfs_size", "")),
        editor_command=str(payload.get("editor_command", "")),
        install_wrapper_path=str(
            payload.get("install_wrapper_path", "~/.local/bin/fbox")
        ),
    )


def resolve_editor_command(config: AppConfig) -> str:
    if config.editor_command:
        return config.editor_command
    return os.environ.get("VISUAL") or os.environ.get("EDITOR") or DEFAULT_EDITOR
