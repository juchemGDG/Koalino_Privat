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

_MAX_AGE_DAYS = 60


def cache_root() -> Path:
    from .config import _user_config_dir
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


def prune(max_age_days: int = _MAX_AGE_DAYS) -> None:
    """Entfernt Zwischenkopien, die lange nicht mehr benutzt wurden."""
    try:
        limit = time.time() - max_age_days * 86400
        for d in cache_root().iterdir():
            for f in d.iterdir():
                if f.stat().st_mtime < limit:
                    f.unlink()
            if not any(d.iterdir()):
                d.rmdir()
    except Exception:
        pass
