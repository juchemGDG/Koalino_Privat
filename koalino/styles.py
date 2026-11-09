"""Stylesheets von Koalino: globales Design (Theme-abhängig) und Hell-Modus-Stile für Dialoge."""
from .config import THEME


# ──────────────────────────────────────────────────────────────────────────────
# Globales Stylesheet (als Funktion, damit Theme-Wechsel möglich ist)
# ──────────────────────────────────────────────────────────────────────────────
def build_global_style() -> str:
    t = THEME
    scroll = t.get("scroll", t["border"])
    from .qt_utils import tab_close_icons
    _close_n, _close_h = tab_close_icons(t["text"], "#ffffff")
    return f"""
QMainWindow, QWidget {{
    background: {t['bg_dark']};
    color: {t['text']};
    font-family: Helvetica, Arial, 'Segoe UI', 'Ubuntu', sans-serif;
    font-size: 13px;
}}
QToolTip {{
    background: {t['text']};
    color: {t['bg_dark']};
    border: none;
    border-radius: 6px;
    padding: 4px 8px;
}}
QMenuBar {{
    background: {t['bg_panel']};
    color: {t['text']};
    border-bottom: 1px solid {t['border']};
    padding: 3px 8px;
}}
QMenuBar::item {{
    padding: 5px 12px;
    margin: 0 1px;
    border-radius: 6px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background: {t['selection']};
    color: {t['accent']};
}}
/* Rechtsbündiger Knopf am rechten Ende der Toolbar */
QPushButton#papToolButton {{
    background: transparent;
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 5px 14px;
    margin: 2px 4px 2px 0;
    font-weight: bold;
}}
QPushButton#papToolButton:hover {{
    background: {t['accent']};
    border-color: {t['accent']};
    color: white;
}}
QMenu {{
    background: {t['bg_panel']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 6px 22px 6px 14px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {t['selection']};
    color: {t['accent']};
}}
QMenu::item:disabled {{
    color: {t['text_dim']};
}}
QMenu::separator {{
    height: 1px;
    background: {t['border']};
    margin: 4px 8px;
}}
QTabWidget::pane {{
    border: none;
    background: {t['bg_editor']};
}}
QTabBar {{
    background: {t['bg_dark']};
}}
QTabBar::tab {{
    background: transparent;
    color: {t['text_dim']};
    padding: 8px 16px;
    margin: 4px 2px 0 2px;
    border: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    min-width: 80px;
}}
QTabBar::tab:selected {{
    background: {t['bg_editor']};
    color: {t['text']};
    font-weight: bold;
    border-bottom: 2px solid {t['accent']};
}}
QTabBar::tab:hover:!selected {{
    background: {t['selection']};
    color: {t['text']};
}}
QTabBar::close-button {{
    subcontrol-position: right;
    image: url({_close_n});
    width: 16px;
    height: 16px;
    margin-left: 6px;
}}
QTabBar::close-button:hover {{
    image: url({_close_h});
}}
QSplitter::handle {{
    background: {t['border']};
}}
QSplitter::handle:hover {{
    background: {t['accent']};
}}
QToolBar {{
    background: {t['bg_panel']};
    border: none;
    border-bottom: 1px solid {t['border']};
    spacing: 6px;
    padding: 6px 10px;
}}
QToolBar::separator {{
    background: {t['border']};
    width: 1px;
    margin: 4px 6px;
}}
QToolButton {{
    background: transparent;
    color: {t['text']};
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 13px;
}}
QToolButton:hover {{
    background: {t['selection']};
    color: {t['accent']};
}}
QToolButton:pressed, QToolButton:checked {{
    background: {t['selection']};
    border-color: {t['accent']};
    color: {t['accent']};
}}
/* Primäraktion „Starten“ – wie der Anmelden-Knopf der MINT-Checker-Seiten */
QToolButton#runButton {{
    background: {t['accent']};
    color: white;
    font-weight: bold;
    padding: 6px 16px;
}}
QToolButton#runButton:hover {{
    background: {t['accent_hover']};
    color: white;
}}
QToolButton#stopButton {{
    border: 1px solid {t['border']};
}}
QToolButton#stopButton:hover {{
    background: {t['error']};
    border-color: {t['error']};
    color: white;
}}
/* Seitenleiste: wie die dunkle Sidebar der MINT-Checker-Seiten */
QWidget#activityBar {{
    background: {t.get('sidebar', '#0f172a')};
    border-right: 1px solid {t['border']};
}}
QToolButton#activityButton {{
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 0;
}}
QToolButton#activityButton:hover {{
    background: #1e293b;
}}
QToolButton#activityButton:checked {{
    background: {t['accent']};
}}
QComboBox {{
    background: {t['bg_dark']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 5px 10px;
}}
QComboBox:hover {{
    border-color: {t['accent']};
}}
QComboBox QAbstractItemView {{
    background: {t['bg_panel']};
    color: {t['text']};
    border: 1px solid {t['border']};
    selection-background-color: {t['selection']};
    selection-color: {t['accent']};
    outline: none;
}}
QStatusBar {{
    background: {t['bg_panel']};
    color: {t['text_dim']};
    border-top: 1px solid {t['border']};
    font-size: 11px;
    padding: 2px 8px;
}}
QStatusBar::item {{
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {scroll};
    border-radius: 3px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t['text_dim']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0;
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {scroll};
    border-radius: 3px;
    min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {t['text_dim']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    width: 0;
    background: transparent;
}}
"""


# ──────────────────────────────────────────────────────────────────────────────
# Hell-Modus-Stile für Standard-Dialoge (gemeinsam genutzt)
# ──────────────────────────────────────────────────────────────────────────────
def _light_dialog_controls_qss(scope: str = "") -> str:
    """Eingabefeld-/Button-Stile für Dialoge auf hellen System-Paletten.

    ``scope`` schränkt die Selektoren optional ein (z. B. "QInputDialog"),
    damit die Regeln nur innerhalb dieses Dialogtyps greifen.
    """
    s = f"{scope} " if scope else ""
    return f"""
        {s}QLineEdit, {s}QComboBox, {s}QListView {{
            background: #ffffff;
            color: #111827;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 4px 6px;
        }}
        {s}QPushButton {{
            background: #e2e8f0;
            color: #111827;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 6px 14px;
        }}
        {s}QPushButton:hover {{ background: #cbd5e1; }}
    """
