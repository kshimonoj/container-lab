// app.js — CX ContainerLab GUI v5
'use strict';

const API = '';

// RADIUS (linux) node defaults. Used by the palette's FreeRADIUS container.
const RADIUS_IMAGE = 'freeradius/freeradius-server:latest';
const RADIUS_BINDS = [
  '/home/kshimono/claude/cx-clab/configs/freeradius/clients.conf:/etc/freeradius/clients.conf',
  '/home/kshimono/claude/cx-clab/configs/freeradius/authorize:/etc/freeradius/mods-config/files/authorize',
];

// Generate a unique node id (base, base2, base3, ...)
function uniqueNodeId(base) {
  if (!topology.nodes.find(n => n.id === base)) return base;
  let i = 2;
  while (topology.nodes.find(n => n.id === `${base}${i}`)) i++;
  return `${base}${i}`;
}

// Derive role from image (visually distinguish RADIUS nodes & restore on import round-trip)
function roleFromNode(nodeData) {
  if (nodeData.role) return nodeData.role;
  if (/freeradius|radius/i.test(nodeData.image || '')) return 'radius';
  return '';
}

// ── State ────────────────────────────────────────────────────
let cy           = null;
let topology     = { nodes: [], links: [] };
let selectedNode = null;
let selectedEdge = null;
let linkMode     = false;
let linkSrcId    = null;
let syncMode     = false;
let termViewMode = 'tabs';   // 'tabs' | 'split' | 'window'
let healthPoller = null;

// terminals: { nodeId: { ws, term, fitAddon, pane, tab } }
const terminals = {};

// nodeMeta: { nodeId: { kind, image, mgmt_ip, state, status } } — filled when loading a running lab
let nodeMeta = {};
let runningLabsCache = [];   // result of /api/labs/running

// ── Init ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  initCytoscape();
  initLogToggle();
  initTermViewModeButtons();
  initSplitters();
  await loadTemplates();
  bindButtons();
  bindExecBar();
  bindLabEnhancements();
  await loadRunningLabs();
  log('CX ContainerLab GUI v6 ready', 'info');
  // auto-restore a deployed lab if one exists
  await restoreDeployedLab();
});

async function restoreDeployedLab() {
  const labName = currentLabName();
  try {
    const res = await fetch(`${API}/api/labs/${labName}/topology`);
    if (!res.ok) return;  // nothing to do if the lab does not exist
    const data = await res.json();
    if (data.topology && data.topology.nodes.length > 0) {
      loadTopology(data.topology);
      log(`🔄 Restored deployed lab: ${labName}`, 'success');
      if (data.is_deployed) {
        setStatus('running');
        await refreshStatus();
        startHealthPolling();
      }
    }
  } catch(e) {
    // restore failure is non-fatal, ignore
  }
}

// ── ANSI strip ───────────────────────────────────────────────
function stripAnsi(str) {
  // eslint-disable-next-line no-control-regex
  return String(str).replace(/\x1b\[[0-9;]*[mGKHF]/g, '').replace(/\x1b\[[0-9;]*[A-Za-z]/g, '');
}

function escapeHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Cytoscape ────────────────────────────────────────────────
function initCytoscape() {
  cy = cytoscape({
    container: document.getElementById('cy'),
    style: [
      { selector: 'node', style: {
        'background-color': '#21262d', 'border-color': '#00d4aa', 'border-width': 2,
        'label': 'data(label)', 'color': '#e6edf3',
        'font-family': 'JetBrains Mono', 'font-size': 11,
        'text-valign': 'bottom', 'text-margin-y': 6,
        'width': 54, 'height': 54, 'shape': 'rectangle',
      }},
      { selector: 'node[kind="linux"]', style: {
        'border-color': '#58a6ff', 'shape': 'ellipse',
      }},
      { selector: 'node[role="radius"]', style: {
        'border-color': '#d29922', 'background-color': '#2d2410', 'shape': 'round-diamond',
      }},
      { selector: 'node.link-src', style: {
        'border-color': '#e3b341', 'border-width': 3, 'background-color': '#2e2200',
      }},
      { selector: 'node.selected', style: {
        'border-color': '#58a6ff', 'border-width': 3, 'background-color': '#1a2f3a',
      }},
      { selector: 'node.running', style: { 'border-color': '#3fb950' }},
      { selector: 'edge', style: {
        'width': 2, 'line-color': '#30363d', 'target-arrow-shape': 'none',
        'curve-style': 'bezier',
        'label': 'data(label)', 'font-family': 'JetBrains Mono', 'font-size': 9,
        'color': '#8b949e', 'text-rotation': 'autorotate',
        'text-wrap': 'wrap',
      }},
      { selector: 'edge.selected', style: { 'line-color': '#58a6ff', 'width': 3 }},
    ],
    layout: { name: 'preset' },
    userZoomingEnabled: true, userPanningEnabled: true, boxSelectionEnabled: false,
  });

  cy.on('dblclick', 'node', (e) => {
    openTerminal(currentLabName(), e.target.id(), e.target.data('kind'));
  });

  cy.on('tap', 'node', (e) => {
    if (linkMode) { handleLinkModeClick(e.target.id()); return; }
    hideCtxMenus();
    selectNode(e.target);
  });

  cy.on('tap', 'edge', (e) => {
    hideCtxMenus();
    cy.edges().removeClass('selected');
    e.target.addClass('selected');
    selectedEdge = e.target;
    selectedNode = null;
  });

  cy.on('tap', (e) => {
    if (e.target === cy) {
      hideCtxMenus();
      deselectAll();
      if (linkMode) cancelLinkMode();
    }
  });

  cy.on('cxttap', 'node', (e) => {
    selectedNode = e.target;
    const pos = e.renderedPosition;
    showCtxMenu('ctx-menu', pos.x, pos.y);
  });

  cy.on('cxttap', 'edge', (e) => {
    selectedEdge = e.target;
    const pos = e.renderedPosition;
    showCtxMenu('ctx-edge-menu', pos.x, pos.y);
  });

  cy.on('dragfree', 'node', () => syncTopologyFromCy());

  // close context menus on ESC
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') hideCtxMenus();
  });
}

// ── Context menus ────────────────────────────────────────────
function showCtxMenu(menuId, x, y) {
  hideCtxMenus();
  const menu = document.getElementById(menuId);
  menu.classList.remove('hidden');
  // keep the menu within the viewport
  const maxX = window.innerWidth  - menu.offsetWidth  - 10;
  const maxY = window.innerHeight - menu.offsetHeight - 10;
  menu.style.left = Math.max(5, Math.min(x, maxX)) + 'px';
  menu.style.top  = Math.max(5, Math.min(y, maxY)) + 'px';

  // close on the next click/tap (one-shot, excluding clicks inside the menu)
  const closeHandler = (e) => {
    if (!menu.contains(e.target)) {
      hideCtxMenus();
      document.removeEventListener('pointerup', closeHandler, true);
      document.removeEventListener('click', closeHandler, true);
    }
  };
  // register with a small delay so the opening click itself does not close it
  setTimeout(() => {
    document.addEventListener('pointerup', closeHandler, true);
    document.addEventListener('click', closeHandler, true);
  }, 100);
}
function hideCtxMenus() {
  document.getElementById('ctx-menu').classList.add('hidden');
  document.getElementById('ctx-edge-menu').classList.add('hidden');
}

