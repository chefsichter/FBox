"""
Interactive Configurator - Ask installer questions and render config.toml

Architecture:
    ┌─────────────────────────────────────────┐
    │  interactive_configurator.py            │
    │  ┌───────────────────────────────────┐  │
    │  │  Prompt helpers                  │  │
    │  │  → bools, choices, strings       │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  Config questionnaire            │  │
    │  │  → installer defaults            │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  TOML rendering                  │  │
    │  │  → editable config file          │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from fbox.install.interactive_configurator import build_config_interactively

    rendered, install_wrapper = build_config_interactively(Path.cwd())
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from fbox.config.profile_store import (
    format_full_profile_config,
    render_full_config,
)
from fbox.config.settings import EXAMPLE_CONFIG_PATH, AppConfig, _apply_overrides

_DEFAULT_WRAPPER_PATH = (
    "~/.local/bin/fbox.cmd" if sys.platform == "win32" else "~/.local/bin/fbox"
)


def ask(prompt: str, default: str) -> str:
    try:
        answer = input(f"{prompt} [{default}]: ").strip()
    except EOFError:
        return default
    return answer or default


def ask_bool(prompt: str, default: bool) -> bool:
    default_text = "y" if default else "n"
    while True:
        try:
            answer = input(f"{prompt} [y/n, default {default_text}]: ").strip().lower()
        except EOFError:
            return default
        if not answer:
            return default
        if answer in {"y", "yes", "j", "ja"}:
            return True
        if answer in {"n", "no", "nein"}:
            return False
        print("Bitte y oder n eingeben.")


def ask_flags(prompt: str, default: list) -> list:
    default_str = " ".join(default)
    try:
        answer = input(f"{prompt} [{default_str or 'keine'}]: ").strip()
    except EOFError:
        return default
    if not answer:
        return default
    return answer.split()


def ask_choice(prompt: str, default: str, options: list[str]) -> str:
    option_text = "/".join(options)
    while True:
        try:
            answer = (
                input(f"{prompt} [{option_text}, default {default}]: ").strip().lower()
            )
        except EOFError:
            return default
        if not answer:
            return default
        if answer in options:
            return answer
        print(f"Bitte eine dieser Optionen waehlen: {option_text}")


def _values_from_config(d: AppConfig) -> dict[str, object]:
    """Baut das values-Dict aus einer AppConfig ohne interaktive Fragen."""
    return {
        "default_image": d.default_image,
        "default_shell": d.default_shell,
        "default_network": d.default_network,
        "gpu_vendor": d.gpu_vendor,
        "root_mode": d.root_mode,
        "extra_mounts_readonly": d.extra_mounts_readonly,
        "workspace_readonly": d.workspace_readonly,
        "container_tmpfs_size": d.container_tmpfs_size,
        "build_tmpfs": d.build_tmpfs,
        "memory_limit": d.memory_limit,
        "pids_limit": d.pids_limit,
        "extra_flags": d.extra_flags,
        "editor_command": "code --wait",
        "install_wrapper_path": _DEFAULT_WRAPPER_PATH,
    }


def build_config_interactively(default_target: Path) -> tuple[str, str]:
    example_profiles = _load_example_profiles()
    chosen_profile, d, direct = _ask_base_profile(example_profiles)

    if direct:
        values = _values_from_config(d)
    else:
        values = {
            "default_image": ask("Docker-Image fuer neue Container", d.default_image),
            "default_shell": ask("Shell fuer `docker exec`", d.default_shell),
            "default_network": ask_choice(
                "Netzwerk-Standard fuer neue Container",
                d.default_network,
                ["none", "bridge", "host"],
            ),
            "gpu_vendor": ask_choice(
                "GPU-Hersteller (none = keine GPU, nvidia = CUDA, amd = ROCm)",
                d.gpu_vendor,
                ["none", "nvidia", "amd"],
            ),
            "root_mode": ask_choice(
                "Container standardmaessig als root oder mit deinem Host-User starten",
                d.root_mode,
                ["root", "host-user"],
            ),
            "extra_mounts_readonly": ask_bool(
                "Zusatz-Mounts standardmaessig read-only einhaengen",
                d.extra_mounts_readonly,
            ),
            "workspace_readonly": ask_bool(
                "Workspace read-only einhaengen",
                d.workspace_readonly,
            ),
            "container_tmpfs_size": ask(
                "Groesse von /tmp im Container (leer = unbegrenzt)",
                d.container_tmpfs_size,
            ),
            "build_tmpfs": ask(
                "Build-tmpfs Spec (leer = deaktiviert, z.B. /build-tmp:rw,exec,nosuid)",
                d.build_tmpfs,
            ),
            "memory_limit": ask(
                "Speicher-Limit fuer Container (leer = unbegrenzt, z.B. 4g)",
                d.memory_limit,
            ),
            "pids_limit": int(
                ask("PID-Limit fuer Container (0 = unbegrenzt)", str(d.pids_limit))
            ),
            "extra_flags": ask_flags(
                "Zusaetzliche Docker-Flags (z.B. --cap-add CHOWN --cap-add FOWNER)",
                d.extra_flags,
            ),
            "editor_command": ask("Editor fuer `fbox --config`", "code --wait"),
            "install_wrapper_path": _DEFAULT_WRAPPER_PATH,
        }

    rendered = render_full_config(values, example_profiles, chosen_profile)
    return rendered, _DEFAULT_WRAPPER_PATH


def _load_example_profiles() -> dict[str, dict]:
    if not EXAMPLE_CONFIG_PATH.exists():
        return {}
    with EXAMPLE_CONFIG_PATH.open("rb") as fh:
        payload = tomllib.load(fh)
    return dict(payload.get("profiles", {}))


def _ask_base_profile(
    profiles: dict[str, dict],
) -> tuple[str, AppConfig, bool]:
    """Nummerierte Auswahl mit Preview und Direkt-Übernahme.

    Gibt (profilname, AppConfig, direct) zurueck.
    direct=True  → Profil direkt uebernehmen, kein Fragebogen
    direct=False → Fragebogen mit Profil-Werten als Defaults
    """
    if not profiles:
        return "", AppConfig(), False

    names = list(profiles.keys())

    def _show_list() -> None:
        print("\nVerfuegbare Profile:")
        print("  [0] default")
        for i, name in enumerate(names, 1):
            print(f"  [{i}] {name}")

    _show_list()

    while True:
        try:
            raw = input(
                "\nProfil anzeigen (PID) oder Enter fuer Auswahl: "
            ).strip()
        except EOFError:
            break

        if not raw:
            break  # → direkt zur Kurzauswahl

        try:
            pid = int(raw)
        except ValueError:
            print("  Bitte eine Zahl eingeben.")
            continue

        base = AppConfig()
        if pid == 0:
            print(format_full_profile_config("default", {}, base))
            action = ask_choice("Aktion (u=uebernehmen / z=zurueck)", "u", ["u", "z"])
            if action == "u":
                return "", base, True
            _show_list()
            continue

        if not (1 <= pid <= len(names)):
            print(f"  Unbekannte PID: {pid}")
            continue

        name = names[pid - 1]
        merged = _apply_overrides(base, profiles[name])
        print(format_full_profile_config(name, profiles[name], merged))
        action = ask_choice(
            "Aktion (u=uebernehmen / b=bearbeiten / z=zurueck)",
            "u",
            ["u", "b", "z"],
        )
        if action == "u":
            # Basis bleibt AppConfig-Defaults, Profil wirkt als Runtime-Override
            return name, base, True
        if action == "b":
            # Fragebogen mit Profil-Werten als Defaults
            return name, merged, False
        _show_list()

    # Enter ohne Preview → Kurzauswahl
    pids = ["0"] + [str(i) for i in range(1, len(names) + 1)]
    choice = ask_choice("Profil als Basis und Standard", "0", pids)
    pid = int(choice)
    if pid == 0:
        return "", AppConfig(), False
    name = names[pid - 1]
    merged = _apply_overrides(AppConfig(), profiles[name])
    return name, merged, False


def choose_install_action(has_existing_installation: bool) -> str:
    if not has_existing_installation:
        return "install"
    shortcuts = {
        "i": "install",
        "r": "reinstall",
        "u": "uninstall",
        "a": "abort",
    }
    option_text = "install(i)/reinstall(r)/uninstall(u)/abort(a)"
    while True:
        try:
            answer = (
                input(
                    "Bestehende fbox-Installation erkannt. Aktion waehlen "
                    f"[{option_text}, default reinstall]: "
                )
                .strip()
                .lower()
            )
        except EOFError:
            return "reinstall"
        if not answer:
            return "reinstall"
        if answer in {"install", "reinstall", "uninstall", "abort"}:
            return answer
        if answer in shortcuts:
            return shortcuts[answer]
        print("Bitte install/reinstall/uninstall/abort oder i/r/u/a eingeben.")


def render_config_toml(values: dict[str, str | bool | int]) -> str:
    lines = [
        "# fbox runtime defaults",
        "# Diese Datei kannst du spaeter mit `fbox --config` bearbeiten.",
        "",
    ]
    for key, value in values.items():
        if value is True:
            rendered_value = "true"
        elif value is False:
            rendered_value = "false"
        elif isinstance(value, int):
            rendered_value = str(value)
        else:
            rendered_value = f'"{value}"'
        lines.append(f"{key} = {rendered_value}")
    lines.append("")
    return "\n".join(lines)


def build_profile_interactively(
    name: str, base: AppConfig, compare_base: AppConfig | None = None
) -> dict[str, object]:
    """Ask profile configuration questions and return only the overriding fields.

    base        – used as defaults for the interactive questions (what the user sees)
    compare_base – used for comparison to determine which fields to save as overrides;
                   defaults to base. For editing, pass the original base config (without
                   profile applied) so that all profile-specific values are preserved.
    """
    if compare_base is None:
        compare_base = base
    questions: dict[str, object] = {
        "default_image": ask(
            "Docker-Image fuer neue Container",
            base.default_image,
        ),
        "default_shell": ask(
            "Shell fuer `docker exec`",
            base.default_shell,
        ),
        "default_network": ask_choice(
            "Netzwerk-Standard fuer neue Container",
            base.default_network,
            ["none", "bridge", "host"],
        ),
        "gpu_vendor": ask_choice(
            "GPU-Hersteller (none = keine GPU, nvidia = CUDA, amd = ROCm)",
            base.gpu_vendor,
            ["none", "nvidia", "amd"],
        ),
        "root_mode": ask_choice(
            "Container standardmaessig als root oder mit deinem Host-User starten",
            base.root_mode,
            ["root", "host-user"],
        ),
        "extra_mounts_readonly": ask_bool(
            "Zusatz-Mounts standardmaessig read-only einhaengen",
            base.extra_mounts_readonly,
        ),
        "workspace_readonly": ask_bool(
            "Workspace read-only einhaengen",
            base.workspace_readonly,
        ),
        "container_tmpfs_size": ask(
            "Groesse von /tmp im Container (leer = unbegrenzt)",
            base.container_tmpfs_size,
        ),
        "build_tmpfs": ask(
            "Build-tmpfs Spec (leer = deaktiviert, z.B. /build-tmp:rw,exec,nosuid)",
            base.build_tmpfs,
        ),
        "memory_limit": ask(
            "Speicher-Limit fuer Container (leer = unbegrenzt, z.B. 4g)",
            base.memory_limit,
        ),
        "pids_limit": int(
            ask("PID-Limit fuer Container (0 = unbegrenzt)", str(base.pids_limit))
        ),
        "extra_flags": ask_flags(
            "Zusaetzliche Docker-Flags (z.B. --cap-add CHOWN --cap-add FOWNER)",
            base.extra_flags,
        ),
    }
    # Return only fields that differ from compare_base (original base without profile)
    overrides: dict[str, object] = {}
    base_dict = {
        "default_image": compare_base.default_image,
        "default_shell": compare_base.default_shell,
        "default_network": compare_base.default_network,
        "gpu_vendor": compare_base.gpu_vendor,
        "root_mode": compare_base.root_mode,
        "extra_mounts_readonly": compare_base.extra_mounts_readonly,
        "workspace_readonly": compare_base.workspace_readonly,
        "container_tmpfs_size": compare_base.container_tmpfs_size,
        "build_tmpfs": compare_base.build_tmpfs,
        "memory_limit": compare_base.memory_limit,
        "pids_limit": compare_base.pids_limit,
        "extra_flags": compare_base.extra_flags,
    }
    for key, value in questions.items():
        if value != base_dict[key]:
            overrides[key] = value
    return overrides
