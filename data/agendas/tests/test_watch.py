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
        self.assertEqual(w.fingerprint(b'<p>Hi  <b>there</b></p>', 'text/html'), w.fingerprint(b'<div>Hi there</div>', 'text/html'))


if __name__ == '__main__':
    unittest.main()
