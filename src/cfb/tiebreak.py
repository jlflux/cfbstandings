"""Conference tiebreaker engine.

Each conference's published procedure is stored as data (``data/rules``) and
interpreted here, so a rule change is a JSON edit rather than a code change.

Shared semantics, which every published FBS procedure follows:

* Teams are first separated by conference winning percentage. Only teams on
  the same percentage are "tied".
* A two-team tie uses the conference's two-team step list; three or more
  teams use the multi-team list.
* When a step splits the tied group, each resulting subgroup **restarts the
  procedure from step one** - dropping to the two-team list if it is now down
  to two teams. That is the "revert to the beginning" language every
  conference uses.
* A step that cannot be evaluated (no common opponents, poll not published
  yet) is skipped. A step that is *inherently* unavailable to us - a
  proprietary analytics rating, or a commissioner's draw - halts the
  procedure and the tie is reported as unresolved rather than silently
  decided by a later step.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from .model import Game, Season
from .standings import Record, TeamStanding, placement_groups

log = logging.getLogger(__name__)


@dataclass
class StepOutcome:
    """What one tiebreaker step concluded about a tied group."""

    scores: dict[str, float] | None = None
    details: dict[str, str] = field(default_factory=dict)
    summary: str = ""
    halt: bool = False
    halt_reason: str = ""


@dataclass
class TiebreakNote:
    conference_id: str
    tied: list[str]
    at_record: str
    step: str
    step_label: str
    summary: str
    details: dict[str, str]
    resolved: bool
    outcome: list[list[str]] = field(default_factory=list)


@dataclass
class TieContext:
    season: Season
    table: dict[str, TeamStanding]
    conference_id: str
    pool: list[str]                  # every team in the standings pool
    scope: str = "conference"        # or "division"
    notes: list[TiebreakNote] = field(default_factory=list)

    def standing(self, team_id: str) -> TeamStanding:
        return self.table[team_id]

    def name(self, team_id: str) -> str:
        team = self.season.teams.get(team_id)
        return team.name if team else team_id


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _played(game: Game) -> bool:
    return game.completed and game.home_score is not None and game.away_score is not None


def _conf_games(ctx: TieContext, team_id: str) -> list[Game]:
    return [g for g in ctx.standing(team_id).conference_games if _played(g)]


def _conf_opponents(ctx: TieContext, team_id: str) -> list[str]:
    return [g.opponent_of(team_id) for g in _conf_games(ctx, team_id)]


def _record_vs(ctx: TieContext, team_id: str, opponents: set[str]) -> Record:
    record = Record()
    for game in _conf_games(ctx, team_id):
        if game.opponent_of(team_id) in opponents:
            record.add(game.score_for(team_id) or 0, game.score_against(team_id) or 0)
    return record


def _is_fbs(ctx: TieContext, team_id: str) -> bool:
    team = ctx.season.teams.get(team_id)
    return bool(team and team.conference_id)


def _partition(ids: list[str], scores: dict[str, float]) -> list[list[str]]:
    """Split a tied group into levels, best first."""
    buckets: dict[float, list[str]] = {}
    for team_id in ids:
        buckets.setdefault(round(scores[team_id], 9), []).append(team_id)
    return [buckets[key] for key in sorted(buckets, reverse=True)]


def _pct(record: Record) -> float:
    return record.pct


# --------------------------------------------------------------------------
# steps
# --------------------------------------------------------------------------
def step_head_to_head(ctx: TieContext, ids: list[str], params: dict) -> StepOutcome:
    mode = params.get("mode", "win_pct")
    tied = set(ids)

    if len(ids) == 2:
        a, b = ids
        meetings = [
            g for g in _conf_games(ctx, a) if g.opponent_of(a) == b
        ]
        if not meetings:
            return StepOutcome(summary="did not play")
        wins = {a: 0.0, b: 0.0}
        detail = {}
        for game in meetings:
            winner = game.winner_id()
            if winner:
                wins[winner] += 1
            for team_id in (a, b):
                detail[team_id] = _game_phrase(ctx, game, team_id)
        if wins[a] == wins[b]:
            return StepOutcome(summary="head-to-head split")
        return StepOutcome(scores=wins, details=detail, summary="head-to-head result")

    # three or more
    records = {team_id: _record_vs(ctx, team_id, tied - {team_id}) for team_id in ids}
    played_pairs = sum(r.games for r in records.values()) / 2
    full_round_robin = played_pairs == len(ids) * (len(ids) - 1) / 2
    details = {
        team_id: f"{records[team_id].label} vs tied teams" for team_id in ids
    }

    if mode == "round_robin_or_sweep" and not full_round_robin:
        # Only a team that played and beat every other tied team separates.
        sweepers = [
            t for t in ids
            if records[t].games == len(ids) - 1 and records[t].losses == 0 and records[t].wins > 0
        ]
        if len(sweepers) == 1:
            scores = {t: (1.0 if t == sweepers[0] else 0.0) for t in ids}
            return StepOutcome(
                scores=scores,
                details=details,
                summary="defeated every other tied team (incomplete round robin)",
            )
        return StepOutcome(summary="incomplete round robin among tied teams")

    if all(r.games == 0 for r in records.values()):
        return StepOutcome(summary="tied teams did not play each other")

    scores = {team_id: _pct(records[team_id]) for team_id in ids}
    return StepOutcome(scores=scores, details=details, summary="record among tied teams")


def _game_phrase(ctx: TieContext, game: Game, team_id: str) -> str:
    scored = game.score_for(team_id)
    allowed = game.score_against(team_id)
    opponent = ctx.name(game.opponent_of(team_id))
    verb = "beat" if (scored or 0) > (allowed or 0) else "lost to"
    date = (game.date or "")[:10]
    return f"{verb} {opponent} {scored}-{allowed} ({date})"


def _common_opponents(ctx: TieContext, ids: list[str]) -> set[str]:
    tied = set(ids)
    sets = [set(_conf_opponents(ctx, t)) - tied for t in ids]
    if not sets:
        return set()
    common = set.intersection(*sets)
    return common


def step_common_opponents(ctx: TieContext, ids: list[str], params: dict) -> StepOutcome:
    common = _common_opponents(ctx, ids)
    if not common:
        return StepOutcome(summary="no common conference opponents")
    records = {t: _record_vs(ctx, t, common) for t in ids}
    names = ", ".join(sorted(ctx.name(o) for o in common))
    details = {t: f"{records[t].label} vs {len(common)} common opponent(s)" for t in ids}
    return StepOutcome(
        scores={t: _pct(records[t]) for t in ids},
        details=details,
        summary=f"record vs all common conference opponents ({names})",
    )


def step_order_of_finish(ctx: TieContext, ids: list[str], params: dict) -> StepOutcome:
    """Record against the highest-placed opponent, proceeding down the standings."""
    common_only = params.get("common_only", True)
    cumulative = params.get("cumulative", False)

    tied = set(ids)
    common = _common_opponents(ctx, ids) if common_only else None
    groups = placement_groups(ctx.pool, ctx.table)

    accumulated: set[str] = set()
    for group in groups:
        candidates = set(group) - tied
        if common is not None:
            candidates &= common
        if not candidates:
            continue
        pool = (accumulated | candidates) if cumulative else candidates
        accumulated |= candidates
        records = {t: _record_vs(ctx, t, pool) for t in ids}
        if any(r.games == 0 for r in records.values()):
            continue
        scores = {t: _pct(records[t]) for t in ids}
        if len(set(round(v, 9) for v in scores.values())) == 1:
            continue
        names = ", ".join(sorted(ctx.name(o) for o in pool))
        details = {t: f"{records[t].label} vs {names}" for t in ids}
        return StepOutcome(
            scores=scores,
            details=details,
            summary=f"record vs next highest-placed common opponent(s): {names}",
        )
    return StepOutcome(summary="order-of-finish comparison did not separate the teams")


def step_conference_opponents_win_pct(ctx: TieContext, ids: list[str], params: dict) -> StepOutcome:
    exclude_tied = params.get("exclude_tied", False)
    tied = set(ids)
    scores: dict[str, float] = {}
    details: dict[str, str] = {}
    for team_id in ids:
        wins = games = 0.0
        for opponent in _conf_opponents(ctx, team_id):
            if exclude_tied and opponent in tied:
                continue
            standing = ctx.table.get(opponent)
            if standing is None:
                continue
            wins += standing.conference.wins + 0.5 * standing.conference.ties
            games += standing.conference.games
        scores[team_id] = (wins / games) if games else 0.0
        details[team_id] = f".{int(round(scores[team_id] * 1000)):03d} opponents' conference win pct"
    if len(set(round(v, 9) for v in scores.values())) == 1:
        return StepOutcome(summary="opponents' conference win pct identical")
    return StepOutcome(
        scores=scores,
        details=details,
        summary="combined conference win pct of conference opponents",
    )


def step_all_opponents_win_pct(ctx: TieContext, ids: list[str], params: dict) -> StepOutcome:
    scores: dict[str, float] = {}
    details: dict[str, str] = {}
    skipped = False
    for team_id in ids:
        wins = games = 0.0
        for game in ctx.standing(team_id).all_games:
            if not _played(game) or game.season_type != 2:
                continue
            opponent = game.opponent_of(team_id)
            if not _is_fbs(ctx, opponent):
                skipped = True
                continue
            standing = ctx.table.get(opponent)
            if standing is None:
                continue
            wins += standing.overall.wins + 0.5 * standing.overall.ties
            games += standing.overall.games
        scores[team_id] = (wins / games) if games else 0.0
        details[team_id] = f".{int(round(scores[team_id] * 1000)):03d} opponents' overall win pct"
    if len(set(round(v, 9) for v in scores.values())) == 1:
        return StepOutcome(summary="opponents' overall win pct identical")
    note = " (FBS opponents only)" if skipped else ""
    return StepOutcome(
        scores=scores,
        details=details,
        summary=f"combined overall win pct of all opponents{note}",
    )


def step_capped_scoring_margin(ctx: TieContext, ids: list[str], params: dict) -> StepOutcome:
    cap_for = params.get("cap_for", 42)
    cap_against = params.get("cap_against", 48)
    per_game = params.get("per_game", True)
    scores: dict[str, float] = {}
    details: dict[str, str] = {}
    for team_id in ids:
        total = 0
        games = 0
        for game in _conf_games(ctx, team_id):
            scored = min(game.score_for(team_id) or 0, cap_for)
            allowed = min(game.score_against(team_id) or 0, cap_against)
            total += scored - allowed
            games += 1
        value = (total / games) if (per_game and games) else float(total)
        scores[team_id] = value
        suffix = "/game" if per_game else ""
        details[team_id] = f"{value:+.2f}{suffix} capped margin"
    if len(set(round(v, 9) for v in scores.values())) == 1:
        return StepOutcome(summary="capped scoring margin identical")
    return StepOutcome(
        scores=scores,
        details=details,
        summary=(
            f"capped relative scoring margin vs conference opponents "
            f"(cap {cap_for} scored / {cap_against} allowed)"
        ),
    )


def step_overall_win_pct(ctx: TieContext, ids: list[str], params: dict) -> StepOutcome:
    scores = {t: ctx.standing(t).overall.pct for t in ids}
    details = {t: f"{ctx.standing(t).overall.label} overall" for t in ids}
    if len(set(round(v, 9) for v in scores.values())) == 1:
        return StepOutcome(summary="overall win pct identical")
    return StepOutcome(scores=scores, details=details, summary="overall winning percentage")


def step_total_wins(ctx: TieContext, ids: list[str], params: dict) -> StepOutcome:
    scores = {t: float(ctx.standing(t).overall.wins) for t in ids}
    details = {t: f"{ctx.standing(t).overall.wins} total wins" for t in ids}
    if len(set(scores.values())) == 1:
        return StepOutcome(summary="total wins identical")
    return StepOutcome(scores=scores, details=details, summary="total wins")


def step_division_record(ctx: TieContext, ids: list[str], params: dict) -> StepOutcome:
    scores = {t: ctx.standing(t).division.pct for t in ids}
    details = {t: f"{ctx.standing(t).division.label} in division" for t in ids}
    if any(ctx.standing(t).division.games == 0 for t in ids):
        return StepOutcome(summary="division records unavailable")
    if len(set(round(v, 9) for v in scores.values())) == 1:
        return StepOutcome(summary="division records identical")
    return StepOutcome(scores=scores, details=details, summary="record within division")


def step_common_nondivision(ctx: TieContext, ids: list[str], params: dict) -> StepOutcome:
    """Record vs common conference opponents from the other division."""
    tied = set(ids)
    sets = []
    for team_id in ids:
        division = (ctx.season.teams.get(team_id).division if ctx.season.teams.get(team_id) else None)
        opponents = {
            o for o in _conf_opponents(ctx, team_id)
            if o not in tied
            and (ctx.season.teams.get(o).division if ctx.season.teams.get(o) else None) != division
        }
        sets.append(opponents)
    common = set.intersection(*sets) if sets else set()
    if not common:
        return StepOutcome(summary="no common cross-division opponents")
    records = {t: _record_vs(ctx, t, common) for t in ids}
    scores = {t: _pct(records[t]) for t in ids}
    if len(set(round(v, 9) for v in scores.values())) == 1:
        return StepOutcome(summary="cross-division records identical")
    names = ", ".join(sorted(ctx.name(o) for o in common))
    return StepOutcome(
        scores=scores,
        details={t: f"{records[t].label} vs {names}" for t in ids},
        summary=f"record vs common non-division conference opponents ({names})",
    )


def step_ranking(ctx: TieContext, ids: list[str], params: dict) -> StepOutcome:
    """Highest position in a published poll (CFP committee rankings, etc.)."""
    wanted = [w.lower() for w in params.get("polls", ["cfp"])]
    table: dict[str, int] | None = None
    poll_name = ""
    for name, ranks in ctx.season.rankings.items():
        lowered = name.lower()
        if any(w in lowered for w in wanted):
            table = ranks
            poll_name = name
            break
    if not table:
        return StepOutcome(
            halt=True,
            halt_reason=f"poll not published yet ({'/'.join(params.get('polls', []))})",
            summary="ranking step could not be evaluated",
        )
    ranked = {t: table.get(t) for t in ids}
    if all(v is None for v in ranked.values()):
        return StepOutcome(summary=f"no tied team is ranked in {poll_name}")
    scores = {t: (-float(v) if v is not None else -999.0) for t, v in ranked.items()}
    details = {
        t: (f"{poll_name} #{ranked[t]}" if ranked[t] else f"unranked ({poll_name})")
        for t in ids
    }
    if len(set(scores.values())) == 1:
        return StepOutcome(summary=f"identical {poll_name} position")
    return StepOutcome(scores=scores, details=details, summary=f"highest {poll_name} position")


def step_unavailable_metric(ctx: TieContext, ids: list[str], params: dict) -> StepOutcome:
    metric = params.get("metric", "an external metric")
    return StepOutcome(
        halt=True,
        halt_reason=f"next step is {metric}, which is not publicly published",
        summary=metric,
    )


def step_draw(ctx: TieContext, ids: list[str], params: dict) -> StepOutcome:
    return StepOutcome(
        halt=True,
        halt_reason="decided by a draw administered by the commissioner",
        summary="commissioner's draw",
    )


STEPS: dict[str, Callable[[TieContext, list[str], dict], StepOutcome]] = {
    "head_to_head": step_head_to_head,
    "common_opponents": step_common_opponents,
    "order_of_finish": step_order_of_finish,
    "conference_opponents_win_pct": step_conference_opponents_win_pct,
    "all_opponents_win_pct": step_all_opponents_win_pct,
    "capped_scoring_margin": step_capped_scoring_margin,
    "overall_win_pct": step_overall_win_pct,
    "total_wins": step_total_wins,
    "division_record": step_division_record,
    "common_nondivision_opponents": step_common_nondivision,
    "ranking": step_ranking,
    "unavailable_metric": step_unavailable_metric,
    "draw": step_draw,
}


# --------------------------------------------------------------------------
# engine
# --------------------------------------------------------------------------
def _step_list(rules: dict, size: int) -> list[dict]:
    key = "two_team" if size == 2 else "multi_team"
    steps = rules.get(key) or rules.get("steps") or []
    return steps


def order_group(ctx: TieContext, ids: list[str], rules: dict) -> list[list[str]]:
    """Order one tied group, returning levels (best first).

    A level with more than one team is a tie the published procedure could not
    resolve from public data.
    """
    ids = sorted(ids, key=lambda t: ctx.name(t))
    if len(ids) <= 1:
        return [ids]

    if all(ctx.standing(t).conference.games == 0 for t in ids):
        # Nobody has played a conference game yet; there is nothing to break.
        return [ids]

    at_record = ctx.standing(ids[0]).conference.label

    for step in _step_list(rules, len(ids)):
        name = step.get("step", "")
        func = STEPS.get(name)
        if func is None:
            log.warning("unknown tiebreaker step %r in %s", name, ctx.conference_id)
            continue
        outcome = func(ctx, ids, step.get("params", {}))

        if outcome.halt:
            ctx.notes.append(
                TiebreakNote(
                    conference_id=ctx.conference_id,
                    tied=ids,
                    at_record=at_record,
                    step=name,
                    step_label=step.get("label", name),
                    summary=outcome.halt_reason,
                    details=outcome.details,
                    resolved=False,
                    outcome=[ids],
                )
            )
            return [ids]

        if outcome.scores is None:
            continue
        levels = _partition(ids, outcome.scores)
        if len(levels) == 1:
            continue

        ctx.notes.append(
            TiebreakNote(
                conference_id=ctx.conference_id,
                tied=ids,
                at_record=at_record,
                step=name,
                step_label=step.get("label", name),
                summary=outcome.summary,
                details=outcome.details,
                resolved=True,
                outcome=[list(level) for level in levels],
            )
        )

        result: list[list[str]] = []
        for level in levels:
            # Each subgroup restarts the published procedure from step one,
            # dropping to the two-team list when only two remain.
            result.extend(order_group(ctx, level, rules))
        return result

    ctx.notes.append(
        TiebreakNote(
            conference_id=ctx.conference_id,
            tied=ids,
            at_record=at_record,
            step="exhausted",
            step_label="Procedure exhausted",
            summary="every published step was applied without separating these teams",
            details={},
            resolved=False,
            outcome=[ids],
        )
    )
    return [ids]


def order_pool(
    season: Season,
    table: dict[str, TeamStanding],
    conference_id: str,
    pool: list[str],
    rules: dict,
    scope: str = "conference",
    notes: list[TiebreakNote] | None = None,
    placement_pool: list[str] | None = None,
) -> tuple[list[list[str]], list[TiebreakNote]]:
    """Order a full standings pool: win pct first, then the tiebreakers."""
    ctx = TieContext(
        season=season,
        table=table,
        conference_id=conference_id,
        pool=placement_pool if placement_pool is not None else pool,
        scope=scope,
        notes=notes if notes is not None else [],
    )
    levels: list[list[str]] = []
    for group in placement_groups(pool, table):
        levels.extend(order_group(ctx, group, rules))
    return levels, ctx.notes
