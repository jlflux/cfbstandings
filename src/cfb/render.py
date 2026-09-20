"""Static site generation.

Plain string templating on purpose: no template engine, no build step, and
the output is a handful of files that can be served from GitHub Pages.
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


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _fmt_pct(value: float) -> str:
    return f"{value:.3f}".lstrip("0") or ".000"


def _kickoff_label(iso: str) -> str:
    if not iso:
        return ""
    try:
        moment = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso[:10]
    return moment.strftime("%b %-d")


def _game_cell(game: dict[str, Any] | None, upcoming: bool = False) -> str:
    if not game:
        return '<span class="muted">—</span>'
    opponent = esc(game["opponent"])
    prefix = "" if game.get("neutral") else ("" if game.get("home") else "@ ")
    if upcoming:
        when = _kickoff_label(game.get("date", ""))
        tv = f' <span class="tv">{esc(game["broadcast"])}</span>' if game.get("broadcast") else ""
        return f'<span class="opp">{prefix}{opponent}</span> <span class="when">{when}</span>{tv}'
    result = game.get("result") or ""
    css = {"W": "win", "L": "loss"}.get(result, "tie")
    score = f'{game.get("score_for")}-{game.get("score_against")}'
    return (
        f'<span class="res {css}">{esc(result)}</span> '
        f'<span class="score">{esc(score)}</span> '
        f'<span class="opp">{prefix}{opponent}</span>'
    )


def _team_cell(row: dict[str, Any]) -> str:
    rank = f'<span class="rank">{row["rank"]}</span>' if row.get("rank") else ""
    logo = (
        f'<img class="logo" src="{esc(row["logo"])}" alt="" loading="lazy" width="20" height="20">'
        if row.get("logo") else '<span class="logo placeholder"></span>'
    )
    berth = ""
    if row.get("berth") == "Championship game":
        berth = '<span class="berth" title="In the projected championship game">◆</span>'
    elif row.get("berth") == "In contention":
        berth = '<span class="berth contested" title="Tied for a championship-game berth">◇</span>'
    elif row.get("berth") == "Division leader":
        berth = '<span class="berth" title="Division leader">◆</span>'
    tied = ""
    if row.get("tied_with"):
        tied = '<span class="tied-flag" title="Tie not resolved by the published procedure">T</span>'
    return f'{logo}{rank}<span class="team-name">{esc(row["name"])}</span>{berth}{tied}'


def _standings_table(block: dict[str, Any], show_title: bool) -> str:
    title = f'<h3 class="block-title">{esc(block["title"])}</h3>' if show_title else ""
    rows = []
    for row in block["rows"]:
        rows.append(
            "<tr>"
            f'<td class="pos">{row["position"]}</td>'
            f'<td class="team">{_team_cell(row)}</td>'
            f'<td class="num">{esc(row["conf_record"])}</td>'
            f'<td class="num pct">{_fmt_pct(row["conf_pct"])}</td>'
            f'<td class="num">{esc(row["overall_record"])}</td>'
            f'<td class="num hide-sm">{row["conf_pf"]}</td>'
            f'<td class="num hide-sm">{row["conf_pa"]}</td>'
            f'<td class="num hide-sm">{esc(row["streak"])}</td>'
            f'<td class="game">{_game_cell(row.get("last_game"))}</td>'
            f'<td class="game hide-sm">{_game_cell(row.get("next_game"), upcoming=True)}</td>'
            "</tr>"
        )
    return f"""{title}
<div class="table-wrap">
<table class="standings">
  <thead>
    <tr>
      <th class="pos">#</th><th class="team">Team</th>
      <th class="num">Conf</th><th class="num">Pct</th><th class="num">Overall</th>
      <th class="num hide-sm">PF</th><th class="num hide-sm">PA</th><th class="num hide-sm">Strk</th>
      <th class="game">Last</th><th class="game hide-sm">Next</th>
    </tr>
  </thead>
  <tbody>
    {''.join(rows)}
  </tbody>
