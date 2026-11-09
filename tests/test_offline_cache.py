"""Zwischenkopien: Pfadzuordnung und Fehlerverhalten (koalino.offline_cache)."""
from koalino import offline_cache


def test_different_paths_get_different_cache_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(offline_cache, "cache_root", lambda: tmp_path)
    a = offline_cache.cache_path("/klasse_a/main.py")
    b = offline_cache.cache_path("/klasse_b/main.py")
    assert a.name == b.name == "main.py"
    assert a.parent != b.parent


def test_load_unknown_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(offline_cache, "cache_root", lambda: tmp_path)
    assert offline_cache.load("/gibt/es/nicht.py") is None


def test_store_overwrites_and_keeps_umlauts(tmp_path, monkeypatch):
    monkeypatch.setattr(offline_cache, "cache_root", lambda: tmp_path)
    assert offline_cache.store("/x/a.py", 'print("alt")')
    assert offline_cache.store("/x/a.py", 'print("Grüße")')
    assert offline_cache.load("/x/a.py") == 'print("Grüße")'


def test_store_reports_failure_instead_of_raising(tmp_path, monkeypatch):
    blocker = tmp_path / "datei"
    blocker.write_text("x")
    monkeypatch.setattr(offline_cache, "cache_root", lambda: blocker)
    assert offline_cache.store("/x/a.py", "1") is False
