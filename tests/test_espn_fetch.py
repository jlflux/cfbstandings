"""Fetch strategy: the scoreboard's 25-event cap and how it is worked around.

Uses a stub transport, so no network is involved.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cfb.espn import SCOREBOARD_CAP, EspnClient  # noqa: E402


def event(event_id: str, home: str, away: str, week: int = 3) -> dict:
    return {
        "id": event_id,
        "date": "2026-09-19T23:30Z",
        "week": {"number": week},
        "competitions": [
            {
                "id": event_id,
                "date": "2026-09-19T23:30Z",
                "status": {"type": {"state": "post", "completed": True, "shortDetail": "Final"}},
                "competitors": [
                    {"homeAway": "home", "score": "21", "team": {"id": home}},
                    {"homeAway": "away", "score": "17", "team": {"id": away}},
                ],
            }
        ],
    }


class StubHttp:
    """Serves canned scoreboard payloads and records what was asked for."""

    def __init__(self, by_request):
        self.by_request = by_request
        self.requests = []
        self.calls = 0

    def get_json(self, url, params=None, no_cache=False):
        params = params or {}
        key = (params.get("groups"), params.get("week"), params.get("dates"))
        self.requests.append({"key": key, "no_cache": no_cache})
        self.calls += 1
        return {"events": self.by_request.get(key, [])}


class CapTests(unittest.TestCase):
    def test_an_uncapped_response_is_taken_as_complete(self):
        payload = {("8", 3, 2026): [event(str(i), "1", "2") for i in range(9)]}
        client = EspnClient(StubHttp(payload))
        games = client.fetch_group_week(2026, 2, 3, "8", ("20260914", "20260920"))
        self.assertEqual(len(games), 9)
        self.assertEqual(client.http.calls, 1, "no date split should be needed")

    def test_a_capped_response_is_re_read_day_by_day(self):
        week_events = [event(str(i), "1", "2") for i in range(SCOREBOARD_CAP)]
        payload = {("8", 3, 2026): week_events}
        # Each day carries a couple of games, including ones the capped week
        # response never showed.
        for index, day in enumerate(
            ["20260914", "20260915", "20260916", "20260917", "20260918", "20260919", "20260920"]
        ):
            # a date-scoped request carries no week parameter
            payload[("8", None, day)] = [
                event(f"day-{index}-a", "1", "2"),
                event(f"day-{index}-b", "3", "4"),
            ]
        client = EspnClient(StubHttp(payload))
        games = client.fetch_group_week(2026, 2, 3, "8", ("20260914", "20260920"))
        self.assertEqual(client.http.calls, 8, "one week call plus one per day")
        self.assertEqual(len(games), SCOREBOARD_CAP + 14)
        self.assertEqual(len({g.id for g in games}), len(games), "ids must be unique")

    def test_a_capped_response_without_a_known_span_is_returned_as_is(self):
        payload = {("8", 3, 2026): [event(str(i), "1", "2") for i in range(SCOREBOARD_CAP)]}
        client = EspnClient(StubHttp(payload))
        games = client.fetch_group_week(2026, 2, 3, "8", None)
        self.assertEqual(len(games), SCOREBOARD_CAP)
        self.assertEqual(client.http.calls, 1)


class SweepTests(unittest.TestCase):
    def _client(self):
        payload = {}
        for week in (1, 2, 3, 4, 5):
            for group in ("8", "5"):
                payload[(group, week, 2026)] = [
                    event(f"{group}-{week}-{i}", "1", "2", week=week) for i in range(3)
                ]
        client = EspnClient(StubHttp(payload))
        client.fetch_calendar = lambda year: {  # type: ignore[assignment]
            2: {w: ("20260901", "20260907") for w in range(1, 16)},
            3: {1: ("20261213", "20261220")},
        }
        return client

    def test_the_sweep_stops_two_weeks_past_the_current_one(self):
        client = self._client()
        games = client.fetch_season_games(2026, ["8", "5"], current_type=2, current_week=3)
        weeks = sorted({g.week for g in games})
        self.assertEqual(weeks, [1, 2, 3, 4, 5])
        asked = sorted({r["key"][1] for r in client.http.requests if r["key"][1]})
        self.assertEqual(asked, [1, 2, 3, 4, 5], "should not read week 6 onward")

    def test_only_the_week_in_play_bypasses_the_cache(self):
        client = self._client()
        client.fetch_season_games(2026, ["8", "5"], current_type=2, current_week=3)
        live = {r["key"][1] for r in client.http.requests if r["no_cache"]}
        self.assertEqual(live, {3})

    def test_games_from_two_conferences_are_deduplicated(self):
        shared = event("shared-1", "1", "2", week=3)
        payload = {("8", 3, 2026): [shared], ("5", 3, 2026): [shared]}
        client = EspnClient(StubHttp(payload))
        client.fetch_calendar = lambda year: {2: {3: ("20260914", "20260920")}}  # type: ignore
        games = client.fetch_season_games(2026, ["8", "5"], current_type=2, current_week=3)
        self.assertEqual(len(games), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
