# Release-Builds (macOS / Windows / Linux)

Dieser Ordner enthaelt alles, um automatisch downloadbare Pakete zu bauen.

## Neue Version veroeffentlichen (Schnellanleitung)

Beispiel: Version `1.3.2`. Im Terminal des Codespace (Ordner `/workspaces/Koalino`):

1. Versionsnummer aendern in `koalino/config.py` (einzige Quelle der Wahrheit):
   `APP_VERSION = "1.3.2"`
2. Committen:
   ```bash
   git add koalino/config.py
   git commit -m "chore: Version 1.3.2"
   ```
3. Tag setzen (Name MUSS mit `v` beginnen und zur Version passen):
   ```bash
   git tag v1.3.2
   ```
4. Commit und Tag hochladen (zwei getrennte Pushes):
   ```bash
   git push origin main
   git push origin v1.3.2
   ```

Der Tag-Push startet GitHub Actions. Fortschritt: GitHub -> Reiter **Actions**.
Das fertige Release mit allen Download-Paketen erscheint unter GitHub -> **Releases**.

Ablauf im Hintergrund: Jeder Plattform-Build haengt seine Pakete direkt an ein
**Entwurfs-Release**; erst wenn Linux, macOS und Windows fertig sind, wird es
automatisch veroeffentlicht. Ein halbfertiges Release wird also nie sichtbar.
Schlaegt ein Build fehl, bleibt der Entwurf liegen -- nach dem Fix denselben
Workflow erneut starten, der Entwurf wird weiterbenutzt.

Hinweise:
- Tag-Name (`v1.3.2`) und `APP_VERSION` (`1.3.2`) muessen uebereinstimmen.
- Builds laufen in der Cloud, nicht im Codespace -- der darf danach geschlossen werden.
- Tag versehentlich falsch? Loeschen mit
  `git tag -d v1.3.2 && git push origin :refs/tags/v1.3.2`, dann neu setzen.

## Zielartefakte

- macOS: `Koalino-macos.dmg`
- Windows: `Koalino-Setup.exe` (Installer, empfohlen) und `Koalino-windows.zip` (portabel)
- Linux: `Koalino-linux-x86_64.tar.gz`

## Lokal bauen

Voraussetzungen: Python 3.11+ und Plattform-spezifische Build-Umgebung.

- Linux:
  - `bash release/scripts/build_linux.sh`
- macOS:
  - `bash release/scripts/build_macos.sh`