</table>
</div>"""


def _championship_line(report: dict[str, Any]) -> str:
    champ = report.get("championship") or {}
    teams = champ.get("teams") or []
    if not teams:
        return ""
    if champ.get("format") == "division champions":
        parts = []
        for entry in teams:
            mark = " (contested)" if entry.get("contested") else ""
            parts.append(f'{esc(entry["division"])}: <b>{esc(entry["team"])}</b>{mark}')
        body = " &nbsp;·&nbsp; ".join(parts)
    else:
        names = " vs. ".join(f'<b>{esc(t["team"])}</b>' for t in teams)
        body = names + (" — berths still contested" if champ.get("contested") else "")
    return f'<p class="champ"><span class="champ-label">Championship game</span> {body}</p>'


def _notes_block(report: dict[str, Any]) -> str:
    notes = report.get("notes") or []
    if not notes:
        return ""
    items = []
    for note in notes:
        tied = ", ".join(esc(t) for t in note["tied"])
        detail_rows = "".join(
            f'<li><b>{esc(team)}</b>: {esc(value)}</li>'
            for team, value in (note.get("details") or {}).items()
        )
        if note["resolved"]:
            outcome = " &rarr; ".join(
                " / ".join(esc(t) for t in level) for level in note["outcome"]
            )
            body = (
                f'<div class="note-head"><span class="badge ok">resolved</span> '
                f'{tied} tied at {esc(note["at_record"])}</div>'
                f'<div class="note-step">{esc(note["step_label"])} — {esc(note["summary"])}</div>'
                f'<div class="note-outcome">{outcome}</div>'
            )
        else:
            body = (
                f'<div class="note-head"><span class="badge warn">unresolved</span> '
                f'{tied} tied at {esc(note["at_record"])}</div>'
                f'<div class="note-step">{esc(note["summary"])}</div>'
            )
        extra = f'<ul class="note-detail">{detail_rows}</ul>' if detail_rows else ""
        items.append(f'<li class="note">{body}{extra}</li>')
    return (
        '<details class="notes"><summary>Tiebreakers applied '
        f'({len(notes)})</summary><ul>{"".join(items)}</ul></details>'
    )


def _rules_footer(report: dict[str, Any]) -> str:
    confidence = report.get("confidence", "none")
    sources = "".join(
        f'<a href="{esc(url)}" rel="noopener">source {i + 1}</a>'
        for i, url in enumerate(report.get("sources") or [])
    )
    verified = f' · verified {esc(report["verified_on"])}' if report.get("verified_on") else ""
    return (
        '<details class="rules"><summary>Tiebreaker procedure</summary>'
        f'<p class="conf-badge {esc(confidence)}">{esc(CONFIDENCE_LABEL.get(confidence, ""))}{verified}</p>'
        f'<p>{esc(report.get("rules_notes", ""))}</p>'
        f'<p class="sources">{sources}</p></details>'
    )


def _conference_section(report: dict[str, Any]) -> str:
    blocks = "".join(
        _standings_table(block, show_title=len(report["blocks"]) > 1)
        for block in report["blocks"]
    )
    flag = '<span class="unresolved-flag" title="At least one tie could not be resolved from public data">!</span>' if report.get("unresolved") else ""
    return f"""<section class="conference" id="{esc(report['slug'])}">
  <header class="conf-header">
    <h2>{esc(report['name'])}{flag}</h2>
    {_championship_line(report)}
  </header>
  {blocks}
  {_notes_block(report)}
  {_rules_footer(report)}
</section>"""


def _nav(active: str, conferences: list[dict[str, Any]]) -> str:
    links = "".join(
        f'<a href="#{esc(c["slug"])}">{esc(c["short_name"] or c["name"])}</a>'
        for c in conferences
    )
    pages = "".join(
        f'<a class="{"active" if page == active else ""}" href="{href}">{label}</a>'
        for page, href, label in (
            ("standings", "index.html", "Standings"),
            ("scores", "scores.html", "Scores"),
            ("tiebreakers", "tiebreakers.html", "Tiebreakers"),
        )
    )
    return f"""<nav class="pages">{pages}</nav>
<nav class="jump">{links}</nav>"""


def _page(title: str, report: dict[str, Any], active: str, body: str) -> str:
    generated = report.get("generated_at", "")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="College football conference standings with every published tiebreaker applied, updated from ESPN.">
<link rel="stylesheet" href="style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏈</text></svg>">
</head>
<body>
<header class="site">
  <div class="wrap">
    <h1><a href="index.html">CFB Standings</a></h1>
    <p class="sub">{esc(report['season'])} season · Week {esc(report['week'])} ·
      <time datetime="{esc(generated)}" class="updated" data-utc="{esc(generated)}">updated {esc(generated)}</time></p>
    {_nav(active, report['conferences'])}
  </div>
</header>
<main class="wrap">
{body}
</main>
<footer class="site">
  <div class="wrap">
    <p>Scores and team data from ESPN's public endpoints. Standings and tiebreakers computed here;
       ties the published procedure cannot settle from public data are flagged rather than guessed.</p>
    <p><a href="data.json">data.json</a> · <a href="https://github.com/jlflux/cfbstandings">source</a></p>
  </div>
</footer>
<script src="app.js"></script>
</body>
</html>
"""


