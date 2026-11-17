(() => {
'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const { esc, render } = Lib;

/* ---------- icons ---------- */
const ICONS = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  upload: '<path d="M12 16V4m0 0L8 8m4-4 4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5zM4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/>',
  spark: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/>',
  bulb: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z"/>',
  quiz: '<circle cx="12" cy="12" r="9"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 2.5-3 4M12 17.5h.01"/>',
  slides: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
  send: '<path d="M5 12l14-7-5 14-2.5-5.5z"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>',
  download: '<path d="M12 4v12m0 0l-4-4m4 4l4-4M4 20h16"/>',
  bolt: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5"/>'
};
const ico = (n) => `<svg class="i" viewBox="0 0 24 24">${ICONS[n] || ''}</svg>`;
function hydrate(root = document) {
  $$('[data-i]', root).forEach((el) => { if (!el.dataset.done) { el.insertAdjacentHTML('afterbegin', ico(el.dataset.i)); el.dataset.done = 1; } });
}
$$('[data-close]').forEach((b) => { b.dataset.i = 'x'; });
hydrate();

/* ---------- state ---------- */
const S = {
  token: localStorage.getItem('tok'), user: null, docs: [], sel: new Set(), sessions: [], sid: null, msgs: [],
  busy: false, ctrl: null, mode: 'ask', hasKey: true, active: -1, level: 'medium', qn: 5, sn: 8, authTab: 'login'
};

/* ---------- helpers ---------- */
function toast(html, cls = '', ms = 3800) {
  const t = document.createElement('div');
  t.className = 'toast ' + cls; t.innerHTML = html;
  $('#toasts').appendChild(t);
  if (ms) setTimeout(() => t.remove(), ms);
  return t;
}
async function api(path, opts = {}) {
  const h = { ...(opts.headers || {}) };
  if (S.token) h.Authorization = 'Bearer ' + S.token;
  let body = opts.body;
  if (body && !(body instanceof FormData)) { h['Content-Type'] = 'application/json'; body = JSON.stringify(body); }
  const r = await fetch('/api' + path, { method: opts.method || (body ? 'POST' : 'GET'), headers: h, body, signal: opts.signal });
  if (!r.ok) {
    if (r.status === 401 && !path.startsWith('/auth/')) { logout(true); throw new Error('Session expired'); }
    let d = '';
    try { d = (await r.json()).detail; } catch (e) { /* ignore */ }
    if (Array.isArray(d)) d = d.map((x) => x.msg).join('; ');
    throw new Error(d || `Request failed (${r.status})`);
  }
  return r;
}
const json = async (p, o) => (await api(p, o)).json();
const isNarrow = () => matchMedia('(max-width:1180px)').matches;

/* ---------- auth ---------- */
function showAuth() { $('#auth').classList.remove('hidden'); $('#app').classList.add('hidden'); }
function setAuthTab(t) {
  S.authTab = t;
  $$('#authTabs button').forEach((b) => b.classList.toggle('on', b.dataset.tab === t));
  $('#aName').classList.toggle('hidden', t !== 'register');
  $('#authSubmit').textContent = t === 'login' ? 'Log in' : 'Create account';
  $('#aPass').autocomplete = t === 'login' ? 'current-password' : 'new-password';
}
$('#authTabs').onclick = (e) => { const b = e.target.closest('button'); if (b) setAuthTab(b.dataset.tab); };
async function authDone(r) {
  S.token = r.token; localStorage.setItem('tok', r.token); S.user = r.user; await enter();
}
$('#btnGuest').onclick = async () => {
  const b = $('#btnGuest'); b.disabled = true;
  try { await authDone(await json('/auth/guest', { method: 'POST' })); }
  catch (e) { toast(e.message, 'err'); } finally { b.disabled = false; }
};
$('#authForm').onsubmit = async (e) => {
  e.preventDefault();
  const err = $('#authErr'); err.classList.add('hidden');
  try {
    const body = { email: $('#aEmail').value, password: $('#aPass').value };
    if (S.authTab === 'register') body.name = $('#aName').value;
    await authDone(await json('/auth/' + S.authTab, { method: 'POST', body }));
  } catch (ex) { err.textContent = ex.message; err.classList.remove('hidden'); }
};
function logout(silent) {
  localStorage.removeItem('tok'); S.token = null; S.user = null; S.msgs = []; S.docs = []; S.sel.clear(); S.sid = null;
  showAuth(); if (!silent) toast('Logged out');
}
$('#btnLogout').onclick = () => logout();

async function enter() {
  $('#auth').classList.add('hidden'); $('#app').classList.remove('hidden');
  const u = S.user;
  $('#uName').textContent = u.name || 'Guest';
  $('#uMail').textContent = (u.email || '').endsWith('@local') ? 'Local guest session' : u.email;
  $('#uAvatar').textContent = (u.name || 'G')[0].toUpperCase();
  try {
    const me = await json('/me'); S.hasKey = me.has_key; $('#setModel').value = me.model;
  } catch (e) { return; }
  $('#keyPill').classList.toggle('hidden', S.hasKey);
  await Promise.all([loadDocs(), loadSessions()]);
  newChat();
  if (!S.hasKey && !sessionStorage.getItem('keyAsked')) { sessionStorage.setItem('keyAsked', 1); openSettings(); }
}

/* ---------- documents ---------- */
async function loadDocs() {
  S.docs = (await json('/documents')).filter((d) => d.status === 'ready');
  const ids = new Set(S.docs.map((d) => d.doc_id));
  [...S.sel].forEach((i) => { if (!ids.has(i)) S.sel.delete(i); });
  renderDocs(); if (!S.msgs.length) renderFeed();
}
const stem = (n) => n.replace(/\.pdf$/i, '');
function renderDocs() {
  $('#docCount').textContent = S.docs.length;
  const list = $('#docList');
  if (!S.docs.length) { list.innerHTML = '<div class="empty">No papers yet. Upload a PDF to begin.</div>'; }
  else {
    list.innerHTML = S.docs.map((d) => `
      <div class="doc ${S.sel.has(d.doc_id) ? 'sel' : ''}" data-id="${d.doc_id}">
        <span class="ck"></span>
        <div class="meta"><div class="nm" title="${esc(d.filename)}">${esc(stem(d.filename))}</div>
        <div class="sub">${d.page_count} pages · ${d.chunk_count} passages</div></div>
        <button class="icon-btn del" data-del="${d.doc_id}" title="Delete">${ico('trash')}</button>
      </div>`).join('');
  }
  const n = S.docs.length;
  $('#scopeText').textContent = !n ? 'No papers yet — upload a PDF'
    : S.sel.size === 0 ? (n === 1 ? stem(S.docs[0].filename) : `All ${n} papers`)
      : S.sel.size === 1 ? stem(S.docs.find((d) => S.sel.has(d.doc_id)).filename) : `${S.sel.size} papers selected`;
}
$('#docList').onclick = async (e) => {
  const del = e.target.closest('[data-del]');
  if (del) {
    e.stopPropagation();
    if (!confirm('Delete this paper and its indexed data?')) return;
    try { await api('/documents/' + del.dataset.del, { method: 'DELETE' }); await loadDocs(); toast('Paper deleted'); }
    catch (ex) { toast(ex.message, 'err'); }
    return;
  }
  const d = e.target.closest('.doc'); if (!d) return;
  const id = +d.dataset.id; S.sel.has(id) ? S.sel.delete(id) : S.sel.add(id);
  renderDocs(); if (!S.msgs.length) renderFeed();
};
async function upload(files) {
  const pdfs = [...files].filter((f) => /\.pdf$/i.test(f.name) || f.type === 'application/pdf');
  if (!pdfs.length) return toast('Please choose PDF files', 'err');
  const fd = new FormData(); pdfs.forEach((f) => fd.append('files', f));
  const t = toast(`<span class="spin"></span>Indexing ${pdfs.length > 1 ? pdfs.length + ' papers' : esc(pdfs[0].name)}…`, '', 0);
  try {
    const r = await json('/documents', { method: 'POST', body: fd });
    t.remove();
    r.results.forEach((x) => x.error ? toast(`${esc(x.filename)}: ${esc(x.error)}`, 'err', 7000)
      : toast(`✓ <b>${esc(x.filename)}</b> ready · ${x.pages} pages · ${x.seconds}s`, 'ok'));
    if (S.sel.size) r.results.forEach((x) => x.doc_id && S.sel.add(x.doc_id));
    await loadDocs();
  } catch (e) { t.remove(); toast(e.message, 'err'); }
}
$('#fileInput').onchange = (e) => { upload(e.target.files); e.target.value = ''; };
['dragenter', 'dragover'].forEach((ev) => window.addEventListener(ev, (e) => { e.preventDefault(); $$('.drop,.bigdrop').forEach((d) => d.classList.add('over')); }));
['dragleave', 'drop'].forEach((ev) => window.addEventListener(ev, (e) => {
  e.preventDefault();
  if (ev === 'dragleave' && e.relatedTarget) return;
  $$('.drop,.bigdrop').forEach((d) => d.classList.remove('over'));
  if (ev === 'drop' && e.dataTransfer && e.dataTransfer.files.length && S.token) upload(e.dataTransfer.files);
}));

/* ---------- sessions ---------- */
async function loadSessions() { S.sessions = await json('/sessions'); renderSessions(); }
function renderSessions() {
  const l = $('#sessList');
  l.innerHTML = S.sessions.length ? S.sessions.map((s) => `
    <div class="sess ${s.session_id === S.sid ? 'on' : ''}" data-id="${s.session_id}">
      <span>${esc(s.title || 'Chat')}</span><button class="icon-btn del" data-del="${s.session_id}" title="Delete">${ico('trash')}</button>
    </div>`).join('') : '<div class="empty">Your conversations will appear here.</div>';
}
$('#sessList').onclick = async (e) => {
  const del = e.target.closest('[data-del]');
  if (del) {
    e.stopPropagation();
    await api('/sessions/' + del.dataset.del, { method: 'DELETE' });
    if (+del.dataset.del === S.sid) newChat();
    return loadSessions();
  }
  const s = e.target.closest('.sess'); if (s) openSession(+s.dataset.id);
};
async function openSession(id) {
  try {
    const rows = await json(`/sessions/${id}/messages`);
    S.sid = id;
    S.msgs = rows.map((m) => ({ role: m.role, kind: m.kind === 'tool' ? 'text' : m.kind, content: m.content, sources: m.sources || [], tool: m.kind === 'tool' }));
    S.active = -1;
    for (let i = S.msgs.length - 1; i >= 0; i--) if (S.msgs[i].role === 'assistant' && S.msgs[i].sources.length) { S.active = i; break; }
    renderFeed(); renderSources(); renderSessions(); closeDrawers();
  } catch (e) { toast(e.message, 'err'); }
}
function newChat() {
  S.sid = null; S.msgs = []; S.active = -1; setMode('ask');
  renderFeed(); renderSources(); renderSessions(); closeDrawers();
  $('#input').focus();
}
$('#btnNew').onclick = newChat;

/* ---------- feed rendering ---------- */
const feed = $('#feed'), wrap = $('.feed-wrap');
function scrollDown(force) {
  const near = wrap.scrollHeight - wrap.scrollTop - wrap.clientHeight < 160;
  if (force || near) wrap.scrollTop = wrap.scrollHeight;
}
function renderFeed() {
  feed.innerHTML = '';
  if (!S.msgs.length) { feed.appendChild(hero()); hydrate(feed); return; }
  S.msgs.forEach((_, i) => feed.appendChild(msgEl(i)));
  hydrate(feed); scrollDown(true);
}
function hero() {
  const d = document.createElement('div'); d.className = 'hero';
  const multi = S.docs.length > 1 && S.sel.size !== 1;
  if (!S.docs.length) {
    d.innerHTML = `<div class="glyph">${ico('spark')}</div>
      <h2>Read papers <em>10× faster</em></h2>
      <p>Upload a research paper and ask anything. Every answer comes with page-level citations you can verify.</p>
      <label class="bigdrop" for="fileInput">${ico('upload')}<b>Drop your PDF here</b><span>or click to choose files · text-based PDFs up to 50 MB</span></label>`;
    return d;
  }
  const sug = [
    ['Overview', 'Summarize the main contribution and results.'],
    ['Method', 'Explain the methodology step by step.'],
    ['Evaluation', 'What datasets, baselines and metrics were used?'],
    [multi ? 'Compare' : 'Limitations', multi ? 'Compare the papers: how do their approaches and results differ?' : 'What limitations and future work do the authors mention?']
  ];
  d.innerHTML = `<div class="glyph">${ico('spark')}</div>
    <h2>Ask your <em>${multi ? 'papers' : 'paper'}</em> anything</h2>
    <p>Answers are grounded in your PDF and cited by page. Pick a starter or type your own question.</p>
    <div class="suggest">${sug.map((s) => `<button data-s="${esc(s[1])}"><small>${s[0]}</small>${esc(s[1])}</button>`).join('')}</div>`;
  return d;
}
feed.addEventListener('click', (e) => {
  const s = e.target.closest('[data-s]'); if (s) { $('#input').value = s.dataset.s; send(); return; }
  const c = e.target.closest('button.cite'); if (c) showSource(+c.dataset.m, c.dataset.c);
  const a = e.target.closest('[data-act]');
  if (a) {
    const i = +a.closest('.msg').dataset.i;
    if (a.dataset.act === 'copy') { navigator.clipboard.writeText(plain(S.msgs[i])).then(() => toast('Copied to clipboard', 'ok', 1800)); }
    if (a.dataset.act === 'dl') download(i);
  }
});

function msgEl(i) {
  const m = S.msgs[i], el = document.createElement('div');
  el.dataset.i = i;
  if (m.role === 'user') { el.className = 'msg user'; el.innerHTML = `<div class="bubble">${esc(m.content)}</div>`; return el; }
  el.className = 'msg ai' + (m.error ? ' error' : '');
  el.innerHTML = `<div class="av">${ico('spark')}</div><div class="bubble"><div class="prose"></div><div class="mfoot"></div></div>`;
  fillBody(el, i); return el;
}
function fillBody(el, i) {
  const m = S.msgs[i], prose = $('.prose', el), foot = $('.mfoot', el);
  if (m.error) { prose.textContent = m.content; foot.innerHTML = ''; return; }
  if (m.pending && !m.content) { prose.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>'; foot.innerHTML = ''; return; }
  if (m.kind === 'quiz' && !m.pending) { prose.innerHTML = ''; prose.appendChild(quizEl(m, i)); }
  else prose.innerHTML = render(m.content, m.sources, i);
  foot.innerHTML = m.pending ? '' : `<button data-act="copy">${ico('copy')}Copy</button><button data-act="dl">${ico('download')}.md</button>` +
    (m.ms ? `<span class="t">${ico('bolt')}${(m.ms / 1000).toFixed(1)}s</span>` : '');
}
let rafId = 0;
function scheduleRender(i) {
  if (rafId) return;
  rafId = requestAnimationFrame(() => {
    rafId = 0; const el = feed.querySelector(`.msg[data-i="${i}"]`);
    if (el) { fillBody(el, i); scrollDown(); }
  });
}

/* ---------- quiz ---------- */
function quizEl(m, mi) {
  const wrapEl = document.createElement('div'); wrapEl.className = 'quiz';
  let data; try { data = JSON.parse(m.content); } catch (e) { wrapEl.textContent = 'Could not display this quiz.'; return wrapEl; }
  let done = 0, ok = 0; const total = data.questions.length;
  const score = document.createElement('div'); score.className = 'qscore hidden';
  data.questions.forEach((q, qi) => {
    const card = document.createElement('div'); card.className = 'qcard';
    card.innerHTML = `<h5>${qi + 1}. ${esc(q.q)}</h5>` + q.options.map((o, oi) =>
      `<button class="qopt" data-o="${oi}"><span class="lt">${'ABCDEFGH'[oi]}</span><span>${esc(o)}</span></button>`).join('') + '<div class="qexp hidden"></div>';
    card.onclick = (e) => {
      const b = e.target.closest('.qopt'); if (!b || b.disabled) return;
      const pick = +b.dataset.o; $$('.qopt', card).forEach((x) => { x.disabled = true; });
      $$('.qopt', card)[q.answer].classList.add('right');
      if (pick !== q.answer) b.classList.add('wrong'); else ok++;
      const ex = $('.qexp', card); ex.classList.remove('hidden');
      ex.innerHTML = (pick === q.answer ? '✅ <b>Correct.</b> ' : '❌ <b>Not quite.</b> ') + render(q.explanation || '', m.sources, mi) +
        (q.source ? ' ' + render('[[c:' + q.source + ']]', m.sources, mi) : '');
      if (++done === total) { score.classList.remove('hidden'); score.textContent = `Score: ${ok} / ${total} — ${ok === total ? 'perfect! 🎉' : ok >= total * 0.6 ? 'nice work 👏' : 'review the sources and try again'}`; }
    };
    wrapEl.appendChild(card);
  });
  wrapEl.appendChild(score); return wrapEl;
}

/* ---------- copy / download ---------- */
function plain(m) {
  const byId = {}; (m.sources || []).forEach((s) => { byId[s.id] = s; });
  if (m.kind === 'quiz') {
    try {
      return JSON.parse(m.content).questions.map((q, i) => `${i + 1}. ${q.q}\n` + q.options.map((o, k) => `   ${'ABCDEFGH'[k]}) ${o}`).join('\n') +
        `\n   Answer: ${'ABCDEFGH'[q.answer]} — ${q.explanation.replace(/\[\[c:[^\]]*\]\]/g, '')}`).join('\n\n');
    } catch (e) { return m.content; }
  }
  return m.content.replace(/\[\[c:([^\]]*)\]\]/g, (x, id) => byId[id] ? ` [${stem(byId[id].doc)}, p.${byId[id].page}]` : '').replace(/ ?\[\[u\]\]/g, '');
}
function download(i) {
  const blob = new Blob([plain(S.msgs[i])], { type: 'text/markdown' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'paper-assistant.md'; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

/* ---------- sources panel ---------- */
function renderSources() {
  const box = $('#pSources'), m = S.msgs[S.active];
  const srcs = m && m.sources ? m.sources : [];
  if (!srcs.length) {
    box.innerHTML = `<div class="empty" style="padding:14px;line-height:1.6">📎 Citations appear here.<br>Click any <span class="cite">p.5</span> chip in an answer to jump to the exact passage in your paper.</div>`;
    return;
  }
  box.innerHTML = `<div class="sec-title">${srcs.length} source${srcs.length > 1 ? 's' : ''} ${m.pending ? '· retrieved' : '· cited'}</div>` + srcs.map((s, k) => `
    <div class="src" data-id="${esc(s.id)}"><div class="h"><span class="n">${s.n || k + 1}</span>Page ${s.page}${s.section ? ' · ' + esc(s.section) : ''}</div>
    <div class="d">${esc(s.doc)}</div><div class="x">${esc(s.text)}</div><div class="more">Show more</div></div>`).join('');
}
$('#pSources').onclick = (e) => {
  const s = e.target.closest('.src'); if (!s) return;
  s.classList.toggle('open'); $('.more', s).textContent = s.classList.contains('open') ? 'Show less' : 'Show more';
};
function showSource(mi, id) {
  S.active = mi; renderSources(); setPanelTab('sources'); openPanel();
  const el = $(`#pSources .src[data-id="${CSS.escape(id)}"]`);
  if (el) { el.classList.add('open', 'flash'); $('.more', el).textContent = 'Show less'; el.scrollIntoView({ block: 'center', behavior: 'smooth' }); setTimeout(() => el.classList.remove('flash'), 1800); }
}
function setPanelTab(t) {
  $$('#panelTabs button').forEach((b) => b.classList.toggle('on', b.dataset.p === t));
  $('#pSources').classList.toggle('hidden', t !== 'sources'); $('#pTools').classList.toggle('hidden', t !== 'tools');
}
$('#panelTabs').onclick = (e) => { const b = e.target.closest('button'); if (b) setPanelTab(b.dataset.p); };

/* ---------- streaming runner ---------- */
function setBusy(b) {
  S.busy = b; $('#btnSend').classList.toggle('hidden', b); $('#btnStop').classList.toggle('hidden', !b);
  $$('[data-run],#quick button').forEach((x) => { x.disabled = b; });
}
async function run(path, body, label) {
  if (S.busy) return;
  if (!S.docs.length) return toast('Upload a PDF first', 'err');
  body.doc_ids = [...S.sel]; body.session_id = S.sid;
  S.msgs.push({ role: 'user', content: label });
  const ai = { role: 'assistant', kind: 'text', content: '', sources: [], pending: true };
  S.msgs.push(ai); const ui = S.msgs.length - 2, ai_i = S.msgs.length - 1;
  S.active = ai_i; renderFeed(); renderSources(); closeDrawers(); scrollDown(true);
  setBusy(true); S.ctrl = new AbortController();
  const t0 = performance.now(); let first = 0;
  try {
    const res = await api(path, { method: 'POST', body, signal: S.ctrl.signal });
    const reader = res.body.getReader(), dec = new TextDecoder(); let buf = '';
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1); if (!line) continue;
        let ev; try { ev = JSON.parse(line); } catch (e) { continue; }
        if (ev.t === 'meta') { if (!S.sid) { S.sid = ev.session_id; } ai.sources = ev.sources || []; renderSources(); }
        else if (ev.t === 'd') { if (!first) first = performance.now() - t0; ai.content += ev.x; scheduleRender(ai_i); }
        else if (ev.t === 'done') { ai.content = ev.content; ai.sources = ev.sources; ai.kind = ev.kind; ai.pending = false; ai.ms = first || performance.now() - t0; }
        else if (ev.t === 'err') { throw new Error(ev.message); }
      }
    }
    ai.pending = false;
    if (!ai.content) throw new Error('No response received. Please try again.');
  } catch (e) {
    if (e.name === 'AbortError') { ai.pending = false; if (!ai.content) { S.msgs.splice(ui, 2); } }
    else { ai.pending = false; ai.error = true; ai.content = e.message; ai.sources = []; if (/key/i.test(e.message)) { S.hasKey = false; $('#keyPill').classList.remove('hidden'); } }
  } finally {
    setBusy(false); S.ctrl = null; renderFeed(); renderSources(); scrollDown(true);
    loadSessions().catch(() => {});
  }
}
$('#btnStop').onclick = () => S.ctrl && S.ctrl.abort();

/* ---------- actions ---------- */
function setMode(m) {
  S.mode = m;
  $('#modeTag').classList.toggle('hidden', m === 'ask');
  $('#input').placeholder = m === 'explain' ? 'Type a concept, term or equation to explain simply…' : 'Ask anything about your papers…';
  if (m === 'explain') $('#input').focus();
}
$('#modeTag').onclick = () => setMode('ask');
function send() {
  const inp = $('#input'), t = inp.value.trim(); if (!t || S.busy) return;
  inp.value = ''; autosize();
  if (S.mode === 'explain') { setMode('ask'); run('/concept', { concept: t }, 'Explain simply: ' + t); }
  else run('/chat', { question: t }, t);
}
$('#btnSend').onclick = send;
$('#input').addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
const autosize = () => { const t = $('#input'); t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 180) + 'px'; };
$('#input').addEventListener('input', autosize);

