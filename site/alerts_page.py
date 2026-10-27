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


def _rule_options():
    """Board members (from recorded votes) and 2026 candidates, for the rule-alert form."""
    import html as H
    D = _load()
    members = sorted({n for v in (D.get('votes') or {}).get('votes', []) for n in (v.get('by_member') or {})})
    cands = []
    try:
        c = json.load(open(os.path.join(HERE, '..', 'data', 'elections', 'candidates_2026.json')))
        cands = sorted({k['name'] for r in c.get('races', []) for k in r.get('candidates') or [] if k.get('name')})
    except (FileNotFoundError, ValueError):
        pass
    opt = lambda xs: ''.join(f'<option value="{H.escape(x)}">{H.escape(x)}</option>' for x in xs)
    govs = ''.join(f'<option value="{g["key"]}">{H.escape(g["short"])}</option>' for g in GOVS)
    return opt(members), opt(cands), govs


def alerts_page(out_dir):
    digest_json(out_dir)
    m_opts, c_opts, g_opts = _rule_options()
    boxes = ''.join(f'<label class="al-opt"><input type="checkbox" name="g" value="{g["key"]}"><span>{g["short"]}</span></label>' for g in GOVS)
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Get involved</span><h1>Get updates by email</h1>
    <p class="lede">Follow the governments you care about. Once a week, when there's something new, you'll get a short email: new votes and data, corrections, and the meetings coming up.</p></div></header>
  <p class="note" style="margin:0">Looking for weather warnings, evacuation orders, shelters or boil-water notices? See <a href="/emergency">Emergencies and alerts</a>, updated every 5 minutes, and <a href="/hurricane-prep">Hurricane prep</a>.</p>
  <div class="al-status" id="alStatus" hidden></div>
  <form class="contact al-form" id="alForm" novalidate>
    <div class="vf"><span>Follow</span><div class="al-grid" role="group" aria-label="Governments to follow">{boxes}</div>
      <button type="button" class="linkbtn al-all" id="alAll">Select all</button></div>
    <label class="cf-f"><span>Email</span><input name="email" type="email" autocomplete="email" required maxlength="200" placeholder="you@example.com"></label>
    <label class="cf-hp" aria-hidden="true">Website <input name="website" type="text" tabindex="-1" autocomplete="off"></label>
    <div class="cf-go"><button type="submit">Sign up</button><p class="cf-msg" id="alMsg" role="status" aria-live="polite"></p></div>
    <p class="cf-note">We'll email you a link to confirm first. Your address is used only for these updates, never shared or published, and every email has a one-click unsubscribe. Emails come from hello@baycounty.me.</p>
  </form>
  <section class="tx-sec" id="rules"><div class="sec-hd"><h2>Alerts for one thing</h2></div>
    <p>Get an email only when something specific shows up: a big contract, a vote by a board member, a street name on an agenda, or a new campaign report. We check every morning.</p>
    <div class="al-status" id="rlStatus" hidden></div>
    <form class="contact al-form" id="rlForm" novalidate>
      <label class="cf-f"><span>Tell me about</span><select name="type" id="rlType">
        <option value="contract">New contracts or change orders over an amount</option>
        <option value="vote">Votes by a board member</option>
        <option value="keyword">Meetings that mention a word or street</option>
        <option value="campaign">New campaign reports for a 2026 candidate</option></select></label>
      <div class="cf-row" data-for="contract"><label class="cf-f"><span>Government</span><select name="gov">{g_opts}</select></label>
        <label class="cf-f"><span>Over this amount ($)</span><input name="min" inputmode="numeric" placeholder="100000" value="100000" maxlength="12"></label></div>
      <label class="cf-f" data-for="vote" hidden><span>Board member</span><select name="member">{m_opts}</select></label>
      <div class="cf-row" data-for="keyword" hidden><label class="cf-f"><span>Word or street name</span><input name="keyword" maxlength="60" placeholder="Ohio Ave"></label>
        <label class="cf-f"><span>Government <em>(optional)</em></span><select name="kgov"><option value="">Any</option>{g_opts}</select></label></div>
      <label class="cf-f" data-for="campaign" hidden><span>Candidate</span><select name="candidate">{c_opts}</select></label>
      <label class="cf-f"><span>Email</span><input name="email" type="email" autocomplete="email" required maxlength="200" placeholder="you@example.com"></label>
      <label class="cf-hp" aria-hidden="true">Website <input name="website" type="text" tabindex="-1" autocomplete="off"></label>
      <div class="cf-go"><button type="submit">Set up alert</button><p class="cf-msg" id="rlMsg" role="status" aria-live="polite"></p></div>
      <p class="cf-note">We'll email you a link to confirm first. Keyword alerts read agenda item titles where the board posts them as text; PDF-only agendas are matched on the meeting title. A match only means a record mentions what you asked about.</p>
    </form></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="what">What you'll get</h2></div><ul class="plain">
    <li><b>Weekly, only when there's news.</b> No email in a quiet week.</li>
    <li><b>What's new</b> for each government you follow: votes, contracts, data updates and corrections from the <a href="/updates">change log</a>.</li>
    <li><b>Meetings coming up</b> in the next week, with agenda links when they're posted. See all of them on the <a href="/meetings">meetings page</a>.</li>
    <li>Prefer a feed reader? Use the <a href="/updates.xml">RSS feed</a>.</li></ul></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="manage">Change or stop your emails</h2></div>
    <p>Every email has a <b>Change what you follow</b> link that lets you add or remove governments, turn off alerts or unsubscribe from everything. Lost it? <a href="/alerts/manage">Get a new link by email</a>.</p></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>
