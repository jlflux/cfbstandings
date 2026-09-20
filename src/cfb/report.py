"""Turn a Season into the fully-resolved structure the site renders."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, asdict
from typing import Any

from .model import Conference, Game, Season
from .rules import RuleBook
from .standings import TeamStanding, build_standings
from .tiebreak import TiebreakNote, order_pool


@dataclass
class Row:
    team_id: str
    name: str
    display: str
    abbrev: str
    logo: str
    color: str
    position: int
    tied_with: list[str] = field(default_factory=list)
    conf_record: str = "0-0"
    conf_pct: float = 0.0
    conf_pf: int = 0
    conf_pa: int = 0
    overall_record: str = "0-0"
    overall_pct: float = 0.0
    division: str | None = None
    streak: str = ""
    rank: int | None = None
    last_game: dict[str, Any] | None = None
    next_game: dict[str, Any] | None = None
    tiebreak_note: str = ""
    berth: str = ""


@dataclass
class Block:
    """One standings table: a whole conference, or one division of one."""

    title: str
    rows: list[Row] = field(default_factory=list)


@dataclass
class ConferenceReport:
    id: str
    name: str
    short_name: str
    slug: str
    logo: str
    structure: str
    confidence: str
    verified_on: str
    sources: list[str]
    rules_notes: str
    blocks: list[Block] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)
    championship: dict[str, Any] = field(default_factory=dict)
    unresolved: bool = False


def _game_brief(season: Season, game: Game, team_id: str) -> dict[str, Any]:
    opponent_id = game.opponent_of(team_id)
    opponent = season.teams.get(opponent_id)
    home = game.home_id == team_id
    return {
        "id": game.id,
        "date": game.date,
        "week": game.week,
        "opponent_id": opponent_id,
        "opponent": opponent.name if opponent else "TBD",
        "opponent_logo": opponent.logo if opponent else "",
        "home": home,
        "neutral": game.neutral_site,
        "score_for": game.score_for(team_id),
        "score_against": game.score_against(team_id),
        "state": game.state,
        "completed": game.completed,
        "status": game.short_detail or game.status_detail,
        "broadcast": game.broadcast,
        "result": (
            None if not game.completed
            else "W" if game.winner_id() == team_id
            else "T" if game.winner_id() is None
            else "L"
        ),
    }


def _last_and_next(season: Season, standing: TeamStanding) -> tuple[dict | None, dict | None]:
    played = [g for g in standing.all_games if g.completed]
    upcoming = [g for g in standing.all_games if not g.completed]
    played.sort(key=lambda g: g.date)
    upcoming.sort(key=lambda g: g.date)
    last = _game_brief(season, played[-1], standing.team_id) if played else None
    nxt = _game_brief(season, upcoming[0], standing.team_id) if upcoming else None
    return last, nxt


# Display preference: the committee's rankings once they exist, else the AP.
# ESPN labels these inconsistently across seasons, so each is matched loosely.
RANK_POLLS = (
    "cfp",
    "playoff",
    "ap top 25",
    "ap poll",
)


def _rank_of(season: Season, team_id: str) -> int | None:
    for poll in RANK_POLLS:
        for name, table in season.rankings.items():
            if poll in name.lower() and team_id in table:
                return table[team_id]
    return None


def _note_dict(season: Season, note: TiebreakNote) -> dict[str, Any]:
    def name(team_id: str) -> str:
        team = season.teams.get(team_id)
        return team.name if team else team_id

    return {
        "tied": [name(t) for t in note.tied],
        "tied_ids": note.tied,
        "at_record": note.at_record,
        "step": note.step,
        "step_label": note.step_label,
        "summary": note.summary,
        "details": {name(k): v for k, v in note.details.items()},
        "resolved": note.resolved,
        "outcome": [[name(t) for t in level] for level in note.outcome],
    }


def _build_rows(
    season: Season,
    table: dict[str, TeamStanding],
    levels: list[list[str]],
) -> list[Row]:
    rows: list[Row] = []
    position = 0
    for level in levels:
        position += 1
        for team_id in level:
            standing = table[team_id]
            team = season.teams.get(team_id)
            last, nxt = _last_and_next(season, standing)
            rows.append(
                Row(
                    team_id=team_id,
                    name=team.name if team else team_id,
                    display=team.display if team else team_id,
                    abbrev=team.abbrev if team else "",
                    logo=team.logo if team else "",
                    color=team.color if team else "",
                    position=position,
                    tied_with=(
                        [t for t in level if t != team_id]
                        if standing.conference.games else []
                    ),
                    conf_record=standing.conference.label,
                    conf_pct=round(standing.conference.pct, 4),
                    conf_pf=standing.conference.points_for,
                    conf_pa=standing.conference.points_against,
                    overall_record=standing.overall.label,
                    overall_pct=round(standing.overall.pct, 4),
                    division=team.division if team else None,
                    streak=standing.streak,
                    rank=_rank_of(season, team_id),
                    last_game=last,
                    next_game=nxt,
                )
            )
        position += len(level) - 1
    return rows


def build_conference_report(
    season: Season,
    table: dict[str, TeamStanding],
    conference: Conference,
    rules: dict,
) -> ConferenceReport:
    pool = [t for t in conference.team_ids if t in table]
    structure = rules.get("structure", "single_table")
    notes: list[TiebreakNote] = []
    blocks: list[Block] = []
    champ: dict[str, Any] = {}

    if structure == "divisions" and conference.divisions:
        division_winners: list[tuple[str, str, bool]] = []
        for div_name, members in conference.divisions.items():
            members = [t for t in members if t in table]
            if not members:
                continue
            levels, _ = order_pool(
                season, table, conference.id, members, rules,
                scope="division", notes=notes, placement_pool=members,
            )
            rows = _build_rows(season, table, levels)
            blocks.append(Block(title=div_name, rows=rows))
            top = levels[0] if levels else []
            division_winners.append((div_name, top[0] if top else "", len(top) > 1))
        champ = {
            "format": "division champions",
            "teams": [
                {
                    "division": div,
                    "team_id": team_id,
                    "team": (season.teams.get(team_id).name if season.teams.get(team_id) else ""),
                    "contested": contested,
                }
                for div, team_id, contested in division_winners
            ],
        }
        for block in blocks:
            for row in block.rows:
                if row.position == 1:
                    row.berth = "Division leader"
    elif structure == "no_championship":
        levels = [[t] for t in sorted(
            pool, key=lambda t: (-table[t].overall.pct, -table[t].overall.wins)
        )]
        blocks.append(Block(title=conference.name, rows=_build_rows(season, table, levels)))
    else:
        levels, _ = order_pool(season, table, conference.id, pool, rules, notes=notes)
        rows = _build_rows(season, table, levels)
        blocks.append(Block(title=conference.name, rows=rows))
        started = any(table[t].conference.games for t in pool)
        participants: list[str] = []
        contested = False
        for level in levels:
            if len(participants) >= 2:
                break
            if len(participants) + len(level) > 2:
                contested = True
                participants.extend(level[: 2 - len(participants)])
                break
            participants.extend(level)
        if not started:
            participants = []
        champ = {
            "format": "top two by conference win pct",
            "contested": contested,
            "teams": [
                {
                    "team_id": t,
                    "team": (season.teams.get(t).name if season.teams.get(t) else t),
                    "seed": i + 1,
                }
                for i, t in enumerate(participants)
            ],
        }
        for row in rows:
            if row.team_id in participants:
                row.berth = "Championship game" if not contested else "In contention"

    unresolved = any(not n.resolved for n in notes)
    return ConferenceReport(
        id=conference.id,
        name=conference.name,
        short_name=conference.short_name or conference.name,
        slug=rules.get("slug", conference.slug or conference.id),
        logo=conference.logo,
        structure=structure,
        confidence=rules.get("confidence", "none"),
        verified_on=rules.get("verified_on", ""),
        sources=rules.get("sources", []),
        rules_notes=rules.get("notes", ""),
        blocks=blocks,
        notes=[_note_dict(season, n) for n in notes],
        championship=champ,
        unresolved=unresolved,
    )


CONFERENCE_ORDER = ["1", "5", "4", "8", "151", "12", "15", "17", "9", "37", "18"]


def build_report(season: Season, rulebook: RuleBook) -> dict[str, Any]:
    table = build_standings(season)
    reports: list[ConferenceReport] = []
    for conference in season.conferences.values():
        if not conference.team_ids:
            continue
        rules = rulebook.for_conference(conference.id, conference.name)
        reports.append(build_conference_report(season, table, conference, rules))

    def sort_key(report: ConferenceReport):
        try:
            return (0, CONFERENCE_ORDER.index(report.id))
        except ValueError:
            return (1, report.name)

    reports.sort(key=sort_key)

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": season.year,
        "season_type": season.season_type,
        "week": season.week,
        "data_fetched_at": season.fetched_at,
        "conferences": [asdict(r) for r in reports],
        "scoreboard": build_scoreboard(season),
        "rankings": season.rankings,
    }


def build_scoreboard(season: Season, weeks: int = 2) -> list[dict[str, Any]]:
    """Recent and in-progress games, newest week first."""
    by_week: dict[tuple[int, int], list[Game]] = {}
    for game in season.games:
        by_week.setdefault((game.season_type, game.week), []).append(game)

    current = (season.season_type, season.week)
    keys = sorted(by_week, reverse=True)
    if current in keys:
        keys.remove(current)
        keys.insert(0, current)

    out = []
    for key in keys[:weeks]:
        season_type, week = key
        games = sorted(by_week[key], key=lambda g: (g.date, g.id))
        entries = []
        for game in games:
            home = season.teams.get(game.home_id)
            away = season.teams.get(game.away_id)
            entries.append(
                {
                    "id": game.id,
                    "date": game.date,
                    "state": game.state,
                    "completed": game.completed,
                    "status": game.short_detail or game.status_detail,
                    "neutral": game.neutral_site,
                    "conference_game": season.is_conference_game(game),
                    "conference": (home.conference_name if home and season.is_conference_game(game) else ""),
                    "home": {
                        "id": game.home_id,
                        "name": home.name if home else "TBD",
                        "logo": home.logo if home else "",
                        "score": game.home_score,
                        "rank": _rank_of(season, game.home_id),
                    },
                    "away": {
                        "id": game.away_id,
                        "name": away.name if away else "TBD",
                        "logo": away.logo if away else "",
                        "score": game.away_score,
                        "rank": _rank_of(season, game.away_id),
                    },
                    "broadcast": game.broadcast,
                    "venue": game.venue,
                }
            )
        out.append({"season_type": season_type, "week": week, "games": entries})
    return out
