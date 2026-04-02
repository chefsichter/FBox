#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 wurde nicht gefunden." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker wurde nicht gefunden." >&2
  exit 1
fi

cd "$REPO_ROOT"
PYTHONPATH=src python3 -m fbox.install.installer_main
