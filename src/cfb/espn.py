"""ESPN ingest.

Two public endpoints do all the work:

* ``sports.core.api.espn.com`` group tree  -> which teams are in which
  conference (and division) for a given season. Conference membership moves
  every year, so it is always read from ESPN rather than hard-coded.
* ``site.api.espn.com`` scoreboard         -> every game, week by week.

Both are the same endpoints espn.com itself calls; no key is required.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Any, Iterable

from .http import FetchError, Http
from .model import Conference, Game, Season, Team

log = logging.getLogger(__name__)

CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/college-football"
SITE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"

FBS_GROUP = "80"   # NCAA Division I-A (FBS)
FCS_GROUP = "81"

# Regular season weeks to sweep. ESPN returns an empty event list for weeks
# that do not exist, so an over-estimate is harmless.
MAX_REGULAR_WEEKS = 17
MAX_POSTSEASON_WEEKS = 6

_REF_ID = re.compile(r"/(\d+)(?:\?|$)")


def _ref_id(ref: str) -> str | None:
    match = _REF_ID.search(ref.split("/teams/")[-1] if "/teams/" in ref else ref)
    return match.group(1) if match else None


def _strip_ref(ref: str) -> str:
    """ESPN core refs come back as http:// with embedded query strings."""
    return ref.replace("http://", "https://")


