const $ = (s) => document.querySelector(s);

function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = value ?? "";
  return node.innerHTML;
}

function toast(message, error = false) {
  const el = $("#toast");
  el.textContent = message;
  el.className = `toast show${error ? " error" : ""}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.className = "toast"; }, 2800);
}

async function api(path) {
  const response = await fetch(path);
  const data = await response.json().catch(() => ({ error: "无效响应" }));
  if (!response.ok) throw new Error(data.error || `请求失败 (${response.status})`);
  return data;
}

async function health() {
  try {
    const data = await api("/api/health");
    $("#statusDot").classList.add("online");
    const n = data.ledger ? data.ledger.count : 0;
    $("#statusText").textContent = `账本 ${n} 条 · 在线`;
  } catch (error) {
    $("#statusText").textContent = "服务离线";
  }
}

function cardHtml(item) {
  const neg = !!item.negative;
  return `<article class="exp-card${neg ? " is-neg" : ""}">
    <header>
      <span class="pill">${neg ? "证伪" : "打法"}</span>
      <code>${escapeHtml(item.skill || "")}</code>
      <strong>${escapeHtml(item.method || "")}</strong>
      <time>${escapeHtml(item.at || "")}</time>
    </header>
    <dl>
      <dt>何时用</dt><dd>${escapeHtml(item.trigger || "—")}</dd>
      <dt>怎么打</dt><dd>${escapeHtml(item.steps || "—")}</dd>
      <dt>怎样算成</dt><dd>${escapeHtml(item.oracle || "—")}</dd>
    </dl>
    ${item.project ? `<footer>项目 ${escapeHtml(item.project)}</footer>` : ""}
  </article>`;
}

async function loadSkills(selected) {
  const cat = await api("/api/skills");
  const select = $("#skill");
  select.innerHTML = '<option value="">全部 skill</option>' +
    cat.skills.map((s) => {
      const mark = s.all ? ` (${s.all})` : "";
      return `<option value="${escapeHtml(s.name)}">${escapeHtml(s.name)}${escapeHtml(mark)}</option>`;
    }).join("");
  if (selected) select.value = selected;
  const list = $("#skillList");
  if (list) {
    list.innerHTML = cat.skills.map((s) => {
      const cls = s.name === selected ? "on" : "";
      const n = s.all ? String(s.all) : "0";
      return `<button type="button" class="skill-item ${cls}" data-skill="${escapeHtml(s.name)}"><span>${escapeHtml(s.name)}</span><small>${n}</small></button>`;
    }).join("");
    list.querySelectorAll(".skill-item").forEach((btn) => {
      btn.addEventListener("click", () => {
        $("#skill").value = btn.dataset.skill;
        loadLedger().catch((err) => toast(err.message, true));
      });
    });
  }
  return cat;
}

async function loadLedger() {
  const q = $("#q").value.trim();
  const skill = $("#skill").value;
  const kind = $("#kind").value;
  const params = new URLSearchParams({ kind });
  if (q) params.set("q", q);
  if (skill) params.set("skill", skill);
  const data = await api(`/api/experience?${params.toString()}`);
  await loadSkills(skill);
  $("#countAll").textContent = String(data.count);
  $("#countPos").textContent = String(data.positive);
  $("#countNeg").textContent = String(data.negative);
  $("#resultBadge").textContent = skill ? `${skill} · ${data.count} 条` : `${data.count} 条`;
  $("#sourceLabel").textContent = data.source || "experience.jsonl";
  const box = $("#cards");
  if (!data.items.length) {
    const msg = skill
      ? `「${skill}」账本里还没有卡片。Skill 手册是只读的，经验只出现在 jsonl。`
      : "账本是空的。学习报告或挖成/证伪后经 src_memory.py remember 会出现在这里。";
    box.innerHTML = `<div class="empty-state"><strong>没有卡片</strong><span>${escapeHtml(msg)}</span></div>`;
    return;
  }
  box.innerHTML = data.items.map(cardHtml).join("");
}

function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

document.addEventListener("DOMContentLoaded", () => {
  health();
  loadLedger().catch((err) => toast(err.message, true));
  $("#refreshBtn").addEventListener("click", () => {
    loadLedger().then(() => toast("已刷新")).catch((err) => toast(err.message, true));
  });
  $("#q").addEventListener("input", debounce(() => loadLedger().catch((err) => toast(err.message, true)), 200));
  $("#skill").addEventListener("change", () => loadLedger().catch((err) => toast(err.message, true)));
  $("#kind").addEventListener("change", () => loadLedger().catch((err) => toast(err.message, true)));
});
