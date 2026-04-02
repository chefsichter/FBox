# Architecture

## Layout

```text
fbox/
|-- scripts/
|   |-- install_ubuntu.sh
|   |-- uninstall_ubuntu.sh
|   |-- install_windows.ps1
|   `-- uninstall_windows.ps1
|-- pyproject.toml
|-- README.md
|-- config/
|   `-- fbox.example.toml
|-- docs/
|   |-- architecture.md
|   `-- faq.md
|-- src/
|   `-- fbox/
|       |-- cli/
|       |-- config/
|       |-- containers/
|       |-- install/
|       `-- state/
`-- tests/
```

## Module Responsibilities

- `scripts/`: repo-local entrypoints for Linux and Windows installation/uninstallation.
- `fbox.cli`: CLI parsing, interactive prompts, orchestration.
- `fbox.config`: XDG paths, TOML config loading, editing.
- `fbox.containers`: Docker command generation and target resolution.
- `fbox.install`: installer and uninstaller logic, local `.venv`, wrapper creation.
- `fbox.state`: persistent JSON state for known containers.

## Runtime Flow

```text
User runs fbox
   |
   v
Load config.toml
   |
   +--> --config / --print-config-path
   |
   v
Resolve target path or container name
   |
   +--> reuse existing container if known
   |
   v
Prompt for name + optional mounts
   |
   v
Build docker create args from config
   |
   v
Start container and open shell
```
