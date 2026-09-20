"""Static site generation.

Plain string templating on purpose: no template engine, no build step, and
the output is a handful of files any static host can serve.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import shutil
from typing import Any

WEB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web"
)

CONFIDENCE_LABEL = {
    "high": "Verified against the conference's own published procedure",
    "medium": "Based on reporting of the conference's published procedure",
    "low": "Best-effort reconstruction - re-check before relying on it",
    "none": "No published procedure on file",
}

TIER_ROWS = [("p4", "P4"), ("g5", "G5"), ("independent", "IND")]


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _pct(value: float) -> str:
    text = f"{value:.3f}"
    return text if value >= 1 else text.lstrip("0")


def _record(label: str) -> str:
    """7-1 reads as 7–1 in the table."""
    return esc(label).replace("-", "&#8211;")


def _diff(value: int) -> str:
    css = "pos" if value > 0 else ("neg" if value < 0 else "flat")
    sign = "+" if value > 0 else ""
    return f'<span class="diff {css}">{sign}{value}</span>'


def _kickoff(iso: str) -> str:
    if not iso:
        return ""
    try:
        moment = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso[:10]
    return moment.strftime("%b %-d")


# --------------------------------------------------------------------------
# standings table
# --------------------------------------------------------------------------
def _badges(row: dict[str, Any]) -> str:
    out = []
    if row.get("berth") in ("Championship game", "Division leader"):
        out.append('<span class="tag ccg" title="In the projected championship game">CCG</span>')
    elif row.get("berth") == "In contention":
        out.append('<span class="tag hold" title="Tied for a championship-game berth">CCG?</span>')
    if row.get("tied_with"):
        out.append(
            '<span class="tag tied" title="Tie the published procedure cannot '
            'settle from public data">TIED</span>'
        )
    return "".join(out)


def _game_log(row: dict[str, Any]) -> str:
    games = row.get("conf_games") or []
    if not games:
        return '<p class="log-empty">No conference games played yet.</p>'
    items = []
    for game in games:
        if game.get("completed"):
            result = game.get("result") or ""
            css = {"W": "win", "L": "loss"}.get(result, "tie")
            score = f'{game.get("score_for")}&#8211;{game.get("score_against")}'
            right = f'<span class="lg-res {css}">{esc(result)}</span><span class="lg-score">{score}</span>'
        else:
            right = f'<span class="lg-when">{esc(_kickoff(game.get("date", "")))}</span>'
        where = "" if game.get("neutral") else ("vs " if game.get("home") else "at ")
        items.append(
            f'<li><span class="lg-opp">{where}{esc(game["opponent"])}</span>{right}</li>'
        )
    return f'<ul class="log">{"".join(items)}</ul>'


def _row(row: dict[str, Any], index: int) -> str:
    share = max(0.0, min(1.0, row.get("conf_pct", 0.0))) * 100
    rank = f'<span class="ap">{row["rank"]}</span>' if row.get("rank") else ""
    detail_id = f'g-{esc(row["team_id"])}'
    return f"""<tr class="team-row">
  <td class="pos">{row["position"]}</td>
  <td class="team">
    <button class="team-toggle" type="button" aria-expanded="false" aria-controls="{detail_id}">
      {rank}<span class="name">{esc(row["name"])}</span>{_badges(row)}<span class="caret" aria-hidden="true">&#9654;</span>
    </button>
    <div class="subline">&#8627; opponents' conf win% &middot;
      <b>{_pct(row.get("opp_conf_pct", 0.0))}</b>
      ({_record(row.get("opp_conf_record", "0-0"))})</div>
  </td>
  <td class="share">
    <div class="bar"><span style="width:{share:.1f}%"></span></div>
    <div class="bar-foot"><span>{_record(row["conf_record"])}</span><span>{_pct(row.get("conf_pct", 0.0))}</span></div>
  </td>
  <td class="conf">{_record(row["conf_record"])}</td>
  <td class="overall">{_record(row["overall_record"])}</td>
  <td class="gb">{esc(row.get("games_back", "&mdash;")) if row.get("games_back") != "—" else "&mdash;"}</td>
  <td class="dif">{_diff(row.get("conf_diff", 0))}</td>
