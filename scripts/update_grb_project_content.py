#!/usr/bin/env python3
"""Synchronize GRB project abstracts and keywords and install the Projects UI.

This module is intentionally separate from update_grb_projects.py so the existing
project/funding synchronizer remains stable. It:

- reads official Chinese/English abstracts and keywords from GRB detail pages;
- preserves the last valid value whenever GRB is unavailable or incomplete;
- stores structured fields in data/projects.json;
- replaces the generated projectCard block in assets/js/app.js;
- installs matching responsive styles in assets/css/styles.css.

The GitHub Action runs this after the existing requests + Playwright GRB update.
"""

from __future__ import annotations

import argparse
import copy
import html
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

LOGGER = logging.getLogger("grb-project-content")
TAIPEI = ZoneInfo("Asia/Taipei")
ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = ROOT / "grb_debug"

UI_START = "/* GRB_PROJECT_FUNDING_START */"
UI_END = "/* GRB_PROJECT_FUNDING_END */"
CSS_START = "/* GRB_PROJECT_CONTENT_STYLES_START */"
CSS_END = "/* GRB_PROJECT_CONTENT_STYLES_END */"

CONTENT_FIELDS = ("abstractZh", "abstractEn", "keywordsZh", "keywordsEn")
ABSTRACT_FIELDS = ("abstractZh", "abstractEn")
KEYWORD_FIELDS = ("keywordsZh", "keywordsEn")

LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "abstractZh": (
        "中文摘要", "計畫中文摘要", "研究計畫中文摘要", "研究摘要", "中文研究摘要",
        "摘要（中文）", "摘要(中文)",
    ),
    "abstractEn": (
        "英文摘要", "計畫英文摘要", "研究計畫英文摘要", "英文研究摘要",
        "摘要（英文）", "摘要(英文)", "abstract", "english abstract",
    ),
    "keywordsZh": (
        "中文關鍵字", "中文關鍵詞", "計畫中文關鍵字", "研究計畫中文關鍵字",
        "關鍵字（中文）", "關鍵字(中文)",
    ),
    "keywordsEn": (
        "英文關鍵字", "英文關鍵詞", "計畫英文關鍵字", "研究計畫英文關鍵字",
        "關鍵字（英文）", "關鍵字(英文)", "keywords", "english keywords",
    ),
}

MAINTENANCE_MARKERS = (
    "系統目前更新中", "暫停所有對外服務", "系統維護", "maintenance",
)

