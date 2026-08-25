/* ══════════════════════════════════════════════════════════════════
   EVE Web v5 — lógica da interface
   Sem dependências externas: SSE via fetch, markdown e highlight
   próprios, ícones SVG inline. Funciona 100% offline.
   ══════════════════════════════════════════════════════════════════ */

"use strict";

const $ = (sel) => document.querySelector(sel);

/* ─── Ícones (SVG inline, traço 1.7) ───────────────────────────── */

const ICONS = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  send: '<path d="M12 19V5M5 12l7-7 7 7"/>',
  stop: '<rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" stroke="none"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/>',
  code: '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  refresh: '<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>',
  pencil: '<path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>',
  trash: '<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><path d="M12 15V3"/>',
  eraser: '<path d="m7 21-4.3-4.3a2.4 2.4 0 0 1 0-3.4l9.6-9.6a2.4 2.4 0 0 1 3.4 0l5.6 5.6a2.4 2.4 0 0 1 0 3.4L13 21"/><path d="M22 21H7"/><path d="m5 11 8 8"/>',
  menu: '<path d="M3 6h18M3 12h18M3 18h18"/>',
  arrowDown: '<path d="M12 5v14m-7-7 7 7 7-7"/>',
  sparkle: '<path d="M12 3l1.9 5.9L20 10.5l-6.1 1.6L12 18l-1.9-5.9L4 10.5l6.1-1.6Z"/>',
  cloud: '<path d="M17.5 19a4.5 4.5 0 0 0 .4-9A7 7 0 1 0 6.3 19Z"/>',
  cpu: '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9.5" y="9.5" width="5" height="5"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
};

