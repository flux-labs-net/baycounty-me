(async () => {
const [M, G, P1, P2] = await Promise.all(['/data/cra-meta.json','/data/cra-geo.json','/data/cra-pay-1.json','/data/cra-pay-2.json'].map(u => fetch(u).then(r => r.json())));
const D = Object.assign({}, M, G, {payments: P1.concat(P2)});


const CRA = {}; D.cras.forEach(c => CRA[c.id] = c);
const ORDER = ['pcb','pc','lh','cw','sf','pk'];
const SHORT = {pc:'Panama City',pcb:'Panama City Beach',lh:'Lynn Haven',cw:'Callaway',sf:'Springfield',pk:'Parker'};
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const colorVar = id => `var(--c-${id})`;
const fmt = (v, short) => {
  if (v == null) return '—';
  if (short){ const a=Math.abs(v);
    if (a>=1e6) return '$'+(v/1e6).toFixed(a>=1e7?1:2).replace(/\.0+$/,'')+'M';
    if (a>=1e3) return '$'+Math.round(v/1e3)+'K';
    return '$'+Math.round(v); }
  return '$'+Math.round(v).toLocaleString('en-US');
};
const esc = s => String(s??'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fyOf = s => { const m = String(s||'').match(/(19|20)\d{2}/); return m ? +m[0] : null; };

/* ---------- state ---------- */
const S = { cras:new Set(), status:'all', cat:'all', q:'', nc:true, sel:null, sortK:'when', sortDir:-1, showAll:false };
try { const saved = JSON.parse(localStorage.getItem('cra-filters')||'null'); if (saved){ S.status=saved.status||'all'; S.cat=saved.cat||'all'; S.nc=saved.nc!==false; (saved.cras||[]).forEach(c=>CRA[c]&&S.cras.add(c)); } } catch(e){}
const save = () => { try { localStorage.setItem('cra-filters', JSON.stringify({cras:[...S.cras],status:S.status,cat:S.cat,nc:S.nc})); } catch(e){} };

function filtered(){
  const q = S.q.toLowerCase();
  return D.payments.filter(p => {
    if (S.cras.size && !S.cras.has(p.cra)) return false;
    if (S.status !== 'all'){
      if (S.status === 'Other'){ if (!['Incoming','Not CRA-funded'].includes(p.status)) return false; }
      else if (p.status !== S.status) return false;
    }
    if (S.cat !== 'all' && p.cat !== S.cat) return false;
    if (!S.nc && !p.count) return false;
    if (q && !(p.payee+' '+p.purpose+' '+p.loc+' '+p.addr+' '+p.district+' '+SHORT[p.cra]).toLowerCase().includes(q)) return false;
    return true;
  });
}

/* ---------- KPIs ---------- */
function renderKPIs(rows){
  const counted = rows.filter(p => p.count && p.amount);
  const spent = counted.filter(p => p.status==='Spent' || p.status==='Committed').reduce((a,p)=>a+p.amount,0);
  const planned = counted.filter(p => p.status==='Budgeted').reduce((a,p)=>a+p.amount,0);
  const ids = S.cras.size ? [...S.cras] : ORDER;
  let tif = 0, tifN = 0; ids.forEach(id => { const s = D.tif[id]||[]; const r = s.find(x=>x[0]===2025); if (r){ tif += r[1]; tifN++; } });
  const named = new Set(counted.filter(p => !/not (named|stated)|various|^\d+ |owners? of|homeowners|businesses \(/i.test(p.payee)).map(p => p.payee)).size;
  document.getElementById('kpis').innerHTML = [
    ['Spent or committed', fmt(spent,true), 'Documented payments and awards, each dollar once'],
    ['Budgeted, not yet confirmed', fmt(planned,true), 'Appropriations and plan lines'],
    ['Records shown', rows.length.toLocaleString(), `${named} named payees`],
    ['FY2025 <span class=\"term\" data-term=\"tif\">tax increment</span>', fmt(tif,true), tifN===ids.length ? `${ids.length===6?'All six CRAs':ids.map(i=>SHORT[i]).join(', ')}` : 'Where reported'],
  ].map(([l,v,s]) => `<div class="kpi"><span class="eyebrow">${l}</span><span class="v">${v}</span><span class="s">${s}</span></div>`).join('');
}

/* ---------- filters UI ---------- */
function renderChips(){
  const el = document.getElementById('craChips');
  el.innerHTML = `<button type="button" class="chip" data-c="" aria-pressed="${S.cras.size===0}">All CRAs</button>` +
    ORDER.map(id => `<button type="button" class="chip" data-c="${id}" style="--dot:${colorVar(id)}" aria-pressed="${S.cras.has(id)}"><span class="dot"></span>${SHORT[id]}</button>`).join('');
}
document.getElementById('craChips').addEventListener('click', e => {
  const b = e.target.closest('.chip'); if (!b) return;
  const c = b.dataset.c;
  if (!c) S.cras.clear(); else if (S.cras.has(c)) S.cras.delete(c); else S.cras.add(c);
  S.sel = null; update(true);
});
const cats = [...new Set(D.payments.map(p=>p.cat))].sort();
document.getElementById('fCat').innerHTML += cats.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');
const fStatus = document.getElementById('fStatus'), fCat = document.getElementById('fCat'), fQ = document.getElementById('fQ'), fNC = document.getElementById('fNC');
fStatus.value = S.status; fCat.value = S.cat; fNC.checked = S.nc;
fStatus.onchange = () => { S.status = fStatus.value; update(); };
fCat.onchange = () => { S.cat = fCat.value; update(); };
fQ.oninput = () => { S.q = fQ.value; update(); };
fNC.onchange = () => { S.nc = fNC.checked; update(); };
document.getElementById('resetAll').onclick = () => { S.cras.clear(); S.status='all'; S.cat='all'; S.q=''; S.nc=true; S.sel=null;
  fStatus.value='all'; fCat.value='all'; fQ.value=''; fNC.checked=true; update(true); };

/* ---------- map ---------- */
const svg = document.getElementById('map'), NS = 'http://www.w3.org/2000/svg';
const LNG0 = -86.05, LAT0 = 30.62, KX = Math.cos(30.2*Math.PI/180)*1000, KY = 1000;
const px = (lng,lat) => [(lng-LNG0)*KX, (LAT0-lat)*KY];
const pathOf = polys => polys.map(poly => poly.map(ring => 'M'+ring.map(([x,y]) => px(x,y).map(v=>v.toFixed(1)).join(',')).join('L')+'Z').join('')).join('');
function el(tag, attrs, parent){ const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }

const gBase = el('g', {}, svg), gDist = el('g', {}, svg), gLbl = el('g', {}, svg), gPins = el('g', {}, svg);
el('path', {d: pathOf(D.land), class:'land'}, gBase);
Object.entries(D.cities).forEach(([n, g]) => el('path', {d: pathOf(g), class:'city'}, gBase));
el('path', {d: pathOf(D.county), class:'county'}, gBase);
const distEls = D.districts.map(d => {
  const p = el('path', {d: pathOf(d.geom), class:'dist', style:`--dc:${colorVar(d.cra)}`}, gDist);
  const t = el('title', {}, p); t.textContent = `${d.name} · est. ${d.est} · ~${d.acres.toLocaleString()} acres`;
  p.addEventListener('click', () => { S.cras = new Set([d.cra]); S.sel = null; update(true); });
  return {d, p};
});
// city labels
const LBL = [['Panama City',-85.662,30.183,1],['Lynn Haven',-85.648,30.262,1],['Panama City Beach',-85.83,30.215,1],['Callaway',-85.565,30.135,1],['Springfield',-85.600,30.185,0],['Parker',-85.598,30.118,0],['Mexico Beach',-85.42,29.95,0],['St. Andrew Bay',-85.70,30.12,0],['Gulf of Mexico',-85.80,30.05,0],['North Bay',-85.70,30.235,0]];
const lblEls = LBL.map(([t,lng,lat,big]) => { const [x,y] = px(lng,lat); const e = el('text', {x, y, class:'lbl'+(big?' big':''), 'text-anchor':'middle'}, gLbl); e.textContent = t; return {e, big}; });

const maxAmt = Math.max(...D.payments.map(p=>p.amount||0));
let VB = {x:0,y:0,w:100,h:100};
function setVB(v){ VB = v; svg.setAttribute('viewBox', `${v.x} ${v.y} ${v.w} ${v.h}`); scaleMarks(); }
function unitsPerPx(){ const r = svg.getBoundingClientRect(); return Math.max(VB.w / r.width, VB.h / r.height) || 1; }
function scaleMarks(){
  const u = unitsPerPx();
  pinEls.forEach(({p, e}) => e.setAttribute('r', (p.amount ? 3.5 + 17*Math.sqrt(p.amount/maxAmt) : 3.5) * u));
  lblEls.forEach(({e,big}) => { e.style.fontSize = (big?12.5:11)*u+'px'; e.style.strokeWidth = 3*u+'px'; });
}
function fitTo(points, pad=0.18){
  const r = svg.getBoundingClientRect(); const ar = (r.width||800)/(r.height||520);
  let [x0,y0,x1,y1] = [Infinity,Infinity,-Infinity,-Infinity];
  points.forEach(([x,y]) => { x0=Math.min(x0,x); y0=Math.min(y0,y); x1=Math.max(x1,x); y1=Math.max(y1,y); });
  if (!isFinite(x0)) return;
  let w = Math.max(x1-x0, 30), h = Math.max(y1-y0, 30);
  w *= 1+pad*2; h *= 1+pad*2;
  if (w/h > ar) h = w/ar; else w = h*ar;
  setVB({x:(x0+x1)/2-w/2, y:(y0+y1)/2-h/2, w, h});
}
function distPoints(ids){
  const pts = [];
  D.districts.filter(d => !ids || ids.has(d.cra)).forEach(d => d.geom.forEach(poly => poly[0].forEach(([x,y]) => pts.push(px(x,y)))));
  return pts;
}

let pinEls = [];
function renderPins(rows){
  gPins.innerHTML = '';
  const sorted = [...rows].sort((a,b) => (b.amount||0)-(a.amount||0));
  pinEls = sorted.map(p => {
    const [x,y] = px(p.lng, p.lat);
    const cls = 'pin' + (!p.count ? ' nocount' : (['Budgeted','Proposed'].includes(p.status) ? ' hollow' : '')) + (S.sel===p.id?' sel':'');
    const e = el('circle', {cx:x, cy:y, r:4, class:cls, style:`--pc:${colorVar(p.cra)}`, tabindex:0, role:'button', 'aria-label':`${fmt(p.amount)} ${p.payee}`}, gPins);
    e.addEventListener('mouseenter', ev => showTip(ev, p));
    e.addEventListener('mousemove', ev => moveTip(ev));
    e.addEventListener('mouseleave', hideTip);
    e.addEventListener('click', ev => { ev.stopPropagation(); select(p.id); });
    e.addEventListener('keydown', ev => { if (ev.key==='Enter' || ev.key===' '){ ev.preventDefault(); select(p.id); } });
    return {p, e};
  });
  distEls.forEach(({d,p}) => p.classList.toggle('dim', S.cras.size>0 && !S.cras.has(d.cra)));
  scaleMarks();
}

const tip = document.getElementById('tip'), mapbox = document.getElementById('mapbox');
function showTip(ev, p){ tip.innerHTML = `<b>${fmt(p.amount)}</b> · ${esc(p.status)}<br>${esc(p.payee)}<br><span class="muted">${esc(p.purpose.slice(0,110))}${p.purpose.length>110?'…':''}</span>`; tip.hidden=false; moveTip(ev); }
function moveTip(ev){ const r = mapbox.getBoundingClientRect(); let x = ev.clientX-r.left+14, y = ev.clientY-r.top+14;
  if (x+270 > r.width) x = ev.clientX-r.left-274; if (y+120 > r.height) y = ev.clientY-r.top-120; tip.style.left = Math.max(4,x)+'px'; tip.style.top = Math.max(4,y)+'px'; }
function hideTip(){ tip.hidden = true; }

// pan + zoom
let drag = null;
function zoomAt(f, cx, cy){ const r = svg.getBoundingClientRect();
  const mx = VB.x + (cx - r.left)/r.width*VB.w, my = VB.y + (cy - r.top)/r.height*VB.h;
  const w = Math.min(Math.max(VB.w*f, 12), 1400), h = w*VB.h/VB.w;
  setVB({x: mx-(mx-VB.x)*w/VB.w, y: my-(my-VB.y)*h/VB.h, w, h}); }
svg.addEventListener('wheel', e => { e.preventDefault(); zoomAt(e.deltaY>0?1.18:1/1.18, e.clientX, e.clientY); }, {passive:false});
const ptrs = new Map(); let pinch = null;
svg.addEventListener('pointerdown', e => { ptrs.set(e.pointerId, e); if (ptrs.size===1){ drag = {x:e.clientX, y:e.clientY, vb:{...VB}, moved:false}; } else if (ptrs.size===2){ const [a,b]=[...ptrs.values()]; pinch = {d:Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY), vb:{...VB}}; drag=null; } });
svg.addEventListener('pointermove', e => {
  if (!ptrs.has(e.pointerId)) return; ptrs.set(e.pointerId, e);
  if (pinch && ptrs.size===2){ const [a,b]=[...ptrs.values()]; const d = Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY);
    const cx=(a.clientX+b.clientX)/2, cy=(a.clientY+b.clientY)/2; setVB({...pinch.vb}); zoomAt(pinch.d/d, cx, cy); return; }
  if (!drag) return; const r = svg.getBoundingClientRect(); const dx = e.clientX-drag.x, dy = e.clientY-drag.y;
  if (Math.abs(dx)+Math.abs(dy) > 3){ drag.moved = true; svg.classList.add('dragging'); if (!svg.hasPointerCapture(e.pointerId)) svg.setPointerCapture(e.pointerId); }
  if (drag.moved) setVB({x: drag.vb.x - dx/r.width*drag.vb.w, y: drag.vb.y - dy/r.height*drag.vb.h, w: drag.vb.w, h: drag.vb.h}); });
const endPtr = e => { ptrs.delete(e.pointerId); if (ptrs.size<2) pinch=null; if (!ptrs.size){ drag=null; svg.classList.remove('dragging'); } };
svg.addEventListener('pointerup', endPtr); svg.addEventListener('pointercancel', endPtr);
document.getElementById('zin').onclick = () => { const r = svg.getBoundingClientRect(); zoomAt(1/1.5, r.left+r.width/2, r.top+r.height/2); };
document.getElementById('zout').onclick = () => { const r = svg.getBoundingClientRect(); zoomAt(1.5, r.left+r.width/2, r.top+r.height/2); };
document.getElementById('zfit').onclick = () => fitView();
function fitView(){ fitTo(distPoints(S.cras.size ? S.cras : null), S.cras.size ? 0.12 : 0.04); }
new ResizeObserver(() => { const keep = {...VB}; if (keep.w>0) setVB(keep); }).observe(mapbox);

function renderLegend(){
  const ring = (cls, extra='') => `<svg width="16" height="16" viewBox="0 0 16 16"><circle cx="8" cy="8" r="5.5" ${extra}/></svg>`;
  document.getElementById('legend').innerHTML =
    `<div class="row">${ring('', `fill="${css('--muted')}" stroke="${css('--surface')}"`)}Spent or committed</div>` +
    `<div class="row">${ring('', `fill="${css('--surface')}" stroke="${css('--muted')}" stroke-width="2"`)}Budgeted or proposed</div>` +
    `<div class="row">${ring('', `fill="none" stroke="${css('--muted')}" stroke-width="1.4" stroke-dasharray="3 2"`)}Left out of totals</div>` +
    `<div class="row">Circle area = amount</div>`;
}

/* ---------- rail ---------- */
function renderRail(rows){
  const rail = document.getElementById('rail');
  if (S.sel != null){
    const p = D.payments[S.sel];
    rail.innerHTML = `<button class="back" type="button" id="back">← Largest items</button>
      <div class="detail">
        <span class="eyebrow"><span class="cradot" style="--dot:${colorVar(p.cra)}"></span>${esc(SHORT[p.cra])} · ${esc(p.district||'')}</span>
        <span class="amt">${p.amount!=null?fmt(p.amount):'Amount not found'}</span>
        <span><span class="pill st-${p.status.replace(/[^A-Za-z]/g,'').replace('NotCRAfunded','NotCRA')}">${esc(p.status)}</span> <span class="muted" style="font-size:.78rem">${esc(p.conf)}</span></span>
        <dl>
          <dt>Paid to</dt><dd>${esc(p.payee)}</dd>
          <dt>For</dt><dd>${esc(p.purpose)}</dd>
          <dt>When</dt><dd>${esc(p.when||'—')}</dd>
          <dt>Where</dt><dd>${esc(p.loc||p.addr||'—')}${p.addr && p.loc ? `<br><span class="muted">${esc(p.addr)}</span>`:''}${p.placed==='district'?'<br><span class="muted">Pinned at district center</span>':(p.prec==='approximate'?'<br><span class="muted">Approximate location</span>':'')}</dd>
          <dt>Type</dt><dd>${esc(p.cat)}</dd>
          <dt>Source</dt><dd>${p.url?`<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.src||'Source')}</a>`:esc(p.src||'—')}</dd>
        </dl>
        ${!p.count ? `<div class="note"><b>Not in totals.</b> ${esc(p.overlap || (p.amount==null?'No amount found.':''))}</div>`:''}
        ${p.notes ? `<div class="note">${esc(p.notes)}</div>`:''}
      </div>`;
    document.getElementById('back').onclick = () => { S.sel = null; update(); };
    return;
  }
  const top = rows.filter(p => p.count && p.amount).sort((a,b)=>b.amount-a.amount).slice(0,12);
  const ids = S.cras.size ? [...S.cras] : null;
  rail.innerHTML = `<div><span class="eyebrow">Largest items${ids?` · ${ids.map(i=>SHORT[i]).join(', ')}`:' · all CRAs'}</span></div>
    ${top.length ? `<ol class="toplist">${top.map(p => `<li data-id="${p.id}" tabindex="0"><span class="d" style="--dot:${colorVar(p.cra)}"></span>
      <span class="t">${esc(p.purpose.length>80?p.purpose.slice(0,78)+'…':p.purpose)}<small>${esc(p.payee.length>60?p.payee.slice(0,58)+'…':p.payee)} · ${esc(p.status)}</small></span>
      <span class="a">${fmt(p.amount,true)}</span></li>`).join('')}</ol>` : '<p class="muted">No counted records match these filters.</p>'}
    <p class="muted" style="font-size:.78rem">Click a pin or a row for the record, its source, and notes.</p>`;
  rail.querySelectorAll('li').forEach(li => { li.onclick = () => select(+li.dataset.id); li.onkeydown = e => { if (e.key==='Enter') select(+li.dataset.id); }; });
}
function select(id){
  S.sel = id; const p = D.payments[id];
  update();
  const [x,y] = px(p.lng,p.lat);
  if (x < VB.x || x > VB.x+VB.w || y < VB.y || y > VB.y+VB.h){ setVB({x:x-VB.w/2, y:y-VB.h/2, w:VB.w, h:VB.h}); }
  if (window.innerWidth <= 980) document.getElementById('rail').scrollIntoView({behavior:'smooth', block:'nearest'});
}

