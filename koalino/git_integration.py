"""Git-Integration von Koalino: Dialoge (Klonen, Konflikte) und Git-Aktionen des Hauptfensters.

``GitIntegrationMixin`` wird von ``MainWindow`` geerbt. Die Methoden greifen auf
Attribute und Hilfen des Hauptfensters zu (``_console``, ``_cfg.git_repo``,
``_cfg.sketchbook``, ``_ask_text_input`` …); das Mixin ist daher nur im
Zusammenspiel mit ``MainWindow`` lauffähig.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse, quote as urlquote

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont, QPalette
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox,
    QDialog, QPushButton, QTextEdit, QLineEdit, QFormLayout, QGroupBox,
    QListWidget, QListWidgetItem,
)

from .config import _SKETCHBOOK_MAX_DEPTH, _skip_sketchbook_dir
from .console_panel import ProcessRunner
from .net_hints import git_network_hint
from .styles import _light_dialog_controls_qss


def _git_network_env() -> dict | None:
    """Umgebung für Git-Netzwerkbefehle: System-Proxy an Git durchreichen.

    Im Schulnetz nutzt der Browser den in Windows hinterlegten Proxy
    automatisch – Git (libcurl) dagegen NICHT. Ohne Proxy-Variablen versucht
    Git eine Direktverbindung, die die Firewall blockiert ("Failed to connect
    to …:443"), obwohl die Domain am Proxy freigegeben ist.

    ``urllib.request.getproxies()`` liest unter Windows die System-Proxy-
    Einstellungen aus der Registry. Sind Proxy-Variablen bereits gesetzt
    (z. B. per Gruppenrichtlinie oder von Hand), wird nichts verändert.
    Rückgabe: komplette Umgebung mit Proxy-Variablen – oder None
    (= Umgebung unverändert erben, kein Proxy erkannt/nötig).
    """
    for key in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        if os.environ.get(key):
            return None
    try:
        import urllib.request
        proxies = urllib.request.getproxies()
    except Exception:
        return None
    http_p = proxies.get("http", "")
    https_p = proxies.get("https", "") or http_p
    if not https_p:
        return None
    # urllib meldet den Windows-Systemproxy "proxy:port" als
    # "https://proxy:port" – gemeint ist aber fast immer ein normaler
    # HTTP-Proxy (CONNECT). Mit https://-Schema würde git/curl TLS zum Proxy
    # selbst aufbauen und scheitern, daher auf http:// zurückdrehen.
    if https_p.startswith("https://"):
        stripped = https_p[len("https://"):]
        if not http_p or http_p.removeprefix("http://") == stripped:
            https_p = "http://" + stripped
    env = os.environ.copy()
    env["HTTPS_PROXY"] = https_p
    env["HTTP_PROXY"] = http_p or https_p
    no = proxies.get("no")
    if no:
        env["NO_PROXY"] = no
    return env


# ──────────────────────────────────────────────────────────────────────────────
# Git-Clone-Dialog
# ──────────────────────────────────────────────────────────────────────────────
class GitCloneDialog(QDialog):
    """Dialog zum Klonen eines Git-Repositories mit optionaler Credential-Eingabe."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Git: Repository klonen")
        self.setMinimumWidth(520)
        self._target_manually_edited = False
        self._build_ui()
        self._apply_light_style_if_needed()
        self._update_auth_section("")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(8)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://github.com/… oder git@github.com:…")
        self._url_edit.textChanged.connect(self._on_url_changed)
        form.addRow("Repository-URL:", self._url_edit)

        self._target_edit = QLineEdit()
        self._target_edit.setPlaceholderText("Ordnername im Sketchbook")
        self._target_edit.textEdited.connect(self._on_target_edited)
        form.addRow("Zielordner:", self._target_edit)

        layout.addLayout(form)

        # Anmeldedaten-Gruppe (nur bei HTTPS sichtbar)
        self._auth_group = QGroupBox("Anmeldedaten (für private Repositories)")
        auth_outer = QVBoxLayout(self._auth_group)
        auth_outer.setSpacing(8)
        auth_outer.setContentsMargins(8, 8, 8, 8)

        auth_form = QFormLayout()
        auth_form.setSpacing(8)

        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("Benutzername")
        auth_form.addRow("Benutzername:", self._username_edit)

        pw_widget = QWidget()
        pw_layout = QHBoxLayout(pw_widget)
        pw_layout.setContentsMargins(0, 0, 0, 0)
        pw_layout.setSpacing(4)
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Passwort oder Access Token")
        self._pw_toggle = QPushButton("👁")
        self._pw_toggle.setCheckable(True)
        self._pw_toggle.setFixedSize(32, 28)
        # Ohne padding:0 schneidet das Dialog-Stylesheet (padding: 6px 14px
        # für alle QPushButton) das Auge bei der festen Größe ab.
        self._pw_toggle.setStyleSheet("QPushButton { padding: 0px; }")
        self._pw_toggle.setToolTip("Passwort anzeigen / verbergen")
        self._pw_toggle.toggled.connect(
            lambda checked: self._password_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        pw_layout.addWidget(self._password_edit)
        pw_layout.addWidget(self._pw_toggle)
        auth_form.addRow("Passwort / Token:", pw_widget)

        auth_outer.addLayout(auth_form)

        # Hinweis unterhalb der Felder, volle Breite
        self._auth_hint = QLabel("")
        self._auth_hint.setWordWrap(True)
        self._auth_hint.setObjectName("hintLabel")
        auth_outer.addWidget(self._auth_hint)

        layout.addWidget(self._auth_group)

        # SSH-Hinweis (nur bei SSH-URLs sichtbar)
        self._ssh_hint = QLabel(
            "SSH-Authentifizierung: SSH-Schlüssel müssen im System eingerichtet sein "
            "(~/.ssh/id_rsa oder id_ed25519). Bei GitHub können Schlüssel unter "
            "Einstellungen → SSH and GPG keys hinzugefügt werden."
        )
        self._ssh_hint.setWordWrap(True)
        self._ssh_hint.setObjectName("hintLabel")
        self._ssh_hint.setVisible(False)
        layout.addWidget(self._ssh_hint)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)
        clone_btn = QPushButton("Klonen")
        clone_btn.setDefault(True)
        clone_btn.clicked.connect(self.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(clone_btn)
        layout.addLayout(btn_layout)

    def _apply_light_style_if_needed(self):
        app = QApplication.instance()
        if app is None:
            return
        if app.palette().color(QPalette.ColorRole.Window).lightness() < 128:
            return
        self.setStyleSheet(_light_dialog_controls_qss() + """
            QDialog, QWidget { background: #f8fafc; color: #111827; }
            QGroupBox {
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding-top: 8px;
                margin-top: 8px;
                font-weight: 600;
                color: #374151;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
            }
            QLabel { color: #374151; }
            QLabel#hintLabel { color: #6b7280; font-size: 11px; }
            QPushButton:default {
                background: #3b82f6;
                color: white;
                border-color: #2563eb;
            }
            QPushButton:default:hover { background: #2563eb; }
        """)

    @staticmethod
    def _clean_url(text: str) -> str:
        """Bereinigt versehentlich eingefügte 'git clone <url>'-Befehle zur reinen URL."""
        text = text.strip()
        # Nutzer kopieren oft den kompletten Befehl von GitHub/Doku
        import re
        text = re.sub(r"^git\s+clone\s+", "", text, flags=re.IGNORECASE).strip()
        return text

    def _on_url_changed(self, text: str):
        url = self._clean_url(text)
        if not self._target_manually_edited:
            name = os.path.basename(url.rstrip("/")).removesuffix(".git")
            if name:
                self._target_edit.setText(name)
        self._update_auth_section(url)

    def _on_target_edited(self):
        self._target_manually_edited = True

    # Bekannte Hosts, bei denen ein Token statt Passwort erforderlich ist
    _TOKEN_REQUIRED_HOSTS = {"github.com", "gitlab.com"}
    # Bekannte Hosts, bei denen normales Passwort funktioniert
    _PASSWORD_OK_HOSTS = {"codeberg.org"}

    def _update_auth_section(self, url: str):
        is_https = url.startswith(("https://", "http://"))
        is_ssh = url.startswith("git@") or url.startswith("ssh://")
        self._auth_group.setVisible(is_https)
        self._ssh_hint.setVisible(is_ssh)

        if is_https:
            try:
                host = urlparse(url).hostname or ""
            except Exception:
                host = ""

            if host in self._TOKEN_REQUIRED_HOSTS:
                self._auth_hint.setText(
                    f"Tipp ({host}): Passwörter werden nicht mehr akzeptiert. "
                    "Bitte einen Personal Access Token verwenden: "
                    "Einstellungen → Developer settings → Personal access tokens (Scope: repo)."
                )
            elif host in self._PASSWORD_OK_HOSTS:
                self._auth_hint.setText(
                    f"Tipp ({host}): Normaler Benutzername und Passwort funktionieren hier direkt."
                )
            elif host:
                self._auth_hint.setText(
                    f"Tipp: Je nach Anbieter ({host}) funktioniert entweder das normale "
                    "Passwort oder ein Access Token."
                )
            else:
                self._auth_hint.setText("")

        self.adjustSize()

    def url(self) -> str:
        return self._clean_url(self._url_edit.text())

    def target_name(self) -> str:
        return self._target_edit.text().strip()

    def username(self) -> str:
        return self._username_edit.text().strip()

    def password(self) -> str:
        return self._password_edit.text()


# ──────────────────────────────────────────────────────────────────────────────
# Git-Konflikt-Dialog
# ──────────────────────────────────────────────────────────────────────────────
class GitConflictDialog(QDialog):
    """Löst Merge-Konflikte ohne Terminal: pro Datei eine Version wählen,
    im Editor von Hand lösen, den Merge abschließen oder abbrechen."""

    def __init__(self, main_window, repo: str):
        super().__init__(main_window)
        self._main = main_window
        self._repo = repo

        self.setWindowTitle("Git: Merge-Konflikte lösen")
        self.resize(640, 460)

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Bei diesen Dateien wurde an beiden Stellen unterschiedlich geändert.\n"
            "Wähle pro Datei eine Lösung – oder öffne sie zum Bearbeiten im Editor.",
            self,
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._list = QListWidget(self)
        self._list.currentItemChanged.connect(lambda *_: self._update_buttons())
        layout.addWidget(self._list, 1)

        # Aktionen pro Datei
        file_row = QHBoxLayout()
        self._btn_ours = QPushButton("Meine Version behalten", self)
        self._btn_theirs = QPushButton("Andere Version übernehmen", self)
        self._btn_open = QPushButton("Im Editor öffnen", self)
        self._btn_mark = QPushButton("Als gelöst markieren", self)
        self._btn_ours.clicked.connect(lambda: self._resolve_with_side("ours"))
        self._btn_theirs.clicked.connect(lambda: self._resolve_with_side("theirs"))
        self._btn_open.clicked.connect(self._open_in_editor)
        self._btn_mark.clicked.connect(self._mark_resolved)
        for b in (self._btn_ours, self._btn_theirs, self._btn_open, self._btn_mark):
            file_row.addWidget(b)
        layout.addLayout(file_row)

        self._status = QLabel("", self)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        # Abschluss-Aktionen
        bottom = QHBoxLayout()
        self._btn_abort = QPushButton("Merge abbrechen", self)
        self._btn_abort.clicked.connect(self._abort_merge)
        bottom.addWidget(self._btn_abort)
        bottom.addStretch()
        self._btn_finish = QPushButton("Merge abschließen", self)
        self._btn_finish.clicked.connect(self._finish_merge)
        bottom.addWidget(self._btn_finish)
        close_btn = QPushButton("Schließen", self)
        close_btn.clicked.connect(self.reject)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        self._refresh()

    # ── Git-Hilfen ──────────────────────────────────────────────────────────
    def _run(self, args: list[str], label: str) -> bool:
        cmd = self._main._git_command("-C", self._repo, *args)
        if cmd is None:
            self._main._console.append_error("[Git] Git wurde auf diesem System nicht gefunden.\n")
            return False
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        self._main._console.append_info(f"[Git] {label}\n")
        if res.stdout.strip():
            self._main._console.append_output(res.stdout)
        if res.returncode == 0:
            return True
        self._main._console.append_error(res.stderr or f"[Git] '{label}' fehlgeschlagen.\n")
        return False

    def _current_file(self) -> str | None:
        item = self._list.currentItem()
        return item.text() if item else None

    def _refresh(self):
        files = self._main._get_conflicted_files(self._repo)
        self._list.clear()
        for f in files:
            self._list.addItem(QListWidgetItem(f))
        if files:
            self._list.setCurrentRow(0)

        merge_open = self._main._merge_in_progress(self._repo)
        if files:
            self._status.setText(f"Noch {len(files)} Datei(en) mit Konflikten.")
        elif merge_open:
            self._status.setText(
                "Alle Konflikte gelöst – jetzt kannst du den Merge abschließen."
            )
        else:
            self._status.setText("Kein offener Merge – nichts zu tun.")

        self._btn_finish.setEnabled(merge_open and not files)
        self._btn_abort.setEnabled(merge_open)
        self._update_buttons()

    def _update_buttons(self):
        has_file = self._current_file() is not None
        for b in (self._btn_ours, self._btn_theirs, self._btn_open, self._btn_mark):
            b.setEnabled(has_file)

    # ── Aktionen ────────────────────────────────────────────────────────────
    def _resolve_with_side(self, side: str):
        rel = self._current_file()
        if not rel:
            return
        label = "Meine Version" if side == "ours" else "Andere Version"
        if self._run(["checkout", f"--{side}", "--", rel], f"{label} für '{rel}' wählen"):
            self._run(["add", "--", rel], f"'{rel}' als gelöst markieren")
        self._refresh()

    def _mark_resolved(self):
        rel = self._current_file()
        if not rel:
            return
        # Sicherheitsnetz: Datei darf keine Konfliktmarker mehr enthalten.
        abs_path = os.path.join(self._repo, rel)
        try:
            with open(abs_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            content = ""
        if any(marker in content for marker in ("<<<<<<<", "=======", ">>>>>>>")):
            QMessageBox.warning(
                self,
                "Git",
                f"In '{rel}' sind noch Konfliktmarker (<<<<<<<, =======, >>>>>>>) "
                "enthalten.\nBitte zuerst im Editor entfernen und die Datei speichern.",
            )
            return
        self._run(["add", "--", rel], f"'{rel}' als gelöst markieren")
        self._refresh()

    def _open_in_editor(self):
        rel = self._current_file()
        if not rel:
            return
        abs_path = os.path.join(self._repo, rel)
        self._main._open_file_path(abs_path)
        QMessageBox.information(
            self,
            "Git",
            f"'{rel}' wurde im Editor geöffnet.\n\n"
            "Entferne die Konfliktmarker (<<<<<<<, =======, >>>>>>>), speichere die "
            "Datei und öffne dann wieder „Git → Merge-Konflikte lösen“, um sie als "
            "gelöst zu markieren.",
        )
        self.reject()

    def _abort_merge(self):
        reply = QMessageBox.question(
            self,
            "Git: Merge abbrechen",
            "Den laufenden Merge komplett abbrechen?\n"
            "Der Zustand vor dem Merge wird wiederhergestellt.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if self._run(["merge", "--abort"], "Merge abbrechen"):
            self._main._console.append_success("[Git] Merge wurde abgebrochen.\n")
            self.accept()

    def _finish_merge(self):
        if self._run(["commit", "--no-edit"], "Merge abschließen (Commit)"):
            self._main._console.append_success("[Git] Merge erfolgreich abgeschlossen.\n")
            self.accept()
        else:
            self._refresh()


class GitIntegrationMixin:
    """Git-Aktionen des Hauptfensters (Klonen, Branches, Merge, Diff, Verlauf, Pull/Push, Commit)."""

    # ──────────────────────────────────────────────────────────────────────
    # Git-Aktionen
    # ──────────────────────────────────────────────────────────────────────
    def _resolve_git_executable(self) -> str | None:
        """Liefert ein nutzbares Git-Programm aus Einstellung oder PATH.

        Das Ergebnis wird gecacht: Auf Schulservern (Git auf Netzlaufwerk,
        Virenscanner) dauert der ``git --version``-Check sonst vor jeder
        Git-Aktion mehrere Sekunden.
        """
        chosen = (self._cfg.git_executable or "").strip()
        cached = getattr(self, "_git_exec_cache", None)
        if cached is not None and cached[0] == chosen and Path(cached[1]).is_file():
            return cached[1]

        candidates: list[str] = []
        if chosen:
            candidates.append(chosen)
        path_git = shutil.which("git")
        if path_git:
            candidates.append(path_git)

        seen: set[str] = set()
        for candidate in candidates:
            resolved = candidate
            if not os.path.isabs(candidate):
                maybe = shutil.which(candidate)
                if maybe:
                    resolved = maybe
            try:
                p = Path(resolved).resolve()
            except OSError:
                continue
            key = str(p)
            if key in seen:
                continue
            seen.add(key)
            if not p.exists() or not p.is_file():
                continue
            try:
                res = subprocess.run(
                    [str(p), "--version"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=15,
                )
            except Exception:
                continue
            if res.returncode == 0:
                self._git_exec_cache = (chosen, str(p))
                return str(p)
        return None

    def _git_command(self, *args: str) -> list[str] | None:
        git_exec = self._resolve_git_executable()
        if not git_exec:
            return None
        return [git_exec, *args]

    def _update_git_menu_visibility(self):
        if hasattr(self, "_m_git"):
            self._m_git.menuAction().setVisible(self._resolve_git_executable() is not None)

    def _get_git_base_dir(self) -> str:
        candidate = self._cfg.sketchbook
        if candidate and os.path.isdir(candidate):
            return candidate
        return str(Path.home())

    def _detect_git_repo_root(self, start_dir: str) -> str | None:
        cmd = self._git_command("-C", start_dir, "rev-parse", "--show-toplevel")
        if cmd is None:
            return None
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            return None
        return None

    def _list_git_repos_in_sketchbook(self) -> list[str]:
        base = self._get_git_base_dir()
        repos: list[str] = []
        seen: set[str] = set()

        base_repo = self._detect_git_repo_root(base)
        if base_repo:
            normalized = str(Path(base_repo).resolve())
            repos.append(normalized)
            seen.add(normalized)

        # Begrenzte Suche (Tiefe + Ignorier-Liste): das Sketchbook ist per
        # Default das Home-Verzeichnis – ein voller os.walk würde die
        # Oberfläche bei jeder Git-Aktion einfrieren.
        for root, dirs, _files in os.walk(base):
            if ".git" in dirs:
                repo_root = str(Path(root).resolve())
                if repo_root not in seen:
                    repos.append(repo_root)
                    seen.add(repo_root)
            rel = os.path.relpath(root, base)
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            if depth >= _SKETCHBOOK_MAX_DEPTH:
                dirs[:] = []
            else:
                dirs[:] = [d for d in dirs if not _skip_sketchbook_dir(d)]

        repos.sort(key=lambda p: p.casefold())
        return repos

    def _select_git_repo_from_list(self, repos: list[str], title: str) -> str | None:
        if not repos:
            return None

        base = Path(self._get_git_base_dir())
        labels = []
        mapping: dict[str, str] = {}
        for repo in repos:
            repo_path = Path(repo)
            try:
                label = str(repo_path.relative_to(base))
                if not label:
                    label = "."
            except ValueError:
                label = repo
            if label in mapping:
                label = repo
            labels.append(label)
            mapping[label] = repo

        labels.sort(key=lambda s: s.casefold())
        default_idx = 0
        if self._cfg.git_repo and self._cfg.git_repo in repos:
            for i, lbl in enumerate(labels):
                if mapping[lbl] == self._cfg.git_repo:
                    default_idx = i
                    break

        selected, ok = self._ask_item_input(
            title,
            "Repository:",
            labels,
            default_idx,
            False,
        )
        if not ok or not selected:
            return None
        return mapping[selected]

    def _resolve_git_repo(self, interactive: bool = True) -> str | None:
        if self._cfg.git_repo and os.path.isdir(self._cfg.git_repo):
            repo = self._detect_git_repo_root(self._cfg.git_repo)
            if repo:
                normalized = str(Path(repo).resolve())
                if normalized == str(Path(self._cfg.git_repo).resolve()):
                    self._cfg.git_repo = normalized
                    return normalized

        repos = self._list_git_repos_in_sketchbook()
        if not repos:
            return None
        if len(repos) == 1:
            self._cfg.git_repo = repos[0]
            self._update_git_status_label()
            return repos[0]
        if not interactive:
            return None

        selected_repo = self._select_git_repo_from_list(repos, "Git: Repository auswählen")
        if not selected_repo:
            return None
        self._cfg.git_repo = selected_repo
        self._save_persistent_settings()
        self._update_git_status_label()
        return selected_repo

    def _require_git_repo(self) -> str | None:
        repo = self._resolve_git_repo(interactive=True)
        if repo:
            return repo
        QMessageBox.warning(
            self,
            "Git",
            "Im Sketchbook-Ordner wurde kein Git-Repository gefunden.\n"
            "Bitte zuerst ein Repository klonen oder initialisieren.",
        )
        return None

    def _git_select_repo(self):
        repos = self._list_git_repos_in_sketchbook()
        if not repos:
            QMessageBox.warning(
                self,
                "Git",
                "Im Sketchbook-Ordner wurden keine Repositories gefunden.",
            )
            return
        selected_repo = self._select_git_repo_from_list(repos, "Git: Repository auswählen")
        if not selected_repo:
            return
        self._cfg.git_repo = selected_repo
        self._save_persistent_settings()
        self._update_git_status_label()
        self._console.append_info(f"[Git] Aktives Repository: {selected_repo}\n")

    def _run_git_process(
        self,
        cmd: list[str],
        cwd: str,
        label: str,
        on_success=None,
        display_cmd: list[str] | None = None,
        on_finish=None,
    ):
        git_exec = self._resolve_git_executable()
        if git_exec is None:
            QMessageBox.critical(self, "Git", "Git wurde auf diesem System nicht gefunden.")
            return

        effective_cmd = list(cmd)
        if effective_cmd and effective_cmd[0] == "git":
            effective_cmd[0] = git_exec

        log_cmd = display_cmd if display_cmd is not None else cmd
        self._console.append_info(f"\n[Git] {label}\n")
        self._console.append_info(f"[Git] Arbeitsordner: {cwd}\n")
        self._console.append_info(f"[Git] Befehl: {' '.join(log_cmd)}\n")

        env = _git_network_env()
        if env is not None:
            self._console.append_info(
                f"[Git] System-Proxy wird verwendet: {env['HTTPS_PROXY']}\n"
            )
        proc = ProcessRunner(effective_cmd, cwd=cwd, env=env)
        # stderr puffern: Git schreibt Fortschritts-/Info-Meldungen auf stderr,
        # auch bei Erfolg. Erst nach Prozessende entscheiden ob rot (Fehler) oder normal.
        stderr_buf: list[str] = []
        proc.output.connect(
            lambda text, kind: self._console.append_output(text)
            if kind == "stdout"
            else stderr_buf.append(text)
        )

        def _on_finish(code: int):
            for chunk in stderr_buf:
                if code == 0:
                    self._console.append_output(chunk)
                else:
                    self._console.append_error(chunk)
            if code == 0:
                self._console.append_success(f"[Git] Fertig (Code {code})\n")
                if on_success is not None:
                    on_success()
            else:
                self._console.append_error(f"[Git] Fehler (Code {code})\n")
                hint = git_network_hint("".join(stderr_buf))
                if hint:
                    self._console.append_info(hint + "\n")
            if on_finish is not None:
                on_finish(code)

        proc.finished_run.connect(_on_finish)
        self._retire_process()
        self._process = proc
        proc.start()

    def _git_clone(self):
        dlg = GitCloneDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        url = dlg.url()
        target_name = dlg.target_name()
        username = dlg.username()
        password = dlg.password()

        if not url or not target_name:
            QMessageBox.warning(self, "Git", "URL und Zielordner dürfen nicht leer sein.")
            return

        base = self._get_git_base_dir()
        target = os.path.join(base, target_name)
        if os.path.exists(target):
            QMessageBox.warning(self, "Git", f"Zielordner existiert bereits:\n{target}")
            return

        # Für HTTPS mit Credentials: URL mit eingebetteten Zugangsdaten bauen
        clone_url = url
        display_url = url
        if username and password and url.startswith(("https://", "http://")):
            parsed = urlparse(url)
            # Sonderzeichen (z. B. @ in E-Mail-Adressen) müssen URL-kodiert werden
            enc_user = urlquote(username, safe="")
            enc_pass = urlquote(password, safe="")
            host = parsed.hostname
            netloc = f"{enc_user}:{enc_pass}@{host}"
            if parsed.port:
                netloc += f":{parsed.port}"
            clone_url = urlunparse(parsed._replace(netloc=netloc))
            display_url = urlunparse(parsed._replace(netloc=f"{enc_user}:***@{host}"))

        clone_cmd = ["git", "clone", clone_url, target]
        display_cmd = ["git", "clone", display_url, target]

        def on_clone_success():
            self._set_active_repo_after_clone(target)
            if username and password and url.startswith(("https://", "http://")):
                # WICHTIG: git speichert die Clone-URL unverändert in
                # .git/config (remote.origin.url) – inklusive eingebettetem
                # Passwort/Token im Klartext. Deshalb die Remote-URL sofort
                # auf die Variante OHNE Zugangsdaten zurücksetzen; für
                # Pull/Push übernimmt der Credential-Helper (s. u.).
                cmd = self._git_command("-C", target, "remote", "set-url", "origin", url)
                if cmd is not None:
                    subprocess.run(cmd, capture_output=True, check=False)
                self._store_git_credentials(target, url, username, password)

        self._run_git_process(
            clone_cmd,
            cwd=base,
            label="Repository klonen",
            on_success=on_clone_success,
            display_cmd=display_cmd,
        )

    def _secure_credential_helper(self) -> str:
        """Plattformabhängiger, sicherer git-credential-Helper.

        Speichert Zugangsdaten verschlüsselt im Betriebssystem (Windows Credential
        Manager / macOS Keychain / GNOME-Keyring via libsecret) statt im Klartext.
        Wo libsecret fehlt, wird der eingebaute, nur im Arbeitsspeicher gehaltene
        ``cache``-Helper genutzt (besser als Klartext auf der Platte).
        """
        if sys.platform == "win32":
            return "manager"
        if sys.platform == "darwin":
            return "osxkeychain"
        if shutil.which("git-credential-libsecret"):
            return "libsecret"
        # Fallback: 8 h im RAM-Cache – kein Klartext auf der Platte
        return "cache --timeout=28800"

    def _store_git_credentials(self, repo_path: str, url: str, username: str, password: str):
        """Speichert HTTPS-Credentials verschlüsselt über den OS-Credential-Manager.

        Es wird KEIN Klartext mehr in ``~/.git-credentials`` geschrieben. Ein evtl.
        vorhandener alter Klartext-Eintrag für denselben Host wird entfernt.
        """
        parsed = urlparse(url)
        helper = self._secure_credential_helper()
        # Lokalen credential.helper auf den sicheren Helper setzen
        cmd = self._git_command("-C", repo_path, "config", "credential.helper", helper)
        if cmd is not None:
            subprocess.run(cmd, capture_output=True, check=False)
        # Zugangsdaten über 'git credential approve' an den Helper übergeben –
        # dieser legt sie verschlüsselt im OS-Schlüsselspeicher ab.
        approve_input = (
            f"protocol={parsed.scheme}\n"
            f"host={parsed.hostname}\n"
            f"username={username}\n"
            f"password={password}\n\n"
        )
        try:
            cmd = self._git_command("-C", repo_path, "credential", "approve")
            if cmd is None:
                self._console.append_info(
                    "[Git] Zugangsdaten konnten nicht im Schlüsselspeicher abgelegt "
                    "werden – Git fragt beim nächsten Zugriff erneut nach.\n")
                return
            res = subprocess.run(
                cmd,
                input=approve_input, text=True,
                capture_output=True, check=False,
            )
            if res.returncode == 0:
                self._console.append_success(
                    "[Git] Zugangsdaten sicher im System-Schlüsselspeicher abgelegt.\n")
            else:
                self._console.append_info(
                    "[Git] Zugangsdaten konnten nicht im Schlüsselspeicher abgelegt "
                    "werden – Git fragt beim nächsten Zugriff erneut nach.\n")
        except OSError as exc:
            self._console.append_error(
                f"[Git] Zugangsdaten konnten nicht gespeichert werden: {exc}\n")

        # Migration/Bereinigung: evtl. früher gespeicherten Klartext-Eintrag löschen
        self._purge_plaintext_credentials(parsed.scheme, parsed.hostname, username)

    def _purge_plaintext_credentials(self, scheme: str, hostname: str | None, username: str):
        """Entfernt einen alten Klartext-Eintrag aus ~/.git-credentials (falls vorhanden)."""
        creds_file = Path.home() / ".git-credentials"
        if not hostname or not creds_file.exists():
            return
        try:
            enc_user = urlquote(username, safe="")
            host_prefix = f"{scheme}://{enc_user}:"
            host_suffix = f"@{hostname}"
            existing = creds_file.read_text(encoding="utf-8").splitlines(keepends=True)
            kept = [
                ln for ln in existing
                if not (ln.startswith(host_prefix) and host_suffix in ln)
            ]
            if len(kept) != len(existing):
                creds_file.write_text("".join(kept), encoding="utf-8")
        except OSError:
            pass

    def _set_active_repo_after_clone(self, repo_path: str):
        normalized = str(Path(repo_path).resolve())
        self._cfg.git_repo = normalized
        self._save_persistent_settings()
        self._update_git_status_label()
        self._console.append_success(f"[Git] Aktives Repository gesetzt: {normalized}\n")

    def _git_show_branch(self):
        repo = self._require_git_repo()
        if not repo:
            return
        branch = self._get_current_branch(repo)
        if not branch:
            QMessageBox.warning(self, "Git", "Aktueller Branch konnte nicht ermittelt werden.")
            return
        self._console.append_info(f"[Git] Aktueller Branch: {branch}\n")
        QMessageBox.information(self, "Git", f"Aktueller Branch:\n{branch}")

    def _get_current_branch(self, repo: str) -> str | None:
        cmd = self._git_command("-C", repo, "rev-parse", "--abbrev-ref", "HEAD")
        if cmd is None:
            return None
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return None
        branch = res.stdout.strip()
        return branch or None

    def _git_switch_branch(self):
        repo = self._require_git_repo()
        if not repo:
            return

        branches = self._get_local_branches(repo)
        if not branches:
            QMessageBox.warning(self, "Git", "Keine lokalen Branches gefunden.")
            return

        current = self._get_current_branch(repo) or ""
        try:
            default_idx = branches.index(current)
        except ValueError:
            default_idx = 0

        target, ok = self._ask_item_input(
            "Git: Branch wechseln",
            "Branch:",
            branches,
            default_idx,
            True,
        )
        if not ok or not target.strip():
            return
        target = target.strip()
        if target == current:
            self._console.append_info(f"[Git] Bereits auf Branch '{target}'.\n")
            return

        self._run_git_process(["git", "switch", target], cwd=repo, label=f"Branch wechseln zu {target}")

    def _get_local_branches(self, repo: str) -> list[str]:
        cmd = self._git_command("-C", repo, "branch", "--format", "%(refname:short)")
        if cmd is None:
            return []
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return []
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]

    def _git_create_branch(self):
        repo = self._require_git_repo()
        if not repo:
            return

        current = self._get_current_branch(repo) or "HEAD"
        name, ok = self._ask_text_input(
            "Git: Neuen Branch anlegen",
            f"Name des neuen Branches\n(wird ausgehend von '{current}' erstellt):",
        )
        if not ok or not name.strip():
            return
        name = name.strip()

        if name in self._get_local_branches(repo):
            QMessageBox.warning(self, "Git", f"Ein Branch mit dem Namen '{name}' existiert bereits.")
            return

        # git switch -c legt den Branch an und wechselt direkt dorthin.
        self._run_git_process(
            ["git", "switch", "-c", name],
            cwd=repo,
            label=f"Neuen Branch '{name}' anlegen",
        )

    def _git_fetch_then(self, repo: str, on_done):
        """Holt den Remote-Stand (``fetch --all --prune``) im Hintergrund-Thread
        und ruft danach ``on_done()`` im UI-Thread auf – ohne die Oberfläche
        einzufrieren. Schlägt der Fetch fehl (z. B. offline), wird trotzdem mit
        dem lokalen Stand fortgefahren.
        """
        cmd = self._git_command("-C", repo, "fetch", "--all", "--prune")
        if cmd is None:
            on_done()
            return
        self._console.append_info("[Git] Hole Remote-Stand …\n")
        proc = ProcessRunner(cmd, cwd=repo, env=_git_network_env())
        # on_done erst nach Rückkehr aus dem finished-Slot starten (sauberer Dialog).
        proc.finished_run.connect(lambda code: QTimer.singleShot(0, on_done))
        self._retire_process()
        self._process = proc
        proc.start()

    def _git_merge_branch(self):
        repo = self._require_git_repo()
        if not repo:
            return

        current = self._get_current_branch(repo)
        if not current or current == "HEAD":
            QMessageBox.warning(
                self,
                "Git",
                "Es ist kein Branch aktiv (losgelöster HEAD). Bitte zuerst einen Branch auswählen.",
            )
            return

        # Remote-Stand im Hintergrund aktualisieren, dann die Auswahl zeigen.
        self._git_fetch_then(repo, lambda: self._merge_branch_choose(repo, current))

    def _merge_branch_choose(self, repo: str, current: str):
        """Zeigt nach dem Hintergrund-Fetch die Branch-Auswahl und startet den Merge."""
        local = [b for b in self._get_local_branches(repo) if b != current]
        remote = self._get_remote_origin_branches(repo)
        candidates = local + remote
        if not candidates:
            QMessageBox.warning(self, "Git", "Es wurde kein anderer Branch zum Mergen gefunden.")
            return

        # Upstream (z. B. origin/<current>) als Vorauswahl, falls vorhanden –
        # das ist der typische Fall „den Remote-Stand in meinen Branch holen".
        upstream = self._get_upstream_branch(repo)
        default_idx = candidates.index(upstream) if upstream in candidates else 0

        source, ok = self._ask_item_input(
            "Git: Branch mergen",
            f"Welcher Branch soll in '{current}' gemergt werden?",
            candidates,
            default_idx,
            False,
        )
        if not ok or not source.strip():
            return
        source = source.strip()

        self._run_git_process(
            ["git", "merge", source],
            cwd=repo,
            label=f"'{source}' in '{current}' mergen",
            on_finish=lambda code: self._offer_conflict_resolution(repo),
        )

    def _get_conflicted_files(self, repo: str) -> list[str]:
        cmd = self._git_command("-C", repo, "diff", "--name-only", "--diff-filter=U")
        if cmd is None:
            return []
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return []
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]

    def _merge_in_progress(self, repo: str) -> bool:
        cmd = self._git_command("-C", repo, "rev-parse", "-q", "--verify", "MERGE_HEAD")
        if cmd is None:
            return False
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode == 0

    def _offer_conflict_resolution(self, repo: str):
        """Nach einem Merge/Pull mit Konflikten anbieten, den Konflikt-Dialog zu öffnen."""
        if not self._get_conflicted_files(repo):
            return
        reply = QMessageBox.warning(
            self,
            "Git: Merge-Konflikt",
            "Beim Mergen sind Konflikte aufgetreten – derselbe Code wurde an beiden "
            "Stellen unterschiedlich geändert.\n\n"
            "Möchtest du sie jetzt im Konflikt-Helfer lösen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._git_resolve_conflicts()

    def _git_resolve_conflicts(self):
        repo = self._require_git_repo()
        if not repo:
            return

        if not self._merge_in_progress(repo) and not self._get_conflicted_files(repo):
            QMessageBox.information(
                self,
                "Git",
                "Aktuell ist kein Merge mit Konflikten offen – es gibt nichts zu lösen.",
            )
            return

        dlg = GitConflictDialog(self, repo)
        dlg.exec()
        self._update_git_status_label()

    def _git_diff(self):
        repo = self._require_git_repo()
        if not repo:
            return
        # Remote-Stand im Hintergrund holen, dann die Vergleichsauswahl zeigen.
        self._git_fetch_then(repo, lambda: self._git_diff_choose(repo))

    def _git_diff_choose(self, repo: str):
        """Zeigt nach dem Hintergrund-Fetch die Vergleichsauswahl und erzeugt den Diff."""
        current = self._get_current_branch(repo)
        working = "Eigene Änderungen (noch nicht committet)"
        options = [working]

        upstream = self._get_upstream_branch(repo)
        remote = self._get_remote_origin_branches(repo)
        local = [b for b in self._get_local_branches(repo) if b != current]

        # Upstream nach vorne ziehen – der häufigste Vergleich.
        ordered_remote = []
        if upstream and upstream in remote:
            ordered_remote.append(upstream)
        ordered_remote += [b for b in remote if b != upstream]

        ref_map: dict[str, list[str]] = {working: ["git", "-C", repo, "--no-pager", "diff"]}
        for ref in ordered_remote + local:
            label = f"Aktueller Branch  ↔  {ref}"
            options.append(label)
            # HEAD..ref zeigt, was auf 'ref' enthalten ist, das hier (noch) fehlt.
            ref_map[label] = ["git", "-C", repo, "--no-pager", "diff", f"HEAD..{ref}"]

        choice, ok = self._ask_item_input(
            "Git: Vergleichen (Diff)",
            "Was soll verglichen werden?",
            options,
            0,
            False,
        )
        if not ok or not choice:
            return

        git_exec = self._resolve_git_executable()
        if git_exec is None:
            self._console.append_error("[Git] Git wurde auf diesem System nicht gefunden.\n")
            return

        res = subprocess.run(
            [git_exec, *ref_map[choice][1:]],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            self._console.append_error(res.stderr or "[Git] Vergleich konnte nicht erstellt werden.\n")
            return

        self._show_git_diff_dialog(f"Git: Vergleich – {choice}", res.stdout)

    def _show_git_diff_dialog(self, title: str, diff_text: str):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(820, 560)

        layout = QVBoxLayout(dialog)
        view = QTextEdit(dialog)
        view.setReadOnly(True)
        view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        view.setFont(QFont("JetBrains Mono, Fira Code, Consolas, monospace", 10))

        if not diff_text.strip():
            view.setPlainText("(Keine Unterschiede – alles auf dem gleichen Stand.)")
        else:
            view.setHtml(self._diff_to_html(diff_text))
        layout.addWidget(view)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dialog.exec()

    def _diff_to_html(self, diff_text: str) -> str:
        from html import escape

        add_color = "#22c55e"   # hinzugefügte Zeilen
        del_color = "#ef4444"   # entfernte Zeilen
        meta_color = "#60a5fa"  # Datei-/Hunk-Köpfe
        lines = []
        for raw in diff_text.splitlines():
            safe = escape(raw)
            if raw.startswith(("+++", "---", "@@", "diff ", "index ")):
                color = meta_color
            elif raw.startswith("+"):
                color = add_color
            elif raw.startswith("-"):
                color = del_color
            else:
                color = None
            if color:
                lines.append(f'<span style="color:{color};">{safe}</span>')
            else:
                lines.append(safe)
        # Innerhalb von <pre> bleiben Zeilenumbrüche und Einrückungen erhalten.
        body = "\n".join(lines)
        return f'<pre style="margin:0; white-space:pre; font-family:inherit;">{body}</pre>'

    def _git_show_history(self):
        repo = self._require_git_repo()
        if not repo:
            return

        cmd = self._git_command("-C", repo, "--no-pager", "log", "--oneline", "--decorate", "-n", "50")
        if cmd is None:
            self._console.append_error("[Git] Git wurde auf diesem System nicht gefunden.\n")
            return

        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            self._console.append_error(res.stderr or "[Git] Historie konnte nicht gelesen werden.\n")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Git: Historie")
        dialog.resize(760, 520)

        layout = QVBoxLayout(dialog)
        history_view = QTextEdit(dialog)
        history_view.setReadOnly(True)
        history_view.setFont(QFont("JetBrains Mono, Fira Code, Consolas, monospace", 10))
        history_view.setPlainText(res.stdout.strip() or "(Keine Commits gefunden)")
        layout.addWidget(history_view)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dialog.exec()

    def _git_status(self):
        repo = self._require_git_repo()
        if not repo:
            return
        self._run_git_process(["git", "status", "--short", "--branch"], cwd=repo, label="Status")

    def _git_fetch(self):
        repo = self._require_git_repo()
        if not repo:
            return
        self._run_git_process(["git", "fetch", "--all", "--prune"], cwd=repo, label="Fetch")

    def _git_pull(self):
        repo = self._require_git_repo()
        if not repo:
            return
        branch = self._get_current_branch(repo)
        if branch and branch != "HEAD":
            self._run_git_process(
                ["git", "pull", "origin", branch],
                cwd=repo,
                label="Pull",
                on_finish=lambda code: self._offer_conflict_resolution(repo),
            )
        else:
            self._run_git_process(
                ["git", "pull"],
                cwd=repo,
                label="Pull",
                on_finish=lambda code: self._offer_conflict_resolution(repo),
            )

    def _get_upstream_branch(self, repo: str) -> str | None:
        cmd = self._git_command("-C", repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        if cmd is None:
            return None
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return None
        value = res.stdout.strip()
        return value or None

    def _get_remote_origin_branches(self, repo: str) -> list[str]:
        cmd = self._git_command(
            "-C", repo, "for-each-ref", "--format", "%(refname:short)", "refs/remotes/origin"
        )
        if cmd is None:
            return []
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return []
        branches = []
        for line in res.stdout.splitlines():
            branch = line.strip()
            if not branch or branch == "origin/HEAD":
                continue
            branches.append(branch)
        branches.sort(key=lambda b: b.casefold())
        return branches

    def _git_push(self):
        repo = self._require_git_repo()
        if not repo:
            return
        self._run_git_process(["git", "push"], cwd=repo, label="Push")

    def _git_commit(self):
        repo = self._require_git_repo()
        if not repo:
            return
        msg, ok = self._ask_text_input(
            "Git: Commit",
            "Commit-Nachricht:",
        )
        if not ok or not msg.strip():
            return
        self._run_git_process(
            ["git", "add", "-A"],
            cwd=repo,
            label="Änderungen stagen",
            on_success=lambda: self._run_git_process(
                ["git", "commit", "-m", msg.strip()],
                cwd=repo,
                label="Commit erstellen",
            ),
        )
