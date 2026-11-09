"""Verständliche Netzwerk-Hinweise (koalino.net_hints)."""
import pytest

from koalino import net_hints as nh


@pytest.mark.parametrize("err, stichwort", [
    ("ProxyError('Cannot connect to proxy.')", "Proxy"),
    ("HTTP 407 Proxy Authentication Required", "Proxy"),
    ("Tunnel connection failed: 403 Forbidden", "Proxy"),
    ("[Errno -2] Name or service not known", "nicht gefunden"),
    ("getaddrinfo failed", "nicht gefunden"),
    ("Read timed out.", "Zeitüberschreitung"),
    ("CERTIFICATE_VERIFY_FAILED", "Zertifikat"),
    ("SSLError(1, 'handshake')", "Zertifikat"),
    ("[Errno 111] Connection refused", "abgelehnt"),
    ("Network is unreachable", "abgelehnt"),
])
def test_friendly_network_error_branches(err, stichwort):
    assert stichwort in nh.friendly_network_error(err)


def test_proxy_hint_lists_required_domains():
    hint = nh.friendly_network_error("ProxyError")
    for domain in nh.REQUIRED_DOMAINS:
        assert domain in hint


def test_friendly_network_error_unknown_is_empty():
    assert nh.friendly_network_error("etwas ganz anderes") == ""
    assert nh.friendly_network_error(None) == ""


@pytest.mark.parametrize("output, stichwort", [
    ("fatal: unable to access: Failed to connect to github.com port 443", "Proxy verwenden"),
    ("fatal: Could not connect to server", "Proxy verwenden"),
    ("error: RPC failed; Connection timed out", "Proxy verwenden"),
    ("fatal: HTTP 407 Proxy Authentication Required", "Anmeldung"),
    ("fatal: SSL certificate problem: unable to get local issuer certificate", "schannel"),
    ("fatal: Could not resolve host: github.com", "nicht gefunden"),
])
def test_git_network_hint_branches(output, stichwort):
    assert stichwort in nh.git_network_hint(output)


def test_git_network_hint_unknown_is_empty():
    assert nh.git_network_hint("fatal: repository not found") == ""
    assert nh.git_network_hint("") == ""
    assert nh.git_network_hint(None) == ""


def test_with_network_hint_appends_hint_only_when_known():
    known = nh.with_network_hint("Read timed out", prefix="Download: ")
    assert known.startswith("Download: Read timed out\n\n→")
    assert nh.with_network_hint("kaputt", prefix="X: ") == "X: kaputt"
