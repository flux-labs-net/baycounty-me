// Link-preview cards drawn on request (api/og.js), for pages the static build doesn't draw one for: each restaurant's
// page and every /profile/<kind>/<id> page. Same look as the build's cards (site/og.py, direction A): deep navy, the
// BayCounty.me mark, an amber chip, the name, one big amber figure, the county outline and the four-color strip.
// Pure layout (no I/O) so tests can check the wording; api/og.js renders it with @vercel/og.
const fs = require('fs');
const path = require('path');

const W = 1200, H = 630;
const C = {bg: '#14295A', glow: '#24488F', amber: '#E8A33D', salmon: '#E5564A', teal: '#1F8A7A', blue: '#3F6FB0', soft: '#C9D6EE'};
const h = (type, style, ...children) => ({type, props: {style: type === 'div' ? {display: 'flex', ...style} : style, children: children.flat().filter(c => c != null && c !== false && c !== '')}});

let MAP;
const mapUri = () => MAP || (MAP = 'data:image/svg+xml;base64,' + fs.readFileSync(path.join(__dirname, 'map.svg')).toString('base64'));
const fit = (t, sizes) => { for (const [n, px] of sizes) if (t.length <= n) return px; return sizes[sizes.length - 1][1]; };
const clip = (t, n) => { t = String(t || '').replace(/\s+/g, ' ').trim(); return t.length <= n ? t : t.slice(0, t.lastIndexOf(' ', n - 1) > n * 0.6 ? t.lastIndexOf(' ', n - 1) : n - 1) + '…'; };

// c: {eyebrow, title, sub, stat, label, desc}
function card(c) {
  const title = clip(c.title, 90), stat = clip(c.stat, 22);
  const ts = stat ? fit(title, [[18, 76], [28, 60], [44, 50], [70, 44], [999, 38]]) : fit(title, [[28, 76], [44, 64], [70, 54], [999, 46]]);
  const ss = fit(stat, [[6, 168], [9, 140], [13, 110], [99, 84]]);
  const pin = {type: 'svg', props: {width: 30, height: 30, viewBox: '0 0 24 24', children: [
    {type: 'path', props: {d: 'M12 2C7.6 2 4 5.5 4 9.9 4 15.6 12 22 12 22s8-6.4 8-12.1C20 5.5 16.4 2 12 2z', fill: '#fff'}},
    {type: 'circle', props: {cx: 12, cy: 10, r: 3.2, fill: C.bg}}]}};
  return h('div', {width: W, height: H, display: 'flex', position: 'relative', background: C.bg, color: '#fff', fontFamily: 'Poppins'},
    h('div', {position: 'absolute', left: 0, top: 0, width: W, height: H, display: 'flex', backgroundImage: `radial-gradient(900px 500px at 85% 20%, ${C.glow} 0%, rgba(20,41,90,0) 60%)`}),
    {type: 'img', props: {src: mapUri(), width: 478, height: 580, style: {position: 'absolute', right: -30, top: 60, opacity: 0.13}}},
    h('div', {position: 'absolute', left: 72, right: 72, top: 56, bottom: 0, display: 'flex', flexDirection: 'column'},
      h('div', {display: 'flex', justifyContent: 'space-between', alignItems: 'center'},
        h('div', {display: 'flex', alignItems: 'center', fontSize: 30, fontWeight: 700, letterSpacing: -0.3},
          pin, h('span', {marginLeft: 10}, 'BayCounty'), h('span', {color: C.salmon}, '.me')),
        h('div', {display: 'flex', fontSize: 19, fontWeight: 600, letterSpacing: 1.9, textTransform: 'uppercase', color: C.bg, background: C.amber, padding: '8px 16px', borderRadius: 999}, clip(c.eyebrow, 34))),
      h('div', {display: 'flex', marginTop: 44, fontSize: ts, lineHeight: 1.1, fontWeight: 600, letterSpacing: -ts * 0.02, maxWidth: stat ? 900 : 960}, title),
      c.sub ? h('div', {display: 'flex', marginTop: 14, fontSize: 28, lineHeight: 1.3, fontWeight: 500, opacity: 0.9, maxWidth: 900}, clip(c.sub, 110)) : null,
      stat
        ? h('div', {display: 'flex', flexDirection: 'column', marginTop: 'auto', marginBottom: 58},
          h('div', {display: 'flex', fontSize: ss, lineHeight: 0.95, fontWeight: 700, letterSpacing: -ss * 0.035, color: C.amber}, stat),
          c.label ? h('div', {display: 'flex', marginTop: 16, fontSize: 26, lineHeight: 1.3, fontWeight: 500, color: C.soft, maxWidth: 820}, clip(c.label, 120)) : null)
        : h('div', {display: 'flex', marginTop: 'auto', marginBottom: 64, fontSize: 30, lineHeight: 1.4, fontWeight: 500, color: C.soft, maxWidth: 820}, clip(c.desc, 150))),
    h('div', {position: 'absolute', left: 0, right: 0, bottom: 0, height: 12, display: 'flex'},
      ...[C.salmon, C.amber, C.teal, C.blue].map(bg => h('div', {flex: 1, background: bg}))));
}

