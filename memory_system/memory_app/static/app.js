const state = { memories: null, sending: false };
const $ = (selector) => document.querySelector(selector);
const els = {
  user: $('#userId'), session: $('#sessionId'), messages: $('#messages'), form: $('#chatForm'),
  input: $('#messageInput'), image: $('#imageInput'), send: $('#sendBtn'), badge: $('#encodingBadge'),
  statusDot: $('#statusDot'), statusText: $('#statusText'), short: $('#shortMemories'),
  events: $('#eventList'), canvas: $('#graphCanvas'), legend: $('#graphLegend'), toast: $('#toast')
};

function identity() {
  return { user_id: els.user.value.trim(), session_id: els.session.value.trim() };
}

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  const data = await response.json().catch(() => ({ error: '服务返回了无效响应' }));
  if (!response.ok) throw new Error(data.error || `请求失败 (${response.status})`);
  return data;
}

function escapeHtml(value) {
  const node = document.createElement('span');
  node.textContent = value ?? '';
  return node.innerHTML;
}

function showToast(message, error = false) {
  els.toast.textContent = message;
  els.toast.className = `toast show${error ? ' error' : ''}`;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => { els.toast.className = 'toast'; }, 2800);
}

function addMessage(role, content) {
  const empty = els.messages.querySelector('.empty-state');
  if (empty) empty.remove();
  const item = document.createElement('div');
  item.className = `message ${role}`;
  item.innerHTML = `<div class="meta">${role === 'user' ? '你' : '记忆助手'}</div><div class="bubble">${escapeHtml(content)}</div>`;
  els.messages.appendChild(item);
  els.messages.scrollTop = els.messages.scrollHeight;
}

async function health() {
  try {
    const data = await api('/api/health');
    els.statusDot.classList.add('online');
    els.statusText.textContent = data.model.enabled ? data.model.name : '本地记忆模式';
  } catch (error) {
    els.statusText.textContent = '服务离线';
  }
}

async function loadHistory() {
  const { user_id, session_id } = identity();
  if (!user_id || !session_id) return;
  const data = await api(`/api/history?user_id=${encodeURIComponent(user_id)}&session_id=${encodeURIComponent(session_id)}`);
  els.messages.innerHTML = '';
  if (!data.items.length) {
    els.messages.innerHTML = '<div class="empty-state"><strong>记忆通道已就绪</strong><span>开始对话，重要事实会依次经过深度加工、工作缓冲与向量编码。</span></div>';
  } else {
    data.items.forEach((item) => addMessage(item.role, item.content));
  }
  $('#sessionLabel').textContent = session_id;
}

async function loadMemories() {
  const { user_id } = identity();
  if (!user_id) return;
  const [memories, events] = await Promise.all([
    api(`/api/memories?user_id=${encodeURIComponent(user_id)}`),
    api(`/api/events?user_id=${encodeURIComponent(user_id)}`)
  ]);
  state.memories = memories;
  $('#countInstant').textContent = `${memories.stats.instant} 条`;
  $('#countWorking').textContent = `${memories.stats.working} 条`;
  $('#countShort').textContent = `${memories.stats.short} 条`;
  $('#countLong').textContent = `${memories.stats.relations} 联结`;
  renderShort(memories.short);
  renderGraph(memories.graph);
  renderEvents(events.items);
}

function renderShort(items) {
  if (!items.length) {
    els.short.innerHTML = '<div class="empty-list">暂无短时记忆</div>';
    return;
  }
  els.short.innerHTML = items.map((item) => `
    <article class="memory-item">
      <p>${escapeHtml(item.content)}</p>
      <div class="importance"><i style="width:${Math.round(item.importance * 100)}%"></i></div>
      <div class="memory-meta"><span>重要度 ${Math.round(item.importance * 100)}%</span><span>召回 ${item.recall_count} 次</span></div>
      <div class="memory-meta"><span>${escapeHtml(item.session_id)}</span><span>${item.consolidated_at ? '已巩固' : '待巩固'}</span></div>
    </article>`).join('');
}

function renderEvents(items) {
  if (!items.length) {
    els.events.innerHTML = '<div class="empty-list">暂无加工记录</div>';
    return;
  }
  els.events.innerHTML = items.map((item) => {
    const detail = item.detail || {};
    const decision = detail.encoded ? `已编码 · ${Math.round((detail.importance || 0) * 100)}%` : '浅层过滤';
    return `<article class="event-item"><strong>${decision}</strong><p>${escapeHtml(detail.reason || '')}</p><div class="memory-meta"><span>${escapeHtml(item.session_id || '')}</span><span>短 ${detail.short_recalled || 0} / 长 ${detail.long_recalled || 0}</span></div></article>`;
  }).join('');
}

