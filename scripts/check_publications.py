"""Find possible new publications using ORCID, then enrich with Crossref."""
from __future__ import annotations

import os
import re
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

CONFERENCE_TYPES = {
    "conference-paper",
    "conference-poster",
    "conference-abstract",
    "conference-output",
    "proceedings-article",
    "proceedings",
}
OTHER_TYPES = {
    "book-chapter",
    "book",
    "edited-book",
    "dissertation",
    "preprint",
    "posted-content",
    "working-paper",
    "editorial",
}

def contains_cjk(value: Any) -> bool:
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", str(value or "")))

def classify_publication(
    *,
    title: str,
    journal: str,
    crossref_type: str = "",
    orcid_type: str = "",
    language: str = "",
) -> dict[str, str]:
    """Return an explainable suggested publication type for manual review."""
    source_type = str(crossref_type or orcid_type or "").strip().lower()
    language_value = str(language or "").strip().lower()
    has_chinese = contains_cjk(title) or contains_cjk(journal) or language_value.startswith("zh")

    if source_type in CONFERENCE_TYPES or "proceeding" in source_type or "conference" in source_type:
        suggested = "conference"
        confidence = "high"
        reason = f"Source document type: {source_type}."
    elif source_type in {"journal-article", "journal article"}:
        suggested = "chinese-journal" if has_chinese else "international-journal"
        confidence = "high" if crossref_type else "medium"
        reason = (
            "Journal article with Chinese title, source, or language metadata."
            if has_chinese
            else "Journal article with non-Chinese title and source metadata."
        )
    elif source_type in OTHER_TYPES:
        suggested = "other"
        confidence = "high"
        reason = f"Source document type: {source_type}."
    elif has_chinese and journal:
        suggested = "chinese-journal"
        confidence = "medium"
        reason = "Chinese title or source and a journal title are present; source type is incomplete."
    else:
        suggested = "unclassified"
        confidence = "low"
        reason = "Source metadata is insufficient or ambiguous; manual classification is required."

    return {
        "sourceDocumentType": source_type,
        "language": language_value or ("zh-TW" if has_chinese else ""),
        "suggestedPublicationType": suggested,
        "publicationTypeConfidence": confidence,
        "publicationTypeReason": reason,
    }

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
            group = group or {}
            summaries = group.get("work-summary", []) or []
            summary = summaries[0] if summaries else {}
            summary = summary or {}
            external_ids = (summary.get("external-ids") or {}).get("external-id", []) or []
            doi = ""
            for external in external_ids:
                external = external or {}
                if str(external.get("external-id-type", "")).lower() == "doi":
                    doi = normalize_doi(external.get("external-id-value"))
                    break

            title_node = summary.get("title") or {}
            nested_title = title_node.get("title") or {}
            orcid_title = nested_title.get("value") or ""
            journal_node = summary.get("journal-title") or {}
            orcid_type = str(summary.get("type") or "").strip().lower()
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
                "journal": first(journal_node.get("value")),
                "publicationDate": "",
                "authors": [],
                "publisher": "",
                "volume": "",
                "issue": "",
                "pages": "",
                "abstract": "",
                "keywords": [],
                "sourceDocumentType": orcid_type,
                "language": "zh-TW" if contains_cjk(orcid_title) or contains_cjk(journal_node.get("value")) else "",
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
                        "sourceDocumentType": str(message.get("type") or orcid_type),
                        "language": str(message.get("language") or item.get("language") or ""),
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
            item.update(classify_publication(
                title=str(item.get("title") or ""),
                journal=str(item.get("journal") or ""),
                crossref_type=str(item.get("sourceDocumentType") or "") if doi else "",
                orcid_type=orcid_type,
                language=str(item.get("language") or ""),
            ))
            candidates.append(item)

        sources.append(source_result("ORCID", orcid_url, "success", count=len(candidates)))
    except Exception as error:
        sources.append(source_result("ORCID", orcid_url, "error", safe_error(error)))

    return {"items": candidates, "sources": sources}
