# Usage

## Install On Ubuntu

```bash
cd /home/chefsichter/Dokumente/fbox
./install_ubuntu.sh
```

The installer:
- creates `~/.config/fbox/config.toml`
- creates repo-local `.venv/`
- installs the package editable into that `.venv`
- writes a global wrapper script, default `~/.local/bin/fbox`

## Daily Commands

```bash
fbox
fbox /path/to/project
fbox my-existing-container
fbox --config
fbox --print-config-path
```

## Important Behavior

- The project directory is mounted to `/workspace`.
- Additional mounts go to `/extra/<dirname>`.
- Containers persist and are reused on the next day.
- Repo code changes are picked up immediately because the wrapper runs the repo-local editable install.
