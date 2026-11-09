# Datenschutz in Koalino

Stand: Koalino 1.15.0, Entwicklungsstand nach dem Code-Check vom November 2026. Dieses Dokument richtet sich an Lehrkräfte und
Administratorinnen und Administratoren, die Koalino an einer Schule einsetzen. Es
beschreibt sachlich, welche Daten das Programm wohin schickt und was es lokal
speichert. Es ist keine Rechtsberatung und ersetzt nicht die Prüfung durch die
schulische Datenschutzbeauftragte oder den Datenschutzbeauftragten.

## Kurzfassung

- **Koalino sendet keine Nutzungsdaten.** Es gibt keine Telemetrie, keine
  Absturzberichte im Hintergrund, keine Update-Prüfung, keine Kennung des Rechners
  oder der Nutzerin bzw. des Nutzers.
- Netzwerkverbindungen entstehen nur, wenn eine Person etwas auslöst: eine
  eingebettete Web-Seite öffnet, Bibliotheken oder Firmware herunterlädt, Git
  benutzt oder einen Fehlerbericht abschickt.
- Eingebettete Web-Seiten laufen in einem **Off-the-record-Profil**: keine Cookies,
  kein Cache, kein Verlauf auf der Platte. Nach dem Schließen ist nichts mehr da.
  Deshalb muss man sich bei ais.chat nach jedem Start neu anmelden.
- Lokal gespeichert werden Einstellungen, Zwischenkopien geöffneter Dateien,
  gesicherte Programmstände und ein Absturzprotokoll, alles im Benutzerprofil
  und mit Löschfristen (siehe unten).

## 1. Verbindungen zu fremden Diensten

Alle Adressen stehen in `koalino/config.py`. Beim Öffnen eines Panels oder Fensters
baut der eingebettete Browser (QtWebEngine, Chromium) eine Verbindung zum
jeweiligen Anbieter auf. Dabei übermittelt er, wie jeder Browser, IP-Adresse,
User-Agent und die angeforderte Seite. Was danach passiert, bestimmt der Anbieter;
seine Datenschutzerklärung gilt.

| Dienst | Adresse | Wann | Was geht hin | Anmeldung |
|---|---|---|---|---|
| ais.chat (SCHULE@BW) | app.ais-chat.schule | Einstellungen → Chatbot → ais.chat, dann Panel öffnen | Chat-Eingaben der Nutzerin oder des Nutzers; Code nur, wenn er hineinkopiert wird | Ja (VIDIS) |
| fobizz | tools.fobizz.com | Einstellungen → Chatbot → fobizz.com, dann Panel öffnen | wie oben | Ja (fobizz-Konto) |
| py.nitbw.de | py.nitbw.de | Knopf „py.nitbw.de“ in der Seitenleiste | nur Seitenaufrufe | Nein |
| PAP-Editor | pap.mint-checker.de | Knopf „PAP-Editor“ | Das gezeichnete Diagramm bleibt im Browser-Fenster; „In Projekt übernehmen“ legt es nur lokal in die Zwischenablage | Nein |
| IBD-Editor | ibd.mint-checker.de | Menü „IBD-Editor“ | wie PAP-Editor | Nein |
| SchaltLab | schaltlab.mint-checker.de | Menü „SchaltLab“ | wie PAP-Editor | Nein |
| StatPlot (Datenauswertung) | statplot.mint-checker.de | Knopf „Datenauswertung“ | Die geöffnete **CSV-Datei wird per `postMessage` an die Seite übergeben** und dort im Browser ausgewertet. Sie wird nicht hochgeladen, aber der ausführende JavaScript-Code kommt vom Server. Ohne Netz läuft die mitgelieferte Offline-Kopie; mit der Einstellung „Datenauswertung immer offline“ (Einstellungen → Funktionen) wird der Server gar nicht kontaktiert | Nein |
| GitHub | api.github.com, codeload.github.com, raw.githubusercontent.com | Bibliotheks-Manager (NIT_Bibliotheken), micro:bit-Firmware | nur Downloads | Nein |
| micropython.org | micropython.org | Firmware flashen | nur Downloads | Nein |
| PyPI | pypi.org, files.pythonhosted.org | Pip-Manager | nur Downloads | Nein |
| Git-Server | vom Nutzer eingegeben (z. B. gitcamp-bw.de, github.com) | Menü „Git“ | Repository-Inhalte, Zugangsdaten (siehe 3.) | Ja |
| Fehlerbericht | mint-checker.de | Hilfe → Fehler melden, nur auf Knopfdruck | siehe 4. | Nein |

