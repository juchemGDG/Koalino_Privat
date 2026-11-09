"""Konsolenbereich: Programmausgaben + Fehler-Links."""
import re
import subprocess
import threading

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLineEdit, QPushButton, QLabel, QTabWidget,
)

from .config import THEME, mono_family


# ──────────────────────────────────────────────────────────────────────────────
# Signal-Brücke für Thread-sichere Ausgaben
# ──────────────────────────────────────────────────────────────────────────────
class _OutputBridge(QObject):
    append_text = pyqtSignal(str, str)   # (text, style)  style ∈ stdout|stderr|info|error


class ProcessRunner(QThread):
    """Führt einen Subprozess aus und leitet stdout/stderr weiter."""
    output = pyqtSignal(str, str)   # (text, kind)
    finished_run = pyqtSignal(int)  # return-code

    def __init__(self, cmd: list, cwd: str | None = None, env=None):
        super().__init__()
        self.cmd = cmd
        self.cwd = cwd
        self.env = env
        self._proc = None

    def send_input(self, text: str):
        """Sendet Text an stdin des laufenden Prozesses (binärer Stream)."""
        if self._proc and self._proc.poll() is None and self._proc.stdin:
            try:
                self._proc.stdin.write((text + "\n").encode("utf-8"))
                self._proc.stdin.flush()
            except Exception:
                pass

    def run(self):
        import codecs
        try:
            self._proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                cwd=self.cwd,
                env=self.env,
                bufsize=0,   # unbuffered – damit input()-Prompts sofort erscheinen
            )
            # Stdout und Stderr parallel in größeren Chunks lesen. Ein
            # inkrementeller UTF-8-Decoder verhindert, dass Mehrbyte-Zeichen
            # (Umlaute, ², €, Emojis) an Chunk-Grenzen zerschnitten werden.
            def read_stream(stream, kind):
                decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
                try:
                    while True:
                        chunk = stream.read(65536)
                        if not chunk:
                            break
                        text = decoder.decode(chunk)
                        if text:
                            self.output.emit(text, kind)
                    rest = decoder.decode(b"", final=True)
                    if rest:
                        self.output.emit(rest, kind)
                except (OSError, ValueError):
                    pass   # Pipe wurde geschlossen / Prozess beendet
                finally:
                    try:
                        stream.close()
                    except Exception:
                        pass

            # Daemon-Threads: blockieren das Programmende nicht, falls eine vom
            # Schülerprogramm gestartete Subprozess-/Thread-Instanz das Pipe-Ende
            # offen hält.
            t_out = threading.Thread(target=read_stream, args=(self._proc.stdout, "stdout"), daemon=True)
            t_err = threading.Thread(target=read_stream, args=(self._proc.stderr, "stderr"), daemon=True)
            t_out.start()
            t_err.start()
            # Auf den ECHTEN Prozess-Exit warten (nicht auf Pipe-EOF). So wird
            # 'Programm beendet' auch dann gemeldet, wenn ein geerbtes Pipe-Ende
            # in einem Kindprozess offen bleibt – sonst „hängt“ die Ausführung.
            rc = self._proc.wait()
            # Restausgabe (z. B. Traceback) noch einsammeln, aber nicht ewig warten.
            t_out.join(timeout=1.5)
            t_err.join(timeout=1.5)
            self.finished_run.emit(rc)
        except Exception as e:
            self.output.emit(f"Fehler beim Starten: {e}\n", "stderr")
            self.finished_run.emit(-1)

    def terminate_process(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()


# ──────────────────────────────────────────────────────────────────────────────
# MicroPython-Runner: interaktiver Raw-REPL via pyserial
# ──────────────────────────────────────────────────────────────────────────────
class MicroPythonRunner(QThread):
    """Führt ein MicroPython-Skript über Raw-REPL (pyserial) aus.
    Unterstützt bidirektionales stdin/stdout – input() funktioniert.
    """
    output       = pyqtSignal(str, str)   # (text, kind)
    finished_run = pyqtSignal(int)

    def __init__(self, port: str, script_path: str):
        super().__init__()
        self._port        = port
        self._script_path = script_path
        self._serial      = None
        self._abort       = False

    def send_input(self, text: str):
        """Schickt Benutzereingabe an den Controller."""
        if self._serial and self._serial.is_open:
            try:
                self._serial.write((text + "\r\n").encode("utf-8"))
            except Exception:
                pass

    def terminate_process(self):
        """Unterbricht laufendes Programm sicher (doppeltes Ctrl+C + Raw-REPL-Exit)."""
        self._abort = True
        if self._serial and self._serial.is_open:
            try:
                # Doppeltes Ctrl+C: unterbricht auch Endlosschleifen zuverlässig
                self._serial.write(b"\x03\x03")
            except Exception:
                pass

    def run(self):
        import serial
        try:
            ser = serial.Serial(self._port, 115200, timeout=0.1)
            self._serial = ser

            # Skript einlesen und an das Board übertragen. Der Handshake wird
            # mehrfach versucht, weil viele Boards (v. a. ESP32) beim Öffnen des
            # seriellen Ports über die DTR/RTS-Leitungen automatisch neu booten.
            # Beim ersten Versuch ist das Board dann noch im Hochfahren und
            # bestätigt den Programmstart nicht – ein erneuter Versuch nach einer
            # kurzen Wartezeit fängt das zuverlässig ab.
            with open(self._script_path, "rb") as f:
                code = f.read()
            if not self._handshake_and_send(ser, code):
                if not self._abort:
                    self.output.emit(
                        "⚠  Der Controller hat den Programmstart nicht bestätigt.\n"
                        "   Bitte Controller über '↻' neu verbinden oder kurz "
                        "aus- und wieder einstecken und erneut starten.\n",
                        "stderr",
                    )
                self.finished_run.emit(1)
                ser.close()
                return

            # Ausgabe lesen. Das Board sendet im Raw-REPL:
            #   OK <stdout> \x04 <stderr/Traceback> \x04
            # Das erste \x04 trennt Programmausgabe von der Fehlermeldung, das
            # zweite \x04 schließt sie ab und beendet damit den Lauf.
            import time as _time
            stdout_done  = False
            stderr_buf   = b""
            rc           = 0
            err_deadline = None   # Sicherheits-Timeout für die Fehlerphase

            while not self._abort:
                # Wird der Controller während des Laufs abgezogen, meldet
                # pyserial entweder einen Fehler oder der Port ist geschlossen –
                # dann sauber abbrechen statt endlos auf Daten zu warten.
                if not ser.is_open:
                    self.output.emit(
                        "\n⚠  Verbindung zum Controller verloren "
                        "(abgezogen?).\n", "stderr")
                    rc = 1
                    break
                try:
                    chunk = ser.read(256)
                except (OSError, serial.SerialException) as exc:
                    self.output.emit(
                        f"\n⚠  Verbindung zum Controller unterbrochen: {exc}\n",
                        "stderr")
                    rc = 1
                    break

                if not chunk:
                    # Nach Programmende (erstes \x04) folgt die Fehlerausgabe
                    # praktisch sofort. Bleibt das abschließende \x04 aus (z. B.
                    # Board hat sich neu gestartet), nicht endlos warten, sondern
                    # den bereits empfangenen Text ausgeben und beenden.
                    if err_deadline is not None and _time.time() > err_deadline:
                        rest = stderr_buf.decode("utf-8", errors="replace").strip()
                        if rest and "KeyboardInterrupt" not in rest:
                            self.output.emit(rest + "\n", "stderr")
                            rc = 1
                        break
                    continue

                if not stdout_done:
                    if b"\x04" in chunk:
                        i    = chunk.index(b"\x04")
                        head = chunk[:i]
                        if head:
                            self.output.emit(head.decode("utf-8", errors="replace"), "stdout")
                        stdout_done  = True
                        stderr_buf   = chunk[i + 1:]
                        err_deadline = _time.time() + 3.0
                    else:
                        self.output.emit(chunk.decode("utf-8", errors="replace"), "stdout")
                        continue
                else:
                    stderr_buf += chunk

                # Gemeinsame Prüfung auf das abschließende \x04 – auch wenn das
                # erste und zweite \x04 im selben Lesepuffer ankommen (häufig bei
                # schnellen Laufzeitfehlern mit wenig Ausgabe). Genau hier hing
                # das Programm bisher: die fertige Fehlermeldung wurde nie geprüft.
                if b"\x04" in stderr_buf:
                    i   = stderr_buf.index(b"\x04")
                    err = stderr_buf[:i].decode("utf-8", errors="replace").strip()
                    if err and "KeyboardInterrupt" not in err:
                        self.output.emit(err + "\n", "stderr")
                        rc = 1
                    break

            try:
                ser.write(b"\x02")   # Zurück in normalen REPL (Ctrl+B)
            except Exception:
                pass
            ser.close()
            self.finished_run.emit(rc)

        except Exception as exc:
            self.output.emit(f"⚠  Verbindungsfehler: {exc}\n", "stderr")
            self._emit_permission_hint(exc)
            self.finished_run.emit(1)

    def _emit_permission_hint(self, exc) -> None:
        """Bei fehlender Port-Berechtigung unter Linux einen Lösungs-Hinweis zeigen.

        Serielle Ports gehören dort der Gruppe ``dialout``; ist der Benutzer nicht
        Mitglied, scheitert das Öffnen mit ``[Errno 13] Permission denied``. Die
        Original-Meldung von pyserial ist für Schülerinnen und Schüler wenig
        hilfreich – darum hier der konkrete Behebungs-Schritt.
        """
        import errno
        import sys

        if not sys.platform.startswith("linux"):
            return
        is_permission = (
            getattr(exc, "errno", None) == errno.EACCES
            or "Errno 13" in str(exc)
            or "Permission denied" in str(exc)
        )
        if not is_permission:
            return
        self.output.emit(
            "   → Keine Berechtigung für den seriellen Port. Unter Linux muss der\n"
            "     eigene Benutzer einmalig zur Gruppe 'dialout' hinzugefügt werden:\n"
            "         sudo usermod -a -G dialout $USER\n"
            "     Danach ab- und wieder anmelden (oder neu starten).\n",
            "stderr",
        )

    def _handshake_and_send(self, ser, code: bytes, attempts: int = 3) -> bool:
        """Geht in den Raw-REPL und überträgt das Skript zur Ausführung.

        Gibt ``True`` zurück, sobald das Board den Start mit ``OK`` bestätigt.
        Der komplette Ablauf – laufendes Programm bzw. Boot unterbrechen →
        Raw-REPL aktivieren → Skript senden → ``OK`` abwarten – wird bis zu
        ``attempts``-mal wiederholt: Öffnet sich der serielle Port, lösen viele
        Boards (ESP32 u. a.) über DTR/RTS einen Auto-Reset aus und sind beim
        ersten Versuch noch im Boot. Zwischen den Versuchen bekommt das Board
        kurz Zeit zum Hochfahren.
        """
        import time as _t
        for _ in range(attempts):
            if self._abort:
                return False

            # 1) Laufendes Programm / Boot-Vorgang unterbrechen (doppeltes Ctrl+C)
            ser.write(b"\x03\x03")
            _t.sleep(0.3)
            ser.reset_input_buffer()

            # 2) Raw-REPL aktivieren (Ctrl+A) und auf den '>'-Prompt warten
            ser.write(b"\x01")
            if not self._read_until(ser, b">", timeout=2.5):
                _t.sleep(0.5)   # Board vermutlich noch am Booten → erneut versuchen
                continue

            # 3) Skript übertragen + ausführen (Ctrl+D)
            ser.write(code + b"\x04")

            # 4) Auf "OK" warten. Genau 2 Bytes lesen, um keine Programmausgabe
            #    zu verschlucken; bis zu 4 s, da große Skripte (mehrere
            #    NIT-Bibliotheken) spürbar länger brauchen als ein read().
            ok       = b""
            deadline = _t.time() + 4.0
            while len(ok) < 2 and _t.time() < deadline:
                ok += ser.read(2 - len(ok))
            if ok == b"OK":
                return True

            # Keine Bestätigung – evtl. angefangene Übertragung abbrechen und
            # den gesamten Handshake erneut versuchen.
            ser.write(b"\x03\x03")
            _t.sleep(0.3)

        return False

    @staticmethod
    def _read_until(ser, needle: bytes, timeout: float) -> bool:
        import time as _t
        buf      = b""
        deadline = _t.time() + timeout
        while _t.time() < deadline:
            data = ser.read(64)
            if data:
                buf += data
                if needle in buf:
                    return True
        return False
# ──────────────────────────────────────────────────────────────────────────────
_ERROR_PATTERN = re.compile(
    r'File "(?P<file>[^"]+)", line (?P<line>\d+)'
)


class OutputConsole(QTextEdit):
    """Zeigt Programmausgaben an. Fehler-Links klickbar (rot, unterstrichen)."""

    error_link_clicked = pyqtSignal(str, int)   # (dateipfad, zeilennummer)
    action_link_clicked = pyqtSignal(str)       # Aktions-Link (siehe append_action_link)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("JetBrains Mono, Fira Code, Consolas, monospace", 11))
        self.setStyleSheet(
            f"background:{THEME['terminal_bg']}; color:{THEME['terminal_text']};"
            f" border:none; padding:4px;"
        )
        self._links: dict[str, tuple[str, int]] = {}   # anchor → (file, line)

    def append_output(self, text: str):
        """Normale Ausgabe (weiß)."""
        self._append_colored(text, THEME["terminal_text"])

    def append_error(self, text: str):
        """Fehlerausgabe: Traceback-Zeilen werden als klickbare Links dargestellt."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        for line in text.splitlines(keepends=True):
            m = _ERROR_PATTERN.search(line)
            if m:
                filepath = m.group("file")
                lineno = int(m.group("line"))
                anchor = f"err_{filepath}_{lineno}"
                self._links[anchor] = (filepath, lineno)

                # Zeile vor dem Match normal ausgeben
                pre = line[:m.start()]
                if pre:
                    fmt = QTextCharFormat()
                    fmt.setForeground(QColor(THEME["error"]))
                    cursor.insertText(pre, fmt)

                # Match als klickbaren Link
                fmt_link = QTextCharFormat()
                fmt_link.setForeground(QColor(THEME["error"]))
                fmt_link.setFontUnderline(True)
                fmt_link.setAnchor(True)
                fmt_link.setAnchorHref(anchor)
                cursor.insertText(m.group(0), fmt_link)

                # Rest der Zeile
                post = line[m.end():]
                if post:
                    fmt2 = QTextCharFormat()
                    fmt2.setForeground(QColor(THEME["error"]))
                    cursor.insertText(post, fmt2)
            else:
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(THEME["error"]))
                cursor.insertText(line, fmt)

        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def append_info(self, text: str):
        self._append_colored(text, THEME["info"])

    def append_success(self, text: str):
        self._append_colored(text, THEME["success"])

    def _append_colored(self, text: str, color: str):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text, fmt)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def refresh_theme(self):
        self.setStyleSheet(
            f"background:{THEME['terminal_bg']}; color:{THEME['terminal_text']};"
            f" border:none; padding:4px;"
        )

    def clear_output(self):
        self.clear()
        self._links.clear()

    def append_action_link(self, label: str, action: str, color: str | None = None):
        """Klickbarer Text in der Ausgabe (z. B. „Stufe 2: Welche Karte?“).
        Ein Klick sendet ``action_link_clicked(action)``."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color or THEME["accent"]))
        fmt.setFontUnderline(True)
        fmt.setAnchor(True)
        fmt.setAnchorHref(f"act:{action}")
        cursor.insertText(label, fmt)
        cursor.insertText("   ", QTextCharFormat())
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        anchor = self.anchorAt(event.pos())
        if anchor.startswith("act:"):
            self.action_link_clicked.emit(anchor[4:])
        elif anchor and anchor in self._links:
            filepath, lineno = self._links[anchor]
            self.error_link_clicked.emit(filepath, lineno)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        # Handcursor über Links, damit sie als klickbar erkennbar sind
        shape = (Qt.CursorShape.PointingHandCursor if self.anchorAt(event.pos())
                 else Qt.CursorShape.IBeamCursor)
        self.viewport().setCursor(shape)


# ──────────────────────────────────────────────────────────────────────────────
# Kombiniertes Konsolenpanel
# ──────────────────────────────────────────────────────────────────────────────
class ConsolePanel(QWidget):
    """Konsolenpanel mit Tabs: Ausgabe (+ Serial Plotter bei Bedarf)."""

    error_link_clicked = pyqtSignal(str, int)
    action_requested   = pyqtSignal(str)   # Aktions-Link in der Ausgabe geklickt

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_runner: ProcessRunner | None = None
        # Gepufferte Programmausgabe: viele kleine print()-Chunks werden
        # gesammelt und nur alle 40 ms gebündelt eingefügt. Das verhindert,
        # dass der GUI-Thread bei ausgabeintensiven Programmen (Schleifen mit
        # vielen print()) durch zehntausende Einzel-Updates einfriert.
        self._pending: list[tuple[str, str]] = []   # (text, kind) kind ∈ out|err
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(40)
        self._flush_timer.timeout.connect(self._flush_pending)
        # Serial Plotter (nur bei Bedarf eingeblendet, siehe set_plotter_visible).
        self._plot = None
        self._plot_active = False
        self._plot_config: dict | None = None   # Achsen-Standardwerte aus den Einstellungen
        self._setup_ui()

    @staticmethod
    def _tabs_style() -> str:
        """Stylesheet der Konsolen-Tabs (aus dem aktuellen THEME)."""
        return f"""
            QTabWidget::pane {{
                border: none;
                background: {THEME['terminal_bg']};
            }}
            QTabBar {{
                background: {THEME['bg_dark']};
            }}
            QTabBar::tab {{
                background: transparent;
                color: {THEME['text_dim']};
                padding: 6px 16px;
                margin: 3px 2px 0 2px;
                border: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
            QTabBar::tab:hover:!selected {{
                background: {THEME['selection']};
                color: {THEME['text']};
            }}
            QTabBar::tab:selected {{
                background: {THEME['terminal_bg']};
                color: {THEME['text']};
                font-weight: bold;
                border-bottom: 2px solid {THEME['accent']};
            }}
            """

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(self._tabs_style())

        # Tab 1: Ausgabe
        output_container = QWidget()
        oc_layout = QVBoxLayout(output_container)
        oc_layout.setContentsMargins(0, 0, 0, 0)
        oc_layout.setSpacing(0)
        self.output_console = OutputConsole()
        self.output_console.error_link_clicked.connect(self.error_link_clicked)
        self.output_console.action_link_clicked.connect(self.action_requested)
        oc_layout.addWidget(self.output_console)

        # Eingabezeile für laufende Programme (input()-Unterstützung)
        self._input_bar = QWidget()
        self._input_bar.setVisible(False)
        inp_row = QHBoxLayout(self._input_bar)
        inp_row.setContentsMargins(4, 2, 4, 4)
        inp_row.setSpacing(4)
        self._input_prompt = QLabel("➜")
        self._input_prompt.setStyleSheet(
            f"color:{THEME['accent']}; font-family:monospace; font-size:13px;"
        )
        inp_row.addWidget(self._input_prompt)
        self._input_field = QLineEdit()
        self._input_field.setPlaceholderText("Eingabe hier tippen und Enter drücken …")
        self._input_field.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f" border:1px solid {THEME['accent']}; border-radius:4px; padding:3px 6px;"
            f" font-family:'JetBrains Mono', Consolas, monospace; font-size:11px;"
        )
        self._input_field.returnPressed.connect(self._send_input)
        inp_row.addWidget(self._input_field)
        oc_layout.addWidget(self._input_bar)

        self.tabs.addTab(output_container, "Ausgabe")

        layout.addWidget(self.tabs)

    def refresh_theme(self):
        self.tabs.setStyleSheet(self._tabs_style())
        self._input_prompt.setStyleSheet(
            f"color:{THEME['accent']}; font-family:monospace; font-size:13px;"
        )
        self._input_field.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f" border:1px solid {THEME['accent']}; border-radius:4px; padding:3px 6px;"
            f" font-family:'JetBrains Mono', Consolas, monospace; font-size:11px;"
        )
        self.output_console.refresh_theme()
        if self._plot is not None:
            self._plot.refresh_theme()

    def _send_input(self):
        text = self._input_field.text()
        self._input_field.clear()
        # Eingabe im Ausgabefeld anzeigen (Echo)
        self.output_console.append_info(f"➜ {text}\n")
        if self._active_runner:
            self._active_runner.send_input(text)

    def set_active_runner(self, runner: ProcessRunner | None):
        """Verbindet Eingabezeile mit dem aktuell laufenden Prozess."""
        self._active_runner = runner
        self._input_bar.setVisible(runner is not None)
        if runner is not None:
            self.tabs.setCurrentIndex(0)
            self._input_field.setFocus()

    # ── Gepufferte Programmausgabe (hohe Frequenz) ──────────────────────────
    def append_program_output(self, text: str):
        """stdout eines laufenden Programms – gepuffert/gebündelt."""
        if self._plot_active and self._plot is not None:
            self._plot.feed(text)
        self._enqueue(text, "out")

    def append_program_error(self, text: str):
        """stderr eines laufenden Programms – gepuffert/gebündelt."""
        self._enqueue(text, "err")

    def _enqueue(self, text: str, kind: str):
        self._pending.append((text, kind))
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _flush_pending(self):
        if not self._pending:
            self._flush_timer.stop()
            return
        pending = self._pending
        self._pending = []
        # stdout und stderr kommen über zwei getrennte Pipes/Threads und damit in
        # nicht garantierter Reihenfolge an (Race Condition – ein Traceback konnte
        # so VOR der zugehörigen Programmausgabe erscheinen). Innerhalb eines
        # Flush-Fensters geben wir deshalb erst die normale Ausgabe, dann die
        # Fehlerausgabe aus. Für den häufigsten Fall (Programm gibt etwas aus und
        # stürzt am Ende ab) ist die Reihenfolge damit immer korrekt.
        out_text = "".join(text for text, kind in pending if kind != "err")
        err_text = "".join(text for text, kind in pending if kind == "err")
        if out_text:
            self.output_console.append_output(out_text)
        if err_text:
            self.output_console.append_error(err_text)
        self._focus_output_tab()

    def _focus_output_tab(self):
        """Schaltet auf den Ausgabe-Tab – außer der Plotter ist gerade aktiv.

        So reißt neue Programmausgabe den Lernenden nicht aus dem Live-Graph.
        """
        if self._plot_active and self.tabs.currentWidget() is self._plot:
            return
        self.tabs.setCurrentIndex(0)

    def flush_now(self):
        """Restpuffer sofort ausgeben (z. B. bevor 'Programm beendet' erscheint)."""
        self._flush_pending()

    # Delegations-Methoden
    def append_output(self, text: str):
        self.output_console.append_output(text)
        self._focus_output_tab()

    def append_error(self, text: str):
        self.output_console.append_error(text)
        self._focus_output_tab()

    def append_info(self, text: str):
        self.output_console.append_info(text)

    def append_success(self, text: str):
        self.output_console.append_success(text)

    def append_hint(self, text: str):
        """Verständlicher Klartext-Hinweis zu einem Fehler (eigene Info-Farbe)."""
        self.output_console.append_info("\n" + text)
        self._focus_output_tab()

    def append_action_link(self, label: str, action: str, color: str | None = None):
        self.output_console.append_action_link(label, action, color)

    def append_warning(self, text: str):
        """Abgesetzter Warnkasten (Schritt 0) in Fehlerfarbe."""
        self.output_console._append_colored(text, THEME["error"])
        self._focus_output_tab()

    def set_plot_defaults(self, config: dict):
        """Achsen-Standardwerte des Plotters setzen (aus den Einstellungen)."""
        self._plot_config = dict(config)
        if self._plot is not None:
            self._plot.apply_config(**config)

    def clear_output(self):
        self.output_console.clear_output()
        if self._plot is not None:
            self._plot.clear()   # bei jedem Programmstart frischer Graph

    def set_plotter_visible(self, visible: bool):
        """Blendet den Serial-Plotter-Tab bei Bedarf ein bzw. wieder aus.

        Solange er aus ist, fällt keinerlei Parsing-Aufwand an (siehe
        :meth:`append_program_output`). Die Plot-Instanz bleibt erhalten, sodass
        beim erneuten Einblenden die bisherigen Kurven nicht verloren gehen.
        """
        if visible:
            if self._plot is None:
                from .serial_plot import SerialPlot
                self._plot = SerialPlot()
                if self._plot_config:
                    self._plot.apply_config(**self._plot_config)
            if self.tabs.indexOf(self._plot) == -1:
                self.tabs.addTab(self._plot, "📈 Plotter")
            self._plot_active = True
            self.tabs.setCurrentWidget(self._plot)
        else:
            self._plot_active = False
            if self._plot is not None:
                idx = self.tabs.indexOf(self._plot)
                if idx != -1:
                    self.tabs.removeTab(idx)

    def set_font_size(self, size: int):
        """Schriftgröße der Konsole ändern."""
        font = QFont(mono_family(), size)
        self.output_console.setFont(font)   # OutputConsole ist selbst das QTextEdit

    def set_scrollback_limit(self, lines: int):
        """Maximale Zeilenzahl im Ausgabepuffer setzen."""
        self.output_console.document().setMaximumBlockCount(lines)
