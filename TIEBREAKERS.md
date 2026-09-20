# Conference tiebreaker procedures

Generated from `data/rules/2026/` by `scripts/render_rules_doc.py` —
edit the JSON, not this file.

Teams are separated first by conference winning percentage. Only teams on
the same percentage are tied. A two-team tie uses the two-team list; three
or more teams use the multi-team list. When a step splits a tied group,
each subgroup restarts the procedure from step one, dropping to the
two-team list once only two teams remain.

A step that does not apply yet is skipped. A step that cannot be computed
from public data stops the procedure, and the tie is reported as unresolved
rather than being decided by a step the conference would never reach.

## Atlantic Coast Conference

*Based on reporting of the conference's published procedure.* Verified 2026-09-20.

One table; the top two meet in the championship game.

New for 2026, after the 2025 five-way tie. Twelve members play nine conference games and five play eight, so the league deliberately dropped the opponent-based steps: head-to-head first, then the SportSource Analytics Team Success Ranking, then a draw. Because the Team Success Ranking is not public, ties that head-to-head cannot settle are reported here as unresolved.

**Two teams tied**

1. Head-to-head competition
2. SportSource Analytics Team Success Ranking *(not public — the tie is reported unresolved here)*
3. Draw administered by the commissioner *(not computable — the tie is reported unresolved here)*

**Three or more teams tied**

1. Record among the tied teams (round robin; a team that beat all others advances)
2. SportSource Analytics Team Success Ranking *(not public — the tie is reported unresolved here)*
3. Draw administered by the commissioner *(not computable — the tie is reported unresolved here)*

Sources:

* <https://theacc.com/news/2026/7/15/acc-announces-new-football-championship-tiebreaker-policy.aspx>
* <https://www.espn.com/college-football/story/_/id/49366844/acc-implements-new-tiebreaker-policy-football-title-game>

## Big Ten Conference

*Verified against the conference's own published procedure.* Verified 2026-09-20.

One table; the top two meet in the championship game.

Six published steps. Step 5 is the SportSource Analytics Team Rating Score, which is not published publicly, so a tie that survives step 4 is reported here as unresolved rather than guessed at.

**Two teams tied**

1. Head-to-head competition
2. Win pct vs all common conference opponents
3. Win pct vs the highest-placed common conference opponent, proceeding through the standings
4. Combined conference win pct of all conference opponents
5. SportSource Analytics Team Rating Score *(not public — the tie is reported unresolved here)*
6. Draw administered by the commissioner *(not computable — the tie is reported unresolved here)*

Sources:

* <https://bigten.org/fb/article/58967/>
* <https://bigten.org/fb/article/blt6104802d94ebe1ab/>

## Big 12 Conference

*Verified against the conference's own published procedure.* Verified 2026-09-20.

One table; the top two meet in the championship game.

Schedules are unbalanced, so the multi-team head-to-head step only separates teams when the tied group played a full round robin, or when one team beat every other tied team.

**Two teams tied**

1. Head-to-head competition
2. Win pct vs all common conference opponents
3. Win pct vs the highest-placed common conference opponent, proceeding through the standings
4. Combined conference win pct of all conference opponents
5. Total wins
6. SportSource Analytics rating *(not public — the tie is reported unresolved here)*
7. Coin toss administered by the commissioner *(not computable — the tie is reported unresolved here)*

**Three or more teams tied**

1. Record among the tied teams (round robin; a team that beat all others advances)
2. Win pct vs all common conference opponents
3. Win pct vs the highest-placed common conference opponent, proceeding through the standings
4. Combined conference win pct of all conference opponents
5. Total wins
6. SportSource Analytics rating *(not public — the tie is reported unresolved here)*
7. Coin toss administered by the commissioner *(not computable — the tie is reported unresolved here)*

Sources:

* <https://www.espn.com/college-football/story/_/id/41149467/big-12-reveals-tiebreaking-policies-conference-title-game>
* <https://www.espn.com/college-football/story/_/id/42082434/what-fbs-college-football-conference-tiebreaker-rules>

