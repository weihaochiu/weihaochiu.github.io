#!/usr/bin/env python3
"""Update per-publication Scopus citation counts and install the front-end integration.

The updater is deliberately conservative:
- API credentials are read only from environment variables.
- A failed request never overwrites a previously verified citation count.
- Missing or unverified records are not displayed as zero citations.
- Front-end integration is idempotently installed using marker comments.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
PUBLICATIONS = ROOT / "data" / "publications.json"
SCOPUS_DATA = ROOT / "data" / "scopus_citations.json"
APP_JS = ROOT / "assets" / "js" / "app.js"
PUBLICATIONS_HTML = ROOT / "publications.html"
API_URL = "https://api.elsevier.com/content/abstract/citations"
START_MARKER = "/* SCOPUS_INTEGRATION_START */"
END_MARKER = "/* SCOPUS_INTEGRATION_END */"

FRONTEND_BLOCK = r'''/* SCOPUS_INTEGRATION_START */
(function installScopusIntegration(){
  if(window.__scopusIntegrationInstalled)return;
  window.__scopusIntegrationInstalled=true;

  const originalEnrichPublications=enrichPublications;
  const originalPublicationCard=publicationCard;

  function scopusMetric(p){
    const metric=p?.scopus||null;
    if(!metric||metric.status!=='verified')return null;
    const count=Number(metric.citationCount);
    return Number.isFinite(count)&&count>=0?{...metric,citationCount:count}:null;
  }

  function normalizeScopusUrl(value){
    const url=String(value||'').trim();
    if(!url)return '';
    try{
      const parsed=new URL(url);
      const host=parsed.hostname.toLowerCase();
      if(parsed.protocol!=='https:'||!(host==='scopus.com'||host.endsWith('.scopus.com')))return '';
      return parsed.toString();
    }catch(error){return ''}
  }

  enrichPublications=function(rows,taxonomy={},mendeley={},unpaywall={},scopus={}){
    const enriched=originalEnrichPublications(rows,taxonomy,mendeley,unpaywall);
    const metricMap=scopus.records||{};
    return enriched.map(p=>({...p,scopus:metricMap[publicationKey(p)]||null}));
  };

  publicationCard=function(p){
    let html=originalPublicationCard(p);
    const metric=scopusMetric(p);
    if(!metric)return html;
    const n=metric.citationCount;
    const url=normalizeScopusUrl(metric.citedByUrl)||normalizeScopusUrl(metric.scopusUrl);
    const label=`Scopus: ${n} citation${n===1?'':'s'}`;
    const action=url
      ?`<a class="action scopus-action" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${label} ↗</a>`
      :`<span class="action scopus-action">${label}</span>`;
    if(html.includes('<a class="action metric-action"'))return html.replace('<a class="action metric-action"',`${action}<a class="action metric-action"`);
    if(html.includes('<span class="share-wrap"'))return html.replace('<span class="share-wrap"',`${action}<span class="share-wrap"`);
    return html.replace('</div></article>',`${action}</div></article>`);
  };

  initCollection=async function(){
    const root=$('[data-collection]');if(!root)return;
    const name=root.dataset.collection;
    const rawRows=await loadData(name);
    const [taxonomy,mendeley,unpaywall,scopus]=name==='publications'
      ?await Promise.all([
          loadData('publication_taxonomy').catch(()=>({})),
          loadData('mendeley_metrics').catch(()=>({})),
          loadData('unpaywall').catch(()=>({})),
          loadData('scopus_citations').catch(()=>({}))
        ])
      :[{},{},{},{}];
    const rows=name==='publications'?enrichPublications(rawRows,taxonomy,mendeley,unpaywall,scopus):rawRows;
    const search=$('#searchInput'),year=$('#yearFilter'),topic=$('#topicFilter'),sort=$('#sortFilter'),count=$('#resultCount'),container=$('#collectionContainer'),empty=$('#emptyState');
    fillSelect(year,rows.map(yearOf),'All years','numeric-desc');
    if(topic){
      if(name==='publications')fillPublicationThemeSelect(topic,taxonomy);
      else fillSelect(topic,rows.map(x=>x.topic).filter(Boolean),'All themes','alpha');
    }
    const citedOption=sort?.querySelector('option[value="citations-desc"]');
    if(citedOption&&name==='publications'){
      citedOption.textContent='Most cited (Scopus)';
      citedOption.disabled=!rows.some(p=>!!scopusMetric(p));
      if(citedOption.disabled&&sort.value==='citations-desc')sort.value='date-desc';
    }
    const card={publications:publicationCard,patents:patentCard,projects:projectCard,awards:awardCard}[name];
    function applyChartSelection(selectedYear,category){
      if(year)year.value=String(selectedYear);
      if(topic&&category)topic.value=`category:${category}`;
      render();
      $('.filter-bar')?.scrollIntoView({behavior:'smooth',block:'center'});
    }
    if(name==='publications')renderPublicationStackedChart($('#collectionYearChart'),rows,applyChartSelection,taxonomy);
    else singleChart($('#collectionYearChart'),rows,y=>applyChartSelection(y,''));
    function compareScopus(a,b){
      const am=scopusMetric(a),bm=scopusMetric(b);
      if(am&&!bm)return -1;
      if(!am&&bm)return 1;
      if(am&&bm&&bm.citationCount!==am.citationCount)return bm.citationCount-am.citationCount;
      const dateDifference=String(b.sortDate||b.date||'').localeCompare(String(a.sortDate||a.date||''));
      return dateDifference||String(a.title||'').localeCompare(String(b.title||''));
    }
    function render(){
      const q=(search?.value||'').trim().toLowerCase();
      let list=rows.filter(x=>{
        const searchMatch=!q||JSON.stringify(x).toLowerCase().includes(q);
        const yearMatch=!year?.value||String(yearOf(x))===year.value;
        const topicMatch=!topic||!topic.value||(name==='publications'?publicationMatchesTheme(x,topic.value):x.topic===topic.value);
        return searchMatch&&yearMatch&&topicMatch;
      });
      const mode=sort?.value||'date-desc';
      list.sort((a,b)=>mode==='date-asc'
        ?String(a.sortDate||a.date).localeCompare(String(b.sortDate||b.date))
        :mode==='title-asc'
          ?String(a.title||a.titleEn).localeCompare(String(b.title||b.titleEn))
          :mode==='citations-desc'&&name==='publications'
            ?compareScopus(a,b)
            :String(b.sortDate||b.date).localeCompare(String(a.sortDate||a.date)));
      if(count)count.textContent=list.length;
      if(empty)empty.hidden=!!list.length;
      if(mode==='citations-desc'&&name==='publications'){
        container.innerHTML=`<section class="year-group citation-ranking"><div class="year-heading"><h3>Most cited in Scopus</h3><span>${list.length} record${list.length===1?'':'s'}</span></div><div class="collection-list">${list.map(card).join('')}</div></section>`;
      }else{
        const grouped=list.reduce((o,x)=>((o[yearOf(x)]??=[]).push(x),o),{});
        container.innerHTML=Object.keys(grouped).sort((a,b)=>mode==='date-asc'?a-b:b-a).map(y=>`<section class="year-group"><div class="year-heading"><h3>${y}</h3><span>${grouped[y].length} record${grouped[y].length===1?'':'s'}</span></div><div class="collection-list">${grouped[y].map(card).join('')}</div></section>`).join('');
      }
      if(name==='publications')requestAnimationFrame(focusHashPublication);
    }
    [search,year,topic,sort].filter(Boolean).forEach(e=>e.addEventListener(e===search?'input':'change',render));
    $('#clearFilters')?.addEventListener('click',()=>{if(search)search.value='';if(year)year.value='';if(topic)topic.value='';if(sort)sort.value='date-desc';render()});
    render();
  };
})();
/* SCOPUS_INTEGRATION_END */'''


def now_taipei() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def install_frontend() -> bool:
    changed = False
    app = APP_JS.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.S)
    updated = pattern.sub(FRONTEND_BLOCK, app) if pattern.search(app) else app.rstrip() + "\n\n" + FRONTEND_BLOCK + "\n"
    if updated != app:
        APP_JS.write_text(updated, encoding="utf-8")
        changed = True

    page = PUBLICATIONS_HTML.read_text(encoding="utf-8")
    updated_page = page.replace(
        '<option value="citations-desc">Most cited</option>',
        '<option value="citations-desc">Most cited (Scopus)</option>',
    )
    if updated_page != page:
        PUBLICATIONS_HTML.write_text(updated_page, encoding="utf-8")
        changed = True
    return changed


def walk(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def first_scalar(payload: Any, keys: tuple[str, ...]) -> Any:
    for node in walk(payload):
        for key in keys:
            if key in node and not isinstance(node[key], (dict, list)):
                return node[key]
    return None


def extract_links(payload: Any) -> tuple[str, str]:
    scopus_url = ""
    cited_by_url = ""
    for node in walk(payload):
        ref = str(node.get("@ref") or node.get("ref") or "").lower()
        href = str(node.get("@href") or node.get("href") or "").strip()
        if not href.startswith("https://"):
            continue
        if ref in {"scopus-citedby", "scopus-cited-by"}:
            cited_by_url = href
        elif ref == "scopus":
            scopus_url = href
    return scopus_url, cited_by_url


def parse_record(payload: Any) -> dict[str, Any] | None:
    raw_count = first_scalar(payload, ("citation-count", "citationCount", "citedby-count"))
    try:
        count = int(str(raw_count).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if count < 0:
        return None
    eid = str(first_scalar(payload, ("eid", "dc:identifier")) or "").strip()
    scopus_url, cited_by_url = extract_links(payload)
    return {
        "citationCount": count,
        "eid": eid,
        "scopusUrl": scopus_url,
        "citedByUrl": cited_by_url,
        "status": "verified",
        "lastUpdated": now_taipei(),
    }


def fetch_scopus(session: requests.Session, doi: str, api_key: str, inst_token: str = "") -> dict[str, Any]:
    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json",
        "User-Agent": "Wei-Hao-Chiu-Academic-Website/1.0",
    }
    if inst_token:
        headers["X-ELS-Insttoken"] = inst_token
    response = session.get(API_URL, params={"doi": doi}, headers=headers, timeout=35)
    if response.status_code in {401, 403}:
        raise PermissionError(f"Scopus API denied access ({response.status_code})")
    if response.status_code == 429:
        raise RuntimeError("Scopus API quota or rate limit exceeded")
    if response.status_code == 404:
        return {"status": "not-found"}
    response.raise_for_status()
    record = parse_record(response.json())
    return record or {"status": "unverified-response"}


def main() -> int:
    frontend_changed = install_frontend()
    publications = read_json(PUBLICATIONS, [])
    old = read_json(SCOPUS_DATA, {"source": "Scopus", "records": {}})
    records = dict(old.get("records") or {})
    attempted = now_taipei()
    api_key = os.getenv("SCOPUS_API_KEY", "").strip()
    inst_token = os.getenv("SCOPUS_INST_TOKEN", "").strip()

    if not api_key:
        payload = {
            **old,
            "source": "Scopus",
            "api": "Scopus Citation Count Metadata API",
            "lastAttempt": attempted,
            "status": "configuration required: add SCOPUS_API_KEY to GitHub Actions secrets",
            "records": records,
        }
        write_json(SCOPUS_DATA, payload)
        print(f"Front-end installed={frontend_changed}; Scopus API update skipped because SCOPUS_API_KEY is not configured.")
        return 0

    updated = 0
    verified = 0
    failures: list[str] = []
    session = requests.Session()
    for publication in publications:
        doi = str(publication.get("doi") or "").strip()
        key = doi.lower()
        if not doi:
            continue
        try:
            result = fetch_scopus(session, doi, api_key, inst_token)
            if result.get("status") == "verified":
                previous = records.get(key) or {}
                previous_count = previous.get("citationCount")
                candidate = int(result["citationCount"])
                if isinstance(previous_count, int) and candidate < previous_count:
                    failures.append(f"{doi}: suspicious citation decrease {previous_count}->{candidate}; previous value retained")
                else:
                    records[key] = {"doi": doi, **result}
                    updated += 1
                verified += 1
            elif result.get("status") == "not-found":
                if key not in records:
                    records[key] = {"doi": doi, "status": "not-found", "lastAttempt": attempted}
            else:
                failures.append(f"{doi}: citation count not present in API response")
        except PermissionError as exc:
            failures.append(str(exc))
            break
        except Exception as exc:  # preserve all previously verified data
            failures.append(f"{doi}: {exc}")
        time.sleep(0.12)

    successful = verified > 0
    payload = {
        "source": "Scopus",
        "api": "Scopus Citation Count Metadata API",
        "lastAttempt": attempted,
        "lastSuccessfulUpdate": attempted if successful else old.get("lastSuccessfulUpdate"),
        "status": "success" if successful and not failures else ("partial success" if successful else "update skipped; previous verified values retained"),
        "verifiedRecords": sum(1 for record in records.values() if record.get("status") == "verified"),
        "records": records,
    }
    if failures:
        payload["warnings"] = failures[:20]
    write_json(SCOPUS_DATA, payload)
    print(f"Front-end installed={frontend_changed}; verified responses={verified}; records updated={updated}; warnings={len(failures)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
