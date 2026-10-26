"""Admin section (/admin): a To do page, review queues, outreach, data and email health, and API keys, grouped in one menu (MENU below).

A standalone page (no site menu, not in search or the sitemap, noindex). Everything it shows comes from
/api/admin after an emailed sign-in link; the page itself holds no data.
"""
import hashlib
import os

CSS = r"""
:root{--bar:#3F6FB0;--ok:#1F7A4D;--warn:#9A5B00;--bad:#B3261E}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bar:#5F92E0;--ok:#5BC98E;--warn:#F2B661;--bad:#FF8C82}}
:root[data-theme="dark"]{--bar:#5F92E0;--ok:#5BC98E;--warn:#F2B661;--bad:#FF8C82}
body{display:block}
.cp{max-width:1180px;margin:0 auto;padding:20px 16px 64px}
.tabs{display:flex;gap:4px;flex-wrap:wrap;margin:0 0 18px}
.tabs button{border:1px solid transparent;background:none;color:var(--muted);font:500 .9rem var(--f-body);padding:8px 14px;border-radius:8px;cursor:pointer}
.tabs button[aria-selected="true"]{background:var(--surface);border-color:var(--line);color:var(--ink)}
.btn{display:inline-flex;align-items:center;gap:6px;min-height:36px;padding:0 14px;border-radius:8px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font:500 .86rem var(--f-body);cursor:pointer;text-decoration:none}
.btn:hover{border-color:var(--blue)}
.btn.primary{background:var(--navy);border-color:var(--navy);color:#fff}
:root[data-theme="dark"] .btn.primary{color:#0E131B}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .btn.primary{color:#0E131B}}
.btn.danger{color:var(--bad)}
.btn:disabled{opacity:.5;cursor:default}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:18px}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.row .grow{flex:1}
.muted{color:var(--muted)} .small{font-size:.84rem}
.mono{font-family:var(--f-data);font-size:.84rem}
table.at{width:100%;border-collapse:collapse;font-size:13px}
.at th{text-align:left;font:500 .7rem var(--f-body);color:var(--muted);text-transform:uppercase;letter-spacing:.04em;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
.at td{padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
.at tr.click{cursor:pointer} .at tr.click:hover td{background:var(--sunken)}
.at td.num,.at th.num{text-align:right;font-variant-numeric:tabular-nums}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--surface)}
.tw table tr:last-child td{border-bottom:0}
.pill{display:inline-flex;align-items:center;gap:5px;font:500 .76rem var(--f-body);padding:2px 8px;border-radius:999px;border:1px solid var(--line);white-space:nowrap}
.pill::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}
.pill.active{color:var(--ok)} .pill.disabled{color:var(--warn)} .pill.revoked{color:var(--bad)} .pill.expired{color:var(--bad)}
label.f{display:flex;flex-direction:column;gap:5px;font:500 .82rem var(--f-body);color:var(--muted)}
label.f input,label.f textarea,label.f select,.sel{font:400 .92rem var(--f-body);color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:8px 10px;min-height:38px}
label.f textarea{min-height:70px;resize:vertical}
.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
@media (max-width:720px){.grid2,.grid3{grid-template-columns:1fr}}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:14px}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px}
.tile b{display:block;font:600 1.35rem var(--f-display);font-variant-numeric:tabular-nums}
.tile span{color:var(--muted);font-size:.8rem}
.chart{position:relative}
.chart svg{display:block;width:100%;height:auto}
.chart .tip{position:absolute;pointer-events:none;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:6px 9px;font-size:.8rem;box-shadow:0 6px 20px rgba(0,0,0,.14);white-space:nowrap;display:none}
.lists{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:12px}
@media (max-width:860px){.lists{grid-template-columns:1fr}}
.linkish{background:none;border:0;padding:0;color:var(--blue);font:inherit;cursor:pointer;text-decoration:underline;text-underline-offset:2px}
.linkish.danger{color:var(--bad)}
.list h3{font:600 .9rem var(--f-display);margin:0 0 10px}
.li{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 10px;margin-bottom:9px;font-size:.84rem}
.li .lbl{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.li .n{font-variant-numeric:tabular-nums;color:var(--muted)}
.li .track{grid-column:1/-1;height:6px;border-radius:3px;background:var(--sunken)}
.li .track i{display:block;height:100%;border-radius:3px;background:var(--bar)}
dialog{border:1px solid var(--line);border-radius:14px;background:var(--surface);color:var(--ink);padding:0;width:min(640px,calc(100vw - 32px));max-height:calc(100vh - 48px)}
dialog::backdrop{background:rgba(10,14,20,.45)}
dialog form{padding:20px;display:flex;flex-direction:column;gap:12px}
dialog h2{font:600 1.05rem var(--f-display);margin:0}
.secret{display:flex;gap:8px;align-items:center;background:var(--sunken);border:1px solid var(--line);border-radius:8px;padding:10px 12px;word-break:break-all}
.secret code{flex:1;font-family:var(--f-data);font-size:.86rem}
.note{border-left:3px solid var(--amber);padding:8px 12px;background:var(--sunken);border-radius:0 8px 8px 0;font-size:.86rem}
.err{color:var(--bad);font-size:.86rem;min-height:1em}
.signin{max-width:420px;margin:12vh auto 0}
.signin h1{font:600 1.3rem var(--f-display);margin:0 0 6px}
.toggle{display:flex;align-items:center;gap:8px;font-size:.9rem}
.empty{padding:28px;text-align:center;color:var(--muted)}
.st{font-variant-numeric:tabular-nums}
.st.e4,.st.e5{color:var(--bad)} .st.e429{color:var(--warn)}
.pill.ok{color:var(--ok)} .pill.failed{color:var(--bad)} .pill.running{color:var(--warn)}
.banner{display:flex;gap:10px;align-items:flex-start;padding:12px 14px;border:1px solid var(--line);border-left-width:4px;border-radius:10px;background:var(--surface);margin-bottom:14px}
.pill.new{color:var(--blue)} .pill.updated{color:var(--warn)} .pill.unchanged{color:var(--muted)} .pill.processed{color:var(--ok)} .pill.unmatched{color:var(--warn)} .pill.pending{color:var(--muted)}
details.ag summary{cursor:pointer;color:var(--blue)} details.ag pre{white-space:pre-wrap;max-height:260px;overflow:auto;font-size:.8rem;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:8px;margin:6px 0 0}
.ag-links{display:flex;flex-direction:column;gap:2px;max-width:420px;word-break:break-all}
.pill.delivered{color:var(--ok)} .pill.opened,.pill.clicked{color:var(--ok)} .pill.sent,.pill.queued,.pill.scheduled{color:var(--muted)}
.pill.bounced,.pill.complained,.pill.suppressed{color:var(--bad)} .pill.delivery_delayed{color:var(--warn)} .pill.canceled{color:var(--muted)}
#se-detail iframe{width:100%;height:520px;border:1px solid var(--line);border-radius:8px;background:#fff}
#se-detail dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 12px;margin:0 0 12px;font-size:.86rem} #se-detail dt{color:var(--muted)} #se-detail dd{margin:0;word-break:break-word}
.banner.good{border-left-color:var(--ok)} .banner.bad{border-left-color:var(--bad)}
.banner ul{margin:6px 0 0;padding-left:18px} .banner li{margin:2px 0}
.sched{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px 16px;font-size:.88rem}
.sched span:nth-child(even){color:var(--muted);text-align:right;white-space:nowrap}
.h2{font:600 1rem var(--f-display);margin:24px 0 10px}
.em{display:grid;grid-template-columns:280px minmax(0,1fr);gap:16px;align-items:start}
@media (max-width:860px){.em{grid-template-columns:1fr}}
.em-list{display:flex;flex-direction:column;gap:6px}
.em-list button{text-align:left;border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:10px;padding:10px 12px;cursor:pointer;font:500 .9rem var(--f-body)}
.em-list button span{display:block;font:400 .78rem var(--f-body);color:var(--muted);margin-top:3px}
.em-list button[aria-pressed="true"]{border-color:var(--blue);box-shadow:0 0 0 1px var(--blue)}
.em-meta{display:flex;flex-direction:column;gap:4px;margin-bottom:10px}
.em-subj{font:600 .98rem var(--f-body)}
.em-frame{border:1px solid var(--line);border-radius:12px;background:#F6F8FB;overflow:hidden;display:flex;justify-content:center}
.em-frame iframe{border:0;width:100%;height:720px;background:#F6F8FB;transition:width .2s}
.em-frame.mobile iframe{width:375px;max-width:100%}
.em-text{white-space:pre-wrap;font-family:var(--f-data);font-size:.82rem;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px;margin:0;max-height:720px;overflow:auto}
.co{display:grid;grid-template-columns:minmax(0,420px) minmax(0,1fr);gap:16px;align-items:start}
@media (max-width:900px){.co{grid-template-columns:1fr}}
.co-list{max-height:560px;overflow:auto;border:1px solid var(--line);border-radius:12px;background:var(--surface)}
.co-gov{font:600 .78rem var(--f-body);text-transform:uppercase;letter-spacing:.04em;color:var(--muted);padding:10px 12px 6px;background:var(--sunken);border-bottom:1px solid var(--line);display:flex;align-items:center;gap:8px;position:sticky;top:0}
.co-gov .grow{flex:1}
.co-p{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:2px 10px;align-items:start;padding:9px 12px;border-bottom:1px solid var(--line);font-size:.88rem}
.co-p:last-child{border-bottom:0}
.co-p input{margin-top:3px;width:16px;height:16px}
.co-p .nm{font-weight:500} .co-p .sub{grid-column:2;color:var(--muted);font-size:.8rem;word-break:break-all}
.co-p.off .nm,.co-p.off .sub,.co-p.off input{opacity:.55}
.co-chip{display:inline-flex;gap:4px;align-items:center;font-size:.78rem;border:1px solid var(--line);border-radius:999px;padding:2px 8px;margin:2px 4px 2px 0;background:var(--sunken)}
.pill.awaiting{color:var(--warn)} .pill.replied{color:var(--ok)} .pill.closed{color:var(--muted)} .pill.public{color:var(--blue)}
.pill.draft{color:var(--muted)} .pill.received{color:var(--ok)}
.rr-gaps{display:flex;flex-wrap:wrap;gap:4px}
.rr-gaps span{font:500 .74rem var(--f-data);border:1px solid var(--line);border-radius:6px;padding:1px 6px;background:var(--sunken)}
.co-p.on{background:var(--sunken)}
.th-msg{border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:10px;background:var(--bg)}
.th-msg.in{border-left:4px solid var(--ok)} .th-msg.out{border-left:4px solid var(--bar)}
.th-msg header{display:flex;gap:8px;flex-wrap:wrap;align-items:center;font-size:.8rem;color:var(--muted);margin-bottom:6px}
.th-msg header b{color:var(--ink);font-weight:500}
.th-msg .body{white-space:pre-wrap;font-size:.9rem;line-height:1.5;word-break:break-word}
.h3{font:600 .95rem var(--f-display);margin:18px 0 8px}
.ac-head{margin:22px 0 6px;gap:8px;flex-wrap:wrap}
.ac-qhead{margin:18px 0 8px;gap:8px;flex-wrap:wrap}
.ac-bulk{position:sticky;top:0;z-index:2;gap:8px;padding:8px 12px;margin-bottom:8px;border:1px solid var(--line);border-radius:10px;background:var(--surface)}
.ac-snd{display:flex;gap:6px;align-items:center;min-width:240px}
.ac-snd input{flex:1;min-width:0;min-height:32px;padding:0 8px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:400 .8rem var(--f-data)}
.ac-snd .btn{min-height:32px;padding:0 10px}
.pill.received{color:var(--blue)} .pill.normalized{color:var(--ok)} .pill.duplicate{color:var(--muted)} .pill.approved{color:var(--ok)} .pill.rejected{color:var(--bad)}
.sw{display:inline-flex;align-items:center;gap:6px;font-size:.82rem;cursor:pointer}
.sw input{width:16px;height:16px}
#ac-queue td:first-child,#ac-queue th:first-child{width:28px}
#ac-queue input[type=checkbox]{width:16px;height:16px}
#ac-files tr.sel-row td{background:var(--sunken)}
.bk{position:sticky;top:0;z-index:2;padding:8px 12px;margin-bottom:8px;border:1px solid var(--line);border-radius:10px;background:var(--surface);display:flex;flex-direction:column;gap:6px}
.bk-top{gap:8px 12px} .bk-top .btn{min-height:32px;padding:0 12px}
.bk-n{font:600 .86rem var(--f-body);min-width:84px}
.bk-sure{gap:8px;padding-top:6px;border-top:1px dashed var(--line)} .bk-sure .btn{min-height:32px;padding:0 12px}
.bk-note{margin:0} .bk-msg .banner{margin:0}
.at td.pk,.at th.pk{width:28px;padding-right:0} .at .pk input{width:16px;height:16px;margin:2px 0 0;cursor:pointer}
[hidden]{display:none!important}

/* layout + menu: side menu from 960px, top bar and full-screen menu below */
.cp{max-width:1320px}
.cp-main{font-size:14px}
/* desktop tables: one line per row, no sideways scroll (fit() in admin.js sizes the columns and marks the ones that shrink .fl) */
@media (min-width:641px){
  table.at.fit th,table.at.fit td{white-space:nowrap}
  table.at.fit.fixed{table-layout:fixed}
  table.at.fit.fixed th{overflow:hidden;text-overflow:ellipsis}
  table.at.fit td{vertical-align:middle}
  table.at.fit .fl{overflow:hidden;text-overflow:ellipsis}
  table.at.fit td > .fl-in{display:inline}
  table.at.fit td > .fl-sep::before{content:" · ";color:var(--muted)}
  table.at.fit td.fl-wrap{white-space:normal}
  table.at.fit td.fl-wrap .fl-in{display:block}
  table.at.fit td.fl-wrap .fl-sep::before{content:none}
}
.cp-shell{display:grid;grid-template-columns:236px minmax(0,1fr);gap:32px;align-items:start}
.cp-main{min-width:0}
.cp-h{font:600 1.45rem var(--f-display);letter-spacing:-.015em;margin:4px 0 16px}
.an{position:sticky;top:16px;max-height:calc(100vh - 32px);overflow-y:auto;display:flex;flex-direction:column;gap:2px;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px 10px}
.an-head{display:flex;align-items:center;gap:10px;padding:0 6px 12px}
.an-logo{width:32px;height:32px;flex-shrink:0;border-radius:9px;background:var(--navy);color:var(--surface);display:inline-flex;align-items:center;justify-content:center;font:600 .78rem var(--f-body)}
.an-brand{display:flex;flex-direction:column;line-height:1.2;flex:1}
.an-brand b{font-size:.9rem} .an-brand span{font-size:.76rem;color:var(--muted)}
.an-btn{width:44px;height:44px;flex-shrink:0;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink);display:inline-flex;align-items:center;justify-content:center;cursor:pointer}
.an-x,.an-top{display:none}
.an-find{display:flex;align-items:center;gap:8px;min-height:38px;padding:0 10px;border:1px solid var(--line);border-radius:8px;color:var(--muted);margin:0 0 8px;background:var(--bg)}
.an-find input{border:0;outline:0;background:none;font:400 .86rem var(--f-body);color:var(--ink);width:100%;min-width:0}
.an a{display:flex;align-items:center;gap:10px;min-height:34px;padding:0 10px;border-radius:8px;color:var(--ink);text-decoration:none;font:400 .88rem var(--f-body)}
.an a span{flex:1;min-width:0}
.an a:hover{background:var(--sunken)}
.an a[aria-current="page"]{background:color-mix(in srgb,var(--blue) 14%,transparent);color:var(--navy);font-weight:600}
.an-todo{font-weight:500!important}
.an-total{font:600 .72rem var(--f-body);font-style:normal;background:var(--navy);color:var(--surface);border-radius:999px;padding:1px 8px}
.an-n{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.an-n.on{background:var(--gold)}
.an-g{display:flex;flex-direction:column;gap:2px}
.an-h{display:flex;align-items:center;gap:8px;font:600 .68rem var(--f-body);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);padding:12px 10px 3px}
.an-teal svg{color:var(--teal)} .an-blue svg{color:var(--blue)} .an-amber svg{color:var(--gold)} .an-gray svg{color:var(--muted)}
.an-items{display:flex;flex-direction:column;gap:2px}
.an-items a{padding-left:32px}
.an a.an-hide{display:none}
.an-foot{margin-top:14px;border-top:1px solid var(--line);padding-top:10px;display:flex;flex-direction:column;gap:2px}
.an-foot svg{color:var(--muted)}
.an-who{display:flex;align-items:center;gap:8px;padding:8px 10px 2px;font-size:.78rem;color:var(--muted)}
.an-who span{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis}
.td{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.td a{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px;display:flex;flex-direction:column;gap:6px;text-decoration:none;color:var(--ink)}
.td a:hover{border-color:var(--blue)}
.td .k{display:flex;align-items:center;justify-content:space-between;font:600 .7rem var(--f-body);text-transform:uppercase;letter-spacing:.06em}
.td .k b{font:600 1.5rem var(--f-display);letter-spacing:0;color:var(--ink);font-variant-numeric:tabular-nums}
.td .t{font-weight:600} .td .d{font-size:.84rem;color:var(--muted)} .td .go{font-size:.84rem;color:var(--blue);margin-top:auto;padding-top:4px}
.td .teal{color:var(--teal)} .td .blue{color:var(--blue)} .td .amber{color:var(--salmon)}
@media (max-width:959px){
  .cp{padding-top:0}
  .an-top{display:flex;position:sticky;top:0;z-index:30;align-items:center;gap:10px;margin:0 -16px 14px;padding:8px 8px 8px 16px;min-height:60px;box-sizing:border-box;background:var(--surface);border-bottom:1px solid var(--line)}
  .an-cur{flex:1;min-width:0;display:flex;flex-direction:column;line-height:1.15}
  .an-cur span{font-size:.72rem;color:var(--muted)} .an-cur b{font-size:.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .cp-shell{display:block}
  .an{display:none;position:fixed;inset:0;z-index:60;max-height:none;border:0;border-radius:0;padding:12px 16px 24px;background:var(--bg)}
  .an.open{display:flex}
  .an-x{display:inline-flex}
  .an a{min-height:44px}
  .an a.an-todo,.an a.an-todo[aria-current="page"],.an a.an-todo:hover{background:var(--navy);color:var(--surface);border-radius:12px;margin-bottom:4px}
  .an-todo .an-total{background:var(--surface);color:var(--navy)}
  .an-items{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}
  .an-items a{padding:0 12px;border:1px solid var(--line);background:var(--surface);font-size:.84rem;line-height:1.2}
  .an-h{padding:12px 2px 6px}
  .cp-h{font-size:1.25rem;margin:0 0 12px}
  body.an-lock{overflow:hidden}
}
/* phones: nothing in a pane may push the page sideways; wide tables scroll inside their own box */
@media (max-width:600px){
  .pane .row > .sel,.pane .row > input.sel,.pane .row > select.sel{min-width:0!important;flex:1 1 150px;max-width:100%}
  .pane .row > .h2.grow{flex-basis:100%}
  .ac-snd{min-width:0}
  .td{grid-template-columns:1fr}
}
"""


