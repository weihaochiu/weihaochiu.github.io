import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PdfBibliographyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((ROOT / 'data/publications.json').read_text(encoding='utf-8'))
        cls.records = {row['id']: row for row in cls.rows}

    def test_new_bibliography_records_do_not_infer_manuscripts_or_metrics(self):
        additions = [row for row in self.rows if row.get('sourceDocument') in {
            'WHChiu-International Conference Paper.pdf', 'WHChiu-Domestie Conference Paper.pdf'}]
        self.assertEqual(19, len(additions))
        for row in additions:
            with self.subTest(identity=row['id']):
                self.assertEqual('conference', row['publicationType'])
                self.assertEqual('other', row['documentType'])
                self.assertEqual('', row['abstract'])
                self.assertEqual('', row['doi'])
                self.assertFalse(any(row['analytics'].values()))
                self.assertTrue(row['automationProtection']['protected'])
                self.assertEqual(row['authors'], [a['name'] for a in row['authorships']])
                self.assertTrue(all(a['isCorresponding'] is None for a in row['authorships']))
                page = (ROOT / 'publications' / (row['id'] + '.html')).read_text(encoding='utf-8')
                self.assertNotIn('Google Scholar citation', page)
                self.assertNotIn('Full conference manuscript', page)
                self.assertIn('Conference contribution (bibliographic record)', page)

    def test_new_journal_and_no_duplicate_aepa(self):
        journal = self.records['10.1002/advs.77623']
        self.assertEqual('2026-09-08', journal['date'])
        self.assertEqual('e77623', journal['pages'])
        self.assertEqual(14, len(journal['authors']))
        self.assertEqual(7, journal['authorOrder'])
        self.assertNotIn('citationCount', journal)
        page = (ROOT / 'publications/10-1002-advs-77623.html').read_text(encoding='utf-8')
        self.assertNotIn('0 Google Scholar', page)
        self.assertEqual(1, sum(row.get('conference', {}).get('acronym') == 'AEPA 2026' for row in self.rows))
        self.assertFalse(any('Stroke Organisation' in row.get('journal', '') for row in self.rows))

    def test_source_conflicts_do_not_overwrite_previously_verified_authors(self):
        blade = self.records['sdse-2025-blade-coating']
        self.assertEqual(['Wei-Chen Chu', 'Wei-Hao Chiu', 'Kun-Mu Lee'], blade['authors'])
        isos = self.records['isos-15-2024-pvdf-hfp-space-reliability']
        self.assertEqual(['Wei-Hao Chiu', 'Kun-Mu Lee', 'Wei-Chen Chu', 'Seoungjun Ahn'], isos['authors'])
        self.assertEqual('conference-full-paper', self.records['iedms-2021-dopant-free-blade-coating']['documentType'])

    def test_patent_document_stages_and_families(self):
        patents = json.loads((ROOT / 'data/patents.json').read_text(encoding='utf-8'))
        records = {p['canonicalId']: p for p in patents}
        families = json.loads((ROOT / 'data/patent_families.json').read_text(encoding='utf-8'))
        self.assertEqual(16, len(records))
        self.assertEqual(9, len(families))
        for identity in ['US20120055796A1', 'TW201216482A']:
            self.assertEqual('Published application', records[identity]['documentStage'])
            self.assertEqual('', records[identity]['grantDate'])
            family = next(f for f in families if f['familyId'] == records[identity]['familyId'])
            self.assertIn(identity, family['documents'])
        self.assertEqual('Granted', records['US8470150B2']['documentStage'])
        self.assertEqual('Granted', records['CN102456482B']['documentStage'])
