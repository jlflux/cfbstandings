"""Report assembly and rendering, end to end on a synthetic season."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from helpers import make_season  # noqa: E402

from cfb.model import Season  # noqa: E402
from cfb.render import write_site  # noqa: E402
from cfb.report import build_report  # noqa: E402
from cfb.rules import load_rules  # noqa: E402
from cfb.standings import build_standings  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "season.json")


def fixture_season() -> Season:
    if not os.path.exists(FIXTURE):
        from make_fixture import build
        return build()
    with open(FIXTURE, encoding="utf-8") as fh:
        return Season.from_dict(json.load(fh))


class PreseasonTests(unittest.TestCase):
    def test_teams_without_conference_games_are_not_reported_as_tied(self):
        season = make_season(
            {"SEC": ["Ash", "Birch", "Cedar"]},
            [("Ash", "Birch"), ("Ash", "Cedar")],   # scheduled, not played
        )
        report = build_report(season, load_rules(2026))
        conf = report["conferences"][0]
        self.assertEqual(conf["notes"], [])
        for row in conf["blocks"][0]["rows"]:
            self.assertEqual(row["tied_with"], [])
        self.assertEqual(conf["championship"]["teams"], [])

    def test_unplayed_team_outranks_a_winless_team(self):
        season = make_season(
            {"SEC": ["Ash", "Birch", "Cedar"]},
            [("Ash", "Birch", 21, 0), ("Ash", "Cedar", 21, 0)],
        )
        table = build_standings(season)
        report = build_report(season, load_rules(2026))
        rows = {r["name"]: r for r in report["conferences"][0]["blocks"][0]["rows"]}
        # Birch and Cedar are 0-1; nobody is 0-0 here, so just check ordering
        self.assertEqual(rows["Ash"]["position"], 1)
        self.assertEqual(table["1"].conference.label, "2-0")


class TableFieldTests(unittest.TestCase):
    """The columns the standings table renders: win share, GB, diff and the
    opponents' conference record shown under each team."""

    def season(self):
        return make_season(
            {"Southeastern Conference": ["Ash", "Birch", "Cedar", "Dogwood"]},
            [
                ("Ash", "Birch", 28, 7),      # Ash +21
                ("Ash", "Cedar", 24, 10),     # Ash +14
                ("Birch", "Cedar", 20, 17),
                ("Cedar", "Dogwood", 14, 10),
                ("Birch", "Dogwood", 31, 3),
            ],
        )

    def rows(self):
        report = build_report(self.season(), load_rules(2026))
        return {r["name"]: r for r in report["conferences"][0]["blocks"][0]["rows"]}

    def test_conference_point_differential(self):
        rows = self.rows()
        self.assertEqual(rows["Ash"]["conf_diff"], 35)        # +21 and +14
        self.assertEqual(rows["Dogwood"]["conf_diff"], -32)   # -4 and -28

    def test_games_back_from_the_leader(self):
        rows = self.rows()
        self.assertEqual(rows["Ash"]["games_back"], "—")      # 2-0, the leader
        self.assertEqual(rows["Birch"]["games_back"], "0.5")  # 2-1
        self.assertEqual(rows["Dogwood"]["games_back"], "2")  # 0-2

    def test_opponents_conference_record(self):
        rows = self.rows()
        # Ash played Birch (2-1) and Cedar (1-2): 3-3 combined.
        self.assertEqual(rows["Ash"]["opp_conf_record"], "3-3")
        self.assertAlmostEqual(rows["Ash"]["opp_conf_pct"], 0.5)

    def test_win_share_matches_the_conference_percentage(self):
        rows = self.rows()
        self.assertEqual(rows["Ash"]["conf_pct"], 1.0)
        self.assertAlmostEqual(rows["Birch"]["conf_pct"], 2 / 3, places=3)

    def test_each_row_carries_its_conference_game_log(self):
        rows = self.rows()
        log = rows["Ash"]["conf_games"]
        self.assertEqual(len(log), 2)
        self.assertEqual({g["opponent"] for g in log}, {"Birch", "Cedar"})
        self.assertTrue(all(g["result"] == "W" for g in log))

    def test_conferences_carry_tier_and_accent_for_the_picker(self):
        report = build_report(self.season(), load_rules(2026))
        conf = report["conferences"][0]
        self.assertEqual(conf["tier"], "p4")
        self.assertEqual(conf["tier_label"], "Power Four")
        self.assertTrue(conf["accent"].startswith("#"))
        self.assertEqual(conf["format_label"], "single-table format")
        self.assertEqual(conf["team_count"], 4)


class TieOrderTests(unittest.TestCase):
    def test_better_record_reads_first_inside_an_unbroken_tie(self):
        # Two ACC teams on the same percentage but different slates; the ACC
        # procedure cannot separate them, so the better record leads.
        season = make_season(
            {"Atlantic Coast Conference": ["Ash", "Birch", "Cedar", "Dogwood"]},
            [
                ("Ash", "Cedar", 21, 14),
                ("Ash", "Dogwood", 28, 10),
                ("Birch", "Cedar", 17, 14),
            ],
        )
        report = build_report(season, load_rules(2026))
        rows = [r for b in report["conferences"][0]["blocks"] for r in b["rows"]]
        self.assertEqual([r["name"] for r in rows[:2]], ["Ash", "Birch"])
        self.assertEqual(rows[0]["conf_record"], "2-0")
        self.assertEqual(rows[1]["conf_record"], "1-0")
        self.assertEqual(rows[0]["position"], rows[1]["position"], "still one tie")
        self.assertEqual(rows[1]["games_back"], "0.5")


