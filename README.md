# fbox

`fbox` startet oder erstellt pro Projektverzeichnis einen persistenten Docker-Container mit sicheren Mount-Defaults und editierbarer globaler Konfiguration.

## Quick Start

```bash
cd /home/chefsichter/Dokumente/fbox
./install_ubuntu.sh
```

Entfernen:

```bash
./uninstall_ubuntu.sh
```

Danach ist `fbox` global verfuegbar:

```bash
fbox
fbox <pfad>
fbox <container-name>
```

## What The Installer Does

- fragt die wichtigsten Sicherheits- und Laufzeit-Defaults ab
- erkennt bestehende Installationen und bietet `install`, `reinstall`, `uninstall` oder `abort`
- erstellt `~/.config/fbox/config.toml`
- erstellt eine repo-lokale `.venv`
- installiert das Paket editable in diese `.venv`
- legt einen globalen Wrapper an, standardmaessig `~/.local/bin/fbox`

Dadurch bleibt der Root-Folder klein, die Installation ist lokal gekapselt, und Aenderungen im Repo wirken sofort beim naechsten `fbox`-Start.

## Config

- Template: [fbox.example.toml](/home/chefsichter/Dokumente/fbox/config/fbox.example.toml)
- Aktive Datei: `~/.config/fbox/config.toml`
- Bearbeiten: `fbox --config`
- Pfad anzeigen: `fbox --print-config-path`

## Docs

- Architektur: [architecture.md](/home/chefsichter/Dokumente/fbox/docs/architecture.md)
- Nutzung: [usage.md](/home/chefsichter/Dokumente/fbox/docs/usage.md)
- FAQ: [faq.md](/home/chefsichter/Dokumente/fbox/docs/faq.md)
