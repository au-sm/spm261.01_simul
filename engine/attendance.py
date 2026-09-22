"""
Ticket pricing and attendance for the SM Owners League.

Every home match, a team sets a ticket price TIER (submitted on the same
weekly form as lineup/strategy). Attendance responds to that price plus
two things the owner has already earned on the field: recent form and
roster star power. Revenue = attendance x price -- the point is the
classic price-elasticity tradeoff: Premium pricing pays more per fan
but empties seats; Budget pricing fills the building but caps the
per-ticket upside. There is no single right answer, which is exactly
why it belongs in a business-management course.

FORMULA:
  attendance_rate = BASE_RATE
                     + PRICE_EFFECT[tier]
                     + (recent_win_rate - 0.5) * FORM_WEIGHT
                     + (avg_star_power - 50) / 50 * STAR_WEIGHT
  clamped to [MIN_RATE, MAX_RATE], then
  attendance = round(capacity * attendance_rate)
  revenue = attendance * PRICE_TIERS[tier]

recent_win_rate: win rate over the team's last 3 played matches (0.5 --
i.e. a neutral debut -- if fewer than 3 have been played yet).
avg_star_power: the team's STARTING XI average Star Power for that match
(not the whole roster) -- fans come to see who's actually playing.
"""

CAPACITY = 20000

PRICE_TIERS = {"Budget": 15, "Standard": 30, "Premium": 50}
PRICE_EFFECT = {"Budget": 0.15, "Standard": 0.0, "Premium": -0.30}

BASE_RATE = 0.60
FORM_WEIGHT = 0.40   # +/- 20 points of attendance at the extremes of win rate
STAR_WEIGHT = 0.15   # +/- 15 points of attendance at the extremes of star power
# MIN_RATE is deliberately low (not a generous floor): Premium pricing on a
# team with no form and no star power must be allowed to crater below what
# Budget/Standard would draw, or the floor quietly rescues Premium's revenue
# and erases the price-elasticity lesson the whole mechanic exists to teach.
MIN_RATE = 0.05
MAX_RATE = 1.00


def recent_win_rate(team_id, matches, upto_round, window=3):
    """Win rate over the team's last `window` played matches strictly
    before `upto_round`. Returns 0.5 (neutral) if fewer than 1 match played."""
    played = [
        m for m in matches
        if m["round"] < upto_round and team_id in (m["home_id"], m["away_id"])
    ]
    played = sorted(played, key=lambda m: -m["round"])[:window]
    if not played:
        return 0.5
    wins = 0
    for m in played:
        is_home = m["home_id"] == team_id
        gf, ga = (m["home_goals"], m["away_goals"]) if is_home else (m["away_goals"], m["home_goals"])
        if gf > ga:
            wins += 1
    return wins / len(played)


def compute_attendance(price_tier, recent_win_rate_val, avg_star_power, capacity=CAPACITY):
    if price_tier not in PRICE_TIERS:
        raise ValueError(f"unknown price tier: {price_tier}")
    rate = (
        BASE_RATE
        + PRICE_EFFECT[price_tier]
        + (recent_win_rate_val - 0.5) * FORM_WEIGHT
        + (avg_star_power - 50) / 50 * STAR_WEIGHT
    )
    rate = max(MIN_RATE, min(MAX_RATE, rate))
    attendance = round(capacity * rate)
    revenue = attendance * PRICE_TIERS[price_tier]
    return {
        "price_tier": price_tier,
        "price": PRICE_TIERS[price_tier],
        "attendance_rate": round(rate, 3),
        "attendance": attendance,
        "revenue": revenue,
    }
