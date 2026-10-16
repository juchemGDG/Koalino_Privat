"""Kleine Qt-Hilfsfunktionen, die mehrere Module gemeinsam nutzen."""
import re
import sys
from pathlib import Path

from PyQt6.QtCore import QThread
from PyQt6.QtGui import QIcon, QPixmap


def retain_thread(registry: list, thread: QThread) -> None:
    """Hält eine Referenz auf einen QThread, bis sein ``finished``-Signal feuert.

    Verhindert, dass Python den QThread per GC einsammelt, während er noch
    läuft ('QThread destroyed while still running' → Absturz). Der Thread wird
    sofort in ``registry`` aufgenommen und beim Beenden automatisch entfernt.
    """
    registry.append(thread)
    thread.finished.connect(
        lambda t=thread: registry.remove(t) if t in registry else None
    )


# ──────────────────────────────────────────────────────────────────────────────
# Skalierung der Oberflächenschrift (nicht Editor/Shell/Terminal)
# ──────────────────────────────────────────────────────────────────────────────
UI_FONT_PT_DEFAULT = 10      # entspricht der bisherigen Größe (13 px) → Faktor 1.0
UI_FONT_PT_RANGE = (9, 16)

_ui_scale = 1.0
_FONT_SIZE_PX = re.compile(r"(font-size\s*:\s*)(\d+(?:\.\d+)?)px", re.IGNORECASE)


def ui_scale() -> float:
    return _ui_scale


def scale_px(value: int) -> int:
    """Skaliert eine Pixelangabe (Mindestgrößen ≤ 2 px bleiben, z. B. Trennlinien)."""
    if _ui_scale == 1.0 or value <= 2:
        return value
    return max(1, round(value * _ui_scale))


def scale_css_px(css: str) -> str:
    """Skaliert alle ``font-size: Npx``-Angaben in einem CSS-/HTML-Text."""
    if _ui_scale == 1.0 or "font-size" not in css:
        return css
    return _FONT_SIZE_PX.sub(
        lambda m: f"{m.group(1)}{round(float(m.group(2)) * _ui_scale, 1):g}px", css
    )


def install_ui_scale(pt: int) -> None:
    """Aktiviert die Oberflächen-Skalierung (einmal, vor dem Bauen der Widgets).

    Die Stylesheets im Code nennen ihre Schriftgrößen fest in ``px``. Statt jede
    der vielen Stellen anzufassen, skalieren wir zentral: ``setStyleSheet`` rechnet
    ``font-size``-Angaben um, und feste Widget-Größen (Kopfzeilen, Icon-Buttons)
    wachsen im gleichen Verhältnis mit – so verschiebt sich das Layout nicht.
    """
    global _ui_scale
    lo, hi = UI_FONT_PT_RANGE
    _ui_scale = max(lo, min(hi, int(pt))) / UI_FONT_PT_DEFAULT
    if _ui_scale == 1.0:
        return

    from PyQt6.QtCore import QSize
    from PyQt6.QtWidgets import QApplication, QWidget

    orig_qw_style = QWidget.setStyleSheet
    orig_app_style = QApplication.setStyleSheet
    orig_fixed_w = QWidget.setFixedWidth
    orig_fixed_h = QWidget.setFixedHeight
    orig_fixed_size = QWidget.setFixedSize

    QWidget.setStyleSheet = lambda self, css: orig_qw_style(self, scale_css_px(css))
    QApplication.setStyleSheet = lambda self, css: orig_app_style(self, scale_css_px(css))
    QWidget.setFixedWidth = lambda self, w: orig_fixed_w(self, scale_px(w))
    QWidget.setFixedHeight = lambda self, h: orig_fixed_h(self, scale_px(h))

    def _fixed_size(self, *args):
        if len(args) == 2:
            return orig_fixed_size(self, scale_px(args[0]), scale_px(args[1]))
        size = args[0]
        return orig_fixed_size(self, QSize(scale_px(size.width()), scale_px(size.height())))

    QWidget.setFixedSize = _fixed_size


def find_logo() -> QIcon:
    """Sucht logo.png im Paket- oder Projektordner (Dev- wie Frozen-Modus)."""
    candidates = []
    if getattr(sys, "frozen", False):
        # PyInstaller-Bundle: logo.png liegt neben der EXE in koalino/
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "koalino" / "logo.png")
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "koalino" / "logo.png")
    candidates += [
        Path(__file__).resolve().parent / "logo.png",           # koalino/logo.png
        Path(__file__).resolve().parent.parent / "logo.png",    # Projektordner/logo.png
    ]
    for p in candidates:
        if p.exists():
            px = QPixmap(str(p))
            if not px.isNull():
                return QIcon(px)
    return QIcon()


# ──────────────────────────────────────────────────────────────────────────────
# Einheitliche Auswahlliste (statt des nativen, auf dem Mac weißen Popups)
# ──────────────────────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import QComboBox, QMenu  # noqa: E402


class ThemedComboBox(QComboBox):
    """QComboBox, die ihre Liste als gestyltes Menü aufklappt.

    Das native macOS-Popup ignoriert Stylesheets; dieses Menü sieht überall
    gleich aus (wie die Geräte-Pille in der Hauptleiste). Die Schnittstelle
    bleibt die einer normalen QComboBox.
    """

    def showPopup(self):
        from .config import THEME as t
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {t['bg_panel']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
            QMenu::item:selected {{ background: {t['selection']}; color: {t['accent']}; }}
            QMenu::item:checked {{ font-weight: bold; color: {t['accent']}; }}
            QMenu::item:disabled {{ color: {t['text_dim']}; }}
        """)
        menu.setMinimumWidth(self.width())
        for i in range(self.count()):
            act = menu.addAction(self.itemText(i))
            act.setCheckable(True)
            act.setChecked(i == self.currentIndex())
            act.setData(i)
        chosen = menu.exec(self.mapToGlobal(self.rect().bottomLeft()))
        if chosen is not None:
            self.setCurrentIndex(chosen.data())

    def hidePopup(self):
        pass

    def paintEvent(self, event):
        super().paintEvent(event)
        # Kleiner Pfeil rechts – das native ist durch das Stylesheet verschwunden.
        from PyQt6.QtCore import Qt, QPointF
        from PyQt6.QtGui import QColor, QPainter, QPen
        from .config import THEME as t
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(t["text_dim"]), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        x, y = self.width() - 16, self.height() / 2
        p.drawPolyline([QPointF(x - 4, y - 2), QPointF(x, y + 2), QPointF(x + 4, y - 2)])
        p.end()


_tab_close_dir = None


def tab_close_icons(normal: str, hover: str) -> tuple[str, str]:
    """Zeichnet das Tab-Schließen-Kreuz (normal/hover) und liefert die Dateipfade für QSS."""
    global _tab_close_dir
    import tempfile
    from PyQt6.QtCore import Qt, QPointF
    from PyQt6.QtGui import QColor, QPainter, QPen
    if _tab_close_dir is None:
        _tab_close_dir = tempfile.mkdtemp(prefix="koalino_icons_")
    paths = []
    for name, color, bg in (("normal", normal, None), ("hover", hover, "#ef4444")):
        pm = QPixmap(48, 48)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if bg:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(bg))
            p.drawEllipse(QPointF(24, 24), 22, 22)
            color = "#ffffff"
        pen = QPen(QColor(color), 5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(16, 16), QPointF(32, 32))
        p.drawLine(QPointF(32, 16), QPointF(16, 32))
        p.end()
        path = f"{_tab_close_dir}/close_{name}.png"
        pm.save(path)
        paths.append(path)
    return paths[0], paths[1]
