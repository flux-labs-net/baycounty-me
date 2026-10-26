// Import progress: renders GET /api/v1/import-progress (api/_progress.js) on /data-sources#progress, and the same
// numbers plus costs on the /admin "Import progress" tab. The page holds no data; everything comes from the API.
(function () {
  const CSS = `
.ip{display:flex;flex-direction:column;gap:16px;min-width:0}
.ip .tablewrap{overflow-x:auto;max-width:100%;-webkit-overflow-scrolling:touch}
.ip-phase{display:flex;align-items:flex-start;gap:12px;padding:14px 16px;border-radius:14px;background:var(--surface);border:1px solid var(--line)}
.ip-dot{flex:none;width:10px;height:10px;margin-top:6px;border-radius:50%;background:var(--faint,#9aa3ad)}
.ip-dot.active{background:var(--blue);box-shadow:0 0 0 4px color-mix(in srgb,var(--blue) 18%,transparent);animation:ip-pulse 2s ease-in-out infinite}
.ip-dot.done{background:var(--teal)}
@keyframes ip-pulse{50%{box-shadow:0 0 0 7px color-mix(in srgb,var(--blue) 6%,transparent)}}
@media (prefers-reduced-motion:reduce){.ip-dot.active{animation:none}}
.ip-phase b{display:block}.ip-phase small{color:var(--muted)}
.ip-stages{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;counter-reset:ip}
.ip-st{padding:14px 16px;border-radius:14px;background:var(--surface);border:1px solid var(--line);display:flex;flex-direction:column;gap:6px;counter-increment:ip}
.ip-st .l{font-size:.78rem;color:var(--muted)}.ip-st .l::before{content:counter(ip) ". "}
.ip-st .v{font:600 1.4rem/1.1 var(--f-display,inherit);font-variant-numeric:tabular-nums}
.ip-st .v small{font:500 .8rem var(--f-body,inherit);color:var(--muted)}
.ip-st .d{font-size:.78rem;color:var(--muted);min-height:1em}
.ip-bar{height:6px;border-radius:99px;background:color-mix(in srgb,var(--line) 70%,transparent);overflow:hidden}
.ip-bar i{display:block;height:100%;border-radius:99px;background:var(--blue);transition:width .4s}
.ip-st.done .ip-bar i{background:var(--teal)}
.ip-facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.ip-f{padding:12px 14px;border-radius:12px;background:var(--surface);border:1px solid var(--line)}
.ip-f b{display:block;font:600 1.1rem var(--f-display,inherit);font-variant-numeric:tabular-nums}.ip-f span{font-size:.78rem;color:var(--muted)}
.ip-grid{border-collapse:separate;border-spacing:3px;font-size:.78rem;min-width:760px;width:100%}
.ip-grid th{font-weight:600;color:var(--muted);font-size:.72rem;padding:4px;text-align:center}
.ip-grid tbody th{text-align:left;max-width:9.5em;white-space:normal!important;line-height:1.25;color:var(--ink,inherit);font-weight:500;position:sticky;left:0;background:var(--bg,var(--surface));z-index:1;padding-right:10px}
.ip-grid td{padding:0;text-align:center}
.ip-c{display:block;min-width:40px;padding:6px 2px;border-radius:7px;font:600 .72rem/1 var(--f-data,inherit);font-variant-numeric:tabular-nums}
.ip-done{background:var(--tint-teal,#e3f4f1);color:var(--teal)}
.ip-reviewing{background:var(--tint-teal,#e3f4f1);color:var(--teal);box-shadow:inset 0 0 0 1.5px color-mix(in srgb,var(--amber) 70%,transparent)}
.ip-reading{background:var(--tint-blue,#e6eefb);color:var(--blue)}
.ip-captured,.ip-found{background:var(--tint-amber,#fbf1dc);color:var(--gold,#8a6100)}
.ip-none_online{color:var(--faint,#9aa3ad);background:repeating-linear-gradient(135deg,transparent 0 4px,color-mix(in srgb,var(--line) 60%,transparent) 4px 5px)}
.ip-not_listed{color:var(--faint,#9aa3ad)}
.ip-tot{font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap;padding-left:8px!important;text-align:right!important}
.ip-key{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.8rem;color:var(--muted)}
.ip-key span{display:inline-flex;align-items:center;gap:6px}.ip-key .ip-c{min-width:22px;padding:4px}
.ip-notes{margin:0;padding-left:18px;font-size:.84rem;color:var(--muted);display:flex;flex-direction:column;gap:4px}
.ip-runs{font-size:.82rem}
.ip-cost .ip-bar{margin-top:6px}
.ip-h{margin:6px 0 0;font-size:1rem}
`;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const num = v => Number(v || 0).toLocaleString('en-US');
  const usd = v => '$' + Number(v || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const ago = t => {
    if (!t) return 'never';
    const s = (Date.now() - Date.parse(t)) / 1000;
    if (s < 90) return 'just now';
    if (s < 5400) return Math.round(s / 60) + ' minutes ago';
    if (s < 129600) return Math.round(s / 3600) + ' hours ago';
    return Math.round(s / 86400) + ' days ago';
  };
  const gov = (b) => (b.gov && window.BC && BC.href && BC.href('gov:' + b.gov) ? BC.a('gov:' + b.gov, b.name) : esc(b.name));
  const STATE = {done: 'Read', reviewing: 'Read, votes waiting for review', reading: 'Being read', captured: 'Stored, not read yet',
    found: 'Found, not downloaded yet', none_online: 'No minutes posted online', not_listed: 'Archive not counted yet'};

  function styles() {
    if (document.getElementById('ip-css')) return;
    const s = document.createElement('style'); s.id = 'ip-css'; s.textContent = CSS; document.head.appendChild(s);
  }

  function cell(b, c) {
    const label = `${b.name} ${c.year}: ${STATE[c.state]}. ${num(c.found)} files found, ${num(c.captured)} stored, ${num(c.read)} read, ${num(c.motions)} motions${c.flagged ? `, ${num(c.flagged)} waiting for review` : ''}.`;
    const text = c.state === 'none_online' ? '—' : c.state === 'not_listed' ? '·' : c.state === 'done' || c.state === 'reviewing' ? num(c.found) : `${num(c.read)}/${num(c.found)}`;
    return `<td><span class="ip-c ip-${c.state}" title="${esc(label)}" aria-label="${esc(label)}">${text}</span></td>`;
  }

  function render(el, d, opts = {}) {
    styles();
    if (!d || !d.installed) {
      el.innerHTML = `<div class="ip"><div class="ip-phase"><span class="ip-dot"></span><div><b>Progress isn’t available yet.</b><small>${esc((d && d.note) || 'Try again shortly.')}</small></div></div></div>`;
      return;
    }
    const T = d.totals, active = !['current', 'not_started'].includes(d.phase.key);
    const stages = d.stages.map(s => `<div class="ip-st ${s.state}"><span class="l">${esc(s.label)}</span>
      <span class="v">${num(s.value)}${s.of != null ? ` <small>of ${num(s.of)}</small>` : ''}</span>
      <div class="ip-bar" role="progressbar" aria-label="${esc(s.label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${s.pct}"><i style="width:${s.pct}%"></i></div>
      <span class="d">${esc(s.detail || (s.of != null ? s.pct + '%' : ''))}</span></div>`).join('');
    const etaText = !T.found ? 'Not started' : d.eta.days === 0 ? 'Done' : d.eta.days === 1 ? 'About a day' : `About ${d.eta.days} days`;
    const facts = [
      [etaText, `Time left to read every file. ${d.eta.note}`],
      [num(T.motions), 'Motions read from minutes'],
      [num(T.passed), 'Votes checked and published'],
      [T.pages ? T.ocr_share + '%' : '—', 'Pages that were scans (read with OCR)'],
      [num(T.gaps), 'Board-years with no minutes online'],
    ].map(([v, l]) => `<div class="ip-f"><b>${esc(v)}</b><span>${esc(l)}</span></div>`).join('');
    let cost = '';
    if (d.cost) {
      const c = d.cost, cap = c.budget || 0, used = c.spent + c.in_flight;
      cost = `<h3 class="ip-h">Cost (admin only)</h3><div class="ip-facts ip-cost">
        <div class="ip-f"><b>${usd(c.spent)}</b><span>Spent so far</span>${cap ? `<div class="ip-bar"><i style="width:${Math.min(100, used / cap * 100)}%"></i></div>` : ''}</div>
        <div class="ip-f"><b>${usd(c.in_flight)}</b><span>In batches now (estimate)</span></div>
        <div class="ip-f"><b>${usd(c.left)}</b><span>Estimated to finish (${usd(c.avg_per_file)} a file, ${c.avg_basis === 'actual' ? 'average so far' : 'estimate until reads come back'})</span></div>
        <div class="ip-f"><b>${usd(c.total)}</b><span>Estimated total${cap ? ` · cap ${usd(cap)}` : ''}</span></div></div>`;
    }
    const head = d.years.map(y => `<th scope="col">${y}</th>`).join('');
    const rows = d.boards.map(b => `<tr><th scope="row">${gov(b)}</th>${b.years.map(c => cell(b, c)).join('')}
      <td class="ip-tot" title="Files read of files found">${b.totals.found ? b.totals.pct_read + '%' : '—'}</td></tr>`).join('')
      || `<tr><td colspan="${d.years.length + 2}" class="muted">No archives counted yet.</td></tr>`;
    const notes = d.boards.filter(b => b.note).map(b => `<li><b>${esc(b.name)}:</b> ${esc(b.note)}</li>`).join('');
    const KIND = {crawl: 'Download from archives', read: 'Read with Claude'};
    const runs = (d.runs || []).slice(0, opts.admin ? 12 : 6).map(r => `<tr><td>${esc(KIND[r.kind] || r.kind)}</td><td>${esc(ago(r.started_at))}</td>
      <td>${esc(r.status === 'ok' ? 'Finished' : r.status === 'running' ? 'Running' : 'Problem')}</td></tr>`).join('');
    el.innerHTML = `<div class="ip">
      <div class="ip-phase"><span class="ip-dot ${active ? 'active' : d.phase.key === 'current' ? 'done' : ''}"></span><div><b>${esc(d.phase.text)}</b>
        <small>Last file read ${esc(ago(d.last.read_at))} · archives last counted ${esc(ago(d.last.listed_at))} · updated ${esc(ago(d.as_of))}</small></div></div>
      <div class="ip-stages">${stages}</div>
      <div class="ip-facts">${facts}</div>${cost}
      <h3 class="ip-h">By board and year</h3>
      <div class="ip-key"><span><span class="ip-c ip-done">24</span>All read (files found)</span><span><span class="ip-c ip-reading">12/24</span>Being read (read / found)</span>
        <span><span class="ip-c ip-captured">0/24</span>Found or stored, not read yet</span><span><span class="ip-c ip-none_online">—</span>None posted online</span>
        <span><span class="ip-c ip-not_listed">·</span>Not counted yet</span></div>
      <div class="tablewrap"><table class="ip-grid" data-tt="off" data-stack="off"><thead><tr><th scope="col"><span class="sr">Board</span></th>${head}<th scope="col">Read</th></tr></thead><tbody>${rows}</tbody></table></div>
      ${notes ? `<ul class="ip-notes">${notes}</ul>` : ''}
      ${runs ? `<h3 class="ip-h">Recent runs</h3><div class="tablewrap"><table class="tx-table at ip-runs" data-tt="off"><thead><tr><th scope="col">Step</th><th scope="col">Started</th><th scope="col">Result</th></tr></thead><tbody>${runs}</tbody></table></div>` : ''}
      <p class="small muted" style="margin:0">${esc(d.method)}</p></div>`;
  }

  async function load(el, url, opts) {
    try {
      const r = await fetch(url, {headers: {Accept: 'application/json'}});
      render(el, r.ok ? await r.json() : null, opts);
    } catch (e) { render(el, null, opts); }
  }

  window.BCProgress = {render, load};
  const auto = document.querySelector('[data-import-progress]');
  if (auto) {
    const go = () => load(auto, '/api/v1/import-progress');
    go();
    setInterval(() => { if (!document.hidden) go(); }, 120000);
  }
})();
