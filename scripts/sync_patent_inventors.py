#!/usr/bin/env python3
"""Ensure every structured patent inventor exists in data/authors.json.

Only names and patent-source URLs already present in patents.json are copied.
No affiliation, employment, ORCID, or profile URL is inferred.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sync_publication_authors import build_name_index, load_json_array


ROOT = Path(__file__).resolve().parents[1]


def pending_inventor(person_id: str, name_en: str, name_zh: str, source: str) -> dict[str, Any]:
    return {
        "id": person_id,
        "name": name_en,
        "displayName": name_en,
        "nameZh": name_zh,
        "aliases": [],
        "role": "",
        "currentPosition": "",
        "affiliation": "",
        "affiliationZh": "",
        "email": [],
        "telephone": "",
        "orcid": "",
        "links": {},
        "status": "pending",
        "verificationLevel": "Patent-record name only",
        "lastVerified": "",
        "sources": [source] if source else [],
        "contributionTypes": ["patent-inventor"],
    }


def synchronize(patents: list[dict[str, Any]], authors: list[dict[str, Any]]) -> list[str]:
    name_index = build_name_index(authors)
    id_index = {str(author.get("id") or ""): author for author in authors}
    added: list[str] = []
    for patent_number, patent in enumerate(patents, start=1):
        inventors = patent.get("inventors")
        if not isinstance(inventors, list) or not inventors:
            raise SystemExit(f"Patent {patent_number} has no structured inventors")
        for inventor_number, inventor in enumerate(inventors, start=1):
            if not isinstance(inventor, dict):
                raise SystemExit(f"Patent {patent_number} inventor {inventor_number} is not an object")
            person_id = str(inventor.get("personId") or "").strip()
            name_en = str(inventor.get("nameEn") or "").strip()
            name_zh = str(inventor.get("nameZh") or "").strip()
            if not person_id or not name_en:
                raise SystemExit(f"Patent {patent_number} inventor {inventor_number} lacks personId or nameEn")
            author = id_index.get(person_id)
            if author is None:
                source = str(patent.get("url") or "")
                author = pending_inventor(person_id, name_en, name_zh, source)
                authors.append(author)
                id_index[person_id] = author
                added.append(name_en)
                name_index = build_name_index(authors)
            elif not any(value is author for value in name_index.values()):
                raise SystemExit(f"Author directory identity conflict for {person_id}")
    return added


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patents", type=Path, default=ROOT / "data/patents.json")
    parser.add_argument("--authors", type=Path, default=ROOT / "data/authors.json")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    patents = load_json_array(args.patents, "Patents")
    authors = load_json_array(args.authors, "Authors")
    original = json.dumps(authors, ensure_ascii=False, sort_keys=True)
    added = synchronize(patents, authors)
    changed = original != json.dumps(authors, ensure_ascii=False, sort_keys=True)
    if args.check:
        if changed:
            raise SystemExit(
                f"authors.json needs patent-inventor synchronization"
                f"{f'; {len(added)} missing inventor(s)' if added else ''}"
            )
        print(f"Patent inventors are synchronized: {len(authors)} people.")
        return
    if not changed:
        print(f"Patent inventors are already synchronized: {len(authors)} people.")
        return
    args.authors.write_text(
        json.dumps(authors, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Synchronized patent inventors; added {len(added)} pending person record(s).")


if __name__ == "__main__":
    main()
