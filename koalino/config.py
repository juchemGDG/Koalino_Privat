"""Konstanten und Konfiguration für Koalino."""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def python_executable() -> str:
    """Liefert einen echten Python-Interpreter zum Starten von Subprozessen.

    WICHTIG: In einem PyInstaller-Bundle ist ``sys.executable`` die App selbst
    (z. B. ``Koalino.app/Contents/MacOS/Koalino``) und KEIN Python-Interpreter.
    Würde man sie als Interpreter starten (``[sys.executable, "-i"]`` o. ä.),
    ignoriert der Bootloader die Argumente und startet die GUI rekursiv neu –
    eine Endlosschleife / Fork-Bomb, die den Rechner zum Absturz bringen kann.

    Im Frozen-Modus wird ein „guter" System-Python gesucht; im normalen Modus
    der venv-Python bzw. der laufende Interpreter.
    """
    if getattr(sys, "frozen", False):
        return _best_system_python()
    venv_py = _venv_python()
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def _is_poor_macos_python(path: str) -> bool:
    """True für macOS-Pythons, die für den Unterricht ungeeignet sind.

    Der Command-Line-Tools-/System-Python bringt ein veraltetes Tk 8.5 mit
    (leere/abstürzende Tkinter-Fenster) und ist häufig „externally managed"
    (pip blockiert). python.org-/Homebrew-Pythons sind klar zu bevorzugen.
    """
    pl = path.lower()
    return (
        "/library/developer/commandlinetools" in pl
        or pl.startswith("/system/")
    )


_BEST_PYTHON_CACHE: str | None = None


def _best_system_python() -> str:
    """Bester verfügbarer System-Python (Frozen-Modus), Command-Line-Tools meidend."""
    global _BEST_PYTHON_CACHE
    if _BEST_PYTHON_CACHE:
        return _BEST_PYTHON_CACHE
    candidates = detect_python_interpreters()
    good = [c for c in candidates if not _is_poor_macos_python(c)]
    chosen = (
        good[0] if good
        else (candidates[0] if candidates else None)
        or shutil.which("python3") or shutil.which("python")
        or ("python" if sys.platform == "win32" else "python3")
    )
    _BEST_PYTHON_CACHE = chosen
    return chosen


