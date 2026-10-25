"""/ask: the "Ask BayCounty.me" chatbot page. Visitors ask questions in their own words and Claude answers from the
site's own data through the MCP tools (api/chat.js, api/_chat.js). The page holds no data of its own.

ASK_ICON is the chat bubble used here and on the header's Ask button (build_site.nav_html).
"""

ASK_ICON = ('<svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><path d="M4 4.5h12a1.5 1.5 0 0 1 1.5 1.5v7a1.5 1.5 0 0 1-1.5 1.5H9l-3.6 2.8V14.5H4A1.5 1.5 0 0 1 2.5 13V6A1.5 1.5 0 0 1 4 4.5z" '
            'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M6.5 8.3h7M6.5 11h4.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>')

SEND_ICON = '<svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><path d="M10 16V4M5 9l5-5 5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'

EXAMPLES = [
    'When is the next County Commission meeting?',
    "How did Lynn Haven's budget change from 2025 to 2026?",
    'Which companies get the most Bay County contracts?',
    'What did the auditors find for Panama City?',
    'How much debt does the school district have?',
    'What is the property tax rate in Callaway?',
]

CSS = '''
.ask-wrap{max-width:820px;width:100%;margin:0 auto;display:flex;flex-direction:column;gap:14px}
.ask-card{background:var(--surface);border-radius:var(--r-lg);box-shadow:var(--ui-shadow);display:flex;flex-direction:column;min-height:min(560px,70vh)}
.ask-log{flex:1;display:flex;flex-direction:column;gap:18px;padding:22px 22px 8px;overflow-wrap:anywhere}
.ask-empty[hidden]{display:none}
.ask-empty{display:flex;flex-direction:column;gap:14px;margin:auto 0;padding:12px 0}
.ask-empty h2{font-size:1.15rem}
.ask-empty p{margin:0;color:var(--muted);font-size:.92rem}
.ask-ex{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.ask-ex button{text-align:left;padding:12px 14px;border-radius:12px;border:1px solid var(--line);background:var(--sunken);color:var(--ink);font:500 .88rem/1.4 var(--f-body);cursor:pointer;transition:background-color .15s,border-color .15s}
.ask-ex button:hover{border-color:var(--blue);background:var(--tint-blue)}
.ask-m{display:flex;gap:10px;align-items:flex-start;max-width:100%}
.ask-m.me{justify-content:flex-end}
.ask-m.me .ask-b{background:var(--navy);color:var(--on-navy);border-radius:16px 16px 4px 16px;padding:10px 14px;max-width:85%;white-space:pre-wrap}
.ask-m.me .ask-b a{color:inherit;text-decoration:underline}
.ask-m.bot .ask-b{flex:1;min-width:0;line-height:1.6;font-size:.95rem}
.ask-av{flex:none;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;background:var(--tint-teal);color:var(--teal)}
.ask-b p{margin:0 0 .7em}.ask-b p:last-child{margin-bottom:0}
.ask-b ul,.ask-b ol{margin:0 0 .7em;padding-left:1.3em}.ask-b li{margin:.2em 0}
.ask-b a{color:var(--blue);text-decoration:underline;text-underline-offset:2px}
.ask-b code{font:500 .85em var(--f-data);background:var(--sunken);padding:1px 5px;border-radius:5px}
.ask-b .tw{overflow-x:auto;margin:0 0 .7em}
.ask-b table{border-collapse:collapse;font-size:.86rem;min-width:100%}
.ask-b th,.ask-b td{border-bottom:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}
.ask-b th{font-weight:600;background:var(--sunken)}
.ask-b td.n,.ask-b th.n{text-align:right;font-family:var(--f-data);white-space:nowrap}
.ask-b th.n{font-family:var(--f-body)}
.ask-b td:empty{display:none}
@media (max-width:640px){
  /* phones: each table row becomes a small card, so nothing is squeezed or scrolls sideways */
  .ask-b .tw{overflow:visible}
  .ask-b table,.ask-b tbody,.ask-b tr,.ask-b td{display:block;width:100%;min-width:0}
  .ask-b thead{display:none}
  .ask-b tr{border:1px solid var(--line);border-radius:10px;padding:8px 12px;margin:0 0 8px;background:var(--sunken)}
  .ask-b td,.ask-b td.n{border:0;padding:3px 0;display:flex;justify-content:space-between;gap:12px;text-align:right;white-space:normal;font-family:inherit;overflow-wrap:anywhere}
  .ask-b td::before{content:attr(data-l);color:var(--muted);font-family:var(--f-body);text-align:left;flex:none;max-width:45%}
  .ask-b td:first-child{display:block;text-align:left;font-weight:600;padding-bottom:5px}
  .ask-b td:first-child::before{content:none}
  .ask-b td.n{font-family:var(--f-data)}
}
.ask-st{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:.85rem}
.ask-st i{width:7px;height:7px;border-radius:50%;background:var(--teal);animation:askp 1s ease-in-out infinite}
@keyframes askp{50%{opacity:.25}}
@media (prefers-reduced-motion:reduce){.ask-st i{animation:none}}
.ask-err{color:var(--accent-ink);font-size:.9rem}
.ask-foot{display:flex;flex-direction:column;gap:8px;padding:12px 14px 14px;border-top:1px solid var(--line)}
.ask-form{display:flex;gap:8px;align-items:flex-end}
.ask-form textarea{flex:1;resize:none;min-height:48px;max-height:180px;padding:12px 14px;border-radius:14px;border:1px solid var(--line);background:var(--sunken);color:var(--ink);font:400 1rem/1.45 var(--f-body)}
.ask-form textarea::placeholder{color:var(--faint);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ask-form textarea:focus{outline:none;border-color:var(--blue);box-shadow:var(--ui-ring)}
.ask-send{flex:none;width:48px;height:48px;border-radius:14px;border:0;background:var(--navy);color:var(--on-navy);display:grid;place-items:center;cursor:pointer}
.ask-send:disabled{opacity:.45;cursor:default}
.ask-meta{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:.78rem;color:var(--muted)}
.ask-meta button{border:0;background:none;color:var(--blue);font:500 .78rem var(--f-body);cursor:pointer;padding:0}
.ask-note{font-size:.85rem;color:var(--muted);margin:0}
.ask-off{padding:14px 16px;border-radius:12px;background:var(--tint-amber);font-size:.9rem}
@media (max-width:640px){
  .ask-log{padding:16px 14px 6px}
  .ask-ex{grid-template-columns:1fr}
  .ask-av{display:none}
  .ask-m.me .ask-b{max-width:92%}
  .ask-card{min-height:62vh;border-radius:var(--r)}
}
'''

