"""
Sponsorship negotiation engine for the SM Owners League.

THE RULE SYSTEM, IN FULL:

Sponsors PAY teams -- there is no cost to sign, matching how real
sponsorship works. Every sponsor posts a BASE OFFER: a season_revenue
number and a performance clause (strict / standard / loose / none).

REVENUE is negotiated on a single, simple axis: the final deal can land
anywhere from -10% to +10% of the brand's base_revenue. There are no
Modest/Bold/Very Bold tiers on this axis anymore -- one straightforward
choice:
  "base"          Take the listed revenue exactly. Guaranteed, zero risk.
  "negotiate"     Push for more. Where you land is set by your
                  NEGOTIATING LEVERAGE (0-100, built from your roster's
                  average Star Power, plus a standings bonus once the
                  season starts):
                    adjustment = -10% + (leverage / 100) * 20%
                  leverage 0 -> -10% (worst case), 50 -> base exactly,
                  100 -> +10% (best case). A weak hand can genuinely
                  land BELOW base -- negotiating is not risk-free the
                  way taking "base" is.

THE COMMISSION (the reason playing sponsor rep isn't just charity):
if a negotiated deal lands ABOVE base, the OVERAGE -- final_revenue
minus base_revenue -- is ALSO credited as bonus revenue to whichever
team's student played the sponsor rep in that negotiation. Landing
AT or BELOW base earns the rep's team nothing, but never costs them
anything either (upside-only, like a real sales commission: you're
never paid a negative commission for a deal that undersells).
Concretely: Nike lists at $3.5M; a deal closes at $3.8M; the signing
team records $3.8M revenue, and the student who played the Nike rep
records a $0.3M commission for THEIR OWN team.

CLAUSE remains its own, separate negotiation -- unaffected by the above.
Ask "looser_clause" at Modest/Bold/Very Bold intensity, gated by the
same leverage number against a required threshold; an unsuccessful ask
can still walk away (no clause change, no revenue change) the way it
always has. See CLAUSE_LEVELS below: strict -> standard -> loose -> none.

LEVERAGE (0-100), shared by both axes:
  leverage = clamp(0, 100, (avg_star_power - 50) * 2 + standings_bonus)
  standings_bonus = 0 before the season starts; once matches exist,
  +15 for a top-third team, +7 for middle-of-table, +0 for bottom-third.

THE MANDATORY RULE: every team must leave the Sponsorship Draft with
exactly one signed brand in every category (sponsorship_categories in
data/deals.json; the required count is
league_config.json -> sponsorship_categories_required). Multiple teams
may hold the same brand; qty on each brand is a LEAGUE-WIDE cap on how
many teams total can sign it, not an exclusivity lock.
"""
import random

REVENUE_RANGE = 0.10  # negotiated revenue can move +/- this fraction of base

REQUIRED_THRESHOLD = {  # clause negotiation only
    "modest": 20,
    "bold": 50,
    "very_bold": 80,
}

CLAUSE_UPSIDE = {  # clause negotiation only
    "modest": 0.10,
    "bold": 0.20,
    "very_bold": 0.30,
}

CLAUSE_LEVELS = ["strict", "standard", "loose", "none"]


def compute_leverage(avg_star_power, standings_rank=None, n_teams=None):
    """avg_star_power: the team's roster average Star Power (0-99).
    standings_rank: 1-indexed current rank, or None pre-season.
    n_teams: league size, required if standings_rank is given."""
    base = (avg_star_power - 50) * 2
    bonus = 0
    if standings_rank is not None and n_teams:
        top_cut = max(1, round(n_teams / 3))
        bottom_cut = n_teams - top_cut
        if standings_rank <= top_cut:
            bonus = 15
        elif standings_rank <= bottom_cut:
            bonus = 7
    return max(0, min(100, base + bonus))


def resolve_revenue(base_revenue, take_base, leverage):
    """
    Resolves the revenue axis. take_base=True -> exactly base_revenue,
    no risk. Otherwise, lands at base_revenue * (1 + adjustment), where
    adjustment ranges linearly from -REVENUE_RANGE (leverage=0) to
    +REVENUE_RANGE (leverage=100). Returns (final_revenue, commission)
    where commission is the amount ABOVE base (0 if at or below base) --
    the caller credits `commission` to whichever team played sponsor rep.
    """
    if take_base:
        return base_revenue, 0
    adjustment = -REVENUE_RANGE + (leverage / 100.0) * (2 * REVENUE_RANGE)
    final_revenue = round(base_revenue * (1 + adjustment))
    commission = max(0, final_revenue - base_revenue)
    return final_revenue, commission


def negotiate_clause(intensity, leverage, rng: random.Random):
    """Clause negotiation only -- unchanged mechanic. Returns
    {outcome, granted_fraction}, outcome one of accepted/partial/walk_away."""
    threshold = REQUIRED_THRESHOLD[intensity]
    gap = leverage - threshold

    if gap >= 15:
        return {"outcome": "accepted", "granted_fraction": 1.0}
    if gap <= -15:
        return {"outcome": "walk_away", "granted_fraction": 0.0}

    accept_prob = 0.5 + gap / 30.0
    if rng.random() < accept_prob:
        return {"outcome": "accepted", "granted_fraction": 1.0}
    return {"outcome": "partial", "granted_fraction": 0.5}


def resolve_clause(base_clause, intensity, leverage, rng: random.Random):
    result = negotiate_clause(intensity, leverage, rng)
    frac = result["granted_fraction"]
    upside = CLAUSE_UPSIDE.get(intensity, 0.0) * frac

    clause = base_clause
    if result["outcome"] != "walk_away" and upside > 0:
        idx = CLAUSE_LEVELS.index(base_clause) if base_clause in CLAUSE_LEVELS else 1
        steps = 2 if (intensity == "very_bold" and frac == 1.0) else 1
        clause = CLAUSE_LEVELS[min(len(CLAUSE_LEVELS) - 1, idx + steps)]

    return {"outcome": result["outcome"], "final_clause": clause}


def resolve_deal(base_revenue, base_clause, take_base_revenue, negotiate_clause_ask,
                  clause_intensity, leverage, rng: random.Random):
    """
    Full deal resolution combining both independent axes. negotiate_clause_ask:
    bool, whether to attempt a clause ask this negotiation (clause_intensity
    required if True). Returns final_revenue, commission (0 if take_base_revenue
    or revenue landed at/below base), and final_clause.
    """
    final_revenue, commission = resolve_revenue(base_revenue, take_base_revenue, leverage)

    final_clause = base_clause
    if negotiate_clause_ask:
        clause_result = resolve_clause(base_clause, clause_intensity, leverage, rng)
        final_clause = clause_result["final_clause"]

    return {
        "final_revenue": final_revenue,
        "commission": commission,
        "final_clause": final_clause,
        "leverage": leverage,
    }
