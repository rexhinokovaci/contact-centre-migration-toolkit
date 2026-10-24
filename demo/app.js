// Playground controller. Plain ES module, no build step: Pyodide does the work.
import { createTour } from './tour.js';

const $ = (id) => document.getElementById(id);
const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

const MODULES = ['__init__', 'calltree', 'validate', 'convert', 'lint', 'waves', 'reconcile'];
let py;
let api;
const samples = {};

async function boot() {
  const [tree, inventory, legacy, connect] = await Promise.all(
    ['samples/partner-ivr.yaml', 'samples/numbers.csv', 'samples/legacy_cdr.csv', 'samples/connect_ctr.csv'].map((p) =>
      fetch(p).then((r) => r.text()),
    ),
  );
  Object.assign(samples, { legacy, connect });
  $('tree-src').value = tree;
  $('inventory').value = inventory;

  py = await loadPyodide();
  await py.loadPackage('pyyaml');
  py.FS.mkdirTree('/home/pyodide/ccmt');
  for (const m of MODULES) {
    py.FS.writeFile(`/home/pyodide/ccmt/${m}.py`, await fetch(`ccmt/${m}.py`).then((r) => r.text()));
  }
  py.runPython(await fetch('bridge.py').then((r) => r.text()));
  api = {
    convert: py.globals.get('api_convert'),
    plan: py.globals.get('api_plan'),
    reconcile: py.globals.get('api_reconcile'),
  };
  const version = py.runPython('import sys; sys.version.split()[0]');
  $('py-status').textContent = `Python ${version} ready · ccmt loaded`;
  $('py-status').parentElement.classList.add('ready');
  for (const id of ['run-convert', 'run-plan', 'run-reconcile']) $(id).disabled = false;
  runConvert();
}

// ---- steps ------------------------------------------------------------------------

function showStep(name) {
  document.querySelectorAll('#steps [role=tab]').forEach((t) => {
    t.setAttribute('aria-selected', String(t.dataset.step === name));
    $(`step-${t.dataset.step}`).hidden = t.dataset.step !== name;
  });
}
document.querySelectorAll('#steps [role=tab]').forEach((t) => t.addEventListener('click', () => showStep(t.dataset.step)));

function tag(id, text, kind = '') {
  const el = $(id);
  el.textContent = text;
  el.className = `tag ${kind}`;
}

// ---- convert ----------------------------------------------------------------------

function renderTree(data) {
  const seen = new Set();
  const node = (id, key) => {
    const n = data.nodes[id];
    const keyHtml = key ? `<span class="k">${esc(key)}</span>` : '';
    if (!n) return `<li><span class="tnode ref">${keyHtml}${esc(id)} (missing)</span></li>`;
    if (seen.has(id)) return `<li><span class="tnode ref">${keyHtml}↩ ${esc(id)}</span></li>`;
    seen.add(id);
    const label =
      n.type === 'queue' ? `Queue: ${esc(n.queue)}` :
      n.type === 'transfer' ? `Transfer ${esc(n.number)}` :
      n.type === 'hangup' ? 'Hang up' : esc(id);
    const kids = [];
    if (n.type === 'menu') {
      for (const [k, t] of Object.entries(n.options)) kids.push(node(t, k));
      if (n.timeout) kids.push(node(n.timeout, 'no input'));
    } else if (n.type === 'hours') {
      kids.push(node(n.open, 'open'), node(n.closed, 'closed'));
    } else if (n.next) {
      kids.push(node(n.next, ''));
    }
    return `<li><span class="tnode ${n.type}">${keyHtml}<span class="t">${n.type}</span>${label}</span>${kids.length ? `<ul>${kids.join('')}</ul>` : ''}</li>`;
  };
  return `<ul class="tree">${node(data.entry)}</ul>`;
}