JS = r'''
(() => {
  const SITE = 'https://baycounty.me', KEY = 'bc-ask-v1';
  const $ = id => document.getElementById(id);
  const log = $('askLog'), form = $('askForm'), box = $('askQ'), send = $('askSend'), empty = $('askEmpty'), meta = $('askLeft');
  const TOOLS = {find_entity: 'Looking up names', get_entity: 'Checking connections', query_dataset: 'Reading the records', list_datasets: 'Finding the right records',
    get_government: 'Opening the government profile', compare_budget_years: 'Comparing budgets', government_checkbook: 'Reading the checkbook',
    budget_vs_actual: 'Checking the budget tracker', upcoming_meetings: 'Checking the meeting calendar', member_voting_record: 'Reading the voting record',
    vendor_profile: 'Looking up the company', official_correspondence: 'Reading letters to officials', search_site: 'Searching the site'};
  let msgs = [], busy = false;
  try { msgs = JSON.parse(sessionStorage.getItem(KEY) || '[]').filter(m => m && m.role && typeof m.content === 'string'); } catch (e) { msgs = []; }
  const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify(msgs.slice(-20))); } catch (e) {} };
  const esc = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

  // Links: pages on this site always; other sites only when the URL came back in the data (sources).
  function href(u, sources) {
    u = u.trim();
    if (u.startsWith('/') && !u.startsWith('//')) return u;
    if (u.startsWith(SITE + '/') || u === SITE) return u.slice(SITE.length) || '/';
    if (/^https:\/\/(www\.)?baycounty\.me(\/|$)/.test(u)) return u.replace(/^https:\/\/(www\.)?baycounty\.me/, '') || '/';
    if (/^https?:\/\//.test(u) && sources && sources.has(u)) return u;
    return null;
  }
  function inline(s, sources) {
    const out = [];
    let rest = s;
    const rx = /\[([^\]]+)\]\(([^)\s]+)\)|\*\*([^*]+)\*\*|`([^`]+)`|(https?:\/\/[^\s)<>"]+[^\s)<>".,;:!?])/;
    let m;
    while ((m = rest.match(rx))) {
      out.push(esc(rest.slice(0, m.index)));
      if (m[1] !== undefined) {
        const h = href(m[2], sources);
        out.push(h ? `<a href="${esc(h)}"${h.startsWith('http') ? ' target="_blank" rel="noopener nofollow"' : ''}>${esc(m[1])}</a>` : esc(m[1]));
      } else if (m[3] !== undefined) out.push(`<b>${esc(m[3])}</b>`);
      else if (m[4] !== undefined) out.push(`<code>${esc(m[4])}</code>`);
      else { const h = href(m[5], sources); out.push(h ? `<a href="${esc(h)}"${h.startsWith('http') ? ' target="_blank" rel="noopener nofollow"' : ''}>${esc(m[5].replace(/^https?:\/\/(www\.)?/, ''))}</a>` : esc(m[5])); }
      rest = rest.slice(m.index + m[0].length);
    }
    out.push(esc(rest));
    return out.join('');
  }
  const num = c => /^[-$(]?[\d,.]+%?\)?[MKB]?$/.test(c.replace(/\*/g, '').trim());
  // A small markdown subset: paragraphs, bullet and numbered lists, tables, headings (as bold lines).
  function md(text, sources) {
    const lines = text.replace(/\r/g, '').split('\n'), out = [];
    let i = 0;
    while (i < lines.length) {
      const l = lines[i];
      if (!l.trim()) { i++; continue; }
      if (/^\s*\|/.test(l) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
        const row = s => s.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());
        const head = row(l); i += 2; const body = [];
        while (i < lines.length && /^\s*\|/.test(lines[i])) body.push(row(lines[i++]));
        const isN = head.map((_, j) => body.length && body.every(r => !r[j] || num(r[j])));
        out.push(`<div class="tw"><table data-tt="off" data-stack="off"><thead><tr>${head.map((c, j) => `<th${isN[j] ? ' class="n"' : ''}>${inline(c, sources)}</th>`).join('')}</tr></thead><tbody>${
          body.map(r => `<tr>${head.map((h, j) => `<td data-l="${esc(h.replace(/[*_\x60]/g, ''))}"${isN[j] ? ' class="n"' : ''}>${inline(r[j] || '', sources)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
        continue;
      }
      if (/^\s*([-*•]|\d+[.)])\s+/.test(l)) {
        const ordered = /^\s*\d/.test(l), items = [];
        while (i < lines.length && /^\s*([-*•]|\d+[.)])\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*([-*•]|\d+[.)])\s+/, ''));
        out.push(`<${ordered ? 'ol' : 'ul'}>${items.map(x => `<li>${inline(x, sources)}</li>`).join('')}</${ordered ? 'ol' : 'ul'}>`);
        continue;
      }
      const para = [lines[i++]];  // always take at least one line, so a stray "|" line can't stall the loop
      while (i < lines.length && lines[i].trim() && !/^\s*([-*•]|\d+[.)])\s+/.test(lines[i]) && !/^\s*\|/.test(lines[i])) para.push(lines[i++]);
      const h = para.length === 1 && /^#{1,4}\s+/.test(para[0]);
      out.push(h ? `<p><b>${inline(para[0].replace(/^#+\s+/, ''), sources)}</b></p>` : `<p>${para.map(x => inline(x.replace(/^#+\s+/, ''), sources)).join('<br>')}</p>`);
    }
    return out.join('');
  }

  const AV = '<span class="ask-av" aria-hidden="true">__ICON__</span>';
  function bubble(role, html) {
    const d = document.createElement('div');
    d.className = 'ask-m ' + (role === 'user' ? 'me' : 'bot');
    d.innerHTML = role === 'user' ? `<div class="ask-b" data-nolink>${esc(html)}</div>` : `${AV}<div class="ask-b">${html}</div>`;
    log.appendChild(d);
    return d.querySelector('.ask-b');
  }
  function draw() {
    log.querySelectorAll('.ask-m').forEach(n => n.remove());
    empty.hidden = msgs.length > 0;
    for (const m of msgs) bubble(m.role, m.role === 'user' ? m.content : md(m.content, new Set(m.sources || [])));
  }
  const scroll = () => { const r = log.lastElementChild && log.lastElementChild.getBoundingClientRect(); if (r && r.bottom > innerHeight - 140) window.scrollBy({top: r.bottom - innerHeight + 160, behavior: 'smooth'}); };

  async function ask(q) {
    if (busy || !q.trim()) return;
    busy = true; send.disabled = true; box.value = ''; fit();
    msgs.push({role: 'user', content: q.trim()}); save();
    empty.hidden = true; bubble('user', q.trim());
    const b = bubble('assistant', '<div class="ask-st"><i></i><span>Looking at the records…</span></div>');
    scroll();
    let text = '', sources = new Set(), failed = '';
    const paint = () => { b.innerHTML = md(text, sources) || '<div class="ask-st"><i></i><span>Looking at the records…</span></div>'; };
    try {
      const r = await fetch('/api/chat', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({messages: msgs.map(m => ({role: m.role, content: m.content}))})});
      if (!r.ok || !(r.headers.get('content-type') || '').includes('event-stream')) {
        const j = await r.json().catch(() => ({}));
        throw new Error(j.error || 'Something went wrong. Please try again.');
      }
      const rd = r.body.getReader(), dec = new TextDecoder();
      let buf = '';
      for (;;) {
        const {value, done} = await rd.read();
        if (done) break;
        buf += dec.decode(value, {stream: true});
        let k;
        while ((k = buf.indexOf('\n\n')) >= 0) {
          const chunk = buf.slice(0, k); buf = buf.slice(k + 2);
          const ev = (chunk.match(/^event: (.+)$/m) || [])[1], dl = (chunk.match(/^data: (.*)$/m) || [])[1];
          if (!ev || dl === undefined) continue;
          const d = JSON.parse(dl);
          if (ev === 'text') { text += d.text; paint(); }
          else if (ev === 'reset') { text = ''; paint(); }
          else if (ev === 'status') {
            const s = `<div class="ask-st"><i></i><span>${esc(TOOLS[d.tool] || 'Looking at the records')}…</span></div>`;
            b.innerHTML = (text ? md(text, sources) : '') + s;
          }
          else if (ev === 'done') {
            sources = new Set(d.sources || []); paint();
            if (d.remaining_hour != null) meta.textContent = d.remaining_hour > 3 ? '' : `${Math.max(0, d.remaining_hour)} question${d.remaining_hour === 1 ? '' : 's'} left this hour`;
          }
          else if (ev === 'error') failed = d.message;
        }
        scroll();
      }
      if (failed && !text) throw new Error(failed);
      if (!text) throw new Error('No answer came back. Please try again.');
      msgs.push({role: 'assistant', content: text, sources: [...sources]}); save();
      if (failed) b.insertAdjacentHTML('beforeend', `<p class="ask-err">${esc(failed)}</p>`);
    } catch (e) {
      msgs.pop(); save();
      // fetch() throws a TypeError ("Load failed" in Safari) when the connection drops, often because the phone left the page
      const m = e instanceof TypeError ? 'The connection dropped before the answer came back. This can happen if you switch apps or lock your phone while Ask is working. Keep this page open and tap send to try again.' : e.message;
      b.innerHTML = `<p class="ask-err">${esc(m)}</p>`;
      box.value = q; fit();
    }
    busy = false; send.disabled = false; box.focus({preventScroll: true});
  }

  function fit() { box.style.height = 'auto'; box.style.height = Math.min(box.scrollHeight, 180) + 'px'; }
  box.addEventListener('input', fit);
  box.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); } });
  form.addEventListener('submit', e => { e.preventDefault(); ask(box.value); });
  document.querySelectorAll('#askEx button').forEach(x => x.addEventListener('click', () => ask(x.textContent)));
  $('askNew').addEventListener('click', () => { if (busy) return; msgs = []; save(); draw(); meta.textContent = ''; box.focus(); });
  draw();
  fetch('/api/chat').then(r => r.json()).then(j => { if (!j.available) { $('askOff').hidden = false; } }).catch(() => {});
  const q0 = new URL(location.href).searchParams.get('q');
  if (q0) { history.replaceState(null, '', location.pathname); ask(q0.slice(0, 600)); }
})();
'''


