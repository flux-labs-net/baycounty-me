"""Volunteer and nonprofit needs board (/volunteer): open volunteer needs in the county, and the local nonprofits that
rely on volunteers.

Built from the volunteer-needs and volunteer-orgs datasets (site/volunteer_data.py). Organization names link to their
nonprofit profile where the board's name matched one; people are never named here.
"""
import datetime as dt
import html

from entity_links import a as link, build
from ui import avatar, ico, tone_of
from volunteer_data import CAUSES

e = lambda s: html.escape(str(s if s is not None else ''))

TONE = {'Kids and mentoring': 'blue', 'Schools and reading': 'blue', 'Food and basic needs': 'amber', 'Health and hospice': 'salmon',
        'Seniors': 'salmon', 'Disaster and emergency': 'salmon', 'Housing and neighborhoods': 'teal', 'Animals': 'teal',
        'Arts and culture': 'amber', 'Environment': 'teal', 'Veterans and service clubs': 'blue', 'Sports and recreation': 'teal',
        'Events and fundraisers': 'amber', 'Faith': 'amber', 'Other': 'blue'}

CSS = r"""
.vo-ctl{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}
.vo-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.vo-card{display:flex;flex-direction:column;gap:10px;padding:18px 20px;border-radius:22px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.vo-card[hidden]{display:none!important}
.vo-card h3{font-size:1.02rem;font-weight:600;margin:0;line-height:1.35;text-wrap:balance;overflow-wrap:anywhere}
.vo-card h3 a{color:inherit;text-decoration:none}
.vo-card h3 a:hover{color:var(--blue);text-decoration:underline}
.vo-org{font-size:.88rem;color:var(--muted);margin:0;overflow-wrap:anywhere}
.vo-org a{color:inherit}
.vo-card p.vo-d{margin:0;font-size:.9rem;line-height:1.5;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.vo-meta{display:flex;flex-wrap:wrap;gap:6px}
.vo-pill{display:inline-flex;align-items:center;font-size:.74rem;font-weight:600;padding:3px 10px;border-radius:999px;background:var(--sunken);color:var(--muted);white-space:nowrap}
.vo-pill.t-blue{background:color-mix(in srgb,var(--blue) 14%,transparent);color:var(--blue)}
.vo-pill.t-teal{background:color-mix(in srgb,var(--teal) 16%,transparent);color:var(--teal)}
.vo-pill.t-amber{background:color-mix(in srgb,var(--amber) 18%,transparent);color:color-mix(in srgb,var(--amber) 70%,var(--ink))}
.vo-pill.t-salmon{background:color-mix(in srgb,var(--salmon) 16%,transparent);color:color-mix(in srgb,var(--salmon) 75%,var(--ink))}
.vo-foot{display:flex;flex-wrap:wrap;gap:8px;margin-top:auto;padding-top:4px}
.vo-foot .ui-btn{min-height:38px;font-size:.84rem}
.vo-hd{display:flex;gap:12px;align-items:center;min-width:0}
.vo-hd .ui-av{margin:0;flex:none;width:42px;height:42px;font-size:14px}
.vo-hd > div{min-width:0}
.vo-nums{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:.84rem;color:var(--muted)}
.vo-nums b{color:var(--ink);font-variant-numeric:tabular-nums;font-weight:600}
.vo .vo-morebtn{width:auto;border:0;cursor:pointer;font-family:inherit}
.vo .vo-morebtn[hidden],.vo [data-none][hidden]{display:none}
.vo-search{min-height:40px;padding:0 14px;border-radius:12px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font:inherit;font-size:.9rem;min-width:0;width:260px;max-width:100%}
@media (max-width:760px){.vo-grid{grid-template-columns:1fr}.vo-card{padding:16px}.vo-search{width:100%}
  .vo-ctl .chips{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;margin:0 -16px;padding:2px 16px;max-width:calc(100% + 32px)}.vo-ctl .chips .chip{flex:none}}
"""

JS = r"""
(() => {
  const root = document.querySelector('.vo'); if (!root) return;
  let cause = '', q = '', np = '';
  const N = matchMedia('(max-width:760px)').matches ? 6 : 12;
  const lists = [...root.querySelectorAll('[data-list]')].map(box => ({box, cards: [...box.querySelectorAll('.vo-card')], open: false,
    more: root.querySelector(`[data-more="${box.dataset.list}"]`), none: root.querySelector(`[data-none="${box.dataset.list}"]`)}));
  function show() {
    for (const L of lists) {
      let n = 0;
      for (const c of L.cards) {
        const ok = (!cause || c.dataset.cause === cause) && (!q || c.dataset.q.includes(q)) && (!np || c.dataset.np === np);
        c.hidden = !ok || (!L.open && n >= N); if (ok) n++;
      }
      const left = n - N;
      if (L.more) { L.more.hidden = L.open || left <= 0; L.more.textContent = `Show ${left} more`; }
      if (L.none) L.none.hidden = n > 0;
    }
  }
  const g = document.getElementById('voCause');
  g.addEventListener('click', ev => { const b = ev.target.closest('button'); if (!b) return;
    g.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); cause = b.dataset.v; show(); });
  const s = document.getElementById('voSearch');
  s.addEventListener('input', () => { q = s.value.trim().toLowerCase(); np = ''; show(); });
  root.addEventListener('click', ev => { const b = ev.target.closest('[data-org]'); if (!b) return;
    np = b.dataset.org; q = ''; s.value = b.dataset.name; cause = '';
    g.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x.dataset.v === '')); show(); });
  for (const L of lists) if (L.more) L.more.addEventListener('click', () => { L.open = true; show(); });
  show();
})();
"""


