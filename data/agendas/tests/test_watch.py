"""Unit tests for the agenda watcher's email parsing. Run: python3 -m unittest discover data/agendas/tests"""
import os, sys, unittest
from email.message import EmailMessage
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import watch_agendas as w


def mail(frm, subject, text=None, html=None, pdf=None):
    m = EmailMessage(); m['From'] = frm; m['Subject'] = subject; m['Message-ID'] = '<x@y>'
    m['Date'] = 'Thu, 22 Oct 2026 13:00:00 -0500'
    m.set_content(text or 'see link')
    if html: m.add_alternative(html, subtype='html')
    if pdf: m.add_attachment(pdf, maintype='application', subtype='pdf', filename='agenda.pdf')
    return m.as_bytes()


class T(unittest.TestCase):
    def test_civicplus_notify_me(self):
        raw = mail('City of Panama City <noreply@civicplus.com>', 'Agenda posted: City Commission',
                   html='<p>A new agenda was posted.</p><a href="https://www.panamacity.gov/AgendaCenter/ViewFile/Agenda/_10272026-920">View</a>'
                        '<a href="https://www.panamacity.gov/AgendaCenter">Agenda Center</a>')
        p = w.parse_email(raw)
        keys, docs = w.classify(p)
        self.assertEqual(keys, ['pc'])
        self.assertEqual(docs, ['https://www.panamacity.gov/AgendaCenter/ViewFile/Agenda/_10272026-920'])
        self.assertTrue(p['received_at'].startswith('2026-10-22T13:00'))

    def test_sender_domain_and_name_fallback(self):
        self.assertEqual(w.classify(w.parse_email(mail('clerk@cityofcallaway.com', 'Agenda')))[0], ['cw'])
        self.assertEqual(w.classify(w.parse_email(mail('notify@civicplus.com', 'Lynn Haven agenda posted')))[0], ['lh'])
        self.assertEqual(w.classify(w.parse_email(mail('x@relay.net', 'City of Panama City Beach council agenda')))[0], ['pcb'])
        self.assertEqual(w.classify(w.parse_email(mail('x@relay.net', 'Your receipt')))[0], [])

    def test_attachment_and_canonical(self):
        p = w.parse_email(mail('a@b.com', 's', pdf=b'%PDF-1.4 test'))
        self.assertEqual(len(p['attachments']), 1)
        self.assertEqual(p['attachments'][0]['filename'], 'agenda.pdf')
        self.assertEqual(w.canonical('https://www.panamacity.gov/AgendaCenter/ViewFile/Agenda/_1-9?html=true'),
                         'https://www.panamacity.gov/AgendaCenter/ViewFile/Agenda/_1-9')
        self.assertEqual(w.canonical('https://cityofparker.com/filr/6652/Approved Minutes 3.17.26.pdf'),
                         'https://cityofparker.com/filr/6652/Approved%20Minutes%203.17.26.pdf')
        self.assertEqual(w.fingerprint(b'<p>Hi  <b>there</b></p>', 'text/html'), w.fingerprint(b'<div>Hi there</div>', 'text/html'))


class ResendInbox(unittest.TestCase):
    def setUp(self):
        self._get = w.resend_get

    def tearDown(self):
        w.resend_get = self._get

    def test_addressed_to(self):
        self.assertTrue(w.addressed_to({'to': ['Ingest <ingest@baycounty.me>']}, 'ingest@baycounty.me'))
        self.assertTrue(w.addressed_to({'to': ['x@y.com'], 'received_for': ['ingest@baycounty.me']}, 'ingest@baycounty.me'))
        self.assertFalse(w.addressed_to({'to': ['hello@baycounty.me']}, 'ingest@baycounty.me'))

    def test_list_stops_at_lookback(self):
        import datetime as dt
        new = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).isoformat()
        old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=40)).isoformat()
        w.resend_get = lambda path, key: {'has_more': True, 'data': [{'id': 'a', 'created_at': new}, {'id': 'b', 'created_at': old}]}
        self.assertEqual([x['id'] for x in w.resend_list('k')], ['a'])

    def test_raw_fallback_rebuilds_message(self):
        w.resend_get = lambda path, key: {'raw': None, 'subject': 'Agenda posted', 'headers': {'from': 'Callaway <clerk@cityofcallaway.com>'},
                                          'message_id': '<m@x>', 'created_at': '2026-10-22 19:13:17.694+00',
                                          'text': 'New agenda', 'html': '<a href="https://www.cityofcallaway.com/AgendaCenter/ViewFile/Agenda/_10272026-430">View</a>'}
        p = w.parse_email(w.resend_raw('k', 'id1'))
        self.assertEqual(w.classify(p), (['cw'], ['https://www.cityofcallaway.com/AgendaCenter/ViewFile/Agenda/_10272026-430']))

    def test_notice_from_resend_dry_run(self):
        run = w.Run(w.DB(None, True), w.Storage()); run.storage.url = ''
        w.resend_get = lambda path, key: {'data': [{'id': 'e1', 'to': ['ingest@baycounty.me'], 'created_at': '2099-01-01T00:00:00Z'},
                                                   {'id': 'e2', 'to': ['hello@baycounty.me'], 'created_at': '2099-01-01T00:00:00Z'}]} \
            if path.startswith('/emails/receiving?') else {'raw': None, 'subject': 'Lynn Haven agenda', 'headers': {'from': 'a@b.c'}, 'text': 'x'}
        self.assertEqual(run.resend_inbox('k'), {'lh'})
        self.assertEqual(run.counts['notices'], 1)


if __name__ == '__main__':
    unittest.main()
