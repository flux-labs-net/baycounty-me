// /correspondence: published emails with officials, from /api/v1/correspondence.
(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const day = t => new Date(t).toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'});
  const clean = n => String(n || '').replace(/\s*\(.*?\)\s*/g, ' ').trim();
  let first = true, stuck = false; // stuck: showing "no letters" for a bar city with none, #crG still on All

  async function load() {
    stuck = false;
    const qs = new URLSearchParams();
    if (!first) { qs.set('year', $('#crY').value || 'all'); if ($('#crG').value) qs.set('government', $('#crG').value); }
    let d;
    try {
      const r = await fetch('/api/v1/correspondence?' + qs);
      if (!r.ok) throw new Error();
      d = await r.json();
    } catch (e) { $('#crList').innerHTML = '<p class="muted">Couldn’t load the correspondence. Try again in a moment.</p>'; return; }
    if (first) {
      // Opens on the latest year with mail; every year is one choice away.
      $('#crY').innerHTML = d.years.map(y => `<option value="${y}">${y}</option>`).join('') + '<option value="all">All years</option>';
      $('#crY').value = d.year ? String(d.year) : 'all';
      $('#crG').innerHTML = '<option value="">All governments</option>' + d.governments.map(g => `<option>${esc(g)}</option>`).join('');
      first = false;
      // the city bar at the top drives #crG (full names, sent as ?government=); offer only governments with mail
      const has = new Set(d.governments.map(g => BCM.city.key(g)).filter(Boolean)), bar = document.getElementById('scCity'), k = BCM.city.get();
      if (bar) [...bar.options].forEach(o => { if (o.value && o.value !== k && !has.has(o.value)) o.remove(); });
      if (k && !has.has(k)) { stuck = true; $('#crList').innerHTML = `<p class="muted">No letters to ${esc(BCM.city.label(k))} officials have been published yet.</p>`; $('#crCount').textContent = ''; return; }
      const o = k && [...$('#crG').options].find(x => BCM.city.key(x.value) === k);
      if (o) { $('#crG').value = o.value; return load(); } // open on the city in the bar
    } else if (!d.conversations.length && d.years.length && $('#crY').value !== 'all' && !d.years.includes(+$('#crY').value)) {
      // this government has no mail in the chosen year: move to its latest year instead of opening empty
      $('#crY').value = String(d.years[0]); return load();
    }
    render(d);
  }

  function render(d) {
    const cs = d.conversations;
    const replies = cs.reduce((a, c) => a + c.replies, 0);
    $('#crCount').textContent = cs.length ? `${cs.length} email${cs.length === 1 ? '' : 's'}, ${replies} with a reply` : '';
    if (!cs.length) { $('#crList').innerHTML = `<p class="muted">${d.total ? 'Nothing for these filters.' : 'Nothing has been published yet.'}</p>`; return; }
    $('#crList').innerHTML = cs.map((c, i) => {
      const orig = (c.threads[0] && c.threads[0].messages.find(m => m.direction === 'out')) || {text: ''};
      const long = orig.text.length > 600;
      const to = c.threads.length === 1 ? `${esc(clean(c.threads[0].official))}, ${esc(c.threads[0].seat)}` : `${c.threads.length} officials`;
      return `<article class="cr-c"><h3>${esc(c.subject)}</h3>
        <div class="cr-meta">Sent ${day(c.sent_at)} to ${to} · ${esc(c.governments.join(', '))} · ${c.replies} of ${c.threads.length} replied</div>
        <div class="cr-orig${long ? ' clip' : ''}" id="o${i}">${esc(orig.text)}</div>${long ? `<button class="cr-more" type="button" data-open="o${i}">Read the whole email</button>` : ''}
        ${c.threads.map(t => {
          const rest = t.messages.slice(t.messages.findIndex(m => m.direction === 'out') + 1);
          const got = rest.some(m => m.direction === 'in');
          return `<div class="cr-th"><div class="cr-who"><b>${esc(clean(t.official) || 'Vacant seat')}</b><span class="muted">${esc(t.seat)} · ${esc(t.government)}</span>
            <span class="cr-st${got ? ' yes' : ''}">${got ? 'Replied' : 'No reply yet'}</span></div>
            ${rest.map(m => `<div class="cr-msg ${m.direction}"><small>${m.direction === 'in' ? esc(clean(t.official)) + ' wrote' : 'BayCounty.me followed up'} · ${day(m.at)}</small>${esc(m.text || '(no text)')}</div>`).join('')}</div>`;
        }).join('')}</article>`;
    }).join('');
  }

  $('#crList').addEventListener('click', e => {
    const b = e.target.closest('[data-open]'); if (!b) return;
    document.getElementById(b.dataset.open).classList.remove('clip'); b.remove();
  });
  $('#crY').addEventListener('change', load);
  $('#crG').addEventListener('change', load);
  // back to All from a city with no letters: #crG doesn't change, so reload here (other cities change #crG, which loads)
  BCM.city.on(k => { if (stuck && !k) { stuck = false; load(); } });
  load();
})();