/* ---------- profiles ---------- */
function spark(id){
  const s = (D.tif[id]||[]).filter(r => r[1]!=null); if (s.length<2) return '<svg class="spark"></svg>';
  const W=300,H=46,P=4; const x0=s[0][0], x1=s[s.length-1][0], ymax=Math.max(...s.map(r=>r[1]))||1;
  const X = y => P+(y-x0)/(x1-x0||1)*(W-2*P), Y = v => H-P-(v/ymax)*(H-2*P-6);
  const line = s.map((r,i)=>`${i?'L':'M'}${X(r[0]).toFixed(1)},${Y(r[1]).toFixed(1)}`).join('');
  const area = line + `L${X(x1).toFixed(1)},${H-P}L${X(x0).toFixed(1)},${H-P}Z`;
  const last = s[s.length-1];
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-label="Tax increment ${x0} to ${x1}">
    <line x1="${P}" x2="${W-P}" y1="${H-P}" y2="${H-P}" stroke="var(--line)" stroke-width="1"/>
    <path d="${area}" fill="${colorVar(id)}" fill-opacity=".14"/>
    <path d="${line}" fill="none" stroke="${colorVar(id)}" stroke-width="2" vector-effect="non-scaling-stroke"/>
    <circle cx="${X(last[0])}" cy="${Y(last[1])}" r="3" fill="${colorVar(id)}"/></svg>`;
}
function renderProfiles(){
  document.getElementById('profiles').innerHTML = ORDER.map(id => {
    const c = CRA[id]; const rows = D.payments.filter(p=>p.cra===id);
    const spent = rows.filter(p=>p.count&&p.amount&&(p.status==='Spent'||p.status==='Committed')).reduce((a,p)=>a+p.amount,0);
    const s = D.tif[id]||[]; const last = s.filter(r=>r[1]!=null).slice(-1)[0];
    const nd = new Set(D.districts.filter(d=>d.cra===id).map(d=>d.key)).size;
    const yrs = s.length ? `${s[0][0]}–${s[s.length-1][0]}` : '';
    return `<button type="button" class="prof" data-c="${id}" style="--dot:${colorVar(id)}" aria-pressed="${S.cras.has(id)}">
      <div class="hd"><h3>${esc(SHORT[id])}</h3><span class="eyebrow">Est. ${esc(String(c.created||'').match(/\d{4}/)?.[0]||'—')}</span></div>
      <div class="stats">
        <div><b>${last?fmt(last[1],true):'—'}</b><span>FY${last?last[0]:''} increment</span></div>
        <div><b>${fmt(spent,true)}</b><span>Spent/committed found</span></div>
        <div><b>${rows.length}</b><span>${nd} district${nd>1?'s':''} · records</span></div>
      </div>
      ${spark(id)}
      <span class="muted" style="font-size:.7rem;margin-top:-6px">Tax increment, FY${yrs.replace('–','–FY')}</span>
      <p>${esc(c.overview)}</p></button>`;
  }).join('');
  document.querySelectorAll('.prof').forEach(b => b.onclick = () => { S.cras = new Set([b.dataset.c]); S.sel=null; update(true);
    document.getElementById('mapbox').scrollIntoView({behavior:'smooth', block:'start'}); });
}

/* ---------- ledger ---------- */
const STATUS_RANK = {Spent:0, Committed:1, Budgeted:2, Proposed:3, Incoming:4, 'Not CRA-funded':5};
function renderLedger(rows){
  const k = S.sortK, d = S.sortDir;
  // the chosen column, then newest first, then payee A to Z
  const typ = k==='amount'||k==='status' ? 'num' : k==='when' ? 'date' : 'text';
  const get = p => k==='amount' ? p.amount : k==='when' ? p.when : k==='status' ? STATUS_RANK[p.status] : k==='where' ? SHORT[p.cra]+' '+(p.district||'') : (p[k]||'');
  const sorted = TT.sortBy(rows, [{get, type:typ, dir:d<0?'desc':'asc'}, {get:p=>p.when, type:'date', dir:'desc'}, {get:p=>p.payee, type:'text', dir:'asc'}]);
  S.lastSorted = sorted;
  const lim = S.showAll ? sorted.length : 60;
  document.querySelector('#ledger tbody').innerHTML = sorted.slice(0,lim).map(p => `<tr data-id="${p.id}" class="${p.count?'':'nc'}" ${!p.count&&p.overlap?`title="Not in totals: ${esc(p.overlap)}"`:''}>
    <td class="amt">${p.amount!=null?fmt(p.amount):'—'}</td>
    <td>${esc(p.payee)}</td>
    <td>${esc(p.purpose)}<span class="sub">${esc(p.cat)}</span></td>
    <td><span class="cradot" style="--dot:${colorVar(p.cra)}"></span>${esc(SHORT[p.cra])}<span class="sub">${esc(p.loc||p.district||'')}</span></td>
    <td>${esc(p.when||'—')}</td>
    <td><span class="pill st-${p.status.replace(/[^A-Za-z]/g,'').replace('NotCRAfunded','NotCRA')}">${esc(p.status)}</span></td>
    <td>${p.url?`<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.conf==='News report'?'News':'Record')}</a>`:'—'}</td></tr>`).join('');
  const more = document.getElementById('more'); more.hidden = sorted.length <= 60 || S.showAll; more.textContent = `Show all ${sorted.length} rows`;
  document.getElementById('ledgerCount').textContent = `${rows.length} records · struck-through rows are left out of totals`;
  document.querySelectorAll('#ledger thead th').forEach(th => { if (th.dataset.k===k) th.setAttribute('aria-sort', d<0?'descending':'ascending'); else th.removeAttribute('aria-sort'); });
  document.querySelectorAll('#ledger tbody tr').forEach(tr => tr.onclick = e => { if (e.target.closest('a')) return; select(+tr.dataset.id); document.getElementById('mapbox').scrollIntoView({behavior:'smooth', block:'start'}); });
}
TT.attach(document.getElementById('ledger'), {cols:[{key:'amount',type:'num'},{key:'payee',type:'text'},{key:'purpose',type:'text'},{key:'where',type:'text'},{key:'when',type:'date'},{key:'status',type:'text'},null],
  sort:{key:S.sortK, dir:S.sortDir<0?'desc':'asc'}, onSort: s => { S.sortK = s.key; S.sortDir = s.dir==='desc' ? -1 : 1; renderLedger(filtered()); }});
document.getElementById('more').onclick = () => { S.showAll = true; renderLedger(filtered()); };

/* ---------- context ---------- */
function renderCtx(){
  document.getElementById('ctx').innerHTML = ORDER.map(id => {
    const cs = D.controversies.filter(x=>x.cra===id), gs = D.gaps.filter(x=>x.cra===id);
    return `<details class="cx" style="--dot:${colorVar(id)}"><summary><span class="cradot"></span>${esc(SHORT[id])}<span class="muted" style="font-weight:400;font-size:.8rem">${cs.length} issue${cs.length!==1?'s':''} · ${gs.length} gap${gs.length!==1?'s':''}</span></summary>
      ${cs.length?`<h4>Controversies and findings</h4><ul>${cs.map(x=>`<li>${esc(x.text)}${x.url?` <a href="${esc(x.url)}" target="_blank" rel="noopener">Source</a>`:''}</li>`).join('')}</ul>`:''}
      ${gs.length?`<h4>What's not public online</h4><ul>${gs.map(x=>`<li>${esc(x.text)}</li>`).join('')}</ul>`:''}
    </details>`;
  }).join('');
}

/* ---------- update ---------- */
function update(refit){
  save();
  renderChips();
  const rows = filtered();
  renderKPIs(rows); renderPins(rows); renderRail(rows); renderLedger(rows);
  document.querySelectorAll('.prof').forEach(b => b.setAttribute('aria-pressed', S.cras.has(b.dataset.c)));
  if (refit) fitView();
}
renderProfiles(); renderCtx(); renderLegend();
requestAnimationFrame(() => update(true));
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', renderLegend);
new MutationObserver(renderLegend).observe(document.documentElement, {attributes:true, attributeFilter:['data-theme']});

document.getElementById('csv').onclick = () => {
  const cols = ['CRA','District','Amount','Paid to','For what','Type','When','Status','Counted in totals','Why not counted','Location','Source type','Source','Notes'];
  const q = v => { v = v == null ? '' : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
  const rows = (S.lastSorted || filtered()).map(p => [CRA[p.cra].name, p.district, p.amount, p.payee, p.purpose, p.cat, p.when, p.status, p.count ? 'Yes' : 'No', p.overlap, p.loc || p.addr, p.conf, p.url, p.notes].map(q).join(','));
  const blob = new Blob(['\ufeff' + cols.join(',') + '\n' + rows.join('\n')], {type: 'text/csv;charset=utf-8'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'bay-county-cra-ledger.csv'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
};

const STATUS_LABEL = {Other:'Incoming / not CRA-funded'};
function filterSummary(){
  const parts = [S.cras.size ? [...S.cras].map(i=>SHORT[i]).join(', ') : 'All six CRAs'];
  if (S.status !== 'all') parts.push('Status: ' + (STATUS_LABEL[S.status] || S.status));
  if (S.cat !== 'all') parts.push('Type: ' + S.cat);
  if (S.q) parts.push('Search: "' + S.q + '"');
  if (!S.nc) parts.push('Rows left out of totals hidden');
  return parts.join(' · ');
}
let printState = null;
function beforePrint(){
  if (printState) return;
  printState = {showAll: S.showAll, open: [...document.querySelectorAll('details.cx')].map(d => d.open), vb: {...VB}};
  S.showAll = true; renderLedger(filtered());
  document.querySelectorAll('details.cx').forEach((d, i) => { d.open = true; d.classList.toggle('print-hide', S.cras.size > 0 && !S.cras.has(ORDER[i])); });
  document.querySelectorAll('.prof').forEach(b => b.classList.toggle('print-hide', S.cras.size > 0 && !S.cras.has(b.dataset.c)));
  const day = new Date().toLocaleDateString('en-US', {year:'numeric', month:'long', day:'numeric'});
  document.getElementById('printMeta').innerHTML = '<b>Report:</b> ' + esc(filterSummary()) + '<br><b>Exported</b> ' + day + ' from baycounty.me/public-money/cra-spending';
  fitView();
}
function afterPrint(){
  if (!printState) return;
  S.showAll = printState.showAll; renderLedger(filtered());
  document.querySelectorAll('details.cx').forEach((d, i) => d.open = printState.open[i]);
  document.querySelectorAll('.print-hide').forEach(e => e.classList.remove('print-hide'));
  setVB(printState.vb); printState = null;
}
window.addEventListener('beforeprint', beforePrint);
window.addEventListener('afterprint', afterPrint);
window.BCReportBefore = beforePrint;
window.BCReportAfter = afterPrint;
window.BCReportMeta = () => 'Report: ' + filterSummary();

})();