// ── Link mode ────────────────────────────────────────────────
function enterLinkMode(srcId) {
  linkMode = true; linkSrcId = srcId || null;
  const banner = document.getElementById('link-mode-banner');
  banner.classList.remove('hidden');
  document.getElementById('btn-add-link').classList.add('active');
  if (srcId) {
    cy.getElementById(srcId).addClass('link-src');
    banner.textContent = `🔗 LINK MODE: "${srcId}" selected — click target node`;
  } else {
    banner.textContent = '🔗 LINK MODE: click the source node';
  }
}
function cancelLinkMode() {
  linkMode = false;
  cy.nodes().removeClass('link-src');
  document.getElementById('link-mode-banner').classList.add('hidden');
  document.getElementById('btn-add-link').classList.remove('active');
  linkSrcId = null;
}
function handleLinkModeClick(nodeId) {
  if (!linkSrcId) {
    linkSrcId = nodeId;
    cy.getElementById(nodeId).addClass('link-src');
    document.getElementById('link-mode-banner').textContent =
      `🔗 LINK MODE: "${nodeId}" selected — click target node`;
  } else {
    if (linkSrcId === nodeId) { cancelLinkMode(); return; }
    openAddLinkModal(linkSrcId, nodeId);
    cancelLinkMode();
  }
}

// ── Topology ─────────────────────────────────────────────────
function currentLabName() {
  return document.getElementById('lab-name').value.trim() || 'mylab';
}

function addNodeToCanvas(nodeData) {
  if (topology.nodes.find(n => n.id === nodeData.id)) {
    log(`Node ${nodeData.id} already exists`, 'warn'); return;
  }
  topology.nodes.push(nodeData);
  cy.add({
    group: 'nodes',
    data: {
      id: nodeData.id,
      label: nodeData.label || nodeData.id,
      kind: nodeData.kind || 'vr-aoscx',
      role: roleFromNode(nodeData),
    },
    position: { x: nodeData.x || 300, y: nodeData.y || 250 },
  });
  document.getElementById('canvas-hint').style.display = 'none';
  updateNodeList(); updateExecNodeSelect();
}

function addLinkToCanvas(srcId, dstId, srcIf, dstIf, label) {
  const src_if = srcIf || '1/1/1';
  const dst_if = dstIf || '1/1/1';
  const edgeId = `e_${srcId}_${src_if.replace(/\//g,'_')}_${dstId}_${dst_if.replace(/\//g,'_')}`;
  if (cy.getElementById(edgeId).length > 0) return;
  topology.links.push({ source: srcId, target: dstId, src_if, dst_if });

  // label: always show interface IDs; append a custom label if present
  const ifLabel = `${src_if}↔${dst_if}`;
  let displayLabel;
  if (label && label.trim() && label.trim() !== ifLabel) {
    displayLabel = `${label.trim()}\n${ifLabel}`;
  } else {
    displayLabel = ifLabel;
  }

  cy.add({
    group: 'edges',
    data: { id: edgeId, source: srcId, target: dstId, label: displayLabel },
  });
}

function loadTopology(topo) {
  cy.elements().remove();
  topology = { nodes: [], links: [] };
  topo.nodes.forEach(n => addNodeToCanvas(n));
  topo.links.forEach(l => addLinkToCanvas(l.source, l.target, l.src_if, l.dst_if, l.label));
  cy.fit(undefined, 50);
  document.getElementById('canvas-hint').style.display = 'none';
}

function syncTopologyFromCy() {
  topology.nodes = topology.nodes.map(n => {
    const cyNode = cy.getElementById(n.id);
    if (cyNode.length > 0) {
      const pos = cyNode.position();
      return { ...n, x: pos.x, y: pos.y };
    }
    return n;
  });
}

function clearCanvas() {
  cy.elements().remove();
  topology = { nodes: [], links: [] };
  document.getElementById('canvas-hint').style.display = 'block';
  updateNodeList(); updateExecNodeSelect();
}

function selectNode(cyNode) {
  cy.nodes().removeClass('selected');
  cyNode.addClass('selected');
  selectedNode = cyNode; selectedEdge = null;
  showNodeDetail(cyNode.id());
}
function deselectAll() {
  cy.nodes().removeClass('selected');
  cy.edges().removeClass('selected');
  selectedNode = null; selectedEdge = null;
  hideNodeDetail();
}

// ── Node list ────────────────────────────────────────────────
function updateNodeList() {
  const list = document.getElementById('node-list');
  list.innerHTML = '';
  topology.nodes.forEach(n => {
    const item = document.createElement('div');
    item.className = 'node-item';
    item.innerHTML = `
      <div class="node-dot" id="dot-${n.id}" title="unknown"></div>
      <span class="node-kind-badge ${n.kind === 'linux' ? 'kind-linux' : 'kind-cx'}">${n.kind === 'linux' ? 'PC' : 'CX'}</span>
      <span>${n.label || n.id}</span>
    `;
    item.onclick = () => {
      const cyNode = cy.getElementById(n.id);
      if (cyNode.length > 0) selectNode(cyNode);
    };
    list.appendChild(item);
  });
}

function updateExecNodeSelect() {
  const sel = document.getElementById('exec-node-select');
  sel.innerHTML = topology.nodes
    .filter(n => n.kind !== 'linux')
    .map(n => `<option value="${n.id}">${n.label || n.id}</option>`)
    .join('');
}

