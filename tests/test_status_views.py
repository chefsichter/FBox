from fbox.cli.status_views import print_container_list, print_debug_report
from fbox.config.settings import AppConfig
from fbox.containers.models import ContainerRecord


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
    assert "NAME\tRUNNING\tIMAGE\tPROJECT_PATH" in output
    assert "fbox-a\ttrue\tubuntu\t/tmp/a" in output
    assert "fbox-b\tfalse\tubuntu\t/tmp/b" in output


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
    assert "fbox debug" in output
    assert "docker_binary: /usr/bin/docker" in output
    assert "default_network: bridge" in output
    assert "state_records: 1" in output
    assert "fbox-a: exists=True running=False project_path=/tmp/a" in output


class FakeStore:
    def __init__(self, records: list[ContainerRecord]) -> None:
        self._records = records

    def load(self) -> list[ContainerRecord]:
        return self._records
