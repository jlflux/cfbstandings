"""Validate the tiebreaker rule files.

Run in CI so a typo in a rule file fails loudly instead of silently turning
into a skipped step at 2am on a Saturday.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cfb.tiebreak import STEPS  # noqa: E402

RULES_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "rules")
REQUIRED = {"slug", "conference", "structure", "confidence", "two_team"}
STRUCTURES = {"single_table", "divisions", "no_championship"}
CONFIDENCE = {"high", "medium", "low", "none"}
TERMINAL = {"draw", "unavailable_metric"}


def check_file(path: str) -> list[str]:
    problems = []
    with open(path, encoding="utf-8") as fh:
        try:
            rules = json.load(fh)
        except ValueError as exc:
            return [f"{path}: invalid JSON: {exc}"]

    name = os.path.basename(path)
    missing = REQUIRED - set(rules)
    if missing:
        problems.append(f"{name}: missing {sorted(missing)}")
    if rules.get("structure") not in STRUCTURES:
        problems.append(f"{name}: unknown structure {rules.get('structure')!r}")
    if rules.get("confidence") not in CONFIDENCE:
        problems.append(f"{name}: unknown confidence {rules.get('confidence')!r}")
    if rules.get("slug") and rules["slug"] != name[:-5]:
        problems.append(f"{name}: slug {rules['slug']!r} does not match the filename")

    for key in ("two_team", "multi_team"):
        steps = rules.get(key)
        if steps is None:
            continue
        if not steps:
            problems.append(f"{name}: {key} is empty")
            continue
        for index, step in enumerate(steps):
            step_name = step.get("step")
            if step_name not in STEPS:
                problems.append(f"{name}: {key}[{index}] unknown step {step_name!r}")
            if not step.get("label"):
                problems.append(f"{name}: {key}[{index}] has no label")
            if not isinstance(step.get("params", {}), dict):
                problems.append(f"{name}: {key}[{index}] params is not an object")
        last = steps[-1].get("step")
        if last not in TERMINAL and rules.get("structure") != "no_championship":
            problems.append(
                f"{name}: {key} ends with {last!r}; a procedure should end in a "
                f"draw or an unavailable metric so an unbreakable tie is reported, not hidden"
            )
    needs_sources = (
        rules.get("confidence") in {"high", "medium"}
        and rules.get("structure") != "no_championship"
    )
    if needs_sources and not rules.get("sources"):
        problems.append(f"{name}: confidence {rules['confidence']} but no sources listed")
    return problems


def main() -> int:
    problems: list[str] = []
    checked = 0
    for season in sorted(os.listdir(RULES_DIR)):
        directory = os.path.join(RULES_DIR, season)
        if not os.path.isdir(directory):
            continue
        for filename in sorted(os.listdir(directory)):
            if filename.endswith(".json"):
                problems.extend(check_file(os.path.join(directory, filename)))
                checked += 1
    if problems:
        print("\n".join(problems))
        print(f"\n{len(problems)} problem(s) across {checked} rule file(s)")
        return 1
    print(f"{checked} rule files OK; steps implemented: {', '.join(sorted(STEPS))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