function updateNodeStatus(containers) {
  let healthyCount = 0;
  let totalCount   = 0;
  containers = containers || [];

  topology.nodes.forEach(n => {
    const dot = document.getElementById(`dot-${n.id}`);
    if (!dot) return;
    const labName = currentLabName();
    const containerName = `clab-${labName}-${n.id}`;
    const c = containers.find(c =>
      (c.Names || '').replace(/^\//, '') === containerName ||
      (c.Names || '').includes(containerName)
    );

    totalCount++;
    const isLinux = n.kind === 'linux';

    if (c) {
      const health = (c.Health || '').toLowerCase();
      // PCs have no health check, so running = healthy
      const effectiveHealthy = isLinux
        ? (c.State === 'running')
        : (c.State === 'running' && health === 'healthy');

      if (effectiveHealthy) {
        dot.style.background = '#3fb950';
        dot.title = isLinux ? 'running ✅' : 'running / healthy ✅';
        cy.getElementById(n.id).addClass('running');
        healthyCount++;
      } else if (c.State === 'running') {
        dot.style.background = '#e3b341';
        dot.title = `running / ${health || 'starting'} ⏳`;
        cy.getElementById(n.id).removeClass('running');
      } else {
        dot.style.background = '#f85149';
        dot.title = 'stopped ❌';
        cy.getElementById(n.id).removeClass('running');
      }
    } else {
      dot.style.background = '#484f58';
      dot.title = 'not deployed';
    }
  });

  const badge = document.getElementById('health-badge');
  if (badge) {
    badge.textContent = `${healthyCount}/${totalCount} ready`;
    badge.style.color = (healthyCount === totalCount && totalCount > 0) ? '#3fb950' : '#e3b341';
  }

  return { healthyCount, totalCount };
}

// ── Health polling ────────────────────────────────────────────
function startHealthPolling() {
  stopHealthPolling();
  log('🔄 Polling node health every 10s...', 'info');
  const tick = async () => {
    try {
      const res  = await fetch(`${API}/api/labs/${currentLabName()}/status`);
      const data = await res.json();
      const { healthyCount, totalCount } = updateNodeStatus(data.containers);
      if (healthyCount === totalCount && totalCount > 0) {
        log(`✅ All ${totalCount} nodes are ready! Terminals are accessible.`, 'deploy');
        stopHealthPolling();
        setStatus('running');
      }
    } catch(e) {}
  };
  tick();  // run once immediately, then every 10s
  healthPoller = setInterval(tick, 10000);
}
function stopHealthPolling() {
  if (healthPoller) { clearInterval(healthPoller); healthPoller = null; }
}

// ── Templates ────────────────────────────────────────────────
async function loadTemplates() {
  try {
    const res  = await fetch(`${API}/api/templates`);
    const data = await res.json();
    const sel  = document.getElementById('template-select');
    data.templates.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.id; opt.textContent = t.name;
      sel.appendChild(opt);
    });
  } catch(e) { log('Failed to load templates: ' + e, 'error'); }
}

// ── Log ──────────────────────────────────────────────────────
function initLogToggle() {
  document.getElementById('btn-toggle-log').onclick = () => {
    const panel = document.getElementById('log-panel');
    const btn   = document.getElementById('btn-toggle-log');
    panel.classList.toggle('collapsed');
    btn.textContent = panel.classList.contains('collapsed') ? '▲' : '▼';
  };
}

function log(msg, level = 'info') {
  const out = document.getElementById('log-output');
  const ts  = new Date().toLocaleTimeString('ja-JP', { hour12: false });
  // strip ANSI escapes
  const clean = escapeHtml(stripAnsi(String(msg)));
  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.innerHTML = `<span class="log-ts">[${ts}]</span><span class="log-msg log-${level}">${clean}</span>`;
  out.appendChild(entry);
  out.scrollTop = out.scrollHeight;
  // expand the log panel on error and deploy
  if (level === 'error' || level === 'deploy') {
    const panel = document.getElementById('log-panel');
    panel.classList.remove('collapsed');
    document.getElementById('btn-toggle-log').textContent = '▼';
  }
}

// ── Status ───────────────────────────────────────────────────
function setStatus(state) {
  const badge = document.getElementById('status-badge');
  badge.className  = `badge badge-${state}`;
  badge.textContent = state.toUpperCase();
}

async function refreshStatus() {
  try {
    const res  = await fetch(`${API}/api/labs/${currentLabName()}/status`);
    const data = await res.json();
    const { healthyCount, totalCount } = updateNodeStatus(data.containers);
    const containers = data.containers || [];
    const running = containers.filter(c => c.State === 'running').length;
    log(`Status: ${running}/${containers.length} running, ${healthyCount}/${totalCount} ready`, 'info');
  } catch(e) {
    log('Status error: ' + e, 'error');
  }
}

// ── Terminal view mode ────────────────────────────────────────
function initTermViewModeButtons() {
  document.querySelectorAll('.term-view-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.term-view-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      termViewMode = btn.dataset.mode;
      applyTermViewMode();
    });
  });
}

function applyTermViewMode() {
  const contents = document.getElementById('term-contents');
  if (termViewMode === 'split') {
    contents.style.display = 'flex';
    contents.style.flexDirection = 'column';
    document.querySelectorAll('.term-pane').forEach(p => {
      p.style.position = 'relative';
      p.style.display  = 'block';
      p.style.flex     = '1';
      p.style.minHeight = '160px';
      p.style.borderBottom = '1px solid #30363d';
    });
    // re-fit every pane's fitAddon
    setTimeout(() => {
      Object.values(terminals).forEach(t => {
        try { t.fitAddon.fit(); } catch(e) {}
      });
    }, 60);
  } else {
    contents.style.display = '';
    contents.style.flexDirection = '';
    document.querySelectorAll('.term-pane').forEach(p => {
      p.style.position = 'absolute';
      p.style.display  = 'none';
      p.style.flex     = '';
      p.style.minHeight = '';
      p.style.borderBottom = '';
    });
    // show only the active tab's pane
    const activeTab = document.querySelector('.term-tab.active');
    if (activeTab) activateTermTab(activeTab.dataset.nodeId);
    else {
      const remaining = Object.keys(terminals);
      if (remaining.length > 0) activateTermTab(remaining[remaining.length - 1]);
    }
  }
}

