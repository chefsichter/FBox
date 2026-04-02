from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import DEFAULT_IMAGE
from .docker_runtime import (
    DockerRuntimeError,
    container_exists,
    create_container,
    ensure_started,
    find_container_by_label,
    open_shell,
    require_docker,
)
from .models import ContainerRecord
from .path_resolution import resolve_target, validate_mounts
from .prompts import prompt_container_name, prompt_extra_mounts
from .state_store import StateStore


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
    return parser.parse_args()


def reuse_existing_record(store: StateStore, project_path: Path | None, name: str | None) -> int | None:
    record = None
    if project_path is not None:
        record = store.find_by_project_path(project_path.resolve())
        if record is not None and not container_exists(record.name):
            store.delete_by_name(record.name)
            record = None
        if record is None:
            existing_name = find_container_by_label(
                "ch.fbox.project_path",
                str(project_path.resolve()),
            )
            if existing_name:
                ensure_started(existing_name)
                return open_shell(existing_name)
    elif name is not None:
        record = store.find_by_name(name)
        if record is not None and not container_exists(record.name):
            store.delete_by_name(record.name)
            record = None
        if record is None and container_exists(name):
            ensure_started(name)
            return open_shell(name)
    if record is None:
        return None
    ensure_started(record.name)
    return open_shell(record.name)


def create_new_record(store: StateStore, project_path: Path, image_override: str | None) -> int:
    resolved_path = project_path.resolve()
    container_name = prompt_container_name(resolved_path)
    if container_exists(container_name):
        ensure_started(container_name)
        return open_shell(container_name)
    extra_mounts = validate_mounts(resolved_path, prompt_extra_mounts())
    image = image_override or DEFAULT_IMAGE
    record = ContainerRecord(
        name=container_name,
        project_path=str(resolved_path),
        image=image,
        container_id=None,
        extra_mounts=extra_mounts,
    )
    record.container_id = create_container(record)
    store.upsert(record)
    ensure_started(record.name)
    return open_shell(record.name)


def main() -> None:
    args = parse_args()
    store = StateStore()
    try:
        require_docker()
        project_path, container_name = resolve_target(args.target)
        reuse_exit_code = reuse_existing_record(store, project_path, container_name)
        if reuse_exit_code is not None:
            raise SystemExit(reuse_exit_code)
        if project_path is None:
            raise SystemExit(f"Kein bekannter fbox-Container gefunden: {container_name}")
        raise SystemExit(create_new_record(store, project_path, args.image))
    except (DockerRuntimeError, ValueError) as error:
        print(f"fbox: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
