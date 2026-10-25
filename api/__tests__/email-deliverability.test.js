// Spam-filter hygiene for outgoing mail (api/_alerts.js finishEmail, api/manage.js one-click unsubscribe). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
process.env.ALERTS_SECRET = process.env.ALERTS_SECRET || 'test-secret';
process.env.RESEND_FULL_KEY = process.env.RESEND_FULL_KEY || 're_test';
const {finishEmail, htmlToText, prefsToken} = require('../_alerts');
const {adminSignInEmail} = require('../_emails');
const {codeEmail} = require('../_finance/auth');

test('a bare HTML fragment is sent as a full document with a footer', () => {
  const out = finishEmail({subject: 'Hi', html: '<p>Hello <a href="https://baycounty.me/x">there</a></p>', text: 'Hello'});
  assert.match(out.html, /^<!DOCTYPE html><html>/);
  assert.match(out.html, /<body/);
  assert.match(out.html, /Built by Flux Labs/);
  assert.equal(out.text, 'Hello');
});

test('a full document is left alone, and missing text is made from the HTML', () => {
  const html = '<!DOCTYPE html><html><body><p>One &amp; two</p><p><a href="https://baycounty.me/a">Open</a></p></body></html>';
  const out = finishEmail({subject: 'S', html});
  assert.equal(out.html, html);
  assert.equal(out.text, 'One & two\nOpen (https://baycounty.me/a)');
  assert.equal(htmlToText('<a href="https://x.y">https://x.y</a>'), 'https://x.y');
});

test('text-only mail stays text-only', () => {
  const out = finishEmail({subject: 'S', text: 'plain'});
  assert.equal(out.html, undefined);
  assert.equal(out.text, 'plain');
});

test('sign-in emails are full documents with a text part', () => {
  for (const m of [adminSignInEmail('https://baycounty.me/api/admin?action=verify&t=abc'), finishEmail(codeEmail('123456'))]) {
    assert.match(m.html, /<html[\s>]/);
    assert.ok(m.text.length > 20);
  }
});

test('one-click unsubscribe works without an Origin header and needs a valid token', async () => {
  const calls = [];
  global.fetch = async (url, opts) => { calls.push([url, opts.method]); return {ok: true, status: 200, json: async () => ({data: []})}; };
  const manage = require('../manage');
  const run = async (t, body) => {
    const res = {code: 0, headers: {}, setHeader(k, v) { this.headers[k] = v; }, status(c) { this.code = c; return this; }, json(b) { this.body = b; return this; }, send(b) { this.body = b; return this; }, end() { return this; }};
    await manage({method: 'POST', headers: {}, query: {t}, body}, res);
    return res;
  };
  const bad = await run('nope', 'List-Unsubscribe=One-Click');
  assert.equal(bad.code, 400);
  const ok = await run(prefsToken('a@example.com'), 'List-Unsubscribe=One-Click');
  assert.equal(ok.code, 200);
  assert.ok(calls.some(([u]) => u.includes('/contacts/a%40example.com')));
  const form = await run(prefsToken('a@example.com'), 'action=unsubscribe');
  assert.equal(form.code, 403); // the page's own forms still need to come from the site
});
