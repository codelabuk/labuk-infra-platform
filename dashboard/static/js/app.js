// ── demo data ──────────────────────────────────────────────────────────────
const DEMO_LOGS = `26/04/04 09:10:05 INFO SparkContext: Running Spark version 3.5.3
26/04/04 09:10:05 INFO ResourceUtils: ==============================================================
26/04/04 09:10:06 INFO SparkContext: Submitted application: WordCount
26/04/04 09:10:07 INFO TaskSchedulerImpl: Starting task 0.0 in stage 0.0 (TID 0)
26/04/04 09:10:08 INFO DAGScheduler: Job 0 finished: collect at WordCount.scala:18, took 1.234s
(Hello,3) (Spark,2) (Docker,1) (CodeLabuk,1)
26/04/04 09:10:09 INFO SparkContext: Successfully stopped SparkContext`;

// ── presets ────────────────────────────────────────────────────────────────
const PRESETS = {
  'scala-pi': {
    name: 'spark-pi', type: 'Scala',
    jar:  'local:///opt/spark/examples/jars/spark-examples_2.12-3.5.1.jar',
    mc:   'org.apache.spark.examples.SparkPi',
    img:  'apache/spark:3.5.1', sv: '3.5.1',
    dc: 1, dm: '512m', ei: 1, ec: 1, em: '512m'
  },
  'scala-wc': {
    name: 'scala-word-count', type: 'Scala',
    jar:  'local:///opt/spark/work-dir/jobs/WordCount.jar',
    mc:   'com.codelabuk.WordCount',
    img:  'spark-jobs:latest', sv: '3.5.3',
    dc: 1, dm: '512m', ei: 1, ec: 1, em: '512m'
  },
  'python-counter': {
    name: 'python-counter', type: 'Python',
    jar:  'local:///opt/spark/work-dir/jobs/simple_counter.py',
    mc:   '',
    img:  'spark-jobs:latest', sv: '3.5.3',
    dc: 1, dm: '512m', ei: 1, ec: 1, em: '512m'
  },
  'clear': {
    name: '', type: 'Scala', jar: '', mc: '',
    img:  'apache/spark:3.5.1', sv: '3.5.1',
    dc: 1, dm: '512m', ei: 1, ec: 1, em: '512m'
  }
};

// ── state ──────────────────────────────────────────────────────────────────
let liveMode = false;
let currentLogPod = null;

// ── navigation ─────────────────────────────────────────────────────────────
function showPage(name, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  if (el) el.classList.add('active');
}

// ── connection status ──────────────────────────────────────────────────────
function setConn(state, msg) {
  const pill = document.getElementById('connPill');
  const txt  = document.getElementById('connText');
  pill.className = 'conn-pill ' + state;
  txt.textContent = msg;
}

// ── namespace loader ───────────────────────────────────────────────────────
async function loadNamespaces() {
  try {
    const res  = await fetch('/api/namespaces', { signal: AbortSignal.timeout(3000) });
    const list = await res.json();
    const sel  = document.getElementById('nsSelect');
    const cur  = sel.value;
    sel.innerHTML = '';
    list.forEach(n => {
      const o = document.createElement('option');
      o.value = n; o.textContent = n;
      if (n === cur) o.selected = true;
      sel.appendChild(o);
    });
  } catch (_) { /* keep current dropdown */ }
}

// ── refresh ────────────────────────────────────────────────────────────────
async function refresh() {
  const ns = document.getElementById('nsSelect').value;
  try {
    const [pr, ar] = await Promise.all([
      fetch(`/api/pods?namespace=${ns}`,       { signal: AbortSignal.timeout(5000) }),
      fetch(`/api/spark-apps?namespace=${ns}`, { signal: AbortSignal.timeout(5000) })
    ]);
    if (!pr.ok || !ar.ok) throw new Error('API error');
    const podData = await pr.json();
    const apps    = await ar.json();
    liveMode = true;
    setConn('live', 'Live');
    const allPods = renderPods(podData);
    const appList = Array.isArray(apps) ? apps : (apps.items || []);
    renderApps(appList);
    updateMetrics(allPods, appList);
    loadNamespaces();
  } catch (_) {
    liveMode = false;
    setConn('error', 'Offline');
  }
  document.getElementById('lastRefresh').textContent =
    'Refreshed ' + new Date().toLocaleTimeString();
}

