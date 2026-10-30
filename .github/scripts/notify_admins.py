"""Email the BayCounty.me admins when an ingestion workflow has a problem.

Runs as the last step of each ingestion workflow (with `if: always()`). It reads the job's step results from the
STEPS environment variable (`${{ toJSON(steps) }}`) and sends one email through Resend when:
  * the job failed, or
  * a step failed (including steps with continue-on-error), unless that step set the output notify=false
    (used to avoid repeating an alert that's already open, e.g. a meetings issue that's only getting a comment), or
  * a step set an `alert` output (a problem that isn't a step failure, e.g. a missing secret).
A cancelled job (superseded by a newer run) never emails.

Environment:
  STEPS        toJSON(steps)
  JOB_STATUS   job.status
  RESEND_KEY   Resend API key (repository secret RESEND_FULL_KEY). Missing: prints a warning and exits 0.
  ADMIN_EMAILS comma-separated recipients (repository secret). Default: hello@fluxlabs.net.
  EXTRA_FILE   optional path to a Markdown/text file whose contents are added to the email (details, e.g. source errors).
Standard GitHub variables (GITHUB_WORKFLOW, GITHUB_SERVER_URL, GITHUB_REPOSITORY, GITHUB_RUN_ID, GITHUB_SHA) fill in the rest.
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'site'))
import email_ui  # noqa: E402  (the shared email layout, twin of api/_email_ui.js)

FROM = os.environ.get('ALERTS_FROM') or 'BayCounty.me <hello@baycounty.me>'


LABELS = {
    'fetch_meetings': 'Fetch meetings', 'meeting_source_errors': 'Meeting sources',
    'fetch_campaign_finance': 'Fetch campaign finance reports', 'rebuild_site': 'Rebuild site',
    'commit_and_push': 'Commit and push', 'fetch_fema_ledger': 'Fetch FEMA Public Assistance ledger',
    'fetch_sales_tax_map': 'Fetch sales tax project map (Bay County GIS)', 'database_secret': 'Database secret',
    'load_database': 'Load the database', 'vercel_deploy': 'Deploy to Vercel (deploy hook)',
}


def label(step_id):
    return LABELS.get(step_id) or step_id.replace('_', ' ').replace('-', ' ').capitalize()


def problems(steps, job_status):
    """Returns (lines, should_send). Pure, so it can be tested without GitHub."""
    lines, send = [], job_status == 'failure'
    for sid, s in (steps or {}).items():
        out = s.get('outputs') or {}
        if s.get('outcome') == 'failure':
            quiet = str(out.get('notify', '')).lower() == 'false'
            lines.append(f"- {label(sid)}: failed{' (already reported; see the open issue)' if quiet else ''}")
            if not quiet:
                send = True
        if out.get('alert'):
            lines.append(f"- {label(sid)}: {out['alert']}")
            send = True
    if job_status == 'failure' and not any('failed' in l and 'already reported' not in l for l in lines):
        lines.append('- The job failed (see the run log).')
    return lines, send


def notice_html(wf, lines, run, extra, sha):
    """The designed version of the alert. lines are the '- Step: problem' lines from problems()."""
    e = email_ui.esc
    rows = []
    for l in lines:
        t = l[2:] if l.startswith('- ') else l
        quiet = 'already reported' in t
        rows.append(('amber' if quiet else 'salmon', 'Reported' if quiet else 'Problem', e(t)))
    body = email_ui.p('The <b>%s</b> run had a problem:' % e(wf)) + email_ui.list_rows(rows)
    if extra:
        body += email_ui.quote(extra)
    body += email_ui.facts([('Workflow', e(wf)), ('Commit', '<span style="font-family:%s;font-size:13px">%s</span>' % (email_ui.MONO, e(sha[:7]) or 'unknown'))])
    body += email_ui.button(run, 'Open the run log')
    body += email_ui.small('When a fetch fails, the site keeps the previous data. Nothing is deleted. Re-run the workflow from the Actions tab once the source is back.')
    n = len(rows)
    return email_ui.admin_notice('BayCounty.me ingestion problem: %s' % wf, body, preheader_text=rows[0][2] if rows else '', kicker='Data health',
                                 tone='salmon', ic='alert', eyebrow='Data workflow', title='%s needs a look' % e(wf) if n else 'A workflow needs a look')


def main():
    job_status = os.environ.get('JOB_STATUS', '')
    if job_status == 'cancelled':
        print('Job was cancelled; no email.')
        return
    try:
        steps = json.loads(os.environ.get('STEPS') or '{}')
    except json.JSONDecodeError:
        steps = {}
    lines, send = problems(steps, job_status)
    if not send:
        print('No problems to report.')
        return
    wf = os.environ.get('GITHUB_WORKFLOW', 'Ingestion workflow')
    run = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
    body = f"The \"{wf}\" run had a problem:\n\n" + '\n'.join(lines) + '\n'
    extra = os.environ.get('EXTRA_FILE')
    details = open(extra, encoding='utf-8').read().strip()[:6000] if extra and os.path.isfile(extra) else ''
    if details:
        body += '\nDetails:\n\n' + details + '\n'
    body += f"\nRun log: {run}\nCommit: {os.environ.get('GITHUB_SHA', '')[:7]}\n\nWhen a fetch fails, the site keeps the previous data; nothing is deleted. Re-run the workflow from the Actions tab once the source is back.\n"
    print(body)

    key = os.environ.get('RESEND_KEY')
    if not key:
        print('::warning title=Admin alert not sent::Add the RESEND_FULL_KEY repository secret to email admins.')
        return
    to = [e.strip() for e in (os.environ.get('ADMIN_EMAILS') or 'hello@fluxlabs.net').replace(';', ',').split(',') if e.strip()]
    subject = f"BayCounty.me ingestion problem: {wf}"
    req = urllib.request.Request('https://api.resend.com/emails', method='POST',
                                 data=json.dumps({'from': FROM, 'to': to, 'subject': subject, 'text': body,
                                                  'html': notice_html(wf, lines, run, details, os.environ.get('GITHUB_SHA', ''))}).encode(),
                                 headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
                                          'User-Agent': 'baycounty-me-notify/1'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print('Admin alert sent:', r.status)
    except urllib.error.HTTPError as e:
        print(f'::warning title=Admin alert failed::Resend returned {e.code}: {e.read()[:300]!r}')
    except Exception as e:  # never fail the workflow over the alert itself
        print(f'::warning title=Admin alert failed::{e}')


if __name__ == '__main__':
    sys.exit(main())
