"""Government workspace (/staff): where a city's or the county's own staff send emergency alerts, post notices, events
and jobs, and flag record data that looks wrong.

A standalone private page like /finance (no site menu, noindex, not in search or the sitemap). It holds no data:
everything comes from /api/gov after a 6-digit emailed sign-in code. Layout and look are shared with /finance.
Record data is read-only here by design: staff can flag it, never change it (api/_gov.js).
"""
import os
import shutil

import place
from finance_page import CSS as FIN_CSS, THEME_BTN, _ICONS as FIN_ICONS
from site_menu import OPEN_BOOKS_PUBLIC

CSS = FIN_CSS + r"""
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px;margin:0 0 22px}
.tile{display:flex;flex-direction:column;gap:2px;padding:14px 16px;border:1px solid var(--line);border-radius:12px;background:var(--surface);text-align:left;color:var(--ink);font:inherit;cursor:pointer}
.tile:hover{border-color:var(--blue)}
.tile b{font:600 1.5rem var(--f-display);font-variant-numeric:tabular-nums}
.tile span{font-size:.84rem;color:var(--muted)}
.tile.hot{border-left:4px solid var(--urgent)}
.form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 14px}
.form .full{grid-column:1/-1}
@media (max-width:700px){.form{grid-template-columns:1fr}}
label.f input,label.f select,label.f textarea{width:100%;box-sizing:border-box}
label.chk{display:flex;gap:10px;align-items:flex-start;font-size:.9rem;line-height:1.4}
label.chk input{width:18px;height:18px;margin-top:2px}
.reach{display:flex;gap:18px;flex-wrap:wrap;padding:12px 14px;border-radius:10px;background:var(--bg);border:1px solid var(--line);font-size:.9rem}
.reach b{font-variant-numeric:tabular-nums}
.confirm{border:2px solid var(--urgent);border-radius:12px;padding:14px;background:var(--surface);display:flex;flex-direction:column;gap:10px}
.confirm h3{margin:0;font:600 1rem var(--f-display)}
.status{font-size:.76rem;font-weight:600;border-radius:999px;padding:2px 9px;white-space:nowrap}
.status.live{background:color-mix(in srgb,var(--urgent) 16%,transparent);color:var(--urgent)}
.status.pending{background:color-mix(in srgb,var(--review) 18%,transparent);color:var(--review)}
.status.done{background:var(--sunken);color:var(--muted)}
.status.open{background:color-mix(in srgb,var(--review) 18%,transparent);color:var(--review)}
.status.fixed{background:color-mix(in srgb,var(--ok) 16%,transparent);color:var(--ok)}
.items{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px}
.items li{border:1px solid var(--line);border-radius:12px;background:var(--surface);padding:12px 14px;display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap}
.items .grow h3{margin:0;font:600 .95rem var(--f-body);overflow-wrap:anywhere}
.items .meta{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:.8rem;color:var(--muted);margin-top:4px}
.items .body{font-size:.86rem;line-height:1.5;margin:6px 0 0;white-space:pre-line;overflow-wrap:anywhere}
.lock{display:flex;gap:10px;align-items:flex-start;padding:12px 14px;border-radius:10px;border:1px solid var(--line);border-left:4px solid var(--blue);background:var(--surface);font-size:.88rem;line-height:1.5;margin:0 0 14px}
.lock svg{flex-shrink:0;color:var(--blue);margin-top:2px}
.rec td{max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rec td.act{max-width:none}
.due{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin:0 0 20px}
.due>div{border:1px solid var(--line);border-radius:12px;background:var(--surface);padding:12px 14px;display:flex;flex-direction:column;gap:4px;border-left:4px solid var(--review)}
.due>div.in{border-left-color:var(--ok)}
.due b{font:600 .95rem var(--f-body)} .due span{font-size:.82rem;color:var(--muted)}
.kinds{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
.kinds label{display:flex;gap:10px;align-items:flex-start;border:1px solid var(--line);border-radius:12px;padding:12px;background:var(--surface);cursor:pointer;font-size:.86rem;line-height:1.4}
.kinds label:has(input:checked){border-color:var(--blue);box-shadow:0 0 0 1px var(--blue)}
.kinds input{margin-top:3px;width:16px;height:16px;flex-shrink:0}
.kinds b{display:block;font-size:.92rem;margin-bottom:2px}
.inbox{display:flex;gap:12px;align-items:flex-start;padding:12px 14px;border-radius:12px;border:1px solid var(--line);background:var(--surface);font-size:.88rem;line-height:1.5;margin:16px 0}
.inbox svg{flex-shrink:0;color:var(--blue);margin-top:2px}
.inbox code{font:500 .9rem var(--f-mono);background:var(--sunken);padding:2px 6px;border-radius:6px;overflow-wrap:anywhere}
.pvsum{display:flex;flex-wrap:wrap;gap:8px 20px;font-size:.9rem;margin:0 0 12px}
.pvsum b{font-variant-numeric:tabular-nums}
.status.held{background:color-mix(in srgb,var(--urgent) 16%,transparent);color:var(--urgent)}
dialog.modal{border:1px solid var(--line);border-radius:14px;padding:0;width:min(560px,calc(100vw - 32px));background:var(--surface);color:var(--ink)}
dialog.modal::backdrop{background:rgba(10,14,20,.45)}
.modal form{padding:18px 20px;display:flex;flex-direction:column;gap:12px}
.modal h2{font:600 1.05rem var(--f-display);margin:0}
.kv{display:grid;grid-template-columns:auto minmax(0,1fr);gap:4px 12px;font-size:.84rem;margin:0}
.kv dt{color:var(--muted)} .kv dd{margin:0;overflow-wrap:anywhere}
.mapfld{display:flex;flex-direction:column;gap:8px}
.mapfld>span{font-size:.86rem;font-weight:600}
"""

