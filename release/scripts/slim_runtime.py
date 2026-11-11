"""Verringert die Zahl der Dateien in der mitgelieferten Python-Runtime.

Aufruf (immer mit dem Python der Runtime selbst, damit die .pyc passen):

    python_runtime/python/bin/python3 -I release/scripts/slim_runtime.py python_runtime
    python_runtime\\python\\python.exe -I release\\scripts\\slim_runtime.py python_runtime

Warum: Die Runtime besteht aus mehreren tausend kleinen Dateien. In
Schulnetzen prüft der Virenscanner jede einzelne – bei der Installation, bei
Updates und bei jedem Import. Das Skript macht zwei Dinge:

1. Standardbibliothek -> ``python3XX.zip``
   Python kann die Standardbibliothek direkt aus diesem Zip laden (so arbeitet
   auch die offizielle „embeddable“-Distribution für Windows); der Pfad steht
   von Haus aus in ``sys.path``, noch vor dem Lib-Ordner. Ins Zip kommen
   Quelltext und Bytecode (hash-basiert, unchecked): Bytecode, damit nichts
   bei jedem Start neu kompiliert wird (zipimport schreibt keine .pyc),
   Quelltext, damit Tracebacks in Schüler-Programmen weiterhin die Codezeile
   aus z. B. tkinter/turtle zeigen.

   NICHT ins Zip kommen:
     * site-packages – pip muss dort weiter installieren/deinstallieren können
     * lib-dynload   – C-Erweiterungen lassen sich nicht aus Zips laden
     * config-3.XX-* – Build-Infos für sysconfig (posix)
     * venv          – liest seine Aktivierungsskripte als echte Dateien
     * os.py         – „Landmark“, an dem Python beim Start sys.prefix erkennt
     * native Dateien (.so/.pyd/.dll), falls es welche gibt

2. Ballast in site-packages entfernen
   * ``tests``-Ordner der Pakete (v. a. numpy/matplotlib, ~1.000 Dateien) –
     werden von Programmen nie importiert. ``matplotlib/testing`` bleibt, das
     ist echter Bibliothekscode.
   * ``.pyi``-Typ-Stubs – nur für Typprüfer, nie zur Laufzeit gelesen.
   pip kommt bei einem späteren Update/Deinstallieren mit den fehlenden
   Dateien zurecht (es überspringt sie).

Das Skript ist wiederholbar: ein vorhandenes Zip wird nicht neu gebaut, der
Ballast-Schritt findet beim zweiten Lauf einfach nichts mehr.
"""

from __future__ import annotations

import importlib.util
import os
import py_compile
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import zipfile
from pathlib import Path

KEEP_DIRS = {"site-packages", "lib-dynload", "venv", "__pycache__"}
KEEP_FILES = {"os.py"}
NATIVE_SUFFIXES = {".so", ".pyd", ".dll", ".dylib"}

# Was danach funktionieren muss (nur Import/Rechnen – kein Fenster öffnen).
SMOKE_TEST = r"""
import importlib.util, os, sys, json, traceback
zip_entries = [p for p in sys.path if p.endswith('.zip')]
assert zip_entries and os.path.isfile(zip_entries[0]), sys.path
assert json.__file__.startswith(zip_entries[0]), json.__file__
import asyncio, ctypes, csv, datetime, decimal, email, hashlib, http.client
import logging, math, multiprocessing, random, re, socket, sqlite3, ssl
import statistics, subprocess, threading, tkinter, turtle, unittest, urllib.request
import venv, zoneinfo
# Tracebacks aus der Standardbibliothek müssen die Codezeile zeigen:
try:
    json.loads('{')
except ValueError:
    tb = traceback.format_exc()
assert '.zip' in tb, tb
assert 'return _default_decoder.decode(s)' in tb, 'Quelltext im Traceback fehlt:\n' + tb
if importlib.util.find_spec('matplotlib'):
    import tempfile, matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt, numpy as np
    plt.plot(np.arange(5), np.arange(5) ** 2)
    plt.savefig(os.path.join(tempfile.mkdtemp(), 'test.png'))
for mod in ('serial', 'requests', 'pip'):
    if importlib.util.find_spec(mod) is None:
        raise SystemExit(f'Paket fehlt: {mod}')
print('Selbsttest ok: Standardbibliothek aus', zip_entries[0])
"""


def _count_files(root: Path) -> int:
    return sum(len(files) for _, _, files in os.walk(root))


def _zip_target() -> Path:
    name = f"python{sys.version_info[0]}{sys.version_info[1]}.zip"
    for entry in sys.path:
        if entry and Path(entry).name == name:
            return Path(entry)
    raise SystemExit(f"Fehler: {name} steht nicht in sys.path: {sys.path}")


def _should_keep(rel: Path) -> bool:
    if rel.parts[0] in KEEP_DIRS or rel.parts[0].startswith("config-"):
        return True
    if "__pycache__" in rel.parts:
        return True
    if len(rel.parts) == 1 and rel.name in KEEP_FILES:
        return True
    return rel.suffix.lower() in NATIVE_SUFFIXES


