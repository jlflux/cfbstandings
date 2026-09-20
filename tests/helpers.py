"""Builders for synthetic seasons used by the tiebreaker tests."""

from __future__ import annotations

import datetime as dt
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cfb.model import Conference, Game, Season, Team  # noqa: E402
from cfb.standings import build_standings  # noqa: E402
from cfb.tiebreak import order_pool  # noqa: E402


def make_season(
    conferences: dict[str, list[str]],
    results: list[tuple],
    year: int = 2026,
    divisions: dict[str, dict[str, list[str]]] | None = None,
    rankings: dict[str, dict[str, int]] | None = None,
) -> Season:
    """conferences: {"SEC": ["Alabama", "Georgia", ...]}

    results: (home, away, home_score, away_score) - or (home, away) for a
    game that has not been played.
    """
    season = Season(year=year)
    next_id = [1]
    ids: dict[str, str] = {}

    for index, (conf_name, schools) in enumerate(conferences.items(), start=1):
        conf = Conference(id=str(index * 100), name=conf_name, short_name=conf_name, slug=conf_name.lower())
        for school in schools:
            team_id = str(next_id[0])
            next_id[0] += 1
            ids[school] = team_id
            division = None
            if divisions and conf_name in divisions:
                for div_name, members in divisions[conf_name].items():
                    if school in members:
                        division = div_name
            season.teams[team_id] = Team(
                id=team_id,
                school=school,
                display=school,
                abbrev=school[:4].upper(),
                conference_id=conf.id,
                conference_name=conf_name,
                division=division,
            )
            conf.team_ids.append(team_id)
        if divisions and conf_name in divisions:
            conf.divisions = {
                div: [ids[s] for s in members]
                for div, members in divisions[conf_name].items()
            }
        season.conferences[conf.id] = conf

    base = dt.datetime(year, 9, 5, tzinfo=dt.timezone.utc)
    for index, result in enumerate(results):
        played = len(result) == 4
        home, away = result[0], result[1]
        game = Game(
            id=f"g{index}",
            date=(base + dt.timedelta(days=7 * (index % 14))).strftime("%Y-%m-%dT%H:%M:%SZ"),
            season=year,
            season_type=2,
            week=(index % 14) + 1,
            home_id=ids[home],
            away_id=ids[away],
            home_score=result[2] if played else None,
            away_score=result[3] if played else None,
            state="post" if played else "pre",
            completed=played,
        )
        season.games.append(game)

    season.rankings = rankings or {}
    season.team_ids_by_school = ids  # type: ignore[attr-defined]
    return season


def order(season: Season, conf_name: str, rules: dict) -> tuple[list[list[str]], list]:
    conf = next(c for c in season.conferences.values() if c.name == conf_name)
    table = build_standings(season)
    return order_pool(season, table, conf.id, list(conf.team_ids), rules)


def names(season: Season, levels: list[list[str]]) -> list[list[str]]:
    return [[season.teams[t].school for t in level] for level in levels]


def flat(season: Season, levels: list[list[str]]) -> list[str]:
    return [season.teams[t].school for level in levels for t in level]


def load_rules(slug: str) -> dict:
    import json
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "rules", "2026", f"{slug}.json"
    )
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
