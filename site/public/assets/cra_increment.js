// How much property tax goes to the CRAs (/public-money/cra-tax-increment). Reads /api/v1/datasets/cra-agencies,
// cra-tax-increment and cra-increment-checks; holds no data.
(() => {
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const M = n => { if (n == null) return '—'; const a = Math.abs(n); return (a >= 1e9 ? '$' + (a / 1e9).toFixed(2) + 'B' : a >= 1e6 ? '$' + (a / 1e6).toFixed(1) + 'M' : a >= 1e4 ? '$' + Math.round(a / 1e3).toLocaleString() + 'K' : '$' + Math.round(a).toLocaleString()); };
const F = n => '$' + Math.round(n || 0).toLocaleString();
const COL = {'pcb-fbr': '--c-fbr', 'pcb-pier': '--c-pier', pc: '--c-pc', lh: '--c-lh', callaway: '--c-cw', springfield: '--c-sf', parker: '--c-pk'};
const SHORT = {'pcb-fbr': 'Front Beach Road', 'pcb-pier': 'Pier Park', pc: 'Panama City', lh: 'Lynn Haven', callaway: 'Callaway', springfield: 'Springfield', parker: 'Parker'};
const gov = (id, t) => window.BC && BC.href && BC.href('gov:' + id) ? BC.a('gov:' + id, t) : esc(t);
const cssv = n => getComputedStyle($('ciChart')).getPropertyValue(n).trim();
const sum = (a, f) => a.reduce((s, x) => s + (f(x) || 0), 0);
let A = [], Y = [], C = [], scen = 'mid', who = 'increment';

async function get(id) {
  const r = await fetch(`/api/v1/datasets/${id}?limit=1000`);
  if (!r.ok) throw new Error(id);
  return (await r.json()).data || [];
}

const order = () => A.map(a => a.cra_id);
const hist = () => Y.filter(r => r.scenario === 'history');
const proj = () => Y.filter(r => r.scenario === scen);

function kpis() {
  const h = hist(), last = Math.max(...h.map(r => r.fiscal_year)), y = h.filter(r => r.fiscal_year === last);
  const t = sum(y, r => r.increment), c = sum(y, r => r.county_amount), fbr = sum(y.filter(r => r.cra_id === 'pcb-fbr'), r => r.increment);
  const lo = sum(A, a => a.to_come_low), hi = sum(A, a => a.to_come_high);
  const first = Math.min(...h.map(r => r.fiscal_year));
  const k = (l, v, s) => `<div class="kpi"><span class="eyebrow">${l}</span><span class="v">${v}</span><span class="s">${s}</span></div>`;
  $('ciKpis').innerHTML = k(`Tax increment, FY${last}`, M(t), `All ${A.length} CRAs. ${Math.round(fbr / t * 100)}% is Front Beach Road`) +
    k(`Paid by Bay County, FY${last}`, M(c), `${Math.round(c / t * 100)}% of the total; the cities paid ${M(t - c)}`) +
    k(`Paid on record, FY${first} to FY${last}`, M(sum(h, r => r.increment)), `${M(sum(h, r => r.county_amount))} from the county. Early years are missing for several CRAs`) +
    k('Still to come, to each sunset', `${M(lo)}–${M(hi).slice(1)}`, 'Low to high growth scenario');
}

function chart() {
  const svg = $('ciChart'), W = 1000, H = 340, L = 56, R = 8, T = 12, B = 30;
  const all = [...hist(), ...proj()], ys = all.map(r => r.fiscal_year);
  const y0 = Math.min(...ys), y1 = Math.max(...ys), years = []; for (let y = y0; y <= y1; y++) years.push(y);
  const lastH = Math.max(...hist().map(r => r.fiscal_year));
  const by = {}; all.forEach(r => { (by[r.fiscal_year] ||= {})[r.cra_id] = r; });
  const tot = years.map(y => sum(Object.values(by[y] || {}), r => r[who]));
  const st = [1e6, 2e6, 5e6, 1e7, 2e7].find(s => Math.max(...tot) / s <= 6) || 2e7;
  const max = Math.max(Math.ceil(Math.max(...tot, 1) / st) * st, st);
  const step = (W - L - R) / years.length, bw = Math.max(step - 2, 1);
  const x = i => L + i * step, y = v => T + (H - T - B) * (1 - v / max);
  let o = '';
  for (let v = 0; v <= max; v += st) o += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="${cssv('--line')}"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${v ? '$' + v / 1e6 + 'M' : '$0'}</text>`;
  const pi = years.indexOf(lastH + 1);
  if (pi >= 0) o += `<rect x="${x(pi)}" y="${T}" width="${W - R - x(pi)}" height="${H - T - B}" fill="${cssv('--c-band')}"/><text x="${x(pi) + 6}" y="${T + 14}">Projected</text>`;
  years.forEach((yr, i) => {
    let base = 0;
    order().forEach(c => {
      const r = (by[yr] || {})[c]; if (!r || !(r[who] > 0)) return;
      const a = y(base), b = y(base + r[who]); base += r[who];
      const op = r.basis === 'filled gap' ? .45 : r.scenario !== 'history' ? .75 : 1;
      o += `<rect x="${x(i) + 1}" y="${b}" width="${bw}" height="${Math.max(0, a - b)}" fill="${cssv(COL[c])}" opacity="${op}"><title>FY${yr} ${SHORT[c]}: ${F(r[who])} (${esc(r.basis)})</title></rect>`;
    });
    if (yr % 5 === 0) o += `<text x="${x(i) + step / 2}" y="${H - B + 16}" text-anchor="middle">${yr}</text>`;
  });
  svg.innerHTML = o;
  $('ciLegend').innerHTML = order().map(c => `<span><i style="background:var(${COL[c]})"></i>${SHORT[c]}</span>`).join('') + '<span><i style="background:var(--c-pc);opacity:.45"></i>Filled gap</span>';
}

function table() {
  const key = {low: 'to_come_low', mid: 'to_come_mid', high: 'to_come_high'}[scen];
  const first = Math.min(...hist().map(r => r.fiscal_year)), last = Math.max(...hist().map(r => r.fiscal_year));
  $('ciTbl').innerHTML = `<thead><tr><th scope="col">CRA</th><th scope="col">Base</th><th scope="col" class="num">FY${last}</th><th scope="col" class="num">County share</th><th scope="col" class="num">Bay County</th><th scope="col" class="num">City</th><th scope="col" class="num">Paid on record</th><th scope="col">Sunset</th><th scope="col" class="num">Still to come</th></tr></thead><tbody>` +
    A.map(a => `<tr><th scope="row"><span class="ci-dot" style="background:var(${COL[a.cra_id]})"></span>${esc(a.cra)}<small>${gov(a.gov_id, a.city)}</small></th><td>${esc(a.base_year)}</td>
      <td class="num">${F(a.increment_fy2025)}</td><td class="num">${Math.round(a.county_share_fy2025 * 100)}%</td><td class="num">${F(a.county_fy2025)}</td><td class="num">${F(a.city_fy2025)}</td>
      <td class="num">${M(a.paid_on_record)}<small>FY${a.first_fy_on_record}–FY${last}${a.years_filled ? `, ${a.years_filled} yrs filled` : ''}</small></td>
      <td>${a.sunset_fy}${a.sunset_assumed ? '<span class="ci-tag">assumed</span>' : ''}</td><td class="num">${M(a[key])}</td></tr>`).join('') +
    `</tbody><tfoot><tr><th scope="row">All CRAs</th><td></td><td class="num">${F(sum(A, a => a.increment_fy2025))}</td><td class="num">${Math.round(sum(A, a => a.county_fy2025) / sum(A, a => a.increment_fy2025) * 100)}%</td><td class="num">${F(sum(A, a => a.county_fy2025))}</td><td class="num">${F(sum(A, a => a.city_fy2025))}</td><td class="num">${M(sum(A, a => a.paid_on_record))}<small>from FY${first}</small></td><td></td><td class="num">${M(sum(A, a => a[key]))}</td></tr></tfoot>`;
  $('ciSunsets').innerHTML = A.map(a => `<li><b>${esc(a.cra)}, ${a.sunset_fy}.</b> ${esc(a.sunset_basis)}</li>`).join('');
}

function whoBars() {
  const c = sum(A, a => a.county_fy2025), ci = sum(A, a => a.city_fy2025), t = c + ci;
  const row = (l, v, col) => `<div class="ci-who-r"><span>${l}</span><span class="ci-who-t"><b style="width:${(v / t * 100).toFixed(1)}%;background:var(${col})"></b></span><span class="ci-who-v">${v ? F(v) : '$0 (exempt)'}</span></div>`;
  $('ciWhoBars').innerHTML = row(gov('county', 'Bay County'), c, '--navy') + row('Cities, into their own CRAs', ci, '--blue') + row(gov('schools', 'School district'), 0, '--faint') + row(gov('nwfwmd', 'Water management district'), 0, '--faint');
}

function checks() {
  $('ciChecks').innerHTML = '<thead><tr><th scope="col">Official figure</th><th scope="col" class="num">Official</th><th scope="col" class="num">Estimate</th></tr></thead><tbody>' +
    C.map(k => `<tr><td>${esc(k.figure)} <a class="src" href="${esc(k.source_url)}" target="_blank" rel="noopener">source</a></td><td class="num">${M(k.official_figure)}</td><td class="num">${M(k.estimate)}<small>${k.difference_pct > 0 ? '+' : ''}${k.difference_pct}%</small></td></tr>`).join('') + '</tbody>';
}

function wire(id, attr, set) {
  $(id).addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    $(id).querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); set(b.dataset[attr]); chart(); table();
  });
}

Promise.all([get('cra-agencies'), get('cra-tax-increment'), get('cra-increment-checks')]).then(([a, y, c]) => {
  const ord = Object.keys(COL);
  A = a.sort((p, q) => ord.indexOf(p.cra_id) - ord.indexOf(q.cra_id)); Y = y; C = c.sort((p, q) => p.fiscal_year - q.fiscal_year);
  kpis(); chart(); table(); whoBars(); checks();
  wire('ciScen', 's', v => { scen = v; }); wire('ciWho', 'w', v => { who = v; });
  const redraw = () => chart();
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', redraw);
  new MutationObserver(redraw).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
}).catch(() => { $('ciKpis').innerHTML = '<p class="muted">The figures could not load. Try again, or download them from <a href="/open-data">Open data</a>.</p>'; });
})();
