"""
CLI Main - Main fbox command for config editing and container reuse/creation

Architecture:
    ┌─────────────────────────────────────────┐
    │  main.py                                │
    │  ┌───────────────────────────────────┐  │
    │  │  CLI flags                       │  │
    │  │  → target, --config             │  │
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

from fbox.cli.interactive_prompts import (
    prompt_container_name,
    prompt_extra_mounts,
    prompt_profile_name,
)
from fbox.cli.commit_command import cmd_commit
from fbox.cli.status_views import (
    get_indexed_records,
    print_container_inspect,
    print_container_list,
    print_create_args,
    print_debug_report,
)
from fbox.config.editing import edit_config, get_config_path
from fbox.config.files import ensure_config_exists
from fbox.config.profile_store import get_default_profile_name, get_profile_names
from fbox.config.settings import AppConfig, load_config
from fbox.containers.docker_runtime import (
    DockerRuntimeError,
    build_create_args,
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
        profile = getattr(args, "profile", None)
        config = load_config(profile=profile)
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
        raise SystemExit(create_new_container(store, project_path, profile))
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
            "fbox [PFAD|NAME] [-p PROFIL]\n"
            "       fbox ls | inspect ID | rm ID | commit\n"
            "       fbox profiles ls | default PID | new | edit PID | rm PID"
        ),
        description="Persistente Docker-Arbeitsboxen verwalten.",
        epilog=(
            "Befehle:\n"
            "  fbox [PFAD|NAME]           Container starten oder neu erstellen\n"
            "  fbox ls                    Alle bekannten Container auflisten\n"
            "  fbox inspect ID            Details + exakte Create-Args anzeigen\n"
            "  fbox rm ID                 Container nach ID aus 'fbox ls' loeschen\n"
            "  fbox commit                Container als versioniertes Image sichern\n"
            "  fbox profiles ls           Profile auflisten + Standard anzeigen\n"
            "  fbox profiles default PID  Standard-Profil setzen (none = keins)\n"
            "  fbox profiles new          Neues Profil interaktiv erstellen\n"
            "  fbox profiles edit PID     Bestehendes Profil neu konfigurieren\n"
            "  fbox profiles rm PID       Profil loeschen\n"
            "  fbox pf ...                Kurzform fuer 'profiles'\n"
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
        "-p", "--profile", default=None, metavar="PROFIL",
        help="Benanntes Profil verwenden (none = kein Profil)",
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
    raw.inspect = None
    raw.commit = False
    raw.profile_cmd = None

    if not words:
        pass
    elif words == ["ls"]:
        raw.ls = True
    elif words[0] in {"profile", "profiles", "pf"}:
        sub = words[1:]
        if not sub or sub == ["ls"]:
            raw.profile_cmd = ("ls",)
        elif sub[0] == "default":
            if len(sub) < 2:
                parser.error(f"{words[0]} default: PID fehlt")
            raw.profile_cmd = ("default", sub[1])
        elif sub == ["new"]:
            raw.profile_cmd = ("new",)
        elif sub[0] == "edit":
            if len(sub) < 2:
                parser.error(f"{words[0]} edit: PID fehlt")
            raw.profile_cmd = ("edit", sub[1])
        elif sub[0] == "rm":
            if len(sub) < 2:
                parser.error(f"{words[0]} rm: PID fehlt")
            raw.profile_cmd = ("rm", sub[1])
        else:
            parser.error(f"Unbekannter {words[0]}-Befehl: {' '.join(sub)}")
    elif words[0] in {"rm", "inspect"}:
        cmd = words[0]
        if len(words) < 2:
            parser.error(f"{cmd}: ID fehlt.  Verwendung: fbox {cmd} ID")
        try:
            numeric_id = int(words[1])
        except ValueError:
            parser.error(f"{cmd}: ID muss eine Zahl sein, nicht '{words[1]}'")
        if cmd == "rm":
            raw.rm = numeric_id
        else:
            raw.inspect = numeric_id
    elif words == ["commit"]:
        raw.commit = True
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
    if args.inspect is not None:
        return print_container_inspect(store, args.inspect)
    if getattr(args, "commit", False):
        return cmd_commit(store, get_config_path(), Path.cwd())
    if getattr(args, "profile_cmd", None) is not None:
        return _dispatch_profile_cmd(args.profile_cmd, config)
    return None


def _dispatch_profile_cmd(profile_cmd: tuple[str, ...], config: AppConfig) -> int:
    from fbox.cli.profile_commands import (
        cmd_profile_edit,
        cmd_profile_ls,
        cmd_profile_new,
        cmd_profile_rm,
        cmd_profile_set_default,
    )
    from fbox.config.settings import get_config_file
    config_path = get_config_file()
    verb = profile_cmd[0]
    if verb == "ls":
        return cmd_profile_ls(config_path)
    if verb == "default":
        return cmd_profile_set_default(config_path, profile_cmd[1])
    if verb == "new":
        return cmd_profile_new(config_path, config)
    if verb == "edit":
        return cmd_profile_edit(config_path, profile_cmd[1], config)
    if verb == "rm":
        return cmd_profile_rm(config_path, profile_cmd[1])
    return 1


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
        if record.create_args:
            print_create_args(
                record.create_args,
                "📦 Willkommen zurueck in deiner Box ...",
            )
        return start_and_open(record.name, _resolve_runtime_config(record, config))
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
        if record.create_args:
            print_create_args(
                record.create_args,
                "📦 Willkommen zurueck in deiner Box ...",
            )
        return start_and_open(record.name, _resolve_runtime_config(record, config))
    if container_exists(container_name):
        return start_and_open(container_name, config)
    return None


def _resolve_runtime_config(record: ContainerRecord, fallback: AppConfig) -> AppConfig:
    if not record.profile_name:
        return fallback
    return load_config(profile=record.profile_name)


def _select_config_for_new_container(
    requested_profile: str | None,
) -> tuple[str, AppConfig]:
    if requested_profile is not None:
        normalized = "" if requested_profile == "none" else requested_profile
        return normalized, load_config(profile=requested_profile)
    profile_names = get_profile_names(get_config_path())
    default_profile = get_default_profile_name(get_config_path())
    selected_profile = prompt_profile_name(profile_names, default_profile)
    if not selected_profile:
        return "", load_config(profile="none")
    return selected_profile, load_config(profile=selected_profile)


def create_new_container(
    store: ContainerStateStore,
    project_path: Path,
    requested_profile: str | None,
) -> int:
    resolved_path = project_path.resolve()
    container_name = prompt_container_name(resolved_path)
    if container_exists(container_name):
        return start_and_open(container_name, load_config(profile=requested_profile))
    selected_profile, selected_config = _select_config_for_new_container(
        requested_profile
    )
    record = ContainerRecord(
        name=container_name,
        project_path=str(resolved_path),
        image=selected_config.default_image,
        container_id=None,
        extra_mounts=validate_mounts(
            resolved_path, selected_config.extra_mounts + prompt_extra_mounts()
        ),
        profile_name=selected_profile,
        extra_mounts_readonly=selected_config.extra_mounts_readonly,
    )
    record.create_args = ["docker"] + build_create_args(selected_config, record)
    print_create_args(record.create_args, "🚀 Richte deine neue Box ein ...")
    record.container_id = create_container(record, selected_config)
    store.upsert(record)
    return start_and_open(record.name, selected_config)


def start_and_open(container_name: str, config: AppConfig) -> int:
    ensure_started(container_name)
    return open_shell(container_name, config)


if __name__ == "__main__":
    main()
