// Email previews for /admin: builds each subscriber email with the same code the live routes use (_emails.js,
// alerts-run.js compose), with sample or live data, and returns {subject, html, text, note}. Sends nothing.
// Links in previews are inert: confirm links carry a dummy token (the page says the link expired), and Resend's
// broadcast placeholders and sample manage links are swapped for the manage page (which asks for an address). Files starting with _ are not routes.
const {GOVS, WEEKLY, SITE, prefsUrl} = require('./_alerts');
const {describe} = require('./_rules');
const {confirmEmail, manageLinkEmail, adminSignInEmail, digestEmail, weeklyEmail} = require('./_emails');

const PREVIEWS = [
  {id: 'confirm_digest', name: 'Sign-up confirmation: weekly updates', when: 'Right after someone signs up for weekly updates on /alerts.'},
  {id: 'confirm_rule', name: 'Sign-up confirmation: rule alert', when: 'Right after someone sets up a rule alert (contracts, votes, keywords, campaign reports).'},
  {id: 'weekly', name: 'This week in Bay County', when: 'Mondays, to everyone on the countywide weekly list. Built from this week’s live data (/this-week).'},
  {id: 'confirm_weekly', name: 'Sign-up confirmation: This week in Bay County', when: 'Right after someone signs up on /this-week.'},
  {id: 'digest', name: 'Weekly digest', when: 'Mondays, one per government, to everyone following it. Built from this week’s live data.', usesGov: true},
  {id: 'rule_alert', name: 'Rule alert matches', when: 'Mornings, when new records match someone’s rules. Sample matches, or the latest real email.', sources: true},
  {id: 'manage_link', name: 'Manage-your-emails link', when: 'When someone asks for a link on the manage page.'},
  {id: 'admin_signin', name: 'Admin sign-in link', when: 'When an admin signs in to /admin.'},
  {id: 'finance_code', name: 'Finance sign-in code', when: 'When a finance workspace member signs in to /finance.'},
  {id: 'letter', name: 'Letter to an official', when: 'Sent from Correspondence. Sample text; the real body is what you write.'},
  {id: 'records_request', name: 'Public records request', when: 'Sent from Records requests. Sample text.'},
  {id: 'contact', name: 'Admin: contact form message', when: 'To hello@fluxlabs.net for each contact form message.'},
  {id: 'corr_reply', name: 'Admin: reply from an official', when: 'When an official answers a letter or records request.'},
  {id: 'health', name: 'Admin: ingestion problems', when: 'Daily, only when the ingestion check finds problems.'},
  {id: 'review_alerts', name: 'Admin: rule alerts ready to review', when: 'After the morning alerts run, while autosend is off.'},
  {id: 'review_digest', name: 'Admin: weekly digests ready to review', when: 'Mondays, while digest autosend is off.'},
  {id: 'review_weekly', name: 'Admin: This week in Bay County ready to review', when: 'Mondays, while weekly autosend is off.'},
];
// The agenda watcher notice and the workflow failure alert are built in Python (site/email_ui.py) and aren't previewed here.

const DUMMY = 'preview-only';
const SAMPLE_EMAIL = 'resident@example.com';
const inert = s => String(s || '').split(prefsUrl(SAMPLE_EMAIL)).join(`${SITE}/alerts/manage?t=${DUMMY}`).replace(/\{\{\{RESEND_UNSUBSCRIBE_URL\}\}\}/g, `${SITE}/alerts/manage`).replace(/\{\{\{contact\.prefs_token\|none\}\}\}/g, 'none');
const govOr = g => (GOVS[g] ? g : 'lh');

