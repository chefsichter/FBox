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

from pathlib import Path


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
        "allow_all_gpus": ask_bool(
            "Alle GPUs standardmaessig in neue Container durchreichen",
            True,
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
        "editor_command": ask("Editor fuer `fbox --config`", "code --wait"),
        "install_wrapper_path": ask(
            "Pfad fuer den globalen `fbox`-Starter",
            "~/.local/bin/fbox",
        ),
    }
    wrapper_path = str(values["install_wrapper_path"])
    return render_config_toml(values), wrapper_path


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
            answer = input(
                "Bestehende fbox-Installation erkannt. Aktion waehlen "
                f"[{option_text}, default reinstall]: "
            ).strip().lower()
        except EOFError:
            return "reinstall"
        if not answer:
            return "reinstall"
        if answer in {"install", "reinstall", "uninstall", "abort"}:
            return answer
        if answer in shortcuts:
            return shortcuts[answer]
        print("Bitte install/reinstall/uninstall/abort oder i/r/u/a eingeben.")


def render_config_toml(values: dict[str, str | bool]) -> str:
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
        else:
            rendered_value = f'"{value}"'
        lines.append(f"{key} = {rendered_value}")
    lines.append("")
    return "\n".join(lines)
