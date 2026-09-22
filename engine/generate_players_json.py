"""
Regenerates submit/players.json (the Submit page's static reference copy
of the player pool) from data/players.csv -- includes team_id (null
until drafted) so the Weekly Lineup form can filter to a team's actual
roster, and the Draft Board form can exclude already-drafted players.

Run after any draft/round resolution (team_id assignments change),
then push. engine/auto_resolve.py calls this automatically as part of
its regenerate step.

Usage:
    python3 engine/generate_players_json.py [output_path]
"""
import csv
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build():
    with open(os.path.join(BASE, "data", "players.csv")) as f:
        players = list(csv.DictReader(f))
    return [
        {
            "id": int(p["player_id"]),
            "name": p["name"],
            "position": p["position"],
            "ovr": int(p["ovr"]),
            "salary": int(p["salary"]),
            "team_id": int(p["team_id"]) if p["team_id"] not in ("", None) else None,
        }
        for p in players
    ]


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "submit", "players.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(build(), f)
    print(f"Written -> {out_path}")
