/* ═══════════════════════════════════════════════════════════════
   MemoryVerse AI — Frontend Application Logic
════════════════════════════════════════════════════════════════ */

const API = '';  // Same origin — all calls go to FastAPI backend

// ─── STATE ────────────────────────────────────────────────────
let authToken = localStorage.getItem('mv_token');
let currentUser = null;
let allDocs = [];
let graphData = { nodes: [], edges: [] };

// Graph canvas state
let graphNodes = [];   // {id, x, y, vx, vy, ...data}
let graphEdges = [];
let isDragging = false;
let dragNode = null;
let panStart = null;
let panOffset = { x: 0, y: 0 };
let hoveredNode = null;

// Theme toggle logic
function initTheme() {
  const savedTheme = localStorage.getItem('mv_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeIcons(savedTheme);
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('mv_theme', newTheme);
  updateThemeIcons(newTheme);

  // Redraw graph canvas if active view is graph
  if (document.getElementById('view-graph')?.classList.contains('active')) {
    const canvas = document.getElementById('graph-canvas');
    if (canvas && canvas.getContext) {
      drawGraph(canvas.getContext('2d'), canvas.width, canvas.height);
    }
  }
}

function updateThemeIcons(theme) {
  const sunIcon = document.querySelector('.theme-icon-sun');
  const moonIcon = document.querySelector('.theme-icon-moon');
  if (!sunIcon || !moonIcon) return;
  if (theme === 'light') {
    sunIcon.classList.remove('hidden');
    moonIcon.classList.add('hidden');
  } else {
    sunIcon.classList.add('hidden');
    moonIcon.classList.remove('hidden');
  }
}

// ─── INIT ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  if (authToken) {
    initApp();
  } else {
    showAuthScreen();
  }
  // Toast container
  const tc = document.createElement('div');
  tc.id = 'toast-container';
  document.body.appendChild(tc);

  // Prevent browser default file open behavior on window drop
  window.addEventListener('dragover', (e) => e.preventDefault(), false);
  window.addEventListener('drop', (e) => {
    e.preventDefault();
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0 && authToken) {
      switchView('upload');
      const files = [...e.dataTransfer.files].filter(f => isValidFile(f));
      if (!files.length) {
        toast('Only PDF, DOCX, or TXT files are supported.', 'error');
        return;
      }
      files.forEach(uploadFile);
    }
  }, false);
});

// ═══════════════════════════════════════════════════════════════
//  AUTH
// ═══════════════════════════════════════════════════════════════
function showAuthScreen() {
  document.getElementById('auth-screen').classList.remove('hidden');
  document.getElementById('app').classList.add('hidden');
}

function showApp() {
  document.getElementById('auth-screen').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');
}

function switchAuthTab(tab) {
  document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
  document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
  document.getElementById('tab-login').classList.toggle('active', tab === 'login');
  document.getElementById('tab-register').classList.toggle('active', tab === 'register');
}

async function handleLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('login-btn');
  const errEl = document.getElementById('login-error');
  errEl.classList.add('hidden');
  btn.disabled = true;
  btn.textContent = 'Signing in…';

  try {
    const res = await fetch(`${API}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: document.getElementById('login-email').value,
        password: document.getElementById('login-password').value,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Login failed');

    authToken = data.access_token;
    localStorage.setItem('mv_token', authToken);
    initApp();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign In';
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const btn = document.getElementById('register-btn');
  const errEl = document.getElementById('register-error');
  errEl.classList.add('hidden');
  btn.disabled = true;
  btn.textContent = 'Creating account…';

  try {
    const res = await fetch(`${API}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: document.getElementById('reg-email').value,
        password: document.getElementById('reg-password').value,
        full_name: document.getElementById('reg-name').value,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || data.details?.[0] || 'Registration failed');

    authToken = data.access_token;
    localStorage.setItem('mv_token', authToken);
    initApp();
    toast('🎉 Account created! Welcome to MemoryVerse.', 'success');
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Create Account';
  }
}

function logout() {
  authToken = null;
  currentUser = null;
  localStorage.removeItem('mv_token');
  showAuthScreen();
}

