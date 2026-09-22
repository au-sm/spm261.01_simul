"""
Renders the printable Sponsorship Negotiation packet (Word docs) --
same 3-document structure as before (Team_Owner_Brief.docx,
Sponsor_Rep_Briefs.docx, Rotation_Schedule_Nteams.docx), but as a real,
rerunnable script instead of a lost one-off build. Content (brand
blurbs, clause-flexibility phrasing, ceilings) is reconstructed
verbatim from the original docx files plus deals.json, so nothing here
is newly invented -- see the BRAND_BLURBS dict below, transcribed
directly from the original Sponsor_Rep_Briefs.docx.

  Team_Owner_Brief.docx        -- how to play the owner role (generic,
                                   does not depend on team count)
  Sponsor_Rep_Briefs.docx      -- one card per BRAND (not per team --
                                   unlike TV, the roster of brands does
                                   not depend on team count either).
                                   Clause thresholds at the bottom DO
                                   pull live from deals.json, so they
                                   stay correct if team count changes.
  Rotation_Schedule_Nteams.docx -- the ONE genuinely team-count-
                                   dependent piece: the 6-round pairing
                                   schedule from
                                   generate_negotiation_rotation.py.

Private-ceiling convention: +30% above base_revenue, verified against
every brand card in the original Sponsor_Rep_Briefs.docx (all 26 use
exactly base x 1.3) -- same convention render_tv_negotiation_docx.py
uses for Local TV Deal ceilings.

Usage:
    python3 engine/render_sponsorship_negotiation_docx.py --n-teams 18
"""
import argparse
import json
import os
import sys

from docx import Document

sys.path.insert(0, os.path.dirname(__file__))
from generate_negotiation_rotation import build_rotation

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CEILING_MULTIPLIER = 1.3

# Transcribed verbatim from the original Sponsor_Rep_Briefs.docx
BRAND_BLURBS = {
    "Nike": "The biggest name in the market -- everyone wants this jersey.",
    "Adidas": "Nike's closest rival -- nearly as prestigious.",
    "Under Armour": "Aggressive challenger brand, hungry for exposure.",
    "Puma": "Solid mid-market kit deal.",
    "New Balance": "Reliable, unglamorous, always available.",
    "Red Bull": "Wants an exciting, attacking team on the pitch -- flash sells cans.",
    "Gatorade": "The default performance-drink partner for a serious club.",
    "Coca-Cola": "Massive, safe, universally recognized.",
    "Pepsi": "Coca-Cola's rival -- comparable deal, slightly less reach.",
    "Monster Energy": "Loud, cheap, easy to get.",
    "Visa": "The prestige payments partner.",
    "Mastercard": "Visa's closest competitor for the same prestige.",
    "American Express": "Wants a winning, upscale image attached to its card.",
    "PayPal": "Easy, low-friction, always has room.",
    "Emirates": "The gold standard of sports sponsorship -- wants a true marquee club.",
    "Qatar Airways": "Right behind Emirates in prestige and price.",
    "Delta": "Solid national carrier, dependable terms.",
    "American Airlines": "Widely available, modest terms.",
    "BMW": "Premium marque, wants a premium club to match.",
    "Toyota": "Dependable, high-volume, broad reach.",
    "Ford": "Solid mainstream automotive deal.",
    "Hyundai": "Value-focused, easy to sign.",
    "Samsung": "Wants marketability and star wattage over wins.",
    "Sony": "Comparable tech-sector prestige deal.",
    "AT&T": "Telecom partner, steady terms.",
    "Verizon": "AT&T's rival, comparable deal.",
}

CLAUSE_PROGRESSION = ["strict", "standard", "loose", "none"]


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def money(n):
    return f"${n:,.0f}"


def clause_flexibility_text(base_clause):
    idx = CLAUSE_PROGRESSION.index(base_clause)
    if base_clause == "loose":
        return 'Loosen to "none" for a solid pitch. That is the most flexibility this brand has left on the clause.'
    one_step = CLAUSE_PROGRESSION[idx + 1]
    two_step = CLAUSE_PROGRESSION[idx + 2]
    return f'Loosen to "{one_step}" for a solid pitch; "{two_step}" only for an exceptional one.'