ICONS = {**FIN_ICONS,
         'bell': '<path d="M6 8a6 6 0 0112 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10 21a2 2 0 004 0"/>',
         'post': '<path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h8M8 17h5"/>',
         'upload': '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3"/>',
         'mail': '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
         'lock': '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/>',
         'users': '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.6 3.2-5.5 6.5-5.5s5.9 1.9 6.5 5.5"/><path d="M16 4.5a3.5 3.5 0 010 7M18 14.8c2 .7 3.2 2.5 3.5 5.2"/>'}

# (group, tone, icon, [(tab, label, least role or None)]). Roles: viewer < publisher < alert_sender < owner (staff.js ROLE).
MENU = [
    ('Emergency', 'teal', 'bell', [('alerts', 'Alerts', None)]),
    ('Post', 'blue', 'post', [('notices', 'Public notices', None), ('events', 'Events', None), ('jobs', 'Jobs', None)]),
    ('Your data', 'amber', 'lock', [('submit', 'Send records', None), ('records', 'Record data', None), ('flags', 'Flags you sent', None)]),
    ('Access', 'gray', 'users', [('people', 'People', 'owner'), ('activity', 'Activity log', 'owner')]),
]


def _svg(name, size=18):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def shell_html():
    groups = []
    for group, tone, icon, items in MENU:
        links = ''.join('<a href="#%s" data-tab="%s"%s><span>%s</span><i class="an-n"></i></a>' % (
            t, t, ' data-min="%s" hidden' % m if m else '', label) for t, label, m in items)
        groups.append(f'<div class="an-g"><div class="an-h an-{tone}">{_svg(icon, 14)}{group}</div><div class="an-items">{links}</div></div>')
    return f"""    <header class="an-top">
      <span class="an-logo" aria-hidden="true">BC</span>
      <div class="an-cur"><span id="an-ws-cur">Workspace</span><b id="an-cur">Home</b></div>
      <button class="an-btn" id="an-open" type="button" aria-label="Open menu" aria-expanded="false" aria-controls="an-nav">{_svg('menu', 20)}</button>
    </header>
    <div class="fw-shell">
    <nav class="an" id="an-nav" aria-label="Workspace">
      <div class="an-head">
        <span class="an-logo" aria-hidden="true">BC</span>
        <div class="an-brand"><b>{place.SITE}</b><span>Government workspace</span></div>
        <button class="an-btn an-x" id="an-close" type="button" aria-label="Close menu">{_svg('close', 20)}</button>
      </div>
      <div class="an-ws"><span>Government</span><b id="ws-name"></b><select class="sel" id="ws-pick" aria-label="Government" hidden></select></div>
      <a href="#home" data-tab="home" class="an-home">{_svg('home')}<span>Home</span><i class="an-total" id="live-count" hidden></i></a>
      {''.join(groups)}
      <div class="an-foot">
        <a href="/emergency" target="_blank" rel="noopener"><span>Public alert timeline</span>{_svg('out', 14)}</a>
        <a href="/" target="_blank" rel="noopener"><span>Public site</span>{_svg('out', 14)}</a>
        {THEME_BTN}
        <div class="an-who"><b id="who"></b><div class="row"><span id="who-role" class="grow"></span><button class="btn quiet" id="signout" type="button">Sign out</button></div></div>
      </div>
    </nav>
    <main class="fw-main">
    <h1 class="fw-h" id="fw-h">Home</h1>"""


