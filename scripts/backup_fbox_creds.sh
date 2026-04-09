#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/scripts/fbox_credential_paths.sh"

DEFAULT_OUTPUT="$REPO_ROOT/secrets/fbox-creds.tar.gz.age"
RECIPIENT="${AGE_RECIPIENT:-}"
OUTPUT_PATH="$DEFAULT_OUTPUT"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/backup_fbox_creds.sh -r AGE_RECIPIENT [-o OUTPUT_PATH]

Options:
  -r  age recipient public key (alternativ via AGE_RECIPIENT)
  -o  Zieldatei fuer das verschluesselte Archiv
  -h  Hilfe anzeigen
EOF
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "'$1' wurde nicht gefunden." >&2
    exit 1
  fi
}

parse_args() {
  while getopts ":r:o:h" opt; do
    case "$opt" in
      r) RECIPIENT="$OPTARG" ;;
      o) OUTPUT_PATH="$OPTARG" ;;
      h)
        usage
        exit 0
        ;;
      :)
        echo "Option -$OPTARG erwartet ein Argument." >&2
        usage >&2
        exit 1
        ;;
      \?)
        echo "Unbekannte Option: -$OPTARG" >&2
        usage >&2
        exit 1
        ;;
    esac
  done
}

validate_inputs() {
  if [[ -z "$RECIPIENT" ]]; then
    echo "Kein age recipient gesetzt. Nutze -r oder AGE_RECIPIENT." >&2
    exit 1
  fi

  require_command age
  require_command tar
}

copy_credentials() {
  local staging_dir="$1"
  local missing=0

  for rel_path in "${FBOX_CREDENTIAL_PATHS[@]}"; do
    local source_path="$HOME/$rel_path"
    local target_dir="$staging_dir/$(dirname "$rel_path")"
    if [[ ! -f "$source_path" ]]; then
      echo "Fehlt: $source_path" >&2
      missing=1
      continue
    fi
    mkdir -p "$target_dir"
    cp "$source_path" "$target_dir/"
  done

  if [[ "$missing" -ne 0 ]]; then
    echo "Backup abgebrochen, weil mindestens eine Credential-Datei fehlt." >&2
    exit 1
  fi
}

create_bundle() {
  local staging_dir="$1"
  local archive_path="$2"

  mkdir -p "$(dirname "$OUTPUT_PATH")"
  tar -C "$staging_dir" -czf "$archive_path" .
  age -r "$RECIPIENT" -o "$OUTPUT_PATH" "$archive_path"
}

main() {
  parse_args "$@"
  validate_inputs

  local temp_dir
  temp_dir="$(mktemp -d)"
  trap 'rm -rf "$temp_dir"' EXIT

  copy_credentials "$temp_dir/payload"
  create_bundle "$temp_dir/payload" "$temp_dir/fbox-creds.tar.gz"
  echo "Verschluesseltes Archiv erstellt: $OUTPUT_PATH"
}

main "$@"