# The admin menu: (group, tone, icon, [(tab, label, count key or None)]). A tab is a <section id="tab-NAME" class="pane">.
# Count keys match api/_summary.js; an item with waiting work shows a dot.
MENU = [
    ('Review', 'teal', 'shield', [('owners', 'Business owners', 'owners'), ('limits', 'Gifts over the limit', 'limits'),
                                  ('boards', 'Nonprofit boards', 'boards'), ('ties', 'Business ties', 'ties'),
                                  ('minutes', 'Votes from minutes', 'minutes'), ('accounting', 'Accounting files', 'accounting')]),
    ('Outreach', 'blue', 'send', [('compose', 'Write to officials', None), ('correspondence', 'Conversations', 'replies'),
                                  ('records', 'Records requests', 'records')]),
    ('Data & email', 'amber', 'db', [('ingestion', 'Data health', 'syncs'), ('agendas', 'Agendas', 'agendas'),
                                     ('sent', 'Sent mail', None), ('emails', 'Email templates', None)]),
    ('API', 'gray', 'key', [('keys', 'Keys', None), ('analytics', 'Usage & request log', None), ('settings', 'Limits & activity', None)]),
]
TITLES = {'todo': 'To do', **{t: label for _, _, _, items in MENU for t, label, _ in items}}

