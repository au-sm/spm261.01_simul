"""
Match resolution engine for the SPM Owner-League soccer simulation.

Deliberately transparent, not a black box: every number that feeds a
result is visible in the recap dict this module returns, so a team's
loss can always be traced back to a specific lineup/formation/strategy
choice for grading and classroom discussion.

FORMULA (documented here because "why did we lose" is the most common
question a student will ask, and the honest answer should be readable
in this file, not reverse-engineered from behavior):

  1. Each formation assigns weight to DF/MF/FW ratings when building a
     team's overall Attack and Defense score (a 4-3-3 leans on attack
     more than a 5-3-2 does).
  2. Strategy shifts +/- 8% between the team's own Attack and Defense
     after formation weighting (Attacking / Balanced / Defensive).
  3. Home side gets a fixed +5% Attack bump (home advantage).
  4. Expected goals (xG) for each side = a saturating function of
     (own Attack - opponent Defense): a big mismatch caps out rather
     than producing absurd scorelines.
  5. Actual goals are drawn from a Poisson distribution around each
     side's xG -- this is the deliberate "luck" component every real
     match has. It uses the shared SEASON RNG (seeded once per season,
     not per match), so a full season replay is reproducible end to
     end but no single match's score is predictable in advance from
     the inputs alone.
"""
import math
import random

from goal_events import generate_goal_events

FORMATIONS = {
    # formation -> (GK, DF, MF, FW) counts, must sum to 11
    "4-4-2": {"GK": 1, "DF": 4, "MF": 4, "FW": 2},
    "4-3-3": {"GK": 1, "DF": 4, "MF": 3, "FW": 3},
    "3-5-2": {"GK": 1, "DF": 3, "MF": 5, "FW": 2},
    "5-3-2": {"GK": 1, "DF": 5, "MF": 3, "FW": 2},
    "4-5-1": {"GK": 1, "DF": 4, "MF": 5, "FW": 1},
}

# how much each outfield group counts toward the team's ATTACK score,
# vs. its DEFENSE score, given the formation leans attacking or defensive
ATTACK_WEIGHT = {"DF": 0.15, "MF": 0.40, "FW": 0.45}
DEFENSE_WEIGHT = {"DF": 0.55, "MF": 0.30, "FW": 0.15}
GK_DEFENSE_WEIGHT = 0.25  # GK folded into defense score on top of outfield

STRATEGY_SHIFT = {
    "Attacking": (1.08, 0.92),
    "Balanced": (1.00, 1.00),
    "Defensive": (0.92, 1.08),
}

HOME_ADVANTAGE = 1.05


def team_ratings(lineup, formation, strategy, conditions=None):
    """
    lineup: dict position -> list of player dicts (from players.csv rows),
            already trimmed to the counts FORMATIONS[formation] requires.
    conditions: optional {player_id: multiplier} from player_condition.py
                -- each player's ATT/DEF is scaled by their own weekly
                condition before the position-group average is taken.
                Omitting it (None) is equivalent to every player being at
                a flat 1.0x -- kept for any caller that doesn't care about
                weekly condition (e.g. a quick what-if check).
    Returns (attack, defense, breakdown-dict) for one team in one match.
    """
    counts = FORMATIONS[formation]
    assert all(len(lineup.get(pos, [])) == n for pos, n in counts.items()), \
        f"lineup does not match formation {formation}: {counts}"

    def avg(field, players):
        if not players:
            return 0
        if conditions:
            return sum(p[field] * conditions.get(p["player_id"], 1.0) for p in players) / len(players)
        return sum(p[field] for p in players) / len(players)

    attack = 0.0
    defense = 0.0
    for pos in ("DF", "MF", "FW"):
        players = lineup.get(pos, [])
        attack += avg("att", players) * ATTACK_WEIGHT[pos]
        defense += avg("def", players) * DEFENSE_WEIGHT[pos]
    gk = lineup.get("GK", [])
    defense += avg("def", gk) * GK_DEFENSE_WEIGHT
    # normalize defense (weights sum to 0.55+0.30+0.15+0.25 = 1.25) back to 0-100ish scale
    defense = defense / 1.25

    atk_mult, def_mult = STRATEGY_SHIFT[strategy]
    attack *= atk_mult
    defense *= def_mult

    starters = [p for pos in ("GK", "DF", "MF", "FW") for p in lineup.get(pos, [])]
    condition_breakdown = (
        [{"player_id": p["player_id"], "name": p["name"], "position": p["position"],
          "multiplier": conditions.get(p["player_id"], 1.0)} for p in starters]
        if conditions else []
    )

    return attack, defense, {
        "formation": formation,
        "strategy": strategy,
        "raw_attack": round(attack, 1),
        "raw_defense": round(defense, 1),
        "player_conditions": condition_breakdown,
    }


