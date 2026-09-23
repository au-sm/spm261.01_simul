"""
Pulls live submissions (Teams/DraftBoards/Lineups) from the Apps Script
backend's admin export and writes them into the exact local shapes the
existing resolve_draft.py / resolve_round.py / resolve_team_names.py
already expect -- so those scripts stay completely unchanged, this is
just the bridge between "data lives in a Google Sheet now" and "the
engine still reads local files".

Requires the ADMIN_KEY env var (a GitHub Actions repo secret -- NEVER
hardcode it here, this repo is public). BACKEND_URL is not secret, it's
already public in assets/config.js.

Usage:
    ADMIN_KEY=... python3 engine/pull_submissions.py
"""
import csv
import json
import os
import sys
import urllib.request

BACKEND_URL = "https://script.google.com/macros/s/AKfycbzt5f3v5N02PlkztMKRtVTSCjgJmsISm_R_KA7LgIZhANrsYY-cbrDtp5ng9Jp7qdQd7g/exec"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LINEUP_CSV_FIELDS = [
    "Team name", "Team PIN", "Formation", "Strategy",
    "Starting Goalkeeper", "Starting Defenders", "Starting Midfielders", "Starting Forwards",
    "Ticket Price", "Decision rationale (2-4 sentences)",
]


def fetch_admin_export():
    admin_key = os.environ.get("ADMIN_KEY")
    if not admin_key:
        print("ERROR: ADMIN_KEY env var not set.")
        sys.exit(1)
    url = f"{BACKEND_URL}?admin_key={admin_key}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.load(resp)
    if not data.get("ok"):
        print("ERROR: backend export failed:", data)
        sys.exit(1)
    return data


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def save_json(name, data):
    with open(os.path.join(BASE, "data", name), "w") as f:
        json.dump(data, f, indent=2)


def sync_team_names(sheet_teams):
    """Updates local league_config.json team names from the Sheet's Teams
    tab (the live, renameable copy) -- idempotent, safe to run every time.
    Returns True if anything actually changed."""
    config = load_json("league_config.json")
    by_id = {str(t["id"]): t for t in sheet_teams}
    changed = False
    for t in config["teams"]:
        sheet_row = by_id.get(str(t["team_id"]))
        if sheet_row and sheet_row["name"] != t["name"]:
            t["name"] = sheet_row["name"]
            changed = True
    if changed:
        save_json("league_config.json", config)
    return changed


def write_draft_boards(draft_boards):
    """{"team_id": [player_id, ...], ...} -- resolve_draft.py's expected shape."""
    out = {str(b["team_id"]): [str(pid) for pid in b["player_ids"]] for b in draft_boards}
    save_json("draft_boards.json", out)
    return out


def write_lineup_csv(lineups, round_num, team_name_by_id, team_pin_by_id):
    """Builds the CSV resolve_round.py --csv expects, for one round, from
    whichever teams actually submitted that round. The PIN column is the
    team's real on-file PIN (from the same Teams sheet the original
    submission was already validated against at write time) -- this is
    NOT a bypass of resolve_round.py's own PIN check, it's supplying the
    same already-validated fact automatically instead of a human
    re-typing it. Returns (path, count); count 0 means nobody submitted,
    which resolve_round.py's own missing-submission fallback (auto-lineup,
    no rationale credit) already handles correctly."""
    rows = [l for l in lineups if str(l["round"]) == str(round_num)]
    out_path = os.path.join(BASE, "data", f"_pulled_round_{round_num}.csv")
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LINEUP_CSV_FIELDS)
        w.writeheader()
        for l in rows:
            team_id = str(l["team_id"])
            w.writerow({
                "Team name": team_name_by_id.get(team_id, ""),
                "Team PIN": team_pin_by_id.get(team_id, ""),
                "Formation": l["formation"],
                "Strategy": l["strategy"],
                "Starting Goalkeeper": l["gk"],
                "Starting Defenders": l["df"],
                "Starting Midfielders": l["mf"],
                "Starting Forwards": l["fw"],
                "Ticket Price": l["ticket_price"],
                "Decision rationale (2-4 sentences)": l["rationale"],
            })
    return out_path, len(rows)


def unapplied_sponsorship_deals(sheet_deals):
    """Sheet rows not yet reflected in team_finances.json's sponsors_owned
    -- safe to apply via resolve_sponsorship_pick.py. A team can only hold
    one brand per category (the backend already enforces this at
    submission time), so "already has this category" is enough to know
    a given row was already applied."""
    finances = load_json("team_finances.json")
    out = []
    for d in sheet_deals:
        owned = finances["teams"].get(str(d["team_id"]), {}).get("sponsors_owned", [])
        if not any(o["category"] == d["category"] for o in owned):
            out.append(d)
    return out


def unapplied_local_tv_deals(sheet_deals):
    """Sheet rows not yet reflected in data/local_tv_deals.json's
    per-team 'negotiated' flag -- a Local TV Deal is one-time, so this
    is a clean not-yet-applied check. Each row is passed through
    untouched -- final_clause (added to the LocalTVDeals sheet and
    readLocalTVDeals_() in backend.gs alongside final_revenue) flows
    through automatically here exactly like sponsorship deals' clause
    field already does, since this function only filters the list, it
    never drops fields off the dicts it returns."""
    ltv = load_json("local_tv_deals.json")
    negotiated_ids = {str(a["team_id"]) for a in ltv["assignments"] if a.get("negotiated")}
    return [d for d in sheet_deals if str(d["team_id"]) not in negotiated_ids]


if __name__ == "__main__":
    export = fetch_admin_export()
    sheet_teams = export["teams"]
    team_name_by_id = {str(t["id"]): t["name"] for t in sheet_teams}

    names_changed = sync_team_names(sheet_teams)
    boards = write_draft_boards(export["draft_boards"])

    print(f"Pulled {len(sheet_teams)} teams, {len(boards)} draft boards, "
          f"{len(export['lineups'])} lineup submissions across all rounds.")
    print("Team names changed:", names_changed)
    # deliberately NOT stashed to a file -- the admin export includes every
    # team's real PIN (readTeams_ on the admin path), and this repo is
    # PUBLIC. auto_resolve.py re-fetches its own export directly instead of
    # reading anything off disk, for exactly this reason -- never persist
    # this export anywhere a commit could pick it up.
