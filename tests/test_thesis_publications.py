import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from academic_monitor_common import publication_matches_existing
from publication_scope import is_automation_protected, is_research_publication


class ThesisPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.publications = json.loads(
            (ROOT / "data" / "publications.json").read_text(encoding="utf-8")
        )
        cls.theses = [
            row for row in cls.publications if row.get("publicationType") == "thesis"
        ]

    def test_research_kpis_remain_unchanged(self):
        research = [row for row in self.publications if is_research_publication(row)]
        core = [
            row
            for row in self.publications
            if row.get("analytics", {}).get("coreJournalCount") is True
        ]
        journal_metrics = [
            row
            for row in self.publications
            if row.get("analytics", {}).get("journalMetrics") is True
        ]
        self.assertEqual(42, len(self.publications))
        self.assertEqual(40, len(research))
        self.assertEqual(37, len(core))
        self.assertEqual(37, len(journal_metrics))
        self.assertEqual(2, len(self.theses))

    def test_theses_are_protected_doi_less_display_records(self):
        expected = {
            "phd-thesis-2011": (2011, "Ph.D.", "doctoral-thesis"),
            "ms-thesis-2005": (2005, "M.S.", "masters-thesis"),
        }
        self.assertEqual(set(expected), {row["id"] for row in self.theses})
        for thesis in self.theses:
            year, degree, document_type = expected[thesis["id"]]
            self.assertEqual(year, thesis["year"])
            self.assertEqual(degree, thesis["degree"])
            self.assertEqual(document_type, thesis["documentType"])
            self.assertFalse(thesis.get("doi"))
            self.assertTrue(thesis["repositoryUrl"].startswith("https://hdl.handle.net/"))
            self.assertTrue(thesis["abstract"])
            self.assertTrue(thesis["abstractZh"])
            self.assertTrue(thesis["keywords"])
            self.assertTrue(thesis["keywordsZh"])
            self.assertFalse(is_research_publication(thesis))
            self.assertTrue(is_automation_protected(thesis))
            self.assertTrue(all(value is False for key, value in thesis["analytics"].items() if key != "excludeFromResearchAnalytics"))

    def test_generated_thesis_pages_have_metadata_without_bibliometrics(self):
        for slug in ("phd-thesis-2011", "ms-thesis-2005"):
            page = (ROOT / "publications" / f"{slug}.html").read_text(encoding="utf-8")
            self.assertIn('<meta name="description"', page)
            self.assertIn(f'<link rel="canonical" href="https://weihaochiu.github.io/publications/{slug}.html"', page)
            self.assertIn('"@type":"CreativeWork"', page)
            self.assertIn("Institutional Repository", page)
            for forbidden in (
                "DOI ↗",
                "Google Scholar citation",
                "OpenAlex citation",
                "Crossref citation",
                "Mendeley reader",
                "FWCI ",
            ):
                self.assertNotIn(forbidden, page)

    def test_publications_page_and_discovery_files_include_theses(self):
        publications_page = (ROOT / "publications.html").read_text(encoding="utf-8")
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
        self.assertIn("Theses &amp; Dissertations", publications_page)
        for slug in ("phd-thesis-2011", "ms-thesis-2005"):
            self.assertIn(f"publications/{slug}.html", publications_page)
            self.assertIn(f"publications/{slug}.html", sitemap)
            self.assertIn(f"publications/{slug}.html", llms)
        self.assertIn("<!-- PATENT_LLMS_START -->", llms)
        self.assertIn("/patents/", sitemap)

    def test_academic_monitor_deduplicates_repository_and_bibliographic_identity(self):
        candidate_by_url = {"repositoryUrl": "http://hdl.handle.net/11296/y6376u?source=orcid"}
        candidate_by_title = {
            "title": self.theses[1]["title"],
            "year": 2005,
            "publicationType": "thesis",
        }
        self.assertTrue(publication_matches_existing(candidate_by_url, self.publications))
        self.assertTrue(publication_matches_existing(candidate_by_title, self.publications))


if __name__ == "__main__":
    unittest.main()