// ── metrics ────────────────────────────────────────────────────────────────
function updateMetrics(pods, apps) {
  const allPods = Array.isArray(pods) ? pods : [];
  const allApps = Array.isArray(apps) ? apps : [];

  const running    = allPods.filter(p => (p.status || '').toLowerCase() === 'running').length;
  const activeApps = allApps.filter(a => (a.state  || '').toUpperCase() === 'RUNNING').length;
  const failedPods = allPods.filter(p => (p.status || '').toLowerCase() === 'failed').length;
  const failedApps = allApps.filter(a => (a.state  || '').toUpperCase() === 'FAILED').length;

  document.getElementById('m-total').textContent   = allPods.length;
  document.getElementById('m-running').textContent = running;
  document.getElementById('m-apps').textContent    = activeApps;
  document.getElementById('m-failed').textContent  = failedPods + failedApps;

  const sparkPodCount = allPods.filter(p =>
    p.labels && ('spark-role' in p.labels || 'spark-app-name' in p.labels)
  ).length;
  const infraPodCount = allPods.length - sparkPodCount;

  document.getElementById('sparkPodsHint').textContent = sparkPodCount + ' spark pods';
  document.getElementById('infraPodsHint').textContent = infraPodCount + ' pods';
  document.getElementById('appsHint').textContent      = allApps.length + ' total';
}

// ── badge helpers ──────────────────────────────────────────────────────────
function statusBadge(s) {
  s = (s || '').toLowerCase();
  const map = {
    running: 'running', completed: 'completed', succeeded: 'completed',
    pending: 'pending', containercreating: 'pending',
    failed: 'failed', error: 'failed'
  };
  const cls = map[s] || 'unknown';
  return `<span class="badge badge-${cls}"><span class="badge-dot"></span>${s || 'unknown'}</span>`;
}

function typeBadge(t) {
  const cls = { Scala: 'scala', Python: 'python', Java: 'java' }[t] || 'unknown';
  return `<span class="badge badge-${cls}">${t || '—'}</span>`;
}

function fmtDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
  });
}

function fmtLabel(l) {
  if (!l || !Object.keys(l).length) return '—';
  return l['spark-role'] || l['app'] || Object.values(l)[0] || '—';
}

// ── render pods ────────────────────────────────────────────────────────────
function renderPods(data) {
  const sparkJobs = data.sparkJobs    || (Array.isArray(data) ? data : []);
  const infra     = data.infrastructure || [];
  const all       = data.all          || (Array.isArray(data) ? data : sparkJobs.concat(infra));

  renderPodTable('sparkJobsTbody', sparkJobs, 'No Spark job pods running');
  renderPodTable('infraTbody',     infra,     'No infrastructure pods');
  return all;
}

function renderPodTable(tbodyId, pods, emptyMsg) {
  const tb = document.getElementById(tbodyId);
  if (!tb) return;
  if (!pods || !pods.length) {
    tb.innerHTML = `<tr class="empty-row"><td colspan="6">${emptyMsg}</td></tr>`;
    return;
  }
  tb.innerHTML = pods.map(p => `
    <tr>
      <td style="font-family:monospace;font-size:12px" title="${p.name}">${p.name}</td>
      <td>${statusBadge(p.status)}</td>
      <td style="color:var(--text2)">${fmtLabel(p.labels)}</td>
      <td style="color:var(--text3)">${p.node || '—'}</td>
      <td style="color:var(--text3)">${fmtDate(p.created)}</td>
      <td>
        <button class="btn btn-sm" onclick="openLogs('${p.name}')">logs</button>
        <button class="btn btn-sm btn-danger" style="margin-left:4px"
                onclick="deletePod('${p.name}')">del</button>
      </td>
    </tr>`).join('');
}

