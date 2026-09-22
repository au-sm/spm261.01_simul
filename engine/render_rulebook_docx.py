"""
Renders the printable/editable Word Rulebook from the SAME data sources
as engine/render_rulebook.py (data/league_config.json, data/deals.json,
scorecard.py, player_condition.py) -- so the Word version and the live
HTML Rulebook can never drift out of sync with each other, or with the
actual dashboard/scorecard numbers, the way the old hand-authored
SM_Owners_League_Rulebook.docx did (it still described fixed Local/
Regional/National sponsorship tiers and a bracket-style playoff system,
both replaced by the live negotiation marketplace and the flat
qualification bonus long before this script was written).

Run any time league_config.json or deals.json changes, then hand the
output to whoever needs a printable/editable copy -- never overwrite an
existing rulebook .docx in place, always save under a new filename (see
project memory on this).

Usage:
    python3 engine/render_rulebook_docx.py [output_path]
"""
import json
import os
import sys

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

sys.path.insert(0, os.path.dirname(__file__))
from scorecard import WEIGHTS, linear_rank_points
from player_condition import (
    TIERS as CONDITION_TIERS, INJURED_MULTIPLIER, INJURY_CHANCE_PER_START, INJURY_DURATION_RANGE,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def money(n):
    return f"${n:,}"


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = str(h)
        for p in hdr[i].paragraphs:
            for r in p.runs:
                r.bold = True
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)
    if widths:
        for i, w in enumerate(widths):
            for row in table.rows:
                row.cells[i].width = Inches(w)
    doc.add_paragraph()
    return table


def add_bullets(doc, items, numbered=False):
    style = "List Number" if numbered else "List Bullet"
    for item in items:
        doc.add_paragraph(item, style=style)
    doc.add_paragraph()


