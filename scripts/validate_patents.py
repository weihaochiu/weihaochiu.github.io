#!/usr/bin/env python3
"""Validate patent identity, family, person, metadata, and date integrity."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from patent_common import build_alias_index, normalize_identifier


ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Unable to load {path}: {exc}") from exc


def validate() -> list[str]:
    patents = load(ROOT / "data/patents.json")
    families = load(ROOT / "data/patent_families.json")
    authors = load(ROOT / "data/authors.json")
    metadata = load(ROOT / "data/patent_metadata.json")
    errors: list[str] = []
    if not isinstance(patents, list):
        return ["data/patents.json must be an array"]
    if not isinstance(families, list):
        return ["data/patent_families.json must be an array"]
    if not isinstance(authors, list):
        return ["data/authors.json must be an array"]
    try:
        alias_index = build_alias_index(patents)
    except ValueError as exc:
        errors.append(str(exc))
        alias_index = {}
    canonical_ids = {
        normalize_identifier(patent.get("canonicalId"))
        for patent in patents
        if normalize_identifier(patent.get("canonicalId"))
    }
    person_ids = {str(author.get("id") or "") for author in authors}
    family_ids = {str(family.get("familyId") or "") for family in families}
    if len(canonical_ids) != len(patents):
        errors.append("Every patent must have a unique canonicalId")
    if len(family_ids) != len(families) or "" in family_ids:
        errors.append("Every patent family must have a unique non-empty familyId")

    family_documents: dict[str, str] = {}
    for family in families:
        family_id = str(family.get("familyId") or "")
        for document in family.get("documents") or []:
            canonical = normalize_identifier(document)
            if canonical not in canonical_ids:
                errors.append(f"Family {family_id} references missing patent {document}")
            previous = family_documents.get(canonical)
            if previous and previous != family_id:
                errors.append(f"Patent {canonical} belongs to two families: {previous}, {family_id}")
            family_documents[canonical] = family_id

    for patent in patents:
        canonical = normalize_identifier(patent.get("canonicalId"))
        label = canonical or str(patent.get("number") or "<unknown>")
        if patent.get("familyId") not in family_ids:
            errors.append(f"{label}: missing or invalid familyId")
        if family_documents.get(canonical) != patent.get("familyId"):
            errors.append(f"{label}: patents.json and patent_families.json disagree")
        if normalize_identifier(patent.get("url", "").split("/patent/")[-1].split("/")[0]) != canonical:
            errors.append(f"{label}: URL identifier does not match canonicalId")
        if not patent.get("titleEn") or not patent.get("jurisdiction"):
            errors.append(f"{label}: missing required display field")
        inventors = patent.get("inventors")
        if not isinstance(inventors, list) or not inventors:
            errors.append(f"{label}: inventors must be a non-empty array")
        else:
            for inventor in inventors:
                person_id = str(inventor.get("personId") or "") if isinstance(inventor, dict) else ""
                if person_id not in person_ids:
                    errors.append(f"{label}: inventor personId {person_id!r} is missing from authors.json")
        sort_date = str(patent.get("sortDate") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", sort_date):
            errors.append(f"{label}: sortDate must use YYYY-MM-DD")
        if str(patent.get("year") or "") != sort_date[:4]:
            errors.append(f"{label}: year and sortDate disagree")
        publication_date = str(patent.get("publicationDate") or "")
        if publication_date and publication_date != sort_date:
            errors.append(f"{label}: exact publicationDate and sortDate disagree")

    records = metadata.get("records", {}) if isinstance(metadata, dict) else {}
    if not isinstance(records, dict):
        errors.append("data/patent_metadata.json records must be an object")
    else:
        for key in records:
            if normalize_identifier(key) not in canonical_ids:
                errors.append(f"Automatic metadata contains unknown patent {key}")
    for alias, canonical in alias_index.items():
        if canonical not in canonical_ids:
            errors.append(f"Alias {alias} resolves to unknown patent {canonical}")
    return errors


def main() -> None:
    errors = validate()
    if errors:
        raise SystemExit("\n".join(f"- {error}" for error in errors))
    patents = load(ROOT / "data/patents.json")
    families = load(ROOT / "data/patent_families.json")
    print(f"Validated {len(patents)} patent documents in {len(families)} families.")


if __name__ == "__main__":
    main()
