#!/usr/bin/env python3
"""Synchronize selected GRB project records with data/projects.json.

The updater keeps data/projects.json as the single formal source of truth:
- known GRB records only receive values for fields that are currently blank;
- values are accepted only from exact GRB labels/selectors and fixed formats;
- newly discovered records are retained for manual review instead of being published;
- all non-blank JSON values remain authoritative;
- failed or incomplete GRB responses never blank existing data;
- removing a tracked GRB project from projects.json records a persistent ignore tombstone;
- every newly discovered project remains in a pending-review file;
- the projects page is patched once to display GRB-reported funding.
"""

from __future__ import annotations

import argparse
import calendar
import copy
import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, Tag

LOGGER = logging.getLogger("grb-projects")
TAIPEI = ZoneInfo("Asia/Taipei")
DEFAULT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT = 35

EXACT_LABELS: dict[str, str] = {
    "計畫系統編號": "systemId",
    "計畫編號": "number",
    "計畫中文名稱": "titleZh",
    "計畫英文名稱": "titleEn",
    "主管機關": "agencyZh",
    "研究性質": "researchNatureZh",
    "研究方式": "researchMethodZh",
    "研究期間": "periodRaw",
    "本期研究期間": "periodRaw",
    "執行機構": "institutionZh",
    "年度": "yearRaw",
    "研究領域": "researchFieldZh",
    "研究經費": "fundingRaw",
    "本期經費(千元)": "fundingRaw",
    "本期經費（千元）": "fundingRaw",
    "研究人員": "researchersRaw",
}

REQUIRED_EXACT_FIELDS = {
    "systemId",
    "number",
    "titleZh",
    "titleEn",
    "agencyZh",
    "periodRaw",
    "institutionZh",
    "fundingRaw",
    "researchersRaw",
}

AGENCY_EN = {
    "國家科學及技術委員會": "National Science and Technology Council, Taiwan",
    "科技部": "Ministry of Science and Technology, Taiwan",
    "行政院國家科學委員會": "National Science Council, Taiwan",
}

MONTHS = ("Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.", "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec.")

PROJECT_UI_MARKER_START = "/* GRB_PROJECT_FUNDING_START */"
PROJECT_UI_MARKER_END = "/* GRB_PROJECT_FUNDING_END */"
PROJECT_UI_BLOCK = r'''/* GRB_PROJECT_FUNDING_START */
function formatProjectFunding(p){
  const amount=Number(p.fundingAmountTwd);
  if(!Number.isFinite(amount)||amount<=0)return '';
  return new Intl.NumberFormat('en-US',{style:'currency',currency:'TWD',maximumFractionDigits:0}).format(amount);
}
function projectCard(p){
  const funding=formatProjectFunding(p);
  const fundingRow=funding?`<p class="meta-row"><strong>GRB-reported funding:</strong> ${esc(funding)}${p.fundingAmountK?` <span lang="zh-Hant">（本期經費 ${esc(Number(p.fundingAmountK).toLocaleString())} 千元）</span>`:''}</p>`:'';
  const agency=p.agencyEn||p.agencyZh||'';
  const summary=p.scopeEn?`<p class="summary">${esc(p.scopeEn)}</p>`:'';
  const autoAdded=p.autoAddedFromGRB?'<span class="card-label">GRB auto-synced</span>':'';
  return `<article class="collection-card"><div class="card-heading"><h4>${p.url?`<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.titleEn||p.titleZh)}</a>`:esc(p.titleEn||p.titleZh)}</h4><span class="date-badge">${esc(p.period||p.startYear)}</span></div>${p.titleZh?`<div class="local-title" lang="zh-Hant">${esc(p.titleZh)}</div>`:''}<div class="card-labels"><span class="card-label">${esc(p.status)}</span><span class="card-label">${esc(p.role)} · ${esc(p.roleZh)}</span>${p.number?`<span class="card-label">${esc(p.number)}</span>`:''}${autoAdded}</div>${agency?`<p>${esc(agency)}</p>`:''}${fundingRow}${summary}${p.url?`<div class="card-actions"><a class="action" href="${esc(p.url)}" target="_blank" rel="noopener">Project record ↗</a></div>`:''}</article>`;
}
/* GRB_PROJECT_FUNDING_END */'''


class UpdateError(RuntimeError):
    """Raised for unsafe or invalid synchronization results."""


@dataclass
class FetchResult:
    url: str
    ok: bool
    status_code: int | None
    html: str = ""
    error: str = ""


