"""
Applies student-submitted team names to data/league_config.json, from
the Team Name Submission form (see forms/google_form_specs.md).

WHY THIS MATCHES BY OWNER, NOT BY THE CURRENT TEAM NAME: every other
form in this league (Draft Board, Weekly Lineup) identifies a team by
its "Team name" field, matched as a literal string against
league_config.json -> teams[i].name. That is exactly the field this
script is about to change -- matching the incoming CSV against the OLD
name would be circular and fragile (a typo in what a student re-types
as their "old" name silently fails). The owner field, once real student
names are loaded, is what's actually stable across a rename, so that's
the join key here.

CONSEQUENCE FOR STUDENTS: once a team's name changes, every Draft
Board / Weekly Lineup submission from that point on must use the NEW
name, not "Team 1" -- resolve_draft.py and resolve_round.py both match
on that literal string. Run this BEFORE Draft Day if at all possible so
the Draft Board form can go out with real names already in place; if it
runs after some rounds are already resolved, matches.json/team_finances.json
are keyed by team_id and are unaffected by the rename.

Usage:
    python3 engine/resolve_team_names.py --csv team_names_responses.csv

Expected CSV columns (exact Google Forms export header text):
    Owner Name, Team Name
"""
import argparse
import csv
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def save_json(name, data):
    with open(os.path.join(BASE, "data", name), "w") as f:
        json.dump(data, f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    args = ap.parse_args()

    config = load_json("league_config.json")
    teams_by_owner = {t["owner"].strip().lower(): t for t in config["teams"] if t.get("owner")}

    with open(args.csv) as f:
        rows = list(csv.DictReader(f))

    applied, errors = [], []
    seen_new_names = {}  # new_name.lower() -> owner, to catch two students picking the same name
    for row in rows:
        owner = (row.get("Owner Name") or "").strip()
        new_name = (row.get("Team Name") or "").strip()
        if not owner or not new_name:
            errors.append(f"blank Owner Name or Team Name in row: {row}")
            continue

        team = teams_by_owner.get(owner.lower())
        if team is None:
            errors.append(f"no team found with owner '{owner}' -- check spelling against league_config.json")
            continue

        key = new_name.lower()
        if key in seen_new_names and seen_new_names[key] != owner:
            errors.append(f"'{new_name}' requested by both {seen_new_names[key]} and {owner} -- names must be unique "
                           f"(Weekly Lineup matching depends on it)")
            continue
        seen_new_names[key] = owner

        old_name = team["name"]
        if old_name != new_name:
            applied.append((owner, old_name, new_name))
            team["name"] = new_name

    if errors:
        print("ERRORS -- fix these rows and re-run (no changes written):")
        for e in errors:
            print(f"  - {e}")
        return

    print(f"{len(applied)} team name change(s):")
    for owner, old, new in applied:
        print(f"  {owner}: '{old}' -> '{new}'")

    if args.dry_run:
        print("\n--dry-run: no files written.")
        return

    save_json("league_config.json", config)
    print("\nSaved -> data/league_config.json")
    print("Re-run engine/render_dashboard.py and engine/render_rulebook.py, then republish both, "
          "so the new names show up live. Tell students their NEW team name is now required on "
          "every future Draft Board / Weekly Lineup submission.")


if __name__ == "__main__":
    main()