function runTool(k) {
  if (k === 'summary') run('/summary', { level: S.level }, `${S.level[0].toUpperCase() + S.level.slice(1)} summary`);
  else if (k === 'quiz') run('/quiz', { count: S.qn }, `Quiz me (${S.qn} questions)`);
  else if (k === 'slides') run('/slides', { count: S.sn }, `Slide outline (${S.sn} slides)`);
  else if (k === 'explain') setMode('explain');
  else if (k === 'concept') {
    const c = $('#conceptIn').value.trim(); if (!c) return toast('Enter a concept first', 'err', 2000);
    run('/concept', { concept: c }, 'Explain simply: ' + c); $('#conceptIn').value = '';
  }
}
$('#quick').onclick = (e) => { const b = e.target.closest('[data-q]'); if (b) runTool(b.dataset.q); };
$('#pTools').onclick = (e) => {
  const r = e.target.closest('[data-run]'); if (r) return runTool(r.dataset.run);
  const sb = e.target.closest('.seg button'); if (!sb) return;
  $$('button', sb.parentElement).forEach((x) => x.classList.toggle('on', x === sb));
  const id = sb.parentElement.id, v = sb.dataset.v;
  if (id === 'segLevel') S.level = v; if (id === 'segQuiz') S.qn = +v; if (id === 'segSlides') S.sn = +v;
};
$('#conceptIn').addEventListener('keydown', (e) => { if (e.key === 'Enter') runTool('concept'); });

