"""Der Leitfaden „Fehler finden: Schritt für Schritt“ als Daten (Cheatsheet V2).

Eine Quelle für alles, was Koalino zum Debugging anzeigt – Konsole, Fehlerprotokoll
und die Anleitungsseite –, damit die Wörter überall dieselben sind wie auf dem
Cheatsheet.

Zwei Stufen mit eigenem Cheatsheet:

* Klasse 8/9 (``kl89``): fünf Schritte – 0 Vorcheck, 1 Beobachten, 2 Eingrenzen (drei
  Fälle), 3 Eine Sache ändern, 4 Geklappt? – und ein Heft mit zwei Spalten, einer Zeile
  pro gelöstem Fehler.
* Klasse 10/KS (``kl10``): sieben Schritte 0 bis 6, vier Fälle, IBD, ein Protokoll mit
  sechs Spalten und einer Zeile pro Runde.

Zwei Modi (:func:`set_mode`): ``micropython`` (Controller, alle Schritte wie auf dem
Cheatsheet) und ``python`` (lokal). Lokal gibt es keine Hardware: Stopp-/Läuft-schon-was-
Schritte und der Fall „Hardware“ entfallen, die Schritte werden ab 1 neu nummeriert, und
„Eingrenzen“ verweist auf den Debugger (Haltepunkt, Einzelschritt, Variablen beobachten).

Schritte werden über ihren Schlüssel (``"eingrenzen"``, ``"aendern"`` …) angesprochen,
weil die Nummern je Stufe verschieden sind (:func:`nr`).

Texte stehen mit `Backticks` für Code; :func:`plain` entfernt sie für die Konsole,
:func:`inline_html` macht daraus ``<code>``.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, replace

LEVEL_KL89 = "kl89"
LEVEL_KL10 = "kl10"
LEVELS = (LEVEL_KL89, LEVEL_KL10)
LEVEL_LABEL = {LEVEL_KL89: "Klasse 8/9", LEVEL_KL10: "Klasse 10/KS"}

# Farben des Cheatsheets
NAVY = "#1d2a4a"
RED = "#b3261e"
BLUE = "#2f6db5"
YELLOW = "#f5b800"
GREEN = "#2e7d32"
CREAM = "#fff6d6"
CREAM_TEXT = "#3d3200"


@dataclass(frozen=True)
class Step:
    nr: int
    key: str
    title: str
    lead: str          # fett
    detail: str        # normal, \n = Zeilenumbruch
    color: str
    lead2: str = ""    # zweiter Absatz (Klasse 8/9: „Läuft schon was?“ im Vorcheck)
    detail2: str = ""


_STEPS_KL10: tuple[Step, ...] = (
    Step(0, "stopp", "Stopp?",
         "Wird etwas warm, riecht es, ist die Betriebs-LED aus?",
         "Sofort USB trennen, nichts anfassen, Lehrkraft rufen.", RED),
    Step(1, "busy", "Läuft schon was?",
         "Tut das Board etwas, bevor du startest? Reagiert die Konsole nicht oder meldet „busy“?",
         "Dann läuft ein altes Programm (`main.py`). Stopp-Knopf der Programmierumgebung "
         "oder **Strg+C** in der Konsole.\n"
         "Hilft nicht: Reset-Taster am Board, sofort Strg+C.", BLUE),
    Step(2, "beobachten", "Beobachten",
         "Was soll passieren? Was passiert?",
         "Gibt es eine Meldung? Dann schreib sie **wörtlich** ab, mit Zeilennummer.", NAVY),
    Step(3, "eingrenzen", "Eingrenzen", "Welcher Fall liegt vor?", "", NAVY),
    Step(4, "vermuten", "Vermuten",
         "Schreib einen Satz: „Ich vermute …, weil …“",
         "Das „weil“ stützt sich auf das, was du in 2 und 3 gesehen hast.", NAVY),
    Step(5, "aendern", "Ändern und testen",
         "Ändere genau eine Sache.",
         "Vorher eine Kopie machen oder `#` vor die alte Zeile setzen.\n"
         "Dann starten und beobachten.", NAVY),
    Step(6, "geklappt", "Geklappt?", "", "", NAVY),
)

_STEPS_KL89: tuple[Step, ...] = (
    Step(0, "vorcheck", "Vorcheck",
         "Wird etwas warm, riecht es, ist die Betriebs-LED aus?",
         "Sofort USB trennen, nichts anfassen, Lehrkraft rufen.", RED,
         lead2="Tut das Board etwas, bevor du startest?",
         detail2="Altes Programm stoppen: Stopp-Knopf oder **Strg+C**. "
                 "Hilft das nicht: Reset-Taster, sofort Strg+C."),
    Step(1, "beobachten", "Beobachten",
         "Was soll passieren? Was passiert?",
         "Gibt es eine Meldung? Dann lies sie **von unten** und beachte die Zeilennummer.", NAVY),
    Step(2, "eingrenzen", "Eingrenzen", "Welcher Fall liegt vor?", "", NAVY),
    Step(3, "aendern", "Eine Sache ändern",
         "Überlege kurz: **Ich ändere …, weil …**",
         "Ändere **genau eine** Sache. Vorher eine Kopie machen oder `#` vor die alte Zeile "
         "setzen. Dann starten.", NAVY),
    Step(4, "geklappt", "Geklappt?", "", "", NAVY),
)

STEPS_BY_LEVEL = {LEVEL_KL89: _STEPS_KL89, LEVEL_KL10: _STEPS_KL10}

MODE_LOCAL = "python"
MODE_DEVICE = "micropython"
_mode = MODE_DEVICE
_HARDWARE_STEPS = ("stopp", "busy", "vorcheck")


def set_mode(mode: str) -> None:
    """Welcher Leitfaden gilt: ``"python"`` (lokal) oder ``"micropython"`` (Controller)."""
    global _mode
    _mode = MODE_LOCAL if mode == MODE_LOCAL else MODE_DEVICE


def mode() -> str:
    return _mode


def is_local(mode: str | None = None) -> bool:
    return (mode or _mode) == MODE_LOCAL


def steps(level: str, mode: str | None = None) -> tuple[Step, ...]:
    base = STEPS_BY_LEVEL.get(level, _STEPS_KL10)
    if not is_local(mode):
        return base
    # Lokal: ohne die Hardware-Schritte, ab 1 neu durchnummeriert
    keep = [st for st in base if st.key not in _HARDWARE_STEPS]
    return tuple(replace(st, nr=i) for i, st in enumerate(keep, start=1))


def step(key: str, level: str, mode: str | None = None) -> Step:
    """Schritt über seinen Schlüssel; ``"stopp"``/``"busy"`` meinen in Klasse 8/9 den Vorcheck.
    Lokal gibt es diese Schritte nicht (StopIteration)."""
    if level == LEVEL_KL89 and key in ("stopp", "busy"):
        key = "vorcheck"
    return next(st for st in steps(level, mode) if st.key == key)


def nr(key: str, level: str, mode: str | None = None) -> int:
    return step(key, level, mode).nr


STEP6_NOTE = "Drei Runden ohne Erfolg? Partner oder Lehrkraft holen."


def geklappt_ja(level: str, mode: str | None = None) -> str:
    if level == LEVEL_KL89:
        return "Ganzes Programm noch einmal testen. **Eine Zeile ins Heft.**"
    return "Ganzes Programm noch einmal testen. Zeile ins Heft."


def zurueck_nr(level: str, mode: str | None = None) -> int:
    """Zu welchem Schritt es nach einem Fehlschlag zurückgeht (Klasse 8/9: Eingrenzen,
    Klasse 10: Vermuten)."""
    return nr("eingrenzen" if level == LEVEL_KL89 else "vermuten", level, mode)


def geklappt_nein(level: str, mode: str | None = None) -> str:
    n = zurueck_nr(level, mode)
    if level == LEVEL_KL89:
        return (f"Änderung **rückgängig** machen, zurück zu {n}. Schreib jetzt dein "
                "„Ich ändere …, weil …“ auf.")
    return f"Änderung rückgängig machen, zurück zu {n}."


# Spalten des Protokolls
PROTOCOL_COLUMNS_KL10 = ("Nr.", "Soll / Ist", "Eingrenzen", "Vermutung", "Änderung", "Ergebnis")
PROTOCOL_COLUMNS_KL89 = ("Meldung oder Symptom", "Ursache und Änderung")


def protocol_columns(level: str) -> tuple[str, ...]:
    return PROTOCOL_COLUMNS_KL89 if level == LEVEL_KL89 else PROTOCOL_COLUMNS_KL10


@dataclass(frozen=True)
class Case:
    key: str
    label: str
    zusatz: str        # z. B. „(SyntaxError, NameError)“
    text: str          # Anleitung
    visible: bool = True


_KL9_NICHTS = ("Pin im Code = Pin am Kabel? LED richtig herum? GND? Wackler? "
               "Umstecken nur bei getrenntem USB.")

CASES: dict[str, tuple[Case, ...]] = {
    LEVEL_KL89: (
        Case("code", "Meldung", "",
             "Zeile ansehen, Fehler liegt dort oder knapp davor. "
             "Tippfehler? Doppelpunkt? Einrückung?"),
        Case("wert", "Keine Meldung, Ergebnis falsch", "",
             "Im **Code** an den Stellen der Kontrollpunkte (K) im PAP ein `print(\"K1\")` usw. "
             "setzen. Vorher überlegen: Was erwarte ich dort? Wo es zum ersten Mal "
             "nicht stimmt: diesen Abschnitt **Zeile für Zeile** prüfen."),
        Case("nichts", "Nichts reagiert", "", _KL9_NICHTS),
        # Hardware-Meldung (z. B. OSError) – in Klasse 8/9 kein eigener Fall, hier gilt die Checkliste.
        Case("hardware", "Meldung", "", _KL9_NICHTS, visible=False),
    ),
    LEVEL_KL10: (
        Case("code", "Meldung zum Code", "(SyntaxError, NameError)",
             "Zeile ansehen, Fehler dort oder knapp davor."),
        Case("hardware", "Meldung zur Hardware", "(z. B. OSError: ENODEV, ValueError: invalid pin)",
             "IBD ab **P1** prüfen: Stimmt der Pin im Code mit der Verdrahtung überein? "
             "Bei I2C-Geräten: `i2c.scan()`, antwortet ein Gerät?"),
        Case("wert", "Wert falsch", "(z. B. 250 °C, Motor brummt nur)",
             "Im **Code** `print()` an den Stellen der PAP-Kontrollpunkte und an P2/P3 der IBD "
             "setzen, mit der Erwartung vergleichen. Wo es nicht stimmt: diesen Abschnitt "
             "Zeile für Zeile im Code prüfen."),
        Case("nichts", "Nichts reagiert", "",
             "IBD **Glied für Glied**. Umstecken nur bei getrenntem USB."),
    ),
}

_DEBUGGER_WERT = ("Debugger starten (Strg+F5) mit einem **Haltepunkt** vor der Stelle, an der der "
                  "Wert entsteht (Klick neben die Zeilennummer, F9). Mit **F10** Zeile für Zeile "
                  "weitergehen und im Variablen-Panel beobachten: Wo weicht ein Wert zum ersten Mal "
                  "von der Erwartung ab? Dort liegt der Fehler.")

CASES_LOCAL: dict[str, tuple[Case, ...]] = {
    LEVEL_KL89: (
        Case("code", "Meldung", "",
             "Zeile ansehen, Fehler liegt dort oder knapp davor. "
             "Tippfehler? Doppelpunkt? Einrückung? Bei Werten: Haltepunkt in die Zeile setzen "
             "(F9), Debugger starten (Strg+F5) und die Variablen ansehen."),
        Case("wert", "Keine Meldung, Ergebnis falsch", "", _DEBUGGER_WERT),
        Case("nichts", "Nichts passiert", "",
             "Startet das Programm überhaupt? Haltepunkt in die erste Zeile, mit **F10** "
             "Zeile für Zeile gehen: Wird die Stelle erreicht? Hängt es in einer Schleife?"),
        # Meldungen, die auf dem Controller „Hardware“ wären – lokal gilt der Fall „Meldung“.
        Case("hardware", "Meldung", "", "", visible=False),
    ),
    LEVEL_KL10: (
        Case("code", "Meldung zum Code", "(SyntaxError, NameError, TypeError)",
             "Zeile ansehen, Fehler dort oder knapp davor. Bei Werten, die nicht passen: "
             "Haltepunkt in die Zeile (F9), Debugger (Strg+F5), Variablen ansehen."),
        Case("wert", "Wert falsch", "(z. B. Ergebnis 250 statt 25, Schleife läuft zu oft)",
             _DEBUGGER_WERT + " Alternativ `print()` an den Kontrollpunkten des PAP."),
        Case("nichts", "Nichts passiert / hängt", "(keine Ausgabe, Endlosschleife)",
             "Haltepunkt in die erste Zeile, mit **F10** Zeile für Zeile gehen. Wird die Stelle "
             "erreicht? In Schleifen die Bedingung im Variablen-Panel beobachten "
             "(Ausdruck unter „Beobachten“ eintragen)."),
        Case("hardware", "Meldung zum Code", "", "", visible=False),
    ),
}

IBD_NOTE = ("Beispiel BME280. Bei jedem Bauteil gilt: Wo stimmt die Erwartung zum ersten Mal "
            "nicht? Dort liegt der Fehler.")
IBD_IMAGE = "IBD_BME280.svg"      # liegt in assets/debug/, P1 bis P4 wie im Cheatsheet


def cases(level: str, visible_only: bool = True, mode: str | None = None) -> tuple[Case, ...]:
    table = CASES_LOCAL if is_local(mode) else CASES
    cs = table.get(level, table[LEVEL_KL10])
    return tuple(c for c in cs if c.visible) if visible_only else cs


def case(key: str, level: str, mode: str | None = None) -> Case | None:
    found = next((c for c in cases(level, visible_only=False, mode=mode) if c.key == key), None)
    if found is not None and not found.text and is_local(mode):
        # lokal fällt „hardware“ auf „code“ zurück (gleiche Anleitung)
        return next((c for c in cases(level, mode=mode) if c.key == "code"), found)
    return found


def case_label(key: str, level: str, mode: str | None = None) -> str:
    c = case(key, level, mode)
    return c.label if c else ""


# ── Textwerkzeuge ─────────────────────────────────────────────────────────────
def plain(text: str) -> str:
    """Für die Konsole: Backticks und **fett**-Markierung entfernen."""
    return text.replace("`", "").replace("**", "")


def inline_html(text: str) -> str:
    """Für HTML: escapen, `code` → <code>, **fett** → <b>, \\n → <br>."""
    t = html.escape(text)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    return t.replace("\n", "<br>")


def step_header(key: str, level: str = LEVEL_KL10) -> str:
    """„◆ Schritt 3 · Eingrenzen“ für die Konsole."""
    st = step(key, level)
    return f"◆ Schritt {st.nr} · {st.title}"


# ── Konsolentexte zu den Schritten ────────────────────────────────────────────
def step0_text(grund: str = "", level: str = LEVEL_KL10) -> str:
    s = step("stopp", level)
    out = f"\n⚠  SCHRITT 0 · {s.title.upper().rstrip('?')}\n"
    if grund:
        out += f"   {grund}\n"
    out += f"   {s.lead}\n   → {plain(s.detail)} Erst danach weiterdenken.\n"
    return out


def step1_text(level: str = LEVEL_KL10) -> str:
    """„Läuft schon was?“ – in Klasse 8/9 der zweite Absatz des Vorchecks."""
    s = step("busy", level)
    lead, detail = (s.lead2, s.detail2) if level == LEVEL_KL89 else (s.lead, s.detail)
    return ("\n" + step_header("busy", level) + "\n"
            f"   {lead}\n   " + "\n   ".join(plain(detail).split("\n")) + "\n")


def steps45_text(level: str = LEVEL_KL10) -> str:
    """Abschluss der Fehlerhilfe: das Ändern als Erinnerung (Klasse 10: Schritt 4 und 5)."""
    sicher = " Koalino sichert bei jedem Start automatisch einen Stand (⏪ bringt dich zurück).\n"
    if level == LEVEL_KL89:
        s = step("aendern", level)
        return ("\n" + step_header("aendern", level) + f" – {plain(s.lead)}\n"
                "   " + plain(s.detail) + sicher)
    s4, s5 = step("vermuten", level), step("aendern", level)
    return ("\n" + step_header("vermuten", level) + f" – {s4.lead}\n"
            f"   {s4.detail}\n"
            + step_header("aendern", level) + f" – {s5.lead}\n"
            "   " + plain(s5.detail).replace("\n", " ") + sicher)


def step6_text(ok: bool, drei_runden: bool = False, level: str = LEVEL_KL10) -> str:
    head = step_header("geklappt", level) + "\n"
    if ok:
        body = f"   Ja: {plain(geklappt_ja(level))}\n"
    else:
        body = f"   Nein: {plain(geklappt_nein(level))}\n"
    if drei_runden:
        body += f"   {STEP6_NOTE}\n"
    return "\n" + head + body


# ── Die Anleitungsseite ───────────────────────────────────────────────────────
_CSS = f"""
body {{ font-family: -apple-system, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; color:#16213a;
        background:#ffffff; margin:0; padding:18px 22px; font-size:13px; }}
h1 {{ font-size:22px; margin:0 0 2px 0; color:{NAVY}; }}
p.sub {{ color:#5b6478; margin:0 0 14px 0; }}
table.steps {{ width:100%; border-collapse:separate; border-spacing:0 7px; }}
td.badge {{ width:118px; vertical-align:top; padding:10px 12px; color:#ffffff;
            border-radius:8px 0 0 8px; }}
td.badge .nr {{ font-size:24px; font-weight:bold; color:{YELLOW}; line-height:1.1; }}
td.badge .ttl {{ font-weight:bold; font-size:13px; }}
td.body {{ vertical-align:top; padding:10px 14px; background:#ffffff; border:1px solid #c9cfdd;
           border-radius:0 8px 8px 0; }}
td.body .lead {{ font-weight:bold; }}
td.body code, code {{ background:#eef1f7; padding:0 3px; border-radius:3px;
           font-family:'JetBrains Mono', Consolas, Menlo, monospace; font-size:12px; }}
ul.cases {{ margin:6px 0 0 0; padding-left:0; list-style:none; }}
ul.cases li {{ margin:5px 0; }}
.ibd {{ margin-top:8px; }}
.ibd img {{ max-width:100%; height:auto; }}
.note {{ color:#5b6478; font-size:12px; margin-top:4px; }}
.ja {{ color:{GREEN}; font-weight:bold; }}
.nein {{ color:{RED}; font-weight:bold; }}
h2 {{ font-size:11px; letter-spacing:1px; color:#5b6478; margin:18px 0 6px 0; }}
table.prot {{ width:100%; border-collapse:collapse; }}
table.prot th {{ background:#eef1f7; text-align:left; padding:6px 8px; border:1px solid #c9cfdd; }}
table.prot td {{ padding:14px 8px; border:1px solid #c9cfdd; }}
div.koalino {{ margin-top:16px; padding:10px 14px; background:{CREAM}; color:{CREAM_TEXT};
               border:1px solid #e0c96a; border-radius:8px; }}
div.koalino b.h {{ color:{CREAM_TEXT}; }}
"""


def _step_body_html(step: Step, level: str, mode: str | None = None) -> str:
    if step.key == "eingrenzen":
        items = []
        for c in cases(level, mode=mode):
            zusatz = f" <span class='note'>{html.escape(c.zusatz)}</span>" if c.zusatz else ""
            items.append(f"<li>▸ <b>{html.escape(c.label)}</b>{zusatz}: {inline_html(c.text)}</li>")
        out = f"<div class='lead'>{html.escape(step.lead)}</div><ul class='cases'>{''.join(items)}</ul>"
        if level == LEVEL_KL10 and not is_local(mode):
            out += (f"<div class='ibd'><img src='{IBD_IMAGE}' width='330' alt='IBD mit P1 bis P4'></div>"
                    f"<div class='note'>{html.escape(IBD_NOTE)}</div>")
        return out
    if step.key == "geklappt":
        return (f"<div><span class='ja'>Ja:</span> {inline_html(geklappt_ja(level, mode))}<br>"
                f"<span class='nein'>Nein:</span> {inline_html(geklappt_nein(level, mode))}</div>"
                f"<div class='note'>{html.escape(STEP6_NOTE)}</div>")
    lead = f"<div class='lead'>{inline_html(step.lead)}</div>" if step.lead else ""
    detail = f"<div>{inline_html(step.detail)}</div>" if step.detail else ""
    if step.lead2:
        lead2 = f"<div class='lead' style='margin-top:6px'>{inline_html(step.lead2)}</div>"
        detail2 = f"<div>{inline_html(step.detail2)}</div>" if step.detail2 else ""
        return lead + detail + lead2 + detail2
    return lead + detail


def cheat_sheet_html(level: str, mode: str | None = None) -> str:
    """Das Cheatsheet „Fehler finden: Schritt für Schritt“ ohne Beispiel als HTML-Seite.
    ``mode``: ``"python"`` (lokal, mit Debugger) oder ``"micropython"``; Standard: aktueller Modus."""
    local = is_local(mode)
    rows = []
    for st in steps(level, mode):
        rows.append(
            f"<tr><td class='badge' bgcolor='{st.color}' width='118' valign='top' "
            f"style='background-color:{st.color}; color:#ffffff; padding:10px;'>"
            f"<div class='nr'><font color='{YELLOW}' size='5'><b>{st.nr}</b></font></div>"
            f"<div class='ttl'><font color='#ffffff'><b>{html.escape(st.title)}</b></font></div></td>"
            f"<td class='body' valign='top' style='padding:10px;'>{_step_body_html(st, level, mode)}</td></tr>")
    cols = protocol_columns(level)
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    empty = "".join("<td>&nbsp;</td>" for _ in cols)
    kl89 = level == LEVEL_KL89
    n = lambda key: nr(key, level, mode)        # noqa: E731 – Schrittnummern je Modus
    nit = (
        "<div class='koalino'><b class='h'>So hilft dir Koalino</b><br>"
        "• <b>Strg+K</b> setzt einen Kontrollpunkt <code>print(\"K1\")</code>, die Nummern "
        "folgen dem Programm. Nach einem Absturz zeigt die Konsole den letzten erreichten.<br>"
        "• <b>Konsole</b>: Nach einer Fehlermeldung begleitet sie dich durch Schritt "
        + (f"{n('beobachten')} und {n('eingrenzen')}") + (" – kurz und knapp.<br>" if kl89 else " – Stufe für Stufe.<br>")
        + "• <b>⏪ Zurück zum letzten funktionierenden Stand</b> und <b>📌 Stand merken</b> ersetzen "
        "die Kopie in Schritt " + (f"{n('aendern')} und {n('geklappt')}") + ".<br>"
        + ("• <b>Debugger</b> (Debuggen-Menü): <b>Haltepunkt</b> im Rand setzen (F9), Programm mit "
           "<b>Strg+F5</b> bis dorthin laufen lassen, dann mit <b>F10</b> Zeile für Zeile weiter. "
           "Das Variablen-Panel zeigt alle Werte; unter „Beobachten“ trägst du eigene "
           "Ausdrücke ein.<br>" if local else "")
        + ("• <b>I2C-Scan</b> (Debuggen-Menü, bei I2C-Geräten) macht <code>i2c.scan()</code> auf Knopfdruck.<br>"
           if level == LEVEL_KL10 and not local else "")
        + "• <b>Fehlerprotokoll</b> (Seitenleiste): "
        + ("eine Zeile pro gelöstem Fehler.</div>" if kl89 else
           f"eine Runde pro Zeile, in den Schritten {n('beobachten')} bis {n('geklappt')}.</div>"))
    sub = "Ändere immer <b>nur eine</b> Sache."
    where = " · lokales Python" if local else " · MicroPython" if kl89 else "Überspringe keinen."
    heft = ("INS HEFT: EINE ZEILE PRO GELÖSTEM FEHLER" if kl89
            else "INS HEFT ODER LABORBUCH: EINE ZEILE PRO RUNDE")
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{_CSS}</style></head><body>"
        f"<h1>Fehler finden: Schritt für Schritt</h1>"
        f"<p class='sub'>{LEVEL_LABEL[level]}{where} · Gehe die Schritte von oben nach unten durch. {sub}</p>"
        f"<table class='steps' width='100%' cellspacing='6' cellpadding='0'>{''.join(rows)}</table>"
        f"<h2>{heft}</h2>"
        f"<table class='prot' width='100%' border='1' cellspacing='0' cellpadding='6'>"
        f"<tr>{head}</tr><tr>{empty}</tr></table>{nit}</body></html>")
