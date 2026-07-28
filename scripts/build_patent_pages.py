#!/usr/bin/env python3
"""Build crawler-readable patent cards and individual patent detail pages."""
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
        "@id": url + "#patent",
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
        + '<p class="patent-source-note">Source-reported status is informational and is not legal advice.</p>'
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


def replace_marked(text: str, start: str, end: str, block: str, fallback: str = "") -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), flags=re.S)
    marked = f"{start}\n{block}\n{end}"
    if pattern.search(text):
        return pattern.sub(marked, text, count=1)
    if fallback and fallback in text:
        return text.replace(fallback, marked, 1)
    raise SystemExit(f"Unable to place generated block beginning {start}")


def update_sitemap(patents: list[dict[str, Any]]) -> None:
    path = ROOT / "sitemap.xml"
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r"\s*<url><loc>https://weihaochiu\.github\.io/patents/[^<]+</loc><lastmod>[^<]+</lastmod></url>",
        "",
        text,
    )
    rows = "\n".join(
        f"  <url><loc>{SITE_URL}/patents/{esc(slug(record))}.html</loc><lastmod>{TODAY}</lastmod></url>"
        for record in patents
    )
    text = text.replace("</urlset>", rows + "\n</urlset>", 1)
    path.write_text(text, encoding="utf-8")


def update_llms(patents: list[dict[str, Any]]) -> None:
    path = ROOT / "llms.txt"
    text = path.read_text(encoding="utf-8")
    lines = ["## Patents", ""]
    for record in patents:
        lines.append(
            f"- [{record.get('titleEn')}]({SITE_URL}/patents/{slug(record)}.html) — "
            f"{record.get('canonicalId')}; {record.get('jurisdiction')}; "
            f"{record.get('documentStage') or record.get('status')}"
        )
    block = "\n".join(lines)
    pattern = re.compile(re.escape(LLMS_START) + r".*?" + re.escape(LLMS_END), flags=re.S)
    marked = f"{LLMS_START}\n{block}\n{LLMS_END}"
    text = pattern.sub(marked, text, count=1) if pattern.search(text) else text.rstrip() + "\n\n" + marked + "\n"
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patents = load(ROOT / "data/patents.json", [])
    metadata = load(ROOT / "data/patent_metadata.json", {})
    authors = author_map(load(ROOT / "data/authors.json", []))
    records = metadata.get("records", {}) if isinstance(metadata, dict) else {}
    enriched = [
        merge_automatic_metadata(record, records.get(record.get("canonicalId"), {}))
        for record in patents
    ]
    enriched.sort(key=lambda record: str(record.get("sortDate") or ""), reverse=True)

    page_path = ROOT / "patents.html"
    page = page_path.read_text(encoding="utf-8")
    cards = "\n".join(static_card(record, authors) for record in enriched)
    static_block = f'<div id="collectionContainer" data-static-patents="{len(enriched)}">\n{cards}\n</div>'
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
            patent_schema(record, authors, f"{SITE_URL}/patents/{slug(record)}.html")
            for record in enriched
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
    detail_dir.mkdir(exist_ok=True)
    for old in detail_dir.glob("*.html"):
        old.unlink()
    for record in enriched:
        (detail_dir / f"{slug(record)}.html").write_text(
            detail_page(record, authors),
            encoding="utf-8",
        )
    update_sitemap(enriched)
    update_llms(enriched)
    print(f"Generated {len(enriched)} static patent cards and detail pages.")


if __name__ == "__main__":
    main()