function runConvert() {
  const data = JSON.parse(api.convert($('tree-src').value));
  const out = $('convert-out');
  if (data.error) {
    tag('convert-tag', 'Could not parse', 'bad');
    out.innerHTML = `<ul class="issues"><li class="error">${esc(data.error)}</li></ul>`;
    return;
  }
  const errors = data.issues.filter((i) => i.severity === 'error').length;
  const issues = data.issues.length
    ? `<ul class="issues">${data.issues.map((i) => `<li class="${i.severity}">${i.node ? `<code>${esc(i.node)}</code> ` : ''}${esc(i.message)}</li>`).join('')}</ul>`
    : '<ul class="issues"><li>No issues found.</li></ul>';

  if (!data.flow) {
    tag('convert-tag', `${errors} error(s)`, 'bad');
    out.innerHTML = `<h3 class="h4">Validation</h3>${issues}<h3 class="h4">Call tree</h3>${renderTree(data)}`;
    return;
  }
  tag('convert-tag', data.lint.length ? 'Lint failed' : 'Flow passes lint', data.lint.length ? 'bad' : 'ok');
  const json = JSON.stringify(data.flow, null, 2);
  out.innerHTML = `
    <div class="stats">
      <div class="stat"><b>${data.flow.Actions.length}</b><span>Connect blocks</span></div>
      <div class="stat"><b>${data.placeholders.length}</b><span>placeholders to bind</span></div>
      <div class="stat"><b>${data.dropped.length}</b><span>dead branches dropped</span></div>
    </div>
    <h3 class="h4">Validation</h3>${issues}
    ${data.lint.length ? `<ul class="issues">${data.lint.map((l) => `<li class="error">${esc(l)}</li>`).join('')}</ul>` : ''}
    <h3 class="h4">What callers hear</h3>${renderTree(data)}
    <h3 class="h4">Placeholders</h3><p class="muted">${data.placeholders.map((p) => `<code>\${${esc(p)}}</code>`).join(' ')}</p>
    <div class="json-wrap">
      <div class="json-actions"><h3 class="h4" style="margin-right:auto">Generated flow</h3>
        <button class="ghost-btn small" id="copy-flow" type="button">Copy</button>
        <button class="ghost-btn small" id="dl-flow" type="button">Download</button></div>
      <pre class="code">${esc(json)}</pre>
    </div>`;
  $('copy-flow').onclick = async () => {
    try {
      await navigator.clipboard.writeText(json);
      $('copy-flow').textContent = 'Copied';
    } catch {
      $('copy-flow').textContent = 'Blocked';
    }
  };
  $('dl-flow').onclick = () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([json], { type: 'application/json' }));
    a.download = 'main-ivr.json';
    a.click();
    URL.revokeObjectURL(a.href);
  };
}
$('run-convert').addEventListener('click', runConvert);

// ---- plan -------------------------------------------------------------------------

function runPlan() {
  const data = JSON.parse(
    api.plan($('inventory').value, $('start').value, $('holidays').value, Number($('bake').value), Number($('share').value)),
  );
  const out = $('plan-out');
  if (data.error) {
    tag('plan-tag', 'Invalid inventory', 'bad');
    out.innerHTML = `<ul class="issues"><li class="error">${esc(data.error)}</li></ul>`;
    return;
  }
  tag('plan-tag', `${data.waves.length} waves · ${data.total.toLocaleString('en-GB')} calls/day`, 'ok');
  out.innerHTML = `<ol class="timeline">${data.waves
    .map(
      (w) => `<li class="wave ${w.name.startsWith('Critical') ? 'critical' : ''}">
        <div class="wave-top"><b>${esc(w.name)}</b><span>${esc(w.weekday)} ${esc(w.cutover)} · ${w.volume.toLocaleString('en-GB')} calls/day · ${w.share}%</span></div>
        <div class="share"><i style="width:${Math.max(2, w.share)}%"></i></div>
        <ul>${w.numbers
          .map((n) => `<li><span><code>${esc(n.did)}</code> ${esc(n.label)}${n.critical ? ' · critical' : ''}</span><span>${n.calls}/day · ${esc(n.group)}</span></li>`)
          .join('')}</ul>
      </li>`,
    )
    .join('')}</ol>`;
}
$('run-plan').addEventListener('click', runPlan);

// ---- reconcile ---------------------------------------------------------------------

function fileInput(inputId, nameId, key) {
  $(inputId).addEventListener('change', async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    samples[key] = await f.text();
    $(nameId).textContent = `${f.name} (${(f.size / 1024).toFixed(0)} KB)`;
  });
}
fileInput('legacy-file', 'legacy-name', 'legacy');
fileInput('connect-file', 'connect-name', 'connect');

