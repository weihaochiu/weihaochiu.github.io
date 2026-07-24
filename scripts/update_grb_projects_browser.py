#!/usr/bin/env python3
"""Render JavaScript-driven GRB pages and merge the resulting project data.

This is a browser fallback for update_grb_projects.py. GRB currently returns an
HTML shell to requests-based clients and injects the actual project values in
the browser. Existing project entries remain authoritative for manually written
summaries and English wording.
"""

from __future__ import annotations

import copy
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Page, sync_playwright

from update_grb_projects import (
    UpdateError,
    build_new_project,
    clean_text,
    discover_links,
    discovery_match_details,
    extract_grb_id,
    merge_known_project,
    normalized_identity,
    now_iso,
    parse_plan_html,
    plan_matches,
    project_grb_id,
    read_json,
    record_key,
    strict_discovery_match,
    sync_tracking_config,
    update_site_meta,
    validate_projects,
    write_json,
)

LOGGER = logging.getLogger("grb-browser")
ROOT = Path(__file__).resolve().parents[1]
DETAIL_PREFIX = "https://www.grb.gov.tw/search/planDetail?id="
DEBUG_DIR = ROOT / "grb_debug"
URL_TRAILING_PUNCTUATION = " \t\r\n:：,，.;；"
STANDARD_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def compact(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def sanitize_grb_url(value: Any) -> str:
    """Remove sentence punctuation and reject non-GRB destinations."""
    url = clean_text(value).rstrip(URL_TRAILING_PUNCTUATION)
    if not url:
        return ""
    if not url.startswith("https://www.grb.gov.tw/"):
        raise UpdateError(f"Unexpected non-GRB URL: {url!r}")
    return url


def debug_slug(value: Any) -> str:
    slug = re.sub(r"[^0-9A-Za-z._-]+", "-", clean_text(value)).strip("-.")
    return slug[:100] or "grb-page"


def save_page_diagnostics(
    page: Page,
    *,
    debug_name: str,
    requested_url: str,
    status: int | None,
    excerpt: str,
) -> None:
    """Persist the exact HTML and screenshot seen by the GitHub runner."""
    if not debug_name:
        return
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    stem = debug_slug(debug_name)
    html_path = DEBUG_DIR / f"{stem}.html"
    png_path = DEBUG_DIR / f"{stem}.png"
    meta_path = DEBUG_DIR / f"{stem}.json"
    try:
        html_path.write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(png_path), full_page=True)
        metadata = {
            "requestedUrl": requested_url,
            "requestedUrlRepr": repr(requested_url),
            "finalUrl": page.url,
            "httpStatus": status,
            "pageTitle": page.title(),
            "userAgent": page.evaluate("() => navigator.userAgent"),
            "excerpt": excerpt,
        }
        meta_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        LOGGER.warning("Unable to save GRB diagnostics for %s: %s", debug_name, exc)


def render_page(
    context: BrowserContext,
    url: str,
    *,
    expected_text: str = "",
    wait_for_detail_links: bool = False,
    debug_name: str = "",
) -> tuple[str, int | None, str]:
    url = sanitize_grb_url(url)
    page: Page = context.new_page()
    status: int | None = None
    LOGGER.info("Opening GRB page\nURL: %s\nURL repr: %r", url, url)
    try:
        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60_000,
            referer="https://www.grb.gov.tw/",
        )
        status = response.status if response else None
        try:
            page.wait_for_load_state("networkidle", timeout=20_000)
        except Exception:
            pass

        if expected_text:
            try:
                page.wait_for_function(
                    "expected => (document.body?.innerText || '').includes(expected)",
                    expected_text,
                    timeout=25_000,
                )
            except Exception:
                page.wait_for_timeout(4_000)
        elif wait_for_detail_links:
            try:
                page.wait_for_function(
                    "() => document.querySelectorAll('a[href*=\"/search/planDetail\"]').length > 0",
                    timeout=20_000,
                )
            except Exception:
                page.wait_for_timeout(4_000)
        else:
            page.wait_for_timeout(1_500)

        html = page.content()
        excerpt = compact(page.locator("body").inner_text())[:800]
        save_page_diagnostics(
            page,
            debug_name=debug_name,
            requested_url=url,
            status=status,
            excerpt=excerpt,
        )
        return html, status, excerpt
    except Exception:
        try:
            excerpt = compact(page.locator("body").inner_text())[:800]
        except Exception:
            excerpt = ""
        save_page_diagnostics(
            page,
            debug_name=debug_name or "navigation-error",
            requested_url=url,
            status=status,
            excerpt=excerpt,
        )
        raise
    finally:
        page.close()


