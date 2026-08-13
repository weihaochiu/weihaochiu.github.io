"""Shared helpers for the academic record monitor."""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlsplit, urlunsplit
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
USER_AGENT = (
    "Wei-Hao-Chiu-Academic-Monitor/1.0 "
    f"(mailto:{os.getenv('CONTACT_EMAIL', 'weihao.chiu@gmail.com')})"
)

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

def read_json(name: str, default: Any) -> Any:
    path = DATA_DIR / name
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)

def request_json(url: str, *, accept: str = "application/json", timeout: int = 30) -> Any:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)

def request_text(url: str, *, timeout: int = 30) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")

def source_result(name: str, url: str, status: str, message: str = "", count: int | None = None) -> dict:
    result = {
        "name": name,
        "url": url,
        "status": status,
        "message": message,
        "checkedAt": now_iso(),
    }
    if count is not None:
        result["candidateCount"] = count
    return result

def normalize_doi(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    text = re.sub(r"^doi:\s*", "", text)
    return text.rstrip(" .")

def normalize_identifier(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())

def normalize_title(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def normalize_repository_url(value: Any) -> str:
    """Normalize a stable repository URL for duplicate comparison."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = urlsplit(text)
    except ValueError:
        return ""
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    return urlunsplit(
        ("https", parsed.netloc.lower(), parsed.path.rstrip("/"), "", "")
    ).lower()


def publication_matches_existing(
    candidate: dict[str, Any], existing: list[dict[str, Any]]
) -> bool:
    """Match DOI-less outputs by repository URL or verified bibliographic identity."""
    candidate_doi = normalize_doi(candidate.get("doi"))
    candidate_urls = {
        normalize_repository_url(candidate.get(field))
        for field in ("repositoryUrl", "publicationUrl", "url")
    }
    candidate_urls.discard("")
    candidate_title = normalize_title(candidate.get("title"))
    candidate_year = str(candidate.get("year") or candidate.get("publicationDate") or "")[:4]
    candidate_type = str(
        candidate.get("publicationType") or candidate.get("suggestedPublicationType") or ""
    ).strip().lower()

    for publication in existing:
        if candidate_doi and candidate_doi == normalize_doi(publication.get("doi")):
            return True
        existing_urls = {
            normalize_repository_url(publication.get(field))
            for field in ("repositoryUrl", "publicationUrl", "url")
        }
        existing_urls.discard("")
        if candidate_urls & existing_urls:
            return True
        existing_title = normalize_title(publication.get("title"))
        if candidate_title and candidate_title == existing_title:
            existing_year = str(
                publication.get("year") or publication.get("publicationDate") or ""
            )[:4]
            existing_type = str(
                publication.get("publicationType")
                or publication.get("suggestedPublicationType")
                or ""
            ).strip().lower()
            if not candidate_year or not existing_year or candidate_year == existing_year:
                if not candidate_type or not existing_type or candidate_type == existing_type:
                    return True
    return False

def review_key(record_type: str, item: dict[str, Any]) -> str:
    """Return a stable key used by the review registry and browser UI."""
    singular = {
        "publications": "publication",
        "patents": "patent",
        "projects": "project",
    }.get(record_type, record_type.rstrip("s"))
    if singular == "publication":
        identity_type = "doi" if item.get("doi") else "title"
        identity = normalize_doi(item.get("doi")) or normalize_title(item.get("title"))
    elif singular == "patent":
        identity_type = "number" if item.get("canonicalId") or item.get("number") else "title"
        identity = normalize_identifier(item.get("canonicalId") or item.get("number")) or normalize_title(
            item.get("titleEn") or item.get("titleZh")
        )
    else:
        if item.get("grbId"):
            identity_type = "grb-id"
            identity = str(item.get("grbId")).strip()
        elif item.get("number"):
            identity_type = "number"
            identity = normalize_identifier(item.get("number"))
        else:
            identity_type = "title"
            identity = normalize_title(item.get("titleEn") or item.get("titleZh"))
    return f"{singular}:{identity_type}:{identity}" if identity else ""

def first(value: Any, default: str = "") -> str:
    if isinstance(value, list):
        return str(value[0]) if value else default
    return str(value) if value is not None else default

def date_parts(message: dict) -> str:
    for key in ("published-print", "published-online", "published", "issued", "created"):
        parts = message.get(key, {}).get("date-parts", [])
        if parts and parts[0]:
            values = [int(v) for v in parts[0][:3]]
            while len(values) < 3:
                values.append(1)
            return f"{values[0]:04d}-{values[1]:02d}-{values[2]:02d}"
    return ""

def safe_error(error: Exception) -> str:
    if isinstance(error, urllib.error.HTTPError):
        return f"HTTP {error.code}: {error.reason}"
    if isinstance(error, urllib.error.URLError):
        return f"Network error: {error.reason}"
    return f"{type(error).__name__}: {error}"