const VERDICT_COPY = {
  pass: ['Ready to decommission the legacy route', 'Every number is within thresholds.'],
  investigate: ['Investigate before the next wave', 'Some numbers drifted. Check routing and number re-pointing.'],
  rollback: ['Roll back at least one number', 'Abandonment rose beyond the rollback threshold. Point it back at the legacy platform.'],
};

function runReconcile() {
  const data = JSON.parse(api.reconcile(samples.legacy, samples.connect));
  const out = $('reconcile-out');
  if (data.error) {
    out.innerHTML = `<ul class="issues"><li class="error">${esc(data.error)}</li></ul>`;
    return;
  }
  const [title, sub] = VERDICT_COPY[data.overall];
  const d = (v, unit, badAbove) => `<span class="${v > badAbove ? 'delta-bad' : ''}">${v > 0 ? '+' : ''}${v}${unit}</span>`;
  out.innerHTML = `
    <div class="verdict ${data.overall}"><span class="pill ${data.overall}">${data.overall}</span><div><strong>${title}</strong><span>${sub}</span></div></div>
    <div class="table-wrap"><table class="table">
      <thead><tr><th>Number</th><th class="num">Calls/day</th><th class="num">Abandon %</th><th class="num">Avg wait</th><th>Verdict</th><th>Why</th></tr></thead>
      <tbody>${data.rows
        .map(
          (r) => `<tr>
          <td>${esc(r.did)}</td>
          <td class="num">${r.legacy.per_day} → ${r.connect.per_day}<span class="sub">${d(r.volume_delta_pct, '%', 10)}</span></td>
          <td class="num">${r.legacy.abandonment} → ${r.connect.abandonment}<span class="sub">${d(r.abandonment_delta_pts, ' pts', 2)}</span></td>
          <td class="num">${r.legacy.wait}s → ${r.connect.wait}s<span class="sub">${d(r.wait_delta_s, 's', 30)}</span></td>
          <td><span class="pill ${r.verdict}">${r.verdict}</span></td>
          <td class="reasons">${esc(r.reasons.join('; ') || '—')}</td></tr>`,
        )
        .join('')}</tbody></table></div>`;
}
$('run-reconcile').addEventListener('click', runReconcile);

// ---- tour --------------------------------------------------------------------------

const tour = createTour('migration', [
  {
    target: '.kicker',
    title: 'Real Python, in your browser',
    body: 'Pyodide loads the actual <code>ccmt</code> package from this repo. Same code as the CLI and the tests.',
  },
  {
    target: '#steps',
    title: 'Three steps of a migration',
    body: '<b>Convert</b> the partner IVR, <b>plan</b> which numbers move when, then <b>reconcile</b> traffic once they have.',
    before: () => showStep('convert'),
  },
  {
    target: '#tree-src',
    title: 'The legacy call tree',
    body: 'An outsourced partner\'s IVR, normalised to YAML. Try breaking it: point an option at a node that doesn\'t exist, or add a seventh menu option.',
  },
  {
    target: '#convert-out',
    title: 'Validation and conversion',
    body: 'Dead branches are found and dropped, menu retries are unrolled into separate input blocks, and the generated flow is linted with the same rules as the Connect platform repo.',
  },
  {
    target: '#step-plan',
    title: 'Cutover waves',
    body: 'Port groups move together, the smallest non-critical group goes first, critical lines go last, and nothing moves on a Friday or a bank holiday.',
    before: () => {
      showStep('plan');
      runPlan();
    },
  },
  {
    target: '#step-reconcile',
    title: 'Did it work?',
    body: 'Compares legacy and Connect traffic per number. The samples include a number that was never re-pointed (volume drop) and one with an abandonment spike (rollback).',
    before: () => {
      showStep('reconcile');
      runReconcile();
    },
  },
]);
$('tour-btn').addEventListener('click', () => tour.open());

boot()
  .then(() => tour.autoStart(300))
  .catch((err) => {
    $('py-status').textContent = `Failed to load Python: ${err.message}`;
    console.error(err);
  });
