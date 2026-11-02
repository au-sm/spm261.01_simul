"""
TV Revenue Day: pays the League-Wide (National) TV Deal and every team's
Local TV Deal together, once. Run it only when the instructor closes Local TV
negotiations; it prints what it would pay unless --apply is given, and it
refuses to pay twice (data/tv_payout.json records the payout).

  National = base + standings bonus (top 3) + star bonus (top-3 starting XI)
  Local    = signed rate, or market-tier base if unsigned; +15% if top-3 XI

Standings and Star Power are read as of the moment this runs. A team with no
signed deal is recorded at its base rate and clause, so the season-end clause
check (resolve_clause_checkpoint.py) covers it too.

Usage:
    python3 engine/resolve_tv_split.py
    python3 engine/resolve_tv_split.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from simulate import Standings
import render_dashboard

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYOUT_FILE = os.path.join(BASE, "data", "tv_payout.json")


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def save_json(name, data):
    with open(os.path.join(BASE, "data", name), "w") as f:
        json.dump(data, f, indent=2)


def latest_xi_star(team_id, matches, players):
    """Average Star Power of the team's most recent recorded starting XI,
    or its whole roster if no match lists its starters."""
    star = {str(p["player_id"]): p["star_power"] for p in players}
    for m in reversed(matches):
        side = "home" if m["home_id"] == team_id else "away" if m["away_id"] == team_id else None
        xi = [star[str(i)] for i in m.get(f"{side}_starters") or [] if str(i) in star] if side else []
        if xi:
            return sum(xi) / len(xi)
    roster = [p["star_power"] for p in players if p.get("team_id") not in ("", None) and int(p["team_id"]) == team_id]
    return sum(roster) / len(roster) if roster else 0


def compute(config, deals, ltv, matches, players):
    team_ids = [t["team_id"] for t in config["teams"]]
    st = Standings(team_ids)
    regular = sorted((m for m in matches if m.get("stage", "regular") == "regular"), key=lambda m: m["round"])
    for m in regular:
        st.record(m["home_id"], m["away_id"], m["home_goals"], m["away_goals"])
    ranked = [tid for tid, _ in st.ranked()]
    stars = {tid: latest_xi_star(tid, regular, players) for tid in team_ids}
    top3_star = set(sorted(team_ids, key=lambda t: (-stars[t], t))[:3])

    tv = deals["tv_deal_formula"]
    bonuses = tv["standings_bonus_amounts"]
    mult = ltv["star_power_modifier"]["multiplier_if_top3_star_power"]
    rows = []
    for a in sorted(ltv["assignments"], key=lambda a: a["team_id"]):
        tid = a["team_id"]
        rank = ranked.index(tid) + 1
        national = (tv["base_payment_per_team"] + (bonuses[rank - 1] if rank <= len(bonuses) else 0)
                    + (tv["star_power_bonus_amount"] if tid in top3_star else 0))
        rate = a["negotiated_revenue"] if a.get("negotiated") else a["base_revenue"]
        local = round(rate * (mult if tid in top3_star else 1))
        rows.append({"team_id": tid, "rank": rank, "xi_star_power": round(stars[tid], 1), "top3_star": tid in top3_star,
                     "signed": bool(a.get("negotiated")), "rate": rate, "national": national, "local": local})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually pay; without this it only prints")
    args = ap.parse_args()

    if os.path.exists(PAYOUT_FILE):
        print("TV Revenue Day has already been paid (data/tv_payout.json). Not paying again."); return

    config = load_json("league_config.json")
    ltv = load_json("local_tv_deals.json")
    names = {t["team_id"]: t["name"] for t in config["teams"]}
    rows = compute(config, load_json("deals.json"), ltv, load_json("matches.json"), render_dashboard.load_players())
    for r in rows:
        print(f'{names[r["team_id"]]:<28} rank {r["rank"]:>2}  XI star {r["xi_star_power"]:>5}{" *" if r["top3_star"] else "  "}  '
              f'{"signed  " if r["signed"] else "unsigned"}  national ${r["national"]:>9,}  local ${r["local"]:>9,}')
    if not args.apply:
        print("\nDry run. Add --apply to pay."); return

    finances = load_json("team_finances.json")
    for r in rows:
        rec = finances["teams"].setdefault(str(r["team_id"]), {})
        rec["tv_revenue"] = rec.get("tv_revenue", 0) + r["national"]
        rec["local_tv_revenue"] = rec.get("local_tv_revenue", 0) + r["local"]
    for a in ltv["assignments"]:
        if not a.get("negotiated"):
            a.update(negotiated=True, mode="base_at_deadline", negotiated_revenue=a["base_revenue"], final_clause=a["base_clause"])
    save_json("team_finances.json", finances)
    save_json("local_tv_deals.json", ltv)
    save_json("tv_payout.json", rows)
    print("\nPaid. Regenerate the pages so budgets show it.")


if __name__ == "__main__":
    main()