// ═══════════════════════════════════════════════════════════════
//  APP INIT
// ═══════════════════════════════════════════════════════════════
async function initApp() {
  try {
    const res = await apiFetch('/api/auth/me');
    currentUser = res;
    document.getElementById('user-name').textContent = currentUser.full_name || 'User';
    document.getElementById('user-email').textContent = currentUser.email;
    document.getElementById('user-avatar').textContent = (currentUser.full_name || 'U')[0].toUpperCase();
    showApp();
    loadDashboard();
  } catch {
    logout();
  }
}

// ═══════════════════════════════════════════════════════════════
//  NAVIGATION
// ═══════════════════════════════════════════════════════════════
function switchView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById(`view-${name}`).classList.add('active');
  document.querySelector(`[data-view="${name}"]`).classList.add('active');

  if (name === 'dashboard') loadDashboard();
  if (name === 'timeline') loadTimeline();
  if (name === 'graph') loadGraph();
}

// ═══════════════════════════════════════════════════════════════
//  DASHBOARD
// ═══════════════════════════════════════════════════════════════
const CATEGORY_COLORS = {
  Certificate: '#f59e0b', Resume: '#3b82f6', Project: '#8b5cf6',
  Internship:  '#10b981', Achievement: '#ef4444', Academic: '#06b6d4', Other: '#6b7280',
};
const CATEGORY_ICONS = {
  Certificate:'🏆', Resume:'📄', Project:'💡', Internship:'🏢',
  Achievement:'⭐', Academic:'🎓', Other:'📁',
};

async function loadDashboard() {
  try {
    allDocs = await apiFetch('/api/documents');
    renderStats(allDocs);
    renderCategoryGrid(allDocs);
    renderRecentDocs(allDocs.slice(0, 8));
  } catch (err) {
    toast('Failed to load documents', 'error');
  }
}

function renderStats(docs) {
  const categories = [...new Set(docs.map(d => d.category).filter(Boolean))];
  const skills = new Set(docs.flatMap(d => d.skills || []));
  const container = document.getElementById('stats-bar');
  container.innerHTML = `
    <div class="stat-card"><div class="stat-num">${docs.length}</div><div class="stat-label">Total Documents</div></div>
    <div class="stat-card"><div class="stat-num">${categories.length}</div><div class="stat-label">Categories</div></div>
    <div class="stat-card"><div class="stat-num">${skills.size}</div><div class="stat-label">Skills Identified</div></div>
    <div class="stat-card"><div class="stat-num">${docs.filter(d=>d.status==='ready').length}</div><div class="stat-label">AI Processed</div></div>
  `;
}

function renderCategoryGrid(docs) {
  const counts = {};
  docs.forEach(d => { if(d.category) counts[d.category] = (counts[d.category]||0)+1; });
  const container = document.getElementById('category-grid');
  const cats = Object.entries(counts).sort((a,b)=>b[1]-a[1]);
  if (!cats.length) { container.innerHTML = '<p style="color:var(--text-muted);grid-column:1/-1;">No documents yet. Upload some to get started!</p>'; return; }
  container.innerHTML = cats.map(([cat, cnt]) => `
    <div class="cat-card" onclick="filterByCategory('${cat}')" style="border-top:3px solid ${CATEGORY_COLORS[cat]||'#6b7280'}">
      <div class="cat-name">${cat}</div>
      <div class="cat-count">${cnt} document${cnt!==1?'s':''}</div>
    </div>
  `).join('');
}

function filterByCategory(cat) {
  const filtered = allDocs.filter(d => d.category === cat);
  renderRecentDocs(filtered);
  document.querySelector('.section-header h3').textContent = `${cat} Documents`;
}

