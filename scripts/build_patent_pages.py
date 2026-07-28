#!/usr/bin/env python3
"""Build crawler-readable patent cards, family pages and document compatibility pages."""
from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from patent_common import merge_automatic_metadata, normalize_identifier


ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://weihaochiu.github.io"
TODAY = date.today().isoformat()
STATIC_START = "<!-- PATENT_STATIC_START -->"
STATIC_END = "<!-- PATENT_STATIC_END -->"
SCHEMA_START = "<!-- PATENT_SCHEMA_START -->"
SCHEMA_END = "<!-- PATENT_SCHEMA_END -->"
LLMS_START = "<!-- PATENT_LLMS_START -->"
LLMS_END = "<!-- PATENT_LLMS_END -->"
GA_TAG = """<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-G82XWMCJDE"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-G82XWMCJDE');
</script>"""


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def slug(record: dict[str, Any]) -> str:
    value = normalize_identifier(record.get("canonicalId") or record.get("number")).lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-") or "patent"


def family_slug(family: dict[str, Any], records: list[dict[str, Any]]) -> str:
    value = family.get("familyId") or records[0].get("familyId") or records[0].get("canonicalId")
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-") or "patent-family"


def family_primary_date(records: list[dict[str, Any]]) -> str:
    dates = [
        str(record.get("sortDate") or record.get("publicationDate") or record.get("grantDate") or "")
        for record in records
    ]
    return min((value for value in dates if value), default="")


