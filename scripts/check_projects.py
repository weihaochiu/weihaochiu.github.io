"""Check GRB project records conservatively.

GRB pages can change and may return unrelated content. This module only accepts
records that expose a planDetail id and a project-number-like value. Any
unexpected response becomes a visible source error.
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

NAMES = ["邱偉豪", "Wei-Hao Chiu"]

def clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()

def run() -> dict:
    current = read_json("projects.json", [])
    known_numbers = {
        normalize_identifier(row.get("number"))
        for row in current
        if row.get("number")
    }
    known_ids = {str(row.get("grbId")) for row in current if row.get("grbId")}

    items = []
    sources = []
    seen = set()

    for name in NAMES:
        # GRB currently exposes search pages rather than a documented public API.
        search_url = "https://www.grb.gov.tw/search"
        display_url = search_url + "?" + urllib.parse.urlencode({"query": name})
        try:
            text = request_text(display_url)
            detail_ids = set(re.findall(r"planDetail\?id=(\d+)", text))
            # Common NSTC/MOST/NSC project-number forms.
            number_matches = set(re.findall(
                r"\b(?:NSTC|MOST|NSC)\s*[-–]?\s*\d{2,3}\s*[-–]\s*\d{3,4}\s*[-–]\s*[A-Z]\s*[-–]?\s*\d{2,4}(?:\s*[-–]\s*[A-Z0-9]+)*\b",
                clean(text),
                flags=re.I,
            ))

            # Do not manufacture a relationship between ids and numbers when
            # the page structure does not expose one clearly.
            if detail_ids and number_matches:
                for grb_id in sorted(detail_ids):
                    if grb_id in known_ids or grb_id in seen:
                        continue
                    seen.add(grb_id)
                    number = next(iter(sorted(number_matches)), "")
                    if number and normalize_identifier(number) in known_numbers:
                        continue
                    detail_url = f"https://www.grb.gov.tw/search/planDetail?id={grb_id}"
                    items.append({
                        "type": "project",
                        "confidence": "possible",
                        "grbId": grb_id,
                        "number": number,
                        "titleZh": "",
                        "titleEn": "",
                        "roleZh": "",
                        "role": "",
                        "agencyZh": "",
                        "agencyEn": "",
                        "institutionZh": "",
                        "period": "",
                        "startDate": "",
                        "endDate": "",
                        "fundingAmountTwd": None,
                        "abstractZh": "",
                        "detectionNotes": [
                            "GRB plan id is not present in the current projects JSON.",
                            "The public GRB search page did not expose enough structured metadata; verify the detail page before adding.",
                        ],
                        "sources": [
                            {"name": "GRB project detail", "url": detail_url},
                            {"name": "GRB search", "url": display_url},
                        ],
                    })
            sources.append(source_result(
                "GRB",
                display_url,
                "success" if detail_ids else "warning",
                "" if detail_ids else "No structured planDetail links were detected; the GRB page layout or access policy may have changed.",
                count=len(detail_ids),
            ))
        except Exception as error:
            sources.append(source_result("GRB", display_url, "error", safe_error(error)))

    return {"items": items, "sources": sources}
