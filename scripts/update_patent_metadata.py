#!/usr/bin/env python3
"""Refresh non-destructive metadata for manually verified patent records."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from academic_monitor_common import request_text, safe_error
from patent_common import (
    build_alias_index,
    canonicalize_identifier,
    normalize_identifier,
    parse_google_patent_page,
)


ROOT = SCRIPT_DIR.parent


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def refreshed_record(patent: dict[str, Any], parsed: dict[str, Any], checked_at: str) -> dict[str, Any]:
    canonical = normalize_identifier(patent.get("canonicalId"))
    parsed_number = normalize_identifier(parsed.get("canonicalId"))
    aliases = {normalize_identifier(value) for value in patent.get("aliases") or []}
    aliases.add(canonical)
    if parsed_number not in aliases:
        raise ValueError(
            f"Exact record returned {parsed_number or '<blank>'}, expected one of {sorted(aliases)}"
        )
    fields = (
        "applicationNumber",
        "priorityDate",
        "filingDate",
        "publicationDate",
        "grantDate",
        "legalStatus",
        "jurisdictionCode",
        "classifications",
        "abstract",
    )
    record = {
        "canonicalId": canonical,
        "source": "Google Patents",
        "sourceUrl": patent.get("url", ""),
        "status": "verified",
        "updatedAt": checked_at,
    }
    for field in fields:
        value = parsed.get(field)
        if value not in ("", None, [], {}):
            record[field] = value
    return record


def update(patents_path: Path, metadata_path: Path) -> tuple[dict[str, Any], bool]:
    patents = read_json(patents_path, [])
    previous = read_json(metadata_path, {})
    previous_records = previous.get("records", {}) if isinstance(previous, dict) else {}
    if not isinstance(patents, list) or not isinstance(previous_records, dict):
        raise SystemExit("Patent source or metadata file has an invalid structure")
    build_alias_index(patents)
    checked_at = now_iso()
    records: dict[str, Any] = {}
    errors: list[dict[str, str]] = []
    success = 0
    for patent in patents:
        canonical = normalize_identifier(patent.get("canonicalId"))
        try:
            page = request_text(str(patent.get("url") or ""))
            parsed = parse_google_patent_page(page, canonical)
            records[canonical] = refreshed_record(patent, parsed, checked_at)
            success += 1
        except Exception as exc:
            cached = previous_records.get(canonical)
            if isinstance(cached, dict) and cached:
                records[canonical] = cached
            errors.append({
                "canonicalId": canonical,
                "sourceUrl": str(patent.get("url") or ""),
                "message": safe_error(exc),
            })
    payload = {
        "schemaVersion": 1,
        "source": "Google Patents exact record pages",
        "lastAttempt": checked_at,
        "lastSuccessfulUpdate": checked_at if success == len(patents) else previous.get("lastSuccessfulUpdate", ""),
        "recordCount": len(records),
        "verifiedCount": sum(1 for record in records.values() if record.get("status") == "verified"),
        "records": records,
        "errors": errors,
    }
    before = json.dumps(previous, ensure_ascii=False, sort_keys=True)
    after = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return payload, before != after


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patents", type=Path, default=ROOT / "data/patents.json")
    parser.add_argument("--metadata", type=Path, default=ROOT / "data/patent_metadata.json")
    parser.add_argument("--check", action="store_true", help="Fetch and validate without writing")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload, changed = update(args.patents, args.metadata)
    if not args.check:
        args.metadata.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        f"Patent metadata: {payload['verifiedCount']}/{len(read_json(args.patents, []))} "
        f"verified; {len(payload.get('errors', []))} source error(s); changed={changed}."
    )


if __name__ == "__main__":
    main()
