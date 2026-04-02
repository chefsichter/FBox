# FAQ

## Why a repo-local `.venv`?

It keeps the installation self-contained. The wrapper script points to the repo-local interpreter, so `fbox` remains callable globally without polluting the system Python.

## Why editable install?

The wrapper uses the package installed from this repo in editable mode. If you change code in the repo, the next `fbox` run uses that code.

## Why are additional mounts read-only by default?

That is the safer default for personal data. The project mount stays writable so you can work normally inside `/workspace`.

## How do I change defaults later?

Run `fbox --config` or edit the path from `fbox --print-config-path`.
