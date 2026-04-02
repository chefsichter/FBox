from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class ContainerRecord:
    name: str
    project_path: str
    image: str
    container_id: str | None
    extra_mounts: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ContainerRecord":
        return cls(
            name=str(payload["name"]),
            project_path=str(payload["project_path"]),
            image=str(payload["image"]),
            container_id=str(payload["container_id"])
            if payload.get("container_id")
            else None,
            extra_mounts=[str(item) for item in payload.get("extra_mounts", [])],
        )
