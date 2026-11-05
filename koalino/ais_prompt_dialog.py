"""Dialog „NiT_Coder (ais.chat)" (Hilfe-Menü).

Zeigt die Vorlage, mit der Lehrkräfte den Code-Generator als eigenen
Dialogpartner auf ais.chat anlegen können. Die Felder entsprechen der
Eingabemaske von ais.chat (Name, Kurzbeschreibung, Sprachmodell,
Instruktionen, Einstiegsfrage, Hintergrundwissen); jedes Feld lässt sich
einzeln in die Zwischenablage kopieren. Die Instruktionen sind identisch
mit dem System-Prompt des eingebauten Code-Generators (coder_panel.py),
damit sich beide Varianten gleich verhalten.
"""
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QWidget,
)

from .qt_utils import ThemedComboBox
from .config import AIS_CHAT_URL, THEME
from .coder_panel import LEVEL_KL10, LEVEL_KL89, coder_system_prompt

_NAME = "NiT_Coder"

_KURZBESCHREIBUNG = (
    "Code-Generator für den Informatikunterricht: setzt vollständige "
    "Spezifikationen (EINGABE, ABLAUF, AUSGABE, VARIABLEN) in "
    "MicroPython-Code für den ESP32 um – entwirft aber nie selbst den "
    "Algorithmus."
)

_SPRACHMODELL = (
    "Empfehlung: mindestens GPT-5 mini. Kleinere Modelle (z. B. GPT-5 nano) "
    "halten die Regeln – kein eigener Algorithmus-Entwurf, keine doppelten "
    "Rückfragen – weniger zuverlässig ein."
)

_EINSTIEGSFRAGE = (
    "Hallo! Ich bin der NiT_Coder. Beschreibe mir deine Spezifikation – "
    "EINGABE, ABLAUF, AUSGABE und VARIABLEN – und ich setze sie in "
    "Python-Code um."
)

_IBD_HINWEIS = (
    "Ab Klasse 10 kannst du dem NiT_Coder zusätzlich einen IBD mitgeben. Das ist "
    "das Informations-Blockdiagramm (Menü „IBD-Editor“): Es zeigt, WAS WOHIN "
    "FLIESST – welche Bauteile es gibt, welche eigenen Funktionen (def …), "
    "welche Variablen in welcher Funktion liegen und was als Übergabewert hinein "
    "und als Rückgabewert (return) heraus geht. Der PAP zeigt dagegen, WANN etwas "
    "passiert.\n"
    "Der IBD ersetzt nur den Teil VARIABLEN der Spezifikation (Name, Datentyp, "
    "Bedeutung). EINGABE, ABLAUF und AUSGABE bleiben nötig, und der IBD ist nie "
    "Pflicht: Die klassische Variablenliste geht weiterhin.\n"
    "So lieferst du ihn mit:\n"
    "• ais.chat: IBD im IBD-Editor zeichnen, „Bild speichern“, die Bilddatei an "
    "die Nachricht anhängen und unter VARIABLEN schreiben: „siehe IBD im Bild“.\n"
    "• Ollama (lokal, liest meist keine Bilder): IBD als Text unter VARIABLEN "
    "schreiben, z. B.\n"
    "  def main(): Variablen reaktionszeiten [ ] (Sammler), zeit (Aktueller Wert)\n"
    "  def reaktionszeit_messen(): liest taster, schaltet led, Rückgabe zeit in ms → main()\n"
    "  def median(werte): Übergabe reaktionszeiten [ ], Rückgabe Median in ms → print()\n"
    "Der NiT_Coder setzt den IBD genau so um (Funktionen, Parameter, Rückgabewerte, "
    "lokale Variablen). Fällt ihm ein Widerspruch auf, etwa ein Rückgabewert ohne "
    "Ziel, verbessert er ihn nicht, sondern fragt nach."
)

_HINTERGRUNDWISSEN = (
    "Dateien sind nicht nötig – die Bibliotheks-Referenz steht bereits in den "
    "Instruktionen. Optional kann als Webseite das Bibliotheks-Repository "
    "angegeben werden:\n"
    "https://github.com/juchemGDG/NIT_Bibliotheken"
)