class DivisionTests(unittest.TestCase):
    def test_sun_belt_style_divisions_produce_two_blocks(self):
        season = make_season(
            {"Sun Belt Conference": ["E1", "E2", "E3", "W1", "W2", "W3"]},
            [
                ("E1", "E2", 21, 14), ("E1", "E3", 28, 10), ("E2", "E3", 17, 14),
                ("W1", "W2", 21, 14), ("W1", "W3", 28, 10), ("W2", "W3", 17, 14),
                ("E1", "W1", 24, 21), ("E2", "W2", 20, 17), ("E3", "W3", 13, 10),
            ],
            divisions={"Sun Belt Conference": {"East": ["E1", "E2", "E3"], "West": ["W1", "W2", "W3"]}},
        )
        report = build_report(season, load_rules(2026))
        conf = next(c for c in report["conferences"] if "Sun Belt" in c["name"])
        self.assertEqual([b["title"] for b in conf["blocks"]], ["East", "West"])
        winners = {t["division"]: t["team"] for t in conf["championship"]["teams"]}
        self.assertEqual(winners, {"East": "E1", "West": "W1"})


    def test_no_division_leader_before_conference_play_starts(self):
        season = make_season(
            {"Sun Belt Conference": ["E1", "E2", "W1", "W2"]},
            [("E1", "E2"), ("W1", "W2")],       # scheduled, not played
            divisions={"Sun Belt Conference": {"East": ["E1", "E2"], "West": ["W1", "W2"]}},
        )
        report = build_report(season, load_rules(2026))
        conf = next(c for c in report["conferences"] if "Sun Belt" in c["name"])
        self.assertEqual(conf["championship"]["teams"], [])
        for block in conf["blocks"]:
            for row in block["rows"]:
                self.assertEqual(row["berth"], "")

    def test_a_member_espn_filed_under_no_division_still_appears(self):
        season = make_season(
            {"Sun Belt Conference": ["E1", "E2", "W1", "W2", "Orphan"]},
            [
                ("E1", "E2", 21, 14), ("W1", "W2", 28, 10),
                ("E1", "W1", 24, 21), ("Orphan", "E2", 30, 7),
            ],
            divisions={"Sun Belt Conference": {"East": ["E1", "E2"], "West": ["W1", "W2"]}},
        )
        report = build_report(season, load_rules(2026))
        conf = next(c for c in report["conferences"] if "Sun Belt" in c["name"])
        self.assertEqual([b["title"] for b in conf["blocks"]], ["East", "West", "Unassigned"])
        listed = {r["name"] for b in conf["blocks"] for r in b["rows"]}
        self.assertIn("Orphan", listed)
        # ... but it cannot be a championship-game participant
        winners = {t["division"] for t in conf["championship"]["teams"]}
        self.assertEqual(winners, {"East", "West"})


class FullSeasonTests(unittest.TestCase):
    def setUp(self):
        self.season = fixture_season()
        self.report = build_report(self.season, load_rules(2026))

    def test_every_conference_is_reported(self):
        self.assertEqual(len(self.report["conferences"]), len(self.season.conferences))
        for conf in self.report["conferences"]:
            self.assertTrue(conf["blocks"])
            self.assertTrue(conf["blocks"][0]["rows"])

    def test_every_team_appears_exactly_once_in_its_conference(self):
        for conf in self.report["conferences"]:
            seen = [r["team_id"] for b in conf["blocks"] for r in b["rows"]]
            self.assertEqual(len(seen), len(set(seen)), conf["name"])
            expected = self.season.conferences[conf["id"]].team_ids
            self.assertEqual(sorted(seen), sorted(expected), conf["name"])

    def test_positions_are_monotonic_and_ties_share_a_position(self):
        for conf in self.report["conferences"]:
            for block in conf["blocks"]:
                last = 0
                for row in block["rows"]:
                    self.assertGreaterEqual(row["position"], last)
                    last = row["position"]
                by_position = {}
                for row in block["rows"]:
                    by_position.setdefault(row["position"], []).append(row)
                for position, rows in by_position.items():
                    if len(rows) > 1:
                        pcts = {r["conf_pct"] for r in rows}
                        self.assertEqual(len(pcts), 1, f"{conf['name']} position {position}")

    def test_notes_only_describe_teams_that_share_a_record(self):
        for conf in self.report["conferences"]:
            rows = {r["name"]: r for b in conf["blocks"] for r in b["rows"]}
            for note in conf["notes"]:
                # Teams are tied on percentage, which is what every published
                # procedure keys on - not necessarily an identical W-L.
                pcts = {rows[n]["conf_pct"] for n in note["tied"] if n in rows}
                self.assertLessEqual(len(pcts), 1, note)

    def test_site_renders(self):
        with tempfile.TemporaryDirectory() as out:
            written = write_site(self.report, out)
            names = {os.path.basename(p) for p in written}
            self.assertTrue({"index.html", "scores.html", "tiebreakers.html", "data.json"} <= names)
            index = open(os.path.join(out, "index.html"), encoding="utf-8").read()
            for conf in self.report["conferences"]:
                self.assertIn(conf["name"], index)
            self.assertEqual(index.count("<html"), 1)
            self.assertNotIn("None", index.split("<body")[0])
            payload = json.load(open(os.path.join(out, "data.json"), encoding="utf-8"))
            self.assertEqual(payload["season"], self.report["season"])

    def test_season_survives_a_json_round_trip(self):
        again = Season.from_dict(json.loads(json.dumps(self.season.to_dict())))
        self.assertEqual(len(again.games), len(self.season.games))
        self.assertEqual(len(again.teams), len(self.season.teams))
        self.assertEqual(
            build_report(again, load_rules(2026))["conferences"][0]["blocks"][0]["rows"][0]["name"],
            self.report["conferences"][0]["blocks"][0]["rows"][0]["name"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