def family_inventors(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        for inventor in record.get("inventors") or []:
            key = str(
                inventor.get("personId") or inventor.get("nameEn") or inventor.get("nameZh") or ""
            ).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(inventor)
    return result


def family_assignees(records: list[dict[str, Any]]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    ordered = sorted(records, key=lambda record: record.get("jurisdiction") != "Taiwan")
    for record in ordered:
        value = (str(record.get("assigneeEn") or ""), str(record.get("assigneeZh") or ""))
        key = value[0].lower() or value[1]
        if not any(value) or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def author_map(authors: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(author.get("id") or ""): author for author in authors if author.get("id")}


def inventor_html(inventor: dict[str, Any], authors: dict[str, dict[str, Any]]) -> str:
    person_id = str(inventor.get("personId") or "")
    name = str(inventor.get("nameEn") or inventor.get("nameZh") or "")
    person = authors.get(person_id)
    if person:
        me = " me" if person_id == "wei-hao-chiu" else ""
        rendered = (
            f'<button class="author-trigger{me}" type="button" '
            f'data-author-id="{esc(person_id)}" data-author-name="{esc(name)}" '
            f'aria-haspopup="dialog" aria-expanded="false">{esc(name)}</button>'
        )
    else:
        rendered = f'<strong class="me">{esc(name)}</strong>' if person_id == "wei-hao-chiu" else esc(name)
    if inventor.get("nameZh"):
        rendered += f' <span lang="zh-Hant">({esc(inventor.get("nameZh"))})</span>'
    return rendered


def inventor_schema(inventor: dict[str, Any], authors: dict[str, dict[str, Any]]) -> dict[str, Any]:
    person = authors.get(str(inventor.get("personId") or ""), {})
    result: dict[str, Any] = {
        "@type": "Person",
        "name": inventor.get("nameEn") or person.get("displayName") or person.get("name"),
    }
    alternate = inventor.get("nameZh") or person.get("nameZh")
    if alternate:
        result["alternateName"] = alternate
    same_as = [
        value
        for value in [
            (person.get("links") or {}).get("orcid"),
            (person.get("links") or {}).get("linkedin"),
            (person.get("links") or {}).get("personalWebsite"),
            (person.get("links") or {}).get("institution"),
        ]
        if value
    ]
    if same_as:
        result["sameAs"] = same_as
    return result


def patent_schema(record: dict[str, Any], authors: dict[str, dict[str, Any]], url: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "@type": "CreativeWork",
        "@id": url + ("-patent" if "#" in url else "#patent"),
        "url": url,
        "additionalType": "Patent",
        "name": record.get("titleEn"),
        "alternateName": record.get("titleZh"),
        "identifier": [
            {"@type": "PropertyValue", "propertyID": "Patent publication", "value": record.get("canonicalId")},
            {"@type": "PropertyValue", "propertyID": "Displayed patent number", "value": record.get("number")},
        ],
        "datePublished": record.get("publicationDate") or record.get("grantDate") or str(record.get("year") or ""),
        "creator": [inventor_schema(inventor, authors) for inventor in record.get("inventors") or []],
        "copyrightHolder": {"@type": "Organization", "name": record.get("assigneeEn")},
        "spatialCoverage": record.get("jurisdiction"),
        "sameAs": record.get("url"),
        "abstract": record.get("abstract"),
        "inLanguage": ["en", "zh-Hant"] if record.get("titleZh") else "en",
    }
    return {key: value for key, value in result.items() if value not in ("", None, [], {})}


def date_rows(record: dict[str, Any]) -> str:
    fields = [
        ("Priority date", record.get("priorityDate")),
        ("Filing date", record.get("filingDate")),
        ("Publication date", record.get("publicationDate")),
        ("Grant date", record.get("grantDate")),
    ]
    return "".join(
        f"<div><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>"
        for label, value in fields
        if value
    )


def static_card(record: dict[str, Any], authors: dict[str, dict[str, Any]]) -> str:
    inventors = ", ".join(inventor_html(inventor, authors) for inventor in record.get("inventors") or [])
    labels = [
        record.get("number"),
        record.get("jurisdiction"),
        record.get("documentStage") or record.get("status"),
        record.get("patentType"),
    ]
    detail = f"patents/{slug(record)}.html"
    return (
        f'<article class="collection-card patent-card" id="patent-{esc(slug(record))}">'
        f'<div class="card-heading"><h4><a href="{esc(detail)}">{esc(record.get("titleEn"))}</a></h4>'
        f'<span class="date-badge">{esc(record.get("date"))}</span></div>'
        + (f'<div class="local-title" lang="zh-Hant">{esc(record.get("titleZh"))}</div>' if record.get("titleZh") else "")
        + '<div class="card-labels">'
        + "".join(f'<span class="card-label">{esc(label)}</span>' for label in labels if label)
        + "</div>"
        + f'<div class="meta-row">Inventors: {inventors}</div>'
        + f'<div class="meta-row">Assignee: {esc(record.get("assigneeEn"))}'
        + (f' <span lang="zh-Hant">({esc(record.get("assigneeZh"))})</span>' if record.get("assigneeZh") else "")
        + "</div>"
        + f'<div class="card-actions"><a class="action" href="{esc(detail)}">Patent details →</a>'
        + f'<a class="action" href="{esc(record.get("url"))}" target="_blank" rel="noopener">Patent record ↗</a></div>'
        + "</article>"
    )


def static_family_document(
    record: dict[str, Any],
    family: dict[str, Any],
    records: list[dict[str, Any]],
) -> str:
    family_url = f"patents/families-{family_slug(family, records)}.html#document-{slug(record)}"
    labels = [
        record.get("jurisdiction"),
        record.get("documentStage") or record.get("status"),
        record.get("patentType"),
    ]
    title = str(record.get("titleEn") or "")
    title_zh = str(record.get("titleZh") or "")
    different_title = (
        f'<p class="patent-family-document-title">{esc(title)}</p>'
        if title and title != str(family.get("titleEn") or "")
        else ""
    )
    different_title_zh = (
        f'<p class="patent-family-document-title" lang="zh-Hant">{esc(title_zh)}</p>'
        if title_zh and title_zh != str(family.get("titleZh") or "")
        else ""
    )
    return (
        f'<article class="patent-family-document" id="patent-{esc(slug(record))}">'
        f'<div class="patent-family-document-heading"><div><h5><a href="{esc(family_url)}">'
        f'{esc(record.get("number") or record.get("canonicalId"))}</a></h5>'
        f"{different_title}{different_title_zh}</div>"
        f'<span class="date-badge">{esc(record.get("date"))}</span></div>'
        '<div class="card-labels">'
        + "".join(f'<span class="card-label">{esc(label)}</span>' for label in labels if label)
        + "</div>"
        + f'<div class="card-actions"><a class="action" href="{esc(record.get("url"))}" '
        'target="_blank" rel="noopener">Patent record ↗</a></div></article>'
    )


def static_family_card(
    records: list[dict[str, Any]],
    family: dict[str, Any],
    authors: dict[str, dict[str, Any]],
) -> str:
    if len(records) == 1:
        return static_card(records[0], authors)
    family_id = family_slug(family, records)
    family_url = f"patents/families-{family_id}.html"
    title = family.get("titleEn") or records[0].get("titleEn")
    title_zh = family.get("titleZh") or records[0].get("titleZh")
    year = family_primary_date(records)[:4]
    jurisdictions = list(dict.fromkeys(record.get("jurisdiction") for record in records if record.get("jurisdiction")))
    inventors = ", ".join(inventor_html(inventor, authors) for inventor in family_inventors(records))
    assignees = family_assignees(records)
    assignee_values = "; ".join(
        esc(name_en or name_zh)
        + (f' <span lang="zh-Hant">({esc(name_zh)})</span>' if name_en and name_zh else "")
        for name_en, name_zh in assignees
    )
    return (
        f'<article class="collection-card patent-family-card" id="patent-family-{esc(family_id)}">'
        f'<div class="card-heading"><h4><a href="{esc(family_url)}">{esc(title)}</a></h4>'
        f'<span class="date-badge">{esc(year)}</span></div>'
        + (f'<div class="local-title" lang="zh-Hant">{esc(title_zh)}</div>' if title_zh else "")
        + '<div class="card-labels">'
        + f'<span class="card-label">{len(records)} documents</span>'
        + "".join(f'<span class="card-label">{esc(value)}</span>' for value in jurisdictions)
        + "</div>"
        + f'<div class="meta-row">Inventors: {inventors}</div>'
        + (
            f'<div class="meta-row">{"Assignee" if len(assignees) == 1 else "Assignees"}: '
            f"{assignee_values}</div>"
            if assignees
            else ""
        )
        + f'<div class="card-actions"><a class="action" href="{esc(family_url)}">'
        "Patent family details →</a></div>"
        + f'<details class="patent-family-documents"><summary>View {len(records)} family documents</summary>'
        + '<div class="patent-family-list">'
        + "".join(static_family_document(record, family, records) for record in records)
        + "</div></details></article>"
    )


def detail_page(record: dict[str, Any], authors: dict[str, dict[str, Any]]) -> str:
    page_url = f"{SITE_URL}/patents/{slug(record)}.html"
    schema = json.dumps(
        {"@context": "https://schema.org", **patent_schema(record, authors, page_url)},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    inventors = ", ".join(inventor_html(inventor, authors) for inventor in record.get("inventors") or [])
    labels = "".join(
        f'<span class="card-label">{esc(value)}</span>'
        for value in [
            record.get("number"),
            record.get("jurisdiction"),
            record.get("documentStage") or record.get("status"),
            record.get("patentType"),
        ]
        if value
    )
    dates = date_rows(record)
    classifications = "".join(
        f"<span>{esc(value)}</span>" for value in record.get("classifications") or []
    )
    metadata = (
        (f'<p><strong>Application number:</strong> {esc(record.get("applicationNumber"))}</p>' if record.get("applicationNumber") else "")
        + (f'<dl class="patent-date-grid">{dates}</dl>' if dates else "")
        + (f'<p><strong>Source-reported legal status:</strong> {esc(record.get("legalStatus"))}</p>' if record.get("legalStatus") else "")
        + (f'<div class="patent-classifications">{classifications}</div>' if classifications else "")
        + (f'<section><h5>Abstract</h5><p>{esc(record.get("abstract"))}</p></section>' if record.get("abstract") else "")
    )
    description = record.get("abstract") or (
        f"{record.get('titleEn')} — {record.get('canonicalId')}, "
        f"{record.get('jurisdiction')} patent record."
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{esc(record.get('titleEn'))} | Wei-Hao Chiu</title>
<meta name="description" content="{esc(description)}"/><link rel="canonical" href="{esc(page_url)}"/>
<meta property="og:type" content="article"/><meta property="og:title" content="{esc(record.get('titleEn'))}"/>
<meta property="og:description" content="{esc(description)}"/><meta property="og:url" content="{esc(page_url)}"/>
<meta property="og:image" content="{SITE_URL}/assets/images/og-profile.jpg"/>{GA_TAG}
<script type="application/ld+json">{schema}</script><link href="../assets/css/styles.css" rel="stylesheet"/></head>
<body><header class="site-header"><div class="shell nav-shell"><a class="brand" href="../index.html"><span>Wei-Hao Chiu</span><small>Academic Profile</small></a><nav aria-label="Main navigation" class="site-nav"><a href="../about.html">About</a><a href="../research.html">Research</a><a href="../publications.html">Publications</a><a href="../patents.html">Patents</a><a href="../projects.html">Projects</a></nav></div></header>
<main class="content shell"><article class="patent-detail-page"><p class="kicker">Patent document</p><h1>{esc(record.get('titleEn'))}</h1>{f'<div class="local-title" lang="zh-Hant">{esc(record.get("titleZh"))}</div>' if record.get('titleZh') else ''}<div class="card-labels">{labels}</div><p class="meta-row">Inventors: {inventors}</p><p class="meta-row">Assignee: {esc(record.get('assigneeEn'))}{f' <span lang="zh-Hant">({esc(record.get("assigneeZh"))})</span>' if record.get('assigneeZh') else ''}</p><div class="patent-detail-body">{metadata}</div><div class="card-actions publication-detail-actions"><a class="action" href="{esc(record.get('url'))}" target="_blank" rel="noopener">Patent record ↗</a></div><a class="action publication-return" href="../patents.html#patent-{esc(slug(record))}">← Return to patents</a></article></main>
<footer class="site-footer"><div class="shell footer-grid"><div><strong>Wei-Hao Chiu, Ph.D.</strong><p>Associate Researcher<br/>Center for Sustainability and Energy Technologies<br/>Chang Gung University</p></div><div class="footer-links"><a href="mailto:weihao.chiu@gmail.com">Personal Email</a><a href="mailto:d000019005@cgu.edu.tw">CGU Email</a></div></div></footer><script src="../assets/js/app.js"></script></body></html>
"""


def family_document_section(record: dict[str, Any], family: dict[str, Any]) -> str:
    labels = "".join(
        f'<span class="card-label">{esc(value)}</span>'
        for value in [
            record.get("jurisdiction"),
            record.get("documentStage") or record.get("status"),
            record.get("patentType"),
        ]
        if value
    )
    title = str(record.get("titleEn") or "")
    title_zh = str(record.get("titleZh") or "")
    title_block = (
        f'<p class="patent-family-document-title">{esc(title)}</p>'
        if title and title != str(family.get("titleEn") or "")
        else ""
    )
    title_zh_block = (
        f'<p class="patent-family-document-title" lang="zh-Hant">{esc(title_zh)}</p>'
        if title_zh and title_zh != str(family.get("titleZh") or "")
        else ""
    )
    dates = date_rows(record)
    classifications = "".join(
        f"<span>{esc(value)}</span>" for value in record.get("classifications") or []
    )
    metadata = (
        (f'<p><strong>Application number:</strong> {esc(record.get("applicationNumber"))}</p>' if record.get("applicationNumber") else "")
        + (f'<dl class="patent-date-grid">{dates}</dl>' if dates else "")
        + (f'<p><strong>Legal status:</strong> {esc(record.get("legalStatus"))}</p>' if record.get("legalStatus") else "")
        + (f'<div class="patent-classifications">{classifications}</div>' if classifications else "")
        + (f'<section><h5>Abstract</h5><p>{esc(record.get("abstract"))}</p></section>' if record.get("abstract") else "")
    )
    return (
        f'<section class="patent-family-detail-document" id="document-{esc(slug(record))}">'
        '<div class="patent-family-document-heading"><div>'
        f'<h2>{esc(record.get("number") or record.get("canonicalId"))}</h2>'
        f"{title_block}{title_zh_block}</div>"
        f'<span class="date-badge">{esc(record.get("date"))}</span></div>'
        f'<div class="card-labels">{labels}</div>'
        + (f'<div class="patent-detail-body">{metadata}</div>' if metadata else "")
        + f'<div class="card-actions"><a class="action" href="{esc(record.get("url"))}" '
        'target="_blank" rel="noopener">Patent record ↗</a></div></section>'
    )


def family_detail_page(
    family: dict[str, Any],
    records: list[dict[str, Any]],
    authors: dict[str, dict[str, Any]],
) -> str:
    family_id = family_slug(family, records)
    page_url = f"{SITE_URL}/patents/families-{family_id}.html"
    title = family.get("titleEn") or records[0].get("titleEn")
    title_zh = family.get("titleZh") or records[0].get("titleZh")
    inventors = family_inventors(records)
    inventor_text = ", ".join(inventor_html(inventor, authors) for inventor in inventors)
    assignees = family_assignees(records)
    assignee_text = "; ".join(
        esc(name_en or name_zh)
        + (f' <span lang="zh-Hant">({esc(name_zh)})</span>' if name_en and name_zh else "")
        for name_en, name_zh in assignees
    )
    jurisdictions = list(
        dict.fromkeys(record.get("jurisdiction") for record in records if record.get("jurisdiction"))
    )
    labels = (
        f'<span class="card-label">{len(records)} documents</span>'
        + "".join(f'<span class="card-label">{esc(value)}</span>' for value in jurisdictions)
        + f'<span class="card-label">Earliest document {esc(family_primary_date(records)[:4])}</span>'
    )
    schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": page_url + "#family",
        "url": page_url,
        "name": title,
        "alternateName": title_zh,
        "about": "Patent family",
        "creator": [inventor_schema(inventor, authors) for inventor in inventors],
        "hasPart": [
            patent_schema(record, authors, f"{page_url}#document-{slug(record)}")
            for record in records
        ],
    }
    schema = {key: value for key, value in schema.items() if value not in ("", None, [], {})}
    description = (
        f"{title} patent family with {len(records)} documents in "
        + ", ".join(jurisdictions)
        + "."
    )
    documents = "".join(family_document_section(record, family) for record in records)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{esc(title)} — Patent Family | Wei-Hao Chiu</title>
<meta name="description" content="{esc(description)}"/><link rel="canonical" href="{esc(page_url)}"/>
<meta property="og:type" content="article"/><meta property="og:title" content="{esc(title)} — Patent Family"/>
<meta property="og:description" content="{esc(description)}"/><meta property="og:url" content="{esc(page_url)}"/>
<meta property="og:image" content="{SITE_URL}/assets/images/og-profile.jpg"/>{GA_TAG}
<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, separators=(",", ":"))}</script>
<link href="../assets/css/styles.css" rel="stylesheet"/></head>
<body><header class="site-header"><div class="shell nav-shell"><a class="brand" href="../index.html"><span>Wei-Hao Chiu</span><small>Academic Profile</small></a><nav aria-label="Main navigation" class="site-nav"><a href="../about.html">About</a><a href="../research.html">Research</a><a href="../publications.html">Publications</a><a href="../patents.html">Patents</a><a href="../projects.html">Projects</a></nav></div></header>
<main class="content shell"><article class="patent-detail-page patent-family-detail-page"><p class="kicker">Patent family</p><h1>{esc(title)}</h1>{f'<div class="local-title" lang="zh-Hant">{esc(title_zh)}</div>' if title_zh else ''}<div class="card-labels">{labels}</div><p class="meta-row">Inventors: {inventor_text}</p>{f'<p class="meta-row">{"Assignee" if len(assignees) == 1 else "Assignees"}: {assignee_text}</p>' if assignees else ''}<div class="patent-family-detail-list">{documents}</div><a class="action publication-return" href="../patents.html#patent-family-{esc(family_id)}">← Return to patents</a></article></main>
<footer class="site-footer"><div class="shell footer-grid"><div><strong>Wei-Hao Chiu, Ph.D.</strong><p>Associate Researcher<br/>Center for Sustainability and Energy Technologies<br/>Chang Gung University</p></div><div class="footer-links"><a href="mailto:weihao.chiu@gmail.com">Personal Email</a><a href="mailto:d000019005@cgu.edu.tw">CGU Email</a></div></div></footer><script src="../assets/js/app.js"></script></body></html>
"""


def family_redirect_page(
    record: dict[str, Any],
    family: dict[str, Any],
    records: list[dict[str, Any]],
) -> str:
    target = f"families-{family_slug(family, records)}.html#document-{slug(record)}"
    canonical = f"{SITE_URL}/patents/families-{family_slug(family, records)}.html"
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{esc(record.get('titleEn'))} | Wei-Hao Chiu</title>
<link rel="canonical" href="{esc(canonical)}"/><meta http-equiv="refresh" content="0; url={esc(target)}"/>
<meta name="robots" content="noindex, follow"/><link href="../assets/css/styles.css" rel="stylesheet"/></head>
<body><main class="content shell"><article class="patent-detail-page"><p class="kicker">Patent document</p>
<h1>{esc(record.get('number') or record.get('canonicalId'))}</h1>
<p>This document is presented with the other records in its patent family.</p>
<p><a class="action" href="{esc(target)}">Open patent family details →</a></p>
</article></main></body></html>
"""


def replace_marked(text: str, start: str, end: str, block: str, fallback: str = "") -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), flags=re.S)
    marked = f"{start}\n{block}\n{end}"
    if pattern.search(text):
        return pattern.sub(marked, text, count=1)
    if fallback and fallback in text:
        return text.replace(fallback, marked, 1)
    raise SystemExit(f"Unable to place generated block beginning {start}")


def update_sitemap(
    groups: list[tuple[dict[str, Any], list[dict[str, Any]]]],
) -> None:
    path = ROOT / "sitemap.xml"
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r"\s*<url><loc>https://weihaochiu\.github\.io/(?:patents|patent-families)/[^<]+</loc><lastmod>[^<]+</lastmod></url>",
        "",
        text,
    )
    urls = []
    for family, records in groups:
        if len(records) == 1:
            urls.append(f"{SITE_URL}/patents/{slug(records[0])}.html")
        else:
            urls.append(f"{SITE_URL}/patents/families-{family_slug(family, records)}.html")
    rows = "\n".join(
        f"  <url><loc>{esc(url)}</loc><lastmod>{TODAY}</lastmod></url>" for url in urls
    )
    text = text.replace("</urlset>", rows + "\n</urlset>", 1)
    path.write_text(text, encoding="utf-8")


def update_llms(
    groups: list[tuple[dict[str, Any], list[dict[str, Any]]]],
) -> None:
    path = ROOT / "llms.txt"
    text = path.read_text(encoding="utf-8")
    lines = ["## Patents", ""]
    for family, records in groups:
        if len(records) == 1:
            record = records[0]
            lines.append(
                f"- [{record.get('titleEn')}]({SITE_URL}/patents/{slug(record)}.html) — "
                f"{record.get('canonicalId')}; {record.get('jurisdiction')}; "
                f"{record.get('documentStage') or record.get('status')}"
            )
            continue
        title = family.get("titleEn") or records[0].get("titleEn")
        documents = ", ".join(str(record.get("canonicalId")) for record in records)
        lines.append(
            f"- [{title}]({SITE_URL}/patents/families-{family_slug(family, records)}.html) — "
            f"Patent family with {len(records)} documents: {documents}"
        )
    block = "\n".join(lines)
    pattern = re.compile(re.escape(LLMS_START) + r".*?" + re.escape(LLMS_END), flags=re.S)
    marked = f"{LLMS_START}\n{block}\n{LLMS_END}"
    text = pattern.sub(marked, text, count=1) if pattern.search(text) else text.rstrip() + "\n\n" + marked + "\n"
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patents = load(ROOT / "data/patents.json", [])
    families = load(ROOT / "data/patent_families.json", [])
    metadata = load(ROOT / "data/patent_metadata.json", {})
    authors = author_map(load(ROOT / "data/authors.json", []))
    records = metadata.get("records", {}) if isinstance(metadata, dict) else {}
    enriched = [
        merge_automatic_metadata(record, records.get(record.get("canonicalId"), {}))
        for record in patents
    ]
    enriched.sort(key=lambda record: str(record.get("sortDate") or ""), reverse=True)
    family_by_id = {str(family.get("familyId") or ""): family for family in families}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in enriched:
        key = str(record.get("familyId") or record.get("canonicalId") or record.get("number"))
        grouped.setdefault(key, []).append(record)
    groups = [
        (family_by_id.get(key, {"familyId": key}), records)
        for key, records in grouped.items()
    ]
    groups.sort(key=lambda item: family_primary_date(item[1]), reverse=True)

    page_path = ROOT / "patents.html"
    page = page_path.read_text(encoding="utf-8")
    by_year: dict[str, list[tuple[dict[str, Any], list[dict[str, Any]]]]] = {}
    for family, records in groups:
        year = family_primary_date(records)[:4] or "Unknown"
        by_year.setdefault(year, []).append((family, records))
    sections = []
    for year in sorted(by_year, reverse=True):
        year_groups = by_year[year]
        family_cards = "\n".join(
            static_family_card(records, family, authors) for family, records in year_groups
        )
        label = "family" if len(year_groups) == 1 else "families"
        sections.append(
            f'<section class="year-group"><div class="year-heading"><h3>{esc(year)}</h3>'
            f'<span>{len(year_groups)} {label}</span></div>'
            f'<div class="collection-list patent-family-results">{family_cards}</div></section>'
        )
    static_block = (
        f'<div id="collectionContainer" data-static-patents="{len(enriched)}">\n'
        + "\n".join(sections)
        + "\n</div>"
    )
    page = replace_marked(
        page,
        STATIC_START,
        STATIC_END,
        static_block,
        '<div id="collectionContainer"></div>',
    )
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            patent_schema(
                record,
                authors,
                (
                    f"{SITE_URL}/patents/{slug(record)}.html"
                    if len(family_records) == 1
                    else (
                        f"{SITE_URL}/patents/families-{family_slug(family, family_records)}.html"
                        f"#document-{slug(record)}"
                    )
                ),
            )
            for family, family_records in groups
            for record in family_records
        ],
    }
    schema_block = (
        '<script type="application/ld+json" id="patents-schema">'
        + json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
        + "</script>"
    )
    page = replace_marked(page, SCHEMA_START, SCHEMA_END, schema_block, "</head>")
    if SCHEMA_END + "\n</head>" not in page:
        page = page.replace(SCHEMA_END, SCHEMA_END + "\n</head>", 1)
    page_path.write_text(page, encoding="utf-8")

    detail_dir = ROOT / "patents"
    family_dir = detail_dir
    detail_dir.mkdir(exist_ok=True)
    family_dir.mkdir(exist_ok=True)
    for old in detail_dir.glob("*.html"):
        old.unlink()
    for old in family_dir.glob("*.html"):
        old.unlink()
    for family, family_records in groups:
        if len(family_records) == 1:
            record = family_records[0]
            (detail_dir / f"{slug(record)}.html").write_text(
                detail_page(record, authors),
                encoding="utf-8",
            )
            continue
        family_id = family_slug(family, family_records)
        (family_dir / f"families-{family_id}.html").write_text(
            family_detail_page(family, family_records, authors),
            encoding="utf-8",
        )
        for record in family_records:
            (detail_dir / f"{slug(record)}.html").write_text(
                family_redirect_page(record, family, family_records),
                encoding="utf-8",
            )
    update_sitemap(groups)
    update_llms(groups)
    print(
        f"Generated {len(groups)} patent-family cards, "
        f"{sum(1 for _, records in groups if len(records) > 1)} integrated family pages "
        f"and {len(enriched)} compatible document URLs."
    )


if __name__ == "__main__":
    main()
