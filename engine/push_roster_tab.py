"""Pushes the current rosters (players.json + league_config team names) into
a "Players per Team" tab of the league Google Sheet via the backend's
admin-only `admin_roster_tab` action. Needs ADMIN_KEY in the environment
(GitHub Actions secret). No PINs are ever sent or written."""
import json, os, sys, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POS = {"GK": 0, "DF": 1, "MF": 2, "FW": 3}


def backend_url():
    txt = open(os.path.join(BASE, "assets", "config.js")).read()
    return txt.split('"')[1]


def build_rows():
    cfg = json.load(open(os.path.join(BASE, "data", "league_config.json")))
    players = json.load(open(os.path.join(BASE, "players.json")))
    rows = [["Team", "Owner", "Player", "Position", "OVR", "Salary"]]
    for t in sorted(cfg["teams"], key=lambda t: t["team_id"]):
        roster = sorted([p for p in players if p.get("team_id") == t["team_id"]],
                        key=lambda p: (POS.get(p["position"], 9), -p["ovr"], p["name"]))
        if not roster:
            continue
        for p in roster:
            rows.append([t["name"], t.get("owner", ""), p["name"], p["position"], p["ovr"], p["salary"]])
        rows.append(["", "%s total (%d players, avg OVR)" % (t["name"], len(roster)), "", "",
                     round(sum(p["ovr"] for p in roster) / len(roster), 1),
                     sum(p["salary"] for p in roster)])
    return rows


def push(admin_key):
    body = json.dumps({"type": "admin_roster_tab", "admin_key": admin_key, "rows": build_rows()}).encode()
    req = urllib.request.Request(backend_url(), data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


if __name__ == "__main__":
    key = os.environ.get("ADMIN_KEY")
    if not key:
        sys.exit("ADMIN_KEY env var not set")
    print(push(key))
