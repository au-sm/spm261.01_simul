"""
Applies accepted Trade Proposals -- the ones where BOTH teams have
already agreed (status "accepted" in the Sheet's TradeProposals tab,
set by the receiving team clicking Accept on the Trade Center page).

backend.gs can only check what it has: PINs, team existence, matching
player counts. It has NO roster data at all (rosters live in
data/players.csv, never synced to the Sheet), so it cannot verify a
team actually owns the players it's offering, and it cannot check the
salary cap. That real validation happens here, every auto_resolve.py
cycle, the same division of labor as resolve_round.py doing the real
match simulation while the Sheet only ever holds what was submitted.

A proposal that fails validation here -- or arrives after the Round 6
deadline -- is logged as VOIDED with a human-readable reason and never
retried; an already-decided outcome (applied or voided) never changes
on a later run, the same permanence guarantee resolve_round.py's own
guard gives a resolved match.

Usage:
    python3 engine/resolve_trade.py --proposals-file /path/to/export.json
"""
import argparse
import csv
import datetime
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def save_json(name, data):
    with open(os.path.join(BASE, "data", name), "w") as f:
        json.dump(data, f, indent=2)


def load_players():
    with open(os.path.join(BASE, "data", "players.csv"), newline="") as f:
        return list(csv.DictReader(f))