_ICONS = {
    'todo': '<path d="M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2"/>',
    'shield': '<path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    'send': '<path d="M21 3L10 14"/><path d="M21 3l-7 18-4-7-7-4z"/>',
    'db': '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    'key': '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3"/>',
    'out': '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h5"/>',
    'menu': '<path d="M4 7h16M4 12h16M4 17h16"/>',
    'close': '<path d="M6 6l12 12M18 6L6 18"/>',
    'search': '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
}


def _svg(name, size=18):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_ICONS[name]}</svg>')


def _esc(t):
    return t.replace('&', '&amp;')


def shell_html():
    """Top bar (phones), the grouped menu (side menu on wide screens, full-screen sheet on phones) and the page title."""
    groups = []
    for group, tone, icon, items in MENU:
        links = ''.join(f'<a href="#{t}" data-tab="{t}"{f" data-count={k}" if k else ""}><span>{_esc(label)}</span><i class="an-n"></i></a>'
                        for t, label, k in items)
        groups.append(f'<div class="an-g"><div class="an-h an-{tone}">{_svg(icon, 14)}{_esc(group)}</div><div class="an-items">{links}</div></div>')
    return f"""    <header class="an-top">
      <span class="an-logo" aria-hidden="true">BC</span>
      <div class="an-cur"><span>Admin</span><b id="an-cur">To do</b></div>
      <button class="an-btn" id="an-open" type="button" aria-label="Open menu" aria-expanded="false" aria-controls="an-nav">{_svg('menu', 20)}</button>
    </header>
    <div class="cp-shell">
    <nav class="an" id="an-nav" aria-label="Admin">
      <div class="an-head">
        <span class="an-logo" aria-hidden="true">BC</span>
        <div class="an-brand"><b>BayCounty.me</b><span>Admin</span></div>
        <button class="an-btn an-x" id="an-close" type="button" aria-label="Close menu">{_svg('close', 20)}</button>
      </div>
      <label class="an-find">{_svg('search', 16)}<input type="search" id="an-find" placeholder="Jump to…" aria-label="Jump to a section" autocomplete="off"></label>
      <a href="#todo" data-tab="todo" class="an-todo">{_svg('todo')}<span>To do</span><i class="an-total" id="an-total" hidden></i></a>
      {''.join(groups)}
      <div class="an-foot">
        <a href="/finance" target="_blank" rel="noopener"><span>Finance workspace</span>{_svg('out', 14)}</a>
        <a href="/" target="_blank" rel="noopener"><span>Public site</span>{_svg('out', 14)}</a>
        <div class="an-who"><span id="who"></span><button class="linkish" id="signout" type="button">Sign out</button></div>
      </div>
    </nav>
    <div class="cp-main" id="cp-main">
    <h1 class="cp-h" id="cp-h">To do</h1>"""


