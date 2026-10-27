"""Unit tests for archive.py parsers, text.chunks and read_minutes' answer handling (no network, no database).
Run: python3 -m unittest discover data/minutes/tests"""
import datetime as dt
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import archive as A  # noqa: E402
import read_minutes as R  # noqa: E402
import text as T  # noqa: E402
from test_match import DATA, PRESENT  # noqa: E402


class Archive(unittest.TestCase):
    def test_agendacenter(self):
        page = ('<div id="cat5"><h2 tabindex="0">City Commission Meetings</h2><table>'
                '<tr class="catAgendaRow"><td><p><a href="/AgendaCenter/ViewFile/Agenda/_12132016-265">Regular Meeting</a></p></td>'
                '<td class="minutes"><a href="/AgendaCenter/ViewFile/Minutes/_12132016-265">Minutes</a></td></tr>'
                '<tr class="catAgendaRow"><td><p><a href="/x">No minutes yet</a></p></td></tr></table></div>'
                '<div id="cat6"><h2>Planning Board</h2><table><tr class="catAgendaRow"><td>'
                '<a href="/AgendaCenter/ViewFile/Minutes/_01052016-1">M</a></td></tr></table></div>')
        recs = A.parse_agendacenter(page, "www.panamacity.gov", A.AC["pc"][1])
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["date"], dt.date(2016, 12, 13))
        self.assertEqual(recs[0]["board"], "pc")
        self.assertTrue(recs[0]["url"].startswith("https://www.panamacity.gov/AgendaCenter/ViewFile/Minutes/"))

    def test_lynn_haven_advisory_board_skipped(self):
        page = ('<div id="cat1"><h2>Community Redevelopment Agency Advisory Board</h2><table><tr class="catAgendaRow">'
                '<td><a href="/AgendaCenter/ViewFile/Minutes/_03012021-9">M</a></td></tr></table></div>')
        self.assertEqual(A.parse_agendacenter(page, "www.cityoflynnhaven.gov", A.AC["lh"][1]), [])

    def test_onbase(self):
        hits = [{"ID": "Ab=", "Name": "Year: 2016 Date: 1/5/2016 - 1/5/2016 - REGULAR MEETING MINUTES",
                 "DisplayColumnValues": [{"Value": "1/5/2016"}, {"Value": "2016"}, {"Value": "REGULAR MEETING MINUTES"}]}]
        r = A.parse_onbase(hits)[0]
        self.assertEqual(r["date"], dt.date(2016, 1, 5))
        self.assertIn("minutes=2016-01-05", r["url"])
        self.assertNotIn("Ab=", r["url"])          # the session-bound id never becomes the document key
        self.assertTrue(callable(r["fetch"]))

    def test_boarddocs_one_per_meeting(self):
        ms = [{"unique": "A1", "name": "School Board Meeting Agenda", "numberdate": "20240109"},
              {"unique": "A2", "name": "School Board Meeting Detailed Agenda", "numberdate": "20240109"},
              {"unique": "A3", "name": "Old", "numberdate": "20151208"}, {"unique": "A4", "name": "x", "numberdate": ""}]
        recs = A.parse_boarddocs(ms, 2016, 2026)
        self.assertEqual([r["url"].split("id=")[1] for r in recs], ["A1"])

    def test_boarddocs_backs_off_then_stops(self):
        calls, sleeps = [], []
        replies = [RuntimeError("HTTPError: HTTP Error 403: Forbidden"), (b"<p>%s</p>" % (b"x" * 300), "text/html")]

        def fake_req(url, data=None, ctype=None, **kw):
            calls.append(url)
            r = replies.pop(0) if replies else RuntimeError("HTTPError: HTTP Error 403: Forbidden")
            if isinstance(r, Exception):
                raise r
            return r
        old_req, old_sleep = A._req, A.fm.time.sleep
        A._req, A.fm.time.sleep = fake_req, sleeps.append
        A._bd.update(last=0.0, blocked=False)
        try:
            self.assertEqual(A.boarddocs_file("U1")()[1], "text/html")   # one 403, a wait, then the page
            self.assertIn(60, sleeps)
            with self.assertRaises(RuntimeError):                         # refused every time: give up for this run
                A.boarddocs_file("U2")()
            self.assertTrue(A._bd["blocked"])
            n = len(calls)
            with self.assertRaises(RuntimeError):                         # later files fail without asking again
                A.boarddocs_file("U3")()
            self.assertEqual(len(calls), n)
        finally:
            A._req, A.fm.time.sleep = old_req, old_sleep
            A._bd.update(last=0.0, blocked=False)

    def test_parker_year_file(self):
        page = ('<table id="filr-library-minutes-1"><tr><td class="title">2016 Minutes</td><td><a href="https://p/2016.pdf">x</a></td></tr>'
                '<tr><td class="title">2015 Official Minutes</td><td><a href="https://p/2015.pdf">x</a></td></tr>'
                '<tr><td class="title">March 1, 2022 Planning Commission</td><td><a href="https://p/pc.pdf">x</a></td></tr>'
                '<tr><td class="title">March 1, 2022 Regular Meeting</td><td><a href="https://p/r.pdf">x</a></td></tr></table>')
        recs = A.parse_parker(page, 2016, 2026)
        self.assertEqual([(r["date"].isoformat(), r["multi"]) for r in recs], [("2016-12-31", True), ("2022-03-01", False)])

    def test_parker_spaces_encoded(self):
        page = ('<table id="filr-library-minutes-1"><tr><td class="title">March 17, 2026 Regular Meeting</td>'
                '<td><a href="https://p/filr/6652/Approved Minutes 3.17.26.pdf">x</a></td></tr></table>')
        self.assertEqual(A.parse_parker(page, 2016, 2026)[0]["url"], "https://p/filr/6652/Approved%20Minutes%203.17.26.pdf")

    def test_archive_center(self):
        page = ('<a href="Archive.aspx?ADID=3854"><span>January 13, 2026, Regular Meeting</span></a>'
                '<a href="Archive.aspx?ADID=1"><span>Not a date</span></a>')
        recs = A.parse_archive_center(page, "cw")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["url"], "https://www.cityofcallaway.com/Archive.aspx?ADID=3854")


