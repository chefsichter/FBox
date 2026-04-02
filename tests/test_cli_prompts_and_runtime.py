from pathlib import Path

import pytest
from conftest import DummyCompletedProcess

from fbox.cli.interactive_prompts import (
    build_default_name,
    prompt_container_name,
    prompt_extra_mounts,
)
from fbox.config.settings import AppConfig
from fbox.containers import docker_runtime
from fbox.containers.docker_runtime import DockerRuntimeError
from fbox.containers.models import ContainerRecord


def test_build_default_name_sanitizes_project_name(tmp_path: Path) -> None:
    project_path = tmp_path / "Demo Project"
    project_path.mkdir()

    result = build_default_name(project_path)

    assert result == "fbox-demo-project"


def test_prompt_container_name_uses_default_when_empty(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.setattr("builtins.input", lambda _: "")

    result = prompt_container_name(project_path)

    assert result == "fbox-demo"


def test_prompt_extra_mounts_splits_and_strips(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: " /tmp/a , /tmp/b ")

    result = prompt_extra_mounts()

    assert result == ["/tmp/a", "/tmp/b"]


def test_require_docker_raises_when_binary_missing(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)

    with pytest.raises(DockerRuntimeError):
        docker_runtime.require_docker()


def test_container_exists_and_find_label(monkeypatch) -> None:
    monkeypatch.setattr(docker_runtime, "inspect_container", lambda name: "ok")
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: DummyCompletedProcess(0, stdout="fbox-demo\n"),
    )

    assert docker_runtime.container_exists("fbox-demo") is True
    assert (
        docker_runtime.find_container_by_label("ch.fbox.project_path", "/tmp/demo")
        == "fbox-demo"
    )


def test_run_docker_command_raises_with_stderr(monkeypatch) -> None:
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: DummyCompletedProcess(1, stderr="boom"),
    )

    with pytest.raises(DockerRuntimeError, match="boom"):
        docker_runtime.run_docker_command(["ps"], capture_output=True)


def test_container_is_running_create_and_open_shell(monkeypatch) -> None:
    record = ContainerRecord(
        name="fbox-demo",
        project_path="/tmp/demo",
        image="ubuntu:24.04",
        container_id=None,
        extra_mounts=[],
    )
    monkeypatch.setattr(
        docker_runtime,
        "run_docker_command",
        lambda args, capture_output=False: DummyCompletedProcess(
            0,
            stdout="true" if "inspect" in args else "container123",
        ),
    )
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: DummyCompletedProcess(0, stdout=""),
    )

    assert docker_runtime.container_is_running("fbox-demo") is True
    assert docker_runtime.create_container(record, AppConfig()) == "container123"
    assert docker_runtime.open_shell("fbox-demo", AppConfig()) == 0


def test_ensure_started_starts_only_when_needed(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(docker_runtime, "container_is_running", lambda name: False)
    monkeypatch.setattr(
        docker_runtime,
        "run_docker_command",
        lambda args, capture_output=False: calls.append(args)
        or DummyCompletedProcess(0),
    )

    docker_runtime.ensure_started("fbox-demo")

    assert calls == [["start", "fbox-demo"]]
