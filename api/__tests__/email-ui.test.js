// The shared email layout (api/_email_ui.js), its Python twin (site/email_ui.py) and every email built on it. Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const {execFileSync} = require('child_process');
process.env.ALERTS_SECRET = process.env.ALERTS_SECRET || 'test-secret';
const ui = require('../_email_ui');

const ICON_DIR = path.join(__dirname, '..', '..', 'site', 'email-icons');

test('the Python twin renders the same admin notice as the JS layout', () => {
  const js = ui.adminNotice({subject: 'S & T', preheader: 'Pre', kicker: 'Agenda watcher', tone: 'blue', icon: 'file', eyebrow: 'Agenda watcher', title: '2 new agendas',
    body: ui.list([['teal', 'New', '<b>A</b>'], ['amber', 'Updated', 'B']]) + ui.p('Hi', {muted: true, size: 14, lh: 21}) + ui.quote('x\ny') +
      ui.facts([['K', 'V']]) + ui.button('https://baycounty.me/admin', 'Open') + ui.small('fine print') + ui.note('n') + ui.a('https://x.y', 'L', 'font-size:13px'),
    footer: ui.adminFooter('Why.')}).html;
  const py = execFileSync('python3', ['-c', `
import sys; sys.path.insert(0, ${JSON.stringify(path.join(__dirname, '..', '..', 'site'))})
import email_ui as u
body = u.list_rows([('teal', 'New', '<b>A</b>'), ('amber', 'Updated', 'B')]) + u.p('Hi', muted=True, size=14, lh=21) + u.quote('x\\ny') + \\
    u.facts([('K', 'V')]) + u.button('https://baycounty.me/admin', 'Open') + u.small('fine print') + u.note('n') + u.a('https://x.y', 'L', 'font-size:13px')
sys.stdout.write(u.admin_notice('S & T', body, 'Pre', 'Agenda watcher', 'blue', 'file', 'Agenda watcher', '2 new agendas', u.admin_footer('Why.')))
`], {encoding: 'utf8'});
  assert.equal(py, js);
});

test('every icon and tone the emails can ask for has a light and a dark PNG', () => {
  for (const name of ui.ICONS) for (const tone of Object.keys(ui.TONES)) for (const d of ['', '-d'])
    assert.ok(fs.existsSync(path.join(ICON_DIR, `${name}-${tone}${d}.png`)), `${name}-${tone}${d}.png`);
});

test('every email is a full document with preview text, dark mode and a text part', async () => {
  const {PREVIEWS, preview} = require('../_previews');
  global.fetch = async () => ({ok: true, status: 200, json: async () => ({govs: [{key: 'lh', slug: 'lynn-haven', name: 'Lynn Haven',
    changes: [{date: new Date().toISOString().slice(0, 10), title: 'New page', text: 'A long update. '.repeat(30), url: 'https://baycounty.me/x'}],
    meetings: [{start: new Date(Date.now() + 2 * 864e5).toISOString(), title: 'City Commission', agenda_url: null, location: 'City Hall'}]}]})});
  for (const p of PREVIEWS) {
    const m = await preview(p.id, {gov: 'lh'});
    assert.match(m.html, /^<!DOCTYPE html><html lang="en">/, p.id);
    assert.match(m.html, /prefers-color-scheme:dark/, p.id);
    assert.match(m.html, /BayCounty<span class="bc-sal"/, p.id);
    assert.match(m.html, /display:none;max-height:0;overflow:hidden;mso-hide:all/, p.id);
    if (p.id !== 'contact') assert.ok(m.text.length > 20, p.id);
    assert.doesNotMatch(m.html + m.text, /\b(Claude|Anthropic|Haiku|Sonnet|Opus)\b/, p.id);
    for (const [, icon] of m.html.matchAll(/assets\/email\/([a-z]+-[a-z]+(?:-d)?)\.png/g)) assert.ok(fs.existsSync(path.join(ICON_DIR, icon + '.png')), icon);
  }
});

test('the digest cuts long updates and keeps the unsubscribe placeholders', () => {
  const {digestEmail, clip} = require('../_emails');
  const now = Date.parse('2026-10-27T12:00:00Z');
  const m = digestEmail({key: 'lh', slug: 'lynn-haven', name: 'Lynn Haven', changes: [{date: '2026-10-26', title: 'T', text: 'First sentence here. ' + 'word '.repeat(80), url: 'https://baycounty.me/t'}],
    meetings: [{start: '2026-10-28T17:30:00-05:00', title: 'City Commission Meeting', agenda_url: 'https://example.gov/a', location: 'City Hall'}]}, {now});
  assert.equal(m.subject, 'Lynn Haven this week: 1 update, 1 meeting');
  assert.match(m.html, /Read more &rarr;/);
  assert.match(m.html, />OCT<\/div>/);
  assert.match(m.html, /\{\{\{RESEND_UNSUBSCRIBE_URL\}\}\}/);
  assert.match(m.html, /\{\{\{contact\.prefs_token\|none\}\}\}/);
  assert.ok(clip('a'.repeat(10)) === 'a'.repeat(10));
  assert.ok(clip('One. Two. ' + 'x '.repeat(200)).length <= 221);
});

test('text that goes into a layout is escaped', () => {
  const h = ui.layout({title: '<b>x</b>', preheader: '<i>', body: ui.quote('<script>'), footer: ''});
  assert.doesNotMatch(h, /<script>|<i>|<title><b>/);
});