</tr>
<tr class="detail" id="{detail_id}" hidden>
  <td colspan="7">{_game_log(row)}</td>
</tr>"""


def _table(block: dict[str, Any], show_title: bool) -> str:
    title = (
        f'<h3 class="block-title">{esc(block["title"])}</h3>' if show_title else ""
    )
    rows = "".join(_row(row, index) for index, row in enumerate(block["rows"]))
    return f"""{title}
<div class="table-wrap">
<table class="standings">
  <thead><tr>
    <th class="pos">#</th>
    <th class="team">Team</th>
    <th class="share">Win share</th>
    <th class="conf">Conf</th>
    <th class="overall">Overall</th>
    <th class="gb">GB</th>
    <th class="dif">Diff</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>
</div>"""


def _notes(report: dict[str, Any]) -> str:
    notes = report.get("notes") or []
    if not notes:
        return ""
    items = []
    for note in notes:
        tied = ", ".join(esc(t) for t in note["tied"])
        detail = "".join(
            f'<li><b>{esc(team)}</b><span>{esc(value)}</span></li>'
            for team, value in (note.get("details") or {}).items()
        )
        if note["resolved"]:
            outcome = " &rarr; ".join(
                " / ".join(esc(t) for t in level) for level in note["outcome"]
            )
            head = (
                f'<span class="badge ok">broken</span>{tied} '
                f'<span class="at">tied at {_record(note["at_record"])}</span>'
            )
            body = (
                f'<div class="note-step">{esc(note["step_label"])}</div>'
                f'<div class="note-out">{outcome}</div>'
            )
        else:
            head = (
                f'<span class="badge warn">unbroken</span>{tied} '
                f'<span class="at">tied at {_record(note["at_record"])}</span>'
            )
            body = f'<div class="note-step">{esc(note["summary"])}</div>'
        extra = f'<ul class="note-detail">{detail}</ul>' if detail else ""
        items.append(f'<li class="note"><div class="note-head">{head}</div>{body}{extra}</li>')
    return (
        f'<details class="panel notes"><summary>How the ties broke '
        f'<span class="count">{len(notes)}</span></summary>'
        f'<ul>{"".join(items)}</ul></details>'
    )


def _rules(report: dict[str, Any]) -> str:
    confidence = report.get("confidence", "none")
    sources = "".join(
        f'<a href="{esc(url)}" rel="noopener">source {i + 1}</a>'
        for i, url in enumerate(report.get("sources") or [])
    )
    verified = f' &middot; verified {esc(report["verified_on"])}' if report.get("verified_on") else ""
    return (
        '<details class="panel rules"><summary>Tiebreaker procedure</summary>'
        f'<p class="conf-badge {esc(confidence)}">'
        f'{esc(CONFIDENCE_LABEL.get(confidence, ""))}{verified}</p>'
        f'<p class="rules-note">{esc(report.get("rules_notes", ""))}</p>'
        f'<p class="sources">{sources}</p></details>'
    )


def _champ_line(report: dict[str, Any]) -> str:
    champ = report.get("championship") or {}
    teams = champ.get("teams") or []
    if not teams:
        return ""
    if champ.get("format") == "division champions":
        body = " &nbsp;&middot;&nbsp; ".join(
            f'<span class="dv">{esc(t["division"])}</span> <b>{esc(t["team"])}</b>'
            + (" <i>contested</i>" if t.get("contested") else "")
            for t in teams
        )
    else:
        body = " <span class='vs'>vs</span> ".join(f'<b>{esc(t["team"])}</b>' for t in teams)
        if champ.get("contested"):
            body += " <i>berths contested</i>"
    return f'<p class="champ"><span class="champ-tag">Title game</span>{body}</p>'


def _league(report: dict[str, Any], active: bool) -> str:
    blocks = "".join(
        _table(block, show_title=len(report["blocks"]) > 1) for block in report["blocks"]
    )
    tier = esc((report.get("tier_label") or "").upper())
    meta = (
        (f'<b>{tier}</b> &middot; ' if tier else "")
        + f'{report.get("team_count", 0)} teams &middot; '
        + esc(report.get("format_label", ""))
    )
    return f"""<section class="league{' is-active' if active else ''}" id="{esc(report['slug'])}"
         data-slug="{esc(report['slug'])}" style="--accent:{esc(report.get('accent', '#e5b93c'))}">
  <header class="league-head">
    <div>
      <h2>{esc(report['name'])}</h2>
      <p class="league-meta">{meta}</p>
    </div>
    {_champ_line(report)}
  </header>
  {blocks}
  {_notes(report)}
  {_rules(report)}