UI_BLOCK = r'''/* GRB_PROJECT_FUNDING_START */
function formatProjectFunding(p){
  const amount=Number(p.fundingAmountTwd);
  if(!Number.isFinite(amount)||amount<=0)return '';
  return new Intl.NumberFormat('en-US',{style:'currency',currency:'TWD',maximumFractionDigits:0}).format(amount);
}
function normalizeProjectKeywords(value){
  const rows=Array.isArray(value)?value:String(value||'').split(/[;；、,，\n]+/);
  return [...new Set(rows.map(item=>String(item||'').trim()).filter(Boolean))];
}
function projectResearchDetails(p){
  const abstractZh=String(p.abstractZh||'').trim();
  const abstractEn=String(p.abstractEn||'').trim();
  const keywordsZh=normalizeProjectKeywords(p.keywordsZh);
  const keywordsEn=normalizeProjectKeywords(p.keywordsEn);
  if(!abstractZh&&!abstractEn&&!keywordsZh.length&&!keywordsEn.length)return '';
  const sections=[];
  if(abstractZh)sections.push(`<section class="project-detail-section" lang="zh-Hant"><h5>中文摘要</h5><p>${esc(abstractZh)}</p></section>`);
  if(abstractEn)sections.push(`<section class="project-detail-section" lang="en"><h5>English Abstract</h5><p>${esc(abstractEn)}</p></section>`);
  if(keywordsZh.length)sections.push(`<section class="project-detail-section" lang="zh-Hant"><h5>中文關鍵字</h5><div class="project-keywords">${keywordsZh.map(item=>`<span>${esc(item)}</span>`).join('')}</div></section>`);
  if(keywordsEn.length)sections.push(`<section class="project-detail-section" lang="en"><h5>English Keywords</h5><div class="project-keywords">${keywordsEn.map(item=>`<span>${esc(item)}</span>`).join('')}</div></section>`);
  const sourceUrl=normalizeExternalUrl(p.grbContentSourceUrl||p.grbSourceUrl||p.url);
  const source=sourceUrl?`<p class="project-detail-source">Source: <a href="${esc(sourceUrl)}" target="_blank" rel="noopener noreferrer">Government Research Bulletin (GRB) ↗</a></p>`:'<p class="project-detail-source">Source: Government Research Bulletin (GRB)</p>';
  return `<details class="project-research-details"><summary>Project abstracts and keywords <span lang="zh-Hant">／計畫摘要與關鍵字</span></summary><div class="project-detail-body">${sections.join('')}${source}</div></details>`;
}
function projectCard(p){
  const funding=formatProjectFunding(p);
  const fundingRow=funding?`<p class="meta-row"><strong>GRB-reported funding:</strong> ${esc(funding)}${p.fundingAmountK?` <span lang="zh-Hant">（本期經費 ${esc(Number(p.fundingAmountK).toLocaleString())} 千元）</span>`:''}</p>`:'';
  const agency=p.agencyEn||p.agencyZh||'';
  const summary=p.scopeEn?`<p class="summary">${esc(p.scopeEn)}</p>`:'';
  const autoAdded=p.autoAddedFromGRB?'<span class="card-label">GRB auto-synced</span>':'';
  const details=projectResearchDetails(p);
  return `<article class="collection-card project-card"><div class="card-heading"><h4>${p.url?`<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.titleEn||p.titleZh)}</a>`:esc(p.titleEn||p.titleZh)}</h4><span class="date-badge">${esc(p.period||p.startYear)}</span></div>${p.titleZh?`<div class="local-title" lang="zh-Hant">${esc(p.titleZh)}</div>`:''}<div class="card-labels"><span class="card-label">${esc(p.status)}</span><span class="card-label">${esc(p.role)} · ${esc(p.roleZh)}</span>${p.number?`<span class="card-label">${esc(p.number)}</span>`:''}${autoAdded}</div>${agency?`<p>${esc(agency)}</p>`:''}${fundingRow}${summary}${details}${p.url?`<div class="card-actions"><a class="action" href="${esc(p.url)}" target="_blank" rel="noopener">Project record ↗</a></div>`:''}</article>`;
}
/* GRB_PROJECT_FUNDING_END */'''

CSS_BLOCK = r'''/* GRB_PROJECT_CONTENT_STYLES_START */
/* GRB project abstracts and bilingual keywords */
.project-research-details{margin:13px 0 12px;border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--muted);font-size:.76rem}
.project-research-details>summary{padding:8px 11px;color:var(--brand);font-weight:750;cursor:pointer;list-style-position:inside}
.project-research-details[open]>summary{border-bottom:1px solid var(--line);background:#f6f8fa}
.project-detail-body{padding:2px 14px 13px}
.project-detail-section{padding:13px 0}
.project-detail-section+.project-detail-section{border-top:1px solid #e7ecf0}
.project-detail-section h5{margin:0 0 7px;color:#374957;font-family:"Source Serif 4","Noto Sans TC",serif;font-size:.88rem}
.project-detail-section p{max-width:92ch;margin:0;color:#455968;font-size:.78rem;line-height:1.82;white-space:pre-line}
.project-keywords{display:flex;flex-wrap:wrap;gap:7px}
.project-keywords span{display:inline-flex;padding:4px 9px;border:1px solid var(--line);border-radius:999px;background:#f4f6f8;color:#425b73;font-size:.7rem;font-weight:700;line-height:1.35}
.project-detail-source{margin:3px 0 0!important;padding-top:10px;border-top:1px solid #e7ecf0;color:var(--muted)!important;font-size:.68rem!important}
.project-detail-source a{color:var(--brand);font-weight:700;text-decoration:none}
.project-detail-source a:hover,.project-detail-source a:focus-visible{text-decoration:underline}
@media(max-width:760px){.project-research-details{font-size:.73rem}.project-detail-body{padding-left:11px;padding-right:11px}.project-detail-section p{font-size:.76rem;line-height:1.75}}
/* GRB_PROJECT_CONTENT_STYLES_END */'''


