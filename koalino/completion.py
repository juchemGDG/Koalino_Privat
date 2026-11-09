"""Jedi-basierte Code-Vervollständigung und Docstring-Hilfe in einem Hintergrund-Worker."""
import textwrap
import threading

from PyQt6.QtCore import QObject, pyqtSignal

try:
    import jedi
    HAS_JEDI = True
except ImportError:
    HAS_JEDI = False

MAX_COMPLETIONS = 200
_DOC_LINES = 14
_DOC_WIDTH = 78


def format_doc(head: str, doc: str) -> str:
    """Kopfzeile (Signatur oder Name) plus gekürzter Docstring für den Tooltip."""
    out = [head.strip()] if head.strip() else []
    lines: list[str] = []
    for para in (doc or "").strip().splitlines():
        para = para.rstrip()
        lines.extend(textwrap.wrap(para, _DOC_WIDTH) or [""])
    if lines:
        if out:
            out.append("")
        if len(lines) > _DOC_LINES:
            lines = lines[:_DOC_LINES] + ["…"]
        out.extend(lines)
    return "\n".join(out)


class JediCompleter(QObject):
    """Berechnet Vervollständigungen, Signaturen und Hilfetexte in EINEM Daemon-Worker.

    Frühere Version: pro Tastendruck wurde ein neuer Thread gestartet. Bei
    schnellem Tippen liefen dadurch viele teure ``jedi.complete()``-Aufrufe
    gleichzeitig (CPU-Spitzen). Jetzt gibt es genau einen Worker mit einem
    "latest wins"-Slot je Art der Anfrage: Nur die jeweils neueste wird
    berechnet, veraltete werden verworfen, bevor (und nachdem) gerechnet wird.

    Der erste jedi-Aufruf ist langsam (Typeshed, builtins); deshalb wärmt der
    Worker beim Start einmal vor. Das ``jedi.Project`` wird je Pfadliste
    wiederverwendet statt bei jeder Anfrage neu gebaut.
    """

    completions_ready = pyqtSignal(list)   # list of (name: str, type: str)
    signature_ready = pyqtSignal(str)      # Signatur + Docstring beim Tippen von „(“
    help_ready = pyqtSignal(int, str)      # (Position, Hilfetext) für die Maus-Hilfe

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cond = threading.Condition()
        self._pending: dict[str, tuple] = {}     # Art -> neueste Anfrage
        self._seq = {"complete": 0, "signature": 0, "help": 0}
        self._extra_paths: list[str] = []
        self._projects: dict[tuple, object] = {}
        self._worker_started = False
        self._worker = threading.Thread(target=self._loop, daemon=True)

    def set_extra_paths(self, paths: list[str]):
        """Zusätzliche sys.path-Einträge für jedi (z. B. MicroPython-Stubs)."""
        self._extra_paths = list(paths)

    def warm_up(self):
        """Ersten (langsamen) jedi-Aufruf schon vor dem ersten Tastendruck erledigen."""
        if not HAS_JEDI:
            return
        with self._cond:
            self._pending["warm"] = ()
            self._start_worker()
            self._cond.notify()

    def _start_worker(self):
        if not self._worker_started:
            self._worker_started = True
            self._worker.start()

    def _post(self, kind: str, source: str, line: int, col: int, path: str | None, extra=None):
        if not HAS_JEDI:
            return
        with self._cond:
            self._seq[kind] += 1
            self._pending[kind] = (source, line + 1, col, path, list(self._extra_paths),
                                   self._seq[kind], extra)
            self._start_worker()
            self._cond.notify()

    def request(self, source: str, line: int, col: int, path: str | None = None):
        """Vervollständigung. line/col sind 0-basiert (wie QScintilla)."""
        self._post("complete", source, line, col, path)

    def request_signature(self, source: str, line: int, col: int, path: str | None = None):
        self._post("signature", source, line, col, path)

    def request_help(self, source: str, line: int, col: int, pos: int, path: str | None = None):
        """Docstring zum Namen an der Mausposition; ``pos`` kommt mit der Antwort zurück."""
        self._post("help", source, line, col, path, extra=pos)

    # ── Worker ────────────────────────────────────────────────────────────
    def _script(self, source, path, extra_paths):
        key = tuple(extra_paths)
        project = self._projects.get(key)
        if project is None:
            kwargs = {"added_sys_path": extra_paths} if extra_paths else {}
            project = self._projects[key] = jedi.Project(".", **kwargs)
        kwargs = {"project": project}
        if path:
            kwargs["path"] = path
        return jedi.Script(source, **kwargs)

    def _loop(self):
        while True:
            with self._cond:
                while not self._pending:
                    self._cond.wait()
                # Reihenfolge: zuerst, was der Nutzer gerade sieht
                kind = next(k for k in ("complete", "signature", "help", "warm") if k in self._pending)
                args = self._pending.pop(kind)
            try:
                if kind == "warm":
                    self._script("import os\nos.pa", None, []).complete(2, 5)
                    continue
                source, line, col, path, extra_paths, seq, extra = args
                script = self._script(source, path, extra_paths)
                if kind == "complete":
                    result = [(c.name, c.type) for c in script.complete(line, col)[:MAX_COMPLETIONS]]
                elif kind == "signature":
                    result = self._signature_text(script, line, col)
                else:
                    result = self._help_text(script, line, col)
            except Exception:
                if kind == "warm":
                    continue   # Aufwärmen fehlgeschlagen – ohne seq/extra unten nicht weitergehen
                result = [] if kind == "complete" else ""

            # Während der Berechnung kam evtl. eine neuere Anfrage → verwerfen
            with self._cond:
                if seq != self._seq[kind]:
                    continue
            if kind == "complete":
                self.completions_ready.emit(result)
            elif kind == "signature":
                if result:
                    self.signature_ready.emit(result)
            elif result:
                self.help_ready.emit(extra, result)

    @staticmethod
    def _signature_text(script, line: int, col: int) -> str:
        sigs = script.get_signatures(line, col)
        if not sigs:
            return ""
        sig = sigs[0]
        try:
            doc = sig.docstring(raw=True)
        except Exception:
            doc = ""
        # Docstring beginnt oft selbst mit der Signatur – dann nicht doppelt zeigen
        head = sig.to_string()
        first = doc.strip().splitlines()[0] if doc.strip() else ""
        if first.replace(" ", "").startswith(head.replace(" ", "")[:20]):
            doc = "\n".join(doc.strip().splitlines()[1:])
        return format_doc(head, doc)

    @staticmethod
    def _help_text(script, line: int, col: int) -> str:
        names = script.help(line, col)
        if not names:
            return ""
        n = names[0]
        try:
            doc = n.docstring(raw=True)
        except Exception:
            doc = ""
        head = ""
        try:
            sigs = n.get_signatures()
            head = sigs[0].to_string() if sigs else ""
            head = (n.name + head) if head.startswith("(") else (head or n.full_name or n.name)
        except Exception:
            head = n.name
        if not doc.strip():
            return ""
        return format_doc(head, doc)
