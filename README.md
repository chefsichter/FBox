# fbox

`fbox` startet oder erstellt pro Projektverzeichnis einen persistenten Docker-Container.

## Installation

```bash
python3 -m pip install -e .
```

Danach ist der Befehl verfuegbar:

```bash
fbox <pfad>
fbox
fbox <container-name>
```

Wenn kein Pfad angegeben wird, nutzt `fbox` das aktuelle Verzeichnis.

## Aktuelles Verhalten

- Beim ersten Start fuer ein Verzeichnis fragt `fbox` nach dem Container-Namen.
- Optional koennen weitere Verzeichnisse gemountet werden.
- Optional kann per `--image` ein anderes Docker-Image gesetzt werden, Standard ist `ubuntu:24.04`.
- Das Projekt wird nach `/workspace` gemountet.
- Weitere Mounts landen unter `/extra/<ordnername>`.
- Der Container bleibt erhalten und wird beim naechsten Aufruf wiederverwendet.

## Sicherheits-Defaults

- Es werden nur explizit angegebene Verzeichnisse gemountet.
- Es wird kein Home-Verzeichnis automatisch freigegeben.
- Der Container startet mit `--cap-drop ALL` und `no-new-privileges`.
- Der Container bekommt standardmaessig kein Netzwerk.
- `/tmp` wird als eigenes `tmpfs` bereitgestellt.

## Noch offen

Die erste Version ist absichtlich minimal. Fuer einen haerteren Sandbox-Modus sollten als Naechstes
Netzwerk-, GPU-, User- und Paketinstallations-Regeln festgelegt werden.
