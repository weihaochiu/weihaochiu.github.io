import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ChinesePublicationTests(unittest.TestCase):
    def test_source_records_are_unique_and_keep_unknown_metrics_empty(self):
        rows = json.loads((ROOT / 'data/publications.json').read_text(encoding='utf-8'))
        for identity in ('materialsnet-51511', 'materialsnet-51512', 'vacuum-technology-2021-mof-perovskite'):
            matches = [row for row in rows if row['id'] == identity]
            self.assertEqual(len(matches), 1)
            row = matches[0]
            self.assertEqual(row['publicationType'], 'chinese-journal')
            self.assertEqual(row['doi'], '')
            self.assertNotIn('citationCount', row)
            self.assertTrue(row['automationProtection']['protected'])
            self.assertFalse(any(row['analytics'].values()))
            page = (ROOT / 'publications' / (identity + '.html')).read_text(encoding='utf-8')
            self.assertIn(row['publicationUrl'].replace('&', '&amp;'), page)
            self.assertNotIn('Google Scholar citation', page)
            listing = (ROOT / 'publications.html').read_text(encoding='utf-8')
            card = re.search(r'<article\b[^>]*id="pub-' + identity + r'".*?</article>', listing, re.S)
            self.assertIsNotNone(card)
            self.assertNotIn('Google Scholar citation', card.group())
        self.assertEqual(sum('10158359-202108-202109170004' in row.get('publicationUrl', '') for row in rows), 1)

