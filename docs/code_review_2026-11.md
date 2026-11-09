# Code-Check Koalino 1.14.1 (November 2026)

Stand: Branch `main`, Commit `082a9ad`. Geprüft wurden das Paket `koalino/`, `start.py`,
`firmware/`, `server/` und der Release-Workflow. Die eingebettete Python-Runtime, die
nitbw-Bibliotheken unter `koalino/assets/nit_lib/` und die Blockly-Dateien sind fremder
bzw. synchronisierter Code und wurden nur auf externe Ressourcen durchsucht.

Jeder Punkt hat eine Einstufung, eine Begründung und einen **Prompt**, mit dem man ihn
gezielt angehen kann. Die Prompts setzen voraus, dass dieses Dokument im Repo liegt
(`docs/code_review_2026-11.md`) und beziehen sich auf seine Abschnittsnummern.

Einstufung: 🔴 sollte zeitnah erledigt werden · 🟠 lohnt sich · 🟢 Kosmetik / bei Gelegenheit

**Erledigt am 2026-11-09:** 1.1 (Ollama-Pfad entfernt, Entscheidung: nicht reaktivieren),
2.1 und der Dokumentationsteil von 2.4 (→ `docs/datenschutz.md`, verlinkt aus README und
Über-Dialog), 2.2 (prune beim Start, `prune_orphans`, Tests in `tests/test_prune.py`),
2.3 (IP aus der Mail, Hinweis und feste Vorschau im Dialog), 2.4 komplett (Option
„Datenauswertung immer offline“ unter Funktionen) und 2.5 (Abschnitt „Lokale Daten“ mit
Größe und Löschknopf, Modul `local_data.py`, Tests in `tests/test_local_data.py`).
Nebenbefund beim Testen: Stände, die in derselben
Millisekunde entstanden, bekamen dieselbe ID (behoben in `snapshots.add`). Zweiter
Nebenbefund: Schlug das Aufwärmen von Jedi fehl, stürzte der Vervollständigungs-Thread
mit `UnboundLocalError` ab (behoben in `completion.py`).

---

## Zusammenfassung

| Bereich | Ergebnis |
|---|---|
| **Kürzen & Optimieren** | Rund 4 200 Zeilen Ollama-/KI-Code (Infi, Code-Generator, Prompts) sind seit der Umstellung auf ais.chat/fobizz nicht mehr erreichbar, werden aber beim Start weiterhin aufgebaut. `main_window.py` ist mit 4 900 Zeilen zu groß; Git-Integration, Einstellungen und Stylesheet lassen sich sauber herauslösen. Fünf Web-Panels wiederholen denselben WebEngine-Aufbau. |
| **Datenschutz** | Grundsätzlich gut: keine Telemetrie, kein Tracking, Web-Ansichten laufen in Off-the-record-Profilen, Git-Zugangsdaten landen im System-Schlüsselspeicher, Fehlerberichte nur auf Knopfdruck. Vier Punkte sind zu beheben: die Offline-Kopien werden nie gelöscht (`prune` wird nirgends aufgerufen), der Fehlerbericht protokolliert die IP-Adresse ohne Hinweis, es gibt keinen Datenschutzhinweis zu den eingebetteten Fremddiensten, und nirgends lassen sich die lokal gespeicherten Daten löschen. |
| **Sonstiges** | Keine Tests im Repo. Abhängigkeiten nur nach unten gepinnt. README beschreibt Funktionen, die es nicht mehr gibt. ESP32-Firmware führt Code ohne Anmeldung aus (bewusst, aber dokumentationswürdig). Ein verstecktes Claude-Terminal im Schulprodukt. |

---

## 1 · Kürzen und Optimieren

### 1.1 ✅ Toter Ollama-Pfad: Infi, Code-Generator, Ollama-Client (erledigt 2026-11-09)

