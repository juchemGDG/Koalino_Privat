"""Hilfe → „Fehler finden: Schritt für Schritt“: das Cheatsheet Klasse 8/9 (ohne Beispiel),
je ein Blatt für lokales Python und MicroPython. Der Text kommt aus :mod:`debug_guide` – derselbe wie in Konsole
und Fehlerprotokoll."""
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QDialog, QTabWidget, QTextBrowser, QVBoxLayout

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    _WEBENGINE = True
except ImportError:      # ohne WebEngine: einfache Qt-Ansicht
    _WEBENGINE = False

from .config import asset_path
from . import debug_guide as guide
from .debug_guide import LEVEL_KL10, LEVEL_KL89, cheat_sheet_html


class DebugMapDialog(QDialog):
    def __init__(self, parent=None, level: str = LEVEL_KL10):
        super().__init__(parent)
        self.setWindowTitle("🗺  Fehler finden: Schritt für Schritt")
        self.resize(900, 860)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self._tabs = QTabWidget()
        lay.addWidget(self._tabs)
        self._views: list = []
        folder = asset_path("debug")          # hier liegt auch das IBD-Bild
        base = QUrl.fromLocalFile(str(folder) + "/") if folder else QUrl()
        # Reihenfolge: zuerst die Blätter des aktuellen Modus (lokal / MicroPython)
        modes = [guide.mode()] + [m for m in (guide.MODE_LOCAL, guide.MODE_DEVICE) if m != guide.mode()]
        self._tab_keys: list[tuple[str, str]] = []
        for mode, key in ((m, LEVEL_KL89) for m in modes):   # Fehlersuche immer Kl. 8/9
            page = cheat_sheet_html(key, mode)
            if _WEBENGINE:
                view = QWebEngineView(self)
                view.setHtml(page, base)
            else:
                view = QTextBrowser(self)
                if folder:
                    view.setSearchPaths([str(folder)])
                view.setHtml(page)
            self._views.append(view)
            self._tab_keys.append((mode, key))
            self._tabs.addTab(view, "Lokales Python" if guide.is_local(mode) else "MicroPython")
        self.set_level(level)

    def set_level(self, level: str):
        """Blatt zum aktuellen Modus zeigen (Stufe ist immer Klasse 8/9)."""
        self._tabs.setCurrentIndex(self._tab_keys.index((guide.mode(), LEVEL_KL89)))
