"""
Publishes this round's Player Condition report -- run this and share the
output BEFORE that round's Weekly Lineup deadline, so students actually
have the information when they pick their starting XI and formation,
not just after the fact when it's too late to matter.

Every player on every roster gets either a routine weekly-form tier
(Poor/Below Average/Average/Good/Excellent) or, if they're carrying an
injury from a previous round, a flat "Injured" tier -- see
engine/player_condition.py for the exact weights, multipliers, and how
injuries persist. Routine form is a pure function of (season_seed,
round, player_id); injury status depends on what actually happened in
earlier rounds (data/player_injuries.json, updated by resolve_round.py).
Run this AFTER the previous round has been resolved and BEFORE this
round's Weekly Lineup deadline, and what it prints is guaranteed to
match what resolve_round.py uses when this round is actually resolved.

Usage:
    python3 engine/generate_weekly_conditions.py --round 3
    python3 engine/generate_weekly_conditions.py --round 3 --team 5   (one team only)
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from player_condition import conditions_for_round
import render_dashboard

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--team", type=int, default=None, help="only show this team_id's roster")
    args = ap.parse_args()

    config = load_json("league_config.json")
    season_seed = config.get("season_seed", 2026)
    players = render_dashboard.load_players()
    injuries_path = os.path.join(BASE, "data", "player_injuries.json")
    injuries = load_json("player_injuries.json") if os.path.exists(injuries_path) else {}
    _mult_by_id, detail_by_id = conditions_for_round(season_seed, args.round, players, injuries)

    team_name_by_id = {t["team_id"]: t["name"] for t in config["teams"]}
    team_owner_by_id = {t["team_id"]: t.get("owner", "") for t in config["teams"]}

    rostered = [p for p in players if p.get("team_id") not in ("", None)]
    rostered.sort(key=lambda p: (int(p["team_id"]), p["position"], p["name"]))

    rows_for_csv = []
    current_team = None
    for p in rostered:
        tid = int(p["team_id"])
        if args.team is not None and tid != args.team:
            continue
        if tid != current_team:
            current_team = tid
            owner = team_owner_by_id.get(tid, "")
            label = f"{team_name_by_id.get(tid, f'Team {tid+1}')}" + (f" ({owner})" if owner else "")
            print(f"\n=== {label} ===")
        tier, mult, injured_until = detail_by_id[p["player_id"]]
        tag = f"out through round {injured_until}" if injured_until else ""
        print(f"  {p['position']:<3} {p['name']:<22} {tier:<15} {mult:.2f}x  (base ATT {p['att']} / DEF {p['def']})  {tag}")
        rows_for_csv.append({
            "round": args.round, "team_id": tid, "team_name": team_name_by_id.get(tid, ""),
            "player_id": p["player_id"], "name": p["name"], "position": p["position"],
            "base_att": p["att"], "base_def": p["def"],
            "condition_tier": tier, "condition_multiplier": mult,
            "injured_until_round": injured_until or "",
        })

    out_dir = os.path.join(BASE, "data", "weekly_conditions")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"round_{args.round}_conditions.csv")
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_for_csv[0].keys()) if rows_for_csv else
                            ["round", "team_id", "team_name", "player_id", "name", "position",
                             "base_att", "base_def", "condition_tier", "condition_multiplier",
                             "injured_until_round"])
        w.writeheader()
        w.writerows(rows_for_csv)

    print(f"\nSaved -> {out_path}")
    print("Share this (or the console output above) with students BEFORE the Round "
          f"{args.round} Weekly Lineup deadline -- resolve_round.py will independently "
          "recompute these exact same values when the round is actually resolved.")


if __name__ == "__main__":
    main()
