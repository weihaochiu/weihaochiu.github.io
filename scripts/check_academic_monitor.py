"""Run all academic monitors and write one dashboard JSON file."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from academic_monitor_common import DATA_DIR, now_iso
import check_patents
import check_projects
import check_publications

def main() -> None:
    result_sets = {
        "publications": check_publications.run(),
        "patents": check_patents.run(),
        "projects": check_projects.run(),
    }

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
        "schemaVersion": 1,
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
        },
        "publications": result_sets["publications"]["items"],
        "patents": result_sets["patents"]["items"],
        "projects": result_sets["projects"]["items"],
        "sources": all_sources,
        "copyInstructions": {
            "finalLine": (
                "請根據資料來源逐筆查核，找不到的資料不要自行猜測。"
                "更新相關 JSON、作者資料、統計及 SEO，最後只提供實際修改檔案的 ZIP。"
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
