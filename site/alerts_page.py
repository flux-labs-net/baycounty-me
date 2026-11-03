"""Email alerts sign-up (/alerts) and the weekly digest feed (/data/digest.json)."""
import json, os, re
from urllib.parse import urlencode
from govs import GOVS, _load

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = {g['key']: g['short'] for g in GOVS}


# How far back the feed keeps "new" items and how far ahead "coming up" items. The Monday email (digestEmail in
# api/_emails.js) shows the last 7 days and the next 8; the wider window lets the /admin preview fall back to 60 days.
BACK_DAYS, AHEAD_DAYS, KEEP = 60, 14, 80
TEST = re.compile(r'\btest(ing)?\b', re.I)  # staff test alerts (an admin can hide them on the site, but not in this file)


def _town_of(g):
    return {'county': 'Bay County'}.get(g['key'], g['short'])


def _city_news(today=None):
    """What happened and what's coming up in each government, keyed by gov key: alerts, events, new votes and contracts,
    public notices and job openings. All of it comes from the published datasets (emergency-notices, community-events,
    school-calendar, votes, contracts, change-orders, public-notices, job-openings)."""
    import datetime as dt
    import weekly
    from page_datasets import community_events, emergency_notices, public_notices, job_openings, school_calendar
    today = today or dt.datetime.now(weekly.TZ).date()
    back, ahead = (today - dt.timedelta(days=BACK_DAYS)).isoformat(), (today + dt.timedelta(days=AHEAD_DAYS)).isoformat()
    now = today.isoformat()
    towns = {_town_of(g): g['key'] for g in GOVS}
    out = {g['key']: {'alerts': [], 'events': [], 'votes': [], 'contracts': [], 'notices': [], 'jobs': []} for g in GOVS}
    add = lambda key, sec, row: key in out and out[key][sec].append(row)

    # Alerts that named this government (boil-water, road closures, outages, city news posts). Countywide weather
    # warnings are left out: by Monday they're over, and /emergency has the live list.
    for n in emergency_notices():
        when = str(n.get('issued') or n.get('first_seen') or '')[:10]
        if n.get('same_as') or not n.get('gov_id') or not (back <= when <= now) or TEST.search(f"{n.get('title')} {n.get('summary')}"):
            continue
        add(n['gov_id'], 'alerts', {'date': when, 'title': n.get('title'), 'text': n.get('summary') or n.get('instruction') or '',
                                    'kind': n.get('kind'), 'status': n.get('status'), 'url': f"https://baycounty.me/emergency#n-{n['notice_id']}"})

    # Events in town (community calendar), plus the school calendar for the school district. Public meetings are
    # their own section, so the calendar's copies of them are left out.
    for r in community_events():
        st = r.get('starts') or ''
        if r.get('same_as') or r.get('category') == 'Public meeting' or not (now <= st[:10] <= ahead):
            continue
        key = r.get('gov') or towns.get(r.get('town'))
        add(key, 'events', {'start': st, 'all_day': bool(r.get('all_day')), 'title': r.get('title'), 'venue': r.get('venue'),
                            'recurring': bool(r.get('recurring')), 'url': r.get('url') or 'https://baycounty.me/events'})
    for r in school_calendar():
        st = r.get('starts') or ''
        if r.get('kind') == 'board-meeting' or not (now <= st[:10] <= ahead):
            continue
        add('schools', 'events', {'start': st, 'all_day': bool(r.get('all_day')), 'title': r.get('title'), 'venue': r.get('venue'),
                                  'recurring': False, 'url': 'https://baycounty.me/schools#calendar'})

    # Votes, contracts and change orders that reached the site (first seen) in the window. Minutes come out weeks after
    # a meeting, so "new" is when we first had it, the same rule as This week in Bay County (site/weekly.py): a record
    # held more than FRESH_DAYS before we first saw it is a backfill, not news.
    seen = weekly._first_seen()
    lo, hi = today - dt.timedelta(days=BACK_DAYS), today
    fresh = lambda r: (r.get('date') or '') >= (dt.date.fromisoformat(r['first_seen'][:10]) - dt.timedelta(days=weekly.FRESH_DAYS)).isoformat()
    for r in filter(fresh, weekly._votes(seen, lo, hi)):
        add(r['gov_id'], 'votes', {'date': r['first_seen'], 'held': r['date'], 'title': r['title'], 'text': r.get('summary') or '',
                                   'board': r.get('board'), 'outcome': r.get('outcome'), 'tally': r.get('tally'), 'split': bool(r.get('split')),
                                   'voted_no': [{'name': p['name'], 'url': p['url']} for p in r.get('people') or []], 'url': r['url']})
    for r in filter(fresh, weekly._contracts(seen, lo, hi)):
        add(r['gov_id'], 'contracts', {'date': r['first_seen'], 'held': r['date'], 'kind': r['section'], 'amount': r.get('amount') or 0,
                                       'vendor': r.get('title'), 'text': r.get('summary') or '', 'url': r['url'], 'source_url': r.get('source_url')})

    for r in public_notices():
        if r.get('same_as') or not (back <= (r.get('published') or '') <= now):
            continue
        add(r.get('gov_id'), 'notices', {'date': r['published'], 'title': r.get('title'), 'kind': r.get('kind_label'), 'event_date': r.get('event_date'),
                                         'text': (r.get('text') or '').split('\n\n')[0],
                                         'url': r.get('pdf_url') or 'https://baycounty.me/notices?' + urlencode({'gov': r.get('gov_id'), 'q': (r.get('title') or '')[:40]})})
    for r in job_openings():
        when = r.get('first_seen') or r.get('posted') or ''
        if r.get('same_as') or not (back <= when <= now):
            continue
        add(r.get('gov_id'), 'jobs', {'date': when, 'title': r.get('title'), 'department': r.get('department'), 'job_type': r.get('job_type'),
                                      'pay': r.get('pay'), 'closes': r.get('closes'), 'url': r.get('url') or 'https://baycounty.me/jobs'})

    for secs in out.values():
        for k, rows in secs.items():
            if k == 'events':
                rows.sort(key=lambda x: (x['recurring'], x['start']))
            elif k not in ('votes', 'contracts'):  # votes keep weekly.py's order (split and big votes first); contracts biggest first
                rows.sort(key=lambda x: x['date'], reverse=True)
            del rows[KEEP:]
    return out


