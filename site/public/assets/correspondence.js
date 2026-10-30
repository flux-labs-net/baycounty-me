// /correspondence: a read-only mail viewer for every email between BayCounty.me and officials or governments.
// Reads /api/v1/mail (folders and the list) and /api/v1/mail/{id} (one conversation). #c12 in the address opens that
// conversation, so every thread has its own link. j / k move between conversations, Esc goes back to the list.
(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const TZ = 'America/Chicago';
  const short = t => {
    if (!t) return '';
    const d = new Date(t), now = new Date();
    if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString('en-US', {hour: 'numeric', minute: '2-digit', timeZone: TZ});
    return d.toLocaleDateString('en-US', {month: 'short', day: 'numeric', ...(d.getFullYear() !== now.getFullYear() ? {year: 'numeric'} : {}), timeZone: TZ});
  };
  const full = t => (t ? new Date(t).toLocaleString('en-US', {weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: TZ}) + ' CT' : '');
  const size = n => (n == null ? '' : n < 1024 ? n + ' B' : n < 1048576 ? Math.round(n / 1024) + ' KB' : (n / 1048576).toFixed(1) + ' MB');
  const initials = s => String(s || '?').replace(/^Staff,\s*/, '').split(/[\s,]+/).filter(w => /^[A-Za-z]/.test(w)).slice(0, 2).map(w => w[0].toUpperCase()).join('') || '?';
  const DELIVERY = {delivered: 'Delivered', opened: 'Delivered', clicked: 'Delivered', sent: 'Sent', bounced: 'Bounced', failed: 'Didn’t send', delivery_delayed: 'Delayed', queued: 'Sent'};
  const STATUS = {awaiting: ['No reply yet', ''], replied: ['Replied', 'ok'], closed: ['Closed', ''], sent: ['Request sent', ''], received: ['Records received', 'ok'],
    accepted: ['Accepted', 'ok'], refused: ['Not accepted', 'warn']};

  const S = {folder: '', government: '', q: '', page: 1, list: null, open: null};
  const app = $('#mv');

  async function getJson(u) { const r = await fetch(u); if (!r.ok) throw new Error(r.status === 404 ? 'That conversation isn’t here.' : 'Couldn’t load the mail. Try again in a moment.'); return r.json(); }

  async function loadList() {
    const qs = new URLSearchParams();
    if (S.folder) qs.set('folder', S.folder);
    if (S.government) qs.set('government', S.government);
    if (S.q) qs.set('q', S.q);
    if (S.page > 1) qs.set('page', S.page);
    try { S.list = await getJson('/api/v1/mail?' + qs); }
    catch (e) { $('#mvItems').innerHTML = `<li class="mv-empty">${esc(e.message)}</li>`; return; }
    drawFolders(); drawList();
  }

  function drawFolders() {
    const d = S.list;
    const btn = (id, label, n) => `<button class="mv-f" type="button" data-folder="${id}" aria-current="${S.folder === id}"><span>${esc(label)}</span><i>${n}</i></button>`;
    $('#mvFolders').innerHTML = btn('', 'All mail', d.total) + d.folders.map(f => btn(f.id, f.label, f.count)).join('') +
      `<select id="mvGov" aria-label="Government"><option value="">All governments</option>${d.governments.map(g => `<option${g === S.government ? ' selected' : ''}>${esc(g)}</option>`).join('')}</select>`;
  }

  function drawList() {
    const d = S.list;
    $('#mvItems').innerHTML = d.threads.map(t => {
      const st = STATUS[t.status];
      return `<li><button class="mv-it" type="button" data-id="${t.id}" aria-current="${S.open === t.id}" data-share-record data-share-url="/correspondence#${t.id}" data-share-title="${esc(t.subject)}">
        <div class="r1"><span class="who">${esc(t.with || t.government || '')}</span><time datetime="${esc(t.last_at)}">${short(t.last_at)}</time></div>
        <div class="sub">${esc(t.subject)}</div>
        <div class="snip">${t.hidden_reason ? 'Taken down: ' + esc(t.hidden_reason) : esc(t.snippet || '')}</div>
        <div class="tags">${t.messages > 1 ? `<span class="mv-tag">${t.messages} messages</span>` : ''}${t.files ? `<span class="mv-tag">📎 ${t.files}</span>` : ''}${st ? `<span class="mv-tag ${st[1]}">${st[0]}</span>` : ''}${!S.folder ? `<span class="mv-tag">${esc((d.folders.find(f => f.id === t.folder) || {}).label || '')}</span>` : ''}</div>
      </button></li>`;
    }).join('') || `<li class="mv-empty">${S.q || S.government || S.folder ? 'No mail matches.' : 'No mail yet.'}</li>`;
    $('#mvPager').hidden = d.pages < 2;
    $('#mvPage').textContent = `Page ${d.page} of ${d.pages}`;
    $('#mvPrev').disabled = d.page <= 1; $('#mvNext').disabled = d.page >= d.pages;
  }

  function who(p) {
    if (!p) return '';
    return `<b>${esc(p.name || p.address || 'Someone')}</b>${p.role ? ` <span class="ad">${esc(p.role)}</span>` : ''}${p.address && p.name ? ` <span class="ad">&lt;${esc(p.address)}&gt;</span>` : ''}`;
  }
  const toLine = list => (list || []).map(p => esc(p.name || p.address || '')).filter(Boolean).join(', ');

  function message(m, open) {
    const us = m.direction === 'out' && /BayCounty\.me/.test((m.from && m.from.name) || '');
    const preview = m.text ? m.text.replace(/\s+/g, ' ').slice(0, 140) : (m.not_opened || '');
    const details = [['Sent', m.sent_at ? full(m.sent_at) : null], ['Received', full(m.at)], ['Logged', m.logged_at ? full(m.logged_at) : null],
      ['Subject', m.subject], ['Message-ID', m.message_id], ['In reply to', m.in_reply_to], ['Delivery', m.delivery ? (DELIVERY[m.delivery] || m.delivery) : null]].filter(x => x[1]);
    return `<div class="mv-m" data-m="${esc(m.id)}">
      <button class="mv-mh" type="button" aria-expanded="${open}">
        <span class="mv-av${us ? ' us' : ''}" aria-hidden="true">${esc(initials(m.from && (m.from.name || m.from.address)))}</span>
        <span class="mv-who">${who(m.from)}<div class="to">to ${toLine(m.to) || '—'}</div>${open ? '' : `<div class="pv">${esc(preview)}</div>`}</span>
        <time datetime="${esc(m.at)}" title="${esc(full(m.at))}">${esc(full(m.at))}${m.delivery ? `<br><span class="mv-tag ${m.delivery === 'delivered' ? 'ok' : ''}">${esc(DELIVERY[m.delivery] || m.delivery)}</span>` : ''}</time>
      </button>
      <div class="mv-mb"${open ? '' : ' hidden'}>
        ${m.text != null ? `<p class="mv-text">${esc(m.text || '(no text)')}</p>` : ''}${m.not_opened ? `<p class="mv-note">${esc(m.not_opened)}</p>` : ''}
        ${m.quoted ? `<details class="mv-q"><summary>Show earlier messages quoted in this email</summary><pre>${esc(m.quoted)}</pre></details>` : ''}
        ${(m.attachments || []).length ? `<div class="mv-att">${m.attachments.map(a => `<span title="${esc(a.sha256 ? 'SHA-256 ' + a.sha256 : a.name)}"><b>📎 ${esc(a.name)}</b><small>${esc([size(a.size), a.note].filter(Boolean).join(' · '))}</small>${a.sha256 ? `<small class="mv-mono">SHA-256 ${esc(a.sha256.slice(0, 20))}…</small>` : ''}</span>`).join('')}</div>` : ''}
        ${details.length ? `<details class="mv-dt"><summary>Details</summary><dl>${details.map(([k, v]) => `<dt>${k}</dt><dd${/ID|reply/.test(k) ? ' class="mv-mono"' : ''}>${esc(v)}</dd>`).join('')}</dl></details>` : ''}
      </div></div>`;
  }

  async function openThread(id, {push = true} = {}) {
    S.open = id;
    document.querySelectorAll('.mv-it').forEach(b => b.setAttribute('aria-current', String(b.dataset.id === id)));
    app.classList.add('reading');
    const box = $('#mvRead');
    box.innerHTML = '<p class="mv-empty">Loading…</p>';
    if (push && location.hash !== '#' + id) history.replaceState(null, '', '#' + id);
    let t;
    try { t = await getJson('/api/v1/mail/' + encodeURIComponent(id)); }
    catch (e) { box.innerHTML = `<div class="mv-tb"><button class="mv-back" type="button" data-back>← Mail</button></div><p class="mv-empty">${esc(e.message)}</p>`; return; }
    if (S.open !== id) return;
    const st = STATUS[t.status];
    const folder = S.list && (S.list.folders.find(f => f.id === t.folder) || {}).label;
    const msgs = t.items.filter(i => i.type === 'message');
    const lastId = msgs.length ? msgs[msgs.length - 1].id : null;
    const many = msgs.length > 1;
    box.innerHTML = `<div class="mv-tb"><button class="mv-back" type="button" data-back>← Mail</button><span class="grow"></span>
        <button type="button" data-go="${esc(t.newer || '')}"${t.newer ? '' : ' disabled'} aria-label="Newer conversation" title="Newer (k)">↑</button>
        <button type="button" data-go="${esc(t.older || '')}"${t.older ? '' : ' disabled'} aria-label="Older conversation" title="Older (j)">↓</button>
        ${many ? '<button type="button" data-expand>Expand all</button>' : ''}<button type="button" data-print>Print</button></div>
      <div class="mv-hd"><h2>${esc(t.subject)}</h2><div class="meta">${folder ? `<span class="mv-tag">${esc(folder)}</span>` : ''}${t.government ? `<span>${esc(t.government)}</span>` : ''}${st ? `<span class="mv-tag ${st[1]}">${st[0]}</span>` : ''}
        <span>${msgs.length} message${msgs.length === 1 ? '' : 's'}</span><span>Started ${esc(full(t.started_at))}</span></div></div>
      <div class="mv-body" data-share-text="${esc(t.subject + (t.government ? ' · ' + t.government : ''))}">
        ${t.hidden_reason ? `<div class="mv-hidden"><b>This conversation was taken down.</b> ${esc(t.hidden_reason)}</div>` : ''}
        ${t.items.map(i => i.type === 'event' ? `<div class="mv-ev"><span>${esc(full(i.at))}</span><b>${esc(i.text)}</b>${i.file ? `<span>${esc(i.file)}</span>` : ''}</div>`
          : message(i, !many || i.id === lastId)).join('')}
      </div>`;
    if (window.innerWidth <= 680) window.scrollTo({top: app.offsetTop - 8});
  }

  function closeThread() { S.open = null; app.classList.remove('reading'); history.replaceState(null, '', location.pathname + location.search); document.querySelectorAll('.mv-it').forEach(b => b.setAttribute('aria-current', 'false')); }

  // ---------- events ----------
  $('#mvFolders').addEventListener('click', e => { const b = e.target.closest('[data-folder]'); if (!b) return; S.folder = b.dataset.folder; S.page = 1; loadList(); });
  $('#mvFolders').addEventListener('change', e => { if (e.target.id === 'mvGov') { S.government = e.target.value; S.page = 1; loadList(); } });
  let qt = null;
  $('#mvQ').addEventListener('input', e => { clearTimeout(qt); qt = setTimeout(() => { S.q = e.target.value.trim(); S.page = 1; loadList(); }, 250); });
  $('#mvItems').addEventListener('click', e => { const b = e.target.closest('.mv-it'); if (b && !e.target.closest('[data-share-menu]')) openThread(b.dataset.id); });
  $('#mvPrev').addEventListener('click', () => { S.page--; loadList(); });
  $('#mvNext').addEventListener('click', () => { S.page++; loadList(); });
  $('#mvRead').addEventListener('click', e => {
    const h = e.target.closest('.mv-mh');
    if (h) { const body = h.nextElementSibling, open = body.hidden; body.hidden = !open; h.setAttribute('aria-expanded', String(open)); const pv = h.querySelector('.pv'); if (pv) pv.hidden = open; return; }
    if (e.target.closest('[data-back]')) return closeThread();
    const g = e.target.closest('[data-go]'); if (g && g.dataset.go) return openThread(g.dataset.go);
    if (e.target.closest('[data-expand]')) { document.querySelectorAll('.mv-mb').forEach(b => { b.hidden = false; }); document.querySelectorAll('.mv-mh').forEach(h => h.setAttribute('aria-expanded', 'true')); document.querySelectorAll('.mv-mh .pv').forEach(p => { p.hidden = true; }); return; }
    if (e.target.closest('[data-print]')) { document.querySelectorAll('.mv-mb').forEach(b => { b.hidden = false; }); window.print(); }
  });
  document.addEventListener('keydown', e => {
    if (/input|select|textarea/i.test((e.target.tagName || ''))) return;
    if (e.key === 'Escape' && S.open) return closeThread();
    if (!S.list || !S.list.threads.length || !/^[jk]$/.test(e.key)) return;
    const ids = S.list.threads.map(t => t.id), i = ids.indexOf(S.open);
    const next = e.key === 'j' ? ids[Math.min(ids.length - 1, i + 1)] : ids[Math.max(0, i - 1)];
    if (next && next !== S.open) openThread(next);
  });
  window.addEventListener('hashchange', () => { const id = location.hash.slice(1); if (/^[cem]\d+$/.test(id)) openThread(id, {push: false}); });

  // The city bar at the top picks the government.
  const city = window.BCM && BCM.city;
  (async () => {
    await loadList();
    if (city && city.get && S.list) {
      const k = city.get(), g = k && S.list.governments.find(x => city.key(x) === k);
      if (g) { S.government = g; await loadList(); }
    }
    const id = location.hash.slice(1);
    if (/^[cem]\d+$/.test(id)) openThread(id, {push: false});
  })();
})();
