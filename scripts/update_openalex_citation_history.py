from __future__ import annotations

import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


OPENALEX_METRICS_PATH = Path("data/openalex_publication_metrics.json")
PUBLICATIONS_PATH = Path("data/publications.json")
OUTPUT_PATH = Path("data/openalex_citation_history.json")
API_URL = "https://api.openalex.org/works"
SELECT_FIELDS = (
    "id,doi,display_name,publication_year,publication_date,"
    "authorships,primary_location,biblio,type"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_openalex_id(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("https://openalex.org/"):
        text = text.rstrip("/").rsplit("/", 1)[-1]
    return text if text.startswith("W") and text[1:].isdigit() else ""


def normalize_doi(value: Any) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .removeprefix("https://doi.org/")
        .removeprefix("http://doi.org/")
        .removeprefix("http://dx.doi.org/")
        .removeprefix("https://dx.doi.org/")
        .removeprefix("doi:")
        .strip()
    )


def as_nonnegative_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_openalex_metrics() -> dict[str, Any]:
    payload = load_json(OPENALEX_METRICS_PATH)
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), dict):
        raise RuntimeError(f"Invalid records object in {OPENALEX_METRICS_PATH}.")
    return payload


def load_publication_years() -> dict[str, int]:
    rows = load_json(PUBLICATIONS_PATH)
    if not isinstance(rows, list):
        raise RuntimeError(f"Expected a JSON array in {PUBLICATIONS_PATH}.")

    years: dict[str, int] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        doi = normalize_doi(row.get("doi") or row.get("doiUrl"))
        year = as_nonnegative_int(row.get("year"))

        if doi and year and year >= 1900:
            years[doi] = year

    if not years:
        raise RuntimeError(
            f"No DOI/publication-year mappings were found in {PUBLICATIONS_PATH}."
        )

    return years


def build_session() -> requests.Session:
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )

    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "User-Agent": (
                "Wei-Hao-Chiu-Academic-Website/1.0 "
                "(annual citation analytics; contact: weihao.chiu@gmail.com)"
            )
        }
    )
    return session


def openalex_params(api_key: str) -> dict[str, str]:
    params: dict[str, str] = {}
    if api_key:
        params["api_key"] = api_key
    mailto = (
        os.environ.get("OPENALEX_MAILTO", "").strip()
        or "weihao.chiu@gmail.com"
    )
    if mailto:
        params["mailto"] = mailto
    return params


def fetch_citing_works(
    session: requests.Session,
    api_key: str,
    work_id: str,
) -> tuple[int, list[dict[str, Any]]]:
    """Return every OpenAlex work that cites ``work_id`` using cursor pagination."""
    cursor = "*"
    expected_count = 0
    results: list[dict[str, Any]] = []

    while cursor:
        params = {
            "filter": f"cites:{work_id}",
            "select": SELECT_FIELDS,
            "sort": "publication_date:desc",
            "per-page": "200",
            "cursor": cursor,
            **openalex_params(api_key),
        }
        response = session.get(API_URL, params=params, timeout=90)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        expected_count = as_nonnegative_int(meta.get("count")) or expected_count
        page = payload.get("results")
        if not isinstance(page, list):
            raise RuntimeError(f"OpenAlex returned an invalid results page for {work_id}.")
        results.extend(item for item in page if isinstance(item, dict))
        cursor = str(meta.get("next_cursor") or "")

    return expected_count, results


def citing_work_years(works: list[dict[str, Any]]) -> dict[int, int]:
    history: Counter[int] = Counter()
    for work in works:
        year = as_nonnegative_int(work.get("publication_year"))
        if year is not None and year >= 1900:
            history[year] += 1
    return dict(history)


def citing_work_is_valid(work: dict[str, Any], publication_year: int | None) -> bool:
    year = as_nonnegative_int(work.get("publication_year"))
    return publication_year is None or year is None or year >= publication_year