(() => {{
  const f = document.getElementById('alForm'), msg = document.getElementById('alMsg'), btn = f.querySelector('button[type=submit]'), st = document.getElementById('alStatus'), t0 = Date.now();
  const q = new URLSearchParams(location.search), boxes = [...f.querySelectorAll('input[name=g]')];
  (q.get('gov') || q.get('g') || '').split(',').forEach(k => {{ const b = boxes.find(x => x.value === k); if (b) b.checked = true; }});
  // no government in the link: start with the city picked on other pages (site.js loads after this inline script)
  if (!q.has('gov') && !q.has('g')) document.addEventListener('DOMContentLoaded', () => {{
    const k = window.BCM && BCM.city.remembered && BCM.city.remembered();
    if (!k || boxes.some(x => x.checked)) return;
    const b = boxes.find(x => x.value === k); if (b) b.checked = true;
    const sel = [document.querySelector('#rlForm select[name=gov]')]; // the keyword alert's government stays "Any"
    sel.forEach(s => {{ if (s && [...s.options].some(o => o.value === k)) s.value = k; }});
  }});
  const S = {{confirmed: ['ok', "You're signed up. Your first update arrives the next week there's news."], rule_confirmed: ['ok', "Your alert is on. We'll email you when something new matches."], expired: ['err', 'That confirmation link has expired or is invalid. Sign up again below.'], error: ['err', 'Something went wrong confirming your sign-up. Please try again.']}};
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
  const rf = document.getElementById('rlForm'), rm = document.getElementById('rlMsg'), rt = document.getElementById('rlType'), rb = rf.querySelector('button[type=submit]');
  const show = () => rf.querySelectorAll('[data-for]').forEach(x => {{ x.hidden = x.dataset.for !== rt.value; x.style.display = x.hidden ? 'none' : ''; }});
  rt.addEventListener('change', show); show();
  if (q.get('status') === 'rule_confirmed') {{ const rs = document.getElementById('rlStatus'); rs.hidden = false; rs.className = 'al-status ok'; rs.textContent = S.rule_confirmed[1]; st.hidden = true; }}
  rf.addEventListener('submit', async e => {{
    e.preventDefault();
    const type = rt.value, F = rf.elements;
    const params = type === 'contract' ? {{gov: F.gov.value, min: F.min.value}} : type === 'vote' ? {{member: F.member.value}} : type === 'keyword' ? {{keyword: F.keyword.value, gov: F.kgov.value}} : {{candidate: F.candidate.value}};
    if (!F.email.checkValidity() || !F.email.value) {{ rm.className = 'cf-msg err'; rm.textContent = 'Please enter a valid email address.'; F.email.focus(); return; }}
    rb.disabled = true; rm.className = 'cf-msg'; rm.textContent = 'Sending…';
    try {{
      const r = await fetch('/api/subscribe', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{email: F.email.value, rule: {{type, params}}, website: F.website.value, t: t0}})}});
      const j = await r.json().catch(() => ({{}}));
      if (!r.ok || !j.ok) throw new Error(j.error || 'Sign-up failed. Please try again.');
      rm.className = 'cf-msg ok'; rm.textContent = 'Check your email for a link to confirm.'; F.email.value = '';
    }} catch (err) {{ rm.className = 'cf-msg err'; rm.textContent = err.message; }}
    rb.disabled = false;
  }});
}})();
</script>'''
