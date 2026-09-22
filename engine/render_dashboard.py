"""
Renders dashboard/index.html from the current contents of data/players.csv,
league_config.json, deals.json, and matches.json.

Run this after ANY state change -- a draft pick, a resolved round, an
approved trade, a signed sponsorship deal -- then republish
dashboard/index.html as the artifact. This script is the single source
of truth for the dashboard's HTML; never hand-edit the published page,
edit the data files and re-render.
"""
import csv
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from simulate import Standings, FORMATIONS
from player_condition import conditions_for_round, INJURED_LABEL
from scorecard import WEIGHTS as SCORECARD_WEIGHTS
from site_nav import NAV_CSS, render_nav

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))



def load_players():
    with open(os.path.join(BASE, "data", "players.csv")) as f:
        rows = list(csv.DictReader(f))
    for p in rows:
        for k in ("age", "att", "def", "pace", "phy", "ovr", "star_power", "salary"):
            p[k] = int(p[k])
    return rows


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def build_standings(matches, team_ids):
    st = Standings(team_ids)
    for m in matches:
        st.record(m["home_id"], m["away_id"], m["home_goals"], m["away_goals"])
    return st.ranked()


def money(n):
    if n >= 1_000_000:
        return f"${n/1_000_000:.1f}M".replace(".0M", "M")
    return f"${n/1000:.0f}K"


def hash_pin(pin):
    """Simple djb2-style hash so a team's PIN isn't sitting in plaintext in
    the page's view-source -- NOT cryptographic security (this is a static
    public page, there's no real backend to guard), just enough that a
    student can't just read every team's PIN off the screen. The actual
    enforcement that matters is server-side, in resolve_round.py, which
    checks the real PIN value directly. Must match the JS hashPin() below
    exactly, bit for bit."""
    h = 5381
    for c in pin:
        h = ((h << 5) + h + ord(c)) & 0xFFFFFFFF
    return h


