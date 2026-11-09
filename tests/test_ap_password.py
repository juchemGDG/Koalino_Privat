"""WLAN-Passwort des iPad-Boards (koalino.ap_password)."""
import pytest

from koalino import ap_password


def test_read_default_from_real_boot_py():
    from pathlib import Path
    fw = Path(__file__).resolve().parent.parent / "firmware"
    assert ap_password.validate(ap_password.read_default(fw)) == ""


def test_read_default_parses_constant(tmp_path):
    (tmp_path / "boot.py").write_text('X = 1\nDEFAULT_AP_PASSWORD = "geheim123"   # Kommentar\n')
    assert ap_password.read_default(tmp_path) == "geheim123"


def test_read_default_falls_back(tmp_path):
    assert ap_password.read_default(tmp_path) == ap_password.FALLBACK_PASSWORD
    (tmp_path / "boot.py").write_text("nichts = 1\n")
    assert ap_password.read_default(tmp_path) == ap_password.FALLBACK_PASSWORD


@pytest.mark.parametrize("pw", ["12345678", "Klasse-7b!", "x" * 63])
def test_valid_passwords(pw):
    assert ap_password.validate(pw) == ""


@pytest.mark.parametrize("pw", ["", "kurz", "x" * 64, "Grüße-aus-Ulm", "tab\tulator1"])
def test_invalid_passwords(pw):
    assert ap_password.validate(pw)
