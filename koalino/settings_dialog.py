"""Einstellungs-Dialog für Koalino."""
import os
import shutil
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton, QFrame,
    QComboBox, QLineEdit, QFileDialog, QButtonGroup, QRadioButton, QWidget, QScrollArea, QGridLayout,
)

from .qt_utils import UI_FONT_PT_DEFAULT, UI_FONT_PT_RANGE
from .qt_utils import ThemedComboBox
from .config import (
    CODE_SCHEME_LABELS, MONO_FONTS, THEME, THEMES,
    detect_python_interpreters, python_version_label, python_has_tkinter,
)

# Auto-Save-Intervalle: Anzeigetext → Sekunden
_AUTOSAVE_OPTIONS = [
    ("Aus", 0),
    ("30 Sek.", 30),
    ("60 Sek.", 60),
    ("5 Min.", 300),
]


def detect_git_executables() -> list[str]:
    """Sucht mögliche Git-Executables auf dem System (dedupliziert)."""
    found: list[str] = []

    def add(path: str | None):
        if not path:
            return
        try:
            p = Path(path)
            if not p.exists():
                return
            real = str(p.resolve())
        except OSError:
            return
        if real not in found:
            found.append(real)

    add(shutil.which("git"))

    for candidate in (
        "/usr/bin/git",
        "/usr/local/bin/git",
        "/opt/homebrew/bin/git",
        "/opt/local/bin/git",
    ):
        add(candidate)

    return found


# ── Hintergrund-Thread: Python-Interpreter suchen ───────────────────────────
class _PythonScanner(QThread):
    """Sucht installierte Python-Interpreter samt Version, ohne die UI zu blockieren."""
    found = pyqtSignal(list)   # list[tuple[str, str, bool]]  (pfad, version, hat_tkinter)

    def run(self):
        results: list[tuple[str, str, bool]] = []
        for path in detect_python_interpreters():
            results.append((path, python_version_label(path), python_has_tkinter(path)))
        self.found.emit(results)


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