function icon(name, cls = "icon") {
  return `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;
}

/* ─── Refs de DOM ──────────────────────────────────────────────── */

const els = {
  app: $("#app"),
  messages: $("#messages"),
  input: $("#input"),
  send: $("#btn-send"),
  attach: $("#btn-attach"),
  code: $("#btn-code"),
  fileInput: $("#file-input"),
  attachments: $("#attachments"),
  chats: $("#chats"),
  newChat: $("#btn-new"),
  search: $("#search"),
  export: $("#btn-export"),
  memory: $("#btn-memory"),
  theme: $("#btn-theme"),
  title: $("#topbar-title"),
  hint: $("#hint"),
  engineGroq: $("#engine-groq"),
  engineOllama: $("#engine-ollama"),
  sidebar: $("#sidebar"),
  sidebarClose: $("#btn-sidebar-close"),
  scrim: $("#sidebar-scrim"),
  burger: $("#btn-burger"),
  jump: $("#btn-jump"),
  modelBtn: $("#btn-model"),
  modelLabel: $("#model-pick-label"),
  modelMenu: $("#model-menu"),
  modal: $("#modal"),
  modalText: $("#modal-text"),
  modalIcon: $("#modal-icon"),
  modalYes: $("#modal-yes"),
  modalNo: $("#modal-no"),
  toasts: $("#toasts"),
};

const state = {
  chatId: null,
  requestId: null,     // geração em andamento (para o stop)
  processing: false,
  codeMode: false,
  attachments: [],     // [{path, name, url}]
  history: [],         // transcript exibido [{role, content, meta, images}]
  model: localStorage.getItem("eve.model") || "auto",
  models: null,        // resposta de /api/models
  atBottom: true,
};

/* ─── Utilidades ───────────────────────────────────────────────── */

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;")
          .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

function fmtTime(ts) {
  // aceita "2026-07-10T14:32:05" ou Date
  try {
    const d = ts instanceof Date ? ts : new Date(String(ts).replace(" ", "T"));
    if (isNaN(d)) return "";
    return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  } catch { return ""; }
}

function toast(msg, isError = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " error" : "");
  el.textContent = msg;
  els.toasts.appendChild(el);
  setTimeout(() => {
    el.style.transition = "opacity .3s, transform .3s";
    el.style.opacity = "0";
    el.style.transform = "translateY(6px)";
    setTimeout(() => el.remove(), 320);
  }, 3600);
}

function confirmDialog(text) {
  return new Promise((resolve) => {
    els.modalText.textContent = text;
    els.modalIcon.innerHTML = icon("trash");
    els.modal.hidden = false;
    els.modalNo.focus();
    const done = (v) => {
      els.modal.hidden = true;
      els.modalYes.onclick = els.modalNo.onclick = null;
      document.removeEventListener("keydown", onKey);
      resolve(v);
    };
    const onKey = (e) => { if (e.key === "Escape") done(false); };
    document.addEventListener("keydown", onKey);
    els.modalYes.onclick = () => done(true);
    els.modalNo.onclick = () => done(false);
    els.modal.onclick = (e) => { if (e.target === els.modal) done(false); };
  });
}

/* ─── Scroll inteligente ───────────────────────────────────────── */

function isNearBottom() {
  const m = els.messages;
  return m.scrollHeight - m.scrollTop - m.clientHeight < 80;
}

function scrollToEnd(force = false) {
  if (force || state.atBottom) els.messages.scrollTop = els.messages.scrollHeight;
}

els.messages && els.messages.addEventListener("scroll", () => {
  state.atBottom = isNearBottom();
  els.jump.hidden = state.atBottom;
});

/* ─── Realce de sintaxe (leve) ─────────────────────────────────── */

const KW = new Set(("abstract as assert async await break case catch class const continue def default del delete do elif " +
  "else enum except export extends false final finally fn for from fun func function if impl import in interface is let " +
  "loop match mod module mut new nil none not null of or and package pass print private protected public pub raise return " +
  "self static struct super switch this throw true try type typeof use using var void while with yield").split(" "));

function highlight(code) {
  const re = /(\/\/[^\n]*|#[^\n]*|\/\*[\s\S]*?\*\/)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|\b(\d+(?:\.\d+)?)\b|\b([A-Za-z_]\w*)(\s*\()?/g;
  let out = "", last = 0, m;
  while ((m = re.exec(code)) !== null) {
    out += escapeHtml(code.slice(last, m.index));
    if (m[1]) out += `<span class="tok-com">${escapeHtml(m[1])}</span>`;
    else if (m[2]) out += `<span class="tok-str">${escapeHtml(m[2])}</span>`;
    else if (m[3]) out += `<span class="tok-num">${m[3]}</span>`;
    else if (m[4]) {
      if (KW.has(m[4])) out += `<span class="tok-kw">${m[4]}</span>` + (m[5] || "");
      else if (m[5]) out += `<span class="tok-fn">${m[4]}</span>` + m[5];
      else out += m[4];
    }
    last = re.lastIndex;
  }
  return out + escapeHtml(code.slice(last));
}

/* ─── Markdown (compacto) ──────────────────────────────────────── */

function inlineMd(s) {
  // s já vem escapado
  return s
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/~~([^~\n]+)~~/g, "<del>$1</del>")
    .replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
}

function renderMarkdown(text) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  let html = "", i = 0, para = [];

  const flushPara = () => {
    if (para.length) {
      html += `<p>${inlineMd(escapeHtml(para.join("\n"))).replace(/\n/g, "<br>")}</p>`;
      para = [];
    }
  };

  while (i < lines.length) {
    const line = lines[i];

    // Bloco de código cercado
    const fence = line.match(/^```(\w*)/);
    if (fence) {
      flushPara();
      const lang = fence[1] || "code";
      const buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++; }
      i++; // pula ```
      const code = buf.join("\n");
      html += `<div class="codeblock"><div class="codeblock-head">` +
        `<span class="codeblock-lang">${escapeHtml(lang)}</span>` +
        `<button class="codeblock-copy" data-code="${escapeHtml(code)}">${icon("copy")}copiar</button>` +
        `</div><pre><code>${highlight(code)}</code></pre></div>`;
      continue;
    }

    // Título
    const h = line.match(/^(#{1,4})\s+(.*)/);
    if (h) { flushPara(); html += `<h${h[1].length}>${inlineMd(escapeHtml(h[2]))}</h${h[1].length}>`; i++; continue; }

    // Separador
    if (/^(-{3,}|\*{3,})\s*$/.test(line)) { flushPara(); html += "<hr>"; i++; continue; }

    // Citação
    if (/^>\s?/.test(line)) {
      flushPara();
      const buf = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) { buf.push(lines[i].replace(/^>\s?/, "")); i++; }
      html += `<blockquote>${inlineMd(escapeHtml(buf.join("\n"))).replace(/\n/g, "<br>")}</blockquote>`;
      continue;
    }

    // Lista (com suporte a task list)
    if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) {
      flushPara();
      const ordered = /^\s*\d/.test(line);
      const tag = ordered ? "ol" : "ul";
      let items = "";
      while (i < lines.length && /^\s*([-*+]|\d+[.)])\s+/.test(lines[i])) {
        let item = lines[i].replace(/^\s*([-*+]|\d+[.)])\s+/, "");
        const task = item.match(/^\[([ xX])\]\s+(.*)/);
        if (task) {
          items += `<li class="task"><input type="checkbox" disabled${task[1].trim() ? " checked" : ""}>` +
                   `${inlineMd(escapeHtml(task[2]))}</li>`;
        } else {
          items += `<li>${inlineMd(escapeHtml(item))}</li>`;
        }
        i++;
      }
      html += `<${tag}>${items}</${tag}>`;
      continue;
    }

    // Tabela (| a | b |)
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      flushPara();
      const parseRow = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
      const head = parseRow(line);
      i += 2;
      let rows = "";
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
        rows += "<tr>" + parseRow(lines[i]).map(c => `<td>${inlineMd(escapeHtml(c))}</td>`).join("") + "</tr>";
        i++;
      }
      html += `<div class="table-wrap"><table><thead><tr>${head.map(c => `<th>${inlineMd(escapeHtml(c))}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>`;
      continue;
    }

    // Linha vazia fecha parágrafo
    if (!line.trim()) { flushPara(); i++; continue; }

    para.push(line);
    i++;
  }
  flushPara();
  return html;
}

/* ─── Chips de metadados ───────────────────────────────────────── */

function metaChips(meta) {
  if (!meta) return "";
  let chips = "";
  const m = meta.model_used || "";
  if (m === "error" || m === "groq_failed") chips += `<span class="chip err">erro</span>`;
  else if (m.includes("groq")) chips += `<span class="chip cloud">nuvem · groq</span>`;
  else if (m === "cache") chips += `<span class="chip local">cache</span>`;
  else if (m.startsWith("skill")) chips += `<span class="chip local">${escapeHtml(m)}</span>`;
  else if (m && m !== "unknown" && m !== "none")
    chips += `<span class="chip local">local${m.includes("ollama") ? "" : " · " + escapeHtml(m)}</span>`;
  if (meta.web_search_used) chips += `<span class="chip search">busca web</span>`;
  if (meta.aborted) chips += `<span class="chip err">interrompida</span>`;
  if (meta.response_time_ms) chips += `<span class="chip">${(meta.response_time_ms / 1000).toFixed(1)}s</span>`;
  return chips;
}

/* ─── Render de mensagens ──────────────────────────────────────── */

function messageActions(role) {
  const copyBtn = `<button class="icon-btn act-copy" title="Copiar mensagem">${icon("copy")}</button>`;
  const regenBtn = role === "eve"
    ? `<button class="icon-btn act-regen" title="Regenerar resposta">${icon("refresh")}</button>`
    : "";
  return `<div class="msg-actions">${copyBtn}${regenBtn}</div>`;
}

function addMessage(role, content, meta = null, images = [], ts = null) {
  const welcome = els.messages.querySelector(".welcome");
  if (welcome) welcome.remove();

  const div = document.createElement("div");
  div.className = `msg ${role === "user" ? "user" : "eve"}`;

  const who = role === "user" ? "Você" : "EVE";
  const when = fmtTime(ts || new Date());
  const imgsHtml = images.length
    ? `<div class="msg-images">${images.map(u => `<img class="thumb" src="${escapeHtml(u)}" alt="Imagem anexada">`).join("")}</div>`
    : "";

  const body = role === "user"
    ? `<div class="msg-content"></div>`
    : `<div class="msg-content md">${renderMarkdown(content)}</div>`;

  div.innerHTML = `
    <div class="msg-caption"><span class="who">${who}</span><span class="when">${when}</span></div>
    ${imgsHtml}${body}
    <div class="msg-foot">${metaChips(meta)}${messageActions(role === "user" ? "user" : "eve")}</div>`;

  if (role === "user") div.querySelector(".msg-content").textContent = content;

  els.messages.appendChild(div);
  updateRegenVisibility();
  scrollToEnd();
  return div;
}

/* só a última resposta da EVE mostra o botão regenerar */
function updateRegenVisibility() {
  const regens = els.messages.querySelectorAll(".act-regen");
  regens.forEach((b, idx) => { b.style.display = idx === regens.length - 1 ? "" : "none"; });
}

function showWelcome() {
  els.messages.innerHTML = `
    <div class="welcome">
      <div class="welcome-avatar"><img src="/avatar" alt="EVE" onerror="this.remove()"></div>
      <h3>Oi, eu sou a EVE.</h3>
      <p>Sua assistente pessoal — respondo pela nuvem quando dá e pelos modelos locais quando precisa.
         Pergunte qualquer coisa, peça código ou anexe uma imagem.</p>
      <div class="hints">
        <button class="hint-card" data-q="Me explica o que você consegue fazer?">
          <span class="hint-title">Conhecer a EVE</span>
          <span class="hint-sub">o que você consegue fazer?</span>
        </button>
        <button class="hint-card" data-q="Escreva um script Python que organiza os arquivos de uma pasta por extensão">
          <span class="hint-title">Gerar código</span>
          <span class="hint-sub">script Python para organizar arquivos</span>
        </button>
        <button class="hint-card" data-q="Quais as principais notícias de tecnologia desta semana?">
          <span class="hint-title">Buscar na web</span>
          <span class="hint-sub">notícias de tecnologia da semana</span>
        </button>
        <button class="hint-card" data-q="Analise a imagem que anexei e descreva o que vê">
          <span class="hint-title">Analisar imagem</span>
          <span class="hint-sub">cole com Ctrl+V ou arraste aqui</span>
        </button>
      </div>
    </div>`;
  els.messages.querySelectorAll(".hint-card").forEach(card =>
    card.addEventListener("click", () => {
      els.input.value = card.dataset.q;
      els.input.focus();
      autoGrow();
    })
  );
}

/* ─── Status das engines ───────────────────────────────────────── */

async function refreshStatus() {
  try {
    const r = await fetch("/api/status");
    const s = await r.json();
    const setEngine = (el, on, label) => {
      el.classList.toggle("on", on);
      el.classList.toggle("off", !on);
      el.querySelector(".engine-state").textContent = label;
    };
    setEngine(els.engineGroq, s.groq.online, s.groq.online ? "online" : "off");
    setEngine(els.engineOllama, s.ollama.online,
      s.ollama.online ? `${s.ollama.models.length} modelos` : "off");
  } catch { /* servidor fora — mantém último estado */ }
}

/* ─── Seletor de modelo ────────────────────────────────────────── */

async function loadModels() {
  try {
    const r = await fetch("/api/models");
    const j = await r.json();
    const next = (j && j.auto) ? j
      // formato antigo do backend: só oferece o automático
      : { auto: { id: "auto", label: "Automático", desc: "Roteamento automático" }, cloud: [], local: [] };
    const changed = JSON.stringify(next) !== JSON.stringify(state.models);
    state.models = next;
    // valida seleção salva (modelo pode ter sido desinstalado)
    const all = allModelIds();
    if (state.model !== "auto" && !all.includes(state.model)) setModel("auto");
    updateModelButton();
    return changed;
  } catch { return false; /* mantém o que tiver */ }
}

function allModelIds() {
  if (!state.models) return [];
  return [...(state.models.cloud || []), ...(state.models.local || [])].map(m => m.id);
}

function findModel(id) {
  if (!state.models || id === "auto") return state.models ? state.models.auto : null;
  return [...(state.models.cloud || []), ...(state.models.local || [])].find(m => m.id === id) || null;
}

function setModel(id) {
  state.model = id;
  localStorage.setItem("eve.model", id);
  updateModelButton();
  updateHint();
}

function updateModelButton() {
  const m = findModel(state.model);
  els.modelLabel.textContent = m ? m.label : "Automático";
  els.modelBtn.querySelector(".model-pick-icon").innerHTML =
    icon(state.model === "auto" ? "sparkle" : state.model.startsWith("groq:") ? "cloud" : "cpu");
}

function renderModelMenu() {
  const j = state.models;
  if (!j) { els.modelMenu.innerHTML = `<div class="model-menu-empty">Carregando…</div>`; return; }

  const opt = (m, group) => `
    <button class="model-opt${state.model === m.id ? " selected" : ""}" data-id="${escapeHtml(m.id)}" role="menuitem">
      <span class="model-opt-check">${icon("check")}</span>
      <span class="model-opt-body">
        <span class="model-opt-label">${escapeHtml(m.label)}</span>
        <span class="model-opt-desc">${escapeHtml(m.desc || "")}</span>
      </span>
      ${m.badge ? `<span class="badge${m.badge === "preview" ? " preview" : ""}">${escapeHtml(m.badge)}</span>` : ""}
    </button>`;

  let html = opt({ ...j.auto, id: "auto" });
  if ((j.cloud || []).length) {
    html += `<div class="model-menu-group">Nuvem — Groq</div>` + j.cloud.map(m => opt(m)).join("");
  }
  if ((j.local || []).length) {
    html += `<div class="model-menu-group">Local — Ollama</div>` + j.local.map(m => opt(m)).join("");
  } else {
    html += `<div class="model-menu-group">Local — Ollama</div><div class="model-menu-empty">Nenhum modelo local encontrado</div>`;
  }
  els.modelMenu.innerHTML = html;
}

// Delegação: sobrevive a re-renders do menu no meio de um clique
els.modelMenu.addEventListener("click", (e) => {
  const opt = e.target.closest(".model-opt");
  if (opt) { setModel(opt.dataset.id); closeModelMenu(); }
});

function openModelMenu() {
  renderModelMenu();
  // atualiza a lista em segundo plano; só re-renderiza se mudou
  loadModels().then((changed) => {
    if (changed && !els.modelMenu.hidden) renderModelMenu();
  });
  els.modelMenu.hidden = false;
  els.modelBtn.setAttribute("aria-expanded", "true");
  const r = els.modelBtn.getBoundingClientRect();
  els.modelMenu.style.top = `${r.bottom + 6}px`;
  els.modelMenu.style.right = `${Math.max(8, window.innerWidth - r.right)}px`;
  els.modelMenu.style.left = "auto";
}

function closeModelMenu() {
  els.modelMenu.hidden = true;
  els.modelBtn.setAttribute("aria-expanded", "false");
}

els.modelBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  els.modelMenu.hidden ? openModelMenu() : closeModelMenu();
});
document.addEventListener("click", (e) => {
  if (!els.modelMenu.hidden && !els.modelMenu.contains(e.target)) closeModelMenu();
});

/* ─── Busy / hint ──────────────────────────────────────────────── */

function setBusy(busy) {
  state.processing = busy;
  els.send.classList.toggle("stop", busy);
  els.send.innerHTML = icon(busy ? "stop" : "send");
  els.send.title = busy ? "Parar geração (Esc)" : "Enviar (Enter)";
  updateHint();
}

function updateHint() {
  let mode = "";
  if (state.codeMode) mode += `<span class="mode-chip">modo código · nuvem</span>`;
  else if (state.model !== "auto") {
    const m = findModel(state.model);
    if (m) mode += `<span class="mode-chip">modelo: ${escapeHtml(m.label)}</span>`;
  }
  els.hint.innerHTML = `${mode}<span class="hint-keys">Enter envia · Shift+Enter quebra linha${state.processing ? " · Esc interrompe" : ""}</span>`;
}

/* ─── Streaming (SSE sobre fetch) ──────────────────────────────── */

async function streamRequest(url, body, bubble) {
  const bodyEl = bubble.querySelector(".msg-content");
  const footEl = bubble.querySelector(".msg-foot");
  bodyEl.innerHTML = `<span class="caret"></span>`;
  let streamed = "";
  let lastRender = 0;

  const renderStream = (force = false) => {
    const now = performance.now();
    if (!force && now - lastRender < 90) return;   // ~11fps: suave e barato
    lastRender = now;
    bodyEl.innerHTML = renderMarkdown(streamed) + `<span class="caret"></span>`;
    scrollToEnd();
  };

  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;
  let result = null;

  while (!finished) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);

      let event = "message", data = "";
      for (const l of raw.split("\n")) {
        if (l.startsWith("event:")) event = l.slice(6).trim();
        else if (l.startsWith("data:")) data += l.slice(5).trim();
      }
      if (!data) continue;
      const payload = JSON.parse(data);

      if (event === "start") {
        state.chatId = payload.chat_id;
      } else if (event === "chunk") {
        streamed += payload.text;
        renderStream();
      } else if (event === "done") {
        bodyEl.innerHTML = renderMarkdown(payload.text);
        footEl.innerHTML = metaChips(payload) + messageActions("eve");
        state.history.push({ role: "assistant", content: payload.text, meta: payload });
        if (payload.title) els.title.textContent = payload.title;
        finished = true;
        result = payload;
      } else if (event === "error") {
        throw new Error(payload.message);
      }
    }
  }

  if (!finished && streamed) {
    // stream caiu no meio: mantém o parcial
    bodyEl.innerHTML = renderMarkdown(streamed);
    footEl.innerHTML = `<span class="chip err">conexão interrompida</span>` + messageActions("eve");
    state.history.push({ role: "assistant", content: streamed, meta: null });
  }
  updateRegenVisibility();
  return result;
}

async function send() {
  if (state.processing) return;
  const text = els.input.value.trim();
  const images = state.attachments.map(a => a.path);
  if (!text && !images.length) return;

  els.input.value = "";
  localStorage.removeItem("eve.draft");
  autoGrow();
  const imgUrls = state.attachments.map(a => a.url);
  clearAttachments();

  addMessage("user", text || "[Imagem]", null, imgUrls);
  state.history.push({ role: "user", content: text || "[Imagem]" });
  setBusy(true);

  state.requestId = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2));
  const bubble = addMessage("eve", "");

  try {
    await streamRequest("/api/chat", {
      message: text,
      chat_id: state.chatId,
      code_mode: state.codeMode,
      images,
      model: state.model === "auto" ? null : state.model,
      request_id: state.requestId,
    }, bubble);
    loadChats();
  } catch (e) {
    bubble.remove();
    state.history.pop();
    toast("Falha ao falar com a EVE: " + e.message, true);
  } finally {
    state.requestId = null;
    setBusy(false);
    els.input.focus();
  }
}

async function stopGeneration() {
  if (!state.processing || !state.requestId) return;
  try {
    await fetch("/api/chat/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: state.requestId }),
    });
    // o stream termina com evento done {aborted:true}
  } catch (e) {
    toast("Não deu para interromper: " + e.message, true);
  }
}

async function regenerate() {
  if (state.processing) { toast("Espera a resposta atual terminar."); return; }
  if (!state.chatId) return;
  // remove a última resposta da EVE da tela e do transcript local
  const eveMsgs = els.messages.querySelectorAll(".msg.eve");
  const lastEve = eveMsgs[eveMsgs.length - 1];
  if (!lastEve) return;
  lastEve.remove();
  for (let i = state.history.length - 1; i >= 0; i--) {
    if (state.history[i].role === "assistant") { state.history.splice(i, 1); break; }
  }

  setBusy(true);
  state.requestId = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2));
  const bubble = addMessage("eve", "");

  try {
    await streamRequest("/api/chat/regenerate", {
      chat_id: state.chatId,
      request_id: state.requestId,
      model: state.model === "auto" ? null : state.model,
    }, bubble);
    loadChats();
  } catch (e) {
    bubble.remove();
    toast("Falha ao regenerar: " + e.message, true);
  } finally {
    state.requestId = null;
    setBusy(false);
  }
}

/* ─── Anexos ───────────────────────────────────────────────────── */

function renderAttachments() {
  els.attachments.innerHTML = state.attachments.map((a, i) =>
    `<div class="attach-chip"><img src="${escapeHtml(a.url)}" alt="${escapeHtml(a.name || "anexo")}">
     <button data-i="${i}" title="Remover">${icon("x")}</button></div>`).join("");
  els.attachments.querySelectorAll("button").forEach(b =>
    b.addEventListener("click", () => {
      state.attachments.splice(+b.dataset.i, 1);
      renderAttachments();
    })
  );
}

function clearAttachments() {
  state.attachments = [];
  renderAttachments();
}

async function uploadFiles(files) {
  for (const file of files) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await fetch("/api/upload", { method: "POST", body: fd });
      if (!r.ok) throw new Error((await r.json()).detail || "upload falhou");
      const j = await r.json();
      state.attachments.push({ path: j.path, name: j.name, url: URL.createObjectURL(file) });
      renderAttachments();
    } catch (e) {
      toast(`Não deu para anexar ${file.name}: ${e.message}`, true);
    }
  }
}

/* ─── Conversas (sidebar) ──────────────────────────────────────── */

function groupLabel(ts) {
  if (!ts) return "Mais antigas";
  const d = new Date(String(ts).replace(" ", "T"));
  if (isNaN(d)) return "Mais antigas";
  const now = new Date();
  const startOfDay = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate());
  const days = Math.round((startOfDay(now) - startOfDay(d)) / 86400000);
  if (days <= 0) return "Hoje";
  if (days === 1) return "Ontem";
  if (days <= 7) return "Últimos 7 dias";
  return "Mais antigas";
}

async function loadChats(q = "") {
  try {
    const url = q ? `/api/chats?q=${encodeURIComponent(q)}` : "/api/chats";
    const r = await fetch(url);
    const j = await r.json();
    let chats = j.chats || [];

    // fallback: se o servidor ignorar ?q=, filtra por título/preview aqui
    if (q) {
      const ql = q.toLowerCase();
      chats = chats.filter(c =>
        (c.title || "").toLowerCase().includes(ql) ||
        (c.preview || "").toLowerCase().includes(ql));
    }

    if (!chats.length) {
      els.chats.innerHTML = `<div class="chats-empty">${q ? "Nada encontrado." : "Nenhuma conversa ainda."}</div>`;
      return;
    }

    let html = "", lastGroup = null;
    for (const c of chats) {
      const g = groupLabel(c.timestamp);
      if (g !== lastGroup) { html += `<div class="chats-group">${g}</div>`; lastGroup = g; }
      html += `
        <div class="chat-item${c.id === state.chatId ? " active" : ""}" data-id="${escapeHtml(c.id)}" tabindex="0">
          <span class="chat-item-title">${escapeHtml(c.title || "Sem título")}</span>
          ${c.preview ? `<span class="chat-item-preview">${escapeHtml(c.preview)}</span>` : ""}
          <div class="chat-item-actions">
            <button class="icon-btn ren" data-id="${escapeHtml(c.id)}" title="Renomear">${icon("pencil")}</button>
            <button class="icon-btn del" data-id="${escapeHtml(c.id)}" title="Apagar">${icon("trash")}</button>
          </div>
        </div>`;
    }
    els.chats.innerHTML = html;

    els.chats.querySelectorAll(".chat-item").forEach(item => {
      item.addEventListener("click", (e) => {
        if (e.target.closest(".chat-item-actions")) return;
        openChat(item.dataset.id);
      });
      item.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.target.closest("input")) openChat(item.dataset.id);
      });
    });
    els.chats.querySelectorAll(".del").forEach(btn =>
      btn.addEventListener("click", async () => {
        const ok = await confirmDialog("Apagar esta conversa? Essa ação não pode ser desfeita.");
        if (!ok) return;
        await fetch(`/api/chats/${btn.dataset.id}`, { method: "DELETE" });
        if (state.chatId === btn.dataset.id) newChat(false);
        loadChats(els.search.value.trim());
      })
    );
    els.chats.querySelectorAll(".ren").forEach(btn =>
      btn.addEventListener("click", () => startRename(btn.dataset.id))
    );
  } catch { /* servidor fora */ }
}

function startRename(id) {
  const item = els.chats.querySelector(`.chat-item[data-id="${CSS.escape(id)}"]`);
  if (!item) return;
  const titleEl = item.querySelector(".chat-item-title");
  const old = titleEl.textContent;
  const input = document.createElement("input");
  input.className = "rename";
  input.value = old;
  input.maxLength = 80;
  titleEl.replaceWith(input);
  input.focus();
  input.select();

  let done = false;
  const finish = async (save) => {
    if (done) return;
    done = true;
    const val = input.value.trim();
    if (save && val && val !== old) {
      try {
        const r = await fetch(`/api/chats/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: val }),
        });
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "falhou");
        if (state.chatId === id) els.title.textContent = val;
      } catch (e) {
        toast("Não deu para renomear: " + e.message, true);
      }
    }
    loadChats(els.search.value.trim());
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") finish(true);
    else if (e.key === "Escape") finish(false);
    e.stopPropagation();
  });
  input.addEventListener("blur", () => finish(true));
  input.addEventListener("click", (e) => e.stopPropagation());
}

