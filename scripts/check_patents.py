"""Find possible new patents from Google Patents search results.

Google Patents has no guaranteed public search API. The parser is intentionally
conservative: any layout/access failure is reported as a source error instead
of incorrectly claiming that no new patents exist.
"""
from __future__ import annotations

import html
import re
import urllib.parse

from academic_monitor_common import (
    normalize_identifier,
    read_json,
    request_text,
    safe_error,
    source_result,
)

SEARCH_TERMS = ['inventor="Wei-Hao Chiu"', 'inventor="邱偉豪"']

def strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()

def run() -> dict:
    current = read_json("patents.json", [])
    known = {normalize_identifier(row.get("number")) for row in current if row.get("number")}
    items = []
    sources = []
    seen = set()

    for term in SEARCH_TERMS:
        url = "https://patents.google.com/xhr/query?" + urllib.parse.urlencode({
            "url": "q=" + urllib.parse.quote(term),
            "exp": "",
        })
        display_url = "https://patents.google.com/?" + urllib.parse.urlencode({"q": term})
        try:
            text = request_text(url)
            # The endpoint commonly returns JSON-like HTML snippets. Match
            # patent publication numbers and titles without depending on one
            # exact page layout.
            records = re.findall(
                r'"publication_number"\s*:\s*"([^"]+)".{0,2500}?"title"\s*:\s*"([^"]+)"',
                text,
                flags=re.S,
            )
            for number, title in records:
                normalized = normalize_identifier(number)
                if not normalized or normalized in known or normalized in seen:
                    continue
                seen.add(normalized)
                patent_url = f"https://patents.google.com/patent/{number}/en"
                items.append({
                    "type": "patent",
                    "confidence": "possible",
                    "number": number,
                    "titleEn": strip_tags(title),
                    "titleZh": "",
                    "inventorsEn": ["Wei-Hao Chiu"],
                    "inventorsZh": "",
                    "assigneeEn": "",
                    "assigneeZh": "",
                    "jurisdiction": "",
                    "filingDate": "",
                    "publicationDate": "",
                    "grantDate": "",
                    "status": "",
                    "abstract": "",
                    "detectionNotes": [
                        "Patent publication number is not present in the current patents JSON.",
                        "Google Patents name matching can include people with similar names; verify inventor, assignee and technical field.",
                    ],
                    "sources": [
                        {"name": "Google Patents result", "url": patent_url},
                        {"name": "Google Patents search", "url": display_url},
                        {"name": "TIPO search", "url": "https://twpat1.tipo.gov.tw/twpatc/twpatkm"},
                        {"name": "Espacenet", "url": "https://worldwide.espacenet.com/"},
                        {"name": "WIPO PATENTSCOPE", "url": "https://patentscope.wipo.int/search/en/search.jsf"},
                    ],
                })
            sources.append(source_result("Google Patents", display_url, "success", count=len(records)))
        except Exception as error:
            sources.append(source_result("Google Patents", display_url, "error", safe_error(error)))

    return {"items": items, "sources": sources}
