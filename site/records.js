(() => {
const R = __REC__, L = __L__;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const qs = new URLSearchParams(location.search);
$('rqG').innerHTML = R.map(r => `<option value="${r.k}">${esc(r.n)}</option>`).join('');
if (qs.get('gov') && R.some(r => r.k === qs.get('gov'))) $('rqG').value = qs.get('gov');
const cur = () => R.find(r => r.k === $('rqG').value);
function suggestions() {
  const r = cur();
  $('rqS').innerHTML = r.s.map((s, i) => `<label class="rq-opt"><input type="radio" name="rqs" value="${i}"><span><b>${esc(s.t)}</b><small>${esc(s.d)}</small></span></label>`).join('')
    + `<label class="rq-opt"><input type="radio" name="rqs" value="own"><span><b>${L.other}</b><small>${L.otherD}</small></span></label>`;
  const first = $('rqS').querySelector('input'); if (first) { first.checked = true; $('rqD').value = r.s[0] ? r.s[0].d : ''; }
  to(); letter();
}
function to() {
  const r = cur();
  const lines = [`<b>${L.sendTo}</b> ${esc(r.title)}, ${esc(r.agency)}`];
  if (r.email) lines.push(`${L.email} <a href="mailto:${esc(r.email)}">${esc(r.email)}</a>`);
  if (r.phone) lines.push(`${L.phone} ${esc(r.phone)}`);
  if (r.address) lines.push(`${L.mail} ${esc(r.address)}`);
  if (r.portal) lines.push(`${L.online} <a href="${esc(r.portal)}" target="_blank" rel="noopener">${L.portal}</a>`);
  if (!r.email && !r.portal) lines.push(`${L.noEmail} ${r.contact ? `<a href="${esc(r.contact)}" target="_blank" rel="noopener">${L.contact}</a>` : r.site ? `<a href="${esc(r.site)}" target="_blank" rel="noopener">${L.site}</a>` : ''} — ${L.askClerk}`);
  if (r.policy) lines.push(`<a href="${esc(r.policy)}" target="_blank" rel="noopener">${L.policy}</a>`);
  $('rqTo').innerHTML = lines.join('<br>');
  $('rqPortal').hidden = !r.portal; if (r.portal) $('rqPortal').href = r.portal;
}
function letter() {
  const r = cur(), d = $('rqD').value.trim() || '[describe the records you want]';
  const name = $('rqN').value.trim() || L.namePh, contact = $('rqC').value.trim() || L.emailPh, phone = $('rqP').value.trim();
  const today = new Date().toLocaleDateString('en-US', {month: 'long', day: 'numeric', year: 'numeric'});
  const txt = `${today}

To: ${r.title}, ${r.agency}

Re: Public records request

Under Florida's Public Records Act, Chapter 119, Florida Statutes, I request copies of the following public records:

${d}
${$('rqE').checked ? '\nPlease provide the records electronically (PDF, or the original format such as Excel for spreadsheets) by email if possible.\n' : ''}
If any part of these records is exempt from disclosure, please cite the specific statutory exemption for each redaction and release the rest, as required by section 119.07(1)(e) and (f), Florida Statutes.

If fulfilling this request will involve a special service charge or copying costs over $25, please send me an estimate before proceeding.

I prepared this request with the free request tool on BayCounty.me, an independent public records website. BayCounty.me is not making this request and does not need a copy. Please send all replies, cost estimates and records directly to me at the contact information below.

Thank you for your help.
\n${name}\n${contact}${phone ? '\n' + phone : ''}`;
  $('rqL').value = txt;
  const subj = 'Public records request';
  $('rqMail').href = `mailto:${r.email || ''}?subject=${encodeURIComponent(subj)}&body=${encodeURIComponent(txt)}`;
}
$('rqG').addEventListener('change', () => { suggestions(); history.replaceState(null, '', '?gov=' + $('rqG').value); });
$('rqS').addEventListener('change', e => { const v = e.target.value, r = cur(); if (v === 'own') { $('rqD').value = ''; $('rqD').focus(); } else $('rqD').value = r.s[+v].d; letter(); });
['rqD', 'rqN', 'rqC', 'rqP', 'rqE'].forEach(id => $(id).addEventListener('input', () => { letter(); if ($(id).getAttribute('aria-invalid') === 'true') $(id).setAttribute('aria-invalid', 'false'); $('rqMsg').textContent = ''; }));
function ready() {
  const n = $('rqN'), c = $('rqC'), okN = !!n.value.trim(), okC = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(c.value.trim());
  n.setAttribute('aria-invalid', String(!okN)); c.setAttribute('aria-invalid', String(!okC));
  if (okN && okC) return true;
  $('rqMsg').textContent = L.need; (okN ? c : n).focus(); return false;
}
$('rqMail').addEventListener('click', ev => { if (!ready()) ev.preventDefault(); });
$('rqCopy').addEventListener('click', async () => { if (!ready()) return; try { await navigator.clipboard.writeText($('rqL').value); $('rqMsg').textContent = L.copied; } catch (e) { $('rqL').select(); $('rqMsg').textContent = L.selectAll; } });
$('rqPrint').addEventListener('click', () => { if (!ready()) return; const w = window.open('', '_blank'); if (!w) return; w.document.write(`<pre style="font:14px/1.5 Georgia,serif;white-space:pre-wrap;max-width:640px;margin:40px auto">${esc($('rqL').value)}</pre>`); w.document.close(); w.focus(); w.print(); });
suggestions();
})();
