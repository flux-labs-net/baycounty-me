"""Correspondence (/correspondence): emails BayCounty.me sent to officials and their replies.

The page holds no data. assets/correspondence.js reads /api/v1/correspondence, which returns only threads published
in /admin, by official name and seat (no email addresses). It opens on the latest year with mail; All years is one
choice away.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

CSS = r"""
.cr-list{display:flex;flex-direction:column;gap:14px;margin-top:12px}
.cr-c{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px}
.cr-c h3{font:600 1.05rem var(--f-display);margin:0 0 4px}
.cr-meta{color:var(--muted);font-size:.86rem;margin-bottom:12px}
.cr-orig{white-space:pre-wrap;line-height:1.55;font-size:.95rem;border-left:3px solid var(--line);padding:2px 0 2px 14px;margin:0 0 14px}
.cr-orig.clip{max-height:9.5em;overflow:hidden;-webkit-mask-image:linear-gradient(#000 60%,transparent);mask-image:linear-gradient(#000 60%,transparent)}
.cr-th{border-top:1px solid var(--line);padding:12px 0 2px}
.cr-who{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.cr-who b{font-weight:600}
.cr-who .muted{font-size:.84rem}
.cr-st{font-size:.78rem;border:1px solid var(--line);border-radius:999px;padding:1px 8px;color:var(--muted)}
.cr-st.yes{color:var(--green,#1F7A4D);border-color:currentColor}
.cr-msg{margin:8px 0 6px 0;padding:10px 12px;border-radius:10px;background:var(--sunken);white-space:pre-wrap;line-height:1.5;font-size:.93rem;word-break:break-word}
.cr-msg.out{background:none;border:1px dashed var(--line)}
.cr-msg small{display:block;color:var(--muted);font-size:.78rem;margin-bottom:4px;white-space:normal}
.cr-more{background:none;border:0;padding:0;color:var(--blue);font:inherit;font-size:.86rem;cursor:pointer;text-decoration:underline;text-underline-offset:2px}
"""


def correspondence_page(out_dir):
    open(os.path.join(out_dir, 'assets', 'correspondence.js'), 'w').write(open(os.path.join(HERE, 'correspondence.js')).read())
    return f'''<style>{CSS}</style>
<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Get involved · Correspondence</span><h1>Letters to officials</h1>
    <p class="lede">Emails BayCounty.me has sent to Bay County's elected officials and managers, and what they wrote back. Each email goes to one person, never a whole board, so officials can't reply to each other outside a public meeting.</p></div></header>
  <section class="tx-sec">
    <div class="filters-row">
      <select id="crY" aria-label="Year"></select>
      <select id="crG" aria-label="Government"><option value="">All governments</option></select>
      </div>
    <p class="muted small" id="crCount" aria-live="polite" style="margin:10px 0 0"></p>
    <div id="crList" class="cr-list"><p class="muted">Loading…</p></div>
  </section>
  <section class="tx-sec method"><div class="sec-hd"><h2>About these emails</h2></div><ul class="plain">
    <li><b>They're public records.</b> Under Chapter 119, Florida Statutes, officials' emails about public business are open to anyone. Every email we send says replies may be published here.</li>
    <li><b>We show the new part of each reply.</b> Earlier messages quoted at the bottom of a reply are left out, since they repeat what's already shown. Officials are named with their seat; email addresses aren't shown.</li>
    <li><b>“No reply yet”</b> means nothing has come back to us. It can take a while, and some answers come by phone or in a public meeting instead.</li>
    <li><b>Something wrong?</b> If you're an official and we've misrepresented a reply, <a href="/about#contact">tell us</a> and we'll fix it.</li>
  </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/correspondence.js" defer></script>'''
