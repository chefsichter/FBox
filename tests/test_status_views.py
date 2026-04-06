from fbox.cli.status_views import (
    get_indexed_records,
    print_container_list,
    print_debug_report,
)
from fbox.config.settings import AppConfig
from fbox.containers.container_record import ContainerRecord


def test_print_container_list_renders_known_records(capsys, monkeypatch) -> None:
    monkeypatch.setattr("fbox.cli.status_views.container_exists", lambda name: True)
    monkeypatch.setattr(
        "fbox.cli.status_views.container_is_running",
        lambda name: name == "fbox-a",
    )
    store = FakeStore(
        [
            ContainerRecord("fbox-b", "/tmp/b", "ubuntu", None, []),
            ContainerRecord("fbox-a", "/tmp/a", "ubuntu", None, []),
        ]
    )

    print_container_list(store)

    output = capsys.readouterr().out
    assert "ID\tNAME\tRUNNING\tIMAGE\tPROJECT_PATH" in output
    assert "1\tfbox-a\ttrue\tubuntu\t/tmp/a" in output
    assert "2\tfbox-b\tfalse\tubuntu\t/tmp/b" in output


def test_print_debug_report_shows_paths_and_values(capsys, monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr("fbox.cli.status_views.container_exists", lambda name: True)
    monkeypatch.setattr(
        "fbox.cli.status_views.container_is_running",
        lambda name: False,
    )
    store = FakeStore([ContainerRecord("fbox-a", "/tmp/a", "ubuntu", None, [])])

    print_debug_report(store, AppConfig(default_network="bridge"), "/tmp/a")

    output = capsys.readouterr().out
    assert "[Runtime]" in output
    assert "/usr/bin/docker" in output
    assert "[Config]" in output
    assert "bridge" in output
    assert "[Containers (1)]" in output
    assert "[1] fbox-a" in output
    assert "stopped" in output


def test_get_indexed_records_returns_stable_sorted_ids() -> None:
    store = FakeStore(
        [
            ContainerRecord("fbox-c", "/tmp/c", "ubuntu", None, []),
            ContainerRecord("fbox-a", "/tmp/a", "ubuntu", None, []),
        ]
    )

    records = get_indexed_records(store)

    assert [(item_id, record.name) for item_id, record in records] == [
        (1, "fbox-a"),
        (2, "fbox-c"),
    ]


def test_print_container_inspect_shows_details(capsys, monkeypatch) -> None:
    record = ContainerRecord(
        "fbox-a",
        "/tmp/a",
        "ubuntu",
        "abc123",
        [],
        create_args=["docker", "create", "--name", "fbox-a", "ubuntu"],
    )
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr("fbox.cli.status_views.container_exists", lambda name: True)
    monkeypatch.setattr("fbox.cli.status_views.container_is_running", lambda name: True)

    from fbox.cli.status_views import print_container_inspect

    store = FakeStore([record])
    result = print_container_inspect(store, 1)

    output = capsys.readouterr().out
    assert result == 0
    assert "fbox-a" in output
    assert "running" in output
    assert "abc123" in output
    assert "docker create (used)" in output


def test_print_container_inspect_unknown_id(capsys, monkeypatch) -> None:
    from fbox.cli.status_views import print_container_inspect

    store = FakeStore([])
    result = print_container_inspect(store, 99)

    assert result == 1


def test_print_container_inspect_no_create_args(capsys, monkeypatch) -> None:
    record = ContainerRecord("fbox-a", "/tmp/a", "ubuntu", None, [])
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr("fbox.cli.status_views.container_exists", lambda name: False)

    from fbox.cli.status_views import print_container_inspect

    store = FakeStore([record])
    result = print_container_inspect(store, 1)

    output = capsys.readouterr().out
    assert result == 0
    assert "not recorded" in output


class FakeStore:
    def __init__(self, records: list[ContainerRecord]) -> None:
        self._records = records

    def load(self) -> list[ContainerRecord]:
        return self._records
