"""Command line entry point.

    python -m cfb build --out site           # fetch from ESPN and render
    python -m cfb fetch --out data/season.json
    python -m cfb build --season-file data/season.json --out site
    python -m cfb probe                      # dump endpoint samples
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

from .espn import EspnClient
from .http import Http
from .model import Season
from .render import write_site
from .report import build_report
from .rules import load_rules

log = logging.getLogger("cfb")


def _client(args) -> EspnClient:
    http = Http(
        cache_dir=args.cache_dir,
        cache_ttl=args.cache_ttl,
        pause=args.pause,
    )
    return EspnClient(http)


def _load_season(args) -> Season:
    if args.season_file and os.path.exists(args.season_file):
        log.info("reading season from %s", args.season_file)
        with open(args.season_file, encoding="utf-8") as fh:
            return Season.from_dict(json.load(fh))
    client = _client(args)
    season = client.load_season(year=args.season)
    log.info(
        "fetched %s teams, %s conferences, %s games in %s requests",
        len(season.teams), len(season.conferences), len(season.games), client.http.calls,
    )
    return season


def cmd_fetch(args) -> int:
    season = _load_season(args)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(season.to_dict(), fh, separators=(",", ":"))
    print(f"wrote {args.out} ({os.path.getsize(args.out) / 1024:.0f} KiB)")
    return 0


def cmd_build(args) -> int:
    started = time.time()
    season = _load_season(args)

    if args.save_season:
        os.makedirs(os.path.dirname(os.path.abspath(args.save_season)) or ".", exist_ok=True)
        with open(args.save_season, "w", encoding="utf-8") as fh:
            json.dump(season.to_dict(), fh, separators=(",", ":"))

    rulebook = load_rules(season.year, args.rules_dir)
    report = build_report(season, rulebook)
    written = write_site(report, args.out)

    unresolved = [c["name"] for c in report["conferences"] if c["unresolved"]]
    print(
        f"built {len(report['conferences'])} conferences "
        f"({len(season.games)} games, week {season.week}) "
        f"in {time.time() - started:.1f}s -> {args.out}"
    )
    for path in written:
        print(f"  {os.path.relpath(path)}")
    if unresolved:
        print("  ties awaiting a non-public step: " + ", ".join(unresolved))
    return 0


def cmd_probe(args) -> int:
    """Dump small samples of each endpoint so the parsing can be eyeballed."""
    client = _client(args)
    year, season_type, week = client.current_season_week()
    print(f"# current: season={year} type={season_type} week={week}")

    conferences, team_conf, team_div = client.fetch_conferences(year)
    print(f"# conferences: {len(conferences)}")
    for conf in sorted(conferences.values(), key=lambda c: c.name):
        divisions = f" divisions={list(conf.divisions)}" if conf.divisions else ""
        print(f"  {conf.id:>4}  {conf.name:<34} {len(conf.team_ids):>2} teams{divisions}")

    teams = client.fetch_teams()
    print(f"# teams feed: {len(teams)}; unmatched group members: "
          f"{sum(1 for t in team_conf if t not in teams)}")

    games = client.fetch_week(year, season_type, week)
    print(f"# week {week}: {len(games)} games")
    for game in games[:5]:
        home = teams.get(game.home_id)
        away = teams.get(game.away_id)
        print(f"  {game.date}  {away.name if away else game.away_id} "
              f"{game.away_score} @ {home.name if home else game.home_id} "
              f"{game.home_score}  [{game.state}] {game.short_detail}")

    rankings = client.fetch_rankings(year)
    print(f"# polls: {list(rankings)}")
    print(f"# http calls: {client.http.calls}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cfb", description=__doc__)
    parser.add_argument("--season", type=int, default=None, help="season year (default: whatever ESPN says is current)")
    parser.add_argument("--cache-dir", default=None, help="directory for the HTTP response cache")
    parser.add_argument("--cache-ttl", type=int, default=0, help="seconds a cached response stays fresh")
    parser.add_argument("--pause", type=float, default=0.0, help="seconds to wait between requests")
    parser.add_argument("--rules-dir", default=None)
    parser.add_argument("--season-file", default=None, help="read the season from this file instead of ESPN")
    parser.add_argument("-v", "--verbose", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="fetch, compute and render the site")
    build.add_argument("--out", default="site")
    build.add_argument("--save-season", default=None, help="also write the raw season JSON here")
    build.set_defaults(func=cmd_build)

    fetch = sub.add_parser("fetch", help="write the raw season JSON")
    fetch.add_argument("--out", default="data/season.json")
    fetch.set_defaults(func=cmd_fetch)

    probe = sub.add_parser("probe", help="print endpoint samples for validation")
    probe.set_defaults(func=cmd_probe)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return args.func(args)
    except Exception as exc:  # a failed run should not leave a half-written site
        log.error("%s", exc, exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    sys.exit(main())