def now_iso() -> str:
    return datetime.now(TAIPEI).replace(microsecond=0).isoformat()


def today_iso() -> str:
    return datetime.now(TAIPEI).date().isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UpdateError(f"Unable to read valid JSON from {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip(" \t\r\n:：|")


def exact_label(value: Any) -> str:
    return re.sub(r"\s+", "", clean_text(value)).rstrip(":：")


def normalized_identity(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", clean_text(value).lower())


def value_from_adjacent(element: Tag) -> str:
    # Typical table layouts.
    if element.name in {"th", "td"}:
        sibling = element.find_next_sibling(["td", "th"])
        if sibling:
            return clean_text(sibling.get_text(" ", strip=True))
    # Typical Bootstrap rows: label and value are sibling columns.
    parent = element.parent if isinstance(element.parent, Tag) else None
    if parent:
        siblings = [child for child in parent.find_all(recursive=False) if isinstance(child, Tag)]
        if len(siblings) >= 2:
            try:
                index = siblings.index(element)
            except ValueError:
                index = -1
            if 0 <= index < len(siblings) - 1:
                candidate = clean_text(siblings[index + 1].get_text(" ", strip=True))
                if candidate:
                    return candidate
        next_parent = parent.find_next_sibling()
        if isinstance(next_parent, Tag):
            candidate = clean_text(next_parent.get_text(" ", strip=True))
            if candidate:
                return candidate
    sibling = element.find_next_sibling()
    if isinstance(sibling, Tag):
        return clean_text(sibling.get_text(" ", strip=True))
    return ""


def extract_label_values(soup: BeautifulSoup) -> dict[str, str]:
    fields: dict[str, str] = {}

    # Accept only exact, allow-listed labels with an explicit paired value.
    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) != 2:
            continue
        key = EXACT_LABELS.get(exact_label(cells[0].get_text(" ", strip=True)))
        value = clean_text(cells[1].get_text(" ", strip=True))
        if key and value and key not in fields:
            fields[key] = value

    for dt in soup.find_all("dt"):
        key = EXACT_LABELS.get(exact_label(dt.get_text(" ", strip=True)))
        dd = dt.find_next_sibling("dd")
        value = clean_text(dd.get_text(" ", strip=True)) if dd else ""
        if key and value and key not in fields:
            fields[key] = value

    # Current GRB detail pages use paired div/span columns. The label itself
    # must still be an exact allow-listed value; no page-wide line fallback.
    for element in soup.find_all(["label", "strong", "span", "div", "p"]):
        direct_text = clean_text(" ".join(element.find_all(string=True, recursive=False)))
        key = EXACT_LABELS.get(exact_label(direct_text))
        if not key or key in fields:
            continue
        value = value_from_adjacent(element)
        if value and exact_label(value) not in EXACT_LABELS:
            fields[key] = value

    return fields


def extract_title(soup: BeautifulSoup, fields: dict[str, str], language: str) -> str:
    key = "titleZh" if language == "zh" else "titleEn"
    if clean_text(fields.get(key)):
        return clean_text(fields[key])

    # Current GRB detail pages place the Chinese title in .planTitle and the
    # English title in its .planTitleen child. Prefer these explicit selectors
    # over modal headings elsewhere on the page.
    if language == "en":
        element = soup.select_one(".planTitleen")
        if element:
            value = clean_text(element.get_text(" ", strip=True))
            if value:
                return value
    else:
        element = soup.select_one(".planTitle")
        if element:
            direct = clean_text(" ".join(element.find_all(string=True, recursive=False)))
            if direct:
                return direct

    # Do not guess titles from generic page headings or metadata.
    return ""


def parse_funding_k(raw: str) -> int | None:
    text = clean_text(raw).replace(",", "")
    match = re.fullmatch(r"(\d+)千元", text)
    if not match:
        return None
    return int(match.group(1))


def roc_to_ad(year: int) -> int:
    return year + 1911 if 0 < year < 1911 else year


def format_site_date(value: date) -> str:
    return f"{value.day} {MONTHS[value.month - 1]} {value.year}"


def parse_period(raw: str) -> dict[str, Any]:
    match = re.fullmatch(
        r"(\d{3})(0[1-9]|1[0-2])\s*[~～]\s*(\d{3})(0[1-9]|1[0-2])",
        clean_text(raw),
    )
    if not match:
        return {}
    start_year, start_month, end_year, end_month = map(int, match.groups())
    start = date(roc_to_ad(start_year), start_month, 1)
    end_ad_year = roc_to_ad(end_year)
    end = date(end_ad_year, end_month, calendar.monthrange(end_ad_year, end_month)[1])
    result: dict[str, Any] = {
        "startYear": start.year,
        "sortDate": start.isoformat(),
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "period": f"{format_site_date(start)} – {format_site_date(end)}",
    }
    today = datetime.now(TAIPEI).date()
    result["status"] = "Upcoming" if today < start else ("Completed" if today > end else "Ongoing")
    return result


def validate_fixed_record(fields: dict[str, str]) -> None:
    missing = sorted(REQUIRED_EXACT_FIELDS - fields.keys())
    if missing:
        raise UpdateError(f"Missing exact GRB labels: {', '.join(missing)}")
    if not re.fullmatch(r"PB\d{5}-\d{4}", fields["systemId"]):
        raise UpdateError("GRB system number does not match PB#####-####")
    if not re.fullmatch(r"(?:NSTC|MOST|NSC)\d{3}-\d{4}-[A-Z]\d{3}-\d{3}", fields["number"]):
        raise UpdateError("GRB plan number does not match the approved fixed format")
    if len(fields["titleZh"]) < 8 or not re.search(r"[\u3400-\u9fff]", fields["titleZh"]):
        raise UpdateError("GRB Chinese title does not match the approved fixed format")
    if len(fields["titleEn"].split()) < 4 or re.search(r"[\u3400-\u9fff]", fields["titleEn"]):
        raise UpdateError("GRB English title does not match the approved fixed format")
    if not parse_period(fields["periodRaw"]):
        raise UpdateError("GRB research period does not match RRRMM ~ RRRMM")
    if parse_funding_k(fields["fundingRaw"]) is None:
        raise UpdateError("GRB funding does not match NNN千元")
    if fields.get("yearRaw") and not re.fullmatch(r"\d{3}年?", fields["yearRaw"]):
        raise UpdateError("GRB year does not match RRR年")


def parse_plan_html(html: str, url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    raw_page_text = clean_text(soup.get_text(" ", strip=True))
    maintenance_detected = (
        "系統目前更新中" in raw_page_text
        or "暫停所有對外服務" in raw_page_text
    )

    # GRB currently embeds an old, normally hidden maintenance announcement at
    # the end of otherwise valid detail pages. It must not invalidate a page
    # that already contains real project fields. Remove only the dedicated
    # maintenance container before parsing visible project content.
    for node in soup.select("#no-service-container, .no-service-container"):
        node.decompose()

    page_text = clean_text(soup.get_text(" ", strip=True))
    if len(page_text) < 100:
        if maintenance_detected:
            raise UpdateError("GRB returned a maintenance page")
        raise UpdateError("GRB response is unexpectedly short")

    fields = extract_label_values(soup)
    fields["titleZh"] = extract_title(soup, fields, "zh")
    fields["titleEn"] = extract_title(soup, fields, "en")
    validate_fixed_record(fields)

    # Only treat a response as maintenance when no formal project identity was
    # found. This prevents hidden announcement markup from causing false errors.
    if maintenance_detected and not clean_text(fields.get("number") or fields.get("systemId")):
        raise UpdateError("GRB returned a maintenance page")

    funding_k = parse_funding_k(fields.get("fundingRaw", ""))
    period = parse_period(fields.get("periodRaw", ""))

    record: dict[str, Any] = {
        "url": url,
        "grbId": extract_grb_id(url),
        "grbSystemNumber": fields["systemId"],
        **{key: clean_text(value) for key, value in fields.items() if clean_text(value)},
        **period,
    }
    if funding_k is not None:
        record.update(
            {
                "fundingAmountK": funding_k,
                "fundingAmountTwd": funding_k * 1000,
                "fundingDisplayEn": f"NT${funding_k * 1000:,.0f}",
                "fundingDisplayZh": f"新臺幣 {funding_k * 1000:,} 元",
                "fundingSource": "GRB",
                "fundingNote": "GRB-reported current-period funding (本期經費)",
            }
        )
    if record.get("agencyZh"):
        agency_key = re.sub(r"\s*[（(][^）)]*[）)]\s*$", "", record["agencyZh"]).strip()
        record["agencyEn"] = AGENCY_EN.get(agency_key, "")
    return record


def extract_grb_id(value: str) -> str:
    match = re.search(r"(?:[?&]id=|/)(\d{5,})(?:\D|$)", str(value or ""))
    return match.group(1) if match else ""


def create_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
            "Cache-Control": "no-cache",
        }
    )
    return session


