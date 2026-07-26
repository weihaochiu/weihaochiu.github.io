#!/usr/bin/env python3
"""Fetch and validate publication-level authorship and affiliation metadata.

The updater keeps ``authors`` as the backward-compatible canonical name list and
adds ``authorships``, ``affiliations`` and ``authorshipMetadata`` to each record.
It never infers equal contribution from author order or corresponding status
from the last-author position.

Primary sources
---------------
1. Europe PMC full-text JATS/XML, when available (explicit affiliation,
   equal-contribution and correspondence markers).
2. Crossref DOI metadata (authors, ORCID and deposited affiliations).
3. OpenAlex Works API (author identities, institutions, order and the
   ``is_corresponding`` flag).
4. Optional publisher HTML citation meta tags, enabled explicitly.

Existing manually verified values are preserved.
"""

from __future__ import annotations

import argparse
import copy
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLICATIONS = ROOT / "data" / "publications.json"
ME_ORCID = "0000-0003-4484-3117"
ME_OPENALEX_IDS = {"A5007707999", "https://openalex.org/A5007707999"}
ME_ALIASES = {
    "weihaochiu",
    "chiuweihao",
    "whchiu",
    "邱偉豪",
}
SOURCE_PRIORITY = {"manual": 0, "europe-pmc": 1, "crossref": 2, "openalex": 3, "publisher-html": 4}
USER_AGENT = "Wei-Hao-Chiu-Academic-Website/1.0 (publication metadata updater)"


def normalize_text(value: Any) -> str:
    text = html.unescape(str(value or "")).strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def name_keys(value: Any) -> set[str]:
    text = clean_space(value)
    keys = {normalize_text(text)} if text else set()
    if "," in text:
        family, rest = text.split(",", 1)
        keys.add(normalize_text(f"{rest} {family}"))
    return {key for key in keys if key}


