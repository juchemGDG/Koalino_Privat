"""Debug-Runner für Koalino (lokales Python): führt ein Programm unter ``bdb`` aus.

Aufruf:  python -u debug_runner.py <port> <programm.py>

Der Runner verbindet sich mit Koalino über einen lokalen Socket (JSON, eine Nachricht
pro Zeile) und hält das Programm an Haltepunkten und bei Einzelschritten an. Ein-/
Ausgabe des Programms (print, input) laufen unverändert über stdin/stdout/stderr –
deshalb gibt es einen eigenen Kanal.

Nachrichten von Koalino:
  {"cmd": "init", "breakpoints": [3, 7], "watches": ["x + 1"], "step": false}
  {"cmd": "breakpoints", "lines": [...]}       jederzeit, auch während der Lauf läuft
  {"cmd": "watches", "exprs": [...]}           jederzeit
  {"cmd": "continue" | "next" | "step" | "out" | "stop"}
  {"cmd": "select", "index": n}                Stapelebene n zeigen (0 = innerste)

Nachrichten an Koalino:
  {"event": "paused", "reason": "stop"|"select", "line": n, "stack": [...], "index": n, "scopes": [...],
   "watches": [...]}
  {"event": "exit"}

Nur Standardbibliothek, damit es mit jeder Python-Runtime läuft.
"""
import bdb
import json
import os
import queue
import socket
import sys
import threading
import traceback
import types

_MAX_REPR = 200
_HIDDEN_TYPES = (types.ModuleType, types.FunctionType, types.BuiltinFunctionType,
                 types.MethodType, type)


def _short_repr(value) -> str:
    try:
        text = repr(value)
    except Exception as e:      # __repr__ des Schülers kann selbst Fehler enthalten
        return f"<repr-Fehler: {e.__class__.__name__}>"
    if len(text) > _MAX_REPR:
        text = text[:_MAX_REPR] + " …"
    return text


def _scope(name: str, namespace: dict) -> dict:
    items = []
    for key, value in list(namespace.items()):
        if key.startswith("__") or isinstance(value, _HIDDEN_TYPES):
            continue
        items.append({"name": key, "type": type(value).__name__, "value": _short_repr(value)})
    return {"name": name, "vars": items}


class _Channel:
    """Socket mit Zeilenprotokoll; ein Lese-Thread legt Befehle in eine Warteschlange."""

    def __init__(self, port: int):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=10)
        self.sock.settimeout(None)
        self.commands: "queue.Queue[dict]" = queue.Queue()
        self._lock = threading.Lock()
        self.on_async = None     # Callback für breakpoints/watches (jederzeit)
        threading.Thread(target=self._reader, daemon=True).start()

    def send(self, msg: dict) -> None:
        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        with self._lock:
            try:
                self.sock.sendall(data)
            except OSError:
                pass

    def _reader(self) -> None:
        buf = b""
        try:
            while True:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line.decode("utf-8"))
                    if msg.get("cmd") in ("breakpoints", "watches") and self.on_async:
                        self.on_async(msg)
                    else:
                        self.commands.put(msg)
        except (OSError, ValueError):
            pass
        self.commands.put({"cmd": "stop"})     # Koalino weg → Programm beenden


