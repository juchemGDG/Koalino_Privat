// app.js – iPad-MicroPython: Texteditor + Konsole (ohne Blockly)

const statusEl  = document.getElementById('status');
const codeEl    = document.getElementById('code');
const consoleEl = document.getElementById('console');
const boardEl   = document.getElementById('board');

// ── Beispielprogramme ────────────────────────────────────────────────────
const EXAMPLES = {
  'Hallo Welt': `import time

zaehler = 0
while True:
    print("Hallo Welt", zaehler)
    zaehler += 1
    time.sleep(1)
`,
  'LED blinken': `from machine import Pin
import time

# Pin 8 = eingebaute LED vieler ESP32-C3-Boards (ggf. anpassen)
led = Pin(8, Pin.OUT)

while True:
    led.on()
    time.sleep(0.5)
    led.off()
    time.sleep(0.5)
`,
  'Taster lesen': `from machine import Pin
import time

taster = Pin(9, Pin.IN, Pin.PULL_UP)

while True:
    if taster.value() == 0:
        print("Taster gedrückt")
    time.sleep_ms(100)
`,
  'Analogwert messen': `from machine import Pin, ADC
import time

adc = ADC(Pin(2))
adc.atten(ADC.ATTN_11DB)   # Messbereich bis ca. 3,3 V

while True:
    print(adc.read_u16())
    time.sleep_ms(200)
`,
};
const exSel = document.getElementById('examples');
for (const name of Object.keys(EXAMPLES)) {
  const o = document.createElement('option');
  o.value = name; o.textContent = name;
  exSel.appendChild(o);
}
exSel.addEventListener('change', () => {
  const name = exSel.value;
  exSel.value = '';
  if (!name) return;
  if (codeEl.value.trim() && !confirm('Das aktuelle Programm durch das Beispiel „' + name + '“ ersetzen?')) return;
  codeEl.value = EXAMPLES[name];
  autosave();
  setStatus('Beispiel geladen: ' + name);
});

// SSID dieses Boards anzeigen (hilft im Klassensatz, das richtige Board zu erkennen)
(async function showBoardName() {
  try {
    const res = await fetch('/api/info');
    if (!res.ok) return;
    const data = await res.json();
    if (data.ssid) boardEl.textContent = '📶 ' + data.ssid;
  } catch (e) { /* im Browser-Vorschaumodus ohne Board ignorieren */ }
})();

function setStatus(t) { statusEl.textContent = t; }

// ── Editor: Tab, automatische Einrückung, Zusatztasten ─────────────────────
const INDENT = '    ';

function insertText(text) {
  codeEl.focus();
  const s = codeEl.selectionStart, e = codeEl.selectionEnd;
  codeEl.setRangeText(text, s, e, 'end');
  codeEl.dispatchEvent(new Event('input'));
}

codeEl.addEventListener('keydown', (ev) => {
  if (ev.key === 'Tab') {
    ev.preventDefault();
    insertText(INDENT);
  } else if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) {
    ev.preventDefault();
    runProgram();
  } else if (ev.key === 'Enter' && !ev.shiftKey) {
    // Einrückung der aktuellen Zeile übernehmen; nach ":" eine Stufe tiefer
    const pos = codeEl.selectionStart;
    const lineStart = codeEl.value.lastIndexOf('\n', pos - 1) + 1;
    const before = codeEl.value.slice(lineStart, pos);
    const indent = (before.match(/^[ \t]*/) || [''])[0];
    const extra = /:\s*(#.*)?$/.test(before) ? INDENT : '';
    ev.preventDefault();
    insertText('\n' + indent + extra);
  }
});

