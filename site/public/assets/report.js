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
// Content width on Letter with 40pt margins: 532 portrait, 712 landscape. A report turns landscape when one of its
// tables can't fit its columns on one line in portrait, even at the smallest type (see fitTable).
const PORTRAIT = {w: 532, h: 682}, LANDSCAPE = {w: 712, h: 502};
let W = PORTRAIT.w, PAGE_H = PORTRAIT.h, WANT_LANDSCAPE = false, WIDE = 0;

function load(src) { return new Promise((res, rej) => { const s = document.createElement('script'); s.src = src; s.onload = res; s.onerror = () => rej(new Error('load ' + src)); document.head.appendChild(s); }); }
async function ready() { if (!window.pdfMake) await load(PDFMAKE); if (!window.pdfMake.vfs || !Object.keys(window.pdfMake.vfs).length) await load(VFS); await fonts(); }

/* ---------- text measuring ----------
   Table columns are sized from the real width of their text in the PDF's own font (pdfmake's Roboto, loaded from
   its font files), so short columns never wrap and only long text columns share what's left. */
let measureCtx = null, FAMILY = 'Helvetica, Arial, sans-serif';
async function fonts() {
  if (measureCtx) return;
  measureCtx = document.createElement('canvas').getContext('2d');
  try {
    const vfs = window.pdfMake.vfs, buf = b64 => Uint8Array.from(atob(b64), c => c.charCodeAt(0)).buffer;
    const faces = [new FontFace('BCPdfRoboto', buf(vfs['Roboto-Regular.ttf']), {weight: '400'}), new FontFace('BCPdfRoboto', buf(vfs['Roboto-Medium.ttf']), {weight: '700'})];
    await Promise.all(faces.map(f => f.load())); faces.forEach(f => document.fonts.add(f)); FAMILY = 'BCPdfRoboto';
  } catch (e) { /* fall back to Helvetica metrics, close enough to Roboto */ }
}
function textW(t, size, bold, spacing) { measureCtx.font = `${bold ? 700 : 400} ${size}px ${FAMILY}`; return measureCtx.measureText(t).width + (spacing || 0) * t.length; }
// Widest line and widest single word of a list of text runs (explicit line breaks kept), at the runs' own sizes.
function runsW(runs, size, bold) {
  let line = 0, max = 0, word = 0;
  (Array.isArray(runs) ? runs : [{text: String(runs ?? '')}]).forEach(r => {
    const fs = r.fontSize || size, b = r.bold ?? bold, parts = String(r.text ?? '').split('\n');
    parts.forEach((p, i) => {
      if (i) { max = Math.max(max, line); line = 0; }
      line += textW(p, fs, b, r.characterSpacing);
      p.split(/\s+/).forEach(w => { if (w) word = Math.max(word, textW(w, fs, b, r.characterSpacing)); });
    });
  });
  return {line: Math.max(max, line), word, lines: (Array.isArray(runs) ? runs : []).reduce((a, r) => a + (String(r.text ?? '').match(/\n/g) || []).length, 0) + 1};
}
// Characters Roboto doesn't have are swapped for ones it does, so nothing prints as an empty box.
const GLYPHS = {'\u25B2': '+', '\u25B4': '+', '\u2191': '+', '\u25BC': '\u2212', '\u25BE': '\u2212', '\u2193': '\u2212', '\u25CF': '\u2022', '\u25CB': '\u2022', '\u2715': '\u00D7', '\u2717': '\u00D7'};
const glyphs = t => t.replace(/[\u25B2\u25B4\u2191\u25BC\u25BE\u2193\u25CF\u25CB\u2715\u2717]/g, c => GLYPHS[c]).replace(/[\u2190-\u21FF\u2600-\u27BF\u25A0-\u25FF]/g, '');

