# NIT ESP32 MicroPython – iPad-Programmierung

Standalone-IDE auf dem ESP32: Board als eigener Accesspoint, Oberfläche wird
direkt vom Board ausgeliefert, kein Schulnetz/Internet nötig. Programmiert wird
**textuell in MicroPython** (keine Blöcke).

Die Web-Oberfläche zeigt links den **Editor** (mit Tab-Taste, automatischer
Einrückung nach `:` und einer Zusatztastenleiste für `( ) [ ] : " _ …` – die
iPad-Tastatur versteckt diese Zeichen), rechts die **Konsole** mit Ausgaben und
Fehlermeldungen des Programms (auf dem iPad hochkant untereinander).
**Syntax-Highlighting** für Python (Schlüsselwörter, Strings, Kommentare, Zahlen,
Funktionen) – das Farbschema folgt automatisch der iPad-Einstellung: hell =
**Eclipse**, dunkel = **One Dark** (gilt auch für Konsole und Dialoge).
Ausführen: Knopf „▶ Ausführen“ oder `Strg/Cmd + Enter`.

## Dateistruktur

```
boot.py        Richtet WLAN-Accesspoint ein
main.py        Webserver (uasyncio): liefert /www aus, führt Code im Thread aus, sammelt Ausgaben
www/index.html Oberfläche: Editor + Konsole
www/app.js     Editor-Hilfen, Beispiele, Ausführen -> /api/run, Konsole pollt /api/output, Stopp -> /api/stop
```

Die Oberfläche ist eigenständig (kein Blockly, keine externen Dateien) und
damit nur wenige KB groß.

## Beispiele, Speichern & Laden (im Browser)

Das Auswahlfeld **Beispiele …** lädt kleine Starterprogramme (Blinken, Taster,
Analogwert, …). Die Arbeit wird **automatisch im Browser gesichert**
(localStorage) und beim erneuten Öffnen wiederhergestellt. Zusätzlich:

- **💾 Speichern** – legt das aktuelle Programm unter einem Namen ab.
- **📂 Projekte** – Liste der gespeicherten Programme zum Laden/Löschen; darin
  auch **„Als Datei sichern“** (lädt eine `.py`-Datei zum Mitnehmen herunter)
  und **„Datei laden“** (importiert eine `.py`-Datei).

> Hinweis: localStorage hängt am jeweiligen Gerät/Browser. Für ein echtes,
> geräteübergreifendes Backup die `.py`-Datei exportieren.

## Raspberry Pi Pico W / Pico 2 W

`boot.py` erkennt den Pico automatisch (`sys.platform == "rp2"`) und nutzt die
Optionen des CYW43-WLAN-Chips: `security` statt `authmode`, `ssid`/`essid` je
nach MicroPython-Version, jede Option einzeln (ein unbekannter Schlüssel
verwirft nicht mehr SSID und Passwort). Früher lief der Pico deshalb mit dem
Standardnamen `MicroPython-xxxxxx` und dem Standardpasswort statt `mint2026`.
Die SSID heißt beim Pico **`NIT-PICO-<Name>`** (sonst `NIT-ESP32-<Name>`).

- Der Deploy (Koalino-Menü oder mpremote) ist identisch; Board vorher als
  „Pico 2 W“ mit MicroPython-Firmware für **Pico W / Pico 2 W** (nicht die
  Variante ohne „W“) flashen.
- Nach dem Update das Board **einmal neu bespielen**; ein vorher am iPad
  gespeichertes WLAN „MicroPython-…“ bitte vergessen.
- Kein Kanal-/Stromspar-Unterschied nötig: Kanal 1/6/11 und `PM_NONE` werden
  auch hier gesetzt, soweit die Firmware es unterstützt.

## Deployment auf den ESP32

> **Wichtig:** Das braucht USB-Zugriff auf das Board und läuft deshalb **nur
> lokal** – nicht im Cloud-Codespace. Port-Namen: ESP32-C3 mit nativem USB
> meist `/dev/ttyACM0` (Linux) bzw. `/dev/cu.usbmodemXXXX` (macOS), mit
> USB-Serial-Chip `/dev/ttyUSB0`.

