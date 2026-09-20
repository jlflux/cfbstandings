"""One-off endpoint diagnostics, run on a CI runner (local egress is blocked).

Prints enough of each raw response to see exactly what ESPN returns, so the
client can be written against reality rather than assumption.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cfb.espn import CORE, SITE  # noqa: E402
from cfb.http import Http  # noqa: E402

http = Http(pause=0.1)
YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2026


def head(label: str) -> None:
    print(f"\n{'=' * 72}\n{label}\n{'=' * 72}")


head("A. conference group children")
children = http.get_json(f"{CORE}/seasons/{YEAR}/types/2/groups/80/children", {"limit": 100})
print("keys:", list(children))
print("count:", children.get("count"), "items:", len(children.get("items", [])))
for item in children.get("items", [])[:2]:
    print("  ref:", item.get("$ref"))

first_ref = children["items"][0]["$ref"].replace("http://", "https://")
head("B. one conference group")
group = http.get_json(first_ref)
print("keys:", list(group))
print("id:", group.get("id"), "name:", group.get("name"), "isConference:", group.get("isConference"))
print("teams ref:", (group.get("teams") or {}).get("$ref"))
print("children:", json.dumps(group.get("children"))[:300])

head("C. that group's team list")
teams_ref = (group.get("teams") or {}).get("$ref", "").replace("http://", "https://")
if teams_ref:
    payload = http.get_json(teams_ref, {"limit": 200})
    print("keys:", list(payload), "count:", payload.get("count"),
          "pageCount:", payload.get("pageCount"), "items:", len(payload.get("items", [])))
    for item in payload.get("items", [])[:3]:
        print("  ", item.get("$ref"))

head("D. site teams endpoint filtered by group")
for group_id in ("8", "37"):
    payload = http.get_json(f"{SITE}/teams", {"groups": group_id, "limit": 200})
    teams = payload["sports"][0]["leagues"][0]["teams"]
    names = [t["team"]["displayName"] for t in teams]
    print(f"  groups={group_id}: {len(teams)} teams -> {names[:4]}")

head("E. Sun Belt group children (divisions?)")
sun_belt = http.get_json(f"{CORE}/seasons/{YEAR}/types/2/groups/37")
print("keys:", list(sun_belt))
print("children:", json.dumps(sun_belt.get("children"))[:400])
kids = (sun_belt.get("children") or {}).get("$ref")
if kids:
    payload = http.get_json(kids.replace("http://", "https://"), {"limit": 50})
    print("child count:", payload.get("count"))
    for item in payload.get("items", [])[:4]:
        child = http.get_json(item["$ref"].replace("http://", "https://"))
        print("   ", child.get("id"), child.get("name"), "| teams ref:",
              bool((child.get("teams") or {}).get("$ref")))

head("F. scoreboard variants for week 3")
variants = {
    "week+groups+limit1000": {"dates": YEAR, "seasontype": 2, "week": 3, "groups": 80, "limit": 1000},
    "week+groups+limit900":  {"dates": YEAR, "seasontype": 2, "week": 3, "groups": 80, "limit": 900},
    "week+nogroups":         {"dates": YEAR, "seasontype": 2, "week": 3, "limit": 1000},
    "week+groups80+fcs81":   {"dates": YEAR, "seasontype": 2, "week": 3, "groups": "80,81", "limit": 1000},
    "single date":           {"dates": "20260919", "groups": 80, "limit": 1000},
    "date range":            {"dates": "20260914-20260921", "groups": 80, "limit": 1000},
}
for label, params in variants.items():
    try:
        payload = http.get_json(f"{SITE}/scoreboard", params)
    except Exception as exc:
        print(f"  {label:<24} ERROR {exc}")
        continue
    events = payload.get("events", [])
    print(f"  {label:<24} events={len(events):<4} keys={[k for k in payload if k != 'events']}")

head("G. scoreboard calendar")
payload = http.get_json(f"{SITE}/scoreboard", {"dates": YEAR, "seasontype": 2, "week": 3, "groups": 80, "limit": 1000})
calendar = payload.get("leagues", [{}])[0].get("calendar", [])
print("calendar entries:", len(calendar))
print(json.dumps(calendar[:2], indent=1)[:700])
print("\nleague keys:", list(payload.get("leagues", [{}])[0]))
print("season:", json.dumps(payload.get("season")))
print("week:", json.dumps(payload.get("week")))

head("H. one event's shape")
events = payload.get("events", [])
if events:
    comp = events[0]["competitions"][0]
    print("event keys:", list(events[0]))
    print("competition keys:", list(comp))
    print("conferenceCompetition:", comp.get("conferenceCompetition"))
    print("competitor team keys:", list(comp["competitors"][0]["team"]))
    print("competitor team conferenceId:", comp["competitors"][0]["team"].get("conferenceId"))
    print("score sample:", repr(comp["competitors"][0].get("score")))

print(f"\ntotal http calls: {http.calls}")
