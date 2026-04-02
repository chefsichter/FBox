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

from fbox.config.profile_store import render_full_config
from fbox.config.settings import EXAMPLE_CONFIG_PATH, AppConfig

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


def build_config_interactively(default_target: Path) -> tuple[str, str]:
    values: dict[str, str | bool] = {
        "default_image": ask("Docker-Image fuer neue Container", "ubuntu:24.04"),
        "default_shell": ask("Shell fuer `docker exec`", "/bin/bash"),
        "default_network": ask_choice(
            "Netzwerk-Standard fuer neue Container",
            "bridge",
            ["none", "bridge", "host"],
        ),
        "gpu_vendor": ask_choice(
            "GPU-Hersteller (none = keine GPU, nvidia = CUDA, amd = ROCm)",
            "none",
            ["none", "nvidia", "amd"],
        ),
        "root_mode": ask_choice(
            "Container standardmaessig als root oder mit deinem Host-User starten",
            "root",
            ["root", "host-user"],
        ),
        "extra_mounts_readonly": ask_bool(
            "Zusatz-Mounts standardmaessig read-only einhaengen",
            True,
        ),
        "workspace_readonly": False,
        "container_tmpfs_size": ask(
            "Groesse von /tmp im Container (leer = unbegrenzt)",
            "",
        ),
        "memory_limit": ask(
            "Speicher-Limit fuer Container (leer = unbegrenzt, z.B. 4g)",
            "",
        ),
        "pids_limit": int(
            ask("PID-Limit fuer Container (0 = unbegrenzt)", "0")
        ),
        "editor_command": ask("Editor fuer `fbox --config`", "code --wait"),
        "install_wrapper_path": _DEFAULT_WRAPPER_PATH,
    }
    wrapper_path = _DEFAULT_WRAPPER_PATH

    example_profiles = _load_example_profiles()
    default_profile = _ask_default_profile(example_profiles)

    rendered = render_full_config(
        dict(values),
        example_profiles,
        default_profile,
    )
    return rendered, wrapper_path


def _load_example_profiles() -> dict[str, dict]:
    if not EXAMPLE_CONFIG_PATH.exists():
        return {}
    with EXAMPLE_CONFIG_PATH.open("rb") as fh:
        payload = tomllib.load(fh)
    return dict(payload.get("profiles", {}))


def _ask_default_profile(profiles: dict[str, dict]) -> str:
    if not profiles:
        return ""
    names = list(profiles.keys())
    options = names + ["none"]
    choice = ask_choice(
        f"Standard-Profil ({', '.join(names)})",
        "none",
        options,
    )
    return "" if choice == "none" else choice


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


def build_profile_interactively(name: str, base: AppConfig) -> dict[str, object]:
    """Ask profile configuration questions and return only the overriding fields."""
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
        "memory_limit": ask(
            "Speicher-Limit fuer Container (leer = unbegrenzt, z.B. 4g)",
            base.memory_limit,
        ),
        "pids_limit": int(
            ask("PID-Limit fuer Container (0 = unbegrenzt)", str(base.pids_limit))
        ),
    }
    # Return only fields that differ from base
    overrides: dict[str, object] = {}
    base_dict = {
        "default_image": base.default_image,
        "default_shell": base.default_shell,
        "default_network": base.default_network,
        "gpu_vendor": base.gpu_vendor,
        "root_mode": base.root_mode,
        "extra_mounts_readonly": base.extra_mounts_readonly,
        "workspace_readonly": base.workspace_readonly,
        "container_tmpfs_size": base.container_tmpfs_size,
        "memory_limit": base.memory_limit,
        "pids_limit": base.pids_limit,
    }
    for key, value in questions.items():
        if value != base_dict[key]:
            overrides[key] = value
    return overrides