function renderGraph(graph) {
  const canvas = els.canvas;
  const panel = $('#graphPanel');
  const width = Math.max(300, panel.clientWidth || 360);
  const height = Math.max(360, panel.clientHeight || 480);
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio; canvas.height = height * ratio;
  const ctx = canvas.getContext('2d'); ctx.scale(ratio, ratio); ctx.clearRect(0, 0, width, height);
  if (!graph.nodes.length) {
    ctx.fillStyle = '#69736f'; ctx.font = '12px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText('巩固后将在此形成长期联结', width / 2, height / 2);
    els.legend.textContent = '0 个实体 · 0 条关系'; return;
  }
  const center = { x: width / 2, y: height / 2 };
  const positions = new Map();
  graph.nodes.forEach((node, index) => {
    const angle = (Math.PI * 2 * index) / graph.nodes.length - Math.PI / 2;
    const radius = node.type === 'Person' ? 0 : Math.min(width, height) * 0.34;
    positions.set(node.id, { x: center.x + Math.cos(angle) * radius, y: center.y + Math.sin(angle) * radius });
  });
  ctx.strokeStyle = '#aebbb6'; ctx.lineWidth = 1;
  graph.edges.forEach((edge) => { const a = positions.get(edge.source); const b = positions.get(edge.target); if (!a || !b) return; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); });
  graph.nodes.forEach((node) => {
    const point = positions.get(node.id); const primary = node.type === 'Person';
    ctx.beginPath(); ctx.arc(point.x, point.y, primary ? 22 : 15, 0, Math.PI * 2);
    ctx.fillStyle = primary ? '#087f73' : '#d49a4d'; ctx.fill();
    ctx.fillStyle = '#18211f'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(node.name.length > 12 ? `${node.name.slice(0, 11)}…` : node.name, point.x, point.y + (primary ? 36 : 29));
  });
  els.legend.textContent = `${graph.nodes.length} 个实体 · ${graph.edges.length} 条关系`;
}

els.form.addEventListener('submit', async (event) => {
  event.preventDefault(); if (state.sending) return;
  const ids = identity(); const message = els.input.value.trim(); if (!message) return;
  state.sending = true; els.send.disabled = true; addMessage('user', message); els.input.value = '';
  try {
    const data = await api('/api/chat', { method: 'POST', body: JSON.stringify({ ...ids, message, image_description: els.image.value.trim() || null }) });
    addMessage('assistant', data.answer); els.image.value = '';
    els.badge.textContent = data.memory.encoded ? `已编码 ${Math.round(data.memory.importance * 100)}%` : '浅层过滤';
    els.badge.classList.toggle('encoded', data.memory.encoded); await loadMemories();
  } catch (error) { showToast(error.message, true); await loadHistory().catch(() => {}); }
  finally { state.sending = false; els.send.disabled = false; els.input.focus(); }
});

$('#refreshBtn').addEventListener('click', () => loadMemories().catch((e) => showToast(e.message, true)));
$('#newSession').addEventListener('click', () => {
  els.session.value = `session_${Date.now().toString(36)}`; loadHistory().catch((e) => showToast(e.message, true));
});
$('#consolidateBtn').addEventListener('click', async () => {
  try { const result = await api('/api/consolidate', { method: 'POST', body: JSON.stringify({ user_id: identity().user_id }) }); showToast(`巩固 ${result.memories} 条记忆，形成 ${result.facts} 个事实`); await loadMemories(); }
  catch (error) { showToast(error.message, true); }
});
$('#clearBtn').addEventListener('click', async () => {
  if (!confirm(`确定清空用户 ${identity().user_id} 的全部四层记忆吗？此操作不可撤销。`)) return;
  try { await api(`/api/memories?user_id=${encodeURIComponent(identity().user_id)}`, { method: 'DELETE' }); showToast('用户记忆已清空'); await Promise.all([loadHistory(), loadMemories()]); }
  catch (error) { showToast(error.message, true); }
});

document.querySelectorAll('.tab').forEach((tab) => tab.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach((item) => item.classList.toggle('active', item === tab));
  document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.toggle('active', panel.id === `${tab.dataset.tab}Panel`));
  if (tab.dataset.tab === 'graph' && state.memories) requestAnimationFrame(() => renderGraph(state.memories.graph));
}));
document.querySelectorAll('.layer').forEach((layer) => layer.addEventListener('click', () => {
  document.querySelectorAll('.layer').forEach((item) => item.classList.toggle('active', item === layer));
  const tab = layer.dataset.layer === 'long' ? 'graph' : layer.dataset.layer === 'short' ? 'short' : 'events';
  document.querySelector(`.tab[data-tab="${tab}"]`).click();
}));
[els.user, els.session].forEach((input) => input.addEventListener('change', () => Promise.all([loadHistory(), loadMemories()]).catch((e) => showToast(e.message, true))));
els.input.addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); els.form.requestSubmit(); } });
window.addEventListener('resize', () => { if (state.memories && $('#graphPanel').classList.contains('active')) renderGraph(state.memories.graph); });

Promise.all([health(), loadHistory(), loadMemories()]).catch((error) => showToast(error.message, true));
