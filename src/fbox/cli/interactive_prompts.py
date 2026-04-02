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


def prompt_container_name(project_path: Path) -> str:
    default_name = build_default_name(project_path)
    answer = input(f"Container-Name [{default_name}]: ").strip()
    return sanitize_container_name(answer or default_name)


def prompt_extra_mounts() -> list[str]:
    answer = input(
        "Weitere Verzeichnisse mounten (mit Komma trennen, leer fuer keine): "
    ).strip()
    if not answer:
        return []
    return [item.strip() for item in answer.split(",") if item.strip()]
