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
    resolved_mounts: list[str] = []
    for raw_mount in mount_paths:
        mount_path = Path(raw_mount).expanduser()
        if not mount_path.exists():
            raise ValueError(f"Mount existiert nicht: {raw_mount}")
        if not mount_path.is_dir():
            raise ValueError(f"Mount ist kein Verzeichnis: {raw_mount}")
        resolved_mounts.append(str(mount_path.resolve()))
    if not project_path.exists():
        raise ValueError(f"Pfad existiert nicht: {project_path}")
    if not project_path.is_dir():
        raise ValueError(f"Pfad ist kein Verzeichnis: {project_path}")
    return resolved_mounts