async function openChat(id) {
  if (state.processing) { toast("Espera a EVE terminar de responder."); return; }
  try {
    const r = await fetch(`/api/chats/${id}`);
    if (!r.ok) throw new Error("chat não encontrado");
    const chat = await r.json();
    state.chatId = id;
    state.history = chat.messages || [];
    els.messages.innerHTML = "";
    for (const m of state.history) {
      addMessage(m.role, m.content, m.meta || null,
        (m.images || []).map(p => "/api/uploads/" + p.split(/[\\/]/).pop()),
        m.timestamp || null);
    }
    if (!state.history.length) showWelcome();
    els.title.textContent = chat.title || "Nova conversa";
    closeSidebarMobile();
    loadChats(els.search.value.trim());
    state.atBottom = true;
    els.jump.hidden = true;
    scrollToEnd(true);
  } catch (e) {
    toast("Erro ao abrir conversa: " + e.message, true);
  }
}

async function newChat(callApi = true) {
  if (state.processing) { toast("Espera a EVE terminar de responder."); return; }
  if (callApi) {
    try {
      const r = await fetch("/api/chats/new", { method: "POST" });
      state.chatId = (await r.json()).id;
    } catch { state.chatId = null; }
  } else {
    state.chatId = null;
  }
  state.history = [];
  els.title.textContent = "Nova conversa";
  showWelcome();
  loadChats(els.search.value.trim());
  closeSidebarMobile();
  els.input.focus();
}

