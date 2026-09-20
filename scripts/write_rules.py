"""Emit the per-conference tiebreaker rule files.

Kept as a script so the whole 2026 rule set can be regenerated and diffed in
one place. The JSON files it writes are the real source of truth at runtime.
"""

import json
import os

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "rules", "2026")
VERIFIED = "2026-09-20"


def step(name, label, **params):
    entry = {"step": name, "label": label}
    if params:
        entry["params"] = params
    return entry


H2H = step("head_to_head", "Head-to-head competition")
H2H_RR = step(
    "head_to_head",
    "Record among the tied teams (round robin; a team that beat all others advances)",
    mode="round_robin_or_sweep",
)
COMMON = step("common_opponents", "Win pct vs all common conference opponents")
ORDER = step(
    "order_of_finish",
    "Win pct vs the highest-placed common conference opponent, proceeding through the standings",
    common_only=True,
)
SOS_CONF = step(
    "conference_opponents_win_pct",
    "Combined conference win pct of all conference opponents",
)
OVERALL = step("overall_win_pct", "Overall winning percentage")
TOTAL_WINS = step("total_wins", "Total wins")
DRAW = step("draw", "Draw administered by the commissioner")
COIN = step("draw", "Coin toss administered by the commissioner")


def sportsource(metric):
    return step("unavailable_metric", metric, metric=metric)


CFP = step("ranking", "Highest College Football Playoff committee ranking", polls=["cfp", "playoff"])

