"""Gemeinsamer Aufbau der eingebetteten Web-Ansichten (QtWebEngine).

Block-Editor, PAP-/IBD-Editor, Arbeitsblatt-Vorschau, py.nitbw.de und die Chat-
Panels bauen alle dieselbe Kette: Off-the-record-Profil → View → Page. Das
steht hier an einer Stelle, ebenso der Hinweis bei fehlender WebEngine und der
einmalige Reload nach einem Absturz des Chromium-Renderprozesses.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QMessageBox

try:
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except Exception:
    HAS_WEBENGINE = False
    QWebEnginePage = QWebEngineProfile = QWebEngineSettings = QWebEngineView = None

from .config import THEME


def make_offtherecord_view(parent, *, clipboard: bool = False, user_agent: str | None = None,
                           on_render_crashed=None, page_class=None):
    """Erzeugt eine QWebEngineView mit Off-the-record-Profil; ``None``, wenn das nicht geht.

    Das Profil bekommt keinen Namen und legt deshalb nichts auf der Platte ab (auf
    Servern mit gesperrtem oder umgeleitetem %LOCALAPPDATA% verhindert das
    außerdem Schreibfehler beim Anlegen des Chromium-Profils). Auf stark
    eingeschränkten Schulrechnern schlägt die WebEngine-Initialisierung
    gelegentlich fehl – dann gibt es ``None`` statt eines Absturzes, und der
    Aufrufer zeigt :func:`webengine_missing_label`.

    ``clipboard``: JavaScript darf die Zwischenablage nutzen (Copy-Buttons).
    ``user_agent``: eigener User-Agent für das Profil.
    ``on_render_crashed``: Aufrufbar für ``renderProcessTerminated``
    (siehe :class:`RenderCrashHandler`).
    ``page_class``: eigene QWebEnginePage-Unterklasse (Signatur wie QWebEnginePage).
    """
    if not HAS_WEBENGINE:
        return None
    try:
        # Reihenfolge: Profil als erstes Kind, View danach. Qt löscht Kinder
        # rückwärts, also View (+ Page) vor dem Profil – sonst warnt Qt beim Beenden.
        profile = QWebEngineProfile(parent)
        if user_agent:
            profile.setHttpUserAgent(user_agent)
        view = QWebEngineView(parent)
        page = (page_class or QWebEnginePage)(profile, view)
        if clipboard:
            settings = page.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanPaste, True)
        view.setPage(page)
        if on_render_crashed is not None:
            page.renderProcessTerminated.connect(on_render_crashed)
        return view
    except Exception:
        return None


def webengine_missing_label(name: str) -> QLabel:
    """Hinweis-Label, wenn ``name`` ohne QtWebEngine nicht angezeigt werden kann."""
    lbl = QLabel(
        f"Der {name} ist nicht verfügbar.\n\n"
        "Er benötigt PyQt6-WebEngine:\n\n"
        "    pip install PyQt6-WebEngine"
    )
    lbl.setWordWrap(True)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(f"color:{THEME['text']}; font-size:13px; padding:24px;")
    return lbl


class RenderCrashHandler:
    """Slot für ``renderProcessTerminated``: erst einmal neu laden, dann Hinweis.

    Stürzt der Chromium-Renderprozess ab (typisch: GPU-/Treiberproblem auf
    Servern), wird die Seite einmal automatisch neu geladen statt ein schwarzes
    Fenster zu zeigen. Beim zweiten Absturz erscheint ein Hinweis mit dem
    Software-Rendering-Workaround.

    ``reload``: Aufrufbar ohne Argumente, das die Ansicht neu lädt.
    ``title``: Fenstertitel des Hinweises; ``name``: Bezeichnung im Text
    („Die Anzeige des <name> ist abgestürzt“), Standard ist ``title``.
    """

    def __init__(self, parent, title: str, reload, name: str | None = None):
        self._parent = parent
        self._title = title
        self._name = name or title
        self._reload = reload
        self._retry_done = False

    def __call__(self, _status, _exit_code):
        if not self._retry_done:
            self._retry_done = True
            self._reload()
            return
        QMessageBox.warning(
            self._parent, self._title,
            f"Die Anzeige des {self._name} ist abgestürzt (Grafik-Problem).\n\n"
            "Unter Windows ist Software-Rendering bereits automatisch aktiv.\n"
            "Falls der Fehler weiter auftritt, Koalino neu starten.\n\n"
            "Optionaler Override:\n"
            "    NIT_SOFTWARE_RENDER=1\n"
            "(erzwingt Software-Rendering vor dem Start).",
        )
