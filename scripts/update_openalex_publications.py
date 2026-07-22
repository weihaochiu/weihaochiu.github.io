#!/usr/bin/env python3
"""Fetch OpenAlex citation and normalized-impact metrics for site publications."""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PUBLICATIONS_PATH = ROOT / "data" / "publications.json"
OUTPUT_PATH = ROOT / "data" / "openalex_publication_metrics.json"
API_BASE = "https://api.openalex.org/works"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_doi(value: Any) -> str:
    doi = str(value or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
            break
    return doi.strip()


def require_nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative integer")
    number = int(value)
    if number < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return number


def optional_nonnegative_float(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative number or null")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be a finite non-negative number or null")
    return number


def optional_percentile(value: Any) -> tuple[float | None, bool | None, bool | None]:
    if value is None:
        return None, None, None
    if not isinstance(value, dict):
        raise ValueError("citation_normalized_percentile must be an object or null")
    percentile = optional_nonnegative_float(value.get("value"), "citation_normalized_percentile.value")
    if percentile is not None and percentile > 1:
        raise ValueError("citation_normalized_percentile.value must be between 0 and 1")
    top_1 = value.get("is_in_top_1_percent")
    top_10 = value.get("is_in_top_10_percent")
    if top_1 is not None and not isinstance(top_1, bool):
        raise ValueError("is_in_top_1_percent must be a boolean or null")
    if top_10 is not None and not isinstance(top_10, bool):
        raise ValueError("is_in_top_10_percent must be a boolean or null")
    return percentile, top_1, top_10


def build_url(doi: str) -> str:
    work_id = quote(f"doi:{doi}", safe=":")
    params = {
        "select": (
            "id,doi,display_name,cited_by_count,fwci,"
            "citation_normalized_percentile,updated_date"
        )
    }
    api_key = os.getenv("OPENALEX_API_KEY", "").strip()
    mailto = os.getenv("OPENALEX_MAILTO", "weihao.chiu@gmail.com").strip()
    if api_key:
        params["api_key"] = api_key
    if mailto:
        params["mailto"] = mailto
    return f"{API_BASE}/{work_id}?{urlencode(params)}"


def fetch_work(doi: str) -> dict[str, Any] | None:
    request = Request(
        build_url(doi),
        headers={
            "Accept": "application/json",
            "User-Agent": "weihaochiu.github.io OpenAlex publication metrics updater",
        },
    )
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with urlopen(request, timeout=45) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code == 404:
                return None
            detail = error.read().decode("utf-8", errors="replace")[:500]
            last_error = RuntimeError(f"OpenAlex returned HTTP {error.code} for DOI {doi}: {detail}")
            if error.code not in {429, 500, 502, 503, 504}:
                break
        except URLError as error:
            last_error = RuntimeError(f"Unable to contact OpenAlex for DOI {doi}: {error.reason}")
        if attempt < 3:
            time.sleep(2**attempt)
    raise last_error or RuntimeError(f"Unable to retrieve OpenAlex work for DOI {doi}")


def normalize_record(doi: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {"status": "not_found", "doi": doi}

    returned_doi = normalize_doi(payload.get("doi"))
    if returned_doi and returned_doi != doi:
        raise ValueError(f"OpenAlex returned DOI {returned_doi!r} for requested DOI {doi!r}")

    openalex_url = str(payload.get("id") or "").strip()
    if not openalex_url.startswith("https://openalex.org/W"):
        raise ValueError(f"Unexpected OpenAlex work id for DOI {doi}: {openalex_url!r}")

    percentile, top_1, top_10 = optional_percentile(payload.get("citation_normalized_percentile"))

    return {
        "status": "verified",
        "doi": doi,
        "title": str(payload.get("display_name") or ""),
        "openAlexId": openalex_url.rsplit("/", 1)[-1],
        "url": openalex_url,
        "citationCount": require_nonnegative_int(payload.get("cited_by_count"), "cited_by_count"),
        "fwci": optional_nonnegative_float(payload.get("fwci"), "fwci"),
        "citationPercentile": percentile,
        "isTop1Percent": top_1,
        "isTop10Percent": top_10,
        "openAlexUpdatedDate": payload.get("updated_date"),
    }


def write_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as temporary:
        temporary.write(serialized)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def main() -> int:
    try:
        publications = json.loads(PUBLICATIONS_PATH.read_text(encoding="utf-8"))
        dois: list[str] = []
        for publication in publications:
            doi = normalize_doi(publication.get("doi"))
            if doi and doi not in dois:
                dois.append(doi)
        if not dois:
            raise ValueError("No publication DOIs were found")

        records: dict[str, Any] = {}
        for index, doi in enumerate(dois, start=1):
            records[doi] = normalize_record(doi, fetch_work(doi))
            print(f"[{index}/{len(dois)}] {doi}: {records[doi]['status']}")
            time.sleep(0.1)

        data = {
            "schemaVersion": 2,
            "source": "OpenAlex Works API",
            "status": "success",
            "publicationCount": len(dois),
            "verifiedCount": sum(r.get("status") == "verified" for r in records.values()),
            "notFoundCount": sum(r.get("status") == "not_found" for r in records.values()),
            "lastSuccessfulUpdate": utc_now(),
            "records": records,
        }
        write_atomic(OUTPUT_PATH, data)
    except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(
            f"OpenAlex publication update failed; existing JSON was preserved: {error}",
            file=sys.stderr,
        )
        return 1

    print(
        "Updated per-publication OpenAlex metrics: "
        f"verified={data['verifiedCount']}, not-found={data['notFoundCount']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
