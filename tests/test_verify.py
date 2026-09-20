"""The cross-check against ESPN's own records."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from helpers import make_season  # noqa: E402

from cfb.standings import build_standings  # noqa: E402
from cfb.verify import cross_check  # noqa: E402


def season_with_espn_records(records_by_school):
    season = make_season(
        {"SEC": ["Ash", "Birch", "Cedar", "Dogwood"]},
        [
            ("Ash", "Birch", 21, 14),
            ("Ash", "Cedar", 28, 10),
            ("Ash", "Dogwood", 35, 7),
            ("Birch", "Cedar", 17, 14),
            ("Birch", "Dogwood", 24, 21),
            ("Cedar", "Dogwood", 20, 17),
        ],
    )
    ids = {t.school: t.id for t in season.teams.values()}
    last = {}
    for game in season.games:
        for team_id in (game.home_id, game.away_id):
            last[team_id] = game
    for school, summary in records_by_school.items():
        game = last[ids[school]]
        game.espn_records.setdefault(ids[school], {})["overall"] = summary
    return season


class CrossCheckTests(unittest.TestCase):
    def test_matching_records_report_no_problems(self):
        # Ash 3-0, Birch 2-1, Cedar 1-2, Dogwood 0-3
        season = season_with_espn_records(
            {"Ash": "3-0", "Birch": "2-1", "Cedar": "1-2", "Dogwood": "0-3"}
        )
        problems, checked = cross_check(season, build_standings(season))
        self.assertEqual(checked, 4)
        self.assertEqual(problems, [])

    def test_a_one_game_difference_is_tolerated(self):
        # ESPN attaches the record either side of the game, so one game either
        # way is not evidence of a problem.
        season = season_with_espn_records({"Ash": "2-0", "Birch": "2-0"})
        problems, _ = cross_check(season, build_standings(season))
        self.assertEqual(problems, [])

    def test_a_large_undercount_is_reported(self):
        # What a truncated game sweep looks like: ESPN has nine games, we have
        # three.
        season = season_with_espn_records({"Ash": "9-0"})
        problems, checked = cross_check(season, build_standings(season))
        self.assertEqual(checked, 1)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].team, "Ash")
        self.assertIn("game count", problems[0].detail)

    def test_a_wrong_win_loss_split_is_reported(self):
        season = season_with_espn_records({"Ash": "0-3"})
        problems, _ = cross_check(season, build_standings(season))
        self.assertEqual(len(problems), 1)
        self.assertIn("win/loss split", problems[0].detail)

    def test_unparseable_and_missing_records_are_skipped(self):
        season = season_with_espn_records({"Ash": "", "Birch": "n/a"})
        problems, checked = cross_check(season, build_standings(season))
        self.assertEqual((problems, checked), ([], 0))

    def test_non_fbs_opponents_are_not_checked(self):
        season = season_with_espn_records({"Ash": "3-0"})
        for team in season.teams.values():
            team.conference_id = None
        problems, checked = cross_check(season, build_standings(season))
        self.assertEqual((problems, checked), ([], 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
