import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_publications import validate_generated_publication


def journal_record(**overrides):
    record = {
        "id": "journal-example",
        "publicationType": "international-journal",
        "authors": ["Wei-Hao Chiu"],
        "authorships": [
            {
                "name": "Wei-Hao Chiu",
                "isEqualContributor": False,
                "isCorresponding": False,
            }
        ],
        "affiliations": [],
    }
    record.update(overrides)
    return record


def journal_html(extra=""):
    return (
        '<article class="publication-detail">'
        '<p class="authors publication-authors">'
        '<span class="publication-author">'
        '<button class="author-trigger me" data-author-name="Wei-Hao Chiu">'
        "Wei-Hao Chiu"
        "</button></span></p>"
        f"{extra}</article>"
    )


def thesis_record(**overrides):
    record = {
        "id": "thesis-example",
        "publicationType": "thesis",
        "authors": ["Wei-Hao Chiu"],
        "advisor": "Wen-Feng Hsieh",
    }
    record.update(overrides)
    return record


def thesis_html(*, author=True, institution=True, advisor=True):
    facts = []
    if author:
        facts.append(
            '<div class="thesis-fact"><dt>Author</dt><dd>'
            '<span class="publication-author">'
            '<button class="author-trigger me" data-author-name="Wei-Hao Chiu">'
            "Wei-Hao Chiu"
            "</button></span></dd></div>"
        )
    facts.append('<div class="thesis-fact"><dt>Degree</dt><dd>Ph.D.</dd></div>')
    facts.append('<div class="thesis-fact"><dt>Year</dt><dd>2011</dd></div>')
    if institution:
        facts.append(
            '<div class="thesis-fact"><dt>Institution</dt>'
            "<dd>National Central University</dd></div>"
        )
    if advisor:
        facts.append(
            '<div class="thesis-fact"><dt>Advisor</dt><dd>Wen-Feng Hsieh</dd></div>'
        )
    return (
        '<article class="publication-detail thesis-detail">'
        "<section><h2>Basic Information</h2><dl>"
        + "".join(facts)
        + "</dl></section></article>"
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"CreativeWork"}'
        "</script>"
    )


class GeneratedPublicationValidationTests(unittest.TestCase):
    def assert_valid(self, record, html):
        self.assertEqual([], validate_generated_publication(record, html))

    def assert_invalid_with(self, record, html, expected):
        errors = validate_generated_publication(record, html)
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_international_journal_with_static_author_row_passes(self):
        self.assert_valid(journal_record(), journal_html())

    def test_international_journal_without_static_author_row_fails(self):
        html = journal_html().replace(" publication-authors", "")
        self.assert_invalid_with(journal_record(), html, "publication-authors")

    def test_thesis_without_journal_author_row_but_with_thesis_author_markup_passes(self):
        html = thesis_html()
        self.assertNotIn("publication-authors", html)
        self.assert_valid(thesis_record(), html)

    def test_thesis_without_author_fails(self):
        self.assert_invalid_with(thesis_record(), thesis_html(author=False), "Author")

    def test_thesis_without_institution_fails(self):
        self.assert_invalid_with(
            thesis_record(), thesis_html(institution=False), "Institution"
        )

    def test_journal_with_affiliation_metadata_without_affiliation_block_fails(self):
        record = journal_record(
            affiliations=[{"id": "aff-1", "institution": "Chang Gung University"}]
        )
        self.assert_invalid_with(record, journal_html(), "publication-affiliations")

    def test_unknown_publication_type_fails(self):
        record = journal_record(publicationType="dataset")
        self.assert_invalid_with(
            record, journal_html(), "Unsupported scholarly output type: dataset"
        )

    def test_equal_contributor_without_marker_or_legend_fails(self):
        record = journal_record(
            authorships=[
                {
                    "name": "Wei-Hao Chiu",
                    "isEqualContributor": True,
                    "isCorresponding": False,
                }
            ]
        )
        html = journal_html('<details class="publication-affiliations"></details>')
        self.assert_invalid_with(record, html, "equal-contributor")

    def test_corresponding_author_without_marker_or_legend_fails(self):
        record = journal_record(
            authorships=[
                {
                    "name": "Wei-Hao Chiu",
                    "isEqualContributor": False,
                    "isCorresponding": True,
                }
            ]
        )
        html = journal_html('<details class="publication-affiliations"></details>')
        self.assert_invalid_with(record, html, "corresponding-author")

    def test_thesis_with_advisor_metadata_without_advisor_row_fails(self):
        self.assert_invalid_with(
            thesis_record(), thesis_html(advisor=False), "Advisor"
        )


if __name__ == "__main__":
    unittest.main()
