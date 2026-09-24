"""
Generates the regular-season fixture list (data/schedule.json) from the
current team count in league_config.json. Run this ONCE, right after
Draft Day, once real team count/names are locked in -- re-running later
would reshuffle who plays whom and desync it from any rounds already
recorded in matches.json.

HOME/AWAY BALANCING: round_robin_schedule()'s naive circle method
guarantees every pair meets exactly once, but does NOT guarantee a
fair home/away split per team -- the raw output can (and did, before
this fix) give one team zero home matches all season while another
gets home 16 times out of 17. Since ticket revenue is booked to the
home side only (engine/resolve_round.py), an unbalanced schedule
directly corrupts the graded Business Revenue component through no
fault of the student's own strategy. rebalance_home_away() fixes this
as a deterministic post-process: it walks every fixture in round order
and flips home/away to whichever team currently has fewer home games
so far, WITHOUT changing who plays whom or in which round -- only
which side of an already-fixed pairing is "home." For an odd number of
games per team (true whenever the team count is even, so rounds =
n-1 is odd), the best possible split is a 1-game difference; this
achieves exactly that for every team, not just on average.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from simulate import round_robin_schedule

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rebalance_home_away(rounds):
    """rounds: list of rounds, each a list of (team_a, team_b) tuples (order
    from round_robin_schedule, not yet meaningful as home/away). Returns the
    same shape with each tuple reordered to (home, away), balanced so every
    team's total home-game count differs from any other's by at most 1."""
    home_count = {}
    balanced = []
    for rnd in rounds:
        new_rnd = []
        for t1, t2 in rnd:
            c1 = home_count.get(t1, 0)
            c2 = home_count.get(t2, 0)
            home, away = (t1, t2) if c1 <= c2 else (t2, t1)
            home_count[home] = home_count.get(home, 0) + 1
            new_rnd.append((home, away))
        balanced.append(new_rnd)
    return balanced


def main():
    with open(os.path.join(BASE, "data", "league_config.json")) as f:
        config = json.load(f)
    team_ids = [t["team_id"] for t in config["teams"]]
    rounds = round_robin_schedule(team_ids)
    rounds = rebalance_home_away(rounds)

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