const KEYS = ['Tab', ':', '(', ')', '[', ']', '{', '}', '"', "'", '=', '_', '#', '.', ',', '<', '>', '+', '-', '*', '/', '%', '!', '&', '|'];
const keysEl = document.getElementById('keys');
for (const k of KEYS) {
  const b = document.createElement('button');
  b.textContent = k === 'Tab' ? '⇥' : k;
  b.title = k === 'Tab' ? 'Einrücken' : k;
  // mousedown/pointerdown verhindern, dass das Textfeld den Fokus (und die Tastatur) verliert
  b.addEventListener('pointerdown', (ev) => ev.preventDefault());
  b.addEventListener('click', () => {
    if (k === 'Tab') return insertText(INDENT);
    // Klammern und Anführungszeichen paarweise einfügen, Cursor dazwischen
    const pairs = { '(': ')', '[': ']', '{': '}', '"': '"', "'": "'" };
    insertText(k);
    if (pairs[k]) {
      insertText(pairs[k]);
      codeEl.selectionStart = codeEl.selectionEnd = codeEl.selectionStart - 1;
    }
  });
  keysEl.appendChild(b);
}

// ── Speichern / Laden (Browser) ──────────────────────────────────────────
const AUTOSAVE_KEY = 'nit_py_autosave';
const PROJECTS_KEY = 'nit_py_projects';

function getProjects() {
  try { return JSON.parse(localStorage.getItem(PROJECTS_KEY) || '{}'); }
  catch (e) { return {}; }
}
function setProjects(obj) { localStorage.setItem(PROJECTS_KEY, JSON.stringify(obj)); }

function autosave() {
  try { localStorage.setItem(AUTOSAVE_KEY, codeEl.value); } catch (e) {}
}
codeEl.addEventListener('input', autosave);

// Beim Start: zuletzt bearbeiteten Stand wiederherstellen, sonst Beispiel
try {
  const auto = localStorage.getItem(AUTOSAVE_KEY);
  codeEl.value = auto !== null ? auto : EXAMPLES['LED blinken'];
} catch (e) { codeEl.value = EXAMPLES['LED blinken']; }

function logLine(text, cls) {
  const span = document.createElement('span');
  if (cls) span.className = cls;
  span.textContent = text;
  consoleEl.appendChild(span);
  consoleEl.scrollTop = consoleEl.scrollHeight;
}

document.getElementById('btnClear').addEventListener('click', () => { consoleEl.textContent = ''; });

// ── Ausführen ────────────────────────────────────────────────────────────
async function runProgram() {
  const code = codeEl.value;
  if (!code.trim()) { setStatus('Kein Code vorhanden'); return; }
  setStatus('Übertrage …');
  consoleEl.textContent = '';
  outputCursor = 0;
  try {
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: code
    });
    if (res.ok) {
      setStatus('Läuft auf dem ESP32 …');
      logLine('▶ Programm gestartet\n', 'sys');
      startPolling();
    } else {
      const msg = await res.text();
      setStatus('Fehler beim Übertragen');
      logLine('✗ ' + msg + '\n', 'err');
    }
  } catch (e) {
    setStatus('Board nicht erreichbar');
    logLine('✗ Board nicht erreichbar (' + e + ')\n', 'err');
  }
}

// ── Stopp ────────────────────────────────────────────────────────────────
async function stopProgram() {
  stopPolling();
  setStatus('Stoppe …');
  try {
    await fetch('/api/stop', { method: 'POST' });
    setStatus('Gestoppt – Board startet neu');
    logLine('■ gestoppt\n', 'sys');
  } catch (e) {
    setStatus('Board nicht erreichbar');
  }
}

// ── Konsolen-Ausgabe pollen ─────────────────────────────────────────────
// Adaptiv: solange Ausgaben kommen, schnell pollen (Konsole wirkt "live");
// bei Funkstille schrittweise bis POLL_MAX zurückfahren, denn jede Anfrage
// unterbricht das Nutzerprogramm auf dem Single-Core-ESP32 kurz.
const POLL_MIN = 200;
const POLL_MAX = 1200;
let pollDelay = POLL_MIN;
let pollGen = 0;        // entwertet alte Poll-Ketten (z. B. bei erneutem "Ausführen")
let pollTimer = null;
let outputCursor = 0;   // wie viele Ausgabezeilen wir schon geholt haben