function sampleRuleGroups(gov) {
  const name = GOVS[gov][0];
  return [
    {rule: {id: 1, rule_type: 'contract', params: {gov, min: 100000}}, hits: [
      {dedupe: 's1', title: '$1,248,500 contract: Example Paving Co.', detail: 'Resurfacing of three streets · 2026-10-14', url: `${SITE}/public-money/contracts`},
      {dedupe: 's2', title: '$162,000 change order: Example Engineering, Inc.', detail: 'Stormwater outfall redesign · new total $1,410,500 · 2026-10-14', url: `${SITE}/public-money/contracts`}]},
    {rule: {id: 2, rule_type: 'keyword', params: {keyword: 'sidewalk', gov}}, hits: [
      {dedupe: 's3', title: `${name}: City Commission regular meeting (2026-10-27)`, detail: 'Award of bid for sidewalk construction · Budget amendment for sidewalk repairs', url: `${SITE}/meetings`}]},
  ];
}

async function latestOutbox() {
  const db = require('./_db');
  if (!db.hasDb()) return null;
  try { const [o] = await db.q(`select id, subject, html, text, status, created_at from alerts.outbox order by id desc limit 1`); return o || null; }
  catch (e) { return null; }
}

async function liveDigest(gov) {
  const {SITE_URL} = require('./_data');
  const r = await fetch(`${SITE_URL}/data/digest.json?ts=${Date.now()}`);
  if (!r.ok) throw Object.assign(new Error(`Couldn’t load digest.json (HTTP ${r.status}).`), {status: 502});
  const dg = await r.json();
  return (dg.govs || []).find(g => g.key === gov) || null;
}