/* ---------- colors ---------- */
function resolve(v) {
  if (!v) return null;
  v = String(v).trim();
  let m = v.match(/^var\(--([\w-]+)\)$/); if (m) return LIGHT[m[1]] || getComputedStyle(document.documentElement).getPropertyValue('--' + m[1]).trim() || C.blue;
  m = v.match(/^color-mix\(in srgb,\s*(var\(--[\w-]+\)|#[0-9a-f]+)\s+(\d+)%,\s*(transparent|var\(--[\w-]+\)|#[0-9a-f]+)\)$/i);
  if (m) return m[3] === 'transparent' ? resolve(m[1]) : mix(resolve(m[1]), resolve(m[3]), +m[2] / 100);
  return v;
}
function rgb2hex(v) { const m = v.match(/rgba?\(([^)]+)\)/); if (!m) return v; const p = m[1].split(',').map(x => parseFloat(x)); if (p.length === 4 && p[3] === 0) return 'none'; const al = p.length === 4 ? p[3] : 1; return '#' + p.slice(0, 3).map(x => Math.round(x * al + 255 * (1 - al)).toString(16).padStart(2, '0')).join(''); }
// color-mix() computes to color(srgb r g b / a); pdfmake's SVG reader only knows hex, so mix the alpha over white.
function srgbHex(v) { const m = v.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?/); if (!m) return v; const a = m[4] === undefined ? 1 : +m[4]; if (a === 0) return 'none';
  return '#' + [m[1], m[2], m[3]].map(x => Math.round((+x * a + (1 - a)) * 255).toString(16).padStart(2, '0')).join(''); }
function hex(c) { c = c.replace('#', ''); if (c.length === 3) c = c.split('').map(x => x + x).join(''); return [0, 2, 4].map(i => parseInt(c.slice(i, i + 2), 16)); }
function mix(a, b, p) { try { const x = hex(a), y = hex(b); return '#' + x.map((v, i) => Math.round(v * p + y[i] * (1 - p)).toString(16).padStart(2, '0')).join(''); } catch (e) { return a; } }
function bgOf(el) { const s = el.getAttribute('style') || ''; const m = s.match(/background(?:-color)?:\s*([^;]+)/); return m ? resolve(m[1]) : null; }
function pct(el, prop) { const s = el.getAttribute('style') || ''; const m = s.match(new RegExp(prop + ':\\s*([\\d.]+)%')); return m ? +m[1] / 100 : 0; }

/* ---------- inline text ---------- */
const abs = h => { try { return new URL(h, location.href).href; } catch (e) { return h; } };
// Block children start and end on their own line; children of a row (display:flex) stay on one line, separated by a dot.
const endsLine = out => !out.length || /\n$/.test(out[out.length - 1].text || '');
function inline(el, base = {}) {
  const out = [];
  const pcs = el.nodeType === 1 ? getComputedStyle(el) : null;
  const row = pcs && /flex/.test(pcs.display) && !/column/.test(pcs.flexDirection);
  el.childNodes.forEach(n => {
    if (n.nodeType === 3) { const t = glyphs(n.textContent.replace(/\s+/g, ' ').replace(/\s*[→↗←]/g, '').replace(/[✓✔]\s*/g, '')); if (t) out.push({text: t, ...base}); return; }
    if (n.nodeType !== 1 || skip(n, true)) return;
    const tag = n.tagName, cls = n.classList, st = {...base};
    if (tag === 'BR') { out.push({text: '\n'}); return; }
    if (tag === 'SVG' || tag === 'svg' || tag === 'SUMMARY' || (tag === 'BUTTON' && !cls.contains('tt-h')) || tag === 'INPUT' || tag === 'SELECT') return;
    const dsp = getComputedStyle(n).display;
    if (dsp === 'none') return;
    if (tag === 'B' || tag === 'STRONG' || tag === 'TH') st.bold = true;
    if (tag === 'EM' || tag === 'I') { if (!cls.length) st.italics = true; else st.color = C.muted; }
    if (tag === 'SMALL' || cls.contains('muted') || cls.contains('small') || cls.contains('src') || cls.contains('r-s')) st.color = C.muted;
    if (tag === 'MARK') st.background = '#FFE6B3';
    if (cls.contains('v-no')) st.color = '#A86A00';
    if (tag === 'A' && n.getAttribute('href') && !n.getAttribute('href').startsWith('#')) { st.link = abs(n.getAttribute('href')); st.color = C.blue; }
    let kid;
    if (cls.contains('badge')) kid = [{text: ' ' + n.textContent.replace(/^[✓!]\s*/, '').trim() + ' ', fontSize: 7, color: cls.contains('warn') ? '#A86A00' : cls.contains('ok') ? '#1F7A4D' : C.muted, bold: true}];
    else if (cls.contains('ar')) kid = [{text: glyphs(n.textContent.trim()), bold: true, color: /▲/.test(n.textContent) ? C.salmon : C.blue}];
    else if (tag === 'I' && !n.textContent.trim()) { const c = bgOf(n); kid = c ? [{text: '• ', color: c, fontSize: 11, lineHeight: .8}] : []; }
    else kid = inline(n, st);
    if (!kid.some(r => String(r.text || '').trim())) { if (kid.some(r => r.text === '\n')) out.push(...kid); return; }
    const block = !row && /^(block|flex|grid|list-item|table)$/.test(dsp);
    if (row && !endsLine(out) && out.some(r => String(r.text || '').trim())) out.push({text: '  ·  ', color: C.faint});
    if (block && !endsLine(out)) out.push({text: '\n'});
    out.push(...kid);
    if (block && !endsLine(out)) out.push({text: '\n'});
  });
  return out;
}
// Roboto in pdfmake has no arrow glyphs, so "$1.2M → $1.4M" reads "$1.2M to $1.4M".
const textOf = el => glyphs(el.textContent).replace(/\s+/g, ' ').replace(/\s*\u2192\s*/g, ' to ').replace(/[\u2197\u2190]/g, '').trim();
function clean(runs) { while (runs.length && /^\s*$/.test(runs[runs.length - 1].text ?? 'x')) runs.pop(); while (runs.length && typeof runs[0].text === 'string' && !runs[0].text.trim()) runs.shift(); if (runs[0]) runs[0] = {...runs[0], text: runs[0].text.replace(/^\s+/, '')}; return runs; }

/* ---------- what to leave out ---------- */
const SKIP = 'nav,.jump,.ui-date,.ui-av,.ui-ti,.ico,label:has(select),label:has(input),.vt-filters,.stamp,.pdf-btn,.print-hide,.addr-hd,.tt,.filters-row,.pills,.addr-search,.home-search,.ac-list,.menu-btn,.theme-btn,script,style,noscript,button:not(.prof):not(.tt-h),input,.filters,.maptools,.tip,.rail,#more,#csv,.prof p,select,form,.print-meta,.skip,.term-pop,#ledMore,.addr-act,[data-report="skip"]';
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
    SVGP.forEach(pr => { const v = cs.getPropertyValue(pr); if (v && v !== 'none' || pr === 'fill' || pr === 'stroke') d.setAttribute(pr, v.startsWith('rgb') ? rgb2hex(v) : v.startsWith('color(') ? srgbHex(v) : v); });
    // Label halos (a white stroke drawn under the text on screen) print over the letters in the PDF, so labels drop the stroke.
    if (el.tagName === 'text' || el.tagName === 'tspan') d.setAttribute('stroke', 'none');
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
  let w = Math.min(maxW, vw * 1.4);
  if (w * vh / vw > PAGE_H * .62) w = PAGE_H * .62 * vw / vh;
  return {svg: s, width: w, margin: [0, 4, 0, 6], _h: w * vh / vw};
}
function bar(frac, color, w = 170, h = 7) {
  return {canvas: [{type: 'rect', x: 0, y: 0, w, h, color: '#EEF2F7', r: 2}, {type: 'rect', x: 0, y: 0, w: Math.max(1, w * Math.min(1, frac)), h, color: color || C.blue, r: 2}], margin: [0, 3, 0, 0]};
}
function stackMini(sb, w = 150, h = 7) { // a bar made of colored segments (e.g. water / sewer / garbage)
  const tot = w * Math.min(1, pct(sb, 'width') || 1), segs = [...sb.querySelectorAll('.seg')].map(x => { const st = x.getAttribute('style') || ''; return [+((st.match(/flex:\s*([\d.]+)/) || [])[1] || 0), bgOf(x) || C.blue]; });
  const sum = segs.reduce((a, [v]) => a + v, 0) || 1; let x = 0;
  return {canvas: [{type: 'rect', x: 0, y: 0, w, h, color: '#EEF2F7', r: 2}, ...segs.map(([v, c]) => { const ww = tot * v / sum, o = {type: 'rect', x, y: 0, w: Math.max(.5, ww), h, color: c}; x += ww; return o; })], margin: [0, 3, 0, 0]};
}
// A value with a second line ("$4.8M 19.7%" over "$220 per resident") printed on one line.
const oneLine = runs => runs.map(r => r.text === '\n' ? {text: '  \u00B7  ', color: C.faint} : r);
function hbars(el) {
  const BW = MAXW < 400 ? 70 : 150;
  const rows = [...el.querySelectorAll(':scope > .hb')].filter(r => !skip(r)).map(r => {
    const b = r.querySelector('.hb-bar'), n = r.querySelector('.hb-n'), v = r.querySelector('.hb-v');
    const sb = !b && r.querySelector('.stackbar');
    return [{text: clean(inline(n)), fontSize: 8}, sb ? stackMini(sb, BW) : bar(b ? pct(b, 'width') : 0, (b && bgOf(b)) || (r.classList.contains('save') ? '#C9CED6' : C.blue), BW), {text: oneLine(clean(inline(v))), fontSize: 8, alignment: 'right', noWrap: true}];
  });
  return rows.length ? {table: {widths: ['*', BW, 'auto'], body: rows, dontBreakRows: true}, layout: 'noBorders', margin: [0, 2, 0, 8], unbreakable: rows.length <= 14} : null;
}
function vbars(el) {
  const items = [...el.querySelectorAll(':scope > .vb')];
  const max = Math.max(...items.map(i => { const s = i.querySelector('.vb-bar,.vb-stack'); return s ? pct(s, 'height') : 0; }), 0.01);
  const cw = Math.min(56, (MAXW - 20) / items.length - 6), H = 90;
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
// The element's painted background as #hex (handles rgb() and the color(srgb ...) that color-mix() computes to).
function colorOf(el, fallback) {
  const v = getComputedStyle(el).backgroundColor || '';
  const m = v.match(/^color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)/);
  if (m) return '#' + m.slice(1, 4).map(x => Math.round(+x * 255).toString(16).padStart(2, '0')).join('');
  const h = v.startsWith('rgb') ? rgb2hex(v) : null;
  return h && h !== 'none' ? h : fallback || C.blue;
}
function dvbars(el) { // diverging bars: increases to the right of a center line, decreases to the left
  const BW = MAXW < 400 ? 90 : 170, H = 8;
  const rows = [...el.querySelectorAll(':scope > .dv-r')].filter(r => !skip(r)).map(r => {
    const b = r.querySelector('.dv-b'), half = BW / 2, w = b ? Math.min(half, pct(b, 'width') * BW) : 0, up = b && b.classList.contains('up');
    const canvas = [{type: 'line', x1: half, y1: -2, x2: half, y2: H + 2, lineWidth: .6, lineColor: '#C9CED6'}];
    if (b) canvas.push({type: 'rect', x: up ? half : half - w, y: 0, w: Math.max(.8, w), h: H, color: colorOf(b), r: 1.5});
    const n = r.querySelector('.dv-n'), v = r.querySelector('.dv-v'), own = x => [...x.childNodes].filter(c => c.nodeType === 3).map(c => c.textContent).join('').trim();
    const tag = n.querySelector('.dv-tag'), sub = n.querySelector('small'), vs = v ? [...v.children].filter(c => c.tagName !== 'SMALL') : [], vsmall = v && v.querySelector('small');
    const name = [{text: own(n), fontSize: 8}].concat(tag ? [{text: '  ' + textOf(tag).toUpperCase(), fontSize: 6, bold: true, color: tag.classList.contains('add') ? '#1F7A4D' : C.muted}] : []).concat(sub ? [{text: '\n' + textOf(sub), fontSize: 6.8, color: C.muted}] : []);
    const val = vs.map((c, k) => ({text: (k ? ' ' : '') + textOf(c), fontSize: 8, bold: !k, color: k ? C.muted : C.ink})).concat(vsmall ? [{text: '\n' + textOf(vsmall), fontSize: 6.8, color: C.muted}] : []);
    return [{text: name}, {canvas, margin: [0, 3, 0, 0]}, {text: val.length ? val : '', alignment: 'right'}];
  });
  if (!rows.length) { const r = clean(inline(el)); return r.length ? {text: r, fontSize: 9, color: C.muted, margin: [0, 0, 0, 6]} : null; }
  return {table: {widths: ['*', BW, 'auto'], body: rows, dontBreakRows: true}, layout: {hLineWidth: (i, n) => i > 0 && i < n.table.body.length ? .4 : 0, vLineWidth: () => 0, hLineColor: () => C.line, paddingLeft: i => i ? 6 : 0, paddingRight: (i, n) => i === n.table.widths.length - 1 ? 0 : 6, paddingTop: () => 3, paddingBottom: () => 3}, margin: [0, 2, 0, 8]};
}
function yhbars(el) { // one column per year, each with one or more bars (total and General Fund)
  const items = [...el.querySelectorAll(':scope > .yh-c')].filter(i => !i.hidden); // year columns are buttons, which skip() drops
  if (!items.length) return null;
  const H = 80, cw = Math.min(40, (MAXW - 4) / items.length - 3);
  const cols = items.map(i => {
    const bars = [...i.querySelectorAll('.yh-bar')], n = Math.max(1, bars.length), gap = 1.5, bw = Math.min(14, (cw - gap * (n - 1)) / n), x0 = (cw - (bw * n + gap * (n - 1))) / 2;
    const canvas = [{type: 'line', x1: 0, y1: H, x2: cw, y2: H, lineWidth: .5, lineColor: C.line}];
    bars.forEach((b, k) => { const h = pct(b, 'height') * H; canvas.push({type: 'rect', x: x0 + k * (bw + gap), y: H - h, w: bw, h: Math.max(.5, h), color: colorOf(b)}); });
    const on = i.classList.contains('on'), note = i.querySelector('small') ? textOf(i.querySelector('small')) : '';
    return {width: cw + 3, stack: [{text: textOf(i.querySelector('.yh-v') || {textContent: ''}), fontSize: 5.6, alignment: 'center', color: C.ink},
      {canvas, margin: [0, 2, 0, 2]}, {text: textOf(i.querySelector('.yh-y') || {textContent: ''}), fontSize: 6.2, bold: on, color: on ? C.blue : C.muted, alignment: 'center'},
      note ? {text: note, fontSize: 5, color: C.faint, alignment: 'center'} : null].filter(Boolean)};
  });
  return {stack: [{columns: cols, columnGap: 0}], unbreakable: true, margin: [0, 4, 0, 10]};
}
function swatches(el) { // an inline legend: <span><i style="background:..."></i>Label</span> ...
  const items = [...el.children].filter(x => !skip(x)).map(sp => {
    const sw = sp.querySelector('i'), label = textOf(sp);
    return sw ? [{canvas: [{type: 'rect', x: 0, y: 1.5, w: 7, h: 7, color: colorOf(sw), r: 1.5}], width: 10}, {text: label, fontSize: 7.5, color: C.muted, width: 'auto', margin: [0, 0, 12, 0]}]
      : [{text: label, fontSize: 7.5, color: C.muted, width: 'auto', margin: [0, 0, 12, 0]}];
  }).flat();
  return items.length ? {columns: items, columnGap: 0, margin: [0, 0, 0, 4]} : null;
}
function legend(el) {
  const rows = [...el.querySelectorAll(':scope > li')].map(li => {
    const sw = li.querySelector('i'), c = sw ? bgOf(sw) : null, parts = [...li.children].filter(x => x !== sw).map(x => textOf(x)).filter(Boolean);
    return {columns: [{canvas: [{type: 'rect', x: 0, y: 1.5, w: 7, h: 7, color: c || C.blue, r: 1.5}], width: 11}, {text: parts.join('   '), fontSize: 8}], margin: [0, 1, 0, 1]};
  });
  return {stack: rows, margin: [0, 2, 0, 8]};
}
// Sizes a table so short columns (names, dates, amounts, statuses) stay on one line. Long text columns share the
// space that's left and wrap. If the short columns can't fit at the smallest type, the report goes landscape; only if
// they still can't fit there do the widest text columns wrap too.
function fitTable(cols, ncol, fs0, minFs) {
  const pad = 10 * (ncol - 1);
  for (let fs = fs0; fs >= minFs - .01; fs -= .4) {
    const k = fs / fs0, nat = cols.map(c => c.line * k + 1), word = cols.map(c => c.word * k + 1);
    const long = cols.map((c, i) => nat[i] > .3 * W); // a column this wide holds prose, even a right-aligned one
    const fixed = nat.reduce((a, v, i) => a + (long[i] ? 0 : v), 0);
    const room = W - pad - fixed, need = cols.reduce((a, c, i) => a + (long[i] ? Math.max(word[i], Math.min(nat[i], .2 * W)) : 0), 0);
    if (room >= need - .5) return {fs, nat, long, room};
  }
  return null;
}
function table(el) {
  const head = [...el.querySelectorAll(':scope > thead > tr')], body = [...el.querySelectorAll(':scope > tbody > tr')].filter(r => !skip(r)), foot = [...el.querySelectorAll(':scope > tfoot > tr')];
  const all = [...head, ...body, ...foot]; if (!all.length) return null;
  const ncol = Math.max(...all.map(r => [...r.children].reduce((a, c) => a + (+c.getAttribute('colspan') || 1), 0)));
  const fs0 = ncol <= 4 ? 8 : ncol <= 6 ? 7.4 : 7, minFs = ncol <= 5 ? 7 : 6.2;
  const shown = body.slice(0, 400);
  const cellOf = (c, isHead, isFoot) => ({c, runs: clean(inline(c, isHead ? {bold: true, color: C.muted} : isFoot ? {bold: true} : {})), head: isHead, foot: isFoot, span: +c.getAttribute('colspan') || 1, num: c.classList.contains('num')});
  const grid = [...head.map(r => [...r.children].map(c => cellOf(c, true))), ...shown.map(r => [...r.children].map(c => cellOf(c))), ...foot.map(r => [...r.children].map(c => cellOf(c, false, true)))];
  // Natural one-line width and widest word per column, from cells that sit in one column.
  const cols = Array.from({length: ncol}, () => ({line: 0, word: 0, num: true, any: false}));
  grid.forEach(row => { let i = 0; row.forEach(x => { if (x.span === 1 && cols[i]) {
    const size = x.head ? fs0 - .8 : fs0, m = runsW(x.head ? x.runs.map(r => ({...r, characterSpacing: .3})) : x.runs, size, x.head || x.foot);
    cols[i].line = Math.max(cols[i].line, m.line); cols[i].word = Math.max(cols[i].word, m.word);
    if (!x.head && !x.foot && m.line > 0) { cols[i].any = true; if (!x.num) cols[i].num = false; }
  } i += x.span; }); });
  // Smallest type: 7pt in portrait; a landscape page may go down to 6.2pt for very wide tables.
  let plan = fitTable(cols, ncol, fs0, W < LANDSCAPE.w ? Math.max(minFs, 7) : minFs);
  // A small table (a handful of rows) wraps its widest column rather than getting a landscape page to itself.
  if (!plan && W < LANDSCAPE.w && shown.length > 5) {
    // Too wide for a portrait page: lay it out for a landscape page; compose() gives it landscape pages of its own.
    const keep = [W, MAXW, PAGE_H]; W = MAXW = LANDSCAPE.w; PAGE_H = LANDSCAPE.h;
    const node = table(el); [W, MAXW, PAGE_H] = keep; WIDE++; node.wide = true; return node;
  }
  if (!plan) {
    // Last resort: every text column may wrap.
    const fs = minFs, k = fs / fs0, nat = cols.map(c => c.line * k + 1);
    const long = cols.map((c, i) => !c.num && nat[i] > 40);
    plan = {fs, nat, long, room: W - 10 * (ncol - 1) - nat.reduce((a, v, i) => a + (long[i] ? 0 : v), 0)};
  }
  const {fs, nat, long} = plan;
  // Long columns share the room in proportion to their natural width; with none, the widest text column takes the slack.
  // Water-filling: the shortest long column gets its full width if its fair share allows, the rest split what's left.
  let widths = nat.slice(), left = plan.room;
  const order = nat.map((v, i) => [v, i]).filter(([, i]) => long[i]).sort((a, b) => a[0] - b[0]);
  order.forEach(([v, i], j) => { const share = left / (order.length - j); widths[i] = Math.max(20, Math.min(v, share)); left -= widths[i]; });
  if (left > 1 && order.length) widths[order[order.length - 1][1]] += left;
  if (!long.some(Boolean)) { const flex = cols.map((c, i) => [c.num ? -1 : nat[i], i]).sort((a, b) => b[0] - a[0])[0][1]; widths[flex] = '*'; }
  const k = fs / fs0;
  const cell = x => {
    const o = {text: x.runs.map(r => r.fontSize ? {...r, fontSize: r.fontSize * k} : r), fontSize: x.head ? fs - .8 : fs, alignment: x.num ? 'right' : 'left'};
    if (x.span > 1) o.colSpan = x.span;
    if (x.head) o.characterSpacing = .3;
    return o;
  };
  const rows = grid.map(row => { const cells = []; let i = 0; row.forEach(x => { const o = cell(x); if (!long[i] || x.span > 1 && !long.slice(i, i + x.span).some(Boolean)) o.noWrap = true; cells.push(o); for (let j = 1; j < x.span; j++) cells.push({}); i += x.span; }); while (cells.length < ncol) cells.push({text: ''}); return cells; });
  if (body.length > 400) rows.splice(head.length + 400, 0, [{text: `… ${body.length - 400} more rows on the website`, colSpan: ncol, fontSize: fs, color: C.muted}, ...Array(ncol - 1).fill({})]);
  // Keep rows whole unless a row is so tall that keeping it whole would leave a big gap at the bottom of a page.
  const lineH = fs * 1.2 * 1.2, tall = grid.some(row => { let i = 0; return row.some(x => { const w = typeof widths[i] === 'number' ? widths[i] : 200;
    const m = runsW(x.runs, fs, x.head), lines = long[i] ? Math.ceil(m.line * k / Math.max(20, w)) + m.lines - 1 : m.lines; i += x.span; return lines * lineH + 6 > PAGE_H * .28; }); });
  return {table: {headerRows: head.length, widths, body: rows, dontBreakRows: !tall}, margin: [0, 2, 0, 10],
    layout: {hLineWidth: (i, n) => (i === 0 || i === n.table.body.length) ? 0 : (i === head.length ? .8 : .4), vLineWidth: () => 0, hLineColor: i => i === head.length ? '#C9CED6' : C.line,
      paddingTop: () => 3, paddingBottom: () => 3, paddingLeft: i => i ? 5 : 0, paddingRight: (i, n) => i === n.table.widths.length - 1 ? 0 : 5,
      fillColor: (i) => (i >= rows.length - foot.length && foot.length) ? '#F6F8FB' : null}};
}
function kv(el) {
  const rows = []; let dt = null;
  [...el.children].flatMap(c => c.tagName === 'DIV' ? [...c.children] : [c]).forEach(c => { if (c.tagName === 'DT' && !c.classList.contains('span')) dt = c; else if (c.tagName === 'DD') { rows.push(dt && !c.classList.contains('span') ? [{text: clean(inline(dt)), color: C.muted, fontSize: 8}, {text: clean(inline(c)), fontSize: 8}] : [{text: clean(inline(c)), fontSize: 7.5, color: C.muted, colSpan: 2}, {}]); dt = null; } });
  const lw = Math.min(MAXW / 3, Math.max(60, ...rows.filter(r => !r[0].colSpan).map(r => runsW(r[0].text, 8).line + 2)));
  rows.forEach(r => { if (!r[0].colSpan) r[0].noWrap = lw < MAXW / 3; });
  return rows.length ? {table: {widths: [lw, '*'], body: rows}, layout: {defaultBorder: false, paddingTop: () => 2, paddingBottom: () => 2, paddingLeft: () => 0}, margin: [0, 0, 0, 4]} : null;
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
    // Short items and paragraphs are kept whole, so a page never starts with the last line of one.
    if (!hasBlocks(li)) { const r = clean(inline(li)); return li.textContent.length < 700 ? {stack: [{text: r, fontSize: 9}], unbreakable: true, margin: [0, 0, 0, 2]} : {text: r, fontSize: 9, margin: [0, 0, 0, 2]}; }
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
  const prev = MAXW; MAXW = (W - 14 * (n - 1)) / n - 22;
  const kids = [...el.children].filter(x => !skip(x)).map(x => { const o = []; walk(x, o, true); return o.length ? {stack: o} : null; }).filter(Boolean);
  MAXW = prev;
  const rows = []; for (let i = 0; i < kids.length; i += n) rows.push({columns: kids.slice(i, i + n).concat(Array(Math.max(0, n - kids.slice(i, i + n).length)).fill({text: ''})), columnGap: 14, unbreakable: [...el.children].slice(i, i + n).every(x => x.textContent.length < 1200)});
  return {stack: rows, margin: [0, 0, 0, 4]};
}
function card(el, title) {
  const prev = MAXW; MAXW -= 18; const body = blocksOf(el); MAXW = prev;
  return {table: {widths: ['*'], body: [[{stack: body, margin: [8, 6, 8, 4]}]]}, layout: {hLineWidth: () => .6, vLineWidth: () => .6, hLineColor: () => C.line, vLineColor: () => C.line, paddingLeft: () => 0, paddingRight: () => 0}, margin: [0, 0, 0, 8], unbreakable: el.textContent.length < 1400};
}
function walk(el, out, inGrid) {
  if (el.nodeType !== 1 || skip(el)) return;
  const t = el.tagName, cl = el.classList;
  if (t === 'svg' || t === 'SVG') { if (el.closest('.cmp-bar')) return; out.push(svgNode(el, inGrid ? W / 2 - 10 : (cl.contains('ex-fig') ? 240 : W))); return; }
  if (t === 'H1') return;
  if (t === 'H2') { out.push({text: textOf(el), style: 'h2', headlineLevel: 1}); return; }
  if (t === 'H3') { out.push({text: textOf(el), style: 'h3', headlineLevel: 2}); return; }
  if (t === 'H4') { out.push({text: clean(inline(el)), style: 'h4', headlineLevel: 3}); return; }
  if (cl.contains('eyebrow')) { out.push({text: textOf(el).toUpperCase(), fontSize: 6.8, color: C.muted, characterSpacing: .6, margin: [0, 4, 0, 2]}); return; }
  if (t === 'TABLE') { const x = table(el); if (x) out.push(x); return; }
  if (t === 'DL') { const x = kv(el); if (x) out.push(x); return; }
  if (t === 'UL' && cl.contains('roster')) { out.push({table: {widths: [62, '*', 'auto'], body: [...el.children].map(li => [{text: textOf(li.querySelector('.seat')), fontSize: 7.5, color: C.muted}, {stack: [{text: textOf(li.querySelector('.who b, .who .vacant')), fontSize: 8.5}].concat(li.querySelector('.who small') ? [{text: textOf(li.querySelector('.who small')), fontSize: 7, color: C.muted}] : [])}, {text: textOf(li.querySelector('.r-term')), fontSize: 7, color: C.muted}])}, layout: {hLineWidth: (i, n) => i > 0 && i < n.table.body.length ? .5 : 0, vLineWidth: () => 0, hLineColor: () => C.line, paddingLeft: () => 0, paddingRight: () => 4}, margin: [0, 0, 0, 4]}); return; }
  if ((t === 'UL' || t === 'OL') && (cl.contains('findings') || cl.contains('results'))) { [...el.children].filter(li => !skip(li)).forEach(li => out.push(card(li))); return; }
  if (t === 'UL' || t === 'OL') { if (cl.contains('leg')) out.push(legend(el)); else { const x = list(el); if (x) out.push(x); } return; }
  // Ruled lines to write on (the meeting briefing): data-lines of them, the page width.
  if (cl.contains('write-lines')) { const n = Math.min(+el.dataset.lines || 4, 30); out.push({canvas: Array.from({length: n}, (_, i) => ({type: 'line', x1: 0, y1: 19 * (i + 1), x2: W, y2: 19 * (i + 1), lineWidth: .5, lineColor: '#C9D1DC'})), margin: [0, 0, 0, 8]}); return; }
  // One agenda item and its writing lines stay on the same page.
  if (cl.contains('brief-item')) { const o = []; [...el.children].forEach(c => walk(c, o, inGrid)); if (o.length) out.push({stack: o, unbreakable: true, margin: [0, 4, 0, 0]}); return; }
  if (cl.contains('kpis')) { out.push(kpis(el)); return; }
  if (cl.contains('bill-hd')) { const sp = [...el.children]; out.push({stack: sp.map(x => x.classList.contains('eyebrow') ? {text: textOf(x).toUpperCase(), fontSize: 6.8, color: C.muted, characterSpacing: .6} : x.classList.contains('bill-v') ? {text: clean(inline(x)), fontSize: 18, bold: true, margin: [0, 1, 0, 1]} : {text: clean(inline(x)), fontSize: 7.8, color: C.muted}), margin: [0, 0, 0, 4]}); return; }
  if (cl.contains('hbars')) { const x = hbars(el); if (x) out.push(x); return; }
  if (cl.contains('dv')) { const x = dvbars(el); if (x) out.push(x); return; }
  if (cl.contains('yh')) { const x = yhbars(el); if (x) out.push(x); return; }
  if (cl.contains('dv-legend')) { const x = swatches(el); if (x) out.push(x); return; }
  if (cl.contains('vbars')) { out.push(vbars(el)); return; }
  if (cl.contains('stackbar')) { out.push(stackbar(el)); return; }
  if (cl.contains('cmp')) { out.push({columns: [...el.querySelectorAll('.cmp-col')].map(c => ({stack: [{text: textOf(c.querySelector('.eyebrow')).toUpperCase(), fontSize: 6.5, color: C.muted}, {text: textOf(c.querySelector('.bill-v')), fontSize: 15, bold: true}, {text: textOf(c.querySelector('.cmp-save')), fontSize: 7.5, color: C.muted}]})), columnGap: 10, margin: [0, 2, 0, 8]}); return; }
  if (cl.contains('callout')) { out.push({table: {widths: [3, '*'], body: [[{text: '', fillColor: C.amber}, {stack: blocksOf(el), margin: [6, 4, 4, 4], fillColor: '#FFF8EC'}]]}, layout: 'noBorders', margin: [0, 2, 0, 10], unbreakable: el.textContent.length < 900}); return; }
  if (cl.contains('profiles') || cl.contains('officers') || cl.contains('ui-people') || cl.contains('ui-row')) { out.push(grid(el, W > PORTRAIT.w ? 4 : 3)); return; }
  if (cl.contains('gov-grid')) { out.push(grid(el, 2)); return; }
  if (cl.contains('addr-grid') || cl.contains('cards') || cl.contains('two') || cl.contains('st-wrap')) { out.push(grid(el, 2)); return; }
  if (cl.contains('card') || cl.contains('prof') || cl.contains('fd') || cl.contains('arg') || cl.contains('g-term') || cl.contains('trend-box') || cl.contains('calc')) { out.push(card(el)); return; }
  if (cl.contains('explain')) { const kids = [...el.children].filter(x => !skip(x)); const fig = kids.find(k => k.tagName.toLowerCase() === 'svg'); const txt = kids.filter(k => k !== fig).flatMap(k => blocksOf(k));
    out.push({table: {widths: ['*'], body: [[{columns: fig ? [{stack: txt, width: '*'}, {...svgNode(fig, 200), width: 200}] : [{stack: txt}], columnGap: 14, margin: [10, 8, 10, 6], fillColor: '#F8FAFC'}]]}, layout: 'noBorders', margin: [0, 0, 0, 10]}); return; }
  if (t === 'DETAILS') { [...el.children].forEach(c => { if (c.tagName === 'SUMMARY') out.push({text: textOf(c), style: 'h4', headlineLevel: 3}); else walk(c, out, inGrid); }); return; }
  if (t === 'P') { const r = clean(inline(el)); if (r.length) { const muted = cl.contains('note') || cl.contains('muted'), small = muted || cl.contains('small'); out.push({stack: [{text: r, fontSize: small ? 7.8 : 9, color: muted ? C.muted : C.ink}], unbreakable: el.textContent.length < 700, margin: [0, 0, 0, 6]}); } return; }
  // A row with a small icon (a legend swatch drawn as an svg) and a label: the icon at text size, then the label.
  const kids = [...el.children].filter(c => !skip(c)), icons = kids.filter(c => c.tagName.toLowerCase() === 'svg' && +(c.getAttribute('width') || 99) <= 24);
  if (icons.length && icons.length === kids.filter(c => BLOCK.test(c.tagName.toUpperCase())).length) {
    const r = clean(inline(el)); out.push({columns: [{...svgNode(icons[0], 9), width: 9, margin: [0, 1, 4, 0]}, {text: r, fontSize: 8, color: C.muted}], columnGap: 0, margin: [0, 0, 0, 2]}); return;
  }
  const hasBlock = [...el.children].some(c => BLOCK.test(c.tagName.toUpperCase()) || c.classList.contains('hb'));
  if (hasBlock) { [...el.children].forEach(c => walk(c, out, inGrid)); return; }
  const r = clean(inline(el)); if (r.length) out.push({text: r, fontSize: 9, margin: [0, 0, 0, 4]});
}