// ── Terminal ─────────────────────────────────────────────────
function openTerminal(labName, nodeId, kind) {
  if (termViewMode === 'window') {
    openWindowTerminal(labName, nodeId, kind);
    return;
  }

  if (terminals[nodeId]) {
    if (termViewMode === 'tabs') activateTermTab(nodeId);
    return;
  }

  const nodeLabel = topology.nodes.find(n => n.id === nodeId)?.label || nodeId;
  const isLinux   = (kind || topology.nodes.find(n => n.id === nodeId)?.kind) === 'linux';

  // create tab
  const tab = document.createElement('div');
  tab.className = 'term-tab';
  tab.dataset.nodeId = nodeId;
  const tabLabel = document.createElement('span');
  tabLabel.textContent = nodeLabel;
  const tabClose = document.createElement('span');
  tabClose.className = 'tab-close';
  tabClose.title = 'Close';
  tabClose.textContent = '✕';
  tab.appendChild(tabLabel);
  tab.appendChild(tabClose);

  // the ✕ button has its own click handler
  tabClose.addEventListener('click', (e) => {
    e.stopPropagation();
    e.preventDefault();
    closeTerminal(nodeId);
  });
  // clicking the tab body activates it
  tabLabel.addEventListener('click', (e) => {
    e.stopPropagation();
    if (termViewMode === 'tabs') activateTermTab(nodeId);
  });

  document.getElementById('term-tabs').appendChild(tab);

  // create pane
  const pane = document.createElement('div');
  pane.className = 'term-pane';
  pane.id = `term-pane-${nodeId}`;
  document.getElementById('term-contents').appendChild(pane);

  // xterm
  const term = new Terminal({
    theme: { background: '#000000', foreground: '#e6edf3', cursor: '#00d4aa' },
    fontFamily: 'JetBrains Mono, monospace',
    fontSize: 13, cursorBlink: true, scrollback: 2000,
  });
  const fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);
  term.open(pane);

  // WebSocket: linux -> exec-terminal, CX -> terminal
  const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsPath  = isLinux
    ? `/ws/exec-terminal/${labName}/${nodeId}`
    : `/ws/terminal/${labName}/${nodeId}`;
  const ws = new WebSocket(`${wsProto}//${location.host}${wsPath}`);

  ws.onopen    = () => log(`Terminal connected: ${nodeLabel}`, 'success');
  ws.onmessage = (e) => term.write(e.data);
  ws.onerror   = () => term.write('\r\n[WebSocket error]\r\n');
  ws.onclose   = () => {
    term.write('\r\n[Disconnected]\r\n');
    log(`Terminal disconnected: ${nodeLabel}`, 'warn');
  };

  term.onData((data) => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(data);
      if (syncMode) {
        Object.entries(terminals).forEach(([id, t]) => {
          if (id !== nodeId && t.ws?.readyState === WebSocket.OPEN) t.ws.send(data);
        });
      }
    }
  });

  terminals[nodeId] = { ws, term, fitAddon, pane, tab };
  log(`Terminal opened: ${nodeLabel}`, 'info');

  if (termViewMode === 'split') {
    applyTermViewMode();
  } else {
    activateTermTab(nodeId);
  }
}

function activateTermTab(nodeId) {
  if (termViewMode === 'split') return; // split shows all panes, nothing to do
  document.querySelectorAll('.term-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.term-pane').forEach(p => {
    p.classList.remove('active');
    p.style.display = 'none';
  });
  const t = terminals[nodeId];
  if (!t) return;
  t.tab.classList.add('active');
  t.pane.classList.add('active');
  t.pane.style.display = 'block';
  setTimeout(() => { try { t.fitAddon.fit(); } catch(e) {} }, 60);
}

function closeTerminal(nodeId) {
  const t = terminals[nodeId];
  if (!t) { log(`No terminal for ${nodeId}`, 'warn'); return; }
  try { if (t.ws) t.ws.close(); }       catch(e) {}
  try { if (t.term) t.term.dispose(); } catch(e) {}
  try { if (t.tab && t.tab.parentNode) t.tab.remove(); }   catch(e) {}
  try { if (t.pane && t.pane.parentNode) t.pane.remove(); } catch(e) {}
  delete terminals[nodeId];

  const remaining = Object.keys(terminals);
  if (remaining.length > 0 && termViewMode === 'tabs') {
    activateTermTab(remaining[remaining.length - 1]);
  }
  log(`Terminal closed: ${nodeId}`, 'info');
}

function openWindowTerminal(labName, nodeId, kind) {
  const nodeLabel = topology.nodes.find(n => n.id === nodeId)?.label || nodeId;
  const isLinux   = (kind || topology.nodes.find(n => n.id === nodeId)?.kind) === 'linux';

  document.getElementById('fullterm-label').textContent = `Terminal: ${nodeLabel}`;
  document.getElementById('modal-fullterm').classList.remove('hidden');

  const container = document.getElementById('fullterm-container');
  container.innerHTML = '';

  const term = new Terminal({
    theme: { background: '#000000', foreground: '#e6edf3', cursor: '#00d4aa' },
    fontFamily: 'JetBrains Mono, monospace',
    fontSize: 14, cursorBlink: true, scrollback: 5000,
  });
  const fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);
  term.open(container);
  setTimeout(() => { try { fitAddon.fit(); } catch(e) {} }, 100);

  const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsPath  = isLinux
    ? `/ws/exec-terminal/${labName}/${nodeId}`
    : `/ws/terminal/${labName}/${nodeId}`;
  const ws = new WebSocket(`${wsProto}//${location.host}${wsPath}`);
  ws.onmessage = (e) => term.write(e.data);
  ws.onerror   = () => term.write('\r\n[WebSocket error]\r\n');
  term.onData((data) => { if (ws.readyState === WebSocket.OPEN) ws.send(data); });

  const closeBtn = document.getElementById('btn-fullterm-close');
  const newBtn   = closeBtn.cloneNode(true);
  closeBtn.parentNode.replaceChild(newBtn, closeBtn);
  newBtn.onclick = () => {
    try { ws.close(); }     catch(e) {}
    try { term.dispose(); } catch(e) {}
    document.getElementById('modal-fullterm').classList.add('hidden');
    container.innerHTML = '';
  };
}

// ── Add Link Modal ────────────────────────────────────────────
function openAddLinkModal(srcId, dstId) {
  const srcSel = document.getElementById('link-src-node');
  const dstSel = document.getElementById('link-dst-node');
  const opts   = topology.nodes.map(n => `<option value="${n.id}">${n.label||n.id}</option>`).join('');
  srcSel.innerHTML = opts; dstSel.innerHTML = opts;
  if (srcId) srcSel.value = srcId;
  if (dstId) dstSel.value = dstId;
  document.getElementById('link-src-if').value = '';
  document.getElementById('link-dst-if').value = '';
  document.getElementById('modal-add-link').classList.remove('hidden');
  document.getElementById('link-src-if').focus();
}

