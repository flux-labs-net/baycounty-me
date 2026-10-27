// This week in Bay County: the weekly email builder, its sign-up list and the Monday route's week check. Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const {weeklyEmail, confirmEmail} = require('../_emails');
const {LISTS, WEEKLY, GOVS} = require('../_alerts');
const {thisMonday} = require('../weekly');

const ed = {week_of: '2026-10-26', rows: [
  {section: 'event', rank: 1, featured: true, title: 'Fall Festival', starts: '2026-10-31T16:00:00', all_day: false, venue: 'Lynn Haven Sports Park', town: 'Lynn Haven', url: 'https://example.gov/fest'},
  {section: 'event', rank: 2, featured: false, title: 'Story time', starts: '2026-10-28T10:00:00', all_day: false, town: 'Panama City', url: 'https://example.gov/st'},
  {section: 'meeting', rank: 1, featured: true, title: 'Lynn Haven: City Commission Meeting', starts: '2026-10-27T17:30:00-05:00', venue: 'City Hall', agenda_posted: false, url: null},
  {section: 'vote', rank: 1, featured: true, title: 'Rejected $3.05 million laptop purchase', summary: 'The board voted 2-3 against buying laptops.', date: '2026-10-20', government: 'Bay District Schools',
    outcome: 'failed', tally: '2-3', voted_no: 'Ann Leonard; <Jerry>', people: [{name: 'Ann Leonard', url: 'https://baycounty.me/people/ann-leonard'}, {name: '<Jerry>', url: null}], url: 'https://baycounty.me/public-money/votes?q=x#all'},
  {section: 'contract', rank: 1, featured: true, title: 'CBC Construction', summary: 'Bus barn roof', amount: 1718585, date: '2026-10-22', government: 'Panama City', vendor_url: 'https://baycounty.me/public-money/vendors/cbc', source_url: 'https://example.gov/minutes'},
  {section: 'change_order', rank: 1, featured: true, title: 'Example Co', summary: 'More dirt', amount: 25000, date: '2026-10-21', government: 'Callaway', url: 'https://baycounty.me/public-money/contracts'},
]};

test('weekly email: sections, counts, links and escaping', () => {
  const m = weeklyEmail(ed);
  assert.equal(m.subject, 'This week in Bay County: 2 events, 1 new vote, 2 new contracts');
  for (const s of ['Happening this week', 'Public meetings', 'New votes', 'New contracts', 'Fall Festival', 'Agenda not posted yet', '$1.7 million', '$25,000',
    'https://baycounty.me/people/ann-leonard', 'https://baycounty.me/public-money/vendors/cbc', 'Every event this week (2)', '{{{RESEND_UNSUBSCRIBE_URL}}}', 'https://baycounty.me/this-week'])
    assert.ok(m.html.includes(s), `html is missing ${s}`);
  assert.ok(!m.html.includes('Story time'), 'only featured events are listed');
  assert.ok(m.html.includes('&lt;Jerry&gt;') && !m.html.includes('<Jerry>'), 'names are escaped');
  assert.ok(m.html.includes('Sat 4 PM'), 'local event time without an offset is read as Central time');
  assert.match(m.text, /NEW VOTES\n- Rejected \$3\.05 million laptop purchase \(Bay District Schools, Oct 20, 2-3\) Voted no:/);
  assert.ok(!/claude|anthropic|\bofficial\b/i.test(m.html), 'no model names or "official" wording');
});

test('weekly email: nothing in the edition means no email', () => {
  assert.equal(weeklyEmail({week_of: '2026-10-26', rows: [{section: 'vote', featured: false}].slice(1)}), null);
  assert.equal(weeklyEmail(null), null);
});

test('the weekly list is a sign-up option beside the governments', () => {
  assert.equal(LISTS.week, WEEKLY);
  assert.match(WEEKLY[1], /^[0-9a-f-]{36}$/);
  for (const k of Object.keys(GOVS)) assert.equal(LISTS[k], GOVS[k]);
  const c = confirmEmail({what: 'the weekly email This week in Bay County', isRule: false, link: 'https://baycounty.me/api/confirm?t=x', govs: [WEEKLY[0]]});
  assert.equal(c.subject, 'Confirm your This week in Bay County email');
  assert.ok(c.html.includes('Confirm my email'));
});

test('the Monday run checks the edition is this week’s, in Bay County time', () => {
  assert.equal(thisMonday(Date.parse('2026-10-26T13:20:00Z')), '2026-10-26');
  assert.equal(thisMonday(Date.parse('2026-11-02T03:00:00Z')), '2026-10-26'); // still Sunday night in Panama City
  assert.equal(thisMonday(Date.parse('2026-11-02T13:20:00Z')), '2026-11-02');
});