class EspnClient:
    def __init__(self, http: Http | None = None) -> None:
        self.http = http or Http()

    # -- season / week discovery --------------------------------------
    def current_scoreboard(self) -> dict[str, Any]:
        return self.http.get_json(f"{SITE}/scoreboard", {"limit": 1000, "groups": FBS_GROUP})

    def current_season_week(self) -> tuple[int, int, int]:
        """(year, season_type, week) as ESPN currently reports them."""
        payload = self.current_scoreboard()
        season = payload.get("season") or {}
        week = payload.get("week") or {}
        year = int(season.get("year") or dt.date.today().year)
        season_type = int(season.get("type") or 2)
        week_no = int(week.get("number") or 1)
        return year, season_type, week_no

    # -- conferences ---------------------------------------------------
    def fetch_conferences(self, year: int) -> tuple[dict[str, Conference], dict[str, str], dict[str, str]]:
        """Return (conferences, team_id -> conference_id, team_id -> division)."""
        conferences: dict[str, Conference] = {}
        team_conf: dict[str, str] = {}
        team_div: dict[str, str] = {}

        children = self.http.get_json(
            f"{CORE}/seasons/{year}/types/2/groups/{FBS_GROUP}/children",
            {"limit": 100},
        )
        refs = [item.get("$ref", "") for item in children.get("items", [])]
        if not refs:
            raise FetchError(f"no FBS conference groups returned for {year}")

        for ref in refs:
            group = self.http.get_json(_strip_ref(ref))
            conf_id = str(group.get("id"))
            conf = Conference(
                id=conf_id,
                name=group.get("name") or group.get("shortName") or f"Group {conf_id}",
                short_name=group.get("shortName") or group.get("abbreviation") or "",
                slug=group.get("slug") or _slugify(group.get("name", conf_id)),
                logo=_group_logo(group),
            )

            for team_id in self._group_team_ids(group):
                conf.team_ids.append(team_id)
                team_conf[team_id] = conf_id

            # Divisions (e.g. the Sun Belt's East/West) come through as
            # children of the conference group.
            for div_ref in _child_refs(group):
                division = self.http.get_json(_strip_ref(div_ref))
                div_name = division.get("name") or division.get("shortName") or ""
                div_teams = self._group_team_ids(division)
                if not div_teams:
                    continue
                conf.divisions[div_name] = div_teams
                for team_id in div_teams:
                    team_div[team_id] = div_name
                    if team_id not in team_conf:
                        team_conf[team_id] = conf_id
                        conf.team_ids.append(team_id)

            conferences[conf_id] = conf

        return conferences, team_conf, team_div

    def _group_team_ids(self, group: dict[str, Any]) -> list[str]:
        ref = (group.get("teams") or {}).get("$ref")
        if not ref:
            return []
        try:
            payload = self.http.get_json(_strip_ref(ref), {"limit": 200})
        except FetchError as exc:
            log.warning("team list failed for group %s: %s", group.get("id"), exc)
            return []
        ids: list[str] = []
        for item in payload.get("items", []):
            team_id = _ref_id(item.get("$ref", ""))
            if team_id:
                ids.append(team_id)
        return ids

    # -- teams ----------------------------------------------------------
    def fetch_teams(self) -> dict[str, Team]:
        payload = self.http.get_json(f"{SITE}/teams", {"limit": 1000})
        teams: dict[str, Team] = {}
        for sport in payload.get("sports", []):
            for league in sport.get("leagues", []):
                for entry in league.get("teams", []):
                    raw = entry.get("team") or {}
                    team = _parse_team(raw)
                    if team:
                        teams[team.id] = team
        if not teams:
            raise FetchError("ESPN returned no teams")
        return teams

    # -- games ------------------------------------------------------------
    def fetch_week(self, year: int, season_type: int, week: int) -> list[Game]:
        payload = self.http.get_json(
            f"{SITE}/scoreboard",
            {
                "dates": year,
                "seasontype": season_type,
                "week": week,
                "groups": FBS_GROUP,
                "limit": 1000,
            },
        )
        games = []
        for event in payload.get("events", []):
            game = _parse_event(event, year, season_type, week)
            if game:
                games.append(game)
        return games

    def fetch_season_games(
        self,
        year: int,
        through_type: int = 3,
        regular_weeks: int = MAX_REGULAR_WEEKS,
    ) -> list[Game]:
        games: dict[str, Game] = {}
        for week in range(1, regular_weeks + 1):
            try:
                week_games = self.fetch_week(year, 2, week)
            except FetchError as exc:
                log.warning("regular week %s failed: %s", week, exc)
                continue
            for game in week_games:
                games[game.id] = game
        if through_type >= 3:
            for week in range(1, MAX_POSTSEASON_WEEKS + 1):
                try:
                    week_games = self.fetch_week(year, 3, week)
                except FetchError as exc:
                    log.warning("postseason week %s failed: %s", week, exc)
                    continue
                for game in week_games:
                    games.setdefault(game.id, game)
        return sorted(games.values(), key=lambda g: (g.date, g.id))

    # -- rankings ----------------------------------------------------------
    def fetch_rankings(self, year: int, week: int | None = None) -> dict[str, dict[str, int]]:
        params: dict[str, Any] = {"season": year}
        if week:
            params["week"] = week
        try:
            payload = self.http.get_json(f"{SITE}/rankings", params)
        except FetchError as exc:
            log.warning("rankings unavailable: %s", exc)
            return {}
        polls: dict[str, dict[str, int]] = {}
        for poll in payload.get("rankings", []):
            name = poll.get("shortName") or poll.get("name") or ""
            if not name:
                continue
            table: dict[str, int] = {}
            for rank in poll.get("ranks", []):
                team_id = str(((rank.get("team") or {}).get("id")) or "")
                current = rank.get("current")
                if team_id and current:
                    table[team_id] = int(current)
            if table:
                polls[name] = table
        return polls

    # -- orchestration -------------------------------------------------------
    def load_season(self, year: int | None = None, include_postseason: bool = True) -> Season:
        detected_year, season_type, week = self.current_season_week()
        year = year or detected_year

        conferences, team_conf, team_div = self.fetch_conferences(year)
        teams = self.fetch_teams()

        for team_id, conf_id in team_conf.items():
            team = teams.get(team_id)
            if team is None:
                # A team ESPN lists in a group but not in the teams feed:
                # keep a stub so games involving it still classify correctly.
                team = Team(id=team_id, school=f"Team {team_id}", display=f"Team {team_id}")
                teams[team_id] = team
            team.conference_id = conf_id
            team.conference_name = conferences[conf_id].name
            team.division = team_div.get(team_id)

        games = self.fetch_season_games(year, through_type=3 if include_postseason else 2)
        rankings = self.fetch_rankings(year)

        return Season(
            year=year,
            season_type=season_type,
            week=week,
            fetched_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            teams=teams,
            conferences=conferences,
            games=games,
            rankings=rankings,
        )