// ── Buttons ──────────────────────────────────────────────────
function bindButtons() {
  // Deploy
  document.getElementById('btn-deploy').onclick = async () => {
    const labName = currentLabName();
    if (topology.nodes.length === 0) { log('No nodes in topology', 'warn'); return; }
    syncTopologyFromCy();
    log(`▶ Deploying lab: ${labName} ...`, 'deploy');
    setStatus('deploying');
    document.getElementById('btn-deploy').disabled = true;
    try {
      const res  = await fetch(`${API}/api/labs/deploy`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lab_name: labName, topology }),
      });
      const data = await res.json();
      if (res.ok) {
        log(`✅ Deploy SUCCESS: ${labName}`, 'deploy');
        log(stripAnsi(data.stdout || ''), 'success');
        setStatus('deploying');
        showDeployBanner(labName, true);
        startHealthPolling();
      } else {
        log(`❌ Deploy FAILED`, 'error');
        log(stripAnsi(data.detail || ''), 'error');
        setStatus('error');
        showDeployBanner(labName, false);
      }
    } catch(e) {
      log('Deploy error: ' + e, 'error'); setStatus('error');
    } finally {
      document.getElementById('btn-deploy').disabled = false;
    }
  };

  // Destroy
  document.getElementById('btn-destroy').onclick = async () => {
    const labName = currentLabName();
    if (!confirm(`Destroy lab "${labName}"? This permanently removes the containers and the topology definition.`)) return;
    stopHealthPolling();
    log(`✕ Destroying lab: ${labName} ...`, 'warn');
    try {
      const res  = await fetch(`${API}/api/labs/${labName}`, { method: 'DELETE' });
      const data = await res.json();
      if (res.ok) {
        log('✅ Destroy complete (containers + topology removed)', 'success');
        setStatus('idle');
        // fully clear the canvas and terminals
        Object.keys(terminals).forEach(id => closeTerminal(id));
        clearCanvas();
      } else {
        log('Destroy failed: ' + (data.detail||''), 'error');
      }
    } catch(e) { log('Destroy error: ' + e, 'error'); }
  };

  // Status
  document.getElementById('btn-refresh').onclick = refreshStatus;

  // Apply Config (push the selected template's default config to running nodes)
  document.getElementById('btn-apply-config').onclick = applyConfig;
  // Disabled until a template is selected
  const applyBtn  = document.getElementById('btn-apply-config');
  const tplSelect = document.getElementById('template-select');
  const syncApplyBtn = () => { applyBtn.disabled = !tplSelect.value; };
  tplSelect.addEventListener('change', syncApplyBtn);
  syncApplyBtn();

  // Load template
  document.getElementById('btn-load-template').onclick = async () => {
    const id = document.getElementById('template-select').value;
    if (!id) { log('Select a template', 'warn'); return; }
    try {
      const res = await fetch(`${API}/api/templates/${id}`);
      const tpl = await res.json();
      loadTopology(tpl); log(`Template loaded: ${tpl.name}`, 'success');
    } catch(e) { log('Template error: ' + e, 'error'); }
  };

  // Add Node
  document.getElementById('btn-add-node').onclick = () => {
    document.getElementById('modal-add-node').classList.remove('hidden');
    document.getElementById('new-node-id').focus();
  };
  document.getElementById('btn-modal-cancel').onclick = () =>
    document.getElementById('modal-add-node').classList.add('hidden');
  document.getElementById('btn-modal-add').onclick = () => {
    const id    = document.getElementById('new-node-id').value.trim();
    const label = document.getElementById('new-node-label').value.trim() || id;
    const kind  = document.getElementById('new-node-kind').value;
    if (!id) { log('Node ID required', 'warn'); return; }
    addNodeToCanvas({ id, label, kind, x: 200 + Math.random()*300, y: 150 + Math.random()*200 });
    document.getElementById('modal-add-node').classList.add('hidden');
    document.getElementById('new-node-id').value = '';
    document.getElementById('new-node-label').value = '';
    log(`Node added: ${label} (${kind})`, 'success');
  };

  // Add RADIUS node (palette: place only, no auto-wiring)
  document.getElementById('btn-add-radius').onclick = () => {
    const id = uniqueNodeId('radius');
    addNodeToCanvas({
      id,
      label: id === 'radius' ? 'RADIUS' : id.toUpperCase(),
      kind: 'linux',
      role: 'radius',
      image: RADIUS_IMAGE,
      binds: [...RADIUS_BINDS],
      x: 200 + Math.random()*300, y: 150 + Math.random()*200,
    });
    log(`RADIUS node added: ${id} (${RADIUS_IMAGE})`, 'success');
  };

  // Add Link
  document.getElementById('btn-add-link').onclick = () => {
    if (linkMode) { cancelLinkMode(); return; }
    if (topology.nodes.length < 2) { log('Need at least 2 nodes', 'warn'); return; }
    enterLinkMode(null);
  };
  document.getElementById('btn-modal-link-cancel').onclick = () =>
    document.getElementById('modal-add-link').classList.add('hidden');
  document.getElementById('btn-modal-link-add').onclick = () => {
    const src   = document.getElementById('link-src-node').value;
    const dst   = document.getElementById('link-dst-node').value;
    const srcIf = document.getElementById('link-src-if').value.trim() || '1/1/1';
    const dstIf = document.getElementById('link-dst-if').value.trim() || '1/1/1';
    if (src === dst) { log('Source and target must differ', 'warn'); return; }
    addLinkToCanvas(src, dst, srcIf, dstIf);
    document.getElementById('modal-add-link').classList.add('hidden');
    log(`Link added: ${src}:${srcIf} ↔ ${dst}:${dstIf}`, 'success');
  };

  // Export YAML
  document.getElementById('btn-export-yaml').onclick = async () => {
    syncTopologyFromCy();
    try {
      const labName = currentLabName();
      const res  = await fetch(`${API}/api/topology/export`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lab_name: labName, topology }),
      });
      const yaml = await res.text();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([yaml], { type: 'text/plain' }));
      a.download = `${labName}.clab.yml`; a.click();
      log(`YAML exported: ${labName}.clab.yml`, 'success');
    } catch(e) { log('Export error: ' + e, 'error'); }
  };

  // Import YAML
  document.getElementById('btn-import-yaml').onclick = () =>
    document.getElementById('modal-import').classList.remove('hidden');
  document.getElementById('btn-modal-import-cancel').onclick = () =>
    document.getElementById('modal-import').classList.add('hidden');
  document.getElementById('btn-modal-import').onclick = async () => {
    const yaml = document.getElementById('import-yaml-text').value;
    if (!yaml.trim()) { log('Paste YAML content', 'warn'); return; }
    try {
      const res  = await fetch(`${API}/api/topology/import`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ yaml_content: yaml }),
      });
      const data = await res.json();
      if (data.success) {
        loadTopology(data.topology);
        document.getElementById('lab-name').value = data.lab_name;
        document.getElementById('modal-import').classList.add('hidden');
        log(`Imported: ${data.lab_name}`, 'success');
      } else { log('Import error: ' + data.error, 'error'); }
    } catch(e) { log('Import error: ' + e, 'error'); }
  };

  // Clear
  document.getElementById('btn-clear').onclick = async () => {
    const labName = currentLabName();
    const choice = confirm(
      `Clear the canvas.\n\n` +
      `OK = also delete the saved lab definition files (will not be restored on reload)\n` +
      `Cancel = clear the view only (keep the files)`
    );
    // always clear the view
    Object.keys(terminals).forEach(id => closeTerminal(id));
    clearCanvas();
    if (choice) {
      try {
        await fetch(`${API}/api/labs/${labName}/files`, { method: 'DELETE' });
        log(`Canvas cleared + lab files removed: ${labName}`, 'info');
      } catch(e) {
        log('File removal error: ' + e, 'error');
      }
    } else {
      log('Canvas cleared (files kept)', 'info');
    }
  };

  // Open All Terminals
  document.getElementById('btn-open-all-terms').onclick = () => {
    topology.nodes.forEach(n => openTerminal(currentLabName(), n.id, n.kind));
  };

  // Sync mode
  document.getElementById('sync-mode').onchange = (e) => {
    syncMode = e.target.checked;
    log(`Sync mode: ${syncMode ? 'ON' : 'OFF'}`, syncMode ? 'warn' : 'info');
  };

  // Close all terminals
  document.getElementById('btn-close-all-terms').onclick = () => {
    Object.keys(terminals).forEach(id => closeTerminal(id));
  };

  // Fullscreen terminal
  document.getElementById('btn-term-fullscreen').onclick = () => {
    const active = document.querySelector('.term-tab.active') || document.querySelector('.term-tab');
    if (!active) { log('No active terminal', 'warn'); return; }
    const nodeId = active.dataset.nodeId;
    const node   = topology.nodes.find(n => n.id === nodeId);
    openWindowTerminal(currentLabName(), nodeId, node?.kind);
  };

  // Context menu: node
  document.getElementById('ctx-terminal').onclick = () => {
    if (!selectedNode) return;
    const n = topology.nodes.find(n => n.id === selectedNode.id());
    openTerminal(currentLabName(), selectedNode.id(), n?.kind);
    hideCtxMenus();
  };
  document.getElementById('ctx-exec').onclick = () => {
    if (!selectedNode) return;
    document.getElementById('exec-node-select').value = selectedNode.id();
    hideCtxMenus();
    document.getElementById('exec-command').focus();
  };
  document.getElementById('ctx-add-link-from').onclick = () => {
    if (!selectedNode) return;
    enterLinkMode(selectedNode.id());
    hideCtxMenus();
  };
  document.getElementById('ctx-del-node').onclick = () => {
    if (!selectedNode) return;
    const id = selectedNode.id();
    topology.nodes = topology.nodes.filter(n => n.id !== id);
    topology.links = topology.links.filter(l => l.source !== id && l.target !== id);
    cy.getElementById(id).remove();
    cy.edges().filter(e => e.data('source') === id || e.data('target') === id).remove();
    hideCtxMenus();
    updateNodeList(); updateExecNodeSelect();
    if (terminals[id]) closeTerminal(id);
    log(`Node deleted: ${id}`, 'info');
  };

  // Context menu: edge
  document.getElementById('ctx-del-edge').onclick = () => {
    if (!selectedEdge) return;
    const src = selectedEdge.data('source');
    const dst = selectedEdge.data('target');
    topology.links = topology.links.filter(
      l => !(l.source===src && l.target===dst) && !(l.source===dst && l.target===src)
    );
    selectedEdge.remove(); selectedEdge = null;
    hideCtxMenus();
    log(`Link deleted: ${src} ↔ ${dst}`, 'info');
  };

  // Clear log
  document.getElementById('btn-clear-log').onclick = () => {
    document.getElementById('log-output').innerHTML = '';
  };
}

