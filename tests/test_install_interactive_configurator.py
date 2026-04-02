from pathlib import Path

from fbox.install.interactive_configurator import build_config_interactively


def test_build_config_interactively_uses_defaults_on_eof(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(EOFError()))

    rendered, wrapper_path = build_config_interactively(Path("/tmp/demo"))

    assert "allow_all_gpus = true" in rendered
    assert 'install_wrapper_path = "~/.local/bin/fbox"' in rendered
    assert wrapper_path == "~/.local/bin/fbox"
