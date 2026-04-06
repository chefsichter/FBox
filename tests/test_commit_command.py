from pathlib import Path
import io

from fbox.cli import commit_command
from fbox.containers.models import ContainerRecord


def test_split_image_ref_handles_latest() -> None:
    assert commit_command.split_image_ref("repo/app") == ("repo/app", "latest")


def test_split_image_ref_handles_registry_port() -> None:
    image = "registry.local:5000/team/app:v1.2.3"
    assert commit_command.split_image_ref(image) == (
        "registry.local:5000/team/app",
        "v1.2.3",
    )


def test_build_semver_options_returns_patch_minor_major() -> None:
    assert commit_command.build_semver_options("repo/app", "v1.2.3") == [
        ("patch", "repo/app:v1.2.4"),
        ("minor", "repo/app:v1.3.0"),
        ("major", "repo/app:v2.0.0"),
    ]


def test_resolve_commit_source_by_id() -> None:
    record = ContainerRecord(
        name="fbox-demo",
        project_path="/tmp/demo",
        image="repo/app:v1.2.3",
        container_id=None,
        extra_mounts=[],
        profile_name="sandbox",
    )
    source = commit_command.resolve_commit_source([(3, record)], "3")

    assert source is not None
    assert source.container_name == "fbox-demo"
    assert source.profile_name == "sandbox"


def test_prompt_target_image_uses_default_for_latest(monkeypatch) -> None:
    monkeypatch.setattr(commit_command, "prompt_text", lambda prompt: "")

    image = commit_command.prompt_target_image("repo/app:latest")

    assert image == "repo/app:v0.0.1"


def test_prompt_target_image_accepts_choice_id(monkeypatch) -> None:
    monkeypatch.setattr(commit_command, "prompt_text", lambda prompt: "2")

    image = commit_command.prompt_target_image("repo/app:v1.2.3")

    assert image == "repo/app:v1.3.0"


def test_container_prompt_label_with_default() -> None:
    record = ContainerRecord(
        name="fbox-demo",
        project_path="/tmp/demo",
        image="repo/app:v1.2.3",
        container_id=None,
        extra_mounts=[],
        profile_name="sandbox",
    )
    assert commit_command.container_prompt_label(record) == (
        "Container fuer Commit "
        "[fbox-demo (image=repo/app:v1.2.3) | ls]: "
    )


def test_profile_prompt_label_with_default() -> None:
    assert commit_command.profile_prompt_label(
        "fbra-running",
        "repo/app:v1.0.0",
        "repo/app:v1.0.1",
    ) == (
        "Profil fuer neues Image "
        "[fbra-running | repo/app:v1.0.0 -> repo/app:v1.0.1 | ls]: "
    )


def test_prompt_commit_description_uses_editable_default(monkeypatch) -> None:
    source = commit_command.CommitSource(
        container_name="fbox-demo",
        image="repo/app:v1.2.3",
        profile_name="sandbox",
    )
    monkeypatch.setattr(commit_command, "prompt_text", lambda prompt: "")

    description = commit_command.prompt_commit_description(
        source,
        "repo/app:v1.2.4",
    )

    assert (
        description
        == "fbox-demo: repo/app:v1.2.3 -> repo/app:v1.2.4"
    )


def test_prompt_commit_description_appends_additional_text(monkeypatch) -> None:
    source = commit_command.CommitSource(
        container_name="fbox-demo",
        image="repo/app:v1.2.3",
        profile_name="sandbox",
    )
    monkeypatch.setattr(commit_command, "prompt_text", lambda prompt: "apt + node")

    description = commit_command.prompt_commit_description(
        source,
        "repo/app:v1.2.4",
    )

    assert (
        description
        == "fbox-demo: repo/app:v1.2.3 -> repo/app:v1.2.4 apt + node"
    )


def test_update_profile_image_creates_new_profile_from_source(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
default_profile = ""
default_image = "ubuntu:24.04"

[profiles.base]
default_network = "none"
workspace_readonly = true
""".strip()
        + "\n",
        encoding="utf-8",
    )

    commit_command.update_profile_image(
        config_path,
        "newprofile",
        "repo/app:v0.0.1",
        "base",
    )

    content = config_path.read_text(encoding="utf-8")
    assert "[profiles.newprofile]" in content
    assert 'default_network = "none"' in content
    assert "workspace_readonly = true" in content
    assert 'default_image = "repo/app:v0.0.1"' in content


def test_print_profile_options_shows_profile_images(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
default_profile = ""
default_image = "base:latest"

[profiles.llm]
default_image = "llm:latest"

[profiles.dev]
default_network = "none"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    commit_command.print_profile_options(
        config_path,
        ["llm", "dev"],
        "llm",
        "base:latest",
        "base:v0.0.1",
    )

    output = captured.getvalue()
    assert "[1] llm  image=llm:latest" in output
    assert "[2] dev  image=base:latest" in output
