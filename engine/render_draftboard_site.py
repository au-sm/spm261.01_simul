"""
Renders draftboard-site/index.html -- the standalone Draft Board page:
the full 399-player pool, sortable/filterable/searchable, moved OUT of
the Dashboard (2026-09-22, instructor request) into its own page right
next to it in the nav, since browsing the whole pool is its own task
separate from checking your own roster/standings.

Reads data/players.csv via render_dashboard.load_players() -- the
exact same source and shape the old in-Dashboard table used, so
nothing about the underlying data changes, just where it's shown.

Run after any draft/round resolves (a player's team_id changing
removes them from "available" here), then republish.
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


def render(config, players):
    free_agents = [p for p in players if p["team_id"] in ("", None)]
    draft_pool_sorted = sorted(free_agents, key=lambda p: -p["ovr"])
    players_json = json.dumps(draft_pool_sorted)

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Draft Board</title>
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
body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Source Serif 4",Georgia,serif;line-height:1.5;}}
.mono{{font-family:"IBM Plex Mono",ui-monospace,monospace;}}
h1,h2{{font-family:"Big Shoulders Display",sans-serif;text-transform:uppercase;letter-spacing:.02em;text-wrap:balance;margin:0;}}
.num{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums;text-align:right;}}

.masthead{{background:var(--pitch);color:var(--pitch-ink);padding:28px clamp(16px,4vw,48px);}}
.masthead-inner{{max-width:1240px;margin:0 auto;}}
.masthead h1{{font-size:clamp(26px,4vw,38px);font-weight:800;}}
.masthead p{{font-family:"IBM Plex Mono",monospace;font-size:12.5px;opacity:.85;margin:6px 0 0;letter-spacing:.03em;}}

.wrap{{max-width:1240px;margin:0 auto;padding:28px clamp(16px,4vw,48px) 70px;}}
.section-head{{display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px solid var(--ink);padding-bottom:6px;margin-bottom:16px;flex-wrap:wrap;gap:8px;}}
.section-head h2{{font-size:22px;}}
.section-note{{color:var(--muted);font-size:13px;font-family:"IBM Plex Mono",monospace;}}

.controls-row{{display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap;align-items:center;}}
.controls-row input[type=text]{{flex:1;min-width:220px;font-family:"Source Serif 4",serif;font-size:14px;background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:2px;padding:8px 10px;}}
.filter-row{{display:flex;gap:8px;flex-wrap:wrap;}}
.filter-btn{{font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.04em;background:var(--surface);border:1px solid var(--line);color:var(--ink);padding:6px 12px;border-radius:2px;cursor:pointer;}}
.filter-btn.active{{background:var(--ink);color:var(--paper);border-color:var(--ink);}}

.table-scroll{{overflow-x:auto;border:1px solid var(--line);border-radius:3px;background:var(--surface);box-shadow:var(--shadow);}}
table{{width:100%;border-collapse:collapse;font-size:14px;}}
thead th{{position:sticky;top:0;background:var(--navy);color:var(--navy-ink);text-align:left;padding:9px 10px;font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;cursor:pointer;white-space:nowrap;}}
thead th.num{{text-align:right;}}
tbody td{{padding:8px 10px;border-top:1px solid var(--line);}}
tbody tr:hover{{background:color-mix(in srgb, var(--accent) 10%, transparent);}}
.pos{{font-family:"IBM Plex Mono",monospace;font-weight:600;font-size:12px;width:1%;white-space:nowrap;}}
.pos-GK{{color:var(--draw,var(--accent));}} .pos-DF{{color:var(--navy);}} .pos-MF{{color:var(--pitch);}} .pos-FW{{color:#b4472f;}}
.star-bar{{display:inline-block;width:48px;height:6px;background:var(--line);border-radius:3px;overflow:hidden;vertical-align:middle;margin-left:6px;}}
.star-bar-fill{{display:block;height:100%;background:var(--accent);}}
.empty-row td{{color:var(--muted);font-style:italic;text-align:center;padding:18px;}}

footer{{max-width:1240px;margin:0 auto;padding:0 clamp(16px,4vw,48px) 50px;color:var(--muted);font-size:12.5px;font-family:"IBM Plex Mono",monospace;}}
{NAV_CSS}
</style>
</head>
<body>
{render_nav("draftboard")}
<div class="masthead">
  <div class="masthead-inner">
    <h1>Draft Board</h1>
    <p>{config["league_name"]} &middot; the full undrafted player pool &mdash; search, filter, sort</p>
  </div>
</div>

<div class="wrap">
  <section>
    <div class="section-head">
      <h2>Available Players</h2>
      <span class="section-note" id="count-note">{len(draft_pool_sorted)} available &middot; click a column to sort</span>
    </div>
    <div class="controls-row">
      <input type="text" id="search-box" placeholder="Search by name...">
      <div class="filter-row">
        <button class="filter-btn active" data-pos="ALL">All</button>
        <button class="filter-btn" data-pos="GK">GK</button>
        <button class="filter-btn" data-pos="DF">DF</button>
        <button class="filter-btn" data-pos="MF">MF</button>
        <button class="filter-btn" data-pos="FW">FW</button>
      </div>
    </div>
    <div class="table-scroll">
      <table id="draft-table">
        <thead>
          <tr>
            <th data-key="position">Pos</th>
            <th data-key="player_id" class="num">ID</th>
            <th data-key="name">Player</th>
            <th data-key="age" class="num">Age</th>
            <th data-key="att" class="num">ATT</th>
            <th data-key="def" class="num">DEF</th>
            <th data-key="pace" class="num">PAC</th>
            <th data-key="phy" class="num">PHY</th>
            <th data-key="ovr" class="num">OVR</th>
            <th data-key="star_power" class="num">Star</th>
            <th data-key="salary" class="num">Salary</th>
          </tr>
        </thead>
        <tbody id="draft-body"></tbody>
      </table>
    </div>
  </section>
</div>

<footer>{config["league_name"]} &middot; draft board &mdash; rank your own picks and submit at the Submit page</footer>

<script>
const PLAYERS = {players_json};
let sortKey = "ovr", sortDir = -1, posFilter = "ALL", searchTerm = "";

function fmtSalary(n) {{
  if (n >= 1000000) {{
    let v = (n/1000000).toFixed(1);
    if (v.endsWith(".0")) v = v.slice(0,-2);
    return "$"+v+"M";
  }}
  return "$"+Math.round(n/1000)+"K";
}}

function starBar(v) {{
  return `${{v}}<span class="star-bar"><span class="star-bar-fill" style="width:${{v}}%"></span></span>`;
}}

function render() {{
  let rows = PLAYERS.filter(p => posFilter === "ALL" || p.position === posFilter);
  if (searchTerm) {{
    rows = rows.filter(p => p.name.toLowerCase().includes(searchTerm));
  }}
  rows.sort((a,b) => {{
    let av = a[sortKey], bv = b[sortKey];
    if (sortKey === "player_id") {{ av = Number(av); bv = Number(bv); }}
    return (av > bv ? 1 : av < bv ? -1 : 0) * sortDir;
  }});
  document.getElementById("count-note").textContent = rows.length + " shown of " + PLAYERS.length + " available -- click a column to sort";
  const body = document.getElementById("draft-body");
  if (rows.length === 0) {{
    body.innerHTML = '<tr class="empty-row"><td colspan="11">No players match this filter</td></tr>';
    return;
  }}
  body.innerHTML = rows.map(p => `
    <tr>
      <td class="pos pos-${{p.position}}">${{p.position}}</td>
      <td class="num mono">${{p.player_id}}</td>
      <td>${{p.name}}</td>
      <td class="num">${{p.age}}</td>
      <td class="num">${{p.att}}</td>
      <td class="num">${{p.def}}</td>
      <td class="num">${{p.pace}}</td>
      <td class="num">${{p.phy}}</td>
      <td class="num">${{p.ovr}}</td>
      <td class="num">${{starBar(p.star_power)}}</td>
      <td class="num">${{fmtSalary(p.salary)}}</td>
    </tr>`).join("");
}}

document.getElementById("search-box").addEventListener("input", (e) => {{
  searchTerm = e.target.value.trim().toLowerCase();
  render();
}});

document.querySelectorAll(".filter-btn").forEach(btn => {{
  btn.addEventListener("click", () => {{
    document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    posFilter = btn.dataset.pos;
    render();
  }});
}});

document.querySelectorAll("#draft-table thead th[data-key]").forEach(th => {{
  th.addEventListener("click", () => {{
    const key = th.dataset.key;
    if (sortKey === key) {{ sortDir *= -1; }} else {{ sortKey = key; sortDir = -1; }}
    render();
  }});
}});

render();
</script>
</body>
</html>'''


if __name__ == "__main__":
    config = load_json("league_config.json")
    players = render_dashboard.load_players()
    html = render(config, players)
    out_dir = os.path.join(BASE, "draftboard-site")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Rendered -> {out_path}")
