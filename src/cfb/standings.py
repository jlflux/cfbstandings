"""Win/loss bookkeeping for a season."""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import Game, Season


@dataclass
class Record:
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: int = 0
    points_against: int = 0

    @property
    def games(self) -> int:
        return self.wins + self.losses + self.ties

    @property
    def pct(self) -> float:
        if self.games == 0:
            return 0.0
        return (self.wins + 0.5 * self.ties) / self.games

    @property
    def label(self) -> str:
        if self.ties:
            return f"{self.wins}-{self.losses}-{self.ties}"
        return f"{self.wins}-{self.losses}"

    @property
    def margin(self) -> int:
        return self.points_for - self.points_against

    def add(self, scored: int, allowed: int) -> None:
        if scored > allowed:
            self.wins += 1
        elif scored < allowed:
            self.losses += 1
        else:
            self.ties += 1
        self.points_for += scored
        self.points_against += allowed


@dataclass
class TeamStanding:
    team_id: str
    conference: Record = field(default_factory=Record)
    overall: Record = field(default_factory=Record)
    division: Record = field(default_factory=Record)
    conference_games: list[Game] = field(default_factory=list)
    all_games: list[Game] = field(default_factory=list)
    streak: str = ""
    position: int = 0
    tiebreak_note: str = ""
    clinched: str = ""

    @property
    def pct(self) -> float:
        return self.conference.pct


def _played(game: Game) -> bool:
    return game.completed and game.home_score is not None and game.away_score is not None


def build_standings(season: Season) -> dict[str, TeamStanding]:
    """Conference and overall records for every team ESPN gave us."""
    table: dict[str, TeamStanding] = {
        team_id: TeamStanding(team_id=team_id) for team_id in season.teams
    }

    for game in sorted(season.games, key=lambda g: (g.date, g.id)):
        for team_id in (game.home_id, game.away_id):
            if team_id and team_id not in table:
                table[team_id] = TeamStanding(team_id=team_id)

        is_conf = season.is_conference_game(game)
        for team_id in (game.home_id, game.away_id):
            if not team_id:
                continue
            standing = table[team_id]
            standing.all_games.append(game)
            if is_conf and game.season_type == 2:
                standing.conference_games.append(game)
            if not _played(game):
                continue
            scored = game.score_for(team_id)
            allowed = game.score_against(team_id)
            if scored is None or allowed is None:
                continue
            standing.overall.add(scored, allowed)
            if is_conf and game.season_type == 2:
                standing.conference.add(scored, allowed)
                opponent = game.opponent_of(team_id)
                team = season.teams.get(team_id)
                other = season.teams.get(opponent)
                if team and other and team.division and team.division == other.division:
                    standing.division.add(scored, allowed)

    for standing in table.values():
        standing.streak = _streak(standing)

    return table


def _streak(standing: TeamStanding) -> str:
    played = [g for g in standing.all_games if _played(g)]
    if not played:
        return ""
    played.sort(key=lambda g: g.date)
    last_result = None
    count = 0
    for game in reversed(played):
        winner = game.winner_id()
        if winner is None:
            result = "T"
        else:
            result = "W" if winner == standing.team_id else "L"
        if last_result is None:
            last_result = result
            count = 1
        elif result == last_result:
            count += 1
        else:
            break
    return f"{last_result}{count}"


def placement_groups(
    team_ids: list[str], table: dict[str, TeamStanding]
) -> list[list[str]]:
    """Conference teams bucketed by conference win pct, best first.

    Conferences express several tiebreakers as "record against the
    highest-placed opponent, proceeding through the standings". Teams sharing
    a win percentage occupy the same place for that purpose.

    A team that has not yet played a conference game has no percentage to
    share, so it is kept apart from the 0-for-everything teams rather than
    being reported as tied with them.
    """
    buckets: dict[tuple[float, int], list[str]] = {}
    for team_id in team_ids:
        standing = table.get(team_id)
        pct = standing.conference.pct if standing else 0.0
        unplayed = 1 if (standing is None or standing.conference.games == 0) else 0
        buckets.setdefault((round(pct, 6), unplayed), []).append(team_id)
    return [buckets[key] for key in sorted(buckets, reverse=True)]
