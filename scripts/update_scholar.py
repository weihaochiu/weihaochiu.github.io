#!/usr/bin/env python3
"""Best-effort Google Scholar updater; never replaces valid values with failed/implausible data."""
from pathlib import Path
import json, re, sys, time
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
METRICS=ROOT/'data/scholar_metrics.json'
PUBS=ROOT/'data/publications.json'
PROFILE_ID='ZYbNQb8AAAAJ'
URL=f'https://scholar.google.com/citations?user={PROFILE_ID}&hl=en&pagesize=100'

def fetch_html():
    headers={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36','Accept-Language':'en-US,en;q=0.9'}
    error=None
    for attempt in range(3):
        try:
            r=requests.get(URL,headers=headers,timeout=35)
            r.raise_for_status()
            if 'gsc_rsb_std' not in r.text or 'unusual traffic' in r.text.lower():
                raise RuntimeError('Scholar profile unavailable or CAPTCHA returned')
            return r.text
        except Exception as exc:
            error=exc
            if attempt<2: time.sleep(5*(attempt+1))
    raise RuntimeError(str(error))

def norm(s): return re.sub(r'[^a-z0-9]+',' ',s.lower()).strip()

def main():
    old=json.loads(METRICS.read_text(encoding='utf-8'))
    try:
        soup=BeautifulSoup(fetch_html(),'html.parser')
        cells=soup.select('#gsc_rsb_st td.gsc_rsb_std')
        vals=[int(x.get_text(strip=True).replace(',','')) for x in cells]
        if len(vals)<5: raise RuntimeError('Metric table incomplete')
        citations,hindex,i10=vals[0],vals[2],vals[4]
        if citations < int(old.get('citations',0))*0.9: raise RuntimeError('Suspicious total-citation decrease')
        now=datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='seconds')
        new={**old,'citations':citations,'hIndex':hindex,'i10Index':i10,'lastSuccessfulUpdate':now,'lastAttempt':now,'status':'success'}
        pubs=json.loads(PUBS.read_text(encoding='utf-8'))
        indexed={norm(p.get('title','')):p for p in pubs}
        updated=0
        for row in soup.select('.gsc_a_tr'):
            title_el=row.select_one('.gsc_a_at'); citation_el=row.select_one('.gsc_a_c a')
            if not title_el: continue
            scholar_title=norm(title_el.get_text(' ',strip=True))
            match=next((p for key,p in indexed.items() if scholar_title==key or (len(key)>35 and (scholar_title in key or key in scholar_title))),None)
            if not match: continue
            raw=citation_el.get_text(strip=True).replace(',','') if citation_el else ''
            if raw.isdigit():
                candidate=int(raw); previous=int(match.get('citationCount') or 0)
                if candidate>=previous:
                    match['citationCount']=candidate; updated+=1
                    if citation_el.get('href'):
                        match['scholarCitedByUrl']='https://scholar.google.com'+citation_el['href']
                        match['scholarLinkVerified']=True
        METRICS.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        PUBS.write_text(json.dumps(pubs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f'Updated profile: citations={citations}, h={hindex}, i10={i10}; matched publications={updated}')
    except Exception as exc:
        attempted=datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='seconds')
        old['lastAttempt']=attempted
        old['status']='update skipped; previous valid values retained'
        METRICS.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f'Scholar update skipped; previous valid values preserved: {exc}',file=sys.stderr)
        sys.exit(0)
if __name__=='__main__': main()
