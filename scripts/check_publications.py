"""Find possible new publications using ORCID, then enrich with Crossref."""
from __future__ import annotations

import os
import urllib.parse
from typing import Any

from academic_monitor_common import (
    date_parts,
    first,
    normalize_doi,
    normalize_title,
    read_json,
    request_json,
    safe_error,
    source_result,
)

ORCID_ID = os.getenv("ORCID_ID", "0000-0003-4484-3117")

def crossref_record(doi: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(doi, safe="")
    payload = request_json(f"https://api.crossref.org/works/{encoded}")
    return payload.get("message", {})

def author_names(message: dict) -> list[str]:
    result = []
    for author in message.get("author", []) or []:
        family = str(author.get("family") or "").strip()
        given = str(author.get("given") or "").strip()
        name = ", ".join(x for x in (family, given) if x)
        if name:
            result.append(name)
    return result

def run() -> dict:
    current = read_json("publications.json", [])
    known_dois = {normalize_doi(row.get("doi")) for row in current if row.get("doi")}
    known_titles = {normalize_title(row.get("title")) for row in current if row.get("title")}

    orcid_url = f"https://pub.orcid.org/v3.0/{ORCID_ID}/works"
    sources = []
    candidates = []
    seen = set()

    try:
        payload = request_json(orcid_url, accept="application/vnd.orcid+json")
        groups = payload.get("group", []) or []
        for group in groups:
            summaries = group.get("work-summary", []) or []
            summary = summaries[0] if summaries else {}
            external_ids = summary.get("external-ids", {}).get("external-id", []) or []
            doi = ""
            for external in external_ids:
                if str(external.get("external-id-type", "")).lower() == "doi":
                    doi = normalize_doi(external.get("external-id-value"))
                    break

            orcid_title = (
                summary.get("title", {})
                .get("title", {})
                .get("value", "")
            )
            key = doi or normalize_title(orcid_title)
            if not key or key in seen:
                continue
            seen.add(key)

            if doi and doi in known_dois:
                continue
            if not doi and normalize_title(orcid_title) in known_titles:
                continue

            item = {
                "type": "publication",
                "confidence": "high" if doi else "possible",
                "detectionNotes": [
                    "ORCID work is not present in the current publications JSON.",
                    "Please verify authorship and publication status before adding.",
                ],
                "sources": [
                    {"name": "ORCID", "url": f"https://orcid.org/{ORCID_ID}"}
                ],
                "doi": doi,
                "title": orcid_title,
                "journal": first(summary.get("journal-title", {}).get("value")),
                "publicationDate": "",
                "authors": [],
                "publisher": "",
                "volume": "",
                "issue": "",
                "pages": "",
                "abstract": "",
                "keywords": [],
            }

            if doi:
                item["sources"].append({"name": "DOI", "url": f"https://doi.org/{doi}"})
                item["sources"].append({
                    "name": "Crossref",
                    "url": f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}",
                })
                try:
                    message = crossref_record(doi)
                    item.update({
                        "title": first(message.get("title")) or orcid_title,
                        "journal": first(message.get("container-title")),
                        "publicationDate": date_parts(message),
                        "authors": author_names(message),
                        "publisher": str(message.get("publisher") or ""),
                        "volume": str(message.get("volume") or ""),
                        "issue": str(message.get("issue") or ""),
                        "pages": str(message.get("page") or message.get("article-number") or ""),
                        "abstract": str(message.get("abstract") or ""),
                    })
                    item["sources"].append({
                        "name": "OpenAlex search",
                        "url": "https://openalex.org/works?"
                               + urllib.parse.urlencode({"filter": f"doi:https://doi.org/{doi}"}),
                    })
                except Exception as error:
                    item["detectionNotes"].append(
                        f"Crossref enrichment failed: {safe_error(error)}"
                    )
            candidates.append(item)

        sources.append(source_result("ORCID", orcid_url, "success", count=len(candidates)))
    except Exception as error:
        sources.append(source_result("ORCID", orcid_url, "error", safe_error(error)))

    return {"items": candidates, "sources": sources}
