"""
Renders rulebook/index.html from data/league_config.json and
data/deals.json -- the SAME source files the dashboard and the
scorecard engine read, so a number can never drift between the
rulebook, the dashboard, and an actual grade. Re-run this any time
league_config.json or deals.json changes (a new sponsorship tier, an
adjusted salary cap, etc.) and republish rulebook/index.html.

Word-doc version (SM_Owners_League_Rulebook.docx, project root) is the
printable/editable copy for the syllabus; this HTML page is the
easy-to-read, easy-to-share version -- keep both in sync by hand if the
rules change, since the docx is authored separately.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from scorecard import WEIGHTS, RANK_STEP, linear_rank_points
from player_condition import (
    TIERS as CONDITION_TIERS, INJURED_MULTIPLIER, INJURY_CHANCE_PER_START, INJURY_DURATION_RANGE,
)
from site_nav import NAV_CSS, render_nav

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def money(n):
    return f"${n:,}"


def render(config, deals, calendar=None):
    tv = deals["tv_deal_formula"]
    ltv = deals["local_tv_deal_formula"]
    tr = deals["trade_rules"]
    po = deals["playoffs"]
    qualification_bonus = po["qualification_bonus"]
    ce = deals["clause_enforcement"]
    rt = ce["rank_threshold_by_clause"]

    n_categories = len(deals["sponsorship_categories"])
    category_blocks = ""
    for cat in deals["sponsorship_categories"]:
        rows = "".join(
            f'<tr><td>{b["name"]}</td><td class="num">{money(b["base_revenue"])}</td><td>{b["base_clause"]}</td><td class="num">{b["qty"]}</td></tr>'
            for b in cat["brands"]
        )
        category_blocks += f'''
      <h3>{cat["category"]}</h3>
      <table><thead><tr><th>Brand</th><th class="num">Base Revenue</th><th>Base Clause</th><th class="num">League-wide Slots</th></tr></thead>
      <tbody>{rows}</tbody></table>'''

    sponsor_html = f'''
      <p><strong>Sponsors pay you</strong> &mdash; there is no cost to sign anything, matching how real sponsorship deals
      work. Brands are grouped into {n_categories} categories (real clubs carry exactly one jersey sponsor, one kit
      manufacturer, one official airline &mdash; not an unlimited pile of deals), and every team MUST sign
      <strong>exactly one brand per category</strong> before the draft ends &mdash; this is mandatory, not optional.
      Multiple teams may hold the same brand (Nike sponsors many real clubs at once); the "slots" number on each brand is
      a league-wide cap, not an exclusivity lock.</p>
      <p>On your turn (same turn-order format as the player draft, cycling through all {n_categories} categories), target
      an open brand in whichever category you're filling. Two separate things are on the table:</p>
      <h3>Revenue</h3>
      <p>Take the listed Base revenue exactly (guaranteed, zero risk), or Negotiate. Negotiating lands you anywhere from
      <strong>&minus;10% to +10%</strong> of the brand's base revenue, set by your <strong>Negotiating Leverage</strong>
      (built from your roster's average Star Power, plus a standings bonus once the season starts): leverage 0 lands at
      &minus;10%, leverage 50 lands exactly at base, leverage 100 lands at +10%. Negotiating is not risk-free the way
      taking Base is &mdash; a weak hand can genuinely land below base.</p>
      <p><strong>The commission:</strong> whenever a negotiated deal lands away from base &mdash; in EITHER direction
      &mdash; that gap is ALSO credited as bonus revenue to whichever team's student played the sponsor rep in that
      negotiation. Land above base (good for the signing team) and the overage goes to the rep's team; talk the team
      down below base (good for the sponsor) and the savings goes to the rep's team instead. Landing exactly at base
      earns nobody a commission, since nothing was actually negotiated. Never a deduction from the signing team's own
      booked revenue either way.</p>
      <h3>Clause</h3>
      <p>A separate ask: push for a looser clause at Modest / Bold / Very Bold intensity, gated by the same leverage
      number. Ask beyond what your leverage supports and the brand walks away on the clause specifically &mdash; that
      costs you nothing on the revenue side, and you can simply not push the clause further.</p>
      {category_blocks}
      <h3>What the Clause Actually Means</h3>
      <p>The performance clause is not flavor text -- it is real revenue at risk, and each clause level sets its OWN
      rank threshold to keep the money. Checked ONCE, at the end of the season (Round {ce["checkpoint_round"]}, the final
      round): if your team's FINAL rank misses that specific deal's threshold, that deal claws back a flat
      <strong>{int(ce["penalty_pct"]*100)}%</strong> of its revenue -- the clause you negotiated sets how hard the bar is
      to clear, not how much you lose if you miss it:</p>
      <table><thead><tr><th>Clause</th><th class="num">Required final rank</th><th class="num">Penalty if missed</th></tr></thead><tbody>
        <tr><td>Strict</td><td class="num">Top {rt["strict"]}</td><td class="num">{int(ce["penalty_pct"]*100)}%</td></tr>
        <tr><td>Standard</td><td class="num">Top {rt["standard"]}</td><td class="num">{int(ce["penalty_pct"]*100)}%</td></tr>
        <tr><td>Loose</td><td class="num">Top {rt["loose"]}</td><td class="num">{int(ce["penalty_pct"]*100)}%</td></tr>
        <tr><td>None</td><td class="num">No requirement</td><td class="num">0%, ever</td></tr>
      </tbody></table>
      <p>This is checked PER DEAL, off your one final rank -- a team can clear a loose-clause deal's easy bar while
      missing a strict-clause deal's demanding one in the exact same season, whether those deals are both sponsors or
      one is a sponsor and the other your Local TV Deal (see the TV / Broadcast Revenue section below -- Local TV
      deals carry a clause too, checked against this exact same table). A strict clause pays more up front for a real
      bet that you'll actually contend; a loose clause is the safer, lower-upside insurance policy. Checked exactly
      once, at season end -- never applied twice to the same deal.</p>
      <p>Full live marketplace (open slots, who's signed what) and a negotiation simulator to rehearse your ask before
      your draft turn: see the separate Sponsorship Marketplace site.</p>'''

    calendar_html = ""
    if calendar:
        total_rounds = sum(len(d["rounds"]) for d in calendar["match_day_schedule"])
        cal_rows = "".join(
            f'<tr><td>{d["date"]}</td><td class="num">{"Round " + str(d["rounds"][0]) if len(d["rounds"]) == 1 else "Rounds " + str(d["rounds"][0]) + "-" + str(d["rounds"][-1])}</td></tr>'
            for d in calendar["match_day_schedule"]
        )
        calendar_html = f'''
          <p><strong>Draft Day:</strong> {calendar["draft_day"]}</p>
          <p><strong>Match days:</strong> {calendar["match_days"]}</p>
          <p><strong>Mandatory Mid-Season Trade Day:</strong> {calendar["trade_day"]}</p>
          <p><strong>Season ends:</strong> {calendar["season_end"]} (Round {total_rounds} of {total_rounds})</p>
          <table><thead><tr><th>Date</th><th class="num">Round(s)</th></tr></thead><tbody>{cal_rows}</tbody></table>'''

    # Section 4's condition-tier table, pulled from player_condition.py's
    # TIERS so it can't drift from what the engine actually uses.
    condition_tier_rows = "".join(
        f'<tr><td>{label}</td><td class="num">{mult:.2f}x</td><td class="num">{weight}%</td></tr>'
        for label, mult, weight in CONDITION_TIERS
    )

    # Worked example for Section 1 -- recomputed from the live WEIGHTS/n_teams
    # so this can never drift the way the old hardcoded "30 + 25 + 22.4 + 17.5"
    # text did when the weights or team count changed.
    dummy_ranked = list(range(config["n_teams"]))
    worked_revenue_pts = linear_rank_points(dummy_ranked, WEIGHTS["revenue"])[dummy_ranked[2]]  # 3rd place
    worked_rationale_pts = round(0.875 * WEIGHTS["rationale"], 2)  # illustrative strong-but-not-perfect score
    worked_total = round(WEIGHTS["ranking"] + WEIGHTS["playoffs"] + worked_revenue_pts + worked_rationale_pts, 2)
    last_ranking_pts = linear_rank_points(dummy_ranked, WEIGHTS["ranking"])[dummy_ranked[-1]]
    last_revenue_pts = linear_rank_points(dummy_ranked, WEIGHTS["revenue"])[dummy_ranked[-1]]

    sections = [
        ("overview", "Overview", f'''
          <p>You are not a player &mdash; you are the <strong>owner and general manager</strong> of a professional soccer club.
          Every decision a real front office makes &mdash; who to draft, how to line up, what to charge for tickets, which sponsor
          to sign, which trades to make, and how far you push for a championship &mdash; is yours to make, in writing, every round.
          Your grade is not just whether you win. It is whether you can run a sports business and explain why you made the calls
          you made.</p>'''),

        ("scorecard", "1. The Season Scorecard &mdash; Your Grade", f'''
          <p>100 points across four components. <strong>Ranking and Revenue are scored
          relative to the rest of the league</strong> &mdash; 1st place earns full points, and every place below the one
          above it costs a flat {RANK_STEP} point, not a fraction of the whole component spread evenly down to zero.
          Finishing last still costs you real points relative to your classmates, but it does not wipe out the entire
          component the way an even 1st-to-0 spread would.</p>
          <table><thead><tr><th>Component</th><th class="num">Points</th><th>Question it answers</th><th>How it's scored</th></tr></thead><tbody>
            <tr><td>Standings Rank</td><td class="num">{WEIGHTS["ranking"]}</td><td>Did your team win?</td><td>1st = {WEIGHTS["ranking"]}, &minus;{RANK_STEP} pt per place down (last of {config["n_teams"]} = {last_ranking_pts})</td></tr>
            <tr><td>Playoff Qualification</td><td class="num">{WEIGHTS["playoffs"]}</td><td>Did you make the playoffs?</td><td>Flat: full {WEIGHTS["playoffs"]} pts for finishing in the top {config["playoff_teams"]}, 0 otherwise &mdash; not tiered, since finishing 1st vs. {config["playoff_teams"]}th is already rewarded by Ranking</td></tr>
            <tr><td>Business Revenue</td><td class="num">{WEIGHTS["revenue"]}</td><td>Did you run it as a business?</td><td>1st = {WEIGHTS["revenue"]}, &minus;{RANK_STEP} pt per place down (last of {config["n_teams"]} = {last_revenue_pts}) &mdash; ticket + sponsorship + national TV + local TV revenue</td></tr>
            <tr><td>Decision Rationale</td><td class="num">{WEIGHTS["rationale"]}</td><td>Could you explain your calls?</td><td>Average grade on the written explanation you submit with your Weekly Lineup, as a % of {WEIGHTS["rationale"]}</td></tr>
          </tbody></table>
          <p class="callout">A well-reasoned decision that loses to bad luck scores exactly as well, on Rationale, as one
          that wins. A last-place team still earns {last_ranking_pts} of {WEIGHTS["ranking"]} Ranking points and
          {last_revenue_pts} of {WEIGHTS["revenue"]} Revenue points just for being in the league, and a last-place team
          that runs a genuinely profitable franchise can still score well on Revenue. There is more than one way to earn
          a strong grade here.</p>
          <h3>Worked Example</h3>
          <p>A team that wins the league ({WEIGHTS["ranking"]}/{WEIGHTS["ranking"]} &mdash; full ranking points), qualifies for the playoffs by finishing top
          {config["playoff_teams"]} ({WEIGHTS["playoffs"]}/{WEIGHTS["playoffs"]}), finishes 3rd in league revenue out of {config["n_teams"]} teams ({worked_revenue_pts} pts), and
          averages a strong rationale score ({worked_rationale_pts} of {WEIGHTS["rationale"]}) lands at
          <strong>{WEIGHTS["ranking"]} + {WEIGHTS["playoffs"]} + {worked_revenue_pts} + {worked_rationale_pts} = {worked_total}</strong> out of 100.</p>'''),

        ("rubric", "2. Decision Rationale Rubric", '''
          <p>Every round, your written rationale is scored against 4 criteria, 4 points each (16 possible; Business/Financial
          Reasoning is excluded on a plain lineup round with no trade/sponsorship attached, graded out of 12 instead). Your
          season average, as a percentage, becomes the 20-point Rationale component above.</p>
          <table><thead><tr><th>Criterion</th><th>1 &mdash; Minimal</th><th>2 &mdash; Developing</th><th>3 &mdash; Proficient</th><th>4 &mdash; Exemplary</th></tr></thead>
          <tbody>
            <tr><td>Strategic Fit</td><td>Unexplained or contradicts your own analysis</td><td>Stated but the link to the opponent/roster is vague</td><td>Clearly justified by a specific comparison</td><td>Reflects a specific tactical read and anticipates a counter-response</td></tr>
            <tr><td>Use of Data</td><td>No reference to ratings/stats/standings</td><td>Mentions a stat without connecting it to the decision</td><td>Cites specific ratings or standings/financial data</td><td>Integrates multiple data points into one argument</td></tr>
            <tr><td>Business/Financial Reasoning</td><td>No cap/budget/revenue consideration</td><td>Acknowledges a cost without weighing it</td><td>Weighs cost against benefit explicitly</td><td>Frames it as a tradeoff among goals and states the priority</td></tr>
            <tr><td>Adaptability</td><td>No reference to prior results</td><td>Mentions a past result without changing the call</td><td>Explicitly adjusts based on a prior outcome</td><td>Names the signal, the lesson, and the causal link to this round</td></tr>
          </tbody></table>
          <p>Full descriptors: <span class="mono">rubric/Decision_Rationale_Rubric.docx</span>.</p>'''),

        ("structure", "3. League Structure", f'''
          <table><thead><tr><th>Setting</th><th>Value</th></tr></thead><tbody>
            <tr><td>Teams</td><td>{config["n_teams"]} (one per student &mdash; solo ownership, no co-owners)</td></tr>
            <tr><td>Roster size</td><td>{config["roster_size"]} players per team</td></tr>
            <tr><td>Starting budget</td><td class="num">{money(config["starting_budget"])}</td></tr>
            <tr><td>Salary cap</td><td class="num">{money(config["salary_cap"])}</td></tr>
            <tr><td>Sponsorship</td><td>{config.get("sponsorship_categories_required", 6)} categories, one brand each, mandatory &mdash; sponsors pay you</td></tr>
            <tr><td>Regular season</td><td>Round-robin &mdash; every team plays every other team once</td></tr>
            <tr><td>Playoffs</td><td>Top {config["playoff_teams"]} teams by regular-season standings</td></tr>
          </tbody></table>'''),

        ("ratings", "4. Player Ratings", f'''
          <p>Every player carries six ratings, 0&ndash;99 (the same convention as most sports video games):</p>
          <table><thead><tr><th>Rating</th><th>What it measures</th></tr></thead><tbody>
            <tr><td class="mono">ATT</td><td>Attack &mdash; finishing and creativity, the biggest input to scoring chances</td></tr>
            <tr><td class="mono">DEF</td><td>Defense &mdash; tackling, positioning, shot-stopping</td></tr>
            <tr><td class="mono">PAC</td><td>Pace &mdash; speed and recovery, a secondary contributor both ways</td></tr>
            <tr><td class="mono">PHY</td><td>Physical &mdash; strength and stamina, a secondary contributor both ways</td></tr>
            <tr><td class="mono">OVR</td><td>Overall &mdash; a quick-reference blend of the four above (NOT what the match engine uses directly)</td></tr>
            <tr><td class="mono">Star Power</td><td>Marketability &mdash; deliberately independent of skill. Drives sponsorship eligibility and ticket demand.</td></tr>
          </tbody></table>
          <h3>Weekly Player Condition</h3>
          <p>ATT and DEF above are a player's fixed BASE ratings &mdash; what actually goes into a match is scaled by that
          player's CONDITION for that specific round, redrawn every round for every player. A player who was excellent last
          week can be off this week, and vice versa &mdash; last week's lineup is not automatically this week's right call.</p>
          <table><thead><tr><th>Condition</th><th class="num">Multiplier</th><th class="num">Odds</th></tr></thead><tbody>
            {condition_tier_rows}
          </tbody></table>
          <p>Condition is drawn once per player per round, from a fixed formula (your season seed + the round number + that
          player's ID) &mdash; not random in a way that can be gamed, and not knowable before the league office publishes it.
          <strong>It is published before that round's Weekly Lineup deadline</strong>, both on the live dashboard (each roster
          card shows a Condition badge per player) and as a standalone report (<span class="mono">engine/generate_weekly_conditions.py</span>)
          specifically so it's real information your starting XI and formation choice should account for, not a surprise
          revealed only in the result. A bench player in Excellent form can outperform a starter having a Poor week &mdash;
          reading the weekly report before you submit is part of the job.</p>
          <h3>Injuries</h3>
          <p>Every player who actually STARTS a match carries a {int(INJURY_CHANCE_PER_START*100)}% chance of picking up an
          injury that round &mdash; unlike the routine week-to-week Condition roll above, an injury is a CONSEQUENCE of
          playing, not a fresh dice roll every week, and it doesn't clear on its own until it runs its course.</p>
          <table><thead><tr><th>What</th><th>Detail</th></tr></thead><tbody>
            <tr><td>Chance per start</td><td class="num">{int(INJURY_CHANCE_PER_START*100)}%</td></tr>
            <tr><td>Duration</td><td>{INJURY_DURATION_RANGE[0]}&ndash;{INJURY_DURATION_RANGE[1]} rounds, randomly, once injured</td></tr>
            <tr><td>Effective multiplier while injured</td><td class="num">{INJURED_MULTIPLIER:.2f}x</td></tr>
          </tbody></table>
          <p>While injured, a player's Condition badge shows "Injured" (not one of the five routine tiers above) with how many
          rounds they're still out for &mdash; visible on the dashboard and in the weekly report exactly like ordinary form,
          before you submit. An already-injured player who gets started anyway just keeps counting down; they cannot get
          newly hurt on top of an existing injury. Bench them, or play them at a real, known cost &mdash; that decision, and
          being able to see it coming, is the point.</p>'''),

        ("draft", "5. The Draft", f'''
          <p>Before the season begins, every owner drafts a full roster from the shared player pool. Two hard rules apply:</p>
          <ul>
            <li>Roster size is fixed at {config["roster_size"]} players, filling every slot your formation choices require.</li>
            <li>Total roster salary may never exceed the {money(config["salary_cap"])} salary cap &mdash; at draft time or afterward.</li>
          </ul>
          <p>Undrafted players remain Free Agents, signable later in the season.</p>
          <h3>How the Draft Actually Runs</h3>
          <p>A real live snake draft &mdash; {config["roster_size"]} rounds &times; {config["n_teams"]} teams &mdash; is hundreds of
          sequential picks, far more than one class period holds. So Draft Day is a <strong>reveal, not a wait</strong>:</p>
          <ol>
            <li><strong>Before Draft Day:</strong> submit a ranked <strong>Draft Board</strong> of at least 25 players (more than
            the {config["roster_size"]} you need, so you still have real choices left once some of your targets are gone).</li>
            <li><strong>Draft order:</strong> one randomized snake order (Round 1 picks 1&hellip;{config["n_teams"]}, Round 2 picks
            {config["n_teams"]}&hellip;1, alternating), drawn reproducibly from the season seed &mdash; the exact order can be
            independently re-verified after the fact, same principle as every match result.</li>
            <li><strong>Live in class:</strong> the league office runs the resolution engine once, in front of everyone. At your
            turn each round, you get the highest-ranked player still on YOUR board who's still available and still fits under
            your remaining cap space &mdash; instant, no live back-and-forth required.</li>
            <li><strong>If your whole board runs out</strong> before your roster is full (bad luck &mdash; too many targets taken
            ahead of you): autopick takes the highest-OVR player still available and affordable &mdash; same "league office
            auto-fills" fallback used for a missed Weekly Lineup submission or a missed Trade Day pairing.</li>
          </ol>'''),

        ("weekly", "6. Weekly Operations", '''
          <p>Every round, before the deadline, each owner submits a Weekly Lineup &amp; Strategy form: formation, strategy,
          starting XI by name, a ticket price if home that round, and a 2&ndash;4 sentence rationale (graded &mdash; see the grading table below).</p>
          <p><strong>Check that round's Player Condition report first</strong> (see Player Ratings above) &mdash; it's published before the
          deadline specifically so your starting XI and formation choice can react to who's actually in form this week, not
          just who has the highest base rating.</p>
          <p><strong>If you do not submit:</strong> the league office auto-fills your highest-rated available player at each
          position, Balanced strategy, Standard pricing. Your match is still played and still counts &mdash; you simply
          forfeit rationale credit, since there is no decision to grade.</p>'''),

        ("formations", "7. Formations &amp; Strategy", '''
          <table><thead><tr><th>Formation</th><th class="num">GK</th><th class="num">DF</th><th class="num">MF</th><th class="num">FW</th></tr></thead><tbody>
            <tr><td class="mono">4-4-2</td><td class="num">1</td><td class="num">4</td><td class="num">4</td><td class="num">2</td></tr>
            <tr><td class="mono">4-3-3</td><td class="num">1</td><td class="num">4</td><td class="num">3</td><td class="num">3</td></tr>
            <tr><td class="mono">3-5-2</td><td class="num">1</td><td class="num">3</td><td class="num">5</td><td class="num">2</td></tr>
            <tr><td class="mono">5-3-2</td><td class="num">1</td><td class="num">5</td><td class="num">3</td><td class="num">2</td></tr>
            <tr><td class="mono">4-5-1</td><td class="num">1</td><td class="num">4</td><td class="num">5</td><td class="num">1</td></tr>
          </tbody></table>
          <table><thead><tr><th>Strategy</th><th>Effect</th></tr></thead><tbody>
            <tr><td>Attacking</td><td class="mono">ATT &times;1.08 / DEF &times;0.92</td></tr>
            <tr><td>Balanced</td><td class="mono">no change</td></tr>
            <tr><td>Defensive</td><td class="mono">ATT &times;0.92 / DEF &times;1.08</td></tr>
          </tbody></table>'''),

        ("engine", "8. How Match Results Are Determined", '''
          <p>Results are not a coin flip, and not roster OVR alone &mdash; every result traces to the lineup, formation, and
          strategy you actually submitted:</p>
          <ol>
            <li>Each starter's ATT/DEF is first scaled by their Weekly Player Condition for this round (see Player Ratings above), then
            your starting XI's (condition-adjusted) ATT/DEF become one Team Attack and one Team Defense score, weighted by
            formation.</li>
            <li>Your Strategy choice shifts that balance further.</li>
            <li>The home team gets a fixed +5% Attack bonus.</li>
            <li>Attack vs. opposing Defense produces an expected-goals (xG) number for each side &mdash; a big mismatch caps
            out rather than producing an unrealistic blowout.</li>
            <li>The actual score is drawn randomly around each side's xG &mdash; the deliberate "luck" every real match has.
            A stronger team is more likely to win, never guaranteed to.</li>
          </ol>
          <p>Every match's random draw is seeded from the season's fixed seed plus that exact matchup &mdash; any result can
          be independently re-verified after the fact, and nothing is adjustable after the fact by the league office.</p>'''),

        ("tickets", "9. Ticket Sales &amp; Attendance", '''
          <p>As the home team, you set a ticket price tier. Attendance responds to price AND to your recent form and
          starting-XI Star Power:</p>
          <table><thead><tr><th>Tier</th><th>Price</th><th>Effect</th></tr></thead><tbody>
            <tr><td>Budget</td><td class="num mono">$15</td><td>Fills more seats, caps per-ticket revenue</td></tr>
            <tr><td>Standard</td><td class="num mono">$30</td><td>Neutral default</td></tr>
            <tr><td>Premium</td><td class="num mono">$50</td><td>Highest per-ticket revenue, but demand drops sharply without form/Star Power to justify it</td></tr>
          </tbody></table>
          <p>There is no universally correct price &mdash; a struggling, low-Star-Power team pricing Premium will earn LESS
          than pricing Standard or Budget. Read your own team's market every home match.</p>'''),

        ("sponsorship", "10. Sponsorship Deals &amp; Negotiation", sponsor_html),

        ("tv", "11. TV / Broadcast Revenue", f'''
          <h3>League-Wide (National) TV Deal</h3>
          <p><strong>Base:</strong> {money(tv["base_payment_per_team"])} per team.</p>
          <p><strong>Standings bonus:</strong> {tv["standings_bonus"]}</p>
          <p><strong>Star Power bonus:</strong> {tv["star_power_bonus"]}</p>
          <p><strong>Split timing:</strong> {tv["midseason_split_timing"]}</p>
          <h3>Local TV Deals</h3>
          <p>{ltv["description"]}</p>
          <p><strong>Market tiers:</strong> {ltv["market_tiers"]}</p>
          <p><strong>Star Power modifier:</strong> {ltv["star_power_modifier"]}</p>
          <p><strong>Payout timing:</strong> {ltv["payout_timing"]}</p>
          <p>{ltv["salary_cap_note"]}</p>
          <h3>Local TV Rights Negotiation</h3>
          <p>{ltv["negotiation"]}</p>
          <h3>Clause</h3>
          <p>Exactly like Sponsorship, a Local TV Deal's clause is a separate ask from its rate: push for a looser
          clause than your market tier's base clause, at Modest / Bold / Very Bold intensity, gated by your same
          Negotiating Leverage number. Ask beyond what your leverage supports and the deal walks away on the clause
          specifically &mdash; that costs you nothing on the revenue side, and you can simply not push the clause
          further. See "What the Clause Actually Means" above (Section 10) for the rank-threshold table &mdash; the
          same thresholds and the same {int(ce["penalty_pct"]*100)}% penalty apply to a Local TV Deal's clause, checked
          once at season end off your one final rank.</p>'''),

        ("trades", "12. Trades &amp; Free Agency", f'''
          <p><strong>Deadline:</strong> {tr["deadline"]}</p>
          <p><strong>Salary cap rule:</strong> {tr["salary_cap"]}</p>
          <p><strong>Cash considerations:</strong> {tr["cash_considerations"]}</p>
          <p><strong>Approval:</strong> {tr["approval"]}</p>
          <h3>Mandatory Mid-Season Trade Day</h3>
          <p>{tr["mid_season_trade_day"]}</p>'''),

        ("standings", "13. Standings", '''
          <p>Win = 3 points, draw = 1 point, loss = 0 points. Ties broken first by goal difference, then total goals scored.</p>'''),

        ("playoffs", "14. Playoff Qualification", f'''
          <p>{po["format"]}</p>
          <table><thead><tr><th>Stage</th><th class="num">Bonus</th></tr></thead><tbody>
            <tr><td>Finish in the top {config["playoff_teams"]} of the final standings</td><td class="num">{money(qualification_bonus)}</td></tr>
          </tbody></table>
          <p>{po["bonus_notes"]}</p>'''),

        ("glossary", "15. Glossary", '''
          <table><thead><tr><th>Term</th><th>Meaning</th></tr></thead><tbody>
            <tr><td class="mono">OVR</td><td>Overall rating &mdash; a quick-reference blend of ATT/DEF/PAC/PHY</td></tr>
            <tr><td class="mono">ATT / DEF / PAC / PHY</td><td>Attack / Defense / Pace / Physical &mdash; the four core skill ratings</td></tr>
            <tr><td>Star Power</td><td>Marketability, independent of skill &mdash; drives sponsorship and attendance</td></tr>
            <tr><td class="mono">xG</td><td>Expected goals &mdash; the engine's estimate before the random draw decides the actual score</td></tr>
            <tr><td>Salary cap</td><td>The hard ceiling on total roster salary a team may carry</td></tr>
            <tr><td>Gate revenue</td><td>Ticket sales revenue from a home match</td></tr>
            <tr><td>Free agent</td><td>An undrafted player available for in-season signing</td></tr>
          </tbody></table>'''),
    ]
    if calendar_html:
        sections.append(("calendar", "16. Season Calendar", calendar_html))

    nav_html = "".join(f'<a href="#{sid}">{title.replace("&amp;","&")}</a>' for sid, title, _ in sections)
    body_html = "".join(f'<section id="{sid}"><h2>{title}</h2>{content}</section>' for sid, title, content in sections)

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{config["league_name"]} Rulebook</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;700;800&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{{
  --paper:#eef2ea; --ink:#16201a; --muted:#5b6b5e; --line:#d6decd;
  --accent:#b8811f; --accent-ink:#3a2a08; --pitch:#2f5233; --pitch-ink:#eef2ea;
  --navy:#223a5e; --navy-ink:#eef2ea; --surface:#f7f9f4;
  --shadow: 0 1px 2px rgba(22,32,26,.06), 0 4px 14px rgba(22,32,26,.05);
}}
@media (prefers-color-scheme: dark){{
  :root:not([data-theme="light"]){{
    --paper:#111611; --ink:#e7ece1; --muted:#93a091; --line:#2a352a;
    --accent:#d9a44a; --accent-ink:#1c1404; --pitch:#4c7a52; --pitch-ink:#0d130e;
    --navy:#4a6693; --navy-ink:#0d130e; --surface:#171d17;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 4px 18px rgba(0,0,0,.35);
  }}
}}
:root[data-theme="dark"]{{
    --paper:#111611; --ink:#e7ece1; --muted:#93a091; --line:#2a352a;
    --accent:#d9a44a; --accent-ink:#1c1404; --pitch:#4c7a52; --pitch-ink:#0d130e;
    --navy:#4a6693; --navy-ink:#0d130e; --surface:#171d17;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 4px 18px rgba(0,0,0,.35);
}}
*{{box-sizing:border-box;}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Source Serif 4",Georgia,serif;line-height:1.6;}}
.mono{{font-family:"IBM Plex Mono",ui-monospace,monospace;}}
h1,h2,h3{{font-family:"Big Shoulders Display",sans-serif;text-transform:uppercase;letter-spacing:.02em;text-wrap:balance;}}
.num{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums;text-align:right;}}

.masthead{{background:var(--pitch);color:var(--pitch-ink);padding:34px clamp(16px,4vw,48px);}}
.masthead-inner{{max-width:1100px;margin:0 auto;}}
.masthead h1{{font-size:clamp(30px,4.5vw,44px);font-weight:800;margin:0 0 6px;}}
.masthead p{{font-family:"IBM Plex Mono",monospace;font-size:13px;opacity:.85;margin:0;letter-spacing:.03em;}}

.layout{{max-width:1100px;margin:0 auto;display:grid;grid-template-columns:220px 1fr;gap:40px;padding:36px clamp(16px,4vw,48px) 100px;align-items:start;}}
@media (max-width:820px){{.layout{{grid-template-columns:1fr;}}}}
nav{{position:sticky;top:20px;display:flex;flex-direction:column;gap:2px;border-right:1px solid var(--line);padding-right:16px;}}
@media (max-width:820px){{nav{{position:static;border-right:none;border-bottom:1px solid var(--line);padding-right:0;padding-bottom:16px;flex-direction:row;flex-wrap:wrap;}}}}
nav a{{color:var(--muted);text-decoration:none;font-family:"IBM Plex Mono",monospace;font-size:12px;padding:5px 0;}}
nav a:hover{{color:var(--accent);}}

section{{margin-bottom:44px;scroll-margin-top:20px;}}
section h2{{font-size:24px;border-bottom:2px solid var(--ink);padding-bottom:6px;margin:0 0 14px;}}
section h3{{font-size:16px;color:var(--muted);margin:20px 0 8px;}}
section p{{margin:0 0 12px;max-width:70ch;}}
section ul, section ol{{max-width:70ch;padding-left:22px;margin:0 0 12px;}}
section li{{margin-bottom:6px;}}
.callout{{background:var(--surface);border-left:3px solid var(--accent);padding:10px 16px;border-radius:2px;}}

.table-scroll{{overflow-x:auto;}}
table{{width:100%;border-collapse:collapse;font-size:14px;background:var(--surface);border:1px solid var(--line);border-radius:3px;box-shadow:var(--shadow);margin-bottom:16px;}}
thead th{{background:var(--navy);color:var(--navy-ink);text-align:left;padding:9px 10px;font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.05em;text-transform:uppercase;}}
thead th.num{{text-align:right;}}
tbody td{{padding:8px 10px;border-top:1px solid var(--line);vertical-align:top;}}

footer{{max-width:1100px;margin:0 auto;padding:0 clamp(16px,4vw,48px) 50px;color:var(--muted);font-size:12.5px;font-family:"IBM Plex Mono",monospace;}}
{NAV_CSS}
</style>
</head>
<body>
{render_nav("rulebook")}
<div class="masthead">
  <div class="masthead-inner">
    <h1>{config["league_name"]} &mdash; Rulebook</h1>
    <p>{config["season_label"]} &middot; every rule, every formula, every point your grade is built from</p>
  </div>
</div>
<div class="layout">
  <nav>{nav_html}</nav>
  <main>{body_html}</main>
</div>
<footer>Numbers on this page are generated directly from data/league_config.json and data/deals.json &mdash; never hand-typed twice.</footer>
</body>
</html>'''


if __name__ == "__main__":
    config = load_json("league_config.json")
    deals = load_json("deals.json")
    cal_path = os.path.join(BASE, "data", "season_calendar.json")
    calendar = load_json("season_calendar.json") if os.path.exists(cal_path) else None
    html = render(config, deals, calendar)
    out_path = os.path.join(BASE, "rulebook", "index.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Rendered -> {out_path}")
