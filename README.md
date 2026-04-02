# 📦 fbox

Persistente Docker-Arbeitsboxen — pro Projekt ein Container, sicher gemountet, global aufrufbar.

`fbox` startet einen bestehenden Container oder erstellt einen neuen — mit sicheren Mount-Defaults,
editierbarer Konfiguration und AMD/NVIDIA GPU-Unterstützung.

---

## 🚀 Installation

```bash
cd /path/to/fbox
./install_ubuntu.sh
```

Der Installer fragt interaktiv die wichtigsten Einstellungen ab und richtet alles ein:

- ✅ `~/.config/fbox/config.toml` — globale Konfiguration
- ✅ `.venv/` — repo-lokale virtuelle Umgebung
- ✅ `~/.local/bin/fbox` — globaler Wrapper-Skript

Da der Wrapper auf das repo-lokale editable Install zeigt, werden Änderungen am Code sofort beim nächsten `fbox`-Aufruf wirksam.

### Entfernen

```bash
./uninstall_ubuntu.sh
```

---

## 🛠️ Verwendung

```
usage: fbox [PFAD|NAME] [-i IMAGE]
       fbox ls
       fbox rm ID
```

### Container starten oder erstellen

```bash
fbox                        # aktuelles Verzeichnis als Projekt
fbox /pfad/zum/projekt      # bestimmtes Verzeichnis
fbox mein-container         # bekannten Container direkt öffnen
```

Beim ersten Mal wird nach einem Container-Namen und optionalen Extra-Mounts gefragt.
Danach wird der Container bei jedem Aufruf direkt geöffnet.

### Container verwalten

```bash
fbox ls                     # alle bekannten Container auflisten (mit ID)
fbox rm 2                   # Container mit ID 2 löschen
```

### Konfiguration

```bash
fbox -c                     # Konfigurationsdatei im Editor öffnen
fbox -d                     # Diagnose: Pfade, Config, Container-Status, docker-create-Preview
```

### Optionen

| Option | Beschreibung |
|---|---|
| `-i IMAGE` | Docker-Image für neue Container |
| `-c, --config` | Konfiguration im Editor öffnen |
| `-d, --debug` | Diagnose-Informationen anzeigen |
| `-h, --help` | Hilfe anzeigen |

---

## ⚙️ Konfiguration

Die aktive Konfiguration liegt unter `~/.config/fbox/config.toml`.

```toml
default_image = "ubuntu:24.04"
default_shell = "/bin/bash"
default_network = "bridge"
gpu_vendor = "none"           # none | nvidia | amd
root_mode = "root"            # root | host-user
extra_mounts_readonly = true
workspace_readonly = false
container_tmpfs_size = ""     # leer = unbegrenzt, z.B. "512m"
editor_command = "code --wait"
install_wrapper_path = "~/.local/bin/fbox"
```

### GPU-Unterstützung

| `gpu_vendor` | Effekt |
|---|---|
| `"none"` | Kein GPU-Zugriff |
| `"nvidia"` | `--gpus all` (nvidia-container-toolkit erforderlich) |
| `"amd"` | `--device=/dev/kfd --device=/dev/dri` + GIDs von `render`/`video` |

### Mounts

| Pfad im Container | Quelle |
|---|---|
| `/workspace` | Projektverzeichnis (standardmäßig schreibbar) |
| `/extra/<dirname>` | Zusatz-Mounts (standardmäßig read-only) |

---

## 🔒 Sicherheits-Defaults

Jeder Container wird mit diesen Einschränkungen erstellt:

- `--cap-drop ALL` — alle Linux Capabilities entzogen
- `--security-opt no-new-privileges` — keine Privilege-Escalation
- `--tmpfs /tmp:rw,noexec,nosuid` — `/tmp` im RAM, nicht ausführbar
- Netzwerk konfigurierbar (`bridge` / `none` / `host`)

---

## 🏗️ Architektur

```text
fbox/
├─ install_ubuntu.sh
├─ pyproject.toml
├─ config/
│  └─ fbox.example.toml
├─ src/fbox/
│  ├─ cli/              # Argument-Parsing, Prompts, Orchestrierung, Status-Views
│  ├─ config/           # XDG-Pfade, TOML laden, Editor öffnen
│  ├─ containers/       # Docker-Befehlsbau, Target-Auflösung
│  ├─ install/          # Installer, venv-Setup, Wrapper-Skript
│  └─ state/            # JSON-State für bekannte Container
└─ tests/
```

### Laufzeit-Ablauf

```
fbox starten
   │
   ├─▶ ls / rm / --config / --debug  →  direkt ausgeben und beenden
   │
   ▼
Config laden (~/.config/fbox/config.toml)
   │
   ▼
Ziel auflösen (Pfad oder Container-Name)
   │
   ├─▶ bekannter Container gefunden  →  starten + Shell öffnen
   │
   ▼
Name + Extra-Mounts abfragen
   │
   ▼
docker create (mit Config-Flags)
   │
   ▼
Container starten + Shell öffnen (docker exec -it)
```

---

## ❓ FAQ

**Warum ein repo-lokales `.venv`?**
Die Installation ist selbst-gekapselt. Der Wrapper zeigt auf den repo-lokalen Interpreter — kein Eingriff ins System-Python.

**Warum editable install?**
Änderungen im Repo wirken beim nächsten `fbox`-Aufruf sofort, ohne Neuinstallation.

**Warum sind Extra-Mounts read-only?**
Sicherer Default für persönliche Daten. Das Projekt-Mount (`/workspace`) bleibt schreibbar.

**Wie ändere ich Einstellungen nachträglich?**
```bash
fbox -c                         # öffnet ~/.config/fbox/config.toml im konfigurierten Editor
```

**Was passiert wenn ein Container fehlt aber noch im State ist?**
`fbox` erkennt das automatisch, bereinigt den State und erstellt beim nächsten Aufruf einen neuen Container.