def citing_article_record(work: dict[str, Any]) -> dict[str, Any] | None:
    doi = normalize_doi(work.get("doi"))
    if not doi:
        return None

    authors = []
    for authorship in work.get("authorships") or []:
        if not isinstance(authorship, dict):
            continue
        author = authorship.get("author")
        name = str(author.get("display_name") or "").strip() if isinstance(author, dict) else ""
        if name and name not in authors:
            authors.append(name)

    location = work.get("primary_location")
    source = location.get("source") if isinstance(location, dict) else None
    journal = str(source.get("display_name") or "").strip() if isinstance(source, dict) else ""
    biblio = work.get("biblio") if isinstance(work.get("biblio"), dict) else {}
    first_page = str(biblio.get("first_page") or "").strip()
    last_page = str(biblio.get("last_page") or "").strip()
    pages = first_page
    if last_page and last_page != first_page:
        pages = f"{first_page}-{last_page}" if first_page else last_page

    return {
        "openAlexId": normalize_openalex_id(work.get("id")),
        "doi": doi,
        "doiUrl": f"https://doi.org/{doi}",
        "title": str(work.get("display_name") or "").strip(),
        "authors": authors,
        "journal": journal,
        "publicationYear": as_nonnegative_int(work.get("publication_year")),
        "publicationDate": str(work.get("publication_date") or "").strip(),
        "volume": str(biblio.get("volume") or "").strip(),
        "issue": str(biblio.get("issue") or "").strip(),
        "pages": pages,
        "type": str(work.get("type") or "").strip(),
    }


def citing_articles_with_doi(
    works: list[dict[str, Any]],
    publication_year: int | None,
) -> list[dict[str, Any]]:
    """Return one normalized, newest-first record per DOI."""
    records: dict[str, dict[str, Any]] = {}
    for work in works:
        if not citing_work_is_valid(work, publication_year):
            continue
        record = citing_article_record(work)
        if record and record["doi"] not in records:
            records[record["doi"]] = record
    alphabetized = sorted(
        records.values(),
        key=lambda row: str(row.get("title") or "").lower(),
    )
    return sorted(
        alphabetized,
        key=lambda row: (
            row.get("publicationYear") or 0,
            str(row.get("publicationDate") or ""),
        ),
        reverse=True,
    )


