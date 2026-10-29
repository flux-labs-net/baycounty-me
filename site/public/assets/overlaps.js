// Overlap sections (site/overlaps_page.py), on whichever page holds them: the "Show all" buttons on long tables, and the
// live parts from GET /api/v1/overlaps (api/_overlaps.js): officials' own businesses and nonprofits named in votes they
// cast (hand-checked matches only), checkbook payees that gave to campaigns, payments just under a purchasing threshold,
// and school spending next to school grades. Each part renders only where its placeholder is on the page.
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const usd = n => n == null ? '—' : '$' + Number(n).toLocaleString('en-US', {maximumFractionDigits: 0});
  const a = (id, text) => id && window.BC && BC.a ? BC.a(id, text) : esc(text);
  const src = (u, t) => u ? `<a href="${esc(u)}" rel="noopener" target="_blank">${esc(t)}</a>` : '';
  const names = s => { const n = String(s).split('; '); return n.slice(0, 3).join(', ') + (n.length > 3 ? ` and ${n.length - 3} more` : ''); };
  const empty = (el, msg) => { el.innerHTML = `<p class="ov-empty">${esc(msg)}</p>`; el.setAttribute('aria-busy', 'false'); };
  const table = (el, head, rows) => {
    el.innerHTML = `<div class="tablewrap"><table class="tx-table ov-tbl" data-tt-year="off"><thead><tr>${head.map(([h, c]) => `<th${c ? ` class="${c}"` : ''}>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
    el.setAttribute('aria-busy', 'false');
  };

  function own(el, biz, np) {
    if (!el) return;
    const rows = [];
    for (const r of biz.rows) rows.push(`<tr><td>${a(r.person_id, r.official)}<span class="sub">${esc(r.board || '')}</span></td>
      <td>${a(r.business_id, r.business)}<span class="sub"><span class="ov-tag">their business</span>${r.paid_by_own_government ? `paid ${usd(r.paid_by_own_government)} by their government` : ''}</span></td>
      <td>${esc(r.date)}: ${esc(r.headline || '')} <span class="ov-tag${r.official_vote === 'yes' ? '' : ' hot'}">${esc(r.official_vote || 'not listed')}</span> ${src(r.source_url, 'minutes')}</td></tr>`);
    for (const r of np.rows) rows.push(`<tr><td>${a(r.person_id, r.official)}<span class="sub">${esc(r.titles || 'Board member')}${r.board_years ? ', ' + esc(r.board_years) : ''}</span></td>
      <td>${a(r.nonprofit_id, r.nonprofit)}<span class="sub"><span class="ov-tag">on its board</span>${r.paid_by_own_government ? `${usd(r.paid_by_own_government)} from ${esc(r.payers || 'their government')}` : ''}</span></td>
      <td>${r.votes.length ? r.votes.slice(0, 6).map(v => `${esc(v.date)}: ${esc(v.headline || '')} <span class="ov-tag${v.official_vote === 'yes' ? '' : ' hot'}">${esc(v.official_vote || 'not listed')}</span> ${src(v.source_url, 'minutes')}`).join('<br>') + (r.votes.length > 6 ? `<br>…${r.votes.length - 6} more` : '') : '<span class="muted">No vote naming it on file</span>'}</td></tr>`);
    if (!rows.length) return empty(el, (biz.error || np.error) ? 'Couldn’t load this part right now. Try again in a moment.' : 'No hand-checked official is named in a vote on their own business or nonprofit yet. Matches appear here as they are checked.');
    table(el, [['Official', ''], ['Business or nonprofit', ''], ['Votes naming it', '']], rows);
  }

  function checkbook(el, x) {
    if (!el) return;
    if (!x.rows.length) return empty(el, x.error ? 'Couldn’t load this part right now.' : 'No checkbook payee on file has given to a local campaign yet. Governments are added as they send their check registers.');
    table(el, [['Payee', ''], ['Paid by', ''], ['Paid', 'n'], ['Gave to campaigns', 'n']], x.rows.slice(0, 200).map(r => `<tr><td>${a(r.payee_id, r.payee)}${r.through_owner ? '<span class="sub">including gifts from its owner</span>' : ''}</td>
      <td>${a('gov:' + r.gov_id, r.government || r.gov_id)}<span class="sub">${esc(r.fiscal_years ? 'FY ' + r.fiscal_years : '')}</span></td><td class="n">${usd(r.paid)}<span class="sub">${r.payments} payments</span></td>
      <td class="n">${usd(r.gave_to_campaigns)}<span class="sub">${r.gave_to_officials_here ? usd(r.gave_to_officials_here) + ' to officials here' : ''}${r.gave_to ? ' · to ' + esc(names(r.gave_to)) : ''}</span></td></tr>`));
  }

  function split(el, x) {
    if (!el) return;
    if (!x.rows.length) return empty(el, x.error ? 'Couldn’t load this part right now.' : 'No run of payments just under a threshold in the check registers on file.');
    table(el, [['Payee', ''], ['Government', ''], ['Payments', 'n'], ['Just under', 'n'], ['Total', 'n']], x.rows.slice(0, 100).map(r => `<tr><td>${a(r.payee_id, r.payee)}
      <details><summary>${esc(r.first_date)} to ${esc(r.last_date)}</summary><ul>${r.items.map(i => `<li>${esc(i.paid_on)}: ${usd(i.amount)}${i.description ? ' · ' + esc(i.description) : ''}${i.doc_no ? ' · #' + esc(i.doc_no) : ''}</li>`).join('')}</ul></details></td>
      <td>${a('gov:' + r.gov_id, r.government || r.gov_id)}</td><td class="n">${r.payments}</td><td class="n">${usd(r.threshold)}</td><td class="n">${usd(r.total)}</td></tr>`));
  }

  function schools(el, x) {
    if (!el) return;
    if (!x.rows.length) return empty(el, x.error ? 'Couldn’t load this part right now.' : 'The state school grades and spending files are not on file for the same years yet. This fills in when both are.');
    table(el, [['School', ''], ['Year', 'n'], ['Grade', 'n'], ['Per student', 'n']], x.rows.map(r => `<tr><td><a href="/schools#${esc(r.school_id)}">${esc(r.school)}</a></td>
      <td class="n">${esc(r.year)}</td><td class="n">${esc(r.grade || '—')}</td><td class="n">${usd(r.per_student)}</td></tr>`));
  }

  async function load() {
    const ids = ['ovOwnBiz', 'ovOwnNp', 'ovCheckbook', 'ovSplit', 'ovSchools'], els = ids.map($);
    if (!els.some(Boolean)) return;
    const none = {rows: []};
    try {
      const r = await fetch('/api/v1/overlaps');
      if (!r.ok) throw new Error();
      const d = (await r.json()).data;
      own(els[0], d.official_business_votes, none);
      own(els[1], none, d.nonprofit_board_money);
      checkbook(els[2], d.checkbook_donors);
      split(els[3], d.split_purchases);
      schools(els[4], d.school_spending_grades);
    } catch (e) {
      els.forEach(el => el && empty(el, 'Couldn’t load this part right now. Try again in a moment.'));
    }
  }

  // long tables show the first rows; "Show all", sorting or filtering shows every row
  const uncut = t => { if (t) t.classList.remove('ov-cut'); };
  document.addEventListener('click', ev => {
    const b = ev.target.closest('[data-ov-more]');
    if (b) { uncut(b.previousElementSibling && b.previousElementSibling.querySelector('table')); b.remove(); return; }
    const th = ev.target.closest('.ov-cut th');
    if (th) uncut(th.closest('table'));
  });
  document.addEventListener('input', ev => {
    const sec = ev.target.closest('.ov-sec');
    if (sec) sec.querySelectorAll('.ov-cut').forEach(t => { uncut(t); const b = t.closest('.tablewrap').nextElementSibling; if (b && b.matches('[data-ov-more]')) b.remove(); });
  });
  load();
})();
