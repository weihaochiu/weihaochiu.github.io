from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from patent_common import (  # noqa: E402
    build_alias_index,
    canonicalize_identifier,
    merge_automatic_metadata,
    parse_google_patent_page,
    search_records_from_payload,
)


class PatentIdentityTests(unittest.TestCase):
    def test_aliases_resolve_to_one_canonical_document(self) -> None:
        records = [
            {
                "canonicalId": "TWI816357B",
                "number": "I816357",
                "aliases": ["TW202341505A", "TW I816357 B"],
            }
        ]
        aliases = build_alias_index(records)
        self.assertEqual(canonicalize_identifier("I816357", aliases), "TWI816357B")
        self.assertEqual(canonicalize_identifier("TW 202341505 A", aliases), "TWI816357B")

    def test_ambiguous_alias_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_alias_index(
                [
                    {"canonicalId": "TWI1B", "aliases": ["I1"]},
                    {"canonicalId": "TWI2B", "aliases": ["I1"]},
                ]
            )


class PatentParsingTests(unittest.TestCase):
    def test_structured_search_records_keep_number_and_title_paired(self) -> None:
        payload = json.dumps(
            {
                "results": [
                    {"publication_number": "TW-I816357-B", "title": "<b>Solar</b> module"},
                    {"publicationNumber": "US-123-A1", "title": "Second result"},
                ]
            }
        )
        self.assertEqual(
            search_records_from_payload(payload),
            [
                {"number": "TWI816357B", "title": "Solar module"},
                {"number": "US123A1", "title": "Second result"},
            ],
        )

    def test_unstructured_search_response_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            search_records_from_payload("<html>not a JSON search response</html>")

    def test_exact_page_parser_extracts_only_the_record_page(self) -> None:
        page = """
        <html><head>
          <meta name="DC.title" content="Grooved solar module - Google Patents">
          <meta name="DC.contributor" content="Wei-Hao Chiu">
          <meta name="DC.contributor" content="Chao-Sung Lai">
          <meta name="DC.rights" content="Chang Gung University">
          <meta name="DC.description" content="A verified abstract.">
          <meta scheme="dateSubmitted" content="2023-03-01">
          <meta scheme="datePublished" content="2024-08-11">
          <meta scheme="priorityDate" content="2023-03-01">
        </head><body>
          <dd itemprop="publicationNumber">TW I851990 B</dd>
          <dd itemprop="applicationNumber">TW112108000A</dd>
          <span itemprop="countryCode">TW</span>
          <span itemprop="status">Active</span>
          <span itemprop="Code">H01L31/00</span>
          <div>2024-08-11 Application granted</div>
        </body></html>
        """
        parsed = parse_google_patent_page(page)
        self.assertEqual(parsed["canonicalId"], "TWI851990B")
        self.assertEqual(parsed["titleEn"], "Grooved solar module")
        self.assertEqual(parsed["inventors"], ["Wei-Hao Chiu", "Chao-Sung Lai"])
        self.assertEqual(parsed["grantDate"], "2024-08-11")
        self.assertEqual(parsed["classifications"], ["H01L31/00"])


class PatentMergeTests(unittest.TestCase):
    def test_automatic_metadata_cannot_replace_manual_identity(self) -> None:
        manual = {
            "canonicalId": "TWI851990B",
            "titleEn": "Manually verified title",
            "inventors": [{"personId": "wei-hao-chiu", "nameEn": "Wei-Hao Chiu"}],
            "legalStatus": "",
        }
        merged = merge_automatic_metadata(
            manual,
            {
                "canonicalId": "WRONG",
                "titleEn": "Automatically changed title",
                "inventors": ["Wrong Person"],
                "legalStatus": "Active",
                "filingDate": "2023-03-01",
            },
        )
        self.assertEqual(merged["canonicalId"], "TWI851990B")
        self.assertEqual(merged["titleEn"], "Manually verified title")
        self.assertEqual(merged["inventors"], manual["inventors"])
        self.assertEqual(merged["legalStatus"], "Active")
        self.assertEqual(merged["filingDate"], "2023-03-01")


if __name__ == "__main__":
    unittest.main()
