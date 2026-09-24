"""
Resolves one regular-season round: reads that round's Google Form CSV
export (Weekly Lineup & Strategy -- see forms/google_form_specs.md),
validates every submitted lineup against the team's actual roster,
simulates every fixture, books ticket revenue, appends to
data/matches.json, and re-renders the dashboard.

Usage:
    python3 engine/resolve_round.py --round 3 --csv path/to/round3_responses.csv

Expected CSV columns (exact Google Forms export header text):
    Team name, Formation, Strategy, Starting Goalkeeper,
    Starting Defenders, Starting Midfielders, Starting Forwards,
    Ticket Price, Decision rationale (2-4 sentences)
"Starting Defenders/Midfielders/Forwards" are the Forms "paragraph"
field, so each cell holds one player name per line.

DETERMINISTIC-BUT-UNPREDICTABLE SCORING: each match's random draw is
seeded from a hash of (config["season_seed"], round, home_id, away_id)
-- not a single RNG stream reused across every match. This keeps the
same guarantee simulate.py's docstring describes (fully reproducible
after the fact, e.g. to settle a grade dispute) while working correctly
across separate CLI runs, since a season doesn't run as one continuous
process. Never derive a seed from anything a student could predict or
influence (their own lineup choice, for instance) -- only season_seed
and the fixture identity.
"""
import argparse
import csv
import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
from simulate import simulate_match, FORMATIONS
from attendance import compute_attendance, recent_win_rate
from player_condition import conditions_for_round, roll_new_injuries
from match_summary import generate_summary
import render_dashboard

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def save_json(name, data):
    with open(os.path.join(BASE, "data", name), "w") as f:
        json.dump(data, f, indent=2)


def load_json_or_default(name, default):
    path = os.path.join(BASE, "data", name)
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def flatten_lineup(lineup):
    """lineup: dict position -> list of player dicts. Returns the flat
    list of player_ids who actually started -- used to decide who's even
    eligible to pick up a new injury this round."""
    return [p["player_id"] for players in lineup.values() for p in players]


def match_seed(season_seed, round_num, home_id, away_id):
    key = f"{season_seed}:{round_num}:{home_id}:{away_id}".encode()
    return int(hashlib.sha256(key).hexdigest()[:16], 16)


def parse_names(cell):
    return [n.strip() for n in (cell or "").splitlines() if n.strip()]


def build_roster_index(players, team_id):
    """name (lowercased) -> player dict, restricted to this team's actual roster."""
    return {p["name"].lower(): p for p in players if p.get("team_id") not in ("", None) and int(p["team_id"]) == team_id}


def build_lineup(row, roster_by_name, formation):
    counts = FORMATIONS[formation]
    errors = []

    def resolve(names, pos, expected_count):
        players, seen = [], set()
        for n in names:
            p = roster_by_name.get(n.strip().lower())
            if p is None:
                errors.append(f"'{n}' is not on this team's roster")
                continue
            if p["position"] != pos:
                errors.append(f"'{n}' is a {p['position']}, not {pos}")
                continue
            if p["name"] in seen:
                errors.append(f"'{n}' listed twice")
                continue
            seen.add(p["name"])
            players.append(p)
        if len(players) != expected_count:
            errors.append(f"{pos}: formation {formation} needs {expected_count} starters, got {len(players)}")
        return players

    lineup = {
        "GK": resolve([row.get("Starting Goalkeeper", "")], "GK", counts["GK"]),
        "DF": resolve(parse_names(row.get("Starting Defenders")), "DF", counts["DF"]),
        "MF": resolve(parse_names(row.get("Starting Midfielders")), "MF", counts["MF"]),
        "FW": resolve(parse_names(row.get("Starting Forwards")), "FW", counts["FW"]),
    }
    return lineup, errors


def fallback_lineup(roster, formation):
    """Applied when a team doesn't submit: Balanced 4-4-2-style default
    using the highest-OVR available player per required slot. No
    rationale credit is possible for a round resolved this way --
    that's the intended incentive to submit on time, not a punishment
    layered on top."""
    counts = FORMATIONS[formation]
    lineup = {}
    for pos, n in counts.items():
        pool = sorted([p for p in roster if p["position"] == pos], key=lambda p: -p["ovr"])
        lineup[pos] = pool[:n]
    return lineup


