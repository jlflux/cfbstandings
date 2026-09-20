"""Cross-check the computed records against ESPN's own.

Each completed game in the scoreboard feed carries the record ESPN has for
the teams involved. Comparing that to the records computed here catches the
failure mode that matters most: silently missing games. It is a sanity check,
not a source of truth, so it tolerates the one-game ambiguity in whether
ESPN's figure is taken before or after the game it is attached to.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .model import Season
from .standings import TeamStanding

RECORD = re.compile(r"^(\d+)-(\d+)(?:-(\d+))?$")
TOLERANCE = 1


@dataclass
class Discrepancy:
    team: str
    computed: str
    espn: str
    detail: str

    def __str__(self) -> str:
        return f"{self.team}: computed {self.computed}, ESPN {self.espn} ({self.detail})"


def _parse(summary: str) -> tuple[int, int, int] | None:
    match = RECORD.match((summary or "").strip())
    if not match:
        return None
    wins, losses, ties = match.groups()
    return int(wins), int(losses), int(ties or 0)


def _latest_records(season: Season) -> dict[str, tuple[int, int, int]]:
    """Each team's most recent ESPN-reported overall record."""
    latest: dict[str, tuple[str, tuple[int, int, int]]] = {}
    for game in season.games:
        if not game.completed:
            continue
        for team_id, records in (game.espn_records or {}).items():
            parsed = _parse(records.get("overall", ""))
            if parsed is None:
                continue
            if team_id not in latest or game.date > latest[team_id][0]:
                latest[team_id] = (game.date, parsed)
    return {team_id: value for team_id, (_, value) in latest.items()}


def cross_check(
    season: Season, table: dict[str, TeamStanding]
) -> tuple[list[Discrepancy], int]:
    """Return (discrepancies, number of teams checked)."""
    espn = _latest_records(season)
    problems: list[Discrepancy] = []
    checked = 0

    for team_id, record in espn.items():
        team = season.teams.get(team_id)
        if team is None or not team.conference_id:
            continue          # only FBS teams are swept in full
        standing = table.get(team_id)
        if standing is None:
            continue
        checked += 1
        wins, losses, ties = record
        played = wins + losses + ties
        ours = standing.overall
        if abs(ours.games - played) > TOLERANCE:
            problems.append(
                Discrepancy(
                    team=team.name,
                    computed=f"{ours.label} ({ours.games} games)",
                    espn=f"{wins}-{losses} ({played} games)",
                    detail="game count differs by more than one",
                )
            )
        elif abs(ours.wins - wins) > TOLERANCE or abs(ours.losses - losses) > TOLERANCE:
            problems.append(
                Discrepancy(
                    team=team.name,
                    computed=ours.label,
                    espn=f"{wins}-{losses}",
                    detail="win/loss split differs by more than one",
                )
            )

    return problems, checked