/* ─── Exportar ─────────────────────────────────────────────────── */

function exportChat() {
  if (!state.history.length) { toast("Nada para exportar ainda."); return; }
  const title = els.title.textContent || "Conversa com EVE";
  const lines = [`# ${title}`, ""];
  for (const m of state.history) {
    lines.push(`**${m.role === "user" ? "Você" : "EVE"}:**`, "", m.content, "");
  }
  const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `eve_chat_${(state.chatId || "atual")}.md`;
  a.click();
  URL.revokeObjectURL(a.href);
  toast("Conversa exportada em Markdown.");
}

/* ─── Tema ─────────────────────────────────────────────────────── */

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("eve.theme", theme);
  els.theme.innerHTML = icon(theme === "dark" ? "sun" : "moon");
  els.theme.title = theme === "dark" ? "Tema claro" : "Tema escuro";
}

function initTheme() {
  const saved = localStorage.getItem("eve.theme");
  const preferred = matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  applyTheme(saved || preferred);
}

/* ─── Sidebar ──────────────────────────────────────────────────── */

const isMobile = () => matchMedia("(max-width: 900px)").matches;

function toggleSidebar() {
  if (isMobile()) {
    const open = els.sidebar.classList.toggle("open");
    els.scrim.classList.toggle("show", open);
    els.scrim.hidden = !open;
  } else {
    const hidden = els.app.classList.toggle("sidebar-hidden");
    localStorage.setItem("eve.sidebar", hidden ? "hidden" : "shown");
  }
}

