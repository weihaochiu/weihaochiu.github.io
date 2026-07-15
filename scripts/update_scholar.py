#!/usr/bin/env python3
"""Best-effort Google Scholar updater; never replaces valid values with failed or implausible data."""
from pathlib import Path
import html
import json
import re
import sys
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / 'data/scholar_metrics.json'
PUBS = ROOT / 'data/publications.json'
PROFILE_ID = 'ZYbNQb8AAAAJ'
SCHOLAR_ORIGIN = 'https://scholar.google.com'
URL = f'{SCHOLAR_ORIGIN}/citations?user={PROFILE_ID}&hl=en&pagesize=100'


def fetch_html():
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    error = None
    for attempt in range(3):
        try:
            response = requests.get(URL, headers=headers, timeout=35)
            response.raise_for_status()
            if 'gsc_rsb_std' not in response.text or 'unusual traffic' in response.text.lower():
                raise RuntimeError('Scholar profile unavailable or CAPTCHA returned')
            return response.text
        except Exception as exc:
            error = exc
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(str(error))


def norm(value):
    return re.sub(r'[^a-z0-9]+', ' ', value.lower()).strip()


def normalize_scholar_url(value):
    """Return one valid Scholar URL and remove accidentally duplicated origins."""
    text = html.unescape(str(value or '').strip())
    if not text:
        return ''

    positions = [index for index in (text.find('https://', 8), text.find('http://', 7)) if index > 0]
    if positions:
        text = text[min(positions):]

    if text.startswith('//'):
        text = f'https:{text}'
    elif text.startswith('/'):
        text = urljoin(f'{SCHOLAR_ORIGIN}/', text)

    try:
        parsed = urlparse(text)
    except ValueError:
        return ''
    if not parsed.netloc or not parsed.netloc.lower().startswith('scholar.google.'):
        return ''

    return urlunparse(('https', 'scholar.google.com', parsed.path, parsed.params, parsed.query, parsed.fragment))


def repair_existing_links(publications):
    repaired = 0
    for publication in publications:
        for field in ('scholarCitedByUrl', 'citedByUrl'):
            previous = str(publication.get(field) or '')
            cleaned = normalize_scholar_url(previous)
            if cleaned != previous:
                publication[field] = cleaned
                repaired += 1
                if field == 'scholarCitedByUrl' and previous and not cleaned:
                    publication['scholarLinkVerified'] = False
    return repaired


def write_publications(publications):
    PUBS.write_text(json.dumps(publications, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    old = json.loads(METRICS.read_text(encoding='utf-8'))
    publications = json.loads(PUBS.read_text(encoding='utf-8'))
    repaired = repair_existing_links(publications)
    if repaired:
        write_publications(publications)

    try:
        soup = BeautifulSoup(fetch_html(), 'html.parser')
        cells = soup.select('#gsc_rsb_st td.gsc_rsb_std')
        values = [int(cell.get_text(strip=True).replace(',', '')) for cell in cells]
        if len(values) < 5:
            raise RuntimeError('Metric table incomplete')

        citations, h_index, i10_index = values[0], values[2], values[4]
        if citations < int(old.get('citations', 0)) * 0.9:
            raise RuntimeError('Suspicious total-citation decrease')

        now = datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='seconds')
        new = {
            **old,
            'citations': citations,
            'hIndex': h_index,
            'i10Index': i10_index,
            'lastSuccessfulUpdate': now,
            'lastAttempt': now,
            'status': 'success',
        }

        indexed = {norm(publication.get('title', '')): publication for publication in publications}
        updated = 0
        for row in soup.select('.gsc_a_tr'):
            title_el = row.select_one('.gsc_a_at')
            citation_el = row.select_one('.gsc_a_c a')
            if not title_el:
                continue

            scholar_title = norm(title_el.get_text(' ', strip=True))
            match = next(
                (
                    publication
                    for key, publication in indexed.items()
                    if scholar_title == key or (len(key) > 35 and (scholar_title in key or key in scholar_title))
                ),
                None,
            )
            if not match:
                continue

            raw_count = citation_el.get_text(strip=True).replace(',', '') if citation_el else ''
            if not raw_count.isdigit():
                continue

            candidate = int(raw_count)
            previous = int(match.get('citationCount') or 0)
            if candidate < previous:
                continue

            match['citationCount'] = candidate
            updated += 1
            raw_link = citation_el.get('href', '') if citation_el else ''
            clean_link = normalize_scholar_url(raw_link)
            if clean_link:
                match['scholarCitedByUrl'] = clean_link
                match['scholarLinkVerified'] = True

        repair_existing_links(publications)
        METRICS.write_text(json.dumps(new, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        write_publications(publications)
        print(f'Updated profile: citations={citations}, h={h_index}, i10={i10_index}; matched publications={updated}; repaired links={repaired}')
    except Exception as exc:
        attempted = datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='seconds')
        old['lastAttempt'] = attempted
        old['status'] = 'update skipped; previous valid values retained'
        METRICS.write_text(json.dumps(old, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'Scholar update skipped; previous valid values preserved: {exc}', file=sys.stderr)
        sys.exit(0)


if __name__ == '__main__':
    main()