def _venv_python() -> Path:
    """Pfad zum Python der projekteigenen .venv (Dev-Modus)."""
    return Path(__file__).resolve().parents[1] / ".venv" / (
        "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    )


def _embedded_runtime_candidates() -> list[Path]:
    """Mögliche Interpreter-Pfade einer mitgelieferten Runtime.

    Dev-Modus: ``<project>/python_runtime/...``
    Frozen-Modus: neben der App-EXE bzw. im App-Bundle-Inhalt.
    """
    project_root = Path(__file__).resolve().parents[1]
    roots: list[Path] = [project_root / "python_runtime"]

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        roots.append(exe_dir / "python_runtime")
        # Falls Startpunkt innerhalb eines App-Bundles liegt, auch einen Level höher prüfen.
        roots.append(exe_dir.parent / "python_runtime")
        # macOS-App-Bundle: Contents/Resources als alternativer Ablageort.
        roots.append(exe_dir.parent / "Resources" / "python_runtime")

    if sys.platform == "win32":
        rels = [
            Path("python.exe"),
            Path("Scripts/python.exe"),
            Path("python/python.exe"),
        ]
    else:
        rels = [
            Path("bin/python3"),
            Path("bin/python"),
            Path("python/bin/python3"),
            Path("python/bin/python"),
        ]

    out: list[Path] = []
    for root in roots:
        for rel in rels:
            out.append(root / rel)
    return out


def embedded_python_executable() -> str | None:
    """Liefert den Pfad zum mitgelieferten Python-Interpreter, falls vorhanden."""
    for cand in _embedded_runtime_candidates():
        if cand.exists():
            return str(cand)
    return None


def preferred_python_interpreter() -> str | None:
    """Bevorzugter Interpreter für die UI-Auswahl (erster ermittelter Treffer)."""
    found = detect_python_interpreters()
    return found[0] if found else None


def detect_python_interpreters() -> list[str]:
    """Sucht mögliche Python-Interpreter auf dem System.

    Durchsucht PATH und plattformtypische Installationsorte. Liefert eine
    deduplizierte Liste echter Pfade (reale Ziele, keine Symlink-Dubletten).
    Die App selbst (Frozen-EXE) wird NIE vorgeschlagen – das würde beim Start
    eines Programms die GUI rekursiv neu öffnen (Fork-Bomb-Schutz).
    """
    found: list[str] = []
    seen_real: set[str] = set()

    def add(path: str | None):
        if not path:
            return
        try:
            p = Path(path)
            if not p.exists():
                return
            shown = str(p)
            real = str(p.resolve())
        except OSError:
            return
        if real in seen_real:
            return
        seen_real.add(real)
        found.append(shown)

    # 0. Mitgelieferte Runtime bevorzugt (Hybrid-Modus)
    for cand in _embedded_runtime_candidates():
        if cand.exists():
            add(str(cand))

    # 1. Projekteigene .venv (Dev-Modus) zuerst
    venv_py = _venv_python()
    if venv_py.exists():
        add(str(venv_py))

    # 2. Über PATH auffindbare Namen
    minor_names = [f"python3.{m}" for m in range(20, 7, -1)]
    if sys.platform == "win32":
        path_names = ["python.exe", "python3.exe", "python"]
    else:
        path_names = ["python3", "python", *minor_names]
    for name in path_names:
        add(shutil.which(name))

    # 3. Plattformtypische Installationsorte
    if sys.platform == "win32":
        # py-Launcher kennt alle registrierten Versionen
        py_launcher = shutil.which("py")
        if py_launcher:
            try:
                res = subprocess.run([py_launcher, "-0p"], capture_output=True,
                                     text=True, timeout=5)
                for line in res.stdout.splitlines():
                    for token in line.split():
                        if token.lower().endswith("python.exe"):
                            add(token)
            except Exception:
                pass
        bases: list[str] = []
        for env_var in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            val = os.environ.get(env_var)
            if val:
                bases.append(val)
        bases.append("C:\\")
        for base in bases:
            for pattern_base in (Path(base), Path(base) / "Programs" / "Python"):
                try:
                    for d in pattern_base.glob("Python3*"):
                        add(str(d / "python.exe"))
                except OSError:
                    pass
    else:
        search_dirs = [
            "/usr/bin", "/usr/local/bin", "/opt/homebrew/bin",
            "/opt/local/bin", str(Path.home() / ".pyenv" / "shims"),
        ]
        macfw = Path("/Library/Frameworks/Python.framework/Versions")
        if macfw.exists():
            try:
                for ver in macfw.glob("3.*"):
                    search_dirs.append(str(ver / "bin"))
            except OSError:
                pass
        for d in search_dirs:
            for name in ["python3", "python", *minor_names]:
                add(str(Path(d) / name))

    # 4. Frozen-App-EXE niemals vorschlagen
    if getattr(sys, "frozen", False):
        try:
            self_exe = str(Path(sys.executable).resolve())
            found = [c for c in found if c != self_exe]
        except OSError:
            pass

    return found


def python_version_label(path: str) -> str:
    """Kurzbeschreibung (z. B. 'Python 3.12.3') eines Interpreters – leer bei Fehler."""
    try:
        res = subprocess.run([path, "--version"], capture_output=True,
                             text=True, timeout=5)
        return (res.stdout or res.stderr).strip()
    except Exception:
        return ""


def python_has_tkinter(path: str) -> bool:
    """Prüft, ob ein Interpreter tkinter importieren kann.

    Viele GUI-Programme im Unterricht brauchen tkinter. Es fehlt z. B. beim
    Homebrew-Python ohne ``python-tk`` oder ist beim macOS-System-Python defekt.
    """
    try:
        res = subprocess.run([path, "-c", "import tkinter"],
                             capture_output=True, text=True, timeout=8)
        return res.returncode == 0
    except Exception:
        return False


def asset_path(name: str) -> Path | None:
    """Findet eine Datei im assets-Ordner – im Dev- wie im PyInstaller-Bundle."""
    candidates = []
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "koalino" / "assets" / name)
        candidates.append(Path(sys.executable).parent / "koalino" / "assets" / name)
    candidates.append(Path(__file__).resolve().parent / "assets" / name)
    for p in candidates:
        if p.exists():
            return p
    return None


