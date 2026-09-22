"""
Season Scorecard -- the exam-replacement grade for the SM Owners League.

100 points, four components, each answering a different question about
how the season went for that owner:

  RANKING     40 pts  "Did your team win?"            -- regular-season standings
  PLAYOFFS     5 pts  "Did you make the playoffs?"     -- flat bonus for finishing inside
                                                           the qualification line (no
                                                           bracket games are played)
  REVENUE     35 pts  "Did you run it as a business?"  -- ticket + sponsorship + national
                                                           TV + local TV revenue generated,
                                                           ranked against the rest of the league
  RATIONALE   20 pts  "Could you explain your calls?"  -- average score on the weekly
                                                           Decision Rationale Rubric

RANKING and REVENUE are both scored by LINEAR RANK within the league
(1st = full points, last = 0, evenly spaced between) rather than against
a fixed target number. A fixed revenue target would have to guess the
league's total economy in advance; rank-based scoring self-calibrates
to whatever actually happens this season and treats "outperforming your
classmates" as the standard, same as the ranking component already does.

PLAYOFFS is a FLAT, BINARY bonus: full 5 points for finishing in the
top `playoff_teams` of the final regular-season standings, 0 otherwise
-- not tiered by seed, since there is no bracket to separate a 1-seed
from a 6-seed. Finishing 1st vs. 6th is already rewarded by RANKING.

Run compute_scorecards() after the season concludes, or at any
freeze-point (e.g. midterm check-in) using whatever standings/finances/
rationale data exist so far -- every component degrades gracefully to 0
for a team with no data yet.
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from simulate import Standings

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WEIGHTS = {"ranking": 40, "playoffs": 5, "revenue": 35, "rationale": 20}


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def load_rationale_scores():
    path = os.path.join(BASE, "data", "rationale_scores.csv")
    by_team = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            tid = int(row["team_id"])
            by_team.setdefault(tid, []).append(
                (float(row["points_earned"]), float(row["points_possible"]))
            )
    return by_team


def linear_rank_points(ranked_team_ids, max_points):
    """ranked_team_ids: best-first list of team_ids (ties broken by caller).
    1st place gets max_points, last place gets 0, evenly spaced between."""
    n = len(ranked_team_ids)
    if n <= 1:
        return {tid: max_points for tid in ranked_team_ids}
    return {
        tid: round(max_points * (n - 1 - i) / (n - 1), 2)
        for i, tid in enumerate(ranked_team_ids)
    }


def compute_scorecards():
    config = load_json("league_config.json")
    deals = load_json("deals.json")
    matches = load_json("matches.json")
    finances = load_json("team_finances.json")["teams"]
    rationale_raw = load_rationale_scores()

    team_ids = [t["team_id"] for t in config["teams"]]
    team_names = {t["team_id"]: t["name"] for t in config["teams"]}

    # --- RANKING (30 pts) ---
    st = Standings(team_ids)
    for m in matches:
        if m.get("stage", "regular") == "regular":
            st.record(m["home_id"], m["away_id"], m["home_goals"], m["away_goals"])
    standings_ranked = st.ranked()
    ranked_ids = [tid for tid, _ in standings_ranked]
    ranking_points = linear_rank_points(ranked_ids, WEIGHTS["ranking"])

    # --- PLAYOFFS (25 pts, flat -- top playoff_teams finishers, no bracket) ---
    n_playoff = config.get("playoff_teams", 6)
    qualifiers = set(ranked_ids[:n_playoff])
    playoff_points = {tid: (WEIGHTS["playoffs"] if tid in qualifiers else 0.0) for tid in team_ids}

    # --- REVENUE (25 pts, ranked) ---
    # Sum only the known numeric revenue fields -- finances also carries
    # non-numeric bookkeeping (sponsors_owned: a list) that a naive
    # sum(dict.values()) would crash on the moment a team actually signs one.
    REVENUE_FIELDS = ("ticket_revenue", "sponsorship_revenue", "tv_revenue", "local_tv_revenue")
    total_revenue = {
        tid: sum(finances.get(str(tid), {}).get(field, 0) for field in REVENUE_FIELDS)
        for tid in team_ids
    }
    revenue_ranked = sorted(team_ids, key=lambda tid: -total_revenue[tid])
    revenue_points = linear_rank_points(revenue_ranked, WEIGHTS["revenue"])

    # --- RATIONALE (20 pts, average % across graded rounds) ---
    rationale_points = {}
    for tid in team_ids:
        rows = rationale_raw.get(tid, [])
        if not rows:
            rationale_points[tid] = 0.0
            continue
        pct = sum(e / p for e, p in rows if p) / len(rows)
        rationale_points[tid] = round(WEIGHTS["rationale"] * pct, 2)

    # --- assemble ---
    scorecards = []
    for tid in team_ids:
        parts = {
            "ranking": ranking_points.get(tid, 0.0),
            "playoffs": playoff_points.get(tid, 0.0),
            "revenue": revenue_points.get(tid, 0.0),
            "rationale": rationale_points.get(tid, 0.0),
        }
        total = round(sum(parts.values()), 2)
        scorecards.append({
            "team_id": tid,
            "team_name": team_names[tid],
            "components": parts,
            "total": total,
        })
    scorecards.sort(key=lambda s: -s["total"])
    return scorecards


if __name__ == "__main__":
    cards = compute_scorecards()
    print(f"{'Team':<14}{'Rank':>7}{'Playoff':>9}{'Revenue':>9}{'Rationale':>11}{'TOTAL':>8}")
    for c in cards:
        p = c["components"]
        print(f"{c['team_name']:<14}{p['ranking']:>7.1f}{p['playoffs']:>9.1f}{p['revenue']:>9.1f}{p['rationale']:>11.1f}{c['total']:>8.1f}")
