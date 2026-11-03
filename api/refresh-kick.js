// Starts the morning refresh (refresh-meetings.yml) on time. Vercel cron, every day at 11:10 UTC.
// GitHub's own schedule for that workflow starts hours late (5-6 h in late Oct 2026), after the Monday emails at
// 13:00-14:30 UTC had already read last week's lists. Vercel crons run on time, so this one starts the refresh; the
// workflow's own schedule stays as a backup and skips itself when this run already happened.
//   GET /api/refresh-kick with Authorization: Bearer CRON_SECRET
const {FROM, resend} = require('./_alerts');
const {dispatch} = require('./_github');
const ui = require('./_email_ui');

module.exports = async (req, res) => {
  if ((req.headers.authorization || '') !== `Bearer ${process.env.CRON_SECRET}` || !process.env.CRON_SECRET) return res.status(401).json({ok: false});
  try {
    await dispatch('refresh-meetings.yml');
    return res.status(200).json({ok: true, started: 'refresh-meetings.yml'});
  } catch (e) {
    console.error('refresh-kick:', e.message);
    const key = process.env.RESEND_FULL_KEY, to = process.env.DIGEST_REVIEWER || 'hello@fluxlabs.net';
    const why = e.message;
    if (key) await resend('/emails', 'POST', {from: FROM, to: [to], ...ui.adminNotice({subject: 'BayCounty.me: the morning refresh didn’t start',
      kicker: 'Daily refresh', tone: 'salmon', icon: 'alert', eyebrow: 'Daily refresh', title: 'The morning refresh didn’t start', preheader: why,
      text: `The site's morning refresh could not be started from Vercel: ${why}.\n\nGitHub's own schedule will still run it, but often hours late. If the token expired, make a new fine-grained token (resource owner flux-labs-net, repository baycounty-me, Actions: read and write) and save it in Vercel as GITHUB_DISPATCH_TOKEN.`,
      body: ui.p(`The site’s morning refresh could not be started from Vercel: ${ui.esc(why)}.`) +
        ui.p('GitHub’s own schedule will still run it, but often hours late. If the token expired, make a new fine-grained GitHub token (resource owner flux-labs-net, repository baycounty-me, Actions: read and write) and save it in Vercel as GITHUB_DISPATCH_TOKEN.', {size: 14, lh: 21})})}, key).catch(() => {});
    return res.status(e.status || 502).json({ok: false, error: why});
  }
};
