"""Realtor console (/realtor): agents sign in by emailed link, save their brokerage's look, run any address and download
a branded PDF of everything BayCounty.me has for it.

The report is GET /api/v1/address-report (api/_address_report.js), built from public datasets and live public map
lookups. Accounts, branding and report history are private (api/_realtor.js, migration 0074). The page itself is a
static shell; site/realtor.js does the rest.
"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))

CSS = r"""
.rc{--rc-r:20px}
.rc [hidden]{display:none!important}
.rc-hero{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:28px;align-items:center;margin:8px 0 28px}
.rc-hero h1{font:600 clamp(1.7rem,3.4vw,2.4rem)/1.15 var(--f-display);margin:6px 0 10px;text-wrap:balance}
.rc-hero .lede{color:var(--muted);font-size:1.02rem;line-height:1.55;margin:0}
.rc-eyebrow{display:inline-block;font-size:.72rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--salmon)}
.rc-card{background:var(--surface);border-radius:var(--rc-r);box-shadow:var(--ui-shadow);padding:22px;min-width:0}
.rc-card h2{font:600 1.15rem var(--f-display);margin:0 0 6px}
.rc-card > p{color:var(--muted);margin:0 0 14px;font-size:.92rem}
.rc-fld{display:flex;flex-direction:column;gap:6px;min-width:0}
.rc-fld > span{font-size:.8rem;font-weight:500;color:var(--muted)}
.rc input[type=text],.rc input[type=email],.rc input[type=search],.rc input[type=tel],.rc input[type=url],.rc textarea{width:100%;box-sizing:border-box;min-height:44px;padding:10px 12px;border:1px solid var(--line);border-radius:12px;background:var(--surface);color:var(--ink);font:400 .95rem var(--f-body)}
.rc textarea{min-height:84px;resize:vertical;line-height:1.45}
.rc input:focus-visible,.rc textarea:focus-visible,.rc button:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.rc-btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:0 18px;border-radius:12px;border:0;background:var(--navy);color:var(--on-navy);font:500 .92rem var(--f-body);cursor:pointer;text-decoration:none;white-space:nowrap}
.rc-btn:disabled{opacity:.6;cursor:progress}
.rc-btn.ghost{background:var(--sunken);color:var(--ink)}
.rc-btn.ghost:hover{background:color-mix(in srgb,var(--blue) 10%,var(--sunken))}
.rc-btn.sm{min-height:36px;padding:0 12px;font-size:.84rem}
.rc-row{display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap}
.rc-row > .rc-fld{flex:1 1 220px}
.rc-msg{font-size:.88rem;margin:10px 0 0;min-height:1.2em;color:var(--muted)}
.rc-msg.ok{color:var(--good,#1F7A4D)} .rc-msg.err,.rc-err{color:var(--salmon)}
.rc-what{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px;margin:0;padding:0;list-style:none}
.rc-what li{padding:12px 14px;border-radius:14px;background:var(--sunken);font-size:.88rem}
.rc-what b{display:block;font-weight:600;margin-bottom:2px}
.rc-what span{color:var(--muted);font-size:.82rem}
.rc-top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin:6px 0 16px}
.rc-top h1{font:600 1.6rem var(--f-display);margin:0}
.rc-who{display:flex;align-items:center;gap:10px;color:var(--muted);font-size:.86rem;min-width:0}
.rc-who span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:240px}
.rc-tabs{display:flex;gap:6px;margin:0 0 16px;overflow-x:auto;scrollbar-width:none}
.rc-tab{min-height:40px;padding:0 16px;border-radius:999px;border:0;background:var(--sunken);color:var(--ink);font:500 .9rem var(--f-body);cursor:pointer;white-space:nowrap}
.rc-tab[aria-selected=true]{background:var(--navy);color:var(--on-navy)}
.rc-ac{position:relative}
.rc-ac .ac-list{position:absolute;z-index:20;left:0;right:0;top:calc(100% + 4px);margin:0;padding:6px;list-style:none;background:var(--surface);border:1px solid var(--line);border-radius:14px;box-shadow:var(--ui-shadow);max-height:320px;overflow:auto}
.rc-ac .ac-list li{padding:10px 12px;border-radius:10px;cursor:pointer;display:flex;justify-content:space-between;gap:12px;font-size:.92rem}
.rc-ac .ac-list li span{color:var(--muted);font-size:.82rem;white-space:nowrap}
.rc-ac .ac-list li[aria-selected=true],.rc-ac .ac-list li[role=option]:hover{background:var(--sunken)}
.rc-ac .ac-list .ac-empty{color:var(--muted);cursor:default}
.rc-acts{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0 12px}
.rc-loading{display:flex;align-items:center;gap:12px;padding:28px;color:var(--muted)}
.rc-spin{width:18px;height:18px;border-radius:50%;border:2px solid var(--line);border-top-color:var(--blue);animation:rcspin 0.8s linear infinite}
@keyframes rcspin{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.rc-spin{animation:none}}
/* the branded report sheet: always light, like the paper it prints on */
.rc-sheet{--ink:#161B24;--muted:#5A6372;--line:#E1E6ED;--sunken:#F3F6FA;--surface:#fff;background:#fff;color:#161B24;border-radius:var(--rc-r);box-shadow:var(--ui-shadow);overflow:hidden;color-scheme:light}
.rc-sheet a{color:var(--b1)}
.rc-band{display:flex;align-items:center;gap:16px;padding:16px 20px;background:var(--b1);color:var(--b1fg,#fff)}
.rc-band-logo{flex:0 1 200px;min-width:0}
.rc-band-logo img{display:block;max-width:100%;max-height:54px;background:#fff;border-radius:6px;padding:4px 6px;box-sizing:border-box}
.rc-band-logo b{font:600 1.1rem var(--f-display)}
.rc-band-who{flex:1;display:flex;flex-direction:column;align-items:flex-end;text-align:right;font-size:.8rem;line-height:1.35;min-width:0}
.rc-band-who b{font-size:1rem}
.rc-band-who span{overflow-wrap:anywhere}
.rc-band-photo{width:56px;height:56px;border-radius:10px;object-fit:cover;flex:none}
.rc-title{padding:20px 22px 4px;border-top:3px solid var(--b2)}
.rc-title .rc-eyebrow{color:var(--b2)}
.rc-title h2{font:600 1.7rem/1.2 var(--f-display);margin:2px 0 4px}
.rc-title p{margin:0;color:var(--muted);font-size:.9rem}
.rc-title .rc-meta{font-size:.84rem;margin-top:4px}
.rc-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;padding:14px 22px 4px}
.rc-tiles div{background:var(--sunken);border-top:2px solid var(--b2);border-radius:10px;padding:10px 12px;min-width:0}
.rc-tiles span{display:block;font-size:.68rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.rc-tiles b{display:block;font:600 1.3rem var(--f-body);margin:2px 0 0;font-variant-numeric:tabular-nums}
.rc-tiles small{font-size:.74rem;color:var(--muted)}
.rc-secs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));grid-auto-flow:row dense;gap:0 28px;padding:6px 22px 8px}
.rc-sec{padding:16px 0 4px;min-width:0;break-inside:avoid}
.rc-sec.wide{grid-column:1/-1}
.rc-sec h3{font:600 1.02rem var(--f-display);color:var(--b1);margin:0 0 8px;padding-bottom:6px;border-bottom:1.5px solid var(--b2)}
.rc-sec h4{font-size:.82rem;font-weight:600;color:var(--b1);margin:12px 0 6px}
.rc-kv{display:grid;grid-template-columns:minmax(110px,38%) minmax(0,1fr);margin:0;font-size:.88rem}
.rc-kv dt,.rc-kv dd{padding:6px 0;border-bottom:1px solid var(--line);margin:0}
.rc-kv dt{color:var(--muted);padding-right:10px}
.rc-kv dd.b{font-weight:600}
.rc-kv dd .muted{color:var(--muted)}
.rc-tw{overflow-x:auto;margin-top:10px}
.rc-tb{width:100%;border-collapse:collapse;font-size:.84rem;font-variant-numeric:tabular-nums}
.rc-tb th{font-weight:600;color:var(--muted);border-bottom:1px solid var(--muted);padding:5px 6px 5px 0;white-space:nowrap}
.rc-tb td{padding:5px 6px 5px 0;border-bottom:1px solid var(--line)}
.rc-tb .right{text-align:right;white-space:nowrap} .rc-tb .left{text-align:left}
.rc-list{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.rc-list.two{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 16px}
.rc-list li{font-size:.88rem;min-width:0}
.rc-list b{display:block;font-weight:600}
.rc-list small{display:block;color:var(--muted);font-size:.78rem;margin-top:1px}
.rc-note{font-size:.78rem;color:var(--muted);font-style:italic;margin:8px 0 0}
.rc-src{font-size:.78rem;margin:6px 0 0;display:flex;flex-wrap:wrap;gap:4px 12px}
.rc-soon{margin:8px 22px 0;padding:10px 12px;border-radius:10px;background:var(--sunken);font-size:.82rem;color:var(--muted)}
.rc-soon.err{color:#9b2c22}
.rc-disc{padding:14px 22px 20px;font-size:.74rem;color:var(--muted);line-height:1.5}
.rc-disc p{margin:8px 0 0}
/* branding */
.rc-brand{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:18px;align-items:start}
.rc-grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.rc-grid2 .span{grid-column:1/-1}
.rc-imgs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:12px}
.rc-img{display:flex;flex-direction:column;gap:8px;padding:12px;border:1px dashed var(--line);border-radius:14px;min-width:0}
.rc-img .prev{height:64px;display:flex;align-items:center;justify-content:center;background:var(--sunken);border-radius:10px;overflow:hidden;color:var(--muted);font-size:.82rem}
.rc-img .prev img{max-height:56px;max-width:100%}
.rc-img input[type=file]{font-size:.82rem;max-width:100%}
.rc-colors{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-top:12px}
.rc-colors label{display:flex;align-items:center;gap:8px;font-size:.86rem}
.rc-colors input[type=color]{width:44px;height:36px;border:1px solid var(--line);border-radius:8px;padding:2px;background:var(--surface)}
.rc-sticky{position:sticky;top:76px}
.rc-prev{border-radius:16px;overflow:hidden;box-shadow:var(--ui-shadow);background:#fff;color:#161B24}
.rc-prev-body{padding:14px 18px 18px;display:flex;flex-direction:column;gap:2px;border-top:3px solid var(--b2,#e5564a)}
.rc-prev-body .rc-eyebrow{color:var(--b2,#e5564a)}
.rc-prev-body b{font:600 1.2rem var(--f-display)} .rc-prev-body small{color:#5A6372} .rc-prev-body em{color:#5A6372;font-size:.86rem;margin-top:6px}
.rc-hist{list-style:none;margin:0;padding:0}
.rc-hist li{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid var(--line)}
.rc-hist li > div{min-width:0}
.rc-hist b{display:block;font-weight:600}
.rc-hist small{color:var(--muted);font-size:.8rem}
.rc-hacts{display:flex;gap:6px;flex:none}
.rc-danger{margin-top:22px;padding-top:16px;border-top:1px solid var(--line);font-size:.86rem;color:var(--muted)}
.rc-danger .rc-btn{background:color-mix(in srgb,var(--salmon) 14%,transparent);color:var(--salmon)}
@media (max-width:860px){.rc-hero,.rc-brand{grid-template-columns:1fr}.rc-sticky{position:static}}
@media (max-width:640px){
  .rc-secs{grid-template-columns:1fr;padding:4px 16px 8px}
  .rc-title,.rc-tiles{padding-left:16px;padding-right:16px}
  .rc-tiles{grid-template-columns:repeat(2,minmax(0,1fr))}
  .rc-band{flex-wrap:wrap;padding:14px 16px}.rc-band-who{align-items:flex-start;text-align:left;flex-basis:100%;order:3}
  .rc-grid2,.rc-imgs{grid-template-columns:1fr}
  .rc-list.two{grid-template-columns:1fr}
  .rc-title h2{font-size:1.4rem}
  .rc-hist li{flex-direction:column;align-items:flex-start}
}
@media print{
  header.site,footer.site,.rc-top,.rc-tabs,.rc-card.rc-runbox,.rc-acts,.crumbs,nav{display:none!important}
  .rc-sheet{box-shadow:none;border-radius:0}
  .rc-band,.rc-tiles div{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}
"""

WHAT = [
    ('The property', 'Use, size, year built, values and sales since 2016'),
    ('Tax estimate', 'Every taxing authority, the millage and flat fees'),
    ('Flood and storms', 'FEMA flood zone, panel, evacuation zone'),
    ('Schools', 'Elementary, middle and high school zones'),
    ('Utilities and trash day', 'Providers, pickup days and rates'),
    ('Zoning and development', 'Zoning, land use and projects nearby'),
    ('Roads and projects', 'Sales tax and road work within a mile'),
    ('Parks and beaches', 'The closest parks and beach accesses'),
    ('Who represents it', 'Commission, city, school board, state and U.S.'),
    ('Coming up', 'Public meetings and community events'),
]


def realtor_page(out_dir):
    shutil.copy(os.path.join(HERE, 'realtor.js'), os.path.join(out_dir, 'assets', 'realtor.js'))
    what = ''.join(f'<li><b>{t}</b><span>{d}</span></li>' for t, d in WHAT)
    return f'''<style>{CSS}</style>
<div class="page rc">
  <section id="rcOut" hidden>
    <div class="rc-hero">
      <div>
        <span class="rc-eyebrow">For real estate agents</span>
        <h1>Every public record for an address, in your brand</h1>
        <p class="lede">Type any Bay County address and get one report with the property, a tax estimate, flood and evacuation zones, schools, utilities, zoning and projects nearby, parks and who represents it. Download it as a PDF with your logo, colors and contact details.</p>
      </div>
      <form class="rc-card" id="signForm">
        <h2>Sign in</h2>
        <p>We email you a link. No password to remember.</p>
        <label class="rc-fld"><span>Work email</span><input id="email" type="email" required maxlength="200" autocomplete="email" placeholder="you@brokerage.com"></label>
        <div class="rc-acts" style="margin-bottom:0"><button class="rc-btn" id="signBtn" type="submit">Email me a sign-in link</button></div>
        <p class="rc-msg" id="signMsg" role="status"></p>
      </form>
    </div>
    <h2 class="rc-h2">What's in a report</h2>
    <ul class="rc-what">{what}</ul>
    <p class="muted small" style="margin-top:16px">Reports come from public records: the county's map server, FEMA, the Florida Department of Revenue and the datasets on this site. Owner names and private details are never included. Your branding and report history are kept private to your account; you can delete them any time.</p>
  </section>

  <section id="rcIn" hidden>
    <div class="rc-top"><h1>Realtor console</h1><div class="rc-who"><span id="who"></span><button type="button" class="rc-btn ghost sm" id="signOut">Sign out</button></div></div>
    <div class="rc-tabs" role="tablist">
      <button type="button" class="rc-tab" role="tab" data-tab="run" aria-selected="true">Run a report</button>
      <button type="button" class="rc-tab" role="tab" data-tab="brand" aria-selected="false">Your branding</button>
      <button type="button" class="rc-tab" role="tab" data-tab="hist" aria-selected="false">History</button>
    </div>

    <div class="rc-panel" id="p-run">
      <form class="rc-card rc-runbox" id="runForm" role="search">
        <div class="rc-row">
          <label class="rc-fld" style="flex:2 1 300px"><span>Bay County address</span>
            <div class="rc-ac"><input id="q" type="search" autocomplete="off" spellcheck="false" placeholder="e.g. 825 Ohio Ave" aria-autocomplete="list" aria-controls="acList"><ul id="acList" class="ac-list" role="listbox" hidden></ul></div></label>
          <label class="rc-fld"><span>Prepared for (optional)</span><input id="prepFor" type="text" maxlength="120" placeholder="Client name"></label>
          <label class="rc-fld"><span>Cover photo for the PDF (optional)</span><input id="coverPhoto" type="file" accept="image/png,image/jpeg,image/webp"></label>
          <button class="rc-btn" id="runBtn" type="submit">Run report</button>
        </div>
        <p class="muted small" id="coverNote">Your listing photo of the house goes across the top of the PDF. It stays in this browser and is never uploaded.</p>
        <p class="rc-err small" id="runErr" role="alert" hidden></p>
      </form>
      <div class="rc-acts" id="reportActs" hidden>
        <button type="button" class="rc-btn" id="pdfBtn"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Download branded PDF</button>
        <button type="button" class="rc-btn ghost" id="printBtn">Print</button>
      </div>
      <div id="report" aria-live="polite"></div>
    </div>

    <div class="rc-panel" id="p-brand" hidden>
      <div class="rc-brand">
        <form class="rc-card" id="brandForm">
          <h2>Your branding</h2>
          <p>This goes on the top of every report and in the PDF's footer.</p>
          <div class="rc-grid2">
            <label class="rc-fld"><span>Your name</span><input id="b_agent_name" type="text" maxlength="120" autocomplete="name"></label>
            <label class="rc-fld"><span>Title</span><input id="b_title" type="text" maxlength="120" placeholder="Realtor®, Broker Associate"></label>
            <label class="rc-fld"><span>Brokerage</span><input id="b_brokerage" type="text" maxlength="160" autocomplete="organization"></label>
            <label class="rc-fld"><span>License number</span><input id="b_license_no" type="text" maxlength="60"></label>
            <label class="rc-fld"><span>Phone</span><input id="b_phone" type="tel" maxlength="40" autocomplete="tel"></label>
            <label class="rc-fld"><span>Email on reports</span><input id="b_email" type="email" maxlength="200" autocomplete="email"></label>
            <label class="rc-fld"><span>Website</span><input id="b_website" type="text" maxlength="200" placeholder="yourbrokerage.com"></label>
            <label class="rc-fld"><span>Office address</span><input id="b_office_address" type="text" maxlength="200"></label>
            <label class="rc-fld span"><span>Tagline (optional)</span><input id="b_tagline" type="text" maxlength="160"></label>
            <label class="rc-fld span"><span>Your disclaimer (optional, printed at the end)</span><textarea id="b_disclaimer" maxlength="1200"></textarea></label>
          </div>
          <div class="rc-imgs">
            <div class="rc-img"><b class="small">Logo</b><div class="prev" id="prev_logo"></div><input id="f_logo" type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" aria-label="Upload logo"><button type="button" class="rc-btn ghost sm" id="rm_logo">Remove logo</button></div>
            <div class="rc-img"><b class="small">Headshot</b><div class="prev" id="prev_photo"></div><input id="f_photo" type="file" accept="image/png,image/jpeg,image/webp" aria-label="Upload headshot"><button type="button" class="rc-btn ghost sm" id="rm_photo">Remove photo</button></div>
          </div>
          <div class="rc-colors">
            <label><input id="b_color_primary" type="color" value="#1e3a76"> Brand color</label>
            <label><input id="b_color_accent" type="color" value="#e5564a"> Accent</label>
            <button type="button" class="rc-btn ghost sm" id="resetColors">Reset colors</button>
          </div>
          <div class="rc-acts"><button class="rc-btn" id="brandBtn" type="submit">Save branding</button></div>
          <p class="rc-msg" id="brandMsg" role="status"></p>
        </form>
        <div class="rc-sticky"><p class="muted small" style="margin:0 0 8px">Preview</p><div class="rc-prev" id="brandPrev"></div></div>
      </div>
    </div>

    <div class="rc-panel rc-card" id="p-hist" hidden>
      <h2>Reports you've run</h2>
      <p id="histCount"></p>
      <ul class="rc-hist" id="histList"></ul>
      <div class="rc-danger"><p>Delete your account, branding and history. This can't be undone.</p><button type="button" class="rc-btn sm" id="delAcct">Delete my account</button></div>
    </div>
  </section>
</div>
<script src="/assets/realtor.js" defer></script>'''
