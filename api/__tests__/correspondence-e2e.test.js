// End-to-end tests for correspondence with officials against a real Postgres (migration 0020), with Resend mocked:
// one email per official, Sunshine-safe addressing, reply matching (headers, quoted Ref, sender), unmatched mail,
// publishing, and the public feed (published only, no addresses).
// Runs when FINANCE_TEST_DATABASE_URL is set (CI provides a Postgres service); skipped otherwise.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const URL_ = process.env.FINANCE_TEST_DATABASE_URL;
const opts = {skip: URL_ ? false : 'FINANCE_TEST_DATABASE_URL not set'};

let C, pool, q;
const sent = [];         // every POST /emails body
const received = {};     // id -> received email returned by GET /emails/receiving/{id}
let n = 0;

test.before(async () => {
  if (!URL_) return;
  process.env.DATABASE_URL = URL_;
  process.env.RESEND_FULL_KEY = 're_test';
  process.env.ADMIN_EMAILS = 'jeremy@fluxlabs.net';
  global.fetch = async (url, o = {}) => {
    const u = String(url).replace('https://api.resend.com', '');
    const reply = (status, body) => ({ok: status < 300, status, json: async () => body});
    if (u === '/emails' && o.method === 'POST') { const b = JSON.parse(o.body); sent.push(b); return reply(200, {id: 'out_' + (++n)}); }
    const m = u.match(/^\/emails\/receiving\/(.+)$/);
    if (m) return received[decodeURIComponent(m[1])] ? reply(200, received[decodeURIComponent(m[1])]) : reply(404, {message: 'not found'});
    if (/^\/emails\/out_/.test(u)) return reply(200, {last_event: 'delivered'});
    return reply(404, {});
  };
  const {Pool} = require('pg');
  pool = new Pool({connectionString: URL_});
  q = async (t, p = []) => (await pool.query(t, p)).rows;
  await q('drop schema if exists corr cascade');
  await pool.query(fs.readFileSync(path.join(__dirname, '../../db/migrations/0020_correspondence.sql'), 'utf8'));
  await pool.query(fs.readFileSync(path.join(__dirname, '../../db/migrations/0046_records_requests.sql'), 'utf8'));
  await q(`insert into corr.contacts (government, seat, name, email, origin) values
    ('City of Lynn Haven', 'Mayor', 'Pat Mayor', 'mayor@lh.test', 'manual'),
    ('City of Lynn Haven', 'Commissioner Seat 1', 'Chris One (vice mayor)', 'one@lh.test', 'manual'),
    ('City of Lynn Haven', 'Commissioner Seat 2', 'Sam Two', null, 'manual'),
    ('City of Callaway', 'Mayor', 'Robin Cw', 'mayor@cw.test', 'manual')`);
  C = require('../_correspondence');
});
test.after(async () => { if (pool) await pool.end(); });

const ids = async where => (await q(`select id from corr.contacts where ${where} order by id`)).map(r => r.id);

test('a send goes to each official separately, never cc or bcc, and skips seats without an address', opts, async () => {
  const lh = await ids(`government = 'City of Lynn Haven'`);
  const r = await C.send({subject: 'Bank reconciliations', body: 'Could you share the FY2026 bank reconciliations?'}, 'jeremy@fluxlabs.net').catch(e => e);
  assert.equal(r.message, 'Pick at least one official.');
  const out = await C.send({subject: 'Bank reconciliations', body: 'Could you share the FY2026 bank reconciliations?', ids: lh}, 'jeremy@fluxlabs.net');
  assert.equal(out.sent, 2);
  assert.equal(out.skipped, 1);
  assert.equal(sent.length, 2);
  for (const s of sent) {
    assert.equal(s.to.length, 1);
    assert.ok(!s.cc && !s.bcc);
    assert.equal(s.reply_to, 'hello@baycounty.me');
    assert.match(s.headers['Message-ID'], /^<bcm-[a-z0-9]{8}-0@baycounty\.me>$/);
  }
  assert.match(sent.find(s => s.to[0] === 'one@lh.test').text, /^Dear Chris One,/);
  const threads = await q('select * from corr.threads order by id');
  assert.equal(threads.length, 2);
  assert.ok(threads.every(t => t.batch_id === out.batch_id && !t.published && t.status === 'awaiting'));
});

