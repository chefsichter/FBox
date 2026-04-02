"""
Profile Commands - CLI handlers for named profile management

Usage:
    from fbox.cli.profile_commands import cmd_profile_ls, cmd_profile_new
"""

from __future__ import annotations

import sys
from pathlib import Path

from fbox.config.profile_store import (
    delete_profile,
    format_full_profile_config,
    get_default_profile_name,
    get_profile_names,
    get_profile_overrides,
    set_default_profile,
    upsert_profile,
)
from fbox.config.settings import AppConfig, _apply_overrides, load_config
from fbox.install.interactive_configurator import build_profile_interactively


def _resolve_pid_or_name(names: list[str], pid_or_name: str) -> str | None:
    """PID (1-basiert) oder Name → Profilname, None wenn nicht gefunden."""
    try:
        pid = int(pid_or_name)
        if 1 <= pid <= len(names):
            return names[pid - 1]
        return None
    except ValueError:
        return pid_or_name if pid_or_name in names else None


def cmd_profile_ls(config_path: Path) -> int:
    names = get_profile_names(config_path)
    default = get_default_profile_name(config_path)

    # [0] default ist immer sichtbar
    default_active = not default or default not in names
    print(f"  {'*' if default_active else ' '} [0] default")
    for pid, name in enumerate(names, 1):
        marker = "*" if name == default else " "
        print(f"  {marker} [{pid}] {name}")
    if default and default not in names:
        print(f"  (default_profile = '{default}', aber kein solches Profil gefunden)")

    if not sys.stdin.isatty():
        return 0

    base = load_config(config_path, profile="none")

    while True:
        try:
            raw = input("\nProfil-Details anzeigen (PID, Enter zum Beenden): ").strip()
        except EOFError:
            break
        if not raw:
            break
        if raw == "0":
            print(format_full_profile_config("default", {}, base))
            continue
        name = _resolve_pid_or_name(names, raw)
        if name is None:
            print(f"  Unbekannte PID: {raw}")
            continue
        overrides = get_profile_overrides(config_path, name)
        merged = _apply_overrides(base, overrides)
        print(format_full_profile_config(name, overrides, merged))
    return 0


def cmd_profile_set_default(config_path: Path, pid_or_name: str) -> int:
    if pid_or_name in ("none", ""):
        set_default_profile(config_path, "")
        print("Standard-Profil zurueckgesetzt (kein Profil).")
        return 0
    names = get_profile_names(config_path)
    name = _resolve_pid_or_name(names, pid_or_name)
    if name is None:
        print(f"fbox: Profil '{pid_or_name}' nicht gefunden.", file=sys.stderr)
        return 1
    set_default_profile(config_path, name)
    print(f"Standard-Profil gesetzt: {name}")
    return 0


def cmd_profile_new(config_path: Path, base_config: AppConfig) -> int:
    try:
        name = input("Profilname: ").strip()
    except EOFError:
        print("\nAbgebrochen.", file=sys.stderr)
        return 1
    if not name:
        print("fbox: Profilname darf nicht leer sein.", file=sys.stderr)
        return 1
    existing = get_profile_names(config_path)
    if name in existing:
        print(
            f"fbox: Profil '{name}' existiert bereits. "
            f"Nutze 'fbox profile edit {name}'.",
            file=sys.stderr,
        )
        return 1
    overrides = build_profile_interactively(name, base_config)
    upsert_profile(config_path, name, overrides)
    print(f"Profil '{name}' erstellt.")
    return 0


def cmd_profile_edit(config_path: Path, pid_or_name: str, base_config: AppConfig) -> int:
    existing = get_profile_names(config_path)
    name = _resolve_pid_or_name(existing, pid_or_name)
    if name is None:
        print(f"fbox: Profil '{pid_or_name}' nicht gefunden.", file=sys.stderr)
        return 1
    from fbox.config.settings import _apply_overrides
    current_overrides = get_profile_overrides(config_path, name)
    effective_base = _apply_overrides(base_config, current_overrides)
    overrides = build_profile_interactively(name, effective_base, compare_base=base_config)
    upsert_profile(config_path, name, overrides)
    print(f"Profil '{name}' aktualisiert.")
    return 0


def cmd_profile_rm(config_path: Path, pid_or_name: str) -> int:
    existing = get_profile_names(config_path)
    name = _resolve_pid_or_name(existing, pid_or_name)
    if name is None:
        print(f"fbox: Profil '{pid_or_name}' nicht gefunden.", file=sys.stderr)
        return 1
    delete_profile(config_path, name)
    print(f"Profil '{name}' geloescht.")
    return 0
