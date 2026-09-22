"""
Renders attendance-site/index.html -- the standalone Attendance &
Ticket Sales page, same sibling pattern as sponsorship-site/index.html
and tv-site/index.html: a status page plus a client-side simulator that
mirrors engine/attendance.py's formula exactly.

Unlike Sponsorship and TV, there's no "deal" here to negotiate or
sign -- ticket price is a per-round choice every home team makes on the
Weekly Lineup form, so this page is pure formula explainer + simulator
+ cumulative ticket revenue standing, not a live marketplace of open
slots.

Reads data/team_finances.json for each team's ticket revenue booked so
far (all zero pre-season) and data/league_config.json for team names.

Run after any resolve_round.py call, then republish.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from site_nav import NAV_CSS, render_nav
from attendance import CAPACITY, PRICE_TIERS, PRICE_EFFECT, BASE_RATE, FORM_WEIGHT, STAR_WEIGHT, MIN_RATE, MAX_RATE

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def money(n):
    return f"${n:,}"


def render(config, finances):
    owner_by_id = {t["team_id"]: t.get("owner", "") for t in config["teams"]}
    name_by_id = {t["team_id"]: t["name"] for t in config["teams"]}

    team_rows = []
    for t in sorted(config["teams"], key=lambda t: t["team_id"]):
        tid = t["team_id"]
        rec = finances["teams"].get(str(tid), {})
        revenue = rec.get("ticket_revenue", 0)
        owner = owner_by_id.get(tid, "")
        label = t["name"] + (f" ({owner})" if owner else "")
        team_rows.append(f'<tr><td>{label}</td><td class="num">{money(revenue)}</td></tr>')
    team_rows_html = "".join(team_rows)

    tier_rows = "".join(
        f'<tr><td>{tier}</td><td class="num">{money(PRICE_TIERS[tier])}</td>'
        f'<td class="num">{"+" if PRICE_EFFECT[tier] >= 0 else ""}{PRICE_EFFECT[tier]*100:.0f} pts</td></tr>'
        for tier in ("Budget", "Standard", "Premium")
    )

    price_effect_json = json.dumps(PRICE_EFFECT)
    price_tiers_json = json.dumps(PRICE_TIERS)

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Attendance &amp; Ticket Sales</title>
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

table{{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--surface);border:1px solid var(--line);border-radius:3px;box-shadow:var(--shadow);margin-bottom:16px;}}
thead th{{background:var(--navy);color:var(--navy-ink);text-align:left;padding:9px 10px;font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;}}
thead th.num{{text-align:right;}}
tbody td{{padding:7px 10px;border-top:1px solid var(--line);}}

.sim{{background:var(--surface);border:1px solid var(--line);border-radius:4px;box-shadow:var(--shadow);padding:20px 22px;}}
.sim-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;}}
@media (max-width:640px){{.sim-grid{{grid-template-columns:1fr;}}}}
.field label{{display:block;font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin-bottom:5px;}}
.field select, .field input[type=range]{{width:100%;}}
select{{font-family:"Source Serif 4",serif;font-size:14px;background:var(--paper);color:var(--ink);border:1px solid var(--line);border-radius:2px;padding:6px 8px;}}
input[type=range]{{accent-color:var(--accent);}}
.sim-readout{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:14px;font-family:"IBM Plex Mono",monospace;font-size:13px;}}
.sim-readout .stat{{background:var(--paper);border:1px solid var(--line);border-radius:3px;padding:8px 14px;}}
.sim-readout .stat b{{display:block;font-size:20px;font-family:"Big Shoulders Display",sans-serif;}}
.pitch-meter{{height:22px;border-radius:11px;background:var(--paper);border:1px solid var(--line);overflow:hidden;margin-bottom:16px;position:relative;}}
.pitch-meter-fill{{height:100%;background:var(--accent);transition:width .15s ease;}}
.pitch-meter-label{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:"IBM Plex Mono",monospace;font-size:11px;font-weight:600;color:var(--ink);mix-blend-mode:difference;}}

footer{{max-width:1180px;margin:0 auto;padding:0 clamp(16px,4vw,48px) 50px;color:var(--muted);font-size:12px;font-family:"IBM Plex Mono",monospace;}}
{NAV_CSS}
</style>
</head>
<body>
{render_nav("attendance")}
<div class="masthead">
  <div class="masthead-inner">
    <h1>Attendance &amp; Ticket Sales</h1>
    <p>{config["league_name"]} &middot; set your price tier every home match &mdash; attendance responds to price, form, and Star Power</p>
  </div>
</div>

<div class="wrap">
  <section>
    <div class="section-head"><h2>How It Works</h2></div>
    <div class="how-it-works">
      <p>Every home match, you choose a ticket price tier on the Weekly Lineup form. Revenue = attendance &times; price
      &mdash; the classic price-elasticity tradeoff: Premium pays more per fan but empties seats; Budget fills the
      building but caps the per-ticket upside. Stadium capacity is <b>{CAPACITY:,}</b>.</p>
      <table><thead><tr><th>Tier</th><th class="num">Price</th><th class="num">Attendance Effect</th></tr></thead><tbody>{tier_rows}</tbody></table>
      <p>The full formula, starting from a {int(BASE_RATE*100)}% base fill rate:</p>
      <div class="asks-grid">
        <div class="ask-chip"><b>Price</b>set by your tier above &mdash; the only thing you directly control</div>
        <div class="ask-chip"><b>Recent Form</b>win rate over your last 3 matches, &plusmn;{int(FORM_WEIGHT*50)} points of
        attendance at the extremes (0.5 = neutral, no history yet)</div>
        <div class="ask-chip"><b>Star Power</b>your STARTING XI's average Star Power (not full roster &mdash; fans come to
        see who's actually playing), &plusmn;{int(STAR_WEIGHT*50)} points of attendance at the extremes</div>
      </div>
      <p style="margin-top:12px;">These three add together on top of the {int(BASE_RATE*100)}% base, then the result is
      clamped between {int(MIN_RATE*100)}% and {int(MAX_RATE*100)}% before being applied to capacity. The floor is
      deliberately low: Premium pricing on a team with no form and no Star Power is allowed to crater &mdash; a generous
      floor would quietly rescue Premium and erase the whole price-elasticity lesson.</p>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2>Ticket Revenue by Team</h2>
      <span class="section-note">live: booked as each home round is resolved</span>
    </div>
    <table>
      <thead><tr><th>Team</th><th class="num">Ticket Revenue Booked</th></tr></thead>
      <tbody>{team_rows_html}</tbody>
    </table>
  </section>

  <section>
    <div class="section-head">
      <h2>Try It</h2>
      <span class="section-note">rehearse a home-match pricing call before you submit the real form</span>
    </div>
    <div class="sim">
      <div class="sim-grid">
        <div class="field">
          <label for="sim-tier">Price Tier</label>
          <select id="sim-tier">
            <option value="Budget">Budget ($15)</option>
            <option value="Standard" selected>Standard ($30)</option>
            <option value="Premium">Premium ($50)</option>
          </select>
        </div>
        <div class="field">
          <label for="sim-form">Recent Form (win rate, last 3): <span id="sim-form-v">50%</span></label>
          <input type="range" min="0" max="100" value="50" id="sim-form">
        </div>
        <div class="field">
          <label for="sim-star">Starting XI Avg. Star Power: <span id="sim-star-v">65</span></label>
          <input type="range" min="0" max="99" value="65" id="sim-star">
        </div>
      </div>
      <div class="pitch-meter"><div class="pitch-meter-fill" id="sim-fill" style="width:0%"></div><div class="pitch-meter-label" id="sim-fill-label">&ndash;</div></div>
      <div class="sim-readout">
        <div class="stat">Attendance<br><b id="sim-attendance">&ndash;</b></div>
        <div class="stat">Revenue<br><b id="sim-revenue">&ndash;</b></div>
      </div>
    </div>
  </section>
</div>

<footer>{config["league_name"]} &middot; attendance simulator &mdash; math matches engine/attendance.py exactly</footer>

<script>
const CAPACITY = {CAPACITY};
const PRICE_TIERS = {price_tiers_json};
const PRICE_EFFECT = {price_effect_json};
const BASE_RATE = {BASE_RATE};
const FORM_WEIGHT = {FORM_WEIGHT};
const STAR_WEIGHT = {STAR_WEIGHT};
const MIN_RATE = {MIN_RATE};
const MAX_RATE = {MAX_RATE};

function update() {{
  const tier = document.getElementById('sim-tier').value;
  const formPct = parseFloat(document.getElementById('sim-form').value);
  const star = parseFloat(document.getElementById('sim-star').value);
  document.getElementById('sim-form-v').textContent = formPct.toFixed(0) + '%';
  document.getElementById('sim-star-v').textContent = star.toFixed(0);

  const winRate = formPct / 100;
  let rate = BASE_RATE + PRICE_EFFECT[tier] + (winRate - 0.5) * FORM_WEIGHT + ((star - 50) / 50) * STAR_WEIGHT;
  rate = Math.max(MIN_RATE, Math.min(MAX_RATE, rate));

  const attendance = Math.round(CAPACITY * rate);
  const revenue = attendance * PRICE_TIERS[tier];

  document.getElementById('sim-fill').style.width = (rate * 100).toFixed(1) + '%';
  document.getElementById('sim-fill-label').textContent = (rate * 100).toFixed(1) + '% full';
  document.getElementById('sim-attendance').textContent = attendance.toLocaleString();
  document.getElementById('sim-revenue').textContent = '$' + revenue.toLocaleString();
}}

document.querySelectorAll('#sim-tier, #sim-form, #sim-star').forEach(el => el.addEventListener('input', update));
update();
</script>
</body>
</html>'''


if __name__ == "__main__":
    config = load_json("league_config.json")
    finances = load_json("team_finances.json")
    html = render(config, finances)
    out_dir = os.path.join(BASE, "attendance-site")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Rendered -> {out_path}")