def fetch_url(session: requests.Session, url: str, retries: int = 3, timeout: int = DEFAULT_TIMEOUT) -> FetchResult:
    last_error = ""
    status_code: int | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=timeout, allow_redirects=True)
            status_code = response.status_code
            response.raise_for_status()
            if "text/html" not in response.headers.get("content-type", "").lower():
                raise UpdateError(f"Unexpected content type: {response.headers.get('content-type')}")
            return FetchResult(url=url, ok=True, status_code=status_code, html=response.text)
        except (requests.RequestException, UpdateError) as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(attempt * 2)
    return FetchResult(url=url, ok=False, status_code=status_code, error=last_error)


def record_key(record: dict[str, Any]) -> str:
    grb_id = clean_text(record.get("grbId")) or extract_grb_id(record.get("url", ""))
    if grb_id:
        return f"grb:{grb_id}"
    number = normalized_identity(record.get("number"))
    if number:
        return f"number:{number}"
    return f"title:{normalized_identity(record.get('titleZh') or record.get('titleEn'))}"


def plan_matches(project: dict[str, Any], source: dict[str, Any]) -> bool:
    source_id = clean_text(source.get("grbId"))
    project_id = clean_text(project.get("grbId")) or extract_grb_id(project.get("url", ""))
    if source_id and source_id == project_id:
        return True
    source_number = normalized_identity(source.get("number"))
    project_number = normalized_identity(project.get("number"))
    return bool(source_number and source_number == project_number)