function renderRecentDocs(docs) {
  const container = document.getElementById('recent-docs');
  if (!docs.length) { container.innerHTML = '<p style="color:var(--text-muted);padding:20px 0;">No documents found.</p>'; return; }
  container.innerHTML = docs.map(d => `
    <div class="doc-item">
      <span class="doc-cat-badge" style="background:${hexAlpha(CATEGORY_COLORS[d.category]||'#6b7280',0.15)};color:${CATEGORY_COLORS[d.category]||'#6b7280'};border:1px solid ${hexAlpha(CATEGORY_COLORS[d.category]||'#6b7280',0.3)}">
        ${d.category||'Other'}
      </span>
      <div class="doc-info">
        <div class="doc-title">${escHtml((d.title && d.title !== 'Untitled Document') ? d.title : d.original_filename)}</div>
        <div class="doc-meta">${d.organization?escHtml(d.organization)+' · ':''}${d.date||'Date unknown'}</div>
        <div class="doc-skills">${(d.skills||[]).slice(0,5).map(s=>`<span class="skill-tag">${escHtml(s)}</span>`).join('')}</div>
      </div>
      <div class="doc-actions">
        <button class="btn-icon" onclick="downloadDoc(${d.id},'${escHtml(d.original_filename)}')" title="Download original">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        </button>
        <button class="btn-icon" onclick="deleteDoc(${d.id})" title="Delete" style="color:var(--accent-rose)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      </div>
    </div>
  `).join('');
}

async function downloadDoc(id, filename) {
  try {
    const res = await fetch(`${API}/api/documents/${id}/file`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });
    if (!res.ok) throw new Error('Download failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    toast('📥 Download started!', 'success');
  } catch { toast('Failed to download file', 'error'); }
}

async function deleteDoc(id) {
  if (!confirm('Delete this document? This cannot be undone.')) return;
  try {
    await apiFetch(`/api/documents/${id}`, { method: 'DELETE' });
    toast('Document deleted', 'info');
    loadDashboard();
  } catch { toast('Failed to delete', 'error'); }
}

async function reprocessAllDocs() {
  toast('🔄 Re-processing uncategorized documents with AI...', 'info');
  try {
    const res = await apiFetch('/api/documents/reprocess-all', { method: 'POST' });
    toast(`✅ ${res.message}`, 'success');
    loadDashboard();
  } catch (err) {
    toast(`❌ Failed to re-process: ${err.message}`, 'error');
  }
}

// ═══════════════════════════════════════════════════════════════
//  UPLOAD
// ═══════════════════════════════════════════════════════════════
let _dragCounter = 0;   // Prevents false dragLeave when cursor crosses child elements

function handleDragEnter(e) {
  e.preventDefault();
  _dragCounter++;
  document.getElementById('drop-zone').classList.add('drag-over');
}
function handleDragOver(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'copy';
}
function handleDragLeave(e) {
  _dragCounter--;
  if (_dragCounter === 0) {
    document.getElementById('drop-zone').classList.remove('drag-over');
  }
}
function handleDrop(e) {
  e.preventDefault();
  e.stopPropagation();  // Prevent window-level drop handler from also firing
  _dragCounter = 0;
  document.getElementById('drop-zone').classList.remove('drag-over');
  const files = [...e.dataTransfer.files].filter(f => isValidFile(f));
  if (!files.length) { toast('⚠️ Only PDF, DOCX, or TXT files are supported.', 'error'); return; }
  files.forEach(uploadFile);
}
function handleFileSelect(e) {
  [...e.target.files].forEach(uploadFile);
  e.target.value = '';
}
function isValidFile(file) {
  return /\.(pdf|docx|txt)$/i.test(file.name);
}

async function uploadFile(file) {
  const queue = document.getElementById('upload-queue');
  const itemId = `upload-${Date.now()}-${Math.random().toString(36).slice(2)}`;

  queue.insertAdjacentHTML('afterbegin', `
    <div class="upload-item" id="${itemId}">
      <span style="font-size:1.5rem">${fileIcon(file.name)}</span>
      <div class="upload-filename">${escHtml(file.name)}</div>
      <span class="upload-status processing">⏳ Processing…</span>
    </div>
  `);

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch(`${API}/api/upload`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${authToken}` },
      body: formData,
    });
    if (res.status === 401) {
      logout();
      toast('Session expired. Please sign in again.', 'error');
      return;
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Upload failed');

    document.querySelector(`#${itemId} .upload-status`).textContent = '✅ Ready';
    document.querySelector(`#${itemId} .upload-status`).className = 'upload-status ready';
    const catEl = document.createElement('span');
    catEl.className = 'upload-category';
    catEl.textContent = `${CATEGORY_ICONS[data.category]||'📁'} ${data.category}`;
    document.getElementById(itemId).appendChild(catEl);

    toast(`✅ "${data.title}" categorized as ${data.category}`, 'success');
  } catch (err) {
    document.querySelector(`#${itemId} .upload-status`).textContent = `❌ ${err.message}`;
    document.querySelector(`#${itemId} .upload-status`).className = 'upload-status failed';
    toast(`Upload failed: ${err.message}`, 'error');
  }
}

