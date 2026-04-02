from pathlib import Path

from fbox.config.settings import AppConfig
from fbox.containers.docker_runtime import (
    build_create_args,
    build_mount_spec,
    build_tmpfs_spec,
)
from fbox.containers.models import ContainerRecord


def test_build_mount_spec_respects_readonly_flag() -> None:
    mount_spec = build_mount_spec(Path("/tmp/project"), "/workspace", True)
    assert mount_spec.endswith("readonly=true")


def test_build_create_args_include_gpu_and_host_user_settings(monkeypatch) -> None:
    monkeypatch.setattr("os.getuid", lambda: 1000)
    monkeypatch.setattr("os.getgid", lambda: 1000)
    config = AppConfig(allow_all_gpus=True, root_mode="host-user")
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
    assert "--user" in args
    assert "1000:1000" in args
    assert any("/extra/data" in item for item in args)


def test_build_tmpfs_spec_omits_size_when_unlimited() -> None:
    assert build_tmpfs_spec("") == "/tmp:rw,noexec,nosuid"
