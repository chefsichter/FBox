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

from fbox.config.config_bootstrap import ensure_config_exists
from fbox.config.settings import get_config_file, load_config
from fbox.install.interactive_configurator import (
    build_config_interactively,
    choose_install_action,
)
from fbox.install.uninstall_cleanup import uninstall_fbox
from fbox.install.venv_setup import install_local_venv, installation_exists


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    config_path = get_config_file()
    action = choose_install_action(installation_exists(repo_root, config_path))
    if action == "abort":
        print("Abgebrochen.")
        return
    if action == "uninstall":
        uninstall_existing_installation(repo_root, config_path)
        print("fbox wurde entfernt.")
        return
    rendered_config, wrapper_path = build_config_interactively(Path.cwd().resolve())
    write_config(config_path, rendered_config)
    install_local_venv(repo_root, wrapper_path)
    print(f"fbox installiert. Konfiguration: {config_path}")
    print(f"Globaler Starter: {Path(wrapper_path).expanduser()}")
    print("Zum spaeteren Bearbeiten: fbox --config")


def write_config(config_path: Path, content: str) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8")


def uninstall_existing_installation(repo_root: Path, config_path: Path) -> None:
    wrapper_path = get_wrapper_path(config_path)
    uninstall_fbox(repo_root, wrapper_path, remove_containers=True)


def get_wrapper_path(config_path: Path) -> Path:
    if config_path.exists():
        return Path(load_config(config_path).install_wrapper_path).expanduser()
    ensure_config_exists(config_path)
    config = load_config(config_path)
    config_path.unlink(missing_ok=True)
    return Path(config.install_wrapper_path).expanduser()


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(f"fbox-installer: {error}", file=sys.stderr)
        raise SystemExit(1) from error
