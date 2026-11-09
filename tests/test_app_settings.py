"""Einstellungen laden/speichern samt Migrationen (koalino.app_settings, ohne Qt)."""
import pytest

from koalino import app_settings
from koalino.app_settings import AppSettings, normalize_sketchbook_dir


class FakeStore(dict):
    """Minimaler Ersatz für QSettings."""

    def value(self, key, default=None, type=None):
        v = self.get(key, default)
        if type is bool and isinstance(v, str):
            return v.lower() == "true"
        return v

    def setValue(self, key, value):
        self[key] = value

    def contains(self, key):
        return key in self

    def remove(self, key):
        self.pop(key, None)

    def sync(self):
        pass


@pytest.fixture(autouse=True)
def no_embedded_runtime(monkeypatch):
    monkeypatch.setattr(app_settings, "embedded_python_executable", lambda: None)
    monkeypatch.setattr(app_settings, "preferred_python_interpreter", lambda: "/usr/bin/python3")


def test_defaults_on_empty_store():
    s = AppSettings.load(FakeStore())
    assert (s.font_size, s.theme, s.tutor_mode, s.scrollback) == (14, "modern_light", "none", 5000)
    assert s.blocks_enabled and not s.statplot_offline and s.hidden_activity == set()


def test_save_then_load_roundtrip(tmp_path):
    store = FakeStore()
    s = AppSettings(font_size=18, word_wrap=True, theme="modern_dark", plot_y_min=1.5, plot_x_max=300,
                    hidden_activity={"stats", "pap"}, sketchbook=str(tmp_path), git_repo="/x/repo",
                    tutor_mode="fobizz", debug_stepped=False, python_exec="/usr/bin/python3")
    s.save(store)
    store["ui/layout_v2"] = True
    store["blocks/default_on_migrated"] = True
    store["python/prefer_embedded_migrated"] = True
    again = AppSettings.load(store)
    assert again == s


def test_hidden_activity_is_sorted_and_unknown_keys_dropped():
    store = FakeStore({"ui/hidden_activity": "stats,bogus,files,,pap"})
    assert AppSettings.load(store).hidden_activity == {"stats", "files", "pap"}
    AppSettings(hidden_activity={"stats", "files"}).save(store)
    assert store["ui/hidden_activity"] == "files,stats"


def test_garbage_numbers_fall_back_to_defaults():
    store = FakeStore({"editor/font_size": "x", "plot/y_min": "?", "console/scrollback": None})
    s = AppSettings.load(store)
    assert s.font_size == 14 and s.plot_y_min == 0.0 and s.scrollback == 5000


@pytest.mark.parametrize("raw, expected", [
    (True, True), (False, False), ("true", True), ("1", True), ("yes", True), ("on", True),
    ("false", False), ("0", False), ("junk", False),
])
def test_bool_parsing(raw, expected):
    assert AppSettings.load(FakeStore({"editor/word_wrap": raw})).word_wrap is expected


# ── Migrationen ──────────────────────────────────────────────────────────────
def test_block_editor_enabled_once_for_old_installations():
    store = FakeStore({"blocks/enabled": False})
    assert AppSettings.load(store).blocks_enabled is True
    assert store["blocks/default_on_migrated"] is True
    # Spätere bewusste Abwahl bleibt erhalten
    store["blocks/enabled"] = False
    assert AppSettings.load(store).blocks_enabled is False


def test_embedded_runtime_preferred_once(monkeypatch):
    monkeypatch.setattr(app_settings, "embedded_python_executable", lambda: "/opt/koalino/python3")
    store = FakeStore({"python/executable": "/usr/bin/python3"})
    assert AppSettings.load(store).python_exec == "/opt/koalino/python3"
    assert store["python/prefer_embedded_migrated"] is True
    # Danach bleibt eine vorhandene Wahl bestehen
    store["python/executable"] = "/usr/bin/python3"
    assert AppSettings.load(store).python_exec == "/usr/bin/python3"


def test_missing_python_falls_back(monkeypatch):
    store = FakeStore({"python/prefer_embedded_migrated": True, "python/executable": "/nonexistent/python"})
    assert AppSettings.load(store).python_exec == "/usr/bin/python3"
    assert store["python/executable"] == "/usr/bin/python3"


def test_ollama_modes_and_keys_are_removed():
    store = FakeStore({"tutor/mode": "ollama", "tutor/url": "http://x", "tutor/model": "m"})
    s = AppSettings.load(store)
    assert s.tutor_mode == "none"
    assert "tutor/url" not in store and "tutor/model" not in store


def test_classic_theme_moves_to_modern_light_once():
    store = FakeStore({"ui/theme": "classic_light"})
    assert AppSettings.load(store).theme == "modern_light"
    assert store["ui/layout_v2"] is True


def test_legacy_theme_becomes_code_scheme():
    from koalino.config import LEGACY_THEME_MIGRATION
    legacy, (theme, scheme) = next(iter(LEGACY_THEME_MIGRATION.items()))
    s = AppSettings.load(FakeStore({"ui/theme": legacy, "ui/layout_v2": True}))
    assert (s.theme, s.code_scheme) == (theme, scheme)


def test_unknown_code_scheme_becomes_auto():
    assert AppSettings.load(FakeStore({"ui/code_scheme": "gibtsnicht"})).code_scheme == "auto"


def test_unknown_debug_level_becomes_kl10():
    assert AppSettings.load(FakeStore({"debug/level": "zzz"})).debug_level == "kl10"


# ── Hilfen ───────────────────────────────────────────────────────────────────
def test_normalize_sketchbook_dir(tmp_path):
    assert normalize_sketchbook_dir(str(tmp_path)) == str(tmp_path.resolve())
    home = normalize_sketchbook_dir("")
    assert normalize_sketchbook_dir(str(tmp_path / "gibt-es-nicht")) == home


def test_copy_is_independent():
    a = AppSettings(hidden_activity={"stats"})
    b = a.copy()
    b.hidden_activity.add("pap")
    b.font_size = 99
    assert a.hidden_activity == {"stats"} and a.font_size == 14