def is_blank(value: Any) -> bool:
    if value in (None, "", [], {}):
        return True
    return isinstance(value, str) and not value.strip()


def should_fill_blank(existing: Any, incoming: Any) -> bool:
    return is_blank(existing) and not is_blank(incoming)


def merge_known_project(project: dict[str, Any], parsed: dict[str, Any], source: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    updated = copy.deepcopy(project)
    changed: list[str] = []

    # Automation may only fill empty JSON fields. Non-empty values are
    # maintained manually and must never be replaced by a GRB fetch.
    automatic_fields = (
        "grbId",
        "grbSystemNumber",
        "url",
        "number",
        "agencyZh",
        "agencyEn",
        "researchNatureZh",
        "researchMethodZh",
        "researchFieldZh",
        "institutionZh",
        "researchersRaw",
        "yearRaw",
        "periodRaw",
        "fundingRaw",
        "period",
        "startYear",
        "sortDate",
        "startDate",
        "endDate",
        "status",
        "fundingAmountK",
        "fundingAmountTwd",
        "fundingDisplayEn",
        "fundingDisplayZh",
        "fundingSource",
        "fundingNote",
    )
    for field in automatic_fields:
        incoming = parsed.get(field)
        if should_fill_blank(updated.get(field), incoming):
            updated[field] = incoming
            changed.append(field)

    # Titles follow the same blank-only rule; configuration cannot overwrite
    # manually maintained wording.
    for field in ("titleZh", "titleEn"):
        incoming = parsed.get(field)
        if should_fill_blank(updated.get(field), incoming):
            updated[field] = incoming
            changed.append(field)

    for field, incoming in (
        ("dataSource", "GRB"),
        ("grbSourceUrl", parsed.get("url") or source.get("url")),
    ):
        if should_fill_blank(updated.get(field), incoming):
            updated[field] = incoming
            changed.append(field)
    if changed and is_blank(updated.get("grbLastChanged")):
        updated["grbLastChanged"] = now_iso()
    return updated, changed


def discovery_match_details(parsed: dict[str, Any], config: dict[str, Any]) -> dict[str, bool]:
    researchers = normalized_identity(parsed.get("researchersRaw"))
    institution = normalized_identity(parsed.get("institutionZh"))
    name_match = any(normalized_identity(alias) in researchers for alias in config.get("researcherAliases", []))
    institution_match = any(normalized_identity(alias) in institution for alias in config.get("institutionAliases", []))
    return {
        "nameMatch": bool(name_match),
        "institutionMatch": bool(institution_match),
        "hasNumber": bool(clean_text(parsed.get("number"))),
        "hasGrbId": bool(clean_text(parsed.get("grbId"))),
        "hasTitle": bool(clean_text(parsed.get("titleZh") or parsed.get("titleEn"))),
    }


def strict_discovery_match(parsed: dict[str, Any], config: dict[str, Any]) -> bool:
    details = discovery_match_details(parsed, config)
    return all(details.values())


def project_grb_id(project: dict[str, Any]) -> str:
    return clean_text(project.get("grbId")) or extract_grb_id(project.get("grbSourceUrl", "")) or extract_grb_id(project.get("url", ""))


def source_from_project(project: dict[str, Any]) -> dict[str, Any] | None:
    grb_id = project_grb_id(project)
    if not grb_id:
        return None
    return {
        "grbId": grb_id,
        "number": clean_text(project.get("number")),
        "url": clean_text(project.get("grbSourceUrl") or project.get("url")) or f"https://www.grb.gov.tw/search/planDetail?id={grb_id}",
        "autoManaged": True,
    }


def sync_tracking_config(projects: list[dict[str, Any]], config: dict[str, Any], *, detect_manual_removal: bool) -> dict[str, Any]:
    updated = copy.deepcopy(config)
    ignored = {clean_text(value) for value in updated.get("ignoredGrbIds", []) if clean_text(value)}
    current_sources: dict[str, dict[str, Any]] = {}
    for project in projects:
        source = source_from_project(project)
        if not source:
            continue
        grb_id = source["grbId"]
        current_sources[grb_id] = source
        # Explicitly restoring a formal project also restores tracking.
        ignored.discard(grb_id)

    existing_sources: dict[str, dict[str, Any]] = {}
    for source in updated.get("knownPlans", []):
        if not isinstance(source, dict):
            continue
        grb_id = clean_text(source.get("grbId")) or extract_grb_id(source.get("url", ""))
        if grb_id:
            existing_sources[grb_id] = copy.deepcopy(source)

    removed_history = [item for item in updated.get("removedPlans", []) if isinstance(item, dict)]
    removed_ids = {clean_text(item.get("grbId")) for item in removed_history}
    if detect_manual_removal and bool(updated.get("treatMissingTrackedProjectsAsIgnored", True)):
        for grb_id, source in existing_sources.items():
            if grb_id in current_sources or grb_id in ignored:
                continue
            ignored.add(grb_id)
            if grb_id not in removed_ids:
                removed_history.append({
                    "grbId": grb_id,
                    "number": clean_text(source.get("number")),
                    "removedAt": now_iso(),
                    "reason": "Missing from data/projects.json; treated as an intentional manual removal.",
                })

    merged_sources: list[dict[str, Any]] = []
    for grb_id, source in sorted(current_sources.items()):
        if grb_id in ignored:
            continue
        existing = existing_sources.get(grb_id, {})
        merged = {**existing, **source}
        merged_sources.append(merged)

    updated["knownPlans"] = merged_sources
    updated["ignoredGrbIds"] = sorted(ignored)
    updated["removedPlans"] = removed_history
    return updated


def discover_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "")
        if "planDetail" not in href or not extract_grb_id(href):
            continue
        links.append(urljoin(base_url, href))
    # Some pages embed URLs in scripts instead of anchors.
    for match in re.findall(r"(?:https?://www\.grb\.gov\.tw)?/search/planDetail\?id=\d+", html):
        links.append(urljoin(base_url, match))
    return list(dict.fromkeys(links))