// ── render apps ────────────────────────────────────────────────────────────
function renderApps(apps) {
  const tb = document.getElementById('appsTbody');
  if (!apps || !apps.length) {
    tb.innerHTML = '<tr class="empty-row"><td colspan="6">No SparkApplications found — submit a job from Deploy job page</td></tr>';
    return;
  }
  tb.innerHTML = apps.map(a => `
    <tr>
      <td style="font-family:monospace;font-size:12px" title="${a.name}">${a.name}</td>
      <td>${statusBadge(a.state)}</td>
      <td>${typeBadge(a.type)}</td>
      <td style="color:var(--text3);font-size:12px" title="${a.image || ''}">${(a.image || '—').replace('apache/', '')}</td>
      <td style="color:var(--text3)">${fmtDate(a.created)}</td>
      <td><button class="btn btn-sm btn-danger" onclick="deleteApp('${a.name}')">delete</button></td>
    </tr>`).join('');
}

// ── log drawer ─────────────────────────────────────────────────────────────
function openLogs(podName) {
  currentLogPod = podName;
  document.getElementById('logPodName').textContent = podName;
  document.getElementById('logBody').textContent    = 'Loading…';
  document.getElementById('logDrawer').style.display = 'flex';
  fetchLogs(podName);
}

function closeLogDrawer() {
  document.getElementById('logDrawer').style.display = 'none';
  currentLogPod = null;
}

function refreshLogs() {
  if (currentLogPod) fetchLogs(currentLogPod);
}

async function fetchLogs(podName) {
  const body = document.getElementById('logBody');
  if (!liveMode) {
    body.textContent = DEMO_LOGS;
    return;
  }
  const ns = document.getElementById('nsSelect').value;
  try {
    const res  = await fetch(`/api/pods/${podName}/logs?namespace=${ns}`,
                             { signal: AbortSignal.timeout(10000) });
    const data = await res.json();
    body.textContent = data.logs || 'No logs available.';
    body.scrollTop   = body.scrollHeight;
  } catch (e) {
    body.textContent = 'Could not fetch logs: ' + e.message;
  }
}

// ── delete ─────────────────────────────────────────────────────────────────
async function deletePod(name) {
  if (!liveMode) { toast('Not connected to API', 'error'); return; }
  if (!confirm(`Delete pod "${name}"?`)) return;
  const ns = document.getElementById('nsSelect').value;
  await fetch(`/api/pods/${name}?namespace=${ns}`, { method: 'DELETE' });
  toast(`Deleted pod "${name}"`, 'success');
  refresh();
}

async function deleteApp(name) {
  if (!liveMode) { toast('Not connected to API', 'error'); return; }
  if (!confirm(`Delete SparkApplication "${name}"?`)) return;
  const ns = document.getElementById('nsSelect').value;
  await fetch(`/api/spark-apps/${name}?namespace=${ns}`, { method: 'DELETE' });
  toast(`Deleted "${name}"`, 'success');
  refresh();
}

// ── deploy ─────────────────────────────────────────────────────────────────
function toggleMainClass() {
  const t     = document.getElementById('f-type').value;
  const group = document.getElementById('mainClassGroup');
  const input = document.getElementById('f-mc');
  if (t === 'Python' || t === 'R') {
    group.style.display = 'none';
    input.value = '';
  } else {
    group.style.display = 'block';
  }
}

function applyPreset(key) {
  const p = PRESETS[key];
  if (!p) return;
  document.getElementById('f-name').value  = p.name;
  document.getElementById('f-type').value  = p.type;
  document.getElementById('f-jar').value   = p.jar;
  document.getElementById('f-mc').value    = p.mc;
  document.getElementById('f-image').value = p.img;
  document.getElementById('f-sv').value    = p.sv;
  document.getElementById('f-dc').value    = p.dc;
  document.getElementById('f-dm').value    = p.dm;
  document.getElementById('f-ei').value    = p.ei;
  document.getElementById('f-ec').value    = p.ec;
  document.getElementById('f-em').value    = p.em;
  toggleMainClass();
  document.getElementById('yamlPre').style.display = 'none';
}

