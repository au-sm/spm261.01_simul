"""
Converts the Draft Board form's CSV export (real player NAMES, typed by
students) into data/draft_boards.json -- the {"team_id": [player_id, ...]}
shape engine/resolve_draft.py actually reads. Without this script, that
conversion is manual: looking up every name a student typed against
data/players.csv by hand, for every team, before Draft Day can run --
see forms/google_form_specs.md's Draft Board section, which describes
the shape but never automated getting there.

Matches teams by the "Team name" column (must already equal the real
team name on file -- run engine/resolve_team_names.py first if names
are still placeholders) and players by exact name (case-insensitive)
against data/players.csv. Reports every unmatched name (typo, wrong
player, retired/traded name) instead of silently dropping it, same
validate-everything-before-writing-anything convention as
resolve_round.py and resolve_team_names.py.

Usage:
    python3 engine/build_draft_boards.py --csv draft_board_responses.csv
    python3 engine/build_draft_boards.py --csv draft_board_responses.csv --dry-run

Expected CSV columns (exact Google Forms export header text):
    Team name, Ranked player list (at least 25 names, most-wanted first)
"""
import argparse
import csv
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD_COLUMN = "Ranked player list (at least 25 names, most-wanted first)"
MIN_RECOMMENDED = 25


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def save_json(name, data):
    with open(os.path.join(BASE, "data", name), "w") as f:
        json.dump(data, f, indent=2)


def parse_names(cell):
    return [n.strip() for n in (cell or "").splitlines() if n.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--dry-run", action="store_true", help="show what would be written, write nothing")
    args = ap.parse_args()

    config = load_json("league_config.json")
    team_by_name = {t["name"].strip().lower(): t["team_id"] for t in config["teams"]}

    with open(os.path.join(BASE, "data", "players.csv"), newline="") as f:
        players = list(csv.DictReader(f))
    player_id_by_name = {}
    dupes = set()
    for p in players:
        key = p["name"].strip().lower()
        if key in player_id_by_name:
            dupes.add(p["name"])
        player_id_by_name[key] = p["player_id"]
    if dupes:
        print("WARNING: these player names appear more than once in players.csv -- "
              "board matching used whichever row loaded last:")
        for d in sorted(dupes):
            print(f"  - {d}")

    with open(args.csv) as f:
        rows = list(csv.DictReader(f))

    boards = {}
    errors = []
    warnings = []
    seen_teams = set()

    for row in rows:
        team_name = (row.get("Team name") or "").strip()
        if not team_name:
            errors.append(f"blank Team name in row: {row}")
            continue
        team_id = team_by_name.get(team_name.lower())
        if team_id is None:
            errors.append(f"'{team_name}' does not match any team in league_config.json -- "
                           f"check spelling, or run resolve_team_names.py first if names changed")
            continue
        if team_name.lower() in seen_teams:
            errors.append(f"'{team_name}' submitted a Draft Board more than once -- only one allowed")
            continue
        seen_teams.add(team_name.lower())

        names = parse_names(row.get(BOARD_COLUMN))
        if not names:
            errors.append(f"'{team_name}': Draft Board is empty")
            continue

        player_ids, seen_names = [], set()
        for n in names:
            key = n.strip().lower()
            if key in seen_names:
                warnings.append(f"'{team_name}': '{n}' listed twice -- kept first occurrence only")
                continue
            seen_names.add(key)
            pid = player_id_by_name.get(key)
            if pid is None:
                errors.append(f"'{team_name}': '{n}' does not match any player in data/players.csv "
                               f"-- check spelling")
                continue
            player_ids.append(pid)

        if len(player_ids) < MIN_RECOMMENDED:
            warnings.append(f"'{team_name}': only {len(player_ids)} valid names on board "
                             f"(recommended at least {MIN_RECOMMENDED}) -- team may get autopicked "
                             f"into some slots if their targets are gone")

        boards[str(team_id)] = player_ids

    missing_teams = [t["name"] for t in config["teams"] if t["name"].lower() not in seen_teams]

    if errors:
        print(f"ERRORS -- fix these and re-run (no file written):")
        for e in errors:
            print(f"  - {e}")
        return

    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
        print()

    print(f"{len(boards)} team board(s) parsed successfully.")
    if missing_teams:
        print(f"{len(missing_teams)} team(s) did NOT submit a board -- will be fully autopicked on Draft Day:")
        for t in missing_teams:
            print(f"  - {t}")

    if args.dry_run:
        print("\n--dry-run: no files written.")
        return

    save_json("draft_boards.json", boards)
    print("\nSaved -> data/draft_boards.json")
    print("Ready to run: python3 engine/resolve_draft.py")


if __name__ == "__main__":
    main()
