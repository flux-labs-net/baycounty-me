// Link previews drawn on request (api/og.js, api/_og/card.js) and the crawler page for profiles (api/meta.js).
// Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const {card, restaurantCard, entityCard, fonts, money, day} = require('../_og/card');
const {withMeta} = require('../meta');

const texts = node => typeof node === 'string' ? [node] : (node && node.props ? [].concat(node.props.children || []).flatMap(texts) : []);

test('a restaurant card names it and shows its latest result and inspection', () => {
  const c = restaurantCard({business_name: "Mosey's Downtown", kind: 'Restaurant with seating', address: '425 Grace Ave', city: 'Panama City',
    last_result: 'Met inspection standards', last_inspection: '2026-10-27'},
  {date: '2026-10-27', inspection_type: 'Routine - Food', total_violations: 7, high_priority: 1});
  assert.equal(c.eyebrow, 'Restaurant inspection');
  assert.equal(c.title, "Mosey's Downtown");
  assert.equal(c.sub, '425 Grace Ave, Panama City');
  assert.equal(c.stat, 'Met standards');
  assert.equal(c.label, 'Routine inspection on Oct 27, 2026 · 7 violations, 1 high priority');
  const clean = restaurantCard({business_name: 'X', last_result: 'Follow-up visit: fixed'}, {date: '2026-01-02', inspection_type: 'Food-Licensing Inspection', total_violations: 0});
  assert.equal(clean.stat, 'Fixed on follow-up');
  assert.equal(clean.label, 'Licensing inspection on Jan 2, 2026 · no violations');
});

test('a profile card leads with money received, then given, then connections', () => {
  assert.equal(entityCard({name: 'A', kind_label: 'Business', amount_received: 1.82e9}).stat, '$1.82B');
  assert.equal(entityCard({name: 'B', kind_label: 'Nonprofit', amount_given: 6.1e6}).stat, '$6.1M');
  const c = entityCard({name: 'C', kind_label: 'Committee or PAC', connections: 1});
  assert.equal(c.stat, '1 connection');
  assert.equal(c.eyebrow, 'Committee or PAC');
  assert.equal(entityCard({name: 'D'}).stat, '');
});

test('the card layout carries the words and long names are cut', () => {
  const words = texts(card({eyebrow: 'Restaurant inspection', title: 'A'.repeat(200), sub: 'Somewhere', stat: 'Met standards', label: 'Routine'}));
  assert.ok(words.includes('Restaurant inspection') && words.includes('Met standards') && words.includes('Somewhere'));
  assert.ok(words.some(w => w.endsWith('…') && w.length <= 90), 'title cut to 90 characters');
  assert.ok(words.includes('BayCounty') && words.includes('.me'));
});

test('fonts and the county outline ship with the function', () => {
  assert.equal(fonts().length, 3);
  assert.ok(fs.readFileSync(path.join(__dirname, '..', '_og', 'map.svg'), 'utf8').startsWith('<svg xmlns='));
  const vercel = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', 'vercel.json'), 'utf8'));
  assert.match(vercel.functions['api/og.js'].includeFiles, /api\/_og/);
});

test('formatting helpers', () => {
  assert.equal(money(950), '$950');
  assert.equal(money(12500), '$13K');
  assert.equal(day('2026-10-27'), 'Oct 27, 2026');
  assert.equal(day(null), '');
});

test('profile crawler page swaps in the profile title, summary, address and image, escaped', () => {
  const shell = '<title>Profile · BayCounty.me</title><meta name="description" content="A profile">'
    + '<link rel="canonical" href="https://baycounty.me/profile"><meta property="og:title" content="Profile">'
    + '<meta property="og:description" content="A profile"><meta property="og:url" content="https://baycounty.me/profile">'
    + '<meta property="og:image" content="https://baycounty.me/og/home.png"><meta property="og:image:alt" content="Profile">'
    + '<meta name="twitter:title" content="Profile"><meta name="twitter:description" content="A profile">'
    + '<meta name="twitter:image" content="https://baycounty.me/og/home.png"><meta name="twitter:image:alt" content="Profile">';
  const out = withMeta(shell, {title: 'Smith & Sons <Inc>: business', desc: 'Its "record"', url: 'https://baycounty.me/profile/business/x1',
    img: 'https://baycounty.me/api/og?p=%2Fprofile%2Fbusiness%2Fx1'});
  assert.match(out, /<title>Smith &amp; Sons &lt;Inc&gt;: business · BayCounty.me<\/title>/);
  assert.match(out, /og:title" content="Smith &amp; Sons &lt;Inc&gt;: business"/);
  assert.match(out, /twitter:description" content="Its &quot;record&quot;"/);
  assert.match(out, /rel="canonical" href="https:\/\/baycounty.me\/profile\/business\/x1"/);
  assert.equal((out.match(/api\/og\?p=%2Fprofile%2Fbusiness%2Fx1/g) || []).length, 2);
  assert.ok(!out.includes('og/home.png'));
});

test('link-preview crawlers, and only they, get the profile crawler page', () => {
  const vercel = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', 'vercel.json'), 'utf8'));
  const i = vercel.rewrites.findIndex(r => r.destination.startsWith('/api/meta'));
  const shell = vercel.rewrites.findIndex(r => r.source === '/profile/:kind/:id' && r.destination === '/profile');
  assert.ok(i >= 0 && i < shell, 'the crawler rewrite comes before the shell rewrite');
  const re = new RegExp('^' + vercel.rewrites[i].has[0].value + '$');
  for (const ua of ['facebookexternalhit/1.1 Facebot Twitterbot/1.0', 'Slackbot-LinkExpanding 1.0', 'Mozilla/5.0 (compatible; Discordbot/2.0)', 'WhatsApp/2.23', 'LinkedInBot/1.0'])
    assert.ok(re.test(ua), ua);
  assert.ok(!re.test('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1'));
});
