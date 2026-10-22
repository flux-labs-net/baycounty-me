"""Unit tests for extract_agendas.py. Run: python3 -m unittest discover data/agendas/tests"""
import io, json, os, sys, unittest, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import extract_agendas as x


class FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass


class T(unittest.TestCase):
    def setUp(self):
        self._open = urllib.request.urlopen
        os.environ['ANTHROPIC_API_KEY'] = 'test'

    def tearDown(self):
        urllib.request.urlopen = self._open

    def test_claude_request_and_parse(self):
        seen = {}
        out = {'meeting': {'body': 'City Council', 'date': '2026-09-24', 'time': '9:00 AM', 'location': None},
               'items': [{'number': 'H.1', 'section': 'Consent', 'title': 'Award bid to GAC Contractors', 'summary': None,
                          'kind': 'contract', 'amounts': [{'amount': 1250000, 'text': '$1.25 million'}], 'parties': ['GAC Contractors'], 'addresses': []}]}
        def fake(req, timeout=0):
            seen['body'] = json.loads(req.data); seen['headers'] = dict(req.header_items())
            return FakeResp(json.dumps({'content': [{'type': 'text', 'text': json.dumps(out)}], 'stop_reason': 'end_turn',
                                        'usage': {'input_tokens': 2000, 'output_tokens': 500}}).encode())
        urllib.request.urlopen = fake
        parsed, tin, tout = x.claude('AGENDA TEXT')
        self.assertEqual(parsed['items'][0]['amounts'][0]['amount'], 1250000)
        self.assertEqual((tin, tout), (2000, 500))
        self.assertEqual(seen['body']['model'], x.MODEL)
        self.assertTrue(seen['body']['model'].startswith(('claude-sonnet', 'claude-haiku')))
        self.assertEqual(seen['body']['output_config']['format']['type'], 'json_schema')
        self.assertIn('AGENDA TEXT', seen['body']['messages'][0]['content'])
        self.assertEqual(seen['headers'].get('Anthropic-version'), '2023-06-01')

    def test_refusal_and_max_tokens_raise(self):
        for reason in ('refusal', 'max_tokens'):
            urllib.request.urlopen = lambda req, timeout=0: FakeResp(json.dumps({'content': [], 'stop_reason': reason, 'usage': {}}).encode())
            with self.assertRaises(RuntimeError):
                x.claude('x')

    def test_helpers(self):
        self.assertEqual(x.cost('claude-sonnet-5-5', 1_000_000, 100_000), 3.0)
        self.assertIsNone(x.cost('unknown-model', 1, 1))
        self.assertEqual(x.norm_date('2026-10-27'), '2026-10-27')
        self.assertIsNone(x.norm_date('Oct 27'))
        self.assertEqual(x.to_text(b'<p>Item 1</p>\n\n\n\n<p>Item 2</p>', 'text/html'), 'Item 1\n\nItem 2')

    def test_schema_is_strict(self):
        def walk(s):
            if isinstance(s, dict):
                if s.get('type') == 'object':
                    self.assertIs(s.get('additionalProperties'), False)
                    self.assertEqual(set(s['required']), set(s['properties']))
                for v in s.values(): walk(v)
            elif isinstance(s, list):
                for v in s: walk(v)
        walk(x.SCHEMA)


if __name__ == '__main__':
    unittest.main()