def normalize_doi(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    return re.sub(r"^doi:\s*", "", text).strip()


def normalize_orcid(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^https?://orcid\.org/", "", text, flags=re.I)
    return text.upper()


def clean_openalex_id(value: Any) -> str:
    text = str(value or "").strip()
    return text.rsplit("/", 1)[-1] if text else ""


def clean_space(value: Any) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip(" ,;\n\t")


def letters(index: int) -> str:
    value = index + 1
    out = ""
    while value:
        value, rem = divmod(value - 1, 26)
        out = chr(97 + rem) + out
    return out


def json_clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def ordered_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for raw in values:
        value = clean_space(raw)
        key = normalize_text(value)
        if value and key and key not in seen:
            seen.add(key)
            output.append(value)
    return output


class FetchError(RuntimeError):
    pass


class JsonHttpClient:
    def __init__(self, timeout: float = 25.0, retries: int = 2, polite_delay: float = 0.12):
        self.timeout = timeout
        self.retries = retries
        self.polite_delay = polite_delay

    def request(self, url: str, *, accept: str = "application/json") -> bytes:
        headers = {"User-Agent": USER_AGENT, "Accept": accept}
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    payload = response.read()
                if self.polite_delay:
                    time.sleep(self.polite_delay)
                return payload
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if isinstance(exc, urllib.error.HTTPError) and exc.code in {400, 401, 403, 404}:
                    break
                if attempt < self.retries:
                    time.sleep(0.7 * (attempt + 1))
        raise FetchError(f"Unable to fetch {url}: {last_error}")

    def json(self, url: str) -> dict[str, Any]:
        try:
            payload = json.loads(self.request(url).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FetchError(f"Invalid JSON from {url}: {exc}") from exc
        if not isinstance(payload, dict):
            raise FetchError(f"Expected JSON object from {url}")
        return payload

    def text(self, url: str, *, accept: str = "text/html,application/xhtml+xml,application/xml") -> str:
        payload = self.request(url, accept=accept)
        for encoding in ("utf-8", "utf-16", "latin-1"):
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
        return payload.decode("utf-8", errors="replace")


@dataclass
class AffiliationCandidate:
    text: str
    institution: str = ""
    department: str = ""
    city: str = ""
    country_code: str = ""
    source: str = ""
    source_id: str = ""

    @property
    def key(self) -> str:
        return normalize_text(self.text or self.institution)


@dataclass
class AuthorCandidate:
    name: str
    author_order: int
    orcid: str = ""
    openalex_id: str = ""
    author_position: str = ""
    is_corresponding: bool | None = None
    is_equal_contributor: bool | None = None
    corresponding_email: str = ""
    affiliations: list[AffiliationCandidate] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


@dataclass
class SourceResult:
    source: str
    authors: list[AuthorCandidate] = field(default_factory=list)
    explicit_correspondence: bool = False
    explicit_equal_contribution: bool = False
    source_url: str = ""
    warnings: list[str] = field(default_factory=list)


def author_from_crossref(row: dict[str, Any], order: int) -> AuthorCandidate:
    name = clean_space(" ".join(str(row.get(key) or "") for key in ("given", "family")))
    if not name:
        name = clean_space(row.get("name"))
    affiliations = []
    for item in row.get("affiliation") or []:
        if isinstance(item, dict):
            text = clean_space(item.get("name"))
        else:
            text = clean_space(item)
        if text:
            affiliations.append(AffiliationCandidate(text=text, institution=text, source="crossref"))
    corresponding = row.get("corresponding")
    if not isinstance(corresponding, bool):
        corresponding = None
    role = str(row.get("role") or row.get("contributor-role") or "").lower()
    if "correspond" in role:
        corresponding = True
    return AuthorCandidate(
        name=name,
        author_order=order,
        orcid=normalize_orcid(row.get("ORCID")),
        author_position="first" if order == 1 else "middle",
        is_corresponding=corresponding,
        affiliations=affiliations,
        sources=["crossref"],
    )


def fetch_crossref(client: JsonHttpClient, doi: str) -> SourceResult:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    mailto = clean_space(os.environ.get("CROSSREF_MAILTO") or os.environ.get("OPENALEX_MAILTO"))
    if mailto:
        url += "?mailto=" + urllib.parse.quote(mailto)
    payload = client.json(url)
    message = payload.get("message") or {}
    rows = message.get("author") or []
    authors = [author_from_crossref(row, index + 1) for index, row in enumerate(rows) if isinstance(row, dict)]
    explicit = any(author.is_corresponding is not None for author in authors)
    if explicit:
        for author in authors:
            if author.is_corresponding is None:
                author.is_corresponding = False
    return SourceResult("crossref", authors, explicit_correspondence=explicit, source_url=url)


def fetch_openalex(client: JsonHttpClient, doi: str) -> SourceResult:
    mailto = clean_space(os.environ.get("OPENALEX_MAILTO") or os.environ.get("CROSSREF_MAILTO"))
    identifier = urllib.parse.quote("https://doi.org/" + doi, safe="")
    url = f"https://api.openalex.org/works/{identifier}"
    if mailto:
        url += "?mailto=" + urllib.parse.quote(mailto)
    payload = client.json(url)
    authors: list[AuthorCandidate] = []
    for index, row in enumerate(payload.get("authorships") or [], start=1):
        if not isinstance(row, dict):
            continue
        author = row.get("author") or {}
        institutions = []
        for inst in row.get("institutions") or []:
            if not isinstance(inst, dict):
                continue
            display = clean_space(inst.get("display_name"))
            institutions.append(
                AffiliationCandidate(
                    text=display,
                    institution=display,
                    country_code=clean_space(inst.get("country_code")),
                    source="openalex",
                    source_id=clean_space(inst.get("id")),
                )
            )
        corresponding = row.get("is_corresponding")
        if not isinstance(corresponding, bool):
            corresponding = None
        authors.append(
            AuthorCandidate(
                name=clean_space(author.get("display_name")),
                author_order=index,
                orcid=normalize_orcid(author.get("orcid")),
                openalex_id=clean_openalex_id(author.get("id")),
                author_position=clean_space(row.get("author_position")),
                is_corresponding=corresponding,
                affiliations=institutions,
                sources=["openalex"],
            )
        )
    explicit = bool(authors) and all(author.is_corresponding is not None for author in authors)
    return SourceResult("openalex", authors, explicit_correspondence=explicit, source_url=url)


def strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def element_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return clean_space(" ".join(element.itertext()))


def find_descendants(element: ET.Element, name: str) -> list[ET.Element]:
    return [node for node in element.iter() if strip_namespace(node.tag) == name]


def first_descendant(element: ET.Element, name: str) -> ET.Element | None:
    for node in element.iter():
        if strip_namespace(node.tag) == name:
            return node
    return None


def parse_jats(xml_text: str, source_url: str) -> SourceResult:
    root = ET.fromstring(xml_text)
    affiliation_nodes = {node.get("id", ""): node for node in find_descendants(root, "aff") if node.get("id")}
    correspondence_nodes = {node.get("id", ""): node for node in find_descendants(root, "corresp") if node.get("id")}
    authors: list[AuthorCandidate] = []
    explicit_equal = False
    explicit_correspondence = False

    for contrib in find_descendants(root, "contrib"):
        if str(contrib.get("contrib-type") or "author").lower() != "author":
            continue
        name_node = first_descendant(contrib, "name")
        if name_node is not None:
            given = element_text(first_descendant(name_node, "given-names"))
            surname = element_text(first_descendant(name_node, "surname"))
            name = clean_space(f"{given} {surname}")
        else:
            name = element_text(first_descendant(contrib, "string-name"))
        if not name:
            continue
        orcid = ""
        for contrib_id in find_descendants(contrib, "contrib-id"):
            if str(contrib_id.get("contrib-id-type") or "").lower() == "orcid":
                orcid = normalize_orcid(element_text(contrib_id))
                break
        affs: list[AffiliationCandidate] = []
        corresp_ids: list[str] = []
        for xref in find_descendants(contrib, "xref"):
            ref_type = str(xref.get("ref-type") or "").lower()
            rid_values = str(xref.get("rid") or "").split()
            if ref_type == "aff":
                for rid in rid_values:
                    text = element_text(affiliation_nodes.get(rid))
                    if text:
                        affs.append(AffiliationCandidate(text=text, institution=text, source="europe-pmc", source_id=rid))
            if ref_type in {"corresp", "author-notes", "fn"}:
                corresp_ids.extend(rid_values)
        equal_attr = str(contrib.get("equal-contrib") or contrib.get("equal_contrib") or "").lower()
        equal: bool | None = None
        if equal_attr in {"yes", "true", "y", "1"}:
            equal = True
            explicit_equal = True
        corresponding = bool(corresp_ids)
        if corresponding:
            explicit_correspondence = True
        emails = []
        for rid in corresp_ids:
            node = correspondence_nodes.get(rid)
            if node is not None:
                emails.extend(element_text(email) for email in find_descendants(node, "email"))
        authors.append(
            AuthorCandidate(
                name=name,
                author_order=len(authors) + 1,
                orcid=orcid,
                author_position="first" if not authors else "middle",
                is_corresponding=corresponding if explicit_correspondence or corresponding else None,
                is_equal_contributor=equal,
                corresponding_email=next((email for email in emails if email), ""),
                affiliations=affs,
                sources=["europe-pmc"],
            )
        )

    if explicit_equal:
        for author in authors:
            if author.is_equal_contributor is None:
                author.is_equal_contributor = False
    if explicit_correspondence:
        for author in authors:
            if author.is_corresponding is None:
                author.is_corresponding = False
    if authors:
        authors[-1].author_position = "last" if len(authors) > 1 else "first"
    return SourceResult(
        "europe-pmc",
        authors,
        explicit_correspondence=explicit_correspondence,
        explicit_equal_contribution=explicit_equal,
        source_url=source_url,
    )


def fetch_europe_pmc(client: JsonHttpClient, doi: str) -> SourceResult:
    search_url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query="
        + urllib.parse.quote(f'DOI:"{doi}"')
        + "&format=json&pageSize=5"
    )
    payload = client.json(search_url)
    results = ((payload.get("resultList") or {}).get("result") or [])
    match = None
    for row in results:
        if normalize_doi(row.get("doi")) == doi:
            match = row
            break
    if match is None:
        return SourceResult("europe-pmc", source_url=search_url, warnings=["No DOI match"])
    pmcid = clean_space(match.get("pmcid"))
    if not pmcid:
        return SourceResult("europe-pmc", source_url=search_url, warnings=["No open full-text XML"])
    xml_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{urllib.parse.quote(pmcid)}/fullTextXML"
    try:
        return parse_jats(client.text(xml_url, accept="application/xml,text/xml"), xml_url)
    except (ET.ParseError, FetchError) as exc:
        return SourceResult("europe-pmc", source_url=xml_url, warnings=[str(exc)])


_META_RE = re.compile(
    r"<meta\s+[^>]*?(?:name|property)=[\"']([^\"']+)[\"'][^>]*?content=[\"']([^\"']*)[\"'][^>]*>",
    flags=re.I,
)


def fetch_publisher_html(client: JsonHttpClient, doi: str) -> SourceResult:
    url = "https://doi.org/" + urllib.parse.quote(doi, safe="/()[]:;._-")
    text = client.text(url)
    meta: dict[str, list[str]] = {}
    for key, value in _META_RE.findall(text):
        meta.setdefault(key.lower(), []).append(clean_space(value))
    names = meta.get("citation_author") or meta.get("dc.creator") or []
    institutions = meta.get("citation_author_institution") or []
    orcids = meta.get("citation_author_orcid") or []
    emails = meta.get("citation_author_email") or []
    authors = []
    for index, name in enumerate(names, start=1):
        affs = []
        if index <= len(institutions) and institutions[index - 1]:
            value = institutions[index - 1]
            affs.append(AffiliationCandidate(text=value, institution=value, source="publisher-html"))
        authors.append(
            AuthorCandidate(
                name=name,
                author_order=index,
                orcid=normalize_orcid(orcids[index - 1]) if index <= len(orcids) else "",
                corresponding_email=emails[index - 1] if index <= len(emails) else "",
                affiliations=affs,
                sources=["publisher-html"],
            )
        )
    if authors:
        authors[0].author_position = "first"
        authors[-1].author_position = "last" if len(authors) > 1 else "first"
    return SourceResult("publisher-html", authors, source_url=url)


def score_match(canonical_name: str, candidate: AuthorCandidate, existing: dict[str, Any] | None = None) -> int:
    score = 0
    if name_keys(canonical_name) & name_keys(candidate.name):
        score += 100
    if existing:
        existing_orcid = normalize_orcid(existing.get("orcid"))
        existing_oa = clean_openalex_id(existing.get("openAlexId"))
        if existing_orcid and candidate.orcid and existing_orcid == candidate.orcid:
            score += 180
        if existing_oa and candidate.openalex_id and existing_oa == candidate.openalex_id:
            score += 140
    return score


def align_source(canonical_names: list[str], source: SourceResult, existing_rows: list[dict[str, Any]]) -> list[AuthorCandidate | None]:
    aligned: list[AuthorCandidate | None] = [None] * len(canonical_names)
    unused = set(range(len(source.authors)))
    positional_fallback = len(source.authors) == len(canonical_names)
    for index, name in enumerate(canonical_names):
        best_idx = None
        best_score = -1
        existing = existing_rows[index] if index < len(existing_rows) else None
        for candidate_idx in unused:
            candidate = source.authors[candidate_idx]
            score = score_match(name, candidate, existing)
            if positional_fallback and candidate.author_order == index + 1:
                score += 25
            if score > best_score:
                best_score = score
                best_idx = candidate_idx
        threshold = 25 if positional_fallback else 100
        if best_idx is not None and best_score >= threshold:
            aligned[index] = source.authors[best_idx]
            unused.remove(best_idx)
    return aligned


def is_manual_metadata(publication: dict[str, Any]) -> bool:
    metadata = publication.get("authorshipMetadata") or {}
    return str(metadata.get("status") or "").lower() in {"manual", "manually-verified"} or bool(metadata.get("manualOverride"))


def merge_affiliations(
    publication: dict[str, Any],
    merged_candidates: list[list[AffiliationCandidate]],
) -> tuple[list[dict[str, Any]], list[list[str]]]:
    existing_affiliations = publication.get("affiliations") or []
    output: list[dict[str, Any]] = []
    key_to_id: dict[str, str] = {}

    for row in existing_affiliations:
        if not isinstance(row, dict):
            continue
        item = json_clone(row)
        aff_id = clean_space(item.get("id")) or f"aff-{len(output) + 1}"
        item["id"] = aff_id
        item.setdefault("label", letters(len(output)))
        key = normalize_text(item.get("raw") or item.get("address") or item.get("institution"))
        if key and key not in key_to_id:
            key_to_id[key] = aff_id
        output.append(item)

    author_ids: list[list[str]] = []
    for candidates in merged_candidates:
        ids: list[str] = []
        ordered = sorted(
            candidates,
            key=lambda item: (SOURCE_PRIORITY.get(item.source, 99), normalize_text(item.text), item.source_id),
        )
        for candidate in ordered:
            key = candidate.key
            if not key:
                continue
            aff_id = key_to_id.get(key)
            matched_row = None
            if not aff_id:
                candidate_institution = normalize_text(candidate.institution)
                for existing in output:
                    existing_institution = normalize_text(existing.get("institution"))
                    existing_text = normalize_text(existing.get("address") or existing.get("raw"))
                    same_institution = bool(candidate_institution and (candidate_institution == existing_institution or candidate_institution in existing_text))
                    if same_institution:
                        aff_id = str(existing.get("id") or "")
                        matched_row = existing
                        break
            if aff_id and matched_row is None:
                matched_row = next((row for row in output if str(row.get("id") or "") == aff_id), None)
            if matched_row is not None:
                key_to_id[key] = aff_id
                enrichments = {
                    "department": candidate.department,
                    "institution": candidate.institution,
                    "city": candidate.city,
                    "countryCode": candidate.country_code,
                    "sourceId": candidate.source_id,
                }
                for field_name, value in enrichments.items():
                    if value and not matched_row.get(field_name):
                        matched_row[field_name] = value
            if not aff_id:
                aff_id = f"aff-{len(output) + 1}"
                key_to_id[key] = aff_id
                output.append(
                    {
                        "id": aff_id,
                        "label": letters(len(output)),
                        "department": candidate.department,
                        "institution": candidate.institution or candidate.text,
                        "address": candidate.text,
                        "city": candidate.city,
                        "countryCode": candidate.country_code,
                        "raw": candidate.text,
                        "source": candidate.source,
                        "sourceId": candidate.source_id,
                    }
                )
            if aff_id not in ids:
                ids.append(aff_id)
        author_ids.append(ids)

    # Preserve stable IDs already stored in the authoritative JSON. New rows are
    # appended deterministically in first-author/source order.
    for index, row in enumerate(output):
        row.setdefault("label", letters(index))
        for key in ("department", "institution", "address", "city", "countryCode", "raw", "source", "sourceId"):
            row.setdefault(key, "")
    return output, author_ids


def merge_publication(publication: dict[str, Any], results: list[SourceResult]) -> tuple[dict[str, Any], bool]:
    original = json_clone(publication)
    output = copy.deepcopy(publication)
    names = output.get("authors") or []
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise ValueError(f"Publication {output.get('doi') or output.get('title')} has invalid authors")
    names = [clean_space(name) for name in names]
    existing_rows = output.get("authorships") or []
    if not isinstance(existing_rows, list):
        existing_rows = []
    manual = is_manual_metadata(output)

    aligned_by_source = {result.source: align_source(names, result, existing_rows) for result in results if result.authors}
    if not aligned_by_source and len(existing_rows) == len(names):
        # A temporary API outage must not downgrade or rewrite the last valid data.
        return original, False
    merged_candidates: list[list[AffiliationCandidate]] = [[] for _ in names]
    authorships: list[dict[str, Any]] = []
    existing_metadata = dict(output.get("authorshipMetadata") or {})
    prior_status = str(existing_metadata.get("status") or "").lower()
    sources_used: list[str] = list(existing_metadata.get("sources") or [])
    warnings: list[str] = [] if prior_status in {"verified", "manual", "manually-verified"} else list(existing_metadata.get("warnings") or [])

    for result in results:
        if result.authors:
            sources_used.append(result.source)
        if prior_status not in {"verified", "manual", "manually-verified"}:
            warnings.extend(f"{result.source}: {warning}" for warning in result.warnings)

    for index, name in enumerate(names):
        existing = existing_rows[index] if index < len(existing_rows) and isinstance(existing_rows[index], dict) else {}
        existing_equal = existing.get("isEqualContributor") if existing.get("isEqualContributor") in {True, False, None} else None
        existing_corresponding = existing.get("isCorresponding") if existing.get("isCorresponding") in {True, False, None} else None
        row = {
            "name": name,
            "orcid": normalize_orcid(existing.get("orcid")),
            "openAlexId": clean_openalex_id(existing.get("openAlexId")),
            "authorOrder": index + 1,
            "authorPosition": clean_space(existing.get("authorPosition")) or ("first" if index == 0 else "last" if index == len(names) - 1 else "middle"),
            "affiliationIds": list(existing.get("affiliationIds") or []),
            "isEqualContributor": existing_equal if manual else None,
            "equalContributionGroup": clean_space(existing.get("equalContributionGroup")),
            "isCorresponding": existing_corresponding if manual else None,
            "correspondingEmail": clean_space(existing.get("correspondingEmail")),
            "sources": list(existing.get("sources") or []),
        }
        for source_name in ("europe-pmc", "crossref", "openalex", "publisher-html"):
            candidate = (aligned_by_source.get(source_name) or [None] * len(names))[index]
            if candidate is None:
                continue
            if not row["orcid"] and candidate.orcid:
                row["orcid"] = candidate.orcid
            if not row["openAlexId"] and candidate.openalex_id:
                row["openAlexId"] = candidate.openalex_id
            if candidate.author_position and row["authorPosition"] in {"", "middle"}:
                row["authorPosition"] = candidate.author_position
            if row["isEqualContributor"] is None and candidate.is_equal_contributor is not None:
                row["isEqualContributor"] = candidate.is_equal_contributor
            if row["isCorresponding"] is None and candidate.is_corresponding is not None:
                row["isCorresponding"] = candidate.is_corresponding
            if not row["correspondingEmail"] and candidate.corresponding_email:
                row["correspondingEmail"] = candidate.corresponding_email
            row["sources"] = ordered_unique([*row["sources"], *candidate.sources])
            merged_candidates[index].extend(candidate.affiliations)
        if not manual and row["isEqualContributor"] is None:
            row["isEqualContributor"] = existing_equal
        if not manual and row["isCorresponding"] is None:
            row["isCorresponding"] = existing_corresponding
        authorships.append(row)

    affiliations, affiliation_ids = merge_affiliations(output, merged_candidates)
    for index, row in enumerate(authorships):
        existing_ids = list(row.get("affiliationIds") or [])
        row["affiliationIds"] = ordered_unique([*existing_ids, *affiliation_ids[index]])

    for index, name in enumerate(names):
        equal_values = []
        corresponding_values = []
        for source_name, aligned in aligned_by_source.items():
            candidate = aligned[index]
            if candidate is None:
                continue
            if candidate.is_equal_contributor is not None:
                equal_values.append((source_name, candidate.is_equal_contributor))
            if candidate.is_corresponding is not None:
                corresponding_values.append((source_name, candidate.is_corresponding))
        if len({value for _, value in equal_values}) > 1:
            warnings.append("Equal-contribution conflict for " + name + ": " + ", ".join(f"{source}={value}" for source, value in equal_values))
        if len({value for _, value in corresponding_values}) > 1:
            warnings.append("Corresponding-author conflict for " + name + ": " + ", ".join(f"{source}={value}" for source, value in corresponding_values))

    explicit_equal = any(result.explicit_equal_contribution for result in results)
    explicit_correspondence = any(result.explicit_correspondence for result in results)
    unmatched_sources = [
        source_name
        for source_name, aligned in aligned_by_source.items()
        if any(candidate is None for candidate in aligned)
    ]
    missing_fields = []
    equal_known = bool(authorships) and all(row.get("isEqualContributor") in {True, False} for row in authorships)
    correspondence_known = bool(authorships) and all(row.get("isCorresponding") in {True, False} for row in authorships)
    if not explicit_equal and not equal_known:
        missing_fields.append("equalContribution")
    if not explicit_correspondence and not correspondence_known:
        missing_fields.append("correspondingAuthor")
    if not affiliations:
        missing_fields.append("affiliations")
    has_full_address = any(
        normalize_text(row.get("address") or row.get("raw"))
        and normalize_text(row.get("address") or row.get("raw")) != normalize_text(row.get("institution"))
        for row in affiliations
    )
    if affiliations and not has_full_address:
        missing_fields.append("affiliationAddresses")
    if unmatched_sources:
        missing_fields.append("sourceAuthorAlignment")

    status = "manual" if manual else "verified" if sources_used and not missing_fields and not warnings else "partial" if sources_used else "pending"
    metadata = existing_metadata
    metadata.update(
        {
            "status": status,
            "sources": ordered_unique(sources_used),
            "sourceUrls": {result.source: result.source_url for result in results if result.source_url and result.authors},
            "requiresManualReview": bool(missing_fields or warnings),
            "missingFields": ordered_unique(missing_fields),
            "warnings": ordered_unique(warnings),
        }
    )
    if manual:
        metadata["manualOverride"] = True

    output["affiliations"] = affiliations
    output["authorships"] = authorships
    output["authorshipMetadata"] = metadata
    update_legacy_me_fields(output)

    comparable_before = json_clone(original)
    comparable_after = json_clone(output)
    for payload in (comparable_before, comparable_after):
        if isinstance(payload.get("authorshipMetadata"), dict):
            payload["authorshipMetadata"].pop("lastChecked", None)
    changed = comparable_before != comparable_after
    if changed:
        output["authorshipMetadata"]["lastChecked"] = date.today().isoformat()
    elif original.get("authorshipMetadata", {}).get("lastChecked"):
        output["authorshipMetadata"]["lastChecked"] = original["authorshipMetadata"]["lastChecked"]
    return output, changed


def is_me(authorship: dict[str, Any]) -> bool:
    if normalize_orcid(authorship.get("orcid")) == ME_ORCID:
        return True
    if clean_openalex_id(authorship.get("openAlexId")) in {clean_openalex_id(value) for value in ME_OPENALEX_IDS}:
        return True
    return normalize_text(authorship.get("name")) in ME_ALIASES


def role_for_me(row: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    count = len(rows)
    order = int(row.get("authorOrder") or 0)
    equal = row.get("isEqualContributor") is True
    corresponding = row.get("isCorresponding") is True
    equal_orders = [int(item.get("authorOrder") or 0) for item in rows if item.get("isEqualContributor") is True]
    equal_group_starts_first = bool(equal_orders) and min(equal_orders) == 1
    if equal and equal_group_starts_first:
        lead = "Co-first author"
    elif equal:
        lead = "Equal contributor"
    elif order == 1:
        lead = "First author"
    elif order == count and count > 1:
        lead = "Last author"
    else:
        lead = "Co-author"
    if corresponding:
        if lead == "Co-author":
            return "Corresponding author"
        return f"{lead} and corresponding author"
    return lead


def update_legacy_me_fields(publication: dict[str, Any]) -> None:
    rows = publication.get("authorships") or []
    mine = next((row for row in rows if isinstance(row, dict) and is_me(row)), None)
    if mine is None:
        return
    publication["authorOrder"] = int(mine.get("authorOrder") or 0) or None
    publication["role"] = role_for_me(mine, rows)


def initialize_publication(publication: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    output = copy.deepcopy(publication)
    names = output.get("authors") or []
    existing = output.get("authorships")
    if isinstance(existing, list) and len(existing) == len(names):
        return output, False
    output["authorships"] = [
        {
            "name": clean_space(name),
            "orcid": "",
            "openAlexId": "",
            "authorOrder": index + 1,
            "authorPosition": "first" if index == 0 else "last" if index == len(names) - 1 else "middle",
            "affiliationIds": [],
            "isEqualContributor": None,
            "equalContributionGroup": "",
            "isCorresponding": None,
            "correspondingEmail": "",
            "sources": [],
        }
        for index, name in enumerate(names)
    ]
    output.setdefault("affiliations", [])
    output["authorshipMetadata"] = {
        "status": "pending",
        "lastChecked": "",
        "sources": [],
        "sourceUrls": {},
        "requiresManualReview": True,
        "missingFields": ["affiliations", "equalContribution", "correspondingAuthor"],
        "warnings": [],
    }
    update_legacy_me_fields(output)
    return output, True


def validate_publications(publications: list[dict[str, Any]], allow_missing: bool = False) -> list[str]:
    errors: list[str] = []
    for number, publication in enumerate(publications, start=1):
        label = normalize_doi(publication.get("doi")) or str(publication.get("title") or f"record {number}")
        names = publication.get("authors") or []
        rows = publication.get("authorships")
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            errors.append(f"{label}: authors must be an array of strings")
            continue
        if not isinstance(rows, list):
            if allow_missing:
                continue
            errors.append(f"{label}: missing authorships array")
            continue
        if len(rows) != len(names):
            errors.append(f"{label}: authors/authorships length mismatch ({len(names)} vs {len(rows)})")
        affiliations = publication.get("affiliations") or []
        if not isinstance(affiliations, list):
            errors.append(f"{label}: affiliations must be an array")
            affiliations = []
        aff_ids = [str(row.get("id") or "") for row in affiliations if isinstance(row, dict)]
        if len(aff_ids) != len(set(aff_ids)):
            errors.append(f"{label}: duplicate affiliation IDs")
        valid_aff_ids = set(aff_ids)
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"{label}: authorship {index + 1} is not an object")
                continue
            if index < len(names) and normalize_text(row.get("name")) != normalize_text(names[index]):
                errors.append(f"{label}: authorship {index + 1} name does not match authors[{index}]")
            if row.get("authorOrder") != index + 1:
                errors.append(f"{label}: authorship {index + 1} has invalid authorOrder")
            for field_name in ("isEqualContributor", "isCorresponding"):
                if row.get(field_name) not in {True, False, None}:
                    errors.append(f"{label}: {field_name} must be true, false or null")
            unknown = set(row.get("affiliationIds") or []) - valid_aff_ids
            if unknown:
                errors.append(f"{label}: authorship {index + 1} references unknown affiliations {sorted(unknown)}")
        mine = next((row for row in rows if isinstance(row, dict) and is_me(row)), None)
        if mine and publication.get("authorOrder") not in {None, int(mine.get("authorOrder") or 0)}:
            errors.append(f"{label}: legacy authorOrder does not match Wei-Hao Chiu authorship")
    return errors


def load_publications(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Publications file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise SystemExit(f"{path} must contain an array of objects")
    return payload


def write_publications(path: Path, publications: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(publications, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publications", type=Path, default=DEFAULT_PUBLICATIONS)
    parser.add_argument("--doi", help="Update only one DOI")
    parser.add_argument("--retry-partial", action="store_true", help="Update pending/partial records and records missing authorships")
    parser.add_argument("--check", action="store_true", help="Validate existing JSON without contacting APIs")
    parser.add_argument("--allow-missing", action="store_true", help="Permit records without authorships during validation")
    parser.add_argument("--initialize-only", action="store_true", help="Create schema placeholders without contacting APIs")
    parser.add_argument("--publisher-html", action="store_true", default=os.environ.get("ENABLE_PUBLISHER_HTML") == "1")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=float, default=25.0)
    return parser.parse_args()


def should_update(publication: dict[str, Any], args: argparse.Namespace) -> bool:
    doi = normalize_doi(publication.get("doi"))
    if args.doi and doi != normalize_doi(args.doi):
        return False
    if args.retry_partial:
        status = str((publication.get("authorshipMetadata") or {}).get("status") or "").lower()
        return not publication.get("authorships") or status in {"", "pending", "partial", "error"}
    return True


def main() -> None:
    args = parse_args()
    publications = load_publications(args.publications)
    if args.check:
        errors = validate_publications(publications, allow_missing=args.allow_missing)
        if errors:
            raise SystemExit("\n".join(errors))
        print(f"Validated {len(publications)} publication records.")
        return

    client = JsonHttpClient(timeout=args.timeout)
    changed_count = 0
    processed_count = 0
    failures: list[str] = []
    output: list[dict[str, Any]] = []

    for publication in publications:
        if not should_update(publication, args):
            output.append(publication)
            continue
        doi = normalize_doi(publication.get("doi"))
        if args.initialize_only:
            updated, changed = initialize_publication(publication)
        elif not doi:
            updated, changed = initialize_publication(publication)
            metadata = dict(updated.get("authorshipMetadata") or {})
            metadata.update({"status": "pending", "requiresManualReview": True})
            metadata["warnings"] = ordered_unique([*(metadata.get("warnings") or []), "Missing DOI"])
            updated["authorshipMetadata"] = metadata
        else:
            results: list[SourceResult] = []
            for fetcher in (fetch_europe_pmc, fetch_crossref, fetch_openalex):
                try:
                    results.append(fetcher(client, doi))
                except FetchError as exc:
                    results.append(SourceResult(fetcher.__name__.replace("fetch_", "").replace("_", "-"), warnings=[str(exc)]))
            if args.publisher_html:
                try:
                    results.append(fetch_publisher_html(client, doi))
                except FetchError as exc:
                    results.append(SourceResult("publisher-html", warnings=[str(exc)]))
            try:
                updated, changed = merge_publication(publication, results)
            except Exception as exc:  # preserve the record and report the exact DOI
                updated, changed = publication, False
                failures.append(f"{doi}: {exc}")
        output.append(updated)
        processed_count += 1
        if changed:
            changed_count += 1

    errors = validate_publications(output, allow_missing=False)
    if errors:
        raise SystemExit("Validation failed after update:\n" + "\n".join(errors))
    if failures:
        print("Warnings:", file=sys.stderr)
        for failure in failures:
            print("- " + failure, file=sys.stderr)
    if not args.dry_run and output != publications:
        write_publications(args.publications, output)
    print(f"Processed {processed_count} publications; {changed_count} records changed; {len(failures)} failures.")


if __name__ == "__main__":
    main()
