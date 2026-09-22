"""
Weekly Player Condition -- every player's effective rating fluctuates
match to match, on top of their fixed base ratings, so a lineup choice
that was right two weeks ago isn't automatically still right this week.

Two independent layers stack together:

1. ROUTINE WEEKLY FORM -- deterministic, same principle as every other
   random draw in this engine (match_seed, market tiers, draft order): a
   player's baseline condition for a given round is a pure function of
   (season_seed, round, player_id) -- reproducible after the fact, and
   NOT knowable in advance from anything else, so it can't be gamed by,
   say, submitting a lineup early or late.

     Poor            0.85x   10%
     Below Average   0.93x   20%
     Average         1.00x   40%
     Good            1.07x   20%
     Excellent       1.15x   10%

2. INJURIES -- NOT a pure function of round alone: whether a player
   picks one up depends on whether they actually started a match, so
   it's rolled once per round, after that round resolves, only for
   players who started (see roll_new_injuries()). An injury persists
   for 1-3 rounds and overrides the routine weekly-form roll for every
   round it's active. This is deliberately path-dependent -- an injury
   is a consequence of playing, not a fact about the calendar date --
   which is exactly why it has to be tracked in persistent state
   (data/player_injuries.json) rather than recomputed from scratch.

The multiplier applies equally to a player's ATT and DEF for that one
match (see simulate.team_ratings) -- "having a bad day" (or playing
hurt) makes a player worse at both ends of the pitch, not selectively
worse at one.

WHY THIS IS STILL SAFE TO PUBLISH BEFORE THE DEADLINE: round N's
conditions only ever depend on (a) the routine weekly-form formula for
round N, and (b) injury state carried over from rounds < N, which are
already fully resolved and fixed by the time round N's report is
generated. Nothing about round N's own lineup submissions feeds back
into round N's conditions. So as long as the report for round N is
generated AFTER round N-1 has been resolved (the natural order anyway),
what students see before the deadline is exactly what resolve_round.py
will use.
"""
import hashlib
import random

TIERS = [
    ("Poor", 0.85, 10),
    ("Below Average", 0.93, 20),
    ("Average", 1.00, 40),
    ("Good", 1.07, 20),
    ("Excellent", 1.15, 10),
]

INJURED_LABEL = "Injured"
INJURED_MULTIPLIER = 0.55  # meaningfully worse than even a Poor week
INJURY_CHANCE_PER_START = 0.06  # per player, per round actually started, if not already hurt
INJURY_DURATION_RANGE = (1, 3)  # rounds out, inclusive, rolled at the moment of injury


def _condition_seed(season_seed, round_num, player_id):
    key = f"{season_seed}:condition:{round_num}:{player_id}".encode()
    return int(hashlib.sha256(key).hexdigest()[:16], 16)


def _injury_seed(season_seed, round_num, player_id):
    key = f"{season_seed}:injury:{round_num}:{player_id}".encode()
    return int(hashlib.sha256(key).hexdigest()[:16], 16)


def get_condition(season_seed, round_num, player_id):
    """Returns (tier_label, multiplier) for one player in one round --
    the routine weekly-form roll only, ignoring injuries. Use
    conditions_for_round() below for the full picture."""
    rng = random.Random(_condition_seed(season_seed, round_num, player_id))
    labels = [t[0] for t in TIERS]
    mults = [t[1] for t in TIERS]
    weights = [t[2] for t in TIERS]
    idx = rng.choices(range(len(TIERS)), weights=weights, k=1)[0]
    return labels[idx], mults[idx]


def conditions_for_round(season_seed, round_num, players, injuries=None):
    """players: list of player dicts (from players.csv, via
    render_dashboard.load_players()).
    injuries: optional {player_id: injured_until_round} from
    data/player_injuries.json (see roll_new_injuries) -- a player with
    injured_until_round >= round_num is still out this round and
    overrides their routine weekly-form roll.

    Returns:
      mult_by_id:   {player_id: multiplier}          -- feed straight into
                     simulate.team_ratings(..., conditions=mult_by_id)
      detail_by_id: {player_id: (tier_label, multiplier, injured_until_round_or_None)}
    """
    injuries = injuries or {}
    mult_by_id = {}
    detail_by_id = {}
    for p in players:
        pid = p["player_id"]
        injured_until = injuries.get(pid)
        if injured_until is not None and injured_until >= round_num:
            tier, mult = INJURED_LABEL, INJURED_MULTIPLIER
            detail_by_id[pid] = (tier, mult, injured_until)
        else:
            tier, mult = get_condition(season_seed, round_num, pid)
            detail_by_id[pid] = (tier, mult, None)
        mult_by_id[pid] = mult
    return mult_by_id, detail_by_id


def roll_new_injuries(season_seed, round_num, starter_ids, injuries):
    """Call this AFTER resolving round `round_num`, with the player_ids
    of everyone who actually started a match that round (both sides, all
    fixtures). Mutates and returns `injuries` (a plain dict, load/save it
    as data/player_injuries.json around this call).

    Only a player who is NOT already injured heading into this round can
    newly pick one up -- an already-hurt player who got started anyway
    just keeps counting down, no double-injury stacking. Deterministic:
    seeded from season_seed + round + player_id, so reproducible after
    the fact like everything else in this engine."""
    for pid in starter_ids:
        if injuries.get(pid, -1) >= round_num:
            continue  # already out this round, can't get newly hurt on top of it
        rng = random.Random(_injury_seed(season_seed, round_num, pid))
        if rng.random() < INJURY_CHANCE_PER_START:
            duration = rng.randint(*INJURY_DURATION_RANGE)
            injuries[pid] = round_num + duration
    return injuries
