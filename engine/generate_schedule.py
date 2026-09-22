"""
Generates the regular-season fixture list (data/schedule.json) from the
current team count in league_config.json. Run this ONCE, right after
Draft Day, once real team count/names are locked in -- re-running later
would reshuffle who plays whom and desync it from any rounds already
recorded in matches.json.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from simulate import round_robin_schedule

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    with open(os.path.join(BASE, "data", "league_config.json")) as f:
        config = json.load(f)
    team_ids = [t["team_id"] for t in config["teams"]]
    rounds = round_robin_schedule(team_ids)

    schedule = [
        {"round": i + 1, "fixtures": [{"home_id": h, "away_id": a} for h, a in rnd]}
        for i, rnd in enumerate(rounds)
    ]

    out_path = os.path.join(BASE, "data", "schedule.json")
    with open(out_path, "w") as f:
        json.dump(schedule, f, indent=2)

    print(f"Generated {len(schedule)}-round schedule for {len(team_ids)} teams -> {out_path}")
    for rnd in schedule:
        names = {t["team_id"]: t["name"] for t in config["teams"]}
        pairs = ", ".join(f"{names[fx['home_id']]} vs {names[fx['away_id']]}" for fx in rnd["fixtures"])
        print(f"  Round {rnd['round']}: {pairs}")


if __name__ == "__main__":
    main()
