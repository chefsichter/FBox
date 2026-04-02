"""
CLI Main - Main fbox command for config editing and container reuse/creation

Architecture:
    ┌─────────────────────────────────────────┐
    │  main.py                                │
    │  ┌───────────────────────────────────┐  │
    │  │  CLI flags                       │  │
    │  │  → target, --image, --config     │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Resolve existing containers     │  │
    │  │  → by project path or name       │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Create and enter containers     │  │
    │  │  → docker runtime + state store  │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    python -m fbox.cli.main
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fbox.cli.interactive_prompts import prompt_container_name, prompt_extra_mounts
from fbox.config.editing import edit_config, get_config_path
from fbox.config.files import ensure_config_exists
from fbox.config.settings import DEFAULT_IMAGE, AppConfig, load_config
from fbox.containers.docker_runtime import (
    DockerRuntimeError,
    container_exists,
    create_container,
    ensure_started,
    find_container_by_label,
    open_shell,
    require_docker,
)
from fbox.containers.models import ContainerRecord
from fbox.containers.target_resolution import resolve_target, validate_mounts
from fbox.state.container_state_store import ContainerStateStore


def main() -> None:
    args = parse_args()
    store = ContainerStateStore()
    try:
        ensure_config_exists()
        config = load_config()
        flag_exit_code = maybe_handle_config_flags(args, config)
        if flag_exit_code is not None:
            raise SystemExit(flag_exit_code)
        require_docker()
        project_path, container_name = resolve_target(args.target)
        reuse_exit_code = reuse_existing_container(
            store,
            project_path,
            container_name,
            config,
        )
        if reuse_exit_code is not None:
            raise SystemExit(reuse_exit_code)
        if project_path is None:
            raise SystemExit(
                f"Kein bekannter fbox-Container gefunden: {container_name}"
            )
        raise SystemExit(create_new_container(store, project_path, args.image, config))
    except (DockerRuntimeError, ValueError) as error:
        print(f"fbox: {error}", file=sys.stderr)
        raise SystemExit(1) from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="fbox",
        description="Startet oder erstellt eine persistente Docker-Arbeitsbox.",
    )
    parser.add_argument("target", nargs="?", help="Pfad oder bestehender fbox-Name")
    parser.add_argument(
        "--image",
        default=None,
        help="Docker-Image fuer neue Container. Default: ubuntu:24.04",
    )
    parser.add_argument(
        "--config",
        action="store_true",
        help="Oeffnet die globale fbox-Konfiguration im Editor.",
    )
    parser.add_argument(
        "--print-config-path",
        action="store_true",
        help="Gibt den Pfad zur globalen fbox-Konfiguration aus.",
    )
    return parser.parse_args()


def maybe_handle_config_flags(
    args: argparse.Namespace,
    config: AppConfig,
) -> int | None:
    if args.print_config_path:
        print(get_config_path())
        return 0
    if args.config:
        return edit_config(config)
    return None


def reuse_existing_container(
    store: ContainerStateStore,
    project_path: Path | None,
    container_name: str | None,
    config: AppConfig,
) -> int | None:
    if project_path is not None:
        return reuse_by_project_path(store, project_path.resolve(), config)
    if container_name is not None:
        return reuse_by_container_name(store, container_name, config)
    return None


def reuse_by_project_path(
    store: ContainerStateStore,
    project_path: Path,
    config: AppConfig,
) -> int | None:
    record = store.find_by_project_path(project_path)
    if record is not None and not container_exists(record.name):
        store.delete_by_name(record.name)
        record = None
    if record is not None:
        return start_and_open(record.name, config)
    existing_name = find_container_by_label("ch.fbox.project_path", str(project_path))
    if existing_name is None:
        return None
    return start_and_open(existing_name, config)


def reuse_by_container_name(
    store: ContainerStateStore,
    container_name: str,
    config: AppConfig,
) -> int | None:
    record = store.find_by_name(container_name)
    if record is not None and not container_exists(record.name):
        store.delete_by_name(record.name)
        record = None
    if record is not None:
        return start_and_open(record.name, config)
    if container_exists(container_name):
        return start_and_open(container_name, config)
    return None


def create_new_container(
    store: ContainerStateStore,
    project_path: Path,
    image_override: str | None,
    config: AppConfig,
) -> int:
    resolved_path = project_path.resolve()
    container_name = prompt_container_name(resolved_path)
    if container_exists(container_name):
        return start_and_open(container_name, config)
    record = ContainerRecord(
        name=container_name,
        project_path=str(resolved_path),
        image=image_override or config.default_image or DEFAULT_IMAGE,
        container_id=None,
        extra_mounts=validate_mounts(resolved_path, prompt_extra_mounts()),
        extra_mounts_readonly=config.extra_mounts_readonly,
    )
    record.container_id = create_container(record, config)
    store.upsert(record)
    return start_and_open(record.name, config)


def start_and_open(container_name: str, config: AppConfig) -> int:
    ensure_started(container_name)
    return open_shell(container_name, config)
