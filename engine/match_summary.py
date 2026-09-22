"""
Turns a match's structured goal_events (from goal_events.py) into a
short written recap -- "Team A struck first through a Marco Andrade
header in the 23rd minute..." -- not just a score line or a bare list
of events. Pure function of already-stored data (home/away names,
scores, goal_events), no new randomness: the same match always produces
the exact same recap text, same reproducibility principle as everything
else in this engine. Phrasing variety comes from the goal's own index/
minute, not a fresh random draw, so re-generating this summary later
(e.g. from render_matchday_replay.py) can never disagree with what
resolve_round.py printed when the round was first resolved.

Used by:
  - resolve_round.py, printed to console alongside the score line
  - render_matchday_replay.py, shown as a "Match Story" paragraph
"""

STRIKE_PHRASES = [
    "finished clinically", "found the net with a well-struck effort",
    "beat the keeper with a low, driven finish", "slotted it home from inside the box",
]
HEADER_PHRASES = [
    "rose highest to head it home", "powered a header past the keeper",
    "nodded it in from close range", "climbed above the defense to head it in",
]
CORNER_PHRASES = [
    "turned it home from a corner", "converted from a corner delivery",
    "was first to react at the near post off a corner", "met the corner cleanly to score",
]
PENALTY_PHRASES = [
    "converted coolly from the penalty spot", "made no mistake from twelve yards",
    "sent the keeper the wrong way from the spot", "kept composed to convert the penalty",
]
FREEKICK_PHRASES = [
    "curled a free kick into the net", "beat the wall with a direct free kick",
    "bent a free kick past the keeper", "found the top corner from a free kick",
]
TYPE_PHRASES = {
    "Strike": STRIKE_PHRASES, "Header": HEADER_PHRASES, "Corner Kick": CORNER_PHRASES,
    "Penalty Kick": PENALTY_PHRASES, "Free Kick": FREEKICK_PHRASES,
}


def _ordinal_minute(m):
    if 10 <= m % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(m % 10, "th")
    return f"{m}{suf}"


def _phrase_for(goal, idx):
    pool = TYPE_PHRASES[goal["type"]]
    return pool[(goal["minute"] + idx) % len(pool)]


def generate_summary(home_name, away_name, home_goals, away_goals, goal_events):
    """Returns a short (2-5 sentence) written recap. goal_events must
    already be sorted by minute (as simulate_match/resolve_round.py store
    them)."""
    if not goal_events:
        return (f"{home_name} and {away_name} played out a scoreless draw -- "
                f"neither side could find a breakthrough. Final score: {home_name} 0, {away_name} 0.")

    sentences = []
    running = {"home": 0, "away": 0}
    names = {"home": home_name, "away": away_name}

    for i, g in enumerate(goal_events):
        side, other = g["side"], ("away" if g["side"] == "home" else "home")
        was_tied = running["home"] == running["away"]
        was_leading = running[side] > running[other]
        running[side] += 1

        scorer, minute_str, phrase = g["scorer"], _ordinal_minute(g["minute"]), _phrase_for(g, i)
        team = names[side]

        if i == 0:
            sentences.append(f"{team} struck first -- {scorer} {phrase} in the {minute_str} minute.")
        elif was_tied:
            sentences.append(f"{scorer} put {team} back in front in the {minute_str}, {phrase}.")
        elif was_leading:
            margin = running[side] - running[other]
            verb = "doubled" if margin == 2 else ("extended" if margin > 2 else "restored")
            sentences.append(f"{scorer} {verb} {team}'s lead in the {minute_str} minute, {phrase}.")
        elif running[side] == running[other]:
            sentences.append(f"{team} leveled things up -- {scorer} {phrase} in the {minute_str} minute.")
        else:
            sentences.append(f"{scorer} pulled one back for {team} in the {minute_str} minute, {phrase}.")

    if home_goals > away_goals:
        close = f"{home_name} held on for a {home_goals}-{away_goals} win."
    elif away_goals > home_goals:
        close = f"{away_name} came away with a {away_goals}-{home_goals} win on the road."
    else:
        close = f"It finished level, {home_goals}-{away_goals}."
    sentences.append(close)

    return " ".join(sentences)
