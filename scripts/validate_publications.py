#!/usr/bin/env python3
"""Validate publication data and type-aware generated detail pages."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PUBLICATIONS_PATH = ROOT / "data" / "publications.json"
TAXONOMY_PATH = ROOT / "data" / "publication_taxonomy.json"
RESEARCH_PUBLICATION_TYPES = frozenset(
    {"international-journal", "chinese-journal", "conference"}
)
SUPPORTED_GENERATED_TYPES = RESEARCH_PUBLICATION_TYPES | {"thesis"}
AFFILIATION_FIELDS = (
    "department",
    "institution",
    "address",
    "raw",
    "city",
    "countryCode",
)


class GeneratedPageParser(HTMLParser):
    """Collect only the generated-page structure needed for validation."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.classes: set[str] = set()
        self.attribute_values: list[str] = []
        self.headings: list[str] = []
        self.facts: dict[str, str] = {}
        self.author_trigger_names: list[str] = []
        self.publication_authors_text: list[str] = []
        self.structured_data: list[str] = []
        self.visible_text: list[str] = []
        self._heading_tag = ""
        self._heading_parts: list[str] = []
        self._fact_tag = ""
        self._fact_parts: list[str] = []
        self._fact_label = ""
        self._structured_data_parts: list[str] | None = None
        self._publication_authors_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        class_names = attributes.get("class", "").split()
        if self._publication_authors_depth:
            self._publication_authors_depth += 1
        elif "publication-authors" in class_names:
            self._publication_authors_depth = 1
        self.classes.update(class_names)
        self.attribute_values.extend(attributes.values())
        if "author-trigger" in class_names:
            self.author_trigger_names.append(attributes.get("data-author-name", "").strip())
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._heading_tag = tag
            self._heading_parts = []
        if tag in {"dt", "dd"}:
            self._fact_tag = tag
            self._fact_parts = []
        if tag == "script" and attributes.get("type", "").lower() == "application/ld+json":
            self._structured_data_parts = []

    def handle_endtag(self, tag: str) -> None:
        if self._publication_authors_depth:
            self._publication_authors_depth -= 1
        if tag == self._heading_tag:
            heading = " ".join("".join(self._heading_parts).split())
            if heading:
                self.headings.append(heading)
            self._heading_tag = ""
            self._heading_parts = []
        if tag == self._fact_tag:
            value = " ".join("".join(self._fact_parts).split())
            if tag == "dt":
                self._fact_label = value
            elif tag == "dd" and self._fact_label:
                self.facts[self._fact_label] = value
                self._fact_label = ""
            self._fact_tag = ""
            self._fact_parts = []
        if tag == "script" and self._structured_data_parts is not None:
            self.structured_data.append("".join(self._structured_data_parts).strip())
            self._structured_data_parts = None

    def handle_data(self, data: str) -> None:
        if self._structured_data_parts is not None:
            self._structured_data_parts.append(data)
            return
        self.visible_text.append(data)
        if self._publication_authors_depth:
            self.publication_authors_text.append(data)
        if self._heading_tag:
            self._heading_parts.append(data)
        if self._fact_tag:
            self._fact_parts.append(data)


