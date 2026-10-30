/* "Sent by the governments": records each city and the county send BayCounty.me directly from their own systems,
   through the government workspace (/staff, Send records) or its intake email. Read live from /api/v1/records-sent, so a
   file shows the moment staff publish it. Two places use it:
     <div data-records-sent="scorecard">  on /data-sources: one row per government, status of each kind of record
     <div data-records-sent="contracts">  on /public-money/contracts: the contracts staff sent (hidden until there are some) */
(() => {
  const boxes = [...document.querySelectorAll('[data-records-sent]')];
  if (!boxes.length) return;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const day = s => { if (!s) return ''; const d = new Date(String(s).slice(0, 10) + 'T12:00:00'); return isNaN(d) ? '' : d.toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'}); };
  const usd = n => '$' + Math.round(Number(n) || 0).toLocaleString('en-US');
  const safe = u => /^https:\/\//i.test(String(u || '')) ? u : null;
  const KINDS = [['checkbook', 'Checkbook'], ['budget', 'Budget vs. actual'], ['contracts', 'Contracts']];
  const ST = {current: ['ok', 'Current'], behind: ['hand', 'Behind'], not_sent: ['wait', 'Not sent yet']};
  const cell = r => {
    const [tone, word] = ST[r.status] || ST.not_sent;
    const sub = r.status === 'not_sent' ? '' : `<span class="sub">${r.latest ? 'Through ' + esc(day(r.latest)) : ''}${r.latest && r.last_sent ? ' · ' : ''}${r.last_sent ? 'sent ' + esc(day(r.last_sent)) : ''}</span>`;
    return `<td><span class="ds-st ds-st-${tone}">${word}</span>${sub}</td>`;
  };
  fetch('/api/v1/records-sent').then(r => r.ok ? r.json() : null).then(j => {
    if (!j || !j.data) return;
    const {governments, contracts} = j.data;
    for (const box of boxes) {
      if (box.dataset.recordsSent === 'scorecard') {
        const n = governments.filter(g => g.sends).length;
        box.innerHTML = `<p class="ds-sent-n"><b>${n} of ${governments.length}</b> governments send records to ${esc(location.hostname.replace(/^www\./, ''))} themselves.</p>
          <div class="tablewrap"><table class="tx-table" data-tt="off"><thead><tr><th scope="col">Government</th>${KINDS.map(k => `<th scope="col">${k[1]}</th>`).join('')}</tr></thead>
          <tbody>${governments.map(g => `<tr data-share-record><td>${window.BC && BC.a ? BC.a('gov:' + g.gov_id, g.government) : esc(g.government)}</td>${KINDS.map(k => cell(g.records[k[0]])).join('')}</tr>`).join('')}</tbody></table></div>`;
      } else if (box.dataset.recordsSent === 'contracts' && contracts.length) {
        box.innerHTML = `<div class="sec-hd"><h2 id="sent">Sent by the governments</h2><span class="muted">${contracts.length} contract${contracts.length === 1 ? '' : 's'}</span></div>
          <p class="note" style="margin-top:0">Contract lists a city or the county sent us straight from its own records. They’re added to the contracts above at the next site update.</p>
          <div class="tablewrap"><table class="tx-table" data-tt="off"><thead><tr><th scope="col">Government</th><th scope="col">Vendor</th><th scope="col">For</th><th scope="col" class="num">Amount</th><th scope="col">How awarded</th><th scope="col">Awarded</th></tr></thead>
          <tbody data-share-items>${contracts.map(c => `<tr><td>${esc(c.government)}</td><td class="wrap">${esc(c.vendor)}</td><td class="wrap small">${esc(c.purpose || '')}${c.notes ? `<br><span class="muted">${esc(c.notes)}</span>` : ''}</td>
            <td class="num">${usd(c.amount)}</td><td class="small">${esc(c.method || 'Not stated')}</td><td class="small">${esc(day(c.date))}${safe(c.source_url) ? ` <a class="src" href="${esc(c.source_url)}" target="_blank" rel="noopener">Document</a>` : ''}<br><span class="muted">${esc(c.source_title)}</span></td></tr>`).join('')}</tbody></table></div>`;
        box.hidden = false;
      }
    }
  }).catch(() => {});
})();