def patch_project_ui(app_js_path: Path) -> bool:
    source = app_js_path.read_text(encoding="utf-8")
    if PROJECT_UI_MARKER_START in source and PROJECT_UI_MARKER_END in source:
        marker_pattern = re.compile(
            re.escape(PROJECT_UI_MARKER_START) + r".*?" + re.escape(PROJECT_UI_MARKER_END),
            re.DOTALL,
        )
        replacement, count = marker_pattern.subn(PROJECT_UI_BLOCK, source, count=1)
        if count != 1:
            raise UpdateError("Unable to refresh the existing GRB project UI block")
        if replacement == source:
            return False
        app_js_path.write_text(replacement, encoding="utf-8")
        return True
    pattern = re.compile(r"function projectCard\(p\)\{return .*?\}\n(?=function awardCard)", re.DOTALL)
    replacement, count = pattern.subn(PROJECT_UI_BLOCK + "\n", source, count=1)
    if count != 1:
        raise UpdateError("Unable to locate the projectCard function in assets/js/app.js")
    app_js_path.write_text(replacement, encoding="utf-8")
    return True


def validate_projects(projects: Any) -> None:
    if not isinstance(projects, list):
        raise UpdateError("data/projects.json must contain an array")
    seen: set[str] = set()
    for index, project in enumerate(projects):
        if not isinstance(project, dict):
            raise UpdateError(f"Project at index {index} is not an object")
        for required in ("titleEn", "titleZh", "startYear", "sortDate"):
            if project.get(required) in (None, ""):
                raise UpdateError(f"Project at index {index} is missing {required}")
        key = record_key(project)
        if key in seen:
            raise UpdateError(f"Duplicate project identity: {key}")
        seen.add(key)
        amount_k = project.get("fundingAmountK")
        amount_twd = project.get("fundingAmountTwd")
        if amount_k not in (None, ""):
            if not isinstance(amount_k, int) or amount_k < 0:
                raise UpdateError(f"Invalid fundingAmountK for {key}")
            if amount_twd != amount_k * 1000:
                raise UpdateError(f"fundingAmountTwd does not match fundingAmountK for {key}")


