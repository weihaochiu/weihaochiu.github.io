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


def fetch_history(
    session: requests.Session,
    api_key: str,
    work_id: str,
) -> dict[int, int]:
    """Return citation events grouped by publication year of the citing work."""
    response = session.get(
        API_URL,
        params={
            "filter": f"cites:{work_id}",
            "group_by": "publication_year",
            "per-page": 200,
            "api_key": api_key,
        },
        timeout=90,
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()

    history: dict[int, int] = {}
    groups = payload.get("group_by", [])

    if not isinstance(groups, list):
        return history

    for group in groups:
        if not isinstance(group, dict):
            continue

        year = as_nonnegative_int(group.get("key"))
        count = as_nonnegative_int(group.get("count"))

        if year is None or count is None or year < 1900:
            continue

        history[year] = count

    return history


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
        raise RuntimeError(
            "OPENALEX_API_KEY is not configured in GitHub Actions secrets."
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
            raw_history = fetch_history(session, api_key, work_id)
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
            raw_unassigned_count = max(0, current_total - raw_work_total)

            per_work[work_id] = {
                **metadata,
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
            }

            print(
                f"[{index}/{len(works)}] {work_id}: "
                f"{sum(valid_history.values())} valid, "
                f"{work_excluded_total} excluded, "
                f"{raw_unassigned_count} unassigned"
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
        "schemaVersion": 2,
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
