"""Lokale Daten: Größe ermitteln und löschen (koalino.local_data)."""
from koalino import local_data


def test_size_of_counts_files_recursively(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.txt").write_bytes(b"12345")
    (tmp_path / "y.txt").write_bytes(b"123")
    assert local_data.size_of(tmp_path) == 8
    assert local_data.size_of(tmp_path / "y.txt") == 3
    assert local_data.size_of(tmp_path / "fehlt") == 0


def test_format_size():
    assert local_data.format_size(512) == "512 B"
    assert local_data.format_size(4096) == "4 KB"
    assert local_data.format_size(3 * 1024 * 1024) == "3.0 MB"


def test_clear_offline_cache_and_snapshots_empty_dir_but_keep_root(tmp_path):
    for sub in ("aaa", "bbb"):
        d = tmp_path / sub
        d.mkdir()
        (d / "f.py").write_text("x")
    (tmp_path / "lose.txt").write_text("y")
    assert local_data.clear_offline_cache(root=tmp_path) == 3
    assert tmp_path.exists() and not any(tmp_path.iterdir())
    assert local_data.clear_snapshots(root=tmp_path) == 0


def test_clear_missing_dir_is_zero(tmp_path):
    assert local_data.clear_offline_cache(root=tmp_path / "nix") == 0


def test_clear_crash_log_keeps_current_session(tmp_path):
    log = tmp_path / "crash.log"
    log.write_text("=== START 1 ===\nalt\nFatal Python error\n=== START 2 ===\n· neu\n",
                   encoding="utf-8")
    removed = local_data.clear_crash_log(path=log)
    assert removed > 0
    assert log.read_text(encoding="utf-8") == "=== START 2 ===\n· neu\n"


def test_clear_crash_log_without_header_empties_file(tmp_path):
    log = tmp_path / "crash.log"
    log.write_text("irgendwas", encoding="utf-8")
    assert local_data.clear_crash_log(path=log) == 9
    assert log.read_text(encoding="utf-8") == ""


def test_clear_crash_log_missing_file(tmp_path):
    assert local_data.clear_crash_log(path=tmp_path / "nein.log") == 0


def test_stores_have_unique_keys_and_callables():
    keys = [s.key for s in local_data.STORES]
    assert len(keys) == len(set(keys)) == 3
    for s in local_data.STORES:
        assert callable(s.path) and callable(s.clear)
