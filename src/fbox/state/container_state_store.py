"""
Container State Store - Persist and lookup fbox container records on disk

Architecture:
    ┌─────────────────────────────────────────┐
    │  container_state_store.py               │
    │  ┌───────────────────────────────────┐  │
    │  │  JSON load/save                  │  │
    │  │  → ~/.local/state/fbox           │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Lookup helpers                  │  │
    │  │  → by name / by project path     │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from fbox.state.container_state_store import ContainerStateStore

    store = ContainerStateStore()
"""

from __future__ import annotations

import json
from pathlib import Path

from fbox.config.settings import get_state_file
from fbox.containers.models import ContainerRecord


class ContainerStateStore:
    def __init__(self, state_file: Path | None = None) -> None:
        self.state_file = state_file or get_state_file()

    def load(self) -> list[ContainerRecord]:
        if not self.state_file.exists():
            return []
        with self.state_file.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return [ContainerRecord.from_dict(item) for item in payload]

    def save(self, records: list[ContainerRecord]) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = [record.to_dict() for record in records]
        with self.state_file.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")

    def upsert(self, record: ContainerRecord) -> None:
        filtered = [
            item
            for item in self.load()
            if item.name != record.name and item.project_path != record.project_path
        ]
        filtered.append(record)
        self.save(filtered)

    def find_by_name(self, name: str) -> ContainerRecord | None:
        return next((record for record in self.load() if record.name == name), None)

    def find_by_project_path(self, project_path: Path) -> ContainerRecord | None:
        wanted_path = str(project_path.resolve())
        return next(
            (record for record in self.load() if record.project_path == wanted_path),
            None,
        )

    def delete_by_name(self, name: str) -> None:
        self.save([record for record in self.load() if record.name != name])