def expected_goals(own_attack, opp_defense):
    """Saturating xG curve: a big attack-vs-defense mismatch caps out
    instead of producing blowout scorelines that feel unfair to grade."""
    diff = own_attack - opp_defense
    # logistic-shaped: ~1.3 xG at parity, climbs toward ~3.6, floors near 0.3
    return 0.3 + 3.3 / (1 + math.exp(-diff / 12))


def simulate_match(home_lineup, home_formation, home_strategy,
                    away_lineup, away_formation, away_strategy,
                    rng: random.Random, conditions=None):
    """
    Returns a full recap dict: score, xG, ratings breakdown for both
    sides. `rng` should be the ONE shared season Random instance,
    passed in by the caller -- never re-seeded per match.
    conditions: optional {player_id: multiplier} for this round, from
    player_condition.conditions_for_round() -- see team_ratings() above.
    """
    h_atk, h_def, h_info = team_ratings(home_lineup, home_formation, home_strategy, conditions)
    a_atk, a_def, a_info = team_ratings(away_lineup, away_formation, away_strategy, conditions)

    h_atk *= HOME_ADVANTAGE

    h_xg = expected_goals(h_atk, a_def)
    a_xg = expected_goals(a_atk, h_def)

    h_goals = _poisson(rng, h_xg)
    a_goals = _poisson(rng, a_xg)

    # same match rng, so goal minute/type/scorer stay exactly as
    # reproducible as the score itself -- see goal_events.py
    h_events = generate_goal_events(rng, "home", home_lineup, h_goals)
    a_events = generate_goal_events(rng, "away", away_lineup, a_goals)
    goal_events = sorted(h_events + a_events, key=lambda e: e["minute"])

    return {
        "home_goals": h_goals,
        "away_goals": a_goals,
        "home_xg": round(h_xg, 2),
        "away_xg": round(a_xg, 2),
        "home_info": h_info,
        "away_info": a_info,
        "goal_events": goal_events,
    }


def _poisson(rng: random.Random, lam):
    """Knuth's algorithm -- stdlib random.Random has no .poisson()."""
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


def round_robin_schedule(team_ids, rng: random.Random = None):
    """
    Standard circle-method round robin. Returns a list of rounds, each
    a list of (home_id, away_id) tuples. If len(team_ids) is odd, one
    team gets a bye each round (paired with None).
    Home/away is fixed by the rotation, not randomized, so the schedule
    is reproducible without needing rng -- accepted for interface
    symmetry with the rest of the engine but currently unused.
    """
    teams = list(team_ids)
    if len(teams) % 2 == 1:
        teams.append(None)
    n = len(teams)
    rounds = []
    fixed = teams[0]
    rotating = teams[1:]
    for r in range(n - 1):
        pairings = [(fixed, rotating[-1])] if r % 2 == 0 else [(rotating[-1], fixed)]
        for i in range((n // 2) - 1):
            t1, t2 = rotating[i], rotating[-2 - i]
            pairings.append((t1, t2) if (r + i) % 2 == 0 else (t2, t1))
        rounds.append([(h, a) for h, a in pairings if h is not None and a is not None])
        rotating = [rotating[-1]] + rotating[:-1]
    return rounds


class Standings:
    """Tracks league table: 3/1/0 points, tiebreak GD then GF."""

    def __init__(self, team_ids):
        self.table = {
            tid: {"P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "PTS": 0}
            for tid in team_ids
        }

    def record(self, home_id, away_id, home_goals, away_goals):
        h, a = self.table[home_id], self.table[away_id]
        h["P"] += 1; a["P"] += 1
        h["GF"] += home_goals; h["GA"] += away_goals
        a["GF"] += away_goals; a["GA"] += home_goals
        if home_goals > away_goals:
            h["W"] += 1; h["PTS"] += 3; a["L"] += 1
        elif home_goals < away_goals:
            a["W"] += 1; a["PTS"] += 3; h["L"] += 1
        else:
            h["D"] += 1; a["D"] += 1; h["PTS"] += 1; a["PTS"] += 1

    def ranked(self):
        def gd(row):
            return row["GF"] - row["GA"]
        return sorted(
            self.table.items(),
            key=lambda kv: (-kv[1]["PTS"], -gd(kv[1]), -kv[1]["GF"]),
        )