## Southeastern Conference

*Verified against the conference's own published procedure.* Verified 2026-09-20.

One table; the top two meet in the championship game.

The two teams with the best conference winning percentage meet in Atlanta. If exactly two teams tie for first, both play in the championship game and the procedure only decides the home team. The capped scoring margin caps points scored at 42 and points allowed at 48 in each conference game; this build compares the per-game average so the step stays fair if teams play a different number of conference games.

**Two teams tied**

1. Head-to-head competition
2. Win pct vs all common conference opponents
3. Win pct vs the highest-placed common conference opponent, proceeding through the standings
4. Combined conference win pct of all conference opponents
5. Capped relative scoring margin vs all conference opponents (42 scored / 48 allowed)
6. Draw administered by the commissioner *(not computable — the tie is reported unresolved here)*

Sources:

* <https://www.secsports.com/fbtiebreaker>
* <https://www.secsports.com/news/2024/08/sec-announces-football-tie-breaking-process>
* <https://www.espn.com/college-football/story/_/id/40944783/sec-reveals-tiebreaking-procedures-conference-title-game>

## American Conference

*Based on reporting of the conference's published procedure.* Verified 2026-09-20.

One table; the top two meet in the championship game.

A multi-team tie without a full round robin goes straight to the College Football Playoff rankings, which only exist from early November onward; before then such a tie is reported as unresolved.

**Two teams tied**

1. Head-to-head competition
2. Win pct vs all common conference opponents
3. Win pct vs the highest-placed common conference opponent, proceeding through the standings
4. Highest College Football Playoff committee ranking
5. Overall winning percentage
6. Draw administered by the commissioner *(not computable — the tie is reported unresolved here)*

**Three or more teams tied**

1. Record among the tied teams (round robin; a team that beat all others advances)
2. Highest College Football Playoff committee ranking
3. Win pct vs all common conference opponents
4. Win pct vs the highest-placed common conference opponent, proceeding through the standings
5. Overall winning percentage
6. Draw administered by the commissioner *(not computable — the tie is reported unresolved here)*

Sources:

* <https://theamerican.org/news/2025/11/23/FOOTBALL_Tiebreaker.aspx>
* <https://www.espn.com/college-football/story/_/id/42082434/what-fbs-college-football-conference-tiebreaker-rules>

## Conference USA

*Best-effort reconstruction — re-check before relying on it.* Verified 2026-09-20.

One table; the top two meet in the championship game.

CUSA rewrote its procedure for 2024 to line up closely with the American and the Mountain West. The official policy is published only as a PDF; this ordering is modelled on those leagues and should be re-checked against the PDF before it is relied on late in the season.

**Two teams tied**

1. Head-to-head competition
2. Win pct vs all common conference opponents
3. Win pct vs the highest-placed common conference opponent, proceeding through the standings
4. Highest College Football Playoff committee ranking
5. Overall winning percentage
6. Draw administered by the commissioner *(not computable — the tie is reported unresolved here)*

**Three or more teams tied**

1. Record among the tied teams (round robin; a team that beat all others advances)
2. Highest College Football Playoff committee ranking
3. Win pct vs all common conference opponents
4. Win pct vs the highest-placed common conference opponent, proceeding through the standings
5. Overall winning percentage
6. Draw administered by the commissioner *(not computable — the tie is reported unresolved here)*

Sources:

* <https://conferenceusa.com/documents/2024/9/19/CUSA_FB_Championship_Game_Tiebreaker_Policy.pdf>
* <https://www.espn.com/college-football/story/_/id/42082434/what-fbs-college-football-conference-tiebreaker-rules>

## Mid-American Conference

*Verified against the conference's own published procedure.* Verified 2026-09-20.

One table; the top two meet in the championship game.

The MAC puts the SportSource Analytics Team Rating Score third, ahead of the opponent-based steps. That is faithfully encoded here, which means MAC ties surviving the common-opponents step are reported as unresolved.

**Two teams tied**

