// Tests for correspondence helpers (api/_correspondence.js). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const {tokenFrom, stripQuoted, composeEmail, messageIdFor, newToken, forInbox} = require('../_correspondence');

test('tokens are 8 uppercase characters and round-trip through our Message-ID', () => {
  for (let i = 0; i < 50; i++) {
    const t = newToken();
    assert.match(t, /^[A-Z0-9]{8}$/);
    assert.deepEqual(tokenFrom({inReplyTo: messageIdFor(t, 2)}), {token: t, by: 'header'});
  }
});

test('replies match by References, then by the quoted Ref line, else not at all', () => {
  assert.deepEqual(tokenFrom({references: '<x@mail.gov> <bcm-ab12cd34-0@baycounty.me>'}), {token: 'AB12CD34', by: 'header'});
  assert.deepEqual(tokenFrom({text: 'Thanks.\n\n> Ref: BCM-ZZ99YY88'}), {token: 'ZZ99YY88', by: 'token'});
  assert.equal(tokenFrom({inReplyTo: '<abc@outlook.com>', text: 'no ref here'}), null);
});

test('quoted history and our footer are cut from replies', () => {
  const gmail = 'Happy to meet Tuesday.\n\nOn Mon, Oct 20, 2026 at 9:01 AM BayCounty.me <hello@baycounty.me> wrote:\n> Dear Commissioner,\n> ...';
  assert.deepEqual(stripQuoted(gmail), {text: 'Happy to meet Tuesday.', quoted: true});
  const outlook = 'The figures are attached.\r\n\r\nFrom: BayCounty.me <hello@baycounty.me>\r\nSent: Monday, October 20, 2026 9:01 AM\r\nTo: Clerk\r\nSubject: Budget';
  assert.equal(stripQuoted(outlook).text, 'The figures are attached.');
  const wrapped = 'Yes.\nOn Mon, Oct 20, 2026 at 9:01 AM BayCounty.me\n<hello@baycounty.me> wrote:\nold';
  assert.equal(stripQuoted(wrapped).text, 'Yes.');
  assert.deepEqual(stripQuoted('Just a note.'), {text: 'Just a note.', quoted: false});
  assert.equal(stripQuoted('Ok\n\nSent from BayCounty.me, an independent site. Ref: BCM-AAAA1111').text, 'Ok');
});

test('the outgoing email greets one official, escapes the body and states that replies may be published', () => {
  const m = composeEmail({subject: 'FY2026 budget', body: 'Could you share <the> ledger?\n\nThank you,\nJeremy', name: 'Daniel Raffield (Vice Chairman per commission page)', token: 'AB12CD34'});
  assert.match(m.text, /^Dear Daniel Raffield,/);
  assert.match(m.text, /Ref: BCM-AB12CD34/);
  assert.match(m.text, /may be published/);
  assert.match(m.html, /&lt;the&gt;/);
  assert.ok(!m.html.includes('<the>'));
});

test('only mail to hello@ counts as correspondence', () => {
  assert.ok(forInbox({to: ['BayCounty.me <hello@baycounty.me>']}));
  assert.ok(!forInbox({to: ['ingest@baycounty.me']}));
});

test('public mail hides residents’ details but keeps government addresses', () => {
  const {redact, shownAddress} = require('../_redact');
  const gov = new Set(['cityoflynnhaven.com', 'baycounty.me']);
  const s = redact('Call 850-555-0142 or (850) 555-0199 ext 12, write jo@gmail.com, cc clerk@cityoflynnhaven.com. Lives at 1204 N Magnolia Ave Apt 3. SSN 123-45-6789. Budget is $1,250,000 for FY2026.', {govDomains: gov, phrases: ['Jo Smith']});
  assert.equal(s, 'Call [phone hidden] or [phone hidden], write [email hidden], cc clerk@cityoflynnhaven.com. Lives at [address hidden]. SSN [number hidden]. Budget is $1,250,000 for FY2026.');
  assert.equal(redact('Jo Smith asked.', {phrases: ['jo smith']}), '[name hidden] asked.');
  assert.equal(shownAddress('Finance@CityOfLynnHaven.com', gov), 'finance@cityoflynnhaven.com');
  assert.equal(shownAddress('a@gmail.com', gov), null);
});
