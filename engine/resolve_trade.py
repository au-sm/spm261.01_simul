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


def open_session(sessions, matches):
    """Index of the trade session that is open right now, or None.
    Sessions run in order; each stays open until its closes_before_round
    has been simulated (rounds are simulated manually, so this follows
    matches.json, not the calendar). A session whose closes_before_round
    is still null hasn't been scheduled yet, so nothing after it is open."""
    played = max((m["round"] for m in matches if m.get("stage", "regular") == "regular"), default=0)
    for i, s in enumerate(sessions):
        close = s.get("closes_before_round")
        if close is None:
            return None
        if played < close:
            return i
    return None


def team_cap_used(players_by_id, team_id):
    return sum(int(p["salary"]) for p in players_by_id.values()
               if p["team_id"] not in ("", None) and int(p["team_id"]) == team_id)


def team_available_cash(finances, config, trades_state, team_id):
    rec = finances["teams"].get(str(team_id), {})
    revenue_total = sum(rec.get(f, 0) for f in
                         ("ticket_revenue", "sponsorship_revenue", "local_tv_revenue", "tv_revenue"))
    trade_cash_net = trades_state.get("team_cash_net", {}).get(str(team_id), 0)
    import health  # Health Hub treatments are paid from this same cash pool
    return config.get("starting_budget", 0) + revenue_total + trade_cash_net - health.team_spend(team_id)


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
    state.setdefault("session_trade_count", {})
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
    sessions = load_json("deals.json")["trade_rules"]["sessions"]
    matches = load_json("matches.json")
    finances = load_json("team_finances.json")
    players = load_players()
    players_by_id = {int(p["player_id"]): p for p in players}
    team_ids = {t["team_id"] for t in config["teams"]}
    salary_cap = config.get("salary_cap", 0)
    session = open_session(sessions, matches)
    today = datetime.date.today().isoformat()

    applied_count = 0
    for prop in proposals:
        pid = prop["proposal_id"]
        if pid in already_done or prop.get("status") != "accepted":
            continue  # still pending/declined, or already resolved earlier -- nothing to do

        def void(reason):
            trades["voided"].append({**prop, "void_reason": reason, "voided_at": today})

        if session is None:
            void("No trade session is open right now -- this trade never took effect.")
            continue
        session_counts = trades["session_trade_count"].setdefault(str(session), {})

        try:
            proposer = int(prop["proposer_team_id"])
            receiver = None if prop.get("receiver_team_id") in ("", None) else int(prop["receiver_team_id"])
        except (TypeError, ValueError):
            void("Malformed team id on this proposal.")
            continue
        if proposer not in team_ids or proposer == receiver or (receiver is not None and receiver not in team_ids):
            void("Invalid team(s) on this proposal.")
            continue

        # A deal mixes a team-to-team swap with free-agent swaps: players
        # flagged fa=True on the way out are released to the free-agent
        # pool, and fa=True on the way in are signed from it.
        out_ids = [int(p["id"]) for p in prop.get("players_out", [])]
        in_ids = [int(p["id"]) for p in prop.get("players_in", [])]
        released = [int(p["id"]) for p in prop.get("players_out", []) if p.get("fa")]
        signed = [int(p["id"]) for p in prop.get("players_in", []) if p.get("fa")]
        to_partner = [i for i in out_ids if i not in released]
        from_partner = [i for i in in_ids if i not in signed]
        if not 1 <= len(out_ids) <= 3 or len(out_ids) != len(in_ids):
            void("A deal must send out and bring in the same number of players (1 to 3).")
            continue
        if len(to_partner) != len(from_partner) or (from_partner and receiver is None):
            void("Players swapped with the partner team must match one-for-one.")
            continue

        # Roster ownership -- re-verified here since backend.gs has no
        # roster data to check this against at submission time.
        def on_team(i, team):
            return (i in players_by_id and players_by_id[i]["team_id"] not in ("", None)
                    and int(players_by_id[i]["team_id"]) == team)
        if not all(on_team(i, proposer) for i in out_ids):
            void("One or more outgoing players are no longer on the proposing team's roster.")
            continue
        if not all(on_team(i, receiver) for i in from_partner):
            void("One or more incoming players are no longer on the receiving team's roster.")
            continue
        if not all(i in players_by_id and players_by_id[i]["team_id"] in ("", None) for i in signed):
            void("One or more free agents in this deal have already been signed by another team.")
            continue

        count = len(out_ids)
        partner_count = len(from_partner)
        proposer_count = session_counts.get(str(proposer), 0)
        receiver_count = session_counts.get(str(receiver), 0)
        if proposer_count + count > 3:
            void(f"Would put the proposing team over its 3 players for {sessions[session]['name']} ({proposer_count} already moved).")
            continue
        if receiver is not None and receiver_count + partner_count > 3:
            void(f"Would put the receiving team over its 3 players for {sessions[session]['name']} ({receiver_count} already moved).")
            continue

        salary = lambda ids: sum(int(players_by_id[i]["salary"]) for i in ids)
        proposer_cap_after = team_cap_used(players_by_id, proposer) - salary(out_ids) + salary(in_ids)
        receiver_cap_after = (team_cap_used(players_by_id, receiver) - salary(from_partner) + salary(to_partner)
                              if receiver is not None else 0)
        if proposer_cap_after > salary_cap:
            void(f"Would put the proposing team over the salary cap (${proposer_cap_after:,} > ${salary_cap:,}).")
            continue
        if receiver_cap_after > salary_cap:
            void(f"Would put the receiving team over the salary cap (${receiver_cap_after:,} > ${salary_cap:,}).")
            continue

        cash_from_proposer = int(prop.get("cash_from_proposer") or 0) if receiver is not None else 0
        cash_from_receiver = int(prop.get("cash_from_receiver") or 0) if receiver is not None else 0
        if cash_from_proposer > team_available_cash(finances, config, trades, proposer):
            void("Proposing team does not have enough cash on hand for this trade.")
            continue
        if cash_from_receiver > team_available_cash(finances, config, trades, receiver):
            void("Receiving team does not have enough cash on hand for this trade.")
            continue

        # everything checks out -- apply it
        for i in to_partner:
            players_by_id[i]["team_id"] = str(receiver)
        for i in released:
            players_by_id[i]["team_id"] = ""
        for i in in_ids:
            players_by_id[i]["team_id"] = str(proposer)

        moved = {proposer: count}
        if receiver is not None:
            moved[receiver] = partner_count
        for t, n in moved.items():
            session_counts[str(t)] = session_counts.get(str(t), 0) + n
            trades["team_trade_count"][str(t)] = trades["team_trade_count"].get(str(t), 0) + n
        if receiver is not None:
            net_to_proposer = cash_from_receiver - cash_from_proposer
            trades["team_cash_net"][str(proposer)] = trades["team_cash_net"].get(str(proposer), 0) + net_to_proposer
            trades["team_cash_net"][str(receiver)] = trades["team_cash_net"].get(str(receiver), 0) - net_to_proposer

        trades["applied"].append({**prop, "applied_at": today})
        applied_count += 1
        print(f"  Applied trade {pid}: team {proposer} <-> team {receiver} ({count} out/in, {len(signed)} free agent)")

    save_players(list(players_by_id.values()))
    save_json("trades.json", trades)
    print(f"resolve_trade.py: {applied_count} trade(s) applied, {len(proposals)} proposal(s) considered.")


if __name__ == "__main__":
    main()
