"""Panama City Beach draft minutes found in later agendas (archive.pcb_drafts), without the network."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import archive as A  # noqa: E402

S3 = "https://legistarweb-production.s3.amazonaws.com/uploads/attachment/pdf"


def agenda(*names):
    return b"%PDF-1.4 " + b" ".join(b"<< /URI (" + ("%s/%d/%s" % (S3, 1000 + i, n)).encode() + b") >>" for i, n in enumerate(names))


class Drafts(unittest.TestCase):
    def test_minutes_date(self):
        self.assertEqual(A.minutes_date("01.13.2022.Council_Meeting_Minutes.draft.pdf"), dt.date(2022, 1, 13))
        self.assertEqual(A.minutes_date("07.27.2023_Council_Minutes.draft.pdf"), dt.date(2023, 7, 27))
        self.assertEqual(A.minutes_date("7.27.23 Council Minutes.pdf"), dt.date(2023, 7, 27))
        self.assertIsNone(A.minutes_date("Council_Minutes.pdf"))

    def test_links_keep_council_minutes_only(self):
        got = A.agenda_minutes_links(agenda("01.13.2022.Council_Meeting_Minutes.draft.pdf", "Res_22-81.pdf",
                                            "01.12.2022.Planning_Board_Minutes.pdf"))
        self.assertEqual(len(got), 1)
        d, url, name = got[0]
        self.assertEqual(d, dt.date(2022, 1, 13))
        self.assertEqual(url, "https://pcbgov.granicus.com/services/legistar/download/pdf/1000/01.13.2022.Council_Meeting_Minutes.draft.pdf")

    def test_drafts_fill_meetings_without_minutes(self):
        rows = [
            {"date": dt.date(2022, 1, 13), "name": "City Council", "minutes": None, "agenda": "a13"},
            {"date": dt.date(2022, 1, 27), "name": "City Council", "minutes": None, "agenda": "a27"},
            {"date": dt.date(2022, 2, 10), "name": "City Council", "minutes": "m", "agenda": "a10"},
        ]
        pdfs = {"a27": agenda("01.13.2022.Council_Meeting_Minutes.draft.pdf"),
                "a10": agenda("01.27.2022.Council_Meeting_Minutes.draft.pdf", "01.13.2022.Council_Meeting_Minutes.draft.pdf")}
        got = A.pcb_drafts(rows, 2016, 2026, get=lambda u: pdfs.get(u, b""))
        self.assertEqual([(r["date"], r["url"].rsplit("/", 1)[1]) for r in got],
                         [(dt.date(2022, 1, 13), "01.13.2022.Council_Meeting_Minutes.draft.pdf"),
                          (dt.date(2022, 1, 27), "01.27.2022.Council_Meeting_Minutes.draft.pdf")])
        self.assertIn("Jan 27, 2022 agenda", got[0]["title"])


if __name__ == "__main__":
    unittest.main()
