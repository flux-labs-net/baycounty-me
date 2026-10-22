/* BayCounty.me PDF reports.
   Turns the page that's on screen into a designed PDF (pdfmake): branded header and
   footer, title block, KPI tiles, real tables, bar charts and vector maps, live links.
   Any button with class "pdf-btn" and id "pdf" (or data-pdf) triggers it. Elements
   with data-report="skip" are left out. */
(() => {
const PDFMAKE = 'https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.10/pdfmake.min.js';
const VFS = 'https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.10/vfs_fonts.min.js';
const C = {navy: '#1E3A76', blue: '#3F6FB0', salmon: '#E5564A', amber: '#FFB84D', ink: '#161B24', muted: '#5A6372', faint: '#8A93A1', line: '#E1E6ED', sunken: '#EEF2F7', bg: '#F6F8FB'};
const LIGHT = {bg: '#F6F8FB', surface: '#FFFFFF', sunken: '#EEF2F7', ink: '#161B24', muted: '#5A6372', faint: '#8A93A1', line: '#E1E6ED', navy: '#1E3A76', blue: '#3F6FB0', salmon: '#E5564A', amber: '#FFB84D',
  water: '#C9DCEF', land: '#FBFCFD', landline: '#AFC2D8', city: '#EEF1F5', cityline: '#CDD6E1', s1: '#2a78d6', s2: '#eb6834', s3: '#1baf7a', s4: '#eda100', s5: '#e87ba4',
  'c-pc': '#3F6FB0', 'c-pcb': '#E5564A', 'c-lh': '#D18A1E', 'c-cw': '#22897C', 'c-sf': '#7B5FBF', 'c-pk': '#2F95C4', good: '#1F7A4D', warn: '#A86A00', none: '#8A93A1', gap: '#FFFFFF'};
const W = 532; // content width on Letter with 40pt margins

function load(src) { return new Promise((res, rej) => { const s = document.createElement('script'); s.src = src; s.onload = res; s.onerror = () => rej(new Error('load ' + src)); document.head.appendChild(s); }); }
async function ready() { if (!window.pdfMake) await load(PDFMAKE); if (!window.pdfMake.vfs || !Object.keys(window.pdfMake.vfs).length) await load(VFS); }

/* ---------- colors ---------- */
function resolve(v) {
  if (!v) return null;
  v = String(v).trim();
  let m = v.match(/^var\(--([\w-]+)\)$/); if (m) return LIGHT[m[1]] || getComputedStyle(document.documentElement).getPropertyValue('--' + m[1]).trim() || C.blue;
  m = v.match(/^color-mix\(in srgb,\s*(var\(--[\w-]+\)|#[0-9a-f]+)\s+(\d+)%,\s*(transparent|var\(--[\w-]+\)|#[0-9a-f]+)\)$/i);
  if (m) return m[3] === 'transparent' ? resolve(m[1]) : mix(resolve(m[1]), resolve(m[3]), +m[2] / 100);
  return v;
}
function rgb2hex(v) { const m = v.match(/rgba?\(([^)]+)\)/); if (!m) return v; const p = m[1].split(',').map(x => parseFloat(x)); if (p.length === 4 && p[3] === 0) return 'none'; return '#' + p.slice(0, 3).map(x => Math.round(x).toString(16).padStart(2, '0')).join(''); }
function hex(c) { c = c.replace('#', ''); if (c.length === 3) c = c.split('').map(x => x + x).join(''); return [0, 2, 4].map(i => parseInt(c.slice(i, i + 2), 16)); }
function mix(a, b, p) { try { const x = hex(a), y = hex(b); return '#' + x.map((v, i) => Math.round(v * p + y[i] * (1 - p)).toString(16).padStart(2, '0')).join(''); } catch (e) { return a; } }
function bgOf(el) { const s = el.getAttribute('style') || ''; const m = s.match(/background(?:-color)?:\s*([^;]+)/); return m ? resolve(m[1]) : null; }
function pct(el, prop) { const s = el.getAttribute('style') || ''; const m = s.match(new RegExp(prop + ':\\s*([\\d.]+)%')); return m ? +m[1] / 100 : 0; }

/* ---------- inline text ---------- */
const abs = h => { try { return new URL(h, location.href).href; } catch (e) { return h; } };
function inline(el, base = {}) {
  const out = [];
  el.childNodes.forEach(n => {
    if (n.nodeType === 3) { const t = n.textContent.replace(/\s+/g, ' ').replace(/\s*[\u2192\u2197\u2190]/g, '').replace(/[\u2713\u2714]\s*/g, ''); if (t) out.push({text: t, ...base}); return; }
    if (n.nodeType !== 1 || skip(n, true)) return;
    const tag = n.tagName, cls = n.classList, st = {...base};
    if (tag === 'BR') { out.push({text: '\n'}); return; }
    if (tag === 'SVG' || tag === 'BUTTON' || tag === 'INPUT' || tag === 'SELECT') return;
    if (tag === 'B' || tag === 'STRONG' || tag === 'TH') st.bold = true;
    if (tag === 'EM' || tag === 'I') { if (!cls.length) st.italics = true; else st.color = C.muted; }
    if (tag === 'SMALL' || cls.contains('muted') || cls.contains('small') || cls.contains('src') || cls.contains('r-s')) st.color = C.muted;
    if (tag === 'MARK') st.background = '#FFE6B3';
    if (tag === 'A' && n.getAttribute('href') && !n.getAttribute('href').startsWith('#')) { st.link = abs(n.getAttribute('href')); st.color = C.blue; }
    if (cls.contains('badge')) { out.push({text: ' ' + n.textContent.replace(/^[\u2713!]\s*/, '').trim() + ' ', fontSize: 7, color: cls.contains('warn') ? '#A86A00' : cls.contains('ok') ? '#1F7A4D' : C.muted, bold: true}); return; }
    if (tag === 'I' && !n.textContent.trim()) { const c = bgOf(n); if (c) out.push({text: '\u2022 ', color: c, fontSize: 11, lineHeight: .8}); return; }
    out.push(...inline(n, st));
    const dsp = getComputedStyle(n).display;
    if (/^(block|flex|grid|list-item)$/.test(dsp) && out.length && !/\n$/.test(out[out.length - 1].text || '')) out.push({text: '\n'});
  });
  return out;
}
const textOf = el => el.textContent.replace(/\s+/g, ' ').trim();
function clean(runs) { while (runs.length && /^\s*$/.test(runs[runs.length - 1].text || 'x')) runs.pop(); while (runs.length && typeof runs[0].text === 'string' && !runs[0].text.trim()) runs.shift(); if (runs[0]) runs[0] = {...runs[0], text: runs[0].text.replace(/^\s+/, '')}; return runs; }

/* ---------- what to leave out ---------- */
const SKIP = '.stamp,.pdf-btn,.print-hide,.addr-hd,.tt,.filters-row,.pills,.addr-search,.home-search,.ac-list,.menu-btn,.theme-btn,script,style,noscript,button:not(.prof),input,.filters,.maptools,.tip,.rail,#more,#csv,.prof p,select,form,.print-meta,.skip,.term-pop,#ledMore,.addr-act,[data-report="skip"]';
function skip(el, inInline) {
  if (el.matches && el.matches(SKIP)) return true;
  if (el.hidden) return true;
  if (!inInline && el.getClientRects && el.getClientRects().length === 0 && el.tagName !== 'DETAILS' && !el.closest('details:not([open])')) return true;
  return false;
}

/* ---------- blocks ---------- */
let MAXW = 532;
const SVGP = ['fill', 'stroke', 'stroke-width', 'opacity', 'fill-opacity', 'stroke-opacity', 'stroke-dasharray', 'font-size', 'font-weight', 'text-anchor'];
function svgNode(svg, maxW) {
  maxW = Math.min(maxW, MAXW);
  const c = svg.cloneNode(true);
  const src = [svg, ...svg.querySelectorAll('*')], dst = [c, ...c.querySelectorAll('*')];
  src.forEach((el, i) => { const d = dst[i]; if (!d || el.tagName === 'svg') return; const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') { d.setAttribute('data-x', '1'); return; }
    SVGP.forEach(pr => { const v = cs.getPropertyValue(pr); if (v && v !== 'none' || pr === 'fill' || pr === 'stroke') d.setAttribute(pr, v.startsWith('rgb') ? rgb2hex(v) : v); });
    d.removeAttribute('class'); d.removeAttribute('style'); });
  c.querySelectorAll('[data-x]').forEach(x => x.remove());
  const vb = (svg.getAttribute('viewBox') || '').split(/[\s,]+/).map(Number);
  const vw = vb[2] || svg.clientWidth || 400, vh = vb[3] || svg.clientHeight || 260;
  c.setAttribute('width', vw); c.setAttribute('height', vh); c.removeAttribute('style'); c.removeAttribute('class');
  let s = new XMLSerializer().serializeToString(c);
  s = s.replace(/(fill|stroke)="([^"]+)"/g, (m, a, v) => `${a}="${resolve(v)}"`)
       .replace(/style="[^"]*paint-order[^"]*"/g, 'stroke="#FFFFFF" stroke-width="2.5" paint-order="stroke"')
       .replace(/var\(--([\w-]+)\)/g, (m, k) => LIGHT[k] || C.blue)
       .replace(/<title>.*?<\/title>/g, '');
  const w = Math.min(maxW, vw * 1.4);
  return {svg: s, width: w, margin: [0, 4, 0, 6]};
}
function bar(frac, color, w = 170, h = 7) {
  return {canvas: [{type: 'rect', x: 0, y: 0, w, h, color: '#EEF2F7', r: 2}, {type: 'rect', x: 0, y: 0, w: Math.max(1, w * Math.min(1, frac)), h, color: color || C.blue, r: 2}], margin: [0, 3, 0, 0]};
}
function stackMini(sb, w = 150, h = 7) { // a bar made of colored segments (e.g. water / sewer / garbage)
  const tot = w * Math.min(1, pct(sb, 'width') || 1), segs = [...sb.querySelectorAll('.seg')].map(x => { const st = x.getAttribute('style') || ''; return [+((st.match(/flex:\s*([\d.]+)/) || [])[1] || 0), bgOf(x) || C.blue]; });
  const sum = segs.reduce((a, [v]) => a + v, 0) || 1; let x = 0;
  return {canvas: [{type: 'rect', x: 0, y: 0, w, h, color: '#EEF2F7', r: 2}, ...segs.map(([v, c]) => { const ww = tot * v / sum, o = {type: 'rect', x, y: 0, w: Math.max(.5, ww), h, color: c}; x += ww; return o; })], margin: [0, 3, 0, 0]};
}
function hbars(el) {
  const BW = MAXW < 400 ? 70 : 150;
  const rows = [...el.querySelectorAll(':scope > .hb')].filter(r => !skip(r)).map(r => {
    const b = r.querySelector('.hb-bar'), n = r.querySelector('.hb-n'), v = r.querySelector('.hb-v');
    const sb = !b && r.querySelector('.stackbar');
    return [{text: clean(inline(n)), fontSize: 8}, sb ? stackMini(sb, BW) : bar(b ? pct(b, 'width') : 0, (b && bgOf(b)) || (r.classList.contains('save') ? '#C9CED6' : C.blue), BW), {text: clean(inline(v)), fontSize: 8, alignment: 'right'}];
  });
  return rows.length ? {table: {widths: ['*', BW, 'auto'], body: rows}, layout: 'noBorders', margin: [0, 2, 0, 8]} : null;
}
function vbars(el) {
  const items = [...el.querySelectorAll(':scope > .vb')];
  const max = Math.max(...items.map(i => { const s = i.querySelector('.vb-bar,.vb-stack'); return s ? pct(s, 'height') : 0; }), 0.01);
  const cw = Math.min(56, (W - 20) / items.length - 6), H = 90;
  const cols = items.map(i => {
    const s = i.querySelector('.vb-bar,.vb-stack'), h = (s ? pct(s, 'height') : 0) / max * H;
    let canvas;
    if (s && s.classList.contains('vb-stack')) {
      const segs = [...s.children].map(x => ({f: parseFloat((x.getAttribute('style') || '').match(/flex:\s*([\d.]+)/)?.[1] || 0), c: bgOf(x)})).reverse();
      const tot = segs.reduce((a, x) => a + x.f, 0) || 1; let y = H; canvas = [];
      segs.forEach(sg => { const sh = sg.f / tot * h; y -= sh; canvas.push({type: 'rect', x: 0, y, w: cw, h: Math.max(0, sh - .6), color: sg.c || C.blue}); });
    } else canvas = [{type: 'rect', x: 0, y: H - h, w: cw, h, color: bgOf(s) || C.blue, r: 2}];
    return {width: cw + 6, stack: [{text: textOf(i.querySelector('.vb-v') || i), fontSize: 6.5, alignment: 'center', color: C.ink}, {canvas, margin: [3, 2, 0, 2]}, {text: textOf(i.querySelector('.vb-x') || i), fontSize: 6.5, color: C.muted, alignment: 'center'}]};
  });
  return {stack: [{columns: cols, columnGap: 2}], unbreakable: true, margin: [0, 4, 0, 8]};
}
function stackbar(el) {
  const segs = [...el.children].map(x => ({f: parseFloat((x.getAttribute('style') || '').match(/flex:\s*([\d.]+)/)?.[1] || 0), c: bgOf(x)}));
  const tot = segs.reduce((a, s) => a + s.f, 0) || 1; let x = 0; const w = Math.min(300, MAXW - 12);
  return {canvas: segs.map(s => { const r = {type: 'rect', x, y: 0, w: Math.max(0, s.f / tot * w - 1), h: 10, color: s.c || C.blue}; x += s.f / tot * w; return r; }), margin: [0, 4, 0, 6]};
}
function legend(el) {
  const rows = [...el.querySelectorAll(':scope > li')].map(li => {
    const sw = li.querySelector('i'), c = sw ? bgOf(sw) : null, parts = [...li.children].filter(x => x !== sw).map(x => textOf(x)).filter(Boolean);
    return {columns: [{canvas: [{type: 'rect', x: 0, y: 1.5, w: 7, h: 7, color: c || C.blue, r: 1.5}], width: 11}, {text: parts.join('   '), fontSize: 8}], margin: [0, 1, 0, 1]};
  });
  return {stack: rows, margin: [0, 2, 0, 8]};
}
function table(el) {
  const head = [...el.querySelectorAll(':scope > thead > tr')], body = [...el.querySelectorAll(':scope > tbody > tr')].filter(r => !skip(r)), foot = [...el.querySelectorAll(':scope > tfoot > tr')];
  const all = [...head, ...body, ...foot]; if (!all.length) return null;
  const ncol = Math.max(...all.map(r => [...r.children].reduce((a, c) => a + (+c.getAttribute('colspan') || 1), 0)));
  const fs = ncol <= 4 ? 8 : ncol <= 6 ? 7.2 : 6.4;
  const cell = (c, isHead, isFoot) => {
    const num = c.classList.contains('num');
    const o = {text: clean(inline(c, isHead ? {bold: true, color: C.muted} : isFoot ? {bold: true} : {})), fontSize: isHead ? fs - .8 : fs, alignment: num ? 'right' : 'left'};
    if (+c.getAttribute('colspan') > 1) o.colSpan = +c.getAttribute('colspan');
    if (isHead) o.characterSpacing = .3;
    return o;
  };
  const rowOf = (r, h, f) => { const cells = []; [...r.children].forEach(c => { cells.push(cell(c, h, f)); for (let i = 1; i < (+c.getAttribute('colspan') || 1); i++) cells.push({}); }); while (cells.length < ncol) cells.push({text: ''}); return cells; };
  const rows = [...head.map(r => rowOf(r, true)), ...body.map(r => rowOf(r)), ...foot.map(r => rowOf(r, false, true))];
  if (body.length > 400) rows.splice(head.length + 400, body.length - 400, [{text: `… ${body.length - 400} more rows on the website`, colSpan: ncol, fontSize: fs, color: C.muted}, ...Array(ncol - 1).fill({})]);
  const widths = Array(ncol).fill('auto'); const wrapCol = [...(head[0]?.children || body[0]?.children || [])].findIndex(c => !c.classList.contains('num')); widths[Math.max(0, wrapCol)] = '*';
  return {table: {headerRows: head.length, widths, body: rows, dontBreakRows: true}, margin: [0, 2, 0, 10],
    layout: {hLineWidth: (i, n) => (i === 0 || i === n.table.body.length) ? 0 : (i === head.length ? .8 : .4), vLineWidth: () => 0, hLineColor: i => i === head.length ? '#C9CED6' : C.line,
      paddingTop: () => 3, paddingBottom: () => 3, paddingLeft: i => i ? 5 : 0, paddingRight: (i, n) => i === n.table.widths.length - 1 ? 0 : 5,
      fillColor: (i) => (i >= rows.length - foot.length && foot.length) ? '#F6F8FB' : null}};
}
function kv(el) {
  const rows = []; let dt = null;
  [...el.children].flatMap(c => c.tagName === 'DIV' ? [...c.children] : [c]).forEach(c => { if (c.tagName === 'DT' && !c.classList.contains('span')) dt = c; else if (c.tagName === 'DD') { rows.push(dt && !c.classList.contains('span') ? [{text: clean(inline(dt)), color: C.muted, fontSize: 8}, {text: clean(inline(c)), fontSize: 8}] : [{text: clean(inline(c)), fontSize: 7.5, color: C.muted, colSpan: 2}, {}]); dt = null; } });
  return rows.length ? {table: {widths: [92, '*'], body: rows}, layout: {defaultBorder: false, paddingTop: () => 2, paddingBottom: () => 2, paddingLeft: () => 0}, margin: [0, 0, 0, 4]} : null;
}
function kpis(el) {
  const tiles = [...el.children].filter(x => !skip(x)).map(k => ({table: {widths: ['*'], body: [[{stack: [
    {text: textOf(k.querySelector('.eyebrow') || k).toUpperCase(), fontSize: 6.2, color: C.muted, characterSpacing: .5},
    {text: textOf(k.querySelector('.v') || k), fontSize: 15, bold: true, color: C.ink, margin: [0, 2, 0, 1]},
    {text: textOf(k.querySelector('.s') || {textContent: ''}), fontSize: 7, color: C.muted}], fillColor: C.sunken, margin: [6, 5, 6, 6]}]]}, layout: 'noBorders'}));
  const rows = []; for (let i = 0; i < tiles.length; i += 4) rows.push({columns: tiles.slice(i, i + 4), columnGap: 6, margin: [0, 0, 0, 6]});
  return {stack: rows, margin: [0, 2, 0, 8], unbreakable: true};
}
function list(el) {
  const items = [...el.children].filter(li => li.tagName === 'LI' && !skip(li)).map(li => {
    if (li.querySelector(':scope > .tl-d')) return {columns: [{text: textOf(li.querySelector('.tl-d')), width: 62, fontSize: 7.5, color: C.muted}, {text: clean(inline(li.querySelector(':scope > span:last-child') || li)), fontSize: 8.5}], margin: [0, 0, 0, 4]};
    if (!hasBlocks(li)) return {text: clean(inline(li)), fontSize: 9, margin: [0, 0, 0, 2]};
    return {stack: blocksOf(li)};
  });
  if (!items.length) return null;
  if (el.classList.contains('timeline')) return {stack: items, margin: [0, 2, 0, 8]};
  return {[el.tagName === 'OL' ? 'ol' : 'ul']: items, fontSize: 9, margin: [0, 2, 0, 8], markerColor: C.muted};
}
const BLOCK = /^(DIV|P|UL|OL|TABLE|H1|H2|H3|H4|SECTION|SVG|DETAILS|DL|ASIDE|HEADER|ARTICLE|FIGURE|LI)$/;
function hasBlocks(el) { return [...el.children].some(c => BLOCK.test(c.tagName.toUpperCase()) || /\b(hb|kpi|bill-hd|stackbar|leg)\b/.test(c.className)); }
function blocksOf(el) { const out = []; if (!hasBlocks(el)) { const r = clean(inline(el)); if (r.length) out.push({text: r, fontSize: 9}); return out; } [...el.children].forEach(c => walk(c, out)); return out; }
function grid(el, n) {
  const prev = MAXW; MAXW = (W - 14 * (n - 1)) / n - 18;
  const kids = [...el.children].filter(x => !skip(x)).map(x => { const o = []; walk(x, o, true); return o.length ? {stack: o} : null; }).filter(Boolean);
  MAXW = prev;
  const rows = []; for (let i = 0; i < kids.length; i += n) rows.push({columns: kids.slice(i, i + n).concat(Array(Math.max(0, n - kids.slice(i, i + n).length)).fill({text: ''})), columnGap: 14, unbreakable: [...el.children].slice(i, i + n).every(x => x.textContent.length < 2200)});
  return {stack: rows, margin: [0, 0, 0, 4]};
}
function card(el, title) {
  return {table: {widths: ['*'], body: [[{stack: blocksOf(el), margin: [8, 6, 8, 4]}]]}, layout: {hLineWidth: () => .6, vLineWidth: () => .6, hLineColor: () => C.line, vLineColor: () => C.line}, margin: [0, 0, 0, 8], unbreakable: el.textContent.length < 1400};
}
function walk(el, out, inGrid) {
  if (el.nodeType !== 1 || skip(el)) return;
  const t = el.tagName, cl = el.classList;
  if (t === 'svg' || t === 'SVG') { if (el.closest('.cmp-bar')) return; out.push(svgNode(el, inGrid ? W / 2 - 10 : (cl.contains('ex-fig') ? 240 : W))); return; }
  if (t === 'H1') return;
  if (t === 'H2') { out.push({text: textOf(el), style: 'h2'}); return; }
  if (t === 'H3') { out.push({text: textOf(el), style: 'h3'}); return; }
  if (t === 'H4') { out.push({text: clean(inline(el)), style: 'h4'}); return; }
  if (cl.contains('eyebrow')) { out.push({text: textOf(el).toUpperCase(), fontSize: 6.8, color: C.muted, characterSpacing: .6, margin: [0, 4, 0, 2]}); return; }
  if (t === 'TABLE') { const x = table(el); if (x) out.push(x); return; }
  if (t === 'DL') { const x = kv(el); if (x) out.push(x); return; }
  if (t === 'UL' && cl.contains('roster')) { out.push({table: {widths: [62, '*', 'auto'], body: [...el.children].map(li => [{text: textOf(li.querySelector('.seat')), fontSize: 7.5, color: C.muted}, {stack: [{text: textOf(li.querySelector('.who b, .who .vacant')), fontSize: 8.5}].concat(li.querySelector('.who small') ? [{text: textOf(li.querySelector('.who small')), fontSize: 7, color: C.muted}] : [])}, {text: textOf(li.querySelector('.r-term')), fontSize: 7, color: C.muted}])}, layout: {hLineWidth: (i, n) => i > 0 && i < n.table.body.length ? .5 : 0, vLineWidth: () => 0, hLineColor: () => C.line, paddingLeft: () => 0, paddingRight: () => 4}, margin: [0, 0, 0, 4]}); return; }
  if ((t === 'UL' || t === 'OL') && (cl.contains('findings') || cl.contains('results'))) { [...el.children].filter(li => !skip(li)).forEach(li => out.push(card(li))); return; }
  if (t === 'UL' || t === 'OL') { if (cl.contains('leg')) out.push(legend(el)); else { const x = list(el); if (x) out.push(x); } return; }
  if (cl.contains('kpis')) { out.push(kpis(el)); return; }
  if (cl.contains('bill-hd')) { const sp = [...el.children]; out.push({stack: sp.map(x => x.classList.contains('eyebrow') ? {text: textOf(x).toUpperCase(), fontSize: 6.8, color: C.muted, characterSpacing: .6} : x.classList.contains('bill-v') ? {text: clean(inline(x)), fontSize: 18, bold: true, margin: [0, 1, 0, 1]} : {text: clean(inline(x)), fontSize: 7.8, color: C.muted}), margin: [0, 0, 0, 4]}); return; }
  if (cl.contains('hbars')) { const x = hbars(el); if (x) out.push(x); return; }
  if (cl.contains('vbars')) { out.push(vbars(el)); return; }
  if (cl.contains('stackbar')) { out.push(stackbar(el)); return; }
  if (cl.contains('cmp')) { out.push({columns: [...el.querySelectorAll('.cmp-col')].map(c => ({stack: [{text: textOf(c.querySelector('.eyebrow')).toUpperCase(), fontSize: 6.5, color: C.muted}, {text: textOf(c.querySelector('.bill-v')), fontSize: 15, bold: true}, {text: textOf(c.querySelector('.cmp-save')), fontSize: 7.5, color: C.muted}]})), columnGap: 10, margin: [0, 2, 0, 8]}); return; }
  if (cl.contains('callout')) { out.push({table: {widths: [3, '*'], body: [[{text: '', fillColor: C.amber}, {stack: blocksOf(el), margin: [6, 4, 4, 4], fillColor: '#FFF8EC'}]]}, layout: 'noBorders', margin: [0, 2, 0, 10]}); return; }
  if (cl.contains('profiles') || cl.contains('officers')) { out.push(grid(el, 3)); return; }
  if (cl.contains('gov-grid')) { out.push(grid(el, 2)); return; }
  if (cl.contains('addr-grid') || cl.contains('cards') || cl.contains('two') || cl.contains('st-wrap')) { out.push(grid(el, 2)); return; }
  if (cl.contains('card') || cl.contains('prof') || cl.contains('fd') || cl.contains('arg') || cl.contains('g-term') || cl.contains('trend-box') || cl.contains('calc')) { out.push(card(el)); return; }
  if (cl.contains('explain')) { const kids = [...el.children].filter(x => !skip(x)); const fig = kids.find(k => k.tagName.toLowerCase() === 'svg'); const txt = kids.filter(k => k !== fig).flatMap(k => blocksOf(k));
    out.push({table: {widths: ['*'], body: [[{columns: fig ? [{stack: txt, width: '*'}, {...svgNode(fig, 200), width: 200}] : [{stack: txt}], columnGap: 14, margin: [10, 8, 10, 6], fillColor: '#F8FAFC'}]]}, layout: 'noBorders', margin: [0, 0, 0, 10]}); return; }
  if (t === 'DETAILS') { [...el.children].forEach(c => { if (c.tagName === 'SUMMARY') out.push({text: textOf(c), style: 'h4'}); else walk(c, out, inGrid); }); return; }
  if (t === 'P') { const r = clean(inline(el)); if (r.length) out.push({text: r, fontSize: cl.contains('note') || cl.contains('small') || cl.contains('muted') ? 7.8 : 9, color: cl.contains('note') || cl.contains('muted') ? C.muted : C.ink, margin: [0, 0, 0, 6]}); return; }
  const hasBlock = [...el.children].some(c => BLOCK.test(c.tagName.toUpperCase()) || c.classList.contains('hb'));
  if (hasBlock) { [...el.children].forEach(c => walk(c, out, inGrid)); return; }
  const r = clean(inline(el)); if (r.length) out.push({text: r, fontSize: 9, margin: [0, 0, 0, 4]});
}

/* ---------- document ---------- */
async function logo() {
  try { const img = new Image(); img.src = '/assets/flux-labs.webp'; await img.decode(); const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight; c.getContext('2d').drawImage(img, 0, 0); return c.toDataURL('image/png'); } catch (e) { return null; }
}
async function build() {
  const root = document.querySelector('main .page') || document.querySelector('main .wrap') || document.querySelector('main');
  const h1 = root.querySelector('h1'), title = window.BCReportTitle ? window.BCReportTitle() : h1 ? textOf(h1) : document.title;
  const header = h1 ? h1.closest('header') || h1.parentElement : null;
  const eyebrow = header?.querySelector('.eyebrow') ? textOf(header.querySelector('.eyebrow')) : 'BayCounty.me';
  const lede = header?.querySelector('.lede') ? textOf(header.querySelector('.lede')) : '';
  const meta = document.getElementById('printMeta');
  const sub = window.BCReportMeta ? window.BCReportMeta() : (meta && meta.textContent.trim() ? meta.textContent.trim() : '');
  const body = [];
  [...root.children].forEach(c => { if (c === header || (header && c.contains(header))) { [...header.children].forEach(x => { if (!x.querySelector('h1') && x.tagName !== 'H1' && !x.classList.contains('stamp') && !x.classList.contains('brand') && !x.classList.contains('tx-brand')) walk(x, body); }); return; } walk(c, body); });
  const date = new Date().toLocaleDateString('es-US', {month: 'long', day: 'numeric', year: 'numeric'});
  const url = location.host + location.pathname.replace(/\/$/, '') + location.search;
  const lg = await logo();
  const cover = [
    {text: eyebrow.toUpperCase(), fontSize: 7.5, color: C.salmon, bold: true, characterSpacing: 1},
    {text: title, fontSize: 22, bold: true, color: C.navy, margin: [0, 3, 0, 4], lineHeight: 1.05},
    lede ? {text: lede, fontSize: 9.5, color: C.muted, margin: [0, 0, 0, 6], lineHeight: 1.25} : null,
    sub ? {text: sub, fontSize: 8.5, color: C.ink, margin: [0, 0, 0, 4]} : null,
    {text: [{text: 'Informe exportado el ' + date + ' · '}, {text: url, link: location.href, color: C.blue}], fontSize: 7.5, color: C.muted},
    {canvas: [{type: 'line', x1: 0, y1: 0, x2: W, y2: 0, lineWidth: 1.2, lineColor: C.navy}], margin: [0, 8, 0, 12]},
  ].filter(Boolean);
  return {
    pageSize: 'LETTER', pageMargins: [40, 58, 40, 52],
    info: {title: title + ' · BayCounty.me', author: 'BayCounty.me (Flux Labs)', subject: lede, creator: 'BayCounty.me'},
    defaultStyle: {font: 'Roboto', fontSize: 9, color: C.ink, lineHeight: 1.2},
    styles: {h2: {fontSize: 13, bold: true, color: C.navy, margin: [0, 10, 0, 5]}, h3: {fontSize: 10.5, bold: true, color: C.ink, margin: [0, 6, 0, 3]}, h4: {fontSize: 9, bold: true, color: C.ink, margin: [0, 5, 0, 3]}},
    header: (page) => ({margin: [40, 22, 40, 0], columns: [
      {text: [{text: 'BayCounty', bold: true, color: C.navy}, {text: '.me', bold: true, color: C.salmon}], fontSize: 11, width: 'auto'},
      {text: page > 1 ? title : '', fontSize: 7.5, color: C.muted, alignment: 'right', margin: [0, 2, 0, 0]}]}),
    footer: (page, pages) => ({margin: [40, 14, 40, 0], columns: [
      lg ? {stack: [{text: 'DESARROLLADO POR', fontSize: 5.5, color: C.muted, characterSpacing: .8}, {image: lg, width: 56, margin: [0, 1, 0, 0]}], width: 'auto', link: 'https://fluxlabs.net/'} : {text: 'Desarrollado por Flux Labs', fontSize: 7, color: C.muted, width: 'auto'},
      {text: 'Registros públicos · fuentes enlazadas en el informe · correcciones: hello@fluxlabs.net', fontSize: 6.5, color: C.muted, alignment: 'center', margin: [0, 5, 0, 0]},
      {text: `Página ${page} de ${pages}`, fontSize: 7, color: C.muted, alignment: 'right', width: 'auto', margin: [0, 5, 0, 0]}]}),
    content: [...cover, ...body],
  };
}
async function exportPDF(btn) {
  const label = btn ? btn.innerHTML : '';
  try {
    if (btn) { btn.disabled = true; btn.lastChild.textContent = 'Creando el PDF…'; }
    document.querySelectorAll('main details').forEach(d => { d.dataset.wasOpen = d.open; d.open = true; });
    const root = document.documentElement, th = root.getAttribute('data-theme'); root.setAttribute('data-theme', 'light'); window.__bcTheme = th;
    if (window.BCReportBefore) await window.BCReportBefore();
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    await ready();
    const doc = await build();
    const name = 'BayCounty.me - ' + (doc.info.title.replace(' · BayCounty.me', '')).replace(/[^\w .,'-]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 80) + ' - ' + new Date().toLocaleDateString('en-CA') + '.pdf';
    await new Promise((res, rej) => { try { window.pdfMake.createPdf(doc).download(name, res); } catch (e) { rej(e); } });
  } catch (e) {
    console.error(e); alert('No se pudo crear el PDF. Todavía puede usar Imprimir > Guardar como PDF en su navegador.');
  } finally {
    document.querySelectorAll('main details').forEach(d => { if (d.dataset.wasOpen === 'false') d.open = false; });
    if (window.BCReportAfter) window.BCReportAfter();
    if ('__bcTheme' in window) { if (window.__bcTheme) document.documentElement.setAttribute('data-theme', window.__bcTheme); else document.documentElement.removeAttribute('data-theme'); delete window.__bcTheme; }
    if (btn) { btn.disabled = false; btn.innerHTML = label; }
  }
}
window.BCReport = {export: exportPDF, build};
document.addEventListener('click', e => {
  const b = e.target.closest('#pdf, [data-pdf]'); if (!b) return;
  e.preventDefault(); e.stopImmediatePropagation(); exportPDF(b);
}, true);
})();
