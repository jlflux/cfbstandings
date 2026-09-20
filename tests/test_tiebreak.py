"""Tiebreaker engine tests.

Each case is a hand-built miniature season where the correct answer under the
published procedure is unambiguous.
"""

import unittest

from helpers import flat, load_rules, make_season, names, order


ROUND_ROBIN_4 = ["Ash", "Birch", "Cedar", "Dogwood"]


def round_robin(results):
    return results


class TwoTeamTests(unittest.TestCase):
    def test_head_to_head_decides_two_team_tie(self):
        season = make_season(
            {"SEC": ["Alabama", "Georgia", "Tennessee", "Vandy"]},
            [
                ("Alabama", "Georgia", 24, 21),      # the head-to-head
                ("Alabama", "Vandy", 35, 7),
                ("Tennessee", "Alabama", 30, 10),
                ("Georgia", "Tennessee", 28, 17),
                ("Georgia", "Vandy", 40, 3),
                ("Vandy", "Tennessee", 21, 14),
            ],
        )
        # Alabama 2-1, Georgia 2-1, Vandy 1-2, Tennessee 1-2
        levels, notes = order(season, "SEC", load_rules("sec"))
        self.assertEqual(flat(season, levels), ["Alabama", "Georgia", "Vandy", "Tennessee"])
        decided = [n for n in notes if n.resolved]
        self.assertTrue(decided)
        self.assertTrue(all(n.step == "head_to_head" for n in decided))

    def test_two_team_tie_that_never_met_falls_through(self):
        season = make_season(
            {"B1G": ["Iowa", "Purdue", "Rutgers", "Illinois"]},
            [
                ("Iowa", "Rutgers", 21, 14),
                ("Iowa", "Illinois", 28, 10),
                ("Purdue", "Rutgers", 17, 10),
                ("Purdue", "Illinois", 24, 21),
                ("Rutgers", "Illinois", 14, 13),
            ],
        )
        # Iowa and Purdue are both 2-0 and did not play. Their common
        # opponents (Rutgers, Illinois) split 2-0 each way, and the Big Ten
        # procedure's next public step is the SportSource rating.
        levels, notes = order(season, "B1G", load_rules("big-ten"))
        self.assertEqual(sorted(names(season, levels)[0]), ["Iowa", "Purdue"])
        halt = [n for n in notes if not n.resolved]
        self.assertTrue(halt)
        self.assertIn("SportSource", halt[0].summary)


