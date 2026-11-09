"""Lokale Daten von Koalino im Benutzerprofil: Größe ermitteln und löschen.

Grundlage für den Abschnitt „Lokale Daten“ im Einstellungsdialog und für
docs/datenschutz.md. Drei Ablagen:

* Offline-Kopien (``offline_cache/``): Zwischenkopien geöffneter Dateien
* Stände (``staende/``): Programmstände für „Zurück zum letzten funktionierenden Stand“
* Absturzprotokoll (``crash.log``)

Alle Funktionen sind „best effort“: Was sich nicht löschen lässt (offene Datei,
fehlende Rechte), wird übersprungen, nie wird eine Ausnahme nach außen gereicht.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import crash_log, offline_cache
from .snapshots import _default_root as _snapshot_root


@dataclass(frozen=True)
class LocalStore:
    key: str
    label: str
    hint: str
    path: Callable[[], Path]
    clear: Callable[[], int]


def size_of(path: Path) -> int:
    """Summe der Dateigrößen unter ``path`` (Datei oder Ordner) in Bytes; 0, wenn es fehlt."""
    try:
        if path.is_file():
            return path.stat().st_size
        if not path.is_dir():
            return 0
        total = 0
        for p in path.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except OSError:
                continue
        return total
    except OSError:
        return 0


def format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def _clear_dir(root: Path) -> int:
    """Löscht alle Einträge unterhalb von ``root`` (den Ordner selbst nicht). Gibt die
    Zahl der entfernten Dateien zurück."""
    removed = 0
    try:
        entries = list(root.iterdir())
    except OSError:
        return 0
    for entry in entries:
        try:
            if entry.is_dir():
                removed += sum(1 for p in entry.rglob("*") if p.is_file())
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def clear_offline_cache(root: Path | None = None) -> int:
    return _clear_dir(root or offline_cache.cache_root())


def clear_snapshots(root: Path | None = None) -> int:
    return _clear_dir(root or _snapshot_root())


def clear_crash_log(path: Path | None = None) -> int:
    """Kürzt das Absturzprotokoll auf die laufende Sitzung.

    Die Datei bleibt offen (faulthandler schreibt im Anhängemodus hinein), deshalb
    wird sie nicht gelöscht, sondern über einen zweiten Handle auf den letzten
    Sitzungskopf gekürzt. Gibt die Zahl der entfernten Bytes zurück.
    """
    path = path or crash_log.log_path()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    i = text.rfind(crash_log._HEADER)
    keep = text[i:] if i >= 0 else ""
    try:
        path.write_text(keep, encoding="utf-8")
    except OSError:
        return 0
    return max(0, len(text) - len(keep))


STORES: tuple[LocalStore, ...] = (
    LocalStore(
        key="offline_cache",
        label="Offline-Kopien",
        hint="Zwischenkopien geöffneter Dateien für Schulserver mit unsicherem Netz. "
             "Werden nach 60 Tagen ohne Nutzung automatisch gelöscht.",
        path=offline_cache.cache_root,
        clear=clear_offline_cache,
    ),
    LocalStore(
        key="snapshots",
        label="Gesicherte Stände",
        hint="Programmstände je Lauf für „Zurück zum letzten funktionierenden Stand“. "
             "Ordner ohne Änderung seit 90 Tagen werden automatisch gelöscht.",
        path=_snapshot_root,
        clear=clear_snapshots,
    ),
    LocalStore(
        key="crash_log",
        label="Absturzprotokoll",
        hint="Zeit, Version, System und Stacktraces unerwarteter Abbrüche. "
             "Löschen behält nur die laufende Sitzung.",
        path=crash_log.log_path,
        clear=clear_crash_log,
    ),
)
