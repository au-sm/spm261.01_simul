"""
Renders the printable Local TV Rights Negotiation packet (Word docs),
same visual style and 4-document structure as the existing Sponsorship
Negotiation packet in negotiation-roleplay/ (Team_Owner_Brief.docx,
Sponsor_Rep_Briefs.docx, Rotation_Schedule_20teams.docx,
Deal_Memo_Template.docx):

  TV_Team_Owner_Brief.docx      -- how to play the owner role
  TV_Network_Rep_Briefs.docx    -- one card per TEAM (not per brand --
                                    TV has no brand catalog, just each
                                    team's own market-tier deal), pulled
                                    live from data/local_tv_deals.json
                                    so the numbers can never drift from
                                    what the engine will actually pay
  TV_Negotiation_Rotation_20teams.docx -- the pairing schedule (one
                                    round only -- a team has ONE Local
                                    TV deal, not 6 sponsorship categories)
  TV_Deal_Memo.docx             -- one row per team to record the
                                    negotiated rate + commission owed

Private-ceiling convention: +30% above the market-tier base, same
multiplier the Sponsorship Rep Briefs use on every brand's base
revenue (verified against Sponsor_Rep_Briefs.docx -- every card there
lists its ceiling as exactly base x 1.3). This is a LIVE-negotiation
narrative ceiling only, distinct from the mechanical +/-10% leverage
cap that engine/negotiation.py applies in ALGORITHMIC mode when no
live rep is available -- see the Team Owner Brief for that distinction
spelled out.

Usage:
    python3 engine/render_tv_negotiation_docx.py --n-teams 20
"""
import argparse
import json
import os
import sys

from docx import Document

sys.path.insert(0, os.path.dirname(__file__))
from generate_tv_negotiation_rotation import build_rotation

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CEILING_MULTIPLIER = 1.3  # matches Sponsor_Rep_Briefs.docx's convention exactly


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def money(n):
    return f"${n:,.0f}"


