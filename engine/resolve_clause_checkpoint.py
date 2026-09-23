"""
Runs the ONE-TIME clause checkpoint (see data/deals.json ->
clause_enforcement). Run this once, at season end, after the round
named in clause_enforcement.checkpoint_round has been resolved via
resolve_round.py -- running it twice would double-claw teams that
already missed a threshold at the first run (each sponsor entry, and
each Local TV deal, is marked "clawed_back": true after processing
specifically to prevent that, and this script skips any entry already
marked).

Checks BOTH deal types that carry a clause: every sponsor in
team_finances.json's sponsors_owned, AND every team's Local TV Deal in
data/local_tv_deals.json's assignments (only once it has been
negotiated and has a final_clause -- an unresolved deal isn't
penalized). Same table, same mechanic, same rank-threshold lookup for
both.

Each clause level has its OWN rank threshold the team must hit to keep
that specific deal's revenue -- strict demands a strict standard (top
5), loose only asks for an easy one (top 15). Miss the threshold and
that deal claws back a flat 20%, regardless of which clause level it
was. This is evaluated PER DEAL, using the team's ONE final rank --
a team can clear a loose-clause deal's bar while missing a strict-
clause deal's bar in the same season (whether those two deals are both
sponsors, both the Local TV deal and a sponsor, etc.).

NOTE -- this enforcement is correctly wired but currently INERT for
Local TV deals in practice: engine/resolve_tv_split.py (the script
that would actually pay Local TV revenue into a team's
local_tv_revenue at the Round 3 split) does not exist yet. Until that
script exists, local_tv_revenue is never populated, so a clawback here
computes against $0 (a no-op in dollar terms) even though the clause
outcome is still correctly recorded. That's a separate, pre-existing
gap -- not something this script needs to fix.

Usage:
    python3 engine/resolve_clause_checkpoint.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from simulate import Standings

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def save_json(name, data):
    with open(os.path.join(BASE, "data", name), "w") as f:
        json.dump(data, f, indent=2)


def main():
    config = load_json("league_config.json")
    deals = load_json("deals.json")
    finances = load_json("team_finances.json")
    matches = load_json("matches.json")
    ltv_path = os.path.join(BASE, "data", "local_tv_deals.json")
    ltv = load_json("local_tv_deals.json") if os.path.exists(ltv_path) else None

    rule = deals["clause_enforcement"]
    checkpoint_round = rule["checkpoint_round"]
    penalty_pct = rule["penalty_pct"]
    thresholds = rule["rank_threshold_by_clause"]

    played_rounds = {m["round"] for m in matches if m.get("stage", "regular") == "regular"}
    if checkpoint_round not in played_rounds:
        print(f"Round {checkpoint_round} has not been resolved yet (played rounds: {sorted(played_rounds) or 'none'}). "
              f"Run resolve_round.py through round {checkpoint_round} first.")
        return

    team_ids = [t["team_id"] for t in config["teams"]]
    team_names = {t["team_id"]: t["name"] for t in config["teams"]}

    st = Standings(team_ids)
    for m in matches:
        if m.get("stage", "regular") == "regular" and m["round"] <= checkpoint_round:
            st.record(m["home_id"], m["away_id"], m["home_goals"], m["away_goals"])
    ranked = [tid for tid, _ in st.ranked()]
    rank_of = {tid: i + 1 for i, tid in enumerate(ranked)}  # 1-indexed final rank

    print(f"Clause checkpoint at Round {checkpoint_round} (season end). Final standings locked in.\n")

    total_clawed = 0
    any_sponsor_deals = any(rec.get("sponsors_owned") for rec in finances["teams"].values())
    any_tv_deals = bool(ltv and any(a.get("negotiated") and a.get("final_clause") for a in ltv["assignments"]))
    any_deals_at_all = any_sponsor_deals or any_tv_deals
    any_newly_processed = False
    ltv_changed = False

    for tid_str, rec in finances["teams"].items():
        tid = int(tid_str)
        team_rank = rank_of.get(tid)
        for deal in rec.get("sponsors_owned", []):
            if deal["outcome"] == "walk_away" or deal.get("clawed_back"):
                continue
            any_newly_processed = True
            deal["clawed_back"] = True

            threshold = thresholds.get(deal["final_clause"])
            if threshold is None:
                continue  # "none" clause: never penalized

            if team_rank is not None and team_rank > threshold:
                amount = round(deal["final_revenue"] * penalty_pct)
                if amount > 0:
                    deal["clawback_amount"] = amount
                    rec["sponsorship_revenue"] -= amount
                    total_clawed += amount
                    print(f"  {team_names[tid]} (final rank {team_rank}, needed top {threshold} for its "
                          f"{deal['final_clause']} clause): {deal['sponsor']} claws back "
                          f"{int(penalty_pct*100)}% = ${amount:,}")

    # Local TV deals -- same table, same mechanic, only skip a deal that
    # was never negotiated (no final_clause) since an unresolved deal
    # shouldn't be penalized.
    if ltv:
        for assignment in ltv["assignments"]:
            if not assignment.get("negotiated") or not assignment.get("final_clause") or assignment.get("clawed_back"):
                continue
            any_newly_processed = True
            ltv_changed = True
            assignment["clawed_back"] = True
            tid = assignment["team_id"]
            team_rank = rank_of.get(tid)

            threshold = thresholds.get(assignment["final_clause"])
            if threshold is None:
                continue  # "none" clause: never penalized

            if team_rank is not None and team_rank > threshold:
                amount = round(assignment["negotiated_revenue"] * penalty_pct)
                if amount > 0:
                    assignment["clawback_amount"] = amount
                    rec = finances["teams"].setdefault(str(tid), {})
                    rec["local_tv_revenue"] = rec.get("local_tv_revenue", 0) - amount
                    total_clawed += amount
                    print(f"  {team_names.get(tid, assignment['team_name'])} (final rank {team_rank}, needed top "
                          f"{threshold} for its {assignment['final_clause']} clause): Local TV Deal claws back "
                          f"{int(penalty_pct*100)}% = ${amount:,} "
                          f"(inert in practice until Round 3 TV payouts exist -- see module docstring)")

    if not any_deals_at_all:
        print("No signed sponsors or negotiated Local TV deals found yet -- nothing to check.")
        return
    if not any_newly_processed:
        print("Every signed sponsor and negotiated Local TV deal was already checked at a previous run of this script -- nothing new to do.")
        return

    save_json("team_finances.json", finances)
    if ltv_changed:
        save_json("local_tv_deals.json", ltv)
    print(f"\nTotal clawed back league-wide: ${total_clawed:,}")
    print("team_finances.json" + (" and local_tv_deals.json" if ltv_changed else "") +
          " updated. Re-render the dashboard, sponsorship site, and TV site to make it live.")


if __name__ == "__main__":
    main()
