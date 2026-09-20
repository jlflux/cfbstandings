"""Generate TIEBREAKERS.md from the rule files, so the docs cannot drift."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cfb.tiebreak import STEPS  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
SEASON = "2026"
TERMINAL = {"draw", "unavailable_metric"}

CONFIDENCE = {
    "high": "Verified against the conference's own published procedure.",
    "medium": "Based on reporting of the conference's published procedure.",
    "low": "Best-effort reconstruction — re-check before relying on it.",
    "none": "No published procedure on file.",
}

ORDER = ["acc", "big-ten", "big-12", "sec", "american", "conference-usa",
         "mac", "mountain-west", "pac-12", "sun-belt", "independents"]


def load():
    directory = os.path.join(ROOT, "data", "rules", SEASON)
    rules = []
    for filename in sorted(os.listdir(directory)):
        if filename.endswith(".json"):
            with open(os.path.join(directory, filename), encoding="utf-8") as fh:
                rules.append(json.load(fh))
    rules.sort(key=lambda r: ORDER.index(r["slug"]) if r["slug"] in ORDER else 99)
    return rules


def steps_table(steps):
    lines = []
    for index, step in enumerate(steps, start=1):
        note = ""
        if step["step"] == "unavailable_metric":
            note = " *(not public — the tie is reported unresolved here)*"
        elif step["step"] == "draw":
            note = " *(not computable — the tie is reported unresolved here)*"
        lines.append(f"{index}. {step['label']}{note}")
    return "\n".join(lines)


def main() -> int:
    out = [
        "# Conference tiebreaker procedures",
        "",
        "Generated from `data/rules/2026/` by `scripts/render_rules_doc.py` —",
        "edit the JSON, not this file.",
        "",
        "Teams are separated first by conference winning percentage. Only teams on",
        "the same percentage are tied. A two-team tie uses the two-team list; three",
        "or more teams use the multi-team list. When a step splits a tied group,",
        "each subgroup restarts the procedure from step one, dropping to the",
        "two-team list once only two teams remain.",
        "",
        "A step that does not apply yet is skipped. A step that cannot be computed",
        "from public data stops the procedure, and the tie is reported as unresolved",
        "rather than being decided by a step the conference would never reach.",
        "",
    ]
    for rules in load():
        out.append(f"## {rules['conference']}")
        out.append("")
        out.append(
            f"*{CONFIDENCE.get(rules['confidence'], '')}*"
            + (f" Verified {rules['verified_on']}." if rules.get("verified_on") else "")
        )
        out.append("")
        structure = {
            "single_table": "One table; the top two meet in the championship game.",
            "divisions": "Two divisions; the division champions meet in the championship game.",
            "no_championship": "No conference schedule and no championship game.",
        }.get(rules["structure"], rules["structure"])
        out.append(structure)
        out.append("")
        if rules.get("notes"):
            out.append(rules["notes"])
            out.append("")
        out.append("**Two teams tied**")
        out.append("")
        out.append(steps_table(rules["two_team"]))
        out.append("")
        multi = rules.get("multi_team")
        if multi and multi != rules["two_team"]:
            out.append("**Three or more teams tied**")
            out.append("")
            out.append(steps_table(multi))
            out.append("")
        if rules.get("sources"):
            out.append("Sources:")
            out.append("")
            for url in rules["sources"]:
                out.append(f"* <{url}>")
            out.append("")

    out.append("## Steps the engine implements")
    out.append("")
    for name in sorted(STEPS):
        out.append(f"* `{name}`")
    out.append("")

    path = os.path.join(ROOT, "TIEBREAKERS.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