def tool_command(module: str) -> list[str]:
    """Befehl, um ein mitgeliefertes Tool (``mpremote``/``esptool``) zu starten.

    Im Frozen-Modus ruft sich die App selbst als Dispatcher auf
    (``[sys.executable, "-m", module]`` – siehe ``release/launcher.py``), weil
    der System-Python das Modul i. d. R. NICHT enthält
    (``No module named mpremote``). Die Module sind ins PyInstaller-Bundle
    eingepackt und werden vom Launcher in-process ausgeführt.

    Im Dev-Modus wird der venv-/aktuelle Python verwendet.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "-m", module]
    return [python_executable(), "-m", module]


APP_NAME = "Koalino"
APP_VERSION = "1.12.0"

# GitHub-Repository für Bibliotheken
LIB_REPO_API = "https://api.github.com/repos/juchemGDG/NIT_Bibliotheken/contents"
LIB_REPO_RAW = "https://raw.githubusercontent.com/juchemGDG/NIT_Bibliotheken/main"

# MicroPython Download-Seite
MICROPYTHON_DOWNLOAD_BASE = "https://micropython.org/download/"

# Fehlerbericht ("Hilfe → Fehler melden"). Der Dialog schickt einen HTTPS-POST
# (JSON) an BUG_REPORT_URL; ein kleines Server-Skript (siehe server/bugreport.php)
# leitet ihn als E-Mail an BUG_REPORT_EMAIL weiter. So liegen KEINE Mail-
# Zugangsdaten im Programm. URL an den eigenen Endpoint anpassen.
BUG_REPORT_URL = "https://mint-checker.de/nitcode/nc-report-x7q3.php"
BUG_REPORT_EMAIL = "nitcode@mint-checker.de"

SUPPORTED_BOARDS = {
    # ESP-Familie: alle über esptool geflasht (flash_cmd "esp32"). Chip-Typ und
    # Bootloader-Offset unterscheiden sich je Variante – der originale ESP32 und
    # der S2 haben den Bootloader bei 0x1000, die neueren RISC-V-/S3-Chips bei 0x0.
    "ESP32": {
        "label": "ESP32",
        "download_page": "ESP32_GENERIC",
        "flash_cmd": "esp32",
        "chip": "esp32",
        "flash_offset": "0x1000",
        "baud": 115200,
    },
    "ESP32-C3": {
        "label": "ESP32-C3",
        "download_page": "ESP32_GENERIC_C3",
        "flash_cmd": "esp32",
        "chip": "esp32c3",
        "flash_offset": "0x0",
        "baud": 115200,
    },
    "ESP32-S3": {
        "label": "ESP32-S3",
        "download_page": "ESP32_GENERIC_S3",
        "flash_cmd": "esp32",
        "chip": "esp32s3",
        "flash_offset": "0x0",
        "baud": 115200,
    },
    "ESP32-C6": {
        "label": "ESP32-C6",
        "download_page": "ESP32_GENERIC_C6",
        "flash_cmd": "esp32",
        "chip": "esp32c6",
        "flash_offset": "0x0",
        "baud": 115200,
    },
    "ESP32-S2": {
        "label": "ESP32-S2",
        "download_page": "ESP32_GENERIC_S2",
        "flash_cmd": "esp32",
        "chip": "esp32s2",
        "flash_offset": "0x1000",
        "baud": 115200,
    },
    "micro:bit": {
        "label": "micro:bit (auto v1/v2)",
        "download_page": "MICROBIT_AUTO",
        "flash_cmd": "microbit",
        "baud": 115200,
    },
    "RPI Pico 2": {
        "label": "Raspberry Pi Pico 2",
        "download_page": "RPI_PICO2",
        "flash_cmd": "rp2",
        "baud": 115200,
    },
    "RPI Pico 2W": {
        "label": "Raspberry Pi Pico 2W",
        "download_page": "RPI_PICO2_W",
        "flash_cmd": "rp2",
        "baud": 115200,
    },
}

# KI-Tutor (Ollama)
TUTOR_DEFAULT_URL    = "http://localhost:11434"
TUTOR_DEFAULT_MODEL  = "llama3.2"


def ollama_web_password() -> str:
    """Optionales Passwort für einen geschützten Ollama-Web-Proxy.

    Wird NICHT im Quellcode gespeichert (kein Klartext im Repository). Reihenfolge:
      1. Umgebungsvariable ``NIT_OLLAMA_PASSWORD``
      2. lokale, nicht versionierte Datei ``<config-dir>/koalino/ollama_password``
      3. leer → es wird ohne Authentifizierung versucht (lokales Ollama braucht keine)

    Lokales Ollama (localhost) benötigt ohnehin kein Passwort; relevant ist dies
    nur für einen schulischen Reverse-Proxy mit Basic-/Bearer-Auth.
    """
    env = os.environ.get("NIT_OLLAMA_PASSWORD")
    if env:
        return env.strip()
    try:
        pw_file = _user_config_dir() / "ollama_password"
        if pw_file.exists():
            return pw_file.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return ""


def _user_config_dir() -> Path:
    """Plattformabhängiges, nutzerspezifisches Konfigverzeichnis für Koalino."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "koalino"


