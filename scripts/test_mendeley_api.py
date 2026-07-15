#!/usr/bin/env python3
"""Test Mendeley Client Credentials and retrieve one Catalog record by DOI.

Required environment variables:
  MENDELEY_CLIENT_ID
  MENDELEY_CLIENT_SECRET

Optional environment variable:
  MENDELEY_TEST_DOI
"""

from __future__ import annotations

import base64
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

TOKEN_URL = "https://api.mendeley.com/oauth/token"
CATALOG_URL = "https://api.mendeley.com/catalog"
DEFAULT_TEST_DOI = "10.1016/j.cej.2024.153974"
DOCUMENT_ACCEPT = "application/vnd.mendeley-document.1+json"
TIMEOUT_SECONDS = 30


class TestFailure(RuntimeError):
    """Expected test failure with a safe user-facing message."""


@dataclass(frozen=True)
class CatalogResult:
    title: str
    document_id: str
    doi: str
    reader_count: int
    link: str
    imported: bool
    exact_match_count: int


def normalize_doi(value: str) -> str:
    doi = value.strip()
    lowered = doi.lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if lowered.startswith(prefix):
            doi = doi[len(prefix):].strip()
            break
    return doi.lower()


def safe_error_body(exc: HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:
        return ""
    # OAuth errors should not contain credentials, but cap the output defensively.
    return body[:500]


def request_json(request: Request) -> Any:
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            payload = response.read().decode(charset)
    except HTTPError as exc:
        body = safe_error_body(exc)
        detail = f" Response: {body}" if body else ""
        raise TestFailure(f"HTTP {exc.code} from Mendeley API.{detail}") from exc
    except URLError as exc:
        raise TestFailure(f"Could not connect to Mendeley API: {exc.reason}") from exc
    except TimeoutError as exc:
        raise TestFailure("Mendeley API request timed out.") from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise TestFailure("Mendeley API returned a non-JSON response.") from exc


def obtain_access_token(client_id: str, client_secret: str) -> tuple[str, int]:
    credentials = f"{client_id}:{client_secret}".encode("utf-8")
    basic_auth = base64.b64encode(credentials).decode("ascii")
    body = urlencode(
        {
            "grant_type": "client_credentials",
            "scope": "all",
        }
    ).encode("ascii")

    request = Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Basic {basic_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "Wei-Hao-Chiu-Academic-Website-Mendeley-Test/1.0",
        },
    )
    data = request_json(request)

    if not isinstance(data, dict) or not data.get("access_token"):
        raise TestFailure("Token response did not contain an access_token.")

    token = str(data["access_token"])
    expires_in = int(data.get("expires_in") or 0)
    return token, expires_in


def extract_doi(record: dict[str, Any]) -> str:
    identifiers = record.get("identifiers")

    if isinstance(identifiers, dict):
        return normalize_doi(str(identifiers.get("doi") or ""))

    # Defensive compatibility in case an API representation returns a list.
    if isinstance(identifiers, list):
        for identifier in identifiers:
            if not isinstance(identifier, dict):
                continue
            if "doi" in identifier:
                return normalize_doi(str(identifier["doi"]))
            if str(identifier.get("type", "")).lower() == "doi":
                return normalize_doi(str(identifier.get("value") or ""))

    return ""


def is_valid_mendeley_link(link: str) -> bool:
    if not link:
        return False
    parsed = urlparse(link)
    hostname = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        hostname == "mendeley.com" or hostname.endswith(".mendeley.com")
    )


