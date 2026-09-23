"""
The unattended orchestrator. Run on a schedule (see
.github/workflows/auto-resolve.yml, every 30 minutes) with no human
involved: pulls live submissions, decides the ONE thing (if anything)
that's due to happen, does it, regenerates every page, and exits.
Idempotent -- running it again with nothing new due is a clean no-op.

Decision order each run:
  1. Always sync team names from the Sheet (cheap, safe, no side effects
     beyond that one field).
  2. If the season is still pre-draft AND today >= draft_day: resolve
     the draft, exactly once (phase flips to "draft" right after so a
     later run never re-drafts).
  3. Else, find the next round whose match day has arrived and that
     hasn't been resolved yet; resolve it (using whatever lineups were
     actually submitted -- resolve_round.py's own fallback already
     auto-lineups anyone who didn't submit, same as it always has).
     Loops until caught up to today in case a run was missed (a
     doubleheader match day, or the workflow didn't fire for a while).

Prints a plain summary of what it did (or "nothing due") -- that's
what shows up in the GitHub Actions log, the only place this run's
story lives since no human is watching it happen.
"""
import datetime
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import pull_submissions


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def save_json(name, data):
    with open(os.path.join(BASE, "data", name), "w") as f:
        json.dump(data, f, indent=2)


def run(cmd):
    print("  $", " ".join(cmd))
    result = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"command failed: {' '.join(cmd)}")


