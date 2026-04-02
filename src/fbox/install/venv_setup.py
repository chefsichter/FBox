"""
Venv Setup - Create the repo-local virtualenv and global fbox wrapper

Architecture:
    ┌─────────────────────────────────────────┐
    │  venv_setup.py                          │
    │  ┌───────────────────────────────────┐  │
    │  │  Create .venv                    │  │
    │  │  → python -m venv                │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Editable install                │  │
    │  │  → .venv/bin/pip install -e .    │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Wrapper script                  │  │
    │  │  → ~/.local/bin/fbox             │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from fbox.install.venv_setup import install_local_venv

    install_local_venv(repo_root, wrapper_path)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_IS_WINDOWS = sys.platform == "win32"


def install_local_venv(repo_root: Path, wrapper_path: str) -> None:
    venv_path = repo_root / ".venv"
    create_virtualenv(venv_path)
    write_wrapper_script(venv_path, repo_root, Path(wrapper_path).expanduser())


def installation_exists(repo_root: Path, config_path: Path) -> bool:
    local_bin = Path.home().joinpath(".local", "bin")
    return (
        (repo_root / ".venv").exists()
        or config_path.exists()
        or local_bin.joinpath("fbox").exists()
        or local_bin.joinpath("fbox.cmd").exists()
    )


def create_virtualenv(venv_path: Path) -> None:
    if venv_path.exists():
        return
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_path)],
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("Erstellen der lokalen .venv ist fehlgeschlagen.")


def write_wrapper_script(venv_path: Path, repo_root: Path, wrapper_path: Path) -> None:
    if _IS_WINDOWS:
        if wrapper_path.suffix.lower() != ".cmd":
            wrapper_path = wrapper_path.with_suffix(".cmd")
        wrapper_path.parent.mkdir(parents=True, exist_ok=True)
        python_path = venv_path / "Scripts" / "python.exe"
        wrapper_content = "\n".join(
            [
                "@echo off",
                f'set "REPO_ROOT={repo_root}"',
                "if defined PYTHONPATH (",
                '    set "PYTHONPATH=%REPO_ROOT%\\src;%PYTHONPATH%"',
                ") else (",
                '    set "PYTHONPATH=%REPO_ROOT%\\src"',
                ")",
                f'"{python_path}" -m fbox.cli.main %*',
                "",
            ]
        )
        wrapper_path.write_text(wrapper_content, encoding="utf-8")
    else:
        wrapper_path.parent.mkdir(parents=True, exist_ok=True)
        wrapper_content = "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f'REPO_ROOT="{repo_root}"',
                'export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"',
                f'exec "{venv_path / "bin" / "python"}" -m fbox.cli.main "$@"',
                "",
            ]
        )
        wrapper_path.write_text(wrapper_content, encoding="utf-8")
        wrapper_path.chmod(0o755)
