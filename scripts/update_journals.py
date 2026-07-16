from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PUBLICATIONS_PATH = Path("data/publications.json")
JOURNALS_PATH = Path("data/journals.json")

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
OPENALEX_SOURCES_URL = "https://api.openalex.org/sources"
JOURNALMETRICS_BASE_URL = "https://www.journalmetrics.org"
BIOXBIO_BASE_URL = "https://www.bioxbio.com"
MANUSIGHTS_BASE_URL = "https://manusights.com"
JOURNALSEARCHES_URL = "https://journalsearches.com/journal.php"

CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "weihao.chiu@gmail.com").strip()
OPENALEX_API_KEY = os.environ.get("OPENALEX_API_KEY", "").strip()
REQUEST_DELAY_SECONDS = 0.55
USER_AGENT = (
    "Wei-Hao-Chiu-Academic-Website/2.0 "
    f"(journal metadata updater; mailto:{CONTACT_EMAIL})"
)

SOURCE_PRIORITY = {
    "JournalMetrics.org": 100,
    "Bioxbio": 90,
    "Manusights": 80,
    "JournalSearches": 60,
    "existing": 10,
}


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compact_whitespace(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def ascii_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", compact_whitespace(value))
    return "".join(
        character for character in text if not unicodedata.combining(character)
    )


def normalize_name(value: Any) -> str:
    text = ascii_text(value).lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "", text)


def slugify(value: Any) -> str:
    text = ascii_text(value).lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "journal"


def normalize_doi(value: Any) -> str:
    text = compact_whitespace(value).lower()
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    ):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return text.strip()


def normalize_issn(value: Any) -> str:
    """Normalize and validate an ISSN using the official modulo-11 checksum."""
    text = re.sub(r"[^0-9Xx]", "", compact_whitespace(value)).upper()
    if len(text) != 8 or not text[:7].isdigit():
        return ""

    checksum_value = 10 if text[7] == "X" else int(text[7]) if text[7].isdigit() else -1
    weighted_sum = sum(int(digit) * weight for digit, weight in zip(text[:7], range(8, 1, -1)))
    expected = (11 - weighted_sum % 11) % 11
    if checksum_value != expected:
        return ""
    return f"{text[:4]}-{text[4:]}"


def valid_issns(values: list[Any]) -> list[str]:
    return unique_strings([normalized for value in values if (normalized := normalize_issn(value))])


def labeled_issns(text: Any) -> dict[str, str]:
    """Extract only explicitly labelled ISSN fields, not every ISSN-like token on a page."""
    source = compact_whitespace(text)
    patterns = {
        "eissn": [
            r"\bE-?ISSN\b\s*[:：]?\s*(\d{4}-?[\dXx]{4})",
            r"\bOnline ISSN\b\s*[:：]?\s*(\d{4}-?[\dXx]{4})",
            r"\bElectronic ISSN\b\s*[:：]?\s*(\d{4}-?[\dXx]{4})",
        ],
        "issn": [
            r"\bPrint ISSN\b\s*[:：]?\s*(\d{4}-?[\dXx]{4})",
            r"(?<!E-)(?<!E)(?<!Online )(?<!Electronic )\bISSN\b\s*[:：]?\s*(\d{4}-?[\dXx]{4})",
        ],
    }
    output: dict[str, str] = {}
    for key, candidates in patterns.items():
        for pattern in candidates:
            match = re.search(pattern, source, flags=re.IGNORECASE)
            if match and (value := normalize_issn(match.group(1))):
                output[key] = value
                break
    return output


def clean_publisher(value: Any) -> str:
    """Keep short organization names and reject scraped explanatory paragraphs."""
    text = compact_whitespace(value)
    if not text:
        return ""

    # Some pages append prose immediately after the publisher name.
    markers = [
        r"\s+Official\s+[^.]{0,80}?profile\b",
        r"\s+The\s+[0-9]+(?:\.[0-9]+)?\s+JIF\b",
        r"\s+The\s+[0-9]+(?:\.[0-9]+)?\s+Impact Factor\b",
        r"\s+The\s+[0-9]+(?:\.[0-9]+)?\s+CiteScore\b",
        r"\s+Is this the exact\b",
        r"\s+The exact journal identifier\b",
    ]
    for marker in markers:
        match = re.search(marker, text, flags=re.IGNORECASE)
        if match:
            text = text[:match.start()].strip(" ,;:-")
            break

    lowered = text.casefold()
    rejected_phrases = (
        "impact factor",
        "citescore",
        "quality score",
        "individual authors",
        "laboratories",
        "journal-level",
        "citation-window",
        "published scope",
        "exact journal record",
    )
    if len(text) > 120 or any(phrase in lowered for phrase in rejected_phrases):
        return ""
    if not re.search(r"[A-Za-z]", text):
        return ""
    return text


def clean_subject(value: Any) -> str:
    text = compact_whitespace(value)
    if not text or len(text) > 180:
        return ""
    if any(token in text.casefold() for token in ("impact factor", "citescore", "submit your", "exact journal")):
        return ""
    return text


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


def similarity(left: Any, right: Any) -> float:
    left_normalized = normalize_name(left)
    right_normalized = normalize_name(right)
    if not left_normalized or not right_normalized:
        return 0.0
    if left_normalized == right_normalized:
        return 1.0
    return SequenceMatcher(None, left_normalized, right_normalized).ratio()


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


def semantic_copy(payload: Any) -> Any:
    """Remove volatile timestamps before deciding whether data changed."""
    if isinstance(payload, dict):
        return {
            key: semantic_copy(value)
            for key, value in payload.items()
            if key not in {"lastUpdated", "retrievedAt", "lastCheckedAt"}
        }
    if isinstance(payload, list):
        return [semantic_copy(value) for value in payload]
    return payload


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
    timeout: int = 50,
) -> requests.Response | None:
    try:
        response = session.get(url, params=params, timeout=timeout)
        if response.status_code in {403, 404, 410}:
            return None
        response.raise_for_status()
        return response
    except requests.RequestException as error:
        print(f"WARNING: request failed: {url}: {error}")
        return None
    finally:
        time.sleep(REQUEST_DELAY_SECONDS)


def source_info(name: str, url: str, **extra: Any) -> dict[str, Any]:
    return clean_nulls(
        {
            "name": name,
            "url": url,
            "type": "secondary-source",
            "verificationStatus": "secondary-source",
            "retrievedAt": utc_now(),
            **extra,
        }
    )


def merge_source_snapshot(
    existing_sources: dict[str, Any],
    key: str,
    new_source: dict[str, Any] | None,
) -> None:
    if not new_source:
        return
    previous = existing_sources.get(key)
    if previous and semantic_copy(previous) == semantic_copy(new_source):
        return
    existing_sources[key] = new_source


