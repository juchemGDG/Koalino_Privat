# Absturzprotokoll

Koalino schreibt auf Wunsch der Betreuung ein Absturzprotokoll, damit auch bei der installierten App ohne Terminal sichtbar wird, warum das Fenster ohne Warnung verschwunden ist (Anlass: Absturz beim Umschalten auf MicroPython, 2026-10-09, danach nicht reproduzierbar).

**Datei:** `crash.log` im Koalino-Konfigurordner

| System | Ort |
|---|---|
| macOS | `~/Library/Application Support/koalino/crash.log` |
| Windows | `%APPDATA%\koalino\crash.log` |
| Linux | `~/.config/koalino/crash.log` |

**Was drinsteht** (Modul `koalino/crash_log.py`):
- Je Sitzung eine Kopfzeile `=== START … · Koalino <Version> · <System> · Python <Version> ===` und beim regulären Beenden `=== ENDE … ===`. Fehlt `ENDE`, wurde die Sitzung abrupt beendet.
- Bei einem **harten Absturz** (Segfault, `abort`) der Python-Stack aller Threads (`faulthandler`).
- Python-Fehler, die Koalino abfängt und als Dialog „Unerwarteter Fehler“ zeigt.
- Die Datei bleibt klein: ab 256 KB wird auf die letzten ca. 100 KB gekürzt.

**Was Koalino damit macht:**
- Nach einem harten Absturz erscheint beim **nächsten Start einmal** ein Hinweis mit „Absturzprotokoll ansehen …“. Erzwungenes Beenden (Task-Manager, `kill`) hinterlässt keinen solchen Eintrag und löst keinen Hinweis aus.
- **Hilfe → Absturzprotokoll anzeigen …** zeigt den Inhalt, öffnet den Ordner und kopiert den Text.
- **Hilfe → Fehler melden …** hängt das Ende des Protokolls an den Bericht an (sichtbar in der Vorschau, nur mit gesetztem Haken „Code und Konsole anhängen“).