test('a test send goes only to the admin and stores nothing', opts, async () => {
  const before = sent.length;
  const r = await C.send({test: true, subject: 'Draft', body: 'Checking how this looks.', ids: await ids(`seat = 'Mayor'`)}, 'jeremy@fluxlabs.net');
  assert.deepEqual(sent[before].to, ['jeremy@fluxlabs.net']);
  assert.ok(r.test);
  assert.equal((await q('select count(*)::int n from corr.batches'))[0].n, 1);
});

test('replies match by header, by quoted Ref, by sender; others wait unmatched', opts, async () => {
  const [mayor] = await q(`select * from corr.threads where email = 'mayor@lh.test'`);
  const [one] = await q(`select * from corr.threads where email = 'one@lh.test'`);
  received.r1 = {from: 'Pat Mayor <mayor@lh.test>', to: ['hello@baycounty.me'], subject: 'Re: Bank reconciliations',
    text: 'The clerk will send them Friday.\n\nOn Thu, Oct 22, 2026 BayCounty.me <hello@baycounty.me> wrote:\n> Could you share', headers: {'In-Reply-To': `<bcm-${mayor.token.toLowerCase()}-0@baycounty.me>`}, message_id: '<r1@lh.test>'};
  received.r2 = {from: 'one@lh.test', to: ['hello@baycounty.me'], subject: 'RE: Bank reconciliations', text: `Forwarded to finance.\n\n> Ref: BCM-${one.token}`, message_id: '<r2@lh.test>'};
  received.r3 = {from: 'mayor@lh.test', to: ['hello@baycounty.me'], subject: 'One more thing', text: 'Also see the audit.', message_id: '<r3@lh.test>'};
  received.r4 = {from: 'stranger@example.com', to: ['hello@baycounty.me'], subject: 'Hi', text: 'Love the site', message_id: '<r4@ex.test>'};
  assert.equal((await C.inbound('r1')).by, 'header');
  assert.equal((await C.inbound('r2')).by, 'token');
  assert.equal((await C.inbound('r3')).by, 'address');
  assert.equal((await C.inbound('r4')).matched, false);
  assert.ok((await C.inbound('r1')).duplicate, 'the same email twice is stored once');
  const v = await C.threads({});
  assert.equal(v.totals.replied, 2);
  assert.equal(v.unmatched.length, 1);
  // Each reply also notifies the admin.
  assert.ok(sent.some(s => s.to[0] === 'jeremy@fluxlabs.net' && /^Reply from Pat Mayor/.test(s.subject)));
  // Dismiss the stranger, and the thread view trims quoted text and refreshes delivery status.
  await C.dismiss({message_id: v.unmatched[0].id});
  const d = await C.thread(mayor.id);
  assert.equal(d.messages.find(m => m.direction === 'in').shown.text, 'The clerk will send them Friday.');
  assert.equal(d.messages.find(m => m.direction === 'out').status, 'delivered');
});

test('a follow-up threads under the earlier messages', opts, async () => {
  const [one] = await q(`select * from corr.threads where email = 'one@lh.test'`);
  await C.reply({thread_id: one.id, body: 'Thank you.'}, 'jeremy@fluxlabs.net');
  const s = sent[sent.length - 1];
  assert.equal(s.subject, 'Re: Bank reconciliations');
  assert.equal(s.headers['In-Reply-To'], '<r2@lh.test>', 'answers their latest reply');
  assert.match(s.headers.References, new RegExp(`bcm-${one.token.toLowerCase()}-0@`), 'and carries our original');
  assert.match(s.headers['Message-ID'], new RegExp(`bcm-${one.token.toLowerCase()}-2@`));
});

