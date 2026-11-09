"""Stände einer Datei (koalino.snapshots.SnapshotStore)."""
import pytest

from koalino import snapshots
from koalino.snapshots import SnapshotStore, change_summary, text_hash

DATEI = "/schule/projekt/ampel.py"


@pytest.fixture
def store(tmp_path):
    return SnapshotStore(tmp_path)


def test_add_and_read_roundtrip(store):
    s = store.add(DATEI, "print(1)")
    assert store.read(DATEI, s.id) == "print(1)"
    assert [x.id for x in store.list(DATEI)] == [s.id]


def test_add_same_content_does_not_duplicate(store):
    a = store.add(DATEI, "print(1)")
    store.set_result(DATEI, a.id, "error", "Boom")
    b = store.add(DATEI, "print(1)")
    assert b.id == a.id
    assert len(store.list(DATEI)) == 1
    # Neuer Lauf desselben Inhalts setzt Ergebnis und Meldung zurück
    assert b.ergebnis == "run" and b.meldung == ""


def test_add_same_content_gemerkt_marks_existing(store):
    a = store.add(DATEI, "x = 1")
    b = store.add(DATEI, "x = 1", gemerkt=True, notiz="läuft")
    assert b.id == a.id
    assert b.gemerkt and b.notiz == "läuft"


def test_different_content_gets_unique_ids_even_in_same_millisecond(store, monkeypatch):
    monkeypatch.setattr(snapshots.time, "time", lambda: 1_700_000_000.123)
    ids = {store.add(DATEI, f"x = {i}").id for i in range(5)}
    assert len(ids) == 5
    assert len(store.list(DATEI)) == 5


def test_list_is_newest_first(store):
    a = store.add(DATEI, "a")
    b = store.add(DATEI, "b")
    assert [s.id for s in store.list(DATEI)] == [b.id, a.id]
    assert store.previous(DATEI).id == b.id


def test_prune_keeps_remembered_states(store, monkeypatch):
    monkeypatch.setattr(snapshots, "MAX_STAENDE", 3)
    gemerkt = store.add(DATEI, "wichtig", gemerkt=True)
    for i in range(6):
        store.add(DATEI, f"lauf {i}")
    staende = store.list(DATEI)
    assert len(staende) == 3
    assert gemerkt.id in [s.id for s in staende]
    # Die Datei des gelöschten Standes ist ebenfalls weg
    dateien = {p.stem for p in store._dir(DATEI).glob("*.txt")}
    assert dateien == {s.id for s in staende}


def test_prune_stops_when_only_remembered_states_remain(store, monkeypatch):
    monkeypatch.setattr(snapshots, "MAX_STAENDE", 2)
    for i in range(4):
        store.add(DATEI, f"m{i}", gemerkt=True)
    assert len(store.list(DATEI)) == 4


def test_last_good_skips_errors_and_excluded_hash(store):
    gut = store.add(DATEI, "gut")
    store.set_result(DATEI, gut.id, "ok")
    schlecht = store.add(DATEI, "schlecht")
    store.set_result(DATEI, schlecht.id, "error", "NameError")
    assert store.last_good(DATEI).id == gut.id
    assert store.last_good(DATEI, exclude_hash=text_hash("gut")) is None


def test_last_good_counts_remembered_state(store):
    s = store.add(DATEI, "gemerkt", gemerkt=True)
    assert store.last_good(DATEI).id == s.id


def test_states_are_per_file(store):
    store.add("/a/x.py", "1")
    assert store.list("/a/y.py") == []
    assert store.list("/b/x.py") == []


def test_unknown_file_has_no_states(store):
    assert store.list(DATEI) == []
    assert store.previous(DATEI) is None
    assert store.read(DATEI, "gibt-es-nicht") is None


def test_corrupt_index_is_treated_as_empty(store):
    s = store.add(DATEI, "x")
    (store._dir(DATEI) / "index.json").write_text("{kaputt", encoding="utf-8")
    assert store.list(DATEI) == []
    assert store.read(DATEI, s.id) == "x"


def test_change_summary_reports_changed_lines():
    assert change_summary("a\nb\nc", "a\nX\nc") == [2]
    assert change_summary("a", "a") == []