def avg_star_power(lineup):
    all_players = [p for players in lineup.values() for p in players]
    return sum(p["star_power"] for p in all_players) / len(all_players)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--csv", required=True)
    args = ap.parse_args()

    config = load_json("league_config.json")
    schedule = load_json("schedule.json")
    matches = load_json("matches.json")
    finances = load_json("team_finances.json")["teams"]
    players = render_dashboard.load_players()

    # HARD GUARD: once a round is resolved, it is permanent -- never
    # re-simulate it, even if this script is invoked again for the same
    # round (a manual re-run, a bug elsewhere in the automation, anything).
    # Re-simulating could produce a DIFFERENT result if a lineup changed
    # in the Sheet since the first resolve, silently rewriting a result
    # students already saw. auto_resolve.py's own round-tracking already
    # prevents this in the normal automated path, but this check makes it
    # true regardless of how the script gets invoked.
    if any(m["round"] == args.round and m.get("stage", "regular") == "regular" for m in matches):
        print(f"ERROR: Round {args.round} has already been resolved and is permanent -- refusing to re-simulate it. "
              f"If this round's results are genuinely wrong, that requires a deliberate manual data fix, not a re-run of this script.")
        return

    season_seed = config.get("season_seed", 2026)
    team_by_name = {t["name"]: t["team_id"] for t in config["teams"]}
    injuries = load_json_or_default("player_injuries.json", {})
    # JSON object keys are always strings, but this round's own injury
    # rolls below use player_id (already a string) directly -- no cast needed.
    conditions, _condition_detail = conditions_for_round(season_seed, args.round, players, injuries)

    fixtures = next((r["fixtures"] for r in schedule if r["round"] == args.round), None)
    if fixtures is None:
        print(f"No fixtures found for round {args.round} in data/schedule.json")
        return

    with open(args.csv) as f:
        submissions = {row["Team name"].strip(): row for row in csv.DictReader(f)}

    # --- pass 1: validate every submitted lineup before simulating anything ---
    all_errors = {}
    pin_rejected = []  # (team_name,) -- treated as a non-submission, does NOT block the round
    parsed = {}
    pin_by_team = {t["team_id"]: t.get("pin") for t in config["teams"]}
    for team_id, name in {t["team_id"]: t["name"] for t in config["teams"]}.items():
        row = submissions.get(name)
        roster_by_name = build_roster_index(players, team_id)
        roster = list(roster_by_name.values())
        if row is None:
            parsed[team_id] = {"lineup": None, "formation": None, "strategy": "Balanced",
                                "ticket_price": None, "roster": roster, "submitted": False}
            continue

        # PIN check FIRST, before any other validation. A wrong/missing PIN is
        # treated as a NON-submission (autopicked, same as a missed deadline)
        # rather than a blocking error -- one bad or malicious PIN shouldn't
        # hold up every other team's correctly-submitted round. A team with
        # no PIN assigned yet (config not regenerated with PINs) skips this
        # check entirely.
        expected_pin = pin_by_team.get(team_id)
        if expected_pin:
            submitted_pin = (row.get("Team PIN") or "").strip()
            if submitted_pin != expected_pin:
                pin_rejected.append(name)
                parsed[team_id] = {"lineup": None, "formation": None, "strategy": "Balanced",
                                    "ticket_price": None, "roster": roster, "submitted": False}
                continue

        formation = row.get("Formation", "").strip()
        if formation not in FORMATIONS:
            all_errors[name] = [f"unknown formation '{formation}'"]
            continue
        lineup, errors = build_lineup(row, roster_by_name, formation)
        if errors:
            all_errors[name] = errors
            continue
        parsed[team_id] = {
            "lineup": lineup, "formation": formation,
            "strategy": row.get("Strategy", "Balanced").strip(),
            "ticket_price": row.get("Ticket Price", "").strip() or None,
            "roster": roster, "submitted": True,
        }

    if all_errors:
        print(f"VALIDATION ERRORS -- round {args.round} NOT resolved. Fix these submissions and re-run:")
        for name, errs in all_errors.items():
            print(f"  {name}:")
            for e in errs:
                print(f"    - {e}")
        return

    # --- pass 2: simulate every fixture ---
    starters_this_round = []
    for fx in fixtures:
        h_id, a_id = fx["home_id"], fx["away_id"]
        h_name = next(t["name"] for t in config["teams"] if t["team_id"] == h_id)
        a_name = next(t["name"] for t in config["teams"] if t["team_id"] == a_id)

        h_info, a_info = parsed[h_id], parsed[a_id]
        h_formation = h_info["formation"] or "4-4-2"
        a_formation = a_info["formation"] or "4-4-2"
        h_lineup = h_info["lineup"] or fallback_lineup(h_info["roster"], h_formation)
        a_lineup = a_info["lineup"] or fallback_lineup(a_info["roster"], a_formation)
        starters_this_round.extend(flatten_lineup(h_lineup))
        starters_this_round.extend(flatten_lineup(a_lineup))

        rng = random.Random(match_seed(season_seed, args.round, h_id, a_id))
        result = simulate_match(
            h_lineup, h_formation, h_info["strategy"] if h_info["submitted"] else "Balanced",
            a_lineup, a_formation, a_info["strategy"] if a_info["submitted"] else "Balanced",
            rng, conditions,
        )

        record = {
            "round": args.round, "stage": "regular",
            "home_id": h_id, "away_id": a_id,
            "home_goals": result["home_goals"], "away_goals": result["away_goals"],
            "home_formation": h_formation, "away_formation": a_formation,
            "home_strategy": h_info["strategy"], "away_strategy": a_info["strategy"],
            "home_submitted": h_info["submitted"], "away_submitted": a_info["submitted"],
            "goal_events": result["goal_events"],
        }
        matches.append(record)

        # ticket revenue -- home side only, this round's price tier
        price_tier = h_info["ticket_price"]
        if price_tier:
            form = recent_win_rate(h_id, matches, upto_round=args.round)
            star = avg_star_power(h_lineup)
            att = compute_attendance(price_tier, form, star)
            finances.setdefault(str(h_id), {"ticket_revenue": 0, "sponsorship_revenue": 0, "tv_revenue": 0})
            finances[str(h_id)]["ticket_revenue"] += att["revenue"]
            gate_note = f" | gate: {att['attendance']:,} @ {price_tier} = ${att['revenue']:,}"
        else:
            gate_note = " | no ticket price submitted -- no gate revenue booked"

        outcome = "W" if result["home_goals"] > result["away_goals"] else ("L" if result["home_goals"] < result["away_goals"] else "D")
        print(f"Round {args.round}: {h_name} {result['home_goals']}-{result['away_goals']} {a_name}  "
              f"(home {outcome}, xG {result['home_xg']}-{result['away_xg']}){gate_note}")
        print(f"    {generate_summary(h_name, a_name, result['home_goals'], result['away_goals'], result['goal_events'])}")
        for side, info in ((h_name, h_info), (a_name, a_info)):
            if not info["submitted"]:
                if side in pin_rejected:
                    print(f"    WARNING: a submission claiming to be {side} had a missing/incorrect PIN -- "
                          f"REJECTED, auto-lineup applied instead. If this wasn't {side}'s own mistake, "
                          f"this is worth following up on.")
                else:
                    print(f"    NOTE: {side} did not submit -- auto-lineup applied, no rationale credit this round.")

    save_json("matches.json", matches)
    save_json("team_finances.json", {"teams": finances})

    # roll new injuries for anyone who actually started this round, then
    # persist -- this is what makes NEXT round's conditions report reflect
    # what just happened (see player_condition.py's module docstring)
    roll_new_injuries(season_seed, args.round, starters_this_round, injuries)
    save_json("player_injuries.json", injuries)
    injured_now = {pid: until for pid, until in injuries.items() if until >= args.round}
    if injured_now:
        name_by_id = {p["player_id"]: p["name"] for p in players}
        print(f"\nInjuries as of round {args.round} ({len(injured_now)} players out):")
        for pid, until in sorted(injured_now.items(), key=lambda kv: -kv[1]):
            print(f"  {name_by_id.get(pid, pid):<24} out through round {until}")

    config["current_round"] = args.round
    config["phase"] = "season"
    save_json("league_config.json", config)

    html = render_dashboard.render(
        players, config, load_json("deals.json"), matches, schedule,
        injuries=injuries,
    )
    dash_path = os.path.join(BASE, "dashboard", "index.html")
    with open(dash_path, "w") as f:
        f.write(html)
    print(f"\nRound {args.round} resolved. Dashboard re-rendered -> {dash_path}")
    print("Republish dashboard/index.html as the artifact to make it live.")


if __name__ == "__main__":
    main()
