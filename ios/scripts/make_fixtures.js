// Runs the website's own calculator and address-parsing code on sample inputs and writes the results,
// so the app's Swift ports can be tested against them (BayCountyKitTests/WebParityTests.swift).
// Usage: node ios/scripts/make_fixtures.js   (after a site build, from the repo root)
const fs = require('fs');
const root = __dirname + '/../..';
const T = JSON.parse(fs.readFileSync(root + '/site/public/data/app/tax.json'));
const A3 = JSON.parse(fs.readFileSync(root + '/site/public/data/app/amendment3.json'));

// --- tax.js: taxable() and billAt(), copied as-is
const D = T, L = D.years.length - 1;
function taxable(v, homestead, yi = L) {
  if (!homestead) return {school: v, other: v};
  const first = Math.min(v, 25000), second = Math.max(0, Math.min(v - 50000, D.second[yi]));
  return {school: Math.max(0, v - first), other: Math.max(0, v - first - second)};
}
function billAt(dist, yi, tv) {
  return dist.stack.map(id => { const a = D.auth[id], m = a.m[yi] || 0, base = a.school ? tv.school : tv.other; return {id, amt: base / 1000 * m}; });
}
const tax = [];
for (const dist of D.districts) for (const v of [0, 40000, 180000, 425000, 2500000]) for (const h of [true, false]) {
  const rows = billAt(dist, L, taxable(v, h)).filter(r => (D.auth[r.id].m[L] || 0) > 0);
  const trend = D.years.map((_, i) => billAt(dist, i, taxable(v, h, i)).reduce((a, x) => a + x.amt, 0));
  tax.push({d: dist.id, v, h, total: rows.reduce((a, r) => a + r.amt, 0), trend});
}

// --- amend.js: scenarios() and bill()
const AL = A3.districts[0].total.length - 1;
function scenarios(v, k) {
  const today = k === 'non' ? [v, v] : [Math.max(0, v - 25000), Math.max(0, v - Math.min(v, 25000) - Math.max(0, Math.min(v - 50000, A3.second)))];
  if (k === 'non') return [['Today', ...today], ['2027 bill', ...today], ['2028 bill and after', ...today]];
  const sch = Math.max(0, v - 25000);
  const e27 = k === 'new' ? 50000 : 150000, e28 = k === 'new' ? 51220 : 250000;
  return [['Today', ...today], ['2027 bill', sch, Math.max(0, v - e27)], ['2028 bill and after', sch, Math.max(0, v - e28)]];
}
function bill(dist, sc) {
  return dist.stack.map(id => { const a = A3.auth[id], m = a.m[AL] || 0, base = a.school ? sc[1] : sc[2]; return {amt: base / 1000 * m, m}; }).filter(r => r.m > 0);
}
const a3 = [];
for (const dist of A3.districts.slice(0, 4)) for (const v of [60000, 300000, 900000]) for (const k of ['home', 'new', 'non'])
  a3.push({d: dist.id, v, k, totals: scenarios(v, k).map(sc => bill(dist, sc).reduce((a, r) => a + r.amt, 0))});

// --- address.js: parseAddr() and whereFor(), extracted from the source
const src = fs.readFileSync(root + '/site/address.js', 'utf8');
const grab = (start, end) => src.slice(src.indexOf(start), src.indexOf(end, src.indexOf(start)));
eval(grab('const TYPES = {', 'const sq = '));
eval(grab('const sq = ', 'async function findAddr'));
const inputs = ['825 Ohio Ave', '825 ohio avenue, Lynn Haven FL 32444', '1614 N Ohio', '100 W 11th Street', '4800 US Hwy 98 #12',
  '17007 Panama City Beach Pkwy', '600 MLK Blvd', '23 Saint Andrews Blvd', '9 Seventh St Apt 3B', '1234 Thomas Dr Unit 1402', 'no number here', '42'];
const parse = inputs.map(s => { const a = parseAddr(s); return {input: s, parsed: a, where: a ? [whereFor(a, ['name', 'type', 'dir']), whereFor(a, ['name'])] : null}; });

// --- addr_page.shard_key / address.js shardOf
function shardOf(pid, n) { let h = 0x811c9dc5; for (const c of new TextEncoder().encode(pid)) h = Math.imul(h ^ c, 0x01000193) >>> 0; return 'h' + (h % n); }
const shards = ['00349-010-000', '12345-678-000', '30123-100-000', 'A-1'].map(p => ({p, ex: shardOf(p, 96), nav: shardOf(p, 128)}));

fs.writeFileSync(root + '/ios/BayCountyKit/Tests/BayCountyKitTests/Fixtures/web-parity.json', JSON.stringify({tax, a3, parse, shards}, null, 1));
console.log(`wrote ${tax.length} tax, ${a3.length} amendment, ${parse.length} parse, ${shards.length} shard cases`);

// --- api/_officials.js and api/_budget.js: who held each seat, and budget comparisons, from the published datasets
const dl = n => JSON.parse(fs.readFileSync(root + '/site/public/downloads/' + n + '.json'));
const {inOffice} = require(root + '/api/_officials.js');
const {compare} = require(root + '/api/_budget.js');
const terms = dl('officeholder-terms'), budgets = dl('budget-years');
const officials = [];
for (const gov of ['county', 'schools', 'lh', 'pc', 'mb', 'parker']) for (const year of [2016, 2019, 2023, 2026]) {
  const r = inOffice(terms, {gov, year});
  officials.push({gov, year, seats: r.seats.map(s => ({seat: s.seat, holders: s.holders.map(h => h.person_name + (h.part_of_period ? '*' : ''))}))});
}
const budget = [];
for (const gov of [...new Set(budgets.map(r => r.gov_id))]) for (const basis of ['adopted', 'actual']) {
  let r; try { r = compare(budgets, {gov, basis}); } catch (e) { continue; }
  const pick = ls => ls.slice(0, 5).map(l => ({key: l.key, from: l.from, to: l.to}));
  budget.push({gov, basis, from: r.from, to: r.to, totals: pick(r.totals),
    sections: Object.fromEntries(Object.entries(r.sections).map(([k, v]) => [k, pick(v)])), notes: r.notes,
    up: r.biggest_increase && r.biggest_increase.key, down: r.biggest_decrease && r.biggest_decrease.key});
}
fs.writeFileSync(root + '/ios/BayCountyKit/Tests/BayCountyKitTests/Fixtures/api-parity.json', JSON.stringify({officials, budget}, null, 1));
console.log(`wrote ${officials.length} officials, ${budget.length} budget comparison cases`);