def render(players, config, deals, matches, schedule=None, calendar=None, injuries=None):
    team_map = {t["team_id"]: t for t in config["teams"]}
    team_ids = list(team_map.keys())

    rosters = {tid: [] for tid in team_ids}
    free_agents = []
    for p in players:
        if p["team_id"] not in ("", None):
            rosters[int(p["team_id"])].append(p)
        else:
            free_agents.append(p)

    standings_rows = build_standings(matches, team_ids) if matches else [
        (tid, {"P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "PTS": 0}) for tid in team_ids
    ]

    phase = config.get("phase", "pre-draft")
    phase_label = {
        "pre-draft": "PRE-DRAFT",
        "draft": "DRAFT DAY",
        "season": f"ROUND {config.get('current_round', 0)}",
        "offseason": "OFF-SEASON",
    }.get(phase, phase.upper())

    draft_pool = free_agents if phase in ("pre-draft", "draft") else free_agents
    draft_pool_sorted = sorted(draft_pool, key=lambda p: -p["ovr"])

    players_json = json.dumps(draft_pool_sorted)

    # --- data for the in-page lineup builder (JS reads this; actual submission
    #     still lands in the Google Form -- see forms/google_form_specs.md) ---
    # A match day can carry MORE THAN ONE round (a doubleheader -- see
    # data/season_calendar.json -> match_day_schedule), each against a
    # DIFFERENT opponent, so the builder must be able to show more than one
    # fixture per team, not just the single next round.
    schedule = schedule or []
    completed = config.get("current_round", 0)
    upcoming_rounds = next(
        (d["rounds"] for d in calendar.get("match_day_schedule", []) if min(d["rounds"]) > completed),
        [completed + 1],
    ) if calendar else [completed + 1]

    fixtures_by_team = {tid: [] for tid in team_ids}
    for rnd in upcoming_rounds:
        round_fixtures = next((r["fixtures"] for r in schedule if r["round"] == rnd), [])
        for fx in round_fixtures:
            fixtures_by_team[fx["home_id"]].append(
                {"round": rnd, "is_home": True, "opponent": team_map[fx["away_id"]]["name"]})
            fixtures_by_team[fx["away_id"]].append(
                {"round": rnd, "is_home": False, "opponent": team_map[fx["home_id"]]["name"]})

    round_label = f"Round {upcoming_rounds[0]}" if len(upcoming_rounds) == 1 \
        else f"Rounds {upcoming_rounds[0]}-{upcoming_rounds[-1]} (doubleheader)"

    # --- weekly player condition, for the NEXT round teams are about to
    # submit a lineup for. A doubleheader match day covers 2 rounds, but
    # showing just the nearer one keeps the roster table readable --
    # generate_weekly_conditions.py --round N covers any single round in
    # full if a team needs the second round's numbers too. ---
    condition_round = upcoming_rounds[0]
    season_seed = config.get("season_seed", 2026)
    _cond_mult_by_id, condition_detail_by_id = conditions_for_round(
        season_seed, condition_round, players, injuries or {}
    )
    CONDITION_CSS = {
        "Excellent": "cond-excellent", "Good": "cond-good", "Average": "cond-average",
        "Below Average": "cond-below", "Poor": "cond-poor", INJURED_LABEL: "cond-injured",
    }

    builder_teams = [
        {
            "team_id": tid,
            "name": team_map[tid]["name"],
            "owner": team_map[tid].get("owner", ""),
            "pin_hash": hash_pin(team_map[tid]["pin"]) if team_map[tid].get("pin") else None,
            "roster": [
                {"player_id": p["player_id"], "name": p["name"], "position": p["position"],
                 "ovr": p["ovr"], "salary": p["salary"]}
                for p in sorted(rosters[tid], key=lambda p: (p["position"], -p["ovr"]))
            ],
            "fixtures": fixtures_by_team.get(tid, []),
        }
        for tid in team_ids
    ]
    builder_teams_json = json.dumps(builder_teams)
    formations_json = json.dumps(FORMATIONS)

    # --- team roster cards ---
    team_cards = []
    for tid in team_ids:
        t = team_map[tid]
        roster = sorted(rosters[tid], key=lambda p: (p["position"], -p["ovr"]))
        drafted_count = len(roster)
        cap_used = sum(p["salary"] for p in roster)
        cap = config.get("salary_cap", 0)
        st_row = next((r for tid2, r in standings_rows if tid2 == tid), None)
        def cond_cell(p):
            tier, mult, injured_until = condition_detail_by_id.get(p["player_id"], ("Average", 1.0, None))
            css = CONDITION_CSS.get(tier, "cond-average")
            title = f"out through round {injured_until}" if injured_until else f"{mult:.2f}x"
            return f'<span class="cond-badge {css}" title="{title}">{tier}</span>'

        rows_html = "".join(
            f'<tr><td class="pos pos-{p["position"]}">{p["position"]}</td>'
            f'<td>{p["name"]}</td><td class="num">{p["ovr"]}</td>'
            f'<td class="num">{money(p["salary"])}</td>'
            f'<td class="cond-col">{cond_cell(p)}</td></tr>'
            for p in roster
        ) or '<tr class="empty-row"><td colspan="5">No players drafted yet</td></tr>'
        record = f'{st_row["W"]}-{st_row["D"]}-{st_row["L"]}' if st_row else "0-0-0"
        pts = st_row["PTS"] if st_row else 0
        team_cards.append(f'''
        <article class="team-card" data-team="{tid}">
          <header class="team-card-head">
            <h3>{t["name"]}</h3>
            <span class="record">{record} &middot; {pts} PTS</span>
          </header>
          <p class="owner">{"Owner: " + t["owner"] if t.get("owner") else "Owner: unassigned"}</p>
          <div class="cap-bar">
            <div class="cap-bar-fill" style="width:{min(100, round(cap_used/cap*100)) if cap else 0}%"></div>
          </div>
          <p class="cap-label"><span class="mono">{money(cap_used)}</span> / <span class="mono">{money(cap)}</span> cap &middot; {drafted_count}/{config.get("roster_size","-")} roster</p>
          <p class="cond-round-label">Condition shown for Round {condition_round}</p>
          <table class="roster-table">
            <thead><tr><th>Pos</th><th>Player</th><th class="num">OVR</th><th class="num">Salary</th><th>Cond</th></tr></thead>
            <tbody>{rows_html}</tbody>
          </table>
        </article>''')
    team_cards_html = "\n".join(team_cards)

    # --- standings table, with the playoff qualification line marked ---
    n_playoff = config.get("playoff_teams", 6)
    standings_rows_html = []
    for i, (tid, r) in enumerate(standings_rows):
        qualifying = i < n_playoff
        standings_rows_html.append(
            f'<tr class="{"qualifier" if qualifying else ""}"><td class="rank">{i+1}</td><td>{team_map[tid]["name"]}</td>'
            f'<td class="num">{r["P"]}</td><td class="num">{r["W"]}</td><td class="num">{r["D"]}</td>'
            f'<td class="num">{r["L"]}</td><td class="num">{r["GF"]}</td><td class="num">{r["GA"]}</td>'
            f'<td class="num">{r["GF"]-r["GA"]:+d}</td><td class="num pts">{r["PTS"]}</td></tr>'
        )
        if i == n_playoff - 1 and i + 1 < len(standings_rows):
            standings_rows_html.append('<tr class="cutoff-row"><td colspan="10">Playoff qualification line</td></tr>')
    standings_html = "".join(standings_rows_html)

    po = deals["playoffs"]
    qualification_bonus = po["qualification_bonus"]

    # --- sponsorship: the full marketplace, negotiation, and live signings
    #     board live on their own site (rendered by render_sponsorship_site.py)
    #     -- this dashboard just points to it, rather than duplicating data it
    #     doesn't load (team_finances.json is that site's job to read).
    n_sponsor_categories = len(deals["sponsorship_categories"])
    sponsor_brand_count = sum(len(c["brands"]) for c in deals["sponsorship_categories"])

    tv = deals["tv_deal_formula"]

    formation_rows = "".join(
        f'<tr><td class="mono">{name}</td><td class="num">{c["GK"]}</td><td class="num">{c["DF"]}</td>'
        f'<td class="num">{c["MF"]}</td><td class="num">{c["FW"]}</td></tr>'
        for name, c in FORMATIONS.items()
    )

    html = f'''<!doctype html>
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
  --navy:#223a5e; --navy-ink:#eef2ea;
  --win:#2f7a4f; --draw:#a5791f; --loss:#b4472f;
  --surface:#f7f9f4; --shadow: 0 1px 2px rgba(22,32,26,.06), 0 4px 14px rgba(22,32,26,.05);
}}
@media (prefers-color-scheme: dark){{
  :root:not([data-theme="light"]){{
    --paper:#111611; --ink:#e7ece1; --muted:#93a091; --line:#2a352a;
    --accent:#d9a44a; --accent-ink:#1c1404; --pitch:#4c7a52; --pitch-ink:#0d130e;
    --navy:#4a6693; --navy-ink:#0d130e;
    --win:#4fae76; --draw:#d1a13e; --loss:#e07a5c;
    --surface:#171d17; --shadow: 0 1px 2px rgba(0,0,0,.3), 0 4px 18px rgba(0,0,0,.35);
  }}
}}
:root[data-theme="dark"]{{
  --paper:#111611; --ink:#e7ece1; --muted:#93a091; --line:#2a352a;
  --accent:#d9a44a; --accent-ink:#1c1404; --pitch:#4c7a52; --pitch-ink:#0d130e;
  --navy:#4a6693; --navy-ink:#0d130e;
  --win:#4fae76; --draw:#d1a13e; --loss:#e07a5c;
  --surface:#171d17; --shadow: 0 1px 2px rgba(0,0,0,.3), 0 4px 18px rgba(0,0,0,.35);
}}
*{{box-sizing:border-box;}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Source Serif 4",Georgia,serif;line-height:1.5;}}
.mono{{font-family:"IBM Plex Mono",ui-monospace,monospace;}}
h1,h2,h3{{font-family:"Big Shoulders Display",sans-serif;text-transform:uppercase;letter-spacing:.02em;text-wrap:balance;margin:0;}}
.num{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums;text-align:right;}}

.masthead{{background:var(--pitch);color:var(--pitch-ink);padding:28px clamp(16px,4vw,48px);}}
.masthead-inner{{max-width:1240px;margin:0 auto;display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:12px;}}
.masthead h1{{font-size:clamp(28px,4vw,40px);font-weight:800;}}
.masthead .season{{font-family:"IBM Plex Mono",monospace;font-size:13px;opacity:.85;letter-spacing:.05em;}}
.phase-pill{{display:inline-block;background:var(--accent);color:var(--accent-ink);font-family:"IBM Plex Mono",monospace;font-size:12px;font-weight:600;letter-spacing:.08em;padding:5px 12px;border-radius:2px;}}

.wrap{{max-width:1240px;margin:0 auto;padding:32px clamp(16px,4vw,48px) 80px;}}
.layout{{display:grid;grid-template-columns:1fr 320px;gap:32px;align-items:start;}}
@media (max-width:900px){{.layout{{grid-template-columns:1fr;}}}}

section{{margin-bottom:40px;}}
.section-head{{display:flex;align-items:baseline;justify-content:space-between;border-bottom:2px solid var(--ink);padding-bottom:6px;margin-bottom:16px;}}
.section-head h2{{font-size:22px;}}
.section-note{{color:var(--muted);font-size:13px;font-family:"IBM Plex Mono",monospace;}}

/* draft board */
.filter-row{{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap;}}
.filter-btn{{font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.04em;background:var(--surface);border:1px solid var(--line);color:var(--ink);padding:6px 12px;border-radius:2px;cursor:pointer;}}
.filter-btn.active{{background:var(--ink);color:var(--paper);border-color:var(--ink);}}
.table-scroll{{overflow-x:auto;border:1px solid var(--line);border-radius:3px;background:var(--surface);box-shadow:var(--shadow);}}
table{{width:100%;border-collapse:collapse;font-size:14px;}}
thead th{{position:sticky;top:0;background:var(--navy);color:var(--navy-ink);text-align:left;padding:9px 10px;font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;cursor:pointer;white-space:nowrap;}}
thead th.num{{text-align:right;}}
tbody td{{padding:8px 10px;border-top:1px solid var(--line);}}
tbody tr:hover{{background:color-mix(in srgb, var(--accent) 10%, transparent);}}
.pos{{font-family:"IBM Plex Mono",monospace;font-weight:600;font-size:12px;width:1%;white-space:nowrap;}}
.pos-GK{{color:var(--draw);}} .pos-DF{{color:var(--navy);}} .pos-MF{{color:var(--pitch);}} .pos-FW{{color:var(--loss);}}
.star-bar{{display:inline-block;width:48px;height:6px;background:var(--line);border-radius:3px;overflow:hidden;vertical-align:middle;margin-left:6px;}}
.star-bar-fill{{display:block;height:100%;background:var(--accent);}}
.empty-row td{{color:var(--muted);font-style:italic;text-align:center;padding:18px;}}

/* rail cards */
.rail-card{{background:var(--surface);border:1px solid var(--line);border-radius:3px;box-shadow:var(--shadow);padding:16px 18px;margin-bottom:20px;}}
.scorecard-card{{border:1.5px solid var(--accent);}}
.rail-card h3{{font-size:16px;margin-bottom:10px;}}
.rail-card table{{font-size:12.5px;}}
.rail-card thead th{{background:transparent;color:var(--muted);padding:4px 6px;position:static;}}
.rail-card tbody td{{padding:4px 6px;border-top:1px solid var(--line);}}
.strategy-row{{display:flex;justify-content:space-between;font-size:13px;padding:5px 0;border-top:1px solid var(--line);}}
.strategy-row:first-of-type{{border-top:none;}}

.tier-card{{border-left:4px solid var(--accent);padding:10px 12px;margin-bottom:12px;background:var(--paper);border-radius:2px;}}
.tier-card.tier-local{{border-color:var(--muted);}}
.tier-card.tier-national{{border-color:var(--loss);}}
.tier-head{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:5px;}}
.tier-name{{font-family:"Big Shoulders Display",sans-serif;font-weight:700;font-size:15px;text-transform:uppercase;}}
.tier-rev{{font-size:12px;color:var(--accent-ink);background:var(--accent);padding:1px 6px;border-radius:2px;}}
.tier-qual,.tier-clause{{font-size:12.5px;margin:3px 0;color:var(--muted);}}
.tier-qual strong,.tier-clause strong{{color:var(--ink);}}

/* lineup builder */
.builder{{background:var(--surface);border:1px solid var(--line);border-radius:3px;box-shadow:var(--shadow);padding:22px clamp(16px,3vw,30px);margin-bottom:40px;}}
.builder-head{{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px;margin-bottom:16px;}}
.builder-head h2{{font-size:20px;}}
.builder-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:16px;}}
.field label{{display:block;font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin-bottom:5px;}}
.field select, .field textarea{{width:100%;font-family:"Source Serif 4",serif;font-size:14px;background:var(--paper);color:var(--ink);border:1px solid var(--line);border-radius:2px;padding:7px 9px;}}
.field select:focus, .field textarea:focus{{outline:2px solid var(--accent);outline-offset:1px;}}
.lineup-slots{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-bottom:16px;}}
.slot-group h4{{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.06em;color:var(--muted);margin:0 0 6px;}}
.slot-group select{{margin-bottom:6px;}}
.fixture-note{{font-family:"IBM Plex Mono",monospace;font-size:12.5px;background:var(--paper);border:1px solid var(--line);border-radius:2px;padding:8px 12px;margin-bottom:16px;}}
.builder-output textarea{{width:100%;min-height:170px;font-family:"IBM Plex Mono",monospace;font-size:12.5px;background:var(--paper);color:var(--ink);border:1px solid var(--line);border-radius:2px;padding:10px;white-space:pre;}}
.btn{{font-family:"IBM Plex Mono",monospace;font-size:12.5px;font-weight:600;letter-spacing:.04em;background:var(--accent);color:var(--accent-ink);border:none;border-radius:2px;padding:9px 16px;cursor:pointer;}}
.btn:hover{{filter:brightness(1.08);}}
.btn.secondary{{background:transparent;border:1px solid var(--ink);color:var(--ink);}}
.builder-actions{{display:flex;gap:10px;align-items:center;margin-top:10px;flex-wrap:wrap;}}
.builder-msg{{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--loss);}}
.builder-msg.ok{{color:var(--win);}}
.gated-locked{{opacity:.4;pointer-events:none;filter:grayscale(.4);transition:opacity .2s ease,filter .2s ease;}}
#b-pin{{letter-spacing:.3em;font-family:"IBM Plex Mono",monospace;}}

/* teams grid */
.teams-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px;}}
.team-card{{background:var(--surface);border:1px solid var(--line);border-radius:3px;box-shadow:var(--shadow);padding:16px 18px;}}
.team-card-head{{display:flex;justify-content:space-between;align-items:baseline;}}
.team-card-head h3{{font-size:19px;}}
.record{{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--muted);}}
.owner{{font-size:13px;color:var(--muted);margin:4px 0 10px;}}
.cap-bar{{height:6px;background:var(--line);border-radius:3px;overflow:hidden;}}
.cap-bar-fill{{height:100%;background:var(--pitch);}}
.cap-label{{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--muted);margin:5px 0 10px;}}
.roster-table{{font-size:12.5px;}}
.roster-table thead th{{background:transparent;color:var(--muted);position:static;padding:3px 6px;}}
.roster-table tbody td{{padding:3px 6px;}}
.cond-round-label{{font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--muted);letter-spacing:.04em;text-transform:uppercase;margin:0 0 4px;}}
.cond-col{{white-space:nowrap;}}
.cond-badge{{display:inline-block;font-family:"IBM Plex Mono",monospace;font-size:10px;font-weight:600;letter-spacing:.02em;padding:2px 7px;border-radius:10px;}}
.cond-excellent{{background:color-mix(in srgb, var(--win) 22%, transparent);color:var(--win);}}
.cond-good{{background:color-mix(in srgb, var(--win) 12%, transparent);color:var(--win);}}
.cond-average{{background:color-mix(in srgb, var(--muted) 16%, transparent);color:var(--muted);}}
.cond-below{{background:color-mix(in srgb, var(--draw) 16%, transparent);color:var(--draw);}}
.cond-poor{{background:color-mix(in srgb, var(--loss) 16%, transparent);color:var(--loss);}}
.cond-injured{{background:var(--loss);color:var(--pitch-ink);}}

/* playoff qualification line */
tr.qualifier{{background:color-mix(in srgb, var(--pitch) 8%, transparent);}}
tr.cutoff-row td{{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);text-align:center;padding:4px;border-top:2px dashed var(--accent);border-bottom:none;background:var(--paper);}}

/* standings */
.standings-table th.pts, td.pts{{background:color-mix(in srgb, var(--accent) 14%, transparent);font-weight:700;}}
.rank{{font-family:"IBM Plex Mono",monospace;color:var(--muted);}}

footer{{max-width:1240px;margin:0 auto;padding:0 clamp(16px,4vw,48px) 60px;color:var(--muted);font-size:12.5px;font-family:"IBM Plex Mono",monospace;}}
{NAV_CSS}
</style>
</head>
<body>
{render_nav("dashboard")}
<div class="masthead">
  <div class="masthead-inner">
    <div>
      <h1>{config["league_name"]}</h1>
      <div class="season">{config["season_label"]} &middot; {config["n_teams"]} teams &middot; {config["roster_size"]}-man rosters</div>
    </div>
    <span class="phase-pill">{phase_label}</span>
  </div>
</div>

<div class="wrap">
  <div class="builder" id="rename-builder">
    <div class="builder-head">
      <h2>Rename Your Team</h2>
      <span class="section-note">one-time, before Draft Day if possible &mdash; builds your submission, doesn't send it</span>
    </div>
    <div class="builder-grid">
      <div class="field">
        <label for="n-team">Team</label>
        <select id="n-team"></select>
      </div>
      <div class="field">
        <label for="n-pin">Team PIN</label>
        <input type="password" inputmode="numeric" maxlength="4" id="n-pin" placeholder="4-digit PIN">
      </div>
    </div>
    <p class="builder-msg" id="n-pin-status">Enter your team's PIN above to unlock renaming.</p>
    <div id="n-gated" class="gated-locked">
      <div class="field">
        <label for="n-name">New team name</label>
        <input type="text" id="n-name" placeholder="Your real club name" disabled>
      </div>
      <div class="builder-actions">
        <button class="btn" id="n-generate" disabled>Generate Submission Block</button>
        <button class="btn secondary" id="n-copy">Copy</button>
        <span class="builder-msg" id="n-msg"></span>
      </div>
      <div class="builder-output" style="margin-top:12px;">
        <textarea id="n-output" readonly placeholder="Your formatted submission will appear here -- paste it into the Team Name Submission form's fields of the same name."></textarea>
      </div>
    </div>
  </div>

  <div class="builder" id="roster-viewer">
    <div class="builder-head">
      <h2>Your Drafted Roster</h2>
      <span class="section-note">every player you drafted &mdash; not just this week's starters. Pick your team to see it.</span>
    </div>
    <div class="builder-grid" style="grid-template-columns:1fr 1fr;max-width:480px;">
      <div class="field">
        <label for="r-team">Team</label>
        <select id="r-team"></select>
      </div>
      <div class="field">
        <label for="r-pin">Team PIN (to add a player)</label>
        <input type="password" inputmode="numeric" maxlength="4" id="r-pin" placeholder="4-digit PIN">
      </div>
    </div>
    <p class="cap-label" id="r-summary"></p>
    <table class="roster-table" style="width:100%;">
      <thead><tr><th class="num">ID</th><th>Pos</th><th>Player</th><th class="num">OVR</th><th class="num">Salary</th><th></th></tr></thead>
      <tbody id="r-rows"></tbody>
    </table>
    <p class="builder-msg" id="r-pin-status">Enter this team's PIN above to unlock adding a player.</p>
    <div id="r-gated" class="gated-locked">
      <div class="builder-grid" style="grid-template-columns:2fr 1fr;margin-top:10px;">
        <div class="field">
          <label for="r-add-name">Add a player to this roster</label>
          <input type="text" id="r-add-name" placeholder="Player ID (1-399) or exact name" disabled>
        </div>
        <div class="field" style="justify-content:flex-end;display:flex;">
          <button class="btn secondary" id="r-add-btn" style="width:100%;" disabled>Add Player</button>
        </div>
      </div>
      <span class="builder-msg" id="r-add-msg"></span>
    </div>
    <p class="section-note" style="margin-top:10px;">Adding a player only changes THIS BROWSER's view, for recording picks live on Draft Day &mdash; it does not touch data/players.csv and resets if the page reloads. To make it official, still run the real Draft Board / resolve_draft.py pipeline (or a manual roster-entry CSV) so it's saved for every student, not just this screen.</p>
  </div>

  <div class="builder" id="lineup-builder">
    <div class="builder-head">
      <h2>Submit Your Lineup</h2>
      <span class="section-note">{round_label} &middot; builds your submission, doesn't send it &mdash; copy the block below into the Weekly Lineup &amp; Strategy form</span>
    </div>
    <div class="builder-grid">
      <div class="field">
        <label for="b-team">Team</label>
        <select id="b-team"></select>
      </div>
      <div class="field">
        <label for="b-pin">Team PIN</label>
        <input type="password" inputmode="numeric" maxlength="4" id="b-pin" placeholder="4-digit PIN">
      </div>
      <div class="field" id="b-match-field" hidden>
        <label for="b-match">Which match (doubleheader)</label>
        <select id="b-match"></select>
      </div>
      <div class="field">
        <label for="b-formation">Formation</label>
        <select id="b-formation" disabled></select>
      </div>
      <div class="field">
        <label for="b-strategy">Strategy</label>
        <select id="b-strategy" disabled>
          <option>Attacking</option>
          <option selected>Balanced</option>
          <option>Defensive</option>
        </select>
      </div>
      <div class="field" id="b-price-field">
        <label for="b-price">Ticket Price (home only)</label>
        <select id="b-price" disabled>
          <option>Budget</option>
          <option selected>Standard</option>
          <option>Premium</option>
        </select>
      </div>
    </div>
    <p class="builder-msg" id="b-pin-status">Enter your team's PIN above to unlock lineup entry.</p>
    <div id="b-gated" class="gated-locked">
      <div class="fixture-note" id="b-fixture-note"></div>
      <div class="lineup-slots" id="b-slots"></div>
      <div class="field">
        <label for="b-rationale">Decision rationale (2-4 sentences)</label>
        <textarea id="b-rationale" rows="3" placeholder="Why this formation, strategy, and lineup against this opponent?" disabled></textarea>
      </div>
      <div class="builder-actions">
        <button class="btn" id="b-generate" disabled>Generate Submission Block</button>
        <button class="btn secondary" id="b-copy">Copy</button>
        <span class="builder-msg" id="b-msg"></span>
      </div>
      <div class="builder-output" style="margin-top:12px;">
        <textarea id="b-output" readonly placeholder="Your formatted submission will appear here -- paste it into the Google Form fields of the same name."></textarea>
      </div>
    </div>
  </div>

  <div class="layout">
    <main>
      <section id="draft-board">
        <div class="section-head">
          <h2>Draft Board</h2>
          <span class="section-note">{len(draft_pool_sorted)} available &middot; click a column to sort</span>
        </div>
        <div class="filter-row">
          <button class="filter-btn active" data-pos="ALL">All</button>
          <button class="filter-btn" data-pos="GK">GK</button>
          <button class="filter-btn" data-pos="DF">DF</button>
          <button class="filter-btn" data-pos="MF">MF</button>
          <button class="filter-btn" data-pos="FW">FW</button>
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

      <section id="standings">
        <div class="section-head">
          <h2>Standings</h2>
          <span class="section-note">{len(matches)} match{"es" if len(matches)!=1 else ""} played</span>
        </div>
        <div class="table-scroll">
          <table class="standings-table">
            <thead><tr><th></th><th>Team</th><th class="num">P</th><th class="num">W</th><th class="num">D</th><th class="num">L</th><th class="num">GF</th><th class="num">GA</th><th class="num">GD</th><th class="num pts">PTS</th></tr></thead>
            <tbody>{standings_html}</tbody>
          </table>
        </div>
      </section>

      <section id="playoffs">
        <div class="section-head">
          <h2>Playoff Qualification</h2>
          <span class="section-note">top {n_playoff} at season's end &middot; no bracket games &mdash; see Standings above</span>
        </div>
        <p>No playoff bracket is played. The top {n_playoff} teams in the final regular-season standings are recognized as
        Playoff Qualifiers and each receive a flat {money(qualification_bonus)} Qualification Bonus &mdash; not tiered by
        seed, since finishing 1st vs. {n_playoff}th is already rewarded by the standings themselves. The qualification
        line is marked directly in the Standings table above.</p>
      </section>

      <section id="teams">
        <div class="section-head">
          <h2>Front Offices</h2>
          <span class="section-note">rosters &amp; salary cap</span>
        </div>
        <div class="teams-grid">
          {team_cards_html}
        </div>
      </section>
    </main>

    <aside>
      <div class="rail-card">
        <h3>Formations</h3>
        <table>
          <thead><tr><th></th><th class="num">GK</th><th class="num">DF</th><th class="num">MF</th><th class="num">FW</th></tr></thead>
          <tbody>{formation_rows}</tbody>
        </table>
      </div>
      <div class="rail-card">
        <h3>Strategy Effect</h3>
        <div class="strategy-row"><span>Attacking</span><span class="mono">ATT &times;1.08 / DEF &times;0.92</span></div>
        <div class="strategy-row"><span>Balanced</span><span class="mono">no change</span></div>
        <div class="strategy-row"><span>Defensive</span><span class="mono">ATT &times;0.92 / DEF &times;1.08</span></div>
      </div>
      <div class="rail-card">
        <h3>Sponsorship</h3>
        <p class="tier-qual">{sponsor_brand_count} real-brand sponsors across {n_sponsor_categories} required categories &mdash; one signed brand per category, mandatory, sponsors pay you.</p>
        <p class="tier-clause">Full marketplace, live signings, and the negotiation simulator: see the separate Sponsorship Marketplace site.</p>
      </div>
      <div class="rail-card">
        <h3>TV / Broadcast Split</h3>
        <p class="tier-qual">Base: <strong class="mono">{money(tv["base_payment_per_team"])}</strong>/team</p>
        <p class="tier-qual">{tv["standings_bonus"]}</p>
        <p class="tier-qual">{tv["star_power_bonus"]}</p>
        <p class="tier-clause">Split at: {tv["midseason_split_timing"]}</p>
      </div>
      <div class="rail-card">
        <h3>Playoff Qualification</h3>
        <div class="strategy-row"><span>Top {n_playoff} at season's end</span><span class="mono">{money(qualification_bonus)}</span></div>
        <p class="tier-clause">Flat bonus, not tiered by seed &mdash; no bracket games are played. Paid by the league office.</p>
      </div>
      <div class="rail-card">
        <h3>Salary Cap</h3>
        <p class="tier-qual">Starting budget: <strong class="mono">{money(config["starting_budget"])}</strong></p>
        <p class="tier-qual">Hard cap: <strong class="mono">{money(config["salary_cap"])}</strong></p>
        <p class="tier-clause">A trade is void if either side ends up over cap.</p>
      </div>
      <div class="rail-card scorecard-card">
        <h3>Season Scorecard &mdash; 100 pts</h3>
        <div class="strategy-row"><span>Standings rank</span><span class="mono">{SCORECARD_WEIGHTS["ranking"]} pts</span></div>
        <div class="strategy-row"><span>Made the playoffs (top {n_playoff})</span><span class="mono">{SCORECARD_WEIGHTS["playoffs"]} pts</span></div>
        <div class="strategy-row"><span>Revenue rank (tickets+sponsor+TV)</span><span class="mono">{SCORECARD_WEIGHTS["revenue"]} pts</span></div>
        <div class="strategy-row"><span>Decision rationale avg.</span><span class="mono">{SCORECARD_WEIGHTS["rationale"]} pts</span></div>
        <p class="tier-clause">Rank &amp; Revenue are scored against the rest of the league (1st = full points, last = 0), not a fixed target &mdash; see <span class="mono">engine/scorecard.py</span>.</p>
      </div>
    </aside>
  </div>
</div>

<footer>{config["league_name"]} &middot; front office terminal &middot; data current as of last instructor update</footer>

<script>
const BUILDER_TEAMS = {builder_teams_json};
const FORMATIONS = {formations_json};

// must match engine/render_dashboard.py's hash_pin() exactly, bit for bit --
// this is NOT real security (static public page, no backend), just enough
// that a team's PIN isn't sitting in plaintext in view-source. The
// enforcement that actually matters is server-side, in resolve_round.py.
function hashPin(pin) {{
  let h = 5381;
  for (let i = 0; i < pin.length; i++) h = ((h << 5) + h + pin.charCodeAt(i)) >>> 0;
  return h;
}}

function initBuilder() {{
  const teamSel = document.getElementById('b-team');
  const matchField = document.getElementById('b-match-field');
  const matchSel = document.getElementById('b-match');
  const formationSel = document.getElementById('b-formation');
  const priceField = document.getElementById('b-price-field');
  const fixtureNote = document.getElementById('b-fixture-note');
  const slotsEl = document.getElementById('b-slots');

  teamSel.innerHTML = BUILDER_TEAMS.map(t => `<option value="${{t.team_id}}">${{t.name}}</option>`).join('');
  formationSel.innerHTML = Object.keys(FORMATIONS).map(f => `<option>${{f}}</option>`).join('');

  // ---- Team PIN gate -- locks formation/strategy/price/lineup slots/
  // rationale/generate button until the PIN for the SELECTED team is
  // entered correctly. Prevents one student from (accidentally or on
  // purpose) building and submitting a lineup for a team that isn't
  // theirs. Client-side only -- see hashPin()'s comment above for the
  // honest limits of that, and resolve_round.py for the real enforcement.
  const pinInput = document.getElementById('b-pin');
  const pinStatus = document.getElementById('b-pin-status');
  const gatedEl = document.getElementById('b-gated');
  const strategySel = document.getElementById('b-strategy');
  const priceSel = document.getElementById('b-price');
  const rationaleEl = document.getElementById('b-rationale');
  const generateBtn = document.getElementById('b-generate');

  function checkPin() {{
    const team = teamSel.value ? BUILDER_TEAMS.find(t => String(t.team_id) === teamSel.value) : null;
    const typed = pinInput.value.trim();
    const unlocked = !!(team && team.pin_hash != null && typed.length === 4 && hashPin(typed) === team.pin_hash);

    [formationSel, strategySel, priceSel, rationaleEl, generateBtn].forEach(el => {{ el.disabled = !unlocked; }});
    gatedEl.classList.toggle('gated-locked', !unlocked);

    if (!team) {{
      pinStatus.textContent = "Pick your team, then enter your team's PIN to unlock lineup entry.";
      pinStatus.className = 'builder-msg';
    }} else if (team.pin_hash == null) {{
      // no PIN assigned in league_config.json yet -- don't lock students out
      pinStatus.textContent = 'No PIN required for this team yet.';
      pinStatus.className = 'builder-msg ok';
      [formationSel, strategySel, priceSel, rationaleEl, generateBtn].forEach(el => {{ el.disabled = false; }});
      gatedEl.classList.remove('gated-locked');
    }} else if (unlocked) {{
      pinStatus.textContent = `Unlocked for ${{team.name}}.`;
      pinStatus.className = 'builder-msg ok';
    }} else if (typed.length === 0) {{
      pinStatus.textContent = `Enter ${{team.name}}'s 4-digit PIN to unlock lineup entry.`;
      pinStatus.className = 'builder-msg';
    }} else {{
      pinStatus.textContent = 'Incorrect PIN.';
      pinStatus.className = 'builder-msg';
    }}
  }}
  pinInput.addEventListener('input', checkPin);
  teamSel.addEventListener('change', () => {{ pinInput.value = ''; checkPin(); }});
  checkPin();

  // ---- Rename Your Team -- same PIN system as the lineup builder above,
  // its own team-select/PIN pair so unlocking one doesn't unlock the other.
  const nTeamSel = document.getElementById('n-team');
  const nPinInput = document.getElementById('n-pin');
  const nPinStatus = document.getElementById('n-pin-status');
  const nGatedEl = document.getElementById('n-gated');
  const nNameInput = document.getElementById('n-name');
  const nGenerateBtn = document.getElementById('n-generate');

  nTeamSel.innerHTML = BUILDER_TEAMS.map(t => `<option value="${{t.team_id}}">${{t.name}}</option>`).join('');

  function checkRenamePin() {{
    const team = nTeamSel.value ? BUILDER_TEAMS.find(t => String(t.team_id) === nTeamSel.value) : null;
    const typed = nPinInput.value.trim();
    const unlocked = !!(team && team.pin_hash != null && typed.length === 4 && hashPin(typed) === team.pin_hash);

    [nNameInput, nGenerateBtn].forEach(el => {{ el.disabled = !unlocked; }});
    nGatedEl.classList.toggle('gated-locked', !unlocked);

    if (!team) {{
      nPinStatus.textContent = "Pick your team, then enter your team's PIN to unlock renaming.";
      nPinStatus.className = 'builder-msg';
    }} else if (team.pin_hash == null) {{
      nPinStatus.textContent = 'No PIN required for this team yet.';
      nPinStatus.className = 'builder-msg ok';
      [nNameInput, nGenerateBtn].forEach(el => {{ el.disabled = false; }});
      nGatedEl.classList.remove('gated-locked');
    }} else if (unlocked) {{
      nPinStatus.textContent = `Unlocked for ${{team.name}}.`;
      nPinStatus.className = 'builder-msg ok';
    }} else if (typed.length === 0) {{
      nPinStatus.textContent = `Enter ${{team.name}}'s 4-digit PIN to unlock renaming.`;
      nPinStatus.className = 'builder-msg';
    }} else {{
      nPinStatus.textContent = 'Incorrect PIN.';
      nPinStatus.className = 'builder-msg';
    }}
  }}
  nPinInput.addEventListener('input', checkRenamePin);
  nTeamSel.addEventListener('change', () => {{ nPinInput.value = ''; checkRenamePin(); }});
  checkRenamePin();

  nGenerateBtn.addEventListener('click', () => {{
    const msg = document.getElementById('n-msg');
    const team = nTeamSel.value ? BUILDER_TEAMS.find(t => String(t.team_id) === nTeamSel.value) : null;
    const newName = nNameInput.value.trim();
    if (!team) {{ msg.textContent = 'Pick a team first.'; msg.className = 'builder-msg'; return; }}
    if (!newName) {{ msg.textContent = 'Type your new team name first.'; msg.className = 'builder-msg'; return; }}
    if (!team.owner) {{
      msg.textContent = 'No owner is on file for this team yet -- ask the instructor to check league_config.json.';
      msg.className = 'builder-msg';
      return;
    }}
    const block = [
      `Owner Name: ${{team.owner}}`,
      `Team Name: ${{newName}}`,
    ].join('\\n\\n');
    document.getElementById('n-output').value = block;
    msg.textContent = 'Block generated -- copy it into the real Team Name Submission form fields of the same name.';
    msg.className = 'builder-msg ok';
  }});

  document.getElementById('n-copy').addEventListener('click', async () => {{
    const out = document.getElementById('n-output');
    const msg = document.getElementById('n-msg');
    out.select();
    let copied = false;
    try {{ await navigator.clipboard.writeText(out.value); copied = true; }} catch (e) {{}}
    if (!copied) {{ try {{ document.execCommand('copy'); copied = true; }} catch (e) {{}} }}
    msg.textContent = copied ? 'Copied.' : 'Select the text above and copy manually.';
    msg.className = copied ? 'builder-msg ok' : 'builder-msg';
  }});

  // ---- Your Drafted Roster -- standalone, no formation/round involved ----
  const rTeamSel = document.getElementById('r-team');
  rTeamSel.innerHTML = BUILDER_TEAMS.map(t => `<option value="${{t.team_id}}">${{t.name}}</option>`).join('');

  // this-browser-only scratchpad for Draft Day live entry -- NOT saved to
  // data/players.csv, resets on reload. Real persistence still runs through
  // the Draft Board / resolve_draft.py pipeline (or a manual roster-entry
  // CSV) -- see the note under the Add Player button.
  const manualAdds = {{}}; // team_id (string) -> [player, ...]
  const manualAddedIds = new Set(); // player_ids already manually placed on ANY team this session

  function renderRoster() {{
    const team = BUILDER_TEAMS.find(t => String(t.team_id) === rTeamSel.value);
    const rows = document.getElementById('r-rows');
    const summary = document.getElementById('r-summary');
    if (!team) {{ rows.innerHTML = ''; summary.textContent = ''; return; }}

    const extra = manualAdds[team.team_id] || [];
    const all = team.roster.concat(extra.map(p => Object.assign({{manual: true}}, p)));

    if (all.length === 0) {{
      rows.innerHTML = '<tr><td colspan="6" style="color:var(--muted);">No players drafted yet.</td></tr>';
      summary.textContent = '';
      return;
    }}
    rows.innerHTML = all.map((p, i) => `<tr${{p.manual ? ' style="opacity:.8;"' : ''}}>
      <td class="num mono">${{p.player_id != null ? p.player_id : '&ndash;'}}</td>
      <td class="pos pos-${{p.position || '?'}}">${{p.position || '?'}}</td>
      <td>${{p.name}}${{p.manual ? ' <span class="mono" style="font-size:10px;color:var(--accent);">MANUAL</span>' : ''}}</td>
      <td class="num">${{p.ovr != null ? p.ovr : '&ndash;'}}</td>
      <td class="num">${{p.salary != null ? '$' + p.salary.toLocaleString() : '&ndash;'}}</td>
      <td>${{p.manual ? `<button type="button" class="btn secondary r-remove" data-idx="${{extra.indexOf(p)}}" style="padding:2px 8px;font-size:10px;">remove</button>` : ''}}</td>
    </tr>`).join('');
    const totalSalary = all.reduce((sum, p) => sum + (p.salary || 0), 0);
    summary.innerHTML = `<span class="mono">${{all.length}}</span> players &middot; total salary <span class="mono">$${{totalSalary.toLocaleString()}}</span>${{extra.length ? ` (<span class="mono">${{extra.length}}</span> manually added, not yet official)` : ''}}`;

    rows.querySelectorAll('.r-remove').forEach(btn => {{
      btn.addEventListener('click', () => {{
        const idx = parseInt(btn.dataset.idx, 10);
        const removed = extra.splice(idx, 1)[0];
        if (removed) manualAddedIds.delete(removed.player_id);
        renderRoster();
      }});
    }});
  }}
  rTeamSel.addEventListener('change', renderRoster);
  renderRoster();

  // ---- PIN gate for Add Player -- same PIN as the lineup builder/rename
  // tool, same hashPin() comparison. Viewing a roster stays open (every
  // team's roster is already visible on the Front Offices cards below),
  // only the mutating "Add Player" action is gated.
  const rPinInput = document.getElementById('r-pin');
  const rPinStatus = document.getElementById('r-pin-status');
  const rGatedEl = document.getElementById('r-gated');
  const rAddNameInput = document.getElementById('r-add-name');
  const rAddBtn = document.getElementById('r-add-btn');

  function checkRosterPin() {{
    const team = rTeamSel.value ? BUILDER_TEAMS.find(t => String(t.team_id) === rTeamSel.value) : null;
    const typed = rPinInput.value.trim();
    const unlocked = !!(team && team.pin_hash != null && typed.length === 4 && hashPin(typed) === team.pin_hash);

    [rAddNameInput, rAddBtn].forEach(el => {{ el.disabled = !unlocked; }});
    rGatedEl.classList.toggle('gated-locked', !unlocked);

    if (!team) {{
      rPinStatus.textContent = "Pick a team, then enter its PIN to unlock adding a player.";
      rPinStatus.className = 'builder-msg';
    }} else if (team.pin_hash == null) {{
      rPinStatus.textContent = 'No PIN required for this team yet.';
      rPinStatus.className = 'builder-msg ok';
      [rAddNameInput, rAddBtn].forEach(el => {{ el.disabled = false; }});
      rGatedEl.classList.remove('gated-locked');
    }} else if (unlocked) {{
      rPinStatus.textContent = `Unlocked for ${{team.name}}.`;
      rPinStatus.className = 'builder-msg ok';
    }} else if (typed.length === 0) {{
      rPinStatus.textContent = `Enter ${{team.name}}'s 4-digit PIN to unlock adding a player.`;
      rPinStatus.className = 'builder-msg';
    }} else {{
      rPinStatus.textContent = 'Incorrect PIN.';
      rPinStatus.className = 'builder-msg';
    }}
  }}
  rPinInput.addEventListener('input', checkRosterPin);
  rTeamSel.addEventListener('change', () => {{ rPinInput.value = ''; checkRosterPin(); }});
  checkRosterPin();

  document.getElementById('r-add-btn').addEventListener('click', () => {{
    const input = document.getElementById('r-add-name');
    const msg = document.getElementById('r-add-msg');
    const typed = input.value.trim();
    const team = BUILDER_TEAMS.find(t => String(t.team_id) === rTeamSel.value);
    if (!typed) {{ msg.textContent = 'Type a player ID (1-399) or name first.'; msg.className = 'builder-msg'; return; }}
    if (!team) {{ msg.textContent = 'Pick a team first.'; msg.className = 'builder-msg'; return; }}

    // ID takes priority when the input is a plain number -- no typo risk,
    // exact match only, no confusion with a name that happens to look numeric.
    const asId = /^\\d+$/.test(typed) ? typed : null;
    const byId = p => asId !== null && String(p.player_id) === asId;
    const byName = p => p.name.toLowerCase() === typed.toLowerCase();
    const matchFn = asId !== null ? byId : byName;

    const alreadyOnTeam = team.roster.some(matchFn) || (manualAdds[team.team_id] || []).some(matchFn);
    if (alreadyOnTeam) {{
      const who = asId !== null
        ? (team.roster.find(matchFn) || (manualAdds[team.team_id]||[]).find(matchFn)).name
        : typed;
      msg.textContent = `${{who}} is already on this roster.`; msg.className = 'builder-msg'; return;
    }}

    const match = PLAYERS.find(matchFn);
    if (!match) {{
      msg.textContent = asId !== null
        ? `No available player has ID ${{asId}} -- check the ID column on the Draft Board below, or they may already be drafted onto another team.`
        : `"${{typed}}" doesn't match any available player -- check the exact spelling on the Draft Board list below, or they may already be drafted onto another team.`;
      msg.className = 'builder-msg';
      return;
    }}
    if (manualAddedIds.has(match.player_id)) {{
      msg.textContent = `${{match.name}} was already manually added to another team this session.`;
      msg.className = 'builder-msg';
      return;
    }}

    manualAdds[team.team_id] = manualAdds[team.team_id] || [];
    manualAdds[team.team_id].push(match);
    manualAddedIds.add(match.player_id);
    input.value = '';
    msg.textContent = `Added ${{match.name}} -- remember, this is a live scratchpad only, not saved to players.csv.`;
    msg.className = 'builder-msg ok';
    renderRoster();
  }});
  document.getElementById('r-add-name').addEventListener('keydown', (e) => {{
    if (e.key === 'Enter') document.getElementById('r-add-btn').click();
  }});

  function currentTeam() {{
    return BUILDER_TEAMS.find(t => String(t.team_id) === teamSel.value);
  }}

  function currentFixture() {{
    const team = currentTeam();
    if (!team || !team.fixtures || team.fixtures.length === 0) return null;
    return team.fixtures[matchSel.value] || team.fixtures[0];
  }}

  function playerOptions(team, position) {{
    const opts = team.roster.filter(p => p.position === position)
      .map(p => `<option value="${{p.name}}">#${{p.player_id}} &mdash; ${{p.name}} (OVR ${{p.ovr}})</option>`).join('');
    return opts || '<option value="" disabled selected>No players drafted at this position yet</option>';
  }}

  function rebuildMatchOptions() {{
    const team = currentTeam();
    const fixtures = (team && team.fixtures) || [];
    matchField.hidden = fixtures.length < 2;
    matchSel.innerHTML = fixtures.map((fx, i) =>
      `<option value="${{i}}">Round ${{fx.round}} -- ${{fx.is_home ? 'HOME vs' : 'AWAY at'}} ${{fx.opponent}}</option>`
    ).join('');
  }}

  function rebuildSlots() {{
    const team = currentTeam();
    const counts = FORMATIONS[formationSel.value];
    if (!team || !counts) return;
    let html = '';
    for (const pos of ['GK','DF','MF','FW']) {{
      for (let i = 0; i < counts[pos]; i++) {{
        html += `<div class="slot-group"><h4>${{pos}} ${{counts[pos] > 1 ? (i+1) : ''}}</h4>
          <select class="b-slot" data-pos="${{pos}}">${{playerOptions(team, pos)}}</select></div>`;
      }}
    }}
    slotsEl.innerHTML = html;
    document.getElementById('b-rationale').value = '';
    document.getElementById('b-output').value = '';

    const fx = currentFixture();
    if (!fx) {{
      fixtureNote.textContent = 'No fixture scheduled for your team this match day (bye).';
      priceField.hidden = true;
    }} else if (fx.is_home) {{
      fixtureNote.textContent = `Round ${{fx.round}}: HOME vs ${{fx.opponent}} -- set a ticket price below.`;
      priceField.hidden = false;
    }} else {{
      fixtureNote.textContent = `Round ${{fx.round}}: AWAY at ${{fx.opponent}} -- no ticket price needed.`;
      priceField.hidden = true;
    }}
  }}

  teamSel.addEventListener('change', () => {{ rebuildMatchOptions(); rebuildSlots(); }});
  matchSel.addEventListener('change', rebuildSlots);
  formationSel.addEventListener('change', rebuildSlots);
  rebuildMatchOptions();
  rebuildSlots();

  document.getElementById('b-generate').addEventListener('click', () => {{
    const msg = document.getElementById('b-msg');
    const team = currentTeam();
    const selects = Array.from(document.querySelectorAll('.b-slot'));
    const chosen = selects.map(s => ({{pos: s.dataset.pos, name: s.value}}));

    if (chosen.some(c => !c.name)) {{
      msg.textContent = 'Fill every starting slot before generating.';
      msg.className = 'builder-msg';
      return;
    }}
    const names = chosen.map(c => c.name);
    if (new Set(names).size !== names.length) {{
      msg.textContent = 'The same player is selected in two slots -- fix that first.';
      msg.className = 'builder-msg';
      return;
    }}

    const byPos = pos => chosen.filter(c => c.pos === pos).map(c => c.name);
    const rationale = document.getElementById('b-rationale').value.trim();
    const fx = currentFixture();
    const price = (fx && fx.is_home) ? document.getElementById('b-price').value : '(away -- leave blank)';

    const block = [
      `Team name: ${{team.name}}`,
      `Round number: ${{fx ? fx.round : '(bye this match day)'}}`,
      `Formation: ${{formationSel.value}}`,
      `Strategy: ${{document.getElementById('b-strategy').value}}`,
      `Starting Goalkeeper: ${{byPos('GK')[0] || ''}}`,
      `Starting Defenders:\\n${{byPos('DF').join('\\n')}}`,
      `Starting Midfielders:\\n${{byPos('MF').join('\\n')}}`,
      `Starting Forwards:\\n${{byPos('FW').join('\\n')}}`,
      `Ticket Price: ${{price}}`,
      `Decision rationale (2-4 sentences): ${{rationale || '(fill this in before submitting)'}}`,
    ].join('\\n\\n');

    document.getElementById('b-output').value = block;
    msg.textContent = 'Block generated -- copy it into the real Google Form fields of the same name.';
    msg.className = 'builder-msg ok';
  }});

  document.getElementById('b-copy').addEventListener('click', async () => {{
    const out = document.getElementById('b-output');
    const msg = document.getElementById('b-msg');
    out.select();
    let copied = false;
    try {{
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        await navigator.clipboard.writeText(out.value);
        copied = true;
      }}
    }} catch (e) {{ copied = false; }}
    if (!copied) {{
      try {{ copied = document.execCommand('copy'); }} catch (e) {{ copied = false; }}
    }}
    msg.textContent = copied ? 'Copied to clipboard.' : 'Could not auto-copy -- text is selected, use Cmd/Ctrl+C.';
    msg.className = copied ? 'builder-msg ok' : 'builder-msg';
  }});
}}
initBuilder();

const PLAYERS = {players_json};
let sortKey = "ovr", sortDir = -1, posFilter = "ALL";

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
  rows.sort((a,b) => {{
    // player_id is a string (preserves exact CSV/players.csv identity), so
    // a plain > / < comparison would sort it alphabetically ("1","10","100"
    // before "2") -- coerce to a number for this one column only, every
    // other sortable column is already numeric or a name string.
    let av = a[sortKey], bv = b[sortKey];
    if (sortKey === "player_id") {{ av = Number(av); bv = Number(bv); }}
    return (av > bv ? 1 : av < bv ? -1 : 0) * sortDir;
  }});
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
    return html


if __name__ == "__main__":
    players = load_players()
    config = load_json("league_config.json")
    deals = load_json("deals.json")
    matches = load_json("matches.json")
    schedule_path = os.path.join(BASE, "data", "schedule.json")
    schedule = load_json("schedule.json") if os.path.exists(schedule_path) else []
    calendar_path = os.path.join(BASE, "data", "season_calendar.json")
    calendar = load_json("season_calendar.json") if os.path.exists(calendar_path) else None
    html = render(players, config, deals, matches, schedule, calendar)
    out_path = os.path.join(BASE, "dashboard", "index.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Rendered -> {out_path}")
