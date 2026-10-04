"""
Renders player-stats-site/index.html -- the Player Stats board.

Every number is derived from data/matches.json, recomputed from scratch on
each run, so the board updates automatically after every simulated round:
  - Goals and goal types come from each match's goal_events (scorer_id).
  - Appearances (starts) and clean sheets come from the starting XI that
    resolve_round.py records per match (home_starters / away_starters).
Before any round is played the board renders with every player at zero.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from site_nav import NAV_CSS, render_nav
import render_dashboard

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOAL_TYPES = ["Strike", "Header", "Corner Kick", "Penalty Kick", "Free Kick"]


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def compute(players, matches):
    stats = {}
    for p in players:
        if p.get("team_id") in ("", None):
            continue
        stats[str(p["player_id"])] = {
            "id": str(p["player_id"]), "name": p["name"], "pos": p["position"],
            "team_id": int(p["team_id"]), "ovr": int(p["ovr"]),
            "apps": 0, "goals": 0, "cs": 0, "ga": 0, "types": {t: 0 for t in GOAL_TYPES},
        }
    rounds = sorted({m["round"] for m in matches})
    for m in matches:
        sides = (("home", m["home_goals"], m["away_goals"]), ("away", m["away_goals"], m["home_goals"]))
        for side, _gf, ga in sides:
            for pid in m.get(f"{side}_starters", []):
                s = stats.get(str(pid))
                if not s:
                    continue
                s["apps"] += 1
                if s["pos"] == "GK":
                    s["ga"] += ga
                    if ga == 0:
                        s["cs"] += 1
        for ev in m.get("goal_events", []):
            s = stats.get(str(ev.get("scorer_id")))
            if not s:
                continue
            s["goals"] += 1
            t = ev.get("type")
            if t in s["types"]:
                s["types"][t] += 1
    return list(stats.values()), rounds


def board(title, rows, value_label, empty):
    if not rows:
        body = f'<tr class="empty-row"><td colspan="4">{empty}</td></tr>'
    else:
        body = "".join(
            f'<tr><td class="rk">{i}</td><td><b>{r[0]}</b><span class="sub">{r[1]}</span></td><td class="pos">{r[2]}</td><td class="num">{r[3]}</td></tr>'
            for i, r in enumerate(rows, 1))
    return (f'<div class="lb"><h3>{title}</h3><table><thead><tr><th>#</th><th>Player</th><th>Pos</th>'
            f'<th class="num">{value_label}</th></tr></thead><tbody>{body}</tbody></table></div>')


def render(config, players, matches):
    team_map = {t["team_id"]: t["name"] for t in config["teams"]}
    stats, rounds = compute(players, matches)
    played = len(rounds)
    tn = lambda s: team_map.get(s["team_id"], "")

    def top(key, filt=lambda s: True, n=10):
        rows = [s for s in stats if filt(s) and key(s) > 0]
        rows.sort(key=lambda s: (-key(s), -s["ovr"], s["name"]))
        return [(s["name"], tn(s), s["pos"], key(s)) for s in rows[:n]]

    empty = "No matches played yet &mdash; stats appear after Round 1 is simulated."
    boards = "".join([
        board("Top Scorers", top(lambda s: s["goals"]), "Goals", empty),
        board("Most Appearances", top(lambda s: s["apps"]), "Starts", empty),
        board("Clean Sheets (GK)", top(lambda s: s["cs"], lambda s: s["pos"] == "GK"), "Clean sheets", empty),
        board("Header Goals", top(lambda s: s["types"]["Header"]), "Headers", empty),
        board("Set-Piece Goals", top(lambda s: s["types"]["Corner Kick"] + s["types"]["Free Kick"] + s["types"]["Penalty Kick"]),
              "Set pieces", empty),
    ])

    table_rows = sorted(stats, key=lambda s: (-s["goals"], -s["apps"], tn(s), s["name"]))
    data_rows = "".join(
        f'<tr data-team="{s["team_id"]}" data-pos="{s["pos"]}"><td><b>{s["name"]}</b></td><td>{tn(s)}</td>'
        f'<td class="pos">{s["pos"]}</td><td class="num">{s["ovr"]}</td><td class="num">{s["apps"]}</td>'
        f'<td class="num">{s["goals"]}</td>'
        + "".join(f'<td class="num">{s["types"][t]}</td>' for t in GOAL_TYPES)
        + f'<td class="num">{s["cs"] if s["pos"] == "GK" else "&ndash;"}</td>'
        f'<td class="num">{s["ga"] if s["pos"] == "GK" else "&ndash;"}</td></tr>'
        for s in table_rows)
    team_opts = "".join(f'<option value="{tid}">{name}</option>' for tid, name in sorted(team_map.items(), key=lambda x: x[1].lower()))
    status = (f"After {played} round{'s' if played != 1 else ''} played" if played
              else "Season not started &mdash; every player at zero until Round 1 is simulated")

    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Player Stats &middot; {config["league_name"]}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;700;800&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{{--paper:#eef2ea;--ink:#16201a;--muted:#5b6b5e;--line:#d6decd;--navy:#223a5e;--surface:#f7f9f4;--accent:#b23a2c;--shadow:0 1px 2px rgba(0,0,0,.05),0 8px 24px -16px rgba(0,0,0,.25);}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--paper:#111611;--ink:#e7ece1;--muted:#93a091;--line:#2a352a;--navy:#4a6693;--surface:#171d17;}}}}
:root[data-theme="dark"]{{--paper:#111611;--ink:#e7ece1;--muted:#93a091;--line:#2a352a;--navy:#4a6693;--surface:#171d17;}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Source Serif 4",Georgia,serif;line-height:1.5;}}
.masthead{{background:var(--navy);color:#eef2ea;padding:34px clamp(16px,4vw,48px) 26px;}}
.masthead-inner{{max-width:1240px;margin:0 auto;}}
.masthead h1{{font-family:"Big Shoulders Display",sans-serif;font-size:clamp(34px,5vw,54px);margin:0;letter-spacing:.02em;}}
.masthead p{{margin:6px 0 0;opacity:.85;font-family:"IBM Plex Mono",monospace;font-size:13px;}}
.wrap{{max-width:1240px;margin:0 auto;padding:26px clamp(16px,4vw,48px) 50px;}}
h2{{font-family:"Big Shoulders Display",sans-serif;font-size:26px;margin:30px 0 12px;letter-spacing:.02em;}}
.status{{display:inline-block;font-family:"IBM Plex Mono",monospace;font-size:12.5px;background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:6px 14px;color:var(--muted);}}
.boards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;}}
.lb{{background:var(--surface);border:1px solid var(--line);border-radius:6px;box-shadow:var(--shadow);padding:14px 16px;}}
.lb h3{{font-family:"Big Shoulders Display",sans-serif;font-size:21px;margin:0 0 8px;color:var(--accent);letter-spacing:.02em;}}
table{{width:100%;border-collapse:collapse;font-size:14px;}}
th{{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap;}}
td{{padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top;}}
td.num,th.num{{text-align:right;font-family:"IBM Plex Mono",monospace;}}
td.rk{{font-family:"IBM Plex Mono",monospace;color:var(--muted);width:24px;}}
td.pos{{font-family:"IBM Plex Mono",monospace;font-size:12.5px;}}
.sub{{display:block;color:var(--muted);font-size:12.5px;}}
.empty-row td{{color:var(--muted);font-style:italic;text-align:center;padding:16px;}}
.filters{{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:4px 0 12px;}}
.filters label{{font-family:"IBM Plex Mono",monospace;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);}}
.filters select{{font-family:inherit;font-size:14px;background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:3px;padding:6px 9px;}}
.table-scroll{{overflow-x:auto;border:1px solid var(--line);border-radius:4px;background:var(--surface);box-shadow:var(--shadow);}}
#all th{{cursor:pointer;user-select:none;}}
#all th:hover{{color:var(--ink);}}
footer{{max-width:1240px;margin:0 auto;padding:0 clamp(16px,4vw,48px) 40px;color:var(--muted);font-size:12.5px;font-family:"IBM Plex Mono",monospace;}}
{NAV_CSS}
</style></head>
<body>
{render_nav("playerstats")}
<div class="masthead"><div class="masthead-inner"><h1>Player Stats</h1>
<p>{config["league_name"]} &middot; updated automatically after every simulated round</p></div></div>
<div class="wrap">
<span class="status">{status}</span>
<h2>Leaderboards</h2>
<div class="boards">{boards}</div>
<h2>All Players</h2>
<div class="filters"><label for="fTeam">Team</label><select id="fTeam"><option value="">All teams</option>{team_opts}</select>
<label for="fPos">Position</label><select id="fPos"><option value="">All</option><option>GK</option><option>DF</option><option>MF</option><option>FW</option></select></div>
<div class="table-scroll"><table id="all"><thead><tr><th>Player</th><th>Team</th><th>Pos</th><th class="num">OVR</th><th class="num">Starts</th><th class="num">Goals</th>
<th class="num">Strike</th><th class="num">Header</th><th class="num">Corner</th><th class="num">Penalty</th><th class="num">Free kick</th><th class="num">Clean sheets</th><th class="num">Goals against</th></tr></thead>
<tbody>{data_rows}</tbody></table></div>
</div>
<footer>Goals, starts and clean sheets are counted from each simulated match's recorded starting XI and goal events. Click a column header to sort.</footer>
<script>
(function(){{
  var t=document.getElementById('all'), tb=t.tBodies[0], fT=document.getElementById('fTeam'), fP=document.getElementById('fPos');
  function filter(){{ [].forEach.call(tb.rows,function(r){{ r.style.display=((!fT.value||r.dataset.team===fT.value)&&(!fP.value||r.dataset.pos===fP.value))?'':'none'; }}); }}
  fT.onchange=filter; fP.onchange=filter;
  var dir={{}};
  [].forEach.call(t.tHead.rows[0].cells,function(th,i){{ th.onclick=function(){{
    dir[i]=!dir[i]; var num=th.classList.contains('num');
    var rows=[].slice.call(tb.rows).sort(function(a,b){{ var x=a.cells[i].textContent, y=b.cells[i].textContent;
      if(num){{ x=parseFloat(x)||0; y=parseFloat(y)||0; return dir[i]? y-x : x-y; }} return dir[i]? x.localeCompare(y) : y.localeCompare(x); }});
    rows.forEach(function(r){{ tb.appendChild(r); }});
  }}; }});
}})();
</script>
</body></html>'''


if __name__ == "__main__":
    config = load_json("league_config.json")
    players = render_dashboard.load_players()
    path = os.path.join(BASE, "data", "matches.json")
    matches = load_json("matches.json") if os.path.exists(path) else []
    html = render(config, players, matches)
    out_dir = os.path.join(BASE, "player-stats-site")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(html)
    print(f"Rendered -> {out_dir}/index.html")
