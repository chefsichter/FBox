"""
Cleanup - Remove local fbox installation artifacts and managed containers

Architecture:
    ┌─────────────────────────────────────────┐
    │  cleanup.py                             │
    │  ┌───────────────────────────────────┐  │
    │  │  Installation artifact cleanup   │  │
    │  │  → wrapper, config, state, .venv │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Docker cleanup                  │  │
    │  │  → remove all managed containers │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from fbox.install.cleanup import uninstall_fbox

    uninstall_fbox(repo_root, Path("~/.local/bin/fbox").expanduser(), True)
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from fbox.config.settings import get_config_file, get_state_file


def uninstall_fbox(
    repo_root: Path,
    wrapper_path: Path,
    remove_containers: bool,
) -> None:
    if remove_containers:
        remove_managed_containers()
    remove_file_if_present(wrapper_path)
    remove_file_if_present(get_config_file())
    remove_file_if_present(get_state_file())
    remove_directory_if_present(repo_root / ".venv")
    remove_empty_parent_directories(wrapper_path.parent)
    remove_empty_parent_directories(get_config_file().parent)
    remove_empty_parent_directories(get_state_file().parent)


def remove_managed_containers() -> None:
    result = subprocess.run(
        [
            "docker",
            "ps",
            "-aq",
            "--filter",
            "label=ch.fbox.managed=true",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return
    container_ids = [
        line.strip() for line in result.stdout.splitlines() if line.strip()
    ]
    if not container_ids:
        return
    subprocess.run(
        ["docker", "rm", "-f", *container_ids],
        check=False,
        text=True,
        capture_output=True,
    )


def remove_file_if_present(path: Path) -> None:
    if path.exists():
        path.unlink()


def remove_directory_if_present(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def remove_empty_parent_directories(path: Path) -> None:
    current = path
    while current.exists() and current != current.parent:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent
