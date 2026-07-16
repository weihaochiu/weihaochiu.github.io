from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


AUTHOR_ID = "ZYbNQb8AAAAJ"
API_URL = "https://serpapi.com/search.json"
OUTPUT_PATH = Path("data/google_scholar_citation_history.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def as_nonnegative_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def metric_from_table(payload: dict[str, Any], metric_name: str) -> dict[str, int] | None:
    table = payload.get("cited_by", {}).get("table", [])
    if not isinstance(table, list):
        return None
    for row in table:
        metric = row.get(metric_name) if isinstance(row, dict) else None
        if not isinstance(metric, dict):
            continue
        result: dict[str, int] = {}
        for key in ("all", "since_2021", "since_2020"):
            value = as_nonnegative_int(metric.get(key))
            if value is not None:
                result[key] = value
        return result or None
    return None


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    api_key = os.environ.get("SERPAPI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("SERPAPI_API_KEY is not configured in GitHub Actions secrets.")

    response = requests.get(
        API_URL,
        params={
            "engine": "google_scholar_author",
            "author_id": AUTHOR_ID,
            "hl": "en",
            "api_key": api_key,
        },
        timeout=90,
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()

    if payload.get("error"):
        raise RuntimeError(f"SerpAPI returned an error: {payload['error']}")

    raw_graph = payload.get("cited_by", {}).get("graph", [])
    citations_by_year: list[dict[str, int]] = []
    if isinstance(raw_graph, list):
        for item in raw_graph:
            if not isinstance(item, dict):
                continue
            year = as_nonnegative_int(item.get("year"))
            citations = as_nonnegative_int(item.get("citations"))
            if year is None or citations is None or year < 1900:
                continue
            citations_by_year.append({"year": year, "citations": citations})

    citations_by_year.sort(key=lambda row: row["year"])
    if not citations_by_year:
        raise RuntimeError("SerpAPI returned no Google Scholar annual citation graph.")

    citations_metric = metric_from_table(payload, "citations") or {}
    h_index_metric = metric_from_table(payload, "h_index") or {}
    i10_index_metric = metric_from_table(payload, "i10_index") or {}

    output = {
        "schemaVersion": 1,
        "source": "Google Scholar via SerpAPI",
        "status": "success",
        "profileId": AUTHOR_ID,
        "profileUrl": f"https://scholar.google.com/citations?user={AUTHOR_ID}&hl=en",
        "lastSuccessfulUpdate": utc_now(),
        "totalCitations": citations_metric.get("all"),
        "hIndex": h_index_metric.get("all"),
        "i10Index": i10_index_metric.get("all"),
        "citationsByYear": citations_by_year,
    }

    write_json_atomic(OUTPUT_PATH, output)
    print(f"Saved {len(citations_by_year)} Google Scholar annual values to {OUTPUT_PATH}.")


if __name__ == "__main__":
    main()
