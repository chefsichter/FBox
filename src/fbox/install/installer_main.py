"""
Installer Main - Bootstrap config, local venv, and the global fbox wrapper

Architecture:
    ┌─────────────────────────────────────────┐
    │  installer_main.py                      │
    │  ┌───────────────────────────────────┐  │
    │  │  Ask installer questions         │  │
    │  │  → config.toml                   │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Create .venv + editable install │  │
    │  │  → repo-local runtime            │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Install wrapper                 │  │
    │  │  → callable as `fbox` anywhere   │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    python -m fbox.install.installer_main
"""

from __future__ import annotations

import sys
from pathlib import Path

from fbox.config.files import ensure_config_exists
from fbox.config.settings import get_config_file
from fbox.install.interactive_configurator import build_config_interactively
from fbox.install.venv_setup import install_local_venv


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    config_path = get_config_file()
    ensure_config_exists(config_path)
    rendered_config, wrapper_path = build_config_interactively(Path.cwd().resolve())
    write_config(config_path, rendered_config)
    install_local_venv(repo_root, wrapper_path)
    print(f"fbox installiert. Konfiguration: {config_path}")
    print(f"Globaler Starter: {Path(wrapper_path).expanduser()}")
    print("Zum spaeteren Bearbeiten: fbox --config")


def write_config(config_path: Path, content: str) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(f"fbox-installer: {error}", file=sys.stderr)
        raise SystemExit(1) from error
