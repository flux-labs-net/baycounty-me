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

FROM = os.environ.get('ALERTS_FROM') or 'BayCounty.me <hello@baycounty.me>'


LABELS = {
    'fetch_meetings': 'Fetch meetings', 'meeting_source_errors': 'Meeting sources',
    'fetch_campaign_finance': 'Fetch campaign finance reports', 'rebuild_site': 'Rebuild site',
    'commit_and_push': 'Commit and push', 'fetch_fema_ledger': 'Fetch FEMA Public Assistance ledger',
    'fetch_sales_tax_map': 'Fetch sales tax project map (Bay County GIS)', 'database_secret': 'Database secret',
    'load_database': 'Load the database',
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
    if extra and os.path.isfile(extra):
        body += '\nDetails:\n\n' + open(extra, encoding='utf-8').read().strip()[:6000] + '\n'
    body += f"\nRun log: {run}\nCommit: {os.environ.get('GITHUB_SHA', '')[:7]}\n\nWhen a fetch fails, the site keeps the previous data; nothing is deleted. Re-run the workflow from the Actions tab once the source is back.\n"
    print(body)

    key = os.environ.get('RESEND_KEY')
    if not key:
        print('::warning title=Admin alert not sent::Add the RESEND_FULL_KEY repository secret to email admins.')
        return
    to = [e.strip() for e in (os.environ.get('ADMIN_EMAILS') or 'hello@fluxlabs.net').replace(';', ',').split(',') if e.strip()]
    subject = f"BayCounty.me ingestion problem: {wf}"
    req = urllib.request.Request('https://api.resend.com/emails', method='POST',
                                 data=json.dumps({'from': FROM, 'to': to, 'subject': subject, 'text': body}).encode(),
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
