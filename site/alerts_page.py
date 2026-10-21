"""Email alerts sign-up (/alerts) and the weekly digest feed (/data/digest.json)."""
import json, os, re
from govs import GOVS, _load

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = {g['key']: g['short'] for g in GOVS}
PAT = {'county': r'\bBay County\b(?! (District|Utility))|County Commission', 'schools': r'School Board|Bay District Schools',
       'pc': r'Panama City(?! Beach)', 'pcb': r'Panama City Beach', 'lh': r'Lynn Haven', 'cw': r'Callaway', 'sp': r'Springfield', 'parker': r'\bParker\b', 'mb': r'Mexico Beach'}


def digest_json(out_dir):
    from updates import CHANGES
    D = _load()
    govs = []
    for g in GOVS:
        ch = []
        for c in CHANGES[:40]:
            txt = c['title'] + ' ' + c['text']
            named = [k for k, p in PAT.items() if re.search(p, txt)]
            if c.get('govs'):
                named = c['govs']
            if not named or g['key'] in named or f'/governments/{g["slug"]}' in c['pages']:
                ch.append({'date': c['date'], 'title': c['title'], 'text': c['text'], 'url': 'https://baycounty.me' + (c['pages'][0] if c['pages'] else '/updates')})
        meets = []
        md = D.get('meetings') or {}
        bids = {b['id'] for b in md.get('boards', []) if b.get('gov') == g['key']}
        for m in md.get('meetings', []):
            if m.get('board') in bids and not m.get('past') and m.get('start'):
                meets.append({k: m.get(k) for k in ('start', 'title', 'agenda_url', 'expected', 'location')})
        govs.append({'key': g['key'], 'slug': g['slug'], 'name': g['short'], 'changes': ch, 'meetings': meets})
    os.makedirs(os.path.join(out_dir, 'data'), exist_ok=True)
    json.dump({'govs': govs}, open(os.path.join(out_dir, 'data', 'digest.json'), 'w'), separators=(',', ':'))


def alerts_page(out_dir):
    digest_json(out_dir)
    boxes = ''.join(f'<label class="al-opt"><input type="checkbox" name="g" value="{g["key"]}"><span>{g["short"]}</span></label>' for g in GOVS)
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Get involved</span><h1>Get updates by email</h1>
    <p class="lede">Follow the governments you care about. Once a week, when there's something new, you'll get a short email: new votes and data, corrections, and the meetings coming up.</p></div></header>
  <div class="al-status" id="alStatus" hidden></div>
  <form class="contact al-form" id="alForm" novalidate>
    <div class="vf"><span>Follow</span><div class="al-grid" role="group" aria-label="Governments to follow">{boxes}</div>
      <button type="button" class="linkbtn al-all" id="alAll">Select all</button></div>
    <label class="cf-f"><span>Email</span><input name="email" type="email" autocomplete="email" required maxlength="200" placeholder="you@example.com"></label>
    <label class="cf-hp" aria-hidden="true">Website <input name="website" type="text" tabindex="-1" autocomplete="off"></label>
    <div class="cf-go"><button type="submit">Sign up</button><p class="cf-msg" id="alMsg" role="status" aria-live="polite"></p></div>
    <p class="cf-note">We'll email you a link to confirm first. Your address is used only for these updates, never shared or published, and every email has a one-click unsubscribe. Emails come from alerts@fluxlabs.net.</p>
  </form>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="what">What you'll get</h2></div><ul class="plain">
    <li><b>Weekly, only when there's news.</b> No email in a quiet week.</li>
    <li><b>What's new</b> for each government you follow: votes, contracts, data updates and corrections from the <a href="/updates">change log</a>.</li>
    <li><b>Meetings coming up</b> in the next week, with agenda links when they're posted. See all of them on the <a href="/meetings">meetings page</a>.</li>
    <li>Prefer a feed reader? Use the <a href="/updates.xml">RSS feed</a>.</li></ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>
(() => {{
  const f = document.getElementById('alForm'), msg = document.getElementById('alMsg'), btn = f.querySelector('button[type=submit]'), st = document.getElementById('alStatus'), t0 = Date.now();
  const q = new URLSearchParams(location.search), boxes = [...f.querySelectorAll('input[name=g]')];
  (q.get('gov') || q.get('g') || '').split(',').forEach(k => {{ const b = boxes.find(x => x.value === k); if (b) b.checked = true; }});
  const S = {{confirmed: ['ok', "You're signed up. Your first update arrives the next week there's news."], expired: ['err', 'That confirmation link has expired or is invalid. Sign up again below.'], error: ['err', 'Something went wrong confirming your sign-up. Please try again.']}};
  if (S[q.get('status')]) {{ st.hidden = false; st.className = 'al-status ' + S[q.get('status')][0]; st.textContent = S[q.get('status')][1]; }}
  fetch('/api/subscribe').then(r => r.json()).then(j => {{ if (!j.ready) {{ f.querySelectorAll('input,button').forEach(x => x.disabled = true); msg.className = 'cf-msg'; msg.textContent = 'Email alerts are launching soon. Until then, follow the RSS feed or check What\u2019s new.'; }} }}).catch(() => {{}});
  document.getElementById('alAll').addEventListener('click', () => boxes.forEach(b => b.checked = true));
  f.addEventListener('submit', async e => {{
    e.preventDefault();
    const govs = boxes.filter(b => b.checked).map(b => b.value);
    if (!govs.length) {{ msg.className = 'cf-msg err'; msg.textContent = 'Pick at least one government.'; return; }}
    if (!f.email.checkValidity() || !f.email.value) {{ msg.className = 'cf-msg err'; msg.textContent = 'Please enter a valid email address.'; f.email.focus(); return; }}
    btn.disabled = true; msg.className = 'cf-msg'; msg.textContent = 'Sending…';
    try {{
      const r = await fetch('/api/subscribe', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{email: f.email.value, govs, website: f.website.value, t: t0}})}});
      const j = await r.json().catch(() => ({{}}));
      if (!r.ok || !j.ok) throw new Error(j.error || 'Sign-up failed. Please try again.');
      msg.className = 'cf-msg ok'; msg.textContent = 'Check your email for a link to confirm.'; f.email.value = '';
    }} catch (err) {{ msg.className = 'cf-msg err'; msg.textContent = err.message; }}
    btn.disabled = false;
  }});
}})();
</script>'''
