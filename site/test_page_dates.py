import unittest
from unittest import mock

import page_dates as pd

PAGE = '<p>Beach flag: yellow</p><p class="foot-links">Page updated {d} · About</p><script>{{"dateModified": "{iso}"}}</script>'


class PageDatesTest(unittest.TestCase):
    def setUp(self):
        pd._now.clear()

    def test_stamps_do_not_count_as_a_change(self):
        a = PAGE.format(d='Nov 3, 2026', iso='2026-11-03')
        b = PAGE.format(d='Nov 16, 2026', iso='2026-11-16')
        self.assertEqual(pd._hash(a), pd._hash(b))
        es_a = '<p>Página actualizada el 3 de noviembre de 2026 · Datos actualizados el 3 de noviembre de 2026</p>'
        es_b = '<p>Página actualizada el 16 de noviembre de 2026 · Datos actualizados el 16 de noviembre de 2026</p>'
        self.assertEqual(pd._hash(es_a), pd._hash(es_b))

    def test_same_content_keeps_its_date(self):
        html = PAGE.format(d='Nov 3, 2026', iso='2026-11-03')
        with mock.patch.object(pd, '_saved', {'/': {'h': pd._hash(html), 'd': '2026-11-03'}}), \
             mock.patch.object(pd, 'today', return_value='2026-11-16'):
            self.assertEqual(pd.updated('/', html, '/nope'), '2026-11-03')

    def test_new_content_gets_today(self):
        old = PAGE.format(d='Nov 3, 2026', iso='2026-11-03')
        new = old.replace('yellow', 'red')
        with mock.patch.object(pd, '_saved', {'/': {'h': pd._hash(old), 'd': '2026-11-03'}}), \
             mock.patch.object(pd, 'today', return_value='2026-11-16'):
            self.assertEqual(pd.updated('/', new, '/nope'), '2026-11-16')
            self.assertEqual(pd.get('/'), '2026-11-16')

    def test_newer_whats_new_entry_wins(self):
        html = PAGE.format(d='Nov 3, 2026', iso='2026-11-03')
        with mock.patch.object(pd, '_saved', {'/': {'h': pd._hash(html), 'd': '2026-11-03'}}):
            self.assertEqual(pd.updated('/', html, '/nope', floor='2026-11-10'), '2026-11-10')


if __name__ == '__main__':
    unittest.main()
