"""Build a synthetic but realistically shaped season.

Local network egress cannot reach ESPN, so this stands in for a real feed
when exercising the report and render paths end to end.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cfb.model import Conference, Game, Season, Team  # noqa: E402

LAYOUT = {
    "1": ("Atlantic Coast Conference", "ACC", 17, None),
    "5": ("Big Ten Conference", "Big Ten", 18, None),
    "4": ("Big 12 Conference", "Big 12", 16, None),
    "8": ("Southeastern Conference", "SEC", 16, None),
    "151": ("American Conference", "American", 14, None),
    "12": ("Conference USA", "CUSA", 12, None),
    "15": ("Mid-American Conference", "MAC", 12, None),
    "17": ("Mountain West Conference", "MW", 12, None),
    "9": ("Pac-12 Conference", "Pac-12", 8, None),
    "37": ("Sun Belt Conference", "Sun Belt", 14, ("East", "West")),
    "18": ("FBS Independents", "Independents", 4, None),
}


def build(seed: int = 7, through_week: int = 4, year: int = 2026) -> Season:
    rng = random.Random(seed)
    season = Season(year=year, season_type=2, week=through_week)
    next_id = 1
    kickoff = dt.datetime(year, 9, 5, 19, 0, tzinfo=dt.timezone.utc)

    for conf_id, (name, short, size, divisions) in LAYOUT.items():
        conf = Conference(id=conf_id, name=name, short_name=short, slug=short.lower().replace(" ", "-"))
        members = []
        for index in range(size):
            team_id = str(next_id)
            next_id += 1
            school = f"{short} {index + 1:02d}"
            division = divisions[index % 2] if divisions else None
            season.teams[team_id] = Team(
                id=team_id,
                slug=f"{short.lower()}-{index}",
                school=school,
                mascot="Team",
                display=school,
                abbrev=f"{short[:2].upper()}{index:02d}",
                conference_id=conf_id,
                conference_name=name,
                division=division,
            )
            conf.team_ids.append(team_id)
            members.append(team_id)
        if divisions:
            conf.divisions = {
                div: [t for i, t in enumerate(members) if divisions[i % 2] == div]
                for div in divisions
            }
        season.conferences[conf_id] = conf

        if conf_id == "18":   # independents play nobody in-conference
            continue

        # Round-robin-ish conference slate, played through `through_week`.
        pairs = [(a, b) for i, a in enumerate(members) for b in members[i + 1:]]
        rng.shuffle(pairs)
        weekly = max(1, len(members) // 2)
        for index, (home, away) in enumerate(pairs[: weekly * 9]):
            week = index // weekly + 1
            played = week <= through_week
            home_pts = rng.choice([7, 10, 13, 17, 20, 21, 24, 27, 28, 31, 35, 38, 42, 49, 56])
            away_pts = rng.choice([0, 3, 7, 10, 13, 14, 17, 20, 21, 24, 27, 31, 34])
            if home_pts == away_pts:
                home_pts += 3
            season.games.append(
                Game(
                    id=f"{conf_id}-{index}",
                    date=(kickoff + dt.timedelta(days=7 * (week - 1))).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    season=year,
                    season_type=2,
                    week=week,
                    home_id=home,
                    away_id=away,
                    home_score=home_pts if played else None,
                    away_score=away_pts if played else None,
                    state="post" if played else "pre",
                    completed=played,
                    short_detail="Final" if played else "Sat 7:00 PM ET",
                    broadcast=rng.choice(["ESPN", "FOX", "CBS", "ABC", ""]),
                    venue="Stadium",
                )
            )

    # A handful of non-conference games so overall records differ.
    ids = list(season.teams)
    for index in range(240):
        home, away = rng.sample(ids, 2)
        if season.teams[home].conference_id == season.teams[away].conference_id:
            continue
        week = index % 4 + 1
        season.games.append(
            Game(
                id=f"nc-{index}",
                date=(kickoff + dt.timedelta(days=7 * (week - 1), hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                season=year,
                season_type=2,
                week=week,
                home_id=home,
                away_id=away,
                home_score=rng.choice([14, 21, 28, 35, 42]),
                away_score=rng.choice([3, 7, 10, 17, 24]),
                state="post",
                completed=True,
                short_detail="Final",
            )
        )

    top = rng.sample(ids, 25)
    season.rankings = {"AP Top 25": {t: i + 1 for i, t in enumerate(top)}}
    season.fetched_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return season


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/season.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    season = build()
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(season.to_dict(), fh, separators=(",", ":"))
    print(f"wrote {out}: {len(season.teams)} teams, {len(season.games)} games")
