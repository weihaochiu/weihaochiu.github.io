#!/usr/bin/env python3
"""Update per-publication citation counts from the free Crossref REST API."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
PUBLICATIONS = ROOT / "data" / "publications.json"
OUTPUT = ROOT / "data" / "crossref_publication_metrics.json"
API = "https://api.crossref.org/works/{}"


def main() -> None:
    publications = json.loads(PUBLICATIONS.read_text(encoding="utf-8"))
    existing = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    old_records = existing.get("records", {})
    records = {}
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    mailto = os.getenv("CROSSREF_MAILTO", "").strip() or "weihao.chiu@gmail.com"
    session = requests.Session()
    session.headers.update({"User-Agent": f"WeiHaoChiuAcademicWebsite/1.0 (mailto:{mailto})"})

    for publication in publications:
        doi = str(publication.get("doi") or "").strip().lower()
        if not doi:
            continue
        try:
            response = session.get(API.format(quote(doi, safe="")), params={"mailto": mailto}, timeout=30)
            response.raise_for_status()
            message = response.json()["message"]
            records[doi] = {
                "doi": doi,
                "citationCount": int(message.get("is-referenced-by-count") or 0),
                "status": "verified",
                "url": f"https://search.crossref.org/?q={quote(doi, safe='')}",
                "apiUrl": API.format(quote(doi, safe="")),
                "updatedAt": now,
            }
        except (requests.RequestException, KeyError, TypeError, ValueError) as error:
            previous = old_records.get(doi, {})
            records[doi] = {
                **previous,
                "doi": doi,
                "status": "stale" if previous.get("status") == "verified" else "error",
                "error": str(error)[:300],
                "lastAttempt": now,
            }
        time.sleep(0.12)

    verified = sum(record.get("status") == "verified" for record in records.values())
    payload = {
        "source": "Crossref REST API",
        "field": "is-referenced-by-count",
        "lastSuccessfulUpdate": now if verified else existing.get("lastSuccessfulUpdate"),
        "recordCount": len(records),
        "verifiedCount": verified,
        "records": records,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {verified}/{len(records)} verified Crossref records to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
