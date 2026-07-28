"""Shared patent identity, parsing, and safe-merge helpers."""
from __future__ import annotations

import html
import json
import re
from typing import Any, Iterable


def normalize_identifier(value: Any) -> str:
    """Return a punctuation-free uppercase patent identifier."""
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def patent_aliases(record: dict[str, Any]) -> set[str]:
    values = [
        record.get("canonicalId"),
        record.get("number"),
        *(record.get("aliases") or []),
    ]
    return {normalize_identifier(value) for value in values if normalize_identifier(value)}


def build_alias_index(records: Iterable[dict[str, Any]]) -> dict[str, str]:
    """Map every known spelling to one canonical identifier.

    Ambiguous aliases are rejected because silently choosing a record could
    publish metadata under the wrong patent.
    """
    index: dict[str, str] = {}
    for record in records:
        canonical = normalize_identifier(record.get("canonicalId") or record.get("number"))
        if not canonical:
            raise ValueError("Patent record has no canonical identifier")
        for alias in patent_aliases(record) | {canonical}:
            previous = index.get(alias)
            if previous and previous != canonical:
                raise ValueError(f"Patent alias {alias!r} maps to both {previous!r} and {canonical!r}")
            index[alias] = canonical
    return index


def canonicalize_identifier(value: Any, alias_index: dict[str, str] | None = None) -> str:
    normalized = normalize_identifier(value)
    return (alias_index or {}).get(normalized, normalized)


def strip_markup(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _meta_values(text: str, name: str) -> list[str]:
    patterns = [
        rf'<meta\b[^>]*\bname=["\']{re.escape(name)}["\'][^>]*\bcontent=["\']([^"\']*)["\'][^>]*>',
        rf'<meta\b[^>]*\bcontent=["\']([^"\']*)["\'][^>]*\bname=["\']{re.escape(name)}["\'][^>]*>',
    ]
    values: list[str] = []
    for pattern in patterns:
        values.extend(strip_markup(value) for value in re.findall(pattern, text, flags=re.I | re.S))
    return [value for value in values if value]


def _itemprop(text: str, name: str) -> str:
    match = re.search(
        rf'<(?:dd|span|time|div)\b[^>]*\bitemprop=["\']{re.escape(name)}["\'][^>]*>(.*?)</(?:dd|span|time|div)>',
        text,
        flags=re.I | re.S,
    )
    return strip_markup(match.group(1)) if match else ""


def _date_meta(text: str, scheme: str) -> str:
    patterns = [
        rf'<meta\b[^>]*\bscheme=["\']{re.escape(scheme)}["\'][^>]*\bcontent=["\']([^"\']+)["\'][^>]*>',
        rf'<meta\b[^>]*\bcontent=["\']([^"\']+)["\'][^>]*\bscheme=["\']{re.escape(scheme)}["\'][^>]*>',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)
        if match:
            return strip_markup(match.group(1))[:10]
    return ""


def parse_google_patent_page(text: str, fallback_number: str = "") -> dict[str, Any]:
    """Parse one exact Google Patents record page.

    Parsing is deliberately scoped to a single patent page. It never pairs a
    publication number with a title found elsewhere in a multi-result payload.
    """
    publication_number = (
        _itemprop(text, "publicationNumber")
        or next(iter(_meta_values(text, "DC.relation")), "")
        or fallback_number
    )
    publication_number = normalize_identifier(publication_number)
    title = next(iter(_meta_values(text, "DC.title")), "")
    if " - Google Patents" in title:
        title = title.split(" - Google Patents", 1)[0]
    inventors = _meta_values(text, "DC.contributor")
    assignees = _meta_values(text, "DC.rights")
    description = next(iter(_meta_values(text, "DC.description")), "")
    if not description:
        abstract_match = re.search(
            r'<div\b[^>]*\bclass=["\'][^"\']*\babstract\b[^"\']*["\'][^>]*>(.*?)</div>',
            text,
            flags=re.I | re.S,
        )
        description = strip_markup(abstract_match.group(1)) if abstract_match else ""
    classifications = []
    for code in re.findall(
        r'<span\b[^>]*\bitemprop=["\']Code["\'][^>]*>(.*?)</span>',
        text,
        flags=re.I | re.S,
    ):
        normalized = strip_markup(code)
        if normalized and normalized not in classifications:
            classifications.append(normalized)
    legal_status = _itemprop(text, "status")
    application_number = _itemprop(text, "applicationNumber")
    filing_date = _date_meta(text, "dateSubmitted")
    publication_date = _date_meta(text, "datePublished")
    priority_date = _date_meta(text, "priorityDate")
    grant_date = ""
    grant_match = re.search(
        r'(\d{4}-\d{2}-\d{2})\s+Application granted',
        strip_markup(text),
        flags=re.I,
    )
    if grant_match:
        grant_date = grant_match.group(1)
    jurisdiction = ""
    authority = _itemprop(text, "countryCode")
    if authority:
        jurisdiction = authority
    return {
        "canonicalId": publication_number,
        "applicationNumber": normalize_identifier(application_number),
        "titleEn": title,
        "inventors": inventors,
        "assignees": assignees,
        "priorityDate": priority_date,
        "filingDate": filing_date,
        "publicationDate": publication_date,
        "grantDate": grant_date,
        "legalStatus": legal_status,
        "jurisdictionCode": jurisdiction,
        "classifications": classifications,
        "abstract": description,
    }


def search_records_from_payload(text: str) -> list[dict[str, str]]:
    """Extract paired number/title records from a structured search response."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Google Patents search response was not valid JSON") from exc

    records: list[dict[str, str]] = []
    seen: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            number = value.get("publication_number") or value.get("publicationNumber")
            title = value.get("title")
            normalized = normalize_identifier(number)
            if normalized and title and normalized not in seen:
                seen.add(normalized)
                records.append({"number": normalized, "title": strip_markup(title)})
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return records


def merge_automatic_metadata(base: dict[str, Any], automatic: dict[str, Any]) -> dict[str, Any]:
    """Merge non-empty automatic fields without replacing manual identity text."""
    protected = {
        "titleEn",
        "titleZh",
        "inventors",
        "inventorsEn",
        "inventorsZh",
        "assigneeEn",
        "assigneeZh",
        "number",
        "canonicalId",
        "aliases",
        "familyId",
    }
    merged = dict(base)
    for key, value in automatic.items():
        if key in protected or value in ("", None, [], {}):
            continue
        merged[key] = value
    return merged
