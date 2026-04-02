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
from fbox.cli.status_views import (
    get_indexed_records,
    print_container_list,
    print_debug_report,
)
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
    remove_container,
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
        flag_exit_code = maybe_handle_config_flags(args, config, store)
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
    except KeyboardInterrupt:
        print("\nAbgebrochen.", file=sys.stderr)
        raise SystemExit(130)


def parse_args() -> argparse.Namespace:
    parser = _build_parser()
    raw = parser.parse_args()
    return _resolve_positionals(parser, raw)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fbox",
        usage=(
            "fbox [PFAD|NAME] [-i IMAGE]\n"
            "       fbox ls\n"
            "       fbox rm ID"
        ),
        description="Persistente Docker-Arbeitsboxen verwalten.",
        epilog=(
            "Befehle:\n"
            "  fbox [PFAD|NAME]      Container starten oder neu erstellen\n"
            "  fbox ls               Alle bekannten Container auflisten\n"
            "  fbox rm ID            Container nach ID aus 'fbox ls' loeschen\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument("words", nargs="*", help=argparse.SUPPRESS)
    opts = parser.add_argument_group("Optionen")
    opts.add_argument(
        "-h", "--help", action="help", default=argparse.SUPPRESS,
        help="Diese Hilfe anzeigen",
    )
    opts.add_argument(
        "-i", "--image", default=None, metavar="IMAGE",
        help="Docker-Image fuer neue Container (default: ubuntu:24.04)",
    )
    opts.add_argument(
        "-c", "--config", action="store_true",
        help="Konfiguration im Editor oeffnen",
    )
    opts.add_argument(
        "-d", "--debug", action="store_true",
        help="Diagnose-Informationen anzeigen",
    )
    opts.add_argument("--print-config-path", action="store_true",
                      help=argparse.SUPPRESS)
    return parser


def _resolve_positionals(
    parser: argparse.ArgumentParser,
    raw: argparse.Namespace,
) -> argparse.Namespace:
    words: list[str] = raw.words
    del raw.words
    raw.target = None
    raw.ls = False
    raw.rm = None

    if not words:
        pass
    elif words == ["ls"]:
        raw.ls = True
    elif words[0] == "rm":
        if len(words) < 2:
            parser.error("rm: ID fehlt.  Verwendung: fbox rm ID")
        try:
            raw.rm = int(words[1])
        except ValueError:
            parser.error(f"rm: ID muss eine Zahl sein, nicht '{words[1]}'")
    elif len(words) == 1:
        raw.target = words[0]
    else:
        parser.error(f"Unbekannte Argumente: {' '.join(words)}")

    return raw


def maybe_handle_config_flags(
    args: argparse.Namespace,
    config: AppConfig,
    store: ContainerStateStore,
) -> int | None:
    if args.print_config_path:
        print(get_config_path())
        return 0
    if args.config:
        return edit_config(config)
    if args.ls:
        print_container_list(store)
        return 0
    if args.debug:
        print_debug_report(store, config, args.target)
        return 0
    if args.rm is not None:
        return remove_container_by_id(store, args.rm)
    return None


def remove_container_by_id(store: ContainerStateStore, container_id: int) -> int:
    indexed_records = dict(get_indexed_records(store))
    record = indexed_records.get(container_id)
    if record is None:
        print(f"fbox: Unbekannte Container-ID: {container_id}", file=sys.stderr)
        return 1
    if container_exists(record.name):
        remove_container(record.name)
    store.delete_by_name(record.name)
    print(f"Geloescht: [{container_id}] {record.name}")
    return 0


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


def _drop_stale_record(
    store: ContainerStateStore,
    record: ContainerRecord | None,
) -> ContainerRecord | None:
    """Delete the stored record if Docker no longer knows the container."""
    if record is not None and not container_exists(record.name):
        store.delete_by_name(record.name)
        return None
    return record


def reuse_by_project_path(
    store: ContainerStateStore,
    project_path: Path,
    config: AppConfig,
) -> int | None:
    record = _drop_stale_record(store, store.find_by_project_path(project_path))
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
    record = _drop_stale_record(store, store.find_by_name(container_name))
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


if __name__ == "__main__":
    main()
