import io
from pathlib import Path

from fbox.cli import commit_command
from fbox.containers.container_record import ContainerRecord


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
        "Container fuer Commit " "[fbox-demo (image=repo/app:v1.2.3) | ls]: "
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

    assert description == "fbox-demo: repo/app:v1.2.3 -> repo/app:v1.2.4"


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

    assert description == "fbox-demo: repo/app:v1.2.3 -> repo/app:v1.2.4 apt + node"


def test_update_profile_image_creates_new_profile_from_source(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
default_profile = ""
default_image = "ubuntu:24.04"

[profiles.base]
default_network = "none"
workspace_readonly = true
""".strip() + "\n",
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


def test_print_profile_options_shows_profile_images(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
default_profile = ""
default_image = "base:latest"

[profiles.llm]
default_image = "llm:latest"

[profiles.dev]
default_network = "none"
""".strip() + "\n",
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
    assert "[1] llm  ->  llm:latest" in output
    assert "[2] dev  ->  base:latest" in output


def test_container_prompt_label_without_default() -> None:
    assert commit_command.container_prompt_label(None) == "Container fuer Commit [ls]: "


def test_profile_prompt_label_without_default() -> None:
    label = commit_command.profile_prompt_label("", "img:v1", "img:v2")
    assert "kein Update" in label


def test_resolve_commit_source_by_name() -> None:
    record = ContainerRecord(
        name="fbox-demo",
        project_path="/tmp/demo",
        image="repo/app:v1.2.3",
        container_id=None,
        extra_mounts=[],
        profile_name="",
    )
    source = commit_command.resolve_commit_source([(1, record)], "fbox-demo")

    assert source is not None
    assert source.container_name == "fbox-demo"


def test_resolve_commit_source_empty_returns_none() -> None:
    assert commit_command.resolve_commit_source([], "") is None


def test_resolve_commit_source_unknown_id_returns_none() -> None:
    assert commit_command.resolve_commit_source([], "99") is None


def test_resolve_commit_source_unknown_name_not_in_docker(monkeypatch) -> None:
    monkeypatch.setattr(commit_command, "container_exists", lambda name: False)
    result = commit_command.resolve_commit_source([], "ghost-container")
    assert result is None


def test_resolve_commit_source_unknown_name_in_docker(monkeypatch) -> None:
    monkeypatch.setattr(commit_command, "container_exists", lambda name: True)
    monkeypatch.setattr(commit_command, "get_container_image", lambda name: "img:v1")
    result = commit_command.resolve_commit_source([], "live-container")
    assert result is not None
    assert result.container_name == "live-container"
    assert result.image == "img:v1"


def test_prompt_target_image_accepts_free_text(monkeypatch) -> None:
    monkeypatch.setattr(commit_command, "prompt_text", lambda prompt: "custom/img:v9")

    image = commit_command.prompt_target_image("repo/app:v1.0.0")

    assert image == "custom/img:v9"


def test_prompt_target_image_ls_then_default(monkeypatch) -> None:
    answers = iter(["ls", ""])
    monkeypatch.setattr(commit_command, "prompt_text", lambda prompt: next(answers))
    monkeypatch.setattr(
        commit_command,
        "print_image_options",
        lambda current, options: None,
    )

    image = commit_command.prompt_target_image("repo/app:v1.2.3")

    assert image == "repo/app:v1.2.4"


def test_resolve_profile_name_by_name() -> None:
    assert commit_command.resolve_profile_name(["sandbox", "llm"], "llm") == "llm"


def test_resolve_profile_name_by_pid() -> None:
    assert commit_command.resolve_profile_name(["sandbox", "llm"], "1") == "sandbox"


def test_resolve_profile_name_out_of_range() -> None:
    assert commit_command.resolve_profile_name(["sandbox"], "9") is None


def test_resolve_profile_name_non_integer() -> None:
    assert commit_command.resolve_profile_name(["sandbox"], "notanumber") is None


def test_is_semver_tag_valid() -> None:
    assert commit_command.is_semver_tag("v1.2.3") is True


def test_is_semver_tag_invalid() -> None:
    assert commit_command.is_semver_tag("latest") is False
    assert commit_command.is_semver_tag("v1.2") is False
    assert commit_command.is_semver_tag("1.2.3") is False


def test_print_commit_sources_renders_list(monkeypatch, capsys) -> None:
    record = ContainerRecord(
        name="fbox-demo",
        project_path="/tmp/demo",
        image="img:v1",
        container_id=None,
        extra_mounts=[],
        profile_name="sandbox",
    )

    commit_command.print_commit_sources([(1, record)], None)

    output = capsys.readouterr().out
    assert "fbox-demo" in output
    assert "sandbox" in output


def test_cmd_commit_full_flow_no_profile_update(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('default_profile = ""\n', encoding="utf-8")

    source = commit_command.CommitSource(
        container_name="fbox-demo",
        image="repo/app:v1.2.3",
        profile_name="",
    )
    monkeypatch.setattr(commit_command, "require_docker", lambda: None)
    monkeypatch.setattr(
        commit_command, "prompt_commit_source", lambda store, cwd: source
    )
    monkeypatch.setattr(
        commit_command, "prompt_target_image", lambda img: "repo/app:v1.2.4"
    )
    monkeypatch.setattr(
        commit_command, "prompt_commit_description", lambda src, tgt: "desc"
    )
    monkeypatch.setattr(
        commit_command, "commit_container_with_spinner", lambda name, img, desc: None
    )
    monkeypatch.setattr(
        commit_command,
        "prompt_profile_target",
        lambda cfg, pname, cimg, timg: "",
    )

    from fbox.state.container_state_store import ContainerStateStore

    store = ContainerStateStore(tmp_path / "state.json")
    result = commit_command.cmd_commit(store, config_path, tmp_path)

    assert result == 0


def test_prompt_commit_source_uses_current_dir(tmp_path: Path, monkeypatch) -> None:
    record = ContainerRecord(
        name="fbox-demo",
        project_path=str(tmp_path),
        image="img:v1",
        container_id=None,
        extra_mounts=[],
        profile_name="sandbox",
    )
    from fbox.state.container_state_store import ContainerStateStore

    state_file = tmp_path / "state.json"
    store = ContainerStateStore(state_file)
    store.upsert(record)

    monkeypatch.setattr(commit_command, "container_exists", lambda name: True)
    monkeypatch.setattr(commit_command, "prompt_text", lambda prompt: "")

    source = commit_command.prompt_commit_source(store, tmp_path)

    assert source.container_name == "fbox-demo"
    assert source.profile_name == "sandbox"


def test_prompt_profile_target_returns_empty_on_zero(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'default_profile = ""\n\n[profiles.sandbox]\ndefault_network = "none"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(commit_command, "prompt_text", lambda prompt: "0")

    result = commit_command.prompt_profile_target(config_path, "", "img:v1", "img:v2")

    assert result == ""


def test_prompt_profile_target_returns_new_name(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'default_profile = ""\n\n[profiles.sandbox]\ndefault_network = "none"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(commit_command, "prompt_text", lambda prompt: "newname")

    result = commit_command.prompt_profile_target(config_path, "", "img:v1", "img:v2")

    assert result == "newname"


def test_commit_container_with_spinner_calls_commit(monkeypatch) -> None:
    committed: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        commit_command,
        "commit_container",
        lambda name, image, description: committed.append((name, image, description)),
    )

    commit_command.commit_container_with_spinner("fbox-demo", "img:v1", "desc")

    assert committed == [("fbox-demo", "img:v1", "desc")]


def test_prompt_profile_target_with_ls(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'default_profile = ""\n\n[profiles.sandbox]\ndefault_network = "none"\n',
        encoding="utf-8",
    )
    answers = iter(["ls", "sandbox"])
    monkeypatch.setattr(commit_command, "prompt_text", lambda prompt: next(answers))
    monkeypatch.setattr(
        commit_command,
        "print_profile_options",
        lambda *args: None,
    )

    result = commit_command.prompt_profile_target(
        config_path, "sandbox", "img:v1", "img:v2"
    )

    assert result == "sandbox"