function closeSidebarMobile() {
  els.sidebar.classList.remove("open");
  els.scrim.classList.remove("show");
  els.scrim.hidden = true;
}

/* ─── Composer ─────────────────────────────────────────────────── */

function autoGrow() {
  els.input.style.height = "auto";
  els.input.style.height = Math.min(els.input.scrollHeight, 200) + "px";
}

const saveDraft = debounce(() => {
  const v = els.input.value;
  if (v.trim()) localStorage.setItem("eve.draft", v);
  else localStorage.removeItem("eve.draft");
}, 300);

/* ─── Eventos ──────────────────────────────────────────────────── */

els.send.addEventListener("click", () => state.processing ? stopGeneration() : send());
els.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
els.input.addEventListener("input", () => { autoGrow(); saveDraft(); });

els.code.addEventListener("click", () => {
  state.codeMode = !state.codeMode;
  els.code.classList.toggle("active", state.codeMode);
  updateHint();
});

els.attach.addEventListener("click", () => els.fileInput.click());
els.fileInput.addEventListener("change", () => {
  uploadFiles([...els.fileInput.files]);
  els.fileInput.value = "";
});

// Colar imagem direto no chat
document.addEventListener("paste", (e) => {
  const files = [...(e.clipboardData?.files || [])].filter(f => f.type.startsWith("image/"));
  if (files.length) { e.preventDefault(); uploadFiles(files); }
});

