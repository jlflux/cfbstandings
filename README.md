# cfbstandings

College football conference standings with every published tiebreaker applied,
rebuilt from ESPN's public data and published as a static site.

* **Standings** — every FBS conference, ordered by conference winning
  percentage and then by that conference's own published tiebreaker procedure.
* **Scores** — the current and previous week's games, live during the day.
* **Tiebreakers** — the exact procedure encoded for each conference, with
  sources, so the ordering above can be checked rather than trusted.

## Update cadence

| When | Frequency |
| --- | --- |
| Saturday 11:00 AM – Sunday 3:00 AM US Central | every 10 minutes |
| Every other day | once, around 7–8 AM Central |

GitHub Actions cron only speaks UTC, so `.github/workflows/update.yml`
schedules the widest UTC span the Central window can occupy under either CST
or CDT, and a guard step converts the current time to `America/Chicago` and
skips the run if it falls outside 11:00 Saturday – 03:00 Sunday. That keeps
the window exact across the November DST change without touching the crons.

Two caveats worth knowing:

* GitHub delays scheduled workflows under load, sometimes by 10–20 minutes,
  and may drop a run entirely at peak times. A 10-minute cadence absorbs this;
  a tighter one would not actually run more often.
* GitHub disables scheduled workflows in a repository with no activity for 60
  days. The daily run commits `data/latest.json`, which keeps the repository
  active year-round and gives the standings a git history for free.

## How the tiebreakers work

Teams are separated first by conference winning percentage. Only teams on the
same percentage are tied, and a tie is resolved with that conference's own
published procedure — the two-team list when exactly two teams are involved,
the multi-team list otherwise.

When a step splits a tied group, each resulting subgroup **restarts the
procedure from step one**, dropping to the two-team list if only two teams
remain. That is the "revert to the beginning" language every conference uses,
and it is why a four-way tie can be settled by a mini round robin and then by
head-to-head inside each surviving pair.

A step that does not apply yet — no common opponents, a poll that has not been
published — is skipped. A step that *cannot* be computed from public data
stops the procedure and the tie is reported as **unresolved**:

* The ACC, Big Ten and MAC all reach a **SportSource Analytics** rating that
  is not published publicly.
* Most procedures end in a **commissioner's draw**.

Those ties are flagged on the site rather than decided by a step the
conference itself would never reach. Guessing there would be worse than
saying so.

The rules live in [`data/rules/2026/`](data/rules/2026), one JSON file per
conference, each carrying its sources, a `verified_on` date and a
`confidence` rating. [`TIEBREAKERS.md`](TIEBREAKERS.md) renders all of them in
readable form and is regenerated from the JSON (CI fails if it drifts). Correcting a rule is a JSON edit — no code change — and
`scripts/check_rules.py` (run in CI) rejects unknown steps, missing labels and
procedures that do not end in a draw or an unavailable metric.

Confidence today: `high` for the SEC, Big Ten, Big 12 and MAC; `medium` for
the ACC, American, Mountain West, Pac-12 and Sun Belt; **`low` for Conference
USA**, whose official policy is published only as a PDF and is modelled here
on the American's. Re-check that one before relying on it in November.

## Data

Everything comes from the same public endpoints espn.com itself calls; no key
is needed.

* `sports.core.api.espn.com` group tree → conference and division membership
  for the season. Membership is read from ESPN every run rather than
  hard-coded, so realignment needs no code change.
* `site.api.espn.com/.../scoreboard` → every game.
* `site.api.espn.com/.../rankings` → AP and CFP polls, used both for display
  and for the conferences whose procedures cite the CFP ranking.

One quirk shapes the whole ingest: **the scoreboard returns at most 25 events
per response and ignores `limit`**, so a Saturday cannot be read in one call —
asking for the whole FBS group week by week quietly returns about a third of
the season and leaves every conference record wrong. It does honour `groups`,
and a group filter matches a game when *either* team belongs to it, so the
sweep runs conference by conference: that covers non-conference games too and
keeps each response comfortably under the cap. If a response ever does hit 25
it is re-read a day at a time, using the week's span from ESPN's own calendar,
and the results merged.

The sweep stops two weeks past the current one — past weeks are settled,
future weeks hold nothing but kickoff times — and only the week in play
bypasses the response cache, so a Saturday refresh is a small number of live
requests rather than a re-read of the season.

A game counts toward the conference standings when both teams are in the same
conference, which is computed here rather than taken from ESPN's own flag —
that way Notre Dame's ACC games stay non-conference where they belong.

## Running it locally

Python 3.11+, no dependencies.

```bash
PYTHONPATH=src python -m cfb build --out site          # fetch and render
PYTHONPATH=src python -m cfb probe                     # check ESPN parsing
PYTHONPATH=src python -m cfb fetch --out data/season.json

# build from a saved season, no network needed
PYTHONPATH=src python -m cfb --season-file data/season.json build --out site

# tests (no network)
cd tests && python -m unittest discover -p "test_*.py"
python scripts/check_rules.py
```

`scripts/make_fixture.py` writes a synthetic season with the real conference
shapes, which is what the tests and the CI build run against.

## Publishing

The site deploys to GitHub Pages from the workflow artifact — nothing is
committed except the daily data snapshot. Set **Settings → Pages → Source**
to **GitHub Actions** once, and the schedule takes it from there.

## Layout

```
src/cfb/
  espn.py       ESPN ingest: conferences, teams, games, polls
  model.py      Team / Game / Conference / Season
  standings.py  win-loss bookkeeping and placement grouping
  tiebreak.py   the step engine - every tiebreaker step lives here
  rules.py      loading the per-conference rule files
  report.py     resolved standings, championship projection, notes
  render.py     static HTML/CSS/JS output
  cli.py        build / fetch / probe
data/rules/2026/  one JSON procedure per conference, with sources
web/              stylesheet and the small client-side script
tests/            tiebreaker and end-to-end tests
```
