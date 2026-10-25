// POST /api/chat: the "Ask BayCounty.me" chatbot on /ask. Body: {messages: [{role: 'user'|'assistant', content}]}.
// Streams Server-Sent Events: status (a tool is being used), text (part of the answer), reset (start the answer over),
// done ({sources, remaining}) and error ({message}). GET returns whether the chat is available.
//
// Env: ANTHROPIC_API_KEY (required), CHAT_MODEL (default claude-haiku-5-5), CHAT_EFFORT (default medium).
// Limits and the daily spending cap are in apiadmin.chat_settings (migration 0049); questions are never stored.
const crypto = require('crypto');
const {q} = require('./_db');
const {gate, ipHash} = require('./_gate');
const C = require('./_chat');

const ALLOWED = /^https:\/\/((www\.)?baycounty\.me|[a-z0-9-]+\.vercel\.app)$|^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/;
const MESSAGES = {
  off: 'The Ask feature is turned off right now. Search the site instead, or try again later.',
  budget: 'Ask has answered all the questions it can for today. It starts again at midnight Central time. Search works in the meantime.',
  hour: 'You’ve asked a lot of questions in the last hour. Please wait a bit and try again.',
  day: 'You’ve reached today’s limit of questions. Ask again tomorrow, or use Search in the meantime.',
  nokey: 'Ask isn’t set up yet. Search the site in the meantime.',
};

// If the database can't be reached: per-instance limits so the chat stays usable but bounded.
const mem = {hits: new Map(), day: '', spent: 0};
function memCheck(ih) {
  const d = new Date().toISOString().slice(0, 10);
  if (mem.day !== d) { mem.day = d; mem.spent = 0; mem.hits.clear(); }
  if (mem.spent >= Number(process.env.CHAT_DAILY_USD || 5)) return {ok: false, reason: 'budget'};
  const now = Date.now(), rec = (mem.hits.get(ih) || []).filter(t => now - t < 3600e3);
  if (rec.length >= 20) return {ok: false, reason: 'hour'};
  rec.push(now); mem.hits.set(ih, rec);
  return {ok: true};
}

async function check(ih) {
  try { return {...(await q('select apiadmin.chat_check($1) as r', [ih]))[0].r, db: true}; }
  catch (e) { console.error('chat: limits unavailable', e.message); return {...memCheck(ih), db: false}; }
}

async function logTurn(db, ih, r, ms) {
  if (!db) { mem.spent += r.cost || 0; return; }
  try {
    await q(`insert into apiadmin.chat_turns (ip_hash, model, status, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost_usd, tools, rounds, ms)
             values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)`,
      [ih, r.model || null, r.status, r.usage.input_tokens, r.usage.output_tokens, r.usage.cache_read_input_tokens, r.usage.cache_creation_input_tokens,
       r.cost || 0, r.tools || [], r.rounds || 0, ms]);
  } catch (e) { console.error('chat: log failed', e.message); mem.spent += r.cost || 0; }
}

let client = null;
function getClient() {
  if (!client) { const A = require('@anthropic-ai/sdk'); const Anthropic = A.default || A; client = new Anthropic({maxRetries: 1, timeout: 60e3}); }
  return client;
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  const origin = req.headers.origin || '';
  if (origin && ALLOWED.test(origin)) { res.setHeader('Access-Control-Allow-Origin', origin); res.setHeader('Vary', 'Origin'); }
  if (req.method === 'OPTIONS') { res.setHeader('Access-Control-Allow-Methods', 'GET, POST'); res.setHeader('Access-Control-Allow-Headers', 'Content-Type'); return res.status(204).end(); }
  if (req.method === 'GET') return res.status(200).json({available: !!process.env.ANTHROPIC_API_KEY, max_question: C.MAX_QUESTION});
  if (req.method !== 'POST') return res.status(405).json({error: 'Use POST'});
  if (origin && !ALLOWED.test(origin)) return res.status(403).json({error: 'Forbidden'});
  if (!process.env.ANTHROPIC_API_KEY) return res.status(503).json({error: MESSAGES.nokey, reason: 'nokey'});

  let body = req.body;
  if (typeof body === 'string') { try { body = JSON.parse(body); } catch (e) { body = {}; } }
  let messages;
  try { messages = C.cleanHistory(body && body.messages); }
  catch (e) { return res.status(e.status || 400).json({error: e.message}); }

  // The API gate: blocklist, the per-connection API limits, and one line in the request log (no question text).
  const g = await gate(req, res, 'chat');
  await g.log({endpoint: 'chat', status: g.ok ? 200 : g.status});
  if (!g.ok) return res.status(g.status).json({error: g.message || 'Request not allowed.', reason: g.reason});

  const ih = ipHash(req);
  const lim = await check(ih);
  if (!lim.ok) return res.status(lim.reason === 'off' || lim.reason === 'budget' ? 503 : 429).json({error: MESSAGES[lim.reason] || 'Try again later.', reason: lim.reason});

  const model = [lim.model, process.env.CHAT_MODEL].find(m => m && C.PRICES[m]) || C.DEFAULT_MODEL;
  const effort = ['low', 'medium', 'high'].includes(process.env.CHAT_EFFORT) ? process.env.CHAT_EFFORT : 'medium';
  res.writeHead(200, {'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no', Connection: 'keep-alive'});
  const send = (event, data) => res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  const t0 = Date.now();
  // A comment line every few seconds while tools run, so phones and proxies don't treat a quiet stream as dead.
  const ping = setInterval(() => { try { res.write(': ping\n\n'); } catch (e) {} }, 5000);
  const mcp = require('./mcp');
  const A = require('@anthropic-ai/sdk'), APIError = (A.default || A).APIError || A.APIError;
  let r;
  try {
    r = await C.answer({
      client: getClient(), model, effort, messages, mcpTools: mcp.TOOLS,
      callTool: (name, args) => mcp.call(req, name, args),
      emit: ev => send(ev.type, ev),
      isApiError: e => APIError && e instanceof APIError,
    });
    await logTurn(lim.db, ih, r, Date.now() - t0);
    send('done', {sources: r.sources, remaining_hour: lim.remaining_hour ?? null, remaining_day: lim.remaining_day ?? null, id: crypto.randomUUID()});
  } catch (e) {
    console.error('chat: failed', e.status || '', e.message);
    await logTurn(lim.db, ih, {status: 'error', model, usage: {input_tokens: 0, output_tokens: 0, cache_read_input_tokens: 0, cache_creation_input_tokens: 0}, cost: 0}, Date.now() - t0);
    const busy = e.status === 429 || e.status === 529 || e.status >= 500;
    send('error', {message: busy ? 'Ask is busy right now. Please try again in a minute.' : 'Something went wrong answering that. Please try again.'});
  }
  clearInterval(ping);
  res.end();
};
