import argparse
from pathlib import Path

import pytest

from fbox.cli import main as cli_main
from fbox.config.settings import AppConfig
from fbox.containers.models import ContainerRecord


def test_maybe_handle_config_flags_prints_path(capsys, monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "get_config_path", lambda: Path("/tmp/config.toml"))
    args = argparse.Namespace(
        print_config_path=True,
        config=False,
        ls=False,
        debug=False,
        target=None,
    )

    result = cli_main.maybe_handle_config_flags(args, AppConfig(), FakeStore())

    assert result == 0
    assert capsys.readouterr().out.strip() == "/tmp/config.toml"


def test_maybe_handle_config_flags_opens_editor(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "edit_config", lambda config: 7)
    args = argparse.Namespace(
        print_config_path=False,
        config=True,
        ls=False,
        debug=False,
        target=None,
    )

    result = cli_main.maybe_handle_config_flags(args, AppConfig(), FakeStore())

    assert result == 7


def test_maybe_handle_config_flags_lists_containers(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "print_container_list", lambda store: None)
    args = argparse.Namespace(
        print_config_path=False,
        config=False,
        ls=True,
        debug=False,
        target=None,
    )

    result = cli_main.maybe_handle_config_flags(args, AppConfig(), FakeStore())

    assert result == 0


def test_maybe_handle_config_flags_prints_debug(monkeypatch) -> None:
    monkeypatch.setattr(
        cli_main,
        "print_debug_report",
        lambda store, config, target: None,
    )
    args = argparse.Namespace(
        print_config_path=False,
        config=False,
        ls=False,
        debug=True,
        target="demo",
    )

    result = cli_main.maybe_handle_config_flags(args, AppConfig(), FakeStore())

    assert result == 0


def test_reuse_by_project_path_uses_record(monkeypatch) -> None:
    record = ContainerRecord(
        name="fbox-demo",
        project_path="/tmp/demo",
        image="ubuntu:24.04",
        container_id=None,
        extra_mounts=[],
    )
    store = FakeStore(record_by_path=record)
    monkeypatch.setattr(cli_main, "container_exists", lambda name: True)
    monkeypatch.setattr(cli_main, "start_and_open", lambda name, config: 11)

    result = cli_main.reuse_by_project_path(store, Path("/tmp/demo"), AppConfig())

    assert result == 11
    assert store.deleted_names == []


def test_reuse_by_project_path_falls_back_to_label(monkeypatch) -> None:
    store = FakeStore()
    monkeypatch.setattr(
        cli_main, "find_container_by_label", lambda label, value: "fbox-labeled"
    )
    monkeypatch.setattr(cli_main, "start_and_open", lambda name, config: 13)

    result = cli_main.reuse_by_project_path(store, Path("/tmp/demo"), AppConfig())

    assert result == 13


def test_reuse_by_container_name_cleans_stale_state(monkeypatch) -> None:
    record = ContainerRecord(
        name="fbox-demo",
        project_path="/tmp/demo",
        image="ubuntu:24.04",
        container_id=None,
        extra_mounts=[],
    )
    store = FakeStore(record_by_name=record)
    monkeypatch.setattr(cli_main, "container_exists", lambda name: False)

    result = cli_main.reuse_by_container_name(store, "fbox-demo", AppConfig())

    assert result is None
    assert store.deleted_names == ["fbox-demo"]


def test_create_new_container_builds_record(monkeypatch) -> None:
    store = FakeStore()
    monkeypatch.setattr(cli_main, "prompt_container_name", lambda path: "fbox-demo")
    monkeypatch.setattr(cli_main, "prompt_extra_mounts", lambda: ["/tmp/data"])
    monkeypatch.setattr(
        cli_main,
        "validate_mounts",
        lambda project, mounts: [str(Path(item).resolve()) for item in mounts],
    )
    monkeypatch.setattr(cli_main, "container_exists", lambda name: False)
    monkeypatch.setattr(cli_main, "create_container", lambda record, config: "abc123")
    monkeypatch.setattr(cli_main, "start_and_open", lambda name, config: 17)

    result = cli_main.create_new_container(
        store,
        Path("/tmp/project"),
        None,
        AppConfig(default_image="ubuntu:24.04", extra_mounts_readonly=True),
    )

    assert result == 17
    assert store.saved_record is not None
    assert store.saved_record.container_id == "abc123"
    assert store.saved_record.extra_mounts == [str(Path("/tmp/data").resolve())]


def test_start_and_open_starts_before_opening(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        cli_main, "ensure_started", lambda name: calls.append(f"start:{name}")
    )
    monkeypatch.setattr(
        cli_main,
        "open_shell",
        lambda name, config: calls.append(f"open:{name}") or 19,
    )

    result = cli_main.start_and_open("fbox-demo", AppConfig())

    assert result == 19
    assert calls == ["start:fbox-demo", "open:fbox-demo"]


def test_main_exits_with_error_when_target_unknown(monkeypatch) -> None:
    monkeypatch.setattr(
        cli_main,
        "parse_args",
        lambda: argparse.Namespace(
            target="missing",
            image=None,
            print_config_path=False,
            config=False,
            ls=False,
            debug=False,
        ),
    )
    monkeypatch.setattr(
        cli_main, "ensure_config_exists", lambda: Path("/tmp/config.toml")
    )
    monkeypatch.setattr(cli_main, "load_config", lambda: AppConfig())
    monkeypatch.setattr(cli_main, "require_docker", lambda: None)
    monkeypatch.setattr(cli_main, "resolve_target", lambda target: (None, "missing"))
    monkeypatch.setattr(cli_main, "reuse_existing_container", lambda *args: None)

    with pytest.raises(SystemExit) as error:
        cli_main.main()

    assert str(error.value) == "Kein bekannter fbox-Container gefunden: missing"


class FakeStore:
    def __init__(
        self,
        record_by_path: ContainerRecord | None = None,
        record_by_name: ContainerRecord | None = None,
    ) -> None:
        self.record_by_path = record_by_path
        self.record_by_name = record_by_name
        self.deleted_names: list[str] = []
        self.saved_record: ContainerRecord | None = None

    def find_by_project_path(self, project_path: Path) -> ContainerRecord | None:
        return self.record_by_path

    def find_by_name(self, name: str) -> ContainerRecord | None:
        return self.record_by_name

    def delete_by_name(self, name: str) -> None:
        self.deleted_names.append(name)

    def upsert(self, record: ContainerRecord) -> None:
        self.saved_record = record
