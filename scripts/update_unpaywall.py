#!/usr/bin/env python3
"""Update legal open-access links for publications using the Unpaywall API.

The script reads ``data/publications.json`` and writes
``data/unpaywall.json``. It prefers a direct PDF URL when Unpaywall provides
one, otherwise it stores the best legal open-access landing page.

Environment variable:
  UNPAYWALL_EMAIL  Optional contact email. If omitted, the public academic
                   email already displayed on the website is used.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PUBLICATIONS_PATH = ROOT / "data" / "publications.json"
OUTPUT_PATH = ROOT / "data" / "unpaywall.json"
API_BASE = "https://api.unpaywall.org/v2"
DEFAULT_CONTACT_EMAIL = "weihchiu@mail.cgu.edu.tw"
USER_AGENT = "Wei-Hao-Chiu-Academic-Website-Unpaywall-Updater/1.0"
TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
REQUEST_DELAY_SECONDS = 0.20


class UpdateFailure(RuntimeError):
    """Fatal updater error with a safe message."""


class ApiRequestError(RuntimeError):
    """Recoverable error for one DOI request."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_doi(value: Any) -> str:
    doi = str(value or "").strip()
    lowered = doi.lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "doi:"):
        if lowered.startswith(prefix):
            doi = doi[len(prefix) :].strip()
            break
    return doi.lower()


def valid_contact_email(value: str) -> bool:
    value = value.strip()
    return "@" in value and "." in value.rsplit("@", 1)[-1] and not any(c.isspace() for c in value)


def valid_external_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return url


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
        return exc.read().decode("utf-8", errors="replace").strip()[:300]
    except Exception:
        return ""


def request_record(doi: str, email: str) -> dict[str, Any] | None:
    query = urlencode({"email": email})
    request = Request(
        f"{API_BASE}/{quote(doi, safe='/')}?{query}",
        method="GET",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )

    for attempt in range(MAX_RETRIES + 1):
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                data = json.loads(response.read().decode(charset))
                return data if isinstance(data, dict) else None
        except HTTPError as exc:
            if exc.code == 404:
                return None
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if retryable and attempt < MAX_RETRIES:
                retry_after = exc.headers.get("Retry-After")
                try:
                    delay = max(float(retry_after), 1.0) if retry_after else 2**attempt
                except ValueError:
                    delay = 2**attempt
                time.sleep(min(delay, 20.0))
                continue
            detail = safe_error_body(exc)
            suffix = f" Response: {detail}" if detail else ""
            raise ApiRequestError(f"HTTP {exc.code} from Unpaywall.{suffix}") from exc
        except (URLError, TimeoutError) as exc:
            if attempt < MAX_RETRIES:
                time.sleep(2**attempt)
                continue
            reason = getattr(exc, "reason", str(exc))
            raise ApiRequestError(f"Could not connect to Unpaywall: {reason}") from exc
        except json.JSONDecodeError as exc:
            raise ApiRequestError("Unpaywall returned invalid JSON.") from exc

    raise ApiRequestError("Unpaywall request failed after retries.")


def candidate_locations(data: dict[str, Any]) -> list[dict[str, Any]]:
    locations: list[dict[str, Any]] = []
    best = data.get("best_oa_location")
    if isinstance(best, dict):
        locations.append(best)
    for item in data.get("oa_locations") or []:
        if isinstance(item, dict) and item not in locations:
            locations.append(item)
    return locations


def make_record(data: dict[str, Any] | None, attempted_at: str) -> dict[str, Any]:
    if not data:
        return {
            "status": "not-found",
            "isOa": False,
            "lastChecked": attempted_at,
        }

    is_oa = bool(data.get("is_oa"))
    if not is_oa:
        return {
            "status": "closed",
            "isOa": False,
            "oaStatus": data.get("oa_status") or "closed",
            "lastChecked": attempted_at,
        }

    pdf_url = ""
    landing_url = ""
    selected: dict[str, Any] = {}
    for location in candidate_locations(data):
        candidate_pdf = valid_external_url(location.get("url_for_pdf"))
        candidate_landing = valid_external_url(location.get("url")) or valid_external_url(
            location.get("url_for_landing_page")
        )
        if candidate_pdf:
            pdf_url = candidate_pdf
            landing_url = candidate_landing
            selected = location
            break
        if not landing_url and candidate_landing:
            landing_url = candidate_landing
            selected = location

    if not pdf_url and not landing_url:
        return {
            "status": "open-access-without-valid-url",
            "isOa": True,
            "oaStatus": data.get("oa_status") or "unknown",
            "lastChecked": attempted_at,
        }

    return {
        "status": "open-access",
        "isOa": True,
        "urlForPdf": pdf_url,
        "landingPageUrl": landing_url,
        "oaStatus": data.get("oa_status") or "unknown",
        "license": selected.get("license"),
        "version": selected.get("version"),
        "hostType": selected.get("host_type"),
        "repositoryInstitution": selected.get("repository_institution"),
        "lastChecked": attempted_at,
    }


def stale_record(previous: dict[str, Any] | None, message: str, attempted_at: str) -> dict[str, Any]:
    if isinstance(previous, dict):
        result = dict(previous)
        result["stale"] = True
        result["lastError"] = message[:300]
        result["lastAttemptedUpdate"] = attempted_at
        return result
    return {
        "status": "error",
        "isOa": False,
        "lastError": message[:300],
        "lastAttemptedUpdate": attempted_at,
    }


def main() -> int:
    email = os.environ.get("UNPAYWALL_EMAIL", "").strip() or DEFAULT_CONTACT_EMAIL
    if not valid_contact_email(email):
        raise UpdateFailure("UNPAYWALL_EMAIL is not a valid contact email address.")

    publications = load_json(PUBLICATIONS_PATH, [])
    if not isinstance(publications, list) or not publications:
        raise UpdateFailure("data/publications.json is missing or contains no records.")

    previous = load_json(OUTPUT_PATH, {})
    if not isinstance(previous, dict):
        previous = {}
    previous_records = previous.get("records", {})
    if not isinstance(previous_records, dict):
        previous_records = {}

    attempted_at = utc_now()
    records: dict[str, Any] = {}
    successful_requests = 0
    failures = 0

    dois = []
    for publication in publications:
        if not isinstance(publication, dict):
            continue
        doi = normalize_doi(publication.get("doi"))
        if doi and doi not in dois:
            dois.append(doi)

    for index, doi in enumerate(dois, start=1):
        try:
            data = request_record(doi, email)
            records[doi] = make_record(data, attempted_at)
            successful_requests += 1
            print(f"[{index}/{len(dois)}] checked {doi}: {records[doi]['status']}")
        except ApiRequestError as exc:
            failures += 1
            records[doi] = stale_record(previous_records.get(doi), str(exc), attempted_at)
            print(f"[{index}/{len(dois)}] retained previous data for {doi}: {exc}", file=sys.stderr)
        time.sleep(REQUEST_DELAY_SECONDS)

    payload = {
        "source": "Unpaywall",
        "apiVersion": "v2",
        "lastSuccessfulUpdate": attempted_at if successful_requests else previous.get("lastSuccessfulUpdate"),
        "lastAttempt": attempted_at,
        "status": "success" if failures == 0 else f"partial success; {failures} request(s) retained previous data",
        "publicationCount": len(dois),
        "records": records,
    }
    write_json_atomic(OUTPUT_PATH, payload)
    print(f"Unpaywall update completed: {successful_requests} checked, {failures} failed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except UpdateFailure as exc:
        print(f"Unpaywall update failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