def parse_rendered_plan(
    context: BrowserContext,
    url: str,
    expected_number: str = "",
    *,
    debug_name: str = "",
) -> tuple[dict[str, Any], int | None, str]:
    url = sanitize_grb_url(url)
    html, status, excerpt = render_page(
        context,
        url,
        expected_text=expected_number,
        debug_name=debug_name,
    )
    parsed = parse_plan_html(html, url)
    if not (clean_text(parsed.get("number")) or clean_text(parsed.get("titleZh"))):
        raise UpdateError("Rendered GRB page still contained no recognizable project record")
    if expected_number and parsed.get("number"):
        if normalized_identity(expected_number) != normalized_identity(parsed["number"]):
            raise UpdateError(
                f"Plan number mismatch: expected {expected_number}, got {parsed['number']}"
            )
    return parsed, status, excerpt


def upsert_pending(
    pending_by_key: dict[str, dict[str, Any]],
    parsed: dict[str, Any],
    checked_at: str,
    reason: str,
    match: dict[str, bool],
) -> None:
    item = copy.deepcopy(parsed)
    item.update(
        {
            "reviewRequired": True,
            "detectedAt": checked_at,
            "reviewReason": reason,
            "match": match,
        }
    )
    pending_by_key[record_key(item)] = item


def main() -> int:
    projects_path = ROOT / "data/projects.json"
    config_path = ROOT / "data/grb_project_sources.json"
    snapshot_path = ROOT / "data/grb_projects_snapshot.json"
    pending_path = ROOT / "data/grb_projects_pending.json"
    site_meta_path = ROOT / "data/site_meta.json"

    projects = read_json(projects_path, [])
    original_projects = copy.deepcopy(projects)
    config = read_json(config_path, {})
    original_config = copy.deepcopy(config)
    pending = read_json(pending_path, [])
    if not isinstance(pending, list):
        pending = []
    pending_by_key = {
        record_key(item): item for item in pending if isinstance(item, dict)
    }

    validate_projects(projects)
    config = sync_tracking_config(projects, config, detect_manual_removal=True)

    checked_at = now_iso()
    snapshot = read_json(snapshot_path, {})
    if not isinstance(snapshot, dict):
        snapshot = {}
    snapshot.update(
        {
            "source": "Government Research Bulletin (GRB), Taiwan",
            "sourceUrl": "https://www.grb.gov.tw/",
            "checkedAt": checked_at,
            "browserFallback": True,
        }
    )
    snapshot["records"] = snapshot.get("records") if isinstance(snapshot.get("records"), dict) else {}
    snapshot["discovery"] = []

    # Do not reuse the requests crawler user agent in Chromium. A bot-style UA can
    # cause some WAFs to return a maintenance page even when a normal browser works.
    browser_user_agent = (
        clean_text(config.get("browserUserAgent")) or STANDARD_BROWSER_USER_AGENT
    )

    success_count = 0
    discovered_urls: list[str] = []
    auto_added: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        context = browser.new_context(
            user_agent=browser_user_agent,
            locale="zh-TW",
            timezone_id="Asia/Taipei",
            extra_http_headers={"Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7"},
        )
        try:
            # Establish cookies/session state in the same way as a normal visitor.
            render_page(
                context,
                "https://www.grb.gov.tw/",
                debug_name="homepage-session",
            )

            # Reproduce the successful manual path: open the researcher search
            # before navigating to individual project detail pages.
            for index, raw_discovery_url in enumerate(config.get("discoveryUrls", []), start=1):
                try:
                    session_url = sanitize_grb_url(raw_discovery_url)
                    render_page(
                        context,
                        session_url,
                        wait_for_detail_links=True,
                        debug_name=f"session-search-{index}",
                    )
                except Exception as exc:
                    LOGGER.warning(
                        "GRB session search failed\nURL: %s\nURL repr: %r\nError: %s",
                        raw_discovery_url,
                        raw_discovery_url,
                        exc,
                    )

            for source in config.get("knownPlans", []):
                grb_id = clean_text(source.get("grbId"))
                url = sanitize_grb_url(source.get("url")) or f"{DETAIL_PREFIX}{grb_id}"
                entry: dict[str, Any] = {
                    "grbId": grb_id,
                    "url": url,
                    "ok": False,
                    "fetchMode": "playwright",
                }
                try:
                    parsed, status, excerpt = parse_rendered_plan(
                        context,
                        url,
                        clean_text(source.get("number")),
                        debug_name=f"known-{grb_id or 'unknown'}",
                    )
                    entry["statusCode"] = status
                    match_index = next(
                        (i for i, project in enumerate(projects) if plan_matches(project, source)),
                        None,
                    )
                    if match_index is None:
                        raise UpdateError("Known GRB plan does not match an existing project")
                    merged, changed_fields = merge_known_project(
                        projects[match_index], parsed, source
                    )
                    projects[match_index] = merged
                    entry.update(
                        {
                            "ok": True,
                            "parsed": parsed,
                            "changedFields": changed_fields,
                            "textExcerpt": excerpt,
                        }
                    )
                    success_count += 1
                except Exception as exc:
                    entry["error"] = str(exc)
                    LOGGER.warning(
                        "Rendered GRB update failed\nURL: %s\nURL repr: %r\nError: %s",
                        url,
                        url,
                        exc,
                    )
                snapshot["records"][grb_id or url] = entry

            for discovery_index, raw_discovery_url in enumerate(config.get("discoveryUrls", []), start=1):
                discovery_url = sanitize_grb_url(raw_discovery_url)
                discovery_entry: dict[str, Any] = {
                    "url": discovery_url,
                    "ok": False,
                    "fetchMode": "playwright",
                }
                try:
                    html, status, excerpt = render_page(
                        context,
                        discovery_url,
                        wait_for_detail_links=True,
                        debug_name=f"discovery-{discovery_index}",
                    )
                    links = discover_links(html, discovery_url)
                    discovery_entry.update(
                        {
                            "ok": True,
                            "statusCode": status,
                            "linksFound": len(links),
                            "textExcerpt": excerpt,
                        }
                    )
                    discovered_urls.extend(links)
                except Exception as exc:
                    discovery_entry["error"] = str(exc)
                snapshot["discovery"].append(discovery_entry)

            ignored_ids = {
                clean_text(value)
                for value in config.get("ignoredGrbIds", [])
                if clean_text(value)
            }
            known_keys = {record_key(project) for project in projects}
            max_candidates = int(config.get("maxDiscoveryCandidates", 20))
            auto_add_verified = bool(config.get("autoAddVerifiedProjects", True))

            for url in list(dict.fromkeys(discovered_urls))[:max_candidates]:
                candidate_id = extract_grb_id(url)
                candidate_key = f"grb:{candidate_id}"
                if not candidate_id or candidate_id in ignored_ids or candidate_key in known_keys:
                    pending_by_key.pop(candidate_key, None)
                    continue
                try:
                    url = sanitize_grb_url(url)
                    parsed, status, excerpt = parse_rendered_plan(
                        context,
                        url,
                        debug_name=f"candidate-{candidate_id or 'unknown'}",
                    )
                    details = discovery_match_details(parsed, config)
                    if strict_discovery_match(parsed, config) and auto_add_verified:
                        project = build_new_project(parsed, config, checked_at)
                        projects.append(project)
                        known_keys.add(record_key(project))
                        pending_by_key.pop(record_key(project), None)
                        auto_added.append(candidate_id)
                        snapshot["records"][candidate_id] = {
                            "grbId": candidate_id,
                            "url": url,
                            "ok": True,
                            "fetchMode": "playwright",
                            "statusCode": status,
                            "autoAdded": True,
                            "match": details,
                            "parsed": parsed,
                            "textExcerpt": excerpt,
                        }
                    elif details["nameMatch"] or details["institutionMatch"]:
                        upsert_pending(
                            pending_by_key,
                            parsed,
                            checked_at,
                            "Automatic publication requires matching researcher name, institution, GRB ID, plan number, and title.",
                            details,
                        )
                except Exception as exc:
                    LOGGER.warning(
                        "Rendered discovery candidate failed\nURL: %s\nURL repr: %r\nError: %s",
                        url,
                        url,
                        exc,
                    )
        finally:
            context.close()
            browser.close()

    config = sync_tracking_config(projects, config, detect_manual_removal=False)
    active_ids = {project_grb_id(project) for project in projects if project_grb_id(project)}
    ignored_ids = {
        clean_text(value)
        for value in config.get("ignoredGrbIds", [])
        if clean_text(value)
    }
    pending = [
        item
        for item in pending_by_key.values()
        if clean_text(item.get("grbId")) not in active_ids
        and clean_text(item.get("grbId")) not in ignored_ids
    ]
    pending.sort(
        key=lambda item: str(item.get("sortDate") or item.get("detectedAt") or ""),
        reverse=True,
    )

    if len(projects) < len(original_projects):
        raise UpdateError("Project count decreased; refusing to write")
    validate_projects(projects)
    projects.sort(key=lambda item: str(item.get("sortDate") or ""), reverse=True)

    projects_changed = projects != original_projects
    config_changed = config != original_config
    if projects_changed:
        write_json(projects_path, projects)
        update_site_meta(site_meta_path)
    if config_changed:
        write_json(config_path, config)
    write_json(snapshot_path, snapshot)
    write_json(pending_path, pending)

    if config.get("knownPlans") and success_count == 0:
        raise UpdateError(
            "Playwright rendered zero known GRB records; inspect the browser-step log before trusting the update"
        )

    LOGGER.info(
        "Browser GRB update complete: known_success=%d auto_added=%d projects_changed=%s pending=%d",
        success_count,
        len(auto_added),
        projects_changed,
        len(pending),
    )
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        sys.exit(main())
    except Exception as exc:
        LOGGER.error("%s", exc)
        sys.exit(1)
