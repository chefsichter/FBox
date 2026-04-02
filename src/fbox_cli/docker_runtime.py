from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .config import DEFAULT_CONTAINER_PREFIX, DEFAULT_SHELL
from .models import ContainerRecord


class DockerRuntimeError(RuntimeError):
    """Raised when docker execution fails."""


def require_docker() -> None:
    if shutil.which("docker") is None:
        raise DockerRuntimeError("docker wurde nicht gefunden.")


def run_docker_command(args: list[str], capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    command = ["docker", *args]
    result = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=capture_output,
    )
    if result.returncode != 0:
        message = result.stderr.strip() if capture_output else "docker command failed"
        raise DockerRuntimeError(message)
    return result


def sanitize_container_name(raw_name: str) -> str:
    cleaned = []
    for char in raw_name.lower():
        if char.isalnum():
            cleaned.append(char)
        elif char in {"-", "_", "."}:
            cleaned.append(char)
        else:
            cleaned.append("-")
    collapsed = "".join(cleaned).strip("-")
    return collapsed or DEFAULT_CONTAINER_PREFIX


def container_exists(name: str) -> bool:
    result = subprocess.run(
        ["docker", "container", "inspect", name],
        check=False,
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def container_is_running(name: str) -> bool:
    result = run_docker_command(
        ["container", "inspect", "--format", "{{.State.Running}}", name],
        capture_output=True,
    )
    return result.stdout.strip() == "true"


def find_container_by_label(label: str, value: str) -> str | None:
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"label={label}={value}", "--format", "{{.Names}}"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    container_name = result.stdout.strip()
    return container_name or None


def create_container(record: ContainerRecord) -> str:
    project_path = Path(record.project_path)
    mounts = [
        "--mount",
        f"type=bind,src={project_path},dst=/workspace,readonly=false",
    ]
    for mount_path in record.extra_mounts:
        resolved = Path(mount_path).resolve()
        mounts.extend(
            [
                "--mount",
                f"type=bind,src={resolved},dst=/extra/{resolved.name},readonly=false",
            ]
        )
    args = [
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
        "none",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=512m",
        "--workdir",
        "/workspace",
        *mounts,
        record.image,
        "sleep",
        "infinity",
    ]
    result = run_docker_command(args, capture_output=True)
    return result.stdout.strip()


def ensure_started(name: str) -> None:
    if not container_is_running(name):
        run_docker_command(["start", name])


def open_shell(name: str) -> int:
    completed = subprocess.run(
        ["docker", "exec", "-it", name, DEFAULT_SHELL],
        check=False,
        text=True,
    )
    return completed.returncode
