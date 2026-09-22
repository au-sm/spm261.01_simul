"""
Renders budget-site/index.html -- the standalone Budget Dashboard page:
one status page showing every team's two separate money pools side by
side --

  Salary Cap (data/players.csv salaries vs league_config.json
  salary_cap) -- what's been spent DRAFTING players, and what's left to
  spend there.

  Budget (league_config.json starting_budget plus everything booked in
  data/team_finances.json -- ticket, sponsorship, local TV, national
  TV) -- actual cash on hand, the pool trade cash considerations come
  from.

These are NOT the same number and never should be added together --
see the "How It Works" section below, which is the same distinction
explained on the Rulebook and in-class.

Reads data/league_config.json, data/players.csv (via
render_dashboard.load_players), and data/team_finances.json. Run after
ANY state change that moves money -- a draft pick, a resolved round, a
signed sponsorship or TV deal -- then republish.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from site_nav import NAV_CSS, render_nav
import render_dashboard

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def money(n):
    return f"${n:,}"


def render(config, players, finances):
    cap = config.get("salary_cap", 0)
    starting_budget = config.get("starting_budget", 0)

    cap_used_by_team = {t["team_id"]: 0 for t in config["teams"]}
    for p in players:
        if p["team_id"] not in ("", None):
            cap_used_by_team[int(p["team_id"])] += p["salary"]

    REVENUE_FIELDS = [
        ("ticket_revenue", "Ticket Sales"),
        ("sponsorship_revenue", "Sponsorship"),
        ("local_tv_revenue", "Local TV"),
        ("tv_revenue", "National TV"),
    ]

    rows = []
    total_cap_used = 0
    total_budget_available = 0
    for t in sorted(config["teams"], key=lambda t: t["team_id"]):
        tid = t["team_id"]
        rec = finances["teams"].get(str(tid), {})
        cap_used = cap_used_by_team.get(tid, 0)
        cap_left = cap - cap_used
        revenue_total = sum(rec.get(field, 0) for field, _ in REVENUE_FIELDS)
        available = starting_budget + revenue_total
        total_cap_used += cap_used
        total_budget_available += available

        owner = t.get("owner", "")
        label = t["name"] + (f" ({owner})" if owner else "")
        cap_pct = min(100, round(cap_used / cap * 100)) if cap else 0
        revenue_cells = "".join(
            f'<td class="num">{money(rec.get(field, 0))}</td>' for field, _ in REVENUE_FIELDS
        )

        rows.append(f'''
        <tr>
          <td>{label}</td>
          <td class="num mono">{money(cap_used)}</td>
          <td class="num mono">{money(max(0, cap_left))}</td>
          <td class="cap-cell"><div class="cap-bar"><div class="cap-bar-fill" style="width:{cap_pct}%"></div></div></td>
          {revenue_cells}
          <td class="num mono total-cell">{money(available)}</td>
        </tr>''')
    team_rows_html = "".join(rows)

    revenue_header_cells = "".join(f'<th class="num">{label}</th>' for _, label in REVENUE_FIELDS)

    n_teams = len(config["teams"])

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Budget Dashboard</title>
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
.masthead-inner{{max-width:1280px;margin:0 auto;}}
.masthead h1{{font-size:clamp(26px,4vw,38px);font-weight:800;}}
.masthead p{{font-family:"IBM Plex Mono",monospace;font-size:12.5px;opacity:.85;margin:6px 0 0;letter-spacing:.03em;}}

.wrap{{max-width:1280px;margin:0 auto;padding:28px clamp(16px,4vw,48px) 70px;}}
section{{margin-bottom:36px;}}
.section-head{{display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px solid var(--ink);padding-bottom:6px;margin-bottom:16px;}}
.section-head h2{{font-size:21px;}}
.section-note{{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--muted);}}

.pool-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-bottom:6px;}}
.pool-card{{background:var(--surface);border:1px solid var(--line);border-radius:4px;box-shadow:var(--shadow);padding:16px 20px;}}
.pool-card b{{display:block;font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--accent);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px;}}
.pool-card p{{margin:0;font-size:13.5px;color:var(--muted);}}

.stat-strip{{display:flex;flex-wrap:wrap;gap:14px;margin-bottom:20px;}}
.stat-tile{{background:var(--surface);border:1px solid var(--line);border-radius:4px;box-shadow:var(--shadow);padding:12px 18px;min-width:160px;}}
.stat-tile .label{{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);}}
.stat-tile .val{{font-family:"Big Shoulders Display",sans-serif;font-size:24px;font-weight:800;font-variant-numeric:tabular-nums;}}

table{{width:100%;border-collapse:collapse;font-size:13px;background:var(--surface);border:1px solid var(--line);border-radius:3px;box-shadow:var(--shadow);margin-bottom:16px;}}
thead th{{background:var(--navy);color:var(--navy-ink);text-align:left;padding:9px 8px;font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:.04em;text-transform:uppercase;white-space:nowrap;}}
thead th.num{{text-align:right;}}
tbody td{{padding:7px 8px;border-top:1px solid var(--line);white-space:nowrap;}}
tbody tr:hover{{background:var(--paper);}}
.total-cell{{font-weight:600;color:var(--accent-ink);background:color-mix(in srgb, var(--accent) 14%, transparent);}}
.cap-cell{{min-width:80px;}}
.cap-bar{{height:8px;border-radius:4px;background:var(--paper);border:1px solid var(--line);overflow:hidden;}}
.cap-bar-fill{{height:100%;background:var(--accent);}}
.table-scroll{{overflow-x:auto;}}

footer{{max-width:1280px;margin:0 auto;padding:0 clamp(16px,4vw,48px) 50px;color:var(--muted);font-size:12px;font-family:"IBM Plex Mono",monospace;}}
{NAV_CSS}
</style>
</head>
<body>
{render_nav("budget")}
<div class="masthead">
  <div class="masthead-inner">
    <h1>Budget Dashboard</h1>
    <p>{config["league_name"]} &middot; {n_teams} teams &middot; salary cap room and cash on hand, side by side</p>
  </div>
</div>

<div class="wrap">
  <section>
    <div class="section-head"><h2>How It Works</h2></div>
    <div class="pool-grid">
      <div class="pool-card">
        <b>Salary Cap &mdash; {money(cap)}</b>
        <p>What you've committed to PLAYER SALARIES on your roster. This is the number that limits your draft picks
        and any roster move &mdash; a trade is only valid if both teams stay at or under this line afterward.
        Spending it down doesn't cost you cash; it's a roster ceiling, not a wallet.</p>
      </div>
      <div class="pool-card">
        <b>Budget &mdash; starts at {money(starting_budget)}</b>
        <p>Actual cash: your starting budget plus everything you've earned from ticket sales, sponsorship deals,
        and TV deals. This is the pool cash considerations in a trade come from &mdash; separate from the salary cap
        and never raised by it.</p>
      </div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2>League Totals</h2>
      <span class="section-note">as of the last resolved event</span>
    </div>
    <div class="stat-strip">
      <div class="stat-tile"><div class="label">Total Cap Committed</div><div class="val">{money(total_cap_used)}</div></div>
      <div class="stat-tile"><div class="label">League Cap Room</div><div class="val">{money(cap * n_teams - total_cap_used)}</div></div>
      <div class="stat-tile"><div class="label">Total Cash Across League</div><div class="val">{money(total_budget_available)}</div></div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2>Team Budgets</h2>
      <span class="section-note">draft money left, revenue booked, and cash on hand &mdash; per team</span>
    </div>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Team</th>
            <th class="num">Cap Used</th>
            <th class="num">Cap Left</th>
            <th>Cap Room</th>
            {revenue_header_cells}
            <th class="num">Cash Available</th>
          </tr>
        </thead>
        <tbody>{team_rows_html}</tbody>
      </table>
    </div>
    <p class="section-note">National TV revenue posts at the Round 9 split; Local TV revenue posts at that same split
    once negotiated. Both read {money(0)} until then &mdash; that's expected pre-split, not a bug.</p>
  </section>
</div>

<footer>{config["league_name"]} &middot; budget dashboard &mdash; Cap Used from data/players.csv, Cash Available from data/team_finances.json</footer>
</body>
</html>'''


if __name__ == "__main__":
    config = load_json("league_config.json")
    players = render_dashboard.load_players()
    finances = load_json("team_finances.json")
    html = render(config, players, finances)
    out_dir = os.path.join(BASE, "budget-site")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Rendered -> {out_path}")
