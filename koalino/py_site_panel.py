"""Lehrgang py.nitbw.de als Seitenleiste (dritte Ansicht neben KI-Assistent und Fehlerprotokoll).

Die Seite wird erst beim ersten Einblenden geladen, damit der Start nicht von
einer Netzabfrage abhängt. Ohne PyQt6-WebEngine zeigt das Panel einen Hinweis
und einen Knopf, der die Seite im Browser öffnet.
"""
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

try:
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except Exception:
    HAS_WEBENGINE = False

from .config import PY_SITE_URL, THEME


class PySitePanel(QWidget):
    """Seitenleiste „🌐 py.nitbw.de“."""

    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view = None
        self._loaded = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QWidget()
        head.setStyleSheet(f"background:{THEME['bg_dark']};")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(10, 6, 6, 6)
        title = QLabel("🌐  py.nitbw.de")
        title.setStyleSheet(f"color:{THEME['text']}; font-weight:bold;")
        hl.addWidget(title, 1)
        self._btn_reload = self._tool_button("↻", "Seite neu laden", self.reload)
        hl.addWidget(self._btn_reload)
        hl.addWidget(self._tool_button("↗", "Im Browser öffnen", self._open_external))
        hl.addWidget(self._tool_button("✕", "Schließen", self.close_requested.emit))
        lay.addWidget(head)

        if HAS_WEBENGINE:
            try:
                # Off-the-record-Profil wie bei PAP/IBD-Editor (keine Daten auf der Platte).
                self._profile = QWebEngineProfile(self)
                self._view = QWebEngineView(self)
                self._view.setPage(QWebEnginePage(self._profile, self._view))
                lay.addWidget(self._view, 1)
            except Exception:
                self._view = None
        if self._view is None:
            self._btn_reload.setEnabled(False)
            msg = QLabel("Die Seite kann hier nicht angezeigt werden.\n"
                         "Sie benötigt PyQt6-WebEngine.")
            msg.setWordWrap(True)
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setStyleSheet(f"color:{THEME['text']}; padding:24px;")
            lay.addWidget(msg, 1)

    @staticmethod
    def _tool_button(text, tip, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setToolTip(tip)
        btn.setFixedSize(28, 28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton{{background:transparent; color:{THEME['text']}; border:none;"
            f" border-radius:4px;}} QPushButton:hover{{background:{THEME['border']};}}")
        btn.clicked.connect(lambda _=False: slot())
        return btn

    def ensure_loaded(self):
        """Seite beim ersten Anzeigen laden."""
        if self._view is not None and not self._loaded:
            self._loaded = True
            self._view.setUrl(QUrl(PY_SITE_URL))

    def reload(self):
        if self._view is not None:
            self._loaded = True
            self._view.setUrl(QUrl(PY_SITE_URL))

    def _open_external(self):
        QDesktopServices.openUrl(QUrl(PY_SITE_URL))
