from fbox.install.interactive_configurator import choose_install_action


def test_choose_install_action_accepts_shortcuts(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "u")

    result = choose_install_action(True)

    assert result == "uninstall"


def test_choose_install_action_uses_default_on_empty_input(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "")

    result = choose_install_action(True)

    assert result == "reinstall"
