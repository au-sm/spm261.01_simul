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


def update_condition_history(cfg):
    """Freezes each published round's Player Condition (the same numbers the
    dashboard shows) into data/condition_history.json so past weeks are kept
    even after injuries heal. Returns {round_str: {player_id_str: tier}}."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from player_condition import conditions_for_round
    import render_dashboard
    path = os.path.join(BASE, "data", "condition_history.json")
    hist = json.load(open(path)) if os.path.exists(path) else {}
    cal_path = os.path.join(BASE, "data", "season_calendar.json")
    total = None
    try:
        cal = json.load(open(cal_path))
        total = max(r for d in cal.get("match_days", []) for r in d.get("rounds", []))
    except Exception:
        pass
    rnd = int(cfg.get("current_round", 0)) + 1
    if (total is None or rnd <= total) and str(rnd) not in hist:
        inj_path = os.path.join(BASE, "data", "player_injuries.json")
        injuries = json.load(open(inj_path)) if os.path.exists(inj_path) else {}
        _m, detail = conditions_for_round(cfg.get("season_seed", 2026), rnd,
                                          render_dashboard.load_players(), injuries)
        hist[str(rnd)] = {str(pid): d[0] for pid, d in detail.items()}
        with open(path, "w") as f:
            json.dump(hist, f, indent=1, sort_keys=True)
    return hist


def build_rows():
    cfg = json.load(open(os.path.join(BASE, "data", "league_config.json")))
    players = json.load(open(os.path.join(BASE, "players.json")))
    hist = update_condition_history(cfg)
    rounds = sorted(hist, key=int)
    rows = [["Team", "Owner", "Player", "Position", "OVR", "Salary"] + ["Round %s Condition" % r for r in rounds]]
    for t in sorted(cfg["teams"], key=lambda t: t["team_id"]):
        roster = sorted([p for p in players if p.get("team_id") == t["team_id"]],
                        key=lambda p: (POS.get(p["position"], 9), -p["ovr"], p["name"]))
        if not roster:
            continue
        for p in roster:
            rows.append([t["name"], t.get("owner", ""), p["name"], p["position"], p["ovr"], p["salary"]]
                        + [hist[r].get(str(p["id"]), "") for r in rounds])
        rows.append(["", "%s total (%d players, avg OVR)" % (t["name"], len(roster)), "", "",
                     round(sum(p["ovr"] for p in roster) / len(roster), 1),
                     sum(p["salary"] for p in roster)] + [""] * len(rounds))
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