function fileIcon(name) {
  if (name.endsWith('.pdf')) return '📄';
  if (name.endsWith('.docx')) return '📝';
  return '📃';
}

// ═══════════════════════════════════════════════════════════════
//  TIMELINE
// ═══════════════════════════════════════════════════════════════
async function loadTimeline() {
  const container = document.getElementById('timeline-container');
  container.innerHTML = '<div style="color:var(--text-3)">Loading your journey…</div>';
  try {
    const data = await apiFetch('/api/timeline');
    if (!data.timeline?.length) {
      container.innerHTML = '<p class="empty-state">Upload documents to see your journey timeline.</p>';
      return;
    }
    container.innerHTML = data.timeline.map(group => `
      <div class="timeline-year-group">
        <div class="timeline-year">${group.year}</div>
        <div class="timeline-events">
          ${group.events.map(ev => {
            // Show document date if available, otherwise show upload date
            const dateDisplay = ev.date_source === 'document'
              ? ev.date
              : ev.uploaded_on ? `Uploaded ${ev.uploaded_on}` : '';
            return `
            <div class="timeline-event">
              <div class="event-header">
                <span class="event-icon">${ev.icon}</span>
                <span class="event-title">${escHtml(ev.title||'Untitled')}</span>
                <span class="event-date" title="${ev.date_source === 'uploaded' ? 'Date based on upload time' : 'Date extracted from document'}">${dateDisplay}</span>
              </div>
              ${ev.organization ? `<div class="event-org">🏢 ${escHtml(ev.organization)}</div>` : ''}
              ${ev.summary ? `<div class="event-org" style="margin-top:4px;color:var(--text-2)">${escHtml(ev.summary)}</div>` : ''}
              <div class="event-skills">${(ev.skills||[]).slice(0,5).map(s=>`<span class="skill-tag">${escHtml(s)}</span>`).join('')}</div>
            </div>`;
          }).join('')}
        </div>
      </div>
    `).join('');
  } catch { container.innerHTML = '<p class="empty-state">Failed to load timeline.</p>'; }
}

// ═══════════════════════════════════════════════════════════════
//  KNOWLEDGE GRAPH (Canvas-based force-directed)
// ═══════════════════════════════════════════════════════════════
async function loadGraph() {
  try {
    graphData = await apiFetch('/api/graph');
    renderGraph(graphData);
  } catch { toast('Failed to load graph', 'error'); }
}

async function rebuildGraph() {
  toast('Rebuilding connections…', 'info');
  try {
    const res = await apiFetch('/api/graph/rebuild', { method: 'POST' });
    toast(res.message, 'success');
    loadGraph();
  } catch (err) { toast(err.message || 'Rebuild failed', 'error'); }
}

function openManualConnectionModal() {
  const modal = document.getElementById('connection-modal');
  const sourceSel = document.getElementById('conn-source');
  const targetSel = document.getElementById('conn-target');

  if (!allDocs || !allDocs.length) {
    toast('No documents found. Upload documents first.', 'error');
    return;
  }

  const optionsHtml = allDocs.map(d => 
    `<option value="${d.id}">${escHtml((d.title && d.title !== 'Untitled Document') ? d.title : d.original_filename)} (${d.category || 'Other'})</option>`
  ).join('');

  sourceSel.innerHTML = optionsHtml;
  targetSel.innerHTML = optionsHtml;
  if (allDocs.length > 1) {
    targetSel.selectedIndex = 1;
  }

  document.getElementById('conn-type').value = '';
  document.getElementById('conn-desc').value = '';
  modal.classList.remove('hidden');
}