**Befund.** `_load_persistent_settings` in [main_window.py:4594-4596](../koalino/main_window.py#L4594-L4596)
setzt jeden gespeicherten Chatbot-Modus außer `none`, `aischat`, `fobizz` auf `none` zurück
(Kommentar: „Ollama-Modi gibt es nicht mehr“). Der Einstellungsdialog bietet nur diese drei
Optionen. Trotzdem:

- `TutorPanel` und `CoderPanel` werden in `_setup_central` bei jedem Start instanziiert
  und in den `_ai_stack` gelegt ([main_window.py:1424-1433](../koalino/main_window.py#L1424-L1433)).
- `_explain_error_with_infi` und der Knopf „Infi erklärt diesen Fehler“ prüfen auf den
  Modus `"ollama"`, der nie mehr gesetzt werden kann ([main_window.py:2374](../koalino/main_window.py#L2374), [2477](../koalino/main_window.py#L2477)).
- `ollama_client.py`, `ollama_web_password()` in `config.py`, `TUTOR_DEFAULT_URL/MODEL`,
  die Einstellungen `tutor/url` und `tutor/model` sowie `is_ollama_available()` hängen
  daran.
- `coder_panel.py` enthält rund 700 Zeilen System-Prompts für drei Niveaus.

Betroffene Dateien: `tutor_panel.py` (398), `coder_panel.py` (1 807), `ollama_client.py` (95),
Teile von `config.py`, `error_hints.py` (`build_infi_error_prompt`), `settings_dialog.py`.
Die AST-Umwandlung `py2blockly.py` (1 714 Zeilen) ist **nicht** betroffen, sie wird vom
Block-Editor weiter genutzt.

**Entscheidung nötig:** Entweder den Ollama-Pfad bewusst entfernen (Code aus der
Git-Historie ist jederzeit wiederherstellbar) oder ihn als vierte Option wieder anbieten.
Der jetzige Zustand kostet Startzeit und Speicher und verwirrt beim Lesen.

**Prompt (Variante Entfernen):**
```
Lies docs/code_review_2026-11.md Abschnitt 1.1. Entferne den nicht mehr erreichbaren
Ollama-Pfad vollständig: tutor_panel.py, coder_panel.py, ollama_client.py, die Funktion
ollama_web_password und die Konstanten TUTOR_DEFAULT_URL/TUTOR_DEFAULT_MODEL in config.py,
build_infi_error_prompt in error_hints.py sowie alle Verwendungen in main_window.py
(_tutor_panel, _coder_panel, _explain_error_with_infi, set_explain_visible, Index-Kommentare
im _ai_stack) und settings_dialog.py. Lass py2blockly.py und den Pfad „Coder → Blockly"
nur dann stehen, wenn er noch ohne CoderPanel erreichbar ist; sonst prüfe, ob
_open_blocks_from_code noch einen Aufrufer hat. Entferne die QSettings-Schlüssel tutor/url
und tutor/model beim Laden (einmalig per remove()). Aktualisiere README.md (Abschnitte
„KI-Tutor Infi", „KI-Codegenerator", „Fehler verstehen", Projektstruktur) und die
Feature-Tabelle. Starte die App einmal headless (siehe Memory „WebEngine-E2E-Tests im
Codespace") und prüfe, dass Einstellungen → Chatbot, die Fehlerhilfe und der Block-Editor
weiter funktionieren. Fasse am Ende zusammen, wie viele Zeilen entfallen sind.
```

**Prompt (Variante Reaktivieren):**
```
Lies docs/code_review_2026-11.md Abschnitt 1.1. Biete den lokalen Ollama-Tutor wieder als
vierte Chatbot-Option „Infi (lokal, Ollama)" an, aber nur wenn config.is_ollama_available()
True liefert. Stelle die Felder URL/Modell im Einstellungsdialog wieder her, verdrahte
_show_tutor_panel für den Modus "ollama" (TutorPanel) und den Code-Generator als
umschaltbaren Reiter im selben Panel. Prüfe _explain_error_with_infi und
set_explain_visible. Ergänze README-Abschnitt „KI-Tutor Infi" um den Hinweis, dass die
Option nur mit installiertem Ollama erscheint.
```

### 1.2 🟠 `main_window.py` aufteilen (4 904 Zeilen, 246 Methoden)

**Befund.** Drei klar abgegrenzte Blöcke lassen sich ohne Verhaltensänderung herauslösen:

| Block | Umfang | Ziel-Modul |
|---|---|---|
| Git: `GitCloneDialog`, `GitConflictDialog`, `_git_network_env`, 17 `_git_*`-Methoden, Credential-Handling | ~900 Zeilen | `git_integration.py` (Mixin oder Helfer-Klasse mit Rückgriff auf Konsole) |
| Einstellungen: ~30 `_settings_*`-Attribute, `_load_persistent_settings` (91 Zeilen), `_save_persistent_settings`, `_open_settings` (82), `_apply_settings` (58) | ~350 Zeilen | `app_settings.py` mit einer `@dataclass AppSettings` und `load()/save()`; der Dialog bekommt und liefert das Objekt statt 20 Einzelparametern |
| Stylesheet: `build_global_style` (261 Zeilen), `_light_dialog_controls_qss` | ~300 Zeilen | `styles.py` |

Danach bleibt `MainWindow` bei etwa 3 300 Zeilen. Die 19 `_open_*`- und 15 `_show_*`-Methoden
sind Menü-Handler und können bleiben.

**Prompt:**
```
Lies docs/code_review_2026-11.md Abschnitt 1.2. Lagere in drei getrennten Commits aus
koalino/main_window.py aus: (1) build_global_style und _light_dialog_controls_qss nach
koalino/styles.py; (2) GitCloneDialog, GitConflictDialog, _git_network_env und alle
_git_*-, _store_git_credentials-, _purge_plaintext_credentials-, _run_git_process-,
_resolve_git_executable-Methoden in ein Mixin GitIntegrationMixin in
koalino/git_integration.py, von dem MainWindow erbt; (3) die _settings_*-Attribute in eine
@dataclass AppSettings in koalino/app_settings.py mit load(store)/save(store), wobei
SettingsDialog das Objekt entgegennimmt und ein geändertes zurückgibt. Verhalten darf sich
nicht ändern: gleiche QSettings-Schlüssel, gleiche Migrationen (prefer_embedded_migrated,
LEGACY_THEME_MIGRATION, default_on_migrated). Führe nach jedem Schritt
python -m pyflakes koalino aus und starte die App headless.
```

### 1.3 🟠 Fünffach wiederholter WebEngine-Aufbau

**Befund.** `ais_chat_panel.py:90`, `block_panel.py:79`, `pap_editor.py:270`,
`py_site_panel.py:50`, `worksheet_panel.py:371` bauen jeweils identisch
Off-the-record-Profil → View → Page → `setPage`, teils mit `renderProcessTerminated`-Retry
und demselben Fallback-Label „PyQt6-WebEngine ist nicht installiert“. Auch die
`try: from PyQt6.QtWebEngineCore import … except ImportError: HAS_WEBENGINE = False`-Präambel
steht in sechs Dateien.

**Prompt:**
```
Lies docs/code_review_2026-11.md Abschnitt 1.3. Lege koalino/webview.py an mit:
HAS_WEBENGINE, einer Funktion make_offtherecord_view(parent, *, clipboard=False,
user_agent=None, on_render_crashed=None) -> QWebEngineView | None (Profil als erstes Kind,
View danach, Kommentar zur Löschreihenfolge übernehmen) und einem Widget
webengine_missing_label(name: str). Ersetze den Aufbau in ais_chat_panel.py,
block_panel.py, pap_editor.py, py_site_panel.py und worksheet_panel.py. Der einmalige
Reload nach Renderer-Absturz (block_panel, pap_editor) soll als gemeinsamer Helfer in
webview.py liegen. Keine Verhaltensänderung; prüfe mit dem Headless-Start, dass PAP-Editor,
Block-Editor und Arbeitsblatt-Vorschau noch laden.
```

### 1.4 🟢 Kleinere Dubletten und Aufräumarbeiten

- **HTML-Escaping** (`.replace("&", "&amp;")…`) steht sechsmal; `html.escape` tut dasselbe.
- **`refresh_theme`** ist in zwölf Widgets fast gleich aufgebaut (Header-Hintergrund,
  Titel, Rand). Eine Basis-Klasse `PanelHeader` würde das bündeln.
- **pyflakes** meldet 27 Stellen: ungenutzte Importe (`QStatusBar`, `QToolBar`, `QComboBox`,
  `QSizePolicy`, `THEMES` in `main_window.py`; `sys`, `QIcon`, `QFont`, `QColor`, `QSplitter`
  in `file_panel.py`; `math` in `terminal_panel.py`; `venv` in `start.py` u. a.), eine
  doppelte `QFrame`-Einfuhr in `coder_panel.py`, unbenutzte lokale Variablen
  (`t` in `editor_widget.py:135`, `flash_cmd` in `micropython_dialogs.py:991`).
- **`except Exception: pass`** kommt 25-mal vor. Die meisten sind begründet
  („best effort“), aber `config.py:421` (QSettings-Migration) und `main_window.py:4873`
  (Autosave) sollten zumindest `crash_log.note()` aufrufen, damit Fehler nicht spurlos
  verschwinden.
- **`micropython_dialogs.py:408`** importiert `os, sys` innerhalb einer Schleife, obwohl
  beide oben im Modul importiert sind.
- `start.py` und `config.py` enthalten je eine eigene Liste der Runtime-Kandidatenpfade
  (`_bundled_python_candidates` vs. `_embedded_runtime_candidates`); eine Quelle reicht.

**Prompt:**
```
Lies docs/code_review_2026-11.md Abschnitt 1.4. Führe python -m pyflakes koalino start.py
aus und bereinige alle gemeldeten Stellen. Ersetze die sechs manuellen
&/</>-replace-Ketten durch html.escape (mit quote=False, wo Attribute nicht betroffen
sind). Ergänze in config.py:421 und main_window.py:4873 je ein crash_log.note(...) im
except-Zweig. Entferne den Import in der Schleife in micropython_dialogs.py:408. Lass
die refresh_theme-Zusammenlegung aus, das ist ein eigener Schritt. Starte danach die App
headless.
```

### 1.5 🟢 Startzeit

`_setup_central` legt alle rechten Panels (Tutor, AIS, Coder, fobizz, Claude-Terminal,
Arbeitsblatt, Fehlerprotokoll, py.nitbw.de) beim Start an; Web-Panels erzeugen dabei
bereits ein QtWebEngine-Profil, auch wenn sie nie gezeigt werden. Die `lazy`-Idee des
fobizz-Panels (URL erst beim ersten `showEvent` laden) ließe sich auf die Erzeugung der
Views selbst ausweiten. Wird 1.1 umgesetzt, entfallen schon zwei Panels.

**Prompt:**
```
Lies docs/code_review_2026-11.md Abschnitt 1.5. Miss zunächst die Startzeit
(time.perf_counter um MainWindow(...) in main.py, Ausgabe über crash_log.note). Baue
dann die WebEngine-Views in AisChatPanel, WorksheetPanel und PySitePanel erst beim
ersten showEvent auf (das Panel selbst bleibt ein leeres QWidget mit Header). Miss erneut
und berichte die Differenz. Falls sie unter 150 ms liegt, mache den Umbau rückgängig.
```

---

## 2 · Datenschutz

### 2.1 Was gut ist (zur Dokumentation)

- **Keine Telemetrie.** Es gibt keinen automatischen Netzwerkverkehr außer den vom Nutzer
  ausgelösten Downloads (Bibliotheken, Firmware), dem optionalen Fehlerbericht und den
  eingebetteten Web-Seiten.
- **Web-Ansichten ohne Spuren.** Alle `QWebEngineProfile` sind namenlos, also
  off-the-record: keine Cookies, kein Cache, kein Verlauf auf der Platte. Für
  Schul-Rechner mit wechselnden Nutzern ist das richtig (Nebenwirkung: die
  ais.chat-Anmeldung muss nach jedem Start neu erfolgen).
- **Git-Zugangsdaten** gehen über `git credential approve` in den OS-Schlüsselspeicher;
  die Remote-URL wird nach dem Klonen vom Passwort bereinigt; alte Klartexteinträge in
  `~/.git-credentials` werden gelöscht. Vorbildlich.
- **Ollama-Passwort** (falls 1.1 zur Reaktivierung führt) kommt aus Umgebungsvariable
  oder lokaler Datei, nie aus dem Repo.
- **Fehlerbericht** nur auf Knopfdruck, mit Vorschau dessen, was gesendet wird, E-Mail
  optional, Code/Konsole abwählbar. Server-Skript: Größenlimit, Rate-Limit,
  Header-Injection-Schutz.
- **Lokale Daten** liegen im Benutzerprofil (`<Konfigordner>/koalino/`), nicht im
  Projektordner oder auf Netzlaufwerken.
- **Firmware-Webserver** blockt Path-Traversal und begrenzt Request-Größen.

### 2.2 ✅ Offline-Kopien werden nie gelöscht (erledigt 2026-11-09)

**Befund.** `offline_cache.store()` legt beim Öffnen und Speichern jeder Datei eine Kopie
unter `<Konfigordner>/koalino/offline_cache/` ab. Die Aufräumfunktion `prune()` (60 Tage)
wird **nirgends aufgerufen**. Auf einem Schul-PC mit Roaming-Profil sammeln sich so
dauerhaft Kopien aller jemals geöffneten Schülerprogramme an, auch von Dateien, die
längst gelöscht wurden. Dasselbe gilt im Prinzip für `snapshots.py` (`staende/`), dort
begrenzt `MAX_STAENDE = 50` je Datei, aber Verzeichnisse gelöschter Dateien bleiben.

**Prompt:**
```
Lies docs/code_review_2026-11.md Abschnitt 2.2. Rufe offline_cache.prune() beim Start in
einem QTimer.singleShot(5000, ...) aus MainWindow.__init__ auf (nicht blockierend, Fehler
werden geschluckt). Ergänze in snapshots.py eine Funktion prune_orphans(max_age_days=90),
die Stände-Ordner entfernt, deren jüngster Eintrag älter als max_age_days ist, und rufe
sie am selben Ort auf. Beide Fristen sollen in config.py als Konstanten stehen
(OFFLINE_CACHE_MAX_AGE_DAYS, SNAPSHOT_MAX_AGE_DAYS). Schreibe einen kleinen Test
(tests/test_prune.py, pytest, mit tmp_path und manipulierten mtime-Werten), der beide
Funktionen prüft.
```

### 2.3 ✅ Fehlerbericht: IP-Adresse und fehlender Hinweis (erledigt 2026-11-09)

**Befund.** Das Server-Skript [nc-report-x7q3.php:119](../server/nc-report-x7q3.php#L119)
schreibt die IP-Adresse des Absenders in die E-Mail. Der Dialog erwähnt das nicht. Die
IP ist ein personenbezogenes Datum; für die Fehlersuche wird sie nicht gebraucht (das
Rate-Limit funktioniert auch ohne Mail-Eintrag). Außerdem fehlt im Dialog ein Satz, wohin
der Bericht geht, wer ihn liest und wie lange er aufbewahrt wird. Code und
Konsolenausgabe können Namen von Schülerinnen und Schülern enthalten (z. B. in
`input()`-Programmen).

**Prompt:**
```
Lies docs/code_review_2026-11.md Abschnitt 2.3. (1) Entferne in
server/nc-report-x7q3.php die Zeile, die $ip in den Mail-Body schreibt; die IP bleibt nur
für das Rate-Limit in Gebrauch. (2) Ergänze in bug_report.py unter dem Einleitungstext
einen kurzen Datenschutzhinweis als QLabel (klein, text_dim): „Der Bericht wird an
<BUG_REPORT_EMAIL> gemailt und nur zur Fehlersuche genutzt. Bitte keine Namen oder
persönlichen Daten in Beschreibung, Code oder Konsole lassen." mit einem Link
„Vorschau prüfen", der den Fokus auf das Vorschaufeld setzt. (3) Setze die Checkbox
„Code und Konsolenausgabe anhängen" weiterhin standardmäßig an, aber zeige die Vorschau
immer (nicht ausblendbar), damit klar ist, was mitgeht. Passe den Modul-Docstring an
(er verweist noch auf server/bugreport.php).
```

### 2.4 ✅ Eingebettete Fremddienste ohne Hinweis (erledigt 2026-11-09)

**Befund.** Koalino bettet sieben externe Seiten ein: app.ais-chat.schule, tools.fobizz.com,
py.nitbw.de, pap.mint-checker.de, ibd.mint-checker.de, schaltlab.mint-checker.de,
statplot.mint-checker.de. Beim Öffnen entsteht jeweils eine Verbindung zu diesem Anbieter
(IP, User-Agent, ggf. Login). Bei StatPlot wird zusätzlich der **CSV-Inhalt** per
`postMessage` an die online geladene Seite übergeben; die Daten verlassen zwar den Rechner
nicht, aber der ausgeführte JavaScript-Code kommt vom Server und könnte sich ändern.
Weder README noch App nennen diese Anbieter gesammelt. Für den Einsatz an Schulen
(Verfahrensverzeichnis, Elterninformation) braucht die Lehrkraft eine solche Liste.

Der mobile User-Agent im AIS-Panel ist eine Verschleierung gegenüber dem Dienst, aber
unproblematisch.

**Prompt:**
```
Lies docs/code_review_2026-11.md Abschnitt 2.4. (1) Lege docs/datenschutz.md an mit:
Liste aller Fremddienste aus config.py (Domain, Zweck, wann die Verbindung entsteht,
welche Daten hingehen, ob ein Login nötig ist), Liste der lokal gespeicherten Daten
(QSettings, crash.log, offline_cache, staende, Fehlerprotokoll neben dem Programm) mit
Speicherort und Löschfrist, sowie dem Fehlerbericht. Halte es sachlich, für
Lehrkräfte und Administratoren, keine Rechtsberatung. (2) Verlinke die Datei aus
README.md (neuer Abschnitt „Datenschutz") und aus dem Über-Dialog in main_window.py
(_show_about) mit einem Satz. (3) Ergänze in statplot_window.py eine QSettings-Option
statplot/offline_first (Standard False) und im Einstellungsdialog unter FUNKTIONEN eine
Checkbox „Datenauswertung immer offline (mitgelieferte Kopie)"; bei True wird gar nicht
erst online geladen.
```

### 2.5 ✅ Keine Funktion „Lokale Daten löschen“ (erledigt 2026-11-09)

**Befund.** Es gibt keinen Weg in der Oberfläche, `offline_cache`, `staende`, `crash.log`
oder die QSettings zu leeren, etwa am Ende eines Schuljahres oder beim Rechnerwechsel.
Der Absturzprotokoll-Dialog hat „Ordner öffnen“, mehr nicht.

**Prompt:**
```
Lies docs/code_review_2026-11.md Abschnitt 2.5. Ergänze im Einstellungsdialog ganz unten
einen Abschnitt „LOKALE DATEN" mit einer Zeile pro Speicherort (Offline-Kopien,
gesicherte Stände, Absturzprotokoll), jeweils mit Größe in KB/MB (im Hintergrund
berechnet, QThread) und einem Knopf „Löschen …" mit Rückfrage. Lege die Lösch- und
Größenfunktionen in ein neues Modul koalino/local_data.py (clear_offline_cache,
clear_snapshots, clear_crash_log, size_of). Die crash.log darf nur bis zur aktuellen
Sitzungskopfzeile gekürzt werden, nicht geschlossen (faulthandler hält sie offen).
```

### 2.6 🟢 Kleinere Punkte

- **`crash_log`** schreibt `platform.platform()` und Python-Version, keine Nutzerkennung.
  Gut. Der Hinweis „Wenn du einen Absturz melden willst, kopiere den Text“ sollte
  erwähnen, dass Pfade im Stacktrace den Benutzernamen enthalten können.
- **`micropython_dialogs.py:41, 331`** nutzt `getpass.getuser()` nur für Mount-Pfade unter
  Linux. Unkritisch.
- **Fehlerprotokoll** (`debug_log_panel.py`) wird **neben dem Programm** als Markdown
  gespeichert. Das ist gewollt (gehört zum Lernprodukt), landet aber damit auch in
  Git-Repos und auf Netzlaufwerken. Der Hinweistext im Panel sagt das; ein Satz in
  `docs/datenschutz.md` genügt.
- **`platform.platform()`** im Fehlerbericht enthält unter Windows keine Rechnernamen.
  Geprüft, unkritisch.

---

## 3 · Sonstige Beobachtungen

### 3.1 🔴 Keine Tests

Im Repo gibt es kein `tests/`-Verzeichnis. Dabei sind mehrere Module rein funktional und
ohne Qt testbar: `checkpoints.py`, `snapshots.py`, `offline_cache.py`, `net_hints.py`,
`error_hints.py`, `py2blockly.py` (1 714 Zeilen, deterministische AST-Übersetzung),
`csv_stats.py`, `worksheet_renderer.py`, `pap_import.py`. Gerade `py2blockly` und
`error_hints` ändern sich oft und brechen leicht.

**Prompt:**
```
Lies docs/code_review_2026-11.md Abschnitt 3.1. Lege tests/ mit pytest an (pytest in
requirements-dev.txt, nicht in requirements.txt). Schreibe zuerst Tests für
checkpoints.py (insert/renumber/remove_all/reached_in_output, inkl. Einrückung nach
Doppelpunkt), net_hints.py (je ein Beispiel pro Hinweis-Zweig), snapshots.py (add
dedupliziert gleichen Inhalt, _prune behält gemerkte Stände, last_good) und
offline_cache.py (store/load/cache_path stabil bei gleichem Pfad). Dann py2blockly.py:
nimm fünf typische Schülerprogramme (print/input, if/elif, while mit break, for range,
Funktion mit return, ein MicroPython-Beispiel mit Pin) und prüfe, dass
python_to_block_state keine Exception wirft und jede Quellzeile entweder einem Block
oder einem Roh-Python-Block zugeordnet wird. Ergänze einen GitHub-Actions-Job
„tests" in .github/workflows (eigene Datei, läuft bei jedem Push), der pytest ohne Qt
ausführt (QT_QPA_PLATFORM=offscreen als Sicherheitsnetz).
```

### 3.2 🟠 Abhängigkeiten nur nach unten gepinnt

`requirements.txt` nutzt ausschließlich `>=`. Ein Release-Build kann dadurch von heute auf
morgen andere PyQt6-/WebEngine-Versionen ziehen als der letzte getestete Build.
`terminal_panel.py` dokumentiert bereits, dass `pyte 0.8.2` Eigenheiten hat.

**Prompt:**
```
Lies docs/code_review_2026-11.md Abschnitt 3.2. Erzeuge aus der aktuellen .venv eine
requirements.lock (pip freeze, nur die direkt und transitiv benötigten Pakete) und lass
die Release-Skripte unter release/scripts sowie release-build.yml mit dieser Datei
installieren. requirements.txt bleibt für die Entwicklung mit >= bestehen. Dokumentiere in
release/README.md, wie die Lock-Datei aktualisiert wird (pip-compile oder pip freeze),
und ergänze einen Hinweis, dass nach dem Aktualisieren ein Testbuild auf allen drei
Plattformen nötig ist.
```

### 3.3 🟠 README beschreibt entfernte Funktionen

Die README nennt Infi, Code-Generator und Ollama als Features, beschreibt den Knopf
„Infi erklärt diesen Fehler“ und listet `tutor_panel.py`/`coder_panel.py` in der
Projektstruktur. Die Theme-Beschreibung („Zwei Themes“) stimmt nicht mehr (vier Designs,
zehn Code-Farbschemata). Der Modul-Docstring von `bug_report.py` und der Kommentar in
`config.py` verweisen auf `server/bugreport.php`, die Datei heißt `nc-report-x7q3.php`.
Wird 1.1 mit „Entfernen“ umgesetzt, erledigt sich der KI-Teil mit.

**Prompt:**
```
Lies docs/code_review_2026-11.md Abschnitt 3.3. Gleiche README.md mit dem tatsächlichen
Funktionsumfang von Koalino 1.14.1 ab: Chatbot-Optionen (ais.chat, fobizz), Designs und
Code-Farbschemata aus config.py, IBD-Editor, SchaltLab, StatPlot online-zuerst,
Fehlerhilfe ohne KI, Debugging-Landkarte (Stände, Kontrollpunkte, Fehlerprotokoll),
Absturzprotokoll, Fehler melden. Entferne oder korrigiere alles, was es nicht mehr gibt.
Aktualisiere die Projektstruktur anhand von ls koalino. Korrigiere die Verweise auf
server/bugreport.php in bug_report.py und config.py.
```

### 3.4 🟠 ESP32-Firmware: Code-Ausführung ohne Anmeldung

`firmware/main.py` nimmt per `POST /api/run` beliebigen Python-Code entgegen und führt
ihn aus. Das WLAN-Passwort `mint2026` steht in `boot.py` und damit öffentlich im Repo und
ist für alle Boards gleich. Jede Person in Funkreichweite, die das Passwort kennt, kann
also fremde Boards steuern. Für ein Klassenzimmer ist das ein bewusster Kompromiss
(Einfachheit), aber er sollte dokumentiert sein und die Lehrkraft sollte ihn beim Deploy
ändern können.

**Prompt:**
```
Lies docs/code_review_2026-11.md Abschnitt 3.4. (1) Ergänze im Deploy-Dialog
(_deploy_ipad_firmware in main_window.py) neben dem Board-Namen ein Feld
„WLAN-Passwort (mind. 8 Zeichen)" mit Vorgabe aus boot.py; der Wert wird wie ap_name.txt
als ap_password.txt aufs Board geschrieben und in boot.py gelesen (Fallback auf die
Konstante). (2) Ergänze in firmware/README.md einen Abschnitt „Sicherheit", der erklärt,
dass das Board jeden Code aus dem eigenen WLAN ausführt und warum das Passwort je Klasse
geändert werden sollte. Keine weiteren Schutzmechanismen in main.py; der ESP32 soll
einfach bleiben.
```

### 3.5 🟢 Verstecktes Claude-Terminal

`terminal_panel.py` (586 Zeilen) und ein Tastenkürzel Ctrl+Alt+Shift+C öffnen ein
eingebettetes Terminal mit der `claude`-CLI im Sketchbook-Ordner. Es ist bewusst versteckt
und nur wirksam, wenn die CLI installiert ist. In einem Produkt für Schülerinnen und
Schüler ist ein undokumentierter Weg, der einen KI-Agenten mit Dateizugriff startet,
dennoch erklärungsbedürftig, vor allem gegenüber Administratoren. Außerdem zieht es
`pyte` als Abhängigkeit in jeden Build.

**Empfehlung:** Entweder hinter eine Umgebungsvariable (`KOALINO_DEV_TOOLS=1`) legen und
im Release-Build nicht einpacken, oder in `docs/datenschutz.md` benennen.

**Prompt:**
```
Lies docs/code_review_2026-11.md Abschnitt 3.5. Aktiviere das Claude-Terminal
(ClaudeTerminalPanel, _toggle_claude_terminal, Shortcut) nur noch, wenn die
Umgebungsvariable KOALINO_DEV_TOOLS=1 gesetzt ist; importiere terminal_panel in
main_window.py dann erst in diesem Fall (lazy), damit pyte im Normalfall nicht geladen
wird. Prüfe, ob pyte aus requirements.txt in eine requirements-dev.txt wandern kann,
ohne dass release/pyinstaller.spec bricht. Dokumentiere die Variable in release/README.md.
```

### 3.6 🟢 Weitere Kleinigkeiten

- `offline_cache.cache_path` und `snapshots._dir` hashen den Pfad mit SHA-1 auf 10 bzw.
  12 Zeichen. Kollisionen sind praktisch ausgeschlossen, aber `hashlib.blake2b(digest_size=6)`
  wäre die zeitgemäße Wahl.
- `config.set_theme()` fällt bei unbekanntem Namen auf `_DARK_THEME` zurück, obwohl der
  Standard `modern_light` ist (`THEME = dict(_LIGHT_MODERN_THEME)`). Inkonsistent.
- `main.py` importiert `sys` ein zweites Mal als `_sys` (Zeile 257).
- `start.py:_user_data_root()` legt die Dev-venv unter `Koalino/`, `config._user_config_dir()`
  unter `koalino/` (klein). Unter Linux ergibt das zwei Ordner.
- `firmware/main.py` prüft `".." in path`, aber nicht URL-kodierte Varianten (`%2e%2e`).
  Da `send_file` den Pfad direkt an `os.stat` gibt und MicroPython nicht dekodiert, ist
  das unkritisch, ein Kommentar würde es aber festhalten.

**Prompt:**
```
Lies docs/code_review_2026-11.md Abschnitt 3.6 und erledige die fünf Punkte in einem
Commit „chore: Kleinigkeiten aus dem Code-Check". set_theme soll auf _LIGHT_MODERN_THEME
zurückfallen. Vereinheitliche den Ordnernamen auf „koalino" nur dann, wenn du die
Migration vorhandener Dev-venvs mit einem Hinweis in start.py abfängst; sonst lass ihn
und dokumentiere die Abweichung in einem Kommentar.
```

---

## Vorgeschlagene Reihenfolge

Abschnitt 1.1, 2.1 bis 2.5 und 3.3 sind erledigt (2026-11-09). Für den Rest:

1. **3.1** Tests ausbauen (Grundgerüst in `tests/` steht), danach erst **1.2** und
   **1.3** (Umbauten mit Netz).
2. **3.2** Lock-Datei für reproduzierbare Builds.
3. **3.4** Firmware-Passwort im Deploy-Dialog, **3.5** Claude-Terminal hinter
   Umgebungsvariable.
4. **1.4**, **1.5**, **3.6** nach Gelegenheit.