async function preview(id, {gov, source} = {}) {
  gov = govOr(gov);
  const fakeConfirm = `${SITE}/api/confirm?t=${DUMMY}`;
  let m, note = '';
  switch (id) {
    case 'confirm_digest': {
      const govs = [gov];
      m = confirmEmail({what: 'weekly BayCounty.me updates for ' + govs.map(g => GOVS[g][0]).join(', '), isRule: false, link: fakeConfirm, govs: govs.map(g => GOVS[g][0])});
      break;
    }
    case 'confirm_weekly':
      m = confirmEmail({what: 'the weekly email This week in Bay County', isRule: false, link: fakeConfirm, govs: [WEEKLY[0]]});
      break;
    case 'weekly': {
      const {SITE_URL} = require('./_data');
      const r = await fetch(`${SITE_URL}/data/weekly.json?ts=${Date.now()}`);
      if (!r.ok) throw Object.assign(new Error(`Couldn’t load weekly.json (HTTP ${r.status}).`), {status: 502});
      const ed = await r.json();
      m = weeklyEmail(ed);
      if (!m) return {subject: '', html: '', text: '', note: 'Nothing this week, so no email would go out.'};
      note = `Week of ${ed.week_of}, live data: ${m.counts.ev} events, ${m.counts.mt} meetings, ${m.counts.vt} new votes, ${m.counts.ct} new contracts.`;
      break;
    }
    case 'confirm_rule':
      m = confirmEmail({what: describe('contract', {gov, min: 100000}), isRule: true, link: fakeConfirm});
      note = 'Shown for a sample rule: contracts over $100,000.';
      break;
    case 'digest': {
      const g = await liveDigest(gov);
      if (!g) return {subject: '', html: '', text: '', note: `No digest data for ${GOVS[gov][0]}.`};
      m = digestEmail(g);
      if (!m) {
        m = digestEmail(g, {days: 60});
        note = m ? `Nothing new for ${g.name} in the last 7 days, so no digest would go out this week. Shown with the last 60 days instead.`
                 : `Nothing new or upcoming for ${g.name}, so no digest would go out this week.`;
        if (!m) return {subject: '', html: '', text: '', note};
      } else note = `This week’s live data: ${m.changes} update${m.changes === 1 ? '' : 's'}, ${m.meetings} meeting${m.meetings === 1 ? '' : 's'}.`;
      break;
    }
    case 'rule_alert': {
      if (source === 'latest') {
        const o = await latestOutbox();
        if (!o) return {subject: '', html: '', text: '', note: 'No rule-alert emails have been built yet.'};
        return {subject: o.subject, html: o.html, text: o.text, note: `The most recent real email (#${o.id}, ${o.status}, ${new Date(o.created_at).toLocaleString('en-US', {timeZone: 'America/Chicago'})} Central). Recipient hidden.`};
      }
      m = require('./alerts-run').compose(SAMPLE_EMAIL, sampleRuleGroups(gov));
      note = 'Sample matches (made-up records) in the real layout.';
      break;
    }
    case 'manage_link': m = manageLinkEmail(`${SITE}/alerts/manage?t=${DUMMY}`); break;
    case 'admin_signin': m = adminSignInEmail(`${SITE}/api/admin?action=verify&t=${DUMMY}`); break;
    case 'finance_code': m = require('./_finance/auth').codeEmail('482913'); note = 'Sample code.'; break;
    case 'letter': case 'records_request': {
      const records = id === 'records_request';
      m = require('./_correspondence').composeEmail(records
        ? {subject: 'Public records request: FY2026 check register', name: 'Records Custodian', token: 'PREVIEW0', kind: 'records',
          body: 'Under Chapter 119, Florida Statutes, we request copies of the check register (all disbursements) for fiscal year 2026 in electronic form.\n\nA spreadsheet or CSV is ideal. If any part is exempt, please cite the exemption and release the rest.\n\nThank you,\nBayCounty.me'}
        : {subject: 'Question about the FY2027 stormwater fee', name: 'Commissioner Sample', token: 'PREVIEW0',
          body: 'I’m writing about the stormwater fee in the FY2027 budget.\n\nCould you tell us which figure the Commission adopted? We’ll publish your answer next to the budget.\n\nThank you,\nBayCounty.me'});
      note = 'Sample text in the real layout.';
      break;
    }
    case 'contact':
      m = {subject: '[BayCounty.me] Correction · /meetings', html: require('./contact').contactEmail({topic: 'Correction', name: 'Jane Resident', email: 'jane@example.org', page: `${SITE}/meetings`,
        message: 'The meeting time listed for the Nov 4 Planning Commission is wrong. The city moved it to 5:30 PM.'}), text: ''};
      note = 'Sample message.';
      break;
    case 'corr_reply':
      m = require('./_correspondence').replyNotice({official_name: 'City Clerk', official_seat: 'Records request', government: GOVS[gov][0], subject: 'Public records request: FY2026 check register'},
        {subject: 'RE: Public records request: FY2026 check register', text: 'Attached is the FY2026 check register you requested. There is no charge for this request.', attachments: [{}]}, 'clerk@example.gov', 'header');
      note = 'Sample reply.';
      break;
    case 'health':
      m = require('./_health').problemsEmail({last_sync: new Date(Date.now() - 30 * 3600e3).toISOString(), problems: [
        {level: 'error', text: 'meetings: last successful load was 52 hours ago (limit 36).'}, {level: 'warning', text: 'agenda-items: 3 files could not be read.'}]});
      note = 'Sample problems.';
      break;
    case 'review_alerts':
      m = require('./alerts-run').reviewEmail([{id: 2041, matches: 4, subject: '4 new matches for your BayCounty.me alerts'}, {id: 2042, matches: 2, subject: '2 new matches for your BayCounty.me alerts'}], 7);
      note = 'Sample drafts.';
      break;
    case 'review_digest':
      m = require('./digest').reviewEmail('ready', {done: [{gov: 'Lynn Haven', ok: true}, {gov: 'Panama City', ok: true}, {gov: 'Callaway', ok: false, error: {message: 'Sample error'}}]});
      note = 'Sample drafts.';
      break;
    case 'review_weekly':
      m = require('./weekly').reviewEmail('ready', {id: 'preview', subject: 'This week in Bay County: 37 events, 6 new votes, 3 new contracts', counts: {ev: 37, mt: 7, vt: 6, ct: 3}});
      note = 'Sample draft.';
      break;
    default: throw Object.assign(new Error('Unknown email.'), {status: 404});
  }
  return {subject: m.subject, html: inert(m.html), text: inert(m.text), note};
}

module.exports = {PREVIEWS, preview, sampleRuleGroups};