test('the public feed shows only published threads, without email addresses', opts, async () => {
  assert.equal((await C.publicFeed({})).conversations.length, 0);
  const [mayor] = await q(`select * from corr.threads where email = 'mayor@lh.test'`);
  await C.publish({id: mayor.id, published: true}, 'jeremy@fluxlabs.net');
  let f = await C.publicFeed({});
  assert.equal(f.conversations.length, 1);
  assert.equal(f.conversations[0].threads.length, 1);
  assert.equal(f.conversations[0].replies, 1);
  assert.ok(!JSON.stringify(f).includes('@lh.test'));
  assert.ok(!JSON.stringify(f).includes('On Thu, Oct 22'), 'quoted history is trimmed');
  await C.publish({batch: mayor.batch_id, published: true}, 'jeremy@fluxlabs.net');
  f = await C.publicFeed({year: 'all'});
  assert.equal(f.conversations[0].threads.length, 2);
  assert.equal(f.year, null);
});

test('contact edits validate addresses and turning someone off keeps them out of a send', opts, async () => {
  const [cw] = await ids(`government = 'City of Callaway'`);
  await assert.rejects(C.saveContact({id: cw, email: 'not an email'}), /doesn’t look like/);
  await C.saveContact({id: cw, active: false});
  await assert.rejects(C.send({subject: 'Hi', body: 'A question about the budget.', ids: [cw]}, 'jeremy@fluxlabs.net'), /None of the selected/);
});

// Records requests (admin "Records requests" tab, migration 0046): drafts from data/civic/records_requests.json.
test('records request drafts seed from the file, keep edits, and send only on request', opts, async () => {
  const R = require('../_records_requests');
  const {requests} = await R.list();
  const file = JSON.parse(fs.readFileSync(path.join(__dirname, '../../data/civic/records_requests.json'), 'utf8')).requests;
  assert.equal(requests.length, file.length);
  assert.ok(requests.every(r => r.status === 'draft' && !r.thread_id));
  assert.equal((await R.seed()).updated, 0);

  const pcb = requests.find(r => r.government_key === 'pcb');
  const noAddr = await R.send({id: pcb.id}, 'jeremy@fluxlabs.net').catch(e => e);
  assert.equal(noAddr.message, 'Add the recipient’s email address first.');
  const bad = await R.save({id: pcb.id, recipient_email: 'not an address'}).catch(e => e);
  assert.match(bad.message, /email address/);
  await R.save({id: pcb.id, recipient_email: 'clerk@pcb.test', body: pcb.body + '\n\nP.S. Links are fine.'});
  await R.seed();
  const [kept] = await q('select * from corr.records_requests where id = $1', [pcb.id]);
  assert.equal(kept.origin, 'manual');
  assert.match(kept.body, /P\.S\. Links are fine\./);

  const before = sent.length;
  const t = await R.send({id: pcb.id, test: true}, 'jeremy@fluxlabs.net');
  assert.ok(t.test);
  assert.deepEqual(sent[before].to, ['jeremy@fluxlabs.net']);
  assert.equal((await q('select status from corr.records_requests where id = $1', [pcb.id]))[0].status, 'draft');

  const out = await R.send({id: pcb.id}, 'jeremy@fluxlabs.net');
  const mail = sent[sent.length - 1];
  assert.deepEqual(mail.to, ['clerk@pcb.test']);
  assert.ok(!mail.cc && !mail.bcc);
  assert.match(mail.text, /^Dear Lynne Fasone,/);
  assert.match(mail.text, /Chapter 119/);
  assert.equal(out.request.status, 'sent');
  const [th] = await q('select * from corr.threads where id = $1', [out.thread_id]);
  assert.equal(th.official_seat, 'Records request');
  assert.equal(th.email, 'clerk@pcb.test');
  const again = await R.send({id: pcb.id}, 'jeremy@fluxlabs.net').catch(e => e);
  assert.equal(again.message, 'This request was already sent.');
  assert.equal(R.greetName('Public Records, City Clerk’s Office'), 'Records Custodian');
});
