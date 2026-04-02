from pathlib import Path

from fbox.config.settings import load_config


def test_load_config_reads_toml_values(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                'default_image = "nvidia/cuda:12.4.1-base-ubuntu24.04"',
                "allow_all_gpus = false",
                'root_mode = "host-user"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.default_image == "nvidia/cuda:12.4.1-base-ubuntu24.04"
    assert config.allow_all_gpus is False
    assert config.root_mode == "host-user"