def _compile(src: Path, display_path: str, tmp_dir: Path) -> bytes | None:
    cfile = tmp_dir / "out.pyc"
    try:
        py_compile.compile(
            str(src), cfile=str(cfile), dfile=display_path, doraise=True,
            invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
        )
    except py_compile.PyCompileError as exc:
        # Absichtlich kaputte Testdateien u. Ä.: nur als Quelltext mitnehmen.
        print(f"  Hinweis: {src.name} nicht kompilierbar ({exc.exc_type_name})")
        return None
    return cfile.read_bytes()


def pack_stdlib(stdlib: Path, target: Path) -> list[Path]:
    """Schreibt das Zip und liefert die Dateien, die danach weg können."""
    packed: list[Path] = []
    tmp_zip = target.with_suffix(".zip.tmp")
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(
        tmp_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as zf:
        tmp_dir = Path(tmp)
        for dirpath, dirnames, filenames in os.walk(stdlib):
            dirnames.sort()
            here = Path(dirpath)
            for fname in sorted(filenames):
                path = here / fname
                rel = path.relative_to(stdlib)
                if _should_keep(rel):
                    continue
                arc = rel.as_posix()
                zf.write(path, arc)
                if path.suffix == ".py":
                    # zipimport erwartet Bytecode als „modul.pyc“ neben
                    # „modul.py“ (nicht in __pycache__). Der Anzeigepfad zeigt
                    # ins Zip – dort liegt der Quelltext später wirklich.
                    code = _compile(path, os.path.join(str(target), *rel.parts), tmp_dir)
                    if code is not None:
                        zf.writestr(arc[:-3] + ".pyc", code)
                packed.append(path)
    os.replace(tmp_zip, target)
    return packed


def _remove_empty_dirs(root: Path) -> None:
    for dirpath, _, _ in sorted(os.walk(root), key=lambda t: -len(t[0])):
        d = Path(dirpath)
        if d != root and not any(d.iterdir()):
            d.rmdir()


def remove_packed(stdlib: Path, packed: list[Path]) -> None:
    tag = sys.implementation.cache_tag
    for path in packed:
        path.unlink()
        # Zugehörige __pycache__-Einträge werden nie wieder benutzt.
        if path.suffix == ".py":
            for cached in (path.parent / "__pycache__").glob(f"{path.stem}.{tag}*.pyc"):
                cached.unlink()
    _remove_empty_dirs(stdlib)


def strip_site_packages(site_packages: Path) -> int:
    """Entfernt tests-Ordner und .pyi-Stubs; liefert die Zahl gelöschter Dateien."""
    removed = 0
    for dirpath, dirnames, filenames in os.walk(site_packages):
        here = Path(dirpath)
        if here == site_packages:
            # Nur innerhalb von Paketen aufräumen, nie ein Top-Level-Paket.
            continue
        for name in list(dirnames):
            if name == "tests":
                removed += _count_files(here / name)
                shutil.rmtree(here / name)
                dirnames.remove(name)
        for fname in filenames:
            if fname.endswith(".pyi"):
                (here / fname).unlink()
                removed += 1
    return removed


def main() -> int:
    # Schutz: niemals versehentlich das System-Python verändern. Der
    # Runtime-Ordner muss ausdrücklich übergeben werden und der laufende
    # Interpreter muss genau darin liegen.
    if len(sys.argv) != 2:
        raise SystemExit("Nutzung: <runtime-python> -I slim_runtime.py <python_runtime-Ordner>")
    expected = Path(sys.argv[1]).resolve()
    runtime_root = Path(sys.prefix).resolve()
    if sys.prefix != sys.base_prefix or expected not in (runtime_root, *runtime_root.parents):
        raise SystemExit(
            f"Fehler: Dieses Python ({sys.executable}) gehört nicht zur Runtime {expected}."
        )
    stdlib = Path(sysconfig.get_path("stdlib")).resolve()
    site_packages = Path(sysconfig.get_path("purelib")).resolve()
    for p in (stdlib, site_packages):
        if runtime_root not in p.parents:
            raise SystemExit(f"Fehler: {p} liegt nicht in der Runtime {runtime_root}")

    before = _count_files(runtime_root)

    target = _zip_target()
    if target.exists():
        print(f"{target.name} existiert bereits – Standardbibliothek ist schon gepackt.")
    else:
        print(f"Packe Standardbibliothek nach {target} ...")
        packed = pack_stdlib(stdlib, target)
        remove_packed(stdlib, packed)
        size_mb = target.stat().st_size / 1e6
        print(f"  {len(packed)} Dateien gepackt ({size_mb:.1f} MB Zip).")

    print("Entferne tests-Ordner und .pyi-Stubs aus site-packages ...")
    print(f"  {strip_site_packages(site_packages)} Dateien entfernt.")

    print(f"Dateien in der Runtime: {before} -> {_count_files(runtime_root)}")

    # Frischer Prozess: lädt die Standardbibliothek wirklich aus dem Zip.
    result = subprocess.run([sys.executable, "-I", "-c", SMOKE_TEST])
    if result.returncode != 0:
        print("Fehler: Selbsttest der verkleinerten Runtime fehlgeschlagen.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
