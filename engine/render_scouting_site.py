"""
Renders scouting-site/index.html -- the Scouting Report page, right next
to Draft Board in the nav (2026-09-22, instructor request).

The problem it answers: a team never knows an opponent's formation or
strategy for THIS week's match before it's played -- lineups are
submitted independently and simultaneously. But two things ARE public
year-round and give a genuine, non-guessy basis for a weekly decision:

  1. Roster composition -- who a team drafted, and at what ATT/DEF,
     has been public since Draft Day. That alone tells you what
     formations are even feasible for them and their rough
     Attack/Defense skew, no matter which exact formation they pick.
  2. Match history -- once a team has played, resolve_round.py already
     records the formation/strategy they actually used that round in
     data/matches.json (home_formation/away_formation/home_strategy/
     away_strategy). This page is the first place that data is shown
     as readable text -- real "game tape" scouting, same as a real
     analyst studies past matches, not a prediction of next week's call.

Deliberately NOT a "play X because they'll play Y" recommendation
engine -- it hands students the same two inputs a real scout would
have and lets the weekly formation/strategy call stay their own
decision (see the Rulebook's Decision Rationale requirement).

The "Scouting Attack" / "Scouting Defense" composite score reuses
engine/simulate.py's EXACT team_ratings() weighting (ATTACK_WEIGHT /
DEFENSE_WEIGHT / GK_DEFENSE_WEIGHT), applied to each team's whole-roster
position-group averages under Balanced strategy -- clearly labeled as
an estimate, not their actual weekly number, since nobody's starting
XI or formation is known in advance.

Run after any draft pick, round resolution, or player condition change,
then republish.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from site_nav import NAV_CSS, render_nav
from simulate import ATTACK_WEIGHT, DEFENSE_WEIGHT, GK_DEFENSE_WEIGHT, FORMATIONS
import render_dashboard

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def avg(field, players):
    if not players:
        return None
    return sum(p[field] for p in players) / len(players)


def scouting_scores(roster):
    """Same weighting as simulate.py's team_ratings(), applied to
    whole-roster position-group averages (not a guessed starting XI)
    under Balanced strategy -- an estimate of a team's baseline
    Attack/Defense profile, not a prediction of any specific week."""
    by_pos = {"GK": [], "DF": [], "MF": [], "FW": []}
    for p in roster:
        by_pos.setdefault(p["position"], []).append(p)

    attack = 0.0
    defense = 0.0
    for pos in ("DF", "MF", "FW"):
        a = avg("att", by_pos.get(pos, [])) or 0
        d = avg("def", by_pos.get(pos, [])) or 0
        attack += a * ATTACK_WEIGHT[pos]
        defense += d * DEFENSE_WEIGHT[pos]
    gk_def = avg("def", by_pos.get("GK", [])) or 0
    defense += gk_def * GK_DEFENSE_WEIGHT
    defense = defense / 1.25

    return round(attack, 1), round(defense, 1), by_pos


def team_history(team_id, matches, team_map):
    rows = []
    record = {"W": 0, "D": 0, "L": 0}
    formation_tally = {}
    strategy_tally = {}
    for m in sorted(matches, key=lambda m: m["round"]):
        is_home = m["home_id"] == team_id
        is_away = m["away_id"] == team_id
        if not (is_home or is_away):
            continue
        opp_id = m["away_id"] if is_home else m["home_id"]
        own_goals = m["home_goals"] if is_home else m["away_goals"]
        opp_goals = m["away_goals"] if is_home else m["home_goals"]
        formation = m["home_formation"] if is_home else m["away_formation"]
        strategy = m["home_strategy"] if is_home else m["away_strategy"]
        outcome = "W" if own_goals > opp_goals else ("L" if own_goals < opp_goals else "D")
        record[outcome] += 1
        formation_tally[formation] = formation_tally.get(formation, 0) + 1
        strategy_tally[strategy] = strategy_tally.get(strategy, 0) + 1
        rows.append({
            "round": m["round"], "venue": "Home" if is_home else "Away",
            "opponent": team_map.get(opp_id, f"Team {opp_id}"),
            "formation": formation, "strategy": strategy,
            "score": f"{own_goals}-{opp_goals}", "outcome": outcome,
        })
    top_formation = max(formation_tally, key=formation_tally.get) if formation_tally else None
    top_strategy = max(strategy_tally, key=strategy_tally.get) if strategy_tally else None
    return rows, record, top_formation, top_strategy


def render(config, players, matches):
    team_map = {t["team_id"]: t["name"] for t in config["teams"]}
    team_ids = list(team_map.keys())

    rosters = {tid: [] for tid in team_ids}
    for p in players:
        if p["team_id"] not in ("", None):
            rosters[int(p["team_id"])].append(p)

    team_reports = []
    for tid in team_ids:
        roster = rosters[tid]
        attack, defense, by_pos = scouting_scores(roster)
        history, record, top_formation, top_strategy = team_history(tid, matches, team_map)
        team_reports.append({
            "team_id": tid, "name": team_map[tid],
            "attack": attack, "defense": defense,
            "df_att": round(avg("att", by_pos.get("DF", [])) or 0, 1),
            "df_def": round(avg("def", by_pos.get("DF", [])) or 0, 1),
            "mf_att": round(avg("att", by_pos.get("MF", [])) or 0, 1),
            "mf_def": round(avg("def", by_pos.get("MF", [])) or 0, 1),
            "fw_att": round(avg("att", by_pos.get("FW", [])) or 0, 1),
            "fw_def": round(avg("def", by_pos.get("FW", [])) or 0, 1),
            "gk_def": round(avg("def", by_pos.get("GK", [])) or 0, 1),
            "roster_size": len(roster),
            "record": f'{record["W"]}-{record["D"]}-{record["L"]}',
            "played": sum(record.values()),
            "top_formation": top_formation or "—",
            "top_strategy": top_strategy or "—",
            "history": history,
        })

    summary_json = json.dumps(team_reports)
    formation_list_json = json.dumps(list(FORMATIONS.keys()))

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scouting Report</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;700;800&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{{
  --paper:#eef2ea; --ink:#16201a; --muted:#5b6b5e; --line:#d6decd;
  --accent:#b8811f; --accent-ink:#3a2a08; --pitch:#2f5233; --pitch-ink:#eef2ea;
  --navy:#223a5e; --navy-ink:#eef2ea; --surface:#f7f9f4;
  --win:#2f7a4f; --draw:#a5791f; --loss:#b4472f;
  --shadow: 0 1px 2px rgba(22,32,26,.06), 0 4px 14px rgba(22,32,26,.05);
}}
@media (prefers-color-scheme: dark){{
  :root:not([data-theme="light"]){{
    --paper:#111611; --ink:#e7ece1; --muted:#93a091; --line:#2a352a;
    --accent:#d9a44a; --accent-ink:#1c1404; --pitch:#4c7a52; --pitch-ink:#0d130e;
    --navy:#4a6693; --navy-ink:#0d130e; --surface:#171d17;
    --win:#4fae76; --draw:#d1a13e; --loss:#e07a5c;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 4px 18px rgba(0,0,0,.35);
  }}
}}
:root[data-theme="dark"]{{
  --paper:#111611; --ink:#e7ece1; --muted:#93a091; --line:#2a352a;
  --accent:#d9a44a; --accent-ink:#1c1404; --pitch:#4c7a52; --pitch-ink:#0d130e;
  --navy:#4a6693; --navy-ink:#0d130e; --surface:#171d17;
  --win:#4fae76; --draw:#d1a13e; --loss:#e07a5c;
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
section{{margin-bottom:40px;}}
.section-head{{display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px solid var(--ink);padding-bottom:6px;margin-bottom:16px;flex-wrap:wrap;gap:8px;}}
.section-head h2{{font-size:22px;}}
.section-note{{color:var(--muted);font-size:13px;font-family:"IBM Plex Mono",monospace;}}

.how-it-works{{background:var(--surface);border:1px solid var(--line);border-radius:4px;box-shadow:var(--shadow);padding:18px 20px;font-size:14.5px;}}
.how-it-works p{{margin:0 0 10px;}}
.how-it-works p:last-child{{margin-bottom:0;}}

.table-scroll{{overflow-x:auto;border:1px solid var(--line);border-radius:3px;background:var(--surface);box-shadow:var(--shadow);}}
table{{width:100%;border-collapse:collapse;font-size:14px;}}
thead th{{position:sticky;top:0;background:var(--navy);color:var(--navy-ink);text-align:left;padding:9px 10px;font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;cursor:pointer;white-space:nowrap;}}
thead th.num{{text-align:right;}}
tbody td{{padding:8px 10px;border-top:1px solid var(--line);}}
tbody tr:hover{{background:color-mix(in srgb, var(--accent) 10%, transparent);}}
.empty-row td{{color:var(--muted);font-style:italic;text-align:center;padding:18px;}}
.outcome{{font-family:"IBM Plex Mono",monospace;font-weight:700;font-size:11px;padding:2px 7px;border-radius:10px;}}
.outcome-W{{background:color-mix(in srgb, var(--win) 20%, transparent);color:var(--win);}}
.outcome-D{{background:color-mix(in srgb, var(--draw) 20%, transparent);color:var(--draw);}}
.outcome-L{{background:color-mix(in srgb, var(--loss) 20%, transparent);color:var(--loss);}}

.picker{{background:var(--surface);border:1px solid var(--line);border-radius:4px;box-shadow:var(--shadow);padding:18px 20px;margin-bottom:16px;display:flex;gap:14px;align-items:center;flex-wrap:wrap;}}
.picker label{{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);}}
.picker select{{font-family:"Source Serif 4",serif;font-size:14px;background:var(--paper);color:var(--ink);border:1px solid var(--line);border-radius:2px;padding:7px 10px;}}
.tendency-chips{{display:flex;gap:16px;flex-wrap:wrap;margin-left:auto;font-family:"IBM Plex Mono",monospace;font-size:12.5px;color:var(--muted);}}
.tendency-chips b{{color:var(--ink);}}

footer{{max-width:1240px;margin:0 auto;padding:0 clamp(16px,4vw,48px) 50px;color:var(--muted);font-size:12.5px;font-family:"IBM Plex Mono",monospace;}}
{NAV_CSS}
</style>
</head>
<body>
{render_nav("scouting")}
<div class="masthead">
  <div class="masthead-inner">
    <h1>Scouting Report</h1>
    <p>{config["league_name"]} &middot; you never know this week's opponent formation in advance &mdash; here's what you DO know</p>
  </div>
</div>

<div class="wrap">
  <section>
    <div class="section-head"><h2>How To Use This</h2></div>
    <div class="how-it-works">
      <p>Every lineup is submitted independently the same week it's played, so you can never see an opponent's exact
      formation or strategy before your own match. Two things ARE public the whole season, though, and give a real basis
      for your weekly call without guessing:</p>
      <p><b>Roster.</b> Every team's drafted players, and their ATT/DEF, have been public since Draft Day. That alone
      tells you what formations are even realistic for an opponent, and roughly how their Attack and Defense compare to
      yours &mdash; no matter which exact formation they end up picking.</p>
      <p><b>Game tape.</b> Once a team has played, the formation and strategy they actually used that round is a matter
      of record below &mdash; scout their tendencies the way a real analyst studies past matches, not a guess about next week.</p>
      <p style="color:var(--muted);">This page does not tell you what to play. Scouting Attack/Defense below is an
      estimate from each team's whole-roster averages under a neutral Balanced strategy &mdash; not their actual number
      any given week, since nobody's exact starting XI or formation is known ahead of time. Your formation, strategy, and
      the rationale behind them are still your call to make and defend.</p>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2>League Scouting Board</h2>
      <span class="section-note" id="summary-count">{len(team_reports)} teams &middot; click a column to sort</span>
    </div>
    <div class="table-scroll">
      <table id="summary-table">
        <thead>
          <tr>
            <th data-key="name">Team</th>
            <th data-key="attack" class="num">Scouting ATT</th>
            <th data-key="defense" class="num">Scouting DEF</th>
            <th data-key="df_att" class="num">DF avg</th>
            <th data-key="mf_att" class="num">MF avg</th>
            <th data-key="fw_att" class="num">FW avg</th>
            <th data-key="roster_size" class="num">Roster</th>
            <th data-key="top_formation">Most-used Formation</th>
            <th data-key="top_strategy">Most-used Strategy</th>
            <th data-key="played" class="num">Record</th>
          </tr>
        </thead>
        <tbody id="summary-body"></tbody>
      </table>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2>Team Game Tape</h2>
      <span class="section-note">round-by-round formation and strategy history, one team at a time</span>
    </div>
    <div class="picker">
      <label for="team-select">Team</label>
      <select id="team-select"></select>
      <div class="tendency-chips" id="tendency-chips"></div>
    </div>
    <div class="table-scroll">
      <table>
        <thead>
          <tr><th>Round</th><th>Venue</th><th>Opponent</th><th>Formation</th><th>Strategy</th><th class="num">Score</th><th>Result</th></tr>
        </thead>
        <tbody id="history-body"></tbody>
      </table>
    </div>
  </section>
</div>

<footer>{config["league_name"]} &middot; scouting report &mdash; roster is always public, game tape builds as the season plays out</footer>

<script>
const TEAMS = {summary_json};
let sortKey = "attack", sortDir = -1;

function fmtNum(v) {{ return (v === null || v === undefined) ? "—" : v; }}

function renderSummary() {{
  const rows = [...TEAMS].sort((a, b) => {{
    let av = a[sortKey], bv = b[sortKey];
    if (typeof av === "string") {{ av = av.toLowerCase(); bv = String(bv).toLowerCase(); }}
    return (av > bv ? 1 : av < bv ? -1 : 0) * sortDir;
  }});
  document.getElementById("summary-body").innerHTML = rows.map(t => `
    <tr>
      <td>${{t.name}}</td>
      <td class="num">${{fmtNum(t.attack)}}</td>
      <td class="num">${{fmtNum(t.defense)}}</td>
      <td class="num">${{fmtNum(t.df_att)}}</td>
      <td class="num">${{fmtNum(t.mf_att)}}</td>
      <td class="num">${{fmtNum(t.fw_att)}}</td>
      <td class="num">${{t.roster_size}}</td>
      <td>${{t.top_formation}}</td>
      <td>${{t.top_strategy}}</td>
      <td class="num">${{t.played ? t.record : "no matches yet"}}</td>
    </tr>`).join("");
}}

document.querySelectorAll("#summary-table thead th[data-key]").forEach(th => {{
  th.addEventListener("click", () => {{
    const key = th.dataset.key;
    if (sortKey === key) {{ sortDir *= -1; }} else {{ sortKey = key; sortDir = -1; }}
    renderSummary();
  }});
}});

renderSummary();

const teamSelect = document.getElementById("team-select");
teamSelect.innerHTML = TEAMS.map(t => `<option value="${{t.team_id}}">${{t.name}}</option>`).join("");

function renderHistory() {{
  const team = TEAMS.find(t => String(t.team_id) === teamSelect.value);
  const body = document.getElementById("history-body");
  const chips = document.getElementById("tendency-chips");
  if (!team) return;

  chips.innerHTML = `<span>Record: <b>${{team.played ? team.record : "no matches yet"}}</b></span>
    <span>Most-used formation: <b>${{team.top_formation}}</b></span>
    <span>Most-used strategy: <b>${{team.top_strategy}}</b></span>`;

  if (team.history.length === 0) {{
    body.innerHTML = '<tr class="empty-row"><td colspan="7">No matches played yet this season.</td></tr>';
    return;
  }}
  body.innerHTML = team.history.map(h => `
    <tr>
      <td class="num mono">${{h.round}}</td>
      <td>${{h.venue}}</td>
      <td>${{h.opponent}}</td>
      <td class="mono">${{h.formation}}</td>
      <td>${{h.strategy}}</td>
      <td class="num mono">${{h.score}}</td>
      <td><span class="outcome outcome-${{h.outcome}}">${{h.outcome}}</span></td>
    </tr>`).join("");
}}

teamSelect.addEventListener("change", renderHistory);
renderHistory();
</script>
</body>
</html>'''


if __name__ == "__main__":
    config = load_json("league_config.json")
    players = render_dashboard.load_players()
    matches_path = os.path.join(BASE, "data", "matches.json")
    matches = load_json("matches.json") if os.path.exists(matches_path) else []
    html = render(config, players, matches)
    out_dir = os.path.join(BASE, "scouting-site")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Rendered -> {out_path}")