function closeManualConnectionModal() {
  document.getElementById('connection-modal').classList.add('hidden');
}

async function handleCreateConnection(e) {
  e.preventDefault();
  const sourceId = parseInt(document.getElementById('conn-source').value);
  const targetId = parseInt(document.getElementById('conn-target').value);
  const relType = document.getElementById('conn-type').value.trim();
  const description = document.getElementById('conn-desc').value.trim();

  if (sourceId === targetId) {
    toast('Please select two different documents.', 'error');
    return;
  }

  try {
    const res = await apiFetch('/api/graph/relationship', {
      method: 'POST',
      body: JSON.stringify({
        source_doc_id: sourceId,
        target_doc_id: targetId,
        relationship_type: relType,
        description: description || null,
      }),
    });
    toast(res.message || 'Connection created!', 'success');
    closeManualConnectionModal();
    loadGraph();
  } catch (err) {
    toast(err.message || 'Failed to create connection', 'error');
  }
}

function openManageConnectionsModal() {
  const modal = document.getElementById('manage-connections-modal');
  renderConnectionList();
  modal.classList.remove('hidden');
}

function closeManageConnectionsModal() {
  document.getElementById('manage-connections-modal').classList.add('hidden');
}

function renderConnectionList() {
  const container = document.getElementById('connection-list-container');
  if (!graphData || !graphData.edges || !graphData.edges.length) {
    container.innerHTML = '<p style="color:var(--text-muted);padding:20px;text-align:center;">No active connections. Add custom links or click "Rebuild Auto Connections".</p>';
    return;
  }

  container.innerHTML = graphData.edges.map(e => {
    const srcDoc = graphNodes.find(n => n.id === e.source) || { label: `Doc #${e.source}` };
    const tgtDoc = graphNodes.find(n => n.id === e.target) || { label: `Doc #${e.target}` };
    const srcLabel = escHtml((srcDoc.label && srcDoc.label !== 'Untitled Document') ? srcDoc.label : `Doc #${e.source}`);
    const tgtLabel = escHtml((tgtDoc.label && tgtDoc.label !== 'Untitled Document') ? tgtDoc.label : `Doc #${e.target}`);
    const typeLabel = escHtml(e.label || 'Connected');

    return `
      <div class="doc-item" style="padding:10px 14px; align-items:center; justify-content:space-between;">
        <div style="overflow:hidden; display:flex; flex-direction:column; gap:2px;">
          <div style="font-size:0.88rem; font-weight:600; color:var(--text-main); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
            ${srcLabel} <span style="color:var(--primary); margin:0 4px;">↔</span> ${tgtLabel}
          </div>
          <div style="font-size:0.75rem; color:var(--text-muted);">
            <span class="skill-tag">${typeLabel}</span> ${e.description ? `· ${escHtml(e.description)}` : ''}
          </div>
        </div>
        <button class="btn-icon" onclick="deleteRelationship(${e.source}, ${e.target})" title="Remove connection" style="color:var(--accent-rose); flex-shrink:0;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      </div>
    `;
  }).join('');
}

async function deleteRelationship(sourceId, targetId) {
  if (!confirm('Remove this connection between documents?')) return;
  try {
    const res = await apiFetch(`/api/graph/relationship/${sourceId}/${targetId}`, { method: 'DELETE' });
    toast(res.message || 'Connection removed', 'info');
    await loadGraph();
    renderConnectionList();
  } catch (err) {
    toast(err.message || 'Failed to remove connection', 'error');
  }
}

