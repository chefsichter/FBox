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
from pathlib import Path

from fbox.config.settings import DEFAULT_CONTAINER_PREFIX, AppConfig
from fbox.containers.models import ContainerRecord


class DockerRuntimeError(RuntimeError):
    """Raised when docker execution fails."""


def require_docker() -> None:
    if shutil.which("docker") is None:
        raise DockerRuntimeError("docker wurde nicht gefunden.")


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
        "--workdir",
        "/workspace",
        *build_user_args(config),
        *build_gpu_args(config),
        *mounts,
        record.image,
        "sleep",
        "infinity",
    ]


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
    return ["--user", f"{os.getuid()}:{os.getgid()}"]


def build_gpu_args(config: AppConfig) -> list[str]:
    if config.gpu_vendor == "nvidia":
        return ["--gpus", "all"]
    if config.gpu_vendor == "amd":
        return [
            "--device=/dev/kfd",
            "--device=/dev/dri",
            "--group-add",
            "video",
            "--group-add",
            "render",
        ]
    return []


def ensure_started(name: str) -> None:
    if not container_is_running(name):
        run_docker_command(["start", name])


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
