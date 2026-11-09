"""WLAN-Passwort des iPad-Boards (firmware/boot.py): Standardwert lesen und prüfen.

Das Board schreibt ein vom Standard abweichendes Passwort beim Aufspielen in
``ap_password.txt``; ``boot.py`` liest es von dort (siehe firmware/README.md,
Abschnitt „Sicherheit“).
"""
import re
from pathlib import Path

FALLBACK_PASSWORD = "mint2026"
MIN_LEN, MAX_LEN = 8, 63   # WPA2-PSK
_DEFAULT_RE = re.compile(r'^DEFAULT_AP_PASSWORD\s*=\s*["\']([^"\']+)["\']', re.M)


def read_default(firmware_dir) -> str:
    """Standardpasswort aus boot.py (Konstante DEFAULT_AP_PASSWORD)."""
    try:
        text = (Path(firmware_dir) / "boot.py").read_text(encoding="utf-8")
    except OSError:
        return FALLBACK_PASSWORD
    m = _DEFAULT_RE.search(text)
    return m.group(1) if m else FALLBACK_PASSWORD


def validate(password: str) -> str:
    """Leerer String = gültig, sonst eine verständliche Fehlermeldung."""
    if not (MIN_LEN <= len(password) <= MAX_LEN):
        return f"Das WLAN-Passwort muss {MIN_LEN} bis {MAX_LEN} Zeichen lang sein."
    if not password.isascii() or not password.isprintable():
        return "Bitte nur Buchstaben ohne Umlaute, Ziffern und Sonderzeichen verwenden."
    return ""
