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
import pwd
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from fbox.config.settings import DEFAULT_CONTAINER_PREFIX, AppConfig
from fbox.containers.container_record import ContainerRecord


class DockerRuntimeError(RuntimeError):
    """Raised when docker execution fails."""


@dataclass(slots=True)
class HostUserContext:
    name: str
    uid: int
    gid: int
    home: str


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


def commit_container(name: str, image: str, description: str = "") -> None:
    args = ["commit"]
    if description:
        args += ["-m", description]
    args += [name, image]
    run_docker_command(args, capture_output=True)


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
        *build_tmpfs_args(config.tmpfs),
        "--workdir",
        "/workspace",
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


def build_tmpfs_args(tmpfs: str) -> list[str]:
    if not tmpfs:
        return []
    return ["--tmpfs", tmpfs]


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
    for mount_entry in extra_mounts:
        parts = mount_entry.split(":", 2)
        source = Path(parts[0]).expanduser()
        destination = str(Path(parts[1]).expanduser()) if len(parts) >= 2 else f"/extra/{source.name}"
        mode = parts[2] if len(parts) == 3 else ""
        readonly = (mode == "ro") if mode in ("rw", "ro") else extra_mounts_readonly
        mounts.extend(
            [
                "--mount",
                build_mount_spec(source, destination, readonly),
            ]
        )
    return mounts


def build_mount_spec(source: Path, destination: str, readonly: bool) -> str:
    readonly_value = "true" if readonly else "false"
    return (
        f"type=bind,src={source.resolve()},"
        f"dst={destination},readonly={readonly_value}"
    )


def resolve_host_user_context() -> HostUserContext:
    if sys.platform == "win32":
        raise DockerRuntimeError(
            "host-user Modus wird auf Windows nicht unterstuetzt. "
            'Bitte root_mode = "root" in der Konfiguration setzen.'
        )
    entry = pwd.getpwuid(os.getuid())
    return HostUserContext(
        name=entry.pw_name,
        uid=os.getuid(),
        gid=os.getgid(),
        home=entry.pw_dir,
    )


def build_host_user_setup_script(host_user: HostUserContext) -> str:
    return f"""set -euo pipefail

username={shlex.quote(host_user.name)}
uid={shlex.quote(str(host_user.uid))}
gid={shlex.quote(str(host_user.gid))}
home={shlex.quote(host_user.home)}

if ! getent group "$gid" >/dev/null 2>&1; then
    if getent group "$username" >/dev/null 2>&1; then
        groupmod -g "$gid" "$username"
    else
        groupadd -g "$gid" "$username"
    fi
fi

current_user="$(getent passwd "$uid" | cut -d: -f1 || true)"
if [ -n "$current_user" ] \
    && [ "$current_user" != "$username" ] \
    && ! id -u "$username" >/dev/null 2>&1; then
    usermod -l "$username" "$current_user"
    if getent group "$current_user" >/dev/null 2>&1; then
        groupmod -n "$username" "$current_user" || true
    fi
fi

if id -u "$username" >/dev/null 2>&1; then
    [ "$(id -u "$username")" = "$uid" ] || usermod -u "$uid" "$username"
    [ "$(id -g "$username")" = "$gid" ] || usermod -g "$gid" "$username"
    current_home="$(getent passwd "$username" | cut -d: -f6)"
    [ "$current_home" = "$home" ] || usermod -d "$home" "$username"
else
    useradd -m -d "$home" -u "$uid" -g "$gid" -s /bin/bash "$username"
fi

mkdir -p "$home"
chown "$uid:$gid" "$home"

if [ ! -f "$home/.bashrc" ] && [ -d /etc/skel ]; then
    cp -rT /etc/skel "$home"
    chown -R "$uid:$gid" "$home"
fi

install -d -m 0755 /etc/sudoers.d
cat <<EOF >/etc/sudoers.d/fbox-host-user
$username ALL=(ALL:ALL) NOPASSWD:ALL
EOF
chmod 0440 /etc/sudoers.d/fbox-host-user

for group_name in sudo video render; do
    if getent group "$group_name" >/dev/null 2>&1; then
        usermod -aG "$group_name" "$username"
    fi
done
"""


def ensure_host_user_ready(name: str, host_user: HostUserContext) -> None:
    run_docker_command(
        ["exec", name, "/bin/bash", "-lc", build_host_user_setup_script(host_user)],
        capture_output=True,
    )


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
    if config.run_as_root:
        return _run_shell_command(["docker", "exec", "-it", name, config.default_shell])
    host_user = resolve_host_user_context()
    ensure_host_user_ready(name, host_user)
    return _open_host_user_shell(name, config.default_shell, host_user)


def _open_host_user_shell(
    name: str,
    shell: str,
    host_user: HostUserContext,
) -> int:
    return _run_shell_command(
        [
            "docker",
            "exec",
            "-it",
            "--user",
            host_user.name,
            "--workdir",
            "/workspace",
            "-e",
            f"HOME={host_user.home}",
            "-e",
            f"USER={host_user.name}",
            "-e",
            f"LOGNAME={host_user.name}",
            name,
            shell,
        ]
    )


def _run_shell_command(args: list[str]) -> int:
    completed = subprocess.run(args, check=False, text=True)
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


def get_container_image(name: str) -> str:
    result = run_docker_command(
        ["container", "inspect", "--format", "{{.Config.Image}}", name],
        capture_output=True,
    )
    return result.stdout.strip()


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
