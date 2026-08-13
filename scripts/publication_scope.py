"""Shared publication-scope rules used by offline builders and updaters."""
from __future__ import annotations

from typing import Any


def is_research_publication(publication: dict[str, Any]) -> bool:
    """Return whether a record belongs in publication research analytics."""
    analytics = publication.get("analytics") or {}
    return analytics.get("excludeFromResearchAnalytics") is not True


def is_automation_protected(publication: dict[str, Any]) -> bool:
    """Return whether automatic enrichment must preserve a record unchanged."""
    protection = publication.get("automationProtection") or {}
    return (
        protection.get("protected") is True
        or str(publication.get("metadataSource") or "").lower() == "manual_verified"
    )
