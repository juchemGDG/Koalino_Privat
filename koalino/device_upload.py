"""Mehrere Dateien und ganze Ordner auf einen MicroPython-Controller hochladen.

Beliebige Dateitypen (auch unbekannte/binäre) werden unverändert per
``mpremote cp`` übertragen. Ordner werden samt Unterordnern übernommen;
Zwischenspeicher und Versionsverwaltung (``__pycache__``, ``.git`` …) bleiben
draußen.
"""
from __future__ import annotations

import os
import subprocess
import time

from PyQt6.QtCore import QThread, pyqtSignal

from .config import tool_command

# Wird beim Ordner-Upload übersprungen (Müll, der nicht aufs Board gehört)
_SKIP_DIRS = {"__pycache__", ".git", ".svn", ".idea", ".vscode", ".venv", "venv", "node_modules"}
_SKIP_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}
_SKIP_SUFFIX = (".pyc", ".pyo")

_CHUNK = 15          # so viele Dateien pro mpremote-Aufruf (hält die Befehlszeile kurz)
_RETRIES = 3


def plan_upload(paths: list[str], folder: str = "") -> tuple[list[str], list[tuple[str, str]]]:
    """Baut aus Dateien/Ordnern den Übertragungsplan.

    Rückgabe: (anzulegende Ordner auf dem Controller, [(lokal, remote), …]).
    ``folder`` ist der Zielordner auf dem Controller ("" = Hauptebene).
    """
    folder = folder.strip("/")
    dirs: set[str] = set()
    files: list[tuple[str, str]] = []

    def _remote(*parts: str) -> str:
        return "/".join(p for p in (folder, *parts) if p)

    def _add_dir(remote_dir: str):
        # alle Zwischenstufen mitnehmen: a, a/b, a/b/c
        acc = ""
        for part in remote_dir.split("/"):
            if not part:
                continue
            acc = f"{acc}/{part}" if acc else part
            dirs.add(acc)

    if folder:
        _add_dir(folder)

    for p in paths:
        p = os.path.normpath(p)
        if os.path.isfile(p):
            files.append((p, _remote(os.path.basename(p))))
        elif os.path.isdir(p):
            base = os.path.basename(p)
            _add_dir(_remote(base))
            for root, subdirs, names in os.walk(p):
                subdirs[:] = sorted(d for d in subdirs if d not in _SKIP_DIRS)
                rel = os.path.relpath(root, p)
                rel_parts = [] if rel == "." else rel.split(os.sep)
                remote_dir = _remote(base, *rel_parts)
                _add_dir(remote_dir)
                for n in sorted(names):
                    if n in _SKIP_FILES or n.endswith(_SKIP_SUFFIX):
                        continue
                    files.append((os.path.join(root, n), f"{remote_dir}/{n}"))
    return sorted(dirs, key=lambda d: (d.count("/"), d)), files


class UploadWorker(QThread):
    """Überträgt einen Übertragungsplan (siehe :func:`plan_upload`)."""

    log = pyqtSignal(str)
    done = pyqtSignal(bool, str)   # (ok, Meldung)

    def __init__(self, port: str, dirs: list[str], files: list[tuple[str, str]]):
        super().__init__()
        self._port = port
        self._dirs = dirs
        self._files = files

    def _mpremote(self, *args: str, timeout: int = 300):
        """mpremote mit Wiederholung, falls das Board noch beschäftigt ist."""
        r = None
        for attempt in range(_RETRIES + 1):
            r = subprocess.run(
                [*tool_command("mpremote"), "connect", self._port, *args],
                capture_output=True, text=True, timeout=timeout,
            )
            if r.returncode == 0:
                break
            if "raw repl" in (r.stderr or "").lower() and attempt < _RETRIES:
                time.sleep(1.5)
                continue
            break
        return r

    def run(self):
        try:
            if self._dirs:
                # Ein einziger Aufruf; bereits vorhandene Ordner sind kein Fehler.
                code = (
                    "import os\n"
                    f"for d in {self._dirs!r}:\n"
                    "    try:\n"
                    "        os.mkdir(d)\n"
                    "    except OSError:\n"
                    "        pass\n"
                )
                r = self._mpremote("exec", code, timeout=60)
                if r.returncode != 0:
                    self.done.emit(False, (r.stderr or "Ordner konnten nicht angelegt werden.").strip())
                    return
            total = len(self._files)
            sent = 0
            for i in range(0, total, _CHUNK):
                chunk = self._files[i:i + _CHUNK]
                args: list[str] = []
                for local, remote in chunk:
                    if args:
                        args.append("+")
                    args += ["cp", local, f":{remote}"]
                r = self._mpremote(*args)
                if r.returncode != 0:
                    last = next((ln for ln in reversed((r.stderr or "").splitlines()) if ln.strip()), "")
                    self.done.emit(False, f"Fehler nach {sent} von {total} Dateien: {last.strip()}")
                    return
                for _local, remote in chunk:
                    self.log.emit(f"   ↑ {remote}\n")
                sent += len(chunk)
            self.done.emit(True, f"{total} Datei(en) hochgeladen.")
        except Exception as e:
            self.done.emit(False, str(e))
