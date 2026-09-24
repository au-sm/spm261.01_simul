"""
Renders schedule-site/index.html -- the standalone Schedule page: every
round's fixtures and date, in one place, separate from the Rulebook
(which only lists the calendar's match DAYS, not who actually plays
whom) and separate from Matchday Replay (which only works once a match
has a real result to animate).

Reads data/schedule.json (every round's fixtures -- home_id/away_id,
generated once by engine/generate_schedule.py), data/season_calendar.json
(which date each round falls on), data/matches.json (final scores for
whatever's already been resolved -- permanent once written, per
resolve_round.py's guard), and data/league_config.json (team names/owners).

Run after any resolve_round.py call, or after season_calendar.json /
schedule.json changes, then republish.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from site_nav import GH_BASE, NAV_CSS, render_nav

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def render(config, schedule, calendar, matches):
    name_by_id = {t["team_id"]: t["name"] for t in config["teams"]}
    owner_by_id = {t["team_id"]: t.get("owner", "") for t in config["teams"]}

    def label(tid):
        owner = owner_by_id.get(tid, "")
        return name_by_id.get(tid, f"Team {tid}") + (f" ({owner})" if owner else "")

    date_by_round = {}
    for entry in calendar.get("match_day_schedule", []):
        for r in entry["rounds"]:
            date_by_round[r] = entry["date"]

    result_by_fixture = {}
    for m in matches:
        if m.get("stage", "regular") != "regular":
            continue
        key = (m["round"], m["home_id"], m["away_id"])
        result_by_fixture[key] = m

    today = None
    import datetime
    today = datetime.date.today().isoformat()

    next_round_banner = ""
    round_blocks = []
    found_next = False
    for round_entry in schedule:
        rnum = round_entry["round"]
        date = date_by_round.get(rnum, "TBD")
        is_resolved = any(
            (rnum, fx["home_id"], fx["away_id"]) in result_by_fixture
            for fx in round_entry["fixtures"]
        )
        is_next = (not is_resolved) and (not found_next) and (date == "TBD" or date >= today)
        if is_next:
            found_next = True
            next_round_banner = (
                f'<p class="schedule-cta"><strong>Next up: Round {rnum}</strong> on '
                f'<strong>{date}</strong> &mdash; <a href="{GH_BASE}/dashboard/">submit your Weekly Lineup</a> '
                f'before then if you haven\'t already. <a href="{GH_BASE}/dashboard/" class="schedule-cta-btn">Go to Dashboard &rarr;</a></p>'
            )

        rows = []
        for fx in round_entry["fixtures"]:
            h, a = fx["home_id"], fx["away_id"]
            result = result_by_fixture.get((rnum, h, a))
            if result:
                score = f'{result["home_goals"]}&ndash;{result["away_goals"]}'
                status_cls = "status-complete"
                status = f'<a href="{GH_BASE}/matchday-replay/">{score} &middot; Replay</a>'
            else:
                status_cls = "status-pending"
                status = "upcoming" if (date == "TBD" or date >= today) else "pending"
            rows.append(
                f'<tr><td>{label(h)}</td><td class="num">vs</td><td>{label(a)}</td>'
                f'<td class="num {status_cls}">{status}</td></tr>'
            )
        rows_html = "".join(rows)

        badge = "complete" if is_resolved else ("next" if is_next else "upcoming")
        round_blocks.append(f'''
        <div class="round-block">
          <div class="round-head">
            <h3>Round {rnum} <span class="round-badge round-badge-{badge}">{badge}</span></h3>
            <span class="round-date">{date}</span>
          </div>
          <table><thead><tr><th>Home</th><th></th><th>Away</th><th class="num">Result</th></tr></thead>
          <tbody>{rows_html}</tbody></table>
        </div>''')
    rounds_html = "".join(round_blocks)

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Schedule</title>
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

.schedule-cta{{background:var(--surface);border:1px solid var(--accent);border-radius:4px;padding:12px 16px;
  display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;margin:0 0 24px;font-size:14px;}}
.schedule-cta-btn{{flex-shrink:0;font-family:"IBM Plex Mono",monospace;font-size:12px;font-weight:600;letter-spacing:.03em;
  text-transform:uppercase;background:var(--accent);color:var(--accent-ink);border-radius:3px;padding:8px 14px;
  text-decoration:none;white-space:nowrap;}}
.schedule-cta-btn:hover{{opacity:.85;}}

.round-block{{margin-bottom:22px;}}
.round-head{{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap;
  border-bottom:2px solid var(--ink);padding-bottom:5px;margin-bottom:8px;}}
.round-head h3{{font-size:17px;display:flex;align-items:center;gap:10px;}}
.round-date{{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--muted);}}
.round-badge{{font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:.04em;text-transform:uppercase;
  padding:2px 8px;border-radius:10px;font-weight:600;}}
.round-badge-complete{{background:var(--win);color:var(--pitch-ink);}}
.round-badge-next{{background:var(--accent);color:var(--accent-ink);}}
.round-badge-upcoming{{background:var(--paper);color:var(--muted);border:1px solid var(--line);}}

table{{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--surface);border:1px solid var(--line);
  border-radius:3px;box-shadow:var(--shadow);margin-bottom:0;}}
thead th{{background:var(--navy);color:var(--navy-ink);text-align:left;padding:8px 10px;font-family:"IBM Plex Mono",monospace;
  font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;}}
thead th.num{{text-align:right;}}
tbody td{{padding:6px 10px;border-top:1px solid var(--line);}}
.status-complete a{{color:var(--win);font-weight:600;text-decoration:none;}}
.status-complete a:hover{{text-decoration:underline;}}
.status-pending{{color:var(--muted);}}

.table-scroll{{overflow-x:auto;}}

footer{{max-width:1180px;margin:0 auto;padding:0 clamp(16px,4vw,48px) 50px;color:var(--muted);font-size:12px;font-family:"IBM Plex Mono",monospace;}}
{NAV_CSS}
</style>
</head>
<body>
{render_nav("schedule")}
<div class="masthead">
  <div class="masthead-inner">
    <h1>Schedule</h1>
    <p>{config["league_name"]} &middot; every round's fixtures and date, in one place</p>
  </div>
</div>

<div class="wrap">
  {next_round_banner}
  {rounds_html}
</div>

<footer>{config["league_name"]} &middot; results are permanent once resolved &mdash; see the Rulebook for how match days are scheduled</footer>
</body>
</html>'''


if __name__ == "__main__":
    config = load_json("league_config.json")
    schedule = load_json("schedule.json")
    calendar = load_json("season_calendar.json")
    matches = load_json("matches.json")
    html = render(config, schedule, calendar, matches)
    out_dir = os.path.join(BASE, "schedule-site")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Rendered -> {out_path}")
