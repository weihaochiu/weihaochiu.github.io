import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDENTIFIERS = (
    'sdse-2025-sn-o2-mesoporous-ti-o2', 'sdse-2026-preheating-lma',
    'sdse-2026-c3n4-graphite-felt', 'pesi-2026-pvdf-hfp-space-reliability',
    'twiche-2025-tin-lead-quasi-2d', 'twiche-2023-tio2-graphite-felt',
    'fpg-2023-laser-crystallization', 'sdse-2023-cesium-halides',
    'sdse-2023-pentafulvalene-htm', 'twiche-2023-blade-slot-die',
    'twiche-2023-csi-two-step', 'iedms-2023-csi-two-step',
    'iedms-2023-blade-slot-die',
    'iedms-2021-dopant-free-blade-coating', 'iedms-2021-csi-two-step',
    'twiche-2021-dopant-free-blade-coating', 'twiche-2021-csi-two-step',
    'acoe-2023-cesium-halides', 'acoe-2023-pentafulvalene-htm',
    'pvsec-35-2024-sn-o2-mesoporous-ti-o2', 'pvsec-35-2024-pentafulvalene-htm',
    'fpg-2024-tio2-nanorods-graphite-felt', 'fpg-2025-tin-lead-quasi-2d',
    'fpg-2025-c3n4-graphite-felt', 'wcpec-9-2026-green-solvents',
    'wcpec-9-2026-pvdf-hfp-space-reliability',
)


class ConferencePublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((ROOT / 'data/publications.json').read_text(encoding='utf-8'))
        cls.records = {row['id']: row for row in cls.rows}

    def test_bilingual_fpg_names_and_event_identity(self):
        for identity, ordinal in [('fpg-2023-laser-crystallization', 18),
                                  ('fpg-2024-tio2-nanorods-graphite-felt', 19),
                                  ('fpg-2025-tin-lead-quasi-2d', 20),
                                  ('fpg-2025-c3n4-graphite-felt', 20)]:
            row = self.records[identity]
            self.assertEqual(row['conference']['nameEn'], f'{ordinal}th Formosa Plastics Group Applied Technology Seminar')
            for path in [ROOT / 'publications.html', ROOT / 'publications' / (identity + '.html')]:
                html = path.read_text(encoding='utf-8')
                self.assertIn(row['conference']['nameEn'], html)
                self.assertIn(row['conference']['nameZh'], html)
                self.assertIn('lang="zh-Hant"', html)
        self.assertEqual(self.records['twiche-2021-csi-two-step']['date'], '2022-01-06')
        self.assertEqual(len(self.records['acoe-2023-cesium-halides']['authors']), 3)
        self.assertEqual(len(self.records['sdse-2023-cesium-halides']['authors']), 4)

    def test_manuscripts_preserve_identity_and_avoid_inferred_bibliometrics(self):
        for identity in IDENTIFIERS:
            with self.subTest(identity=identity):
                self.assertEqual(sum(row['id'] == identity for row in self.rows), 1)
                row = self.records[identity]
                self.assertEqual(row['publicationType'], 'conference')
                self.assertTrue(row['automationProtection']['protected'])
                self.assertFalse(any(row['analytics'].values()))
                self.assertEqual(row['doi'], '')
                self.assertNotIn('citationCount', row)
                self.assertGreater(len(row['abstract']), 100)
                self.assertEqual(row['authors'], [a['name'] for a in row['authorships']])
                self.assertNotIn('/', row['sourceDocument'])
                self.assertNotIn('\\', row['sourceDocument'])
                page = (ROOT / 'publications' / (identity + '.html')).read_text(encoding='utf-8')
                self.assertIn('Conference information', page)
                self.assertIn(row['conference']['startDate'], page)
                self.assertNotIn('Google Scholar citation', page)
                self.assertNotIn('圖二的scale bar', page)
                for aff in row['affiliations']:
                    self.assertNotIn(aff['department'] + ', ' + aff['institution'] + ', ' + aff['raw'], page) if aff['department'] else None
                for image in re.findall(r'<img[^>]+src="([^"]+)"', page):
                    self.assertTrue((ROOT / 'publications' / image).is_file(), image)

    def test_acceptance_and_event_specific_authorship(self):
        lma = self.records['sdse-2026-preheating-lma']['conference']
        self.assertEqual((lma['acceptanceStatus'], lma['presentationType'], lma['abstractNumber']),
                         ('Accepted', 'Poster', '00145'))
        self.assertEqual(lma['presentingAuthor'], 'Wei-Hao Chiu')
        for identity in IDENTIFIERS:
            if identity != 'sdse-2026-preheating-lma':
                self.assertEqual(self.records[identity]['conference']['acceptanceStatus'], '')
        first = self.records['twiche-2023-csi-two-step']
        second = self.records['iedms-2023-csi-two-step']
        self.assertEqual(first['title'], second['title'])
        self.assertEqual(len(first['authors']), 3)
        self.assertEqual(len(second['authors']), 4)
        self.assertNotEqual(first['conference']['startDate'], second['conference']['startDate'])
        self.assertEqual(self.records['fpg-2023-laser-crystallization']['authors'][0], '陳思羽')
        chinese_page = (ROOT / 'publications/fpg-2023-laser-crystallization.html').read_text(encoding='utf-8')
        self.assertIn('長庚大學化工與材料學系', chinese_page)
        self.assertEqual(self.records['sdse-2023-pentafulvalene-htm']['authors'][-1], 'Yan-Duo Lin')

