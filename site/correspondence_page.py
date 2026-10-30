"""Correspondence (/correspondence): every email between BayCounty.me and officials or governments, in a read-only
mail viewer: folders, a list, and each conversation start to finish.

The page holds no data. assets/correspondence.js reads /api/v1/mail (the list) and /api/v1/mail/{id} (one
conversation), which hide residents' email addresses, phone numbers and street addresses. Officials and government
staff are named. Sign-in codes and links are never part of it.
"""
import json, os
from city_filter import city_bar, gkey, KEYS

HERE = os.path.dirname(os.path.abspath(__file__))

CSS = r"""
.mv-app{display:grid;grid-template-columns:190px minmax(260px,360px) 1fr;border:1px solid var(--line);border-radius:14px;background:var(--surface);overflow:hidden;min-height:620px;margin-top:12px}
.mv-side{border-right:1px solid var(--line);padding:12px 8px;display:flex;flex-direction:column;gap:2px;background:var(--sunken)}
.mv-f{display:flex;align-items:center;gap:8px;width:100%;border:0;background:none;font:inherit;font-size:.9rem;color:var(--ink);padding:8px 10px;border-radius:8px;cursor:pointer;text-align:left}
.mv-f:hover{background:var(--surface)}.mv-f[aria-current="true"]{background:var(--surface);font-weight:600;box-shadow:inset 3px 0 0 var(--blue)}
.mv-f span{flex:1}.mv-f i{font-style:normal;font-size:.78rem;color:var(--muted);font-variant-numeric:tabular-nums}
.mv-side select{margin:10px 4px 0;font:inherit;font-size:.86rem;padding:6px 8px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink)}
.mv-list{border-right:1px solid var(--line);display:flex;flex-direction:column;min-width:0}
.mv-search{padding:10px;border-bottom:1px solid var(--line)}
.mv-search input{width:100%;box-sizing:border-box;font:inherit;font-size:.9rem;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink)}
.mv-items{list-style:none;margin:0;padding:0;overflow:auto;flex:1;max-height:760px}
.mv-it{display:block;width:100%;text-align:left;border:0;border-bottom:1px solid var(--line);background:none;font:inherit;color:var(--ink);padding:11px 14px;cursor:pointer}
.mv-it:hover{background:var(--sunken)}.mv-it[aria-current="true"]{background:var(--sunken);box-shadow:inset 3px 0 0 var(--blue)}
.mv-it .r1{display:flex;gap:8px;align-items:baseline}.mv-it .who{flex:1;font-weight:600;font-size:.9rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mv-it time{font-size:.76rem;color:var(--muted);white-space:nowrap}
.mv-it .sub{font-size:.88rem;margin:2px 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mv-it .snip{font-size:.8rem;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.mv-it .tags{display:flex;gap:6px;margin-top:5px;flex-wrap:wrap}
.mv-tag{font-size:.7rem;border:1px solid var(--line);border-radius:999px;padding:0 7px;color:var(--muted);white-space:nowrap}
.mv-tag.ok{color:var(--green,#1F7A4D);border-color:currentColor}.mv-tag.warn{color:#9a5b00;border-color:currentColor}
.mv-pager{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;border-top:1px solid var(--line);font-size:.82rem;color:var(--muted)}
.mv-pager button,.mv-tb button,.mv-tb a{font:inherit;font-size:.84rem;border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:8px;padding:5px 10px;cursor:pointer;text-decoration:none}
.mv-pager button:disabled,.mv-tb button:disabled{opacity:.4;cursor:default}
.mv-read{min-width:0;display:flex;flex-direction:column}
.mv-empty{margin:auto;text-align:center;color:var(--muted);padding:40px 20px;font-size:.92rem}
.mv-tb{display:flex;gap:6px;align-items:center;padding:10px 14px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.mv-tb .grow{flex:1}.mv-back{display:none}
.mv-hd{padding:16px 20px 6px}.mv-hd h2{font:600 1.2rem var(--f-display);margin:0 0 6px;line-height:1.3}
.mv-hd .meta{font-size:.84rem;color:var(--muted);display:flex;gap:6px 12px;flex-wrap:wrap}
.mv-body{padding:6px 20px 24px;overflow:auto;max-height:760px}
.mv-m{border:1px solid var(--line);border-radius:12px;margin:10px 0;background:var(--surface)}
.mv-mh{display:flex;gap:10px;align-items:flex-start;padding:12px 14px;cursor:pointer;border:0;background:none;width:100%;text-align:left;font:inherit;color:var(--ink)}
.mv-av{width:34px;height:34px;border-radius:50%;flex:none;display:grid;place-items:center;font-size:.8rem;font-weight:600;color:#fff;background:#5b6876}
.mv-av.us{background:var(--blue)}
.mv-who{flex:1;min-width:0}.mv-who b{font-weight:600;font-size:.92rem}.mv-who .ad{font-size:.8rem;color:var(--muted)}
.mv-who .to{font-size:.8rem;color:var(--muted);margin-top:1px}
.mv-who .pv{font-size:.84rem;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:2px}
.mv-mh time{font-size:.78rem;color:var(--muted);white-space:nowrap;text-align:right}
.mv-mb{padding:0 14px 14px 58px}
.mv-text{white-space:pre-wrap;line-height:1.55;font-size:.94rem;word-break:break-word;margin:0}
.mv-note{font-size:.88rem;color:var(--muted);font-style:italic;margin:0}
.mv-q{margin-top:10px}.mv-q summary,.mv-dt summary{font-size:.8rem;color:var(--muted);cursor:pointer}
.mv-q pre{white-space:pre-wrap;font:inherit;font-size:.86rem;color:var(--muted);border-left:3px solid var(--line);padding-left:10px;margin:8px 0 0}
.mv-att{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.mv-att span{display:inline-flex;flex-direction:column;border:1px solid var(--line);border-radius:10px;padding:6px 10px;font-size:.8rem;max-width:100%}
.mv-att b{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mv-att small{color:var(--muted)}
.mv-mono{font-family:ui-monospace,Menlo,monospace;font-size:.74rem;word-break:break-all}
.mv-dt{margin-top:10px}.mv-dt dl{display:grid;grid-template-columns:max-content 1fr;gap:3px 12px;font-size:.78rem;margin:8px 0 0}.mv-dt dt{color:var(--muted)}.mv-dt dd{margin:0}
.mv-ev{display:flex;gap:10px;align-items:baseline;font-size:.84rem;color:var(--muted);margin:8px 0 8px 14px;padding-left:14px;border-left:2px solid var(--line)}
.mv-ev b{color:var(--ink);font-weight:500}
.mv-hidden{margin:20px;padding:16px;border:1px dashed var(--line);border-radius:12px;font-size:.92rem}
@media (max-width:980px){.mv-app{grid-template-columns:minmax(240px,320px) 1fr}.mv-side{grid-column:1/-1;flex-direction:row;flex-wrap:wrap;border-right:0;border-bottom:1px solid var(--line);padding:8px}
  .mv-f{width:auto}.mv-side select{margin:0 0 0 auto}}
@media (max-width:680px){.mv-app{grid-template-columns:1fr;min-height:0}.mv-list{border-right:0}.mv-read{display:none}
  .mv-app.reading .mv-list,.mv-app.reading .mv-side{display:none}.mv-app.reading .mv-read{display:flex}.mv-back{display:inline-block}
  .mv-mb{padding:0 14px 14px}.mv-body{padding:4px 12px 18px;max-height:none}.mv-hd{padding:14px 14px 4px}.mv-items{max-height:none}
  .mv-side{overflow-x:auto;flex-wrap:nowrap}.mv-f{white-space:nowrap}
  .mv-mh{flex-wrap:wrap}.mv-mh time{order:-1;width:100%;text-align:left;padding-left:44px}.mv-mh time br{display:none}.mv-mh time .mv-tag{margin-left:6px}
  .mv-ev{flex-direction:column;gap:2px}}
@media print{.mv-side,.mv-list,.mv-tb,.city-bar,.tx-top,.method{display:none!important}.mv-app{display:block;border:0}.mv-read{display:block!important}.mv-body{max-height:none}}
"""


