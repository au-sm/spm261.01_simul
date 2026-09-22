"""
Generates the Sponsorship Negotiation rotation schedule -- who pairs
with whom, for which category, across all 6 negotiation rounds.

Reuses round_robin_schedule() from simulate.py: pairing 20 (or 21, or
any N) people across rounds with no repeat partners is the exact same
combinatorial problem as scheduling a round-robin season, just with
"negotiation partner" standing in for "opponent." We only need the
first 6 rounds of that schedule (one per sponsorship category), which
also guarantees no student meets the same partner twice across the
whole exercise.

WITHIN each round's pair, both students fill THIS round's category for
their own team -- they do two short negotiations back to back, swapping
who plays team owner and who plays sponsor rep, so both leave the round
with a signed deal in that category. Nobody sits out a category: an
odd student count produces one "bye" pairing each round, which is
assigned to the INSTRUCTOR to fill in for (see --instructor-fills-bye).

CRITICAL: the two negotiations in a pair use TWO DIFFERENT BRANDS from
the category, never the same one. If both directions used the same
brand, whoever plays owner SECOND would already have watched the first
negotiation reveal that brand's private ceiling and tactics while
playing its sponsor rep -- not a fair test of their own negotiating
skill, just a replay of what they watched. Different brands per
direction means both negotiations are genuinely independent trials.

Usage:
    python3 engine/generate_negotiation_rotation.py --n-teams 20
    python3 engine/generate_negotiation_rotation.py --n-teams 21
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from simulate import round_robin_schedule

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_rotation(n_teams, categories, team_names=None):
    team_names = team_names or [f"Team {i+1}" for i in range(n_teams)]
    team_ids = list(range(n_teams))
    schedule = round_robin_schedule(team_ids)

    n_categories = len(categories)
    if len(schedule) < n_categories:
        raise ValueError(f"round_robin_schedule only produced {len(schedule)} rounds, need {n_categories}")

    rotation = []
    for round_idx in range(n_categories):
        cat = categories[round_idx]
        pairs = schedule[round_idx]
        paired_ids = {tid for pair in pairs for tid in pair}
        bye = [tid for tid in team_ids if tid not in paired_ids]

        brands = cat["brands"]
        n_brands = len(brands)
        pair_assignments = []
        for i, (a, b) in enumerate(pairs):
            # two distinct brands per pair: consecutive indices in a cycle of
            # length n_brands are guaranteed different as long as n_brands >= 2
            brand_for_a_as_owner = brands[(2 * i) % n_brands]["name"]
            brand_for_b_as_owner = brands[(2 * i + 1) % n_brands]["name"]
            pair_assignments.append({
                "team_a": team_names[a], "team_b": team_names[b],
                "brand_a_owner": brand_for_a_as_owner,   # brand when team_a plays owner
                "brand_b_owner": brand_for_b_as_owner,   # brand when team_b plays owner
            })

        rotation.append({
            "round": round_idx + 1,
            "category": cat["category"],
            "pairs": pair_assignments,
            "bye": [team_names[tid] for tid in bye],  # instructor fills in for these
        })
    return rotation


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-teams", type=int, required=True)
    args = ap.parse_args()

    with open(os.path.join(BASE, "data", "deals.json")) as f:
        deals = json.load(f)
    categories = deals["sponsorship_categories"]

    rotation = build_rotation(args.n_teams, categories)

    for r in rotation:
        print(f"\n=== Round {r['round']}: {r['category']} ===")
        for p in r["pairs"]:
            print(f"  {p['team_a']} & {p['team_b']}:")
            print(f"    Negotiation 1 -- {p['team_a']} (owner) vs {p['team_b']} (sponsor rep) -- {p['brand_a_owner']}")
            print(f"    Negotiation 2 -- {p['team_b']} (owner) vs {p['team_a']} (sponsor rep) -- {p['brand_b_owner']}")
        if r["bye"]:
            print(f"  BYE (instructor fills in): {', '.join(r['bye'])}")
