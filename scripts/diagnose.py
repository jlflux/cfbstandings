"""Round 2: how to read a full slate past the scoreboard's 25-event cap."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cfb.espn import CORE, SITE  # noqa: E402
from cfb.http import Http  # noqa: E402

http = Http(pause=0.1)
YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
CDN = "https://cdn.espn.com/core/college-football/scoreboard"


def head(label: str) -> None:
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")


head("I. cdn.espn.com core scoreboard (what espn.com itself calls)")
for params in (
    {"xhr": 1, "year": YEAR, "week": 3, "seasontype": 2, "groups": 80, "limit": 500},
    {"xhr": 1, "year": YEAR, "week": 3, "seasontype": 2, "limit": 500},
):
    try:
        payload = http.get_json(CDN, params)
        content = payload.get("content") or {}
        sb = content.get("sbData") or {}
        events = sb.get("events") or content.get("events") or []
        print(f"  {params} -> top keys={list(payload)[:6]} content keys={list(content)[:8]}")
        print(f"     events={len(events)}")
    except Exception as exc:
        print(f"  {params} -> ERROR {exc}")

head("J. per-conference scoreboard counts (is 25 ever hit?)")
groups = {"1": "ACC", "5": "Big Ten", "4": "Big 12", "8": "SEC", "151": "American",
          "12": "CUSA", "15": "MAC", "17": "MW", "9": "Pac-12", "37": "Sun Belt", "18": "Ind"}
worst = 0
for week in (1, 2, 3, 4):
    line = []
    for gid, label in groups.items():
        try:
            payload = http.get_json(
                f"{SITE}/scoreboard",
                {"dates": YEAR, "seasontype": 2, "week": week, "groups": gid, "limit": 1000},
            )
            count = len(payload.get("events", []))
        except Exception:
            count = -1
        worst = max(worst, count)
        line.append(f"{label}={count}")
    print(f"  week {week}: " + " ".join(line))
print(f"  worst single response: {worst} (cap is 25)")

head("K. team schedule endpoint")
for team_id, label in (("99", "LSU"), ("145", "Ole Miss"), ("2294", "Iowa")):
    try:
        payload = http.get_json(f"{SITE}/teams/{team_id}/schedule", {"season": YEAR})
    except Exception as exc:
        print(f"  {label}: ERROR {exc}")
        continue
    events = payload.get("events", [])
    print(f"  {label}: keys={list(payload)} events={len(events)}")
    if events:
        event = events[0]
        comp = (event.get("competitions") or [{}])[0]
        print(f"     event keys: {list(event)}")
        print(f"     competition keys: {list(comp)}")
        competitor = (comp.get("competitors") or [{}])[0]
        print(f"     competitor keys: {list(competitor)}")
        print(f"     team keys: {list((competitor.get('team') or {}))}")
        print(f"     score: {json.dumps(competitor.get('score'))[:160]}")
        print(f"     conferenceId: {(competitor.get('team') or {}).get('conferenceId')}")
    live = [
        e for e in events
        if (((e.get("competitions") or [{}])[0].get("status") or {}).get("type") or {}).get("state") == "in"
    ]
    print(f"     in-progress events visible: {len(live)}")
    for e in live[:1]:
        comp = e["competitions"][0]
        print("     live:", json.dumps([
            {"id": c.get("team", {}).get("id"), "score": c.get("score")} for c in comp["competitors"]
        ])[:200], comp["status"]["type"].get("shortDetail"))

head("L. competition.groups on a scoreboard event")
payload = http.get_json(f"{SITE}/scoreboard", {"dates": YEAR, "seasontype": 2, "week": 3, "groups": 80, "limit": 1000})
comp = payload["events"][0]["competitions"][0]
print("groups:", json.dumps(comp.get("groups"))[:400])
print("notes:", json.dumps(comp.get("notes"))[:200])

head("M. postseason calendar")
try:
    payload = http.get_json(f"{SITE}/scoreboard", {"dates": YEAR, "seasontype": 3, "week": 1, "groups": 80, "limit": 1000})
    cal = payload.get("leagues", [{}])[0].get("calendar", [])
    for entry in cal:
        if isinstance(entry, dict):
            print(" ", entry.get("label"), entry.get("value"),
                  len(entry.get("entries", [])), "entries",
                  entry.get("startDate"), "->", entry.get("endDate"))
except Exception as exc:
    print("  ERROR", exc)

print(f"\ntotal http calls: {http.calls}")
