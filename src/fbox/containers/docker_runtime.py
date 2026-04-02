"""
Docker Runtime - Translate fbox config and records into docker commands

Architecture:
    ┌─────────────────────────────────────────┐
    │  docker_runtime.py                      │
    │  ┌───────────────────────────────────┐  │
    │  │  Docker availability             │  │
    │  │  → require_docker()              │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Create/start/exec helpers       │  │
    │  │  → build_create_args()           │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Security and GPU flags          │  │
    │  │  → user, network, tmpfs, gpus    │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from fbox.containers.docker_runtime import build_create_args

    args = build_create_args(config, record)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from fbox.config.settings import DEFAULT_CONTAINER_PREFIX, AppConfig
from fbox.containers.models import ContainerRecord


class DockerRuntimeError(RuntimeError):
    """Raised when docker execution fails."""


def require_docker() -> None:
    if shutil.which("docker") is None:
        raise DockerRuntimeError("docker wurde nicht gefunden.")
    result = subprocess.run(
        ["docker", "info"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise DockerRuntimeError(
            "Docker-Daemon ist nicht erreichbar. "
            "Bitte Docker Desktop starten und sicherstellen, "
            "dass der Linux-Engine aktiv ist."
        )


def sanitize_container_name(raw_name: str) -> str:
    cleaned = []
    for char in raw_name.lower():
        if char.isalnum() or char in {"-", "_", "."}:
            cleaned.append(char)
        else:
            cleaned.append("-")
    collapsed = "".join(cleaned).strip("-")
    return collapsed or DEFAULT_CONTAINER_PREFIX


def container_exists(name: str) -> bool:
    return inspect_container(name) is not None


def container_is_running(name: str) -> bool:
    result = run_docker_command(
        ["container", "inspect", "--format", "{{.State.Running}}", name],
        capture_output=True,
    )
    return result.stdout.strip() == "true"


def find_container_by_label(label: str, value: str) -> str | None:
    result = subprocess.run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label={label}={value}",
            "--format",
            "{{.Names}}",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def create_container(record: ContainerRecord, config: AppConfig) -> str:
    args = build_create_args(config, record)
    result = run_docker_command(args, capture_output=True)
    return result.stdout.strip()


def build_create_args(config: AppConfig, record: ContainerRecord) -> list[str]:
    project_path = Path(record.project_path)
    mounts = build_mount_args(
        project_path=project_path,
        extra_mounts=record.extra_mounts,
        workspace_readonly=config.workspace_readonly,
        extra_mounts_readonly=record.extra_mounts_readonly,
    )
    return [
        "create",
        "--name",
        record.name,
        "--hostname",
        record.name,
        "--label",
        "ch.fbox.managed=true",
        "--label",
        f"ch.fbox.project_path={project_path}",
        "--cap-drop",
        "ALL",
        "--network",
        config.default_network,
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        build_tmpfs_spec(config.container_tmpfs_size),
        *build_build_tmpfs_args(config.build_tmpfs),
        "--workdir",
        "/workspace",
        *build_user_args(config),
        *build_gpu_args(config),
        *build_resource_args(config),
        *config.extra_flags,
        *mounts,
        record.image,
        "sleep",
        "infinity",
    ]


def build_resource_args(config: AppConfig) -> list[str]:
    args = []
    if config.memory_limit:
        args.extend(["--memory", config.memory_limit])
    if config.pids_limit > 0:
        args.extend(["--pids-limit", str(config.pids_limit)])
    return args


def build_build_tmpfs_args(build_tmpfs: str) -> list[str]:
    if not build_tmpfs:
        return []
    return ["--tmpfs", build_tmpfs]


def build_tmpfs_spec(container_tmpfs_size: str) -> str:
    base_spec = "/tmp:rw,noexec,nosuid"
    if not container_tmpfs_size:
        return base_spec
    return f"{base_spec},size={container_tmpfs_size}"


def build_mount_args(
    project_path: Path,
    extra_mounts: list[str],
    workspace_readonly: bool,
    extra_mounts_readonly: bool,
) -> list[str]:
    mounts = [
        "--mount",
        build_mount_spec(project_path, "/workspace", workspace_readonly),
    ]
    for mount_path in extra_mounts:
        resolved = Path(mount_path).resolve()
        mounts.extend(
            [
                "--mount",
                build_mount_spec(
                    resolved,
                    f"/extra/{resolved.name}",
                    extra_mounts_readonly,
                ),
            ]
        )
    return mounts


def build_mount_spec(source: Path, destination: str, readonly: bool) -> str:
    readonly_value = "true" if readonly else "false"
    return (
        f"type=bind,src={source.resolve()},"
        f"dst={destination},readonly={readonly_value}"
    )


def build_user_args(config: AppConfig) -> list[str]:
    if config.run_as_root:
        return []
    if sys.platform == "win32":
        raise DockerRuntimeError(
            "host-user Modus wird auf Windows nicht unterstuetzt. "
            "Bitte root_mode = \"root\" in der Konfiguration setzen."
        )
    return ["--user", f"{os.getuid()}:{os.getgid()}"]


def _resolve_group_id(name: str) -> str:
    """Return the numeric GID for a host group, or the name as fallback."""
    if sys.platform == "win32":
        return name
    import grp
    try:
        return str(grp.getgrnam(name).gr_gid)
    except KeyError:
        return name


def build_gpu_args(config: AppConfig) -> list[str]:
    if config.gpu_vendor == "nvidia":
        return ["--gpus", "all"]
    if config.gpu_vendor == "amd":
        if sys.platform == "win32":
            raise DockerRuntimeError(
                "AMD-GPU-Passthrough (ROCm) wird auf Windows nicht unterstuetzt."
            )
        return [
            "--device=/dev/kfd",
            "--device=/dev/dri",
            "--group-add",
            _resolve_group_id("video"),
            "--group-add",
            _resolve_group_id("render"),
        ]
    return []


def ensure_started(name: str) -> None:
    if not container_is_running(name):
        run_docker_command(["start", name])


def remove_container(name: str) -> None:
    run_docker_command(["rm", "-f", name])


def open_shell(name: str, config: AppConfig) -> int:
    completed = subprocess.run(
        ["docker", "exec", "-it", name, config.default_shell],
        check=False,
        text=True,
    )
    return completed.returncode


def inspect_container(name: str) -> str | None:
    result = subprocess.run(
        ["docker", "container", "inspect", name],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def run_docker_command(
    args: list[str],
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["docker", *args],
        check=False,
        text=True,
        capture_output=capture_output,
    )
    if result.returncode == 0:
        return result
    message = result.stderr.strip() if capture_output else "docker command failed"
    raise DockerRuntimeError(message)