def regenerate_all_pages():
    print("Regenerating all pages...")
    run(["python3", "engine/render_home.py"])
    run(["python3", "engine/render_budget_site.py"])
    run(["python3", "engine/render_rulebook.py"])
    run(["python3", "engine/render_sponsorship_site.py"])
    run(["python3", "engine/render_tv_site.py"])
    run(["python3", "engine/render_attendance_site.py"])
    run(["python3", "engine/render_matchday_replay.py"])
    run(["python3", "engine/render_draftboard_site.py"])
    run(["python3", "engine/render_scouting_site.py"])
    run(["python3", "engine/generate_players_json.py"])
    # dashboard has no __main__ CLI entry -- render inline exactly like every
    # manual regenerate this project has done all along
    script = '''
import sys, os, json
sys.path.insert(0, "engine")
import render_dashboard
def load(name):
    with open(os.path.join("data", name)) as f:
        return json.load(f)
config = load("league_config.json")
players = render_dashboard.load_players()
deals = load("deals.json")
matches = load("matches.json")
schedule = load("schedule.json")
calendar = load("season_calendar.json")
injuries = load("player_injuries.json") if os.path.exists("data/player_injuries.json") else {}
html = render_dashboard.render(players, config, deals, matches, schedule, calendar, injuries)
with open("dashboard/index.html", "w") as f:
    f.write(html)
print("dashboard OK")
'''
    result = subprocess.run(["python3", "-c", script], cwd=BASE, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit("dashboard regeneration failed")

    # copy every generated index.html into its GitHub Pages path
    mapping = {
        "home/index.html": "index.html",
        "dashboard/index.html": "dashboard/index.html",
        "budget-site/index.html": "budget/index.html",
        "rulebook/index.html": "rulebook/index.html",
        "sponsorship-site/index.html": "sponsorship/index.html",
        "tv-site/index.html": "tv/index.html",
        "attendance-site/index.html": "attendance/index.html",
        "matchday-replay/index.html": "matchday-replay/index.html",
        "draftboard-site/index.html": "draftboard/index.html",
        "scouting-site/index.html": "scouting/index.html",
    }
    for src, dst in mapping.items():
        src_path = os.path.join(BASE, src)
        dst_path = os.path.join(BASE, dst)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        with open(src_path) as f:
            content = f.read()
        with open(dst_path, "w") as f:
            f.write(content)


def find_date_for_round(calendar, round_num):
    for entry in calendar["match_day_schedule"]:
        if round_num in entry["rounds"]:
            return entry["date"]
    return None


def total_rounds(calendar):
    return sum(len(e["rounds"]) for e in calendar["match_day_schedule"])


def inject_pins(team_pin_by_id):
    """Writes real PINs into data/league_config.json ON DISK, temporarily,
    so the resolve_draft.py / resolve_round.py subprocesses (which read
    league_config.json fresh off disk themselves) can validate against
    them. MUST be paired with strip_pins() before this process exits --
    the committed file this repo tracks never carries pins, since this
    repo is public. See inject/strip calls in main()'s try/finally."""
    config = load_json("league_config.json")
    for t in config["teams"]:
        pin = team_pin_by_id.get(str(t["team_id"]))
        if pin:
            t["pin"] = pin
    save_json("league_config.json", config)


def strip_pins():
    """Undoes inject_pins() -- always call this before the process exits,
    success or failure, so a committed league_config.json never carries a
    real PIN. See main()'s try/finally."""
    config = load_json("league_config.json")
    for t in config["teams"]:
        t.pop("pin", None)
    save_json("league_config.json", config)


def resolve_draft_now():
    print("\n=== Resolving the draft ===")
    run(["python3", "engine/resolve_draft.py"])
    config = load_json("league_config.json")
    config["phase"] = "draft"
    save_json("league_config.json", config)
    return "resolved the draft"


def resolve_round_now(round_num, team_name_by_id, team_pin_by_id, lineups):
    print(f"\n=== Resolving round {round_num} ===")
    csv_path, n_submitted = pull_submissions.write_lineup_csv(lineups, round_num, team_name_by_id, team_pin_by_id)
    print(f"  {n_submitted} lineup submission(s) found for round {round_num}")
    run(["python3", "engine/resolve_round.py", "--round", str(round_num), "--csv", csv_path])
    return f"resolved round {round_num}"


def resolve_sponsorship_deals(sheet_sponsorship_deals):
    """Applies every Sheet sponsorship_deal row not yet reflected in
    team_finances.json's sponsors_owned. Sponsorship can be negotiated any
    time after the draft (no match-day gate the way round resolution has),
    so this runs unconditionally every cycle once a team has a roster.
    The Sheet already resolved base-vs-negotiate into concrete final_revenue
    / final_clause numbers at submission time, so this only ever needs
    --live -- there is no separate base/negotiate branch here."""
    actions = []
    for d in pull_submissions.unapplied_sponsorship_deals(sheet_sponsorship_deals):
        print(f"\n=== Applying sponsorship deal: team {d['team_id']} / {d['brand']} ===")
        cmd = [
            "python3", "engine/resolve_sponsorship_pick.py",
            "--team", str(d["team_id"]), "--brand", d["brand"],
            "--live", "--final-revenue", str(int(d["final_revenue"])),
            "--final-clause", d["final_clause"],
        ]
        if d.get("rep_team_id") not in (None, "", "null"):
            cmd += ["--sponsor-rep-team", str(d["rep_team_id"])]
        run(cmd)
        actions.append(f"sponsorship: team {d['team_id']} signed {d['brand']} ({d['category']})")
    return actions


def resolve_local_tv_deals(sheet_local_tv_deals):
    """Applies every Sheet local_tv_deal row not yet reflected as
    'negotiated' in data/local_tv_deals.json. Same no-gate reasoning as
    resolve_sponsorship_deals -- runs unconditionally once a team has a
    roster, since Local TV negotiation isn't tied to a round date either.
    The Sheet already resolved base-vs-negotiate into concrete
    final_revenue / final_clause numbers at submission time (see
    backend.gs's local_tv_deal handler), so this only ever needs
    --live -- same as resolve_sponsorship_deals, there is no separate
    base/negotiate branch here."""
    actions = []
    for d in pull_submissions.unapplied_local_tv_deals(sheet_local_tv_deals):
        print(f"\n=== Applying local TV deal: team {d['team_id']} ===")
        cmd = [
            "python3", "engine/resolve_local_tv_pick.py",
            "--team", str(d["team_id"]), "--live",
            "--final-revenue", str(int(d["final_revenue"])),
            "--final-clause", str(d["final_clause"]),
        ]
        if d.get("rep_team_id") not in (None, "", "null"):
            cmd += ["--network-rep-team", str(d["rep_team_id"])]
        run(cmd)
        actions.append(f"local TV: team {d['team_id']} negotiated a rate")
    return actions


def main():
    print(f"auto_resolve.py run at {datetime.datetime.utcnow().isoformat()}Z")
    export = pull_submissions.fetch_admin_export()
    sheet_teams = export["teams"]
    names_changed = pull_submissions.sync_team_names(sheet_teams)
    pull_submissions.write_draft_boards(export["draft_boards"])
    team_name_by_id = {str(t["id"]): t["name"] for t in sheet_teams}
    team_pin_by_id = {str(t["id"]): t["pin"] for t in sheet_teams}

    # PINs go onto disk ONLY for the duration of this try block, so
    # resolve_draft.py / resolve_round.py (which read league_config.json
    # fresh off disk) can validate them -- strip_pins() in `finally`
    # guarantees they're gone again before this process exits, success
    # or failure, since the file this writes is committed to a PUBLIC repo.
    inject_pins(team_pin_by_id)
    try:
        config = load_json("league_config.json")
        calendar = load_json("season_calendar.json")
        today = datetime.date.today().isoformat()

        actions = []
        if names_changed:
            actions.append("synced renamed team(s) from the Sheet")

        if config["phase"] == "pre-draft":
            if today >= calendar["draft_day"]:
                actions.append(resolve_draft_now())
                config = load_json("league_config.json")  # re-read post-draft state
            else:
                print(f"NOOP: today ({today}) is before draft day ({calendar['draft_day']})")

        if config["phase"] in ("draft", "season"):
            rounds_total = total_rounds(calendar)
            # loop in case more than one due round is unresolved (a missed
            # scheduled run, or a doubleheader match day)
            while True:
                next_round = config.get("current_round", 0) + 1
                if next_round > rounds_total:
                    break
                target_date = find_date_for_round(calendar, next_round)
                if not target_date or today < target_date:
                    break
                actions.append(resolve_round_now(next_round, team_name_by_id, team_pin_by_id, export["lineups"]))
                config = load_json("league_config.json")

        # Sponsorship and Local TV negotiation aren't tied to a round date --
        # a team can submit either any time after it has a drafted roster --
        # so these run unconditionally every cycle rather than being gated
        # by today's date the way draft/round resolution are.
        if config["phase"] != "pre-draft":
            actions.extend(resolve_sponsorship_deals(export.get("sponsorship_deals", [])))
            actions.extend(resolve_local_tv_deals(export.get("local_tv_deals", [])))

        if actions:
            regenerate_all_pages()
            print("\nACTIONS TAKEN:")
            for a in actions:
                print(" -", a)
        else:
            print("\nNOOP: nothing due this run.")
    finally:
        strip_pins()

    # write a marker file the workflow uses to decide whether to commit
    with open(os.path.join(BASE, "_auto_resolve_actions.txt"), "w") as f:
        f.write("\n".join(actions))


if __name__ == "__main__":
    main()
