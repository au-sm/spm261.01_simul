"""
Generates WHEN and HOW each goal in a simulated match happened -- not
just the final score. simulate.py's Poisson draw already decides HOW
MANY goals each side scores; this module decides, for each of those
goals, a minute (1-90), a goal type, and which starting player scored
it, all from the SAME match rng passed in by simulate_match() so a full
season replay stays exactly as reproducible as the score itself (see
simulate.py's module docstring).

GOAL TYPES and how a scorer is picked for each:
  Strike, Header, Corner Kick -- random, weighted by POSITION (a
    forward is far more likely to poach a Strike than a defender is;
    a defender is more likely to score a Header off a set piece than
    an open-play Strike) and then, within that position group, by the
    attribute that actually matters for that action (att for Strike,
    phy for the two aerial types) -- so a team's best finisher/aerial
    threat scores more often, same "results trace back to a real
    attribute" principle as the rest of the engine.
  Penalty Kick, Free Kick -- DETERMINISTIC: the team's designated
    taker (highest ATT outfielder overall for penalties; highest ATT
    among MF/FW for free kicks, matching how real teams assign dead
    ball duty to one or two specialists) always takes it -- not
    randomized like the open-play types, since a real team doesn't
    re-roll who's on penalty duty from goal to goal.
"""

GOAL_TYPE_WEIGHTS = {
    "Strike": 0.42,
    "Header": 0.20,
    "Corner Kick": 0.18,
    "Penalty Kick": 0.12,
    "Free Kick": 0.08,
}

# position mix for the three RANDOM goal types (Penalty/Free Kick are
# deterministic taker-based, handled separately below)
POSITION_WEIGHTS = {
    "Strike": {"FW": 0.60, "MF": 0.32, "DF": 0.08},
    "Header": {"FW": 0.35, "DF": 0.40, "MF": 0.25},
    "Corner Kick": {"FW": 0.30, "DF": 0.45, "MF": 0.25},
}

# which player attribute the scorer is weighted by, within their position group
SCORER_ATTRIBUTE = {"Strike": "att", "Header": "phy", "Corner Kick": "phy"}


def _weighted_choice(rng, weight_map):
    """weight_map: {key: weight}. Returns one key, weighted by its share
    of the total (doesn't need to sum to exactly 1)."""
    items = list(weight_map.items())
    total = sum(w for _, w in items)
    r = rng.random() * total
    upto = 0.0
    for key, w in items:
        upto += w
        if r <= upto:
            return key
    return items[-1][0]


def _weighted_pick(rng, players, attr):
    """players: list of player dicts, all non-empty. Weighted by attr
    (a positive int rating), so a higher-rated player scores more often
    without the pick ever being fully deterministic."""
    weights = [max(1, p[attr]) for p in players]
    total = sum(weights)
    r = rng.random() * total
    upto = 0.0
    for p, w in zip(players, weights):
        upto += w
        if r <= upto:
            return p
    return players[-1]


def pick_scorer(rng, lineup, goal_type):
    """lineup: dict position -> list of player dicts (the team's actual
    starting XI for this match). Returns the player dict who scored."""
    outfield = {pos: lineup.get(pos, []) for pos in ("DF", "MF", "FW")}
    all_outfield = [p for pos in ("DF", "MF", "FW") for p in outfield[pos]]

    if goal_type == "Penalty Kick":
        return max(all_outfield, key=lambda p: p["att"])

    if goal_type == "Free Kick":
        dead_ball_pool = [p for pos in ("MF", "FW") for p in outfield[pos]] or all_outfield
        return max(dead_ball_pool, key=lambda p: p["att"])

    pos = _weighted_choice(rng, POSITION_WEIGHTS[goal_type])
    pool = outfield[pos] or all_outfield
    return _weighted_pick(rng, pool, SCORER_ATTRIBUTE[goal_type])


def generate_goal_events(rng, side, lineup, n_goals):
    """Returns n_goals event dicts for one side: {minute, side, type,
    scorer, scorer_position, scorer_id}. Not yet merged/sorted with the
    other side's events -- simulate_match() does that once it has both."""
    events = []
    for _ in range(n_goals):
        minute = rng.randint(1, 90)
        goal_type = _weighted_choice(rng, GOAL_TYPE_WEIGHTS)
        scorer = pick_scorer(rng, lineup, goal_type)
        events.append({
            "minute": minute,
            "side": side,
            "type": goal_type,
            "scorer": scorer["name"],
            "scorer_position": scorer["position"],
            "scorer_id": scorer["player_id"],
        })
    return events
