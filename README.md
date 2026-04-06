# fbox

Persistente Docker-Arbeitsboxen: pro Projekt ein Container, sicher gemountet und global aufrufbar.

`fbox` startet einen bestehenden Container oder erstellt einen neuen, mit sicheren Mount-Defaults,
editierbarer Konfiguration und AMD/NVIDIA-GPU-Unterstuetzung.

---

## Installation

Linux / Ubuntu:

```bash
cd /path/to/fbox
./scripts/install_ubuntu.sh
```

Windows PowerShell:

```powershell
cd C:\path\to\fbox
.\scripts\install_windows.ps1
```

Der Installer fragt interaktiv die wichtigsten Einstellungen ab und richtet alles ein:

- `~/.config/fbox/config.toml` als globale Konfiguration
- `.venv/` als repo-lokale virtuelle Umgebung
- `~/.local/bin/fbox` als globales Wrapper-Skript

Da der Wrapper auf das repo-lokale editable Install zeigt, werden Aenderungen am Code sofort
beim naechsten `fbox`-Aufruf wirksam.

Hinweis fuer Windows:
Das PowerShell-Skript startet nur den Python-Installer. Der erzeugte Wrapper-Pfad bleibt eine
Einstellung aus der fbox-Konfiguration und ist derzeit weiterhin auf Unix-Pfade ausgerichtet.

### Entfernen

Linux / Ubuntu:

```bash
./scripts/uninstall_ubuntu.sh
```

Windows PowerShell:

```powershell
.\scripts\uninstall_windows.ps1
```

---

## Verwendung

```text
usage: fbox [PFAD|NAME] [-p PROFIL]
       fbox ls | inspect ID | rm ID | commit
       fbox profiles ls | default PID | new | edit PID | rm PID
```

### Container starten oder erstellen

```bash
fbox                        # aktuelles Verzeichnis als Projekt
fbox /pfad/zum/projekt      # bestimmtes Verzeichnis
fbox mein-container         # bekannten Container direkt oeffnen
```

Beim ersten Mal wird nach dem Profil, einem Container-Namen und optionalen Extra-Mounts gefragt.
Danach wird der Container bei jedem Aufruf direkt geoeffnet.

### Profile

```bash
fbox profiles ls           # Profile anzeigen
fbox profiles default 2    # Standard-Profil setzen
fbox profiles new          # Profil anlegen
fbox profiles edit 2       # Profil bearbeiten
fbox profiles rm 2         # Profil loeschen
fbox pf ls                 # Kurzform fuer profiles
```

### Container verwalten

```bash
fbox ls                     # alle bekannten Container auflisten (mit ID)
fbox rm 2                   # Container mit ID 2 loeschen
fbox commit                 # aktuellen/verknuepften Container als neues Image sichern
```

`fbox commit` nimmt standardmaessig den Container des aktuellen Verzeichnisses.
Falls dort keiner bekannt ist, kannst du per PID aus der Liste oder per Containername
einen anderen waehlen. Das Ziel-Image wird immer versioniert vorgeschlagen
(`v0.0.1` oder bei bestehendem `vX.Y.Z` als `patch` / `minor` / `major`), und
anschliessend kannst du optional ein Profil in `config.toml` auf das neue
`default_image` umstellen oder ein neues Profil dafuer anlegen.

### Konfiguration

```bash
fbox -c                     # Konfigurationsdatei im Editor oeffnen
fbox -d                     # Diagnose: Pfade, Config, Container-Status, docker-create-Preview
```

### Optionen

| Option | Beschreibung |
|---|---|
| `-p, --profile` | Profil fuer diesen Aufruf direkt vorgeben |
| `-c, --config` | Konfiguration im Editor oeffnen |
| `-d, --debug` | Diagnose-Informationen anzeigen |
| `-h, --help` | Hilfe anzeigen |

---

## Konfiguration

Die aktive Konfiguration liegt unter `~/.config/fbox/config.toml`.

```toml
default_image = "ubuntu:24.04"
default_shell = "/bin/bash"
default_network = "bridge"
root_mode = "root"            # root | host-user
gpu_vendor = "none"           # none | nvidia | amd
workspace_readonly = false
extra_mounts_readonly = true
extra_mounts = []             # z.B. ["~/.cache/huggingface:/root/.cache/huggingface:rw"]
tmpfs = "/tmp:rw,noexec,nosuid"
memory_limit = ""             # z.B. "4g", "" = kein Limit
pids_limit = 0                # 0 = kein Limit
extra_flags = []
editor_command = "code --wait"
install_wrapper_path = "~/.local/bin/fbox"
```

