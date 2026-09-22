"""
Renders sponsorship-site/index.html -- the standalone Sponsorship
Marketplace, separate from the main league dashboard.

Reads data/deals.json (sponsorship_categories), data/team_finances.json
(who owns what), and data/league_config.json (team names, required
category count) -- always current, never hand-typed. Also ships a
client-side negotiation simulator that mirrors engine/negotiation.py
exactly, so students can rehearse an ask before their live draft turn
actually locks it in.

Run after every resolve_sponsorship_pick.py call, then republish.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from site_nav import NAV_CSS, render_nav

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def money(n):
    return f"${n:,}"


def render(config, deals, finances):
    team_map = {t["team_id"]: t["name"] for t in config["teams"]}
    n_required = config.get("sponsorship_categories_required", len(deals["sponsorship_categories"]))
    ce = deals["clause_enforcement"]
    rt = ce["rank_threshold_by_clause"]

    def slots_taken(name):
        return sum(
            1 for t in finances["teams"].values()
            for s in t.get("sponsors_owned", [])
            if s["sponsor"] == name and s["outcome"] != "walk_away"
        )

    def owners_of(name):
        return [
            team_map[int(tid)] for tid, t in finances["teams"].items()
            for s in t.get("sponsors_owned", [])
            if s["sponsor"] == name and s["outcome"] != "walk_away"
        ]

    category_sections = []
    all_brands_for_sim = []
    for cat in deals["sponsorship_categories"]:
        cards = []
        for b in cat["brands"]:
            taken = slots_taken(b["name"])
            remaining = b["qty"] - taken
            owners = owners_of(b["name"])
            owners_html = ", ".join(owners) if owners else '<span class="none">no signings yet</span>'
            sold_out = remaining <= 0
            cards.append(f'''
            <article class="sponsor-card{' sold-out' if sold_out else ''}">
              <header><h3>{b["name"]}</h3><span class="slots">{max(0,remaining)}/{b["qty"]} open</span></header>
              <p class="flavor">{b["flavor"]}</p>
              <div class="terms">
                <span><b>Revenue</b> {money(b["base_revenue"])}/season</span>
                <span><b>Clause</b> {b["base_clause"]}</span>
              </div>
              <p class="owners"><b>Signed by:</b> {owners_html}</p>
            </article>''')
            all_brands_for_sim.append({**b, "category": cat["category"]})
        category_sections.append(f'''
        <div class="category-block">
          <h3 class="category-title">{cat["category"]}</h3>
          <div class="sponsor-grid">{"".join(cards)}</div>
        </div>''')
    categories_html = "".join(category_sections)

    team_rows = []
    for t in config["teams"]:
        tid = t["team_id"]
        rec = finances["teams"].get(str(tid), {})
        owned = [s for s in rec.get("sponsors_owned", []) if s["outcome"] != "walk_away"]
        filled = len({s["category"] for s in owned})
        deal_names = ", ".join(f'{s["sponsor"]} ({s["category"]})' for s in owned) or "&mdash;"
        status = "complete" if filled >= n_required else f"{filled}/{n_required}"
        team_rows.append(
            f'<tr><td>{t["name"]}</td><td class="num status-{"complete" if filled>=n_required else "pending"}">{status}</td><td>{deal_names}</td></tr>'
        )
    team_rows_html = "".join(team_rows)

    sponsor_pool_json = json.dumps(all_brands_for_sim)

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sponsorship Marketplace</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;700;800&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{{
  --paper:#eef2ea; --ink:#16201a; --muted:#5b6b5e; --line:#d6decd;
  --accent:#b8811f; --accent-ink:#3a2a08; --pitch:#2f5233; --pitch-ink:#eef2ea;
  --navy:#223a5e; --navy-ink:#eef2ea; --surface:#f7f9f4;
  --win:#2f7a4f; --loss:#b4472f; --draw:#a5791f;
  --shadow: 0 1px 2px rgba(22,32,26,.06), 0 4px 14px rgba(22,32,26,.05);
}}
@media (prefers-color-scheme: dark){{
  :root:not([data-theme="light"]){{
    --paper:#111611; --ink:#e7ece1; --muted:#93a091; --line:#2a352a;
    --accent:#d9a44a; --accent-ink:#1c1404; --pitch:#4c7a52; --pitch-ink:#0d130e;
    --navy:#4a6693; --navy-ink:#0d130e; --surface:#171d17;
    --win:#4fae76; --loss:#e07a5c; --draw:#d1a13e;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 4px 18px rgba(0,0,0,.35);
  }}
}}
:root[data-theme="dark"]{{
    --paper:#111611; --ink:#e7ece1; --muted:#93a091; --line:#2a352a;
    --accent:#d9a44a; --accent-ink:#1c1404; --pitch:#4c7a52; --pitch-ink:#0d130e;
    --navy:#4a6693; --navy-ink:#0d130e; --surface:#171d17;
    --win:#4fae76; --loss:#e07a5c; --draw:#d1a13e;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 4px 18px rgba(0,0,0,.35);
}}
*{{box-sizing:border-box;}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Source Serif 4",Georgia,serif;line-height:1.5;}}
.mono{{font-family:"IBM Plex Mono",ui-monospace,monospace;}}
h1,h2,h3{{font-family:"Big Shoulders Display",sans-serif;text-transform:uppercase;letter-spacing:.02em;text-wrap:balance;margin:0;}}
.num{{font-variant-numeric:tabular-nums;text-align:right;}}

.masthead{{background:var(--pitch);color:var(--pitch-ink);padding:28px clamp(16px,4vw,48px);}}
.masthead-inner{{max-width:1180px;margin:0 auto;}}
.masthead h1{{font-size:clamp(26px,4vw,38px);font-weight:800;}}
.masthead p{{font-family:"IBM Plex Mono",monospace;font-size:12.5px;opacity:.85;margin:6px 0 0;letter-spacing:.03em;}}

.wrap{{max-width:1180px;margin:0 auto;padding:28px clamp(16px,4vw,48px) 70px;}}
section{{margin-bottom:36px;}}
.section-head{{display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px solid var(--ink);padding-bottom:6px;margin-bottom:16px;}}
.section-head h2{{font-size:21px;}}
.section-note{{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--muted);}}

.how-it-works{{background:var(--surface);border:1px solid var(--line);border-radius:4px;box-shadow:var(--shadow);padding:18px 22px;}}
.how-it-works ul{{margin:8px 0 0;padding-left:20px;}}
.how-it-works li{{margin-bottom:6px;}}
.asks-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-top:14px;}}
.ask-chip{{background:var(--paper);border:1px solid var(--line);border-radius:3px;padding:8px 12px;font-size:13px;}}
.ask-chip b{{display:block;font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--accent);text-transform:uppercase;letter-spacing:.04em;margin-bottom:3px;}}

.category-block{{margin-bottom:26px;}}
.category-title{{font-size:15px;letter-spacing:.06em;color:var(--navy);border-bottom:1px solid var(--line);padding-bottom:6px;margin-bottom:12px;}}
.sponsor-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px;}}
.sponsor-card{{background:var(--surface);border:1px solid var(--line);border-radius:4px;box-shadow:var(--shadow);padding:14px 16px;border-top:4px solid var(--accent);}}
.sponsor-card.sold-out{{border-top-color:var(--loss);opacity:.75;}}
.sponsor-card header{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px;}}
.sponsor-card h3{{font-size:15px;}}
.slots{{font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--muted);white-space:nowrap;}}
.sold-out .slots{{color:var(--loss);}}
.flavor{{font-size:12.5px;color:var(--muted);margin:0 0 8px;font-style:italic;}}
.terms{{display:flex;flex-direction:column;gap:2px;font-family:"IBM Plex Mono",monospace;font-size:12px;margin-bottom:8px;}}
.terms b{{color:var(--muted);font-weight:600;margin-right:4px;}}
.owners{{font-size:12px;margin:0;}}
.owners .none{{color:var(--muted);font-style:italic;}}

table{{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--surface);border:1px solid var(--line);border-radius:3px;box-shadow:var(--shadow);}}
thead th{{background:var(--navy);color:var(--navy-ink);text-align:left;padding:9px 10px;font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;}}
thead th.num{{text-align:right;}}
tbody td{{padding:7px 10px;border-top:1px solid var(--line);}}
.status-complete{{color:var(--win);font-weight:600;}}
.status-pending{{color:var(--draw);font-weight:600;}}

.sim{{background:var(--surface);border:1px solid var(--line);border-radius:4px;box-shadow:var(--shadow);padding:20px 22px;}}
.sim-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;}}
@media (max-width:640px){{.sim-grid{{grid-template-columns:1fr;}}}}
.field label{{display:block;font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin-bottom:5px;}}
.field select, .field input[type=range]{{width:100%;}}
select{{font-family:"Source Serif 4",serif;font-size:14px;background:var(--paper);color:var(--ink);border:1px solid var(--line);border-radius:2px;padding:6px 8px;}}
input[type=range]{{accent-color:var(--accent);}}
.sim-readout{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:14px;font-family:"IBM Plex Mono",monospace;font-size:13px;}}
.sim-readout .stat{{background:var(--paper);border:1px solid var(--line);border-radius:3px;padding:8px 14px;}}
.sim-readout .stat b{{display:block;font-size:20px;font-family:"Big Shoulders Display",sans-serif;}}
.btn{{font-family:"Big Shoulders Display",sans-serif;font-weight:800;font-size:16px;letter-spacing:.03em;text-transform:uppercase;background:var(--accent);color:var(--accent-ink);border:none;border-radius:4px;padding:12px 28px;cursor:pointer;}}
.btn:hover{{filter:brightness(1.08);}}
.sim-result{{margin-top:16px;padding:14px 16px;border-radius:3px;background:var(--paper);border:1px solid var(--line);font-family:"IBM Plex Mono",monospace;font-size:13px;min-height:1.4em;}}
.sim-result.accepted{{border-color:var(--win);}}
.sim-result.partial{{border-color:var(--draw);}}
.sim-result.walk_away{{border-color:var(--loss);}}

footer{{max-width:1180px;margin:0 auto;padding:0 clamp(16px,4vw,48px) 50px;color:var(--muted);font-size:12px;font-family:"IBM Plex Mono",monospace;}}
{NAV_CSS}
</style>
</head>
<body>
{render_nav("sponsorship")}
<div class="masthead">
  <div class="masthead-inner">
    <h1>Sponsorship Marketplace</h1>
    <p>{config["league_name"]} &middot; every team must sign one sponsor in each of {n_required} categories &mdash; sponsors pay YOU</p>
  </div>
</div>

<div class="wrap">
  <section>
    <div class="section-head"><h2>How It Works</h2></div>
    <div class="how-it-works">
      <p>Real clubs carry exactly one jersey sponsor, one kit manufacturer, one official airline &mdash; not an unlimited
      pile of deals. Sponsorship here works the same way: brands are grouped into {n_required} categories, and every team
      must sign <b>exactly one brand per category</b> before the draft ends. Multiple teams CAN sign the same brand
      (Nike sponsors dozens of real clubs at once) &mdash; the number on each card is a league-wide cap, not exclusivity.</p>
      <p style="margin-top:10px;"><b>Sponsors pay you.</b> There is no cost to sign anything &mdash; season revenue flows
      straight into your team, same as a real sponsorship deal.</p>
      <p style="margin-top:10px;">On your turn, target an open brand in whichever category you're filling. Two separate
      things are on the table:</p>
      <div class="asks-grid">
        <div class="ask-chip"><b>Revenue</b>Take the listed Base amount (guaranteed), or Negotiate &mdash; lands anywhere
        from &minus;10% to +10% of base, set by your <b>Negotiating Leverage</b> (roster avg. Star Power + a standings
        bonus once the season starts). Negotiating is not risk-free: a weak hand can land below base.</div>
        <div class="ask-chip"><b>Clause</b>A separate ask &mdash; push for a looser clause at Modest/Bold/Very Bold
        intensity, gated by the same leverage. This one CAN walk away if you overreach; the revenue side never does.</div>
      </div>
      <p style="margin-top:12px;"><b>The commission:</b> if a negotiated deal lands ABOVE base, the overage is ALSO
      credited as bonus revenue to whichever team's student played the sponsor rep &mdash; playing sponsor well pays off
      for your own team too, upside-only (never a penalty for landing at or below base).</p>
      <p style="margin-top:14px;"><b>The clause is real, not flavor text.</b> Once, at season end (Round
      {ce["checkpoint_round"]}), each clause level's OWN rank threshold gets checked against your team's FINAL standing.
      Miss it, and that specific deal claws back a flat {int(ce["penalty_pct"]*100)}% &mdash; the clause sets how hard
      the bar is, not how much you lose:</p>
      <div class="asks-grid">
        <div class="ask-chip"><b>Strict</b>needs top {rt["strict"]} &mdash; {int(ce["penalty_pct"]*100)}% if missed</div>
        <div class="ask-chip"><b>Standard</b>needs top {rt["standard"]} &mdash; {int(ce["penalty_pct"]*100)}% if missed</div>
        <div class="ask-chip"><b>Loose</b>needs top {rt["loose"]} &mdash; {int(ce["penalty_pct"]*100)}% if missed</div>
        <div class="ask-chip"><b>None</b>no requirement &mdash; fully protected</div>
      </div>
      <p style="margin-top:10px;">Checked per sponsor, off your one final rank &mdash; you can clear a loose-clause
      deal's easy bar while missing a strict-clause deal's demanding one in the same season. A strict clause pays more
      up front for a real bet you'll contend; loose is the safer, lower-upside insurance policy.</p>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2>Sponsor Categories</h2>
      <span class="section-note">live: slots and signings update as picks are made</span>
    </div>
    {categories_html}
  </section>

  <section>
    <div class="section-head"><h2>Team Progress</h2></div>
    <table>
      <thead><tr><th>Team</th><th class="num">Categories Filled</th><th>Sponsors</th></tr></thead>
      <tbody>{team_rows_html}</tbody>
    </table>
  </section>

  <section>
    <div class="section-head">
      <h2>Try a Negotiation</h2>
      <span class="section-note">a rehearsal &mdash; the real pick still happens live, on your draft turn</span>
    </div>
    <div class="sim">
      <div class="sim-grid">
        <div class="field">
          <label for="sim-sponsor">Brand</label>
          <select id="sim-sponsor"></select>
        </div>
        <div class="field">
          <label for="sim-star">Your Roster Avg. Star Power: <span id="sim-star-v">65</span></label>
          <input type="range" min="30" max="99" value="65" id="sim-star">
        </div>
        <div class="field">
          <label for="sim-revenue-ask">Revenue</label>
          <select id="sim-revenue-ask">
            <option value="base">Take Base (guaranteed)</option>
            <option value="negotiate">Negotiate (&minus;10% to +10%, by leverage)</option>
          </select>
        </div>
        <div class="field">
          <label for="sim-clause-ask">Clause</label>
          <select id="sim-clause-ask">
            <option value="none">Don't push it (keep base clause)</option>
            <option value="modest">Ask Modest</option>
            <option value="bold">Ask Bold</option>
            <option value="very_bold">Ask Very Bold</option>
          </select>
        </div>
      </div>
      <div class="sim-readout">
        <div class="stat">Leverage<br><b id="sim-leverage">0</b></div>
        <div class="stat">Revenue Adjustment<br><b id="sim-adjustment">&ndash;</b></div>
      </div>
      <button class="btn" id="sim-go">Make This Ask</button>
      <div class="sim-result" id="sim-result">Pick a brand and your asks, then hit the button.</div>
    </div>
  </section>
</div>

<footer>{config["league_name"]} &middot; sponsorship marketplace &mdash; math matches engine/negotiation.py exactly</footer>

<script>
const SPONSORS = {sponsor_pool_json};
const REQUIRED_THRESHOLD = {{modest: 20, bold: 50, very_bold: 80}};
const CLAUSE_UPSIDE = {{modest: 0.10, bold: 0.20, very_bold: 0.30}};
const CLAUSE_LEVELS = ["strict", "standard", "loose", "none"];
const REVENUE_RANGE = 0.10;

const sponsorSel = document.getElementById('sim-sponsor');
sponsorSel.innerHTML = SPONSORS.map(s => `<option value="${{s.name}}">${{s.category}}: ${{s.name}} &mdash; $${{s.base_revenue.toLocaleString()}}</option>`).join('');

function computeLeverage(avgStar) {{
  return Math.max(0, Math.min(100, (avgStar - 50) * 2));
}}

function updateReadout() {{
  const star = parseFloat(document.getElementById('sim-star').value);
  document.getElementById('sim-star-v').textContent = star;
  const leverage = computeLeverage(star);
  document.getElementById('sim-leverage').textContent = leverage.toFixed(0);
  const revenueAsk = document.getElementById('sim-revenue-ask').value;
  if (revenueAsk === 'base') {{
    document.getElementById('sim-adjustment').textContent = '0% (guaranteed)';
  }} else {{
    const adj = -REVENUE_RANGE + (leverage / 100) * (2 * REVENUE_RANGE);
    document.getElementById('sim-adjustment').textContent = (adj >= 0 ? '+' : '') + (adj * 100).toFixed(1) + '%';
  }}
}}

document.querySelectorAll('#sim-star, #sim-revenue-ask, #sim-clause-ask').forEach(el => el.addEventListener('input', updateReadout));
updateReadout();

document.getElementById('sim-go').addEventListener('click', () => {{
  const star = parseFloat(document.getElementById('sim-star').value);
  const leverage = computeLeverage(star);
  const revenueAsk = document.getElementById('sim-revenue-ask').value;
  const clauseAsk = document.getElementById('sim-clause-ask').value;
  const sponsor = SPONSORS.find(s => s.name === sponsorSel.value);
  const resultEl = document.getElementById('sim-result');

  // --- revenue axis ---
  let revenue = sponsor.base_revenue, commission = 0;
  if (revenueAsk === 'negotiate') {{
    const adj = -REVENUE_RANGE + (leverage / 100) * (2 * REVENUE_RANGE);
    revenue = Math.round(sponsor.base_revenue * (1 + adj));
    commission = Math.max(0, revenue - sponsor.base_revenue);
  }}

  // --- clause axis (independent) ---
  let clause = sponsor.base_clause;
  let clauseNote = '';
  if (clauseAsk !== 'none') {{
    const threshold = REQUIRED_THRESHOLD[clauseAsk];
    const gap = leverage - threshold;
    let outcome, fraction;
    if (gap >= 15) {{ outcome = 'accepted'; fraction = 1.0; }}
    else if (gap <= -15) {{ outcome = 'walk_away'; fraction = 0.0; }}
    else {{
      const acceptProb = 0.5 + gap / 30.0;
      if (Math.random() < acceptProb) {{ outcome = 'accepted'; fraction = 1.0; }}
      else {{ outcome = 'partial'; fraction = 0.5; }}
    }}
    if (outcome === 'walk_away') {{
      clauseNote = ` Clause ask WALKED AWAY (leverage ${{leverage.toFixed(0)}} too far below the ${{threshold}} needed) -- clause stays ${{sponsor.base_clause}}.`;
    }} else {{
      const upside = CLAUSE_UPSIDE[clauseAsk] * fraction;
      if (upside > 0) {{
        const idx = CLAUSE_LEVELS.indexOf(sponsor.base_clause);
        const steps = (clauseAsk === 'very_bold' && fraction === 1.0) ? 2 : 1;
        clause = CLAUSE_LEVELS[Math.min(CLAUSE_LEVELS.length - 1, idx + steps)];
        clauseNote = outcome === 'accepted' ? ' Clause ask ACCEPTED.' : ' Clause ask PARTIAL (met halfway).';
      }}
    }}
  }}

  resultEl.className = 'sim-result ' + (revenueAsk === 'negotiate' && revenue < sponsor.base_revenue ? 'walk_away' : 'accepted');
  let text = `Final terms: revenue $${{revenue.toLocaleString()}}/season, clause ${{clause}}.${{clauseNote}}`;
  if (commission > 0) {{
    text += ` A live sponsor rep playing ${{sponsor.name}} here would earn a $${{commission.toLocaleString()}} commission for their own team.`;
  }}
  resultEl.textContent = text;
}});
</script>
</body>
</html>'''


if __name__ == "__main__":
    config = load_json("league_config.json")
    deals = load_json("deals.json")
    finances = load_json("team_finances.json")
    html = render(config, deals, finances)
    out_dir = os.path.join(BASE, "sponsorship-site")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Rendered -> {out_path}")
