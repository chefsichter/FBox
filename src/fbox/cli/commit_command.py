"""
Commit Command - Interactively snapshot a container into a versioned image

Usage:
    from fbox.cli.commit_command import cmd_commit
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import itertools
import subprocess
import sys
import threading

from fbox.cli.interactive_prompts import prompt_text
from fbox.cli.status_views import get_indexed_records
from fbox.config.profile_store import (
    get_profile_names,
    get_profile_overrides,
    upsert_profile,
)
from fbox.config.settings import load_config
from fbox.containers.docker_runtime import (
    DockerRuntimeError,
    container_exists,
    get_container_image,
    require_docker,
)
from fbox.containers.models import ContainerRecord
from fbox.state.container_state_store import ContainerStateStore


@dataclass(slots=True)
class CommitSource:
    container_name: str
    image: str
    profile_name: str = ""


def cmd_commit(store: ContainerStateStore, config_path: Path, cwd: Path) -> int:
    require_docker()
    source = prompt_commit_source(store, cwd.resolve())
    target_image = prompt_target_image(source.image)
    description = prompt_commit_description(source, target_image)
    commit_container_with_spinner(source.container_name, target_image, description)
    print(
        f"Image erstellt: {target_image}"
        f"  (aus Container {source.container_name})"
    )
    profile_name = prompt_profile_target(
        config_path,
        source.profile_name,
        source.image,
        target_image,
    )
    if not profile_name:
        print("Kein Profil aktualisiert.")
        return 0
    update_profile_image(config_path, profile_name, target_image, source.profile_name)
    print(f"Profil '{profile_name}' aktualisiert: default_image = {target_image}")
    return 0


def prompt_commit_source(store: ContainerStateStore, cwd: Path) -> CommitSource:
    indexed = [
        item for item in get_indexed_records(store) if container_exists(item[1].name)
    ]
    current = next(
        (record for _, record in indexed if record.project_path == str(cwd)),
        None,
    )
    if current is None:
        print_commit_sources(indexed, current)
    default_label = current.name if current is not None else None
    while True:
        answer = prompt_text(container_prompt_label(current))
        if answer == "ls":
            print_commit_sources(indexed, current)
            continue
        if not answer and current is not None:
            return CommitSource(current.name, current.image, current.profile_name)
        selected = resolve_commit_source(indexed, answer)
        if selected is not None:
            return selected
        print("Bitte PID, Containername oder `ls` eingeben.")


def print_commit_sources(
    indexed: list[tuple[int, ContainerRecord]],
    current: ContainerRecord | None,
) -> None:
    print("\nVerfuegbare fbox-Container:")
    if not indexed:
        print("  <none>")
    for record_id, record in indexed:
        marker = " (aktuelles Verzeichnis)" if current and record.name == current.name else ""
        print(
            f"  [{record_id}] {record.name}"
            f"  image={record.image}"
            f"  profile={record.profile_name or '-'}{marker}"
        )
    print("  Oder einen anderen existierenden Docker-Containernamen eingeben.")


def container_prompt_label(current: ContainerRecord | None) -> str:
    if current:
        return (
            "Container fuer Commit "
            f"[{current.name} (image={current.image}) | ls]: "
        )
    return "Container fuer Commit [ls]: "


def resolve_commit_source(
    indexed: list[tuple[int, ContainerRecord]],
    answer: str,
) -> CommitSource | None:
    if not answer:
        return None
    try:
        wanted_id = int(answer)
    except ValueError:
        wanted_id = None
    if wanted_id is not None:
        for record_id, record in indexed:
            if record_id == wanted_id:
                return CommitSource(record.name, record.image, record.profile_name)
        return None
    for _, record in indexed:
        if record.name == answer:
            return CommitSource(record.name, record.image, record.profile_name)
    if not container_exists(answer):
        return None
    return CommitSource(answer, get_container_image(answer))


def prompt_target_image(current_image: str) -> str:
    repository, tag = split_image_ref(current_image)
    if is_semver_tag(tag):
        options = build_semver_options(repository, tag)
    else:
        options = [("default", f"{repository}:v0.0.1")]
    print_image_options(current_image, options)
    default_image = options[0][1]
    while True:
        answer = prompt_text(f"Neues Image [{default_image}]: ")
        if not answer:
            return default_image
        if answer == "ls":
            print_image_options(current_image, options)
            continue
        if answer.isdigit():
            selected = resolve_option_by_id(options, int(answer))
            if selected is not None:
                return selected
        return answer


def print_image_options(current_image: str, options: list[tuple[str, str]]) -> None:
    print(f"\nAktuelles Image: {current_image}")
    print("Moegliche Ziel-Images:")
    for index, (label, image) in enumerate(options, start=1):
        marker = " (default)" if index == 1 else ""
        print(f"  [{index}] {label:<7} {image}{marker}")
    print("  Oder einen neuen Image-Namen direkt eingeben.")


def split_image_ref(image: str) -> tuple[str, str]:
    last_slash = image.rfind("/")
    last_colon = image.rfind(":")
    if last_colon > last_slash:
        return image[:last_colon], image[last_colon + 1 :]
    return image, "latest"


def is_semver_tag(tag: str) -> bool:
    if not tag.startswith("v"):
        return False
    parts = tag[1:].split(".")
    return len(parts) == 3 and all(part.isdigit() for part in parts)


def build_semver_options(repository: str, tag: str) -> list[tuple[str, str]]:
    major, minor, patch = (int(part) for part in tag[1:].split("."))
    return [
        ("patch", f"{repository}:v{major}.{minor}.{patch + 1}"),
        ("minor", f"{repository}:v{major}.{minor + 1}.0"),
        ("major", f"{repository}:v{major + 1}.0.0"),
    ]


def resolve_option_by_id(
    options: list[tuple[str, str]],
    wanted_id: int,
) -> str | None:
    if 1 <= wanted_id <= len(options):
        return options[wanted_id - 1][1]
    return None


def prompt_profile_target(
    config_path: Path,
    current_profile: str,
    current_image: str,
    target_image: str,
) -> str:
    names = get_profile_names(config_path)
    default_name = current_profile if current_profile in names else ""
    if not default_name:
        print_profile_options(
            config_path, names, default_name, current_image, target_image
        )
    while True:
        answer = prompt_text(
            profile_prompt_label(default_name, current_image, target_image)
        )
        if answer == "ls":
            print_profile_options(
                config_path, names, default_name, current_image, target_image
            )
            continue
        if not answer:
            return default_name
        if answer in {"0", "none", "-"}:
            return ""
        resolved = resolve_profile_name(names, answer)
        if resolved is not None:
            return resolved
        return answer


def print_profile_options(
    config_path: Path,
    names: list[str],
    default_name: str,
    current_image: str,
    target_image: str,
) -> None:
    profile_images = [
        (name, load_config(config_path, profile=name).default_image) for name in names
    ]
    name_width = max((len(name) for name, _ in profile_images), default=0)
    print("\nConfig-Profile:")
    marker = " (default)" if not default_name else ""
    print(f"  [0] nichts aktualisieren{marker}")
    for index, (name, profile_image) in enumerate(profile_images, start=1):
        marker = " (default)" if name == default_name else ""
        print(f"  [{index}] {name:<{name_width}}  ->  {profile_image}{marker}")
    print(f"  Ersetzt: {current_image} -> {target_image}")
    print("  Oder einen neuen Profilnamen eingeben.")


def profile_prompt_label(
    default_name: str,
    current_image: str,
    target_image: str,
) -> str:
    replacement = f"{current_image} -> {target_image}"
    if default_name:
        return f"Profil fuer neues Image [{default_name} | {replacement} | ls]: "
    return f"Profil fuer neues Image [kein Update | {replacement} | ls]: "


def resolve_profile_name(names: list[str], answer: str) -> str | None:
    if answer in names:
        return answer
    try:
        pid = int(answer)
    except ValueError:
        return None
    if 1 <= pid <= len(names):
        return names[pid - 1]
    return None


def prompt_commit_description(source: CommitSource, target_image: str) -> str:
    default_description = (
        f"{source.container_name}: {source.image} -> {target_image}"
    )
    answer = prompt_text(f"Beschreibung: [{default_description}] ")
    if not answer:
        return default_description
    return f"{default_description} {answer}"


def update_profile_image(
    config_path: Path,
    profile_name: str,
    image: str,
    source_profile_name: str,
) -> None:
    base_profile = source_profile_name if source_profile_name else profile_name
    overrides = get_profile_overrides(config_path, base_profile)
    overrides["default_image"] = image
    upsert_profile(config_path, profile_name, overrides)


def commit_container_with_spinner(
    container_name: str,
    target_image: str,
    description: str,
) -> None:
    message = f"Committe Container {container_name} nach {target_image}"
    stop_event = threading.Event()
    spinner_thread = threading.Thread(
        target=_render_spinner,
        args=(message, stop_event),
        daemon=True,
    )
    spinner_thread.start()
    try:
        subprocess.run(
            ["docker", "commit", "-m", description, container_name, target_image],
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        message_detail = error.stderr.strip() or "docker commit failed"
        raise DockerRuntimeError(message_detail) from error
    finally:
        stop_event.set()
        spinner_thread.join()
        sys.stdout.write(f"\r{message} ... fertig.\n")
        sys.stdout.flush()


def _render_spinner(message: str, stop_event: threading.Event) -> None:
    for frame in itertools.cycle("|/-\\"):
        if stop_event.wait(0.1):
            break
        sys.stdout.write(f"\r{message} ... {frame}")
        sys.stdout.flush()
