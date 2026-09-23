"""
Resolves the Player Draft from pre-submitted Draft Boards.

WHY NOT A LIVE PICK-BY-PICK DRAFT: a real snake draft is 18 rounds x 20
teams = 360 sequential picks. Even at a brisk 1 minute per pick that's 6
hours -- not a single class period. So the "draft" a student experiences
is: submit a ranked Draft Board of AT LEAST 25 players (more than the 18
they need, so they still have real choices left if their top targets are
gone) before Draft Day, via the Draft Board form. Draft Day itself is a
live REVEAL -- this script runs in front of the class in seconds and
projects the resulting rosters, not a slow round-by-round wait.

DRAFT ORDER: one randomized snake order (round 1 picks 1..N, round 2
picks N..1, alternating), drawn reproducibly from league_config.json's
season_seed -- same reproducibility principle as everything else in this
engine (match results, local TV tiers, negotiation/trade-day pairings).

PER-PICK RESOLUTION: at a team's turn, walk down THEIR OWN submitted
board and take the first player who is (a) still available and (b)
affordable -- i.e. adding their salary keeps the team's running total at
or under salary_cap. If a team's whole board is exhausted before their
roster is full (bad luck -- too many of their targets were taken first),
fall back to the highest-OVR still-available, affordable player in the
whole pool -- same "league office auto-fills" philosophy already used
for a missed Weekly Lineup submission and a missed Trade Day pairing. If even that has no affordable option (shouldn't
happen -- the cheapest 18 players in the pool sum to well under the cap),
fall back again to the single cheapest still-available player, so the
draft always completes.

Usage:
    python3 engine/resolve_draft.py
"""
import csv
import json
import os
import random
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def load_players():
    with open(os.path.join(BASE, "data", "players.csv"), newline="") as f:
        return list(csv.DictReader(f))


def save_players(players, fieldnames):
    path = os.path.join(BASE, "data", "players.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(players)


def snake_order(team_ids, season_seed, roster_size):
    rng = random.Random(season_seed)
    base_order = list(team_ids)
    rng.shuffle(base_order)

    order = []
    for round_num in range(roster_size):
        order.append(list(reversed(base_order)) if round_num % 2 == 1 else list(base_order))
    return base_order, order


def resolve(config, draft_boards, players):
    team_ids = [t["team_id"] for t in config["teams"]]
    team_names = {t["team_id"]: t["name"] for t in config["teams"]}
    roster_size = config["roster_size"]
    cap = config["salary_cap"]

    by_id = {int(p["player_id"]): p for p in players}
    available = set(by_id.keys())

    board_order = {tid: list(draft_boards.get(str(tid), [])) for tid in team_ids}
    board_ptr = {tid: 0 for tid in team_ids}
    spent = {tid: 0 for tid in team_ids}
    picks_made = {tid: 0 for tid in team_ids}

    first_pick_order, rounds = snake_order(team_ids, config["season_seed"], roster_size)
    print(f"Draft order (round 1): {', '.join(team_names[t] for t in first_pick_order)}\n")

    recap = []

    def affordable_ovr_fallback(tid):
        candidates = [by_id[pid] for pid in available if spent[tid] + int(by_id[pid]["salary"]) <= cap]
        if not candidates:
            return None
        return max(candidates, key=lambda p: int(p["ovr"]))

    def cheapest_fallback(tid):
        candidates = [by_id[pid] for pid in available if spent[tid] + int(by_id[pid]["salary"]) <= cap]
        if not candidates:
            return None
        return min(candidates, key=lambda p: int(p["salary"]))

    for round_num, pick_order in enumerate(rounds, start=1):
        for tid in pick_order:
            pick = None
            source = None

            board = board_order[tid]
            ptr = board_ptr[tid]
            while ptr < len(board):
                pid = board[ptr]
                ptr += 1
                if pid in available and spent[tid] + int(by_id[pid]["salary"]) <= cap:
                    pick = by_id[pid]
                    source = "board"
                    break
            board_ptr[tid] = ptr

            if pick is None:
                pick = affordable_ovr_fallback(tid)
                source = "autopick (highest OVR affordable)"

            if pick is None:
                pick = cheapest_fallback(tid)
                source = "autopick (cheapest available)"

            if pick is None:
                raise RuntimeError(f"Player pool exhausted before {team_names[tid]} could fill round {round_num}")

            pick["team_id"] = str(tid)
            available.discard(int(pick["player_id"]))
            spent[tid] += int(pick["salary"])
            picks_made[tid] += 1

            recap.append({
                "round": round_num, "team": team_names[tid], "player": pick["name"],
                "pos": pick["position"], "ovr": pick["ovr"], "salary": int(pick["salary"]), "source": source,
            })

    return recap, spent, picks_made


def main():
    config = load_json("league_config.json")
    boards_path = os.path.join(BASE, "data", "draft_boards.json")
    if not os.path.exists(boards_path):
        print(f"No draft_boards.json found at {boards_path} -- every team will be fully autopicked.")
        draft_boards = {}
    else:
        draft_boards = load_json("draft_boards.json")

    players = load_players()
    fieldnames = list(players[0].keys())

    recap, spent, picks_made = resolve(config, draft_boards, players)

    for r in recap:
        salary_str = f"${r['salary']:,}"
        print(f"R{r['round']:<3} {r['team']:<10} {r['player']:<22} {r['pos']:<3} OVR {r['ovr']:<3} "
              f"{salary_str:<12} {'' if r['source']=='board' else '<- ' + r['source']}")

    print("\n=== Final cap usage ===")
    team_names = {t["team_id"]: t["name"] for t in config["teams"]}
    for tid in sorted(spent):
        print(f"  {team_names[tid]:<10} {picks_made[tid]}/{config['roster_size']} players -- "
              f"${spent[tid]:,} / ${config['salary_cap']:,} cap")

    save_players(players, fieldnames)
    print(f"\nSaved roster assignments -> data/players.csv")


if __name__ == "__main__":
    main()
