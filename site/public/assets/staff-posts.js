/* "Posted by government staff": notices, events and jobs a city or the county posted in the BayCounty.me government
   workspace (/staff). They are in the database the moment they are saved, so this reads them live from
   /api/v1/government-posts instead of waiting for the next site build. Fills <section data-staff-posts="notice|event|job">. */
(() => {
  const box = document.querySelector('[data-staff-posts]');
  if (!box) return;
  const kind = box.dataset.staffPosts;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const day = s => { if (!s) return ''; const d = new Date(String(s).length <= 10 ? s + 'T12:00:00' : s); return isNaN(d) ? '' : d.toLocaleDateString('en-US', {weekday: String(s).length > 10 ? 'short' : undefined, month: 'short', day: 'numeric', year: 'numeric'}); };
  const time = s => String(s || '').length > 10 ? new Date(s).toLocaleTimeString('en-US', {hour: 'numeric', minute: '2-digit'}) : '';
  const safe = u => /^https:\/\//i.test(String(u || '')) ? u : null;
  const item = r => {
    const by = `<span>Posted by ${esc(r.posted_by || 'government staff')}</span>`;
    if (kind === 'notice') return `<li class="sp-item" data-share-record><h3>${esc(r.title)}</h3><div class="sp-meta"><span class="sp-pill">${esc(r.kind_label || 'Notice')}</span>${by}<span>Published ${esc(day(r.published))}</span>${r.event_date ? `<span>Date: ${esc(day(r.event_date))}</span>` : ''}${safe(r.pdf_url) ? `<a href="${esc(r.pdf_url)}" rel="noopener">Document</a>` : ''}</div>
      <details><summary>Read the notice</summary><p>${esc(r.text)}</p></details></li>`;
    if (kind === 'event') return `<li class="sp-item" data-share-record><h3>${safe(r.url) ? `<a href="${esc(r.url)}" rel="noopener">${esc(r.title)}</a>` : esc(r.title)}</h3><div class="sp-meta">${by}<span>${esc(day(r.starts))}${time(r.starts) ? ', ' + esc(time(r.starts)) : ''}</span>${r.venue ? `<span>${esc(r.venue)}</span>` : ''}${r.cost ? `<span>${esc(r.cost)}</span>` : ''}</div></li>`;
    return `<li class="sp-item" data-share-record><h3><a href="${esc(safe(r.url) || '#')}" rel="noopener">${esc(r.title)}</a></h3><div class="sp-meta">${by}${r.department ? `<span>${esc(r.department)}</span>` : ''}${r.job_type ? `<span>${esc(r.job_type)}</span>` : ''}${r.pay ? `<span>${esc(r.pay)}</span>` : ''}${r.closes ? `<span>Closes ${esc(day(r.closes))}</span>` : ''}</div></li>`;
  };
  fetch('/api/v1/government-posts?kind=' + encodeURIComponent(kind)).then(r => r.ok ? r.json() : null).then(j => {
    const rows = j && j.data && (j.data[kind === 'notice' ? 'notices' : kind + 's'] || []);
    if (!rows || !rows.length) return;
    box.innerHTML = `<style>.sp-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px}.sp-item{padding:14px 16px;border-radius:20px;background:var(--surface);box-shadow:var(--ui-shadow, 0 1px 2px rgba(0,0,0,.06));border-left:4px solid var(--teal);min-width:0}
      .sp-item h3{margin:0;font-size:.98rem;font-weight:600;overflow-wrap:anywhere}.sp-item h3 a{color:inherit}.sp-meta{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:.82rem;color:var(--muted);margin-top:4px}
      .sp-pill{font-size:.72rem;font-weight:600;padding:2px 9px;border-radius:999px;background:var(--sunken)}.sp-item details{margin-top:8px}.sp-item summary{cursor:pointer;font-size:.84rem;color:var(--blue)}.sp-item details p{font-size:.86rem;line-height:1.5;white-space:pre-line;margin:8px 0 0;overflow-wrap:anywhere}</style>
      <div class="sec-hd"><h2 id="from-staff">Posted by government staff</h2><span class="muted">${rows.length}</span></div>
      <p class="muted" style="margin:-4px 0 12px;font-size:.88rem">Posted directly by the government’s own staff on ${esc(location.hostname.replace(/^www\./, ''))}.</p>
      <ul class="sp-list" data-share-items>${rows.map(item).join('')}</ul>`;
    box.hidden = false;
  }).catch(() => {});
})();