// ── Exec bar ─────────────────────────────────────────────────
function bindExecBar() {
  document.getElementById('btn-exec').onclick = execCommand;
  document.getElementById('exec-command').addEventListener('keydown', e => {
    if (e.key === 'Enter') execCommand();
  });
}

async function execCommand() {
  const nodeId  = document.getElementById('exec-node-select').value;
  const command = document.getElementById('exec-command').value.trim();
  if (!nodeId || !command) return;
  try {
    const res  = await fetch(`${API}/api/labs/${currentLabName()}/nodes/${nodeId}/exec`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command }),
    });
    const data = await res.json();
    log(`[${nodeId}] ${command}`, 'info');
    log(stripAnsi(data.output || ''), data.success ? 'success' : 'error');
  } catch(e) { log('Exec error: ' + e, 'error'); }
}

// ── Apply Config ──────────────────────────────────────────────
// Independent of Deploy: deploy -> wait for nodes ready -> Apply Config.
async function applyConfig() {
  const labName    = currentLabName();
  const templateId = document.getElementById('template-select').value;
  if (!templateId) { log('Select a template first', 'warn'); return; }

  const btn  = document.getElementById('btn-apply-config');
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = '⏳ Applying...';
  log(`⚙ Applying default config for "${templateId}" to lab "${labName}"...`, 'deploy');
  try {
    const res  = await fetch(`${API}/api/labs/${labName}/apply-config`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_id: templateId }),
    });
    const data = await res.json();
    if (!res.ok) {
      log(`❌ Apply Config failed: ${data.detail || res.status}`, 'error');
      return;
    }
    if (data.error) { log(`❌ ${data.error}`, 'error'); return; }

    const nodes = data.nodes || {};
    let okCount = 0, total = 0;
    Object.entries(nodes).forEach(([nid, r]) => {
      total++;
      if (r.ok) {
        okCount++;
        log(`  ✅ ${nid}: ${r.applied_lines} lines applied`, 'success');
      } else {
        log(`  ❌ ${nid}: ${(r.errors || []).join(' | ') || 'failed'}`, 'error');
      }
    });
    log(data.success
      ? `✅ Apply Config complete: ${okCount}/${total} nodes OK`
      : `⚠ Apply Config finished with errors: ${okCount}/${total} nodes OK`,
      data.success ? 'deploy' : 'error');
  } catch(e) {
    log('Apply Config error: ' + e, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = orig;
  }
}

// ── Splitters (drag resize) ───────────────────────────────────
function resizeTermsAndCy(fitTerms) {
  try { if (cy) cy.resize(); } catch(e) {}
  if (fitTerms) {
    Object.values(terminals).forEach(t => { try { t.fitAddon.fit(); } catch(e) {} });
  }
}

function makeSplitter(splitter, onMove) {
  let raf = null;
  splitter.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    splitter.classList.add('dragging');
    try { splitter.setPointerCapture(e.pointerId); } catch(_) {}
    const move = (ev) => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = null;
        onMove(ev);
        resizeTermsAndCy(false);
      });
    };
    const up = (ev) => {
      splitter.classList.remove('dragging');
      try { splitter.releasePointerCapture(ev.pointerId); } catch(_) {}
      document.removeEventListener('pointermove', move);
      document.removeEventListener('pointerup', up);
      resizeTermsAndCy(true);
    };
    document.addEventListener('pointermove', move);
    document.addEventListener('pointerup', up);
  });
}

