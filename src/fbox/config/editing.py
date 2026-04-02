"""
Editing - Open and locate the active editable fbox configuration file

Architecture:
    ┌─────────────────────────────────────────┐
    │  editing.py                             │
    │  ┌───────────────────────────────────┐  │
    │  │  Ensure config exists            │  │
    │  │  → returns active config path    │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Launch configured editor        │  │
    │  │  → e.g. nano or code --wait      │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from fbox.config.editing import edit_config

    edit_config(config)
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

from .files import ensure_config_exists
from .settings import AppConfig, get_config_file, resolve_editor_command


def get_config_path() -> Path:
    return ensure_config_exists(get_config_file())


def edit_config(config: AppConfig) -> int:
    config_path = get_config_path()
    editor_parts = shlex.split(resolve_editor_command(config), posix=(sys.platform != "win32"))
    completed = subprocess.run(
        [*editor_parts, str(config_path)],
        check=False,
        text=True,
    )
    return completed.returncode