Zuerst muss **MicroPython** auf dem Board sein – am einfachsten über den
Koalino-Flash-Dialog (Board „ESP32-C3" wählen, neueste Firmware automatisch).
Manuell:

```bash
esptool --chip esp32c3 --port /dev/ttyACM0 --baud 460800 \
    write_flash -e -z 0x0 ESP32_GENERIC_C3-*.bin
```

### Weg A – direkt in Koalino (empfohlen)

Menü **MicroPython → 📲 iPad-Programmierung aufs Board spielen**. Kopiert `boot.py`,
`main.py` und `www/` automatisch auf den angeschlossenen Controller und startet
ihn neu – kein Terminal nötig. Der Dialog fragt nach einer **Nummer/Name für das
Board** (→ WLAN-SSID, siehe unten), einem **WLAN-Passwort** (Vorgabe: Standard aus
`boot.py`, siehe [Sicherheit](#sicherheit)) und kann per Häkchen zusätzlich die
**Sensor-Bibliotheken (`nitbw_`)** nach `/lib` installieren (damit eigene
Programme sie per `import` nutzen können; Quelle: aktueller Stand von GitHub per ZIP-Download,
ohne Internet die mit Koalino gelieferten Module; dauert einige Minuten, braucht Internet).

### Weg B – manuell per mpremote

```bash
pip install mpremote
cd firmware
mpremote connect /dev/ttyACM0 cp boot.py main.py :
mpremote connect /dev/ttyACM0 cp -r www :
mpremote connect /dev/ttyACM0 reset
```

Danach mit Laptop/iPad ins jeweilige Board-WLAN (Standardpasswort: `mint2026`, ein
eigenes setzt man wie unter [Sicherheit](#sicherheit) beschrieben) und
`http://192.168.4.1/` öffnen. Die SSID steht oben in der Oberfläche.

## Eindeutige SSIDs im Klassensatz

Damit sich bei 10+ Boards niemand ins falsche WLAN verbindet, hat jedes Board
eine eindeutige SSID:

- **Name gesetzt** (Deploy-Dialog, Weg A): SSID = `NIT-ESP32-<Name>`, z. B.
  `NIT-ESP32-01`. Board am besten gleich mit derselben Nummer bekleben.
- **Kein Name**: `boot.py` bildet automatisch `NIT-ESP32-<Chip-ID>` aus den
  letzten 4 Stellen der eindeutigen Chip-Kennung (z. B. `NIT-ESP32-A1B2`). So
  gibt es **nie zwei gleiche SSIDs**, auch ohne Konfiguration.

Der Deploy-Dialog zeigt die resultierende SSID an; zusätzlich steht sie in der
Web-Oberfläche und wird beim Boot seriell ausgegeben. Der Name liegt auf dem
Board in `ap_name.txt` – bei Weg B (manuell) kann man ihn selbst setzen:

```bash
echo -n "01" | mpremote connect /dev/ttyACM0 fs cp - :ap_name.txt   # oder Datei anlegen
```

## Sicherheit

Das Board führt **jeden Python-Code aus, der per `POST /api/run` ankommt**, ohne
Anmeldung. Der einzige Schutz ist das WLAN-Passwort. Das ist ein bewusster
Kompromiss: Im Unterricht soll das iPad ohne Konto und ohne Einrichtung direkt
programmieren können, und die Firmware bleibt klein und einfach.

Folgen, die man kennen sollte:

- Wer das WLAN-Passwort kennt und in Funkreichweite ist, kann auf dem Board
  beliebigen Code ausführen und damit angeschlossene Hardware (Pins, Motoren,
  Relais) steuern oder Dateien auf dem Board überschreiben.
- Das Standardpasswort `mint2026` steht in `boot.py` und damit **öffentlich im
  Repository**; es ist auf allen Boards gleich. Wer Koalino kennt, kennt es also.
- Das Board hängt in einem eigenen Accesspoint ohne Internet. Fremde Netze oder
  Rechner sind nicht gefährdet, nur das Board selbst und seine Hardware.

**Empfehlung:** Pro Klasse (oder pro Kurs) beim Aufspielen ein eigenes Passwort
vergeben und nur den Lernenden dieser Gruppe nennen. Dann sind Boards aus
anderen Räumen und Dritte in der Nähe ausgesperrt. Das Passwort sollte nicht für
etwas anderes verwendet werden, da es auf dem Board im Klartext liegt.

- **Weg A:** Im Deploy-Dialog das Feld „WLAN-Passwort (mind. 8 Zeichen)“ ändern
  (8 bis 63 Zeichen). Koalino schreibt es als `ap_password.txt` auf das Board;
  bleibt der Standard stehen, wird eine vorhandene `ap_password.txt` entfernt.
- **Weg B:** Die Datei selbst anlegen und neu starten:

  ```bash
  echo -n "MeinKlassenPasswort" | mpremote connect /dev/ttyACM0 fs cp - :ap_password.txt
  mpremote connect /dev/ttyACM0 reset
  ```

`boot.py` liest `ap_password.txt` beim Start; fehlt die Datei oder ist das
Passwort ungültig (nicht 8 bis 63 Zeichen), gilt `DEFAULT_AP_PASSWORD`. Das
Passwort steht beim Boot in der seriellen Ausgabe und im Abschluss-Dialog von
Koalino – am besten zusammen mit der SSID auf dem Board vermerken.

## Bekannte Einschränkungen von V1

1. **Ausführung im Hintergrund-Thread**: `main.py` startet den Nutzercode per
   `_thread`, fängt `print`-Ausgaben und Fehler ab (Ringpuffer) und liefert sie
   über `/api/output`; der Webserver bleibt erreichbar. **Stopp** beendet das
   Programm *ohne Neustart* (das WLAN bleibt): `main.py` ersetzt das Modul `time`
   durch eine Variante, deren `sleep*` abbrechbar ist, und prüft das Stopp-Flag
   in jedem `print()`. Ein Programm **ganz ohne `print` und `sleep`** (reine
   Busy-Loop) reagiert nicht – dann startet das Board nach 3 s als Notausgang
   neu, das iPad verliert kurz das WLAN und die Seite wartet automatisch, bis
   das Board wieder da ist. Zeitgeber (`Timer`) und Interrupts des Programms
   laufen nach einem Stopp weiter, bis das Board neu startet. Einschränkung des
   einzelnen Kerns: Eine Endlosschleife ohne `sleep` kann den Webserver bremsen.
2. **Ein Client pro Board**: AP-Client-Limit ist bei 1:1-Zuordnung
   (ein ESP32 pro Schüler:in) unkritisch.
3. **Kein Captive Portal** in V1 – man muss die IP manuell aufrufen.
   Lässt sich später per simplem DNS-Spoofing nachrüsten.
4. **Sensor-Bibliotheken brauchen Module auf dem Board**: `import nitbw_...`
   funktioniert nur, wenn die Module in `/lib` liegen (Deploy-Häkchen oder
   „Bibliotheken installieren …“). Reines MicroPython (`machine`, `time`, …)
   läuft ohne Zusatz.
5. **Keine Autovervollständigung** im Editor
   (bewusst schlank gehalten, damit die Seite schnell vom Board lädt).

## Troubleshooting: „Verbindung fehlgeschlagen" auf dem iPad

`boot.py` enthält seit Juli 2026 drei Stabilitäts-Fixes (dazu die Boards einmal
**neu bespielen**, Weg A oder B):

- **Kanalverteilung**: Jedes Board wählt anhand seiner Chip-ID fest Kanal 1, 6
  oder 11 (vorher: alle auf Kanal 6). Im Klassensatz stören sich die APs so
  deutlich weniger gegenseitig. Der Kanal wird beim Boot seriell ausgegeben.
- **Modem-Sleep aus** (`pm=PM_NONE`): Der Stromsparmodus ließ den AP
  Anmelde-Frames verpassen – häufigste Einzelursache für Verbindungsabbrüche.
- **`ap.config()`-Retry**: Direkt nach dem Aktivieren schlägt die
  AP-Konfiguration auf dem C3 gelegentlich intern fehl; ohne Retry lief der AP
  dann mit Default-SSID weiter.

Bleibt es instabil:

- **Nach „Stopp" 3–5 s warten**: Stopp = Board-Reset, das WLAN verschwindet
  kurz und das iPad muss sich neu verbinden.
- **Abstand zum Schul-WLAN-Accesspoint**: Ein starker AP direkt im Raum
  überdeckt die schwachen ESP32-Signale; notfalls Boards näher ans iPad.
- **iPad-Seite**: Netzwerk einmal „ignorieren" und neu verbinden, falls iOS
  einen alten Zustand gespeichert hat.
