"""
Uninstall Main - Remove the local runtime, wrapper, config, state, and containers

Architecture:
    ┌─────────────────────────────────────────┐
    │  uninstall_main.py                      │
    │  ┌───────────────────────────────────┐  │
    │  │  Ask uninstall scope             │  │
    │  │  → containers yes/no             │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Remove install artifacts        │  │
    │  │  → wrapper, config, .venv        │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Remove managed containers       │  │
    │  │  → docker rm -f by label         │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    python -m fbox.install.uninstall_main
"""

from __future__ import annotations

import sys
from pathlib import Path

from fbox.config.files import ensure_config_exists
from fbox.config.settings import AppConfig, get_config_file, load_config
from fbox.install.cleanup import uninstall_fbox
from fbox.install.interactive_configurator import ask_bool


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    config = load_existing_config()
    wrapper_path = Path(config.install_wrapper_path).expanduser()
    remove_containers = ask_bool(
        "Auch alle von fbox verwalteten Container loeschen",
        True,
    )
    uninstall_fbox(repo_root, wrapper_path, remove_containers)
    print("fbox wurde entfernt.")


def load_existing_config() -> AppConfig:
    config_path = get_config_file()
    if config_path.exists():
        return load_config(config_path)
    ensure_config_exists(config_path)
    config = load_config(config_path)
    config_path.unlink(missing_ok=True)
    return config


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(f"fbox-uninstall: {error}", file=sys.stderr)
        raise SystemExit(1) from error