def add_callout(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.italic = True
    p.paragraph_format.left_indent = Inches(0.3)


def build(config, deals, calendar=None):
    tv = deals["tv_deal_formula"]
    ltv = deals["local_tv_deal_formula"]
    tr = deals["trade_rules"]
    po = deals["playoffs"]
    qualification_bonus = po["qualification_bonus"]
    ce = deals["clause_enforcement"]
    rt = ce["rank_threshold_by_clause"]

    condition_tier_rows = [(label, f"{mult:.2f}x", f"{weight}%") for label, mult, weight in CONDITION_TIERS]

    dummy_ranked = list(range(config["n_teams"]))
    worked_revenue_pts = linear_rank_points(dummy_ranked, WEIGHTS["revenue"])[dummy_ranked[2]]
    worked_rationale_pts = round(0.875 * WEIGHTS["rationale"], 2)
    worked_total = round(WEIGHTS["ranking"] + WEIGHTS["playoffs"] + worked_revenue_pts + worked_rationale_pts, 2)

    doc = Document()

    title = doc.add_heading(f'{config["league_name"]} — Official Rulebook', level=0)
    sub = doc.add_paragraph(f'{config["season_label"]} · every rule, every formula, every point your grade is built from')
    sub.runs[0].italic = True
    doc.add_paragraph(
        "Numbers in this document are generated directly from data/league_config.json and data/deals.json — "
        "never hand-typed twice. See engine/render_rulebook_docx.py."
    ).runs[0].font.size = Pt(9)
    doc.add_page_break()

    # ---- Overview ----
    doc.add_heading("Overview", level=1)
    doc.add_paragraph(
        "You are not a player — you are the owner and general manager of a professional soccer club. "
        "Every decision a real front office makes — who to draft, how to line up, what to charge for "
        "tickets, which sponsor to sign, which trades to make, and how far you push for a championship — "
        "is yours to make, in writing, every round. Your grade is not just whether you win. It is whether "
        "you can run a sports business and explain why you made the calls you made."
    )

    # ---- 1. League Structure ----
    doc.add_heading("1. League Structure", level=1)
    add_table(doc, ["Setting", "Value"], [
        ("Teams", f'{config["n_teams"]} (one per student — solo ownership, no co-owners)'),
        ("Roster size", f'{config["roster_size"]} players per team'),
        ("Starting budget", money(config["starting_budget"])),
        ("Salary cap", money(config["salary_cap"])),
        ("Sponsorship", f'{config.get("sponsorship_categories_required", 6)} categories, one brand each, mandatory — sponsors pay you'),
        ("Regular season", "Round-robin — every team plays every other team once"),
        ("Playoffs", f'Top {config["playoff_teams"]} teams by regular-season standings'),
    ])

    # ---- 2. Player Ratings ----
    doc.add_heading("2. Player Ratings", level=1)
    doc.add_paragraph("Every player carries six ratings, 0-99 (the same convention as most sports video games):")
    add_table(doc, ["Rating", "What it measures"], [
        ("ATT", "Attack — finishing and creativity, the biggest input to scoring chances"),
        ("DEF", "Defense — tackling, positioning, shot-stopping"),
        ("PAC", "Pace — speed and recovery, a secondary contributor both ways"),
        ("PHY", "Physical — strength and stamina, a secondary contributor both ways"),
        ("OVR", "Overall — a quick-reference blend of the four above (NOT what the match engine uses directly)"),
        ("Star Power", "Marketability — deliberately independent of skill. Drives sponsorship eligibility and ticket demand."),
    ])
    doc.add_heading("Weekly Player Condition", level=2)
    doc.add_paragraph(
        "ATT and DEF above are a player's fixed BASE ratings — what actually goes into a match is scaled by "
        "that player's CONDITION for that specific round, redrawn every round for every player. A player who "
        "was excellent last week can be off this week, and vice versa — last week's lineup is not "
        "automatically this week's right call."
    )
    add_table(doc, ["Condition", "Multiplier", "Odds"], condition_tier_rows)
    doc.add_paragraph(
        "Condition is drawn once per player per round, from a fixed formula (your season seed + the round "
        "number + that player's ID) — not random in a way that can be gamed, and not knowable before the "
        "league office publishes it. It is published before that round's Weekly Lineup deadline, both on the "
        "live dashboard (each roster card shows a Condition badge per player) and as a standalone report "
        "(engine/generate_weekly_conditions.py) specifically so it's real information your starting XI and "
        "formation choice should account for, not a surprise revealed only in the result. A bench player in "
        "Excellent form can outperform a starter having a Poor week — reading the weekly report before you "
        "submit is part of the job."
    )
    doc.add_heading("Injuries", level=2)
    doc.add_paragraph(
        f"Every player who actually STARTS a match carries a {int(INJURY_CHANCE_PER_START*100)}% chance of "
        "picking up an injury that round — unlike the routine week-to-week Condition roll above, an injury "
        "is a CONSEQUENCE of playing, not a fresh dice roll every week, and it doesn't clear on its own "
        "until it runs its course."
    )
    add_table(doc, ["What", "Detail"], [
        ("Chance per start", f"{int(INJURY_CHANCE_PER_START*100)}%"),
        ("Duration", f"{INJURY_DURATION_RANGE[0]}-{INJURY_DURATION_RANGE[1]} rounds, randomly, once injured"),
        ("Effective multiplier while injured", f"{INJURED_MULTIPLIER:.2f}x"),
    ])
    doc.add_paragraph(
        'While injured, a player\'s Condition badge shows "Injured" (not one of the five routine tiers above) '
        "with how many rounds they're still out for — visible on the dashboard and in the weekly report "
        "exactly like ordinary form, before you submit. An already-injured player who gets started anyway "
        "just keeps counting down; they cannot get newly hurt on top of an existing injury. Bench them, or "
        "play them at a real, known cost — that decision, and being able to see it coming, is the point."
    )

    # ---- 3. The Draft ----
    doc.add_heading("3. The Draft", level=1)
    doc.add_paragraph("Before the season begins, every owner drafts a full roster from the shared player pool. Two hard rules apply:")
    add_bullets(doc, [
        f"Roster size is fixed at {config['roster_size']} players, filling every slot your formation choices require.",
        f"Total roster salary may never exceed the {money(config['salary_cap'])} salary cap — at draft time or afterward.",
    ])
    doc.add_paragraph("Undrafted players remain Free Agents, signable later in the season.")
    doc.add_heading("How the Draft Actually Runs", level=2)
    doc.add_paragraph(
        f"A real live snake draft — {config['roster_size']} rounds × {config['n_teams']} teams — is hundreds "
        "of sequential picks, far more than one class period holds. So Draft Day is a reveal, not a wait:"
    )
    add_bullets(doc, [
        "Before Draft Day: submit a ranked Draft Board of at least 25 players (more than the "
        f"{config['roster_size']} you need, so you still have real choices left once some of your targets are gone).",
        "Draft order: one randomized snake order (Round 1 picks 1..." + str(config["n_teams"]) +
        ", Round 2 picks " + str(config["n_teams"]) + "...1, alternating), drawn reproducibly from the season "
        "seed — the exact order can be independently re-verified after the fact, same principle as every match result.",
        "Live in class: the league office runs the resolution engine once, in front of everyone. At your turn "
        "each round, you get the highest-ranked player still on YOUR board who's still available and still "
        "fits under your remaining cap space — instant, no live back-and-forth required.",
        "If your whole board runs out before your roster is full (bad luck — too many targets taken ahead of "
        "you): autopick takes the highest-OVR player still available and affordable — same \"league office "
        "auto-fills\" fallback used for a missed Weekly Lineup (Section 4) or a missed Trade Day pairing (Section 10).",
    ], numbered=True)

    # ---- 4. Weekly Operations ----
    doc.add_heading("4. Weekly Operations", level=1)
    doc.add_paragraph(
        "Every round, before the deadline, each owner submits a Weekly Lineup & Strategy form: formation, "
        "strategy, starting XI by name, a ticket price if home that round, and a 2-4 sentence rationale "
        "(graded — Section 14). Every submission must also include your team's 4-digit PIN — a submission "
        "with a missing or incorrect PIN is rejected and that team is auto-lineup'd instead, so a lineup "
        "can't be changed (by accident or on purpose) by anyone but that team's own owner."
    )
    doc.add_paragraph(
        "Check that round's Player Condition report first (Section 2) — it's published before the deadline "
        "specifically so your starting XI and formation choice can react to who's actually in form this week, "
        "not just who has the highest base rating."
    )
    doc.add_paragraph(
        "If you do not submit: the league office auto-fills your highest-rated available player at each "
        "position, Balanced strategy, Standard pricing. Your match is still played and still counts — you "
        "simply forfeit rationale credit, since there is no decision to grade."
    )

    # ---- 5. Formations & Strategy ----
    doc.add_heading("5. Formations & Strategy", level=1)
    add_table(doc, ["Formation", "GK", "DF", "MF", "FW"], [
        ("4-4-2", 1, 4, 4, 2), ("4-3-3", 1, 4, 3, 3), ("3-5-2", 1, 3, 5, 2),
        ("5-3-2", 1, 5, 3, 2), ("4-5-1", 1, 4, 5, 1),
    ])
    add_table(doc, ["Strategy", "Effect"], [
        ("Attacking", "ATT x1.08 / DEF x0.92"),
        ("Balanced", "no change"),
        ("Defensive", "ATT x0.92 / DEF x1.08"),
    ])

    # ---- 6. How Match Results Are Determined ----
    doc.add_heading("6. How Match Results Are Determined", level=1)
    doc.add_paragraph(
        "Results are not a coin flip, and not roster OVR alone — every result traces to the lineup, "
        "formation, and strategy you actually submitted:"
    )
    add_bullets(doc, [
        "Each starter's ATT/DEF is first scaled by their Weekly Player Condition for this round (Section 2), "
        "then your starting XI's (condition-adjusted) ATT/DEF become one Team Attack and one Team Defense "
        "score, weighted by formation.",
        "Your Strategy choice shifts that balance further.",
        "The home team gets a fixed +5% Attack bonus.",
        "Attack vs. opposing Defense produces an expected-goals (xG) number for each side — a big mismatch "
        "caps out rather than producing an unrealistic blowout.",
        "The actual score is drawn randomly around each side's xG — the deliberate \"luck\" every real match "
        "has. A stronger team is more likely to win, never guaranteed to.",
        "Every scored goal also carries a real minute, a goal type (Strike, Header, Corner Kick, Penalty "
        "Kick, or Free Kick), and a real scorer drawn from that team's actual starting XI — not just a final score.",
    ], numbered=True)
    doc.add_paragraph(
        "Every match's random draw is seeded from the season's fixed seed plus that exact matchup — any "
        "result can be independently re-verified after the fact, and nothing is adjustable after the fact by "
        "the league office."
    )

    # ---- 7. Ticket Sales & Attendance ----
    doc.add_heading("7. Ticket Sales & Attendance", level=1)
    doc.add_paragraph(
        "As the home team, you set a ticket price tier. Attendance responds to price AND to your recent form "
        "and starting-XI Star Power:"
    )
    add_table(doc, ["Tier", "Price", "Effect"], [
        ("Budget", "$15", "Fills more seats, caps per-ticket revenue"),
        ("Standard", "$30", "Neutral default"),
        ("Premium", "$50", "Highest per-ticket revenue, but demand drops sharply without form/Star Power to justify it"),
    ])
    doc.add_paragraph(
        "There is no universally correct price — a struggling, low-Star-Power team pricing Premium will earn "
        "LESS than pricing Standard or Budget. Read your own team's market every home match."
    )

    # ---- 8. Sponsorship ----
    doc.add_heading("8. Sponsorship Deals & Negotiation", level=1)
    n_categories = len(deals["sponsorship_categories"])
    doc.add_paragraph(
        f"Sponsors pay you — there is no cost to sign anything, matching how real sponsorship deals work. "
        f"Brands are grouped into {n_categories} categories (real clubs carry exactly one jersey sponsor, one "
        "kit manufacturer, one official airline — not an unlimited pile of deals), and every team MUST sign "
        "exactly one brand per category before the draft ends — this is mandatory, not optional. Multiple "
        "teams may hold the same brand (Nike sponsors many real clubs at once); the \"slots\" number on each "
        "brand is a league-wide cap, not an exclusivity lock."
    )
    doc.add_paragraph(
        f"On your turn (same turn-order format as the player draft, cycling through all {n_categories} "
        "categories), target an open brand in whichever category you're filling. Two separate things are on "
        "the table:"
    )
    doc.add_heading("Revenue", level=2)
    doc.add_paragraph(
        "Take the listed Base revenue exactly (guaranteed, zero risk), or Negotiate. Negotiating lands you "
        "anywhere from -10% to +10% of the brand's base revenue, set by your Negotiating Leverage (built from "
        "your roster's average Star Power, plus a standings bonus once the season starts): leverage 0 lands "
        "at -10%, leverage 50 lands exactly at base, leverage 100 lands at +10%. Negotiating is not risk-free "
        "the way taking Base is — a weak hand can genuinely land below base."
    )
    doc.add_paragraph(
        "The commission: if a negotiated deal lands ABOVE base, the overage is ALSO credited as bonus "
        "revenue to whichever team's student played the sponsor rep in that negotiation — playing sponsor "
        "well pays off for your own team too, upside-only (landing at or below base costs the rep's team "
        "nothing, but earns them nothing either)."
    )
    doc.add_heading("Clause", level=2)
    doc.add_paragraph(
        "A separate ask: push for a looser clause at Modest / Bold / Very Bold intensity, gated by the same "
        "leverage number. Ask beyond what your leverage supports and the brand walks away on the clause "
        "specifically — that costs you nothing on the revenue side, and you can simply not push the clause further."
    )
    for cat in deals["sponsorship_categories"]:
        doc.add_heading(cat["category"], level=3)
        add_table(doc, ["Brand", "Base Revenue", "Base Clause", "League-wide Slots"], [
            (b["name"], money(b["base_revenue"]), b["base_clause"], b["qty"]) for b in cat["brands"]
        ])
    doc.add_heading("What the Clause Actually Means", level=2)
    doc.add_paragraph(
        "The performance clause is not flavor text — it is real revenue at risk, and each clause level sets "
        f"its OWN rank threshold to keep the money. Checked ONCE, at the end of the season (Round "
        f'{ce["checkpoint_round"]}, the final round): if your team\'s FINAL rank misses that specific deal\'s '
        f"threshold, that deal claws back a flat {int(ce['penalty_pct']*100)}% of its revenue — the clause "
        "you negotiated sets how hard the bar is to clear, not how much you lose if you miss it:"
    )
    add_table(doc, ["Clause", "Required final rank", "Penalty if missed"], [
        ("Strict", f'Top {rt["strict"]}', f"{int(ce['penalty_pct']*100)}%"),
        ("Standard", f'Top {rt["standard"]}', f"{int(ce['penalty_pct']*100)}%"),
        ("Loose", f'Top {rt["loose"]}', f"{int(ce['penalty_pct']*100)}%"),
        ("None", "No requirement", "0%, ever"),
    ])
    doc.add_paragraph(
        "This is checked PER SPONSOR, off your one final rank — a team can clear a loose-clause deal's easy "
        "bar while missing a strict-clause deal's demanding one in the exact same season. A strict clause "
        "pays more up front for a real bet that you'll actually contend; a loose clause is the safer, "
        "lower-upside insurance policy. Checked exactly once, at season end — never applied twice to the same deal."
    )
    doc.add_paragraph(
        "Full live marketplace (open slots, who's signed what) and a negotiation simulator to rehearse your "
        "ask before your draft turn: see the separate Sponsorship Marketplace site."
    )

    # ---- 9. TV / Broadcast Revenue ----
    doc.add_heading("9. TV / Broadcast Revenue", level=1)
    doc.add_heading("League-Wide (National) TV Deal", level=2)
    doc.add_paragraph(f'Base: {money(tv["base_payment_per_team"])} per team.')
    doc.add_paragraph(f'Standings bonus: {tv["standings_bonus"]}')
    doc.add_paragraph(f'Star Power bonus: {tv["star_power_bonus"]}')
    doc.add_paragraph(f'Split timing: {tv["midseason_split_timing"]}')
    doc.add_heading("Local TV Deals", level=2)
    doc.add_paragraph(ltv["description"])
    doc.add_paragraph(f'Market tiers: {ltv["market_tiers"]}')
    doc.add_paragraph(f'Star Power modifier: {ltv["star_power_modifier"]}')
    doc.add_paragraph(f'Payout timing: {ltv["payout_timing"]}')
    doc.add_paragraph(ltv["salary_cap_note"])
    doc.add_heading("Local TV Rights Negotiation", level=2)
    doc.add_paragraph(ltv["negotiation"])

    # ---- 10. Trades ----
    doc.add_heading("10. Trades & Free Agency", level=1)
    doc.add_paragraph(f'Deadline: {tr["deadline"]}')
    doc.add_paragraph(f'Salary cap rule: {tr["salary_cap"]}')
    doc.add_paragraph(f'Cash considerations: {tr["cash_considerations"]}')
    doc.add_paragraph(f'Approval: {tr["approval"]}')
    doc.add_heading("Mandatory Mid-Season Trade Day", level=2)
    doc.add_paragraph(tr["mid_season_trade_day"])

    # ---- 11. Standings ----
    doc.add_heading("11. Standings", level=1)
    doc.add_paragraph("Win = 3 points, draw = 1 point, loss = 0 points. Ties broken first by goal difference, then total goals scored.")

    # ---- 12. Playoff Qualification ----
    doc.add_heading("12. Playoff Qualification", level=1)
    doc.add_paragraph(po["format"])
    add_table(doc, ["Stage", "Bonus"], [
        (f'Finish in the top {config["playoff_teams"]} of the final standings', money(qualification_bonus)),
    ])
    doc.add_paragraph(po["bonus_notes"])

    # ---- 13. Season Scorecard ----
    doc.add_heading("13. The Season Scorecard — Your Grade", level=1)
    doc.add_paragraph(
        "The exam-replacement grade: 100 points across four components. Ranking and Revenue are scored "
        "relative to the rest of the league — 1st place earns full points, last earns zero, spaced evenly "
        "between — so the standard self-calibrates to however the season actually plays out."
    )
    add_table(doc, ["Component", "Points", "Question it answers", "How it's scored"], [
        ("Standings Rank", WEIGHTS["ranking"], "Did your team win?",
         f'Linear by finish: 1st = {WEIGHTS["ranking"]}, last = 0'),
        ("Playoff Qualification", WEIGHTS["playoffs"], "Did you make the playoffs?",
         f'Flat: full {WEIGHTS["playoffs"]} pts for finishing in the top {config["playoff_teams"]}, 0 '
         f'otherwise — not tiered, since finishing 1st vs. {config["playoff_teams"]}th is already rewarded by Ranking'),
        ("Business Revenue", WEIGHTS["revenue"], "Did you run it as a business?",
         "Ticket + sponsorship + national TV + local TV revenue, ranked against the league"),
        ("Decision Rationale", WEIGHTS["rationale"], "Could you explain your calls?",
         f'Season-average rubric score (Section 14), as a % of {WEIGHTS["rationale"]}'),
    ])
    add_callout(doc,
        "A well-reasoned decision that loses to bad luck scores exactly as well, on Rationale, as one that "
        "wins. A last-place team that runs a genuinely profitable franchise can still score well on Revenue. "
        "There is more than one way to earn a strong grade here."
    )
    doc.add_heading("Worked Example", level=2)
    doc.add_paragraph(
        f'A team that wins the league ({WEIGHTS["ranking"]}/{WEIGHTS["ranking"]} — full ranking points), '
        f'qualifies for the playoffs by finishing top {config["playoff_teams"]} '
        f'({WEIGHTS["playoffs"]}/{WEIGHTS["playoffs"]}), finishes 3rd in league revenue out of '
        f'{config["n_teams"]} teams ({worked_revenue_pts} pts), and averages a strong rationale score '
        f'({worked_rationale_pts} of {WEIGHTS["rationale"]}) lands at '
        f'{WEIGHTS["ranking"]} + {WEIGHTS["playoffs"]} + {worked_revenue_pts} + {worked_rationale_pts} = '
        f'{worked_total} out of 100.'
    )

    # ---- 14. Decision Rationale Rubric ----
    doc.add_heading("14. Decision Rationale Rubric", level=1)
    doc.add_paragraph(
        "Every round, your written rationale is scored against 4 criteria, 4 points each (16 possible; "
        "Business/Financial Reasoning is excluded on a plain lineup round with no trade/sponsorship attached, "
        "graded out of 12 instead). Your season average, as a percentage, becomes the 20-point Rationale "
        "component above."
    )
    add_table(doc, ["Criterion", "1 - Minimal", "2 - Developing", "3 - Proficient", "4 - Exemplary"], [
        ("Strategic Fit", "Unexplained or contradicts your own analysis", "Stated but the link to the opponent/roster is vague",
         "Clearly justified by a specific comparison", "Reflects a specific tactical read and anticipates a counter-response"),
        ("Use of Data", "No reference to ratings/stats/standings", "Mentions a stat without connecting it to the decision",
         "Cites specific ratings or standings/financial data", "Integrates multiple data points into one argument"),
        ("Business/Financial Reasoning", "No cap/budget/revenue consideration", "Acknowledges a cost without weighing it",
         "Weighs cost against benefit explicitly", "Frames it as a tradeoff among goals and states the priority"),
        ("Adaptability", "No reference to prior results", "Mentions a past result without changing the call",
         "Explicitly adjusts based on a prior outcome", "Names the signal, the lesson, and the causal link to this round"),
    ])
    doc.add_paragraph("Full descriptors: rubric/Decision_Rationale_Rubric.docx").runs[0].font.size = Pt(9)

    # ---- 15. Glossary ----
    doc.add_heading("15. Glossary", level=1)
    add_table(doc, ["Term", "Meaning"], [
        ("OVR", "Overall rating — a quick-reference blend of ATT/DEF/PAC/PHY"),
        ("ATT / DEF / PAC / PHY", "Attack / Defense / Pace / Physical — the four core skill ratings"),
        ("Star Power", "Marketability, independent of skill — drives sponsorship and attendance"),
        ("xG", "Expected goals — the engine's estimate before the random draw decides the actual score"),
        ("Salary cap", "The hard ceiling on total roster salary a team may carry"),
        ("Gate revenue", "Ticket sales revenue from a home match"),
        ("Free agent", "An undrafted player available for in-season signing"),
    ])

    # ---- 16. Season Calendar ----
    if calendar:
        total_rounds = sum(len(d["rounds"]) for d in calendar["match_day_schedule"])
        doc.add_heading("16. Season Calendar", level=1)
        doc.add_paragraph(f'Draft Day: {calendar["draft_day"]}')
        doc.add_paragraph(f'Match days: {calendar["match_days"]}')
        doc.add_paragraph(f'Mandatory Mid-Season Trade Day: {calendar["trade_day"]}')
        doc.add_paragraph(f'Season ends: {calendar["season_end"]} (Round {total_rounds} of {total_rounds})')
        add_table(doc, ["Date", "Round(s)"], [
            (d["date"], f'Round {d["rounds"][0]}' if len(d["rounds"]) == 1
             else f'Rounds {d["rounds"][0]}-{d["rounds"][-1]}')
            for d in calendar["match_day_schedule"]
        ])

    return doc


if __name__ == "__main__":
    config = load_json("league_config.json")
    deals = load_json("deals.json")
    cal_path = os.path.join(BASE, "data", "season_calendar.json")
    calendar = load_json("season_calendar.json") if os.path.exists(cal_path) else None
    doc = build(config, deals, calendar)

    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        BASE, f'{config["league_name"].replace(" ", "_").replace(".", "_")}_Rulebook.docx'
    )
    doc.save(out_path)
    print(f"Saved -> {out_path}")