class Inventory(unittest.TestCase):
    def test_zero_years_are_kept(self):
        import crawl_minutes as C
        recs = [{"board": "pc", "date": dt.date(2017, 3, 1), "source": "pc"}, {"board": "pc", "date": dt.date(2017, 4, 1), "source": "pc"},
                {"board": "parker", "date": dt.date(2016, 12, 31), "source": "parker", "multi": True}]
        rows = C.inventory_rows(recs, 2016, 2018)
        self.assertIn(("pc", 2016, 0, 0, "pc"), rows)
        self.assertIn(("pc", 2017, 2, 0, "pc"), rows)
        self.assertIn(("parker", 2016, 1, 1, "parker"), rows)
        self.assertEqual(len(rows), 6)


class Text(unittest.TestCase):
    def test_chunks_break_at_meeting_start(self):
        pages = ["x" * 30000, "y" * 30000, "MINUTES OF THE REGULAR MEETING\n" + "z" * 30000, "w" * 30000]
        parts = T.chunks(pages, 90000)
        self.assertEqual([p[0] for p in parts], [1, 3])
        self.assertEqual(sum(len(p[1]) for p in parts), 4)
        self.assertEqual(len(T.chunks(["a" * 10] * 3)), 1)

    def test_html(self):
        self.assertIn("Yes: Chapman", T.html_text(b"<p>Motion carried</p><p>Yes: Chapman, Moss</p>"))

    def test_docx(self):
        import io
        import zipfile
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                       '<w:p><w:r><w:t>Motion by </w:t></w:r><w:r><w:t>Smith</w:t></w:r></w:p><w:p><w:r><w:t>Passed 5-0</w:t></w:r></w:p></w:body></w:document>')
        self.assertEqual(T.to_pages(b.getvalue(), T.DOCX), (["Motion by Smith\nPassed 5-0"], "text", 0))


