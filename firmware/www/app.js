// app.js – iPad-MicroPython: Texteditor mit Syntax-Highlighting + Konsole

const statusEl  = document.getElementById('status');
const codeEl    = document.getElementById('code');
const consoleEl = document.getElementById('console');
const boardEl   = document.getElementById('board');

// ── Syntax-Highlighting (Python) ───────────────────────────────────────────
// Eigener kleiner Tokenizer; Farben kommen aus CSS-Variablen (hell = Eclipse,
// dunkel = One Dark, automatisch nach iPad-Einstellung).
const hlEl = document.getElementById('hl');
const KW = new Set(['and','as','assert','async','await','break','class','continue','def','del',
  'elif','else','except','finally','for','from','global','if','import','in','is','lambda',
  'nonlocal','not','or','pass','raise','return','try','while','with','yield']);
const CONSTS = new Set(['True','False','None','self','cls']);
const BUILTINS = new Set(['print','len','range','int','float','str','bool','list','dict','tuple',
  'set','abs','min','max','sum','round','sorted','enumerate','zip','map','filter','input','open',
  'isinstance','type','bytes','bytearray','hex','bin','ord','chr','pow','divmod','any','all',
  'Exception','ValueError','OSError','KeyboardInterrupt','Pin','ADC','PWM','I2C','SPI','UART','Timer','NeoPixel']);
const TOKEN_RE = new RegExp([
  /(#[^\n]*)/.source,                                                         // 1 Kommentar
  /((?:[rRbBfFuU]{0,2})(?:"""[\s\S]*?(?:"""|$)|'''[\s\S]*?(?:'''|$)))/.source, // 2 Strings dreifach
  /((?:[rRbBfFuU]{0,2})(?:"(?:\\.|[^"\\\n])*(?:"|$)|'(?:\\.|[^'\\\n])*(?:'|$)))/.source, // 3 Strings
  /(@[A-Za-z_][\w.]*)/.source,                                                // 4 Dekorator
  /(0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|(?:\d[\d_]*\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)/.source, // 5 Zahl
  /([A-Za-z_]\w*)/.source,                                                    // 6 Name
].join('|'), 'g');

function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

function highlight(src) {
  let out = '', last = 0, prevWord = '', m;
  TOKEN_RE.lastIndex = 0;
  while ((m = TOKEN_RE.exec(src)) !== null) {
    out += esc(src.slice(last, m.index));
    const tok = m[0];
    let cls = '';
    if (m[1]) cls = 't-com';
    else if (m[2] || m[3]) cls = 't-str';
    else if (m[4]) cls = 't-dec';
    else if (m[5]) cls = 't-num';
    else if (m[6]) {
      if (KW.has(tok)) cls = 't-kw';
      else if (CONSTS.has(tok)) cls = 't-const';
      else if (prevWord === 'def' || prevWord === 'class') cls = 't-def';
      else if (BUILTINS.has(tok)) cls = 't-bi';
      else if (/^ *\(/.test(src.slice(m.index + tok.length, m.index + tok.length + 8))) cls = 't-fn';
    }
    prevWord = m[6] ? tok : '';
    out += cls ? '<span class="' + cls + '">' + esc(tok) + '</span>' : esc(tok);
    last = m.index + tok.length;
  }
  return out + esc(src.slice(last));
}

let hlQueued = false;
function renderHighlight() {
  if (hlQueued) return;
  hlQueued = true;
  requestAnimationFrame(() => {
    hlQueued = false;
    // Abschließender Zeilenumbruch, damit eine leere letzte Zeile gleich hoch ist
    hlEl.innerHTML = highlight(codeEl.value) + '\n';
    syncScroll();
  });
}
function syncScroll() {
  hlEl.scrollTop = codeEl.scrollTop;
  hlEl.scrollLeft = codeEl.scrollLeft;
}
codeEl.addEventListener('input', renderHighlight);
codeEl.addEventListener('scroll', syncScroll);

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
  autosave(); renderHighlight();
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

// fetch mit Zeitlimit: ohne WLAN haengt ein normales fetch ewig (Seite wirkt eingefroren)
function fetchT(url, opts, ms) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), ms || 6000);
  return fetch(url, Object.assign({}, opts, { signal: ctl.signal }))
    .finally(() => clearTimeout(timer));
}

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
renderHighlight();

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
    const res = await fetchT('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: code
    }, 10000);
    if (res.ok) {
      setStatus('Läuft auf dem uC …');
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
// Das Board beendet das Programm selbst (ohne Neustart, das WLAN bleibt). Nur
// wenn es nicht reagiert (reine Endlosschleife ohne print/sleep), startet es neu –
// dann verschwindet kurz das WLAN und das iPad muss sich neu verbinden.
async function stopProgram() {
  setStatus('Stoppe …');
  try {
    const res = await fetchT('/api/stop', { method: 'POST' }, 8000);
    let info = {};
    try { info = await res.json(); } catch (e) {}
    if (info.reset) {
      stopPolling();
      setStatus('Board startet neu …');
      logLine('■ Programm reagierte nicht – Board startet neu. Das WLAN ist kurz weg, ' +
              'das iPad verbindet sich gleich wieder.\n', 'sys');
      waitForBoard();
    } else {
      await fetchOutput();   // letzte Ausgaben ("■ Programm gestoppt") holen
      stopPolling();
      setStatus('Gestoppt');
    }
  } catch (e) {
    // Antwort ging verloren (z. B. Board hat neu gestartet)
    stopPolling();
    setStatus('Board startet neu …');
    logLine('■ keine Antwort vom Board – es startet evtl. neu\n', 'sys');
    waitForBoard();
  }
}

// Nach einem Neustart pollt die Seite /api/info, bis das Board wieder da ist.
async function waitForBoard() {
  for (let i = 0; i < 40; i++) {
    await new Promise(r => setTimeout(r, 1500));
    try {
      const res = await fetchT('/api/info', {}, 2500);
      if (res.ok) { setStatus('Bereit'); logLine('✓ Board wieder erreichbar\n', 'sys'); return; }
    } catch (e) { /* noch nicht da */ }
  }
  setStatus('Board nicht erreichbar');
  logLine('✗ Board nicht erreichbar – WLAN prüfen und Seite neu laden\n', 'err');
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
    const res = await fetchT('/api/output?since=' + outputCursor, {}, 5000);
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
      autosave(); renderHighlight();
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
    autosave(); renderHighlight();
    modal.hidden = true;
    setStatus('Datei geladen: ' + file.name);
  };
  reader.readAsText(file);
  fileInput.value = '';
});
