"""
Config Files - Ensure example-backed config files exist before use

Architecture:
    ┌─────────────────────────────────────────┐
    │  files.py                               │
    │  ┌───────────────────────────────────┐  │
    │  │  Example config path             │  │
    │  │  → repo config/fbox.example.toml │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Config bootstrap                │  │
    │  │  → create ~/.config/fbox file    │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from fbox.config.config_bootstrap import ensure_config_exists

    ensure_config_exists()
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .settings import EXAMPLE_CONFIG_PATH, get_config_file


def ensure_config_exists(config_path: Path | None = None) -> Path:
    target_path = config_path or get_config_file()
    if target_path.exists():
        return target_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(EXAMPLE_CONFIG_PATH, target_path)
    return target_path
