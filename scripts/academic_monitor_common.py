"""Shared helpers for the academic record monitor."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
USER_AGENT = (
    "Wei-Hao-Chiu-Academic-Monitor/1.0 "
    f"(mailto:{os.getenv('CONTACT_EMAIL', 'weihao.chiu@gmail.com')})"
)

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

def read_json(name: str, default: Any) -> Any:
    path = DATA_DIR / name
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)

def request_json(url: str, *, accept: str = "application/json", timeout: int = 30) -> Any:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)

def request_text(url: str, *, timeout: int = 30) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")

def source_result(name: str, url: str, status: str, message: str = "", count: int | None = None) -> dict:
    result = {
        "name": name,
        "url": url,
        "status": status,
        "message": message,
        "checkedAt": now_iso(),
    }
    if count is not None:
        result["candidateCount"] = count
    return result

def normalize_doi(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    text = re.sub(r"^doi:\s*", "", text)
    return text.rstrip(" .")

def normalize_identifier(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())

def normalize_title(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

def first(value: Any, default: str = "") -> str:
    if isinstance(value, list):
        return str(value[0]) if value else default
    return str(value) if value is not None else default

def date_parts(message: dict) -> str:
    for key in ("published-print", "published-online", "published", "issued", "created"):
        parts = message.get(key, {}).get("date-parts", [])
        if parts and parts[0]:
            values = [int(v) for v in parts[0][:3]]
            while len(values) < 3:
                values.append(1)
            return f"{values[0]:04d}-{values[1]:02d}-{values[2]:02d}"
    return ""

def safe_error(error: Exception) -> str:
    if isinstance(error, urllib.error.HTTPError):
        return f"HTTP {error.code}: {error.reason}"
    if isinstance(error, urllib.error.URLError):
        return f"Network error: {error.reason}"
    return f"{type(error).__name__}: {error}"