</section>"""


# --------------------------------------------------------------------------
# page shell
# --------------------------------------------------------------------------
def _pills(report: dict[str, Any], active: str) -> str:
    rows = []
    for tier, label in TIER_ROWS:
        members = [c for c in report["conferences"] if c.get("tier") == tier]
        if not members:
            continue
        pills = "".join(
            f'<button class="pill{" on" if c["slug"] == active else ""}" type="button"'
            f' data-slug="{esc(c["slug"])}" style="--accent:{esc(c.get("accent", "#e5b93c"))}">'
            f'<i class="dot"></i>{esc(c["short_name"] or c["name"])}</button>'
            for c in members
        )
        rows.append(
            f'<div class="tier-row"><span class="tier-label">{label}</span>'
            f'<div class="pills">{pills}</div></div>'
        )
    return f'<nav class="leagues">{"".join(rows)}</nav>'


def _masthead(report: dict[str, Any], page: str, lede: str) -> str:
    generated = report.get("generated_at", "")
    nav = "".join(
        f'<a class="{"on" if key == page else ""}" href="{href}">{label}</a>'
        for key, href, label in (
            ("standings", "index.html", "Standings"),
            ("scores", "scores.html", "Scores"),
            ("tiebreakers", "tiebreakers.html", "Tiebreakers"),
        )
    )
    return f"""<header class="masthead">
  <p class="eyebrow">The Press Box &middot; College Football</p>
  <h1><span class="yr">{esc(report['season'])} FBS</span><span class="ttl">Conference Standings</span></h1>
  <p class="lede">{lede}</p>
  <p class="stat">
    <b>{report.get('league_count', 0)}</b> <span>FBS leagues</span>
    <em>&middot;</em> <b>{esc(report['season'])}</b> <span>{esc(report.get('season_label', ''))}</span>
    <em>&middot;</em> <b>{report.get('conference_games_played', 0)}</b> <span>conference games played</span>
  </p>
  <p class="stamp">
    <time datetime="{esc(generated)}" data-utc="{esc(generated)}">updated {esc(generated)}</time>
    &middot; live from ESPN
  </p>
  <nav class="pages">{nav}</nav>
</header>"""


def _page(title: str, report: dict[str, Any], page: str, lede: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="College football conference standings with every published tiebreaker applied, rebuilt from ESPN.">
<meta name="color-scheme" content="dark">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏈</text></svg>">
</head>
<body>
<div class="page">
{_masthead(report, page, lede)}
{body}
<footer class="foot">
  <p>Scores and team data from ESPN's public endpoints. Standings and tiebreakers are
     computed here; a tie the published procedure cannot settle from public data is
     flagged rather than guessed.</p>
  <p><a href="data.json">data.json</a> &middot;
     <a href="https://github.com/jlflux/cfbstandings">source</a></p>
</footer>
</div>
<script src="app.js"></script>
</body>
</html>
"""


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------
def render_standings(report: dict[str, Any]) -> str:
    conferences = report["conferences"]
    active = conferences[0]["slug"] if conferences else ""
    leagues = "".join(_league(c, c["slug"] == active) for c in conferences)
    body = _pills(report, active) + f'<div class="leagues-body">{leagues}</div>'
    return _page(
        f"{report['season']} FBS Conference Standings",
        report,
        "standings",
        "Where every league actually stands &mdash; read the race at a glance, "
        "and see exactly how each tie breaks.",
        body,
    )