def migrate_legacy_data() -> None:
    """Übernimmt Konfig und Einstellungen aus der Zeit, als das Programm NIT_Code hieß.

    Läuft bei jedem Start, ist aber nach der ersten Übernahme ein No-op: Ordner
    werden nur kopiert, wenn der neue noch fehlt; QSettings-Werte nur, wenn der
    neue Speicher noch leer ist. Die alten Daten bleiben unangetastet.
    """
    import shutil
    try:
        new_dir = _user_config_dir()
        old_dir = new_dir.parent / "nit_code"
        if old_dir.is_dir() and not new_dir.exists():
            shutil.copytree(old_dir, new_dir)
    except OSError:
        pass
    try:
        from PyQt6.QtCore import QSettings
        neu = QSettings("NIT", "Koalino")
        if not neu.allKeys():
            alt = QSettings("NIT", "NIT_Code")
            for key in alt.allKeys():
                neu.setValue(key, alt.value(key))
            neu.sync()
    except Exception:
        pass

# AIS-Chat (schulischer Web-Chatbot)
AIS_CHAT_URL = "https://app.ais-chat.schule"
FOBIZZ_URL = "https://tools.fobizz.com"

# Lehrgang py.nitbw.de als Seitenleisten-Panel (py_site_panel.py)
PY_SITE_URL = "https://py.nitbw.de"

# PAP-Editor (Programmablaufpläne zeichnen). Die Seite kennt einen Embed-Modus
# (?embed=1), der nur aktiv wird, wenn sie in einem iframe steckt – siehe
# pap_editor.py. PAP_EDITOR_ORIGIN wird als Base-URL der Host-Seite und als
# targetOrigin der postMessage-Aufrufe benutzt.
PAP_EDITOR_ORIGIN = "https://pap.mint-checker.de"
PAP_EDITOR_URL = PAP_EDITOR_ORIGIN + "/?embed=1"

# IBD-Editor (Informations-Blockdiagramm): gleiches Embed-Protokoll wie der PAP-Editor.
IBD_EDITOR_ORIGIN = "https://ibd.mint-checker.de"
IBD_EDITOR_URL = IBD_EDITOR_ORIGIN + "/?embed=1"

# SchaltLab (Schaltplan-Editor): gleiches Embed-Protokoll wie PAP- und IBD-Editor
# (source/target "schaltlab").
SCHALTLAB_ORIGIN = "https://schaltlab.mint-checker.de"
SCHALTLAB_URL = SCHALTLAB_ORIGIN + "/?embed=1"