class ContentError(RuntimeError):
    pass


@dataclass
class FetchOutcome:
    url: str
    html_documents: list[str]
    json_payloads: list[Any]
    error: str = ""


def now_iso() -> str:
    return datetime.now(TAIPEI).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip(" \t\r\n:：|-")


def compact_key(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", clean_text(value).lower())


def alias_lookup() -> dict[str, str]:
    result: dict[str, str] = {}
    for field, aliases in LABEL_ALIASES.items():
        for alias in aliases:
            result[compact_key(alias)] = field
    return result


ALIASES = alias_lookup()


def has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value))


def valid_abstract(value: Any) -> str:
    text = clean_text(value)
    if len(text) < 40 or len(text) > 80_000:
        return ""
    low = text.lower()
    if any(marker.lower() in low for marker in MAINTENANCE_MARKERS):
        return ""
    if text.count("|") > 20 or text.count("[Button") > 2:
        return ""
    return text


def split_keywords(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_items: Iterable[Any] = value
    else:
        text = clean_text(value)
        if not text or len(text) > 5_000:
            return []
        raw_items = re.split(r"[;；、\n\r]+|(?<!\d)[,，](?!\d)", text)
    output: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        term = clean_text(item).strip(".;；,，、")
        key = compact_key(term)
        if not term or not key or len(term) > 180 or key in seen:
            continue
        if compact_key(term) in ALIASES:
            continue
        seen.add(key)
        output.append(term)
    return output[:80]


def field_from_label(label: Any) -> str:
    key = compact_key(label)
    if key in ALIASES:
        return ALIASES[key]
    # GRB occasionally adds punctuation or explanatory suffixes to labels.
    for alias, field in ALIASES.items():
        if len(alias) >= 4 and (key.startswith(alias) or alias.startswith(key)):
            return field
    return ""


def adjacent_value(element: Tag) -> str:
    if element.name in {"th", "td"}:
        sibling = element.find_next_sibling(["td", "th"])
        if sibling:
            return clean_text(sibling.get_text("\n", strip=True))
    parent = element.parent if isinstance(element.parent, Tag) else None
    if parent:
        siblings = [node for node in parent.find_all(recursive=False) if isinstance(node, Tag)]
        if element in siblings:
            index = siblings.index(element)
            for sibling in siblings[index + 1 :]:
                value = clean_text(sibling.get_text("\n", strip=True))
                if value:
                    return value
    sibling = element.find_next_sibling()
    if isinstance(sibling, Tag):
        return clean_text(sibling.get_text("\n", strip=True))
    return ""


def extract_labeled_content(soup: BeautifulSoup) -> dict[str, list[Any]]:
    found: dict[str, list[Any]] = {field: [] for field in CONTENT_FIELDS}

    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) < 2:
            continue
        field = field_from_label(cells[0].get_text(" ", strip=True))
        if field:
            found[field].append("\n".join(cell.get_text("\n", strip=True) for cell in cells[1:]))

    for dt in soup.find_all("dt"):
        field = field_from_label(dt.get_text(" ", strip=True))
        dd = dt.find_next_sibling("dd")
        if field and dd:
            found[field].append(dd.get_text("\n", strip=True))

    for element in soup.find_all(["label", "strong", "span", "div", "p", "h4", "h5"]):
        direct = clean_text(" ".join(element.find_all(string=True, recursive=False)))
        field = field_from_label(direct)
        if not field:
            continue
        value = adjacent_value(element)
        if value and not field_from_label(value):
            found[field].append(value)

    lines = [clean_text(line) for line in soup.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]
    for index, line in enumerate(lines):
        field = field_from_label(line)
        if field and index + 1 < len(lines):
            value = lines[index + 1]
            if not field_from_label(value):
                found[field].append(value)
        for separator in ("：", ":"):
            if separator not in line:
                continue
            label, value = line.split(separator, 1)
            field = field_from_label(label)
            if field and clean_text(value):
                found[field].append(value)

    return found


