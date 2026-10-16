"""Eigene Bedienelemente der Hauptleiste: Modus-Schalter und Geräte-Auswahl.

Statt zweier Standard-Comboboxen (deren Aufklappmenü je nach Betriebssystem
nativ und uneinheitlich aussieht) gibt es einen segmentierten Schalter
„Python | MicroPython“ und eine Geräte-„Pille“ mit Statuspunkt.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QMenu, QPushButton, QToolButton,
)

from .config import THEME


class ModeSwitch(QFrame):
    """Segmentierter Schalter für den Ausführungsmodus (genau ein Segment aktiv)."""

    modeChanged = pyqtSignal(str)

    def __init__(self, options: list[tuple[str, str, str]], parent=None):
        """``options``: Liste aus (Schlüssel, Beschriftung, Tooltip)."""
        super().__init__(parent)
        self.setObjectName("modeSwitch")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for key, label, tip in options:
            btn = QPushButton(label)
            btn.setObjectName("modeSegment")
            btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._group.addButton(btn)
            self._buttons[key] = btn
            lay.addWidget(btn)
            btn.toggled.connect(lambda on, k=key: on and self.modeChanged.emit(k))
        self.apply_theme()

    def mode(self) -> str:
        for key, btn in self._buttons.items():
            if btn.isChecked():
                return key
        return next(iter(self._buttons))

    def set_mode(self, key: str):
        btn = self._buttons.get(key)
        if btn is not None:
            btn.setChecked(True)

    def apply_theme(self):
        t = THEME
        self.setStyleSheet(f"""
            QFrame#modeSwitch {{
                background: {t['bg_dark']};
                border: 1px solid {t['border']};
                border-radius: 10px;
            }}
            QPushButton#modeSegment {{
                background: transparent;
                color: {t['text_dim']};
                border: none;
                border-radius: 7px;
                padding: 5px 16px;
                font-size: 13px;
            }}
            QPushButton#modeSegment:hover:!checked {{
                background: {t['selection']};
                color: {t['text']};
            }}
            QPushButton#modeSegment:checked {{
                background: {t['accent']};
                color: white;
            }}
        """)


class PortPicker(QToolButton):
    """Geräte-Auswahl als Pille mit Statuspunkt und eigenem Aufklappmenü.

    Bietet die kleine Teilmenge der QComboBox-Schnittstelle, die die
    Hauptleiste braucht (``clear``/``addItem``/``itemData``/``currentData`` …),
    ``currentIndexChanged`` wird nur bei einer Auswahl durch den Menschen
    ausgelöst.
    """

    currentIndexChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("portPicker")
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Angeschlossenes Gerät (Controller) auswählen")
        self.setMinimumWidth(190)
        self._items: list[tuple[str, object]] = []
        self._index = -1
        self._menu = QMenu(self)
        self._menu.aboutToShow.connect(self._build_menu)
        self.setMenu(self._menu)
        self._update_text()

    # ── QComboBox-ähnliche Schnittstelle ────────────────────────────────
    def clear(self):
        self._items = []
        self._index = -1
        self._update_text()

    def addItem(self, label: str, data=None):
        self._items.append((label, data))
        if self._index < 0:
            self._index = 0
        self._update_text()

    def count(self) -> int:
        return len(self._items)

    def itemData(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index][1]
        return None

    def currentData(self):
        return self.itemData(self._index)

    def currentIndex(self) -> int:
        return self._index

    def findData(self, data) -> int:
        for i, (_label, d) in enumerate(self._items):
            if d == data:
                return i
        return -1

    def setCurrentIndex(self, index: int):
        if 0 <= index < len(self._items):
            self._index = index
            self._update_text()

    # ── Darstellung ──────────────────────────────────────────────────────
    def _build_menu(self):
        self._menu.clear()
        for i, (label, data) in enumerate(self._items):
            act = self._menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(i == self._index)
            act.setEnabled(data is not None)
            act.triggered.connect(lambda _c=False, idx=i: self._choose(idx))

    def _choose(self, index: int):
        changed = index != self._index
        self.setCurrentIndex(index)
        if changed:
            self.currentIndexChanged.emit(index)

    def _update_text(self):
        connected = self.currentData() is not None
        label = self._items[self._index][0] if self._index >= 0 else "Kein Gerät"
        if len(label) > 34:
            label = label[:33] + "…"
        self.setText(f"●  {label}  ▾")
        self.setProperty("connected", connected)
        self.style().unpolish(self)
        self.style().polish(self)

    def apply_theme(self):
        t = THEME
        self.setStyleSheet(f"""
            QToolButton#portPicker {{
                background: {t['bg_dark']};
                color: {t['text_dim']};
                border: 1px solid {t['border']};
                border-radius: 14px;
                padding: 5px 14px;
                font-size: 13px;
            }}
            QToolButton#portPicker:hover {{
                border-color: {t['accent']};
                color: {t['text']};
            }}
            QToolButton#portPicker[connected="true"] {{
                color: {t['text']};
                border-color: {t['accent']};
            }}
            QToolButton#portPicker::menu-indicator {{ image: none; width: 0; }}
        """)
        self._menu.setStyleSheet(f"""
            QMenu {{
                background: {t['bg_panel']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
            QMenu::item:selected {{ background: {t['selection']}; color: {t['accent']}; }}
            QMenu::item:disabled {{ color: {t['text_dim']}; }}
        """)