// Arrastar e soltar imagem
document.addEventListener("dragover", (e) => e.preventDefault());
document.addEventListener("drop", (e) => {
  e.preventDefault();
  const files = [...(e.dataTransfer?.files || [])].filter(f => f.type.startsWith("image/"));
  if (files.length) uploadFiles(files);
});

els.newChat.addEventListener("click", () => newChat(true));
els.export.addEventListener("click", exportChat);
els.theme.addEventListener("click", () =>
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));

els.memory.addEventListener("click", async () => {
  const ok = await confirmDialog(
    "Limpar a memória de longo prazo da EVE? Ela vai esquecer preferências e fatos aprendidos.");
  if (!ok) return;
  try {
    const r = await fetch("/api/memory/clear", { method: "POST" });
    const j = await r.json();
    toast(j.cleared.length ? "Memória limpa." : "Nenhuma memória ativa para limpar.");
  } catch (e) { toast("Erro: " + e.message, true); }
});

els.burger.addEventListener("click", toggleSidebar);
els.sidebarClose.addEventListener("click", closeSidebarMobile);
els.scrim.addEventListener("click", closeSidebarMobile);
els.jump.addEventListener("click", () => { state.atBottom = true; scrollToEnd(true); els.jump.hidden = true; });

els.search.addEventListener("input", debounce(() => loadChats(els.search.value.trim()), 250));