def _money(n):
    if not n:
        return None
    return f'${n / 1e6:.1f}M' if n >= 1e6 else f'${round(n / 1e3):,}K' if n >= 1e4 else f'${round(n):,}'


def _date(s):
    try:
        return dt.date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


def when_label(r):
    """'Ongoing', 'Thu, Dec 3', 'Shifts', 'Nov 1 to Nov 8'. Mirrors Volunteer.whenLabel in the apps."""
    s, en = _date(r.get('starts')), _date(r.get('ends'))
    if r.get('schedule') == 'Shifts':
        return 'Multiple shifts'
    if s and en and en != s:
        return f"{s.strftime('%b %-d')} to {en.strftime('%b %-d')}"
    if s:
        return s.strftime('%a, %b %-d')
    return 'Ongoing'


def _org_link(name, eid):
    return link(eid, name) if eid and eid in build().ents else e(name)


def _pill(cause):
    return f'<span class="vo-pill t-{TONE.get(cause, "blue")}">{e(cause)}</span>'


def _need_card(r):
    where = 'Remote or from home' if r.get('remote') and not r.get('city') else (r.get('city') or 'Location varies')
    btn = 'Sign up' if r['board'] != 'Idealist' else 'Details and sign-up'
    q = ' '.join(x or '' for x in (r['title'], r['organization'], r.get('description'), r.get('city'))).lower()
    return f'''<article class="vo-card" data-cause="{e(r["cause"])}" data-q="{e(q)}" data-np="{e(r.get("nonprofit_id") or "")}">
  <div class="vo-meta">{_pill(r["cause"])}<span class="vo-pill">{ico("calendar")}&nbsp;{e(when_label(r))}</span><span class="vo-pill">{ico("pin")}&nbsp;{e(where)}</span></div>
  <h3><a href="{e(r["url"])}" rel="noopener" target="_blank">{e(r["title"])}</a></h3>
  <p class="vo-org">{_org_link(r["organization"], r.get("organization_entity_id"))}</p>
  {f'<p class="vo-d">{e(r["description"])}</p>' if r.get("description") else ""}
  <div class="vo-foot"><a class="ui-btn" href="{e(r["url"])}" rel="noopener" target="_blank">{ico("arrow")}{btn}</a><span class="muted" style="font-size:.78rem;align-self:center">via {e(r["board"])}</span></div>
</article>'''


def _org_card(o):
    nums = []
    if o.get('volunteers_reported'):
        nums.append(f'<span><b>{o["volunteers_reported"]:,}</b> volunteers ({o["volunteers_year"]} filing)</span>')
    if o.get('employees'):
        nums.append(f'<span><b>{o["employees"]:,}</b> staff</span>')
    if _money(o.get('revenue')):
        nums.append(f'<span><b>{_money(o["revenue"])}</b> revenue</span>')
    acts = []
    if o.get('open_needs'):
        acts.append(f'<a class="ui-btn" href="#needs" data-org="{e(o["nonprofit_id"])}" data-name="{e(o["name"])}">{ico("heart")}{o["open_needs"]} open need{"s" if o["open_needs"] != 1 else ""}</a>')
    if o.get('website'):
        acts.append(f'<a class="ui-btn" href="{e(o["website"])}" rel="noopener" target="_blank">{ico("globe")}Website</a>')
    q = ' '.join(x or '' for x in (o['name'], o.get('mission'), o.get('city'))).lower()
    return f'''<article class="vo-card" data-cause="{e(o["cause"])}" data-q="{e(q)}" data-np="{e(o["nonprofit_id"])}">
  <div class="vo-hd">{avatar(o["name"], TONE.get(o["cause"], tone_of(o["name"])))}<div><h3>{_org_link(o["name"], o["entity_id"])}</h3>
    <p class="vo-org">{e(o.get("city") or "")}</p></div></div>
  <div class="vo-meta">{_pill(o["cause"])}</div>
  {f'<p class="vo-d">{e(o["mission"])}</p>' if o.get("mission") else ""}
  <div class="vo-nums">{"".join(nums)}</div>
  {f'<div class="vo-foot">{"".join(acts)}</div>' if acts else ""}
</article>'''