def update_site_meta(path: Path) -> bool:
    meta = read_json(path, {})
    today = today_iso()
    if meta.get("lastUpdated") == today:
        return False
    meta["lastUpdated"] = today
    write_json(path, meta)
    return True


def run_update(root: Path, allow_network_failure: bool, patch_ui: bool) -> int:
    projects_path = root / "data/projects.json"
    config_path = root / "data/grb_project_sources.json"
    snapshot_path = root / "data/grb_projects_snapshot.json"
    pending_path = root / "data/grb_projects_pending.json"
    app_js_path = root / "assets/js/app.js"
    site_meta_path = root / "data/site_meta.json"

    projects = read_json(projects_path, [])
    original_projects = copy.deepcopy(projects)
    config = read_json(config_path, {})
    original_config = copy.deepcopy(config)
    validate_projects(projects)
    # projects.json is authoritative. A tracked plan missing from it is considered manually removed.
    config = sync_tracking_config(projects, config, detect_manual_removal=True)

    ui_changed = patch_project_ui(app_js_path) if patch_ui else False
    session = create_session(config.get("userAgent", "Wei-Hao-Chiu-Academic-Site-GRB-Updater/1.0 (+https://weihaochiu.github.io/)"))
    checked_at = now_iso()
    snapshot: dict[str, Any] = {
        "source": "Government Research Bulletin (GRB), Taiwan",
        "sourceUrl": "https://www.grb.gov.tw/",
        "checkedAt": checked_at,
        "records": {},
        "discovery": [],
    }

    success_count = 0
    known_sources = config.get("knownPlans", [])
    for source in known_sources:
        grb_id = clean_text(source.get("grbId"))
        url = source.get("url") or f"https://www.grb.gov.tw/search/planDetail?id={grb_id}"
        result = fetch_url(session, url)
        snapshot_entry: dict[str, Any] = {
            "grbId": grb_id,
            "url": url,
            "ok": result.ok,
            "statusCode": result.status_code,
        }
        if not result.ok:
            snapshot_entry["error"] = result.error
            snapshot["records"][grb_id or url] = snapshot_entry
            LOGGER.warning("Unable to fetch %s: %s", url, result.error)
            continue
        try:
            parsed = parse_plan_html(result.html, url)
            if source.get("number") and parsed.get("number"):
                if normalized_identity(source["number"]) != normalized_identity(parsed["number"]):
                    raise UpdateError(f"Plan number mismatch: expected {source['number']}, got {parsed['number']}")
            if not (parsed.get("number") or parsed.get("titleZh")):
                raise UpdateError("GRB detail page did not contain a recognizable project record")
            match_index = next((i for i, project in enumerate(projects) if plan_matches(project, source)), None)
            if match_index is None:
                raise UpdateError("Known GRB plan does not match any existing project; refusing automatic insertion")
            merged, changed_fields = merge_known_project(projects[match_index], parsed, source)
            projects[match_index] = merged
            snapshot_entry.update({"parsed": parsed, "changedFields": changed_fields})
            success_count += 1
        except UpdateError as exc:
            snapshot_entry.update({"ok": False, "error": str(exc)})
            LOGGER.warning("Rejected GRB response for %s: %s", url, exc)
        snapshot["records"][grb_id or url] = snapshot_entry

    pending = read_json(pending_path, [])
    if not isinstance(pending, list):
        pending = []
    pending_by_key = {record_key(item): item for item in pending if isinstance(item, dict)}
    ignored_ids = {clean_text(value) for value in config.get("ignoredGrbIds", []) if clean_text(value)}
    known_keys = {record_key(project) for project in projects}
    discovered_urls: list[str] = []
    for discovery_url in config.get("discoveryUrls", []):
        result = fetch_url(session, discovery_url)
        discovery_entry: dict[str, Any] = {
            "url": discovery_url,
            "ok": result.ok,
            "statusCode": result.status_code,
        }
        if result.ok:
            discovered = discover_links(result.html, discovery_url)
            discovery_entry["linksFound"] = len(discovered)
            discovered_urls.extend(discovered)
        else:
            discovery_entry["error"] = result.error
        snapshot["discovery"].append(discovery_entry)

    max_candidates = int(config.get("maxDiscoveryCandidates", 20))
    for url in list(dict.fromkeys(discovered_urls))[:max_candidates]:
        candidate_id = extract_grb_id(url)
        candidate_key = f"grb:{candidate_id}"
        if not candidate_id or candidate_id in ignored_ids or candidate_key in known_keys:
            pending_by_key.pop(candidate_key, None)
            continue
        result = fetch_url(session, url)
        if not result.ok:
            continue
        try:
            parsed = parse_plan_html(result.html, url)
        except UpdateError:
            continue
        details = discovery_match_details(parsed, config)
        # Discovery is review-only. Even a complete exact-format match must be
        # added to projects.json manually before automation can fill blanks.
        if strict_discovery_match(parsed, config) or details["nameMatch"] or details["institutionMatch"]:
            parsed.update({
                "reviewRequired": True,
                "detectedAt": checked_at,
                "reviewReason": "Discovery is review-only; add the project to data/projects.json manually.",
                "match": details,
            })
            pending_by_key[record_key(parsed)] = parsed

    # Manually published records are added to continuous tracking.
    config = sync_tracking_config(projects, config, detect_manual_removal=False)
    active_ids = {project_grb_id(project) for project in projects if project_grb_id(project)}
    ignored_ids = {clean_text(value) for value in config.get("ignoredGrbIds", []) if clean_text(value)}
    pending = [
        item for item in pending_by_key.values()
        if clean_text(item.get("grbId")) not in active_ids
        and clean_text(item.get("grbId")) not in ignored_ids
    ]
    pending = sorted(pending, key=lambda item: str(item.get("sortDate") or item.get("detectedAt") or ""), reverse=True)

    if success_count == 0 and known_sources and not allow_network_failure:
        raise UpdateError("No known GRB record could be updated")

    # Hard safety rules: this updater never deletes projects or blanks required fields.
    if len(projects) < len(original_projects):
        raise UpdateError("Project count decreased; refusing to write")
    validate_projects(projects)

    projects.sort(key=lambda item: str(item.get("sortDate") or ""), reverse=True)
    projects_changed = projects != original_projects
    config_changed = config != original_config
    write_json(snapshot_path, snapshot)
    write_json(pending_path, pending)
    if projects_changed:
        write_json(projects_path, projects)
    if config_changed:
        write_json(config_path, config)

    site_meta_changed = False
    if projects_changed or ui_changed:
        site_meta_changed = update_site_meta(site_meta_path)

    LOGGER.info(
        "GRB update complete: %d/%d known records fetched; discovery_mode=review-only; projects_changed=%s; config_changed=%s; ui_changed=%s; pending=%d; site_meta_changed=%s",
        success_count,
        len(known_sources),
        projects_changed,
        config_changed,
        ui_changed,
        len(pending),
        site_meta_changed,
    )
    return 0


