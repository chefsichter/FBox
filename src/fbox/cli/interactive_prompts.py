"""
Interactive Prompts - Gather CLI answers for container name and extra mounts

Architecture:
    ┌─────────────────────────────────────────┐
    │  interactive_prompts.py                 │
    │  ┌───────────────────────────────────┐  │
    │  │  Default name builder            │  │
    │  │  → fbox-<directory>              │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  User prompts                    │  │
    │  │  → name + optional mount list    │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from fbox.cli.interactive_prompts import prompt_container_name

    name = prompt_container_name(project_path)
"""

from __future__ import annotations

from pathlib import Path

from fbox.config.settings import DEFAULT_CONTAINER_PREFIX
from fbox.containers.docker_runtime import sanitize_container_name

def build_default_name(project_path: Path) -> str:
    base_name = project_path.resolve().name or DEFAULT_CONTAINER_PREFIX
    return sanitize_container_name(f"{DEFAULT_CONTAINER_PREFIX}-{base_name}")


def prompt_text(prompt: str) -> str:
    return input(prompt).strip()


def prompt_container_name(project_path: Path) -> str:
    default_name = build_default_name(project_path)
    answer = prompt_text(f"Container-Name [{default_name}]: ")
    return sanitize_container_name(answer or default_name)


def prompt_extra_mounts() -> list[str]:
    answer = prompt_text(
        "Weitere Verzeichnisse mounten (quelle:ziel[:rw|ro], Komma trennt mehrere): "
    )
    if not answer:
        return []
    return [item.strip() for item in answer.split(",") if item.strip()]


def prompt_profile_name(
    profile_names: list[str],
    default_profile: str,
) -> str:
    if not profile_names:
        return ""

    print("\nVerfuegbare Profile fuer die neue Box:")
    print("  [0] ohne Profil")
    default_index = 0
    for index, name in enumerate(profile_names, 1):
        marker = " (default)" if name == default_profile else ""
        print(f"  [{index}] {name}{marker}")
        if name == default_profile:
            default_index = index

    default_label = profile_names[default_index - 1] if default_index else "ohne Profil"
    while True:
        answer = prompt_text(
            f"Profil fuer neue Box [{default_label}]: "
        )
        if not answer:
            return default_profile if default_index else ""
        if answer in {"0", "none"}:
            return ""
        if answer in profile_names:
            return answer
        try:
            pid = int(answer)
        except ValueError:
            print("Bitte Profilname, PID oder 0 eingeben.")
            continue
        if 1 <= pid <= len(profile_names):
            return profile_names[pid - 1]
        print(f"Unbekannte PID: {pid}")
