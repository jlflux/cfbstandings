"""Core data model.

Everything downstream (standings, tiebreakers, rendering) works off these
plain dataclasses so the ESPN-specific parsing stays isolated in ``espn.py``.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Team:
    id: str
    slug: str = ""
    school: str = ""          # "Ohio State"
    mascot: str = ""          # "Buckeyes"
    display: str = ""         # "Ohio State Buckeyes"
    abbrev: str = ""
    conference_id: str | None = None
    conference_name: str = ""
    division: str | None = None
    logo: str = ""
    color: str = ""
    alt_color: str = ""

    @property
    def name(self) -> str:
        return self.school or self.display or self.abbrev or self.id


@dataclass
class Game:
    id: str
    date: str                 # ISO-8601 UTC, e.g. "2026-09-19T23:30Z"
    season: int = 0
    season_type: int = 2      # 1 pre, 2 regular, 3 post
    week: int = 0
    home_id: str = ""
    away_id: str = ""
    home_score: int | None = None
    away_score: int | None = None
    state: str = "pre"        # pre | in | post
    completed: bool = False
    neutral_site: bool = False
    status_detail: str = ""
    short_detail: str = ""
    venue: str = ""
    broadcast: str = ""
    espn_conference_game: bool | None = None
    notes: str = ""
    # ESPN's own record for each team as of this game, when the feed carries
    # it: {team_id: {"overall": "3-0", "vs. conf.": "1-0"}}. Used only to
    # cross-check the records computed here.
    espn_records: dict[str, dict[str, str]] = field(default_factory=dict)

    @property
    def kickoff(self) -> dt.datetime | None:
        try:
            return dt.datetime.fromisoformat(self.date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def opponent_of(self, team_id: str) -> str:
        return self.away_id if team_id == self.home_id else self.home_id

    def score_for(self, team_id: str) -> int | None:
        return self.home_score if team_id == self.home_id else self.away_score

    def score_against(self, team_id: str) -> int | None:
        return self.away_score if team_id == self.home_id else self.home_score

    def winner_id(self) -> str | None:
        """Winning team id, or None for a tie or an unfinished game."""
        if not self.completed or self.home_score is None or self.away_score is None:
            return None
        if self.home_score > self.away_score:
            return self.home_id
        if self.away_score > self.home_score:
            return self.away_id
        return None


@dataclass
class Conference:
    id: str
    name: str
    short_name: str = ""
    slug: str = ""
    team_ids: list[str] = field(default_factory=list)
    divisions: dict[str, list[str]] = field(default_factory=dict)
    is_fbs: bool = True
    logo: str = ""


@dataclass
class Season:
    """Everything one build needs: who plays where, and every game."""

    year: int
    season_type: int = 2
    week: int = 0
    fetched_at: str = ""
    teams: dict[str, Team] = field(default_factory=dict)
    conferences: dict[str, Conference] = field(default_factory=dict)
    games: list[Game] = field(default_factory=list)
    rankings: dict[str, dict[str, int]] = field(default_factory=dict)  # poll -> team_id -> rank

    # -- serialisation -------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "season_type": self.season_type,
            "week": self.week,
            "fetched_at": self.fetched_at,
            "teams": {k: asdict(v) for k, v in self.teams.items()},
            "conferences": {k: asdict(v) for k, v in self.conferences.items()},
            "games": [asdict(g) for g in self.games],
            "rankings": self.rankings,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Season":
        return cls(
            year=raw["year"],
            season_type=raw.get("season_type", 2),
            week=raw.get("week", 0),
            fetched_at=raw.get("fetched_at", ""),
            teams={k: Team(**v) for k, v in raw.get("teams", {}).items()},
            conferences={k: Conference(**v) for k, v in raw.get("conferences", {}).items()},
            games=[Game(**g) for g in raw.get("games", [])],
            rankings=raw.get("rankings", {}),
        )

    # -- helpers -------------------------------------------------------
    def conference_of(self, team_id: str) -> str | None:
        team = self.teams.get(team_id)
        return team.conference_id if team else None

    def is_conference_game(self, game: Game) -> bool:
        """A game counts toward the league standings only when both teams are
        in the same conference. ESPN's own flag is used as a fallback for
        games where we could not resolve a team."""
        home = self.conference_of(game.home_id)
        away = self.conference_of(game.away_id)
        if home is None or away is None:
            return bool(game.espn_conference_game)
        return home == away