/* ---------- chrome: drawers, theme, settings ---------- */
function closeDrawers() { $('#sidebar').classList.remove('open'); $('#panel').classList.remove('open'); $('#scrim').classList.remove('on'); }
function openPanel() { if (isNarrow()) { $('#panel').classList.add('open'); $('#scrim').classList.add('on'); } }
$('#btnMenu').onclick = () => { $('#sidebar').classList.add('open'); $('#scrim').classList.add('on'); };
$('#btnPanel').onclick = () => { $('#panel').classList.toggle('open'); $('#scrim').classList.toggle('on', $('#panel').classList.contains('open')); };
$('#scrim').onclick = closeDrawers;
$$('[data-close]').forEach((b) => { b.onclick = closeDrawers; });

function applyTheme(t) {
  document.documentElement.dataset.theme = t; localStorage.setItem('theme', t);
  const b = $('#btnTheme'); b.innerHTML = ico(t === 'dark' ? 'sun' : 'moon');
}
$('#btnTheme').onclick = () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
applyTheme(document.documentElement.dataset.theme || 'dark');

function openSettings() { $('#modal').classList.remove('hidden'); $('#setKey').value = ''; $('#setKey').placeholder = S.hasKey ? '•••••••• (saved — leave blank to keep)' : 'AIza…'; }
$('#btnSettings').onclick = openSettings; $('#keyPill').onclick = openSettings;
$('#setCancel').onclick = () => $('#modal').classList.add('hidden');
$('#modal').onclick = (e) => { if (e.target.id === 'modal') $('#modal').classList.add('hidden'); };
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { $('#modal').classList.add('hidden'); closeDrawers(); } });
$('#setTest').onclick = async () => {
  const b = $('#setTest'); b.disabled = true; b.textContent = 'Testing…';
  try {
    const key = $('#setKey').value.trim(), model = $('#setModel').value.trim();
    if (key || model) { const r = await json('/settings', { method: 'POST', body: { api_key: key || null, model: model || null } }); S.hasKey = r.has_key; $('#keyPill').classList.toggle('hidden', S.hasKey); }
    const d = await json('/diagnose');
    toast(d.ok ? `✓ Connected to Gemini in ${d.seconds}s (${esc(d.model)})` : '✗ ' + esc(d.error), d.ok ? 'ok' : 'err', d.ok ? 4000 : 12000);
  } catch (e) { toast(e.message, 'err'); }
  b.disabled = false; b.textContent = 'Test connection';
};
$('#setSave').onclick = async () => {
  const key = $('#setKey').value.trim(), model = $('#setModel').value.trim();
  try {
    const r = await json('/settings', { method: 'POST', body: { api_key: key || null, model: model || null } });
    S.hasKey = r.has_key; $('#keyPill').classList.toggle('hidden', S.hasKey);
    $('#modal').classList.add('hidden'); toast(S.hasKey ? '✓ Saved — AI answers enabled' : 'Saved. Add an API key to enable AI answers.', S.hasKey ? 'ok' : '');
  } catch (e) { toast(e.message, 'err'); }
};

/* ---------- boot ---------- */
(async function boot() {
  setAuthTab('login');
  if (!S.token) return showAuth();
  try { S.user = (await json('/me')).user; await enter(); } catch (e) { showAuth(); }
})();
})();