# StatPlot (Datenauswertung): erst online, ohne Netz die mitgelieferte Kopie –
# siehe statplot_window.py.
STATPLOT_ORIGIN = "https://statplot.mint-checker.de"
STATPLOT_URL = STATPLOT_ORIGIN + "/?embed=1"


def is_ollama_available() -> bool:
    """True wenn das ollama-Kommando im PATH gefunden wird."""
    return shutil.which("ollama") is not None


# ── Themes ───────────────────────────────────────────────────────────────────

_LIGHT_MODERN_THEME: dict[str, str] = {   # an pap./reglerlab.mint-checker.de angelehnt (Slate + Blau)
    "bg_dark":       "#f8fafc",
    "bg_mid":        "#f1f5f9",
    "bg_panel":      "#ffffff",
    "bg_editor":     "#ffffff",
    "accent":        "#2563eb",
    "accent_hover":  "#4f46e5",            # Schlüsselwörter: Indigo
    "text":          "#0f172a",
    "text_dim":      "#64748b",
    "success":       "#047857",            # Strings: Grün
    "error":         "#dc2626",
    "warning":       "#c2410c",            # Zahlen: Orange
    "info":          "#0369a1",            # Klassen/Funktionen: Blau
    "selection":     "#e0ebff",
    "border":        "#e2e8f0",
    "scroll":        "#cbd5e1",
    "terminal_bg":   "#ffffff",
    "terminal_text": "#0f172a",
}

_DARK_THEME: dict[str, str] = {           # Slate-Dunkel wie die MINT-Checker-Seiten
    "bg_dark":       "#0f172a",
    "bg_mid":        "#1e293b",
    "bg_panel":      "#1e293b",
    "bg_editor":     "#0f172a",
    "accent":        "#3b82f6",
    "accent_hover":  "#818cf8",
    "text":          "#e2e8f0",
    "text_dim":      "#94a3b8",
    "success":       "#86efac",
    "error":         "#f87171",
    "warning":       "#fbbf24",
    "info":          "#67e8f9",
    "selection":     "#273449",
    "border":        "#334155",
    "scroll":        "#475569",
    "sidebar":       "#0b1120",
    "terminal_bg":   "#0b1120",
    "terminal_text": "#e2e8f0",
}

_LIGHT_THEME: dict[str, str] = {          # Eclipse-klassisch
    "bg_dark":       "#f5f5f5",
    "bg_mid":        "#eeeeee",
    "bg_panel":      "#e8e8e8",
    "bg_editor":     "#ffffff",
    "accent":        "#3b6ea5",
    "accent_hover":  "#7f0055",            # Eclipse-Schlüsselwort-Lila
    "text":          "#1a1a1a",
    "text_dim":      "#3f7f5f",            # Eclipse-Kommentar-Grün
    "success":       "#2a00ff",            # Eclipse-String-Blau
    "error":         "#cc0000",
    "warning":       "#00627a",            # Zahlen: Blaugrün
    "info":          "#0000c0",            # Klassen/Funktionen: Dunkelblau
    "selection":     "#cce0f5",
    "border":        "#c8c8c8",
    "scroll":        "#b8b8b8",
    "terminal_bg":   "#ffffff",
    "terminal_text": "#1a1a1a",
}

_CONTRAST_THEME: dict[str, str] = {       # Hoher Kontrast: Schwarz auf Weiß, für Beamer und Sehhilfe
    "bg_dark":       "#ffffff",
    "bg_mid":        "#ececec",
    "bg_panel":      "#f4f4f4",
    "bg_editor":     "#ffffff",
    "accent":        "#0033cc",
    "accent_hover":  "#7a0099",
    "text":          "#000000",
    "text_dim":      "#4d4d4d",
    "success":       "#00661a",
    "error":         "#c00000",
    "warning":       "#a34700",
    "info":          "#003399",
    "selection":     "#cfe0ff",
    "border":        "#8c8c8c",
    "scroll":        "#a6a6a6",
    "terminal_bg":   "#ffffff",
    "terminal_text": "#000000",
}

