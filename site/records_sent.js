/* "Sent by the governments": records each city and the county send BayCounty.me directly from their own systems,
   through the government workspace (/staff, Send records) or its intake email. Read live from /api/v1/records-sent, so a
   file shows the moment staff publish it. Two places use it:
     <div data-records-sent="scorecard">  on /data-sources: one row per government, status of each kind of record
     <div data-records-sent="contracts">  on /public-money/contracts: the contracts staff sent (hidden until there are some)
     <div data-records-sent="appointments">  on /people: board appointments staff sent (hidden until there are some)
     <div data-records-sent="payroll">  on /people: pay by job title (never names employees; hidden until there is some)
     <div data-records-sent="fees">  on /public-money/fees-and-bills: fee and rate changes (hidden until there are some) */
(() => {
  const boxes = [...document.querySelectorAll('[data-records-sent]')];
  if (!boxes.length) return;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const day = s => { if (!s) return ''; const d = new Date(String(s).slice(0, 10) + 'T12:00:00'); return isNaN(d) ? '' : d.toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'}); };
  const usd = n => '$' + Math.round(Number(n) || 0).toLocaleString('en-US');
  const safe = u => /^https:\/\//i.test(String(u || '')) ? u : null;
  const KINDS = [['checkbook', 'Checkbook'], ['budget', 'Budget vs. actual'], ['contracts', 'Contracts'], ['payroll', 'Pay by job'], ['appointments', 'Board seats'], ['fees', 'Fee changes']];
  const money = n => n === null || n === undefined ? '' : '$' + Number(n).toLocaleString('en-US', Number(n) % 1 ? {minimumFractionDigits: 2, maximumFractionDigits: 2} : {maximumFractionDigits: 0});
  const median = a => { const v = (a || []).map(Number).filter(n => n > 0).sort((x, y) => x - y); return v.length ? v[Math.floor(v.length / 2)] : null; };
  const govA = (id, name) => window.BC && BC.a && id ? BC.a('gov:' + id, name) : esc(name);
  const ST = {current: ['ok', 'Current'], behind: ['hand', 'Behind'], not_sent: ['wait', 'Not sent yet']};
  const cell = r => {
    if (!r) return '<td></td>';
    const [tone, word] = ST[r.status] || ST.not_sent;
    const sub = r.status === 'not_sent' ? '' : `<span class="sub">${r.latest ? 'Through ' + esc(day(r.latest)) : ''}${r.latest && r.last_sent ? ' · ' : ''}${r.last_sent ? 'sent ' + esc(day(r.last_sent)) : ''}</span>`;
    return `<td><span class="ds-st ds-st-${tone}">${word}</span>${sub}</td>`;
  };
  fetch('/api/v1/records-sent').then(r => r.ok ? r.json() : null).then(j => {
    if (!j || !j.data) return;
    const {governments, contracts, appointments = [], payroll = [], fees = []} = j.data;
    for (const box of boxes) {
      if (box.dataset.recordsSent === 'scorecard') {
        const n = governments.filter(g => g.sends).length;
        box.innerHTML = `<p class="ds-sent-n"><b>${n} of ${governments.length}</b> governments send records to ${esc(location.hostname.replace(/^www\./, ''))} themselves.</p>
          <div class="tablewrap"><table class="tx-table" data-tt="off"><thead><tr><th scope="col">Government</th>${KINDS.map(k => `<th scope="col">${k[1]}</th>`).join('')}</tr></thead>
          <tbody>${governments.map(g => `<tr data-share-record><td>${govA(g.gov_id, g.government)}${g.feeds_agreed ? `<br><span class="sub">${g.feeds_agreed} feed${g.feeds_agreed === 1 ? '' : 's'} agreed</span>` : ''}</td>${KINDS.map(k => cell(g.records[k[0]])).join('')}</tr>`).join('')}</tbody></table></div>`;
      } else if (box.dataset.recordsSent === 'contracts' && contracts.length) {
        box.innerHTML = `<div class="sec-hd"><h2 id="sent">Sent by the governments</h2><span class="muted">${contracts.length} contract${contracts.length === 1 ? '' : 's'}</span></div>
          <p class="note" style="margin-top:0">Contract lists a city or the county sent us straight from its own records. They’re added to the contracts above at the next site update.</p>
          <div class="tablewrap"><table class="tx-table" data-tt="off"><thead><tr><th scope="col">Government</th><th scope="col">Vendor</th><th scope="col">For</th><th scope="col" class="num">Amount</th><th scope="col">How awarded</th><th scope="col">Awarded</th></tr></thead>
          <tbody data-share-items>${contracts.map(c => `<tr><td>${esc(c.government)}</td><td class="wrap">${esc(c.vendor)}</td><td class="wrap small">${esc(c.purpose || '')}${c.notes ? `<br><span class="muted">${esc(c.notes)}</span>` : ''}</td>
            <td class="num">${usd(c.amount)}</td><td class="small">${esc(c.method || 'Not stated')}</td><td class="small">${esc(day(c.date))}${safe(c.source_url) ? ` <a class="src" href="${esc(c.source_url)}" target="_blank" rel="noopener">Document</a>` : ''}<br><span class="muted">${esc(c.source_title)}</span></td></tr>`).join('')}</tbody></table></div>`;
        box.hidden = false;
      } else if (box.dataset.recordsSent === 'appointments' && appointments.length) {
        box.innerHTML = `<div class="sec-hd"><h2 id="appointments">Board appointments</h2><span class="muted">${appointments.length} seat${appointments.length === 1 ? '' : 's'}</span></div>
          <p class="note" style="margin-top:0">Who sits on each city and county board, sent by the government itself.</p>
          <div class="tablewrap"><table class="tx-table" data-tt="off"><thead><tr><th scope="col">Government</th><th scope="col">Board</th><th scope="col">Seat</th><th scope="col">Member</th><th scope="col">Appointed by</th><th scope="col">Term</th></tr></thead>
          <tbody data-share-items>${appointments.map(a => `<tr><td>${govA(a.gov_id, a.government)}</td><td class="wrap">${esc(a.board)}</td><td class="small">${esc(a.seat || '')}</td><td>${esc(a.person)}</td>
            <td class="small">${esc(a.appointed_by || '')}</td><td class="small">${esc(day(a.term_start))}${a.term_end ? ' to ' + esc(day(a.term_end)) : ''}${safe(a.source_url) ? ` <a class="src" href="${esc(a.source_url)}" target="_blank" rel="noopener">Source</a>` : ''}</td></tr>`).join('')}</tbody></table></div>`;
        box.hidden = false;
      } else if (box.dataset.recordsSent === 'payroll' && payroll.length) {
        box.innerHTML = `<div class="sec-hd"><h2 id="staff-pay">Pay by job title</h2><span class="muted">${payroll.length} job${payroll.length === 1 ? '' : 's'}</span></div>
          <p class="note" style="margin-top:0">Sent by the government from its payroll system. Employee names are removed before anything is published; each row is a job title with how many people hold it and what they’re paid.</p>
          <div class="tablewrap"><table class="tx-table" data-tt="off"><thead><tr><th scope="col">Government</th><th scope="col">Job title</th><th scope="col">Department</th><th scope="col" class="num">People</th><th scope="col" class="num">Typical pay</th><th scope="col" class="num">Pay range</th><th scope="col">Year</th></tr></thead>
          <tbody data-share-items>${payroll.map(p => `<tr><td>${govA(p.gov_id, p.government)}</td><td class="wrap">${esc(p.title)}</td><td class="small">${esc(p.department || '')}</td>
            <td class="num">${(p.actual_salaries || []).length || ''}</td><td class="num">${money(median(p.actual_salaries))}</td>
            <td class="num small">${p.pay_min !== null || p.pay_max !== null ? esc(money(p.pay_min)) + (p.pay_max !== null ? ' to ' + esc(money(p.pay_max)) : '') : ''}</td><td class="small">${esc(p.fiscal_year || '')}</td></tr>`).join('')}</tbody></table></div>`;
        box.hidden = false;
      } else if (box.dataset.recordsSent === 'fees' && fees.length) {
        box.innerHTML = `<div class="sec-hd"><h2 id="changes">Fee and rate changes</h2><span class="muted">${fees.length} change${fees.length === 1 ? '' : 's'}</span></div>
          <p class="note" style="margin-top:0">New or changed fees, sent by the government when they’re adopted.</p>
          <div class="tablewrap"><table class="tx-table" data-tt="off"><thead><tr><th scope="col">Government</th><th scope="col">Fee</th><th scope="col" class="num">Was</th><th scope="col" class="num">Now</th><th scope="col">Starts</th><th scope="col">Adopted by</th></tr></thead>
          <tbody data-share-items>${fees.map(f => `<tr><td>${govA(f.gov_id, f.government)}</td><td class="wrap">${esc(f.fee)}${f.unit ? `<br><span class="muted small">${esc(f.unit)}</span>` : ''}</td>
            <td class="num">${f.old_amount === null ? '<span class="muted">New</span>' : esc(money(f.old_amount))}</td><td class="num"><b>${esc(money(f.new_amount))}</b></td>
            <td class="small">${esc(day(f.effective_date))}</td><td class="small wrap">${esc(f.adopted_by || '')}${safe(f.source_url) ? ` <a class="src" href="${esc(f.source_url)}" target="_blank" rel="noopener">Source</a>` : ''}</td></tr>`).join('')}</tbody></table></div>`;
        box.hidden = false;
      }
    }
  }).catch(() => {});
})();