# ---------------------------------------------------------------------------
# Publication-derived journal list
# ---------------------------------------------------------------------------

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

    for group in groups.values():
        title_counts = Counter(group["titleCandidates"])
        canonical_title = sorted(
            title_counts,
            key=lambda item: (-title_counts[item], -len(item), item.casefold()),
        )[0]
        years = sorted(set(group["years"]))
        dois = unique_strings(group["dois"])
        publishers = unique_strings(group["publishers"])
        group.update(
            {
                "canonicalTitle": canonical_title,
                "aliases": unique_strings(group["titleCandidates"]),
                "publisherFromPublications": publishers[0] if publishers else "",
                "publicationCount": len(group["titleCandidates"]),
                "publicationYears": years,
                "firstPublicationYear": years[0] if years else None,
                "latestPublicationYear": years[-1] if years else None,
                "sampleDoi": dois[0] if dois else "",
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
        for name in [record.get("title"), *(record.get("aliases") or [])]:
            normalized = normalize_name(name)
            if normalized:
                index[normalized] = journal_id
    return index


# ---------------------------------------------------------------------------
# Crossref and OpenAlex basic metadata
# ---------------------------------------------------------------------------

def crossref_metadata(session: requests.Session, doi: str) -> dict[str, Any]:
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

    print_issn = ""
    electronic_issn = ""
    for item in message.get("issn-type") or []:
        if not isinstance(item, dict):
            continue
        value = normalize_issn(item.get("value"))
        item_type = compact_whitespace(item.get("type")).lower()
        if item_type == "print" and value:
            print_issn = value
        elif item_type == "electronic" and value:
            electronic_issn = value

    return {
        "title": compact_whitespace((message.get("container-title") or [""])[0]),
        "abbreviation": compact_whitespace(
            (message.get("short-container-title") or [""])[0]
        ),
        "publisher": compact_whitespace(message.get("publisher")),
        "issn": print_issn,
        "eissn": electronic_issn,
        "allIssns": unique_strings(
            [normalize_issn(value) for value in (message.get("ISSN") or [])]
        ),
        "subjects": unique_strings(message.get("subject") or []),
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
    params: dict[str, Any] = {"per-page": 10}
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    elif CONTACT_EMAIL:
        params["mailto"] = CONTACT_EMAIL

    for issn in issns:
        response = safe_get(
            session,
            OPENALEX_SOURCES_URL,
            params={**params, "filter": f"issn:{issn}"},
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
        params={**params, "search": title},
    )
    if response is None:
        return []
    try:
        return [
            item for item in response.json().get("results", [])
            if isinstance(item, dict)
        ]
    except ValueError:
        return []


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
        score = similarity(title, candidate.get("display_name", ""))
        if normalized_issns & candidate_issns:
            score += 1.0
        scored.append((score, candidate))
    if not scored:
        return None
    score, best = max(scored, key=lambda item: item[0])
    return best if score >= 0.72 else None


def openalex_metadata(source: dict[str, Any] | None) -> dict[str, Any]:
    if not source:
        return {}
    summary = source.get("summary_stats") or {}
    publisher = compact_whitespace(source.get("host_organization_name"))
    if not publisher:
        lineage = source.get("host_organization_lineage_names") or []
        publisher = compact_whitespace(lineage[-1]) if lineage else ""
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
        "publisher": publisher,
        "countryCode": compact_whitespace(source.get("country_code")),
        "sourceType": compact_whitespace(source.get("type")),
        "isOpenAccess": bool(source.get("is_oa")),
        "isInDoaj": bool(source.get("is_in_doaj")),
        "worksCount": as_int(source.get("works_count")),
        "citedByCount": as_int(source.get("cited_by_count")),
        "twoYearMeanCitedness": as_float(summary.get("2yr_mean_citedness")),
        "hIndex": as_int(summary.get("h_index")),
        "i10Index": as_int(summary.get("i10_index")),
        "source": {
            "name": "OpenAlex Sources API",
            "url": compact_whitespace(source.get("id")),
            "retrievedAt": utc_now(),
        },
    }


# ---------------------------------------------------------------------------
# Metric source 1: JournalMetrics.org (primary current JIF/JCR source)
# ---------------------------------------------------------------------------

def journalmetrics_url(title: str) -> str:
    return f"{JOURNALMETRICS_BASE_URL}/{slugify(title)}-impact-factor"


def parse_journalmetrics_document(
    html: str,
    *,
    page_url: str,
    expected_title: str,
    expected_issns: list[str],
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    heading = compact_whitespace(
        soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else ""
    )
    text = compact_whitespace(soup.get_text(" ", strip=True))
    labelled = labeled_issns(text)
    page_issns = valid_issns([labelled.get("issn"), labelled.get("eissn")])
    issn_match = bool(set(expected_issns) & set(page_issns))
    if similarity(expected_title, heading) < 0.42 and not issn_match:
        return {}

    release_match = re.search(
        r"newest impact factor is\s*([0-9]+(?:\.[0-9]+)?),\s*"
        r"released\s+([A-Za-z]+\s+\d{1,2},\s+(20\d{2}))\s+"
        r"and based on\s+(20\d{2})\s+citation data",
        text,
        flags=re.IGNORECASE,
    )
    impact_factor = as_float(release_match.group(1)) if release_match else None
    release_date = compact_whitespace(release_match.group(2)) if release_match else ""
    release_year = as_int(release_match.group(3)) if release_match else None
    metric_year = as_int(release_match.group(4)) if release_match else None

    if impact_factor is None:
        match = re.search(
            r"(?:Impact Factor|newest impact factor)\s*(?:is|:)\s*"
            r"([0-9]+(?:\.[0-9]+)?)",
            text,
            flags=re.IGNORECASE,
        )
        impact_factor = as_float(match.group(1)) if match else None

    if release_year is None:
        match = re.search(r"\b(20\d{2})\s+Impact Factor\b", heading, re.I)
        release_year = as_int(match.group(1)) if match else None
    if metric_year is None and release_year:
        metric_year = release_year - 1

    quartile_match = re.search(r"\bJCR\s+(Q[1-4])\b", text, re.I)
    quartile = quartile_match.group(1).upper() if quartile_match else None

    category = ""
    if quartile_match:
        tail = text[quartile_match.end():]
        category_match = re.match(
            r"\s*([^|]{3,120}?)(?=\s+(?:CAS:|Nature is|Compare |About |Publisher:))",
            tail,
            flags=re.IGNORECASE,
        )
        category = compact_whitespace(category_match.group(1)) if category_match else ""

    publisher_match = re.search(
        r"Publisher:\s*(.+?)(?=\s+Founded:|\s+Frequency:|\s+ISSN:)",
        text,
        flags=re.IGNORECASE,
    )
    founded_match = re.search(r"Founded:\s*(\d{4})", text, re.I)
    frequency_match = re.search(
        r"Frequency:\s*(.+?)(?=\s+ISSN:|\s+Subject Areas:|\s+Language:)",
        text,
        re.I,
    )
    subject_match = re.search(
        r"Subject Areas:\s*(.+?)(?=\s+Language:|\s+Why |\s+About )",
        text,
        re.I,
    )

    if impact_factor is None or metric_year is None:
        return {}

    fields: dict[str, Any] = {"impactFactor": impact_factor}
    if quartile:
        fields["bestQuartile"] = quartile
    if release_year:
        fields["jcrReleaseYear"] = release_year
    if release_date:
        fields["releaseDate"] = release_date

    category_record: dict[str, Any] = {}
    if category:
        category_record["name"] = category
    if quartile:
        category_record["quartile"] = quartile

    return clean_nulls(
        {
            "title": expected_title,
            "issn": page_issns[0] if page_issns else "",
            "publisher": clean_publisher(publisher_match.group(1)) if publisher_match else "",
            "foundedYear": as_int(founded_match.group(1)) if founded_match else None,
            "frequency": compact_whitespace(frequency_match.group(1)) if frequency_match else "",
            "subjects": [clean_subject(subject_match.group(1))] if subject_match and clean_subject(subject_match.group(1)) else [],
            "metricCandidates": [
                {
                    "metricYear": metric_year,
                    "fields": fields,
                    "categories": [category_record] if category_record else [],
                    "source": source_info(
                        "JournalMetrics.org",
                        page_url,
                        priority=SOURCE_PRIORITY["JournalMetrics.org"],
                    ),
                }
            ],
            "source": source_info(
                "JournalMetrics.org",
                page_url,
                priority=SOURCE_PRIORITY["JournalMetrics.org"],
            ),
        }
    )


def journalmetrics_metadata(
    session: requests.Session,
    *,
    title: str,
    issns: list[str],
) -> dict[str, Any]:
    url = journalmetrics_url(title)
    response = safe_get(session, url)
    if response is None:
        return {}
    return parse_journalmetrics_document(
        response.text,
        page_url=response.url,
        expected_title=title,
        expected_issns=issns,
    )


# ---------------------------------------------------------------------------
# Metric source 2: Bioxbio (historical JIF series)
# ---------------------------------------------------------------------------

def bioxbio_tokens(title: str, abbreviation: str) -> list[str]:
    candidates: list[str] = []
    abbreviation_map = {
        "advanced": "ADV",
        "applied": "APPL",
        "chemical": "CHEM",
        "chemistry": "CHEM",
        "communications": "COMMUN",
        "engineering": "ENG",
        "energy": "ENERG",
        "environmental": "ENVIRON",
        "functional": "FUNCT",
        "international": "INT",
        "journal": "J",
        "materials": "MATER",
        "nanotechnology": "NANOTECHNOL",
        "organic": "ORG",
        "physical": "PHYS",
        "physics": "PHYS",
        "power": "POWER",
        "purification": "PURIF",
        "research": "RES",
        "reviews": "REV",
        "science": "SCI",
        "separation": "SEP",
        "solar": "SOL",
        "technology": "TECHNOL",
    }

    for value in [abbreviation, title]:
        token = re.sub(r"[^A-Za-z0-9]+", "-", ascii_text(value).upper()).strip("-")
        if token:
            candidates.append(token)

    title_words = re.findall(r"[A-Za-z0-9]+", ascii_text(title).lower())
    if title_words:
        compact_token = "-".join(
            abbreviation_map.get(word, word.upper()) for word in title_words
        )
        candidates.insert(0, compact_token)

    return unique_strings(candidates)


def parse_bioxbio_document(
    html: str,
    *,
    page_url: str,
    expected_title: str,
    expected_issns: list[str],
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    heading = compact_whitespace(
        soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else ""
    )
    text = compact_whitespace(soup.get_text(" ", strip=True))
    issn_match = re.search(r"Journal ISSN:\s*(\d{4}-[\dXx]{4})", text, re.I)
    page_issn = normalize_issn(issn_match.group(1)) if issn_match else ""
    if similarity(expected_title, heading) < 0.42 and page_issn not in expected_issns:
        return {}

    abbreviation_match = re.search(
        r"Journal Abbreviation:\s*(.+?)(?=\s+Journal ISSN:)", text, re.I
    )
    candidates: list[dict[str, Any]] = []

    for row in soup.find_all("tr"):
        cells = [compact_whitespace(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        if len(cells) < 2:
            continue
        year_match = re.match(
            r"^(20\d{2})(?:\s*\((20\d{2})\s+update\))?$",
            cells[0],
            flags=re.IGNORECASE,
        )
        if not year_match:
            continue
        metric_year = as_int(year_match.group(1))
        release_year = as_int(year_match.group(2)) if year_match.group(2) else None
        impact_factor = as_float(cells[1])
        if metric_year is None or impact_factor is None:
            continue
        total_articles = as_int(cells[2]) if len(cells) > 2 and cells[2] != "-" else None
        total_cites = as_int(cells[3]) if len(cells) > 3 and cells[3] != "-" else None
        fields: dict[str, Any] = {"impactFactor": impact_factor}
        if total_articles is not None:
            fields["totalArticles"] = total_articles
        if total_cites is not None:
            fields["totalCites"] = total_cites
        if release_year is not None:
            fields["jcrReleaseYear"] = release_year
        candidates.append(
            {
                "metricYear": metric_year,
                "fields": fields,
                "source": source_info(
                    "Bioxbio",
                    page_url,
                    priority=SOURCE_PRIORITY["Bioxbio"],
                ),
            }
        )

    if not candidates:
        # Fallback for pages whose table markup is flattened unusually.
        pattern = re.compile(
            r"\b(20\d{2})(?:\s*\((20\d{2})\s+update\))?\s+"
            r"([0-9]+(?:\.[0-9]+)?)\s+(-|[0-9,]+)\s+(-|[0-9,]+)"
        )
        for match in pattern.finditer(text):
            fields = {"impactFactor": as_float(match.group(3))}
            articles = as_int(match.group(4)) if match.group(4) != "-" else None
            cites = as_int(match.group(5)) if match.group(5) != "-" else None
            if articles is not None:
                fields["totalArticles"] = articles
            if cites is not None:
                fields["totalCites"] = cites
            release_year = as_int(match.group(2))
            if release_year:
                fields["jcrReleaseYear"] = release_year
            candidates.append(
                {
                    "metricYear": as_int(match.group(1)),
                    "fields": fields,
                    "source": source_info(
                        "Bioxbio",
                        page_url,
                        priority=SOURCE_PRIORITY["Bioxbio"],
                    ),
                }
            )

    if not candidates:
        return {}

    return clean_nulls(
        {
            "title": heading,
            "abbreviation": compact_whitespace(abbreviation_match.group(1)) if abbreviation_match else "",
            "issn": page_issn,
            "metricCandidates": candidates,
            "source": source_info(
                "Bioxbio",
                page_url,
                priority=SOURCE_PRIORITY["Bioxbio"],
            ),
        }
    )


def bioxbio_metadata(
    session: requests.Session,
    *,
    title: str,
    abbreviation: str,
    issns: list[str],
) -> dict[str, Any]:
    for token in bioxbio_tokens(title, abbreviation):
        url = f"{BIOXBIO_BASE_URL}/journal/{token}"
        response = safe_get(session, url)
        if response is None:
            continue
        parsed = parse_bioxbio_document(
            response.text,
            page_url=response.url,
            expected_title=title,
            expected_issns=issns,
        )
        if parsed:
            return parsed
    return {}


# ---------------------------------------------------------------------------
# Metric source 3: Manusights (five-year JIF/JCI/rank backup)
# ---------------------------------------------------------------------------

def manusights_urls(title: str) -> list[str]:
    slug = slugify(title)
    return [
        f"{MANUSIGHTS_BASE_URL}/journals/{slug}",
        f"{MANUSIGHTS_BASE_URL}/blog/{slug}-impact-factor",
    ]


def parse_manusights_document(
    html: str,
    *,
    page_url: str,
    expected_title: str,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    heading = compact_whitespace(
        soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else ""
    )
    text = compact_whitespace(soup.get_text(" ", strip=True))
    if similarity(expected_title, heading) < 0.38:
        return {}

    quick = re.search(
        r"has a\s+(20\d{2})\s+Journal Impact Factor of\s*"
        r"([0-9]+(?:\.[0-9]+)?)\s+in the\s+(20\d{2})\s+"
        r"Journal Citation Reports release,\s+with a\s+five-year JIF of\s*"
        r"([0-9]+(?:\.[0-9]+)?),\s*(Q[1-4])\s+status,\s+and a\s+"
        r"(\d+)\s*/\s*(\d+)\s+rank in\s+(.+?)\.",
        text,
        flags=re.IGNORECASE,
    )

    metric_year = as_int(quick.group(1)) if quick else None
    impact_factor = as_float(quick.group(2)) if quick else None
    release_year = as_int(quick.group(3)) if quick else None
    five_year_if = as_float(quick.group(4)) if quick else None
    quartile = quick.group(5).upper() if quick else None
    rank = as_int(quick.group(6)) if quick else None
    total_journals = as_int(quick.group(7)) if quick else None
    category = compact_whitespace(quick.group(8)) if quick else ""

    if impact_factor is None:
        match = re.search(
            rf"{re.escape(expected_title)}(?:'s)?\s+impact factor is\s*"
            r"([0-9]+(?:\.[0-9]+)?)",
            text,
            flags=re.IGNORECASE,
        )
        impact_factor = as_float(match.group(1)) if match else None
    if impact_factor is None:
        match = re.search(
            r"Impact factor\s*([0-9]+(?:\.[0-9]+)?)\s+Current JIF",
            text,
            flags=re.IGNORECASE,
        )
        impact_factor = as_float(match.group(1)) if match else None

    if five_year_if is None:
        match = re.search(
            r"Five-year impact factor:\s*([0-9]+(?:\.[0-9]+)?)",
            text,
            re.I,
        )
        five_year_if = as_float(match.group(1)) if match else None

    if metric_year is None:
        match = re.search(r"\b(20\d{2})\s+Journal Impact Factor of\b", text, re.I)
        metric_year = as_int(match.group(1)) if match else None
    if release_year is None:
        match = re.search(r"\b(20\d{2})\s+Journal Citation Reports release\b", text, re.I)
        release_year = as_int(match.group(1)) if match else None
    if metric_year is None and release_year:
        metric_year = release_year - 1

    if quartile is None:
        match = re.search(r"\b(Q[1-4])\s+status\b", text, re.I)
        quartile = match.group(1).upper() if match else None
    if rank is None or total_journals is None:
        match = re.search(r"\b(\d+)\s*/\s*(\d+)\s+rank in\s+(.+?)(?:\.|,)", text, re.I)
        if match:
            rank = as_int(match.group(1))
            total_journals = as_int(match.group(2))
            category = compact_whitespace(match.group(3))

    jci_match = re.search(r"\bJCI(?:\s*\([^)]*\))?\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
    total_cites_match = re.search(r"\bTotal Cites(?:\s*\([^)]*\))?\s*([0-9,]+)", text, re.I)
    citescore_match = re.search(r"\bCiteScore\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
    publisher_match = re.search(
        r"\bPublisher\s+(.+?)(?=\s+(?:Founded|ISSN|Publication|Open access|Article Types)\b)",
        text,
        re.I,
    )
    issn_match = re.search(r"\bISSN\s+(\d{4}-[\dXx]{4})\b", text, re.I)
    eissn_match = re.search(r"\b(?:E-?ISSN|Online ISSN)\s+(\d{4}-[\dXx]{4})\b", text, re.I)
    founded_match = re.search(r"\bFounded\s+(\d{4})\b", text, re.I)

    fields: dict[str, Any] = {}
    for key, value in {
        "impactFactor": impact_factor,
        "fiveYearImpactFactor": five_year_if,
        "jci": as_float(jci_match.group(1)) if jci_match else None,
        "totalCites": as_int(total_cites_match.group(1)) if total_cites_match else None,
        "citeScore": as_float(citescore_match.group(1)) if citescore_match else None,
        "bestQuartile": quartile,
        "jcrReleaseYear": release_year,
    }.items():
        if value is not None:
            fields[key] = value

    category_record: dict[str, Any] = {}
    if category:
        category_record["name"] = category
    if quartile:
        category_record["quartile"] = quartile
    if rank is not None:
        category_record["rank"] = rank
    if total_journals is not None:
        category_record["totalJournals"] = total_journals

    if not fields or metric_year is None:
        return {}

    return clean_nulls(
        {
            "publisher": clean_publisher(publisher_match.group(1)) if publisher_match else "",
            "issn": normalize_issn(issn_match.group(1)) if issn_match else "",
            "eissn": normalize_issn(eissn_match.group(1)) if eissn_match else "",
            "foundedYear": as_int(founded_match.group(1)) if founded_match else None,
            "metricCandidates": [
                {
                    "metricYear": metric_year,
                    "fields": fields,
                    "categories": [category_record] if category_record else [],
                    "source": source_info(
                        "Manusights",
                        page_url,
                        priority=SOURCE_PRIORITY["Manusights"],
                    ),
                }
            ],
            "source": source_info(
                "Manusights",
                page_url,
                priority=SOURCE_PRIORITY["Manusights"],
            ),
        }
    )


def manusights_metadata(session: requests.Session, *, title: str) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    for url in manusights_urls(title):
        response = safe_get(session, url)
        if response is None:
            continue
        parsed = parse_manusights_document(
            response.text,
            page_url=response.url,
            expected_title=title,
        )
        if parsed:
            documents.append(parsed)
    if not documents:
        return {}

    result: dict[str, Any] = {"metricCandidates": []}
    source_urls: list[str] = []
    for document in documents:
        result["metricCandidates"].extend(document.get("metricCandidates") or [])
        for key in ["publisher", "issn", "eissn", "foundedYear"]:
            if result.get(key) in (None, "") and document.get(key) not in (None, ""):
                result[key] = document[key]
        source_urls.append((document.get("source") or {}).get("url", ""))
    result["source"] = source_info(
        "Manusights",
        source_urls[0] if source_urls else manusights_urls(title)[0],
        urls=unique_strings(source_urls),
        priority=SOURCE_PRIORITY["Manusights"],
    )
    return clean_nulls(result)


# ---------------------------------------------------------------------------
# Metric source 4: JournalSearches (last-resort IF/basic/Scopus metadata)
# ---------------------------------------------------------------------------

def parse_journalsearches_document(
    html: str,
    *,
    page_url: str,
    expected_title: str,
    expected_issns: list[str],
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    heading = compact_whitespace(
        soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else ""
    )
    text = compact_whitespace(soup.get_text(" ", strip=True))
    labelled = labeled_issns(text)
    page_issns = valid_issns([labelled.get("issn"), labelled.get("eissn")])
    if similarity(expected_title, heading) < 0.42 and not (set(page_issns) & set(expected_issns)):
        return {}

    release_match = re.search(r"Impact Factor(?:[^0-9]{0,80})(20\d{2})", heading, re.I)
    if release_match is None:
        release_match = re.search(r"\((20\d{2})\)\s*$", heading)
    release_year = as_int(release_match.group(1)) if release_match else None
    metric_year = release_year - 1 if release_year else None
    if_match = re.search(r"\bImpact Factor:\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
    impact_factor = as_float(if_match.group(1)) if if_match else None
    five_match = re.search(r"\b5-Year JIF:\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
    five_year_if = as_float(five_match.group(1)) if five_match else None

    publisher_match = re.search(r"Journal Title:\s*.+?\s+Publisher:\s*(.+?)\s+ISSN:", text, re.I)
    scope_match = re.search(r"Journal Scope:\s*(.+?)\s+Country of Publisher:", text, re.I)
    country_match = re.search(r"Country of Publisher:\s*(.+?)\s+Scopus CiteScore:", text, re.I)
    citescore_match = re.search(r"Scopus CiteScore:\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
    hindex_match = re.search(r"H-Index:\s*([0-9,]+)", text, re.I)
    sjr_match = re.search(r"SJR:\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
    quartile_match = re.search(r"Quartile:\s*(?:[^()]{0,120}\()?\s*(Q[1-4])\)?", text, re.I)
    open_access_match = re.search(r"Open Access:\s*(Yes|No)", text, re.I)

    metric_candidates: list[dict[str, Any]] = []
    if impact_factor is not None and metric_year is not None:
        fields: dict[str, Any] = {"impactFactor": impact_factor, "jcrReleaseYear": release_year}
        if five_year_if is not None:
            fields["fiveYearImpactFactor"] = five_year_if
        metric_candidates.append(
            {
                "metricYear": metric_year,
                "fields": fields,
                "source": source_info(
                    "JournalSearches",
                    page_url,
                    priority=SOURCE_PRIORITY["JournalSearches"],
                    note="Backup JIF source; quartile is stored separately as Scopus quartile.",
                ),
            }
        )

    scopus: dict[str, Any] = {}
    if citescore_match:
        scopus["citeScore"] = as_float(citescore_match.group(1))
    if hindex_match:
        scopus["hIndex"] = as_int(hindex_match.group(1))
    if sjr_match:
        scopus["sjr"] = as_float(sjr_match.group(1))
    if quartile_match:
        scopus["quartile"] = quartile_match.group(1).upper()
    if release_year:
        scopus["releaseYear"] = release_year
    if scopus:
        scopus["source"] = source_info(
            "JournalSearches",
            page_url,
            priority=SOURCE_PRIORITY["JournalSearches"],
            metricSystem="Scopus/SCImago",
        )

    return clean_nulls(
        {
            "publisher": clean_publisher(publisher_match.group(1)) if publisher_match else "",
            "issn": labelled.get("issn", ""),
            "eissn": labelled.get("eissn", ""),
            "issns": page_issns,
            "subjects": [clean_subject(scope_match.group(1))] if scope_match and clean_subject(scope_match.group(1)) else [],
            "country": compact_whitespace(country_match.group(1)) if country_match else "",
            "isOpenAccess": open_access_match.group(1).lower() == "yes" if open_access_match else None,
            "metricCandidates": metric_candidates,
            "scopusLatest": scopus,
            "source": source_info(
                "JournalSearches",
                page_url,
                priority=SOURCE_PRIORITY["JournalSearches"],
            ),
        }
    )


def journalsearches_metadata(
    session: requests.Session,
    *,
    title: str,
    issns: list[str],
) -> dict[str, Any]:
    response = safe_get(session, JOURNALSEARCHES_URL, params={"title": title})
    if response is None:
        return {}
    return parse_journalsearches_document(
        response.text,
        page_url=response.url,
        expected_title=title,
        expected_issns=issns,
    )


# ---------------------------------------------------------------------------
# Merge rules and reporting
# ---------------------------------------------------------------------------

def metric_source_priority(source: Any) -> int:
    if isinstance(source, dict):
        explicit = as_int(source.get("priority"))
        if explicit is not None:
            return explicit
        return SOURCE_PRIORITY.get(compact_whitespace(source.get("name")), 0)
    return 0


def merge_categories(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    overwrite: bool,
) -> list[dict[str, Any]]:
    if incoming and overwrite:
        return clean_nulls(incoming)
    if not incoming:
        return existing
    output = [dict(item) for item in existing if isinstance(item, dict)]
    index = {normalize_name(item.get("name")): item for item in output if item.get("name")}
    for item in incoming:
        if not isinstance(item, dict):
            continue
        key = normalize_name(item.get("name"))
        if key and key in index:
            for field, value in item.items():
                if value not in (None, "") and index[key].get(field) in (None, ""):
                    index[key][field] = value
        else:
            output.append(dict(item))
    return clean_nulls(output)


def apply_metric_candidate(
    metrics_by_year: dict[str, Any],
    candidate: dict[str, Any],
    report_conflicts: list[dict[str, Any]],
    journal_title: str,
) -> None:
    metric_year = as_int(candidate.get("metricYear"))
    if metric_year is None:
        return
    year_key = str(metric_year)
    entry = dict(metrics_by_year.get(year_key) or {})
    field_sources = dict(entry.get("fieldSources") or {})
    incoming_source = dict(candidate.get("source") or {})
    incoming_priority = metric_source_priority(incoming_source)

    for field, incoming_value in (candidate.get("fields") or {}).items():
        if incoming_value in (None, ""):
            continue
        current_value = entry.get(field)
        current_source = field_sources.get(field) or {
            "name": entry.get("sourceName", "existing"),
            "priority": SOURCE_PRIORITY["existing"],
        }
        current_priority = metric_source_priority(current_source)

        if current_value not in (None, "") and current_value != incoming_value:
            report_conflicts.append(
                {
                    "journal": journal_title,
                    "metricYear": metric_year,
                    "field": field,
                    "existingValue": current_value,
                    "existingSource": current_source.get("name", "existing"),
                    "incomingValue": incoming_value,
                    "incomingSource": incoming_source.get("name", "unknown"),
                    "selectedSource": (
                        incoming_source.get("name", "unknown")
                        if incoming_priority >= current_priority
                        else current_source.get("name", "existing")
                    ),
                }
            )

        if current_value in (None, "") or incoming_priority >= current_priority:
            if current_value != incoming_value:
                entry[field] = incoming_value
                field_sources[field] = incoming_source
            elif field not in field_sources:
                field_sources[field] = incoming_source

    incoming_categories = candidate.get("categories") or []
    category_source = field_sources.get("categories") or {}
    category_overwrite = incoming_priority >= metric_source_priority(category_source)
    if incoming_categories:
        old_categories = entry.get("categories") or []
        merged = merge_categories(
            old_categories,
            incoming_categories,
            overwrite=category_overwrite,
        )
        if merged != old_categories:
            entry["categories"] = merged
            field_sources["categories"] = incoming_source

    entry["fieldSources"] = field_sources
    entry["verificationStatus"] = "secondary-source"
    metrics_by_year[year_key] = clean_nulls(entry)


def merge_basic_metadata(
    record: dict[str, Any],
    *,
    group: dict[str, Any],
    crossref: dict[str, Any],
    openalex: dict[str, Any],
    source_documents: list[dict[str, Any]],
) -> dict[str, Any]:
    document_titles = [document.get("title") for document in source_documents]
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
            *document_titles,
            crossref.get("title"),
            openalex.get("title"),
            crossref.get("abbreviation"),
            openalex.get("abbreviation"),
        ]
    )

    # Never carry the old allIssns list forward blindly. A prior scraper version
    # could collect dates and unrelated journal ISSNs from whole-page text.
    document_issns: list[Any] = []
    for document in source_documents:
        document_issns.extend(document.get("issns") or [])
        document_issns.extend([document.get("issn"), document.get("eissn")])

    all_issns = valid_issns(
        [
            record.get("issn"),
            record.get("eissn"),
            record.get("issnL"),
            *(crossref.get("allIssns") or []),
            *(openalex.get("allIssns") or []),
            crossref.get("issn"),
            crossref.get("eissn"),
            openalex.get("issnL"),
            *document_issns,
        ]
    )

    # Crossref, OpenAlex and the publication list are more reliable for the
    # publisher name than free-form secondary-site prose.
    publishers = [
        openalex.get("publisher"),
        crossref.get("publisher"),
        group.get("publisherFromPublications"),
        record.get("publisher"),
        *(document.get("publisher") for document in source_documents),
    ]
    publisher = next((cleaned for value in publishers if (cleaned := clean_publisher(value))), "")

    sources = dict(record.get("sources") or {})
    merge_source_snapshot(sources, "crossref", crossref.get("source"))
    merge_source_snapshot(sources, "openalex", openalex.get("source"))
    for document in source_documents:
        source = document.get("source") or {}
        name = compact_whitespace(source.get("name")).lower()
        if name:
            merge_source_snapshot(sources, re.sub(r"[^a-z0-9]+", "", name), source)

    subjects: list[str] = []
    for candidate in [
        *(record.get("subjects") or []),
        *(crossref.get("subjects") or []),
        *(subject for document in source_documents for subject in (document.get("subjects") or [])),
    ]:
        if cleaned := clean_subject(candidate):
            subjects.append(cleaned)

    print_issn = next(
        (
            value
            for candidate in [
                crossref.get("issn"),
                record.get("issn"),
                openalex.get("issnL"),
                *(document.get("issn") for document in source_documents),
                *(all_issns[:1]),
            ]
            if (value := normalize_issn(candidate))
        ),
        "",
    )
    electronic_issn = next(
        (
            value
            for candidate in [
                crossref.get("eissn"),
                record.get("eissn"),
                *(document.get("eissn") for document in source_documents),
            ]
            if (value := normalize_issn(candidate))
        ),
        "",
    )

    founded_year = record.get("foundedYear")
    frequency = compact_whitespace(record.get("frequency"))
    country = compact_whitespace(record.get("country"))
    is_open_access = record.get("isOpenAccess")
    for document in source_documents:
        if founded_year is None and document.get("foundedYear") is not None:
            founded_year = document.get("foundedYear")
        if not frequency and document.get("frequency"):
            frequency = compact_whitespace(document.get("frequency"))[:80]
        if not country and document.get("country"):
            country = compact_whitespace(document.get("country"))[:80]
        if is_open_access is None and document.get("isOpenAccess") is not None:
            is_open_access = document.get("isOpenAccess")

    return clean_nulls(
        {
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
            "eissn": electronic_issn,
            "issnL": normalize_issn(openalex.get("issnL") or record.get("issnL")),
            "allIssns": all_issns,
            "homepage": openalex.get("homepage") or record.get("homepage") or "",
            "countryCode": openalex.get("countryCode") or record.get("countryCode") or "",
            "country": country,
            "journalType": openalex.get("sourceType") or record.get("journalType") or "journal",
            "isOpenAccess": (
                openalex.get("isOpenAccess")
                if "isOpenAccess" in openalex
                else is_open_access
            ),
            "isInDoaj": (
                openalex.get("isInDoaj")
                if "isInDoaj" in openalex
                else record.get("isInDoaj")
            ),
            "subjects": unique_strings(subjects),
            "openAlexId": openalex.get("openAlexId") or record.get("openAlexId") or "",
            "openAlexUrl": openalex.get("openAlexUrl") or record.get("openAlexUrl") or "",
            "openAlexStats": {
                "worksCount": openalex.get("worksCount", (record.get("openAlexStats") or {}).get("worksCount")),
                "citedByCount": openalex.get("citedByCount", (record.get("openAlexStats") or {}).get("citedByCount")),
                "twoYearMeanCitedness": openalex.get("twoYearMeanCitedness", (record.get("openAlexStats") or {}).get("twoYearMeanCitedness")),
                "hIndex": openalex.get("hIndex", (record.get("openAlexStats") or {}).get("hIndex")),
                "i10Index": openalex.get("i10Index", (record.get("openAlexStats") or {}).get("i10Index")),
            },
            "foundedYear": founded_year,
            "frequency": frequency,
            "publicationCount": group["publicationCount"],
            "publicationYears": group["publicationYears"],
            "firstPublicationYear": group["firstPublicationYear"],
            "latestPublicationYear": group["latestPublicationYear"],
            "sampleDoi": group["sampleDoi"],
            "sources": sources,
        }
    )


def merge_all_metrics(
    record: dict[str, Any],
    source_documents: list[dict[str, Any]],
    report_conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    metrics_by_year = dict(record.get("metricsByYear") or {})
    candidates: list[dict[str, Any]] = []
    for document in source_documents:
        candidates.extend(document.get("metricCandidates") or [])

    # Apply low-priority candidates first so higher-priority sources can replace them.
    candidates.sort(key=lambda item: metric_source_priority(item.get("source")))
    for candidate in candidates:
        apply_metric_candidate(
            metrics_by_year,
            candidate,
            report_conflicts,
            record.get("title", ""),
        )

    record["metricsByYear"] = dict(
        sorted(metrics_by_year.items(), key=lambda item: item[0])
    )
    valid_years = [as_int(year) for year in record["metricsByYear"]]
    valid_years = [year for year in valid_years if year is not None]
    record["latestMetricYear"] = max(valid_years) if valid_years else None

    for document in source_documents:
        if document.get("scopusLatest"):
            current = record.get("scopusLatest") or {}
            incoming = document["scopusLatest"]
            if semantic_copy(current) != semantic_copy(incoming):
                record["scopusLatest"] = incoming
    return clean_nulls(record)


def run_self_tests() -> None:
    assert normalize_issn("1616-301X") == "1616-301X"
    assert normalize_issn("21983844") == "2198-3844"
    assert normalize_issn("2000-2026") == ""
    assert normalize_issn("not-an-issn") == ""

    polluted_publisher = (
        "Wiley-VCH GmbH Official Wiley profile The 14.1 JIF is a journal-level, "
        "two-year citation-window measure."
    )
    assert clean_publisher(polluted_publisher) == "Wiley-VCH GmbH"
    assert clean_publisher("Elsevier BV") == "Elsevier BV"

    fixture = """
    <html><body><h1>Advanced Science Impact Factor (2026)</h1>
    Journal Title: Advanced Science Publisher: Wiley-VCH GmbH ISSN: 2198-3844
    E-ISSN: 2198-3844 Impact Factor: 14.1 Scopus CiteScore: 18.1
    Related journals: 2000-2026, 1044-5498, 0022-2844 Quartile: Q1
    </body></html>
    """
    parsed = parse_journalsearches_document(
        fixture,
        page_url="https://example.test",
        expected_title="Advanced Science",
        expected_issns=["2198-3844"],
    )
    assert parsed["issns"] == ["2198-3844"]
    assert parsed["publisher"] == "Wiley-VCH GmbH"

    merged = merge_basic_metadata(
        {
            "title": "Advanced Science",
            "publisher": polluted_publisher,
            "issn": "2198-3844",
            "eissn": "2198-3844",
            "issnL": "2198-3844",
            "allIssns": ["2198-3844", "2000-2026", "1044-5498"],
            "subjects": [],
            "sources": {},
        },
        group={
            "canonicalTitle": "Advanced Science",
            "aliases": ["Advanced Science"],
            "publisherFromPublications": "Wiley",
            "publicationCount": 1,
            "publicationYears": [2025],
            "firstPublicationYear": 2025,
            "latestPublicationYear": 2025,
            "sampleDoi": "10.1002/advs.202410666",
        },
        crossref={
            "title": "Advanced Science",
            "publisher": "Wiley",
            "issn": "2198-3844",
            "eissn": "2198-3844",
            "allIssns": ["2198-3844"],
        },
        openalex={
            "title": "Advanced Science",
            "publisher": "Wiley-VCH GmbH",
            "issnL": "2198-3844",
            "allIssns": ["2198-3844"],
            "openAlexId": "S2737737698",
        },
        source_documents=[parsed],
    )
    assert merged["publisher"] == "Wiley-VCH GmbH"
    assert merged["allIssns"] == ["2198-3844"]
    assert "2000-2026" not in merged["allIssns"]
    assert "1044-5498" not in merged["allIssns"]
    print("All journal updater self-tests passed.")


# ---------------------------------------------------------------------------
# Main update process
# ---------------------------------------------------------------------------

def default_payload() -> dict[str, Any]:
    return {
        "schemaVersion": 2,
        "sourcePolicy": {
            "primaryMetricSource": "JournalMetrics.org",
            "backupMetricSources": [
                "Bioxbio",
                "Manusights",
                "JournalSearches",
            ],
            "basicMetadataSources": [
                "Crossref",
                "OpenAlex",
                "publication records",
            ],
            "fieldRules": {
                "currentImpactFactorAndJcrQuartile": "JournalMetrics.org is preferred.",
                "historicalImpactFactor": "Bioxbio is preferred.",
                "fiveYearImpactFactorJciAndCategoryRank": "Manusights is preferred when available.",
                "lastResortCurrentImpactFactor": "JournalSearches may fill missing JIF values.",
                "quartileSeparation": "JournalSearches quartiles are stored as Scopus quartiles and never treated as JCR quartiles.",
            },
            "note": (
                "All JIF and JCR values are secondary-source observations and "
                "should be checked against Clarivate/JCR for formal use."
            ),
        },
        "journals": {},
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build and update data/journals.json from publications, Crossref, "
            "OpenAlex, JournalMetrics.org, Bioxbio, Manusights, and JournalSearches."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("missing", "refresh"),
        default="missing",
        help="missing enriches new journals; refresh rechecks all journal metric sources.",
    )
    parser.add_argument(
        "--report",
        default="journal_update_report.json",
        help="Path for the run report.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run offline parser and sanitation tests, then exit.",
    )
    args = parser.parse_args()

    if args.self_test:
        run_self_tests()
        return

    groups = load_publication_groups()
    existing = load_json(JOURNALS_PATH, default=default_payload())
    if not isinstance(existing, dict):
        raise RuntimeError(f"{JOURNALS_PATH} must contain a JSON object.")
    if not isinstance(existing.get("journals"), dict):
        existing["journals"] = {}

    before = copy.deepcopy(existing)
    journals: dict[str, Any] = existing["journals"]
    name_index = existing_index(existing)
    used_ids = set(journals)

    report: dict[str, Any] = {
        "generatedAt": utc_now(),
        "mode": args.mode,
        "publicationJournalCount": len(groups),
        "newJournals": [],
        "locallyUpdatedJournals": [],
        "sourceMatches": defaultdict(list),
        "sourceMisses": defaultdict(list),
        "conflicts": [],
        "sanitizedFields": [],
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

            should_refresh_metrics = is_new or args.mode == "refresh"
            needs_basic_metadata = is_new or args.mode == "refresh" or not record.get("allIssns") or not record.get("openAlexId")

            print(
                f"[{number}/{len(groups)}] {group['canonicalTitle']} "
                f"({'new' if is_new else 'existing'}; "
                f"{'remote refresh' if should_refresh_metrics else 'local statistics only'})"
            )

            crossref: dict[str, Any] = {}
            openalex: dict[str, Any] = {}
            if needs_basic_metadata:
                crossref = crossref_metadata(session, group["sampleDoi"])
                known_issns = valid_issns(
                    [
                        *(record.get("allIssns") or []),
                        *(crossref.get("allIssns") or []),
                        crossref.get("issn"),
                        crossref.get("eissn"),
                    ]
                )
                openalex = openalex_metadata(
                    select_openalex_source(
                        openalex_candidates(
                            session,
                            title=group["canonicalTitle"],
                            issns=known_issns,
                        ),
                        title=group["canonicalTitle"],
                        issns=known_issns,
                    )
                )

            source_documents: list[dict[str, Any]] = []
            if should_refresh_metrics:
                title_for_search = (
                    openalex.get("title")
                    or crossref.get("title")
                    or record.get("title")
                    or group["canonicalTitle"]
                )
                abbreviation = (
                    openalex.get("abbreviation")
                    or crossref.get("abbreviation")
                    or record.get("abbreviation")
                    or ""
                )
                known_issns = valid_issns(
                    [
                        *(record.get("allIssns") or []),
                        *(crossref.get("allIssns") or []),
                        *(openalex.get("allIssns") or []),
                        crossref.get("issn"),
                        crossref.get("eissn"),
                        openalex.get("issnL"),
                    ]
                )

                fetchers = [
                    (
                        "JournalMetrics.org",
                        lambda: journalmetrics_metadata(
                            session,
                            title=title_for_search,
                            issns=known_issns,
                        ),
                    ),
                    (
                        "Bioxbio",
                        lambda: bioxbio_metadata(
                            session,
                            title=title_for_search,
                            abbreviation=abbreviation,
                            issns=known_issns,
                        ),
                    ),
                    (
                        "Manusights",
                        lambda: manusights_metadata(
                            session,
                            title=title_for_search,
                        ),
                    ),
                    (
                        "JournalSearches",
                        lambda: journalsearches_metadata(
                            session,
                            title=title_for_search,
                            issns=known_issns,
                        ),
                    ),
                ]

                for source_name, fetcher in fetchers:
                    try:
                        document = fetcher()
                    except Exception as error:  # defensive: one site must not abort the run
                        report["errors"].append(
                            {
                                "journal": title_for_search,
                                "source": source_name,
                                "error": str(error),
                            }
                        )
                        document = {}
                    if document:
                        source_documents.append(document)
                        report["sourceMatches"][source_name].append(title_for_search)
                    else:
                        report["sourceMisses"][source_name].append(title_for_search)
            else:
                report["locallyUpdatedJournals"].append(group["canonicalTitle"])

            previous_publisher = compact_whitespace(record.get("publisher"))
            previous_issns = list(record.get("allIssns") or [])
            record = merge_basic_metadata(
                record,
                group=group,
                crossref=crossref,
                openalex=openalex,
                source_documents=source_documents,
            )
            if previous_publisher and previous_publisher != record.get("publisher"):
                report["sanitizedFields"].append({
                    "journal": group["canonicalTitle"],
                    "field": "publisher",
                    "before": previous_publisher,
                    "after": record.get("publisher", ""),
                })
            if previous_issns and previous_issns != record.get("allIssns"):
                report["sanitizedFields"].append({
                    "journal": group["canonicalTitle"],
                    "field": "allIssns",
                    "before": previous_issns,
                    "after": record.get("allIssns", []),
                })
            record["journalId"] = journal_id
            record = merge_all_metrics(
                record,
                source_documents,
                report["conflicts"],
            )
            journals[journal_id] = record
            name_index[normalized_name] = journal_id

    active_ids = {
        name_index[normalized]
        for normalized in groups
        if normalized in name_index
    }
    for journal_id, record in journals.items():
        if isinstance(record, dict):
            record["currentlyUsedInPublications"] = journal_id in active_ids

    existing["schemaVersion"] = 2
    existing["sourcePolicy"] = default_payload()["sourcePolicy"]
    existing["journalCount"] = len(journals)
    existing["activeJournalCount"] = len(active_ids)
    existing["journals"] = dict(
        sorted(
            journals.items(),
            key=lambda item: compact_whitespace((item[1] or {}).get("title")).casefold(),
        )
    )

    if semantic_copy(existing) != semantic_copy(before):
        existing["lastUpdated"] = utc_now()
    else:
        existing["lastUpdated"] = before.get("lastUpdated")

    report["sourceMatches"] = dict(report["sourceMatches"])
    report["sourceMisses"] = dict(report["sourceMisses"])
    report["journalDataChanged"] = semantic_copy(existing) != semantic_copy(before)

    write_json_atomic(JOURNALS_PATH, clean_nulls(existing))
    write_json_atomic(Path(args.report), clean_nulls(report))

    print(f"Saved {len(journals)} journal records to {JOURNALS_PATH}.")
    print(f"Journal data changed: {report['journalDataChanged']}")
    for source_name in ["JournalMetrics.org", "Bioxbio", "Manusights", "JournalSearches"]:
        print(
            f"{source_name}: "
            f"{len(report['sourceMatches'].get(source_name, []))} matched, "
            f"{len(report['sourceMisses'].get(source_name, []))} missed"
        )
    print(f"Metric conflicts recorded: {len(report['conflicts'])}")


if __name__ == "__main__":
    main()
