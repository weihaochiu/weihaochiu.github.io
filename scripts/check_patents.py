"""Find possible new patents using exact-record verification.

Google Patents has no guaranteed public search API. Search responses are only
used to discover publication numbers. Titles, inventors, assignees, and dates
are then read from each exact patent page so fields from adjacent search
results cannot be paired accidentally.
"""
from __future__ import annotations

import urllib.parse

from academic_monitor_common import read_json, request_text, safe_error, source_result
from patent_common import (
    build_alias_index,
    canonicalize_identifier,
    normalize_identifier,
    parse_google_patent_page,
    search_records_from_payload,
)


SEARCH_TERMS = ['inventor="Wei-Hao Chiu"', 'inventor="邱偉豪"']
TARGET_INVENTOR_KEYS = {"weihaochiu", "邱偉豪"}


def normalize_name(value: object) -> str:
    return "".join(char.lower() for char in str(value or "") if char.isalnum())


def jurisdiction(number: str) -> str:
    if number.startswith("TW"):
        return "Taiwan"
    if number.startswith("US"):
        return "United States"
    if number.startswith("CN"):
        return "China"
    if number.startswith("EP"):
        return "European Patent Office"
    if number.startswith("JP"):
        return "Japan"
    return ""


def candidate_from_exact_page(number: str, search_url: str) -> dict | None:
    patent_url = f"https://patents.google.com/patent/{number}/en"
    page = request_text(patent_url)
    parsed = parse_google_patent_page(page, number)
    parsed_number = normalize_identifier(parsed.get("canonicalId"))
    if parsed_number != normalize_identifier(number):
        raise ValueError(f"Exact page returned {parsed_number or '<blank>'} for {number}")
    inventor_names = [str(name) for name in parsed.get("inventors") or []]
    if not TARGET_INVENTOR_KEYS.intersection(normalize_name(name) for name in inventor_names):
        return None
    title = str(parsed.get("titleEn") or "").strip()
    if not title:
        raise ValueError(f"Exact page for {number} has no title")
    stage = "Granted" if parsed.get("grantDate") else "Published application"
    return {
        "type": "patent",
        "confidence": "possible",
        "canonicalId": parsed_number,
        "number": parsed_number,
        "titleEn": title,
        "titleZh": "",
        "inventorsEn": inventor_names,
        "inventorsZh": "",
        "assigneeEn": "; ".join(parsed.get("assignees") or []),
        "assigneeZh": "",
        "jurisdiction": jurisdiction(parsed_number),
        "applicationNumber": parsed.get("applicationNumber", ""),
        "priorityDate": parsed.get("priorityDate", ""),
        "filingDate": parsed.get("filingDate", ""),
        "publicationDate": parsed.get("publicationDate", ""),
        "grantDate": parsed.get("grantDate", ""),
        "documentStage": stage,
        "legalStatus": parsed.get("legalStatus", ""),
        "status": stage,
        "abstract": parsed.get("abstract", ""),
        "classifications": parsed.get("classifications", []),
        "detectionNotes": [
            "The publication number is not an alias of a verified record in patents.json.",
            "The exact patent page lists Wei-Hao Chiu or 邱偉豪 as an inventor.",
            "Name matching can still include a different person with the same name; verify assignee and technical field.",
        ],
        "sources": [
            {"name": "Google Patents exact record", "url": patent_url},
            {"name": "Google Patents search", "url": search_url},
            {"name": "TIPO search", "url": "https://twpat1.tipo.gov.tw/twpatc/twpatkm"},
            {"name": "Espacenet", "url": "https://worldwide.espacenet.com/"},
            {"name": "WIPO PATENTSCOPE", "url": "https://patentscope.wipo.int/search/en/search.jsf"},
        ],
    }


def run() -> dict:
    current = read_json("patents.json", [])
    alias_index = build_alias_index(current)
    known = set(alias_index.values())
    items = []
    sources = []
    seen: set[str] = set()

    for term in SEARCH_TERMS:
        url = "https://patents.google.com/xhr/query?" + urllib.parse.urlencode({
            "url": "q=" + urllib.parse.quote(term),
            "exp": "",
        })
        display_url = "https://patents.google.com/?" + urllib.parse.urlencode({"q": term})
        try:
            search_text = request_text(url)
            records = search_records_from_payload(search_text)
            sources.append(source_result("Google Patents", display_url, "success", count=len(records)))
        except Exception as error:
            sources.append(source_result("Google Patents", display_url, "error", safe_error(error)))
            continue

        for record in records:
            raw_number = record.get("number", "")
            normalized = normalize_identifier(raw_number)
            canonical = canonicalize_identifier(normalized, alias_index)
            if not normalized or canonical in known or normalized in seen:
                continue
            seen.add(normalized)
            patent_url = f"https://patents.google.com/patent/{normalized}/en"
            try:
                candidate = candidate_from_exact_page(normalized, display_url)
                if candidate:
                    items.append(candidate)
            except Exception as error:
                sources.append(
                    source_result(
                        f"Google Patents exact record {normalized}",
                        patent_url,
                        "warning",
                        safe_error(error),
                    )
                )

    items.sort(
        key=lambda item: (
            str(item.get("publicationDate") or item.get("grantDate") or ""),
            str(item.get("canonicalId") or ""),
        ),
        reverse=True,
    )
    return {"items": items, "sources": sources}
