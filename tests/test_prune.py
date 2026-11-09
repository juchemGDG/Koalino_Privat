"""Aufräumen der lokalen Daten (offline_cache.prune, snapshots.prune_orphans)."""
import os
import time

import pytest

from koalino import offline_cache
from koalino.snapshots import SnapshotStore, prune_orphans

DAY = 86400


def _age(path, days: float) -> None:
    """Setzt die Änderungszeit einer Datei/eines Ordners ``days`` Tage zurück."""
    t = time.time() - days * DAY
    os.utime(path, (t, t))


# ── offline_cache ────────────────────────────────────────────────────────────
def test_cache_path_is_stable_and_keeps_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(offline_cache, "cache_root", lambda: tmp_path)
    p1 = offline_cache.cache_path("/schule/projekt/ampel.py")
    p2 = offline_cache.cache_path("/schule/projekt/ampel.py")
    assert p1 == p2
    assert p1.name == "ampel.py"
    assert p1.parent.parent == tmp_path


def test_store_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(offline_cache, "cache_root", lambda: tmp_path)
    assert offline_cache.store("/x/y/test.py", "print('hi')\n")
    assert offline_cache.load("/x/y/test.py") == "print('hi')\n"
    assert offline_cache.load("/x/y/unbekannt.py") is None


def test_prune_removes_only_old_files_and_empty_dirs(tmp_path):
    old_dir = tmp_path / "aaaa"
    new_dir = tmp_path / "bbbb"
    old_dir.mkdir(); new_dir.mkdir()
    old_file = old_dir / "alt.py"
    new_file = new_dir / "neu.py"
    old_file.write_text("alt"); new_file.write_text("neu")
    _age(old_file, 61)

    removed = offline_cache.prune(max_age_days=60, root=tmp_path)

    assert removed == 1
    assert not old_file.exists()
    assert not old_dir.exists()          # leerer Ordner weg
    assert new_file.exists()


def test_prune_without_root_dir_is_harmless(tmp_path):
    assert offline_cache.prune(root=tmp_path / "gibt_es_nicht") == 0


# ── snapshots ────────────────────────────────────────────────────────────────
def test_prune_orphans_removes_stale_dirs_keeps_recent(tmp_path):
    store = SnapshotStore(root=tmp_path)
    store.add("/p/alt.py", "print(1)\n")
    store.add("/p/neu.py", "print(2)\n")
    alt_dir = store._dir("/p/alt.py")
    neu_dir = store._dir("/p/neu.py")
    for p in alt_dir.iterdir():
        _age(p, 91)
    _age(alt_dir, 91)

    removed = prune_orphans(max_age_days=90, root=tmp_path)

    assert removed == 1
    assert not alt_dir.exists()
    assert neu_dir.exists()
    assert store.list("/p/neu.py")       # Index intakt


def test_prune_orphans_pinned_does_not_protect(tmp_path):
    """Gemerkte Stände schützen den Ordner nicht – die Frist gilt für alle."""
    store = SnapshotStore(root=tmp_path)
    store.add("/p/x.py", "a", gemerkt=True, notiz="wichtig")
    d = store._dir("/p/x.py")
    for p in d.iterdir():
        _age(p, 100)
    assert prune_orphans(max_age_days=90, root=tmp_path) == 1
    assert not d.exists()


def test_prune_orphans_missing_root(tmp_path):
    assert prune_orphans(max_age_days=1, root=tmp_path / "nix") == 0


# ── SnapshotStore-Grundverhalten (mitgenommen, weil ohne Qt testbar) ─────────
def test_add_dedupes_same_content(tmp_path):
    store = SnapshotStore(root=tmp_path)
    s1 = store.add("/p/a.py", "x = 1\n")
    s2 = store.add("/p/a.py", "x = 1\n")
    assert s1.id == s2.id
    assert len(store.list("/p/a.py")) == 1


def test_last_good_prefers_ok_or_pinned(tmp_path):
    store = SnapshotStore(root=tmp_path)
    s1 = store.add("/p/b.py", "v1")
    store.set_result("/p/b.py", s1.id, "ok")
    s2 = store.add("/p/b.py", "v2")
    store.set_result("/p/b.py", s2.id, "error", "NameError")
    good = store.last_good("/p/b.py")
    assert good is not None and good.id == s1.id
