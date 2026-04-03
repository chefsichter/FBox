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
import sys
from pathlib import Path

from fbox.config.profile_store import (
    get_default_profile_name,
    get_profile_names,
    get_profile_overrides,
)
from fbox.config.settings import (
    EXAMPLE_CONFIG_PATH,
    AppConfig,
    get_config_file,
    get_state_file,
)
from fbox.containers.docker_runtime import (
    build_create_args,
    container_exists,
    container_is_running,
)
from fbox.containers.models import ContainerRecord
from fbox.state.container_state_store import ContainerStateStore


def _format_docker_args(args: list[str]) -> str:
    """Group flags with their values; run consecutive non-flag tokens together."""
    groups: list[str] = []
    i = 0
    while i < len(args):
        token = args[i]
        next_is_value = i + 1 < len(args) and not args[i + 1].startswith("-")
        if token.startswith("-") and "=" not in token and next_is_value:
            groups.append(f"{token} {args[i + 1]}")
            i += 2
        elif not token.startswith("-"):
            chunk = [token]
            while i + 1 < len(args) and not args[i + 1].startswith("-"):
                i += 1
                chunk.append(args[i])
            groups.append(" ".join(chunk))
            i += 1
        else:
            groups.append(token)
            i += 1
    return " \\\n    ".join(groups)


def _section(title: str) -> None:
    print(f"\n[{title}]")


def _row(label: str, value: object, width: int = 24) -> None:
    print(f"  {label:<{width}} {value}")


def get_indexed_records(
    store: ContainerStateStore,
) -> list[tuple[int, ContainerRecord]]:
    records = sorted(store.load(), key=lambda item: item.name)
    return list(enumerate(records, start=1))


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

    print("fbox --debug")

    _section("Runtime")
    _row("cwd", Path.cwd().resolve())
    _row("target", target or "<none>")
    _row("docker", docker_binary or "<not found>")

    _section("Paths")
    _row("repo_root", repo_root)
    venv_path = repo_root / ".venv"
    _row("venv", f"{venv_path}  ({'ok' if venv_path.exists() else 'missing'})")
    _row("config", f"{config_path}  ({'ok' if config_path.exists() else 'missing'})")
    _row("config_example", EXAMPLE_CONFIG_PATH)
    _row("state", f"{state_path}  ({'ok' if state_path.exists() else 'missing'})")
    _row("wrapper", f"{wrapper_path}  ({'ok' if wrapper_path.exists() else 'missing'})")

    _section("Config")
    _row("default_image", config.default_image)
    _row("default_shell", config.default_shell)
    _row("default_network", config.default_network)
    _row("gpu_vendor", config.gpu_vendor)
    _row("root_mode", config.root_mode)
    _row("extra_mounts_readonly", config.extra_mounts_readonly)
    _row("workspace_readonly", config.workspace_readonly)
    _row("tmpfs", config.tmpfs or "<deaktiviert>")
    _row("editor_command", config.editor_command or "<default>")

    profile_names = get_profile_names(config_path)
    default_profile = get_default_profile_name(config_path)
    _section(f"Profiles ({len(profile_names)})")
    if not profile_names:
        print("  <none>")
    for name in profile_names:
        marker = " (default)" if name == default_profile else ""
        overrides = get_profile_overrides(config_path, name)
        print(f"  [{name}]{marker}")
        for key, value in overrides.items():
            _row(key, value, width=28)
    if not default_profile:
        _row("default_profile", "<none>", width=28)

    indexed_records = get_indexed_records(store)
    _section(f"Containers ({len(indexed_records)})")
    if not indexed_records:
        print("  <none>")
    for record_id, record in indexed_records:
        exists = container_exists(record.name) if docker_binary else False
        running = container_is_running(record.name) if exists else False
        status = "running" if running else ("stopped" if exists else "missing")
        print(f"  [{record_id}] {record.name}")
        _row("status", status, width=10)
        _row("image", record.image, width=10)
        _row("project", record.project_path, width=10)

    _section("docker create (preview)")
    project_path = Path.cwd().resolve()
    preview_record = ContainerRecord(
        name="<name>",
        project_path=str(project_path),
        image=config.default_image,
        container_id=None,
        extra_mounts=[],
        extra_mounts_readonly=config.extra_mounts_readonly,
    )
    args = ["docker"] + build_create_args(config, preview_record)
    print("  " + _format_docker_args(args))


def print_create_args(args: list[str], heading: str = "docker create") -> None:
    """Gibt die docker-create-Argumente formatiert aus."""
    print(f"\n{heading}")
    print("  " + _format_docker_args(args))
    print()


def print_container_inspect(store: ContainerStateStore, container_id: int) -> int:
    indexed = dict(get_indexed_records(store))
    record = indexed.get(container_id)
    if record is None:
        print(f"fbox: Unbekannte Container-ID: {container_id}", file=sys.stderr)
        return 1
    docker_binary = shutil.which("docker")
    exists = container_exists(record.name) if docker_binary else False
    running = container_is_running(record.name) if exists else False
    status = "running" if running else ("stopped" if exists else "missing")
    print(f"[{container_id}] {record.name}")
    _row("status", status)
    _row("image", record.image)
    _row("project_path", record.project_path)
    _row("container_id", record.container_id or "<unknown>")
    _row("extra_mounts", record.extra_mounts or "<none>")
    _row("extra_mounts_readonly", record.extra_mounts_readonly)
    if record.create_args:
        print("\n  docker create (used):")
        print("    " + _format_docker_args(record.create_args))
    else:
        print("\n  docker create (used): <not recorded>")
    return 0


def print_container_list(store: ContainerStateStore) -> None:
    indexed_records = get_indexed_records(store)
    if not indexed_records:
        print("Keine gespeicherten fbox-Container gefunden.")
        return
    print("ID\tNAME\tRUNNING\tIMAGE\tPROJECT_PATH")
    for record_id, record in indexed_records:
        exists = container_exists(record.name)
        running = container_is_running(record.name) if exists else False
        print(
            f"{record_id}\t{record.name}\t{str(running).lower()}\t"
            f"{record.image}\t{record.project_path}"
        )
