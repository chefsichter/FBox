#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/scripts/fbox_credential_paths.sh"

DEFAULT_BUNDLE="$REPO_ROOT/secrets/fbox-creds.tar.gz.age"
BUNDLE_PATH="$DEFAULT_BUNDLE"
IDENTITY_PATH="${AGE_IDENTITY_FILE:-$HOME/.config/age/key.txt}"
FORCE_OVERWRITE=0

usage() {
  cat <<'EOF'
Usage:
  ./scripts/restore_fbox_creds.sh [-i AGE_IDENTITY_FILE] [-b BUNDLE_PATH] [--force]

Options:
  -i  age identity key file (alternativ via AGE_IDENTITY_FILE)
  -b  Pfad zum verschluesselten Archiv
  -h  Hilfe anzeigen
  --force  vorhandene Dateien ueberschreiben
EOF
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "'$1' wurde nicht gefunden." >&2
    exit 1
  fi
}

parse_args() {
  while (($# > 0)); do
    case "$1" in
      -i)
        IDENTITY_PATH="$2"
        shift 2
        ;;
      -b)
        BUNDLE_PATH="$2"
        shift 2
        ;;
      --force)
        FORCE_OVERWRITE=1
        shift
        ;;
      -h)
        usage
        exit 0
        ;;
      *)
        echo "Unbekanntes Argument: $1" >&2
        usage >&2
        exit 1
        ;;
    esac
  done
}

validate_inputs() {
  require_command age
  require_command tar

  if [[ ! -f "$BUNDLE_PATH" ]]; then
    echo "Archiv nicht gefunden: $BUNDLE_PATH" >&2
    exit 1
  fi

  if [[ ! -f "$IDENTITY_PATH" ]]; then
    echo "Identity-Datei nicht gefunden: $IDENTITY_PATH" >&2
    exit 1
  fi
}

guard_overwrite() {
  if [[ "$FORCE_OVERWRITE" -eq 1 ]]; then
    return
  fi

  for rel_path in "${FBOX_CREDENTIAL_PATHS[@]}"; do
    if [[ -e "$HOME/$rel_path" ]]; then
      echo "Zieldatei existiert bereits: $HOME/$rel_path" >&2
      echo "Nutze --force, um vorhandene Dateien zu ueberschreiben." >&2
      exit 1
    fi
  done
}

restore_credentials() {
  local temp_dir="$1"

  age -d -i "$IDENTITY_PATH" -o "$temp_dir/fbox-creds.tar.gz" "$BUNDLE_PATH"
  tar -C "$temp_dir/extracted" -xzf "$temp_dir/fbox-creds.tar.gz"

  for rel_path in "${FBOX_CREDENTIAL_PATHS[@]}"; do
    local source_path="$temp_dir/extracted/$rel_path"
    local target_path="$HOME/$rel_path"
    if [[ ! -f "$source_path" ]]; then
      echo "Archiv ist unvollstaendig, es fehlt: $rel_path" >&2
      exit 1
    fi
    mkdir -p "$(dirname "$target_path")"
    cp "$source_path" "$target_path"
    chmod 600 "$target_path"
  done
}

main() {
  parse_args "$@"
  validate_inputs
  guard_overwrite

  local temp_dir
  temp_dir="$(mktemp -d)"
  trap 'rm -rf "$temp_dir"' EXIT
  mkdir -p "$temp_dir/extracted"

  restore_credentials "$temp_dir"
  echo "Credential-Dateien wurden nach \$HOME wiederhergestellt."
}

main "$@"