def query_catalog(access_token: str, requested_doi: str) -> CatalogResult:
    query = urlencode({"doi": requested_doi, "view": "all"})
    request = Request(
        f"{CATALOG_URL}?{query}",
        method="GET",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": DOCUMENT_ACCEPT,
            "User-Agent": "Wei-Hao-Chiu-Academic-Website-Mendeley-Test/1.0",
        },
    )
    data = request_json(request)

    if isinstance(data, dict):
        records = [data]
    elif isinstance(data, list):
        records = [item for item in data if isinstance(item, dict)]
    else:
        records = []

    normalized_requested = normalize_doi(requested_doi)
    exact_matches = [
        record for record in records
        if extract_doi(record) == normalized_requested
    ]

    if not exact_matches:
        raise TestFailure(
            "OAuth succeeded, but no Mendeley Catalog record with an exactly "
            f"matching DOI was returned for {requested_doi}."
        )

    # Prefer imported/canonical metadata; use reader count as a deterministic
    # tie-breaker if duplicate exact DOI records are returned.
    exact_matches.sort(
        key=lambda record: (
            bool(record.get("imported")),
            int(record.get("reader_count") or 0),
        ),
        reverse=True,
    )
    record = exact_matches[0]

    link = str(record.get("link") or "").strip()
    if not is_valid_mendeley_link(link):
        raise TestFailure(
            "A DOI match was found, but the API did not return a valid HTTPS "
            "Mendeley document link."
        )

    try:
        reader_count = int(record.get("reader_count") or 0)
    except (TypeError, ValueError) as exc:
        raise TestFailure("The returned reader_count is not a valid integer.") from exc

    return CatalogResult(
        title=str(record.get("title") or "(Untitled record)"),
        document_id=str(record.get("id") or ""),
        doi=extract_doi(record),
        reader_count=reader_count,
        link=link,
        imported=bool(record.get("imported")),
        exact_match_count=len(exact_matches),
    )


def github_safe(value: str) -> str:
    return value.replace("\r", " ").replace("\n", " ").replace("|", r"\|").strip()


def write_step_summary(result: CatalogResult, expires_in: int) -> None:
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return

    content = "\n".join(
        [
            "## Mendeley API test passed",
            "",
            "| Field | Result |",
            "|---|---|",
            f"| Title | {github_safe(result.title)} |",
            f"| DOI | `{github_safe(result.doi)}` |",
            f"| Mendeley document ID | `{github_safe(result.document_id)}` |",
            f"| Reader count | **{result.reader_count}** |",
            f"| Direct page | [Open in Mendeley]({result.link}) |",
            f"| Imported record | {'Yes' if result.imported else 'No'} |",
            f"| Exact DOI matches | {result.exact_match_count} |",
            f"| Token lifetime reported | {expires_in} seconds |",
            "",
            "> No client credential or access token is printed or saved.",
            "",
        ]
    )
    with Path(summary_file).open("a", encoding="utf-8") as handle:
        handle.write(content)


def main() -> int:
    client_id = os.environ.get("MENDELEY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("MENDELEY_CLIENT_SECRET", "").strip()
    test_doi = normalize_doi(
        os.environ.get("MENDELEY_TEST_DOI", DEFAULT_TEST_DOI)
    )

    if not client_id:
        raise TestFailure("MENDELEY_CLIENT_ID is missing.")
    if not client_secret:
        raise TestFailure("MENDELEY_CLIENT_SECRET is missing.")
    if not test_doi:
        raise TestFailure("MENDELEY_TEST_DOI is empty.")

    print("1/2 Requesting a Mendeley Client Credentials access token...")
    access_token, expires_in = obtain_access_token(client_id, client_secret)
    print(f"Token request succeeded (reported lifetime: {expires_in} seconds).")
    print("The token value is intentionally not displayed.")

    print(f"2/2 Querying Mendeley Catalog by DOI: {test_doi}")
    result = query_catalog(access_token, test_doi)

    print("\nMendeley API test PASSED")
    print(f"Title: {result.title}")
    print(f"DOI: {result.doi}")
    print(f"Mendeley document ID: {result.document_id}")
    print(f"Reader count: {result.reader_count}")
    print(f"Mendeley page: {result.link}")
    print(f"Imported record: {'yes' if result.imported else 'no'}")
    print(f"Exact DOI matches returned: {result.exact_match_count}")

    write_step_summary(result, expires_in)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TestFailure as exc:
        print(f"\nMendeley API test FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