class Runner(bdb.Bdb):
    def __init__(self, script: str, channel: _Channel):
        super().__init__()
        self.script = os.path.abspath(script)
        self.ch = channel
        self.watches: list = []
        self.start_stepping = False
        self._first_line = True
        channel.on_async = self._on_async

    # ── Befehle, die jederzeit ankommen dürfen ─────────────────────────────
    def _on_async(self, msg: dict) -> None:
        if msg["cmd"] == "breakpoints":
            self._set_breakpoints(msg.get("lines", []))
        else:
            self.watches = list(msg.get("exprs", []))

    def _set_breakpoints(self, lines) -> None:
        self.clear_all_breaks()
        for ln in lines:
            self.set_break(self.script, int(ln))

    # ── bdb-Haken ──────────────────────────────────────────────────────────
    def _is_script(self, frame) -> bool:
        return os.path.abspath(frame.f_code.co_filename) == self.script

    def stop_here(self, frame):
        # Nur im eigenen Programm anhalten – nie in Bibliotheken oder im Runner.
        return self._is_script(frame) and super().stop_here(frame)

    def user_line(self, frame):
        if self._first_line:
            # bdb.run() beginnt immer im Einzelschritt; ohne Haltepunkt in Zeile 1
            # und ohne „Schritt für Schritt“ läuft das Programm bis zum ersten Haltepunkt.
            self._first_line = False
            if not self.start_stepping and not self.break_here(frame):
                self.set_continue()
                return
        self._pause(frame)

    def user_return(self, frame, return_value):
        pass

    def user_exception(self, frame, exc_info):
        pass

    # ── Anhalten und auf Befehle warten ────────────────────────────────────
    def _stack(self, frame) -> list:
        frames = []
        while frame is not None:
            if self._is_script(frame):
                frames.append(frame)
            frame = frame.f_back
        return frames

    def _state(self, frames: list, index: int, reason: str) -> dict:
        frame = frames[index]
        is_module = frame.f_locals is frame.f_globals
        scopes = [_scope("Globale Variablen" if is_module else "Lokale Variablen",
                         frame.f_globals if is_module else frame.f_locals)]
        if not is_module:
            scopes.append(_scope("Globale Variablen", frame.f_globals))
        watches = []
        for expr in self.watches:
            try:
                value = eval(expr, frame.f_globals, frame.f_locals)   # noqa: S307
                watches.append({"expr": expr, "type": type(value).__name__,
                                "value": _short_repr(value)})
            except Exception as e:
                watches.append({"expr": expr, "error": f"{e.__class__.__name__}: {e}"})
        return {
            "event": "paused",
            "reason": reason,      # "stop" = neu angehalten, "select" = andere Stapelebene
            "line": frame.f_lineno,
            "index": index,
            "stack": [{"name": f.f_code.co_name, "line": f.f_lineno} for f in frames],
            "scopes": scopes,
            "watches": watches,
        }

    def _pause(self, frame) -> None:
        frames = self._stack(frame)
        if not frames:
            return
        self.ch.send(self._state(frames, 0, "stop"))
        while True:
            msg = self.ch.commands.get()
            cmd = msg.get("cmd")
            if cmd == "select":
                idx = max(0, min(int(msg.get("index", 0)), len(frames) - 1))
                self.ch.send(self._state(frames, idx, "select"))
            elif cmd == "continue":
                self.set_continue()
                return
            elif cmd == "step":
                self.set_step()
                return
            elif cmd == "next":
                self.set_next(frame)
                return
            elif cmd == "out":
                self.set_return(frame)
                return
            elif cmd == "stop":
                self.set_quit()
                os._exit(1)


def _print_error(script: str) -> None:
    """Traceback ohne die Runner-Zeilen – so sieht er aus wie bei normalem Lauf."""
    etype, value, tb = sys.exc_info()
    while tb is not None and os.path.abspath(tb.tb_frame.f_code.co_filename) != script:
        tb = tb.tb_next
    sys.stdout.flush()
    traceback.print_exception(etype, value, tb)


def main() -> int:
    if len(sys.argv) < 3:
        print("Aufruf: debug_runner.py <port> <programm.py>", file=sys.stderr)
        return 2
    port, script = int(sys.argv[1]), os.path.abspath(sys.argv[2])
    channel = _Channel(port)
    runner = Runner(script, channel)

    init = channel.commands.get()
    runner.watches = list(init.get("watches", []))
    runner._set_breakpoints(init.get("breakpoints", []))

    with open(script, "rb") as f:
        source = f.read()
    code = compile(source, script, "exec")
    namespace = {"__name__": "__main__", "__file__": script, "__builtins__": __builtins__,
                 "__doc__": None, "__package__": None, "__spec__": None}
    sys.argv = [script] + sys.argv[3:]
    sys.path.insert(0, os.path.dirname(script))

    runner.start_stepping = bool(init.get("step"))
    rc = 0
    try:
        runner.run(code, namespace)
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
    except BaseException:
        _print_error(script)
        rc = 1
    sys.stdout.flush()
    channel.send({"event": "exit"})
    return rc


if __name__ == "__main__":
    sys.exit(main())
