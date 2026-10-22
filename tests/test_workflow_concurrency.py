"""Keep every shared content writer on the same non-replacing Actions queue."""
import re
import unittest
from pathlib import Path


WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


class WorkflowConcurrencyTests(unittest.TestCase):
    def test_shared_content_writers_retain_pending_runs(self):
        expected = {
            "build-seo.yml", "update-crossref.yml", "update-journals.yml",
            "update-grb-projects.yml", "update-openalex-stats.yml",
            "update-patent-metadata.yml", "update-publication-authorships.yml",
            "update-scholar.yml", "update-unpaywall.yml",
        }
        participants = set()
        for path in WORKFLOWS.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            if "group: website-content-write" not in text:
                continue
            participants.add(path.name)
            with self.subTest(workflow=path.name):
                block = re.search(r"^concurrency:\s*\n((?:[ \t]+[^\n]*\n|\n)+)", text, re.M)
                self.assertIsNotNone(block, "Shared writer needs workflow-level concurrency")
                settings = block.group(1)
                self.assertRegex(settings, r"(?m)^  group: website-content-write\s*$")
                self.assertRegex(settings, r"(?m)^  queue: max\s*$")
                self.assertRegex(settings, r"(?m)^  cancel-in-progress: false\s*$")
        self.assertEqual(expected, participants)


if __name__ == "__main__":
    unittest.main()