# -- parsing helpers -------------------------------------------------------
def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")


def _group_logo(group: dict[str, Any]) -> str:
    logos = group.get("logos") or []
    if isinstance(logos, list) and logos:
        return logos[0].get("href", "")
    return ""


def _child_refs(group: dict[str, Any]) -> list[str]:
    children = group.get("children") or {}
    if isinstance(children, dict):
        items = children.get("items") or []
    elif isinstance(children, list):
        items = children
    else:
        items = []
    return [item.get("$ref", "") for item in items if item.get("$ref")]


def _parse_team(raw: dict[str, Any]) -> Team | None:
    team_id = str(raw.get("id") or "")
    if not team_id:
        return None
    logos = raw.get("logos") or []
    logo = logos[0].get("href", "") if logos else raw.get("logo", "")
    return Team(
        id=team_id,
        slug=raw.get("slug", ""),
        school=raw.get("location") or raw.get("displayName", ""),
        mascot=raw.get("name", ""),
        display=raw.get("displayName", ""),
        abbrev=raw.get("abbreviation", ""),
        logo=logo,
        color=raw.get("color", "") or "",
        alt_color=raw.get("alternateColor", "") or "",
    )


def _parse_event(event: dict[str, Any], year: int, season_type: int, week: int) -> Game | None:
    competitions = event.get("competitions") or []
    if not competitions:
        return None
    comp = competitions[0]
    competitors = comp.get("competitors") or []
    if len(competitors) != 2:
        return None

    home = next((c for c in competitors if c.get("homeAway") == "home"), None)
    away = next((c for c in competitors if c.get("homeAway") == "away"), None)
    if home is None or away is None:
        home, away = competitors[0], competitors[1]

    status = (comp.get("status") or event.get("status") or {})
    state = ((status.get("type") or {}).get("state")) or "pre"
    completed = bool((status.get("type") or {}).get("completed"))

    venue = (comp.get("venue") or {}).get("fullName", "")
    broadcasts = comp.get("broadcasts") or []
    broadcast = ""
    if broadcasts:
        names = broadcasts[0].get("names") or []
        broadcast = names[0] if names else ""

    notes = ""
    for note in comp.get("notes") or []:
        if note.get("headline"):
            notes = note["headline"]
            break

    return Game(
        id=str(event.get("id") or comp.get("id") or ""),
        date=_normalise_date(comp.get("date") or event.get("date") or ""),
        season=year,
        season_type=season_type,
        week=int((event.get("week") or {}).get("number") or week),
        home_id=str((home.get("team") or {}).get("id") or ""),
        away_id=str((away.get("team") or {}).get("id") or ""),
        home_score=_score(home, completed, state),
        away_score=_score(away, completed, state),
        state=state,
        completed=completed,
        neutral_site=bool(comp.get("neutralSite")),
        status_detail=(status.get("type") or {}).get("detail", "") or "",
        short_detail=(status.get("type") or {}).get("shortDetail", "") or "",
        venue=venue,
        broadcast=broadcast,
        espn_conference_game=comp.get("conferenceCompetition"),
        notes=notes,
    )


def _score(competitor: dict[str, Any], completed: bool, state: str) -> int | None:
    if state == "pre" and not completed:
        return None
    raw = competitor.get("score")
    if isinstance(raw, dict):
        raw = raw.get("value", raw.get("displayValue"))
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _normalise_date(value: str) -> str:
    if not value:
        return ""
    return value.replace("+0000", "Z")


def iter_fbs_conferences(season: Season) -> Iterable[Conference]:
    for conf in season.conferences.values():
        if conf.team_ids:
            yield conf