1. Head-to-head competition
2. Win pct vs all common conference opponents
3. SportSource Analytics Team Rating Score *(not public — the tie is reported unresolved here)*
4. Win pct vs the highest-placed common conference opponent, proceeding through the standings
5. Combined conference win pct of all conference opponents
6. Draw administered by the commissioner *(not computable — the tie is reported unresolved here)*

Sources:

* <https://getsomemaction.com/news/2025/11/24/2025-mac-football-championship-game-tiebreakers.aspx>
* <https://getsomemaction.com/sports/2025/11/12/FB_1112255434.aspx>

## Mountain West Conference

*Based on reporting of the conference's published procedure.* Verified 2026-09-20.

One table; the top two meet in the championship game.

The league leans on the CFP ranking and then an average of designated computer ratings. The computer composite is not reproducible from public feeds, so it halts the procedure here.

**Two teams tied**

1. Head-to-head competition
2. Win pct vs all common conference opponents
3. Highest College Football Playoff committee ranking
4. average of the designated computer rankings *(not public — the tie is reported unresolved here)*
5. Overall winning percentage
6. Coin toss administered by the commissioner *(not computable — the tie is reported unresolved here)*

Sources:

* <https://themw.com/sports/2023/8/17/football-tiebreaker-procedures.aspx>
* <https://www.espn.com/college-football/story/_/id/42082434/what-fbs-college-football-conference-tiebreaker-rules>

## Pac-12 Conference

*Based on reporting of the conference's published procedure.* Verified 2026-09-20.

One table; the top two meet in the championship game.

The rebuilt eight-team league plays a true round robin (seven conference games), so head-to-head resolves almost every tie. The championship game is hosted by the higher seed.

**Two teams tied**

1. Head-to-head competition
2. Win pct vs all common conference opponents
3. Win pct vs the highest-placed common conference opponent, proceeding through the standings
4. Combined conference win pct of all conference opponents
5. Overall winning percentage
6. Draw administered by the commissioner *(not computable — the tie is reported unresolved here)*

**Three or more teams tied**

1. Head-to-head competition
2. Win pct vs the highest-placed common conference opponent, proceeding through the standings
3. Combined conference win pct of all conference opponents
4. Overall winning percentage
5. Draw administered by the commissioner *(not computable — the tie is reported unresolved here)*

Sources:

* <https://pac-12.com/news/2026/2/9/general-the-new-pac-12-announces-its-2026-football-schedule.aspx>
* <https://pac-12.com/news/2026/9/3/pac-12-announces-commercial-and-operational-updates-ahead-of-its-2026-football-season-kickoff.aspx>

## Sun Belt Conference

*Based on reporting of the conference's published procedure.* Verified 2026-09-20.

Two divisions; the division champions meet in the championship game.

The only FBS league still using divisions: the East and West champions meet for the title. Each team plays six divisional games and two crossovers, so the divisional record carries most of the weight.

**Two teams tied**

1. Head-to-head competition
2. Win pct within the division
3. Win pct vs the next highest-placed team in the division, proceeding down
4. Combined win pct vs all common non-divisional conference opponents
5. Overall winning percentage
6. Draw administered by the commissioner *(not computable — the tie is reported unresolved here)*

Sources:

* <https://sunbeltsports.org/sports/2018/8/30/FB_Tie-Breakers.aspx>
* <https://sunbeltsports.org/news/2026/3/13/sun-belt-announces-2026-football-schedule.aspx>

## FBS Independents

*Verified against the conference's own published procedure.* Verified 2026-09-20.

No conference schedule and no championship game.

Independents play no conference schedule; they are listed by overall record.

**Two teams tied**

1. Overall winning percentage

## Steps the engine implements

* `all_opponents_win_pct`
* `capped_scoring_margin`
* `common_nondivision_opponents`
* `common_opponents`
* `conference_opponents_win_pct`
* `division_record`
* `draw`
* `head_to_head`
* `order_of_finish`
* `overall_win_pct`
* `ranking`
* `total_wins`
* `unavailable_metric`