def save_players(players):
    fieldnames = list(players[0].keys())
    with open(os.path.join(BASE, "data", "players.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(players)


def trade_deadline_date(calendar):
    """The match day that resolves Round 7 -- a trade must be accepted
    and applied before this date; Round 6, whichever day it lands on,
    is the last day a trade can take effect."""
    for entry in calendar["match_day_schedule"]:
        if 7 in entry["rounds"]:
            return entry["date"]
    return None


def team_cap_used(players_by_id, team_id):
    return sum(int(p["salary"]) for p in players_by_id.values()
               if p["team_id"] not in ("", None) and int(p["team_id"]) == team_id)


def team_available_cash(finances, config, trades_state, team_id):
    rec = finances["teams"].get(str(team_id), {})
    revenue_total = sum(rec.get(f, 0) for f in
                         ("ticket_revenue", "sponsorship_revenue", "local_tv_revenue", "tv_revenue"))
    trade_cash_net = trades_state.get("team_cash_net", {}).get(str(team_id), 0)
    return config.get("starting_budget", 0) + revenue_total + trade_cash_net


def load_trades_state():
    path = os.path.join(BASE, "data", "trades.json")
    if os.path.exists(path):
        state = load_json("trades.json")
    else:
        state = {}
    state.setdefault("applied", [])
    state.setdefault("voided", [])
    state.setdefault("team_trade_count", {})
    state.setdefault("team_cash_net", {})
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proposals-file", required=True)
    args = ap.parse_args()

    with open(args.proposals_file) as f:
        proposals = json.load(f)

    trades = load_trades_state()
    already_done = {t["proposal_id"] for t in trades["applied"]} | {t["proposal_id"] for t in trades["voided"]}

    config = load_json("league_config.json")
    calendar = load_json("season_calendar.json")
    finances = load_json("team_finances.json")
    players = load_players()
    players_by_id = {int(p["player_id"]): p for p in players}
    team_ids = {t["team_id"] for t in config["teams"]}
    salary_cap = config.get("salary_cap", 0)
    deadline = trade_deadline_date(calendar)
    today = datetime.date.today().isoformat()

    applied_count = 0
    for prop in proposals:
        pid = prop["proposal_id"]
        if pid in already_done or prop.get("status") != "accepted":
            continue  # still pending/declined, or already resolved earlier -- nothing to do

        def void(reason):
            trades["voided"].append({**prop, "void_reason": reason, "voided_at": today})

        if deadline and today >= deadline:
            void(f"Trade deadline has passed (Round 7's match day is {deadline}) -- this trade never took effect.")
            continue

        try:
            proposer = int(prop["proposer_team_id"])
            receiver = int(prop["receiver_team_id"])
        except (TypeError, ValueError):
            void("Malformed team id on this proposal.")
            continue
        if proposer == receiver or proposer not in team_ids or receiver not in team_ids:
            void("Invalid team(s) on this proposal.")
            continue

        out_ids = [int(p["id"]) for p in prop.get("players_out", [])]
        in_ids = [int(p["id"]) for p in prop.get("players_in", [])]
        if not out_ids or len(out_ids) != len(in_ids) or len(out_ids) > 3:
            void("Player counts must match on both sides (1-for-1, 2-for-2, or 3-for-3).")
            continue

        # Roster ownership -- re-verified here since backend.gs has no
        # roster data to check this against at submission time.
        bad_out = any(i not in players_by_id or players_by_id[i]["team_id"] in ("", None)
                       or int(players_by_id[i]["team_id"]) != proposer for i in out_ids)
        bad_in = any(i not in players_by_id or players_by_id[i]["team_id"] in ("", None)
                      or int(players_by_id[i]["team_id"]) != receiver for i in in_ids)
        if bad_out:
            void("One or more outgoing players are no longer on the proposing team's roster.")
            continue
        if bad_in:
            void("One or more incoming players are no longer on the receiving team's roster.")
            continue

        count = len(out_ids)
        proposer_count = trades["team_trade_count"].get(str(proposer), 0)
        receiver_count = trades["team_trade_count"].get(str(receiver), 0)
        if proposer_count + count > 3:
            void(f"Would put the proposing team over the 3-player season trade limit ({proposer_count} already traded).")
            continue
        if receiver_count + count > 3:
            void(f"Would put the receiving team over the 3-player season trade limit ({receiver_count} already traded).")
            continue

        out_salary = sum(int(players_by_id[i]["salary"]) for i in out_ids)
        in_salary = sum(int(players_by_id[i]["salary"]) for i in in_ids)
        proposer_cap_after = team_cap_used(players_by_id, proposer) - out_salary + in_salary
        receiver_cap_after = team_cap_used(players_by_id, receiver) - in_salary + out_salary
        if proposer_cap_after > salary_cap:
            void(f"Would put the proposing team over the salary cap (${proposer_cap_after:,} > ${salary_cap:,}).")
            continue
        if receiver_cap_after > salary_cap:
            void(f"Would put the receiving team over the salary cap (${receiver_cap_after:,} > ${salary_cap:,}).")
            continue

        cash_from_proposer = int(prop.get("cash_from_proposer") or 0)
        cash_from_receiver = int(prop.get("cash_from_receiver") or 0)
        if cash_from_proposer > team_available_cash(finances, config, trades, proposer):
            void("Proposing team does not have enough cash on hand for this trade.")
            continue
        if cash_from_receiver > team_available_cash(finances, config, trades, receiver):
            void("Receiving team does not have enough cash on hand for this trade.")
            continue

        # everything checks out -- apply it
        for i in out_ids:
            players_by_id[i]["team_id"] = str(receiver)
        for i in in_ids:
            players_by_id[i]["team_id"] = str(proposer)

        trades["team_trade_count"][str(proposer)] = proposer_count + count
        trades["team_trade_count"][str(receiver)] = receiver_count + count
        net_to_proposer = cash_from_receiver - cash_from_proposer
        trades["team_cash_net"][str(proposer)] = trades["team_cash_net"].get(str(proposer), 0) + net_to_proposer
        trades["team_cash_net"][str(receiver)] = trades["team_cash_net"].get(str(receiver), 0) - net_to_proposer

        trades["applied"].append({**prop, "applied_at": today})
        applied_count += 1
        print(f"  Applied trade {pid}: team {proposer} <-> team {receiver} ({count}-for-{count})")

    save_players(list(players_by_id.values()))
    save_json("trades.json", trades)
    print(f"resolve_trade.py: {applied_count} trade(s) applied, {len(proposals)} proposal(s) considered.")


if __name__ == "__main__":
    main()
