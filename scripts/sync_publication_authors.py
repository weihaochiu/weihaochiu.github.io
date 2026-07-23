#!/usr/bin/env python3
"""Synchronize publication author names into the site's author directory.

Only facts already present in publications.json are copied. Newly observed authors
are marked pending and all unverified profile fields remain blank.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return "".join(char.lower() for char in text if char.isalnum())


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or f"author-{hashlib.sha1(value.encode('utf-8')).hexdigest()[:10]}"


def load_json_array(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"{label} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise SystemExit(f"{label} must be a JSON array of objects: {path}")
    return payload


def author_names(author: dict[str, Any]) -> list[str]:
    values = [author.get("name"), author.get("displayName"), author.get("nameZh")]
    aliases = author.get("aliases") or []
    if not isinstance(aliases, list):
        raise SystemExit(f"Author aliases must be an array: {author.get('id') or author.get('name')}")
    values.extend(aliases)
    return [str(value).strip() for value in values if str(value or "").strip()]


def build_name_index(authors: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for author in authors:
        for name in author_names(author):
            key = normalize_name(name)
            if not key:
                continue
            previous = index.get(key)
            if previous is not None and previous is not author:
                raise SystemExit(
                    f"Ambiguous author name or alias {name!r}: "
                    f"{previous.get('id')!r} and {author.get('id')!r}"
                )
            index[key] = author
    return index


def unique_author_id(name: str, used_ids: set[str]) -> str:
    base = slugify(name)
    candidate = base
    if candidate in used_ids:
        suffix = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
        candidate = f"{base}-{suffix}"
        counter = 2
        while candidate in used_ids:
            candidate = f"{base}-{suffix}-{counter}"
            counter += 1
    used_ids.add(candidate)
    return candidate


def pending_author(name: str, used_ids: set[str]) -> dict[str, Any]:
    return {
        "id": unique_author_id(name, used_ids),
        "name": name,
        "displayName": name,
        "nameZh": "",
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
        "lastVerified": "",
        "sources": [],
    }


def synchronize(publications: list[dict[str, Any]], authors: list[dict[str, Any]]) -> list[str]:
    index = build_name_index(authors)
    used_ids = {str(author.get("id") or "").strip() for author in authors}
    used_ids.discard("")
    added: list[str] = []

    for publication_number, publication in enumerate(publications, start=1):
        names = publication.get("authors") or []
        if not isinstance(names, list):
            raise SystemExit(f"Publication {publication_number} has a non-array authors field")
        for raw_name in names:
            name = str(raw_name or "").strip()
            if not name:
                continue
            key = normalize_name(name)
            if not key or key in index:
                continue
            author = pending_author(name, used_ids)
            authors.append(author)
            index[key] = author
            added.append(name)
    return added


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--publications",
        type=Path,
        default=ROOT / "data/publications.json",
        help="Path to publications.json",
    )
    parser.add_argument(
        "--authors",
        type=Path,
        default=ROOT / "data/authors.json",
        help="Path to authors.json",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report missing authors without writing authors.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    publications = load_json_array(args.publications, "Publications")
    authors = load_json_array(args.authors, "Authors")
    added = synchronize(publications, authors)

    if args.check:
        if added:
            raise SystemExit(f"authors.json is missing {len(added)} publication author(s)")
        print(f"Author directory is complete: {len(authors)} authors, no changes needed.")
        return

    if not added:
        print(f"Author directory is already synchronized: {len(authors)} authors.")
        return

    args.authors.write_text(
        json.dumps(authors, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Added {len(added)} pending author(s) to {args.authors}.")


if __name__ == "__main__":
    main()