def admin_page(out_dir):
    shell = shell_html()
    # A new admin.js gets a new URL, so a cached old copy can never run against new page markup.
    js_ver = hashlib.sha1(open(os.path.join(os.path.dirname(__file__), 'admin.js'), 'rb').read()).hexdigest()[:10]
    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Admin · BayCounty.me</title>
<script>try{{var t=localStorage.getItem('theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t)}}catch(e){{}}</script>
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="/assets/site.css">
<script src="/assets/tables.js" defer></script>
<style>{CSS}</style>
</head>
<body>
<div class="cp tt-scope">
  <section id="signin" class="signin card" hidden>
    <h1>BayCounty.me admin</h1>
    <p class="muted small">Enter your admin email and we'll send you a sign-in link.</p>
    <form id="signin-form" class="row" style="margin-top:12px">
      <label class="f grow"><input type="email" name="email" aria-label="Email" required autocomplete="email" placeholder="you@example.com"></label>
      <button class="btn primary" type="submit">Send link</button>
    </form>
    <p id="signin-msg" class="small muted" role="status" style="margin:10px 0 0"></p>
  </section>

  <div id="app" hidden>
{shell}
    <section id="tab-todo" class="pane">
      <div id="td-banner"></div>
      <div class="td" id="td-list"><p class="empty">Loading…</p></div>
      <p class="muted small" id="td-quiet" style="margin:14px 0 0"></p>
    </section>

    <section id="tab-keys" class="pane" hidden>
      <div class="row" style="margin-bottom:12px"><p class="muted small grow" style="margin:0">Each key belongs to one person or app. Limits apply per key; requests without a key use the keyless limits in Limits &amp; activity.</p>
        <button class="btn primary" id="new-key" type="button">New key</button></div>
      <div class="tw"><table class="at" id="keys-table"><thead><tr><th>Name</th><th>Assigned to</th><th>Key</th><th class="num">Per minute</th><th class="num">Per day</th><th>Status</th><th class="num">24 hours</th><th class="num">30 days</th><th>Last used</th></tr></thead><tbody></tbody></table></div>
    </section>

    <section id="tab-analytics" class="pane" hidden>
      <div class="row" style="margin-bottom:12px">
        <select class="sel" id="an-scope" aria-label="Traffic to show"></select>
        <select class="sel" id="an-days" aria-label="Date range"><option value="7">Last 7 days</option><option value="30" selected>Last 30 days</option><option value="90">Last 90 days</option></select>
      </div>
      <div class="tiles" id="an-tiles"></div>
      <div class="card"><div class="row" style="margin-bottom:6px"><b class="grow">Requests per day</b><span class="muted small">Central time</span></div><div class="chart" id="an-chart"></div></div>
      <div class="lists" id="an-lists"></div>
      <h2 class="h2" id="logs" style="margin-top:28px">Request log</h2>
      <div class="row" style="margin-bottom:12px">
        <select class="sel" id="lg-scope" aria-label="Traffic to show"></select>
        <input class="sel mono" id="lg-ip" placeholder="Filter by IP or range" aria-label="Filter by IP address or range" style="min-width:200px">
        <label class="toggle"><input type="checkbox" id="lg-errors"> Errors and blocked only</label>
        <button class="btn" id="lg-refresh" type="button">Refresh</button>
      </div>
      <div class="tw"><table class="at" id="logs-table"><thead><tr><th>Time</th><th>Key</th><th>Where</th><th>Request</th><th>IP address</th><th class="num">Status</th><th class="num">Rows</th><th class="num">ms</th></tr></thead><tbody></tbody></table></div>
      <div class="row" style="margin-top:12px"><button class="btn" id="lg-more" type="button" hidden>Load older</button></div>
    </section>

    <section id="tab-settings" class="pane" hidden>
      <form id="settings-form" class="card" style="display:flex;flex-direction:column;gap:14px">
        <div><b>Requests without a key</b><p class="muted small" style="margin:4px 0 0">Counted per connection. Leave a box empty for no limit.</p></div>
        <div class="grid2"><label class="f">Per minute<input type="number" min="0" name="anon_per_minute"></label><label class="f">Per day<input type="number" min="0" name="anon_per_day"></label></div>
        <label class="toggle"><input type="checkbox" name="require_key"> Require a key for every request (turns off keyless access)</label>
        <div><b>Starting limits for new keys</b></div>
        <div class="grid2"><label class="f">Per minute<input type="number" min="0" name="default_per_minute"></label><label class="f">Per day<input type="number" min="0" name="default_per_day"></label></div>
        <div class="row"><button class="btn primary" type="submit">Save</button><span id="settings-msg" class="small muted" role="status"></span></div>
      </form>
      <h2 style="font:600 1rem var(--f-display);margin:24px 0 6px">Blocked addresses</h2>
      <p class="muted small" style="margin:0 0 10px">Requests from these addresses get a 403, with or without a key. IP addresses in the request log are kept for 90 days.</p>
      <form id="block-form" class="card row" style="margin-bottom:10px;align-items:flex-end">
        <label class="f">Address or range<input name="network" class="mono" required placeholder="203.0.113.7 or 203.0.113.0/24"></label>
        <label class="f grow">Reason<input name="reason" maxlength="300" placeholder="Optional"></label>
        <label class="f">Until<input type="date" name="expires_at"></label>
        <button class="btn danger" type="submit">Block</button>
      </form>
      <p id="block-msg" class="err" role="status"></p>
      <div class="tw"><table class="at" id="blocks-table"><thead><tr><th>Address or range</th><th>Reason</th><th>Until</th><th class="num">Blocked requests, 30 days</th><th>Added</th><th></th></tr></thead><tbody></tbody></table></div>
      <h2 style="font:600 1rem var(--f-display);margin:24px 0 10px">Admin activity</h2>
      <div class="tw"><table class="at" id="audit-table"><thead><tr><th>Time</th><th>Who</th><th>What</th><th>Details</th></tr></thead><tbody></tbody></table></div>
    </section>

    <section id="tab-ingestion" class="pane" hidden>
      <div class="row" style="margin-bottom:12px"><p class="muted small grow" style="margin:0">Each database sync logs one run per dataset. Admins (ADMIN_EMAILS) are emailed when a workflow fails and by the daily check below.</p>
        <a class="btn" href="https://github.com/jeremymcs/baycounty-me/actions" target="_blank" rel="noopener">Workflow runs</a><button class="btn" id="in-refresh" type="button">Refresh</button></div>
      <div id="in-banner"></div>
      <div class="tiles" id="in-tiles"></div>
      <div class="lists" style="margin-top:0">
        <div class="card"><h3 style="font:600 .9rem var(--f-display);margin:0 0 10px">Schedule <span class="muted small" style="font-weight:400">(Central time)</span></h3><div class="sched" id="in-sched"></div></div>
        <div class="card"><h3 style="font:600 .9rem var(--f-display);margin:0 0 10px">Who gets told</h3><div class="small" style="display:flex;flex-direction:column;gap:6px">
          <div><b>Workflow problems</b> <span class="muted">(failed fetch, new meeting-source errors, failed push, failed load, missing secret): an email right after the run.</span></div>
          <div><b>Daily check</b> <span class="muted">(failed or stuck loads, no sync in 36 hours, failed alert emails, unprocessed alert backlog): an email only when something is wrong.</span></div>
          <div><b>Weekly digest</b> <span class="muted">drafts or failures: the digest reviewer.</span></div></div></div>
      </div>
      <h2 class="h2">Datasets</h2>
      <div class="tw"><table class="at" id="in-table"><thead><tr><th>Dataset</th><th>Status</th><th>Last run</th><th>Last success</th><th class="num">Rows</th><th class="num">Added</th><th class="num">Removed</th><th>Notes</th></tr></thead><tbody></tbody></table></div>
      <h2 class="h2">Failures, last 14 days</h2>
      <div class="tw"><table class="at" id="in-fail"><thead><tr><th>Time</th><th>Dataset</th><th>Error</th><th>Commit</th></tr></thead><tbody></tbody></table></div>
    </section>

    <section id="tab-agendas" class="pane" hidden>
      <div class="row" style="margin-bottom:12px"><p class="muted small grow" style="margin:0">Notice emails (CivicPlus Notify Me and similar) arrive at ingest@baycounty.me. Each one triggers a rescan of that government’s agenda system; every agenda, packet and minutes file is downloaded and hashed. A changed file is a new version.</p>
        <a class="btn" href="https://github.com/jeremymcs/baycounty-me/actions/workflows/watch-agendas.yml" target="_blank" rel="noopener">Workflow runs</a>
        <button class="btn" id="ag-run" type="button">Run now</button><button class="btn" id="ag-refresh" type="button">Refresh</button></div>
      <div id="ag-banner"></div>
      <div class="tiles" id="ag-tiles"></div>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin:18px 0 8px">
        <h2 class="h2 grow" style="margin:0">Documents</h2>
        <select class="sel" id="ag-board" aria-label="Board"><option value="">All boards</option></select>
        <select class="sel" id="ag-status" aria-label="Status"><option value="">Any status</option><option value="new">New</option><option value="updated">Updated</option><option value="unchanged">Unchanged</option><option value="failed">Failed</option></select>
        <select class="sel" id="ag-days" aria-label="Window"><option value="7">Last 7 days</option><option value="14" selected>Last 14 days</option><option value="30">Last 30 days</option><option value="120">Last 120 days</option></select>
      </div>
      <div class="tw"><table class="at" id="ag-docs" data-tt="off"><thead><tr><th>Changed</th><th>Board</th><th>Document</th><th>Meeting</th><th>Status</th><th>Versions</th><th>Files</th></tr></thead><tbody></tbody></table></div>
      <h2 class="h2">Inbox</h2>
      <div class="tw"><table class="at" id="ag-notices" data-tt="off"><thead><tr><th>Received</th><th>From</th><th>Subject</th><th>Matched</th><th>Links</th><th>Attachments</th><th>Status</th></tr></thead><tbody></tbody></table></div>
      <div class="row" style="margin:18px 0 8px"><h2 class="h2 grow" style="margin:0">Errors, last 14 days</h2><button class="btn" id="ag-resolve-all" type="button">Mark all resolved</button></div>
      <div class="tw"><table class="at" id="ag-errors" data-tt="off"><thead><tr><th>Time</th><th>Stage</th><th>Source</th><th>Error</th><th></th></tr></thead><tbody></tbody></table></div>
      <h2 class="h2">Runs</h2>
      <div class="tw"><table class="at" id="ag-runs" data-tt="off"><thead><tr><th>Started</th><th>Status</th><th class="num">Files checked</th><th>Summary</th></tr></thead><tbody></tbody></table></div>
    </section>

    <section id="tab-sent" class="pane" hidden>
      <div class="row" style="margin-bottom:12px"><p class="muted small grow" style="margin:0">Every email sent through Resend (alerts, digests, sign-in links, agenda summaries) and its latest delivery status. Resend reports only the most recent event for each email. Open and click tracking are off for baycounty.me, so delivered is the best status you’ll see.</p>
        <a class="btn" href="https://resend.com/emails" target="_blank" rel="noopener">Resend dashboard</a><button class="btn" id="se-refresh" type="button">Refresh</button></div>
      <div id="se-banner"></div>
      <div class="tiles" id="se-tiles"></div>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin:18px 0 8px">
        <h2 class="h2 grow" style="margin:0">Emails</h2>
        <input class="sel" id="se-q" type="search" placeholder="Search to, from, subject" aria-label="Search" style="min-width:200px">
        <select class="sel" id="se-status" aria-label="Status"><option value="">Any status</option><option value="problems">Problems only</option></select>
        <select class="sel" id="se-domain" aria-label="Sending domain"><option value="baycounty.me">baycounty.me</option><option value="">All domains</option></select>
        <select class="sel" id="se-days" aria-label="Window"><option value="1">Last 24 hours</option><option value="7" selected>Last 7 days</option><option value="30">Last 30 days</option><option value="90">Last 90 days</option></select>
      </div>
      <div class="card" id="se-detail" hidden style="margin-bottom:14px"></div>
      <div class="tw"><table class="at" id="se-table" data-tt="off"><thead><tr><th>Sent</th><th>To</th><th>Subject</th><th>From</th><th>Status</th><th></th></tr></thead><tbody></tbody></table></div>
      <p class="muted small" id="se-foot"></p>
    </section>

    <section id="tab-emails" class="pane" hidden>
      <div class="em">
        <div>
          <div class="em-list" id="em-list"></div>
          <div class="card" style="margin-top:12px;display:flex;flex-direction:column;gap:10px">
            <label class="f" id="em-gov-wrap">Government<select class="sel" id="em-gov"></select></label>
            <label class="f" id="em-src-wrap" hidden>Content<select class="sel" id="em-src"><option value="sample">Sample matches</option><option value="latest">Latest real email</option></select></label>
            <button class="btn" id="em-test" type="button">Send a test to me</button>
            <p class="small muted" id="em-test-msg" role="status" style="margin:0"></p>
          </div>
        </div>
        <div>
          <div class="em-meta"><span class="muted small" id="em-when"></span><span class="em-subj" id="em-subj"></span><span class="note" id="em-note" hidden></span></div>
          <div class="row" style="margin-bottom:10px">
            <div class="tabs" style="margin:0" role="group" aria-label="View"><button type="button" data-view="html" aria-selected="true">Email</button><button type="button" data-view="text" aria-selected="false">Plain text</button></div>
            <span class="grow"></span>
            <div class="tabs" style="margin:0" role="group" aria-label="Width"><button type="button" data-width="desktop" aria-selected="true">Desktop</button><button type="button" data-width="mobile" aria-selected="false">Phone</button></div>
          </div>
          <div class="em-frame" id="em-frame"><iframe id="em-iframe" title="Email preview" sandbox="allow-popups allow-popups-to-escape-sandbox"></iframe></div>
          <pre class="em-text" id="em-text" hidden></pre>
        </div>
      </div>
    </section>

    <section id="tab-compose" class="pane" hidden>
      <p class="muted small" style="margin:0 0 12px">Each person gets their own email from hello@baycounty.me, addressed to them alone, so no one can reply-all to other board members (Sunshine Law). Replies come back to hello@ and show up under Conversations. Nothing is public until you publish it.</p>
      <div class="co">
        <div>
          <div class="row" style="margin-bottom:8px">
            <select class="sel" id="co-gov" aria-label="Government" style="flex:1;min-width:0;width:auto"><option value="">All governments</option></select>
            <select class="sel" id="co-kind" aria-label="Who" style="width:auto"><option value="">Everyone</option><option value="elected">Elected only</option><option value="staff">Staff only</option></select>
          </div>
          <div class="row small" style="margin-bottom:8px"><label class="toggle"><input type="checkbox" id="co-all"> Select everyone shown</label><span class="grow"></span><span class="muted" id="co-count">0 selected</span></div>
          <div class="co-list" id="co-list"><p class="empty">Loading…</p></div>
          <p class="muted small" id="co-foot" style="margin:8px 0 0"></p>
        </div>
        <div class="card" style="display:flex;flex-direction:column;gap:12px">
          <div><div class="small muted" style="margin-bottom:4px">To</div><div id="co-to" class="small muted">Pick officials on the left.</div></div>
          <label class="f">Subject<input id="co-subj" maxlength="200" placeholder="e.g. Request: FY2026 bank reconciliations"></label>
          <label class="f">Message<textarea id="co-body" style="min-height:240px" placeholder="Write the message. Each email starts with “Dear [name],” and ends with a line saying replies may be published, plus a reference number."></textarea></label>
          <div class="row"><button class="btn" type="button" id="co-test">Send a test to me</button><span class="grow"></span><button class="btn primary" type="button" id="co-send" disabled>Send</button></div>
          <p class="small" id="co-msg" role="status" style="margin:0"></p>
        </div>
      </div>
    </section>

    <section id="tab-correspondence" class="pane" hidden>
      <div class="tiles" id="cr-tiles"></div>
      <div id="cr-unmatched"></div>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin:6px 0 8px">
        <h2 class="h2 grow" style="margin:0">Conversations</h2>
        <input class="sel" id="cr-q" type="search" placeholder="Search name, subject" aria-label="Search" style="min-width:180px">
        <select class="sel" id="cr-year" aria-label="Year"></select>
        <select class="sel" id="cr-gov" aria-label="Government"><option value="">All governments</option></select>
        <select class="sel" id="cr-status" aria-label="Status"><option value="">Any status</option><option value="awaiting">Awaiting reply</option><option value="replied">Replied</option><option value="closed">Closed</option></select>
        <select class="sel" id="cr-pub" aria-label="Published"><option value="">Public or not</option><option value="yes">Published</option><option value="no">Not published</option></select>
      </div>
      <div class="card" id="cr-detail" hidden style="margin-bottom:14px"></div>
      <div class="tw"><table class="at" id="cr-table" data-tt="off"><thead><tr><th>Last activity</th><th>Official</th><th>Subject</th><th class="num">Sent</th><th class="num">Replies</th><th>Status</th><th>Public</th></tr></thead><tbody></tbody></table></div>
      <p class="muted small" style="margin-top:8px">The public page is <a href="/correspondence" target="_blank" rel="noopener">baycounty.me/correspondence</a>. It shows only published threads, by official name and seat, without email addresses.</p>
    </section>

    <section id="tab-records" class="pane" hidden>
      <p class="muted small" style="margin:0 0 12px">Public records requests (Chapter 119) for the budget years the site is missing, one draft per government. Nothing is sent until you press Send on a request. Each goes to one address from hello@baycounty.me, and the reply shows up under Conversations.</p>
      <div class="tiles" id="rr-tiles"></div>
      <div class="co">
        <div class="co-list" id="rr-list"><p class="empty">Loading…</p></div>
        <div class="card" id="rr-detail" style="display:flex;flex-direction:column;gap:12px"><p class="muted small" style="margin:0">Pick a request on the left.</p></div>
      </div>
    </section>

    <section id="tab-ties" class="pane" hidden>
      <div class="banner"><div><b>Check each match before confirming it.</b> <span class="small muted">Officials, department leaders and candidates paired by name with people in the state corporate file (Sunbiz). A name match can be a different person: open the Sunbiz record and check the address, middle initial or business before you confirm. Confirming publishes that official's businesses and links on <a href="/connections/business-ties" target="_blank" rel="noopener">/connections/business-ties</a>; rejecting or setting it back to unreviewed takes them down. Other people on those businesses are never named publicly.</span></div></div>
      <div class="tiles" id="bt-tiles"></div>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin:18px 0 8px">
        <h2 class="h2 grow" style="margin:0">Name matches</h2>
        <input class="sel" id="bt-q" type="search" placeholder="Official's name" aria-label="Official's name">
        <select class="sel" id="bt-confidence" aria-label="Confidence"><option value="">Any confidence</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
        <select class="sel" id="bt-status" aria-label="Review status"><option value="unreviewed">Unreviewed</option><option value="">Any review status</option><option value="confirmed">Confirmed</option><option value="rejected">Rejected</option></select>
      </div>
      <div class="tw"><table class="at" id="bt-table" data-tt="off"><thead><tr><th class="pk"><input type="checkbox" data-bk-all aria-label="Select all shown"></th><th>Official</th><th>Sunbiz person</th><th>Businesses</th><th>Links</th><th>Review</th></tr></thead><tbody></tbody></table></div>
    </section>

    <section id="tab-minutes" class="pane" hidden>
      <div class="banner"><div><b>Votes read from meeting minutes.</b> <span class="small muted">Every minutes file since 2016 is read by Claude into motions and roll calls, and the printed names are matched to officeholder terms. Motions that pass every check go on the site automatically on the next daily refresh. Motions here failed a check, or are a random 1-in-50 spot check of passing ones: open the minutes page, then approve (publishes a flagged motion) or reject (keeps any motion off the site). To fix a wrong name or term, correct data/civic/officeholders.json and re-match.</span></div></div>
      <div class="tiles" id="mv-tiles"></div>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin:18px 0 8px">
        <h2 class="h2 grow" style="margin:0">Motions</h2>
        <input class="sel" id="mv-q" type="search" placeholder="Words in the motion" aria-label="Words in the motion">
        <select class="sel" id="mv-queue" aria-label="Queue"><option value="flagged">Flagged</option><option value="sample">Spot checks</option><option value="passed">Passed checks</option><option value="all">All motions</option></select>
        <select class="sel" id="mv-board" aria-label="Board"><option value="">Every board</option></select>
        <select class="sel" id="mv-year" aria-label="Year"><option value="">Every year</option></select>
        <select class="sel" id="mv-status" aria-label="Review status"><option value="unreviewed">Unreviewed</option><option value="">Any review status</option><option value="approved">Approved</option><option value="rejected">Rejected</option></select>
      </div>
      <div id="mv-checks" class="small muted" style="margin:0 0 8px"></div>
      <div class="tw"><table class="at" id="mv-table" data-tt="off"><thead><tr><th class="pk"><input type="checkbox" data-bk-all aria-label="Select all shown"></th><th>Meeting</th><th>Motion</th><th>Votes</th><th>Checks</th><th>Review</th></tr></thead><tbody></tbody></table></div>
      <h2 class="h2" style="margin:24px 0 8px">Coverage</h2>
      <div class="tw"><table class="at" id="mv-coverage"><thead><tr><th>Board</th><th class="num">Files</th><th class="num">Read</th><th class="num">Motions</th><th>By year (files read / captured)</th></tr></thead><tbody></tbody></table></div>
      <h2 class="h2" style="margin:24px 0 8px">Batches</h2>
      <div class="tw"><table class="at" id="mv-batches"><thead><tr><th>Batch</th><th>Status</th><th class="num">Requests</th><th class="num">Estimate</th><th class="num">Cost</th><th>Sent</th><th>Collected</th></tr></thead><tbody></tbody></table></div>
    </section>

    <section id="tab-owners" class="pane" hidden>
      <div class="banner"><div><b>Private research. Do not publish names from this tab.</b> <span class="small muted">Officers, managers and registered agents from the state corporate file (Sunbiz), grouped into people by name and address, and business campaign gifts matched to those businesses. Public pages show business names only. Mark a group confirmed after checking it on Sunbiz; nothing here is published automatically. Giving through several companies is legal in Florida when each company is a real contributor.</span></div></div>
      <div class="tiles" id="ow-tiles"></div>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin:18px 0 8px">
        <h2 class="h2 grow" style="margin:0">Businesses that share a person and gave to the same candidate</h2>
        <select class="sel" id="ow-status" aria-label="Review status"><option value="">Any review status</option><option value="unreviewed">Unreviewed</option><option value="confirmed">Confirmed</option><option value="rejected">Rejected</option></select>
      </div>
      <div class="tw"><table class="at" id="ow-groups" data-tt="off"><thead><tr><th class="pk"><input type="checkbox" data-bk-all aria-label="Select all shown"></th><th>Candidate</th><th>Businesses</th><th>Linked by</th><th class="num">Checks</th><th class="num">Total</th><th>Review</th></tr></thead><tbody></tbody></table></div>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin:24px 0 8px">
        <h2 class="h2 grow" style="margin:0">Look up a person or business</h2>
        <input class="sel" id="ow-q" type="search" placeholder="Last name first, business name or Sunbiz document number" aria-label="Search" style="min-width:320px">
      </div>
      <div id="ow-results"></div>
      <div id="ow-detail"></div>
    </section>

    <section id="tab-limits" class="pane" hidden>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin:0 0 8px">
        <h2 class="h2 grow" style="margin:0">Gifts over the $1,000 limit</h2>
        <select class="sel" id="ol-status" aria-label="Review status"><option value="">Any review status</option><option value="unreviewed">Unreviewed</option><option value="confirmed">Confirmed (open)</option><option value="resolved">Resolved</option><option value="rejected">Rejected</option></select>
      </div>
      <p class="small muted" style="margin:0 0 8px">One organization giving one candidate more than $1,000 in the same election, as the campaign reported it, net of refunds. The primary and general count separately. <b>Confirmed</b> publishes it as an open case. <b>Resolved</b> publishes it with your explanation and source (for example a reporting error by the campaign or the Supervisor of Elections, an amended report, a refund, a check designated for the general, or an Elections Commission ruling). <b>Rejected</b> keeps it private (not the same contributor, or a data mistake on our side).</p>
      <div class="tw"><table class="at" id="ol-cases" data-tt="off"><thead><tr><th class="pk"><input type="checkbox" data-bk-all aria-label="Select all shown"></th><th>Candidate</th><th>Contributor</th><th>Gifts as reported</th><th class="num">Net</th><th>Review</th></tr></thead><tbody></tbody></table></div>
    </section>

    <section id="tab-accounting" class="pane" hidden>
      <div class="row" style="margin-bottom:12px"><span class="grow"></span>
        <button class="btn" id="ac-norm-all" type="button">Normalize all new files</button><button class="btn" id="ac-refresh" type="button">Refresh</button></div>
      <p class="muted small" style="margin:0 0 12px">City and county ERP exports (New World, BS&amp;A, Springbrook) emailed to each government’s address at ingest.baycounty.me. Only senders on a source’s list are accepted. Every file also goes to its government’s private /finance workspace as an unreviewed import. Check registers are normalized into rows here; approved rows go to the public ledger. Budget and bank files stay in /finance only.</p>
      <div id="ac-banner"></div>
      <div class="tiles" id="ac-tiles"></div>
      <h3 class="h3">Sources</h3>
      <div class="tw"><table class="at" id="ac-sources" data-tt="off"><thead><tr><th>Government</th><th>System</th><th>Inbound address</th><th>/finance</th><th>Allowed senders</th><th class="num">Files</th><th>Last file</th><th class="num">Pending</th><th>Auto-normalize</th></tr></thead><tbody></tbody></table></div>
      <h3 class="h3">Files</h3>
      <div class="tw"><table class="at" id="ac-files" data-tt="off"><thead><tr><th>Received</th><th>Government</th><th>File</th><th>From</th><th>Status</th><th class="num">Rows</th><th>Review</th><th>/finance</th><th></th></tr></thead><tbody></tbody></table></div>
      <div class="row ac-qhead"><h3 class="h3 grow" style="margin:0">Review queue <span class="muted small" id="ac-qscope" style="font-weight:400"></span></h3>
        <select class="sel" id="ac-status" aria-label="Review status"><option value="pending" selected>Pending</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="all">All</option></select>
        <select class="sel" id="ac-source" aria-label="Government"><option value="">All governments</option></select></div>
      <div class="row ac-bulk" id="ac-bulk" hidden><span class="small" id="ac-picked">0 selected</span>
        <input class="sel grow" id="ac-note" maxlength="500" placeholder="Note (required to reject)" aria-label="Review note">
        <button class="btn danger" id="ac-reject" type="button">Reject selected</button><button class="btn primary" id="ac-approve" type="button">Approve selected</button></div>
      <div class="tw"><table class="at" id="ac-queue" data-tt="off"><thead><tr><th><input type="checkbox" id="ac-all" aria-label="Select all"></th><th>Date</th><th>Government</th><th>Fund</th><th>Account</th><th>Vendor</th><th>Description</th><th class="num">Amount</th><th>Status</th></tr></thead><tbody></tbody></table></div>
    </section>

    <section id="tab-boards" class="pane" hidden>
      <div class="banner"><div><b>Board members are public; the links on this tab are not.</b> <span class="small muted">Officers, directors and trustees of every county nonprofit, from IRS 990 returns (2019 on), 990-N postcards and state corporate filings (Sunbiz), grouped into people by name, are listed on the public Nonprofits page. The official name matches and Sunbiz business links here are leads: check the filing before confirming. Only officials you mark confirmed are tagged as officials on the public page.</span></div></div>
      <div class="tiles" id="bd-tiles"></div>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin:18px 0 8px">
        <h2 class="h2 grow" style="margin:0">Officials, department leaders and candidates on nonprofit boards</h2>
        <select class="sel" id="bd-status" aria-label="Review status"><option value="">Any review status</option><option value="unreviewed">Unreviewed</option><option value="confirmed">Confirmed</option><option value="rejected">Rejected</option></select>
      </div>
      <div class="tw"><table class="at" id="bd-officials" data-tt="off"><thead><tr><th class="pk"><input type="checkbox" data-bk-all aria-label="Select all shown"></th><th>Official</th><th>Board member as filed</th><th>Boards</th><th class="num">Same name in Sunbiz</th><th>Review</th></tr></thead><tbody></tbody></table></div>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin:24px 0 8px"><h2 class="h2 grow" style="margin:0">People on the most boards</h2></div>
      <div class="tw"><table class="at" id="bd-interlocks" data-tt="off"><thead><tr><th>Person</th><th class="num">Current boards (not HOAs)</th><th>Boards</th><th>Also</th></tr></thead><tbody></tbody></table></div>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin:24px 0 8px"><h2 class="h2 grow" style="margin:0">Board members who run businesses that gave to campaigns</h2></div>
      <p class="muted small" style="margin:0 0 8px">Matched by name to Sunbiz officers. "Same person" means the Sunbiz officer with that name and address is also on the nonprofit's own state filing; "same name" is a name match only, so check it.</p>
      <div class="tw"><table class="at" id="bd-donors" data-tt="off"><thead><tr><th>Person</th><th>Boards</th><th>Businesses that gave</th><th class="num">Gifts</th></tr></thead><tbody></tbody></table></div>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin:24px 0 8px">
        <h2 class="h2 grow" style="margin:0">Look up a person or nonprofit</h2>
        <input class="sel" id="bd-q" type="search" placeholder="Name, nonprofit name or EIN" aria-label="Search" style="min-width:320px">
      </div>
      <div id="bd-results"></div>
      <div id="bd-detail"></div>
    </section>
    </div>
    </div>
  </div>
</div>

<dialog id="ct-dialog"><form method="dialog" id="ct-form">
  <h2 id="ct-title">Contact</h2>
  <label class="f">Name<input name="name" maxlength="200"></label>
  <label class="f">Email<input type="email" name="email" maxlength="200" placeholder="Leave blank if there's no official address"></label>
  <label class="f">Where it's published<input type="url" name="source_url" maxlength="500" placeholder="https://"></label>
  <label class="f">Notes<textarea name="notes" maxlength="1000"></textarea></label>
  <label class="toggle"><input type="checkbox" name="active"> Can be written to</label>
  <p class="err" id="ct-err" role="alert"></p>
  <div class="row"><button class="btn primary" type="button" id="ct-save">Save</button><span class="grow"></span><button class="btn" value="cancel">Close</button></div>
</form></dialog>

<dialog id="co-confirm"><form method="dialog">
  <h2>Send this email?</h2>
  <p class="small" id="co-confirm-text" style="margin:0"></p>
  <div id="co-confirm-list" class="small" style="max-height:240px;overflow:auto"></div>
  <div class="row"><button class="btn primary" type="button" id="co-confirm-go">Send now</button><span class="grow"></span><button class="btn" value="cancel">Cancel</button></div>
</form></dialog>

<dialog id="rr-confirm"><form method="dialog">
  <h2>Send this records request?</h2>
  <p class="small" id="rr-confirm-text" style="margin:0"></p>
  <div class="row"><button class="btn primary" type="button" id="rr-confirm-go">Send now</button><span class="grow"></span><button class="btn" value="cancel">Cancel</button></div>
</form></dialog>

<dialog id="key-dialog"><form method="dialog" id="key-form">
  <h2 id="kd-title">New API key</h2>
  <div id="kd-secret" hidden><div class="note"><b>Copy this key now.</b> It's only shown once. Send it to the key's owner; we keep only a fingerprint of it.</div>
    <div class="secret" style="margin-top:10px"><code id="kd-secret-val"></code><button class="btn" type="button" id="kd-copy">Copy</button></div></div>
  <div id="kd-fields" style="display:flex;flex-direction:column;gap:12px">
    <label class="f">Name<input name="name" required maxlength="300" placeholder="What it's for, e.g. News Herald data desk"></label>
    <div class="grid2"><label class="f">Assigned to<input name="owner_name" maxlength="300" placeholder="Person"></label><label class="f">Their email<input type="email" name="owner_email" maxlength="300"></label></div>
    <label class="f">Organization<input name="organization" maxlength="300"></label>
    <div class="grid3"><label class="f">Per minute<input type="number" min="0" name="per_minute" placeholder="No limit"></label><label class="f">Per day<input type="number" min="0" name="per_day" placeholder="No limit"></label><label class="f">Expires<input type="date" name="expires_at"></label></div>
    <label class="f" id="kd-status-wrap" hidden>Status<select name="status"><option value="active">Active</option><option value="disabled">Paused</option><option value="revoked">Revoked (permanent)</option></select></label>
    <label class="f">Notes<textarea name="notes" maxlength="2000"></textarea></label>
  </div>
  <p class="err" id="kd-err" role="alert"></p>
  <div class="row">
    <button class="btn primary" type="button" id="kd-save">Create key</button>
    <button class="btn" type="button" id="kd-stats" hidden>Analytics</button>
    <button class="btn" type="button" id="kd-logs" hidden>Log</button>
    <button class="btn danger" type="button" id="kd-rotate" hidden>Replace key</button>
    <span class="grow"></span><button class="btn" value="cancel" id="kd-close">Close</button>
  </div>
</form></dialog>
<script src="/assets/admin.js?v={js_ver}" defer></script>
</body>
</html>
'''
    os.makedirs(os.path.join(out_dir, 'admin'), exist_ok=True)
    open(os.path.join(out_dir, 'admin', 'index.html'), 'w').write(html)
    import shutil
    shutil.copy(os.path.join(os.path.dirname(__file__), 'admin.js'), os.path.join(out_dir, 'assets', 'admin.js'))