def render_owner_brief(out_dir):
    doc = Document()
    doc.add_heading("Local TV Rights Negotiation — Team Owner Brief", level=0)
    doc.add_paragraph(
        "CONFIDENTIAL — do not show this page to whoever is playing the network rep."
    )

    doc.add_heading("Your Role", level=1)
    doc.add_paragraph(
        "You are the owner/GM of your club, negotiating your Local TV Deal rate. "
        "You will sit across from a classmate playing a broadcast network's "
        "representative. Your market tier and market-tier base rate were assigned "
        "randomly right after Draft Day (see the league dashboard) — that base is "
        "public information, but how far above it you can actually push is not."
    )

    doc.add_heading("Step 1 — Calculate Your Own Leverage (private)", level=1)
    doc.add_paragraph(
        "Before you sit down, work out your own Negotiating Leverage — the exact "
        "same formula used for Sponsorship:"
    )
    for line in [
        "Find your roster's average Star Power (all players, or your usual starting XI).",
        "leverage = (avg Star Power − 50) × 2, then add a standings bonus once the "
        "season has started: +15 if you're in the top third of the table, +7 if "
        "you're mid-table, +0 if you're in the bottom third.",
        "Clamp the result between 0 and 100.",
    ]:
        doc.add_paragraph(line, style="List Bullet")
    doc.add_paragraph(
        "This number is YOURS to reveal, exaggerate, downplay, or keep to yourself."
    )

    doc.add_heading("Step 2 — One Decision, One Axis", level=1)
    doc.add_paragraph(
        "Unlike Sponsorship, there is no clause to negotiate here — just one number, "
        "your season TV rate:"
    )
    doc.add_paragraph(
        "Take Base (your market-tier rate exactly, guaranteed, zero risk), or "
        "Negotiate for more. A weak, unconvincing pitch can land you below base — "
        "if your leverage is low, taking Base may be the smarter play.",
        style="List Bullet",
    )

    doc.add_heading("What Actually Gets Paid, and When", level=1)
    doc.add_paragraph(
        "This negotiation only sets your RATE. The money itself is still paid at "
        "the league's Round 9 TV Revenue Day, same as before — and the Star Power "
        "modifier (+15% if your starting XI is top-3 league-wide at that time) is "
        "still applied on top of whatever rate you lock in today. Negotiating a "
        "strong rate now is a bet on where your team will actually be at Round 9."
    )
    doc.add_paragraph(
        "The one exception: if your negotiated rate lands ABOVE base, that overage "
        "is credited immediately to whichever team played your network rep — that "
        "commission does not wait for Round 9."
    )

    doc.add_heading("Tactics Worth Trying", level=1)
    for line in [
        "Open ambitious, not absurd.",
        "Make your case with real evidence: your roster's Star Power, your recent "
        "form, your market size.",
        "Don't reveal your exact leverage number early — let your pitch do the work.",
        "Listen for hesitation — it usually means there's more room than they're "
        "admitting.",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    doc.add_heading("Step 3 — Record & Reflect", level=1)
    doc.add_paragraph(
        "Use the separate TV Deal Memo (TV_Deal_Memo.docx) to record your "
        "negotiated rate and to write your one graded reflection. Hand it to your "
        "instructor when the exercise is done."
    )

    out_path = os.path.join(out_dir, "TV_Team_Owner_Brief.docx")
    doc.save(out_path)
    print(f"Saved -> {out_path}")


def render_network_rep_briefs(out_dir, assignments, display_names, n_teams):
    """display_names: dict team_id -> 'Owner Name (Team N)' label, so
    students find their assigned card by real name, not the placeholder
    team name baked into local_tv_deals.json."""
    doc = Document()
    doc.add_heading("Local TV Rights Negotiation — Network Representative Brief", level=0)
    doc.add_paragraph(
        "CONFIDENTIAL — do not show this page to whoever is playing the team owner."
    )
    doc.add_paragraph(
        "Find the ONE card below for the team your instructor assigned you to "
        "negotiate with. Read only that card — the numbers on other teams' cards "
        "are not yours to know or reveal."
    )

    doc.add_heading("How to Play This Role", level=1)
    for line in [
        "You represent a regional broadcast network deciding how much to pay for "
        "this club's local media rights.",
        "Your card lists the team's PUBLIC market-tier base rate and a PRIVATE "
        "ceiling you're authorized to reach. Never open with your ceiling — "
        "negotiate up to it gradually, and only if the owner makes a real case for "
        "it (strong roster Star Power, good standing, a persuasive pitch).",
        "If they don't make a case — they just ask for more without justifying it "
        "— you're allowed to hold firm or offer only a token move.",
        "If talks fully break down, you're allowed to end the meeting — they can "
        "come back for a second attempt.",
        "If the final rate lands above base, your OWN team earns that overage as "
        "a commission, credited right away — playing this role well pays off for "
        "your own team too.",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    for a in assignments:
        base = a["base_revenue"]
        ceiling = round(base * CEILING_MULTIPLIER)
        label = display_names.get(a["team_id"], a["team_name"]) if display_names else a["team_name"]
        doc.add_heading(label, level=1)
        table = doc.add_table(rows=0, cols=2)
        table.style = "Light Grid Accent 1"
        rows = [
            ("Market tier", a["market_tier"]),
            ("Public market-tier base rate", f"{money(base)} / season"),
            ("Your private ceiling", f"{money(ceiling)} — only for a genuinely strong pitch"),
            ("What this market actually cares about",
             "A big-market broadcaster with deep pockets, chasing star wattage." if a["market_tier"] == "Major Market"
             else "A mid-size regional network, price-sensitive but willing to pay for a winner." if a["market_tier"] == "Mid Market"
             else "A small local affiliate on a tight budget — a hard sell without a real case."),
        ]
        for label, value in rows:
            row = table.add_row().cells
            row[0].text = label
            row[1].text = value

    out_path = os.path.join(out_dir, f"TV_Network_Rep_Briefs_{n_teams}teams.docx")
    doc.save(out_path)
    print(f"Saved -> {out_path}")


def render_rotation(out_dir, n_teams, assignments, team_names):
    market_tiers_by_team = {a["team_id"]: a["market_tier"] for a in assignments}
    rotation = build_rotation(n_teams, market_tiers_by_team, team_names)

    doc = Document()
    doc.add_heading(f"Local TV Rights Negotiation — Rotation Schedule ({n_teams} teams)", level=0)
    doc.add_paragraph(
        "Held right after Draft Day, alongside the Local TV Deal market-tier "
        "assignment. Every pair runs two negotiations back to back, swapping who "
        "plays owner and who plays network rep — each team negotiates its OWN "
        "market-tier deal both times (there is no brand to swap, unlike "
        "Sponsorship). No student repeats a partner across this exercise; an odd "
        "team count leaves one bye, filled by the instructor."
    )

    table = doc.add_table(rows=1, cols=4)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text = "Meeting"
    hdr[1].text = "Plays Owner"
    hdr[2].text = "Plays Network Rep"
    hdr[3].text = "Deal on the Table"
    for i, p in enumerate(rotation["pairs"], start=1):
        row = table.add_row().cells
        row[0].text = f"Meeting {i} — Negotiation 1"
        row[1].text = p["team_a"]
        row[2].text = p["team_b"]
        row[3].text = f"{p['team_a']}'s {p['team_a_market_tier']} deal"

        row = table.add_row().cells
        row[0].text = f"Meeting {i} — Negotiation 2 (swap)"
        row[1].text = p["team_b"]
        row[2].text = p["team_a"]
        row[3].text = f"{p['team_b']}'s {p['team_b_market_tier']} deal"

    if rotation["bye"]:
        doc.add_heading("Bye", level=1)
        doc.add_paragraph(
            f"{', '.join(rotation['bye'])} draws the bye this round (odd team "
            f"count) — the instructor fills in as network rep so this team still "
            f"completes its negotiation, same convention as the Sponsorship "
            f"Negotiation rotation's bye."
        )

    out_path = os.path.join(out_dir, f"TV_Negotiation_Rotation_{n_teams}teams.docx")
    doc.save(out_path)
    print(f"Saved -> {out_path}")


def render_deal_memo(out_dir):
    doc = Document()
    doc.add_heading("Local TV Deal Memo", level=0)
    doc.add_paragraph(
        "Fill this in immediately after your negotiation. Hand it to your "
        "instructor at the end of the exercise — it's how your negotiated rate "
        "gets entered into the league via engine/resolve_local_tv_pick.py, "
        "including any commission owed to whoever played network rep for you."
    )
    doc.add_paragraph(
        "Commission Owed: only fill this in if your Final Rate is ABOVE your "
        "market-tier base (e.g., Mid Market base $700,000, you negotiated "
        "$770,000 -> commission owed = $70,000). That amount goes to the team "
        "listed in \"Network Rep Played By,\" not to you, and is credited "
        "immediately — not at the Round 9 split. Leave at $0 if you took Base or "
        "negotiated at or below base."
    )
    doc.add_paragraph(
        "If your negotiation fell through (no agreement reached): write \"NO "
        "DEAL\" in the Final Rate column instead. Your deal gets resolved "
        "afterward through the algorithmic fallback — see your instructor."
    )

    name_table = doc.add_table(rows=1, cols=2)
    name_table.style = "Light Grid Accent 1"
    cells = name_table.rows[0].cells
    cells[0].text = "Team Name"
    cells[1].text = ""

    doc.add_paragraph("")
    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text = "Market Tier"
    hdr[1].text = "Market-Tier Base"
    hdr[2].text = "Final Negotiated Rate"
    hdr[3].text = "Network Rep Played By (Team)"
    hdr[4].text = "Commission Owed"
    row = table.add_row().cells
    row[0].text = ""
    row[1].text = "$"
    row[2].text = "$"
    row[3].text = ""
    row[4].text = "$0 (only if rate > base)"

    doc.add_heading("Reflection (graded)", level=1)
    doc.add_paragraph(
        "Answer in 2-4 sentences, using the same Decision Rationale Rubric as "
        "your weekly lineup submissions: what did you learn about your own "
        "leverage from this negotiation, and would you play it differently at "
        "Round 9 once your actual standing and Star Power are known?"
    )

    out_path = os.path.join(out_dir, "TV_Deal_Memo.docx")
    doc.save(out_path)
    print(f"Saved -> {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-teams", type=int, required=True)
    args = ap.parse_args()

    config = load_json("league_config.json")
    has_real_roster = len(config["teams"]) == args.n_teams
    # 'Owner Name (Team N)' so students find their own card/pairing by their
    # real name, not just the placeholder team name -- falls back to the
    # placeholder alone if an owner isn't filled in yet.
    team_names = (
        [f"{t['owner']} ({t['name']})" if t.get("owner") else t["name"] for t in config["teams"]]
        if has_real_roster else None
    )
    display_names_by_id = (
        {t["team_id"]: (f"{t['owner']} ({t['name']})" if t.get("owner") else t["name"]) for t in config["teams"]}
        if has_real_roster else None
    )

    ltv_path = os.path.join(BASE, "data", "local_tv_deals.json")
    if not os.path.exists(ltv_path):
        print("ERROR: data/local_tv_deals.json not found -- run generate_local_tv_deals.py first.")
        sys.exit(1)
    ltv = load_json("local_tv_deals.json")
    assignments = ltv["assignments"]

    out_dir = os.path.join(BASE, "negotiation-roleplay")
    os.makedirs(out_dir, exist_ok=True)

    render_owner_brief(out_dir)
    render_network_rep_briefs(out_dir, assignments, display_names_by_id, args.n_teams)
    render_rotation(out_dir, args.n_teams, assignments, team_names)
    render_deal_memo(out_dir)
