from __future__ import annotations

from pathlib import Path


APP_DIR_NAME = "fbox"
DEFAULT_IMAGE = "ubuntu:24.04"
DEFAULT_CONTAINER_PREFIX = "fbox"
DEFAULT_SHELL = "/bin/bash"
STATE_FILE_NAME = "containers.json"


def get_state_file() -> Path:
    state_home = Path.home() / ".local" / "state" / APP_DIR_NAME
    state_home.mkdir(parents=True, exist_ok=True)
    return state_home / STATE_FILE_NAME