# ── Einstellungs-Dialog ──────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    """Einstellungs-Popup mit Editor- und KI-Optionen."""

    def __init__(
        self,
        parent=None,
        font_size: int = 14,
        line_numbers: bool = True,
        word_wrap: bool = False,
        highlight_line: bool = True,
        autosave_secs: int = 0,
        python_exec: str = "",
        scrollback: int = 5000,
        tutor_mode: str = "none",
        sketchbook_dir: str = "",
        git_exec: str = "",
        theme: str = "modern_dark",
        blocks_enabled: bool = True,
        plot_y_mode: str = "auto",
        plot_y_min: float = 0.0,
        plot_y_max: float = 100.0,
        plot_x_mode: str = "sliding",
        plot_x_min: int = 0,
        plot_x_max: int = 500,
        plot_style: str = "line",
        ui_font_pt: int = UI_FONT_PT_DEFAULT,
        debug_level: str = "kl10",
        debug_stepped: bool = True,
        debug_change_hint: bool = True,
        hidden_activity=(),
        editor_font: str = "default",
        code_scheme: str = "auto",
    ):
        super().__init__(parent)
        self._editor_font_init = editor_font
        self._code_scheme_init = code_scheme
        self._hidden_activity_init = set(hidden_activity)
        self._initial_ui_font_pt = ui_font_pt
        self._debug_init = (debug_level, debug_stepped, debug_change_hint)
        self.setWindowTitle("Einstellungen")
        self.setModal(True)
        # Etwas breiter und mit Scrollbereich (siehe _build_ui), damit das Fenster
        # auch auf niedrigen Auflösungen nie höher als der Bildschirm wird und der
        # „Übernehmen“-Button immer sichtbar bleibt.
        self.setMinimumWidth(620)
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {THEME['bg_panel']};
                color: {THEME['text']};
            }}
            QLabel {{
                color: {THEME['text']};
            }}
            QSpinBox, QCheckBox, QComboBox, QLineEdit {{
                background: {THEME['bg_dark']};
                color: {THEME['text']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 3px 6px;
            }}
            QRadioButton {{
                color: {THEME['text']};
                spacing: 6px;
            }}
            QRadioButton::indicator {{
                width: 14px; height: 14px; border-radius: 8px;
                border: 2px solid {THEME['text_dim']}; background: {THEME['bg_dark']};
            }}
            QRadioButton::indicator:hover {{ border-color: {THEME['accent']}; }}
            QRadioButton::indicator:checked {{
                border: 2px solid {THEME['accent']};
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                    stop:0 {THEME['accent']}, stop:0.5 {THEME['accent']},
                    stop:0.6 {THEME['bg_dark']}, stop:1 {THEME['bg_dark']});
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background: {THEME['bg_panel']};
                border: none;
                width: 16px;
            }}
            QComboBox {{
                combobox-popup: 0;
            }}
            QComboBox::drop-down {{
                border: none;
                background: {THEME['bg_panel']};
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background: {THEME['bg_dark']};
                color: {THEME['text']};
                border: 1px solid {THEME['border']};
                selection-background-color: {THEME['accent']};
                selection-color: #fff;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 24px;
                padding: 2px 6px;
            }}
            QPushButton {{
                background: {THEME['accent']};
                color: #fff;
                border: none;
                border-radius: 4px;
                padding: 6px 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {THEME['accent_hover']};
            }}
            QPushButton#ok, QPushButton#ok:default, QPushButton#ok:focus {{
                background: {THEME['accent']};
                color: #ffffff;
                border: 1px solid {THEME['accent']};
            }}
            QPushButton#ok:hover, QPushButton#ok:pressed {{
                background: {THEME['accent_hover']};
                color: #ffffff;
                border: 1px solid {THEME['accent_hover']};
            }}
            QPushButton#cancel {{
                background: {THEME['bg_dark']};
                color: {THEME['text']};
            }}
            QPushButton#cancel:hover {{
                background: {THEME['border']};
            }}
            QPushButton#browse {{
                background: {THEME['bg_dark']};
                color: {THEME['text']};
                padding: 4px 10px;
                font-weight: normal;
            }}
            QPushButton#browse:hover {{
                background: {THEME['border']};
            }}
            """
        )
        self._build_ui(font_size, line_numbers, word_wrap, highlight_line,
                       autosave_secs, python_exec, scrollback,
                       tutor_mode, sketchbook_dir, git_exec, theme,
                       blocks_enabled,
                       plot_y_mode, plot_y_min, plot_y_max,
                       plot_x_mode, plot_x_min, plot_x_max, plot_style, ui_font_pt)

    # ── Hilfsmethode: Abschnittsüberschrift ─────────────────────────────
    @staticmethod
    def _section(label: str) -> tuple:
        title = QLabel(label)
        title.setStyleSheet(
            f"color:{THEME['text_dim']}; font-size:11px; font-weight:bold; letter-spacing:1px;"
        )
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{THEME['border']};")
        sep.setFixedHeight(1)
        return title, sep

    def _build_ui(
        self,
        font_size: int,
        line_numbers: bool,
        word_wrap: bool,
        highlight_line: bool,
        autosave_secs: int,
        python_exec: str,
        scrollback: int,
        tutor_mode: str = "none",
        sketchbook_dir: str = "",
        git_exec: str = "",
        theme: str = "modern_dark",
        blocks_enabled: bool = True,
        plot_y_mode: str = "auto",
        plot_y_min: float = 0.0,
        plot_y_max: float = 100.0,
        plot_x_mode: str = "sliding",
        plot_x_min: int = 0,
        plot_x_max: int = 500,
        plot_style: str = "line",
        ui_font_pt: int = UI_FONT_PT_DEFAULT,
    ):
        # Äußeres Layout: Scrollbereich (Inhalt) + feste Button-Leiste unten.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)

        content = QWidget()
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(20, 20, 20, 14)
        root.setSpacing(10)

        # ── Abschnitt: Editor ────────────────────────────────────────────
        title, sep = self._section("EDITOR")
        root.addWidget(title)
        root.addWidget(sep)

        form_ed = QFormLayout()
        form_ed.setSpacing(8)
        form_ed.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._spin = QSpinBox()
        self._spin.setRange(8, 32)
        self._spin.setValue(font_size)
        self._spin.setSuffix(" pt")
        self._spin.setFixedWidth(90)
        form_ed.addRow("Schriftgröße (Editor und Konsole):", self._spin)

        self._chk_lineno = QCheckBox("  Zeilennummern anzeigen")
        self._chk_lineno.setChecked(line_numbers)
        form_ed.addRow("", self._chk_lineno)

        self._chk_wrap = QCheckBox("  Zeilenumbruch")
        self._chk_wrap.setChecked(word_wrap)
        form_ed.addRow("", self._chk_wrap)

        self._chk_hl = QCheckBox("  Aktuelle Zeile hervorheben")
        self._chk_hl.setChecked(highlight_line)
        form_ed.addRow("", self._chk_hl)

        root.addLayout(form_ed)
        root.addSpacing(6)

        # ── Abschnitt: Funktionen ────────────────────────────────────────
        title_f, sep_f = self._section("FUNKTIONEN")
        root.addWidget(title_f)
        root.addWidget(sep_f)

        form_func = QFormLayout()
        form_func.setSpacing(8)
        form_func.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._chk_blocks = QCheckBox("  Block-Editor aktivieren")
        self._chk_blocks.setChecked(blocks_enabled)
        self._chk_blocks.setToolTip(
            "Blendet das Menü „Blöcke“ und „Als Blöcke öffnen“ ein. "
            "Blockbasiertes Programmieren mit Umwandlung in Python/MicroPython.")
        form_func.addRow("", self._chk_blocks)

        hint_blocks = QLabel(
            "Standardmäßig aktiviert. Haken entfernen, um Menü und Button "
            "auszublenden.")
        hint_blocks.setWordWrap(True)
        hint_blocks.setStyleSheet(f"color:{THEME['text_dim']}; font-size:10px;")
        form_func.addRow("", hint_blocks)

        root.addLayout(form_func)
        root.addSpacing(6)

        # ── Abschnitt: Seitenleiste ──────────────────────────────────────
        title_ab, sep_ab = self._section("SEITENLEISTE")
        root.addWidget(title_ab)
        root.addWidget(sep_ab)

        hint_ab = QLabel("Welche Schnellstart-Knöpfe sollen links in der Seitenleiste erscheinen? "
                         "Hilfe und Einstellungen sind immer da.")
        hint_ab.setWordWrap(True)
        hint_ab.setStyleSheet(f"color:{THEME['text_dim']}; font-size:10px;")
        root.addWidget(hint_ab)
        grid_ab = QGridLayout()
        grid_ab.setSpacing(6)
        self._chk_activity: dict[str, QCheckBox] = {}
        for i, (key, label) in enumerate(ACTIVITY_ITEMS):
            chk = QCheckBox("  " + label)
            chk.setChecked(key not in self._hidden_activity_init)
            self._chk_activity[key] = chk
            grid_ab.addWidget(chk, i // 2, i % 2)
        root.addLayout(grid_ab)
        root.addSpacing(6)

        # ── Abschnitt: Debugging ─────────────────────────────────────────
        title_dbg, sep_dbg = self._section("DEBUGGING")
        root.addWidget(title_dbg)
        root.addWidget(sep_dbg)

        form_dbg = QFormLayout()
        form_dbg.setSpacing(8)
        form_dbg.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        dbg_level, dbg_stepped, dbg_change = self._debug_init

        self._combo_dbg_level = ThemedComboBox()
        self._combo_dbg_level.setFixedWidth(220)
        self._combo_dbg_level.addItem("Klasse 8/9 (ohne main())", "kl89")
        self._combo_dbg_level.addItem("Klasse 10/KS (mit main(), IBD)", "kl10")
        self._combo_dbg_level.setCurrentIndex(max(0, self._combo_dbg_level.findData(dbg_level)))
        self._combo_dbg_level.setToolTip(
            "Wie der Code-Generator Programme aufbaut. Die Fehlersuche (Konsole, "
            "Fehlerprotokoll, Hilfe) folgt immer dem Cheatsheet Klasse 8/9.")
        form_dbg.addRow("Code-Generator (Stufe):", self._combo_dbg_level)

        self._chk_dbg_stepped = QCheckBox("  Fehlerhilfe in Stufen (Fall → Wo suche ich? → Verdächtige)")
        self._chk_dbg_stepped.setChecked(dbg_stepped)
        form_dbg.addRow("", self._chk_dbg_stepped)

        self._chk_dbg_change = QCheckBox("  Beim Start zeigen, wie viele Stellen seit dem letzten Lauf geändert wurden")
        self._chk_dbg_change.setChecked(dbg_change)
        form_dbg.addRow("", self._chk_dbg_change)

        root.addLayout(form_dbg)
        root.addSpacing(6)

        # ── Abschnitt: Ausführen ─────────────────────────────────────────
        title2, sep2 = self._section("AUSFÜHREN")
        root.addWidget(title2)
        root.addWidget(sep2)

        form_run = QFormLayout()
        form_run.setSpacing(8)
        form_run.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._combo_as = ThemedComboBox()
        self._combo_as.setFixedWidth(120)
        self._combo_as.setMaxVisibleItems(6)
        for label, secs in _AUTOSAVE_OPTIONS:
            self._combo_as.addItem(label, secs)
        idx = next((i for i, (_, s) in enumerate(_AUTOSAVE_OPTIONS) if s == autosave_secs), 0)
        self._combo_as.setCurrentIndex(idx)
        form_run.addRow("Auto-Speichern:", self._combo_as)

        root.addLayout(form_run)
        root.addSpacing(6)

        # ── Abschnitt: Serial Plotter ────────────────────────────────────
        title_pl, sep_pl = self._section("SERIAL PLOTTER")
        root.addWidget(title_pl)
        root.addWidget(sep_pl)

        form_pl = QFormLayout()
        form_pl.setSpacing(8)
        form_pl.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Hochachse (Y): automatisch oder feste Grenzen
        self._combo_plot_y = ThemedComboBox()
        self._combo_plot_y.setFixedWidth(190)
        self._combo_plot_y.addItem("Automatisch (gleitend)", "auto")
        self._combo_plot_y.addItem("Feste Grenzen (Min/Max)", "fixed")
        self._combo_plot_y.setCurrentIndex(max(0, self._combo_plot_y.findData(plot_y_mode)))
        form_pl.addRow("Hochachse (Y):", self._combo_plot_y)

        y_row = QHBoxLayout()
        self._spin_plot_ymin = QDoubleSpinBox()
        self._spin_plot_ymin.setRange(-1_000_000_000, 1_000_000_000)
        self._spin_plot_ymin.setDecimals(2)
        self._spin_plot_ymin.setFixedWidth(110)
        self._spin_plot_ymin.setValue(plot_y_min)
        self._spin_plot_ymax = QDoubleSpinBox()
        self._spin_plot_ymax.setRange(-1_000_000_000, 1_000_000_000)
        self._spin_plot_ymax.setDecimals(2)
        self._spin_plot_ymax.setFixedWidth(110)
        self._spin_plot_ymax.setValue(plot_y_max)
        y_row.addWidget(self._spin_plot_ymin)
        y_row.addWidget(QLabel("bis"))
        y_row.addWidget(self._spin_plot_ymax)
        y_row.addStretch()
        form_pl.addRow("Y Min / Max:", y_row)

        # Rechtsachse (X): gleitend, fester Indexbereich (Sweep) oder X-Y (Kennlinie)
        self._combo_plot_x = ThemedComboBox()
        self._combo_plot_x.setFixedWidth(190)
        self._combo_plot_x.addItem("Gleitend (letzte Werte)", "sliding")
        self._combo_plot_x.addItem("Fester Bereich (Sweep)", "sweep")
        self._combo_plot_x.addItem("X-Y (Kennlinie)", "xy")
        self._combo_plot_x.setCurrentIndex(max(0, self._combo_plot_x.findData(plot_x_mode)))
        form_pl.addRow("Rechtsachse (X):", self._combo_plot_x)

        x_row = QHBoxLayout()
        self._spin_plot_xmin = QSpinBox()
        self._spin_plot_xmin.setRange(0, 100_000_000)
        self._spin_plot_xmin.setFixedWidth(110)
        self._spin_plot_xmin.setValue(plot_x_min)
        self._spin_plot_xmax = QSpinBox()
        self._spin_plot_xmax.setRange(0, 100_000_000)
        self._spin_plot_xmax.setFixedWidth(110)
        self._spin_plot_xmax.setValue(plot_x_max)
        x_row.addWidget(self._spin_plot_xmin)
        x_row.addWidget(QLabel("bis"))
        x_row.addWidget(self._spin_plot_xmax)
        x_row.addStretch()
        form_pl.addRow("X Min / Max:", x_row)

        self._combo_plot_style = ThemedComboBox()
        self._combo_plot_style.setFixedWidth(190)
        self._combo_plot_style.addItem("Linie (Punkte verbunden)", "line")
        self._combo_plot_style.addItem("Streuplot (nur Punkte)", "scatter")
        self._combo_plot_style.setCurrentIndex(max(0, self._combo_plot_style.findData(plot_style)))
        form_pl.addRow("Darstellung:", self._combo_plot_style)

        hint_pl = QLabel(
            "Standardwerte – im Plotter selbst jederzeit live umstellbar."
        )
        hint_pl.setStyleSheet(f"color:{THEME['text_dim']}; font-size:11px; padding:2px 0;")
        hint_pl.setWordWrap(True)
        form_pl.addRow("", hint_pl)

        root.addLayout(form_pl)
        root.addSpacing(6)

        self._combo_plot_y.currentIndexChanged.connect(self._on_plot_axis_changed)
        self._combo_plot_x.currentIndexChanged.connect(self._on_plot_axis_changed)
        self._on_plot_axis_changed()

        # ── Abschnitt: Shell ─────────────────────────────────────────────
        title3, sep3 = self._section("AUSGABE")
        root.addWidget(title3)
        root.addWidget(sep3)

        form_sh = QFormLayout()
        form_sh.setSpacing(8)
        form_sh.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._spin_sb = QSpinBox()
        self._spin_sb.setRange(500, 50000)
        self._spin_sb.setSingleStep(1000)
        self._spin_sb.setValue(scrollback)
        self._spin_sb.setSuffix(" Zeilen")
        self._spin_sb.setFixedWidth(130)
        form_sh.addRow("Scrollback-Puffer:", self._spin_sb)

        root.addLayout(form_sh)
        root.addSpacing(6)

        # ── Abschnitt: Design ────────────────────────────────────────────
        title_d, sep_d = self._section("DESIGN")
        root.addWidget(title_d)
        root.addWidget(sep_d)

        form_design = QFormLayout()
        form_design.setSpacing(8)
        form_design.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._combo_theme = ThemedComboBox()
        self._combo_theme.setMaxVisibleItems(8)
        self._combo_theme.addItem("Modern Hell", "modern_light")
        self._combo_theme.addItem("Modern Dunkel", "modern_dark")
        self._combo_theme.addItem("Klassisch Hell", "classic_light")
        self._combo_theme.addItem("Schwarz-Weiß (hoher Kontrast)", "contrast")
        tidx = max(0, self._combo_theme.findData(theme))
        self._combo_theme.setCurrentIndex(tidx)
        form_design.addRow("Design:", self._combo_theme)

        self._combo_scheme = ThemedComboBox()
        self._combo_scheme.setMaxVisibleItems(8)
        for key, label in CODE_SCHEME_LABELS.items():
            self._combo_scheme.addItem(label, key)
        self._combo_scheme.setCurrentIndex(
            max(0, self._combo_scheme.findData(self._code_scheme_init)))
        self._combo_scheme.setToolTip(
            "Farben des Code-Editors, unabhängig vom Design der Oberfläche.")
        form_design.addRow("Code-Farben:", self._combo_scheme)

        self._combo_font = ThemedComboBox()
        for key, (label, _family) in MONO_FONTS.items():
            self._combo_font.addItem(label, key)
        self._combo_font.setCurrentIndex(max(0, self._combo_font.findData(self._editor_font_init)))
        self._combo_font.setToolTip("Schriftart für Editor und Konsole. Fehlt eine Schrift auf dem "
                                    "Rechner, nimmt Qt automatisch die nächste.")
        form_design.addRow("Schriftart (Editor/Konsole):", self._combo_font)

        self._spin_ui_font = QSpinBox()
        self._spin_ui_font.setRange(*UI_FONT_PT_RANGE)
        self._spin_ui_font.setValue(ui_font_pt)
        self._spin_ui_font.setSuffix(" pt")
        self._spin_ui_font.setFixedWidth(90)
        form_design.addRow("Schriftgröße (Oberfläche):", self._spin_ui_font)
        hint_ui_font = QLabel("Gilt für Menüs, Leisten und Panels (nicht für Editor/Konsole). "
                              "Wirkt nach einem Neustart.")
        hint_ui_font.setStyleSheet(f"color:{THEME['text_dim']}; font-size:10px;")
        hint_ui_font.setWordWrap(True)
        form_design.addRow("", hint_ui_font)

        root.addLayout(form_design)
        root.addSpacing(6)

        # ── Abschnitt: Python (lokal) ────────────────────────────────────
        title4, sep4 = self._section("PYTHON (LOKAL)")
        root.addWidget(title4)
        root.addWidget(sep4)

        form_py = QFormLayout()
        form_py.setSpacing(8)
        form_py.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        py_row = QHBoxLayout()
        py_row.setSpacing(6)
        self._combo_py = ThemedComboBox()
        self._combo_py.setEditable(True)
        self._combo_py.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._combo_py.lineEdit().setPlaceholderText("(automatisch erkannt)")
        self._combo_py.setMinimumWidth(280)
        self._combo_py.setCurrentText(python_exec)
        self._combo_py.lineEdit().setCursorPosition(0)
        py_row.addWidget(self._combo_py, stretch=1)
        self._btn_scan_py = QPushButton("↻")
        self._btn_scan_py.setFixedWidth(32)
        self._btn_scan_py.setToolTip("Erneut nach Python-Interpretern suchen")
        self._btn_scan_py.clicked.connect(self._scan_python_interpreters)
        py_row.addWidget(self._btn_scan_py)
        btn_browse = QPushButton("…")
        btn_browse.setObjectName("browse")
        btn_browse.setFixedWidth(32)
        btn_browse.clicked.connect(self._browse_python)
        py_row.addWidget(btn_browse)
        form_py.addRow("Python-Interpreter:", py_row)

        # Versions-Anzeige des aktuell gewählten Interpreters
        self._lbl_py_version = QLabel("")
        self._lbl_py_version.setStyleSheet(f"color:{THEME['text_dim']}; font-size:11px;")
        form_py.addRow("", self._lbl_py_version)
        self._py_versions: dict[str, str] = {}   # pfad → version-label
        self._py_has_tk: dict[str, bool] = {}    # pfad → tkinter verfügbar
        self._py_scanner: _PythonScanner | None = None
        self._combo_py.currentTextChanged.connect(self._update_py_version_label)

        root.addLayout(form_py)
        root.addSpacing(6)

        # Beim Öffnen automatisch im Hintergrund nach Interpretern suchen
        self._scan_python_interpreters()

        # ── Abschnitt: Dateisystem ───────────────────────────────────────
        title_fs, sep_fs = self._section("DATEISYSTEM")
        root.addWidget(title_fs)
        root.addWidget(sep_fs)

        form_fs = QFormLayout()
        form_fs.setSpacing(8)
        form_fs.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        sb_row = QHBoxLayout()
        sb_row.setSpacing(6)
        self._edit_sketchbook = QLineEdit()
        self._edit_sketchbook.setPlaceholderText("(optional)")
        self._edit_sketchbook.setText(sketchbook_dir)
        sb_row.addWidget(self._edit_sketchbook)
        btn_sketchbook = QPushButton("…")
        btn_sketchbook.setObjectName("browse")
        btn_sketchbook.setFixedWidth(32)
        btn_sketchbook.clicked.connect(self._browse_sketchbook)
        sb_row.addWidget(btn_sketchbook)
        form_fs.addRow("Sketchbook-Ordner:", sb_row)

        git_row = QHBoxLayout()
        git_row.setSpacing(6)
        self._combo_git = ThemedComboBox()
        self._combo_git.setEditable(True)
        self._combo_git.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._combo_git.lineEdit().setPlaceholderText("(automatisch erkannt)")
        self._combo_git.setMinimumWidth(280)
        self._combo_git.setCurrentText(git_exec)
        self._combo_git.lineEdit().setCursorPosition(0)
        for path in detect_git_executables():
            self._combo_git.addItem(path)
        if git_exec and self._combo_git.findText(git_exec) < 0:
            self._combo_git.addItem(git_exec)
        git_row.addWidget(self._combo_git)

        btn_git = QPushButton("…")
        btn_git.setObjectName("browse")
        btn_git.setFixedWidth(32)
        btn_git.clicked.connect(self._browse_git)
        git_row.addWidget(btn_git)
        form_fs.addRow("Git-Programm:", git_row)

        hint_git = QLabel(
            "Leer lassen = automatisch 'git' aus PATH verwenden."
        )
        hint_git.setWordWrap(True)
        hint_git.setStyleSheet(f"color:{THEME['text_dim']}; font-size:10px;")
        form_fs.addRow("", hint_git)

        root.addLayout(form_fs)
        root.addSpacing(6)

        # ── Abschnitt: KI-Tutor ─────────────────────────────────────────
        title5, sep5 = self._section("CHATBOT")
        root.addWidget(title5)
        root.addWidget(sep5)

        form_ai = QFormLayout()
        form_ai.setSpacing(8)
        form_ai.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Radiobuttons: genau ein Chatbot (oder keiner). Alte Ollama-Modi → „kein Chatbot“.
        self._tutor_group = QButtonGroup(self)
        self._tutor_radios: dict[str, QRadioButton] = {}
        for key, label in (("none", "Kein Chatbot"),
                           ("aischat", "ais.chat (Schule)"),
                           ("fobizz", "fobizz.com")):
            rb = QRadioButton(label)
            self._tutor_group.addButton(rb)
            self._tutor_radios[key] = rb
            form_ai.addRow("Chatbot:" if key == "none" else "", rb)
        self._tutor_radios.get(tutor_mode, self._tutor_radios["none"]).setChecked(True)
        root.addLayout(form_ai)

        root.addStretch()

        # ── Buttons (fest unten, immer sichtbar – außerhalb des Scrollbereichs) ──
        btn_bar = QFrame()
        btn_bar.setObjectName("btnBar")
        btn_bar.setStyleSheet(f"QFrame#btnBar {{ background:{THEME['bg_panel']}; border-top:1px solid {THEME['border']}; }}")
        btn_row = QHBoxLayout(btn_bar)
        btn_row.setContentsMargins(20, 10, 20, 12)
        btn_row.addStretch()

        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.setObjectName("cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_ok = QPushButton("Übernehmen")
        btn_ok.setObjectName("ok")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)

        outer.addWidget(btn_bar)

        # Maximalhöhe an den Bildschirm koppeln, damit nie etwas abgeschnitten wird.
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            avail_h = screen.availableGeometry().height()
            self.setMaximumHeight(int(avail_h * 0.92))
            self.resize(660, min(660, int(avail_h * 0.85)))

    def done(self, result: int):
        if self._py_scanner and self._py_scanner.isRunning():
            self._py_scanner.wait(1500)
        super().done(result)

    # ── Hilfsmethoden ───────────────────────────────────────────────────────

    def _browse_python(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Python-Interpreter wählen",
            "/usr/bin",
            "Ausführbare Dateien (*python* *python3*);; Alle Dateien (*)",
        )
        if path:
            self._combo_py.setCurrentText(path)
            self._combo_py.lineEdit().setCursorPosition(0)

    # ── Python-Interpreter automatisch suchen ────────────────────────────────
    def _scan_python_interpreters(self):
        if self._py_scanner and self._py_scanner.isRunning():
            return
        self._btn_scan_py.setEnabled(False)
        self._btn_scan_py.setText("…")
        self._py_scanner = _PythonScanner()
        self._py_scanner.found.connect(self._on_python_found)
        self._py_scanner.start()

    def _on_python_found(self, results: list):
        self._btn_scan_py.setEnabled(True)
        self._btn_scan_py.setText("↻")
        current = self._combo_py.currentText().strip()
        self._py_versions = {}
        self._py_has_tk = {}
        for path, ver, tk in results:
            self._py_versions[path] = ver
            self._py_has_tk[path] = tk
            try:
                real = os.path.realpath(path)
            except OSError:
                real = ""
            if real:
                self._py_versions.setdefault(real, ver)
                self._py_has_tk.setdefault(real, tk)
        self._combo_py.blockSignals(True)
        self._combo_py.clear()
        for path, ver, has_tk in results:
            self._combo_py.addItem(path)
            idx = self._combo_py.count() - 1
            tip = ver
            if ver and not has_tk:
                tip = f"{ver} – ohne tkinter"
            if tip:
                self._combo_py.setItemData(idx, tip, Qt.ItemDataRole.ToolTipRole)
        # Vorherige Auswahl beibehalten; bei leerer Auswahl den bevorzugten
        # ersten Treffer setzen (durch detect_python_interpreters priorisiert).
        selected = ""
        valid_current = False
        if current:
            for path, _ver, _tk in results:
                if current == path:
                    valid_current = True
                    break
                if os.path.exists(current) and os.path.exists(path):
                    try:
                        if os.path.realpath(current) == os.path.realpath(path):
                            valid_current = True
                            break
                    except OSError:
                        pass

        if valid_current:
            selected = current
            self._combo_py.setCurrentText(current)
        elif results:
            selected = results[0][0]
            self._combo_py.setCurrentText(selected)
        self._combo_py.lineEdit().setCursorPosition(0)
        self._combo_py.blockSignals(False)
        self._update_py_version_label(selected)

    def _update_py_version_label(self, text: str):
        path = (text or "").strip()
        if not path:
            n = len(self._py_versions)
            self._lbl_py_version.setText(
                f"Automatisch erkannt – {n} Interpreter gefunden"
                if n else "Automatisch (kein Interpreter gefunden)"
            )
            return
        key = path
        if path not in self._py_versions and os.path.exists(path):
            key = os.path.realpath(path)
        ver = self._py_versions.get(key, "")
        if ver and key in self._py_has_tk and not self._py_has_tk[key]:
            self._lbl_py_version.setText(
                f"{ver}  ·  ⚠ tkinter fehlt (z. B. 'brew install python-tk')"
            )
        else:
            self._lbl_py_version.setText(ver or "")

    def _browse_sketchbook(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Sketchbook-Ordner wählen",
            self._edit_sketchbook.text().strip() or "/home",
        )
        if folder:
            self._edit_sketchbook.setText(folder)

    def _browse_git(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Git-Programm wählen",
            "/usr/bin",
            "Ausführbare Dateien (*git*);; Alle Dateien (*)",
        )
        if path:
            self._combo_git.setCurrentText(path)
            self._combo_git.lineEdit().setCursorPosition(0)

    def _on_plot_axis_changed(self, *_):
        y_fixed = self._combo_plot_y.currentData() == "fixed"
        self._spin_plot_ymin.setEnabled(y_fixed)
        self._spin_plot_ymax.setEnabled(y_fixed)
        x_sweep = self._combo_plot_x.currentData() == "sweep"
        self._spin_plot_xmin.setEnabled(x_sweep)
        self._spin_plot_xmax.setEnabled(x_sweep)

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def ui_font_pt(self) -> int:
        return self._spin_ui_font.value()

    @property
    def font_size(self) -> int:
        return self._spin.value()

    @property
    def line_numbers(self) -> bool:
        return self._chk_lineno.isChecked()

    @property
    def word_wrap(self) -> bool:
        return self._chk_wrap.isChecked()

    @property
    def highlight_line(self) -> bool:
        return self._chk_hl.isChecked()

    @property
    def hidden_activity(self) -> set:
        return {k for k, chk in self._chk_activity.items() if not chk.isChecked()}

    @property
    def blocks_enabled(self) -> bool:
        return self._chk_blocks.isChecked()

    @property
    def editor_font(self) -> str:
        return self._combo_font.currentData()

    @property
    def debug_level(self) -> str:
        return self._combo_dbg_level.currentData()

    @property
    def debug_stepped(self) -> bool:
        return self._chk_dbg_stepped.isChecked()

    @property
    def debug_change_hint(self) -> bool:
        return self._chk_dbg_change.isChecked()

    @property
    def autosave_secs(self) -> int:
        return self._combo_as.currentData()

    @property
    def python_exec(self) -> str:
        return self._combo_py.currentText().strip()

    @property
    def scrollback_lines(self) -> int:
        return self._spin_sb.value()

    @property
    def theme(self) -> str:
        return self._combo_theme.currentData()

    @property
    def code_scheme(self) -> str:
        return self._combo_scheme.currentData()

    @property
    def tutor_mode(self) -> str:
        for key, rb in self._tutor_radios.items():
            if rb.isChecked():
                return key
        return "none"

    @property
    def sketchbook_dir(self) -> str:
        return self._edit_sketchbook.text().strip()

    @property
    def git_exec(self) -> str:
        return self._combo_git.currentText().strip()

    @property
    def plot_y_mode(self) -> str:
        return self._combo_plot_y.currentData()

    @property
    def plot_y_min(self) -> float:
        return self._spin_plot_ymin.value()

    @property
    def plot_y_max(self) -> float:
        return self._spin_plot_ymax.value()

    @property
    def plot_x_mode(self) -> str:
        return self._combo_plot_x.currentData()

    @property
    def plot_x_min(self) -> int:
        return self._spin_plot_xmin.value()

    @property
    def plot_x_max(self) -> int:
        return self._spin_plot_xmax.value()

    @property
    def plot_style(self) -> str:
        return self._combo_plot_style.currentData()