function renderGraph(data) {
  const canvas = document.getElementById('graph-canvas');
  const ctx = canvas.getContext('2d');
  const empty = document.getElementById('graph-empty');
  const legendEl = document.getElementById('graph-legend');

  canvas.width = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;

  if (!data.nodes.length) {
    empty.classList.remove('hidden');
    canvas.style.display = 'none';
    return;
  }
  empty.classList.add('hidden');
  canvas.style.display = 'block';

  // Legend
  const cats = [...new Set(data.nodes.map(n => n.category))];
  legendEl.innerHTML = cats.map(c => `
    <div class="legend-item">
      <div class="legend-dot" style="background:${CATEGORY_COLORS[c]||'#6b7280'}"></div> ${c}
    </div>
  `).join('');

  // Initialize node positions in a spacious circle layout
  const W = canvas.width, H = canvas.height;
  const numNodes = data.nodes.length;
  const ringRadius = Math.min(W, H) * 0.32;

  graphNodes = data.nodes.map((n, i) => {
    const angle = (i / numNodes) * 2 * Math.PI;
    return {
      ...n,
      x: W / 2 + ringRadius * Math.cos(angle),
      y: H / 2 + ringRadius * Math.sin(angle),
      vx: 0, vy: 0,
      r: 22,
    };
  });
  graphEdges = data.edges;

  let animFrame;
  const simulate = () => {
    // Force-directed simulation: high repulsion & spacious spring equilibrium
    const k = 180, repulsion = 14000, attraction = 0.03, damping = 0.85;

    // Repulsion between nodes
    for (let i = 0; i < graphNodes.length; i++) {
      for (let j = i+1; j < graphNodes.length; j++) {
        const a = graphNodes[i], b = graphNodes[j];
        const dx = b.x-a.x, dy = b.y-a.y;
        const dist = Math.sqrt(dx*dx+dy*dy)||1;
        const force = repulsion/(dist*dist);
        a.vx -= force*dx/dist; a.vy -= force*dy/dist;
        b.vx += force*dx/dist; b.vy += force*dy/dist;
      }
    }
    // Edge spring attraction
    graphEdges.forEach(e => {
      const a = graphNodes.find(n=>n.id===e.source);
      const b = graphNodes.find(n=>n.id===e.target);
      if (!a||!b) return;
      const dx=b.x-a.x, dy=b.y-a.y, dist=Math.sqrt(dx*dx+dy*dy)||1;
      const force = (dist-k)*attraction;
      a.vx += force*dx/dist; a.vy += force*dy/dist;
      b.vx -= force*dx/dist; b.vy -= force*dy/dist;
    });
    // Gentle center gravity
    graphNodes.forEach(n => {
      n.vx += (W/2 - n.x)*0.001;
      n.vy += (H/2 - n.y)*0.001;
      n.vx *= damping; n.vy *= damping;
      n.x += n.vx; n.y += n.vy;
      n.x = Math.max(40, Math.min(W-40, n.x));
      n.y = Math.max(40, Math.min(H-40, n.y));
    });
    drawGraph(ctx, W, H);
    animFrame = requestAnimationFrame(simulate);
  };

  // Stop simulation after settling
  setTimeout(() => { cancelAnimationFrame(animFrame); drawGraph(ctx, W, H); }, 2500);
  simulate();

  // Interaction
  setupGraphInteraction(canvas, ctx, W, H);
}

