"""Parsing of ESPN payload shapes.

The payload samples here are trimmed copies of real responses, so the parsing
can be regression-tested without network access.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cfb.espn import _child_refs, _parse_event, _parse_team, _ref_id, _score  # noqa: E402

REF = (
    "http://sports.core.api.espn.com/v2/sports/football/leagues/college-football"
    "/seasons/2026/types/2/groups/8/teams/2005?lang=en&region=us"
)


class RefTests(unittest.TestCase):
    def test_team_id_is_the_last_numeric_segment(self):
        self.assertEqual(_ref_id(REF), "2005")

    def test_ref_without_a_query_string(self):
        self.assertEqual(_ref_id(REF.split("?")[0]), "2005")

    def test_group_ref(self):
        self.assertEqual(_ref_id("http://x/groups/37?lang=en"), "37")

    def test_non_numeric_ref_is_ignored(self):
        self.assertIsNone(_ref_id("http://x/groups/standings?lang=en"))

    def test_child_refs_handles_both_shapes(self):
        as_dict = {"children": {"items": [{"$ref": "a"}, {"$ref": "b"}]}}
        as_list = {"children": [{"$ref": "a"}]}
        self.assertEqual(_child_refs(as_dict), ["a", "b"])
        self.assertEqual(_child_refs(as_list), ["a"])
        self.assertEqual(_child_refs({}), [])


class EventTests(unittest.TestCase):
    EVENT = {
        "id": "401752000",
        "date": "2026-09-19T23:30Z",
        "week": {"number": 3},
        "competitions": [
            {
                "id": "401752000",
                "date": "2026-09-19T23:30Z",
                "neutralSite": False,
                "conferenceCompetition": True,
                "venue": {"fullName": "Vaught-Hemingway Stadium"},
                "broadcasts": [{"names": ["ABC"]}],
                "status": {"type": {"state": "post", "completed": True,
                                    "detail": "Final", "shortDetail": "Final"}},
                "competitors": [
                    {"homeAway": "home", "score": "32", "team": {"id": "145"}},
                    {"homeAway": "away", "score": "24", "team": {"id": "99"}},
                ],
            }
        ],
    }

    def test_completed_game(self):
        game = _parse_event(self.EVENT, 2026, 2, 3)
        self.assertEqual((game.home_id, game.home_score), ("145", 32))
        self.assertEqual((game.away_id, game.away_score), ("99", 24))
        self.assertTrue(game.completed)
        self.assertEqual(game.winner_id(), "145")
        self.assertEqual(game.broadcast, "ABC")
        self.assertEqual(game.week, 3)
        self.assertTrue(game.espn_conference_game)

    def test_scheduled_game_has_no_score(self):
        event = {
            **self.EVENT,
            "competitions": [
                {
                    **self.EVENT["competitions"][0],
                    "status": {"type": {"state": "pre", "completed": False,
                                        "shortDetail": "Sat 3:30 PM"}},
                    "competitors": [
                        {"homeAway": "home", "score": "0", "team": {"id": "145"}},
                        {"homeAway": "away", "score": "0", "team": {"id": "99"}},
                    ],
                }
            ],
        }
        game = _parse_event(event, 2026, 2, 3)
        self.assertIsNone(game.home_score)
        self.assertIsNone(game.away_score)
        self.assertFalse(game.completed)
        self.assertIsNone(game.winner_id())

    def test_score_accepts_the_object_form(self):
        self.assertEqual(_score({"score": {"value": 31.0}}, True, "post"), 31)
        self.assertEqual(_score({"score": "17"}, True, "post"), 17)
        self.assertIsNone(_score({"score": None}, True, "post"))

    def test_event_without_two_competitors_is_skipped(self):
        self.assertIsNone(_parse_event({"competitions": [{"competitors": []}]}, 2026, 2, 3))
        self.assertIsNone(_parse_event({}, 2026, 2, 3))


class TeamTests(unittest.TestCase):
    def test_team_fields(self):
        team = _parse_team({
            "id": "2005",
            "slug": "air-force-falcons",
            "location": "Air Force",
            "name": "Falcons",
            "displayName": "Air Force Falcons",
            "abbreviation": "AF",
            "color": "004a7b",
            "logos": [{"href": "https://a.espncdn.com/logo.png"}],
        })
        self.assertEqual(team.id, "2005")
        self.assertEqual(team.school, "Air Force")
        self.assertEqual(team.name, "Air Force")
        self.assertEqual(team.logo, "https://a.espncdn.com/logo.png")

    def test_team_without_an_id_is_skipped(self):
        self.assertIsNone(_parse_team({"displayName": "Nobody"}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