function getForm() {
  return {
    name:              document.getElementById('f-name').value.trim(),
    type:              document.getElementById('f-type').value,
    jarPath:           document.getElementById('f-jar').value.trim(),
    mainClass:         document.getElementById('f-mc').value.trim(),
    image:             document.getElementById('f-image').value.trim(),
    namespace:         document.getElementById('f-ns').value.trim() || 'spark',
    sparkVersion:      document.getElementById('f-sv').value.trim(),
    driverCores:       document.getElementById('f-dc').value,
    driverMemory:      document.getElementById('f-dm').value.trim(),
    executorInstances: document.getElementById('f-ei').value,
    executorCores:     document.getElementById('f-ec').value,
    executorMemory:    document.getElementById('f-em').value.trim()
  };
}

function buildYaml(d) {
  const mc = d.mainClass ? `  mainClass: ${d.mainClass}\n` : '';
  return `apiVersion: sparkoperator.k8s.io/v1beta2
kind: SparkApplication
metadata:
  name: ${d.name || 'my-spark-job'}
  namespace: ${d.namespace}
spec:
  type: ${d.type}
  mode: cluster
  image: ${d.image}
  imagePullPolicy: Never
${mc}  mainApplicationFile: ${d.jarPath}
  sparkVersion: "${d.sparkVersion}"
  restartPolicy:
    type: Never
  driver:
    cores: ${d.driverCores}
    memory: "${d.driverMemory}"
    serviceAccount: spark
  executor:
    cores: ${d.executorCores}
    instances: ${d.executorInstances}
    memory: "${d.executorMemory}"`;
}

function previewYaml() {
  const pre = document.getElementById('yamlPre');
  pre.textContent = buildYaml(getForm());
  pre.style.display = pre.style.display === 'none' ? 'block' : 'none';
}

async function submitJob() {
  const d = getForm();
  if (!d.name)    { toast('Job name is required', 'error'); return; }
  if (!d.jarPath) { toast('JAR / application file is required', 'error'); return; }
  if ((d.type === 'Scala' || d.type === 'Java') && !d.mainClass) {
    toast('Main class is required for Scala/Java', 'error'); return;
  }

  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span> Submitting…';
  document.getElementById('submitStatus').textContent = '';

  if (!liveMode) {
    await new Promise(r => setTimeout(r, 700));
    btn.disabled = false;
    btn.textContent = '▶ Submit job';
    toast('Not connected — run python app.py and refresh first', 'error');
    return;
  }

  try {
    const res = await fetch('/api/spark-apps', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(d)
    });
    if (res.ok) {
      toast(`Job "${d.name}" submitted`, 'success');
      setTimeout(() => {
        showPage('apps', document.getElementById('nav-apps'));
        refresh();
      }, 1500);
    } else {
      let msg = res.statusText;
      try { const e = await res.json(); msg = e.message || msg; } catch(_) {}
      toast(`Error: ${msg}`, 'error');
    }
  } catch (e) {
    toast('Cannot reach Flask API: ' + e.message, 'error');
  }
  btn.disabled = false;
  btn.textContent = '▶ Submit job';
}

// ── toast ──────────────────────────────────────────────────────────────────
function toast(msg, type) {
  const stack = document.getElementById('toastStack');
  const t = document.createElement('div');
  t.className   = `toast toast-${type}`;
  t.textContent = msg;
  stack.appendChild(t);
  requestAnimationFrame(() => t.classList.add('show'));
  setTimeout(() => {
    t.classList.remove('show');
    setTimeout(() => t.remove(), 250);
  }, 3500);
}

// ── auto-refresh ───────────────────────────────────────────────────────────
setInterval(() => { if (liveMode) refresh(); }, 30000);

// ── init ──────────────────────────────────────────────────────────────────
async function init() {
  await AppConfig.load();
  refresh();
}

init();
