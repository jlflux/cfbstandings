"""Loading the per-conference tiebreaker rule files."""

from __future__ import annotations

import json
import logging
import os

log = logging.getLogger(__name__)

DEFAULT_RULES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "rules",
)

# Used when a conference has no rule file at all: the near-universal opening
# steps, stopping honestly rather than inventing later ones.
GENERIC = {
    "conference": "",
    "slug": "generic",
    "structure": "single_table",
    "confidence": "none",
    "verified_on": "",
    "sources": [],
    "notes": (
        "No published procedure is on file for this conference, so only the steps "
        "common to every FBS league are applied."
    ),
    "two_team": [
        {"step": "head_to_head", "label": "Head-to-head competition"},
        {"step": "common_opponents", "label": "Win pct vs all common conference opponents"},
        {"step": "draw", "label": "Conference procedure not on file"},
    ],
}


class RuleBook:
    def __init__(self, rules: list[dict], season: int) -> None:
        self.season = season
        self.by_slug: dict[str, dict] = {}
        self.by_group: dict[str, dict] = {}
        self.by_name: dict[str, dict] = {}
        for entry in rules:
            self.by_slug[entry["slug"]] = entry
            group = str(entry.get("espn_group_id") or "")
            if group:
                self.by_group[group] = entry
            name = (entry.get("conference") or "").lower()
            if name:
                self.by_name[name] = entry

    def for_conference(self, conference_id: str, conference_name: str = "") -> dict:
        entry = self.by_group.get(str(conference_id))
        if entry:
            return entry
        entry = self.by_name.get((conference_name or "").lower())
        if entry:
            return entry
        log.warning(
            "no tiebreaker rules for conference %s (%s); using the generic fallback",
            conference_id,
            conference_name,
        )
        fallback = dict(GENERIC)
        fallback["conference"] = conference_name
        fallback["multi_team"] = fallback["two_team"]
        return fallback

    def all(self) -> list[dict]:
        return sorted(self.by_slug.values(), key=lambda r: r.get("conference", ""))


def load_rules(season: int, rules_dir: str | None = None) -> RuleBook:
    base = rules_dir or DEFAULT_RULES_DIR
    directory = os.path.join(base, str(season))
    if not os.path.isdir(directory):
        # Fall back to the most recent season we have rules for.
        available = [d for d in os.listdir(base) if d.isdigit()] if os.path.isdir(base) else []
        if not available:
            log.warning("no rule files under %s", base)
            return RuleBook([], season)
        newest = max(available, key=int)
        log.warning("no rules for %s; falling back to %s", season, newest)
        directory = os.path.join(base, newest)

    entries = []
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(directory, filename), encoding="utf-8") as fh:
            entries.append(json.load(fh))
    return RuleBook(entries, season)
