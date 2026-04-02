# Architecture

## Layout

```text
fbox/
├─ install_ubuntu.sh
├─ pyproject.toml
├─ README.md
├─ config/
│  └─ fbox.example.toml
├─ docs/
│  ├─ architecture.md
│  ├─ faq.md
│  └─ usage.md
├─ src/
│  └─ fbox/
│     ├─ cli/
│     ├─ config/
│     ├─ containers/
│     ├─ install/
│     └─ state/
└─ tests/
```

## Module Responsibilities

- `fbox.cli`: CLI parsing, interactive prompts, orchestration.
- `fbox.config`: XDG paths, TOML config loading, editing.
- `fbox.containers`: Docker command generation and target resolution.
- `fbox.install`: interactive installer, local `.venv`, wrapper creation.
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
