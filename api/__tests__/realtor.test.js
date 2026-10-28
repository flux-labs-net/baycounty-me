// Realtor console accounts (api/_realtor.js): branding validation and sign-in tokens. Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
process.env.ALERTS_SECRET = process.env.ALERTS_SECRET || 'test-secret';
const R = require('../_realtor');

const PNG = 'data:image/png;base64,' + Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0]).toString('base64');
const JPG = 'data:image/jpeg;base64,' + Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0, 0x10, 0x4a, 0x46]).toString('base64');

test('branding is cleaned: text trimmed, website normalized, colors checked, unknown fields dropped', () => {
  const b = R.cleanBrand({agent_name: '  Alex   Rivera ', website: 'samplerealty.example', color_primary: '#0F5E5C', email: 'Alex@Sample.example', logo: PNG, photo: JPG, is_admin: true});
  assert.equal(b.agent_name, 'Alex Rivera');
  assert.equal(b.website, 'https://samplerealty.example');
  assert.equal(b.color_primary, '#0f5e5c');
  assert.equal(b.email, 'alex@sample.example');
  assert.ok(!('is_admin' in b));
  assert.throws(() => R.cleanBrand({color_accent: 'red'}), /Colors/);
  assert.throws(() => R.cleanBrand({email: 'nope'}), /email/);
  assert.throws(() => R.cleanBrand({website: 'javascript:alert(1)'}), /web address/);
});

test('images must be real PNG or JPEG data, never SVG, and small', () => {
  assert.equal(R.image(PNG, 400000, 'Logo'), PNG);
  assert.throws(() => R.image('data:image/svg+xml;base64,PHN2Zz4=', 400000, 'Logo'), /PNG or JPEG/);
  assert.throws(() => R.image('data:image/png;base64,' + Buffer.from('<svg onload=x>').toString('base64'), 400000, 'Logo'), /doesn't look like/);
  assert.throws(() => R.image(PNG + 'A'.repeat(500000), 400000, 'Logo'), /too large/);
});

test('sign-in tokens are signed and expire', () => {
  const t = R.makeToken({kind: 'login', e: 'a@b.example', n: 'x', exp: Date.now() + 60e3});
  assert.equal(R.readToken(t).e, 'a@b.example');
  assert.equal(R.readToken(t.slice(0, -2) + 'xx'), null);
  assert.equal(R.readToken(R.makeToken({kind: 'login', exp: Date.now() - 1})), null);
});

test('sign-up is open unless REALTOR_SIGNUP=invite', () => {
  delete process.env.REALTOR_SIGNUP; assert.equal(R.signupMode(), 'open');
  process.env.REALTOR_SIGNUP = 'invite'; assert.equal(R.signupMode(), 'invite');
  delete process.env.REALTOR_SIGNUP;
});

test('emailed reports go out from hello@baycounty.me under the agent’s name, replies to the agent, PDF attached', () => {
  const pdf = Buffer.from('%PDF-1.3\n%test').toString('base64');
  const agent = {email: 'login@sample.example'};
  const m = R.reportEmail({to: 'Client@Buyer.example, second@buyer.example', pdf, address: '825 Ohio Ave', message: 'Hi Sam,\nhere it is', cc_me: true, filename: 'property-report-825-ohio-ave.pdf'},
    agent, {agent_name: 'Alex "Ace" Rivera', brokerage: 'Sample Realty', email: 'alex@sample.example'});
  assert.equal(m.from, '"Alex Ace Rivera via BayCounty.me" <hello@baycounty.me>');
  assert.equal(m.reply_to, 'alex@sample.example');
  assert.deepEqual(m.to, ['client@buyer.example', 'second@buyer.example']);
  assert.deepEqual(m.cc, ['alex@sample.example']);
  assert.equal(m.subject, 'Property report: 825 Ohio Ave');
  assert.equal(m.attachments[0].filename, 'property-report-825-ohio-ave.pdf');
  assert.match(m.text, /Hi Sam,\nhere it is/);
  assert.match(m.html, /Sample Realty/);
  // no branding: plain BayCounty.me name, replies to the sign-in address
  const plain = R.reportEmail({to: 'a@b.example', pdf, address: '1 Main St', filename: '../../x.pdf'}, agent, null);
  assert.equal(plain.from, '"BayCounty.me" <hello@baycounty.me>');
  assert.equal(plain.reply_to, 'login@sample.example');
  assert.equal(plain.attachments[0].filename, 'property-report.pdf');
  assert.equal(plain.cc, undefined);
});

test('emailed reports are checked: real addresses, at most 5, a real PDF under 3 MB', () => {
  const pdf = Buffer.from('%PDF-1.3\n').toString('base64'), a = {email: 'x@y.example'};
  assert.throws(() => R.reportEmail({to: '', pdf, address: 'x'}, a), /at least one/);
  assert.throws(() => R.reportEmail({to: 'nope', pdf, address: 'x'}, a), /isn’t a valid/);
  assert.throws(() => R.reportEmail({to: 'a@b.co,c@b.co,d@b.co,e@b.co,f@b.co,g@b.co', pdf, address: 'x'}, a), /5 people/);
  assert.throws(() => R.reportEmail({to: 'a@b.co', pdf: Buffer.from('<html>').toString('base64'), address: 'x'}, a), /didn’t come through/);
  assert.throws(() => R.reportEmail({to: 'a@b.co', pdf: Buffer.from('%PDF-' + 'x'.repeat(3.2e6)).toString('base64'), address: 'x'}, a), /too big/);
});