def render_owner_brief(out_dir):
    doc = Document()
    doc.add_heading("Sponsorship Negotiation — Team Owner Brief", level=0)
    doc.add_paragraph(
        "CONFIDENTIAL — do not show this page to whoever is playing the sponsor representative."
    )

    doc.add_heading("Your Role", level=1)
    doc.add_paragraph(
        "You are the owner/GM of your club, negotiating one sponsorship category "
        "today (your instructor will tell you which). You will sit across from a "
        "classmate playing the sponsor's representative. They do NOT know your "
        "team's real numbers unless you choose to tell them -- and they may not be "
        "telling you the truth about theirs, either."
    )

    doc.add_heading("Step 1 — Calculate Your Own Leverage (private)", level=1)
    doc.add_paragraph(
        "Before you sit down, work out your own Negotiating Leverage. This is real "
        "information about YOUR team that the sponsor rep does not automatically "
        "have access to:"
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
        "Example: avg Star Power 75, no season data yet → leverage = (75−50)×2 = 50."
    )
    doc.add_paragraph(
        "This number is YOURS to reveal, exaggerate, downplay, or keep to yourself. "
        "A real negotiator rarely leads with their weakest card face-up."
    )

    doc.add_heading("Step 2 — Two Separate Decisions", level=1)
    for line in [
        "Revenue: you can always take Base (the listed number, guaranteed, zero "
        "risk), or Negotiate -- which lands you anywhere from -10% to +10% of base, "
        "depending on how compelling your case is. Negotiating is NOT risk-free: a "
        "weak, unconvincing pitch can land you BELOW base. If your leverage is low, "
        "taking Base may be the smarter play.",
        "Clause: a separate ask, only worth making if you want. This one CAN fail "
        "outright (the sponsor holds firm and nothing changes) if you push harder "
        "than your leverage supports -- but failing here never affects your revenue.",
        "These are independent -- you are not trading one for the other. You could "
        "negotiate hard on revenue and not touch the clause at all, or vice versa, "
        "or both.",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    doc.add_heading("Step 3 — Know Your Walk-Away", level=1)
    doc.add_paragraph(
        "Revenue negotiation always resolves -- there is no walk-away on that side, "
        "worst case you land at -10%. The CLAUSE ask is what can fail outright. "
        "Either way, you are not stuck with a bad outcome forever: if you genuinely "
        "dislike where things landed, you can end the meeting and try a different "
        "brand in the same category (ask your instructor which brands still have "
        "open slots). You CANNOT skip the category entirely -- every team must end "
        "the draft with one signed brand per category."
    )

    doc.add_heading("Tactics Worth Trying", level=1)
    for line in [
        "Open ambitious, not absurd. A real opening ask is usually well above what "
        "you'd actually accept.",
        'Ask direct questions: "What\'s the most flexibility you have on revenue?" '
        '"Is that clause negotiable?"',
        "Don't reveal your exact leverage number early -- let your case (recent "
        "form, star players, brand fit) do the persuading first.",
        "Listen for hesitation or hedging -- it usually means there's more room "
        "than they're admitting.",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    doc.add_heading("Step 4 — Record & Reflect", level=1)
    doc.add_paragraph(
        "Use the separate Deal Memo Template (Deal_Memo_Template.docx) to record "
        "all 6 of your negotiations as you go, and to write your one graded "
        "reflection at the end. Hand that sheet to your instructor when the "
        "exercise is done."
    )

    out_path = os.path.join(out_dir, "Team_Owner_Brief.docx")
    doc.save(out_path)
    print(f"Saved -> {out_path}")


def render_rep_briefs(out_dir, deals, n_teams):
    ce = deals["clause_enforcement"]
    rt = ce["rank_threshold_by_clause"]

    doc = Document()
    doc.add_heading("Sponsorship Negotiation — Sponsor Representative Brief", level=0)
    doc.add_paragraph(
        "CONFIDENTIAL — do not show this page to whoever is playing the team owner."
    )
    doc.add_paragraph(
        "Find the ONE card below for the brand your instructor assigned you. Read "
        "only that card -- the numbers on other brands' cards are not yours to "
        "know or reveal."
    )

    doc.add_heading("How to Play This Role", level=1)
    for line in [
        "You represent this brand's sports marketing division. Your job is to "
        "sign a good deal for the brand -- not to give away the store, but not to "
        "lose the deal over stubbornness either.",
        "Your card lists a PUBLIC starting offer and a PRIVATE ceiling you're "
        "authorized to reach. Never open with your ceiling -- negotiate up to it "
        "gradually, and only if the team owner makes a real case for it (strong "
        "roster quality, good standing, a persuasive pitch).",
        "If they don't make a case -- they just ask for more without justifying "
        "it -- you're allowed to hold firm or offer only a token move.",
        "You may also propose the trade yourself: \"I can move on revenue if "
        "you'll accept the stricter clause.\"",
        "If talks fully break down, you're allowed to end the meeting -- they can "
        "come back for a second attempt, or try a different brand in this "
        "category.",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    for cat in deals["sponsorship_categories"]:
        doc.add_heading(cat["category"], level=1)
        for b in cat["brands"]:
            base = b["base_revenue"]
            ceiling = round(base * CEILING_MULTIPLIER)
            doc.add_heading(b["name"], level=2)
            blurb = BRAND_BLURBS.get(b["name"], "")
            if blurb:
                doc.add_paragraph(blurb)
            table = doc.add_table(rows=0, cols=2)
            table.style = "Light Grid Accent 1"
            rows = [
                ("Public opening offer", f"{money(base)} / season, {b['base_clause']} clause"),
                ("Your private ceiling (revenue)", f"{money(ceiling)} -- only for a genuinely strong pitch"),
                ("Clause flexibility", clause_flexibility_text(b["base_clause"])),
                ("What this brand actually cares about", blurb),
                ("League-wide slots available", f"{b['qty']} teams total may sign this brand"),
            ]
            for label, value in rows:
                row = table.add_row().cells
                row[0].text = label
                row[1].text = value

    doc.add_heading("What the Clause Actually Means", level=1)
    doc.add_paragraph(
        f"Checked ONCE, at the end of the season (the final round): if your "
        f"team's FINAL rank misses that specific deal's threshold, that deal "
        f"claws back a flat {int(ce['penalty_pct']*100)}% of its revenue."
    )
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text = "Clause"
    hdr[1].text = "Required final rank"
    hdr[2].text = "Penalty if missed"
    for label, key in [("Strict", "strict"), ("Standard", "standard"), ("Loose", "loose")]:
        row = table.add_row().cells
        row[0].text = label
        row[1].text = f"Top {rt[key]}"
        row[2].text = f"{int(ce['penalty_pct']*100)}%"
    row = table.add_row().cells
    row[0].text = "None"
    row[1].text = "No requirement"
    row[2].text = "0%, ever"

    out_path = os.path.join(out_dir, f"Sponsor_Rep_Briefs_{n_teams}teams.docx")
    doc.save(out_path)
    print(f"Saved -> {out_path}")


def render_rotation(out_dir, n_teams, categories, team_names):
    rotation = build_rotation(n_teams, categories, team_names)

    doc = Document()
    doc.add_heading(f"Sponsorship Negotiation — Rotation Schedule ({n_teams} teams)", level=0)
    doc.add_paragraph(
        "Every pair runs two negotiations back to back, in the order listed, using "
        "TWO DIFFERENT BRANDS -- never the same brand twice in one meeting. That is "
        "deliberate: if both directions used the same brand, whoever plays owner "
        "second would already know the sponsor's private ceiling from watching the "
        "first negotiation while playing its rep. Different brands keep both "
        "negotiations honest, independent tests. No student repeats a partner "
        "across all 6 rounds."
    )

    for r in rotation:
        doc.add_heading(f"Round {r['round']} — {r['category']}", level=1)
        table = doc.add_table(rows=1, cols=4)
        table.style = "Light Grid Accent 1"
        hdr = table.rows[0].cells
        hdr[0].text = "Meeting"
        hdr[1].text = "Plays Owner"
        hdr[2].text = "Plays Sponsor Rep"
        hdr[3].text = "Brand"
        for p in r["pairs"]:
            row = table.add_row().cells
            row[0].text = f"{p['team_a']} & {p['team_b']} — Negotiation 1"
            row[1].text = p["team_a"]
            row[2].text = p["team_b"]
            row[3].text = p["brand_a_owner"]

            row = table.add_row().cells
            row[0].text = f"{p['team_a']} & {p['team_b']} — Negotiation 2 (swap, different brand)"
            row[1].text = p["team_b"]
            row[2].text = p["team_a"]
            row[3].text = p["brand_b_owner"]
        if r["bye"]:
            doc.add_paragraph(
                f"BYE (instructor fills in): {', '.join(r['bye'])}"
            )

    out_path = os.path.join(out_dir, f"Rotation_Schedule_{n_teams}teams.docx")
    doc.save(out_path)
    print(f"Saved -> {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-teams", type=int, required=True)
    args = ap.parse_args()

    config = load_json("league_config.json")
    deals = load_json("deals.json")
    # 'Owner Name (Team N)' so students find themselves by their real name,
    # not just the placeholder team name -- falls back to the placeholder
    # alone if an owner isn't filled in yet.
    team_names = (
        [f"{t['owner']} ({t['name']})" if t.get("owner") else t["name"] for t in config["teams"]]
        if len(config["teams"]) == args.n_teams else None
    )

    out_dir = os.path.join(BASE, "negotiation-roleplay")
    os.makedirs(out_dir, exist_ok=True)

    render_owner_brief(out_dir)
    render_rep_briefs(out_dir, deals, args.n_teams)
    render_rotation(out_dir, args.n_teams, deals["sponsorship_categories"], team_names)
