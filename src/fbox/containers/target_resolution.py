"""
Target Resolution - Resolve CLI targets into project paths or container names

Architecture:
    ┌─────────────────────────────────────────┐
    │  target_resolution.py                   │
    │  ┌───────────────────────────────────┐  │
    │  │  Target parsing                  │  │
    │  │  → path if it exists             │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Mount validation                │  │
    │  │  → existing directories only     │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from fbox.containers.target_resolution import resolve_target

    project_path, name = resolve_target(raw_target)
"""

from __future__ import annotations

from pathlib import Path


def resolve_target(raw_target: str | None) -> tuple[Path | None, str | None]:
    if raw_target is None:
        return Path("."), None
    target_path = Path(raw_target).expanduser()
    if target_path.exists():
        return target_path, None
    return None, raw_target


def validate_mounts(project_path: Path, mount_paths: list[str]) -> list[str]:
    if not project_path.exists():
        raise ValueError(f"Pfad existiert nicht: {project_path}")
    if not project_path.is_dir():
        raise ValueError(f"Pfad ist kein Verzeichnis: {project_path}")
    resolved_mounts: list[str] = []
    for raw_mount in mount_paths:
        parts = raw_mount.split(":", 2)
        raw_source = parts[0]
        destination = parts[1] if len(parts) >= 2 else ""
        mode = parts[2] if len(parts) == 3 else ""
        if mode and mode not in ("rw", "ro"):
            raise ValueError(f"Ungueltiger Mount-Modus '{mode}', erlaubt: rw, ro")
        source = Path(raw_source).expanduser()
        if not source.exists():
            raise ValueError(f"Mount existiert nicht: {raw_source}")
        if not source.is_dir():
            raise ValueError(f"Mount ist kein Verzeichnis: {raw_source}")
        resolved = str(source.resolve())
        entry = resolved
        if destination:
            entry = f"{resolved}:{destination}"
            if mode:
                entry = f"{entry}:{mode}"
        resolved_mounts.append(entry)
    return resolved_mounts
