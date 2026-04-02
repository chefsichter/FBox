"""
Container Models - Persisted metadata for managed fbox containers

Architecture:
    ┌─────────────────────────────────────────┐
    │  models.py                              │
    │  ┌───────────────────────────────────┐  │
    │  │  ContainerRecord dataclass       │  │
    │  │  → path, image, mounts, flags    │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  JSON serialization              │  │
    │  │  → state file compatibility      │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from fbox.containers.models import ContainerRecord

    record = ContainerRecord(...)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class ContainerRecord:
    name: str
    project_path: str
    image: str
    container_id: str | None
    extra_mounts: list[str]
    extra_mounts_readonly: bool = True
    create_args: list[str] | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ContainerRecord:
        extra_mounts_payload = payload.get("extra_mounts", [])
        if not isinstance(extra_mounts_payload, list):
            extra_mounts_payload = []
        return cls(
            name=str(payload["name"]),
            project_path=str(payload["project_path"]),
            image=str(payload["image"]),
            container_id=(
                str(payload["container_id"]) if payload.get("container_id") else None
            ),
            extra_mounts=[str(item) for item in extra_mounts_payload],
            extra_mounts_readonly=bool(payload.get("extra_mounts_readonly", True)),
            create_args=(
                [str(a) for a in payload["create_args"]]
                if isinstance(payload.get("create_args"), list)
                else None
            ),
        )
