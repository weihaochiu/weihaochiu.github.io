"""Expose GRB discovery results from the dedicated Playwright updater.

The GRB site is JavaScript-driven. The academic monitor therefore consumes the
structured pending/snapshot files produced by update_grb_projects_browser.py
instead of issuing unsupported ``/search?query=...`` requests.
"""
from __future__ import annotations

from datetime import datetime

from academic_monitor_common import (
    normalize_identifier,
    read_json,
    source_result,
)

DEFAULT_SEARCH_URL = (
    "https://www.grb.gov.tw/advq?"
    "queryStr=%E9%82%B1%E5%81%89%E8%B1%AA&queryType=grb05"
)


def snapshot_age_days(checked_at: str) -> int | None:
    try:
        checked = datetime.fromisoformat(str(checked_at))
        now = datetime.now().astimezone()
        return max(0, (now - checked.astimezone()).days)
    except (TypeError, ValueError):
        return None


def normalize_pending(row: dict) -> dict:
    parsed = row.get("parsed") if isinstance(row.get("parsed"), dict) else row
    grb_id = str(parsed.get("grbId") or row.get("grbId") or "").strip()
    detail_url = (
        parsed.get("url")
        or row.get("url")
        or (f"https://www.grb.gov.tw/search/planDetail?id={grb_id}" if grb_id else "")
    )
    search_url = str(row.get("searchUrl") or DEFAULT_SEARCH_URL)
    return {
        "type": "project",
        "confidence": "possible",
        "grbId": grb_id,
        "number": str(parsed.get("number") or ""),
        "titleZh": str(parsed.get("titleZh") or ""),
        "titleEn": str(parsed.get("titleEn") or ""),
        "roleZh": str(parsed.get("roleZh") or ""),
        "role": str(parsed.get("role") or ""),
        "agencyZh": str(parsed.get("agencyZh") or ""),
        "agencyEn": str(parsed.get("agencyEn") or ""),
        "institutionZh": str(parsed.get("institutionZh") or ""),
        "period": str(parsed.get("period") or ""),
        "startDate": str(parsed.get("startDate") or ""),
        "endDate": str(parsed.get("endDate") or ""),
        "fundingAmountTwd": parsed.get("fundingAmountTwd"),
        "abstractZh": str(parsed.get("abstractZh") or ""),
        "detectionNotes": [
            "This exact GRB record was discovered by the JavaScript-capable Playwright updater.",
            "It is not present in the current projects JSON and requires manual confirmation.",
        ],
        "sources": [
            {"name": "GRB project detail", "url": detail_url},
            {"name": "GRB researcher search", "url": search_url},
        ],
    }


def run() -> dict:
    current = read_json("projects.json", [])
    known_numbers = {
        normalize_identifier(row.get("number"))
        for row in current
        if row.get("number")
    }
    known_ids = {str(row.get("grbId")) for row in current if row.get("grbId")}
    pending = read_json("grb_projects_pending.json", [])
    snapshot = read_json("grb_projects_snapshot.json", {})

    discovery = snapshot.get("discovery", []) if isinstance(snapshot, dict) else []
    successful = next(
        (row for row in discovery if isinstance(row, dict) and row.get("ok")),
        None,
    )
    search_url = str((successful or {}).get("url") or DEFAULT_SEARCH_URL)

    items = []
    seen = set()
    for row in pending if isinstance(pending, list) else []:
        if not isinstance(row, dict):
            continue
        item = normalize_pending(row)
        grb_id = item["grbId"]
        number = normalize_identifier(item["number"])
        identity = grb_id or number
        if not identity or identity in seen:
            continue
        seen.add(identity)
        if grb_id in known_ids or (number and number in known_numbers):
            continue
        item["sources"][1]["url"] = search_url
        items.append(item)

    checked_at = snapshot.get("checkedAt", "") if isinstance(snapshot, dict) else ""
    age_days = snapshot_age_days(checked_at)
    if successful and age_days is not None and age_days <= 5:
        status = "success"
        message = (
            f"GRB Playwright discovery completed; {len(items)} pending "
            "record(s) require review."
        )
    elif successful:
        status = "warning"
        message = (
            f"Last successful Playwright discovery is {age_days if age_days is not None else 'an unknown number of'} "
            f"day(s) old; {len(items)} pending record(s) require review."
        )
    else:
        status = "warning"
        message = (
            "No successful structured GRB Playwright discovery snapshot is available. "
            "The monitor did not fall back to the unsupported query URL."
        )

    return {
        "items": items,
        "sources": [
            source_result("GRB (Playwright snapshot)", search_url, status, message, len(items))
        ],
    }
