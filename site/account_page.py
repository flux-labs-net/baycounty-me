"""My home (/account): a resident signs in with a code sent to their email, saves their home address and sees what's
happening around it: alerts that reach the home, trash day, meetings, things to do, building and road work nearby,
public notices, restaurant inspections and new businesses in their ZIP. They pick what they hear about by email and
on their phone.

What the page shows is GET /api/v1/nearby (api/_nearby.js) for the saved home, through /api/account?action=feed.
The account, the home address and the choices are private (api/_account.js, migration 0077). The page is a static
shell; site/account.js does the rest.
"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))

CSS = r"""
.mh{--mh-r:20px}
.mh [hidden]{display:none!important}
.mh-hero{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:32px;align-items:center;margin:10px 0 30px}
.mh-hero h1{font:700 clamp(1.8rem,3.6vw,2.6rem)/1.1 var(--f-display);letter-spacing:-.03em;margin:6px 0 12px;text-wrap:balance}
.mh-hero .lede{color:var(--muted);font-size:1.04rem;line-height:1.55;margin:0}
.mh-eyebrow{display:inline-block;font-size:.72rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--salmon)}
.mh-card{background:var(--surface);border-radius:var(--mh-r);box-shadow:var(--ui-shadow);padding:22px;min-width:0}
.mh-card h2{font:600 1.15rem var(--f-display);margin:0 0 6px}
.mh-card > p{color:var(--muted);margin:0 0 14px;font-size:.92rem}
.mh-fld{display:flex;flex-direction:column;gap:6px;min-width:0}
.mh-fld > span{font-size:.8rem;font-weight:500;color:var(--muted)}
.mh input[type=text],.mh input[type=email],.mh input[type=search],.mh select{width:100%;box-sizing:border-box;min-height:46px;padding:10px 12px;border:1px solid var(--line);border-radius:12px;background:var(--surface);color:var(--ink);font:400 1rem var(--f-body)}
.mh input.code{font:600 1.5rem var(--f-data,monospace);letter-spacing:.4em;text-align:center}
.mh input:focus-visible,.mh select:focus-visible,.mh button:focus-visible,.mh a:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.mh-btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:46px;padding:0 20px;border-radius:12px;border:0;background:var(--navy);color:var(--on-navy);font:500 .95rem var(--f-body);cursor:pointer;text-decoration:none;white-space:nowrap}
.mh-btn:disabled{opacity:.6;cursor:progress}
.mh-btn.ghost{background:var(--sunken);color:var(--ink)}
.mh-btn.link{background:none;color:var(--blue);padding:0 4px;min-height:36px}
.mh-btn.sm{min-height:36px;padding:0 14px;font-size:.86rem}
.mh-btn.danger{background:var(--salmon);color:#fff}
.mh-stack{display:grid;gap:12px}
.mh-row{display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap}
.mh-row > .mh-fld{flex:1 1 220px}
.mh-msg{font-size:.88rem;margin:0;min-height:1.2em;color:var(--muted)}
.mh-msg.ok{color:var(--good,#1F7A4D)} .mh-msg.err{color:var(--salmon)}
.mh-what{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin:0;padding:0;list-style:none}
.mh-what li{display:flex;gap:12px;align-items:flex-start;padding:16px;border-radius:16px;background:var(--surface);box-shadow:var(--ui-shadow);font-size:.9rem}
.mh-what b{display:block;font-weight:600;margin-bottom:2px}
.mh-what span.d{color:var(--muted);font-size:.84rem;line-height:1.45}
.mh-fine{color:var(--muted);font-size:.82rem;margin:18px 0 0}
/* signed in */
.mh-top{display:flex;justify-content:space-between;align-items:flex-end;gap:14px;flex-wrap:wrap;margin:8px 0 18px}
.mh-top h1{font:700 clamp(1.5rem,3vw,2.1rem)/1.15 var(--f-display);letter-spacing:-.02em;margin:4px 0 6px}
.mh-addr{display:flex;flex-wrap:wrap;gap:6px;align-items:center;color:var(--muted);font-size:.92rem}
.mh-chip{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;background:var(--sunken);color:var(--ink);font-size:.8rem;font-weight:500;white-space:nowrap}
.mh-chip.zone{background:var(--tint-amber);color:color-mix(in srgb,var(--gold) 70%,var(--ink))}
.mh-tabs{display:flex;gap:6px}
.mh-tab{min-height:40px;padding:0 16px;border-radius:999px;border:0;background:var(--sunken);color:var(--ink);font:500 .9rem var(--f-body);cursor:pointer;white-space:nowrap}
.mh-tab[aria-selected=true]{background:var(--navy);color:var(--on-navy)}
.mh-today{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:0 0 18px}
.mh-t{display:flex;gap:12px;align-items:flex-start;background:var(--surface);border-radius:16px;box-shadow:var(--ui-shadow);padding:16px;min-width:0;text-decoration:none;color:inherit}
.mh-t .k{display:block;font-size:.72rem;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);font-weight:600}
.mh-t b{display:block;font:600 1.05rem/1.3 var(--f-display);margin:2px 0 1px}
.mh-t small{display:block;color:var(--muted);font-size:.8rem;line-height:1.4}
.mh-t.warn{box-shadow:inset 0 0 0 2px var(--salmon),var(--ui-shadow)}
.mh-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;align-items:start}
.mh-sec{background:var(--surface);border-radius:var(--mh-r);box-shadow:var(--ui-shadow);padding:18px 18px 8px;min-width:0}
.mh-sec.wide{grid-column:1/-1}
.mh-sec h2{display:flex;align-items:center;gap:10px;font:600 1.05rem var(--f-display);margin:0 0 6px}
.mh-sec h2 .n{margin-left:auto;font:500 .78rem var(--f-body);color:var(--muted)}
.mh-items{list-style:none;margin:0;padding:0}
.mh-items li{display:flex;gap:12px;padding:11px 0;border-top:1px solid var(--line);min-width:0}
.mh-items li:first-child{border-top:0}
.mh-when{flex:none;width:46px;text-align:center;border-radius:10px;background:var(--sunken);padding:5px 0 6px;line-height:1.05}
.mh-when span{display:block;font-size:.64rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--salmon)}
.mh-when b{display:block;font:600 1.15rem var(--f-display)}
.mh-when.mi b{font-size:.92rem;padding-top:2px}
.mh-when.mi span{color:var(--muted)}
.mh-it{min-width:0;flex:1}
.mh-it a.t,.mh-it b.t{display:block;font-weight:600;font-size:.93rem;line-height:1.35;color:var(--ink);text-decoration:none;overflow-wrap:anywhere}
.mh-it a.t:hover{color:var(--blue);text-decoration:underline}
.mh-it small{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;color:var(--muted);font-size:.8rem;line-height:1.4;margin-top:2px;overflow-wrap:anywhere}
.mh-it .tag{display:inline-block;margin-right:6px;padding:1px 7px;border-radius:999px;font-size:.7rem;font-weight:600;background:var(--sunken);color:var(--muted)}
.mh-it .tag.closed,.mh-it .tag.evacuation{background:var(--tint-salmon,#fff1ee);color:var(--salmon)}
.mh-it .tag.warning,.mh-it .tag.weather{background:var(--tint-amber);color:color-mix(in srgb,var(--gold) 70%,var(--ink))}
.mh-empty{color:var(--muted);font-size:.88rem;padding:6px 0 12px;margin:0}
.mh-govs{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0 0}
.mh-loading{display:flex;align-items:center;gap:12px;padding:32px 4px;color:var(--muted)}
.mh-spin{width:18px;height:18px;border-radius:50%;border:2px solid var(--line);border-top-color:var(--blue);animation:mhspin .8s linear infinite}
@keyframes mhspin{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.mh-spin{animation:none}}
.mh-ac{position:relative}
.mh-ac .ac-list{position:absolute;z-index:20;left:0;right:0;top:calc(100% + 4px);margin:0;padding:6px;list-style:none;background:var(--surface);border:1px solid var(--line);border-radius:14px;box-shadow:var(--ui-shadow);max-height:320px;overflow:auto}
.mh-ac .ac-list li{padding:10px 12px;border-radius:10px;cursor:pointer;display:flex;justify-content:space-between;gap:12px;font-size:.92rem}
.mh-ac .ac-list li span{color:var(--muted);font-size:.82rem;white-space:nowrap}
.mh-ac .ac-list li[aria-selected=true],.mh-ac .ac-list li[role=option]:hover{background:var(--sunken)}
.mh-ac .ac-list .ac-empty{color:var(--muted);cursor:default}
/* settings */
.mh-set{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;align-items:start}
.mh-set .mh-card h2{display:flex;align-items:center;gap:10px}
.mh-checks{display:grid;gap:4px;margin:4px 0 14px}
.mh-checks label{display:flex;gap:10px;align-items:flex-start;padding:8px 0;font-size:.92rem;cursor:pointer}
.mh-checks input{width:18px;height:18px;margin:2px 0 0;accent-color:var(--navy);flex:none}
.mh-checks small{display:block;color:var(--muted);font-size:.8rem}
.mh-apps{display:flex;gap:8px;flex-wrap:wrap}
.mh-danger{border-top:1px solid var(--line);margin-top:6px;padding-top:14px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.mh-danger p{margin:0;color:var(--muted);font-size:.86rem}
@media (max-width:860px){
  .mh-hero{grid-template-columns:1fr;gap:20px}
  .mh-grid,.mh-set{grid-template-columns:1fr}
}
@media (max-width:520px){
  .mh-card,.mh-sec{padding:16px}
  .mh-top{align-items:flex-start}
  .mh-tabs{width:100%}
  .mh-tab{flex:1}
  .mh-today{grid-template-columns:1fr 1fr;gap:10px}
  .mh-t{padding:12px;gap:10px}
  .mh-t .ui-ti{display:none}
}
"""

WHAT = [
    ('bell', 'salmon', 'Alerts for your home', 'Evacuation orders for your zone, boil-water notices for your city and weather warnings, on My home and by email or phone if you want.'),
    ('calendar', 'blue', 'Meetings and things to do', 'Your county, city and school board meetings with agendas, and events around town, your town first.'),
    ('crane', 'amber', 'What’s being built nearby', 'Development, road work, sales tax projects and agenda items within the distance you pick.'),
    ('mail', 'teal', 'One email on Mondays', 'Your week near home in one short email. Turn it off any time.'),
]


def account_page(out_dir):
    from ui import ico
    shutil.copy(os.path.join(HERE, 'account.js'), os.path.join(out_dir, 'assets', 'account.js'))
    what = ''.join(f'<li>{ico(i, t)}<div><b>{h}</b><span class="d">{d}</span></div></li>' for i, t, h, d in WHAT)
    return f'''<style>{CSS}</style>
<div class="page mh">
  <p class="mh-loading" id="mhWait"><span class="mh-spin" aria-hidden="true"></span>Loading…</p>

  <section id="mhOut" hidden>
    <div class="mh-hero">
      <div>
        <span class="mh-eyebrow">My home</span>
        <h1>What’s happening around your home</h1>
        <p class="lede">Save your address once. BayCounty.me shows you the alerts, meetings, events and work going on near you, and tells you about the ones you care about by email or on your phone.</p>
      </div>
      <form class="mh-card" id="startForm" novalidate>
        <h2>Sign in or create an account</h2>
        <p>We’ll email you a 6-digit code. No password to remember.</p>
        <div class="mh-stack" id="stepEmail">
          <label class="mh-fld"><span>Email</span><input id="email" type="email" required maxlength="200" autocomplete="email" inputmode="email" placeholder="you@example.com"></label>
          <button class="mh-btn" id="startBtn" type="submit">Email me a code</button>
        </div>
        <div class="mh-stack" id="stepCode" hidden>
          <label class="mh-fld"><span id="codeLbl">Code from the email</span><input id="code" class="code" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]*" placeholder="000000"></label>
          <button class="mh-btn" id="verifyBtn" type="button">Sign in</button>
          <button class="mh-btn link" id="backBtn" type="button">Use a different email</button>
        </div>
        <p class="mh-msg" id="startMsg" role="status" aria-live="polite"></p>
      </form>
    </div>
    <ul class="mh-what">{what}</ul>
    <p class="mh-fine">Your home address is only shown to you and never published. You can delete your account and everything in it at any time. See <a href="/privacy">Privacy</a>.</p>
  </section>

  <section id="mhIn" hidden>
    <div class="mh-top">
      <div>
        <span class="mh-eyebrow" id="hello">My home</span>
        <h1 id="homeTitle">Your home</h1>
        <div class="mh-addr" id="homeAddr"></div>
      </div>
      <div class="mh-tabs" role="tablist" id="tabs">
        <button class="mh-tab" role="tab" aria-selected="true" aria-controls="pFeed" id="tFeed" type="button">My home</button>
        <button class="mh-tab" role="tab" aria-selected="false" aria-controls="pSet" id="tSet" type="button">Settings</button>
      </div>
    </div>

    <form class="mh-card" id="homeForm" hidden novalidate>
      <h2 id="homeFormH">Where’s home?</h2>
      <p>Type your street address in Bay County. We use it to find what’s near you; it’s never shown to anyone else.</p>
      <div class="mh-row">
        <label class="mh-fld" style="flex:2 1 300px"><span>Street address</span>
          <div class="mh-ac"><input id="q" type="search" autocomplete="off" spellcheck="false" placeholder="e.g. 825 Ohio Ave" aria-autocomplete="list" aria-controls="acList"><ul id="acList" class="ac-list" role="listbox" hidden></ul></div></label>
        <button class="mh-btn" id="homeBtn" type="submit">Save my home</button>
        <button class="mh-btn ghost" id="homeCancel" type="button" hidden>Cancel</button>
      </div>
      <p class="mh-msg" id="homeMsg" role="status" aria-live="polite"></p>
    </form>

    <div role="tabpanel" id="pFeed" aria-labelledby="tFeed">
      <div id="feed" aria-live="polite"></div>
    </div>

    <div role="tabpanel" id="pSet" aria-labelledby="tSet" hidden>
      <div class="mh-set">
        <div class="mh-card">
          <h2>{ico('home', 'blue')}Your home</h2>
          <p id="setHome">No home saved yet.</p>
          <div class="mh-row"><button class="mh-btn ghost sm" id="changeHome" type="button">Change address</button><button class="mh-btn link" id="removeHome" type="button">Remove</button></div>
          <label class="mh-fld" style="margin-top:14px"><span>Your first name (for greetings, optional)</span><input id="firstName" type="text" maxlength="60" autocomplete="given-name"></label>
          <label class="mh-fld" style="margin-top:12px"><span>How far is “near my home”</span>
            <select id="radius"><option value="0.25">A quarter mile</option><option value="0.5">Half a mile</option><option value="1">1 mile</option><option value="2">2 miles</option><option value="5">5 miles</option></select></label>
        </div>
        <div class="mh-card">
          <h2>{ico('mail', 'teal')}Emails</h2>
          <div class="mh-checks">
            <label><input type="checkbox" id="weekly"><span>Monday email about my home<small>Meetings, events and what’s new near you this week</small></span></label>
          </div>
          <p class="mh-fine" style="margin:0 0 4px">Email me right away when one of these affects my home:</p>
          <div class="mh-checks" id="alertEmail"></div>
        </div>
        <div class="mh-card">
          <h2>{ico('grid', 'amber')}Show on My home</h2>
          <div class="mh-checks" id="topics"></div>
        </div>
        <div class="mh-card">
          <h2>{ico('bell', 'salmon')}Phone notifications</h2>
          <p>Sign in to the BayCounty.me app with the same email. Your phone then follows your home: evacuation orders for your zone, boil-water notices, weather warnings and agenda items near you.</p>
          <div class="mh-checks" id="pushTopics"></div>
          <p class="mh-fine" id="devices" style="margin:0"></p>
          <div class="mh-row" id="testRow" hidden><button class="mh-btn ghost sm" id="testPush" type="button">Send a test alert to my phones</button><p class="mh-msg" id="testMsg" role="status" aria-live="polite"></p></div>
        </div>
        <div class="mh-card" style="grid-column:1/-1">
          <div class="mh-row" style="justify-content:space-between;align-items:center"><p class="mh-msg" id="setMsg" role="status" aria-live="polite"></p>
            <div class="mh-row"><button class="mh-btn" id="saveSet" type="button">Save settings</button><button class="mh-btn ghost" id="signOut" type="button">Sign out</button></div></div>
          <div class="mh-danger"><p>Signed in as <b id="who"></b>. Deleting your account removes your home, choices and sign-ins. It can’t be undone.</p><button type="button" class="mh-btn danger sm" id="delAcct">Delete my account</button></div>
        </div>
      </div>
    </div>
  </section>
</div>
<script src="/assets/account.js" defer></script>'''
