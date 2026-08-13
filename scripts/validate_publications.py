#!/usr/bin/env python3
"""Validate publication identity, type, and analytics-scope invariants."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLICATIONS_PATH = ROOT / "data" / "publications.json"
TAXONOMY_PATH = ROOT / "data" / "publication_taxonomy.json"


def main() -> None:
    publications = json.loads(PUBLICATIONS_PATH.read_text(encoding="utf-8"))
    taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    type_rows = taxonomy.get("publicationTypes") or []
    allowed_types = {row.get("value") for row in type_rows if isinstance(row, dict)}
    allowed_document_types = set(taxonomy.get("documentTypes") or [])
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_dois: set[str] = set()
    collaboration_statuses = {"international", "domestic", "foreign-only", "needs-review"}

    if not isinstance(publications, list):
        raise SystemExit("data/publications.json must contain a JSON array.")
    if not allowed_types:
        raise SystemExit("publication taxonomy does not define publicationTypes.")

    for index, publication in enumerate(publications, start=1):
        label = publication.get("title") or f"record {index}"
        output_id = str(publication.get("id") or "").strip().lower()
        publication_type = publication.get("publicationType")
        document_type = publication.get("documentType")
        analytics = publication.get("analytics")
        collaboration = publication.get("internationalCollaboration")
        excluded_from_research = isinstance(analytics, dict) and analytics.get(
            "excludeFromResearchAnalytics"
        ) is True

        if not output_id:
            errors.append(f"{label}: missing stable id")
        elif output_id in seen_ids:
            errors.append(f"{label}: duplicate id {output_id}")
        seen_ids.add(output_id)

        doi = str(publication.get("doi") or "").strip().lower()
        if doi:
            if doi in seen_dois:
                errors.append(f"{label}: duplicate DOI {doi}")
            seen_dois.add(doi)

        if publication_type not in allowed_types:
            errors.append(f"{label}: invalid publicationType {publication_type!r}")
        if document_type not in allowed_document_types:
            errors.append(f"{label}: invalid documentType {document_type!r}")
        if not isinstance(analytics, dict):
            errors.append(f"{label}: analytics must be an object")
            continue
        for field in ("coreJournalCount", "journalMetrics", "fwci", "citationMetrics"):
            if not isinstance(analytics.get(field), bool):
                errors.append(f"{label}: analytics.{field} must be boolean")

        if "excludeFromResearchAnalytics" in analytics and not isinstance(
            analytics.get("excludeFromResearchAnalytics"), bool
        ):
            errors.append(
                f"{label}: analytics.excludeFromResearchAnalytics must be boolean"
            )

        if publication_type == "international-journal":
            for field in ("coreJournalCount", "journalMetrics", "fwci"):
                if analytics.get(field) is not True:
                    errors.append(f"{label}: international journal requires analytics.{field}=true")
        else:
            for field in ("coreJournalCount", "journalMetrics", "fwci"):
                if analytics.get(field) is not False:
                    errors.append(f"{label}: non-core output requires analytics.{field}=false")

        if publication_type == "thesis":
            if not excluded_from_research:
                errors.append(f"{label}: thesis must be excluded from research analytics")
            for field in ("coreJournalCount", "journalMetrics", "fwci", "citationMetrics"):
                if analytics.get(field) is not False:
                    errors.append(f"{label}: thesis requires analytics.{field}=false")
            if str(publication.get("doi") or "").strip():
                errors.append(f"{label}: thesis must not contain an unverified DOI")
            if not str(publication.get("repositoryUrl") or "").strip():
                errors.append(f"{label}: thesis requires repositoryUrl")
            if publication.get("metadataSource") != "manual_verified":
                errors.append(f"{label}: thesis metadataSource must be manual_verified")
            if (publication.get("automationProtection") or {}).get("protected") is not True:
                errors.append(f"{label}: thesis must be protected from automatic enrichment")

        if not isinstance(collaboration, dict):
            errors.append(f"{label}: internationalCollaboration must be an object")
            continue
        status = collaboration.get("status")
        if status not in collaboration_statuses:
            errors.append(f"{label}: invalid internationalCollaboration.status {status!r}")
        if collaboration.get("isInternational") is not (status == "international"):
            errors.append(f"{label}: collaboration status and isInternational disagree")
        if collaboration.get("homeCountryCode") != "TW":
            errors.append(f"{label}: collaboration homeCountryCode must be TW")
        if status == "international" and not collaboration.get("partnerCountryCodes"):
            errors.append(f"{label}: international collaboration requires a partner country")
        if status != "international" and collaboration.get("partnerCountryCodes"):
            errors.append(f"{label}: non-international record cannot have partner countries")
        if collaboration.get("manualOverride") not in {True, False}:
            errors.append(f"{label}: collaboration manualOverride must be boolean")
        if collaboration.get("requiresManualReview") not in {True, False}:
            errors.append(f"{label}: collaboration requiresManualReview must be boolean")
        for field in ("countryCodes", "partnerCountryCodes", "partnerInstitutions", "sources", "warnings"):
            if not isinstance(collaboration.get(field), list):
                errors.append(f"{label}: collaboration {field} must be an array")

    if errors:
        raise SystemExit("\n".join(errors))

    counts = {
        value: sum(row.get("publicationType") == value for row in publications)
        for value in sorted(allowed_types)
    }
    core_count = sum(
        row.get("analytics", {}).get("coreJournalCount") is True
        for row in publications
    )
    research_count = sum(
        row.get("analytics", {}).get("excludeFromResearchAnalytics") is not True
        for row in publications
    )
    thesis_count = sum(row.get("publicationType") == "thesis" for row in publications)
    print(
        f"Validated {len(publications)} scholarly outputs; "
        f"{research_count} research publications; {core_count} core journal publications; "
        f"{thesis_count} theses; types={counts}."
    )


if __name__ == "__main__":
    main()
