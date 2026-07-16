from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PUBLICATIONS_PATH = Path("data/publications.json")
JOURNALS_PATH = Path("data/journals.json")

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
OPENALEX_SOURCES_URL = "https://api.openalex.org/sources"
MANUSIGHTS_BASE_URL = "https://manusights.com"

CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "weihao.chiu@gmail.com").strip()
OPENALEX_API_KEY = os.environ.get("OPENALEX_API_KEY", "").strip()

REQUEST_DELAY_SECONDS = 0.65
USER_AGENT = (
    "Wei-Hao-Chiu-Academic-Website/1.0 "
    f"(journal metadata updater; mailto:{CONTACT_EMAIL})"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compact_whitespace(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def ascii_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", compact_whitespace(value))
    return "".join(character for character in text if not unicodedata.combining(character))


def normalize_name(value: Any) -> str:
    text = ascii_text(value).lower()
    text = text.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "", text)


def slugify(value: Any) -> str:
    text = ascii_text(value).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "journal"


def normalize_doi(value: Any) -> str:
    text = compact_whitespace(value).lower()
    prefixes = (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    )
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return text.strip()


def normalize_issn(value: Any) -> str:
    text = re.sub(r"[^0-9Xx]", "", compact_whitespace(value)).upper()
    if len(text) != 8:
        return ""
    return f"{text[:4]}-{text[4:]}"


def as_int(value: Any) -> int | None:
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def as_float(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def unique_strings(values: list[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = compact_whitespace(value)
        if not text:
            continue
        key = text.casefold()
        if key not in seen:
            seen.add(key)
            output.append(text)
    return output


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def build_session() -> requests.Session:
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def safe_get(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int = 45,
) -> requests.Response | None:
    try:
        response = session.get(url, params=params, timeout=timeout)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response
    except requests.RequestException as error:
        print(f"WARNING: request failed: {url}: {error}")
        return None
    finally:
        time.sleep(REQUEST_DELAY_SECONDS)


def load_publication_groups() -> dict[str, dict[str, Any]]:
    rows = load_json(PUBLICATIONS_PATH)
    if not isinstance(rows, list):
        raise RuntimeError(f"{PUBLICATIONS_PATH} must contain a JSON array.")

    groups: dict[str, dict[str, Any]] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        title = compact_whitespace(row.get("journal"))
        if not title:
            continue

        normalized = normalize_name(title)
        if not normalized:
            continue

        group = groups.setdefault(
            normalized,
            {
                "titleCandidates": [],
                "publishers": [],
                "years": [],
                "dois": [],
                "articleTitles": [],
            },
        )

        group["titleCandidates"].append(title)
        group["publishers"].append(row.get("publisher"))
        year = as_int(row.get("year"))
        if year and 1800 <= year <= 2200:
            group["years"].append(year)

        doi = normalize_doi(row.get("doi") or row.get("doiUrl"))
        if doi:
            group["dois"].append(doi)

        article_title = compact_whitespace(row.get("title"))
        if article_title:
            group["articleTitles"].append(article_title)

    for normalized, group in groups.items():
        title_counts: dict[str, int] = defaultdict(int)
        for title in group["titleCandidates"]:
            title_counts[title] += 1

        canonical_title = sorted(
            title_counts,
            key=lambda item: (-title_counts[item], -len(item), item.casefold()),
        )[0]

        years = sorted(set(group["years"]))
        dois = unique_strings(group["dois"])
        publishers = unique_strings(group["publishers"])

        group.update(
            {
                "normalizedName": normalized,
                "canonicalTitle": canonical_title,
                "aliases": unique_strings(group["titleCandidates"]),
                "publisherFromPublications": publishers[0] if publishers else "",
                "publicationCount": len(group["titleCandidates"]),
                "publicationYears": years,
                "firstPublicationYear": years[0] if years else None,
                "latestPublicationYear": years[-1] if years else None,
                "sampleDoi": dois[0] if dois else "",
                "dois": dois,
            }
        )

    return groups


def make_journal_id(title: str, used_ids: set[str]) -> str:
    base = slugify(title)
    candidate = base
    if candidate in used_ids:
        suffix = hashlib.sha1(normalize_name(title).encode("utf-8")).hexdigest()[:7]
        candidate = f"{base}-{suffix}"
    used_ids.add(candidate)
    return candidate


def existing_index(existing: dict[str, Any]) -> dict[str, str]:
    index: dict[str, str] = {}
    journals = existing.get("journals", {})
    if not isinstance(journals, dict):
        return index

    for journal_id, record in journals.items():
        if not isinstance(record, dict):
            continue
        names = [record.get("title"), *(record.get("aliases") or [])]
        for name in names:
            normalized = normalize_name(name)
            if normalized:
                index[normalized] = journal_id
    return index


def crossref_metadata(
    session: requests.Session,
    doi: str,
) -> dict[str, Any]:
    if not doi:
        return {}

    response = safe_get(
        session,
        f"{CROSSREF_WORKS_URL}/{doi}",
        params={"mailto": CONTACT_EMAIL},
    )
    if response is None:
        return {}

    try:
        message = response.json().get("message", {})
    except ValueError:
        return {}

    if not isinstance(message, dict):
        return {}

    issn_types = message.get("issn-type") or []
    print_issn = ""
    electronic_issn = ""

    if isinstance(issn_types, list):
        for item in issn_types:
            if not isinstance(item, dict):
                continue
            value = normalize_issn(item.get("value"))
            issn_type = compact_whitespace(item.get("type")).lower()
            if issn_type == "print" and value:
                print_issn = value
            elif issn_type == "electronic" and value:
                electronic_issn = value

    all_issns = unique_strings(
        [normalize_issn(value) for value in (message.get("ISSN") or [])]
    )

    return {
        "title": compact_whitespace((message.get("container-title") or [""])[0]),
        "abbreviation": compact_whitespace(
            (message.get("short-container-title") or [""])[0]
        ),
        "publisher": compact_whitespace(message.get("publisher")),
        "issn": print_issn,
        "eissn": electronic_issn,
        "allIssns": all_issns,
        "subjects": unique_strings(message.get("subject") or []),
        "articleUrl": compact_whitespace(message.get("URL")),
        "source": {
            "name": "Crossref REST API",
            "url": f"https://api.crossref.org/works/{doi}",
            "retrievedAt": utc_now(),
        },
    }


def openalex_candidates(
    session: requests.Session,
    *,
    title: str,
    issns: list[str],
) -> list[dict[str, Any]]:
    common_params: dict[str, Any] = {"per-page": 10}
    if OPENALEX_API_KEY:
        common_params["api_key"] = OPENALEX_API_KEY
    elif CONTACT_EMAIL:
        common_params["mailto"] = CONTACT_EMAIL

    for issn in issns:
        response = safe_get(
            session,
            OPENALEX_SOURCES_URL,
            params={**common_params, "filter": f"issn:{issn}"},
        )
        if response is None:
            continue
        try:
            results = response.json().get("results", [])
        except ValueError:
            results = []
        if results:
            return [item for item in results if isinstance(item, dict)]

    response = safe_get(
        session,
        OPENALEX_SOURCES_URL,
        params={**common_params, "search": title},
    )
    if response is None:
        return []

    try:
        return [
            item
            for item in response.json().get("results", [])
            if isinstance(item, dict)
        ]
    except ValueError:
        return []


def similarity(left: str, right: str) -> float:
    left_normalized = normalize_name(left)
    right_normalized = normalize_name(right)
    if not left_normalized or not right_normalized:
        return 0.0
    if left_normalized == right_normalized:
        return 1.0
    return SequenceMatcher(None, left_normalized, right_normalized).ratio()


def select_openalex_source(
    candidates: list[dict[str, Any]],
    *,
    title: str,
    issns: list[str],
) -> dict[str, Any] | None:
    normalized_issns = {normalize_issn(value) for value in issns if value}
    scored: list[tuple[float, dict[str, Any]]] = []

    for candidate in candidates:
        candidate_issns = {
            normalize_issn(value)
            for value in (candidate.get("issn") or [])
            if value
        }
        issn_match = bool(normalized_issns & candidate_issns)
        name_score = similarity(title, candidate.get("display_name", ""))
        score = name_score + (1.0 if issn_match else 0.0)
        scored.append((score, candidate))

    if not scored:
        return None

    score, best = max(scored, key=lambda item: item[0])
    if score < 0.72:
        return None
    return best


def openalex_metadata(source: dict[str, Any] | None) -> dict[str, Any]:
    if not source:
        return {}

    summary_stats = source.get("summary_stats") or {}
    host_name = compact_whitespace(source.get("host_organization_name"))
    if not host_name:
        lineage = source.get("host_organization_lineage_names") or []
        if lineage:
            host_name = compact_whitespace(lineage[-1])

    return {
        "openAlexId": compact_whitespace(source.get("id")).rsplit("/", 1)[-1],
        "openAlexUrl": compact_whitespace(source.get("id")),
        "title": compact_whitespace(source.get("display_name")),
        "abbreviation": compact_whitespace(source.get("abbreviated_title")),
        "issnL": normalize_issn(source.get("issn_l")),
        "allIssns": unique_strings(
            [normalize_issn(value) for value in (source.get("issn") or [])]
        ),
        "homepage": compact_whitespace(source.get("homepage_url")),
        "publisher": host_name,
        "countryCode": compact_whitespace(source.get("country_code")),
        "sourceType": compact_whitespace(source.get("type")),
        "isOpenAccess": bool(source.get("is_oa")),
        "isInDoaj": bool(source.get("is_in_doaj")),
        "worksCount": as_int(source.get("works_count")),
        "citedByCount": as_int(source.get("cited_by_count")),
        "twoYearMeanCitedness": as_float(
            summary_stats.get("2yr_mean_citedness")
        ),
        "hIndex": as_int(summary_stats.get("h_index")),
        "i10Index": as_int(summary_stats.get("i10_index")),
        "source": {
            "name": "OpenAlex Sources API",
            "url": compact_whitespace(source.get("id")),
            "retrievedAt": utc_now(),
        },
    }


def find_value(text: str, patterns: list[str], cast: str = "str") -> Any:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1)
        if cast == "float":
            return as_float(value)
        if cast == "int":
            return as_int(value)
        return compact_whitespace(value)
    return None


def parse_manusights_document(
    html: str,
    *,
    page_url: str,
    expected_title: str,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    page_title = compact_whitespace(soup.title.get_text(" ", strip=True) if soup.title else "")
    heading = compact_whitespace(
        soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else ""
    )
    full_text = compact_whitespace(soup.get_text(" ", strip=True))

    if max(similarity(expected_title, page_title), similarity(expected_title, heading)) < 0.45:
        return {}

    metric_match = re.search(
        r"\b(20\d{2})\s+(?:Journal\s+)?Impact Factor"
        r"(?:\s*\(\s*(20\d{2})\s+(?:Journal Citation Reports|JCR)\s+release\s*\))?"
        r"\s*([0-9]+(?:\.[0-9]+)?)",
        full_text,
        flags=re.IGNORECASE,
    )

    metric_year = as_int(metric_match.group(1)) if metric_match else None
    release_year = as_int(metric_match.group(2)) if metric_match and metric_match.group(2) else None
    impact_factor = as_float(metric_match.group(3)) if metric_match else None

    if impact_factor is None:
        impact_factor = find_value(
            full_text,
            [
                r"\bIF\s+([0-9]+(?:\.[0-9]+)?)\b",
                r"\bImpact Factor\s+([0-9]+(?:\.[0-9]+)?)\b",
            ],
            "float",
        )

    five_year_if = find_value(
        full_text,
        [
            r"\b5[- ]Year\s+(?:Impact Factor|JIF)"
            r"(?:\s*\([^)]*\))?\s*([0-9]+(?:\.[0-9]+)?)",
            r"\bFive[- ]year impact factor\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)",
        ],
        "float",
    )

    jci = find_value(
        full_text,
        [r"\bJCI(?:\s*\([^)]*\))?\s*([0-9]+(?:\.[0-9]+)?)"],
        "float",
    )
    total_cites = find_value(
        full_text,
        [r"\bTotal Cites(?:\s*\([^)]*\))?\s*([0-9,]+)"],
        "int",
    )
    citescore = find_value(
        full_text,
        [r"\bCiteScore(?:\s*\([^)]*\))?\s*([0-9]+(?:\.[0-9]+)?)"],
        "float",
    )

    quartile = find_value(
        full_text,
        [
            r"\bQuartile\s*(Q[1-4])\b",
            r"\b(Q[1-4])\s+(?:status|placement)\b",
        ],
    )

    rank_match = re.search(
        r"\bCategory Rank\s*(\d+)\s*/\s*(\d+)",
        full_text,
        flags=re.IGNORECASE,
    )
    rank = as_int(rank_match.group(1)) if rank_match else None
    category_total = as_int(rank_match.group(2)) if rank_match else None

    category = find_value(
        full_text,
        [
            r"\bwithin\s+([^,.]{3,120}?),\s+[^.]{0,80}?\b\d+\s*/\s*\d+\s+rank",
            r"\branked?\s+\d+\s*/\s*\d+\s+in\s+([^,.]{3,120})",
            r"\bQ[1-4]\s+(?:status|placement)\s+in\s+([^,.]{3,120})",
        ],
    )

    publisher = find_value(
        full_text,
        [r"\bPublisher\s+([A-Za-z0-9&.,'’\- ]{2,80}?)(?=\s+(?:Founded|ISSN|Publication|Open access|Article Types|Before you submit)\b)"],
    )
    founded = find_value(full_text, [r"\bFounded\s+(\d{4})\b"], "int")
    issn = find_value(full_text, [r"\bISSN\s+(\d{4}-[\dXx]{4})\b"])
    eissn = find_value(
        full_text,
        [
            r"\bE-?ISSN\s+(\d{4}-[\dXx]{4})\b",
            r"\bOnline ISSN\s+(\d{4}-[\dXx]{4})\b",
        ],
    )

    release_year = release_year or find_value(
        full_text,
        [r"\b(20\d{2})\s+(?:Journal Citation Reports|JCR)\s+release\b"],
        "int",
    )

    result: dict[str, Any] = {
        "pageUrl": page_url,
        "pageTitle": page_title,
        "publisher": publisher,
        "foundedYear": founded,
        "issn": normalize_issn(issn),
        "eissn": normalize_issn(eissn),
        "metricYear": metric_year,
        "jcrReleaseYear": release_year,
        "impactFactor": impact_factor,
        "fiveYearImpactFactor": five_year_if,
        "jci": jci,
        "totalCites": total_cites,
        "citeScore": citescore,
        "bestQuartile": quartile.upper() if quartile else None,
        "category": category,
        "categoryRank": rank,
        "categoryJournalCount": category_total,
    }

    return {key: value for key, value in result.items() if value not in (None, "", [])}


def manuscripts_urls(title: str) -> list[str]:
    slug = slugify(title)
    return [
        f"{MANUSIGHTS_BASE_URL}/journals/{slug}",
        f"{MANUSIGHTS_BASE_URL}/blog/{slug}-impact-factor",
    ]


def manuscripts_metadata(
    session: requests.Session,
    title: str,
) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    fetched_urls: set[str] = set()

    for url in manuscripts_urls(title):
        if url in fetched_urls:
            continue
        response = safe_get(session, url)
        if response is None:
            continue
        fetched_urls.add(response.url)

        parsed = parse_manusights_document(
            response.text,
            page_url=response.url,
            expected_title=title,
        )
        if parsed:
            documents.append(parsed)

        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = urljoin(response.url, anchor["href"])
            anchor_text = compact_whitespace(anchor.get_text(" ", strip=True))
            if (
                "manusights.com/" in href
                and "impact-factor" in href
                and (
                    similarity(anchor_text, title) >= 0.35
                    or normalize_name(title) in normalize_name(anchor_text)
                )
                and href not in fetched_urls
            ):
                linked = safe_get(session, href)
                if linked is not None:
                    fetched_urls.add(linked.url)
                    linked_parsed = parse_manusights_document(
                        linked.text,
                        page_url=linked.url,
                        expected_title=title,
                    )
                    if linked_parsed:
                        documents.append(linked_parsed)
                break

    if not documents:
        return {}

    merged: dict[str, Any] = {}
    source_urls: list[str] = []

    for document in documents:
        source_urls.append(document.get("pageUrl", ""))
        for key, value in document.items():
            if key in {"pageUrl", "pageTitle"}:
                continue
            if value not in (None, "", []) and merged.get(key) in (None, "", []):
                merged[key] = value

    merged["source"] = {
        "name": "Manusights",
        "type": "secondary-source",
        "urls": unique_strings(source_urls),
        "retrievedAt": utc_now(),
        "verificationStatus": "secondary-source",
    }
    return merged


def merge_basic_metadata(
    record: dict[str, Any],
    *,
    group: dict[str, Any],
    crossref: dict[str, Any],
    openalex: dict[str, Any],
    manuscripts: dict[str, Any],
) -> dict[str, Any]:
    title = (
        openalex.get("title")
        or crossref.get("title")
        or record.get("title")
        or group["canonicalTitle"]
    )

    aliases = unique_strings(
        [
            *(record.get("aliases") or []),
            *group["aliases"],
            crossref.get("title"),
            openalex.get("title"),
            crossref.get("abbreviation"),
            openalex.get("abbreviation"),
        ]
    )

    all_issns = unique_strings(
        [
            *(record.get("allIssns") or []),
            *(crossref.get("allIssns") or []),
            *(openalex.get("allIssns") or []),
            crossref.get("issn"),
            crossref.get("eissn"),
            openalex.get("issnL"),
            manuscripts.get("issn"),
            manuscripts.get("eissn"),
        ]
    )

    print_issn = (
        crossref.get("issn")
        or manuscripts.get("issn")
        or record.get("issn")
        or (all_issns[0] if all_issns else "")
    )
    eissn = (
        crossref.get("eissn")
        or manuscripts.get("eissn")
        or record.get("eissn")
    )

    publisher = (
        openalex.get("publisher")
        or crossref.get("publisher")
        or manuscripts.get("publisher")
        or group.get("publisherFromPublications")
        or record.get("publisher")
        or ""
    )

    sources = dict(record.get("sources") or {})
    if crossref.get("source"):
        sources["crossref"] = crossref["source"]
    if openalex.get("source"):
        sources["openalex"] = openalex["source"]
    if manuscripts.get("source"):
        sources["manusights"] = manuscripts["source"]

    merged = {
        **record,
        "title": title,
        "abbreviation": (
            openalex.get("abbreviation")
            or crossref.get("abbreviation")
            or record.get("abbreviation")
            or ""
        ),
        "aliases": aliases,
        "publisher": publisher,
        "issn": print_issn,
        "eissn": eissn or "",
        "issnL": openalex.get("issnL") or record.get("issnL") or "",
        "allIssns": all_issns,
        "homepage": openalex.get("homepage") or record.get("homepage") or "",
        "countryCode": openalex.get("countryCode") or record.get("countryCode") or "",
        "journalType": openalex.get("sourceType") or record.get("journalType") or "journal",
        "isOpenAccess": (
            openalex.get("isOpenAccess")
            if "isOpenAccess" in openalex
            else record.get("isOpenAccess")
        ),
        "isInDoaj": (
            openalex.get("isInDoaj")
            if "isInDoaj" in openalex
            else record.get("isInDoaj")
        ),
        "subjects": unique_strings(
            [*(record.get("subjects") or []), *(crossref.get("subjects") or [])]
        ),
        "openAlexId": openalex.get("openAlexId") or record.get("openAlexId") or "",
        "openAlexUrl": openalex.get("openAlexUrl") or record.get("openAlexUrl") or "",
        "openAlexStats": {
            "worksCount": openalex.get("worksCount"),
            "citedByCount": openalex.get("citedByCount"),
            "twoYearMeanCitedness": openalex.get("twoYearMeanCitedness"),
            "hIndex": openalex.get("hIndex"),
            "i10Index": openalex.get("i10Index"),
        },
        "foundedYear": manuscripts.get("foundedYear") or record.get("foundedYear"),
        "publicationCount": group["publicationCount"],
        "publicationYears": group["publicationYears"],
        "firstPublicationYear": group["firstPublicationYear"],
        "latestPublicationYear": group["latestPublicationYear"],
        "sampleDoi": group["sampleDoi"],
        "sources": sources,
    }

    return merged


def merge_metrics(
    record: dict[str, Any],
    manuscripts: dict[str, Any],
) -> dict[str, Any]:
    metrics_by_year = dict(record.get("metricsByYear") or {})
    metric_year = manuscripts.get("metricYear")

    if metric_year and manuscripts.get("impactFactor") is not None:
        year_key = str(metric_year)
        current = dict(metrics_by_year.get(year_key) or {})

        category_record: dict[str, Any] = {}
        if manuscripts.get("category"):
            category_record["name"] = manuscripts["category"]
        if manuscripts.get("bestQuartile"):
            category_record["quartile"] = manuscripts["bestQuartile"]
        if manuscripts.get("categoryRank") is not None:
            category_record["rank"] = manuscripts["categoryRank"]
        if manuscripts.get("categoryJournalCount") is not None:
            category_record["totalJournals"] = manuscripts["categoryJournalCount"]

        current.update(
            {
                "impactFactor": manuscripts.get("impactFactor"),
                "fiveYearImpactFactor": manuscripts.get("fiveYearImpactFactor"),
                "jci": manuscripts.get("jci"),
                "totalCites": manuscripts.get("totalCites"),
                "citeScore": manuscripts.get("citeScore"),
                "bestQuartile": manuscripts.get("bestQuartile"),
                "categories": [category_record] if category_record else [],
                "jcrReleaseYear": manuscripts.get("jcrReleaseYear"),
                "sourceType": "secondary-source",
                "sourceName": "Manusights",
                "sourceUrls": (manuscripts.get("source") or {}).get("urls", []),
                "verificationStatus": "secondary-source",
                "retrievedAt": utc_now(),
            }
        )
        metrics_by_year[year_key] = {
            key: value
            for key, value in current.items()
            if value not in (None, "", [])
        }

    record["metricsByYear"] = dict(
        sorted(metrics_by_year.items(), key=lambda item: item[0])
    )

    years = [as_int(year) for year in record["metricsByYear"]]
    valid_years = [year for year in years if year is not None]
    record["latestMetricYear"] = max(valid_years) if valid_years else None
    return record


def clean_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: clean_nulls(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [clean_nulls(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build and update data/journals.json from data/publications.json, "
            "Crossref, OpenAlex, and public Manusights journal pages."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("missing", "refresh"),
        default="missing",
        help=(
            "missing: remotely enrich new journals only; "
            "refresh: remotely recheck all journals."
        ),
    )
    parser.add_argument(
        "--report",
        default="journal_update_report.json",
        help="Path for a run report. The report is not required by the website.",
    )
    args = parser.parse_args()

    groups = load_publication_groups()
    existing = load_json(
        JOURNALS_PATH,
        default={
            "schemaVersion": 1,
            "sourcePolicy": {
                "basicMetadata": ["Crossref", "OpenAlex", "publication records"],
                "journalMetrics": ["Manusights secondary-source pages"],
                "note": (
                    "Journal Impact Factor and JCR values are secondary-source "
                    "data and should be checked against Clarivate for formal use."
                ),
            },
            "journals": {},
        },
    )

    if not isinstance(existing, dict):
        raise RuntimeError(f"{JOURNALS_PATH} must contain a JSON object.")
    if not isinstance(existing.get("journals"), dict):
        existing["journals"] = {}

    journals: dict[str, Any] = existing["journals"]
    name_index = existing_index(existing)
    used_ids = set(journals)

    report: dict[str, Any] = {
        "generatedAt": utc_now(),
        "mode": args.mode,
        "publicationJournalCount": len(groups),
        "newJournals": [],
        "refreshedJournals": [],
        "metadataOnlyUpdates": [],
        "manusightsNotFound": [],
        "errors": [],
    }

    with build_session() as session:
        for number, (normalized_name, group) in enumerate(
            sorted(groups.items(), key=lambda item: item[1]["canonicalTitle"].casefold()),
            start=1,
        ):
            journal_id = name_index.get(normalized_name)
            is_new = journal_id is None

            if is_new:
                journal_id = make_journal_id(group["canonicalTitle"], used_ids)
                record: dict[str, Any] = {
                    "journalId": journal_id,
                    "title": group["canonicalTitle"],
                    "aliases": group["aliases"],
                    "metricsByYear": {},
                }
                report["newJournals"].append(group["canonicalTitle"])
            else:
                record = dict(journals.get(journal_id) or {})

            should_fetch_remote = is_new or args.mode == "refresh"
            crossref: dict[str, Any] = {}
            openalex: dict[str, Any] = {}
            manuscripts: dict[str, Any] = {}

            print(
                f"[{number}/{len(groups)}] {group['canonicalTitle']} "
                f"({'new' if is_new else 'existing'}; "
                f"{'remote refresh' if should_fetch_remote else 'local statistics only'})"
            )

            if should_fetch_remote:
                crossref = crossref_metadata(session, group["sampleDoi"])
                known_issns = unique_strings(
                    [
                        *(record.get("allIssns") or []),
                        *(crossref.get("allIssns") or []),
                        crossref.get("issn"),
                        crossref.get("eissn"),
                    ]
                )
                candidates = openalex_candidates(
                    session,
                    title=group["canonicalTitle"],
                    issns=known_issns,
                )
                source = select_openalex_source(
                    candidates,
                    title=group["canonicalTitle"],
                    issns=known_issns,
                )
                openalex = openalex_metadata(source)
                manuscripts = manuscripts_metadata(
                    session,
                    openalex.get("title")
                    or crossref.get("title")
                    or group["canonicalTitle"],
                )

                if manuscripts:
                    report["refreshedJournals"].append(group["canonicalTitle"])
                else:
                    report["manusightsNotFound"].append(group["canonicalTitle"])
            else:
                report["metadataOnlyUpdates"].append(group["canonicalTitle"])

            record = merge_basic_metadata(
                record,
                group=group,
                crossref=crossref,
                openalex=openalex,
                manuscripts=manuscripts,
            )
            record = merge_metrics(record, manuscripts)
            record["journalId"] = journal_id
            journals[journal_id] = clean_nulls(record)
            name_index[normalized_name] = journal_id

    active_ids = {
        name_index[normalized]
        for normalized in groups
        if normalized in name_index
    }

    for journal_id, record in journals.items():
        if isinstance(record, dict):
            record["currentlyUsedInPublications"] = journal_id in active_ids

    existing["schemaVersion"] = 1
    existing["lastUpdated"] = utc_now()
    existing["journalCount"] = len(journals)
    existing["activeJournalCount"] = len(active_ids)
    existing["journals"] = dict(
        sorted(
            journals.items(),
            key=lambda item: compact_whitespace(
                (item[1] or {}).get("title")
            ).casefold(),
        )
    )

    write_json_atomic(JOURNALS_PATH, clean_nulls(existing))
    write_json_atomic(Path(args.report), clean_nulls(report))

    print(f"Saved {len(journals)} journal records to {JOURNALS_PATH}.")
    print(
        f"New: {len(report['newJournals'])}; "
        f"Manusights matched: {len(report['refreshedJournals'])}; "
        f"Manusights not found: {len(report['manusightsNotFound'])}."
    )


if __name__ == "__main__":
    main()
