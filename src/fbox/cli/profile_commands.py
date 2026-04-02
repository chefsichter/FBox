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
    get_default_profile_name,
    get_profile_names,
    get_profile_overrides,
    set_default_profile,
    upsert_profile,
)
from fbox.config.settings import AppConfig
from fbox.install.interactive_configurator import build_profile_interactively


def cmd_profile_ls(config_path: Path) -> int:
    names = get_profile_names(config_path)
    default = get_default_profile_name(config_path)
    if not names:
        print("Keine Profile vorhanden.")
        return 0
    for name in names:
        marker = " (default)" if name == default else ""
        print(f"  {name}{marker}")
    if default and default not in names:
        print(f"  (default_profile = '{default}', aber kein solches Profil gefunden)")
    return 0


def cmd_profile_set_default(config_path: Path, name: str) -> int:
    if name == "none" or name == "":
        set_default_profile(config_path, "")
        print("Standard-Profil zurueckgesetzt (kein Profil).")
        return 0
    names = get_profile_names(config_path)
    if name not in names:
        print(f"fbox: Profil '{name}' existiert nicht.", file=sys.stderr)
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


def cmd_profile_edit(config_path: Path, name: str, base_config: AppConfig) -> int:
    existing = get_profile_names(config_path)
    if name not in existing:
        print(f"fbox: Profil '{name}' existiert nicht.", file=sys.stderr)
        return 1
    # Build an AppConfig that reflects current overrides so they appear as defaults
    from fbox.config.settings import _apply_overrides
    current_overrides = get_profile_overrides(config_path, name)
    effective_base = _apply_overrides(base_config, current_overrides)
    overrides = build_profile_interactively(name, effective_base)
    upsert_profile(config_path, name, overrides)
    print(f"Profil '{name}' aktualisiert.")
    return 0


def cmd_profile_rm(config_path: Path, name: str) -> int:
    existing = get_profile_names(config_path)
    if name not in existing:
        print(f"fbox: Profil '{name}' existiert nicht.", file=sys.stderr)
        return 1
    delete_profile(config_path, name)
    print(f"Profil '{name}' geloescht.")
    return 0
