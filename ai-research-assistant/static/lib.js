/* Pure helpers: markdown renderer + citation token prep. Usable from node for tests. */
(function (root) {
  const CH_O = '\uE000', CH_C = '\uE001', CH_U = '\uE002';

  function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  function inline(s) {
    s = esc(s);
    const codes = [];
    s = s.replace(/`([^`\n]+)`/g, (m, c) => { codes.push(c); return '\uE010' + (codes.length - 1) + '\uE011'; });
    s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^*\w])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    s = s.replace(/\uE010(\d+)\uE011/g, (m, i) => '<code>' + codes[+i] + '</code>');
    return s;
  }

  function md(src) {
    const lines = src.replace(/\r/g, '').split('\n');
    const out = [];
    let i = 0, para = [], list = null;
    const flushPara = () => { if (para.length) { out.push('<p>' + inline(para.join(' ')) + '</p>'); para = []; } };
    const flushList = () => { if (list) { out.push('</' + list + '>'); list = null; } };
    while (i < lines.length) {
      const ln = lines[i];
      if (/^```/.test(ln)) {
        flushPara(); flushList();
        const code = []; i++;
        while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
        i++;
        out.push('<pre><code>' + esc(code.join('\n')) + '</code></pre>');
        continue;
      }
      if (/^\s*\|.*\|\s*$/.test(ln) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
        flushPara(); flushList();
        const row = (l) => l.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
        const head = row(ln); i += 2;
        let t = '<div class="tbl"><table><thead><tr>' + head.map((h) => '<th>' + inline(h) + '</th>').join('') + '</tr></thead><tbody>';
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
          t += '<tr>' + row(lines[i]).map((c) => '<td>' + inline(c) + '</td>').join('') + '</tr>'; i++;
        }
        out.push(t + '</tbody></table></div>');
        continue;
      }
      let m;
      if ((m = /^(#{1,4})\s+(.*)$/.exec(ln))) {
        flushPara(); flushList();
        const lv = Math.min(m[1].length + 1, 5);
        out.push('<h' + lv + '>' + inline(m[2]) + '</h' + lv + '>'); i++; continue;
      }
      if ((m = /^\s*[-*•]\s+(.*)$/.exec(ln))) {
        flushPara();
        if (list !== 'ul') { flushList(); out.push('<ul>'); list = 'ul'; }
        out.push('<li>' + inline(m[1]) + '</li>'); i++; continue;
      }
      if ((m = /^\s*\d+[.)]\s+(.*)$/.exec(ln))) {
        flushPara();
        if (list !== 'ol') { flushList(); out.push('<ol>'); list = 'ol'; }
        out.push('<li>' + inline(m[1]) + '</li>'); i++; continue;
      }
      if ((m = /^>\s?(.*)$/.exec(ln))) {
        flushPara(); flushList();
        out.push('<blockquote>' + inline(m[1]) + '</blockquote>'); i++; continue;
      }
      if (/^\s*([-*_])\1{2,}\s*$/.test(ln)) { flushPara(); flushList(); out.push('<hr>'); i++; continue; }
      if (!ln.trim()) { flushPara(); flushList(); i++; continue; }
      flushList();
      para.push(ln.trim()); i++;
    }
    flushPara(); flushList();
    return out.join('\n');
  }

  const LIVE = /\[\s*((?:S\s*\d+)(?:\s*[,;\/&]\s*(?:S\s*\d+))*)\s*\]/gi;

  // Convert raw model text (live [S#] tags or stored [[c:ID]] tags) to private-use tokens.
  function prep(raw, sources) {
    const byN = {};
    (sources || []).forEach((s) => { if (s.n) byN[s.n] = s; });
    raw = raw.replace(LIVE, (m, g) => (g.match(/\d+/g) || []).map((n) => {
      const s = byN[+n];
      return CH_O + (s ? s.id : '?') + CH_C;
    }).join(''));
    raw = raw.replace(/\[\[c:([^\]]+)\]\]/g, CH_O + '$1' + CH_C).replace(/\[\[u\]\]/g, CH_U);
    return raw;
  }

  function chipHtml(id, srcById, msgIdx, multi) {
    if (id === '?') return '<span class="cite bad" title="This citation could not be verified against the retrieved passages">?</span>';
    const s = srcById[id];
    if (!s) return '<span class="cite gone" title="Source no longer available">src</span>';
    const label = (multi ? shortName(s.doc) + ' · ' : '') + 'p.' + s.page;
    return '<button class="cite" data-c="' + esc(id) + '" data-m="' + msgIdx + '" title="' + esc(s.doc + ' — page ' + s.page + (s.section ? ' — ' + s.section : '')) + '">' + esc(label) + '</button>';
  }

  function shortName(n) { n = (n || '').replace(/\.pdf$/i, ''); return n.length > 14 ? n.slice(0, 13) + '…' : n; }

  function render(raw, sources, msgIdx) {
    const srcById = {};
    (sources || []).forEach((s) => { srcById[s.id] = s; });
    const multi = new Set((sources || []).map((s) => s.doc_id)).size > 1;
    let html = md(prep(raw, sources));
    html = html.replace(new RegExp(CH_O + '([^' + CH_C + ']*)' + CH_C, 'g'), (m, id) => chipHtml(id, srcById, msgIdx, multi));
    html = html.replace(new RegExp(CH_U, 'g'), '<span class="unsrc" title="No supporting source was cited for this statement — verify before relying on it">⚑</span>');
    return html;
  }

  const api = { esc, md, inline, prep, render, shortName };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Lib = api;
})(typeof window !== 'undefined' ? window : globalThis);
