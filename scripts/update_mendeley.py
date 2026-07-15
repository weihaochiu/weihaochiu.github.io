#!/usr/bin/env python3
"""Update Mendeley reader metrics for publications using DOI exact matching.

Required environment variables:
  MENDELEY_CLIENT_ID
  MENDELEY_CLIENT_SECRET

The script reads data/publications.json and writes data/mendeley_metrics.json.
It never prints or stores OAuth credentials or access tokens.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PUBLICATIONS_PATH = ROOT / "data" / "publications.json"
OUTPUT_PATH = ROOT / "data" / "mendeley_metrics.json"
TOKEN_URL = "https://api.mendeley.com/oauth/token"
CATALOG_URL = "https://api.mendeley.com/catalog"
DOCUMENT_ACCEPT = "application/vnd.mendeley-document.1+json"
USER_AGENT = "Wei-Hao-Chiu-Academic-Website-Mendeley-Updater/1.0"
TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
REQUEST_DELAY_SECONDS = 0.20


class UpdateFailure(RuntimeError):
    """Fatal update error with a safe message."""


class ApiRequestError(RuntimeError):
    """Recoverable per-publication API request error."""


@dataclass(frozen=True)
class CatalogMatch:
    title: str
    document_id: str
    doi: str
    reader_count: int
    url: str
    imported: bool
    match_count: int


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_doi(value: Any) -> str:
    doi = str(value or "").strip()
    lowered = doi.lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if lowered.startswith(prefix):
            doi = doi[len(prefix) :].strip()
            break
    return doi.lower()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Warning: could not read {path.relative_to(ROOT)}: {exc}", file=sys.stderr)
        return default


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def safe_error_body(exc: HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:
        return ""
    return body[:400]


def request_json(request: Request, retries: int = MAX_RETRIES) -> Any:
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return json.loads(response.read().decode(charset))
        except HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if retryable and attempt < retries:
                retry_after = exc.headers.get("Retry-After")
                try:
                    delay = max(float(retry_after), 1.0) if retry_after else 2**attempt
                except ValueError:
                    delay = 2**attempt
                time.sleep(min(delay, 20.0))
                continue
            detail = safe_error_body(exc)
            suffix = f" Response: {detail}" if detail else ""
            raise ApiRequestError(f"HTTP {exc.code} from Mendeley API.{suffix}") from exc
        except (URLError, TimeoutError) as exc:
            if attempt < retries:
                time.sleep(2**attempt)
                continue
            reason = getattr(exc, "reason", str(exc))
            raise ApiRequestError(f"Could not connect to Mendeley API: {reason}") from exc
        except json.JSONDecodeError as exc:
            raise ApiRequestError("Mendeley API returned invalid JSON.") from exc
    raise ApiRequestError("Mendeley API request failed after retries.")


def obtain_access_token(client_id: str, client_secret: str) -> str:
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    body = urlencode({"grant_type": "client_credentials", "scope": "all"}).encode("ascii")
    request = Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        data = request_json(request)
    except ApiRequestError as exc:
        raise UpdateFailure(f"Unable to obtain Mendeley access token: {exc}") from exc
    if not isinstance(data, dict) or not data.get("access_token"):
        raise UpdateFailure("Mendeley token response did not contain an access_token.")
    return str(data["access_token"])


def extract_doi(record: dict[str, Any]) -> str:
    identifiers = record.get("identifiers")
    if isinstance(identifiers, dict):
        return normalize_doi(identifiers.get("doi"))
    if isinstance(identifiers, list):
        for identifier in identifiers:
            if not isinstance(identifier, dict):
                continue
            if "doi" in identifier:
                return normalize_doi(identifier.get("doi"))
            if str(identifier.get("type", "")).lower() == "doi":
                return normalize_doi(identifier.get("value"))
    return ""


def valid_mendeley_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        return ""
    if hostname != "mendeley.com" and not hostname.endswith(".mendeley.com"):
        return ""
    return url


def query_catalog(access_token: str, requested_doi: str) -> CatalogMatch | None:
    query = urlencode({"doi": requested_doi, "view": "all"})
    request = Request(
        f"{CATALOG_URL}?{query}",
        method="GET",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": DOCUMENT_ACCEPT,
            "User-Agent": USER_AGENT,
        },
    )
    data = request_json(request)
    if isinstance(data, dict):
        records = [data]
    elif isinstance(data, list):
        records = [item for item in data if isinstance(item, dict)]
    else:
        records = []

    exact_matches = [record for record in records if extract_doi(record) == requested_doi]
    if not exact_matches:
        return None

    def sort_key(record: dict[str, Any]) -> tuple[bool, int]:
        try:
            count = int(record.get("reader_count") or 0)
        except (TypeError, ValueError):
            count = 0
        return bool(record.get("imported")), count

    exact_matches.sort(key=sort_key, reverse=True)
    record = exact_matches[0]
    url = valid_mendeley_url(record.get("link"))
    if not url:
        raise ApiRequestError("Exact DOI match did not include a valid Mendeley HTTPS link.")
    try:
        reader_count = int(record.get("reader_count") or 0)
    except (TypeError, ValueError) as exc:
        raise ApiRequestError("Mendeley reader_count was not an integer.") from exc
    if reader_count < 0:
        raise ApiRequestError("Mendeley reader_count was negative.")

    return CatalogMatch(
        title=str(record.get("title") or ""),
        document_id=str(record.get("id") or ""),
        doi=extract_doi(record),
        reader_count=reader_count,
        url=url,
        imported=bool(record.get("imported")),
        match_count=len(exact_matches),
    )


def previous_verified_record(previous_records: dict[str, Any], doi: str) -> dict[str, Any] | None:
    record = previous_records.get(doi)
    if not isinstance(record, dict) or record.get("status") != "verified":
        return None
    try:
        count = int(record.get("readerCount"))
    except (TypeError, ValueError):
        return None
    if count < 0 or not valid_mendeley_url(record.get("url")):
        return None
    return dict(record)


def make_stale(record: dict[str, Any], error: str, attempted_at: str) -> dict[str, Any]:
    stale = dict(record)
    stale["stale"] = True
    stale["lastError"] = error[:300]
    stale["lastAttemptedUpdate"] = attempted_at
    return stale


def main() -> int:
    client_id = os.environ.get("MENDELEY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("MENDELEY_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise UpdateFailure("MENDELEY_CLIENT_ID or MENDELEY_CLIENT_SECRET is missing.")

    publications = load_json(PUBLICATIONS_PATH, [])
    if not isinstance(publications, list):
        raise UpdateFailure("data/publications.json must contain a JSON array.")

    doi_titles: dict[str, str] = {}
    for publication in publications:
        if not isinstance(publication, dict):
            continue
        doi = normalize_doi(publication.get("doi"))
        if doi:
            doi_titles.setdefault(doi, str(publication.get("title") or ""))

    if not doi_titles:
        raise UpdateFailure("No DOI values were found in data/publications.json.")

    previous = load_json(OUTPUT_PATH, {})
    previous_records = previous.get("records", {}) if isinstance(previous, dict) else {}
    if not isinstance(previous_records, dict):
        previous_records = {}

    attempted_at = utc_now()
    print(f"Requesting Mendeley access token for {len(doi_titles)} DOI records...")
    token = obtain_access_token(client_id, client_secret)
    print("Token request succeeded. Token value is not displayed or stored.")

    records: dict[str, dict[str, Any]] = {}
    fresh_count = 0
    stale_count = 0
    not_found_count = 0
    error_count = 0

    for index, (doi, publication_title) in enumerate(doi_titles.items(), start=1):
        print(f"[{index}/{len(doi_titles)}] {doi}")
        try:
            match = query_catalog(token, doi)
            if match is None:
                old = previous_verified_record(previous_records, doi)
                if old:
                    records[doi] = make_stale(old, "No exact DOI match returned", attempted_at)
                    stale_count += 1
                else:
                    records[doi] = {
                        "status": "not_found",
                        "title": publication_title,
                        "lastAttemptedUpdate": attempted_at,
                    }
                    not_found_count += 1
            else:
                records[doi] = {
                    "status": "verified",
                    "title": match.title or publication_title,
                    "readerCount": match.reader_count,
                    "documentId": match.document_id,
                    "url": match.url,
                    "matchedBy": "doi",
                    "exactMatchCount": match.match_count,
                    "imported": match.imported,
                    "updatedAt": attempted_at,
                    "stale": False,
                }
                fresh_count += 1
        except ApiRequestError as exc:
            error_count += 1
            old = previous_verified_record(previous_records, doi)
            if old:
                records[doi] = make_stale(old, str(exc), attempted_at)
                stale_count += 1
            else:
                records[doi] = {
                    "status": "error",
                    "title": publication_title,
                    "lastError": str(exc)[:300],
                    "lastAttemptedUpdate": attempted_at,
                }
            print(f"  Warning: {exc}", file=sys.stderr)
        if index < len(doi_titles):
            time.sleep(REQUEST_DELAY_SECONDS)

    verified = [record for record in records.values() if record.get("status") == "verified"]
    total_readers = sum(int(record.get("readerCount") or 0) for record in verified)
    successful_at = attempted_at if fresh_count else str(previous.get("lastSuccessfulUpdate") or "")
    status = "success" if error_count == 0 and stale_count == 0 else "partial"

    payload = {
        "schemaVersion": 1,
        "source": "Mendeley Catalog API",
        "status": status,
        "lastAttemptedUpdate": attempted_at,
        "lastSuccessfulUpdate": successful_at,
        "totalReaders": total_readers,
        "publicationCount": len(doi_titles),
        "matchedPublications": len(verified),
        "freshPublications": fresh_count,
        "stalePublications": stale_count,
        "notFoundPublications": not_found_count,
        "errorPublications": error_count,
        "note": "Total readers is the sum of per-publication Mendeley reader counts and is not a count of unique people.",
        "records": dict(sorted(records.items())),
    }
    write_json_atomic(OUTPUT_PATH, payload)

    print("\nMendeley reader metrics updated")
    print(f"Matched publications: {len(verified)}/{len(doi_titles)}")
    print(f"Total reader count: {total_readers}")
    print(f"Fresh: {fresh_count}; stale preserved: {stale_count}; not found: {not_found_count}; errors: {error_count}")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        summary = "\n".join(
            [
                "## Mendeley reader metrics",
                "",
                f"- Publications with DOI: **{len(doi_titles)}**",
                f"- Verified records displayed: **{len(verified)}**",
                f"- Total Mendeley reader count: **{total_readers}**",
                f"- Fresh records: **{fresh_count}**",
                f"- Stale records preserved: **{stale_count}**",
                f"- Not found: **{not_found_count}**",
                f"- API errors: **{error_count}**",
                "",
                "> The total is a sum across publications, not a de-duplicated count of people.",
                "",
            ]
        )
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(summary)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except UpdateFailure as exc:
        print(f"Mendeley update failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