Hinweis zu den MINT-Checker-Seiten (PAP, IBD, SchaltLab, StatPlot): Sie werden online
zuerst geladen, damit Verbesserungen sofort ankommen. Für Räume ohne Internet gibt es
bei StatPlot eine mitgelieferte Kopie, die automatisch einspringt.

Das AIS-Chat-Panel meldet sich mit einem Smartphone-User-Agent, damit die Seite in der
schmalen Seitenleiste lesbar ist. Das ist keine Verschleierung von Personen, nur der
Darstellung.

## 2. Lokal gespeicherte Daten

Alles liegt im Benutzerprofil der angemeldeten Person, nicht im Projektordner und nicht
auf Netzlaufwerken:

| Betriebssystem | Ordner |
|---|---|
| Windows | `%APPDATA%\koalino\` |
| macOS | `~/Library/Application Support/koalino/` |
| Linux | `~/.config/koalino/` |

| Inhalt | Zweck | Personenbezug | Löschfrist |
|---|---|---|---|
| Einstellungen (QSettings, Organisation „NIT“, Anwendung „Koalino“) | Schriftgröße, Design, Sketchbook-Ordner, gewählter Chatbot, Python-Pfad | Pfade können den Benutzernamen enthalten | bleibt, bis Koalino deinstalliert oder der Ordner gelöscht wird |
| `offline_cache/` | Zwischenkopie jeder geöffneten und gespeicherten Datei, damit bei hängendem Schulserver weitergearbeitet werden kann | Inhalt der Schülerprogramme | Dateien, die 60 Tage nicht benutzt wurden, werden kurz nach dem Start gelöscht (`OFFLINE_CACHE_MAX_AGE_DAYS`) |
| `staende/` | Stand der Datei bei jedem Programmlauf (max. 50 je Datei) für „Zurück zum letzten funktionierenden Stand“ | Inhalt der Schülerprogramme | Ordner, deren jüngster Stand älter als 90 Tage ist, werden kurz nach dem Start gelöscht (`SNAPSHOT_MAX_AGE_DAYS`) |
| `crash.log` | Absturzprotokoll: Zeit, Koalino-Version, Betriebssystem, Python-Version, Stacktraces | Dateipfade im Stacktrace können den Benutzernamen enthalten | wird ab 256 KB auf die letzten 100 KB gekürzt; einsehbar unter Hilfe → Absturzprotokoll |

Außerhalb des Benutzerprofils:

| Inhalt | Ort | Hinweis |
|---|---|---|
| Fehlerprotokoll (`<programm>.fehlerprotokoll.md`) | neben der Programmdatei | Gehört zum Lernprodukt (Debugging-Landkarte) und wandert mit dem Programm in Git-Repos oder auf Netzlaufwerke. Das Panel zeigt den Speicherort an |
| Git-Zugangsdaten | Schlüsselspeicher des Betriebssystems (Windows Credential Manager, macOS Keychain, libsecret) | siehe 3. |

Unter **Datei → Einstellungen → Lokale Daten** stehen Offline-Kopien, gesicherte
Stände und Absturzprotokoll mit ihrer aktuellen Größe und je einem Knopf „Löschen …“
(mit Rückfrage). Das Absturzprotokoll wird dabei auf die laufende Sitzung gekürzt,
weil die Datei während des Betriebs offen bleibt. Wer alles entfernen will, löscht den
Ordner `koalino/` im Benutzerprofil bei geschlossenem Programm.

## 3. Git-Zugangsdaten

Beim Klonen über HTTPS mit Benutzername und Passwort oder Token:

- Die Zugangsdaten werden über `git credential approve` an den **Credential-Helper
  des Betriebssystems** übergeben und dort verschlüsselt abgelegt. Wo keiner
  verfügbar ist (Linux ohne libsecret), bleibt nur ein 8-Stunden-Cache im
  Arbeitsspeicher.
- Die Remote-URL im Repository wird sofort nach dem Klonen von den eingebetteten
  Zugangsdaten bereinigt.
- Ein eventuell früher angelegter Klartexteintrag in `~/.git-credentials` wird für
  diesen Host entfernt.
- In der Konsole erscheint die URL nur mit `***` statt des Passworts.

## 4. Fehlerbericht (Hilfe → Fehler melden)

Wird nur auf Knopfdruck gesendet. Der Dialog zeigt vorher an, was mitgeht:

- Beschreibung (Pflicht), E-Mail-Adresse (freiwillig, für Rückfragen)
- Koalino-Version, Betriebssystem und Version (`platform.platform()`, ohne Rechnername)
- Zeitstempel
- auf Wunsch (abwählbar): aktueller Code, Konsolenausgabe und das Ende des
  Absturzprotokolls

Der Bericht geht per HTTPS an ein Skript auf mint-checker.de
(`server/nc-report-x7q3.php`), das ihn als E-Mail an nitcode@mint-checker.de
weiterleitet und sonst nichts speichert. Die IP-Adresse wird nur für ein Rate-Limit
verwendet und **nicht** in die Mail geschrieben. Das Skript begrenzt die Größe auf
200 KB und die Zahl der Berichte (1 je 30 s pro Adresse, 60 je Stunde insgesamt).

Code und Konsolenausgabe können persönliche Angaben enthalten (z. B. Namen in
`input()`-Programmen). Der Dialog bittet darum, solche Stellen vor dem Senden zu
entfernen.

## 5. ESP32-Standalone-Firmware (iPad-Programmierung)

Das Board öffnet ein eigenes WLAN (`NIT-ESP32-…` bzw. `NIT-PICO-…`) und führt Code
aus, der per Web-Oberfläche geschickt wird. Es gibt keine Verbindung zum Schulnetz
oder ins Internet. Jede Person im WLAN des Boards kann Code darauf ausführen. Das
Standardpasswort steht öffentlich im Repository; beim Aufspielen lässt sich im
Deploy-Dialog ein eigenes setzen (je Klasse empfohlen). Für den Klassenraum ist
das ein bewusster Kompromiss zugunsten der Einfachheit; Einzelheiten stehen in
`firmware/README.md`, Abschnitt „Sicherheit“.

## 6. Nicht enthalten

- Kein lokaler KI-Dienst mehr: Der Ollama-basierte Tutor „Infi“ und der lokale
  Code-Generator (bis Version 1.14) wurden entfernt.
- Kein eingebauter KI-Agent: Das Claude-Terminal (Ctrl+Alt+Shift+C) ist ein
  Entwickler-Werkzeug und nur mit der Umgebungsvariable `KOALINO_DEV_TOOLS=1`
  vorhanden. Im Release-Build ist es nicht enthalten.
- Kein Zugriff auf Kamera, Mikrofon, Standort oder Kontakte.
- Keine Werbung, keine Dritt-Tracker in den mitgelieferten Seiten (Blockly, StatPlot-Kopie,
  Hilfe); diese laden keine externen Ressourcen.

## Änderungen

| Datum | Änderung |
|---|---|
| 2026-11-09 | Erstfassung nach dem Code-Check (docs/code_review_2026-11.md). Löschfristen für Offline-Kopien und Stände aktiviert, IP-Adresse aus dem Fehlerbericht entfernt, Ollama-Pfad entfernt. Neu: Abschnitt „Lokale Daten“ in den Einstellungen und Option „Datenauswertung immer offline“. |
