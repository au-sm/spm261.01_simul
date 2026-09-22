"""
Assigns each team a Local TV Deal -- a per-team regional broadcast
contract, separate from and additional to the league-wide national TV
deal in data/deals.json -> tv_deal_formula. Modeled on how real clubs
carry both a shared national media-rights split AND their own
individual local/regional broadcast deal that varies hugely by market
size (a big-market club's local deal dwarfs a small-market club's).

Run ONCE, right after Draft Day, same timing rule as
generate_schedule.py -- market tier is a fixed, season-long assignment
(like a real regional broadcast contract), not renegotiated mid-season.

Every team gets exactly one of three market tiers, split as evenly as
possible across the league and drawn reproducibly from season_seed (same
principle as match simulation: any assignment can be independently
re-verified after the fact). The dollar amount is paid out at the same
midseason split point as the national TV deal (after Round 3 of a
19-round season -- see tv_deal_formula.midseason_split_timing) with a
Star Power modifier: local broadcasters pay more for star wattage in
their own market, same logic as the national deal's star bonus, scaled
proportionally instead of as a flat add since local bases already vary
so much by tier.

Usage:
    python3 engine/generate_local_tv_deals.py --n-teams 20
    python3 engine/generate_local_tv_deals.py --n-teams 21
"""
import argparse
import json
import os
import random
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MARKET_TIERS = [
    {"tier": "Major Market", "base_revenue": 1200000},
    {"tier": "Mid Market", "base_revenue": 700000},
    {"tier": "Small Market", "base_revenue": 500000},
]

STAR_POWER_MODIFIER = {
    "description": "If a team's average starting-XI Star Power ranks in the league's top 3 at "
                    "split time, its Local TV Deal pays +15% that round (same top-3 threshold as "
                    "the national deal's star bonus) -- scaled off the team's own base rather than "
                    "a flat dollar add, since a Major Market base and a Small Market base are "
                    "already such different sizes.",
    "multiplier_if_top3_star_power": 1.15,
    "multiplier_otherwise": 1.0,
}


def assign_tiers(n_teams, season_seed, team_names=None):
    team_names = team_names or [f"Team {i + 1}" for i in range(n_teams)]
    base, remainder = divmod(n_teams, 3)
    sizes = [base + (1 if i < remainder else 0) for i in range(3)]  # Major, Mid, Small

    pool = []
    for tier, size in zip(MARKET_TIERS, sizes):
        pool.extend([tier] * size)

    rng = random.Random(season_seed)
    rng.shuffle(pool)

    return [
        {
            "team_id": tid,
            "team_name": team_names[tid],
            "market_tier": pool[tid]["tier"],
            "base_revenue": pool[tid]["base_revenue"],
        }
        for tid in range(n_teams)
    ]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-teams", type=int, required=True)
    ap.add_argument("--season-seed", type=int, default=None,
                     help="Defaults to league_config.json's season_seed if omitted.")
    args = ap.parse_args()

    with open(os.path.join(BASE, "data", "league_config.json")) as f:
        config = json.load(f)
    seed = args.season_seed if args.season_seed is not None else config["season_seed"]

    team_names = None
    if len(config["teams"]) == args.n_teams:
        team_names = [t["name"] for t in config["teams"]]

    assignments = assign_tiers(args.n_teams, seed, team_names)

    out = {
        "_description": "Local TV Deals -- one per-team regional broadcast contract, fixed for "
                         "the season, additional to the league-wide national TV deal. See "
                         "data/deals.json -> local_tv_deal_formula for the full mechanic.",
        "market_tiers": MARKET_TIERS,
        "star_power_modifier": STAR_POWER_MODIFIER,
        "assignments": assignments,
    }
    out_path = os.path.join(BASE, "data", "local_tv_deals.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"Assigned Local TV Deals for {args.n_teams} teams -> {out_path}")
    for a in assignments:
        print(f"  {a['team_name']:<10} {a['market_tier']:<14} ${a['base_revenue']:,}")
