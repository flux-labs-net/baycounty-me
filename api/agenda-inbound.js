// Resend inbound webhook: Resend POSTs `email.received` here when mail reaches the agenda inbox
// (AGENDA_INBOX, default ingest@baycounty.me). We verify the signature, then start the "Watch agendas"
// workflow for that one email so the agenda is picked up within a minute or two instead of at the next
// 30-minute check. The workflow does the real work (reads the email through the Resend API, rescans the
// government, downloads files). If anything here fails, the 30-minute check still catches the email.
// Env: RESEND_WEBHOOK_SECRET (the webhook's signing secret, whsec_...), GITHUB_DISPATCH_TOKEN.
const crypto = require('crypto');
const {runNow} = require('./_agendas');

const INBOX = String(process.env.AGENDA_INBOX || 'ingest@baycounty.me').toLowerCase();
const TOLERANCE_S = 5 * 60;

// Resend signs webhooks the Svix way: HMAC-SHA256 over `${id}.${timestamp}.${body}` with the base64 secret after
// "whsec_", sent as one or more space-separated "v1,<base64>" values. Pure, so it can be tested.
function verify(secret, headers, body, now = Date.now()) {
  const id = headers['svix-id'], ts = headers['svix-timestamp'], sigs = headers['svix-signature'];
  if (!secret || !id || !ts || !sigs) return false;
  if (!/^\d+$/.test(String(ts)) || Math.abs(now / 1000 - Number(ts)) > TOLERANCE_S) return false;
  const key = Buffer.from(String(secret).replace(/^whsec_/, ''), 'base64');
  const expected = crypto.createHmac('sha256', key).update(`${id}.${ts}.${body}`).digest();
  return String(sigs).split(' ').some(s => {
    const [ver, val] = s.split(',');
    if (ver !== 'v1' || !val) return false;
    const got = Buffer.from(val, 'base64');
    return got.length === expected.length && crypto.timingSafeEqual(got, expected);
  });
}

function forInbox(data) {
  const all = [].concat(data.to || [], data.cc || [], data.bcc || [], data.received_for || []);
  return all.some(a => String(a).toLowerCase().includes(INBOX));
}

// The signature covers the exact bytes Resend sent, so read the raw stream before anything touches req.body
// (on Vercel, reading req.body parses the request and consumes the stream).
async function rawBody(req) {
  const chunks = [];
  for await (const c of req) chunks.push(Buffer.from(c));
  if (chunks.length) return Buffer.concat(chunks).toString('utf8');
  const b = req.body;
  return typeof b === 'string' ? b : Buffer.isBuffer(b) ? b.toString('utf8') : '';
}

async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ok: false});
  const body = await rawBody(req);
  if (!verify(process.env.RESEND_WEBHOOK_SECRET, req.headers, body)) return res.status(401).json({ok: false, error: 'bad signature'});
  let evt;
  try { evt = JSON.parse(body); } catch (e) { return res.status(400).json({ok: false, error: 'bad json'}); }
  const data = evt.data || {};
  if (evt.type !== 'email.received' || !data.email_id) return res.status(200).json({ok: true, ignored: evt.type});
  // Replies from officials to hello@baycounty.me go to the correspondence log, not the agenda watcher.
  const corr = require('./_correspondence');
  if (!forInbox(data) && corr.forInbox(data)) {
    try { return res.status(200).json(await corr.inbound(data.email_id)); }
    catch (e) {
      // 500 so Resend retries; inbound() skips emails it has already stored.
      console.error('correspondence inbound', e.message);
      return res.status(500).json({ok: false, error: 'not stored yet'});
    }
  }
  if (!forInbox(data)) return res.status(200).json({ok: true, ignored: 'other address'});
  try {
    await runNow('inbox', '', data.email_id);
    return res.status(200).json({ok: true, started: data.email_id});
  } catch (e) {
    // 200 anyway: Resend would only retry into the same error, and the scheduled inbox check picks the email up.
    console.error('agenda-inbound dispatch', e.message);
    return res.status(200).json({ok: true, started: false, note: e.message});
  }
}

module.exports = handler;
module.exports.verify = verify;
module.exports.forInbox = forInbox;
module.exports.config = {api: {bodyParser: false}};
