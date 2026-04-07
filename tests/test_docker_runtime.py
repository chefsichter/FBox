from pathlib import Path

from fbox.config.settings import AppConfig
from fbox.containers.container_record import ContainerRecord
from fbox.containers.docker_runtime import (
    build_create_args,
    build_mount_spec,
    build_tmpfs_args,
    open_shell,
)


def test_build_mount_spec_respects_readonly_flag() -> None:
    mount_spec = build_mount_spec(Path("/tmp/project"), "/workspace", True)
    assert mount_spec.endswith("readonly=true")


def test_build_create_args_include_gpu_and_host_user_settings(monkeypatch) -> None:
    monkeypatch.setattr("os.getuid", lambda: 1000)
    monkeypatch.setattr("os.getgid", lambda: 1000)
    config = AppConfig(gpu_vendor="nvidia", root_mode="host-user")
    record = ContainerRecord(
        name="fbox-demo",
        project_path="/tmp/demo",
        image="ubuntu:24.04",
        container_id=None,
        extra_mounts=["/tmp/data"],
    )

    args = build_create_args(config, record)

    assert "--gpus" in args
    assert "all" in args
    assert "--user" not in args
    assert "--security-opt" not in args
    assert any("/extra/data" in item for item in args)


def test_build_tmpfs_args_returns_empty_when_disabled() -> None:
    assert build_tmpfs_args("") == []


def test_build_tmpfs_args_returns_flag_with_spec() -> None:
    assert build_tmpfs_args("/tmp:rw,exec,nosuid") == ["--tmpfs", "/tmp:rw,exec,nosuid"]


def test_open_shell_maps_host_user_and_runs_shell(monkeypatch) -> None:
    calls: list[list[str]] = []

    class _PwEntry:
        pw_name = "chefsichter"
        pw_dir = "/home/chefsichter"

    monkeypatch.setattr("os.getuid", lambda: 1000)
    monkeypatch.setattr("os.getgid", lambda: 1000)
    monkeypatch.setattr("pwd.getpwuid", lambda uid: _PwEntry())

    def _fake_run(args, check=False, text=True, capture_output=False):
        calls.append(args)
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr("subprocess.run", _fake_run)

    exit_code = open_shell(
        "fbox-demo",
        AppConfig(root_mode="host-user", default_shell="/bin/zsh"),
    )

    assert exit_code == 0
    assert calls[0][:4] == ["docker", "exec", "fbox-demo", "/bin/bash"]
    assert "NOPASSWD:ALL" in calls[0][-1]
    assert calls[1] == [
        "docker",
        "exec",
        "-it",
        "--user",
        "chefsichter",
        "--workdir",
        "/workspace",
        "-e",
        "HOME=/home/chefsichter",
        "-e",
        "USER=chefsichter",
        "-e",
        "LOGNAME=chefsichter",
        "fbox-demo",
        "/bin/zsh",
    ]