def run_validation(root: Path) -> int:
    validate_projects(read_json(root / "data/projects.json", []))
    app_js = (root / "assets/js/app.js").read_text(encoding="utf-8")
    if PROJECT_UI_MARKER_START not in app_js or PROJECT_UI_MARKER_END not in app_js:
        raise UpdateError("GRB funding UI marker is missing from assets/js/app.js")
    config = json.loads((root / "data/grb_project_sources.json").read_text(encoding="utf-8"))
    if config.get("discoveryMode") != "review-only":
        raise UpdateError("GRB discoveryMode must remain review-only")
    LOGGER.info("Validation completed successfully")
    return 0


def run_self_test() -> int:
    sample = """
    <html><body>
    <div class="planTitle">測試型鈣鈦礦計畫
      <span class="planTitleen">Test Perovskite Research Project</span>
    </div>
    <table>
      <tr><th>計畫系統編號</th><td>PB11411-0001</td></tr>
      <tr><th>計畫編號</th><td>NSTC114-0000-E182-001</td></tr>
      <tr><th>主管機關</th><td>國家科學及技術委員會</td></tr>
      <tr><th>本期研究期間</th><td>11411 ～ 11510</td></tr>
      <tr><th>本期經費(千元)</th><td>1,200千元</td></tr>
      <tr><th>執行機構</th><td>長庚大學</td></tr>
      <tr><th>研究人員</th><td>計畫主持人：邱偉豪</td></tr>
    </table></body></html>
    """
    parsed = parse_plan_html(sample, "https://www.grb.gov.tw/search/planDetail?id=12345678")
    assert parsed["fundingAmountK"] == 1200
    assert parsed["fundingAmountTwd"] == 1_200_000
    assert parsed["startDate"] == "2025-11-01"
    assert parsed["endDate"] == "2026-10-31"
    assert parsed["number"] == "NSTC114-0000-E182-001"
    assert parsed["grbSystemNumber"] == "PB11411-0001"

    rendered_sample = """
    <html><body>
      <div class="planTitle">實際 GRB 測試計畫
        <span class="planTitleen">Rendered GRB Test Project</span>
      </div>
      <div><span>計畫系統編號</span><span>PB11412-5590</span></div>
      <div><span>計畫編號</span><span>NSTC114-2622-E182-006</span></div>
      <div><span>主管機關</span><span>國家科學及技術委員會(本會)</span></div>
      <div><span>研究期間</span><span>11411 ~ 11510</span></div>
      <div><span>執行機構</span><span>長庚大學綠色科技研究中心</span></div>
      <div><span>研究經費</span><span>622千元</span></div>
      <div><span>研究人員</span><span>邱偉豪</span></div>
      <div id="no-service-container">
        本系統將於 5/30 進行系統升級作業，期間將暫停所有對外服務
      </div>
    </body></html>
    """
    rendered = parse_plan_html(
        rendered_sample,
        "https://www.grb.gov.tw/search/planDetail?id=18623445",
    )
    assert rendered["titleZh"] == "實際 GRB 測試計畫"
    assert rendered["titleEn"] == "Rendered GRB Test Project"
    assert rendered["fundingAmountK"] == 622
    assert rendered["fundingAmountTwd"] == 622_000
    assert rendered["startDate"] == "2025-11-01"
    assert rendered["endDate"] == "2026-10-31"
    assert rendered["agencyEn"] == "National Science and Technology Council, Taiwan"

    existing = {
        "titleZh": "人工中文題名",
        "titleEn": "",
        "number": "NSTC114-0000-E182-001",
        "fundingAmountK": 999,
    }
    merged, changed = merge_known_project(existing, parsed, {"url": parsed["url"]})
    assert merged["titleZh"] == "人工中文題名"
    assert merged["fundingAmountK"] == 999
    assert merged["titleEn"] == "Test Perovskite Research Project"
    assert "titleEn" in changed and "titleZh" not in changed and "fundingAmountK" not in changed

    config = {
        "researcherAliases": ["邱偉豪"],
        "institutionAliases": ["長庚大學"],
        "knownPlans": [],
        "ignoredGrbIds": [],
        "treatMissingTrackedProjectsAsIgnored": True,
    }
    assert strict_discovery_match(parsed, config)
    project = {
        "titleEn": "",
        "titleZh": "人工新增測試計畫",
        "startYear": 2025,
        "sortDate": "2025-11-01",
        "number": parsed["number"],
        "grbId": parsed["grbId"],
        "grbSourceUrl": parsed["url"],
    }
    tracked = sync_tracking_config([project], config, detect_manual_removal=True)
    assert tracked["knownPlans"][0]["grbId"] == "12345678"
    removed = sync_tracking_config([], tracked, detect_manual_removal=True)
    assert "12345678" in removed["ignoredGrbIds"]
    assert removed["knownPlans"] == []
    restored = sync_tracking_config([project], removed, detect_manual_removal=True)
    assert "12345678" not in restored["ignoredGrbIds"]
    assert restored["knownPlans"][0]["grbId"] == "12345678"
    LOGGER.info("Self-test completed successfully")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Repository root")
    parser.add_argument("--allow-network-failure", action="store_true", help="Preserve old data and exit successfully if GRB is unavailable")
    parser.add_argument("--patch-ui", action="store_true", help="Patch the project card renderer to show GRB funding")
    parser.add_argument("--validate-only", action="store_true", help="Validate generated files without network access")
    parser.add_argument("--self-test", action="store_true", help="Run parser self-tests")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        if args.self_test:
            return run_self_test()
        if args.validate_only:
            return run_validation(args.root.resolve())
        return run_update(args.root.resolve(), args.allow_network_failure, args.patch_ui)
    except (UpdateError, OSError, json.JSONDecodeError, AssertionError) as exc:
        LOGGER.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
