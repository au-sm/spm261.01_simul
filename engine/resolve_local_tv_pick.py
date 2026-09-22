"""
Records one team's NEGOTIATED Local TV Deal rate -- either a LIVE deal
(you type in exactly what two students agreed to, crediting a
commission to whoever played the network rep) or ALGORITHMIC (leverage
decides everything, no live counterpart, no commission).

This is the Local TV Deal ONLY. The League-Wide (National) TV Deal
stays fully automatic -- it is one shared league-wide split (a base
payment plus a standings/Star Power bonus applied identically to every
team), with no natural second party to negotiate against, unlike a
market-specific regional broadcast contract. See engine/negotiation.py
for the shared leverage/revenue-axis math (the exact same -10%/+10%
mechanic already used for Sponsorship Revenue) and
engine/generate_tv_negotiation_rotation.py for who negotiates with whom.

Unlike Sponsorship, there is no clause axis here and no brand choice --
every team already has exactly one Local TV Deal, fixed by its
randomly assigned market tier (data/local_tv_deals.json). Negotiating
only ever moves that ONE number, and only once per team (re-running
this for a team that already negotiated is refused).

IMPORTANT -- this does NOT pay anyone yet. Local TV money is still
paid out at the Round 3 split, same as before, with the Star Power
modifier (+15% for a top-3 starting-XI at that time) still applied on
top. All this script does is replace the flat market-tier base with
the NEGOTIATED number that the Round 3 payout step will use instead
-- exactly like a real regional broadcast contract is negotiated once,
long before the checks it generates ever get cut. Writes to
data/local_tv_deals.json, not data/team_finances.json.

LIVE MODE (the normal path for the in-class negotiation exercise):
    python3 engine/resolve_local_tv_pick.py --team 3 \\
        --live --final-revenue 770000 --network-rep-team 17

  Team 3 is Mid Market ($700,000 base), so the live-negotiated
  $770,000 rate credits a $70,000 commission to Team 17, whoever
  played the network rep in that negotiation -- booked immediately
  (the commission is a reward for negotiating skill, not TV money
  itself, so it doesn't wait for the Round 3 split).

  The mirror case is rewarded too: if the rep instead talks the team
  down BELOW base (a good deal for the network), the same size
  commission -- the savings, base minus final_revenue -- is credited
  to the rep's team instead, same immediate booking. Either direction
  requires --network-rep-team (only an exact match to base needs no
  rep). Never a deduction from the negotiating team's own rate --
  always additive, on top of whatever they locked in, in both
  directions.

ALGORITHMIC MODE (practice / fallback if a team never got a live
negotiation -- no human played network rep, so no commission applies):
    python3 engine/resolve_local_tv_pick.py --team 3 --take-base
    python3 engine/resolve_local_tv_pick.py --team 3 --negotiate
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from negotiation import compute_leverage, resolve_revenue
from simulate import Standings
import render_dashboard

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def save_json(name, data):
    with open(os.path.join(BASE, "data", name), "w") as f:
        json.dump(data, f, indent=2)


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

    ap.add_argument("--live", action="store_true", help="record an already-negotiated live rate")
    ap.add_argument("--final-revenue", type=int, help="[live] the exact agreed season rate")
    ap.add_argument("--network-rep-team", type=int, help="[live] team whose student played network rep (receives a commission whenever the rate differs from base, either direction)")

    ap.add_argument("--take-base", action="store_true", help="[algorithmic] take the market-tier base exactly, no negotiation")
    ap.add_argument("--negotiate", action="store_true", help="[algorithmic] resolve the rate via leverage formula")
    args = ap.parse_args()

    config = load_json("league_config.json")
    finances = load_json("team_finances.json")
    matches = load_json("matches.json")
    players = render_dashboard.load_players()

    ltv_path = os.path.join(BASE, "data", "local_tv_deals.json")
    if not os.path.exists(ltv_path):
        print("ERROR: data/local_tv_deals.json not found -- run generate_local_tv_deals.py first."); return
    ltv = load_json("local_tv_deals.json")

    team_ids = [t["team_id"] for t in config["teams"]]
    team_name = next((t["name"] for t in config["teams"] if t["team_id"] == args.team), None)
    if team_name is None:
        print(f"ERROR: no team with id {args.team}"); return

    assignment = next((a for a in ltv["assignments"] if a["team_id"] == args.team), None)
    if assignment is None:
        print(f"ERROR: {team_name} has no Local TV Deal assignment -- run generate_local_tv_deals.py first."); return
    base_revenue = assignment["base_revenue"]

    if assignment.get("negotiated"):
        print(f"ERROR: {team_name}'s Local TV Deal rate is already negotiated "
              f"({assignment['mode']}, ${assignment['negotiated_revenue']:,}/season). Not re-resolving."); return

    if team_avg_star_power(args.team, players) is None:
        print(f"ERROR: {team_name} has no drafted players yet -- run the player draft first."); return

    # ---------------- LIVE MODE ----------------
    if args.live:
        if args.final_revenue is None:
            print("ERROR: --live requires --final-revenue"); return

        commission = 0
        rep_team_name = None
        if args.final_revenue != base_revenue:
            direction = "above" if args.final_revenue > base_revenue else "below"
            if args.network_rep_team is None:
                print(f"ERROR: negotiated rate (${args.final_revenue:,}) is {direction} base (${base_revenue:,}), "
                      f"so --network-rep-team is required to credit the ${abs(args.final_revenue - base_revenue):,} commission."); return
            rep_team_name = next((t["name"] for t in config["teams"] if t["team_id"] == args.network_rep_team), None)
            if rep_team_name is None:
                print(f"ERROR: no team with id {args.network_rep_team}"); return
            commission = abs(args.final_revenue - base_revenue)

        assignment["negotiated"] = True
        assignment["mode"] = "live"
        assignment["negotiated_revenue"] = args.final_revenue
        assignment["network_rep_team_id"] = args.network_rep_team
        save_json("local_tv_deals.json", ltv)

        print(f"\n{team_name} ({assignment['market_tier']}): Local TV Deal rate negotiated at ${args.final_revenue:,}/season "
              f"(base ${base_revenue:,}). Still paid out at the Round 3 split, plus Star Power bonus if earned then.")

        if commission > 0:
            direction = "above" if args.final_revenue > base_revenue else "below"
            rep_key = str(args.network_rep_team)
            rep_fin = finances["teams"].setdefault(rep_key, {})
            rep_fin.setdefault("tv_commissions_earned", []).append({
                "negotiating_team": team_name, "commission_amount": commission, "direction": direction,
            })
            rep_fin["local_tv_revenue"] = rep_fin.get("local_tv_revenue", 0) + commission
            finances["teams"][rep_key] = rep_fin
            save_json("team_finances.json", finances)
            print(f"{rep_team_name} earns a ${commission:,} commission for playing the network rep "
                  f"(rate closed ${commission:,} {direction} base) -- booked now, not at the Round 3 split.")

    # ---------------- ALGORITHMIC MODE ----------------
    else:
        if not (args.take_base or args.negotiate):
            print("ERROR: pick one of --take-base or --negotiate (or use --live to record an already-negotiated rate)"); return

        avg_star = team_avg_star_power(args.team, players)
        rank = team_standing_rank(args.team, matches, team_ids)
        leverage = compute_leverage(avg_star, standings_rank=rank, n_teams=len(team_ids))

        final_revenue, commission = resolve_revenue(base_revenue, take_base=args.take_base, leverage=leverage)

        print(f"\n{team_name} ({assignment['market_tier']})  (avg Star Power {avg_star:.0f}, leverage {leverage:.0f})")
        print(f"  Negotiated rate: ${final_revenue:,}/season (base ${base_revenue:,}). "
              f"{'(no live network rep, so no commission credited)' if commission else ''}")
        print("  Still paid out at the Round 3 split, plus Star Power bonus if earned then.")

        assignment["negotiated"] = True
        assignment["mode"] = "algorithmic"
        assignment["negotiated_revenue"] = final_revenue
        save_json("local_tv_deals.json", ltv)

    schedule_path = os.path.join(BASE, "data", "schedule.json")
    schedule = load_json("schedule.json") if os.path.exists(schedule_path) else []
    deals = load_json("deals.json")
    html = render_dashboard.render(players, config, deals, matches, schedule)
    with open(os.path.join(BASE, "dashboard", "index.html"), "w") as f:
        f.write(html)
    print("Dashboard re-rendered. Re-run render_sponsorship_site.py and republish both to make it live.")


if __name__ == "__main__":
    main()
