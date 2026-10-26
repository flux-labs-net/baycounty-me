"""Unit tests for match.py. Run: python3 -m unittest discover data/minutes/tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import match as M  # noqa: E402

DATA = {"governments": [
    {"gov_id": "pc", "seats": [
        {"seat": "Mayor", "terms": [{"name": "Greg Brudnicki", "end": "2021-04-27"}, {"name": "Michael Rohan", "start": "2021-04-27"}]},
        {"seat": "Ward 1", "terms": [{"name": "John Kady"}]},
        {"seat": "Ward 2", "terms": [{"name": "Kenneth Brown"}]},
        {"seat": "Ward 3", "terms": [{"name": "Billy Rader"}]},
        {"seat": "Ward 4", "terms": [{"name": "Mike Nichols"}]},
        {"seat": "City Manager", "appointed": True, "terms": [{"name": "Jeff Brown"}]}]},
    {"gov_id": "schools", "seats": [
        {"seat": "Superintendent", "terms": [{"name": "Bill Husfelt"}]},
        {"seat": "District 1", "terms": [{"name": "Jerry Register"}]},
        {"seat": "District 2", "terms": [{"name": "Ginger Littleton", "end": "2020-11-17", "end_approx": True}, {"name": "Brenda Ruthven", "start": "2020-11-17"}]},
        {"seat": "District 3", "terms": [{"name": "Pamm Chapman"}]},
        {"seat": "District 4", "terms": [{"name": "Winston Chester"}]},
        {"seat": "District 5", "terms": [{"name": "Steve Moss"}]}]},
]}
PRESENT = ["Mayor Greg Brudnicki", "Commissioner John Kady", "Kenneth E. Brown", "Billy Rader", "Mike Nichols"]


class Roster(unittest.TestCase):
    def test_seats_on_date(self):
        names = [r["name"] for r in M.roster("pc", "2016-12-13", DATA)]
        self.assertEqual(names, ["Greg Brudnicki", "John Kady", "Kenneth Brown", "Billy Rader", "Mike Nichols"])
        self.assertIn("Michael Rohan", [r["name"] for r in M.roster("pc-cra", "2022-01-11", DATA)])

    def test_non_voting_seats_left_out(self):
        names = [r["name"] for r in M.roster("schools", "2023-01-10", DATA)]
        self.assertNotIn("Bill Husfelt", names)
        self.assertEqual(len(names), 5)

    def test_approximate_end_has_slack(self):
        names = [r["name"] for r in M.roster("schools", "2020-12-01", DATA)]
        self.assertIn("Ginger Littleton", names)  # end_approx: within 75 days
        self.assertIn("Brenda Ruthven", names)


class Names(unittest.TestCase):
    names = ["Greg Brudnicki", "John Kady", "Kenneth Brown", "Billy Rader", "Mike Nichols"]

    def test_titles_and_ocr(self):
        self.assertEqual(M.resolve("Commissioner Rader", self.names), "Billy Rader")
        self.assertEqual(M.resolve("Mavor Brudnicki", self.names), "Greg Brudnicki")
        self.assertEqual(M.resolve("Kadv", self.names), "John Kady")
        self.assertEqual(M.resolve("Kenneth E. Brown", self.names), "Kenneth Brown")
        self.assertIsNone(M.resolve("Ms. Channon Johnston", self.names))

    def test_shared_last_name_needs_first(self):
        names = ["Chris Moore", "Doug Moore"]
        self.assertIsNone(M.resolve("Commissioner Moore", names))
        self.assertEqual(M.resolve("Doug Moore", names), "Doug Moore")
        self.assertEqual(M.resolve("D. Moore", names), "Doug Moore")

    def test_tally(self):
        self.assertEqual(M.parse_tally("passed by a 5-0 vote"), (5, 0))
        self.assertEqual(M.parse_tally("carried 4 to 1"), (4, 1))
        self.assertIsNone(M.parse_tally("carried unanimously"))


class Votes(unittest.TestCase):
    meeting = {"date": "2016-12-13", "present": PRESENT, "absent": []}

    def test_roll_call(self):
        m = {"yes": ["Rader", "Nichols", "Kady", "Brown", "Mayor Brudnicki"], "no": [], "outcome": "passed", "tally_text": "5-0"}
        r = M.evaluate(m, self.meeting, "pc", data=DATA)
        self.assertEqual(r["method"], "roll_call")
        self.assertEqual(r["tally"], "5-0")
        self.assertEqual(r["checks"], [])
        self.assertEqual(r["check_status"], "passed")

    def test_split_vote_and_unanimous_expansion(self):
        m = {"yes": ["Rader", "Nichols", "Kady", "Brudnicki"], "no": ["Brown"], "outcome": "passed", "tally_text": "4-1"}
        r = M.evaluate(m, self.meeting, "pc", data=DATA)
        self.assertEqual(r["votes"]["Kenneth Brown"], "no")
        self.assertEqual(r["checks"], [])
        u = M.evaluate({"unanimous": True, "outcome": "passed"}, {**self.meeting, "absent": ["Commissioner Nichols"],
                                                                   "present": PRESENT[:4]}, "pc", data=DATA)
        self.assertEqual(u["votes"]["Mike Nichols"], "absent")
        self.assertEqual(u["tally"], "4-0")
        self.assertEqual(u["method"], "unanimous")

    def test_flags(self):
        m = {"yes": ["Rader", "Nichols"], "no": [], "outcome": "passed", "tally_text": "5-0"}
        self.assertIn("tally_mismatch", M.evaluate(m, self.meeting, "pc", data=DATA)["checks"])
        m = {"yes": ["Rader", "Nichols", "Kady", "Brown", "Smith"], "outcome": "passed"}
        r = M.evaluate(m, self.meeting, "pc", data=DATA)
        self.assertIn("unmatched_name", r["checks"])
        self.assertEqual(r["unmatched"], ["Smith"])
        self.assertIn("no_vote_detail", M.evaluate({"outcome": "failed"}, self.meeting, "pc", data=DATA)["checks"])
        self.assertIn("date_mismatch", M.evaluate({"unanimous": True, "outcome": "passed"}, self.meeting, "pc",
                                                  doc_date="2016-11-22", data=DATA)["checks"])

    def test_off_term_member_flagged(self):
        m = {"yes": ["Rohan", "Kady", "Brown", "Rader", "Nichols"], "outcome": "passed", "tally_text": "5-0"}
        r = M.evaluate(m, self.meeting, "pc", data=DATA)
        self.assertIn("off_term", r["checks"])


if __name__ == "__main__":
    unittest.main()