function drawGraph(ctx, W, H) {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';

  ctx.clearRect(0, 0, W, H);

  // Background
  ctx.fillStyle = isLight ? '#f8fafc' : '#080c14';
  ctx.fillRect(0, 0, W, H);

  // Draw edges
  graphEdges.forEach(e => {
    const a = graphNodes.find(n=>n.id===e.source);
    const b = graphNodes.find(n=>n.id===e.target);
    if (!a||!b) return;

    const isEdgeHovered = hoveredNode && (hoveredNode.id === a.id || hoveredNode.id === b.id);

    ctx.beginPath();
    ctx.moveTo(a.x+panOffset.x, a.y+panOffset.y);
    ctx.lineTo(b.x+panOffset.x, b.y+panOffset.y);
    ctx.strokeStyle = isEdgeHovered 
      ? (isLight ? '#2563eb' : '#60a5fa') 
      : (isLight ? 'rgba(148,163,184,0.35)' : 'rgba(71,85,105,0.4)');
    ctx.lineWidth = isEdgeHovered ? 2.5 : 1.5;
    ctx.stroke();

    // Edge label: ONLY show when edge or connected node is hovered to keep graph clean!
    if (isEdgeHovered && e.label) {
      const mx = (a.x+b.x)/2+panOffset.x, my=(a.y+b.y)/2+panOffset.y;
      ctx.fillStyle = isLight ? '#0f172a' : '#f8fafc';
      ctx.font = '600 11px Inter';
      ctx.textAlign = 'center';

      // Label background pill
      const tw = ctx.measureText(e.label).width;
      ctx.fillStyle = isLight ? '#ffffff' : '#1e293b';
      ctx.beginPath();
      ctx.roundRect(mx - tw/2 - 6, my - 12, tw + 12, 18, 4);
      ctx.fill();
      ctx.strokeStyle = isLight ? '#cbd5e1' : '#334155';
      ctx.stroke();

      ctx.fillStyle = isLight ? '#0f172a' : '#f8fafc';
      ctx.textBaseline = 'middle';
      ctx.fillText(e.label, mx, my-3);
    }
  });

  // Draw nodes
  graphNodes.forEach(n => {
    const x = n.x+panOffset.x, y = n.y+panOffset.y;
    const isHovered = hoveredNode?.id === n.id;
    const color = CATEGORY_COLORS[n.category]||'#6b7280';
    const r = isHovered ? n.r+4 : n.r;

    // Glow
    if (isHovered) {
      ctx.shadowColor = color;
      ctx.shadowBlur = 12;
    }

    // Circle
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI*2);
    ctx.fillStyle = isLight ? '#ffffff' : color+'22';
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = isHovered ? 3 : 2;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Document File Icon inside node circle
    ctx.fillStyle = isLight ? '#334155' : '#e2e8f0';
    ctx.font = `${isHovered ? 14 : 12}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    
    // Choose clean file format icon based on category/filename
    let icon = '📄';
    if (n.category === 'Certificate') icon = '🏆';
    else if (n.category === 'Project') icon = '💡';
    else if (n.category === 'Academic') icon = '🎓';
    else if (n.category === 'Internship') icon = '🏢';
    else if (n.category === 'Resume') icon = '📄';
    ctx.fillText(icon, x, y);

    // Label below
    ctx.fillStyle = isLight ? (isHovered ? '#0f172a' : '#1e293b') : (isHovered ? '#f8fafc' : '#cbd5e1');
    ctx.font = `${isHovered ? '700' : '600'} 11px Inter`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const label = (n.label||'').substring(0,25) + (n.label?.length>25?'…':'');
    ctx.fillText(label, x, y+r+6);
  });
}

function setupGraphInteraction(canvas, ctx, W, H) {
  const tooltip = document.getElementById('graph-tooltip');

  canvas.addEventListener('mousemove', e => {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left - panOffset.x;
    const my = e.clientY - rect.top - panOffset.y;

    if (isDragging && dragNode) {
      dragNode.x = mx; dragNode.y = my;
      dragNode.vx = 0; dragNode.vy = 0;
      drawGraph(ctx, W, H);
      return;
    }
    if (panStart) {
      panOffset.x += e.clientX - panStart.x;
      panOffset.y += e.clientY - panStart.y;
      panStart = { x: e.clientX, y: e.clientY };
      drawGraph(ctx, W, H);
      return;
    }

    hoveredNode = graphNodes.find(n => {
      const dx=n.x-mx, dy=n.y-my;
      return Math.sqrt(dx*dx+dy*dy) < n.r+4;
    }) || null;

    if (hoveredNode) {
      canvas.style.cursor = 'pointer';
      tooltip.classList.remove('hidden');
      tooltip.style.left = (e.clientX+12)+'px';
      tooltip.style.top  = (e.clientY-10)+'px';
      const skills = (hoveredNode.skills||[]).slice(0,5).join(', ');
      tooltip.innerHTML = `
        <strong>${CATEGORY_ICONS[hoveredNode.category]} ${escHtml(hoveredNode.label||'')}</strong><br/>
        <span style="color:#94a3b8">${hoveredNode.category} · ${hoveredNode.date||'Date unknown'}</span><br/>
        ${hoveredNode.organization ? `<span style="color:#94a3b8">${escHtml(hoveredNode.organization)}</span><br/>` : ''}
        ${skills ? `<span style="color:#a78bfa;font-size:0.8em">${skills}</span>` : ''}
      `;
      drawGraph(ctx, W, H);
    } else {
      canvas.style.cursor = 'grab';
      tooltip.classList.add('hidden');
    }
  });

  canvas.addEventListener('mousedown', e => {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left - panOffset.x;
    const my = e.clientY - rect.top - panOffset.y;
    const node = graphNodes.find(n => {
      const dx=n.x-mx, dy=n.y-my;
      return Math.sqrt(dx*dx+dy*dy) < n.r;
    });
    if (node) { isDragging = true; dragNode = node; }
    else { panStart = { x: e.clientX, y: e.clientY }; }
  });

  canvas.addEventListener('mouseup', () => {
    isDragging = false; dragNode = null; panStart = null;
  });
  canvas.addEventListener('mouseleave', () => {
    isDragging = false; dragNode = null; panStart = null;
    tooltip.classList.add('hidden');
  });
}

// ═══════════════════════════════════════════════════════════════
//  SEARCH & CHAT
// ═══════════════════════════════════════════════════════════════
async function sendChat() {
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  await submitChat(msg);
}

function sendQuickQuery(query) {
  submitChat(query);
}

async function submitChat(message) {
  const messages = document.getElementById('chat-messages');
  const btn = document.getElementById('send-btn');

  // Clear welcome screen on first message
  messages.querySelector('.chat-welcome')?.remove();

  // User bubble
  messages.insertAdjacentHTML('beforeend', `
    <div class="msg-user">
      <div class="msg-bubble">${escHtml(message)}</div>
    </div>
  `);

  // Thinking bubble
  const thinkId = 'think-' + Date.now();
  messages.insertAdjacentHTML('beforeend', `
    <div class="msg-ai msg-thinking" id="${thinkId}">
      <div class="msg-bubble">MemoryVerse is searching your documents…</div>
    </div>
  `);
  messages.scrollTop = messages.scrollHeight;
  btn.disabled = true;

  try {
    const data = await apiFetch('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id: 'main' }),
    });

    document.getElementById(thinkId).remove();
    const sources = (data.sources||[]).map(s =>
      `<span class="source-chip">${CATEGORY_ICONS[s.category]||'📄'} ${escHtml(s.title||'Doc')}</span>`
    ).join('');

    // Preserve newlines in AI reply
    const formattedReply = escHtml(data.reply).replace(/\n/g, '<br/>');
    messages.insertAdjacentHTML('beforeend', `
      <div class="msg-ai">
        <div class="msg-bubble">${formattedReply}</div>
        ${sources ? `<div class="msg-sources">${sources}</div>` : ''}
      </div>
    `);
  } catch (err) {
    document.getElementById(thinkId).remove();
    const errMsg = err.message || 'Something went wrong. Please try again.';
    messages.insertAdjacentHTML('beforeend', `
      <div class="msg-ai">
        <div class="msg-bubble" style="color:var(--rose)">⚠️ ${escHtml(errMsg)}</div>
      </div>
    `);
  } finally {
    btn.disabled = false;
    messages.scrollTop = messages.scrollHeight;
  }
}

// ═══════════════════════════════════════════════════════════════
//  UTILITIES
async function apiFetch(path, opts = {}) {
  const res = await fetch(API + path, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${authToken}`,
      ...(opts.headers || {}),
    },
  });

  if (res.status === 401) { logout(); throw new Error('Unauthorized'); }
  if (res.status === 204) return null;

  const text = await res.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text };
    }
  }

  if (!res.ok) throw new Error(data.error || data.detail || `HTTP ${res.status}`);
  return data;
}

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function hexAlpha(hex, alpha) {
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function toast(msg, type='info') {
  const tc = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  tc.appendChild(el);
  setTimeout(() => { el.style.opacity='0'; el.style.transition='opacity 0.4s'; setTimeout(()=>el.remove(),400); }, 3500);
}
