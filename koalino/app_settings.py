"""Anwendungseinstellungen von Koalino als Datenobjekt (ohne Qt-Abhängigkeit).

``AppSettings`` bündelt alle Einstellungen, die das Hauptfenster in QSettings
ablegt. ``load(store)`` liest sie samt aller Migrationen älterer Installationen,
``save(store)`` schreibt sie zurück. ``store`` ist ein ``QSettings`` – oder jedes
Objekt mit ``value/setValue/contains/remove/sync`` (so lässt sich das in Tests
ohne Qt prüfen). Die QSettings-Schlüssel sind unverändert geblieben.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field, replace
from pathlib import Path

from .config import (
    CODE_SCHEMES,
    LEGACY_THEME_MIGRATION,
    embedded_python_executable,
    preferred_python_interpreter,
)

UI_FONT_PT_DEFAULT = 10      # entspricht der bisherigen Größe (13 px) → Faktor 1.0

# Knöpfe der Seitenleiste, die sich ein-/ausblenden lassen (Schlüssel wie in
# MainWindow._build_activity_bar). Hilfe und Einstellungen bleiben immer sichtbar.
ACTIVITY_ITEMS = [
    ("files",    "Dateien"),
    ("ai",       "KI-Assistent"),
    ("debuglog", "Fehlerprotokoll"),
    ("pysite",   "Lehrgang py.nitbw.de"),
    ("blocks",   "Block-Editor"),
    ("plotter",  "Serial Plotter"),
    ("pap",      "PAP-Editor"),
    ("ibd",      "IBD-Editor"),
    ("schaltlab", "SchaltLab (Schaltplan)"),
    ("stats",    "Datenauswertung"),
]
ACTIVITY_TOGGLEABLE = frozenset(k for k, _ in ACTIVITY_ITEMS)

CHATBOT_MODES = ("none", "aischat", "fobizz")


def normalize_sketchbook_dir(path: str) -> str:
    """Existierenden Ordner auflösen; sonst das Home-Verzeichnis."""
    candidate = Path(path).expanduser() if path else Path.home()
    if not candidate.exists() or not candidate.is_dir():
        return str(Path.home())
    return str(candidate.resolve())


def _bool(store, key: str, default: bool) -> bool:
    raw = store.value(key, default)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _int(store, key: str, default: int) -> int:
    raw = store.value(key, default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _float(store, key: str, default: float) -> float:
    raw = store.value(key, default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


@dataclass
class AppSettings:
    # Editor und Konsole
    font_size: int = 14
    line_numbers: bool = True
    word_wrap: bool = False
    highlight_line: bool = True
    autosave_secs: int = 0
    python_exec: str = ""
    scrollback: int = 5000
    editor_font: str = "default"
    # Funktionen
    blocks_enabled: bool = True      # Block-Editor, Standard: an
    statplot_offline: bool = False   # Datenauswertung nur aus der mitgelieferten Kopie
    hidden_activity: set[str] = field(default_factory=set)   # ausgeblendete Knöpfe der Seitenleiste
    tutor_mode: str = "none"         # Chatbot: "none" | "aischat" | "fobizz"
    # Dateien und Git
    sketchbook: str = field(default_factory=lambda: str(Path.home()))
    git_executable: str = ""
    git_repo: str = ""
    # Erscheinungsbild
    theme: str = "modern_light"
    code_scheme: str = "auto"
    ui_font_pt: int = UI_FONT_PT_DEFAULT
    # Serial-Plotter-Achsen (Standardwerte; im Plotter live übersteuerbar)
    plot_y_mode: str = "auto"        # "auto" | "fixed"
    plot_y_min: float = 0.0
    plot_y_max: float = 100.0
    plot_x_mode: str = "sliding"     # "sliding" | "sweep" | "xy"
    plot_x_min: int = 0
    plot_x_max: int = 500
    plot_style: str = "line"         # "line" | "scatter"
    # Fehler finden (Cheatsheet)
    debug_level: str = "kl10"        # "kl89" | "kl10" – nur noch für die NiT_Coder-Vorlage
    debug_stepped: bool = True       # Fehlerhilfe in Stufen
    debug_change_hint: bool = True   # „Seit dem letzten Lauf: n Stellen geändert"

    def copy(self) -> "AppSettings":
        return replace(self, hidden_activity=set(self.hidden_activity))

    # ── Laden (mit Migrationen) ──────────────────────────────────────────
    @classmethod
    def load(cls, store, base: "AppSettings | None" = None) -> "AppSettings":
        """Liest die Einstellungen aus ``store``; fehlende Werte kommen aus ``base`` (Standard: Vorgaben).

        Führt die einmaligen Migrationen alter Installationen aus und schreibt
        dabei deren Marker (``…_migrated``, ``ui/layout_v2``) in ``store`` zurück.
        """
        s = (base or cls()).copy()
        s.font_size = _int(store, "editor/font_size", s.font_size)
        s.editor_font = str(store.value("editor/font_family", "default") or "default")
        s.line_numbers = _bool(store, "editor/line_numbers", s.line_numbers)
        s.word_wrap = _bool(store, "editor/word_wrap", s.word_wrap)
        s.highlight_line = _bool(store, "editor/highlight_line", s.highlight_line)
        s.autosave_secs = _int(store, "editor/autosave_secs", s.autosave_secs)
        s.python_exec = str(store.value("python/executable", s.python_exec) or "")
        embedded_py = embedded_python_executable()

        # Einmalige Migration: wenn eine mitgelieferte Runtime vorhanden ist,
        # soll sie standardmäßig gewählt werden (auch bei Alt-Settings).
        migrated_embedded = _bool(store, "python/prefer_embedded_migrated", False)
        if embedded_py and not migrated_embedded:
            s.python_exec = embedded_py
            store.setValue("python/executable", s.python_exec)
            store.setValue("python/prefer_embedded_migrated", True)
        else:
            chosen = (s.python_exec or "").strip()
            usable = False
            if chosen:
                if os.path.isfile(chosen):
                    usable = True
                elif shutil.which(chosen):
                    usable = True

            if not usable:
                fallback = embedded_py or preferred_python_interpreter() or ""
                s.python_exec = fallback
                if fallback:
                    store.setValue("python/executable", fallback)
        s.scrollback = _int(store, "console/scrollback", s.scrollback)
        # Block-Editor ist seit dem Ende der BETA standardmäßig an. Bestehende
        # Installationen haben durch den früheren Standard („aus") ein
        # blocks/enabled=False persistiert (closeEvent speichert alle Settings).
        # Darum einmalig auf an setzen; eine spätere bewusste Abwahl bleibt erhalten.
        if _bool(store, "blocks/default_on_migrated", False):
            s.blocks_enabled = _bool(store, "blocks/enabled", s.blocks_enabled)
        else:
            s.blocks_enabled = True
            store.setValue("blocks/enabled", True)
            store.setValue("blocks/default_on_migrated", True)
        s.statplot_offline = _bool(store, "statplot/offline_first", s.statplot_offline)
        s.tutor_mode = str(store.value("tutor/mode", s.tutor_mode) or "none")
        if s.tutor_mode not in CHATBOT_MODES:
            s.tutor_mode = "none"   # Ollama-Modi (bis 1.14) gibt es nicht mehr
        # Schlüssel des entfernten Ollama-Tutors aus alten Installationen aufräumen.
        for key in ("tutor/url", "tutor/model"):
            if store.contains(key):
                store.remove(key)
        s.sketchbook = normalize_sketchbook_dir(
            str(store.value("files/sketchbook_dir", s.sketchbook) or "")
        )
        s.git_executable = str(store.value("git/executable", s.git_executable) or "")
        s.git_repo = str(store.value("git/repo_dir", s.git_repo) or "")
        s.theme = str(store.value("ui/theme", s.theme) or "modern_light")
        # Einmalige Migration: das bisherige Standard-Design (Eclipse) wird beim
        # ersten Start mit dem neuen Layout auf das moderne Hell-Design gesetzt.
        if not store.value("ui/layout_v2", False, type=bool):
            if s.theme == "classic_light":
                s.theme = "modern_light"
            store.setValue("ui/layout_v2", True)
        # Solarized/Dracula gibt es nur noch als Code-Farbschema.
        s.code_scheme = str(store.value("ui/code_scheme", "") or "")
        if s.theme in LEGACY_THEME_MIGRATION:
            s.theme, legacy_scheme = LEGACY_THEME_MIGRATION[s.theme]
            if not s.code_scheme:
                s.code_scheme = legacy_scheme
        if s.code_scheme not in CODE_SCHEMES:
            s.code_scheme = "auto"
        s.ui_font_pt = _int(store, "ui/font_pt", s.ui_font_pt)
        # Serial-Plotter-Achsen
        s.plot_y_mode = str(store.value("plot/y_mode", s.plot_y_mode) or "auto")
        s.plot_y_min = _float(store, "plot/y_min", s.plot_y_min)
        s.plot_y_max = _float(store, "plot/y_max", s.plot_y_max)
        s.plot_x_mode = str(store.value("plot/x_mode", s.plot_x_mode) or "sliding")
        s.plot_x_min = _int(store, "plot/x_min", s.plot_x_min)
        s.plot_x_max = _int(store, "plot/x_max", s.plot_x_max)
        s.plot_style = str(store.value("plot/style", s.plot_style) or "line")
        level = str(store.value("debug/level", s.debug_level) or "kl10")
        s.debug_level = level if level in ("kl89", "kl10") else "kl10"
        raw_hidden = str(store.value("ui/hidden_activity", "") or "")
        s.hidden_activity = {k for k in raw_hidden.split(",") if k in ACTIVITY_TOGGLEABLE}
        s.debug_stepped = _bool(store, "debug/stepped", s.debug_stepped)
        s.debug_change_hint = _bool(store, "debug/change_hint", s.debug_change_hint)
        return s

    # ── Speichern ────────────────────────────────────────────────────────
    def save(self, store) -> None:
        store.setValue("editor/font_size", self.font_size)
        store.setValue("editor/font_family", self.editor_font)
        store.setValue("editor/line_numbers", self.line_numbers)
        store.setValue("editor/word_wrap", self.word_wrap)
        store.setValue("editor/highlight_line", self.highlight_line)
        store.setValue("editor/autosave_secs", self.autosave_secs)
        store.setValue("blocks/enabled", self.blocks_enabled)
        store.setValue("statplot/offline_first", self.statplot_offline)
        store.setValue("python/executable", self.python_exec)
        store.setValue("console/scrollback", self.scrollback)
        store.setValue("tutor/mode", self.tutor_mode)
        store.setValue("files/sketchbook_dir", self.sketchbook)
        store.setValue("git/executable", self.git_executable)
        store.setValue("git/repo_dir", self.git_repo)
        store.setValue("ui/theme", self.theme)
        store.setValue("ui/code_scheme", self.code_scheme)
        store.setValue("ui/font_pt", self.ui_font_pt)
        store.setValue("plot/y_mode", self.plot_y_mode)
        store.setValue("plot/y_min", self.plot_y_min)
        store.setValue("plot/y_max", self.plot_y_max)
        store.setValue("plot/x_mode", self.plot_x_mode)
        store.setValue("plot/x_min", self.plot_x_min)
        store.setValue("plot/x_max", self.plot_x_max)
        store.setValue("plot/style", self.plot_style)
        store.setValue("ui/hidden_activity", ",".join(sorted(self.hidden_activity)))
        store.setValue("debug/level", self.debug_level)
        store.setValue("debug/stepped", self.debug_stepped)
        store.setValue("debug/change_hint", self.debug_change_hint)
        store.sync()