RULES = {
    "sec": {
        "conference": "Southeastern Conference",
        "espn_group_id": "8",
        "structure": "single_table",
        "confidence": "high",
        "sources": [
            "https://www.secsports.com/fbtiebreaker",
            "https://www.secsports.com/news/2024/08/sec-announces-football-tie-breaking-process",
            "https://www.espn.com/college-football/story/_/id/40944783/sec-reveals-tiebreaking-procedures-conference-title-game",
        ],
        "notes": (
            "The two teams with the best conference winning percentage meet in Atlanta. "
            "If exactly two teams tie for first, both play in the championship game and the "
            "procedure only decides the home team. The capped scoring margin caps points "
            "scored at 42 and points allowed at 48 in each conference game; this build "
            "compares the per-game average so the step stays fair if teams play a different "
            "number of conference games."
        ),
        "two_team": [H2H, COMMON, ORDER, SOS_CONF,
                     step("capped_scoring_margin",
                          "Capped relative scoring margin vs all conference opponents (42 scored / 48 allowed)",
                          cap_for=42, cap_against=48, per_game=True),
                     DRAW],
    },
    "big-ten": {
        "conference": "Big Ten Conference",
        "espn_group_id": "5",
        "structure": "single_table",
        "confidence": "high",
        "sources": [
            "https://bigten.org/fb/article/58967/",
            "https://bigten.org/fb/article/blt6104802d94ebe1ab/",
        ],
        "notes": (
            "Six published steps. Step 5 is the SportSource Analytics Team Rating Score, "
            "which is not published publicly, so a tie that survives step 4 is reported here "
            "as unresolved rather than guessed at."
        ),
        "two_team": [H2H, COMMON, ORDER, SOS_CONF,
                     sportsource("SportSource Analytics Team Rating Score"), DRAW],
    },
    "big-12": {
        "conference": "Big 12 Conference",
        "espn_group_id": "4",
        "structure": "single_table",
        "confidence": "high",
        "sources": [
            "https://www.espn.com/college-football/story/_/id/41149467/big-12-reveals-tiebreaking-policies-conference-title-game",
            "https://www.espn.com/college-football/story/_/id/42082434/what-fbs-college-football-conference-tiebreaker-rules",
        ],
        "notes": (
            "Schedules are unbalanced, so the multi-team head-to-head step only separates "
            "teams when the tied group played a full round robin, or when one team beat every "
            "other tied team."
        ),
        "two_team": [H2H, COMMON, ORDER, SOS_CONF, TOTAL_WINS,
                     sportsource("SportSource Analytics rating"), COIN],
        "multi_team": [H2H_RR, COMMON, ORDER, SOS_CONF, TOTAL_WINS,
                       sportsource("SportSource Analytics rating"), COIN],
    },
    "acc": {
        "conference": "Atlantic Coast Conference",
        "espn_group_id": "1",
        "structure": "single_table",
        "confidence": "medium",
        "sources": [
            "https://theacc.com/news/2026/7/15/acc-announces-new-football-championship-tiebreaker-policy.aspx",
            "https://www.espn.com/college-football/story/_/id/49366844/acc-implements-new-tiebreaker-policy-football-title-game",
        ],
        "notes": (
            "New for 2026, after the 2025 five-way tie. Twelve members play nine conference "
            "games and five play eight, so the league deliberately dropped the opponent-based "
            "steps: head-to-head first, then the SportSource Analytics Team Success Ranking, "
            "then a draw. Because the Team Success Ranking is not public, ties that head-to-head "
            "cannot settle are reported here as unresolved."
        ),
        "two_team": [H2H, sportsource("SportSource Analytics Team Success Ranking"), DRAW],
        "multi_team": [H2H_RR, sportsource("SportSource Analytics Team Success Ranking"), DRAW],
    },
    "american": {
        "conference": "American Conference",
        "espn_group_id": "151",
        "structure": "single_table",
        "confidence": "medium",
        "sources": [
            "https://theamerican.org/news/2025/11/23/FOOTBALL_Tiebreaker.aspx",
            "https://www.espn.com/college-football/story/_/id/42082434/what-fbs-college-football-conference-tiebreaker-rules",
        ],
        "notes": (
            "A multi-team tie without a full round robin goes straight to the College Football "
            "Playoff rankings, which only exist from early November onward; before then such a "
            "tie is reported as unresolved."
        ),
        "two_team": [H2H, COMMON, ORDER, CFP, OVERALL, DRAW],
        "multi_team": [H2H_RR, CFP, COMMON, ORDER, OVERALL, DRAW],
    },
    "mountain-west": {
        "conference": "Mountain West Conference",
        "espn_group_id": "17",
        "structure": "single_table",
        "confidence": "medium",
        "sources": [
            "https://themw.com/sports/2023/8/17/football-tiebreaker-procedures.aspx",
            "https://www.espn.com/college-football/story/_/id/42082434/what-fbs-college-football-conference-tiebreaker-rules",
        ],
        "notes": (
            "The league leans on the CFP ranking and then an average of designated computer "
            "ratings. The computer composite is not reproducible from public feeds, so it halts "
            "the procedure here."
        ),
        "two_team": [H2H, COMMON, CFP,
                     sportsource("average of the designated computer rankings"), OVERALL, COIN],
    },
    "pac-12": {
        "conference": "Pac-12 Conference",
        "espn_group_id": "9",
        "structure": "single_table",
        "confidence": "medium",
        "sources": [
            "https://pac-12.com/news/2026/2/9/general-the-new-pac-12-announces-its-2026-football-schedule.aspx",
            "https://pac-12.com/news/2026/9/3/pac-12-announces-commercial-and-operational-updates-ahead-of-its-2026-football-season-kickoff.aspx",
        ],
        "notes": (
            "The rebuilt eight-team league plays a true round robin (seven conference games), "
            "so head-to-head resolves almost every tie. The championship game is hosted by the "
            "higher seed."
        ),
        "two_team": [H2H, COMMON, ORDER, SOS_CONF, OVERALL, DRAW],
        "multi_team": [H2H, ORDER, SOS_CONF, OVERALL, DRAW],
    },
    "mac": {
        "conference": "Mid-American Conference",
        "espn_group_id": "15",
        "structure": "single_table",
        "confidence": "high",
        "sources": [
            "https://getsomemaction.com/news/2025/11/24/2025-mac-football-championship-game-tiebreakers.aspx",
            "https://getsomemaction.com/sports/2025/11/12/FB_1112255434.aspx",
        ],
        "notes": (
            "The MAC puts the SportSource Analytics Team Rating Score third, ahead of the "
            "opponent-based steps. That is faithfully encoded here, which means MAC ties "
            "surviving the common-opponents step are reported as unresolved."
        ),
        "two_team": [H2H, COMMON,
                     sportsource("SportSource Analytics Team Rating Score"),
                     ORDER, SOS_CONF, DRAW],
    },
    "conference-usa": {
        "conference": "Conference USA",
        "espn_group_id": "12",
        "structure": "single_table",
        "confidence": "low",
        "sources": [
            "https://conferenceusa.com/documents/2024/9/19/CUSA_FB_Championship_Game_Tiebreaker_Policy.pdf",
            "https://www.espn.com/college-football/story/_/id/42082434/what-fbs-college-football-conference-tiebreaker-rules",
        ],
        "notes": (
            "CUSA rewrote its procedure for 2024 to line up closely with the American and the "
            "Mountain West. The official policy is published only as a PDF; this ordering is "
            "modelled on those leagues and should be re-checked against the PDF before it is "
            "relied on late in the season."
        ),
        "two_team": [H2H, COMMON, ORDER, CFP, OVERALL, DRAW],
        "multi_team": [H2H_RR, CFP, COMMON, ORDER, OVERALL, DRAW],
    },
    "sun-belt": {
        "conference": "Sun Belt Conference",
        "espn_group_id": "37",
        "structure": "divisions",
        "confidence": "medium",
        "sources": [
            "https://sunbeltsports.org/sports/2018/8/30/FB_Tie-Breakers.aspx",
            "https://sunbeltsports.org/news/2026/3/13/sun-belt-announces-2026-football-schedule.aspx",
        ],
        "notes": (
            "The only FBS league still using divisions: the East and West champions meet for "
            "the title. Each team plays six divisional games and two crossovers, so the "
            "divisional record carries most of the weight."
        ),
        "two_team": [
            H2H,
            step("division_record", "Win pct within the division"),
            step("order_of_finish",
                 "Win pct vs the next highest-placed team in the division, proceeding down",
                 common_only=False),
            step("common_nondivision_opponents",
                 "Combined win pct vs all common non-divisional conference opponents"),
            OVERALL,
            DRAW,
        ],
    },
    "independents": {
        "conference": "FBS Independents",
        "espn_group_id": "18",
        "structure": "no_championship",
        "confidence": "high",
        "sources": [],
        "notes": "Independents play no conference schedule; they are listed by overall record.",
        "two_team": [OVERALL],
    },
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for slug, rules in RULES.items():
        payload = {
            "slug": slug,
            "season": 2026,
            "verified_on": VERIFIED,
            "championship": {
                "participants": 2,
                "selection": (
                    "division champions" if rules["structure"] == "divisions"
                    else "top two by conference winning percentage"
                ),
            },
            **rules,
        }
        payload.setdefault("multi_team", payload["two_team"])
        path = os.path.join(OUT, f"{slug}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