// Ações nas mensagens e cópia de código (delegação)
document.addEventListener("click", (e) => {
  const copyCode = e.target.closest(".codeblock-copy");
  if (copyCode) {
    navigator.clipboard.writeText(copyCode.dataset.code).then(() => {
      copyCode.classList.add("ok");
      copyCode.innerHTML = `${icon("check")}copiado`;
      setTimeout(() => { copyCode.classList.remove("ok"); copyCode.innerHTML = `${icon("copy")}copiar`; }, 1800);
    });
    return;
  }
  const copyMsg = e.target.closest(".act-copy");
  if (copyMsg) {
    const msg = copyMsg.closest(".msg");
    const idx = [...els.messages.querySelectorAll(".msg")].indexOf(msg);
    const h = state.history[idx];
    const text = h ? h.content : msg.querySelector(".msg-content").textContent;
    navigator.clipboard.writeText(text).then(() => toast("Mensagem copiada."));
    return;
  }
  if (e.target.closest(".act-regen")) regenerate();
});

// Atalhos globais
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (!els.modelMenu.hidden) { closeModelMenu(); return; }
    if (state.processing) { stopGeneration(); return; }
    if (isMobile() && els.sidebar.classList.contains("open")) closeSidebarMobile();
    return;
  }
  if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === "k") {
    e.preventDefault();
    if (isMobile()) { els.sidebar.classList.add("open"); els.scrim.hidden = false; els.scrim.classList.add("show"); }
    else els.app.classList.remove("sidebar-hidden");
    els.search.focus();
  }
  if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "o") {
    e.preventDefault();
    newChat(true);
  }
});

/* ─── Boot ─────────────────────────────────────────────────────── */

function boot() {
  // ícones estáticos
  els.newChat.querySelector(".btn-new-icon").innerHTML = icon("plus");
  document.querySelector(".search-icon").innerHTML = icon("search");
  els.burger.innerHTML = icon("menu");
  els.sidebarClose.innerHTML = icon("x");
  els.export.innerHTML = icon("download");
  els.memory.innerHTML = icon("eraser");
  els.attach.innerHTML = icon("image");
  els.code.innerHTML = icon("code");
  els.jump.innerHTML = icon("arrowDown");
  els.modelBtn.querySelector(".model-pick-chevron").innerHTML = icon("chevronDown");

  initTheme();
  setBusy(false);
  updateModelButton();

  if (!isMobile() && localStorage.getItem("eve.sidebar") === "hidden") {
    els.app.classList.add("sidebar-hidden");
  }

  const draft = localStorage.getItem("eve.draft");
  if (draft) { els.input.value = draft; autoGrow(); }

  showWelcome();
  loadChats();
  loadModels();
  refreshStatus();
  setInterval(refreshStatus, 30000);
  els.input.focus();
}

boot();
