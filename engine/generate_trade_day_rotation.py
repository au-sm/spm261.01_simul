"""
Generates the Mandatory Mid-Season Trade Day pairing -- one round only,
every team paired with exactly one partner, reusing the same
round_robin_schedule() combinatorics as the sponsorship negotiation
rotation (engine/generate_negotiation_rotation.py) since "pair everyone
up with no repeats" is the identical problem either way.

Unlike the sponsorship rotation (6 rounds, two negotiations per pair,
swapping owner/rep), Trade Day is ONE round, ONE negotiation per pair:
both sides are owners, negotiating directly with each other, and must
submit a completed Trade Proposal form (real assets or a good-faith
minor swap -- the grade is on the negotiation and rationale, not on
whether the trade was a "good" one).

Odd team count (Section 2, 21 teams) produces one bye pairing, filled
by the INSTRUCTOR -- same convention as the sponsorship rotation, so
every team still completes exactly one mandatory trade that day.

Usage:
    python3 engine/generate_trade_day_rotation.py --n-teams 20
    python3 engine/generate_trade_day_rotation.py --n-teams 21
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from simulate import round_robin_schedule

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_trade_day(n_teams, team_names=None):
    team_names = team_names or [f"Team {i + 1}" for i in range(n_teams)]
    team_ids = list(range(n_teams))
    first_round = round_robin_schedule(team_ids)[0]

    paired_ids = {tid for pair in first_round for tid in pair}
    bye = [tid for tid in team_ids if tid not in paired_ids]

    pairs = [
        {"team_a": team_names[a], "team_b": team_names[b]}
        for a, b in first_round
    ]
    return {
        "pairs": pairs,
        "bye": [team_names[tid] for tid in bye],  # instructor fills in for these
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-teams", type=int, required=True)
    args = ap.parse_args()

    trade_day = build_trade_day(args.n_teams)

    print(f"=== Mandatory Mid-Season Trade Day -- {args.n_teams} teams ===")
    for i, p in enumerate(trade_day["pairs"], start=1):
        print(f"  Meeting {i}: {p['team_a']} & {p['team_b']}")
    if trade_day["bye"]:
        print(f"  BYE (instructor fills in as trade partner): {', '.join(trade_day['bye'])}")
    print(f"\nEvery team submits ONE completed Trade Proposal form from this pairing "
          f"before end of class -- on top of, not instead of, the ordinary voluntary "
          f"trade window that continues through the Round 15 deadline.")