def classify_structured_key(key: Any, value: Any) -> str:
    normalized = compact_key(key)
    if not normalized:
        return ""
    is_abstract = any(token in normalized for token in ("abstract", "summary", "摘要"))
    is_keyword = any(token in normalized for token in ("keyword", "keywords", "keyw", "關鍵字", "關鍵詞"))
    if not (is_abstract or is_keyword):
        return ""

    zh_hint = any(token in normalized for token in ("zh", "ch", "chi", "cht", "cn", "中文", "chinese"))
    en_hint = any(token in normalized for token in ("en", "eng", "英文", "english"))
    text = clean_text(value)
    language = "Zh" if zh_hint and not en_hint else "En" if en_hint and not zh_hint else ("Zh" if has_cjk(text) else "En")
    return ("abstract" if is_abstract else "keywords") + language


def recursive_structured_candidates(value: Any, output: dict[str, list[Any]]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            field = classify_structured_key(key, item)
            if field:
                output[field].append(item)
            recursive_structured_candidates(item, output)
    elif isinstance(value, list):
        for item in value:
            recursive_structured_candidates(item, output)


def embedded_json_payloads(soup: BeautifulSoup) -> list[Any]:
    payloads: list[Any] = []
    for script in soup.find_all("script"):
        text = script.string or script.get_text("", strip=False)
        if not text or len(text) > 5_000_000:
            continue
        script_type = str(script.get("type") or "").lower()
        candidates: list[str] = []
        if "json" in script_type:
            candidates.append(text.strip())
        for match in re.finditer(r"(?s)(\{.{20,}?\}|\[.{20,}?\])", text):
            snippet = match.group(1).strip()
            if any(token in snippet.lower() for token in ("abstract", "keyword", "摘要", "關鍵")):
                candidates.append(snippet)
                if len(candidates) >= 20:
                    break
        for candidate in candidates:
            try:
                payloads.append(json.loads(candidate))
            except (json.JSONDecodeError, TypeError):
                continue
    return payloads


def choose_content(candidates: dict[str, list[Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in ABSTRACT_FIELDS:
        valid = [valid_abstract(value) for value in candidates[field]]
        valid = [value for value in valid if value]
        if valid:
            # The full official abstract is normally the longest candidate.
            result[field] = max(valid, key=len)
    for field in KEYWORD_FIELDS:
        sets = [split_keywords(value) for value in candidates[field]]
        sets = [value for value in sets if value]
        if sets:
            result[field] = max(sets, key=lambda values: (len(values), sum(map(len, values))))
    return result


def parse_documents(html_documents: Iterable[str], json_payloads: Iterable[Any] = ()) -> dict[str, Any]:
    candidates: dict[str, list[Any]] = {field: [] for field in CONTENT_FIELDS}
    payloads = list(json_payloads)
    for document in html_documents:
        if not document:
            continue
        soup = BeautifulSoup(document, "html.parser")
        for node in soup.select("#no-service-container, .no-service-container"):
            node.decompose()
        labeled = extract_labeled_content(soup)
        for field, values in labeled.items():
            candidates[field].extend(values)
        payloads.extend(embedded_json_payloads(soup))
    for payload in payloads:
        recursive_structured_candidates(payload, candidates)
    return choose_content(candidates)


def project_grb_url(project: dict[str, Any]) -> str:
    url = clean_text(project.get("grbSourceUrl") or project.get("url"))
    if url.startswith("https://www.grb.gov.tw/"):
        return url
    grb_id = clean_text(project.get("grbId"))
    return f"https://www.grb.gov.tw/search/planDetail?id={grb_id}" if grb_id else ""


def project_identity(project: dict[str, Any]) -> tuple[str, str]:
    return clean_text(project.get("grbId")), compact_key(project.get("number"))


def diagnostic_documents(project: dict[str, Any]) -> list[str]:
    if not DEBUG_DIR.exists():
        return []
    grb_id, number = project_identity(project)
    output: list[str] = []
    for path in sorted(DEBUG_DIR.glob("*.html")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        probe = compact_key(text[:500_000])
        filename = compact_key(path.name)
        if (grb_id and grb_id in filename + probe) or (number and number in probe):
            output.append(text)
    return output


def is_grb_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == "www.grb.gov.tw"


def browser_fetch(url: str, debug_name: str) -> FetchOutcome:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return FetchOutcome(url, [], [], f"Playwright unavailable: {exc}")

    html_documents: list[str] = []
    json_payloads: list[Any] = []
    errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(
            locale="zh-TW",
            timezone_id="Asia/Taipei",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            extra_http_headers={"Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7"},
        )

        def capture_response(response: Any) -> None:
            try:
                content_type = str(response.headers.get("content-type", "")).lower()
                if "json" not in content_type:
                    return
                payload = response.json()
                if payload not in (None, "", [], {}):
                    json_payloads.append(payload)
            except Exception:
                return

        page = context.new_page()
        page.on("response", capture_response)
        try:
            page.goto(url, wait_until="commit", timeout=35_000, referer="https://www.grb.gov.tw/")
            page.wait_for_selector("body", state="attached", timeout=12_000)
            page.wait_for_timeout(3_000)
            html_documents.append(page.content())

            # Collect linked summary/keyword pages without leaving the main record.
            link_targets: list[str] = []
            anchors = page.locator("a")
            for index in range(min(anchors.count(), 300)):
                anchor = anchors.nth(index)
                try:
                    text = clean_text(anchor.inner_text(timeout=500))
                    href = clean_text(anchor.get_attribute("href") or "")
                except Exception:
                    continue
                if not re.search(r"摘要|關鍵字|關鍵詞|abstract|keyword", text, flags=re.I):
                    continue
                target = urljoin(page.url, href)
                if is_grb_url(target) and target not in link_targets:
                    link_targets.append(target)

            # Hidden/modal content often appears only after a button is clicked.
            controls = page.locator("button,[role='button'],a[href='#']")
            clicked = 0
            for index in range(min(controls.count(), 220)):
                control = controls.nth(index)
                try:
                    text = clean_text(control.inner_text(timeout=400))
                except Exception:
                    continue
                if not re.search(r"摘要|關鍵字|關鍵詞|abstract|keyword", text, flags=re.I):
                    continue
                try:
                    control.click(timeout=2_500, force=True)
                    page.wait_for_timeout(700)
                    html_documents.append(page.content())
                    clicked += 1
                except Exception:
                    continue
                if clicked >= 12:
                    break

            for index, target in enumerate(link_targets[:8]):
                child = context.new_page()
                child.on("response", capture_response)
                try:
                    child.goto(target, wait_until="commit", timeout=25_000, referer=page.url)
                    child.wait_for_selector("body", state="attached", timeout=8_000)
                    child.wait_for_timeout(1_500)
                    html_documents.append(child.content())
                except Exception as exc:
                    errors.append(f"linked page {index + 1}: {exc}")
                finally:
                    child.close()

            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r"[^0-9A-Za-z._-]+", "-", debug_name).strip("-.") or "project-content"
            (DEBUG_DIR / f"{safe_name}-content.html").write_text(
                "\n\n<!-- DOCUMENT BREAK -->\n\n".join(html_documents), encoding="utf-8"
            )
            (DEBUG_DIR / f"{safe_name}-content.json").write_text(
                json.dumps(json_payloads, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        except Exception as exc:
            errors.append(str(exc))
        finally:
            page.close()
            context.close()
            browser.close()

    return FetchOutcome(url, html_documents, json_payloads, "; ".join(errors))


def merge_project_content(project: dict[str, Any], incoming: dict[str, Any], checked_at: str, source_url: str) -> tuple[dict[str, Any], list[str]]:
    updated = copy.deepcopy(project)
    changed: list[str] = []
    for field in ABSTRACT_FIELDS:
        value = valid_abstract(incoming.get(field))
        if value and updated.get(field) != value:
            updated[field] = value
            changed.append(field)
    for field in KEYWORD_FIELDS:
        value = split_keywords(incoming.get(field))
        if value and updated.get(field) != value:
            updated[field] = value
            changed.append(field)

    if incoming.get("abstractZh") or incoming.get("abstractEn"):
        if updated.get("abstractSource") != "GRB":
            updated["abstractSource"] = "GRB"
            changed.append("abstractSource")
    if incoming.get("keywordsZh") or incoming.get("keywordsEn"):
        if updated.get("keywordsSource") != "GRB":
            updated["keywordsSource"] = "GRB"
            changed.append("keywordsSource")
    if any(incoming.get(field) for field in CONTENT_FIELDS):
        if updated.get("grbContentSourceUrl") != source_url:
            updated["grbContentSourceUrl"] = source_url
            changed.append("grbContentSourceUrl")
        updated["grbContentLastChecked"] = checked_at
        if "grbContentLastChecked" not in changed:
            changed.append("grbContentLastChecked")
    return updated, changed


def validate_projects(projects: Any) -> None:
    if not isinstance(projects, list):
        raise ContentError("data/projects.json must contain an array")
    for index, project in enumerate(projects):
        if not isinstance(project, dict):
            raise ContentError(f"Project {index} is not an object")
        for field in ABSTRACT_FIELDS:
            if field in project and not isinstance(project[field], str):
                raise ContentError(f"Project {index} field {field} must be a string")
        for field in KEYWORD_FIELDS:
            if field in project:
                value = project[field]
                if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
                    raise ContentError(f"Project {index} field {field} must be a non-empty string array")


def replace_marked_block(source: str, start: str, end: str, block: str) -> tuple[str, bool]:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), flags=re.DOTALL)
    if pattern.search(source):
        updated = pattern.sub(lambda _match: block, source, count=1)
    else:
        updated = source.rstrip() + "\n\n" + block + "\n"
    return updated, updated != source


def patch_ui(root: Path) -> list[str]:
    changed: list[str] = []
    app_path = root / "assets/js/app.js"
    css_path = root / "assets/css/styles.css"
    if not app_path.exists():
        raise ContentError(f"Missing {app_path}")
    if not css_path.exists():
        raise ContentError(f"Missing {css_path}")

    app_source = app_path.read_text(encoding="utf-8")
    app_updated, app_changed = replace_marked_block(app_source, UI_START, UI_END, UI_BLOCK)
    if app_changed:
        app_path.write_text(app_updated, encoding="utf-8")
        changed.append("assets/js/app.js")

    css_source = css_path.read_text(encoding="utf-8")
    css_updated, css_changed = replace_marked_block(css_source, CSS_START, CSS_END, CSS_BLOCK)
    if css_changed:
        css_path.write_text(css_updated, encoding="utf-8")
        changed.append("assets/css/styles.css")
    return changed


def update_projects(root: Path, allow_network_failure: bool) -> tuple[list[str], list[dict[str, Any]]]:
    projects_path = root / "data/projects.json"
    projects = read_json(projects_path, [])
    validate_projects(projects)
    checked_at = now_iso()
    changed_projects: list[str] = []
    diagnostics: list[dict[str, Any]] = []

    for index, project in enumerate(projects):
        source_url = project_grb_url(project)
        if not source_url:
            continue
        grb_id = clean_text(project.get("grbId")) or source_url.rsplit("=", 1)[-1]
        documents = diagnostic_documents(project)
        parsed = parse_documents(documents)
        network_error = ""

        missing = [field for field in CONTENT_FIELDS if not parsed.get(field)]
        if missing:
            outcome = browser_fetch(source_url, f"grb-{grb_id}")
            network_error = outcome.error
            browser_parsed = parse_documents(outcome.html_documents, outcome.json_payloads)
            for field, value in browser_parsed.items():
                if value:
                    parsed[field] = value

        merged, changed = merge_project_content(project, parsed, checked_at, source_url)
        projects[index] = merged
        if changed:
            changed_projects.append(grb_id or clean_text(project.get("number")) or str(index))
        diagnostics.append(
            {
                "grbId": grb_id,
                "url": source_url,
                "found": {field: bool(parsed.get(field)) for field in CONTENT_FIELDS},
                "changedFields": changed,
                "error": network_error,
            }
        )

    if changed_projects:
        validate_projects(projects)
        write_json(projects_path, projects)

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    write_json(
        DEBUG_DIR / "grb-project-content-summary.json",
        {"checkedAt": checked_at, "records": diagnostics},
    )

    successful = any(any(record["found"].values()) for record in diagnostics)
    if diagnostics and not successful and not allow_network_failure:
        raise ContentError("No GRB abstracts or keywords could be retrieved")
    return changed_projects, diagnostics


def self_test() -> None:
    sample_html = """
    <html><body><table>
      <tr><th>中文摘要</th><td>本計畫將建立一套可程式化控制的真空閃蒸系統，並透過壓力曲線與光學監測提升鈣鈦礦模組製程的一致性與可靠度。</td></tr>
      <tr><th>英文摘要</th><td>This project develops a programmable vacuum-flash platform with pressure-profile control and optical monitoring for reliable perovskite module processing.</td></tr>
      <tr><th>中文關鍵字</th><td>鈣鈦礦太陽能電池；真空閃蒸；模組製程</td></tr>
      <tr><th>英文關鍵字</th><td>Perovskite solar cells; Vacuum flash; Module processing</td></tr>
    </table></body></html>
    """
    parsed = parse_documents([sample_html])
    assert parsed["abstractZh"].startswith("本計畫")
    assert parsed["abstractEn"].startswith("This project")
    assert parsed["keywordsZh"] == ["鈣鈦礦太陽能電池", "真空閃蒸", "模組製程"]
    assert parsed["keywordsEn"] == ["Perovskite solar cells", "Vacuum flash", "Module processing"]

    structured = {
        "planAbstractCh": "這是一段足夠長度的中文計畫摘要，用來驗證動態 JSON 回應中的欄位也能正確被辨識與保存，而不是只依賴頁面表格。",
        "planAbstractEn": "This sufficiently long English project abstract verifies that dynamically returned JSON fields are also recognized and retained.",
        "chKeywords": ["薄膜", "可靠度"],
        "enKeywords": ["Thin films", "Reliability"],
    }
    parsed_json = parse_documents([], [structured])
    assert parsed_json["keywordsZh"] == ["薄膜", "可靠度"]
    assert parsed_json["keywordsEn"] == ["Thin films", "Reliability"]

    source = f"before\n{UI_START}\nold\n{UI_END}\nafter\n"
    updated, changed = replace_marked_block(source, UI_START, UI_END, UI_BLOCK)
    assert changed and "projectResearchDetails" in updated and updated.count(UI_START) == 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--allow-network-failure", action="store_true")
    parser.add_argument("--patch-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    try:
        if args.self_test:
            self_test()
            LOGGER.info("GRB project content parser self-test passed")
            return 0

        root = args.root.resolve()
        projects_path = root / "data/projects.json"
        if args.validate_only:
            validate_projects(read_json(projects_path, []))
            LOGGER.info("GRB project content fields are valid")
            return 0

        ui_changes = patch_ui(root)
        if args.patch_only:
            LOGGER.info("UI files updated: %s", ", ".join(ui_changes) if ui_changes else "none")
            return 0

        project_changes, diagnostics = update_projects(root, args.allow_network_failure)
        LOGGER.info("UI files updated: %s", ", ".join(ui_changes) if ui_changes else "none")
        LOGGER.info("Projects with refreshed GRB content: %s", ", ".join(project_changes) if project_changes else "none")
        LOGGER.info("GRB records checked: %d", len(diagnostics))
        return 0
    except (ContentError, OSError, json.JSONDecodeError) as exc:
        LOGGER.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
