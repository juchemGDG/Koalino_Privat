"""Debugger für lokales Python: Haltepunkte, Einzelschritt, Variablen beobachten.

Koalino startet das Programm über ``assets/debug/debug_runner.py`` (bdb). Der Runner
meldet sich über einen lokalen Socket (:class:`DebugSession`) und schickt bei jedem
Anhalten Aufrufstapel, Variablen und Beobachtungsausdrücke; :class:`DebugPanel`
zeigt sie an. Programmausgabe und ``input()`` laufen wie sonst über die Konsole.

Gilt nur für lokales Python. MicroPython hat kein ``sys.settrace`` – dort bleibt es bei
Kontrollpunkten und Fehlerprotokoll.
"""
from __future__ import annotations

import json

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtNetwork import QHostAddress, QTcpServer
from PyQt6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QMenu,
    QPushButton, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .config import THEME, asset_path, mono_family


def runner_script() -> str | None:
    p = asset_path("debug/debug_runner.py")
    return str(p) if p else None


class DebugSession(QObject):
    """Wartet auf den Runner und tauscht JSON-Zeilen mit ihm aus."""

    paused = pyqtSignal(dict)
    exited = pyqtSignal()

    def __init__(self, breakpoints: list[int], watches: list[str], step: bool, parent=None):
        super().__init__(parent)
        self._init = {"cmd": "init", "breakpoints": breakpoints, "watches": watches,
                      "step": step}
        self._sock = None
        self._buf = b""
        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._on_connection)
        if not self._server.listen(QHostAddress.SpecialAddress.LocalHost, 0):
            raise OSError(self._server.errorString())

    @property
    def port(self) -> int:
        return self._server.serverPort()

    def _on_connection(self):
        if self._sock is not None:
            self._server.nextPendingConnection().close()
            return
        self._sock = self._server.nextPendingConnection()
        self._server.close()
        self._sock.readyRead.connect(self._on_ready)
        self.send(self._init)

    def _on_ready(self):
        self._buf += bytes(self._sock.readAll())
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            if not line.strip():
                continue
            try:
                msg = json.loads(line.decode("utf-8"))
            except ValueError:
                continue
            if msg.get("event") == "paused":
                self.paused.emit(msg)
            elif msg.get("event") == "exit":
                self.exited.emit()

    def send(self, msg: dict) -> None:
        if self._sock is not None:
            self._sock.write((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
            self._sock.flush()

    def close(self) -> None:
        self._server.close()
        if self._sock is not None:
            self._sock.close()
            self._sock = None


class DebugPanel(QWidget):
    """Leiste mit Schritt-Knöpfen, Variablen, Aufrufstapel und Beobachtungsliste."""

    command = pyqtSignal(str)            # continue | next | step | out | stop
    watches_changed = pyqtSignal(list)
    frame_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._prev: dict = {}
        self._watches: list[str] = []
        self._paused = False
        self._index = 0
        self._build()
        self.setVisible(False)

    # ── Aufbau ────────────────────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        self._status = QLabel("")
        self._status.setTextFormat(Qt.TextFormat.RichText)
        bar.addWidget(self._status, 1)
        self._buttons: dict[str, QPushButton] = {}
        for key, text, tip, keys in (
            ("continue", "▶ Weiter", "Weiter bis zum nächsten Haltepunkt (F8)", "F8"),
            ("next", "↓ Nächste Zeile", "Eine Zeile ausführen, Funktionsaufrufe als Ganzes (F10)", "F10"),
            ("step", "⤵ Hinein", "In die aufgerufene Funktion hineinspringen (F11)", "F11"),
            ("out", "⤴ Heraus", "Funktion zu Ende laufen lassen (Umschalt+F11)", "Shift+F11"),
            ("stop", "■ Beenden", "Debuggen beenden", ""),
        ):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.command.emit(k))
            self._buttons[key] = b
            bar.addWidget(b)
        root.addLayout(bar)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(1)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Variable", "Typ", "Wert"])
        self._tree.setRootIsDecorated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setStretchLastSection(True)
        split.addWidget(self._tree)

        side = QWidget()
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(2)
        self._stack_label = QLabel("Aufrufstapel")
        sl.addWidget(self._stack_label)
        self._stack = QListWidget()
        self._stack.setMaximumHeight(70)
        self._stack.currentRowChanged.connect(self._on_stack_row)
        sl.addWidget(self._stack)
        self._watch_label = QLabel("Beobachten")
        sl.addWidget(self._watch_label)
        self._watch_tree = QTreeWidget()
        self._watch_tree.setHeaderHidden(True)
        self._watch_tree.setRootIsDecorated(False)
        self._watch_tree.setColumnCount(2)
        self._watch_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._watch_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._watch_tree.customContextMenuRequested.connect(self._watch_menu)
        sl.addWidget(self._watch_tree, 1)
        self._watch_edit = QLineEdit()
        self._watch_edit.setPlaceholderText("Ausdruck beobachten, z. B. summe * 2 – Enter")
        self._watch_edit.returnPressed.connect(self._add_watch)
        sl.addWidget(self._watch_edit)
        split.addWidget(side)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        root.addWidget(split, 1)

        self.apply_theme()
        self._set_buttons(False)

    def apply_theme(self):
        t = THEME
        self.setStyleSheet(f"""
            DebugPanel {{ background:{t['bg_panel']}; border-top:1px solid {t['border']}; }}
            QLabel {{ color:{t['text']}; }}
            QTreeWidget, QListWidget, QLineEdit {{
                background:{t['bg_editor']}; color:{t['text']};
                border:1px solid {t['border']}; font-family:{mono_family()}; font-size:12px; }}
            QHeaderView::section {{ background:{t['bg_mid']}; color:{t['text']};
                border:none; border-right:1px solid {t['border']}; padding:2px 6px; }}
            QPushButton {{ background:{t['bg_mid']}; color:{t['text']};
                border:1px solid {t['border']}; border-radius:5px; padding:3px 9px; }}
            QPushButton:hover {{ border-color:{t['accent']}; }}
            QPushButton:disabled {{ color:{t['text_dim']}; }}
        """)

    # ── Zustand ───────────────────────────────────────────────────────────
    def start(self, step: bool):
        self._prev = {}
        self._tree.clear()
        self._stack.clear()
        self._set_buttons(False)
        self._status.setText("Programm läuft … " + ("(startet im Einzelschritt)" if step else
                                                    "(bis zum ersten Haltepunkt)"))
        self.setVisible(True)
        self._refresh_watch_rows([{"expr": e} for e in self._watches])

    def finish(self):
        self._paused = False
        self.setVisible(False)

    def set_running(self):
        self._paused = False
        self._set_buttons(False)
        self._status.setText("Programm läuft …")

    def _set_buttons(self, paused: bool):
        for k, b in self._buttons.items():
            b.setEnabled(paused or k == "stop")

    def watches(self) -> list[str]:
        return list(self._watches)

    def current_index(self) -> int:
        return self._index

    def is_paused(self) -> bool:
        return self._paused

    # ── Anzeige beim Anhalten ─────────────────────────────────────────────
    def show_paused(self, msg: dict):
        fresh = msg.get("reason", "stop") == "stop"
        self._index = msg.get("index", 0)
        self._paused = True
        self._set_buttons(True)
        stack = msg.get("stack", [])
        idx = msg.get("index", 0)
        if stack:
            top = stack[idx]
            self._status.setText(
                f"<b>Angehalten in Zeile {msg.get('line')}</b>"
                f"<span style='color:{THEME['text_dim']}'> · {self._where(top['name'])}</span>")
        self._fill_stack(stack, idx)
        self._fill_vars(msg.get("scopes", []), stack[idx]["name"] if stack else "",
                        compare=fresh)
        self._refresh_watch_rows(msg.get("watches", []))

    @staticmethod
    def _where(name: str) -> str:
        return "Hauptprogramm" if name == "<module>" else f"Funktion {name}"

    def _fill_stack(self, stack: list, idx: int):
        self._stack.blockSignals(True)
        self._stack.clear()
        for i, fr in enumerate(stack):
            self._stack.addItem(f"{self._where(fr['name'])}, Zeile {fr['line']}")
        self._stack.setCurrentRow(idx)
        self._stack.blockSignals(False)

    def _on_stack_row(self, row: int):
        if row >= 0 and self._paused:
            self.frame_selected.emit(row)

    def _fill_vars(self, scopes: list, fname: str, compare: bool):
        self._tree.clear()
        new_prev = {}
        hi = QBrush(QColor(250, 204, 21, 110))
        for sc in scopes:
            local = sc["name"].startswith("Lokale")
            head = QTreeWidgetItem([sc["name"], "", ""])
            f = head.font(0)
            f.setBold(True)
            for c in range(3):
                head.setFont(c, f)
                head.setForeground(c, QBrush(QColor(THEME["text_dim"])))
            self._tree.addTopLevelItem(head)
            if not sc["vars"]:
                head.addChild(QTreeWidgetItem(["(noch keine)", "", ""]))
            for v in sc["vars"]:
                key = (fname if local else "", v["name"])
                new_prev[key] = v["value"]
                item = QTreeWidgetItem([v["name"], v["type"], v["value"]])
                item.setToolTip(2, v["value"])
                if compare and self._prev.get(key) != v["value"] and self._prev:
                    for c in range(3):
                        item.setBackground(c, hi)
                        item.setForeground(c, QBrush(QColor("#1a1a1a")))
                    item.setToolTip(0, "neu oder geändert seit dem letzten Halt")
                head.addChild(item)
            head.setExpanded(True)
        if compare:
            self._prev = new_prev

    # ── Beobachten ────────────────────────────────────────────────────────
    def _add_watch(self):
        expr = self._watch_edit.text().strip()
        self._watch_edit.clear()
        if expr and expr not in self._watches:
            self._watches.append(expr)
            self.watches_changed.emit(self.watches())
            self._refresh_watch_rows([{"expr": e} for e in self._watches])

    def _watch_menu(self, pos):
        item = self._watch_tree.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        act = menu.addAction("Nicht mehr beobachten")
        if menu.exec(self._watch_tree.viewport().mapToGlobal(pos)) is act:
            expr = item.data(0, Qt.ItemDataRole.UserRole)
            if expr in self._watches:
                self._watches.remove(expr)
                self.watches_changed.emit(self.watches())
                self._refresh_watch_rows([{"expr": e} for e in self._watches])

    def _refresh_watch_rows(self, rows: list):
        self._watch_tree.clear()
        for r in rows:
            if "error" in r:
                text, color = r["error"], THEME["error"]
            elif "value" in r:
                text, color = f"{r['value']}", THEME["text"]
            else:
                text, color = "", THEME["text_dim"]
            item = QTreeWidgetItem([r["expr"], text])
            item.setData(0, Qt.ItemDataRole.UserRole, r["expr"])
            item.setForeground(1, QBrush(QColor(color)))
            if "type" in r:
                item.setToolTip(1, r["type"])
            self._watch_tree.addTopLevelItem(item)
