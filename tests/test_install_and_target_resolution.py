from pathlib import Path

import pytest

from fbox.containers.target_resolution import resolve_target, validate_mounts
from fbox.install.installer_main import main as installer_main
from fbox.install.venv_setup import (
    create_virtualenv,
    install_editable_package,
    install_local_venv,
    write_wrapper_script,
)


def test_resolve_target_returns_path_for_existing_directory(tmp_path: Path) -> None:
    project_path, name = resolve_target(str(tmp_path))

    assert project_path == tmp_path
    assert name is None


def test_validate_mounts_rejects_missing_or_file_mounts(tmp_path: Path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    file_mount = tmp_path / "file.txt"
    file_mount.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError):
        validate_mounts(project_path, [str(tmp_path / "missing")])

    with pytest.raises(ValueError):
        validate_mounts(project_path, [str(file_mount)])


def test_validate_mounts_resolves_directories(tmp_path: Path) -> None:
    project_path = tmp_path / "project"
    extra_mount = tmp_path / "data"
    project_path.mkdir()
    extra_mount.mkdir()

    mounts = validate_mounts(project_path, [str(extra_mount)])

    assert mounts == [str(extra_mount.resolve())]


def test_create_virtualenv_and_install_editable_raise_on_failure(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: DummyCompletedProcess(1),
    )

    with pytest.raises(RuntimeError):
        create_virtualenv(tmp_path / ".venv")

    with pytest.raises(RuntimeError):
        install_editable_package(tmp_path / ".venv", tmp_path)


def test_write_wrapper_script_creates_executable(tmp_path: Path) -> None:
    venv_path = tmp_path / ".venv"
    wrapper_path = tmp_path / "bin" / "fbox"
    (venv_path / "bin").mkdir(parents=True)

    write_wrapper_script(venv_path, tmp_path, wrapper_path)

    assert wrapper_path.exists()
    assert wrapper_path.stat().st_mode & 0o111
    assert "python" in wrapper_path.read_text(encoding="utf-8")


def test_install_local_venv_calls_all_steps(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "fbox.install.venv_setup.create_virtualenv",
        lambda path: calls.append(f"venv:{path}"),
    )
    monkeypatch.setattr(
        "fbox.install.venv_setup.install_editable_package",
        lambda venv, repo: calls.append(f"editable:{venv}:{repo}"),
    )
    monkeypatch.setattr(
        "fbox.install.venv_setup.write_wrapper_script",
        lambda venv, repo, wrapper: calls.append(f"wrapper:{wrapper}"),
    )

    install_local_venv(tmp_path, "~/.local/bin/fbox")

    assert calls[0].startswith("venv:")
    assert calls[1].startswith("editable:")
    assert calls[2] == "wrapper:/root/.local/bin/fbox" or calls[2].startswith(
        "wrapper:"
    )


def test_installer_main_writes_config_and_installs_wrapper(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(
        "fbox.install.installer_main.build_config_interactively",
        lambda path: ('default_image = "ubuntu:24.04"\n', "~/.local/bin/fbox"),
    )
    install_calls: list[tuple[Path, str]] = []
    monkeypatch.setattr(
        "fbox.install.installer_main.install_local_venv",
        lambda repo_root, wrapper: install_calls.append((repo_root, wrapper)),
    )

    installer_main()

    config_path = tmp_path / "config" / "fbox" / "config.toml"
    assert config_path.exists()
    assert install_calls


class DummyCompletedProcess:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode
