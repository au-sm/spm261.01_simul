"""
Renders home/index.html -- the SM Owners League site's front door.
Every other page (Dashboard, Rulebook, Sponsorship Marketplace, Match
Engine Walkthrough) already cross-links via the shared nav bar
(engine/site_nav.py); this page is the landing spot that introduces the
league and sends a first-time visitor to the right one of the four.

Reads league_config.json and season_calendar.json for the status strip
(phase, team count, Draft Day) -- never hand-typed, so this page can't
go stale the way a hardcoded landing page would.

Usage:
    python3 engine/render_home.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from site_nav import NAV_CSS, PAGES, render_nav

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def money(n):
    return f"${n:,}"


CARD_COPY = {
    "dashboard": ("Dashboard", "Standings, rosters, salary caps, this week's Player Condition report, and every real submission tool — rename your team, submit your Draft Board, and turn in your weekly lineup."),
    "draftboard": ("Draft Board", "The full undrafted player pool — search, filter, and sort all 399 players before you rank your own board."),
    "schedule": ("Schedule", "Every round's fixtures and date in one place — see what's already final and what's still coming up."),
    "scouting": ("Scouting Report", "Every team's roster-based Attack/Defense profile, plus their formation and strategy history once they've played — the real inputs for your weekly call."),
    "budget": ("Budget Dashboard", "Draft money left, and cash on hand from ticket, sponsorship, and TV revenue — one team's whole financial picture."),
    "rulebook": ("Rulebook", "Every rule, every formula, every point your grade is built from — start here if you're new."),
    "sponsorship": ("Sponsorship Marketplace", "Open brand slots, live deal status, a negotiation simulator, and the real form to sign your sponsor."),
    "trade": ("Trade Center", "Propose a trade, respond to one sent to you, and see the full trade log -- real roster swaps, real cap checks, real cash considerations."),
    "tv": ("TV Rights Marketplace", "Your market tier, your Local TV base rate, a negotiation simulator, and the real form to lock in your rate."),
    "attendance": ("Attendance &amp; Ticket Sales", "Ticket revenue by team, the attendance formula explained, and a pricing simulator for your next home match."),
    "replay": ("Matchday Replay", "A 90-minute match compressed into a 30-second animated replay — real formation shape, real goal minutes, real final score."),
    "walkthrough": ("Match Engine Walkthrough", "Drag the sliders, hit Kickoff — see exactly how a lineup, formation, and strategy turn into a final score."),
}


def render(config, calendar):
    phase = config.get("phase", "pre-draft")
    phase_label = {
        "pre-draft": "PRE-DRAFT", "draft": "DRAFT DAY",
        "season": f"ROUND {config.get('current_round', 0)}", "offseason": "OFF-SEASON",
    }.get(phase, phase.upper())

    cards_html = "".join(
        f'''<a class="page-card" href="{url}" target="_blank" rel="noopener">
      <h3>{CARD_COPY[key][0]}</h3>
      <p>{CARD_COPY[key][1]}</p>
      <span class="page-card-go">Open &rarr;</span>
    </a>'''
        for key, _, url in PAGES if key in CARD_COPY  # skip "home" itself -- no self-link card
    )

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{config["league_name"]}</title>
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

.hero{{background:var(--pitch);color:var(--pitch-ink);padding:clamp(48px,10vw,88px) clamp(16px,4vw,48px) clamp(40px,8vw,64px);}}
.hero-inner{{max-width:900px;margin:0 auto;text-align:center;}}
.phase-pill{{display:inline-block;background:var(--accent);color:var(--accent-ink);font-family:"IBM Plex Mono",monospace;font-size:12px;font-weight:600;letter-spacing:.08em;padding:5px 12px;border-radius:2px;margin-bottom:18px;}}
.hero h1{{font-family:"Big Shoulders Display",sans-serif;text-transform:uppercase;letter-spacing:.02em;text-wrap:balance;font-size:clamp(36px,7vw,64px);font-weight:800;margin:0 0 10px;}}
.hero p.tagline{{font-family:"IBM Plex Mono",monospace;font-size:14px;opacity:.85;letter-spacing:.02em;margin:0 0 30px;}}

.stat-row{{display:flex;justify-content:center;gap:clamp(18px,4vw,44px);flex-wrap:wrap;}}
.stat{{text-align:left;}}
.stat .num{{display:block;font-family:"Big Shoulders Display",sans-serif;font-size:clamp(22px,3.4vw,30px);font-weight:800;font-variant-numeric:tabular-nums;}}
.stat .label{{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;opacity:.75;}}

.wrap{{max-width:1080px;margin:0 auto;padding:clamp(32px,6vw,56px) clamp(16px,4vw,48px) 40px;}}
.section-label{{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:0 0 16px;}}

.page-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;}}
.page-card{{display:flex;flex-direction:column;gap:8px;background:var(--surface);border:1px solid var(--line);border-radius:4px;
  box-shadow:var(--shadow);padding:22px clamp(18px,2.4vw,26px);text-decoration:none;color:var(--ink);
  transition:transform .12s ease, border-color .12s ease;}}
.page-card:hover{{transform:translateY(-2px);border-color:var(--accent);}}
.page-card h3{{font-family:"Big Shoulders Display",sans-serif;text-transform:uppercase;letter-spacing:.01em;font-size:20px;margin:0;}}
.page-card p{{margin:0;font-size:14.5px;color:var(--muted);flex:1;}}
.page-card-go{{font-family:"IBM Plex Mono",monospace;font-size:11.5px;letter-spacing:.04em;color:var(--accent);font-weight:600;}}

footer{{max-width:1080px;margin:0 auto;padding:20px clamp(16px,4vw,48px) 56px;color:var(--muted);font-size:12.5px;font-family:"IBM Plex Mono",monospace;}}
{NAV_CSS}
</style>
</head>
<body>
{render_nav("home")}
<div class="hero">
  <div class="hero-inner">
    <span class="phase-pill">{phase_label}</span>
    <h1>{config["league_name"]}</h1>
    <p class="tagline">{config["season_label"]} &middot; Arcadia University &mdash; School of Global Business, Sport Management</p>
    <div class="stat-row">
      <div class="stat"><span class="num">{config["n_teams"]}</span><span class="label">Teams</span></div>
      <div class="stat"><span class="num">{calendar["draft_day"]}</span><span class="label">Draft Day</span></div>
      <div class="stat"><span class="num">{money(config["salary_cap"])}</span><span class="label">Salary Cap</span></div>
      <div class="stat"><span class="num">{calendar["season_end"]}</span><span class="label">Season Ends</span></div>
    </div>
  </div>
</div>

<div class="wrap">
  <p class="section-label">The Site</p>
  <div class="page-grid">
    {cards_html}
  </div>
</div>

<footer>You are not a player &mdash; you are the owner and general manager of a professional soccer club. Every number on this site traces back to a decision you made, in writing.</footer>
</body>
</html>
'''


if __name__ == "__main__":
    config = load_json("league_config.json")
    calendar = load_json("season_calendar.json")
    html = render(config, calendar)
    out_dir = os.path.join(BASE, "home")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Rendered -> {out_path}")