class Answers(unittest.TestCase):
    answer = {"meetings": [{"board": "City Commission", "date": "2016-12-13", "type": "regular", "present": PRESENT, "absent": [],
                            "motions": [{"item_number": "9a", "item_title": "Janitorial services", "motion": "Award bid to Pro Force",
                                         "summary": "Awarded janitorial services to Pro Force.", "kind": "contract", "consent": False,
                                         "mover": "Brown", "seconder": None, "outcome": "passed", "tally_text": "5-0",
                                         "yes": ["Rader", "Nichols", "Kady", "Brown", "Mayor Brudnicki"], "no": [], "abstain": [],
                                         "absent": [], "unanimous": False, "amounts": [{"amount": 113640, "text": "$113,640"}],
                                         "ordinances": [], "resolutions": [], "parties": ["Pro Force"], "page": 2}]},
                           {"board": "City Commission", "date": "2015-12-08", "type": "regular", "present": [], "absent": [],
                            "motions": [{"item_number": None, "item_title": None, "motion": "old", "summary": "old", "kind": "other",
                                         "consent": False, "mover": None, "seconder": None, "outcome": "passed", "tally_text": None,
                                         "yes": [], "no": [], "abstain": [], "absent": [], "unanimous": True, "amounts": [],
                                         "ordinances": [], "resolutions": [], "parties": [], "page": 1}]}]}

    def test_rows(self):
        rows = R.motion_rows(self.answer["meetings"], "pc", dt.date(2016, 12, 13), data=DATA)
        self.assertEqual(len(rows), 1)                 # the 2015 meeting is dropped (site starts in 2016)
        r = rows[0]
        self.assertEqual((r["check_status"], r["tally"], r["amount"], r["page"]), ("passed", "5-0", 113640, 2))
        self.assertEqual(r["votes"]["Greg Brudnicki"], "yes")
        json.dumps(r)                                  # stored as jsonb

    def test_merge_chunks_joins_split_meeting(self):
        a = {"meetings": [{"date": "2016-12-13", "present": ["A"], "absent": [], "motions": [{"motion": "1"}]}]}
        b = {"meetings": [{"date": "2016-12-13", "present": ["B"], "absent": [], "motions": [{"motion": "2"}]},
                          {"date": "2017-01-10", "present": [], "absent": [], "motions": []}]}
        m = R.merge_chunks([a, b])
        self.assertEqual(len(m), 2)
        self.assertEqual([x["motion"] for x in m[0]["motions"]], ["1", "2"])
        self.assertEqual(m[0]["present"], ["A", "B"])

    def test_request_shape(self):
        p = R.body(R.params("Panama City Commission", "2016-12-13", "=== Page 1 ===\ntext", 1, 1), "claude-sonnet-5-5")
        self.assertEqual(p["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(p["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertIn("2016-12-13", p["messages"][0]["content"])

    def test_request_shape_gpt(self):
        p = R.body(R.params("Panama City Commission", "2016-12-13", "=== Page 1 ===\ntext", 1, 1), "gpt-6.1-sol")
        self.assertEqual(p["model"], "gpt-6.1-sol")
        self.assertEqual(p["response_format"]["json_schema"]["strict"], True)
        self.assertIs(p["response_format"]["json_schema"]["schema"], R.SCHEMA)
        self.assertEqual(p["messages"][0]["content"], R.SYSTEM)
        self.assertIn("2016-12-13", p["messages"][1]["content"])

    def test_batch_price_is_half(self):
        self.assertAlmostEqual(R.price(1_000_000, 0, model="claude-sonnet-5-5"), 1.0)   # $2 per million in, half in a batch
        self.assertAlmostEqual(R.price(1_000_000, 100_000, model="gpt-6.1-sol"), 1.5)    # $2 in / $10 out, half in a batch


if __name__ == "__main__":
    unittest.main()
