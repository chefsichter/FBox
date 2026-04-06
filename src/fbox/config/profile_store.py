"""
Profile Store - Read and write named profiles in config.toml

Functions for managing named profiles without external TOML write libraries.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from fbox.config.settings import (
    CONFIG_FIELD_ORDER,
    DEFAULT_PROFILE_KEY,
    iter_ordered_config_items,
)

# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


def _load_payload(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    with config_path.open("rb") as fh:
        return tomllib.load(fh)


def get_profile_names(config_path: Path) -> list[str]:
    payload = _load_payload(config_path)
    return list(payload.get("profiles", {}).keys())


def get_default_profile_name(config_path: Path) -> str:
    payload = _load_payload(config_path)
    return str(payload.get(DEFAULT_PROFILE_KEY, ""))


def get_profile_overrides(config_path: Path, name: str) -> dict[str, object]:
    payload = _load_payload(config_path)
    return dict(payload.get("profiles", {}).get(name, {}))


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


def set_default_profile(config_path: Path, name: str) -> None:
    payload = _load_payload(config_path)
    profiles = dict(payload.get("profiles", {}))
    base_values = {
        k: v for k, v in payload.items() if k not in ("profiles", DEFAULT_PROFILE_KEY)
    }
    default_profile = name
    config_path.write_text(
        render_full_config(base_values, profiles, default_profile),
        encoding="utf-8",
    )


def upsert_profile(config_path: Path, name: str, overrides: dict[str, object]) -> None:
    payload = _load_payload(config_path)
    profiles = dict(payload.get("profiles", {}))
    profiles[name] = overrides
    base_values = {
        k: v for k, v in payload.items() if k not in ("profiles", DEFAULT_PROFILE_KEY)
    }
    default_profile = str(payload.get(DEFAULT_PROFILE_KEY, ""))
    config_path.write_text(
        render_full_config(base_values, profiles, default_profile),
        encoding="utf-8",
    )


def delete_profile(config_path: Path, name: str) -> None:
    payload = _load_payload(config_path)
    profiles = dict(payload.get("profiles", {}))
    profiles.pop(name, None)
    base_values = {
        k: v for k, v in payload.items() if k not in ("profiles", DEFAULT_PROFILE_KEY)
    }
    default_profile = str(payload.get(DEFAULT_PROFILE_KEY, ""))
    # If the deleted profile was the default, clear the default
    if default_profile == name:
        default_profile = ""
    config_path.write_text(
        render_full_config(base_values, profiles, default_profile),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# TOML rendering (no external library)
# ---------------------------------------------------------------------------


def _render_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, list):
        items = ", ".join(_render_value(item) for item in value)
        return f"[{items}]"
    # String
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


_PREVIEW_FIELDS = CONFIG_FIELD_ORDER


def format_full_profile_config(
    name: str, overrides: dict[str, Any], merged: object
) -> str:
    """Vollstaendige Konfiguration — mit Profil ueberschriebene Felder mit * markiert.

    merged ist eine AppConfig-Instanz (Basis + Profil zusammengefuehrt).
    overrides ist das reine Profil-Dict (nur die ueberschriebenen Felder).
    Leeres overrides-Dict → kein * → zeigt reine Basis-Konfiguration.
    """
    width = max(len(f) for f in _PREVIEW_FIELDS)
    lines = [f"\n  [{name}]  (* = Profilwert):"]
    for fname in _PREVIEW_FIELDS:
        value = getattr(merged, fname)
        marker = "* " if fname in overrides else "  "
        lines.append(f"  {marker}{fname:<{width}} = {_render_value(value)}")
    return "\n".join(lines)


def format_profile_overrides(name: str, overrides: dict[str, Any]) -> str:
    """Gibt Profilinhalt als lesbaren String zurueck."""
    lines = [f"  [{name}]"]
    if not overrides:
        lines.append("  (keine Einstellungen - entspricht Basis-Konfiguration)")
    else:
        ordered_overrides = iter_ordered_config_items(overrides)
        width = max(len(k) for k, _ in ordered_overrides)
        for k, v in ordered_overrides:
            lines.append(f"  {k:<{width}} = {_render_value(v)}")
    return "\n".join(lines)


def render_full_config(
    base_values: dict[str, object],
    profiles: dict[str, dict[str, object]],
    default_profile: str,
) -> str:
    lines: list[str] = []

    lines.append("# fbox runtime defaults")
    lines.append("# Diese Datei kannst du spaeter mit `fbox --config` bearbeiten.")
    lines.append("")

    # default_profile key first
    lines.append(f"{DEFAULT_PROFILE_KEY} = {_render_value(default_profile)}")
    lines.append("")

    # Base key-value pairs
    for key, value in iter_ordered_config_items(base_values):
        lines.append(f"{key} = {_render_value(value)}")
    lines.append("")

    # Profile sections
    for profile_name, overrides in profiles.items():
        lines.append(f"[profiles.{profile_name}]")
        for key, value in iter_ordered_config_items(overrides):
            lines.append(f"{key} = {_render_value(value)}")
        lines.append("")

    return "\n".join(lines)
