from pathlib import Path

import pytest
from conftest import DummyCompletedProcess

from fbox.containers.target_resolution import resolve_target, validate_mounts
from fbox.install.cleanup import uninstall_fbox
from fbox.install.installer_main import main as installer_main
from fbox.install.venv_setup import (
    create_virtualenv,
    install_local_venv,
    installation_exists,
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


def test_create_virtualenv_raises_on_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: DummyCompletedProcess(1),
    )

    with pytest.raises(RuntimeError):
        create_virtualenv(tmp_path / ".venv")


def test_write_wrapper_script_creates_executable(tmp_path: Path) -> None:
    venv_path = tmp_path / ".venv"
    wrapper_path = tmp_path / "bin" / "fbox"
    (venv_path / "bin").mkdir(parents=True)

    write_wrapper_script(venv_path, tmp_path, wrapper_path)

    assert wrapper_path.exists()
    assert wrapper_path.stat().st_mode & 0o111
    assert "python" in wrapper_path.read_text(encoding="utf-8")
    assert 'PYTHONPATH="$REPO_ROOT/src' in wrapper_path.read_text(encoding="utf-8")


def test_install_local_venv_calls_all_steps(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "fbox.install.venv_setup.create_virtualenv",
        lambda path: calls.append(f"venv:{path}"),
    )
    monkeypatch.setattr(
        "fbox.install.venv_setup.write_wrapper_script",
        lambda venv, repo, wrapper: calls.append(f"wrapper:{wrapper}"),
    )

    install_local_venv(tmp_path, "~/.local/bin/fbox")

    assert calls[0].startswith("venv:")
    assert calls[1] == "wrapper:/root/.local/bin/fbox" or calls[1].startswith(
        "wrapper:"
    )


def test_installation_exists_checks_repo_and_config(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    assert installation_exists(repo_root, config_path) is False

    (repo_root / ".venv").mkdir()
    assert installation_exists(repo_root, config_path) is True


def test_installer_main_writes_config_and_installs_wrapper(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(
        "fbox.install.installer_main.choose_install_action",
        lambda exists: "install",
    )
    monkeypatch.setattr(
        "fbox.install.installer_main.installation_exists",
        lambda repo_root, config_path: False,
    )
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


def test_installer_main_uninstalls_when_selected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    uninstall_calls: list[tuple[Path, Path, bool]] = []
    monkeypatch.setattr(
        "fbox.install.installer_main.choose_install_action",
        lambda exists: "uninstall",
    )
    monkeypatch.setattr(
        "fbox.install.installer_main.installation_exists",
        lambda repo_root, config_path: True,
    )
    monkeypatch.setattr(
        "fbox.install.installer_main.uninstall_fbox",
        lambda repo_root, wrapper_path, remove_containers: uninstall_calls.append(
            (repo_root, wrapper_path, remove_containers)
        ),
    )
    monkeypatch.setattr(
        "fbox.install.installer_main.get_wrapper_path",
        lambda config_path: Path("/tmp/fbox-wrapper"),
    )

    installer_main()

    assert uninstall_calls
    assert uninstall_calls[0][2] is True


def test_uninstall_fbox_removes_artifacts(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".venv").mkdir()
    wrapper_path = tmp_path / "bin" / "fbox"
    wrapper_path.parent.mkdir(parents=True)
    wrapper_path.write_text("", encoding="utf-8")
    config_dir = tmp_path / "config-home"
    state_dir = tmp_path / "state-home"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_dir))
    monkeypatch.setenv("XDG_STATE_HOME", str(state_dir))
    config_path = config_dir / "fbox" / "config.toml"
    state_path = state_dir / "fbox" / "containers.json"
    config_path.parent.mkdir(parents=True)
    state_path.parent.mkdir(parents=True)
    config_path.write_text("", encoding="utf-8")
    state_path.write_text("", encoding="utf-8")
    remove_calls: list[bool] = []
    monkeypatch.setattr(
        "fbox.install.cleanup.remove_managed_containers",
        lambda: remove_calls.append(True),
    )

    uninstall_fbox(repo_root, wrapper_path, remove_containers=True)

    assert remove_calls == [True]
    assert not wrapper_path.exists()
    assert not config_path.exists()
    assert not state_path.exists()
    assert not (repo_root / ".venv").exists()