function startPolling() {
  stopPolling();
  pollDelay = POLL_MIN;
  const gen = pollGen;
  pollTimer = setTimeout(() => pollOnce(gen), pollDelay);
}
function stopPolling() {
  pollGen++;
  if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
}
// setTimeout-Kette statt setInterval: die nächste Anfrage startet erst,
// wenn die vorige fertig ist – sonst stauen sich bei trägem Board Requests.
async function pollOnce(gen) {
  await fetchOutput();
  if (gen === pollGen) pollTimer = setTimeout(() => pollOnce(gen), pollDelay);
}
async function fetchOutput() {
  try {
    const res = await fetch('/api/output?since=' + outputCursor);
    if (!res.ok) return;
    const data = await res.json();   // { lines: [...], next: N, running: bool }
    if (Array.isArray(data.lines)) {
      for (const line of data.lines) {
        const isErr = line.indexOf('Traceback') === 0 || line.indexOf('Error') >= 0;
        logLine(line, isErr ? 'err' : null);
      }
      pollDelay = data.lines.length ? POLL_MIN
                                    : Math.min(pollDelay * 1.5, POLL_MAX);
    }
    if (typeof data.next === 'number') outputCursor = data.next;
    if (!data.running) {
      stopPolling();
      setStatus('Programm beendet');
      logLine('◼ Programm beendet\n', 'sys');
    }
  } catch (e) {
    // Board evtl. beim Neustart – Polling ruhig weiterlaufen lassen
    pollDelay = POLL_MAX;
  }
}

document.getElementById('btnRun').addEventListener('click', runProgram);
document.getElementById('btnStop').addEventListener('click', stopProgram);

// ── Projekte: Speichern / Laden / Löschen / Datei-Export-Import ───────────
const modal    = document.getElementById('projModal');
const projList = document.getElementById('projList');
const fileInput = document.getElementById('fileInput');
let lastName = '';

document.getElementById('btnSave').addEventListener('click', () => {
  const name = (prompt('Projektname zum Speichern:', lastName) || '').trim();
  if (!name) return;
  const projects = getProjects();
  if (projects[name] !== undefined && !confirm('„' + name + '“ überschreiben?')) return;
  projects[name] = codeEl.value;
  setProjects(projects);
  lastName = name;
  setStatus('Gespeichert: ' + name);
});

document.getElementById('btnProjects').addEventListener('click', () => {
  renderProjects();
  modal.hidden = false;
});
document.getElementById('projClose').addEventListener('click', () => { modal.hidden = true; });
modal.addEventListener('click', (e) => { if (e.target === modal) modal.hidden = true; });

function renderProjects() {
  const projects = getProjects();
  const names = Object.keys(projects).sort();
  projList.innerHTML = '';
  if (!names.length) {
    const li = document.createElement('li');
    li.innerHTML = '<span class="empty">Noch keine Projekte gespeichert.</span>';
    projList.appendChild(li);
    return;
  }
  for (const name of names) {
    const li = document.createElement('li');
    const label = document.createElement('span');
    label.className = 'pname';
    label.textContent = name;
    const load = document.createElement('button');
    load.className = 'load'; load.textContent = 'Laden';
    load.addEventListener('click', () => {
      codeEl.value = projects[name];
      autosave();
      lastName = name; modal.hidden = true; setStatus('Geladen: ' + name);
    });
    const del = document.createElement('button');
    del.className = 'del'; del.textContent = '🗑';
    del.addEventListener('click', () => {
      if (!confirm('„' + name + '“ löschen?')) return;
      const p = getProjects(); delete p[name]; setProjects(p); renderProjects();
    });
    li.appendChild(label); li.appendChild(load); li.appendChild(del);
    projList.appendChild(li);
  }
}

// Als Datei sichern (herunterladen) – echtes, geräteübergreifendes Backup
document.getElementById('projExport').addEventListener('click', () => {
  const blob = new Blob([codeEl.value], { type: 'text/x-python' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = (lastName || 'programm') + '.py';
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
});

// Datei laden (importieren)
document.getElementById('projImportBtn').addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  const file = fileInput.files && fileInput.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    codeEl.value = String(reader.result);
    autosave();
    modal.hidden = true;
    setStatus('Datei geladen: ' + file.name);
  };
  reader.readAsText(file);
  fileInput.value = '';
});