def _keys():
    """Governments that can have mail here (the contact list); the script drops the ones with none."""
    try:
        f = json.load(open(os.path.join(HERE, '..', 'data', 'civic', 'official_contacts.json')))
        ks = {g.get('key') or gkey(g['government']) for g in f['governments']}
        return [k for k in KEYS if k in ks]
    except (OSError, ValueError, KeyError):
        return None


def correspondence_page(out_dir):
    open(os.path.join(out_dir, 'assets', 'correspondence.js'), 'w').write(open(os.path.join(HERE, 'correspondence.js')).read())
    return f'''<style>{CSS}</style>
<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Get involved · Correspondence</span><h1>Government mail</h1>
    <p class="lede">Every email between BayCounty.me and Bay County’s officials and governments, start to finish: letters to officials, public records requests, and the records governments email in. Read-only, exactly as sent, with residents’ personal details hidden.</p></div></header>
  {city_bar(_keys())}
  <section class="tx-sec">
    <div class="mv-app" id="mv">
      <nav class="mv-side" id="mvFolders" aria-label="Folders"></nav>
      <section class="mv-list" aria-label="Conversations">
        <div class="mv-search"><input id="mvQ" type="search" placeholder="Search mail" aria-label="Search mail"></div>
        <ul class="mv-items" id="mvItems" data-share-items><li class="mv-empty">Loading…</li></ul>
        <div class="mv-pager" id="mvPager" hidden><button type="button" id="mvPrev">Newer</button><span id="mvPage"></span><button type="button" id="mvNext">Older</button></div>
      </section>
      <article class="mv-read" id="mvRead" aria-live="polite"><p class="mv-empty">Choose a conversation to read it.</p></article>
    </div>
  </section>
  <section class="tx-sec method"><div class="sec-hd"><h2>About this mail</h2></div><ul class="plain">
    <li><b>It’s all here.</b> Every email BayCounty.me sends to or gets from an official or a government shows up on its own, with the full back-and-forth. The only mail left out is sign-in codes and links.</li>
    <li><b>They’re public records.</b> Under Chapter 119, Florida Statutes, email about public business is open to anyone. Every letter we send says replies may be published here.</li>
    <li><b>Residents stay private.</b> Email addresses that aren’t government addresses, phone numbers and street addresses are hidden automatically, and we hide a resident’s name by hand when one comes up. Officials and government staff are named.</li>
    <li><b>Records sent in</b> are files a government emailed to its address at ingest.baycounty.me. Each one shows when it arrived, the file’s fingerprint (SHA-256), and what happened next: checked against our own records, published, or held for review. Mail from anyone not on that government’s list is turned away unopened and never shown.</li>
    <li><b>One email per official.</b> Each letter goes to one person, never a whole board, so officials can’t reply to each other outside a public meeting.</li>
    <li><b>Something wrong?</b> If you’re an official and we’ve misrepresented a reply, <a href="/about#contact">tell us</a> and we’ll fix it. If a conversation is ever taken down, it stays listed with the reason.</li>
  </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/correspondence.js" defer></script>'''