- Windows (PowerShell):
  - `pwsh -File release/scripts/build_windows.ps1`
  - Fuer die `Koalino-Setup.exe` wird zusaetzlich [Inno Setup 6](https://jrsoftware.org/isdl.php) benoetigt.
    Fehlt es, wird nur das ZIP erstellt (das Skript bricht nicht ab). Auf den
    GitHub-Actions-Runnern (`windows-latest`) ist Inno Setup vorinstalliert.

Die fertigen Dateien landen in `release/downloads/<plattform>/`.

Alle Plattform-Builds nehmen standardmaessig eine eingebettete Python-Runtime
(inkl. pip und tkinter) mit ins Paket auf und pruefen am Ende, dass das
gebuendelte `python`/`pip` tatsaechlich startet. Abschalten (z. B. fuer
schnelle lokale Test-Builds):

- Linux: `INCLUDE_RUNTIME=0 bash release/scripts/build_linux.sh`
- macOS: `INCLUDE_RUNTIME=0 bash release/scripts/build_macos.sh`
- Windows: `pwsh -File release/scripts/build_windows.ps1 -SkipRuntime`

Hinweis: Die Runtime vergroessert die Downloadpakete deutlich, macht den Start
aber unabhaengig von einer vorinstallierten Python-Installation auf
Zielsystemen.

## Eingebettete Python-Runtime (Hybrid-Modus)

Fuer Schulserver oder Umgebungen ohne zuverlaessige Python-Installation kann
eine Runtime im Projektordner unter `python_runtime/` erzeugt werden. Beim Start
nutzt Koalino diese Runtime bevorzugt automatisch, und in den Einstellungen
wird sie als Standard-Interpreter vorausgewaehlt.

Die Runtime basiert auf
[python-build-standalone](https://github.com/astral-sh/python-build-standalone)
(vollstaendig eigenstaendiges, verschiebbares CPython inkl. tkinter und pip).
Ein venv ist dafuer ungeeignet: es verlinkt nur auf das Python des
Build-Rechners und ist auf anderen Rechnern kaputt.

- Linux/macOS:
  - `bash release/scripts/create_embedded_runtime.sh --force`
- Windows (PowerShell):
  - `pwsh -File release/scripts/create_embedded_runtime.ps1 -Force`

Optionen:

- Ohne Zusatzpakete (nur Python + pip):
  - `--skip-requirements` (Shell) bzw. `-SkipRequirements` (PowerShell)
- Andere Paketliste (Standard: `release/requirements-runtime.txt`):
  - `--requirements <datei>` (Shell) bzw. `-Requirements <datei>` (PowerShell)
- Python-Version/Release uebersteuern: Umgebungsvariablen `PBS_PYTHON_VERSION`
  und `PBS_RELEASE` (Standard: 3.12.13 / 20260623).

Hinweise:

- Die Runtime enthaelt nur die Pakete aus `release/requirements-runtime.txt`
  (fuer Schueler-Programme, z. B. `pyserial`, `requests`) – die IDE selbst
  laeuft aus dem PyInstaller-Bundle. Weitere Pakete lassen sich ueber den
  Pip-Manager der IDE nachinstallieren.
- `python_runtime/` ist in `.gitignore` eingetragen und wird nicht ins Repo committed.

## Lock-Datei (`requirements.lock`)

Die Release-Skripte (`build_linux.sh`, `build_macos.sh`, `build_windows.ps1`) und damit
auch `release-build.yml` installieren aus `requirements.lock` statt aus
`requirements.txt`. Die Datei enthaelt alle Pakete der IDE **und** der Build-Werkzeuge
(`release/requirements-build.txt`) samt Unterpaketen mit exakter Version, fuer Python 3.11.
Plattformabhaengige Pakete (z. B. `pefile` nur Windows, `macholib` nur macOS) tragen einen
Marker, die Datei gilt also fuer alle Release-Plattformen. Fuer die Entwicklung bleibt
`requirements.txt` (mit `>=`) massgeblich.

**Lock-Datei aktualisieren** (nur mit [uv](https://docs.astral.sh/uv/), `pip install uv`):

```bash
uv pip compile requirements.txt release/requirements-build.txt \
    --universal --python-version 3.11 --no-annotate --no-header -o /tmp/neu.lock
```

Die Ausgabe ersetzt die Paketzeilen in `requirements.lock` (der Kommentarkopf bleibt).
Einzelne Pakete gezielt anheben: Zeile in `requirements.lock` aendern und mit
`uv pip compile … -c requirements.lock` pruefen. Alternativ nach einem Test in einer
frischen venv `pip freeze` – dann fehlen aber die Plattform-Marker (`pefile`,
`macholib`, `pywin32-ctypes`, `colorama`), die von Hand ergaenzt werden muessen.

> **Nach jedem Aktualisieren ist ein Testbuild auf allen drei Plattformen noetig**
> (Linux x86_64 und ARM, macOS, Windows): Actions → *Build Release Packages* →
> *Run workflow*. Erst wenn alle Builds gruen sind und die App startet, committen.

## GitHub Actions

Die Workflow-Datei liegt in `.github/workflows/release-build.yml` und baut die Artefakte automatisch fuer alle drei Plattformen:

- manuell per `workflow_dispatch`
- automatisch bei Tags wie `v1.2.3`

Bei Tag-Builds werden die Dateien zusaetzlich als GitHub-Release-Assets hochgeladen.