class MultiTeamTests(unittest.TestCase):
    def test_circular_three_way_tie_passes_through_head_to_head(self):
        # Rock-paper-scissors: everyone is 1-1 against the other tied teams,
        # so head-to-head cannot separate them and the SEC procedure runs on
        # down to the capped scoring margin.
        season = make_season(
            {"SEC": ["Ash", "Birch", "Cedar", "Dogwood"]},
            [
                ("Ash", "Birch", 21, 17),
                ("Birch", "Cedar", 30, 27),
                ("Cedar", "Ash", 24, 21),
                ("Ash", "Dogwood", 40, 0),
                ("Birch", "Dogwood", 40, 0),
                ("Dogwood", "Cedar", 0, 40),
            ],
        )
        levels, notes = order(season, "SEC", load_rules("sec"))
        self.assertEqual(flat(season, levels), ["Ash", "Cedar", "Birch", "Dogwood"])
        self.assertFalse(any(n.step == "head_to_head" and n.resolved for n in notes))
        decider = next(n for n in notes if n.resolved)
        self.assertEqual(decider.step, "capped_scoring_margin")

    def test_multi_team_step_splits_then_pair_restarts_at_head_to_head(self):
        # Four teams tie at 3-2. The mini round robin puts Ash and Birch at
        # 2-1 and Cedar and Dogwood at 1-2; each surviving pair then restarts
        # the procedure, where head-to-head settles it.
        season = make_season(
            {"SEC": ["Ash", "Birch", "Cedar", "Dogwood", "Elm", "Fir"]},
            [
                ("Ash", "Birch", 21, 17),
                ("Ash", "Cedar", 24, 20),
                ("Dogwood", "Ash", 30, 27),
                ("Birch", "Cedar", 28, 24),
                ("Birch", "Dogwood", 31, 28),
                ("Cedar", "Dogwood", 20, 17),
                ("Ash", "Elm", 40, 10), ("Fir", "Ash", 30, 20),
                ("Birch", "Elm", 40, 10), ("Fir", "Birch", 30, 20),
                ("Cedar", "Elm", 40, 10), ("Cedar", "Fir", 30, 20),
                ("Dogwood", "Elm", 40, 10), ("Dogwood", "Fir", 30, 20),
                ("Elm", "Fir", 21, 14),
            ],
        )
        levels, notes = order(season, "SEC", load_rules("sec"))
        self.assertEqual(
            flat(season, levels),
            ["Ash", "Birch", "Cedar", "Dogwood", "Fir", "Elm"],
        )
        resolved = [n for n in notes if n.resolved]
        # first the four-team mini round robin, then a head-to-head per pair
        self.assertEqual(len(resolved[0].tied), 4)
        self.assertEqual(resolved[0].step, "head_to_head")
        self.assertEqual([len(level) for level in resolved[0].outcome], [2, 2])
        self.assertTrue(all(len(n.tied) == 2 for n in resolved[1:]))

    def test_sweep_rule_when_round_robin_incomplete(self):
        # A, B and C tie at 2-2. A beat both B and C; B and C never met, so
        # only the sweep clause applies.
        season = make_season(
            {"Big 12": ["A", "B", "C", "D", "E", "F"]},
            [
                ("A", "B", 21, 17), ("A", "C", 24, 20),
                ("D", "A", 30, 27), ("E", "A", 31, 28),
                ("B", "D", 20, 17), ("B", "E", 21, 14), ("F", "B", 24, 21),
                ("C", "D", 20, 17), ("E", "C", 28, 24), ("C", "F", 31, 28),
                ("E", "D", 35, 7), ("D", "F", 21, 20), ("E", "F", 40, 3),
            ],
        )
        levels, notes = order(season, "Big 12", load_rules("big-12"))
        ordering = flat(season, levels)
        self.assertEqual(ordering[0], "E")   # 4-1, clear of the tie
        self.assertEqual(ordering[1], "A")   # swept the tied group
        sweep = [n for n in notes if "defeated every other tied team" in n.summary]
        self.assertTrue(sweep)
        # B and C then restart and are split further down the procedure
        self.assertEqual(ordering[2:4], ["B", "C"])

    def test_two_team_tie_below_the_lead_also_uses_head_to_head(self):
        season = make_season(
            {"Big 12": ["Ash", "Birch", "Cedar", "Dogwood"]},
            [
                ("Ash", "Birch", 21, 17),
                ("Cedar", "Dogwood", 24, 20),
                ("Ash", "Dogwood", 30, 27),
                ("Birch", "Cedar", 31, 28),
            ],
        )
        levels, _ = order(season, "Big 12", load_rules("big-12"))
        ordering = flat(season, levels)
        self.assertEqual(ordering[0], "Ash")
        self.assertEqual(ordering[1], "Birch")   # beat Cedar head to head


