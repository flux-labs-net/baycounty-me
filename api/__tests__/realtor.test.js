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