### GPU-Unterstuetzung

| `gpu_vendor` | Effekt |
|---|---|
| `"none"` | Kein GPU-Zugriff |
| `"nvidia"` | `--gpus all` (nvidia-container-toolkit erforderlich) |
| `"amd"` | `--device=/dev/kfd --device=/dev/dri` + GIDs von `render`/`video` |

### Mounts

| Pfad im Container | Quelle |
|---|---|
| `/workspace` | Projektverzeichnis (standardmaessig schreibbar) |
| `/extra/<dirname>` | Zusatz-Mounts ohne explizites Ziel (Fallback) |

Extra-Mounts koennen global oder pro Profil in `config.toml` definiert werden:

```toml
extra_mounts = [
    "~/.cache/huggingface:/root/.cache/huggingface:rw",
    "~/models:/models",
]
```

Format: `quelle:ziel[:rw|ro]`

| Format | Ziel | Read-only |
|---|---|---|
| `~/pfad` | `/extra/<dirname>` | gem. `extra_mounts_readonly` |
| `~/pfad:/ziel` | `/ziel` | gem. `extra_mounts_readonly` |
| `~/pfad:/ziel:ro` | `/ziel` | ja (immer) |
| `~/pfad:/ziel:rw` | `/ziel` | nein (immer) |

Beim Erstellen eines Containers werden Config-Mounts automatisch eingebunden.
Der interaktive Prompt fragt danach noch nach containerspezifischen Zusatz-Mounts.

---

## Sicherheits-Defaults

Jeder Container wird mit diesen Einschraenkungen erstellt:

- `--cap-drop ALL` entzieht alle Linux Capabilities
- `--security-opt no-new-privileges` verhindert Privilege Escalation
- `--tmpfs /tmp:rw,noexec,nosuid` legt `/tmp` im RAM an und macht es nicht ausfuehrbar
- Netzwerk ist konfigurierbar (`bridge` / `none` / `host`)

---

## Architektur

```text
fbox/
|-- scripts/
|   |-- install_ubuntu.sh
|   |-- uninstall_ubuntu.sh
|   |-- install_windows.ps1
|   `-- uninstall_windows.ps1
|-- pyproject.toml
|-- config/
|   `-- fbox.example.toml
|-- src/fbox/
|   |-- cli/              # Argument-Parsing, Prompts, Orchestrierung, Status-Views
|   |-- config/           # XDG-Pfade, TOML laden, Editor oeffnen
|   |-- containers/       # Docker-Befehlsbau, Target-Aufloesung
|   |-- install/          # Installer-Logik, venv-Setup, Wrapper-Erzeugung
|   `-- state/            # JSON-State fuer bekannte Container
`-- tests/
```

### Laufzeit-Ablauf

```text
fbox starten
   |
   +--> ls / rm / --config / --debug  -> direkt ausgeben und beenden
   |
   v
Config laden (~/.config/fbox/config.toml)
   |
   v
Ziel aufloesen (Pfad oder Container-Name)
   |
   +--> bekannter Container gefunden  -> starten + Shell oeffnen
   |
   v
Name + Extra-Mounts abfragen
   |
   v
docker create (mit Config-Flags)
   |
   v
Container starten + Shell oeffnen (docker exec -it)
```

---

## FAQ

**Warum ein repo-lokales `.venv`?**
Die Installation ist selbst gekapselt. Der Wrapper zeigt auf den repo-lokalen Interpreter,
ohne Eingriff ins System-Python.

**Warum editable install?**
Aenderungen im Repo wirken beim naechsten `fbox`-Aufruf sofort, ohne Neuinstallation.

**Warum sind Extra-Mounts read-only?**
Das ist der sichere Default fuer persoenliche Daten. Das Projekt-Mount (`/workspace`)
bleibt schreibbar.

**Wie aendere ich Einstellungen nachtraeglich?**

```bash
fbox -c
```

**Was passiert wenn ein Container fehlt aber noch im State ist?**
`fbox` erkennt das automatisch, bereinigt den State und erstellt beim naechsten Aufruf
einen neuen Container.