class AisChatPromptDialog(QDialog):
    """Zeigt die ais.chat-Dialogpartner-Vorlage mit Kopier-Knöpfen."""

    def __init__(self, parent=None, level: str = LEVEL_KL10):
        super().__init__(parent)
        self.setWindowTitle("NiT_Coder als Dialogpartner auf ais.chat")
        self.setMinimumSize(640, 640)
        self._level = LEVEL_KL10 if level == LEVEL_KL10 else LEVEL_KL89
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)

        intro = QLabel(
            f"So legst du den Code-Generator als Dialogpartner auf ais.chat an "
            f"({AIS_CHAT_URL}): Neuen Dialogpartner erstellen und die Felder "
            f"unten hineinkopieren."
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        level_row = QHBoxLayout()
        level_row.addWidget(QLabel("Stufe der Instruktionen:"))
        self._level_combo = ThemedComboBox()
        self._level_combo.addItem("Klasse 8/9 (ohne main())", LEVEL_KL89)
        self._level_combo.addItem("Klasse 10/KS (mit main(), nach IBD gegliedert)", LEVEL_KL10)
        self._level_combo.setCurrentIndex(self._level_combo.findData(self._level))
        self._level_combo.currentIndexChanged.connect(self._on_level_changed)
        level_row.addWidget(self._level_combo)
        level_row.addStretch(1)
        outer.addLayout(level_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(10)

        self._add_field(layout, "Name des Dialogpartners", _NAME, single_line=True)
        self._add_field(layout, "Kurzbeschreibung", _KURZBESCHREIBUNG, height=64)
        self._add_hint(layout, "Sprachmodell", _SPRACHMODELL)
        self._ibd_widgets = []
        n0 = layout.count()
        self._add_hint(layout, "IBD mitliefern (optional, ab Klasse 10)", _IBD_HINWEIS)
        for i in range(n0, layout.count()):
            it = layout.itemAt(i)
            self._ibd_widgets.append(it.widget() or it.layout())
        self._instr_edit = self._add_field(layout, "Instruktionen", coder_system_prompt(self._level), height=260)
        self._add_field(layout, "Einstiegsfrage", _EINSTIEGSFRAGE, height=56)
        self._add_hint(layout, "Hintergrundwissen", _HINTERGRUNDWISSEN)

        layout.addStretch(1)
        self._update_ibd_visibility()
        scroll.setWidget(inner)
        outer.addWidget(scroll, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        outer.addLayout(btn_row)

    def _add_field(self, layout, title: str, text: str,
                   height: int = 80, single_line: bool = False):
        """Überschrift + (nur lesbares) Textfeld + Kopieren-Knopf."""
        field = None
        row = self._header_row(title, text, lambda: field.toPlainText() if hasattr(field, "toPlainText") else text)
        layout.addLayout(row)
        if single_line:
            field = QLineEdit(text)
            field.setReadOnly(True)
        else:
            field = QPlainTextEdit(text)
            field.setReadOnly(True)
            field.setFixedHeight(height)
        layout.addWidget(field)
        return field

    def _update_ibd_visibility(self):
        show = self._level == LEVEL_KL10
        for item in self._ibd_widgets:
            if hasattr(item, "setVisible"):
                item.setVisible(show)
            else:                                   # Layout (Überschriftenzeile)
                for i in range(item.count()):
                    w = item.itemAt(i).widget()
                    if w is not None:
                        w.setVisible(show)

    def _on_level_changed(self):
        self._level = self._level_combo.currentData()
        self._instr_edit.setPlainText(coder_system_prompt(self._level))
        self._update_ibd_visibility()

    def _add_hint(self, layout, title: str, text: str):
        """Überschrift + Hinweistext (Feld, das man nicht 1:1 kopiert)."""
        layout.addLayout(self._header_row(title, text))
        hint = QLabel(text)
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{THEME['text_dim']};")
        layout.addWidget(hint)

    def _header_row(self, title: str, text: str, getter=None) -> QHBoxLayout:
        row = QHBoxLayout()
        lbl = QLabel(f"<b>{title}</b>")
        row.addWidget(lbl)
        row.addStretch(1)
        btn = QPushButton("Kopieren")
        btn.setFixedWidth(90)
        btn.clicked.connect(lambda _, b=btn: self._copy(getter() if getter else text, b))
        row.addWidget(btn)
        return row

    @staticmethod
    def _copy(text: str, btn: QPushButton):
        QApplication.clipboard().setText(text)
        btn.setText("Kopiert ✓")
