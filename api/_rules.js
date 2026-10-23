// Rule-based email alerts: rule definitions, validation, matching and the confirm step.
// (Files starting with _ are not routes.) Signup: subscribe.js (kind 'rule'), confirm: confirm.js -> confirmRule,
// daily matching and email: alerts-run.js. Events come from db/scripts/load.py (alerts.events, migration 0008).
const crypto = require('crypto');
const {GOVS} = require('./_alerts');

const TYPES = ['contract', 'vote', 'keyword', 'campaign'];
const money = n => '$' + Math.round(Number(n) || 0).toLocaleString('en-US');
const norm = s => String(s ?? '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
const clip = (s, n) => String(s ?? '').trim().replace(/\s+/g, ' ').slice(0, n);
const num = x => { const n = Number(x); return x == null || x === '' || !Number.isFinite(n) ? null : n; };

// Validate and normalize what the sign-up form sent. Returns {ok, type, params} or {ok:false, error}.
function validate(type, p = {}) {
  if (!TYPES.includes(type)) return {ok: false, error: 'Pick a kind of alert.'};
  if (type === 'contract') {
    const gov = String(p.gov || '');
    const min = Math.round(Number(String(p.min ?? '').replace(/[$,\s]/g, '')));
    if (!GOVS[gov]) return {ok: false, error: 'Pick a government.'};
    if (!Number.isFinite(min) || min < 0 || min > 1e10) return {ok: false, error: 'Enter a dollar amount, like 100000.'};
    return {ok: true, type, params: {gov, min}};
  }
  if (type === 'vote') {
    const member = clip(p.member, 80);
    if (norm(member).length < 3) return {ok: false, error: 'Pick a board member.'};
    return {ok: true, type, params: {member}};
  }
  if (type === 'keyword') {
    const keyword = clip(p.keyword, 60), gov = p.gov && GOVS[p.gov] ? String(p.gov) : null;
    if (norm(keyword).length < 3) return {ok: false, error: 'Enter a word or street name with at least 3 letters.'};
    return {ok: true, type, params: gov ? {keyword, gov} : {keyword}};
  }
  const candidate = clip(p.candidate, 80);
  if (norm(candidate).length < 3) return {ok: false, error: 'Pick a candidate.'};
  return {ok: true, type, params: {candidate}};
}

function describe(type, p = {}) {
  const g = p.gov && GOVS[p.gov] ? GOVS[p.gov][0] : null;
  if (type === 'contract') return `Contracts and change orders over ${money(p.min)} for ${g || 'a government'}, including ones on upcoming agendas`;
  if (type === 'vote') return `Recorded votes by ${p.member}`;
  if (type === 'keyword') return `Meetings and agenda items that mention “${p.keyword}”${g ? ` (${g})` : ''}`;
  if (type === 'campaign') return `New campaign finance reports for ${p.candidate}`;
  return 'Alert';
}

// Board id from meetings.json ('lh', 'pc-cra', 'county-planning') -> government key.
const govOfBoard = b => { const k = String(b || '').split('-')[0]; return GOVS[k] ? k : null; };
const h = s => crypto.createHash('sha1').update(s).digest('hex').slice(0, 16);

// Agenda items read from posted agendas (data/agendas/extract_agendas.py, dataset 'agenda-items').
const AGENDA_SPEND = new Set(['contract', 'purchase', 'change_order']);
const itemKey = (board, date, title) => `${String(board || '').split('-')[0]}|${String(date || '').slice(0, 10)}|${norm(title)}`;
const govName = board => (govOfBoard(board) ? GOVS[govOfBoard(board)][0] : board || 'A board');
function agendaHit(r, why) {
  const num_ = r.item_number ? `Item ${r.item_number}: ` : '';
  return {dedupe: 'ai:' + h(itemKey(r.board, r.meeting_date, r.title)), itemKeys: [itemKey(r.board, r.meeting_date, r.title)],
    title: `${govName(r.board)} agenda, ${String(r.meeting_date || '').slice(0, 10)}: ${clip(r.title, 160)}`,
    detail: [num_ && num_.slice(0, -2), r.amount != null ? money(r.amount) : null, (r.parties || []).slice(0, 2).join(', ') || null, why, r.summary ? clip(r.summary, 200) : null].filter(Boolean).join(' · '),
    url: r.agenda_url || 'https://baycounty.me/meetings'};
}

// Does one event match one rule? Returns null, or {dedupe, title, detail, url} for the email.
// ev: {dataset, record_hash, government_key, record}.
function match(rule, ev) {
  const p = rule.params || {}, r = ev.record || {};
  if (rule.rule_type === 'contract') {
    if (ev.government_key !== p.gov) return null;
    if (ev.dataset === 'contracts') {
      const a = num(r.amount);
      if (a === null || a < p.min) return null;
      return {dedupe: 'c:' + ev.record_hash, title: `${money(a)} contract: ${r.vendor || 'vendor not listed'}`, detail: [r.purpose, r.date].filter(Boolean).join(' · '), url: r.source_url};
    }
    if (ev.dataset === 'agenda-items') {
      const a = num(r.amount);
      if (!AGENDA_SPEND.has(r.kind) || a === null || a < p.min) return null;
      return agendaHit(r, 'on the agenda, not yet approved');
    }
    if (ev.dataset === 'change-orders') {
      const a = num(r.change_amount);
      if (a === null || Math.abs(a) < p.min) return null;
      return {dedupe: 'co:' + ev.record_hash, title: `${money(a)} change order: ${r.vendor || 'vendor not listed'}`, detail: [r.project, r.new_total != null ? `new total ${money(r.new_total)}` : null, r.date].filter(Boolean).join(' · '), url: r.source_url};
    }
    return null;
  }
  if (rule.rule_type === 'vote') {
    if (ev.dataset !== 'member-votes' || norm(r.member) !== norm(p.member)) return null;
    return {dedupe: 'v:' + ev.record_hash, title: `${r.member} voted ${String(r.vote || '').toUpperCase() || '(not listed)'}: ${r.headline || 'vote'}`, detail: [r.board, r.date].filter(Boolean).join(' · '), url: r.source_url};
  }
  if (rule.rule_type === 'keyword' && ev.dataset === 'agenda-items') {
    if (p.gov && govOfBoard(r.board) !== p.gov) return null;
    const kw = norm(p.keyword);
    const fields = [r.title, r.summary, ...(r.parties || []), ...(r.addresses || [])].filter(Boolean);
    if (!fields.some(t => norm(t).includes(kw))) return null;
    return agendaHit(r, null);
  }
  if (rule.rule_type === 'keyword') {
    if (ev.dataset !== 'meetings' || r.past || r.cancelled) return null;
    if (p.gov && govOfBoard(r.board) !== p.gov) return null;
    const kw = norm(p.keyword);
    const texts = [r.title, ...(Array.isArray(r.items) ? r.items.map(i => i && i.title) : []), ...(Array.isArray(r.agenda_items) ? r.agenda_items : [])].filter(Boolean);
    const hits = [...new Set(texts.filter(t => (' ' + norm(t) + ' ').includes(' ' + kw + ' ') || norm(t).includes(kw)))];
    if (!hits.length) return null;
    const gname = govOfBoard(r.board) ? GOVS[govOfBoard(r.board)][0] : r.board;
    return {dedupe: 'k:' + h(`${r.board}|${String(r.start || '').slice(0, 10)}|${hits.join('|')}`), itemKeys: hits.map(t => itemKey(r.board, r.start, t)), title: `${gname}: ${r.title || 'meeting'} (${String(r.start || '').slice(0, 10)})`,
      detail: hits.filter(t => t !== r.title).slice(0, 3).map(t => clip(t, 240)).join(' · ') || 'The meeting title mentions it.', url: r.agenda_url || r.detail_url || 'https://baycounty.me/meetings'};
  }
  if (rule.rule_type === 'campaign') {
    if (ev.dataset !== 'candidates-2026' || norm(r.candidate) !== norm(p.candidate)) return null;
    if (!r.reports_through && r.total_raised == null) return null;
    return {dedupe: 'f:' + h(`${norm(r.candidate)}|${r.reports_through}|${r.total_raised}`), title: `${r.candidate} (${r.office || 'candidate'}): report through ${r.reports_through || 'latest'}`,
      detail: [r.total_raised != null ? `raised ${money(r.total_raised)}` : null, r.total_spent != null ? `spent ${money(r.total_spent)}` : null].filter(Boolean).join(' · '), url: r.finance_report_url || 'https://baycounty.me/elections'};
  }
  return null;
}

// confirm.js calls this for tokens of kind 'rule' ({kind, r: type, p: params, e: email}). Returns the redirect.
async function confirmRule(tok) {
  const v = validate(tok.r, tok.p);
  if (!v.ok) return '/alerts?status=error';
  const db = require('./_db');
  if (!db.hasDb()) throw new Error('DATABASE_URL is not set');
  await db.q(`insert into alerts.subscriptions (email, confirmed, confirmed_at, rule_type, params) values ($1, true, now(), $2, $3)
              on conflict (email, rule_type, md5(params::text)) do update set confirmed = true, confirmed_at = now(), unsubscribed_at = null`,
    [String(tok.e).toLowerCase(), v.type, JSON.stringify(v.params)]);
  return '/alerts?status=rule_confirmed#rules';
}

module.exports = {TYPES, validate, describe, match, confirmRule, govOfBoard, norm};
