"""
Generates the Local TV Rights Negotiation rotation -- who pairs with
whom to negotiate their Local TV Deal, right after Draft Day.

Reuses round_robin_schedule() from simulate.py for the same reason
generate_negotiation_rotation.py does: pairing every team with exactly
one partner, no repeats, is the same combinatorial problem as
scheduling a round-robin round. Unlike the Sponsorship Negotiation
rotation (6 rounds, one per category), a team only has ONE Local TV
Deal, so this needs just ONE round of that schedule -- but NOT round 0.

The Sponsorship Negotiation rotation (generate_negotiation_rotation.py)
also builds its schedule from round_robin_schedule(list(range(n_teams)))
with no seed/offset, and consumes rounds 0..n_categories-1 (rounds
0-5 for the current 6 sponsorship categories). Since that schedule is
fully deterministic, TV's own round 0 would be IDENTICAL to
Sponsorship's round 0 pairing -- every student would get the exact
same partner for both exercises, defeating the point of practicing
negotiation against a different classmate. Round-robin guarantees
each pair of teams meets in exactly ONE round across the whole
schedule, so picking any round AT OR AFTER n_categories is
mathematically guaranteed to share zero pairs with any Sponsorship
round -- this uses round `n_categories` (the one immediately after
Sponsorship's last used round) for that reason, read live from
data/deals.json's sponsorship_categories so it can never silently
drift back into a collision if the category count ever changes.

WITHIN each pair, both students negotiate back to back, swapping who
plays team owner and who plays "network rep":
  Negotiation 1 -- team_a (owner) vs team_b (network rep) -- team_a's own market-tier deal
  Negotiation 2 -- team_b (owner) vs team_a (network rep) -- team_b's own market-tier deal
Each team negotiates its OWN deal both times (unlike sponsorship, there
is no second brand to swap to -- your Local TV deal is fixed by your
own market tier). An odd team count leaves one team unpaired for this
round; the instructor fills in as that team's network rep, same
convention as the Sponsorship Negotiation rotation's bye.

Usage:
    python3 engine/generate_tv_negotiation_rotation.py --n-teams 20
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from simulate import round_robin_schedule

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_rotation(n_teams, market_tiers_by_team, team_names=None, sponsorship_rounds_used=6):
    """market_tiers_by_team: dict team_id -> market_tier string, from
    data/local_tv_deals.json, shown alongside each pairing so students
    know what's actually on the table before they negotiate.

    sponsorship_rounds_used: how many rounds of the SAME underlying
    round_robin_schedule() the Sponsorship Negotiation rotation already
    consumed (its round count = its number of categories -- 6 by
    default, see module docstring). This picks the round right after
    that block, which round-robin's one-meeting-per-pair guarantee
    ensures shares zero partners with any Sponsorship round."""
    team_names = team_names or [f"Team {i+1}" for i in range(n_teams)]
    team_ids = list(range(n_teams))
    schedule = round_robin_schedule(team_ids)
    if len(schedule) <= sponsorship_rounds_used:
        raise ValueError(
            f"round_robin_schedule only produced {len(schedule)} rounds, but round "
            f"{sponsorship_rounds_used} (right after the {sponsorship_rounds_used} rounds "
            f"Sponsorship already uses) is needed to avoid repeating a Sponsorship partner -- "
            f"too few teams for both rotations to stay partner-disjoint."
        )
    pairs = schedule[sponsorship_rounds_used]
    paired_ids = {tid for pair in pairs for tid in pair}
    bye = [tid for tid in team_ids if tid not in paired_ids]

    pair_assignments = []
    for a, b in pairs:
        pair_assignments.append({
            "team_a": team_names[a], "team_a_market_tier": market_tiers_by_team.get(a, "?"),
            "team_b": team_names[b], "team_b_market_tier": market_tiers_by_team.get(b, "?"),
        })

    return {
        "pairs": pair_assignments,
        "bye": [team_names[tid] for tid in bye],  # instructor fills in for these
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-teams", type=int, required=True)
    args = ap.parse_args()

    with open(os.path.join(BASE, "data", "league_config.json")) as f:
        config = json.load(f)
    team_names = [t["name"] for t in config["teams"]] if len(config["teams"]) == args.n_teams else None

    tiers_path = os.path.join(BASE, "data", "local_tv_deals.json")
    market_tiers_by_team = {}
    if os.path.exists(tiers_path):
        with open(tiers_path) as f:
            ltv = json.load(f)
        market_tiers_by_team = {a["team_id"]: a["market_tier"] for a in ltv["assignments"]}

    with open(os.path.join(BASE, "data", "deals.json")) as f:
        deals = json.load(f)
    sponsorship_rounds_used = len(deals["sponsorship_categories"])

    rotation = build_rotation(args.n_teams, market_tiers_by_team, team_names, sponsorship_rounds_used)

    print("=== Local TV Rights Negotiation ===")
    for p in rotation["pairs"]:
        print(f"  {p['team_a']} & {p['team_b']}:")
        print(f"    Negotiation 1 -- {p['team_a']} (owner, {p['team_a_market_tier']}) vs {p['team_b']} (network rep)")
        print(f"    Negotiation 2 -- {p['team_b']} (owner, {p['team_b_market_tier']}) vs {p['team_a']} (network rep)")
    if rotation["bye"]:
        print(f"  BYE (instructor fills in as network rep): {', '.join(rotation['bye'])}")