def render_scores(report: dict[str, Any]) -> str:
    chunks = []
    for week in report.get("scoreboard", []):
        label = "Bowls &amp; championships" if week["season_type"] == 3 else f"Week {week['week']}"
        cards = []
        for game in week["games"]:
            state = {"in": "live", "post": "final", "pre": "soon"}.get(game["state"], "")
            sides = []
            for side in ("away", "home"):
                team = game[side]
                other = game["home" if side == "away" else "away"]
                won = (
                    game["completed"]
                    and team["score"] is not None
                    and other["score"] is not None
                    and team["score"] > other["score"]
                )
                rank = f'<span class="ap">{team["rank"]}</span>' if team.get("rank") else ""
                logo = (
                    f'<img class="logo" src="{esc(team["logo"])}" alt="" loading="lazy" width="18" height="18">'
                    if team["logo"] else '<span class="logo"></span>'
                )
                score = "" if team["score"] is None else esc(team["score"])
                sides.append(
                    f'<div class="side{" won" if won else ""}">{logo}{rank}'
                    f'<span class="nm">{esc(team["name"])}</span>'
                    f'<span class="sc">{score}</span></div>'
                )
            tag = f'<span class="cf">{esc(game["conference"])}</span>' if game["conference"] else ""
            cards.append(
                f'<article class="game {state}">{"".join(sides)}'
                f'<div class="meta"><span class="status">{esc(game["status"])}</span>{tag}</div></article>'
            )
        chunks.append(
            f'<section class="scores"><h2>{label}</h2><div class="grid">{"".join(cards)}</div></section>'
        )
    return _page(
        f"{report['season']} College Football Scores",
        report,
        "scores",
        "Every FBS result, refreshed through Saturday night.",
        "".join(chunks),
    )


def render_tiebreakers(report: dict[str, Any]) -> str:
    sections = []
    for conf in report["conferences"]:
        sources = "".join(
            f'<li><a href="{esc(u)}" rel="noopener">{esc(u)}</a></li>'
            for u in conf.get("sources") or []
        )
        sections.append(
            f'<section class="league is-active rulecard" style="--accent:{esc(conf.get("accent", "#e5b93c"))}">'
            f'<header class="league-head"><div><h2>{esc(conf["name"])}</h2>'
            f'<p class="league-meta">{esc((conf.get("tier_label") or "").upper())} &middot; '
            f'{esc(conf.get("format_label", ""))}</p></div></header>'
            f'<p class="conf-badge {esc(conf["confidence"])}">'
            f'{esc(CONFIDENCE_LABEL.get(conf["confidence"], ""))}'
            f'{" &middot; verified " + esc(conf["verified_on"]) if conf.get("verified_on") else ""}</p>'
            f'<p class="rules-note">{esc(conf.get("rules_notes", ""))}</p>'
            f'<ul class="src">{sources}</ul></section>'
        )
    intro = """<section class="league is-active rulecard intro">
      <header class="league-head"><div><h2>How ties are broken here</h2></div></header>
      <p class="rules-note">Teams are separated first by conference winning percentage. Only teams
      on the same percentage are tied, and a tie is resolved with the conference's own published
      procedure &mdash; the two-team list when exactly two teams are involved, the multi-team list
      otherwise.</p>
      <p class="rules-note">When a step splits a tied group, each subgroup restarts the procedure
      from step one, dropping to the two-team list if only two teams remain. That is the
      &ldquo;revert to the beginning&rdquo; language every conference uses.</p>
      <p class="rules-note">A step that does not apply yet is skipped. A step that
      <em>cannot</em> be computed from public data &mdash; a proprietary analytics rating, or a
      commissioner's draw &mdash; stops the procedure, and the tie is reported as unresolved
      rather than decided by a step the conference would never reach.</p>
    </section>"""
    return _page(
        f"{report['season']} Conference Tiebreaker Procedures",
        report,
        "tiebreakers",
        "The exact procedure encoded for each league, with sources.",
        intro + "".join(sections),
    )


def write_site(report: dict[str, Any], out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    written = []

    for name, content in {
        "index.html": render_standings(report),
        "scores.html": render_scores(report),
        "tiebreakers.html": render_tiebreakers(report),
    }.items():
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(path)

    data_path = os.path.join(out_dir, "data.json")
    with open(data_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, separators=(",", ":"))
    written.append(data_path)

    for asset in ("style.css", "app.js"):
        source = os.path.join(WEB_DIR, asset)
        if os.path.exists(source):
            shutil.copy(source, os.path.join(out_dir, asset))
            written.append(os.path.join(out_dir, asset))

    with open(os.path.join(out_dir, ".nojekyll"), "w") as fh:
        fh.write("")
    return written
