"""Lokale Zwischenkopien von Dateien (für Schulserver mit unsicherem Netz).

Jede erfolgreich gelesene oder gespeicherte Datei wird zusätzlich im
Konfigordner abgelegt. Ist der Server später nicht erreichbar, kann das
Programm trotzdem geöffnet, ausgeführt und woanders gespeichert werden.
Alle Funktionen sind „best effort“: Fehler hier dürfen nie die Arbeit stören.
"""
import hashlib
import os
import time
from pathlib import Path

from .config import OFFLINE_CACHE_MAX_AGE_DAYS, _user_config_dir


def cache_root() -> Path:
    return _user_config_dir() / "offline_cache"


def cache_path(filepath: str) -> Path:
    """Pfad der Zwischenkopie; gleicher Dateiname, damit Tracebacks lesbar bleiben."""
    key = os.path.normcase(os.path.abspath(filepath))
    digest = hashlib.sha1(key.encode("utf-8", "replace")).hexdigest()[:10]
    return cache_root() / digest / os.path.basename(filepath)


def store(filepath: str, text: str) -> bool:
    try:
        p = cache_path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        return True
    except Exception:
        return False


def load(filepath: str) -> str | None:
    try:
        return cache_path(filepath).read_text(encoding="utf-8")
    except Exception:
        return None


def prune(max_age_days: int = OFFLINE_CACHE_MAX_AGE_DAYS, root: Path | None = None) -> int:
    """Entfernt Zwischenkopien, die lange nicht mehr benutzt wurden.

    Wird kurz nach dem Start aufgerufen (main_window). Gibt die Zahl der
    gelöschten Dateien zurück; Fehler einzelner Einträge werden übersprungen.
    """
    root = root or cache_root()
    limit = time.time() - max_age_days * 86400
    removed = 0
    try:
        dirs = list(root.iterdir())
    except OSError:
        return 0
    for d in dirs:
        try:
            if not d.is_dir():
                continue
            for f in d.iterdir():
                if f.stat().st_mtime < limit:
                    f.unlink()
                    removed += 1
            if not any(d.iterdir()):
                d.rmdir()
        except OSError:
            continue
    return removed