THEMES: dict[str, dict[str, str]] = {
    "modern_light":  _LIGHT_MODERN_THEME,
    "modern_dark":   _DARK_THEME,
    "classic_light": _LIGHT_THEME,
    "contrast":      _CONTRAST_THEME,
}

# Frühere Oberflächen-Designs, die es nur noch als Code-Farbschema gibt:
# gespeicherte Einstellung -> (Design, Code-Farbschema)
LEGACY_THEME_MIGRATION: dict[str, tuple[str, str]] = {
    "solarized": ("modern_light", "solarized"),
    "dracula":   ("modern_dark",  "dracula"),
}

# ── Code-Farbschemata (nur der Editor, unabhängig vom Oberflächen-Design) ─────
# "auto" = Farben aus dem gewählten Design ableiten (Verhalten wie bisher).
# bg/text: Hintergrund und Standardtext; margin_*: Zeilennummernrand;
# line: aktuelle Zeile; bold_kw: Schlüsselwörter fett.
CODE_SCHEMES: dict[str, dict] = {
    "auto": {},
    "eclipse": {
        "bg": "#ffffff", "text": "#000000", "comment": "#3f7f5f",
        "keyword": "#7f0055", "string": "#2a00ff", "number": "#00627a",
        "name": "#0000c0", "decorator": "#646464", "error": "#cc0000",
        "margin_bg": "#f0f0f0", "margin_fg": "#787878",
        "line": "#e8f2fe", "caret": "#000000", "bold_kw": True,
    },
    "thonny": {
        "bg": "#ffffff", "text": "#000000", "comment": "#8a8a8a",
        "keyword": "#c25a00", "string": "#00923a", "number": "#a31515",
        "name": "#0033cc", "decorator": "#900090", "error": "#d00000",
        "margin_bg": "#f2f2f2", "margin_fg": "#8a8a8a",
        "line": "#f3f7ff", "caret": "#000000", "bold_kw": True,
    },
    "idle": {
        "bg": "#ffffff", "text": "#000000", "comment": "#dd0000",
        "keyword": "#ff7700", "string": "#00aa00", "number": "#000000",
        "name": "#0000ff", "decorator": "#900090", "error": "#dd0000",
        "margin_bg": "#e0e0e0", "margin_fg": "#555555",
        "line": "#f0f0f0", "caret": "#000000", "bold_kw": False,
    },
    "solarized": {
        "bg": "#fdf6e3", "text": "#073642", "comment": "#7c8b8d",
        "keyword": "#6c71c4", "string": "#2a7f78", "number": "#b4540a",
        "name": "#1f6fb0", "decorator": "#b4540a", "error": "#dc322f",
        "margin_bg": "#eee8d5", "margin_fg": "#7c8b8d",
        "line": "#eee8d5", "caret": "#268bd2", "bold_kw": False,
    },
    "dracula": {
        "bg": "#282a36", "text": "#f8f8f2", "comment": "#6272a4",
        "keyword": "#ff79c6", "string": "#f1fa8c", "number": "#bd93f9",
        "name": "#50fa7b", "decorator": "#ffb86c", "error": "#ff5555",
        "margin_bg": "#21222c", "margin_fg": "#6272a4",
        "line": "#44475a", "caret": "#f8f8f2", "bold_kw": False,
    },
    "onedark": {
        "bg": "#282c34", "text": "#abb2bf", "comment": "#5c6370",
        "keyword": "#c678dd", "string": "#98c379", "number": "#d19a66",
        "name": "#61afef", "decorator": "#e5c07b", "error": "#e06c75",
        "margin_bg": "#21252b", "margin_fg": "#636d83",
        "line": "#2c313c", "caret": "#528bff", "bold_kw": False,
    },
    "github": {
        "bg": "#ffffff", "text": "#24292f", "comment": "#6e7781",
        "keyword": "#cf222e", "string": "#0a3069", "number": "#0550ae",
        "name": "#8250df", "decorator": "#953800", "error": "#cf222e",
        "margin_bg": "#f6f8fa", "margin_fg": "#8c959f",
        "line": "#f6f8fa", "caret": "#24292f", "bold_kw": False,
    },
    "monokai": {
        "bg": "#272822", "text": "#f8f8f2", "comment": "#88846f",
        "keyword": "#f92672", "string": "#e6db74", "number": "#ae81ff",
        "name": "#a6e22e", "decorator": "#fd971f", "error": "#ff5555",
        "margin_bg": "#1e1f1c", "margin_fg": "#90908a",
        "line": "#3e3d32", "caret": "#f8f8f0", "bold_kw": False,
    },
    # Farbenblind-freundlich (Okabe-Ito, für weißen Grund abgedunkelt):
    # Schlüsselwörter fett, Kommentare kursiv – nicht nur über die Farbe.
    "okabe": {
        "bg": "#ffffff", "text": "#000000", "comment": "#5f5f5f",
        "keyword": "#b34700", "string": "#0072b2", "number": "#007a5a",
        "name": "#9c3f7c", "decorator": "#7a6a00", "error": "#b34700",
        "margin_bg": "#f0f0f0", "margin_fg": "#6b6b6b",
        "line": "#eef5fb", "caret": "#000000", "bold_kw": True,
        "italic_comment": True,
    },
}
CODE_SCHEME_LABELS: dict[str, str] = {
    "auto":      "Passend zum Design",
    "eclipse":   "Eclipse",
    "thonny":    "Thonny",
    "idle":      "IDLE (klassisch)",
    "github":    "GitHub Hell",
    "solarized": "Solarized Hell",
    "okabe":     "Okabe-Ito (farbenblind-freundlich)",
    "dracula":   "Dracula (dunkel)",
    "onedark":   "One Dark (dunkel)",
    "monokai":   "Monokai (dunkel, hoher Kontrast)",
}
_code_scheme = "auto"


