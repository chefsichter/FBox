"""
Status Views - Render debug and container listing output without side effects

Architecture:
    ┌─────────────────────────────────────────┐
    │  status_views.py                        │
    │  ┌───────────────────────────────────┐  │
    │  │  Debug report                    │  │
    │  │  → config, paths, docker, state  │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Container list                  │  │
    │  │  → known fbox containers         │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from fbox.cli.status_views import print_debug_report

    print_debug_report(store, config)
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fbox.config.settings import (
    EXAMPLE_CONFIG_PATH,
    AppConfig,
    get_config_file,
    get_state_file,
)
from fbox.containers.docker_runtime import container_exists, container_is_running
from fbox.state.container_state_store import ContainerStateStore


def print_debug_report(
    store: ContainerStateStore,
    config: AppConfig,
    target: str | None,
) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    config_path = get_config_file()
    state_path = get_state_file()
    wrapper_path = Path(config.install_wrapper_path).expanduser()
    docker_binary = shutil.which("docker")
    print("fbox debug")
    print(f"cwd: {Path.cwd().resolve()}")
    print(f"repo_root: {repo_root}")
    print(f"target_arg: {target or '<none>'}")
    print(f"config_file: {config_path}")
    print(f"config_exists: {config_path.exists()}")
    print(f"config_example: {EXAMPLE_CONFIG_PATH}")
    print(f"state_file: {state_path}")
    print(f"state_exists: {state_path.exists()}")
    print(f"wrapper_path: {wrapper_path}")
    print(f"wrapper_exists: {wrapper_path.exists()}")
    print(f"repo_venv: {repo_root / '.venv'}")
    print(f"repo_venv_exists: {(repo_root / '.venv').exists()}")
    print(f"docker_binary: {docker_binary or '<not found>'}")
    print("config_values:")
    print(f"  default_image: {config.default_image}")
    print(f"  default_shell: {config.default_shell}")
    print(f"  default_network: {config.default_network}")
    print(f"  gpu_vendor: {config.gpu_vendor}")
    print(f"  root_mode: {config.root_mode}")
    print(f"  extra_mounts_readonly: {config.extra_mounts_readonly}")
    print(f"  workspace_readonly: {config.workspace_readonly}")
    print(f"  container_tmpfs_size: {config.container_tmpfs_size or '<unlimited>'}")
    print(f"  editor_command: {config.editor_command or '<default>'}")
    records = store.load()
    print(f"state_records: {len(records)}")
    for record in sorted(records, key=lambda item: item.name):
        exists = container_exists(record.name) if docker_binary else False
        running = container_is_running(record.name) if exists else False
        print(
            "  "
            f"{record.name}: exists={exists} running={running} "
            f"project_path={record.project_path}"
        )


def print_container_list(store: ContainerStateStore) -> None:
    records = sorted(store.load(), key=lambda item: item.name)
    if not records:
        print("Keine gespeicherten fbox-Container gefunden.")
        return
    print("NAME\tRUNNING\tIMAGE\tPROJECT_PATH")
    for record in records:
        exists = container_exists(record.name)
        running = container_is_running(record.name) if exists else False
        print(
            f"{record.name}\t{str(running).lower()}\t"
            f"{record.image}\t{record.project_path}"
        )