/* ---------- document ---------- */
async function logo() {
  try { const img = new Image(); img.src = '/assets/flux-labs.webp'; await img.decode(); const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight; c.getContext('2d').drawImage(img, 0, 0); return c.toDataURL('image/png'); } catch (e) { return null; }
}
async function build() {
  await fonts();
  W = MAXW = PORTRAIT.w; PAGE_H = PORTRAIT.h; WANT_LANDSCAPE = false; WIDE = 0;
  let doc = await compose('portrait');
  // Wide tables get landscape pages of their own (from their heading to the next heading). If a wide table sits inside
  // a card or a column, or there are many of them, the whole report goes landscape instead.
  const body = doc.content, wide = body.filter(n => n.wide).length;
  if (WIDE && (wide < WIDE || wide > 2)) WANT_LANDSCAPE = true;
  else if (wide) landscapeSections(body);
  if (WANT_LANDSCAPE) { W = MAXW = LANDSCAPE.w; PAGE_H = LANDSCAPE.h; doc = await compose('landscape'); }
  return doc;
}
// A heading (and its one-line subtitle) is glued to the block after it when that block can't split, such as a card or
// a row of cards, so the heading moves to the next page with it instead of staying behind.
function keepWithNext(body) {
  for (let i = 0; i < body.length; i++) {
    if (!body[i].headlineLevel) continue;
    let j = i + 1; if (body[j] && !body[j].headlineLevel && body[j].text && !body[j].table && JSON.stringify(body[j].text).length < 300) j++;
    const n = body[j]; if (!n || n.headlineLevel) continue;
    let first = null;
    if (n.unbreakable) { first = n; body.splice(j, 1); }
    else if (n.stack && n.stack[0] && n.stack[0].unbreakable) first = n.stack.shift();
    if (!first) continue;
    const lvl = body[i].headlineLevel; delete body[i].headlineLevel; const glued = {stack: [...body.slice(i, j), first], unbreakable: true, headlineLevel: lvl};
    body.splice(i, j - i, glued);
  }
}
// Each top-level heading carries the room it needs at the bottom of a page: itself, a short subtitle and the start of
// what follows (a few lines, a table's header and first rows, or a whole chart). pdfmake reports unreliable positions
// for content inside blocks it keeps together, so the test uses only the heading's own position. The number travels in
// the node id ("hb:<points>:<index>") because pageBreakBefore sees only a few fields of each node.
function needH(n) {
  if (!n) return 0;
  if (n.svg) return (n._h || 200) + 10;
  if (n.table) return 50;
  if (n.ul || n.ol || n.columns) return 40;
  if (n.stack) return needH(n.stack[0]);
  if (typeof n.text !== 'undefined') { const len = JSON.stringify(n.text).length; return Math.min(3, Math.ceil(len / 110)) * 12 + 6; }
  return 36;
}
function linkHeadings(body) {
  body.forEach((n, i) => {
    if (!n.headlineLevel || n.id) return;
    let need = 22, j = i + 1;
    while (body[j] && !body[j].headlineLevel && typeof body[j].text !== 'undefined' && !body[j].table && JSON.stringify(body[j].text).length < 300 && j - i < 4) { need += 13; j++; }
    need += body[j] && body[j].headlineLevel ? 40 : needH(body[j]);
    n.id = 'hb:' + Math.round(Math.min(need, PAGE_H * .6)) + ':' + i; // ids must be unique
  });
}
function headingBreak(node, after, next) {
  if (!node.headlineLevel || !next.length || !node.startPosition) return false;
  const need = +((node.id || '').split(':')[1]) || 60;
  return (1 - node.startPosition.verticalRatio) * PAGE_H < need;
}
function landscapeSections(body) {
  const isHead = n => n.headlineLevel && n.headlineLevel <= 2;
  for (let i = 0; i < body.length; i++) {
    if (!body[i].wide) continue;
    // Start at the table's own heading (any level), never reaching back past another table.
    let a = i; while (a > 0 && i - a < 3 && !body[a].headlineLevel && !body[a - 1].table && !body[a - 1].wide) a--; if (!body[a].headlineLevel) a = i;
    let b = i + 1; while (b < body.length && !isHead(body[b]) && !body[b].wide && !body[b].table) b++;
    if (b < body.length && body[b].table && !body[b].wide) while (b - 1 > i && (body[b - 1].headlineLevel || (typeof body[b - 1].text !== 'undefined' && JSON.stringify(body[b - 1].text).length < 300))) b--;
    body[a] = {stack: [body[a]], pageBreak: 'before', pageOrientation: 'landscape'};
    // A short tail (a closing note or two) stays on the landscape page rather than getting a portrait page of its own.
    if (b < body.length && (body.length - b > 4 || body.slice(b).some(n => n.wide || n.svg))) body[b] = {stack: [body[b]], pageBreak: 'before', pageOrientation: 'portrait'};
    i = b - 1;
  }
}
async function compose(orientation) {
  const root = document.querySelector('main .page') || document.querySelector('main .wrap') || document.querySelector('main');
  const h1 = root.querySelector('h1'), title = window.BCReportTitle ? window.BCReportTitle() : h1 ? textOf(h1) : document.title;
  const header = h1 ? h1.closest('header') || h1.parentElement : null;
  const eyebrow = window.BCReportEyebrow ? window.BCReportEyebrow() : header?.querySelector('.eyebrow') ? textOf(header.querySelector('.eyebrow')) : 'BayCounty.me';
  const lede = header?.querySelector('.lede') ? textOf(header.querySelector('.lede')) : '';
  const meta = document.getElementById('printMeta');
  const sub = window.BCReportMeta ? window.BCReportMeta() : (meta && meta.textContent.trim() ? meta.textContent.trim() : '');
  const body = [];
  [...root.children].forEach(c => { if (c === header || (header && c.contains(header))) { [...header.children].forEach(x => { if (!x.querySelector('h1') && x.tagName !== 'H1' && !x.classList.contains('stamp') && !x.classList.contains('brand') && !x.classList.contains('tx-brand')) walk(x, body); }); return; } walk(c, body); });
  // Only top-level headings move to the next page; one inside a card or column moves with its card.
  const strip = n => { if (Array.isArray(n)) n.forEach(strip); else if (n && typeof n === 'object') { delete n.headlineLevel; Object.values(n).forEach(strip); } };
  body.forEach(n => { const h = n.headlineLevel; strip(n); if (h) n.headlineLevel = h; });
  keepWithNext(body);
  linkHeadings(body);
  const date = new Date().toLocaleDateString('en-US', {month: 'long', day: 'numeric', year: 'numeric'});
  const url = location.host + location.pathname.replace(/\/$/, '') + location.search;
  const lg = await logo();
  const cover = [
    {text: eyebrow.toUpperCase(), fontSize: 7.5, color: C.salmon, bold: true, characterSpacing: 1},
    {text: title, fontSize: 22, bold: true, color: C.navy, margin: [0, 3, 0, 4], lineHeight: 1.05},
    lede ? {text: lede, fontSize: 9.5, color: C.muted, margin: [0, 0, 0, 6], lineHeight: 1.25} : null,
    sub ? {text: sub, fontSize: 8.5, color: C.ink, margin: [0, 0, 0, 4]} : null,
    {text: [{text: 'Report exported ' + date + ' · '}, {text: url, link: location.href, color: C.blue}], fontSize: 7.5, color: C.muted},
    {canvas: [{type: 'line', x1: 0, y1: 0, x2: W, y2: 0, lineWidth: 1.2, lineColor: C.navy}], margin: [0, 8, 0, 12]},
  ].filter(Boolean);
  return {
    pageSize: 'LETTER', pageOrientation: orientation, pageMargins: [40, 58, 40, 52],
    // A heading never ends a page: if what follows it starts on the next page, the heading moves there too.
    pageBreakBefore: headingBreak,
    info: {title: title + ' · BayCounty.me', author: 'BayCounty.me (Flux Labs)', subject: lede, creator: 'BayCounty.me'},
    defaultStyle: {font: 'Roboto', fontSize: 9, color: C.ink, lineHeight: 1.2},
    styles: {h2: {fontSize: 13, bold: true, color: C.navy, margin: [0, 10, 0, 5]}, h3: {fontSize: 10.5, bold: true, color: C.ink, margin: [0, 6, 0, 3]}, h4: {fontSize: 9, bold: true, color: C.ink, margin: [0, 5, 0, 3]}},
    header: (page) => ({margin: [40, 22, 40, 0], columns: [
      {text: [{text: 'BayCounty', bold: true, color: C.navy}, {text: '.me', bold: true, color: C.salmon}], fontSize: 11, width: 'auto'},
      {text: page > 1 ? title : '', fontSize: 7.5, color: C.muted, alignment: 'right', margin: [0, 2, 0, 0]}]}),
    footer: (page, pages) => ({margin: [40, 14, 40, 0], columns: [
      lg ? {stack: [{text: 'POWERED BY', fontSize: 5.5, color: C.muted, characterSpacing: .8}, {image: lg, width: 56, margin: [0, 1, 0, 0]}], width: 'auto', link: 'https://fluxlabs.net/'} : {text: 'Powered by Flux Labs', fontSize: 7, color: C.muted, width: 'auto'},
      {text: 'Public records · sources linked in the report · corrections: hello@fluxlabs.net', fontSize: 6.5, color: C.muted, alignment: 'center', margin: [0, 5, 0, 0]},
      {text: `Page ${page} of ${pages}`, fontSize: 7, color: C.muted, alignment: 'right', width: 'auto', margin: [0, 5, 0, 0]}]}),
    content: [...cover, ...body],
  };
}
async function exportPDF(btn) {
  const label = btn ? btn.innerHTML : '';
  try {
    if (btn) { btn.disabled = true; btn.lastChild.textContent = 'Building PDF…'; }
    document.querySelectorAll('main details').forEach(d => { d.dataset.wasOpen = d.open; d.open = true; });
    const root = document.documentElement, th = root.getAttribute('data-theme'); root.setAttribute('data-theme', 'light'); window.__bcTheme = th;
    if (window.BCReportBefore) await window.BCReportBefore();
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    await ready();
    const doc = await build();
    const name = 'BayCounty.me - ' + (doc.info.title.replace(' · BayCounty.me', '')).replace(/[^\w .,'-]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 80) + ' - ' + new Date().toLocaleDateString('en-CA') + '.pdf';
    await new Promise((res, rej) => { try { window.pdfMake.createPdf(doc).download(name, res); } catch (e) { rej(e); } });
  } catch (e) {
    console.error(e); alert('Sorry, the PDF could not be built. Your browser\'s Print > Save as PDF still works.');
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