def slugify(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-") or "publication"


def publication_slug(publication: dict[str, Any]) -> str:
    return slugify(
        publication.get("id") or publication.get("doi") or publication.get("title")
    )


def publication_identifier(publication: dict[str, Any]) -> str:
    return str(
        publication.get("doi")
        or publication.get("id")
        or publication.get("title")
        or "publication"
    )


def publication_author_names(publication: dict[str, Any]) -> list[str]:
    authorships = publication.get("authorships") or []
    if isinstance(authorships, list) and authorships:
        return [
            str(row.get("name") or "").strip()
            for row in authorships
            if isinstance(row, dict) and str(row.get("name") or "").strip()
        ]
    authors = publication.get("authors") or []
    if not isinstance(authors, list):
        return []
    return [str(name or "").strip() for name in authors if str(name or "").strip()]


def has_affiliation_metadata(publication: dict[str, Any]) -> bool:
    affiliations = publication.get("affiliations") or []
    return any(
        isinstance(row, dict)
        and any(str(row.get(field) or "").strip() for field in AFFILIATION_FIELDS)
        for row in affiliations
    )


def has_authorship_role(publication: dict[str, Any], field: str) -> bool:
    return any(
        isinstance(row, dict) and row.get(field) is True
        for row in (publication.get("authorships") or [])
    )


def structured_data_types(parser: GeneratedPageParser) -> set[str]:
    types: set[str] = set()

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            schema_type = value.get("@type")
            if isinstance(schema_type, str):
                types.add(schema_type)
            elif isinstance(schema_type, list):
                types.update(str(item) for item in schema_type)
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    for raw in parser.structured_data:
        try:
            collect(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return types


def validate_static_authors(
    publication: dict[str, Any], parser: GeneratedPageParser, author_text: str
) -> list[str]:
    errors: list[str] = []
    expected_names = publication_author_names(publication)
    if not expected_names:
        errors.append("publication JSON has no author names")
    for name in expected_names:
        if name not in author_text:
            errors.append(f"missing static author name {name!r}")
    if "publication-author" not in parser.classes:
        errors.append("missing publication-author markup")
    if "author-trigger" not in parser.classes or not any(
        name in expected_names for name in parser.author_trigger_names
    ):
        errors.append("missing author-trigger markup")
    return errors


def validate_research_publication_page(
    publication: dict[str, Any], parser: GeneratedPageParser
) -> list[str]:
    errors: list[str] = []
    page_text = " ".join(parser.visible_text)
    if "publication-authors" not in parser.classes:
        errors.append("missing static author row (publication-authors)")
    errors.extend(
        validate_static_authors(
            publication, parser, " ".join(parser.publication_authors_text)
        )
    )

    has_equal = has_authorship_role(publication, "isEqualContributor")
    has_corresponding = has_authorship_role(publication, "isCorresponding")
    if (has_affiliation_metadata(publication) or has_equal or has_corresponding) and (
        "publication-affiliations" not in parser.classes
    ):
        errors.append("missing static affiliation or author-role block (publication-affiliations)")

    attribute_text = " ".join(parser.attribute_values)
    if has_equal and not (
        "Equal contribution" in attribute_text
        or "These authors contributed equally." in page_text
    ):
        errors.append("missing equal-contributor marker or legend")
    if has_corresponding and not (
        "Corresponding author" in attribute_text or "Corresponding author" in page_text
    ):
        errors.append("missing corresponding-author marker or legend")
    return errors


def validate_thesis_page(
    publication: dict[str, Any], parser: GeneratedPageParser
) -> list[str]:
    errors: list[str] = []
    if "thesis-detail" not in parser.classes:
        errors.append("missing thesis-detail structure")
    if "Basic Information" not in parser.headings:
        errors.append("missing Basic Information section")

    author_text = parser.facts.get("Author", "").strip()
    if not author_text:
        errors.append("missing Author in Basic Information")
    else:
        errors.extend(validate_static_authors(publication, parser, author_text))

    for field, source_field in (
        ("Degree", "degree"),
        ("Year", "year"),
        ("Institution", "institution"),
    ):
        fact_value = parser.facts.get(field, "").strip()
        if not fact_value:
            errors.append(f"missing {field} in Basic Information")
            continue
        expected_value = str(publication.get(source_field) or "").strip()
        if expected_value and expected_value not in fact_value:
            errors.append(f"Basic Information {field} does not match publication JSON")
    expected_advisor = str(publication.get("advisor") or "").strip()
    if expected_advisor:
        advisor_value = parser.facts.get("Advisor", "").strip()
        if not advisor_value:
            errors.append("missing Advisor in Basic Information")
        elif expected_advisor not in advisor_value:
            errors.append("Basic Information Advisor does not match publication JSON")
    if "CreativeWork" not in structured_data_types(parser):
        errors.append("missing CreativeWork structured data")
    return errors


def validate_generated_publication(
    publication: dict[str, Any], html_text: str
) -> list[str]:
    publication_type = str(publication.get("publicationType") or "").strip()
    if publication_type not in SUPPORTED_GENERATED_TYPES:
        return [f"Unsupported scholarly output type: {publication_type or '<missing>'}"]

    parser = GeneratedPageParser()
    parser.feed(html_text)
    parser.close()
    if publication_type == "thesis":
        return validate_thesis_page(publication, parser)
    return validate_research_publication_page(publication, parser)


def validate_generated_pages(
    publications: list[dict[str, Any]], root: Path = ROOT
) -> list[str]:
    errors: list[str] = []
    detail_pages = list((root / "publications").glob("*.html"))
    if len(detail_pages) != len(publications):
        errors.append(
            f"detail page count: expected {len(publications)}, found {len(detail_pages)}"
        )

    for publication in publications:
        identifier = publication_identifier(publication)
        publication_type = str(publication.get("publicationType") or "").strip()
        if publication_type not in SUPPORTED_GENERATED_TYPES:
            errors.append(
                f"{identifier}: Unsupported scholarly output type: "
                f"{publication_type or '<missing>'}"
            )
            continue
        page = root / "publications" / f"{publication_slug(publication)}.html"
        if not page.exists():
            errors.append(
                f"{identifier}: missing generated detail page ({page.as_posix()})"
            )
            continue
        page_errors = validate_generated_publication(
            publication, page.read_text(encoding="utf-8")
        )
        errors.extend(f"{identifier}: {error}" for error in page_errors)

    insights_path = root / "publication-insights-4d8c7a.html"
    if not insights_path.exists():
        errors.append("Publication Analytics page is missing")
    else:
        insights = insights_path.read_text(encoding="utf-8")
        if "PUBLICATION_AUTHORSHIP_INSIGHTS_START" not in insights:
            errors.append("Publication Analytics authorship extension is not embedded")
        if "assets/js/international-collaboration-insights.js" not in insights:
            errors.append(
                "Publication Analytics international-collaboration extension is not embedded"
            )
    return errors


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
    generated_errors = validate_generated_pages(publications)
    if generated_errors:
        raise SystemExit("\n".join(generated_errors))
    print(
        f"Validated {len(publications)} generated scholarly-output pages; "
        f"{research_count} research publications; {thesis_count} theses."
    )


if __name__ == "__main__":
    main()