def digest_json(out_dir):
    """/data/digest.json: one entry per government for the Monday city emails (api/digest.js)."""
    D = _load()
    news = _city_news()
    govs = []
    for g in GOVS:
        meets = []
        md = D.get('meetings') or {}
        bids = {b['id']: b for b in md.get('boards', []) if b.get('gov') == g['key']}
        for m in md.get('meetings', []):
            if m.get('board') in bids and not m.get('past') and m.get('start'):
                meets.append({**{k: m.get(k) for k in ('start', 'title', 'agenda_url', 'expected', 'location')}, 'board': bids[m['board']].get('name')})
        govs.append({'key': g['key'], 'slug': g['slug'], 'name': g['short'], 'meetings': meets, **news[g['key']]})
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
    <p class="lede">Follow the governments you care about. Once a week you'll get a short email about each one: meetings and events coming up, new votes and contracts, alerts, public notices and job openings.</p></div></header>
  <p class="note" style="margin:0">Looking for weather warnings, evacuation orders, shelters or boil-water notices? See <a href="/emergency">Emergencies and alerts</a>, updated every 5 minutes, and <a href="/hurricane-prep">Hurricane prep</a>.</p>
  <div class="al-status" id="alStatus" hidden></div>
  <form class="contact al-form" id="alForm" novalidate>
    <div class="vf"><span>Countywide</span><label class="al-opt al-week"><input type="checkbox" name="g" value="week"><span><b>This week in Bay County</b>: events, meetings, new votes and contracts across the county (<a href="/this-week">see this week's</a>)</span></label></div>
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
    <li><b>This week in Bay County</b> (countywide, Mondays): events happening that week, public meetings, and the votes and contracts added the week before. <a href="/this-week">See this week's</a>.</li>
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
    if (!govs.length) {{ msg.className = 'cf-msg err'; msg.textContent = 'Pick the weekly email or at least one government.'; return; }}
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