def set_code_scheme(name: str) -> None:
    global _code_scheme
    _code_scheme = name if name in CODE_SCHEMES else "auto"


def editor_colors() -> dict:
    """Farben des Code-Editors: Schema, sonst aus dem aktiven Design abgeleitet."""
    t = THEME
    c = {
        "bg": t["bg_editor"], "text": t["text"], "comment": t["text_dim"],
        "keyword": t["accent_hover"], "string": t["success"],
        "number": t["warning"], "name": t["info"], "decorator": t["warning"],
        "error": t["error"], "margin_bg": t["bg_mid"], "margin_fg": t["text_dim"],
        "line": t["selection"], "caret": t["accent"], "bold_kw": False,
        "italic_comment": False,
        "guide": t["scroll"],
    }
    scheme = CODE_SCHEMES.get(_code_scheme, {})
    c.update(scheme)
    if scheme:   # Einrückungslinien: Mitte zwischen Rand-Hintergrund und Rand-Schrift
        a, b = c["margin_bg"].lstrip("#"), c["margin_fg"].lstrip("#")
        c["guide"] = "#" + "".join(
            f"{(int(a[i:i + 2], 16) + int(b[i:i + 2], 16)) // 2:02x}" for i in (0, 2, 4))
    return c

THEME: dict[str, str] = dict(_LIGHT_MODERN_THEME)  # aktives Theme (veränderlich), Standard: modern hell


# ── Schriftart für Editor und Konsole ────────────────────────────────────────
MONO_FONTS: dict[str, tuple[str, str]] = {
    "default": ("Standard (JetBrains Mono)", "JetBrains Mono, Fira Code, Consolas, monospace"),
    "system":  ("Systemschrift (Consolas / Menlo)", "Consolas, Menlo, DejaVu Sans Mono, monospace"),
    "courier": ("Courier New (klassisch)", "Courier New, Courier, monospace"),
}
_mono_key = "default"


def set_mono_font(key: str) -> None:
    global _mono_key
    _mono_key = key if key in MONO_FONTS else "default"


def mono_family() -> str:
    """Schriftfamilien-Liste für Editor und Konsole (Qt wählt die erste vorhandene)."""
    return MONO_FONTS[_mono_key][1]


def set_theme(name: str) -> None:
    """Aktives Theme in-place aktualisieren (alle Referenzen auf THEME sehen die Änderung)."""
    THEME.update(THEMES.get(name, _DARK_THEME))
