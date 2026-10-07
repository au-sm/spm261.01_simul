"""
Pushes the instructor-only "Forfeits" tab into this section's Submissions
Google Sheet (owned by the instructor, never shown on the public site).

Publicly, a forfeit looks like an ordinary result (see resolve_round.py's
forfeit branch). This tab is the ONLY place that says who forfeited and
why: no lineup submitted, wrong/missing PIN, or no decision rationale.

Uses the backend's admin-only `admin_tab` action (ADMIN_KEY), same pattern
as push_roster_tab.py. Called from auto_resolve.py after every cycle; also
runnable by hand:  ADMIN_KEY=... python3 engine/push_forfeit_tab.py
"""
import json
import os
import re
import sys
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def backend_url():
    with open(os.path.join(BASE, "assets", "config.js")) as f:
        m = re.search(r'BACKEND_URL\s*=\s*"([^"]+)"', f.read())
    return m.group(1)


def build_rows():
    config = load_json("league_config.json")
    calendar = load_json("season_calendar.json")
    matches = load_json("matches.json")
    name = {t["team_id"]: t["name"] for t in config["teams"]}
    owner = {t["team_id"]: t.get("owner", "") for t in config["teams"]}
    date_by_round = {r: e["date"] for e in calendar.get("match_day_schedule", []) for r in e["rounds"]}
    rows = [["Round", "Match date", "Team that lost by forfeit", "Owner", "Reason", "Opponent",
             "Result shown publicly", "Ticket revenue given"]]
    for m in sorted(matches, key=lambda m: (m["round"], m["home_id"])):
        ff = m.get("forfeit")
        if not ff:
            continue
        reasons = m.get("forfeit_reason") or {}
        shown = f'{name.get(m["home_id"], "")} {m["home_goals"]}-{m["away_goals"]} {name.get(m["away_id"], "")}'
        sides = ["home", "away"] if ff == "both" else [ff]
        for side in sides:
            tid = m[f"{side}_id"]
            opp = m["away_id"] if side == "home" else m["home_id"]
            reason = reasons.get(side) or "no valid lineup"
            if ff == "both":
                reason += " (both teams forfeited: both take a loss)"
            payout = (m.get("gate") or {}).get(f"{side}_payout", 0)
            rows.append([m["round"], date_by_round.get(m["round"], ""), name.get(tid, ""), owner.get(tid, ""),
                         reason, name.get(opp, ""), shown,
                         f"${payout:,} (50% of round avg {side} revenue)" if payout else "$0"])
    if len(rows) == 1:
        rows.append(["", "", "No forfeits yet", "", "", "", "", ""])
    return rows


def push(admin_key):
    if not admin_key:
        return "skipped (no ADMIN_KEY)"
    body = json.dumps({"type": "admin_tab", "admin_key": admin_key, "tab_name": "Forfeits",
                       "rows": build_rows()}).encode()
    req = urllib.request.Request(backend_url(), data=body, headers={"Content-Type": "text/plain;charset=utf-8"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode()[:200]


if __name__ == "__main__":
    print(push(os.environ.get("ADMIN_KEY", "")))
