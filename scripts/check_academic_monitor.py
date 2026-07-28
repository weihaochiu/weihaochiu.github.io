"""Run all academic monitors and write one dashboard JSON file."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from academic_monitor_common import DATA_DIR, now_iso, read_json, review_key
import check_patents
import check_projects
import check_publications

def previous_monitor_payload() -> dict:
    fallback = os.getenv("ACADEMIC_MONITOR_FALLBACK_PATH", "").strip()
    path = Path(fallback) if fallback else DATA_DIR / "academic-monitor.json"
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}

def main() -> None:
    previous = previous_monitor_payload()
    result_sets = {
        "publications": check_publications.run(),
        "patents": check_patents.run(),
        "projects": check_projects.run(),
    }

    for record_type, result in result_sets.items():
        source_failed = any(
            source.get("status") == "error"
            for source in result.get("sources", [])
        )
        cached = previous.get(record_type, [])
        if source_failed and not result.get("items") and isinstance(cached, list) and cached:
            result["items"] = cached
            for source in result.get("sources", []):
                if source.get("status") == "error":
                    suffix = (
                        " The previous candidate list was retained; "
                        "these are cached candidates, not a successful new check."
                    )
                    source["message"] = str(source.get("message") or "") + suffix

    registry = read_json("academic_monitor_review_decisions.json", {})
    decisions = registry.get("decisions", []) if isinstance(registry, dict) else []
    resolved_keys = {
        str(row.get("reviewKey") or "")
        for row in decisions
        if isinstance(row, dict)
        and row.get("status") in {"confirmed_mine", "confirmed_not_mine"}
    }
    suppressed_counts = {}
    for record_type, result in result_sets.items():
        visible = []
        suppressed = 0
        for item in result.get("items", []):
            key = review_key(record_type, item)
            if key:
                item["reviewKey"] = key
            if key and key in resolved_keys:
                suppressed += 1
                continue
            visible.append(item)
        result["items"] = visible
        suppressed_counts[record_type] = suppressed

    all_sources = [
        source
        for result in result_sets.values()
        for source in result.get("sources", [])
    ]
    counts = {
        key: len(result.get("items", []))
        for key, result in result_sets.items()
    }
    source_errors = sum(1 for source in all_sources if source.get("status") == "error")
    source_warnings = sum(1 for source in all_sources if source.get("status") == "warning")

    payload = {
        "schemaVersion": 2,
        "generatedAt": now_iso(),
        "repository": os.getenv(
            "REPOSITORY_URL",
            "https://github.com/weihaochiu/weihaochiu.github.io",
        ),
        "status": "partial" if source_errors or source_warnings else "completed",
        "summary": {
            **counts,
            "totalCandidates": sum(counts.values()),
            "sourceErrors": source_errors,
            "sourceWarnings": source_warnings,
            "resolvedRecordsSuppressed": sum(suppressed_counts.values()),
        },
        "publications": result_sets["publications"]["items"],
        "patents": result_sets["patents"]["items"],
        "projects": result_sets["projects"]["items"],
        "sources": all_sources,
        "copyInstructions": {
            "finalLine": (
                "請根據資料來源逐筆查核，找不到的資料不要自行猜測。"
                "把所有已確認結果寫入 data/academic_monitor_review_decisions.json。"
                "「已確認是本人的」再更新對應成果 JSON；「已確認非本人的」只建立永久排除紀錄，"
                "不要加入成果 JSON；「尚未確認」不可修改成果 JSON。"
                "保留現有非空白人工內容，最後只提供實際修改檔案的 ZIP。"
            )
        },
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output = DATA_DIR / "academic-monitor.json"
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output}")
    print(json.dumps(payload["summary"], ensure_ascii=False))

if __name__ == "__main__":
    main()