def render_standings(report: dict[str, Any]) -> str:
    sections = "".join(_conference_section(c) for c in report["conferences"])
    legend = """<p class="legend">
      <span class="berth">◆</span> projected championship-game berth ·
      <span class="berth contested">◇</span> berth still contested ·
      <span class="tied-flag">T</span> tie the published procedure could not resolve
    </p>"""
    return _page(
        f"{report['season']} College Football Standings",
        report,
        "standings",
        legend + sections,
    )


def render_scores(report: dict[str, Any]) -> str:
    chunks = []
    for week in report.get("scoreboard", []):
        label = "Bowls / Championships" if week["season_type"] == 3 else f"Week {week['week']}"
        games = []
        for game in week["games"]:
            state_css = {"in": "live", "post": "final", "pre": "upcoming"}.get(game["state"], "")
            status = game["status"] or ""
            conf = f'<span class="conf-tag">{esc(game["conference"])}</span>' if game["conference"] else ""
            rows = []
            for side in ("away", "home"):
                team = game[side]
                winner = (
                    game["completed"]
                    and team["score"] is not None
                    and game["home"]["score"] is not None
                    and game["away"]["score"] is not None
                    and team["score"] > game["home" if side == "away" else "away"]["score"]
                )
                rank = f'<span class="rank">{team["rank"]}</span>' if team.get("rank") else ""
                logo = f'<img class="logo" src="{esc(team["logo"])}" alt="" loading="lazy" width="18" height="18">' if team["logo"] else ""
                score = "" if team["score"] is None else esc(team["score"])
                rows.append(
                    f'<div class="side {"winner" if winner else ""}">{logo}{rank}'
                    f'<span class="nm">{esc(team["name"])}</span>'
                    f'<span class="sc">{score}</span></div>'
                )
            games.append(
                f'<article class="game {state_css}">{"".join(rows)}'
                f'<div class="meta"><span class="status">{esc(status)}</span>{conf}</div></article>'
            )
        chunks.append(f'<section class="scores"><h2>{esc(label)}</h2><div class="grid">{"".join(games)}</div></section>')
    return _page(f"{report['season']} College Football Scores", report, "scores", "".join(chunks))


def render_tiebreakers(report: dict[str, Any]) -> str:
    sections = []
    for conf in report["conferences"]:
        sources = "".join(
            f'<li><a href="{esc(u)}" rel="noopener">{esc(u)}</a></li>'
            for u in conf.get("sources") or []
        )
        sections.append(
            f'<section class="conference" id="rules-{esc(conf["slug"])}">'
            f'<h2>{esc(conf["name"])}</h2>'
            f'<p class="conf-badge {esc(conf["confidence"])}">'
            f'{esc(CONFIDENCE_LABEL.get(conf["confidence"], ""))}'
            f'{" · verified " + esc(conf["verified_on"]) if conf.get("verified_on") else ""}</p>'
            f'<p>{esc(conf.get("rules_notes", ""))}</p>'
            f'<ul class="src">{sources}</ul></section>'
        )
    intro = """<section class="intro">
      <h2>How ties are broken here</h2>
      <p>Teams are separated first by conference winning percentage. Only teams on the same
      percentage are tied, and a tie is resolved with the conference's own published procedure:
      the two-team list when exactly two teams are involved, the multi-team list otherwise.</p>
      <p>When a step splits a tied group, each resulting subgroup restarts the procedure from
      step one — dropping to the two-team list if only two teams remain. That is the
      "revert to the beginning" language every conference uses.</p>
      <p>A step that simply does not apply (no common opponents yet, poll not published) is
      skipped. A step that <em>cannot</em> be computed from public data — a proprietary analytics
      rating, or a commissioner's draw — stops the procedure, and the tie is reported as
      unresolved rather than being decided by a step the conference would never reach.</p>
    </section>"""
    return _page(
        f"{report['season']} Conference Tiebreaker Procedures", report, "tiebreakers",
        intro + "".join(sections),
    )


def write_site(report: dict[str, Any], out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    written = []

    pages = {
        "index.html": render_standings(report),
        "scores.html": render_scores(report),
        "tiebreakers.html": render_tiebreakers(report),
    }
    for name, content in pages.items():
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