class StepTests(unittest.TestCase):
    def test_common_opponents_breaks_tie_when_head_to_head_absent(self):
        # A and B tie at 2-1 and never played. Their only common opponents
        # are C and D: A went 2-0, B went 1-1.
        season = make_season(
            {"SEC": ["A", "B", "C", "D", "E", "F"]},
            [
                ("A", "C", 21, 14), ("A", "D", 28, 20), ("E", "A", 30, 10),
                ("B", "C", 24, 17), ("D", "B", 21, 20), ("B", "F", 35, 7),
                ("E", "C", 40, 0), ("F", "C", 21, 14),
                ("E", "D", 30, 10), ("D", "F", 24, 21),
            ],
        )
        levels, notes = order(season, "SEC", load_rules("sec"))
        ordering = flat(season, levels)
        self.assertEqual(ordering[0], "E")           # 3-0
        self.assertLess(ordering.index("A"), ordering.index("B"))
        used = [n for n in notes if n.resolved and n.step == "common_opponents"]
        self.assertTrue(used)

    def test_capped_scoring_margin_caps_blowouts(self):
        # Two teams identical everywhere except margin. Ash won one game by
        # 70; the cap keeps that from dwarfing Birch's steady margins.
        season = make_season(
            {"SEC": ["Ash", "Birch", "Cedar", "Dogwood"]},
            [
                ("Ash", "Cedar", 77, 7),
                ("Ash", "Dogwood", 14, 10),
                ("Birch", "Cedar", 35, 0),
                ("Birch", "Dogwood", 35, 0),
                ("Cedar", "Dogwood", 20, 17),
            ],
        )
        rules = load_rules("sec")
        levels, notes = order(season, "SEC", rules)
        ordering = flat(season, levels)
        # Ash capped: (42-7) + (14-10) = 39 -> 19.5/game
        # Birch capped: 35 + 35 = 70 -> 35.0/game
        self.assertEqual(ordering[0], "Birch")
        margin = [n for n in notes if n.step == "capped_scoring_margin"]
        self.assertTrue(margin and margin[0].resolved)

    def test_order_of_finish_uses_highest_placed_common_opponent(self):
        season = make_season(
            {"SEC": ["Ash", "Birch", "Top", "Mid", "Low"]},
            [
                ("Top", "Mid", 30, 10),
                ("Top", "Low", 30, 10),
                ("Mid", "Low", 21, 14),
                # Ash and Birch never meet; both 1-1 vs the common set,
                # but Ash beat the highest-placed common opponent.
                ("Ash", "Top", 21, 20),
                ("Ash", "Mid", 10, 20),
                ("Birch", "Top", 10, 20),
                ("Birch", "Mid", 21, 20),
                ("Ash", "Low", 40, 0),
                ("Birch", "Low", 40, 0),
            ],
        )
        levels, notes = order(season, "SEC", load_rules("sec"))
        ordering = flat(season, levels)
        self.assertLess(ordering.index("Ash"), ordering.index("Birch"))
        step_used = [n for n in notes if n.resolved and n.step == "order_of_finish"]
        self.assertTrue(step_used)

    def test_cfp_ranking_step(self):
        season = make_season(
            {"American": ["Ash", "Birch", "Cedar", "Dogwood"]},
            [
                ("Ash", "Cedar", 21, 14),
                ("Ash", "Dogwood", 21, 14),
                ("Birch", "Cedar", 21, 14),
                ("Birch", "Dogwood", 21, 14),
                ("Cedar", "Dogwood", 21, 14),
            ],
            rankings={"CFP Rankings": {"2": 12}},  # Birch is team id 2
        )
        levels, notes = order(season, "American", load_rules("american"))
        ordering = flat(season, levels)
        self.assertEqual(ordering[0], "Birch")
        self.assertTrue(any(n.step == "ranking" and n.resolved for n in notes))

    def test_acc_halts_on_unavailable_analytics(self):
        season = make_season(
            {"ACC": ["Ash", "Birch", "Cedar", "Dogwood"]},
            [
                ("Ash", "Cedar", 21, 14),
                ("Ash", "Dogwood", 21, 14),
                ("Birch", "Cedar", 21, 14),
                ("Birch", "Dogwood", 21, 14),
                ("Cedar", "Dogwood", 21, 14),
            ],
        )
        levels, notes = order(season, "ACC", load_rules("acc"))
        self.assertEqual(sorted(names(season, levels)[0]), ["Ash", "Birch"])
        self.assertTrue(any("Team Success Ranking" in n.summary for n in notes))


class OrderingTests(unittest.TestCase):
    def test_win_pct_separates_before_any_tiebreaker_runs(self):
        season = make_season(
            {"SEC": ["Ash", "Birch", "Cedar"]},
            [
                ("Ash", "Birch", 21, 14),
                ("Ash", "Cedar", 21, 14),
                ("Birch", "Cedar", 21, 14),
            ],
        )
        levels, notes = order(season, "SEC", load_rules("sec"))
        self.assertEqual(flat(season, levels), ["Ash", "Birch", "Cedar"])
        self.assertEqual(notes, [])

    def test_unbalanced_schedules_compare_by_percentage(self):
        season = make_season(
            {"ACC": ["Ash", "Birch", "Cedar", "Dogwood", "Elm"]},
            [
                ("Ash", "Cedar", 21, 0),
                ("Ash", "Dogwood", 21, 0),
                ("Ash", "Elm", 21, 0),      # Ash 3-0 (.1000)
                ("Birch", "Cedar", 21, 0),
                ("Birch", "Dogwood", 21, 0),  # Birch 2-0 (.1000) - still tied
                ("Cedar", "Dogwood", 10, 7),
                ("Cedar", "Elm", 10, 7),
                ("Dogwood", "Elm", 10, 7),
            ],
        )
        levels, _ = order(season, "ACC", load_rules("acc"))
        self.assertEqual(sorted(names(season, levels)[0]), ["Ash", "Birch"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
