"""
Records one team's sponsorship pick -- either resolved algorithmically
(leverage decides everything, no live counterpart) or as a LIVE deal
(you type in exactly what two students actually agreed to, and credit
a commission to whoever played the sponsor rep).

LIVE MODE (the normal path for the in-class negotiation exercise):
    python3 engine/resolve_sponsorship_pick.py --team 3 --brand "Nike" \\
        --live --final-revenue 3800000 --final-clause standard \\
        --sponsor-rep-team 17

  This records $3.8M for Team 3 (Nike lists at $3.5M base, so the
  $300,000 overage is ALSO credited as commission revenue to Team 17,
  whoever played the Nike rep in that negotiation). If the negotiated
  revenue is at or below base, no commission is credited to anyone --
  upside-only, never a penalty for playing sponsor.

ALGORITHMIC MODE (practice / fallback for a category that never got a
live negotiation -- no human played sponsor, so no commission applies):
    python3 engine/resolve_sponsorship_pick.py --team 3 --brand "Nike" \\
        --take-base
    python3 engine/resolve_sponsorship_pick.py --team 3 --brand "Nike" \\
        --negotiate --negotiate-clause --clause-intensity bold

RULES ENFORCED HERE (see engine/negotiation.py for the full system):
  - A team may hold AT MOST ONE brand per category.
  - A brand's qty is a LEAGUE-WIDE cap on how many teams total may hold
    it -- multiple teams sharing a brand is expected, not a bug.
  - Sponsors PAY teams. There is no cost check because there is no cost.
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
from negotiation import compute_leverage, resolve_revenue, resolve_clause
from simulate import Standings
import render_dashboard

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def save_json(name, data):
    with open(os.path.join(BASE, "data", name), "w") as f:
        json.dump(data, f, indent=2)


def find_brand(deals, brand_name):
    for cat in deals["sponsorship_categories"]:
        for b in cat["brands"]:
            if b["name"] == brand_name:
                return cat["category"], b
    return None, None


def brand_slots_taken(brand_name, finances):
    return sum(
        1 for t in finances["teams"].values()
        for s in t.get("sponsors_owned", [])
        if s["sponsor"] == brand_name and s["outcome"] != "walk_away"
    )


def team_standing_rank(team_id, matches, team_ids):
    if not matches:
        return None
    st = Standings(team_ids)
    for m in matches:
        if m.get("stage", "regular") == "regular":
            st.record(m["home_id"], m["away_id"], m["home_goals"], m["away_goals"])
    ranked = [tid for tid, _ in st.ranked()]
    return ranked.index(team_id) + 1 if team_id in ranked else None


def team_avg_star_power(team_id, players):
    roster = [p for p in players if p.get("team_id") not in ("", None) and int(p["team_id"]) == team_id]
    if not roster:
        return None
    return sum(p["star_power"] for p in roster) / len(roster)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", type=int, required=True)
    ap.add_argument("--brand", required=True)

    ap.add_argument("--live", action="store_true", help="record an already-negotiated live deal")
    ap.add_argument("--final-revenue", type=int, help="[live] the exact agreed revenue")
    ap.add_argument("--final-clause", choices=["strict", "standard", "loose", "none"], help="[live] the exact agreed clause")
    ap.add_argument("--sponsor-rep-team", type=int, help="[live] team whose student played sponsor rep (receives commission if revenue > base)")

    ap.add_argument("--take-base", action="store_true", help="[algorithmic] take listed terms exactly, no negotiation")
    ap.add_argument("--negotiate", action="store_true", help="[algorithmic] resolve revenue via leverage formula")
    ap.add_argument("--negotiate-clause", action="store_true", help="[algorithmic] also attempt a clause ask")
    ap.add_argument("--clause-intensity", choices=["modest", "bold", "very_bold"], default=None)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    config = load_json("league_config.json")
    deals = load_json("deals.json")
    finances = load_json("team_finances.json")
    matches = load_json("matches.json")
    players = render_dashboard.load_players()

    team_ids = [t["team_id"] for t in config["teams"]]
    team_name = next(t["name"] for t in config["teams"] if t["team_id"] == args.team)

    category, brand = find_brand(deals, args.brand)
    if brand is None:
        print(f"ERROR: no brand named '{args.brand}' in any sponsorship category"); return

    owned = finances["teams"][str(args.team)].get("sponsors_owned", [])
    signed_categories = {s["category"] for s in owned if s["outcome"] != "walk_away"}
    if category in signed_categories:
        current = next(s["sponsor"] for s in owned if s["category"] == category and s["outcome"] != "walk_away")
        print(f"ERROR: {team_name} already has a {category} sponsor ({current}). One brand per category."); return

    taken = brand_slots_taken(brand["name"], finances)
    if taken >= brand["qty"]:
        print(f"SOLD OUT: {brand['name']} has all {brand['qty']} slots taken league-wide. Try a different {category} brand."); return

    if team_avg_star_power(args.team, players) is None:
        print(f"ERROR: {team_name} has no drafted players yet -- run the player draft first."); return

    # ---------------- LIVE MODE ----------------
    if args.live:
        if args.final_revenue is None or args.final_clause is None:
            print("ERROR: --live requires --final-revenue and --final-clause"); return

        commission = 0
        rep_team_name = None
        if args.final_revenue > brand["base_revenue"]:
            if args.sponsor_rep_team is None:
                print(f"ERROR: final revenue (${args.final_revenue:,}) is above base (${brand['base_revenue']:,}), "
                      f"so --sponsor-rep-team is required to credit the ${args.final_revenue - brand['base_revenue']:,} commission."); return
            rep_team_name = next((t["name"] for t in config["teams"] if t["team_id"] == args.sponsor_rep_team), None)
            if rep_team_name is None:
                print(f"ERROR: no team with id {args.sponsor_rep_team}"); return
            commission = args.final_revenue - brand["base_revenue"]

        owned.append({
            "category": category, "sponsor": brand["name"], "mode": "live",
            "outcome": "accepted", "final_revenue": args.final_revenue, "final_clause": args.final_clause,
            "sponsor_rep_team_id": args.sponsor_rep_team,
        })
        finances["teams"][str(args.team)]["sponsors_owned"] = owned
        finances["teams"][str(args.team)]["sponsorship_revenue"] = finances["teams"][str(args.team)].get("sponsorship_revenue", 0) + args.final_revenue

        print(f"\n{team_name} signs {brand['name']} ({category}): ${args.final_revenue:,}/season, {args.final_clause} clause.")

        if commission > 0:
            rep_key = str(args.sponsor_rep_team)
            finances["teams"].setdefault(rep_key, {}).setdefault("sponsors_owned", [])
            finances["teams"][rep_key].setdefault("commissions_earned", []).append({
                "as_sponsor_for": brand["name"], "negotiating_team": team_name,
                "category": category, "commission_amount": commission,
            })
            finances["teams"][rep_key]["sponsorship_revenue"] = finances["teams"][rep_key].get("sponsorship_revenue", 0) + commission
            print(f"{rep_team_name} earns a ${commission:,} commission for playing {brand['name']}'s rep (deal closed ${commission:,} above base).")

        save_json("team_finances.json", finances)

    # ---------------- ALGORITHMIC MODE ----------------
    else:
        if not (args.take_base or args.negotiate):
            print("ERROR: pick one of --take-base or --negotiate (or use --live to record an already-negotiated deal)"); return
        if args.negotiate_clause and not args.clause_intensity:
            print("ERROR: --negotiate-clause requires --clause-intensity"); return

        avg_star = team_avg_star_power(args.team, players)
        rank = team_standing_rank(args.team, matches, team_ids)
        leverage = compute_leverage(avg_star, standings_rank=rank, n_teams=len(team_ids))

        seed_val = args.seed if args.seed is not None else config.get("season_seed", 0)
        rng = random.Random(f"{seed_val}:sponsorship:{args.team}:{brand['name']}:{len(owned)}")

        final_revenue, commission = resolve_revenue(brand["base_revenue"], take_base=args.take_base, leverage=leverage)
        final_clause = brand["base_clause"]
        if args.negotiate_clause:
            clause_result = resolve_clause(brand["base_clause"], args.clause_intensity, leverage, rng)
            if clause_result["outcome"] == "walk_away":
                print(f"\n{team_name} -> {brand['name']} ({category}): clause ask WALKED AWAY (revenue side still resolved below).")
            final_clause = clause_result["final_clause"]

        print(f"\n{team_name} -> {brand['name']} ({category})  (avg Star Power {avg_star:.0f}, leverage {leverage:.0f})")
        print(f"  Final terms: ${final_revenue:,}/season, {final_clause} clause. "
              f"{'(no live sponsor rep, so no commission credited)' if commission else ''}")

        owned.append({
            "category": category, "sponsor": brand["name"], "mode": "algorithmic",
            "outcome": "accepted", "final_revenue": final_revenue, "final_clause": final_clause,
        })
        finances["teams"][str(args.team)]["sponsors_owned"] = owned
        finances["teams"][str(args.team)]["sponsorship_revenue"] = finances["teams"][str(args.team)].get("sponsorship_revenue", 0) + final_revenue
        save_json("team_finances.json", finances)

    n_required = config.get("sponsorship_categories_required", 6)
    filled = len({s["category"] for s in owned if s["outcome"] != "walk_away"})
    print(f"{team_name}: {filled}/{n_required} categories filled.")

    schedule_path = os.path.join(BASE, "data", "schedule.json")
    schedule = load_json("schedule.json") if os.path.exists(schedule_path) else []
    html = render_dashboard.render(players, config, deals, matches, schedule)
    with open(os.path.join(BASE, "dashboard", "index.html"), "w") as f:
        f.write(html)
    print("Dashboard re-rendered. Re-run render_sponsorship_site.py and republish both to make it live.")


if __name__ == "__main__":
    main()