def volunteer_page(out_dir):
    from volunteer_data import volunteer_needs, volunteer_orgs
    N, O = volunteer_needs(), volunteer_orgs()
    today = dt.date.today().isoformat()
    N = [r for r in N if (r.get('closes') or r.get('ends') or '9999') >= today]
    order = {c: i for i, c in enumerate(CAUSES)}
    N.sort(key=lambda r: (r.get('starts') is None, r.get('starts') or '', order.get(r['cause'], 99), r['organization'] or ''))
    used = [c for c in CAUSES if any(x['cause'] == c for x in N + O)]
    chips = ''.join(f'<button type="button" class="chip" data-v="{e(c)}" aria-pressed="false">{e(c)}</button>' for c in used)
    as_of = N[0]['as_of'] if N else today
    boards = list(dict.fromkeys(r['board'] for r in N))
    n_orgs_posting = len({r['organization'] for r in N})
    local = sum(1 for r in N if r.get('nonprofit_id'))
    reported = sum(o['volunteers_reported'] or 0 for o in O)

    k = lambda lab, v, s: f'<div class="kpi"><span class="eyebrow">{lab}</span><span class="v">{v}</span><span class="s">{s}</span></div>'
    kpis = (k('Open needs', len(N), f'From {n_orgs_posting} organizations, on {len(boards)} public volunteer boards') +
            k('Posted by local nonprofits', local, 'The rest are regional groups serving Bay County') +
            k('Nonprofits that use volunteers', len(O), 'Reported on their IRS filing, or posting a need now') +
            k('Volunteers they reported', f'{reported:,}', 'On their latest Form 990; some counts cover a whole state group'))

    return f'''<style>{CSS}</style>
<div class="page tax vo">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Take part · Volunteer</span><h1>Volunteer in Bay County</h1>
    <p class="lede">Local nonprofits looking for help right now, and the groups that rely on volunteers year-round. Pick a cause, find something that fits, and sign up with the organization.</p></div>
    <div class="stamp"><a class="pill" href="/connections/nonprofits">All nonprofits →</a><span>Needs checked {e(as_of)}</span></div></header>
  <div class="kpis">{kpis}</div>

  <section class="tx-sec"><div class="vo-ctl">
    <div class="chips" id="voCause" role="group" aria-label="Cause"><button type="button" class="chip" data-v="" aria-pressed="true">All causes</button>{chips}</div>
    <input type="search" class="vo-search" id="voSearch" placeholder="Search needs and nonprofits" aria-label="Search needs and nonprofits">
  </div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="needs" data-tile="Open needs">Open needs right now</h2><span class="muted">Soonest first, then ongoing</span></div>
    <div class="vo-grid" data-list="needs">{"".join(_need_card(r) for r in N)}</div>
    <p class="note" data-none="needs" hidden>No open needs match. Try another cause, or reach out to one of the nonprofits below.</p>
    <div><button type="button" class="ui-btn vo-morebtn" data-more="needs" hidden>Show more</button></div>
    <p class="note">Sign-up happens on the organization's board. Needs are read every day from {" and ".join(e(b) for b in boards)}; check the details there before you go.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="nonprofits" data-tile="Who uses volunteers">Nonprofits that rely on volunteers</h2><span class="muted">Open needs first, then by volunteers reported</span></div>
    <div class="vo-grid" data-list="orgs">{"".join(_org_card(o) for o in O)}</div>
    <p class="note" data-none="orgs" hidden>No nonprofits match.</p>
    <div><button type="button" class="ui-btn vo-morebtn" data-more="orgs" hidden>Show more</button></div>
    <p class="note">Volunteer counts are each organization's own estimate on Form 990, Part I, line 6. Statewide groups with a Bay County address (a state VFW department, for example) report for the whole group. Smaller nonprofits file the 990-EZ or 990-N, which don't ask, so many active groups aren't counted here: see <a href="/connections/nonprofits">every nonprofit</a>.</p></section>

  <section class="explain"><div class="ex-txt"><span class="eyebrow">Getting started</span><h2>How to help</h2>
    <ol class="ex-steps"><li><b>Pick a cause and a schedule.</b> Ongoing roles like mentoring ask for a few hours a month; one-day events need no long commitment.</li>
    <li><b>Sign up with the organization.</b> Many roles that work with children or patients ask for a background check and a short training first.</li>
    <li><b>No need listed?</b> Most nonprofits below take volunteers year-round. Visit their website or call and ask what they need.</li></ol></div></section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Open needs</b> are read every day from United Way of Northwest Florida's volunteer center and from Idealist's listings for Bay County towns. Only needs in a Bay County town or ZIP are kept. We copy the title, organization, what volunteers do, when, and the city; no addresses or contact names.</li>
      <li><b>Organizations</b> are joined to local nonprofits by exact name (a few checked by hand), so their names link to the nonprofit's profile with its filings, board and public money.</li>
      <li><b>Causes</b> are plain groupings made from each need's words and the nonprofit's IRS category.</li>
      <li><b>Volunteer counts, staff and revenue</b> come from each nonprofit's latest e-filed IRS Form 990.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/volunteer-needs">volunteer-needs</a> (<a href="/downloads/volunteer-needs.csv">CSV</a>) · <a href="/api/v1/datasets/volunteer-orgs">volunteer-orgs</a> (<a href="/downloads/volunteer-orgs.csv">CSV</a>).</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>{JS}</script>'''
