#!/usr/bin/env python3
"""Fetch Wei-Hao Chiu's OpenAlex author metrics and update the site JSON."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

AUTHOR_ID = "A5007707999"
PROFILE_URL = f"https://openalex.org/{AUTHOR_ID}"
API_URL = f"https://api.openalex.org/authors/{AUTHOR_ID}"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "openalex_metrics.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def require_nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative integer")
    number = int(value)
    if number < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return number


def build_url() -> str:
    params = {
        "select": "id,display_name,cited_by_count,summary_stats,updated_date",
    }
    api_key = os.getenv("OPENALEX_API_KEY", "").strip()
    mailto = os.getenv("OPENALEX_MAILTO", "weihao.chiu@gmail.com").strip()
    if api_key:
        params["api_key"] = api_key
    if mailto:
        params["mailto"] = mailto
    return f"{API_URL}?{urlencode(params)}"


def fetch_author() -> dict[str, Any]:
    request = Request(
        build_url(),
        headers={
            "Accept": "application/json",
            "User-Agent": "weihaochiu.github.io OpenAlex metrics updater",
        },
    )
    try:
        with urlopen(request, timeout=45) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"OpenAlex returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Unable to contact OpenAlex: {error.reason}") from error


def normalize(payload: dict[str, Any]) -> dict[str, Any]:
    expected_id = PROFILE_URL.lower()
    returned_id = str(payload.get("id", "")).rstrip("/")
    if returned_id.lower() != expected_id:
        raise ValueError(f"Unexpected OpenAlex author id: {returned_id!r}")

    stats = payload.get("summary_stats") or {}
    return {
        "schemaVersion": 1,
        "source": "OpenAlex Author API",
        "status": "success",
        "authorId": AUTHOR_ID,
        "authorName": str(payload.get("display_name") or "Wei-Hao Chiu"),
        "profileUrl": PROFILE_URL,
        "citations": require_nonnegative_int(payload.get("cited_by_count"), "cited_by_count"),
        "hIndex": require_nonnegative_int(stats.get("h_index"), "summary_stats.h_index"),
        "i10Index": require_nonnegative_int(stats.get("i10_index"), "summary_stats.i10_index"),
        "openAlexUpdatedDate": payload.get("updated_date"),
        "lastSuccessfulUpdate": utc_now(),
    }


def write_atomic(data: dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=OUTPUT_PATH.parent,
        prefix=f".{OUTPUT_PATH.name}.",
        delete=False,
    ) as temporary:
        temporary.write(serialized)
        temporary_path = Path(temporary.name)
    temporary_path.replace(OUTPUT_PATH)


def main() -> int:
    try:
        data = normalize(fetch_author())
        write_atomic(data)
    except (RuntimeError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(f"OpenAlex update failed; existing JSON was preserved: {error}", file=sys.stderr)
        return 1

    print(
        "Updated OpenAlex metrics: "
        f"citations={data['citations']}, h-index={data['hIndex']}, i10-index={data['i10Index']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
