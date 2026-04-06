import json
from pathlib import Path

from conftest import DummyCompletedProcess

from fbox.config.config_bootstrap import ensure_config_exists
from fbox.config.config_editor import edit_config, get_config_path
from fbox.config.settings import AppConfig, get_config_file, get_state_file
from fbox.containers.container_record import ContainerRecord
from fbox.state.container_state_store import ContainerStateStore


def test_get_config_and_state_file_respect_xdg(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    assert get_config_file() == tmp_path / "config" / "fbox" / "config.toml"
    assert get_state_file() == tmp_path / "state" / "fbox" / "containers.json"


def test_ensure_config_exists_copies_example(tmp_path: Path) -> None:
    target = tmp_path / "fbox" / "config.toml"

    ensure_config_exists(target)

    assert target.exists()
    assert 'default_image = "ubuntu:24.04"' in target.read_text(encoding="utf-8")


def test_get_config_path_bootstraps_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    config_path = get_config_path()

    assert config_path.exists()
    assert config_path == tmp_path / "fbox" / "config.toml"


def test_edit_config_uses_configured_editor(monkeypatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []
    config_path = tmp_path / "config.toml"
    config_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "fbox.config.config_editor.get_config_path", lambda: config_path
    )
    monkeypatch.setattr(
        "subprocess.run",
        lambda args, check, text: commands.append(args) or DummyCompletedProcess(0),
    )

    result = edit_config(AppConfig(editor_command="code --wait"))

    assert result == 0
    assert commands == [["code", "--wait", str(config_path)]]


def test_container_state_store_roundtrip(tmp_path: Path) -> None:
    state_file = tmp_path / "containers.json"
    store = ContainerStateStore(state_file)
    record = ContainerRecord(
        name="fbox-demo",
        project_path="/tmp/demo",
        image="ubuntu:24.04",
        container_id="123",
        extra_mounts=["/tmp/data"],
        profile_name="sandbox",
    )

    store.upsert(record)

    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0].name == "fbox-demo"
    assert loaded[0].profile_name == "sandbox"
    assert store.find_by_name("fbox-demo") is not None
    assert store.find_by_project_path(Path("/tmp/demo")) is not None


def test_container_state_store_delete_and_invalid_extra_mounts(tmp_path: Path) -> None:
    state_file = tmp_path / "containers.json"
    state_file.write_text(
        json.dumps(
            [
                {
                    "name": "fbox-demo",
                    "project_path": "/tmp/demo",
                    "image": "ubuntu:24.04",
                    "container_id": None,
                    "extra_mounts": "invalid",
                }
            ]
        ),
        encoding="utf-8",
    )
    store = ContainerStateStore(state_file)

    loaded = store.load()
    store.delete_by_name("fbox-demo")

    assert loaded[0].extra_mounts == []
    assert store.load() == []
