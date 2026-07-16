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


INPUT_PATH = Path("data/openalex_publication_metrics.json")
OUTPUT_PATH = Path("data/openalex_citation_history.json")
API_URL = "https://api.openalex.org/works"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_openalex_id(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("https://openalex.org/"):
        text = text.rstrip("/").rsplit("/", 1)[-1]
    return text if text.startswith("W") and text[1:].isdigit() else ""


def as_nonnegative_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def load_input() -> dict[str, Any]:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Missing {INPUT_PATH}. Run the existing OpenAlex metrics updater first.")
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload.get("records"), dict):
        raise RuntimeError(f"Invalid records object in {INPUT_PATH}.")
    return payload


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
    response = session.get(
        API_URL,
        params={
            "filter": f"cites:{work_id}",
            "group_by": "publication_year",
            "per_page": 1,
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
        raise RuntimeError("OPENALEX_API_KEY is not configured in GitHub Actions secrets.")

    input_payload = load_input()
    records: dict[str, Any] = input_payload["records"]

    works: dict[str, dict[str, Any]] = {}
    expected_total = 0
    for doi, record in records.items():
        if not isinstance(record, dict) or record.get("status") != "verified":
            continue
        work_id = normalize_openalex_id(record.get("openAlexId") or record.get("url"))
        if not work_id:
            continue
        citation_count = as_nonnegative_int(record.get("citationCount")) or 0
        expected_total += citation_count
        works[work_id] = {
            "doi": doi,
            "title": record.get("title", ""),
            "currentCitationCount": citation_count,
        }

    if not works:
        raise RuntimeError("No verified OpenAlex Work IDs were found.")

    annual_totals: Counter[int] = Counter()
    per_work: dict[str, dict[str, Any]] = {}

    with build_session() as session:
        for index, (work_id, metadata) in enumerate(sorted(works.items()), start=1):
            history = fetch_history(session, api_key, work_id)
            for year, count in history.items():
                annual_totals[year] += count

            per_work[work_id] = {
                **metadata,
                "citationsByYear": [
                    {"year": year, "citations": count}
                    for year, count in sorted(history.items())
                ],
                "historyTotal": sum(history.values()),
            }
            print(f"[{index}/{len(works)}] {work_id}: {sum(history.values())} citation events")
            time.sleep(0.15)

    citations_by_year = [
        {"year": year, "citations": annual_totals[year]}
        for year in sorted(annual_totals)
    ]
    calculated_total = sum(annual_totals.values())

    output = {
        "schemaVersion": 1,
        "source": "OpenAlex Works API",
        "status": "success",
        "lastSuccessfulUpdate": utc_now(),
        "workCount": len(works),
        "totalCitationsFromHistory": calculated_total,
        "totalCitationsFromPublicationMetrics": expected_total,
        "validationDifference": calculated_total - expected_total,
        "citationsByYear": citations_by_year,
        "works": per_work,
    }

    write_json_atomic(OUTPUT_PATH, output)
    print(f"Saved {len(citations_by_year)} OpenAlex annual values to {OUTPUT_PATH}.")
    print(f"Validation difference: {output['validationDifference']}")


if __name__ == "__main__":
    main()