function initSplitters() {
  // vertical: canvas height <-> term height (within center-column)
  const splitterV = document.getElementById('splitter-v');
  const termPanel = document.getElementById('term-panel');
  const centerCol = document.getElementById('center-column');
  makeSplitter(splitterV, (ev) => {
    const rect = centerCol.getBoundingClientRect();
    let h = rect.bottom - ev.clientY - 3;           // term height
    const maxH = rect.height - 120 - 6;             // canvas min 120
    h = Math.max(120, Math.min(h, Math.max(120, maxH)));
    termPanel.style.height = h + 'px';
  });

  // horizontal: center width <-> right width (within main-layout)
  const splitterH = document.getElementById('splitter-h');
  const rightCol  = document.getElementById('right-column');
  const mainLayout = document.getElementById('main-layout');
  makeSplitter(splitterH, (ev) => {
    const rect = mainLayout.getBoundingClientRect();
    let w = rect.right - ev.clientX - 3;            // right width
    const maxW = rect.width - 210 - 320 - 6;        // sidebar 210 + center min 320
    w = Math.max(240, Math.min(w, Math.max(240, maxW)));
    rightCol.style.width = w + 'px';
  });
}

// ── Running labs ──────────────────────────────────────────────
function bindLabEnhancements() {
  document.getElementById('btn-refresh-running').onclick = loadRunningLabs;
  document.getElementById('btn-load-running').onclick = () => {
    const lab = document.getElementById('running-lab-select').value;
    if (!lab) { log('Select a running lab', 'warn'); return; }
    loadRunningLab(lab);
  };
}

async function loadRunningLabs() {
  try {
    const res  = await fetch(`${API}/api/labs/running`);
    const data = await res.json();
    runningLabsCache = data.labs || [];
    const sel  = document.getElementById('running-lab-select');
    const prev = sel.value;
    sel.innerHTML = '<option value="">-- Select --</option>' +
      runningLabsCache.map(l => `<option value="${escapeHtml(l.name)}">${escapeHtml(l.name)} (${l.node_count})</option>`).join('');
    if (prev && runningLabsCache.find(l => l.name === prev)) sel.value = prev;
    log(`Running labs: ${runningLabsCache.length}`, 'info');
  } catch(e) { log('Failed to fetch running labs: ' + e, 'error'); }
}

async function loadRunningLab(labName) {
  // build nodeMeta from running info (image/mgmt_ip/state)
  const labInfo = runningLabsCache.find(l => l.name === labName);
  nodeMeta = {};
  if (labInfo) labInfo.nodes.forEach(n => { nodeMeta[n.name] = n; });

  try {
    const res = await fetch(`${API}/api/labs/${labName}/topology`);
    if (!res.ok) { log(`Failed to fetch topology: ${labName}`, 'error'); return; }
    const data = await res.json();
    if (!data.topology || data.topology.nodes.length === 0) {
      log(`Topology is empty: ${labName}`, 'warn'); return;
    }
    // close existing terminals before loading (avoid mixing labs)
    Object.keys(terminals).forEach(id => closeTerminal(id));
    hideNodeDetail();
    document.getElementById('lab-name').value = labName;
    loadTopology(data.topology);   // nodes + links from YAML. Does not call Deploy
    log(`📥 Loaded running lab: ${labName} (${data.topology.nodes.length} nodes, no Deploy)`, 'success');
    if (data.is_deployed) {
      setStatus('running');
      await refreshStatus();
      startHealthPolling();
    }
  } catch(e) { log('Load error: ' + e, 'error'); }
}

// ── Node detail panel ─────────────────────────────────────────
function hideNodeDetail() {
  const empty = document.getElementById('detail-empty');
  const c     = document.getElementById('detail-content');
  if (empty) empty.style.display = '';
  if (c) { c.classList.add('hidden'); c.innerHTML = ''; }
}

function showNodeDetail(nodeId) {
  const node = topology.nodes.find(n => n.id === nodeId);
  if (!node) { hideNodeDetail(); return; }
  const meta    = nodeMeta[nodeId] || {};
  const kind    = node.kind || meta.kind || 'vr-aoscx';
  const isLinux = kind === 'linux';
  const image   = meta.image || node.image || (isLinux ? 'alpine:latest' : '-');
  const mgmt    = meta.mgmt_ip || '-';

  // links from this node's perspective
  const links = [];
  topology.links.forEach(l => {
    if (l.source === nodeId)      links.push({ localIf: l.src_if, peer: l.target, peerIf: l.dst_if });
    else if (l.target === nodeId) links.push({ localIf: l.dst_if, peer: l.source, peerIf: l.src_if });
  });

  document.getElementById('detail-empty').style.display = 'none';
  const c = document.getElementById('detail-content');
  c.classList.remove('hidden');

  const kindLabel = isLinux ? 'PC (linux)' : `CX (${kind})`;
  const stateTxt  = (meta.state || '-') + (meta.status ? ' / ' + meta.status : '');

  c.innerHTML = `
    <div class="detail-section">
      <div class="detail-section-title">Node</div>
      <div class="detail-row"><span class="detail-key">Name</span><span class="detail-val">${escapeHtml(node.label || nodeId)}</span></div>
      <div class="detail-row"><span class="detail-key">Node ID</span><span class="detail-val">${escapeHtml(nodeId)}</span></div>
      <div class="detail-row"><span class="detail-key">Kind</span><span class="detail-val">${escapeHtml(kindLabel)}</span></div>
      <div class="detail-row"><span class="detail-key">Image</span><span class="detail-val">${escapeHtml(image)}</span></div>
      <div class="detail-row"><span class="detail-key">Mgmt IP</span><span class="detail-val">${escapeHtml(mgmt)}</span></div>
      <div class="detail-row"><span class="detail-key">State</span><span class="detail-val">${escapeHtml(stateTxt)}</span></div>
    </div>
    <div id="detail-radius"></div>
    <div class="detail-section">
      <div class="detail-section-title">Links (${links.length})</div>
      ${links.length
        ? links.map(l => `<div class="detail-link-item"><span class="detail-link-if">${escapeHtml(l.localIf)}</span> ↔ <span class="detail-link-peer">${escapeHtml(l.peer)}:${escapeHtml(l.peerIf)}</span></div>`).join('')
        : '<div class="detail-empty" style="padding:4px;text-align:left">No links</div>'}
    </div>
    <div class="detail-section">
      <div class="detail-section-title">Live Info</div>
      <button id="btn-detail-refresh" class="btn btn-secondary small full-width" data-node="${escapeHtml(nodeId)}" data-kind="${escapeHtml(kind)}">↻ Refresh (show)</button>
      <div id="detail-live"></div>
    </div>
  `;
  document.getElementById('btn-detail-refresh').onclick = (e) => {
    const b = e.currentTarget;
    fetchNodeLive(b.dataset.node, b.dataset.kind);
  };

  // RADIUS Config block: only for FreeRADIUS (linux) nodes
  const isRadius = roleFromNode(node) === 'radius'
    || /freeradius|radius/i.test(image)
    || /freeradius|radius/i.test(node.id || '');
  if (isLinux && isRadius) {
    fetchRadiusSummary();
  }
}