LOCK_NOTE = (f'<div class="lock">{_svg("lock")}<div><b>Record data can’t be edited here.</b> It comes from public records (budgets, '
             'minutes, rate sheets, the notice website, your job board and calendar). If a number or name is wrong, flag it with the right value '
             'and where it comes from. We check it against the source and fix it there, so the record and the site agree.</div></div>')


def post_panel(kind, label, fields, intro):
    return f"""
    <section id="p-{kind}s" data-panel hidden>
      <p class="sub">{intro}</p>
      <div class="row" style="margin-bottom:12px" data-can="publisher"><button class="btn primary" type="button" data-new="{kind}">Add {label}</button></div>
      <form class="panel form" id="f-{kind}" data-kind="{kind}" hidden style="margin-bottom:16px">
        <input type="hidden" name="id">
{fields}
        <div class="full row"><button class="btn primary" type="submit">Save and post</button><button class="btn quiet" type="button" data-cancel>Cancel</button><span class="small err" role="alert"></span></div>
      </form>
      <h2 class="h2">Posted from this workspace</h2>
      <ul class="items" id="l-{kind}"></ul>
      <details style="margin-top:22px"><summary class="small" style="cursor:pointer">Already on the site from your records (read only)</summary>
        <p class="small muted">Read from your own website, calendar or the notice site. These can’t be edited here; use Record data to flag a mistake.</p>
        <ul class="items" id="r-{kind}"></ul></details>
    </section>"""


NOTICE_FIELDS = """        <label class="f full">Title<input name="title" required maxlength="200"></label>
        <label class="f">Kind<select name="kind"><option value="meeting">Public meeting</option><option value="hearing">Public hearing or ordinance</option><option value="bid">Bid or proposal request</option><option value="utility">Water, sewer or utility work</option><option value="road">Road or street work</option><option value="other">Other notice</option></select></label>
        <label class="f">Meeting, hearing or due date<input type="date" name="event_date"></label>
        <label class="f">Published<input type="date" name="published"></label>
        <label class="f">Link to the document (optional)<input type="url" name="pdf_url" placeholder="https://"></label>
        <label class="f full">Notice text<textarea name="text" required rows="8"></textarea></label>
        <div class="f full mapfld"><span>Map of where it applies (optional)</span><input type="hidden" name="geometry">
        <div class="row"><button class="btn" type="button" data-map-open>Add a map</button><span class="small muted" data-map-sum></span></div><div data-map-box hidden></div></div>"""
EVENT_FIELDS = """        <label class="f full">Event name<input name="title" required maxlength="200"></label>
        <label class="f">Starts<input type="datetime-local" name="starts" required></label>
        <label class="f">Ends (optional)<input type="datetime-local" name="ends"></label>
        <label class="f">Where<input name="venue" maxlength="200"></label>
        <label class="f">Kind<select name="category"><option value="Community">Community event</option><option value="Public meeting">Public meeting</option></select></label>
        <label class="f">Cost (optional)<input name="cost" maxlength="80" placeholder="Free"></label>
        <label class="f">More information (optional)<input type="url" name="url" placeholder="https://"></label>"""