def ask_page():
    ex = ''.join(f'<button type="button">{e}</button>' for e in EXAMPLES)
    js = JS.replace('__ICON__', ASK_ICON.replace('\n', ''))
    return f'''<div class="page tax ask">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Ask</span><h1>Ask BayCounty.me</h1>
    <p class="lede">Ask a question in your own words about Bay County budgets, taxes, votes, contracts, meetings or officials. Answers come from the records on this site, with links to each source.</p></div></header>
  <div class="ask-wrap">
    <p class="ask-off" id="askOff" hidden>Ask isn't turned on yet. In the meantime, <a href="/search">search the site</a>.</p>
    <section class="ask-card" aria-label="Chat">
      <div class="ask-log" id="askLog" aria-live="polite" data-nolinkify>
        <div class="ask-empty" id="askEmpty">
          <h2>Try a question</h2>
          <div class="ask-ex" id="askEx">{ex}</div>
        </div>
      </div>
      <div class="ask-foot">
        <form class="ask-form" id="askForm">
          <label class="sr" for="askQ">Your question</label>
          <textarea id="askQ" rows="1" maxlength="600" enterkeyhint="send" placeholder="Ask a question"></textarea>
          <button class="ask-send" id="askSend" type="submit" aria-label="Send">{SEND_ICON}</button>
        </form>
        <div class="ask-meta"><span id="askLeft" aria-live="polite"></span><button type="button" id="askNew">New chat</button></div>
      </div>
    </section>
    <p class="ask-note">Answers are written by AI and can be wrong, so check the linked records before relying on one. BayCounty.me is neutral and doesn't take sides. Your questions aren't saved, but please don't type personal information. <a href="/privacy">Privacy</a></p>
  </div>
</div>
<style>{CSS}</style>
<script>{js}</script>'''
