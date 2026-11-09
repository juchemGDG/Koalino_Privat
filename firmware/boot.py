# boot.py
# Wird beim Start automatisch ausgefuehrt (vor main.py).
# Richtet den ESP32 / Raspberry Pi Pico (2) W als eigenen WLAN-Accesspoint ein.

import network
import machine
import time
import ubinascii
import sys

DEFAULT_AP_PASSWORD = "mint2026"   # min. 8 Zeichen fuer WPA2; oeffentlich im Repo, daher je Klasse aendern
PASSWORD_FILE = "ap_password.txt"   # optional, beim Deploy gesetztes WLAN-Passwort


def _read_password():
    """Passwort aus ap_password.txt; fehlt die Datei oder ist es ungueltig, der Standard.

    WPA2 verlangt 8 bis 63 Zeichen - ein zu kurzes Passwort wuerde den AP sonst
    gar nicht starten lassen.
    """
    try:
        with open(PASSWORD_FILE) as f:
            pw = f.read().strip()
    except OSError:
        return DEFAULT_AP_PASSWORD
    return pw if 8 <= len(pw) <= 63 else DEFAULT_AP_PASSWORD


AP_PASSWORD = _read_password()
# Nur die drei ueberlappungsfreien 2,4-GHz-Kanaele. Jedes Board waehlt anhand
# seiner Chip-ID fest einen davon: Im Klassensatz verteilen sich die APs so
# auf drei Kanaele, statt sich alle auf einem Kanal gegenseitig zu stoeren
# (haeufigste Ursache fuer "Verbindung fehlgeschlagen" auf dem iPad).
AP_CHANNELS = (1, 6, 11)
NAME_FILE = "ap_name.txt"   # optionaler, beim Deploy gesetzter Board-Name

# WPA2-PSK. Die Namens-Konstante existiert nicht in jeder MicroPython-Version,
# der Zahlwert 3 (WPA2-PSK) ist aber stabil – daher mit Fallback.
AUTHMODE_WPA2_PSK = getattr(network, "AUTH_WPA2_PSK", 3)


# Raspberry Pi Pico (W): Port "rp2", WLAN-Chip CYW43 – eigene Konfigurationsschluessel
IS_RP2 = (sys.platform == "rp2")
BOARD_PREFIX = "NIT-PICO-" if IS_RP2 else "NIT-ESP32-"

# CYW43-"security"-Wert fuer WPA2 (AES-PSK). Neuere MicroPython-Versionen haben
# eine Konstante, sonst der feste Zahlwert aus dem CYW43-Treiber.
SECURITY_WPA2 = getattr(network.WLAN, "SEC_WPA2", 0x00400004)


def ap_ssid():
    """SSID dieses Boards.

    Reihenfolge fuer eindeutige Namen im Klassensatz:
      1. Inhalt von ``ap_name.txt`` (beim Aufspielen gesetzt) -> NIT-ESP32-<Name>
         bzw. NIT-PICO-<Name>
      2. sonst automatisch die letzten 4 Hex-Stellen der eindeutigen Chip-ID
         -> z. B. NIT-ESP32-A1B2 (nie zwei gleiche SSIDs, auch ohne Konfiguration)
    """
    name = ""
    try:
        with open(NAME_FILE) as f:
            name = f.read().strip()
    except OSError:
        name = ""
    if not name:
        name = ubinascii.hexlify(machine.unique_id()).decode().upper()[-4:]
    return BOARD_PREFIX + name


def ap_channel():
    """Fester, aus der Chip-ID abgeleiteter Kanal (1, 6 oder 11)."""
    return AP_CHANNELS[machine.unique_id()[-1] % len(AP_CHANNELS)]


def _try_config(ap, **kw):
    """Setzt eine AP-Option; False, wenn diese MicroPython-Version sie nicht kennt.

    Jede Option einzeln: Ein unbekannter Schluessel (z. B. ``authmode`` auf dem
    Pico, dort heisst er ``security``) wirft ValueError und wuerde sonst auch
    SSID und Passwort verwerfen -> AP liefe mit Standardname/-passwort.
    """
    try:
        ap.config(**kw)
        return True
    except (ValueError, TypeError):
        return False


def _apply_ap_config(ap, ssid):
    """Wendet SSID, Passwort, Sicherheit und Kanal an (idempotent)."""
    # SSID: aeltere Ports kennen nur "essid", neuere auch "ssid" (rp2: beide)
    if not _try_config(ap, essid=ssid):
        _try_config(ap, ssid=ssid)
    if IS_RP2:
        # CYW43: "security" statt "authmode"; vor dem Passwort setzen
        _try_config(ap, security=SECURITY_WPA2)
        _try_config(ap, password=AP_PASSWORD)
    else:
        _try_config(ap, password=AP_PASSWORD)
        _try_config(ap, authmode=AUTHMODE_WPA2_PSK)
    _try_config(ap, channel=ap_channel())


def start_ap():
    ssid = ap_ssid()

    # Station-Modus zuerst abschalten: ein spaeterer Moduswechsel wuerde den
    # AP kurz neu starten und laufende Verbindungsversuche abbrechen.
    sta = network.WLAN(network.STA_IF)
    sta.active(False)

    ap = network.WLAN(network.AP_IF)
    if IS_RP2:
        # Pico: SSID/Passwort vor dem Aktivieren setzen (so macht es auch die
        # offizielle Doku) und danach nochmals zur Sicherheit.
        _apply_ap_config(ap, ssid)
    ap.active(True)

    # Direkt nach active(True) wirft config() auf dem C3 gelegentlich
    # "Wifi Internal Error" - der AP liefe dann mit Default-SSID/-Passwort
    # weiter. Deshalb mit kurzen Pausen erneut versuchen.
    for _ in range(5):
        try:
            _apply_ap_config(ap, ssid)
            break
        except OSError:
            time.sleep_ms(200)

    # WLAN-Stromsparmodus (Modem-Sleep) abschalten: Der AP verpasst sonst
    # Anmelde-Frames des iPads -> haeufige "Verbindung fehlgeschlagen"-Fehler.
    try:
        ap.config(pm=network.WLAN.PM_NONE)
    except (AttributeError, ValueError, OSError, TypeError):
        pass   # aeltere MicroPython-Version ohne pm-Option

    while not ap.active():
        pass

    print("Accesspoint aktiv")
    print("SSID:    ", _get_ssid(ap))
    print("Passwort:", AP_PASSWORD)
    try:
        print("Kanal:   ", ap.config("channel"))
    except (ValueError, OSError):
        pass
    print("IP:      ", ap.ifconfig()[0])
    return ap


def _get_ssid(ap):
    """Tatsaechlich aktive SSID (zur Kontrolle); Rueckgabe wie im Treiber."""
    for key in ("essid", "ssid"):
        try:
            return ap.config(key)
        except (ValueError, OSError):
            pass
    return ""


start_ap()