// ── RADIUS Config block (detail panel) ────────────────────────
async function fetchRadiusSummary() {
  const box = document.getElementById('detail-radius');
  if (!box) return;
  try {
    const res = await fetch(`${API}/api/radius/summary`);
    if (!res.ok) return;
    const d = await res.json();
    const E = escapeHtml;
    const macAuth = d.mac_auth === 'accept-all'
      ? 'accept-all (all MACs accepted)'
      : (d.mac_auth || '-');
    const clients = (d.clients || [])
      .map(c => `<div class="detail-link-item"><span class="detail-link-if">${E(c.name)}</span> <span class="detail-link-peer">${E(c.ipaddr || '')}</span></div>`)
      .join('');
    box.innerHTML = `
      <div class="detail-section">
        <div class="detail-section-title">RADIUS Config</div>
        <div class="detail-row"><span class="detail-key">MAC-auth</span><span class="detail-val">${E(macAuth)}</span></div>
        <div class="detail-row"><span class="detail-key">802.1X user</span><span class="detail-val">${E(d.dot1x_user || '-')}</span></div>
        <div class="detail-row"><span class="detail-key">Secret</span><span class="detail-val">${E(d.secret || '-')}</span></div>
        ${clients ? `<div class="detail-section-title" style="margin-top:8px">Clients (${(d.clients||[]).length})</div>${clients}` : ''}
      </div>`;
  } catch(e) {
    // non-fatal: leave the block empty
  }
}

function statusChip(s) {
  s = (s || '').toLowerCase();
  if (s === 'up')   return '<span class="detail-chip chip-up">up</span>';
  if (s === 'down') return '<span class="detail-chip chip-down">down</span>';
  if (!s)           return '';
  return `<span class="detail-chip chip-na">${escapeHtml(s)}</span>`;
}

function detailTable(title, headers, rows, rawText) {
  let body;
  if (rows.length) {
    body = `<table class="detail-table"><thead><tr>${
      headers.map(h => `<th>${escapeHtml(h)}</th>`).join('')
    }</tr></thead><tbody>${
      rows.map(r => `<tr>${r.map(c => `<td>${c == null ? '' : c}</td>`).join('')}</tr>`).join('')
    }</tbody></table>`;
  } else {
    body = '<div class="detail-empty" style="padding:4px;text-align:left">No data (check raw)</div>';
  }
  let raw = '';
  if (rawText != null && rawText !== '') {
    raw = `<span class="detail-raw-toggle">▸ show raw</span><pre class="detail-raw hidden">${escapeHtml(rawText)}</pre>`;
  }
  return `<div class="detail-section"><div class="detail-section-title">${escapeHtml(title)}</div>${body}${raw}</div>`;
}

function renderLive(d, isLinux) {
  const E = escapeHtml;
  let h = `<div class="detail-section" style="margin-top:8px">
      <div class="detail-section-title">Deploy Info</div>
      <div class="detail-row"><span class="detail-key">State</span><span class="detail-val">${E(d.deploy_state || '-')}</span></div>
    </div>`;

  if (!isLinux) {
    h += detailTable('VLAN', ['ID', 'Name', 'Status', 'Type', 'Interfaces'],
      (d.vlans || []).map(v => [E(v.id), E(v.name), statusChip(v.status), E(v.type), E(v.interfaces)]),
      d.raw && d.raw.vlan);
  }
  h += detailTable('IP Address', ['Interface', 'IP', 'Status'],
    (d.ip_ifs || []).map(i => [E(i.interface), E(i.ip), statusChip(i.status)]),
    isLinux ? (d.raw && d.raw.ip_addr) : (d.raw && d.raw.ip_int));

  if (isLinux) {
    h += detailTable('Interfaces', ['Port', 'Status'],
      (d.interfaces || []).map(i => [E(i.port), statusChip(i.status)]),
      d.raw && d.raw.ip_link);
  } else {
    h += detailTable('Interfaces', ['Port', 'Status', 'Detail'],
      (d.interfaces || []).map(i => [E(i.port), statusChip(i.status), E(i.detail || '')]),
      d.raw && d.raw.if);
    h += detailTable('LLDP Neighbors', ['Local', 'Neighbor', 'Detail'],
      (d.lldp || []).map(n => [E(n.local_port), E(n.neighbor), E(n.detail || '')]),
      d.raw && d.raw.lldp);
  }
  return h;
}

function bindRawToggles(root) {
  root.querySelectorAll('.detail-raw-toggle').forEach(t => {
    t.onclick = () => {
      const pre = t.nextElementSibling;
      if (!pre) return;
      pre.classList.toggle('hidden');
      t.textContent = pre.classList.contains('hidden') ? '▸ show raw' : '▾ hide raw';
    };
  });
}

async function fetchNodeLive(nodeId, kind) {
  const liveDiv = document.getElementById('detail-live');
  if (!liveDiv) return;
  const isLinux = kind === 'linux';
  liveDiv.innerHTML = '<div class="detail-loading">⏳ Fetching show output... (up to ~1 min)</div>';
  const labName = currentLabName();
  try {
    const res = await fetch(`${API}/api/labs/${labName}/nodes/${encodeURIComponent(nodeId)}/live?kind=${encodeURIComponent(kind)}`);
    if (!res.ok) {
      liveDiv.innerHTML = `<div class="detail-loading" style="color:var(--danger)">Fetch failed (HTTP ${res.status})</div>`;
      return;
    }
    const d = await res.json();
    liveDiv.innerHTML = renderLive(d, isLinux);
    bindRawToggles(liveDiv);
    log(`Live info updated: ${nodeId}`, 'info');
  } catch(e) {
    liveDiv.innerHTML = `<div class="detail-loading" style="color:var(--danger)">Fetch error: ${escapeHtml(String(e))}</div>`;
  }
}

// ── Deploy banner ─────────────────────────────────────────────
function showDeployBanner(labName, success) {
  const existing = document.getElementById('deploy-banner');
  if (existing) existing.remove();
  const banner = document.createElement('div');
  banner.id = 'deploy-banner';
  banner.style.cssText = `
    position:absolute; top:12px; left:50%; transform:translateX(-50%);
    padding:8px 20px; border-radius:6px; z-index:50;
    font-family:var(--font-mono); font-size:12px; font-weight:600;
    pointer-events:none; white-space:nowrap;
    ${success
      ? 'background:#1f3a2a;border:1px solid #3fb950;color:#3fb950;'
      : 'background:#2d1a1a;border:1px solid #f85149;color:#f85149;'}
  `;
  banner.textContent = success
    ? `✅ Deploy complete: ${labName} — Polling health every 10s...`
    : `❌ Deploy failed: ${labName}`;
  document.getElementById('canvas-area').appendChild(banner);
  setTimeout(() => { if (banner.parentNode) banner.remove(); }, success ? 15000 : 20000);
}