def split_valid_and_invalid_history(
    history: dict[int, int],
    publication_year: int | None,
) -> tuple[dict[int, int], list[dict[str, int | str]]]:
    """
    Exclude impossible citation years.

    A citing work cannot cite a paper before that paper's publication year.
    When publication year is unavailable, retain the OpenAlex values and mark
    the work separately in the output.
    """
    if publication_year is None:
        return dict(history), []

    valid: dict[int, int] = {}
    excluded: list[dict[str, int | str]] = []

    for citation_year, count in sorted(history.items()):
        if citation_year < publication_year:
            excluded.append(
                {
                    "reason": "citation_year_before_cited_publication_year",
                    "citationYear": citation_year,
                    "publicationYear": publication_year,
                    "citations": count,
                }
            )
            continue

        valid[citation_year] = count

    return valid, excluded


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    api_key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if not api_key:
        print(
            "OPENALEX_API_KEY is not configured; using the public API quota.",
        )

    input_payload = load_openalex_metrics()
    publication_years = load_publication_years()
    records: dict[str, Any] = input_payload["records"]

    works: dict[str, dict[str, Any]] = {}
    expected_total = 0

    for raw_doi, record in records.items():
        if not isinstance(record, dict) or record.get("status") != "verified":
            continue

        doi = normalize_doi(raw_doi or record.get("doi"))
        work_id = normalize_openalex_id(
            record.get("openAlexId") or record.get("url")
        )

        if not doi or not work_id:
            continue

        citation_count = as_nonnegative_int(record.get("citationCount")) or 0
        expected_total += citation_count

        works[work_id] = {
            "doi": doi,
            "title": record.get("title", ""),
            "publicationYear": publication_years.get(doi),
            "currentCitationCount": citation_count,
        }

    if not works:
        raise RuntimeError("No verified OpenAlex Work IDs were found.")

    annual_totals: Counter[int] = Counter()
    per_work: dict[str, dict[str, Any]] = {}
    excluded_invalid_citations: list[dict[str, Any]] = []
    raw_history_total = 0
    missing_publication_year_count = 0

    with build_session() as session:
        for index, (work_id, metadata) in enumerate(
            sorted(works.items()),
            start=1,
        ):
            fetched_count, citing_works = fetch_citing_works(
                session,
                api_key,
                work_id,
            )
            raw_history = citing_work_years(citing_works)
            raw_work_total = sum(raw_history.values())
            raw_history_total += raw_work_total

            publication_year = metadata.get("publicationYear")
            if publication_year is None:
                missing_publication_year_count += 1

            valid_history, excluded = split_valid_and_invalid_history(
                raw_history,
                publication_year,
            )

            for year, count in valid_history.items():
                annual_totals[year] += count

            work_excluded_total = sum(
                int(item["citations"]) for item in excluded
            )

            for item in excluded:
                excluded_invalid_citations.append(
                    {
                        "citedWorkId": work_id,
                        "doi": metadata["doi"],
                        "title": metadata["title"],
                        **item,
                    }
                )

            current_total = int(metadata["currentCitationCount"])
            source_total = max(current_total, fetched_count, len(citing_works))
            raw_unassigned_count = max(0, source_total - raw_work_total)
            citing_articles = citing_articles_with_doi(
                citing_works,
                publication_year,
            )

            per_work[work_id] = {
                **metadata,
                "sourceUrl": (
                    f"https://api.openalex.org/works?"
                    f"filter=cites:{work_id}"
                ),
                "citationsByYear": [
                    {"year": year, "citations": count}
                    for year, count in sorted(valid_history.items())
                ],
                "rawCitationsByYear": [
                    {"year": year, "citations": count}
                    for year, count in sorted(raw_history.items())
                ],
                "historyTotal": sum(valid_history.values()),
                "rawHistoryTotal": raw_work_total,
                "excludedInvalidCitationCount": work_excluded_total,
                "excludedInvalidCitations": excluded,
                "unassignedCitationCount": raw_unassigned_count,
                "citingWorkCount": len(citing_works),
                "citingArticlesWithDoiCount": len(citing_articles),
                "citingArticlesWithDoi": citing_articles,
            }

            print(
                f"[{index}/{len(works)}] {work_id}: "
                f"{sum(valid_history.values())} valid, "
                f"{work_excluded_total} excluded, "
                f"{raw_unassigned_count} unassigned, "
                f"{len(citing_articles)} with DOI"
            )
            time.sleep(0.15)

    citations_by_year = [
        {"year": year, "citations": annual_totals[year]}
        for year in sorted(annual_totals)
    ]

    included_total = sum(annual_totals.values())
    raw_validation_difference = raw_history_total - expected_total
    unassigned_total = max(0, expected_total - raw_history_total)
    excluded_total = sum(
        int(item["citations"]) for item in excluded_invalid_citations
    )

    if raw_validation_difference != 0:
        status = "partial"
    elif excluded_total > 0:
        status = "success_with_exclusions"
    else:
        status = "success"

    output = {
        "schemaVersion": 3,
        "source": "OpenAlex Works API",
        "status": status,
        "lastSuccessfulUpdate": utc_now(),
        "workCount": len(works),
        "missingPublicationYearCount": missing_publication_year_count,
        "totalCitationsFromPublicationMetrics": expected_total,
        "rawTotalCitationsFromHistory": raw_history_total,
        "totalCitationsIncludedInAnnualChart": included_total,
        "rawValidationDifference": raw_validation_difference,
        "unassignedCitationCount": unassigned_total,
        "excludedInvalidCitationCount": excluded_total,
        "excludedInvalidCitations": excluded_invalid_citations,
        "citationsByYear": citations_by_year,
        "works": per_work,
    }

    write_json_atomic(OUTPUT_PATH, output)

    print(
        f"Saved {len(citations_by_year)} OpenAlex annual values "
        f"to {OUTPUT_PATH}."
    )
    print(f"Raw validation difference: {raw_validation_difference}")
    print(f"Excluded invalid citation events: {excluded_total}")
    print(f"Included in annual chart: {included_total}/{expected_total}")


if __name__ == "__main__":
    main()