JOB_FIELDS = """        <label class="f full">Job title<input name="title" required maxlength="200"></label>
        <label class="f">Department<input name="department" maxlength="200"></label>
        <label class="f">Type<select name="job_type"><option value="">Not stated</option><option>Full time</option><option>Part time</option><option>Seasonal</option><option>Temporary</option><option>Volunteer</option></select></label>
        <label class="f">Pay (optional)<input name="pay" maxlength="120" placeholder="$18.50 an hour"></label>
        <label class="f">Link to apply<input type="url" name="url" required placeholder="https://"></label>
        <label class="f">Posted<input type="date" name="posted"></label>
        <label class="f">Closes (optional)<input type="date" name="closes"></label>"""


def staff_page(out_dir):
    shell = shell_html()
    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Government workspace · {place.SITE}</title>
<script>try{{var t=localStorage.getItem('theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t)}}catch(e){{}}</script>
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="/assets/site.css">
<style>{CSS}</style>
</head>
<body>
<div class="fw">
  <section id="signin" class="signin" hidden>
    <div class="row" style="justify-content:flex-end;margin-bottom:24px">{THEME_BTN}</div>
    <h1>Government workspace</h1>
    <p class="muted small">For city and county staff with access: send emergency alerts, post notices, events and jobs, send your records, and flag data on {place.SITE}. We’ll email you a 6-digit code.</p>
    <form id="email-form" class="row" style="margin-top:14px">
      <label class="f grow"><span>Work email</span><input type="email" name="email" required autocomplete="email" placeholder="you@cityoflynnhaven.com"></label>
      <button class="btn primary" type="submit" style="align-self:flex-end">Email me a code</button>
    </form>
    <form id="code-form" hidden style="margin-top:14px;display:flex;flex-direction:column;gap:10px">
      <p class="small" id="code-sent"></p>
      <label class="f"><span>6-digit code</span><input class="code" name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9 ]*" maxlength="7" required></label>
      <div class="row"><button class="btn primary" type="submit">Sign in</button><button class="btn quiet" type="button" id="code-back">Use a different email</button></div>
    </form>
    <p id="signin-msg" class="small" role="status" style="margin-top:12px"></p>
    <p class="small muted" style="margin-top:28px">No access yet? Your workspace owner can add you, or write to <a href="mailto:hello@{place.DOMAIN}">hello@{place.DOMAIN}</a>.</p>
  </section>

  <div id="app" hidden data-open-books="{'1' if OPEN_BOOKS_PUBLIC else ''}">
{shell}

    <section id="p-home" data-panel>
      <p class="lead" id="home-lead"></p>
      <div class="tiles" id="home-tiles"></div>
      <h2 class="h2">Latest activity</h2>
      <p class="sub">Everything anyone does here is logged with who and when.</p>
      <ul class="items" id="home-activity"></ul>
    </section>

    <section id="p-alerts" data-panel hidden>
      <p class="sub">An alert goes to residents who asked for that kind of alert on their phone or by email, and shows on the public alert timeline at /emergency. It is labeled with your government’s name.</p>
      <div data-can="alert_sender">
        <form class="panel form" id="f-alert">
          <label class="f">What kind of alert<select name="kind" id="al-kind"></select></label>
          <label class="f">How serious<select name="severity"><option value="extreme">Extreme: act now</option><option value="severe" selected>Severe</option><option value="moderate">Moderate</option><option value="minor">Minor</option><option value="info">For information</option></select></label>
          <label class="f full">Headline<input name="title" required maxlength="140" placeholder="Boil-water notice for Highway 77 north of 23rd Street"></label>
          <label class="f full">What is happening<textarea name="message" required rows="4" maxlength="900"></textarea></label>
          <label class="f full">What people should do (optional)<textarea name="instruction" rows="2" maxlength="900" placeholder="Boil tap water for one minute before drinking or cooking."></textarea></label>
          <div class="f full mapfld"><span>Map of where it applies (optional)</span><input type="hidden" name="geometry">
          <div class="row"><button class="btn" type="button" data-map-open>Add a map</button><span class="small muted" data-map-sum></span></div><div data-map-box hidden></div></div>
          <label class="f">Ends on its own after<select name="hours"><option value="6">6 hours</option><option value="12">12 hours</option><option value="24" selected>1 day</option><option value="48">2 days</option><option value="72">3 days</option><option value="168">1 week</option></select></label>
          <label class="chk full" id="al-cw-l" hidden><input type="checkbox" name="countywide" id="al-cw"><span><b>Send to all of Bay County.</b> A second alert sender has to confirm a countywide alert before it goes out.</span></label>
          <div class="full reach" id="al-reach"></div>
          <div class="full row"><button class="btn primary" type="submit">Review and send</button><span class="small err" role="alert"></span></div>
          <div class="full confirm" id="al-confirm" hidden>
            <h3 id="al-confirm-h"></h3>
            <p class="small" id="al-confirm-p" style="margin:0"></p>
            <div class="row"><button class="btn primary" type="button" id="al-send">Send it</button><button class="btn quiet" type="button" id="al-back">Go back and edit</button></div>
          </div>
        </form>
      </div>
      <p class="readonly" data-cant="alert_sender" hidden>Only alert senders and owners can send alerts. You can see what has been sent.</p>
      <h2 class="h2">Alerts from this workspace</h2>
      <ul class="items" id="l-alerts"></ul>
    </section>
{post_panel('notice', 'a notice', NOTICE_FIELDS, 'Legal notices, hearings, bid openings and meetings. A notice shows on the public notices page as soon as you save it, labeled as posted by your staff.')}
{post_panel('event', 'an event', EVENT_FIELDS, 'Events and closures for the community calendar. They show on the events page as soon as you save them.')}
{post_panel('job', 'a job', JOB_FIELDS, 'Job openings. They show on the government jobs page as soon as you save them, with your link to apply.')}

    <section id="p-submit" data-panel hidden>
      <p class="sub">Send the files your own systems already make: the check register, the budget-vs-actual report, contracts, a payroll or position list, board appointments, fee changes. We read them, you check a preview, and they go on {place.SITE} with the same privacy rules as everything else: payments to private people are listed without their name, and payroll never names employees. Nothing you send changes numbers already on the site.</p>
      <h2 class="h2">What we’d expect by now</h2>
      <div class="due" id="sub-due"></div>
      <div data-can="submit">
        <form class="panel" id="sub-form" style="display:flex;flex-direction:column;gap:14px">
          <div class="kinds" id="sub-kinds" role="radiogroup" aria-label="What are you sending"></div>
          <div class="drop" id="sub-drop" tabindex="0" role="button" aria-label="Choose a file">{_svg('upload', 28)}<b>Drop the file here, or choose it</b><span class="small muted">Excel (.xlsx) or CSV, as it comes out of your system. No need to change the columns.</span></div>
          <input type="file" id="sub-file" accept=".csv,.tsv,.txt,.xlsx" hidden>
          <div class="row" id="sub-opts" hidden><label class="f" id="sub-asof-l">Report “as of” date (if it isn’t in the title)<input type="date" id="sub-asof"></label><label class="f">Printed total (optional, to check the rows add up)<input id="sub-total" inputmode="decimal" placeholder="1,234,567.89"></label></div>
          <p class="small" id="sub-msg" role="status"></p>
        </form>
        <details class="panel" id="sub-one" hidden style="margin-top:14px"><summary><b id="sub-one-h">Or fill in just one</b> <span class="small muted">No file needed</span></summary>
          <form id="sub-one-f" style="display:flex;flex-direction:column;gap:12px;margin-top:12px"><div class="form" id="sub-one-fields"></div>
            <div class="row"><button class="btn primary" type="submit">Publish on {place.SITE}</button><span class="small err" role="alert"></span></div></form></details>
        <div class="panel" id="sub-pv" hidden style="margin-top:14px">
          <h2 class="h2" id="sub-pv-h" style="margin-top:0">Check the preview</h2>
          <div class="pvsum" id="sub-pv-sum"></div>
          <p class="small" id="sub-pv-note"></p>
          <div class="tw"><table class="t rec" id="sub-pv-t"><thead></thead><tbody></tbody></table></div>
          <div class="row" style="margin-top:12px"><button class="btn primary" type="button" id="sub-go">Publish on {place.SITE}</button><button class="btn quiet" type="button" id="sub-cancel">Cancel</button><span class="small err" role="alert" id="sub-err"></span></div>
        </div>
      </div>
      <p class="readonly" data-cant="submit" hidden>Only records senders, publishers and owners can send records. You can see what has been sent.</p>
      <div class="inbox" id="sub-inbox" hidden>{_svg('mail')}<div><b>Or email it.</b> Send the file from your work address to <code id="sub-addr"></code>. It shows up below as “Emailed in” for someone here to check and publish. Same files, same rules.</div></div>
      <p class="small muted" id="sub-tpl"></p>
      <h2 class="h2">Files sent</h2>
      <ul class="items" id="sub-list"></ul>
      <div id="sub-feeds-w" hidden>
        <h2 class="h2">Sources we already read</h2>
        <p class="small muted">We read these pages of yours automatically. Saying yes tells the public you agree they are the right place to get these records; it doesn’t change what we read. You can take it back any time.</p>
        <ul class="items" id="sub-feeds"></ul>
      </div>
    </section>

    <section id="p-records" data-panel hidden>
      {LOCK_NOTE}
      <div class="filters"><select class="sel" id="rec-pick" aria-label="Data"></select><span class="small muted" id="rec-count" style="align-self:center"></span></div>
      <div class="tw"><table class="t rec" id="rec-t"><thead></thead><tbody></tbody></table></div>
    </section>

    <section id="p-flags" data-panel hidden>
      <p class="sub">Flags you sent about record data, and our answers. A flag doesn’t change anything by itself: we check the source first.</p>
      <ul class="items" id="l-flags"></ul>
    </section>

    <section id="p-people" data-panel hidden>
      <p class="sub">Who can sign in to this workspace. Viewers see everything and change nothing. Records senders also send records (your finance or clerk contact). Publishers post notices, events and jobs and send records. Alert senders also send emergency alerts. Owners also manage this list. Auditors read everything, including the activity log.</p>
      <form id="pp-form" class="panel row" style="align-items:flex-end;margin-bottom:12px">
        <label class="f grow">Work email<input type="email" name="email" required placeholder="name@cityoflynnhaven.com"></label>
        <label class="f">Access<select name="role"><option value="viewer">Viewer</option><option value="records">Records sender</option><option value="publisher">Publisher</option><option value="alert_sender">Alert sender</option><option value="owner">Owner</option><option value="auditor">Auditor (read only)</option></select></label>
        <button class="btn primary" type="submit">Give access</button>
      </form>
      <p class="small" id="pp-msg" role="status"></p>
      <div class="tw"><table class="t" id="pp-t"><thead><tr><th>Email</th><th>Access</th><th>Added by</th><th>Since</th><th></th></tr></thead><tbody></tbody></table></div>
    </section>

    <section id="p-activity" data-panel hidden>
      <p class="sub">Every sign-in, post, alert, flag and access change in this workspace, newest first.</p>
      <div class="tw"><table class="t" id="act-t"><thead><tr><th>When</th><th>Who</th><th>What</th></tr></thead><tbody></tbody></table></div>
    </section>
    </main>
    </div>
  </div>
</div>

<dialog class="modal" id="flag-dlg" aria-labelledby="flag-h"><form method="dialog" id="flag-form">
  <h2 id="flag-h">Flag this record</h2>
  <dl class="kv" id="flag-rec"></dl>
  <label class="f">Which value is wrong<select name="field" id="flag-field"></select></label>
  <label class="f">What it should be<input name="correct_value" maxlength="500"></label>
  <label class="f">Where that comes from (link, optional)<input type="url" name="evidence_url" placeholder="https://"></label>
  <label class="f">Anything else (optional)<textarea name="note" rows="3" maxlength="2000"></textarea></label>
  <div class="row"><button class="btn primary" type="submit" value="send">Send flag</button><button class="btn quiet" type="button" id="flag-cancel">Cancel</button><span class="small err" role="alert"></span></div>
</form></dialog>
<script src="/assets/area-map.js" defer></script>
<script src="/assets/staff.js" defer></script>
</body>
</html>
'''
    os.makedirs(os.path.join(out_dir, 'staff'), exist_ok=True)
    open(os.path.join(out_dir, 'staff', 'index.html'), 'w').write(html)
    os.makedirs(os.path.join(out_dir, 'assets'), exist_ok=True)
    shutil.copy(os.path.join(os.path.dirname(__file__), 'staff.js'), os.path.join(out_dir, 'assets', 'staff.js'))


if __name__ == '__main__':
    staff_page(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public'))
