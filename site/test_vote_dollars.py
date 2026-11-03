"""Rules behind the contract dollars on officials' profiles (site/vote_dollars.py). Run: python3 -m unittest discover -s site -p 'test_*.py'"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vote_dollars as V  # noqa: E402


def vote(headline, summary='', item='Contract award', amount=None, cat='contract', outcome='passed', **kw):
    return {'headline': headline, 'plain_summary': '', 'summary': summary, 'item': item, 'amount': amount, 'category': cat, 'outcome': outcome, **kw}


class Figures(unittest.TestCase):
    def test_parses_dollar_figures(self):
        self.assertEqual(V.money_figures('for $69.497.00 and $1.2 million, $5,000.50, $1.234.567. Then $40,000.'),
                         [69497.0, 1200000.0, 5000.5, 1234567.0, 40000.0])


class Classify(unittest.TestCase):
    def amount(self, v, linked=(), researched=False):
        return V._classify(v, list(linked), researched)

    def test_one_figure_in_the_summary_is_counted(self):
        a = self.amount(vote('The board awarded contract 25-18 to Roberts and Roberts, Inc. for $571,999.45.', amount=571999.45))
        self.assertEqual((a[0], a[1], a[5]), (571999.45, 'vote summary', None))

    def test_the_largest_figure_in_the_minutes_is_never_used_alone(self):
        a = self.amount(vote('The board approved task order 25-06WW with Dewberry Engineers.', amount=402284.0))
        self.assertIsNone(a[0])
        self.assertIn('not tied to this approval', a[5])

    def test_two_figures_are_left_out(self):
        a = self.amount(vote('Awarded the contract to GAC for $700,211 with $70,021.10 contingency.'))
        self.assertIsNone(a[0])
        self.assertIn('several dollar figures', a[5])

    def test_not_new_spending(self):
        for h in ('The board approved a deductive change order with net savings of about $275,000.',
                  'Sold 75 acres of surplus land for $1,200,000.',
                  'Approved a lease agreement with Global Impact Products for $14,500,000.',
                  'Council approved paying KK Storm $313,440.11 for debris removal billing.',
                  'Amended the sludge contract to include hauling at $1,000 per 20-yard roll.',
                  'Approved a change order for $3,100, bringing the project total to $99,210.',
                  'Directed staff to present $4.5 million in budget cuts.',
                  'Started talks with Core & Main on smart water meters estimated at $8,697,999.62.',
                  'Postponed the Glencove contract award of $2,716,208 to April 24.'):
            self.assertIsNone(self.amount(vote(h))[0], h)

    def test_researched_background_is_not_a_figure(self):
        a = self.amount(vote('Extended Hurricane Michael recovery consultant contract', summary='about $100 million in costs not yet submitted'), researched=True)
        self.assertIsNone(a[0])

    def test_consent_agenda_needs_a_contract_record(self):
        v = vote('The board approved the consent agenda.', item='V Consent Agenda', cat='consent agenda', amount=331632.0, consent=True)
        self.assertIsNone(self.amount(v)[0])
        a = self.amount(v, [{'record_id': 'contract:1', 'record_amount': 818268.7}, {'record_id': 'contract:2', 'record_amount': 100.0}])
        self.assertEqual((a[0], a[1]), (818368.7, 'contract record'))

    def test_ceiling_and_yearly_marks(self):
        a = self.amount(vote('Awarded the paving bid for a not-to-exceed amount of $1,522,923.90.'))
        self.assertTrue(a[3])
        a = self.amount(vote('Renewed the mowing contract at $40,000 per year.'))
        self.assertTrue(a[4])


class Dedupe(unittest.TestCase):
    def row(self, vid, date, words, amount=55000.0, outcome='passed'):
        return {'vote_id': vid, 'gov_id': 'pc', 'date': date, 'amount': amount, 'counted': True, 'outcome': outcome, 'source_type': 'minutes',
                'contract_record_ids': None, '_words': set(words.split()), 'not_counted_reason': None, 'same_item_as': None}

    def test_same_item_twice_is_counted_once_on_the_later_vote(self):
        a, b = self.row('a', '2024-03-01', 'harrison avenue paving'), self.row('b', '2024-04-01', 'harrison avenue paving')
        other = self.row('c', '2024-05-01', 'fire truck purchase')
        V._dedupe([a, b, other])
        self.assertEqual((a['counted'], a['same_item_as'], b['counted'], other['counted']), (False, 'b', True, True))

    def test_a_year_apart_is_a_new_item(self):
        a, b = self.row('a', '2023-01-01', 'mowing contract renewal'), self.row('b', '2024-03-01', 'mowing contract renewal')
        V._dedupe([a, b])
        self.assertTrue(a['counted'] and b['counted'])


class Totals(unittest.TestCase):
    def test_raffield_totals_add_up_from_his_votes(self):
        t = next(t for t in V.totals() if t['person_id'] == 'daniel-raffield')
        mine = [r for r in V.member_rows() if r['person_id'] == 'daniel-raffield']
        yes = round(sum(r['amount'] for r in mine if r['vote'] == 'yes' and r['outcome'] == 'passed'), 2)
        self.assertEqual(t['yes_total'], yes)
        self.assertEqual(t['yes_votes'], sum(1 for r in mine if r['vote'] == 'yes' and r['outcome'] == 'passed'))
        self.assertGreaterEqual(t['first_date'], '2024-11-01')  # took office November 2024

    def test_every_counted_vote_has_a_source_and_one_figure(self):
        for r in V.items():
            if r['counted']:
                self.assertTrue(r['amount'] and r['amount'] > 0 and r['source_url'], r['vote_id'])
                self.assertIn(r['outcome'], ('passed', 'failed'))
            else:
                self.assertTrue(r['not_counted_reason'], r['vote_id'])
        self.assertTrue(all(int(r['date'][:4]) >= 2016 for r in V.items()))


if __name__ == '__main__':
    unittest.main()