let FONTS;
const fonts = () => FONTS || (FONTS = [['Medium', 500], ['SemiBold', 600], ['Bold', 700]].map(([n, weight]) =>
  ({name: 'Poppins', data: fs.readFileSync(path.join(__dirname, `Poppins-${n}.ttf`)), weight, style: 'normal'})));

const money = n => n >= 1e9 ? `$${(n / 1e9).toFixed(2)}B` : n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `$${Math.round(n / 1e3).toLocaleString('en-US')}K` : `$${Math.round(n).toLocaleString('en-US')}`;
const day = d => { const x = d && new Date(String(d).slice(0, 10) + 'T12:00:00Z'); return x && !isNaN(x) ? x.toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC'}) : ''; };
const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
// short results for the big figure (site/restaurants_page.py SHORT)
const SHORT = {'Met inspection standards': 'Met standards', 'Warning, follow-up visit set': 'Warning', 'Follow-up visit: fixed': 'Fixed on follow-up',
  'Follow-up visit: more time given': 'More time given', 'Fine recommended (administrative complaint)': 'Fine recommended',
  'Follow-up visit: not fixed, fine recommended': 'Fine recommended', 'Follow-up after complaint: fixed': 'Fixed',
  'Follow-up after complaint: not fixed': 'Not fixed', 'Follow-up after complaint: more time given': 'More time given',
  'Referred for an administrative decision': 'Referred', 'Ordered closed (emergency order)': 'Closed by the state',
  'Allowed to reopen': 'Reopened', 'Stayed closed: not fixed': 'Still closed', 'Stayed closed: more time given': 'Still closed'};

// A restaurant (restaurants row) and its latest inspection (restaurant-inspections row, optional).
function restaurantCard(r, last) {
  const where = [r.address, r.city].filter(Boolean).join(', ');
  const res = r.last_result ? (SHORT[r.last_result] || r.last_result) : '';
  let label = '';
  if (last) {
    const kind = String(last.inspection_type || '').replace(/ - Food$/, '').replace(/^Food-Licensing Inspection$/, 'Licensing');
    label = `${kind ? kind + ' inspection' : 'Inspection'} on ${day(last.date)}` + (last.total_violations ? ` · ${plural(+last.total_violations, 'violation')}, ${last.high_priority || 0} high priority` : ' · no violations');
  } else if (r.last_inspection) label = `Last inspected ${day(r.last_inspection)}`;
  return {eyebrow: 'Restaurant inspection', title: r.business_name, sub: where || r.kind, stat: res, label,
    desc: 'Every Florida food safety inspection since 2016: results, violations, warnings and closures.'};
}

// An entity profile (entity-profiles row, or getEntity().entity).
function entityCard(e, kindLabel) {
  const n = +e.connections || 0;
  let stat = '', label = '';
  if (+e.amount_received > 0) { stat = money(+e.amount_received); label = 'received in payments, gifts and grants in public records'; }
  else if (+e.amount_given > 0) { stat = money(+e.amount_given); label = 'given or paid in payments, gifts and grants in public records'; }
  else if (n > 0) { stat = plural(n, 'connection'); label = 'documented in public records, each with its source'; }
  return {eyebrow: kindLabel || e.kind_label || 'Profile', title: e.name, sub: e.subtitle || '', stat, label,
    desc: 'Every documented connection in Bay County public records: payments, contracts, board seats and businesses.'};
}

module.exports = {card, fonts, restaurantCard, entityCard, W, H, money, day};
