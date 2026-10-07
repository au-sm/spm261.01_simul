"""
Renders matchday-replay/index.html -- a broadcast-style 2D replay of every
resolved match.

What is REAL (straight from the match record the simulation produced):
  - both starting XIs (names, positions) and formations,
  - the final score, and every goal's minute, scorer, side and goal type,
  - the Match Story text (engine/match_summary.py).

What is ILLUSTRATIVE (generated deterministically from the match, so a
replay always plays out the same way): the possession play between goals,
the non-goal shots/saves, and the possession/shot stats derived from that
animation. Each goal type plays out its own way: Strike (build-up + finish),
Header (wide cross + header), Corner Kick (won corner, delivery, finish),
Penalty Kick (foul in the box, spot kick), Free Kick (foul, wall, curler).
Teams switch ends at half-time.

Run after any resolve_round.py call, then republish.
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from site_nav import NAV_CSS, render_nav
from match_summary import generate_summary

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

POS_ORDER = {"GK": 0, "DF": 1, "MF": 2, "FW": 3}
KITS = ["#1f4fd1", "#c62828", "#f2f2f2", "#1b1b1b", "#f9a825", "#6a1b9a", "#00838f", "#ef6c00",
        "#ad1457", "#0d47a1", "#8d6e63", "#455a64"]


def load_json(name):
    with open(os.path.join(BASE, "data", name)) as f:
        return json.load(f)


def load_players():
    with open(os.path.join(BASE, "data", "players.csv")) as f:
        return {p["player_id"]: p for p in csv.DictReader(f)}


def _hex_dist(a, b):
    a, b = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** .5


def kits_for(home_id, away_id):
    h = KITS[home_id % len(KITS)]
    k = away_id % len(KITS)
    a = KITS[k]
    while _hex_dist(h, a) < 160:
        k = (k + 1) % len(KITS)
        a = KITS[k]
    return h, a


def xi_for(m, side, players):
    ids = [str(x) for x in m.get(f"{side}_starters") or []]
    xi = []
    for pid in ids:
        p = players.get(pid)
        if p:
            xi.append({"n": p["name"], "p": p["position"]})
    if len(xi) != 11:  # no stored lineup: a neutral XI in the stored formation
        form = (m.get(f"{side}_formation") or "4-4-2").split("-")
        xi = [{"n": "", "p": "GK"}]
        for pos, cnt in zip(("DF", "MF", "FW"), form):
            xi += [{"n": "", "p": pos} for _ in range(int(cnt))]
    xi.sort(key=lambda q: POS_ORDER.get(q["p"], 2))
    return xi


def formation_of(xi):
    c = {k: 0 for k in ("DF", "MF", "FW")}
    for q in xi:
        if q["p"] in c:
            c[q["p"]] += 1
    return f'{c["DF"]}-{c["MF"]}-{c["FW"]}'


def render(config, matches):
    team_map = {t["team_id"]: t for t in config["teams"]}
    players = load_players()
    sorted_matches = sorted(matches, key=lambda m: (m["round"], m["home_id"], m["away_id"]))

    entries = []
    for m in sorted_matches:
        home, away = team_map[m["home_id"]], team_map[m["away_id"]]
        hk, ak = kits_for(m["home_id"], m["away_id"])
        hxi, axi = xi_for(m, "home", players), xi_for(m, "away", players)
        goals = sorted(({"minute": g["minute"], "side": g["side"], "type": g["type"], "scorer": g["scorer"],
                         "pos": g.get("scorer_position", "")} for g in m.get("goal_events", [])),
                       key=lambda g: g["minute"])
        entries.append({
            "round": m["round"],
            "seed": m["round"] * 1009 + m["home_id"] * 97 + m["away_id"] * 13 + 7,
            "home": {"name": home["name"], "owner": home.get("owner", ""), "kit": hk, "xi": hxi, "form": formation_of(hxi)},
            "away": {"name": away["name"], "owner": away.get("owner", ""), "kit": ak, "xi": axi, "form": formation_of(axi)},
            "hg": m["home_goals"], "ag": m["away_goals"],
            "goals": goals,
            "summary": generate_summary(home["name"], away["name"], m["home_goals"], m["away_goals"], m.get("goal_events", [])),
        })

    default_idx = len(entries) - 1
    options, cur = "", None
    for i, e in enumerate(entries):
        if e["round"] != cur:
            if cur is not None:
                options += "</optgroup>"
            options += f'<optgroup label="Round {e["round"]}">'
            cur = e["round"]
        sel = " selected" if i == default_idx else ""
        options += (f'<option value="{i}"{sel}>{_esc(e["home"]["name"])} {e["hg"]}&ndash;{e["ag"]} '
                    f'{_esc(e["away"]["name"])}</option>')
    if cur is not None:
        options += "</optgroup>"

    html = TEMPLATE
    for k, v in {
        "__NAV_CSS__": NAV_CSS,
        "__NAV__": render_nav("replay"),
        "__LEAGUE__": _esc(config.get("league_name", "")),
        "__OPTIONS__": options or '<option value="-1">No matches played yet</option>',
        "__DATA__": json.dumps(entries).replace("</", "<\\/"),
        "__DEFAULT__": str(default_idx),
    }.items():
        html = html.replace(k, v)
    return html


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Matchday Replay</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;700;800;900&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{--paper:#eef2ea;--ink:#16201a;--muted:#5b6b5e;--line:#d6decd;--accent:#b8811f;--surface:#f7f9f4;
  --bc:#0b110d;--bc2:#141c16;--bcline:#26322a;--bctxt:#eef2ea;--bcmuted:#8d9b8f;--led:#ffb627;}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--paper:#111611;--ink:#e7ece1;--muted:#93a091;--line:#2a352a;--accent:#d9a44a;--surface:#171d17;}}
:root[data-theme="dark"]{--paper:#111611;--ink:#e7ece1;--muted:#93a091;--line:#2a352a;--accent:#d9a44a;--surface:#171d17;}
*{box-sizing:border-box;}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Source Serif 4",Georgia,serif;}
.wrap{max-width:1240px;margin:0 auto;padding:22px clamp(12px,3vw,40px) 60px;}
h1{font-family:"Big Shoulders Display",sans-serif;text-transform:uppercase;letter-spacing:.02em;font-size:clamp(26px,4vw,38px);margin:0;}
.sub{color:var(--muted);font-family:"IBM Plex Mono",monospace;font-size:12.5px;margin:4px 0 14px;}
.picker{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 12px;}
.picker label{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);}
.picker select{font-family:"Source Serif 4",serif;font-size:14px;background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:8px 10px;min-width:260px;max-width:100%;}

.bc{background:var(--bc);color:var(--bctxt);border-radius:14px;overflow:hidden;box-shadow:0 18px 50px -20px rgba(0,0,0,.6);}
.board{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:12px;padding:12px clamp(12px,2.5vw,24px);background:linear-gradient(180deg,#121a15,#0b110d);border-bottom:1px solid var(--bcline);}
.tm{display:flex;align-items:center;gap:10px;min-width:0;} .tm.away{flex-direction:row-reverse;text-align:right;}
.kit{width:22px;height:22px;border-radius:5px;flex:none;box-shadow:inset 0 0 0 2px rgba(255,255,255,.35);}
.tm b{display:block;font-family:"Big Shoulders Display",sans-serif;font-weight:800;text-transform:uppercase;font-size:clamp(15px,2.2vw,22px);line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.tm small{display:block;font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--bcmuted);}
.mid{text-align:center;}
.sc{display:flex;align-items:center;gap:8px;justify-content:center;}
.dig{min-width:42px;height:50px;display:inline-flex;align-items:center;justify-content:center;background:#050806;border:1px solid #1d261f;border-radius:7px;font-family:"Big Shoulders Display",sans-serif;font-weight:900;font-size:38px;color:var(--led);text-shadow:0 0 12px rgba(255,182,39,.55);}
.dig.pop{animation:pop .6s ease;} @keyframes pop{0%{transform:scale(1)}40%{transform:scale(1.35)}100%{transform:scale(1)}}
.clock{margin-top:4px;font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.08em;color:var(--bcmuted);}
.clock .live{display:inline-block;width:7px;height:7px;border-radius:50%;background:#e8543f;margin-right:6px;vertical-align:1px;animation:blink 1.2s infinite;}
@keyframes blink{50%{opacity:.25}}

.main{display:grid;grid-template-columns:1fr 300px;}
.stage{position:relative;background:#173d22;}
canvas{display:block;width:100%;}
.banner{position:absolute;left:50%;top:42%;transform:translate(-50%,-50%) scale(.6);opacity:0;pointer-events:none;text-align:center;transition:opacity .25s,transform .35s cubic-bezier(.2,1.4,.4,1);}
.banner.show{opacity:1;transform:translate(-50%,-50%) scale(1);}
.banner .g{font-family:"Big Shoulders Display",sans-serif;font-weight:900;font-size:clamp(46px,9vw,110px);line-height:.9;color:#fff;letter-spacing:.04em;text-shadow:0 6px 30px rgba(0,0,0,.6);}
.banner .w{display:inline-block;margin-top:8px;padding:6px 14px;border-radius:6px;background:rgba(5,8,6,.82);font-family:"IBM Plex Mono",monospace;font-size:13px;color:#fff;border-left:5px solid var(--k,#ffb627);}
.overlay{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(5,9,6,.55);opacity:0;pointer-events:none;transition:opacity .4s;}
.overlay.show{opacity:1;pointer-events:auto;}
.overlay .card{background:rgba(11,17,13,.92);border:1px solid var(--bcline);border-radius:12px;padding:16px 26px;text-align:center;}
.overlay .card span{display:block;font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.16em;color:var(--bcmuted);}
.overlay .card b{font-family:"Big Shoulders Display",sans-serif;font-size:40px;color:var(--led);}
.overlay button{margin-top:10px;}

.side{border-left:1px solid var(--bcline);display:flex;flex-direction:column;min-height:0;background:var(--bc2);}
.stats{padding:12px 14px;border-bottom:1px solid var(--bcline);font-family:"IBM Plex Mono",monospace;font-size:11.5px;}
.srow{display:grid;grid-template-columns:52px 1fr 52px;align-items:center;gap:8px;margin:6px 0;}
.srow .v{text-align:center;color:var(--bctxt);font-weight:600;} .srow .l{text-align:center;color:var(--bcmuted);letter-spacing:.08em;text-transform:uppercase;font-size:10px;}
.pbar{height:8px;border-radius:5px;overflow:hidden;display:flex;background:#222;margin-top:4px;} .pbar i{display:block;height:100%;transition:width .5s;}
.feedh{padding:10px 14px 4px;font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.14em;color:var(--led);text-transform:uppercase;}
.feed{list-style:none;margin:0;padding:0 14px 12px;overflow-y:auto;flex:1;min-height:120px;max-height:420px;font-size:13px;line-height:1.35;}
.feed li{padding:7px 0;border-bottom:1px dashed var(--bcline);animation:fin .4s ease;} @keyframes fin{from{opacity:0;transform:translateY(-6px)}}
.feed li .m{font-family:"IBM Plex Mono",monospace;color:var(--led);margin-right:6px;font-size:11.5px;}
.feed li.goal{color:#fff;font-weight:600;} .feed li.goal .m{color:#4fd18b;}
.feed li.hl{color:var(--bcmuted);}

.ctrls{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:10px clamp(12px,2.5vw,24px);border-top:1px solid var(--bcline);background:#0d140f;}
.btn{background:#1b241e;color:var(--bctxt);border:1px solid #2c3a30;border-radius:7px;padding:7px 12px;font:600 12.5px "IBM Plex Mono",monospace;cursor:pointer;}
.btn:hover{border-color:var(--led);} .btn.on{background:var(--led);color:#1a1205;border-color:var(--led);}
.btn.primary{background:var(--led);color:#1a1205;border-color:var(--led);}
.sp{display:flex;gap:4px;} .grow{flex:1;}
.chk{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--bcmuted);display:flex;align-items:center;gap:6px;cursor:pointer;}

.note{font-size:12.5px;color:var(--muted);font-family:"IBM Plex Mono",monospace;margin:10px 2px 0;}
.story,.tl{margin-top:22px;}
.story h2,.tl h2{font-family:"Big Shoulders Display",sans-serif;text-transform:uppercase;font-size:20px;margin:0 0 8px;}
.story p{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:0;line-height:1.55;}
.tl ul{list-style:none;margin:0;padding:0;}
.tl li{display:flex;align-items:center;gap:12px;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:9px 12px;margin-bottom:6px;cursor:pointer;}
.tl li:hover{border-color:var(--accent);}
.tl .mn{font-family:"IBM Plex Mono",monospace;font-weight:600;width:36px;}
.tl .ty{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;padding:2px 7px;border-radius:4px;background:color-mix(in srgb,var(--accent) 20%,transparent);}
.tl .kd{width:12px;height:12px;border-radius:3px;flex:none;}
.tl .go{margin-left:auto;font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--muted);}
.empty{background:var(--surface);border:1px dashed var(--line);border-radius:10px;padding:22px;color:var(--muted);font-family:"IBM Plex Mono",monospace;}
@media (max-width:900px){.main{grid-template-columns:1fr;}.side{border-left:0;border-top:1px solid var(--bcline);}.feed{max-height:220px;}}
__NAV_CSS__
</style>
</head>
<body>
__NAV__
<div class="wrap">
  <h1>Matchday Replay</h1>
  <p class="sub">__LEAGUE__ &middot; every match, replayed with the real line-ups, formations, scorers and goal minutes</p>
  <div class="picker"><label for="pick">Match</label><select id="pick">__OPTIONS__</select></div>

  <div id="app">
  <div class="bc">
    <div class="board">
      <div class="tm"><span class="kit" id="hk"></span><div style="min-width:0"><b id="hn"></b><small id="ho"></small></div></div>
      <div class="mid"><div class="sc"><span class="dig" id="hs">0</span><span class="dig" id="as">0</span></div>
        <div class="clock" id="clock"><span class="live"></span>KICK-OFF</div></div>
      <div class="tm away"><span class="kit" id="ak"></span><div style="min-width:0"><b id="an"></b><small id="ao"></small></div></div>
    </div>
    <div class="main">
      <div class="stage" id="stage">
        <canvas id="cv"></canvas>
        <div class="banner" id="banner"><div class="g">GOAL!</div><div class="w" id="bannerW"></div></div>
        <div class="overlay" id="overlay"><div class="card"><span id="ovT">FULL-TIME</span><b id="ovS">0 &ndash; 0</b><div><button class="btn primary" id="ovBtn">&#8634; Watch again</button></div></div></div>
      </div>
      <div class="side">
        <div class="stats">
          <div class="srow"><span class="v" id="sPh">50%</span><span class="l">Possession</span><span class="v" id="sPa">50%</span></div>
          <div class="pbar"><i id="pbH" style="width:50%"></i><i id="pbA" style="width:50%"></i></div>
          <div class="srow"><span class="v" id="sSh">0</span><span class="l">Shots</span><span class="v" id="sSa">0</span></div>
          <div class="srow"><span class="v" id="sTh">0</span><span class="l">On target</span><span class="v" id="sTa">0</span></div>
          <div class="srow"><span class="v" id="sFh"></span><span class="l">Formation</span><span class="v" id="sFa"></span></div>
        </div>
        <div class="feedh">Live commentary</div>
        <ul class="feed" id="feed"></ul>
      </div>
    </div>
    <div class="ctrls">
      <button class="btn primary" id="play">&#10073;&#10073; Pause</button>
      <button class="btn" id="restart">&#8634; Restart</button>
      <div class="sp"><button class="btn sp1 on" data-s="1">1&times;</button><button class="btn" data-s="2">2&times;</button><button class="btn" data-s="4">4&times;</button></div>
      <button class="btn" id="nextGoal">&#9193; Next goal</button>
      <span class="grow"></span>
      <label class="chk"><input type="checkbox" id="names"> All player names</label>
    </div>
  </div>
  <p class="note">Score, line-ups, formations, goal minutes, scorers and goal types are the real simulation result. The build-up play, near-misses and saves between goals are an illustration of the match.</p>

  <div class="story"><h2>Match Story</h2><p id="story"></p></div>
  <div class="tl"><h2>Goal Timeline</h2><ul id="tl"></ul></div>
  </div>
  <div class="empty" id="empty" hidden>No matches played yet &mdash; replays appear here automatically after each round.</div>
</div>

<script>
(function(){
const MATCHES = __DATA__;
const DEFAULT = __DEFAULT__;
const $ = id => document.getElementById(id);
if(!MATCHES.length){ $('app').hidden = true; $('empty').hidden = false; return; }

/* ---------------- constants ---------------- */
const W = 105, H = 68, MG = 4, DT = 1/60;
const ANIM = 64;                  // seconds of animation for 90 minutes at 1x
const MPS = 90 / ANIM;            // match minutes per animation second
const GOAL_Y0 = 30.34, GOAL_Y1 = 37.66;
const GOAL_AT = 0.45;             // a goal in the 18th minute shows 17:33 on the clock

/* ---------------- canvas ---------------- */
const cv = $('cv'), ctx = cv.getContext('2d');
let S = 6, CW = 0, CH = 0, pitchImg = null, flip = false;
function resize(){
  const w = $('stage').clientWidth, dpr = Math.min(window.devicePixelRatio || 1, 2);
  CW = w; CH = w * (H + 2*MG) / (W + 2*MG); S = CW / (W + 2*MG);
  cv.width = Math.round(CW*dpr); cv.height = Math.round(CH*dpr); cv.style.height = CH + 'px';
  ctx.setTransform(dpr,0,0,dpr,0,0);
  pitchImg = drawPitch(dpr);
}
const px = x => (MG + (flip ? W - x : x)) * S;
const py = y => (MG + (flip ? H - y : y)) * S;

function drawPitch(dpr){
  const c = document.createElement('canvas'); c.width = cv.width; c.height = cv.height;
  const g = c.getContext('2d'); g.setTransform(dpr,0,0,dpr,0,0);
  const P = (x)=> (MG + x) * S, Q = (y)=> (MG + y) * S;
  g.fillStyle = '#1f5a2e'; g.fillRect(0,0,CW,CH);
  for(let i=0;i<14;i++){ g.fillStyle = i%2 ? '#22632f' : '#1d5629'; g.fillRect(P(i*W/14), Q(0)-MG*S, W/14*S+0.5, CH); }
  const grad = g.createRadialGradient(CW/2, CH/2, CH*.2, CW/2, CH/2, CW*.75);
  grad.addColorStop(0,'rgba(255,255,255,0)'); grad.addColorStop(1,'rgba(0,0,0,.28)');
  g.fillStyle = grad; g.fillRect(0,0,CW,CH);
  g.strokeStyle = 'rgba(255,255,255,.85)'; g.lineWidth = Math.max(1.2, S*.14); g.fillStyle = 'rgba(255,255,255,.9)';
  g.strokeRect(P(0),Q(0),W*S,H*S);
  g.beginPath(); g.moveTo(P(W/2),Q(0)); g.lineTo(P(W/2),Q(H)); g.stroke();
  g.beginPath(); g.arc(P(W/2),Q(H/2),9.15*S,0,Math.PI*2); g.stroke();
  g.beginPath(); g.arc(P(W/2),Q(H/2),S*.35,0,Math.PI*2); g.fill();
  for(const side of [0,1]){
    const x0 = side ? W : 0, d = side ? -1 : 1;
    g.strokeRect(P(side ? W-16.5 : 0), Q(H/2-20.16), 16.5*S, 40.32*S);
    g.strokeRect(P(side ? W-5.5 : 0), Q(H/2-9.16), 5.5*S, 18.32*S);
    g.beginPath(); g.arc(P(x0+d*11),Q(H/2),S*.35,0,Math.PI*2); g.fill();
    const a = Math.acos(5.5/9.15);
    g.beginPath(); if(side) g.arc(P(W-11),Q(H/2),9.15*S,Math.PI-a,Math.PI+a); else g.arc(P(11),Q(H/2),9.15*S,-a,a); g.stroke();
    // goal + net
    const gx = P(x0), gw = 2.2*S*d;
    g.save(); g.strokeStyle='rgba(255,255,255,.35)'; g.lineWidth=1;
    for(let k=0;k<=8;k++){ const yy = Q(GOAL_Y0)+(GOAL_Y1-GOAL_Y0)*S*k/8; g.beginPath(); g.moveTo(gx,yy); g.lineTo(gx+gw,yy); g.stroke(); }
    for(let k=1;k<=3;k++){ g.beginPath(); g.moveTo(gx+gw*k/3,Q(GOAL_Y0)); g.lineTo(gx+gw*k/3,Q(GOAL_Y1)); g.stroke(); }
    g.restore();
    g.lineWidth = Math.max(2, S*.3); g.strokeStyle = '#fff';
    g.beginPath(); g.moveTo(gx,Q(GOAL_Y0)); g.lineTo(gx+gw,Q(GOAL_Y0)); g.lineTo(gx+gw,Q(GOAL_Y1)); g.lineTo(gx,Q(GOAL_Y1)); g.stroke();
    g.lineWidth = Math.max(1.2, S*.14); g.strokeStyle = 'rgba(255,255,255,.85)';
  }
  for(const [cx,cy,a0] of [[0,0,0],[W,0,Math.PI/2],[W,H,Math.PI],[0,H,-Math.PI/2]]){ g.beginPath(); g.arc(P(cx),Q(cy),S,a0,a0+Math.PI/2); g.stroke(); }
  return c;
}

/* ---------------- helpers ---------------- */
function rng(seed){ let s = (seed*2654435761)>>>0 || 1; return ()=>{ s^=s<<13; s>>>=0; s^=s>>>17; s^=s<<5; s>>>=0; return s/4294967296; }; }
let R = Math.random;
const rr = (a,b)=> a + (b-a)*R();
const pick = arr => arr[Math.floor(R()*arr.length)];
const dist = (a,b)=> Math.hypot(a.x-b.x, a.y-b.y);
const clamp = (v,a,b)=> Math.max(a, Math.min(b, v));
const surname = n => { const p = (n||'').trim().split(/\s+/); return p.length > 1 ? p.slice(1).join(' ') : (p[0] || ''); };
function textOn(hex){ const c=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)); return (c[0]*.299+c[1]*.587+c[2]*.114) > 150 ? '#111' : '#fff'; }

/* ---------------- match state ---------------- */
let M, T, P, ball, st;
function frame(t, x, y){ return t.side === 0 ? {x, y} : {x: W - x, y: H - y}; }   // team-attack frame -> model
function lineXs(n){ return n === 3 ? [23, 45, 66] : [21, 36, 50, 66]; }

function mkTeam(info, side){
  const t = {side, name: info.name, kit: info.kit, num: textOn(info.kit), players: []};
  const groups = [[],[],[],[]];
  info.xi.forEach(q => groups[{GK:0,DF:1,MF:2,FW:3}[q.p] ?? 2].push(q));
  const lines = groups.filter((g,i)=> i>0 && g.length);
  const xs = lineXs(lines.length);
  let num = 1;
  const add = (q, bx, by) => {
    const pos = frame(t, bx, by);
    t.players.push({team: t, name: q.n || '', short: surname(q.n) || ('#'+num), pos: q.p, num: num++, bx, by,
                    x: pos.x, y: pos.y, vx: 0, vy: 0, tx: pos.x, ty: pos.y, ov: null});
  };
  groups[0].forEach(q => add(q, 4.5, H/2));
  lines.forEach((g, li) => {
    const k = g.length, spread = k === 1 ? 0 : Math.min(56, 14*k + (li === 0 ? 8 : 4));
    g.forEach((q, j) => {
      const by = k === 1 ? H/2 : H/2 - spread/2 + spread*j/(k-1);
      const wing = (k >= 3 && (j === 0 || j === k-1)) ? (li === lines.length-1 ? -4 : 2) : 0;
      add(q, xs[li] + wing, by);
    });
  });
  t.gk = t.players[0];
  t.dir = side === 0 ? 1 : -1;
  return t;
}

function load(i){
  M = MATCHES[i];
  R = rng(M.seed);
  T = [mkTeam(M.home, 0), mkTeam(M.away, 1)];
  P = T[0].players.concat(T[1].players);
  ball = {x: W/2, y: H/2, z: 0, owner: null, fl: null, last: T[0]};
  st = {clock: 0, half: 1, phase: 'pre', timer: 0, score: [0,0], gi: 0, script: null, poss: [1.5,1.5],
        shots: [0,0], ont: [0,0], kick: 0, hold: 0, chances: [3 + Math.floor(R()*4), 3 + Math.floor(R()*4)],
        celebrate: null, msgs: [], done: false};
  flip = false;
  // board
  $('hn').textContent = M.home.name; $('ho').textContent = M.home.owner; $('hk').style.background = M.home.kit;
  $('an').textContent = M.away.name; $('ao').textContent = M.away.owner; $('ak').style.background = M.away.kit;
  $('hs').textContent = 0; $('as').textContent = 0;
  $('pbH').style.background = M.home.kit; $('pbA').style.background = M.away.kit;
  $('sFh').textContent = M.home.form; $('sFa').textContent = M.away.form;
  $('feed').innerHTML = ''; $('overlay').classList.remove('show'); $('banner').classList.remove('show');
  $('story').textContent = M.summary;
  $('tl').innerHTML = M.goals.length ? M.goals.map((g, k) =>
    `<li data-g="${k}"><span class="mn">${g.minute}'</span><span class="kd" style="background:${g.side==='home'?M.home.kit:M.away.kit}"></span><span class="ty">${g.type}</span><b>${esc(g.scorer)}</b><span style="color:var(--muted);font-size:13px">${esc(g.side==='home'?M.home.name:M.away.name)}</span><span class="go">&#9654; watch</span></li>`).join('')
    : '<li style="cursor:default">No goals in this match.</li>';
  kickoffSetup(0);
  say(0, `Kick-off! ${M.home.name} (${M.home.form}) v ${M.away.name} (${M.away.form}).`, 'hl');
  updateStats();
}
function esc(s){ return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

/* ---------------- commentary ---------------- */
function say(min, text, cls){
  st.msgs.push({min, text, cls});
  if(skipping) return;
  const li = document.createElement('li'); if(cls) li.className = cls;
  li.innerHTML = `<span class="m">${min}'</span>${esc(text)}`;
  $('feed').prepend(li);
}
const curMin = () => Math.max(1, Math.min(90, Math.ceil(st.clock)));

/* ---------------- positioning ---------------- */
function kickoffSetup(teamIdx){
  st.kick = teamIdx; st.phase = 'kickoff'; st.timer = 1.4; st.script = null;
  P.forEach(p => {
    p.ov = null;
    let x = p.bx * 0.92, y = p.by;
    if(p.team.side === teamIdx && p.pos === 'FW'){ x = 51.2; }
    const m = frame(p.team, Math.min(x, 51.5), y); p.tx = m.x; p.ty = m.y;
  });
  const kt = T[teamIdx];
  const fws = kt.players.filter(p => p.pos === 'FW');
  const taker = fws[0] || kt.players[kt.players.length-1];
  taker.ov = {x: W/2 - kt.dir*0.6, y: H/2};
  ball.fl = null; ball.owner = null; ball.x = W/2; ball.y = H/2; ball.z = 0; ball.taker = taker;
}

function teamTargets(){
  const att = ball.owner ? ball.owner.team : ball.last;
  const bx = ball.fl ? ball.fl.x1 : ball.x, by = ball.fl ? ball.fl.y1 : ball.y;
  for(const t of T){
    const inPoss = t === att;
    for(const p of t.players){
      if(p.ov){ p.tx = p.ov.x; p.ty = p.ov.y; continue; }
      if(st.phase === 'kickoff' || st.phase === 'reset' || st.phase === 'celebrate') continue;
      if(p === t.gk){
        const gx = t.side === 0 ? 3 : W - 3;
        const near = Math.abs(bx - (t.side===0?0:W)) < 30;
        p.tx = gx + t.dir * (near ? 1.5 : 3.5);
        p.ty = H/2 + (by - H/2) * (near ? 0.35 : 0.15);
        continue;
      }
      const shift = (bx - W/2) * 0.55 + t.dir * (inPoss ? 7 : -5);
      const base = frame(t, p.bx, p.by);
      p.tx = clamp(base.x + shift, 3, W - 3);
      p.ty = clamp(base.y + (by - H/2) * (inPoss ? 0.25 : 0.4) + Math.sin((st.clock*2.1) + p.num) * 1.6, 2, H - 2);
    }
  }
  // the nearest defender presses the ball carrier
  if(ball.owner && st.phase === 'play'){
    const opp = T[1 - ball.owner.team.side];
    let best = null, bd = 1e9;
    for(const p of opp.players){ if(p === opp.gk || p.ov) continue; const d = dist(p, ball.owner); if(d < bd){ bd = d; best = p; } }
    if(best){ best.tx = ball.owner.x - opp.dir*-1.6; best.ty = ball.owner.y + 0.8; best.tx = ball.owner.x + opp.dir * -1.4; }
  }
  if(ball.fl && ball.fl.to && !ball.fl.to.ov){ ball.fl.to.tx = ball.fl.x1; ball.fl.to.ty = ball.fl.y1; }
}

function movePlayers(dt){
  const fast = st.phase === 'reset' || st.phase === 'kickoff';
  for(const p of P){
    const dx = p.tx - p.x, dy = p.ty - p.y, d = Math.hypot(dx, dy);
    const vmax = (p.ov && p.ov.sprint) ? 13 : fast ? 16 : 8.5;
    let ax = 0, ay = 0;
    if(d > 0.05){ const s = Math.min(vmax, d * 3.2); ax = dx/d*s; ay = dy/d*s; }
    p.vx += (ax - p.vx) * Math.min(1, dt*6); p.vy += (ay - p.vy) * Math.min(1, dt*6);
  }
  for(let i=0;i<P.length;i++) for(let j=i+1;j<P.length;j++){
    const a = P[i], b = P[j], dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy);
    if(d > 0 && d < 1.6){ const f = (1.6 - d) * 2.5; a.vx -= dx/d*f; a.vy -= dy/d*f; b.vx += dx/d*f; b.vy += dy/d*f; }
  }
  for(const p of P){ p.x = clamp(p.x + p.vx*dt, -1, W + 1); p.y = clamp(p.y + p.vy*dt, -1, H + 1); }
}

/* ---------------- ball ---------------- */
function kickTo(x1, y1, dur, opts){
  opts = opts || {};
  const from = ball.owner || null;
  if(from) ball.last = from.team;
  ball.owner = null;
  ball.fl = {x0: ball.x, y0: ball.y, x1, y1, t: 0, dur, peak: opts.peak || 0, cx: opts.cx, cy: opts.cy,
             to: opts.to || null, end: opts.end || null, team: from ? from.team : ball.last};
}
function passTo(p, dur, opts){
  opts = opts || {};
  // lead the receiver: aim where they will be when the ball arrives
  const tx = p.ov ? p.ov.x : p.tx, ty = p.ov ? p.ov.y : p.ty;
  const d = Math.hypot(tx - p.x, ty - p.y), run = Math.min(d, 9 * dur);
  const ax = d > 0 ? p.x + (tx - p.x) / d * run : p.x, ay = d > 0 ? p.y + (ty - p.y) / d * run : p.y;
  kickTo(ax, ay, dur, {...opts, to: p, end: opts.end || (() => receive(p))});
}
function receive(p){ ball.owner = p; ball.last = p.team; st.hold = rr(0.35, 0.9); }
function updateBall(dt){
  if(ball.fl){
    const f = ball.fl; f.t += dt; const u = Math.min(1, f.t / f.dur);
    if(f.cx !== undefined){ const a = (1-u)*(1-u), b = 2*(1-u)*u, c = u*u; ball.x = a*f.x0 + b*f.cx + c*f.x1; ball.y = a*f.y0 + b*f.cy + c*f.y1; }
    else { ball.x = f.x0 + (f.x1 - f.x0)*u; ball.y = f.y0 + (f.y1 - f.y0)*u; }
    ball.z = 4 * f.peak * u * (1 - u);
    if(u >= 1){ ball.fl = null; ball.z = 0; if(f.end) f.end(); }
  } else if(ball.owner){
    const o = ball.owner, sp = Math.hypot(o.vx, o.vy);
    const ux = sp > 0.3 ? o.vx/sp : o.team.dir, uy = sp > 0.3 ? o.vy/sp : 0;
    ball.x = o.x + ux*0.75; ball.y = o.y + uy*0.75; ball.z = 0;
  }
  const t = ball.owner ? ball.owner.team : (ball.fl ? ball.fl.team : ball.last);
  if(t && (st.phase === 'play' || st.phase === 'script')) st.poss[t.side] += dt;
}

/* ---------------- open play ---------------- */
function goalX(t){ return t.side === 0 ? W : 0; }
function openPlay(dt){
  const o = ball.owner;
  if(!o || ball.fl) return;
  // dribble forward a little
  if(!o.ov){ o.tx = clamp(o.x + o.team.dir * 6, 2, W - 2); o.ty = o.y + (H/2 - o.y) * 0.1; }
  st.hold -= dt;
  if(st.hold > 0) return;
  const t = o.team, opp = T[1 - t.side];
  const dg = Math.abs(goalX(t) - o.x);
  const next = M.goals[st.gi];
  const goalSoon = next && (next.minute - st.clock) / MPS < 4.5;
  if(o === t.gk){ return passTo(pick(t.players.filter(p => p.pos === 'DF' || p.pos === 'MF')), 1.0, {peak: 3}); }
  if(dg < 28 && st.chances[t.side] > 0 && !goalSoon && R() < 0.22){ return chance(o); }
  // choose a pass: forward progress, open space, not too far
  let best = null, bs = -1e9;
  for(const p of t.players){
    if(p === o || p === t.gk) continue;
    const d = dist(p, o); if(d < 5 || d > 38) continue;
    let near = 1e9; for(const q of opp.players) near = Math.min(near, dist(q, p));
    const sc = (p.x - o.x) * t.dir * 0.55 + Math.min(near, 8) * 0.9 - d * 0.12 + R() * 6;
    if(sc > bs){ bs = sc; best = p; }
  }
  if(!best){ st.hold = 0.3; return; }
  const d = dist(best, o), dur = clamp(d / 26, 0.35, 1.3), lofted = d > 26 && R() < 0.6;
  if(!goalSoon && R() < 0.10 + d / 300){
    // intercepted
    let cut = null, cd = 1e9; const mx = (o.x + best.x)/2, my = (o.y + best.y)/2;
    for(const q of opp.players){ if(q === opp.gk) continue; const dd = Math.hypot(q.x - mx, q.y - my); if(dd < cd){ cd = dd; cut = q; } }
    if(cut){ return passTo(cut, dur * 0.7, {peak: lofted ? 2 : 0}); }
  }
  passTo(best, dur, {peak: lofted ? 3 : 0});
}

function chance(o){
  const t = o.team, opp = T[1 - t.side], gk = opp.gk;
  st.chances[t.side]--; st.shots[t.side]++;
  const onTarget = R() < 0.55, min = curMin();
  const ty = onTarget ? rr(GOAL_Y0 + 0.6, GOAL_Y1 - 0.6) : (R() < 0.5 ? rr(GOAL_Y0 - 5, GOAL_Y0 - 0.8) : rr(GOAL_Y1 + 0.8, GOAL_Y1 + 5));
  const gx = goalX(t);
  if(onTarget){
    st.ont[t.side]++;
    gk.ov = {x: gx - t.dir * 1.2, y: ty, sprint: true};
    kickTo(gx - t.dir * 1.0, ty, 0.42, {peak: R() < 0.4 ? 1.6 : 0.4, end: () => {
      gk.ov = null; ball.owner = gk; ball.last = opp; st.hold = 0.9;
      say(min, `${o.short} (${t.name}) tries a shot${Math.abs(gx - o.x) > 20 ? ' from distance' : ''} — saved by ${gk.short}.`);
    }});
  } else {
    kickTo(gx + t.dir * 2.5, ty, 0.45, {peak: R() < 0.5 ? 2.2 : 0.6, end: () => {
      say(min, `${o.short} (${t.name}) ${R() < .5 ? 'drags it wide' : 'fires over the bar'}.`, 'hl');
      // goal kick
      st.phase = 'dead'; st.timer = 0.9;
      st.after = () => { ball.x = goalX(t) - t.dir * 5.5; ball.y = rr(28, 40); ball.owner = gk; gk.x = ball.x - opp.dir*0.8; gk.y = ball.y; ball.last = opp; st.hold = 0.4; st.phase = 'play'; };
    }});
  }
  updateStats();
}

/* ---------------- scripted goals ---------------- */
function A(t, x, y){ return frame(t, x, y); }            // attacking-frame position for team t
function role(t, pos, not){ const c = t.players.filter(p => p.pos === pos && !(not||[]).includes(p)); return c.length ? pick(c) : null; }
function findScorer(t, g){
  return t.players.find(p => p.name === g.scorer) || t.players.find(p => p.pos === g.pos && p !== t.gk) || t.players[t.players.length-1];
}
const LEAD = {"Strike": 3.0, "Header": 3.4, "Corner Kick": 5.4, "Penalty Kick": 4.9, "Free Kick": 5.0};  // measured build-up length (anim s)
function leadMin(g){ return (LEAD[g.type] || 4.4) * MPS; }

function startScript(g){
  const t = g.side === 'home' ? T[0] : T[1], opp = T[1 - t.side];
  const s = findScorer(t, g);
  const helpers = t.players.filter(p => p !== s && p !== t.gk);
  const mf = role(t, 'MF', [s]) || pick(helpers), fw = role(t, 'FW', [s, mf]) || pick(helpers.filter(p => p !== mf));
  const steps = [];
  const go = (fn) => steps.push(fn);
  const wait = (sec) => go(done => { st.wait = sec; st.waitDone = done; });
  const win = () => go(done => {
    if((ball.owner && ball.owner.team === t) || (ball.fl && ball.fl.to && ball.fl.to.team === t)) return done();
    let best = null, bd = 1e9; for(const p of t.players){ if(p === t.gk) continue; const d = dist(p, ball); if(d < bd){ bd = d; best = p; } }
    if(ball.fl) ball.fl = null;
    passTo(best, clamp(bd/24, 0.3, 0.9), {end: () => { receive(best); done(); }});
  });
  const pass = (p, dur, peak) => go(done => passTo(p, dur, {peak: peak || 0, end: () => { receive(p); st.hold = 9; done(); }}));
  const place = (p, x, y, sprint) => { const q = A(t, x, y); p.ov = {x: q.x, y: q.y, sprint: sprint !== false}; };
  const placeOpp = (p, x, y) => { const q = A(t, x, y); p.ov = {x: q.x, y: q.y, sprint: true}; };
  const corner = R() < 0.5 ? 0 : 1, sideY = (y) => corner ? H - y : y;
  const goalAim = () => { const left = R() < 0.5; return {y: left ? GOAL_Y0 + 0.7 : GOAL_Y1 - 0.7, gkY: left ? GOAL_Y1 - 1.5 : GOAL_Y0 + 1.5}; };
  const finish = (dur, peak, label) => go(done => {
    const aim = goalAim(), gpos = A(t, W + 1.3, aim.y), gkp = A(t, W - 1.4, aim.gkY);
    opp.gk.ov = {x: gkp.x, y: gkp.y, sprint: true};
    st.shots[t.side]++; st.ont[t.side]++;
    kickTo(gpos.x, gpos.y, dur, {peak: peak, end: () => { scoreGoal(t, s, g, label); done(); }});
  });

  if(g.type === 'Penalty Kick'){
    win(); pass(fw === s ? mf : fw, 0.7);
    go(done => { place(s, 86, sideY(26)); done(); });
    pass(s, 0.6);
    go(done => { place(s, 95, sideY(30)); const d = role(opp, 'DF') || opp.players[1]; const q = A(t, 95.8, sideY(31)); d.ov = {x: q.x, y: q.y, sprint: true}; st.wait = 0.8; st.waitDone = done; });
    go(done => { say(curMin(), `PENALTY to ${t.name}! ${s.short} is brought down in the box.`, 'hl'); st.phase = 'dead-script';
      // everyone out of the box, taker at the spot
      P.forEach(p => { if(p === s || p === opp.gk) return; const ang = (p.num + p.team.side*11) / 22 * Math.PI - Math.PI/2; place(p, 84 - Math.abs(Math.sin(ang))*6, H/2 + Math.cos(ang)*14 * (p.team === t ? 1 : -1)); });
      place(s, 92.2, H/2); placeOpp(opp.gk, W - 0.6, H/2);
      ball.owner = null; const q = A(t, W - 11, H/2); ball.fl = {x0: ball.x, y0: ball.y, x1: q.x, y1: q.y, t: 0, dur: 1.2, peak: 0, end: null, team: t};
      st.wait = 1.8; st.waitDone = done; });
    go(done => { place(s, W - 11.6, H/2); st.wait = 0.55; st.waitDone = () => { st.phase = 'script'; done(); }; });
    finish(0.28, 0.5, 'penalty');
  } else if(g.type === 'Free Kick'){
    const fy = rr(26, 42);
    win(); pass(mf === s ? fw : mf, 0.75);
    go(done => { const r = fw === s ? mf : fw; place(r, 79, fy); passTo(r, 0.7, {end: () => { receive(r); st.hold = 9; st.wait = 0.5; st.waitDone = done; }}); });
    go(done => { say(curMin(), `Foul — free kick to ${t.name} in a dangerous position.`, 'hl'); st.phase = 'dead-script';
      const bx = 80, by = fy, gxv = W - bx, gyv = H/2 - by, gl = Math.hypot(gxv, gyv), wx = bx + gxv/gl*9.15, wy = by + gyv/gl*9.15;
      const wall = opp.players.filter(p => p !== opp.gk).slice(0, 4);
      wall.forEach((p, k) => placeOpp(p, wx, wy + (k - 1.5) * 0.9 * (gxv/gl)));
      opp.players.filter(p => p !== opp.gk && !wall.includes(p)).forEach((p, k) => placeOpp(p, rr(90, 100), rr(22, 46)));
      t.players.filter(p => p !== t.gk && p !== s).forEach((p, k) => place(p, k < 4 ? rr(91, 99) : rr(62, 76), k < 4 ? rr(24, 44) : rr(14, 54)));
      place(s, bx - 2.2, by - 1.0); placeOpp(opp.gk, W - 1.2, H/2);
      ball.owner = null; const q = A(t, bx, by); ball.fl = {x0: ball.x, y0: ball.y, x1: q.x, y1: q.y, t: 0, dur: 0.8, peak: 0, end: null, team: t};
      st.wait = 1.8; st.waitDone = done; });
    go(done => { place(s, 79.4, fy - 0.4); st.wait = 0.5; st.waitDone = () => { st.phase = 'script'; done(); }; });
    go(done => {
      const aim = goalAim(), gpos = A(t, W + 1.2, aim.y), gkp = A(t, W - 1.3, aim.gkY), mid = A(t, (80 + W)/2, (fy + aim.y)/2 + (aim.y < H/2 ? 6 : -6));
      opp.gk.ov = {x: gkp.x, y: gkp.y, sprint: true}; st.shots[t.side]++; st.ont[t.side]++;
      kickTo(gpos.x, gpos.y, 0.62, {peak: 2.4, cx: mid.x, cy: mid.y, end: () => { scoreGoal(t, s, g, 'freekick'); done(); }});
    });
  } else if(g.type === 'Corner Kick'){
    const taker = (mf && mf !== s) ? mf : (fw !== s ? fw : helpers[0]);
    const box = fw !== s ? fw : (helpers.find(p => p !== taker && p !== s) || helpers[0]);
    win(); pass(taker === s ? box : taker, 0.75);
    go(done => { place(box, 90, sideY(20)); const q = ball.owner || box; passTo(box, 0.8, {end: () => { receive(box); st.hold = 9; done(); }}); });
    go(done => { st.shots[t.side]++; const blk = role(opp, 'DF') || opp.players[1]; const bq = A(t, 95, sideY(19)); blk.ov = {x: bq.x, y: bq.y, sprint: true};
      const out = A(t, W + 1.5, sideY(14)); kickTo(out.x, out.y, 0.55, {peak: 0.6, end: () => { blk.ov = null; done(); }}); });
    go(done => { say(curMin(), `${box.short}'s effort is blocked behind — corner to ${t.name}.`, 'hl'); st.phase = 'dead-script';
      const flag = A(t, W - 0.3, corner ? H - 0.3 : 0.3);
      place(taker, W - 1.2, corner ? H - 1.0 : 1.0);
      t.players.filter(p => p !== t.gk && p !== taker).forEach((p, k) => place(p, p === s ? 92 : (k < 5 ? rr(93, 100) : rr(66, 80)), p === s ? H/2 + rr(-6, 6) : (k < 5 ? rr(26, 42) : rr(16, 52))));
      opp.players.filter(p => p !== opp.gk).forEach((p, k) => placeOpp(p, k < 7 ? rr(94, 101) : rr(80, 88), k < 7 ? rr(27, 41) : rr(20, 48)));
      placeOpp(opp.gk, W - 1.0, H/2 + (corner ? 2 : -2));
      ball.owner = null; ball.fl = {x0: ball.x, y0: ball.y, x1: flag.x, y1: flag.y, t: 0, dur: 1.0, peak: 0, end: null, team: t};
      st.wait = 2.0; st.waitDone = done; });
    go(done => { place(s, 97.5, H/2 + rr(-4, 4)); st.phase = 'script'; const q = A(t, 97.5, s.ov ? (t.side === 0 ? s.ov.y : H - s.ov.y) : H/2);
      kickTo(s.ov.x, s.ov.y, 0.85, {peak: 3.4, to: s, end: () => { done(); }}); });
    finish(0.24, 0.8, 'corner');
  } else if(g.type === 'Header'){
    const wide = (fw && fw !== s) ? fw : (mf !== s ? mf : helpers[0]);
    win(); pass(mf === s || mf === wide ? helpers.find(p => p !== s && p !== wide) : mf, 0.75);
    go(done => { place(wide, 88, sideY(7)); place(s, 86, H/2 + rr(-6, 6)); passTo(wide, 0.95, {peak: 1.5, end: () => { receive(wide); st.hold = 9; st.wait = 0.45; st.waitDone = done; }}); });
    go(done => { place(s, 98, H/2 + rr(-4, 4)); const q = s.ov;
      kickTo(q.x, q.y, 0.8, {peak: 3.0, to: s, end: () => { done(); }}); });
    finish(0.26, 0.9, 'header');
  } else {   // Strike
    const a = mf === s ? helpers[0] : mf, b = (fw && fw !== s && fw !== a) ? fw : helpers.find(p => p !== s && p !== a);
    win(); pass(a, 0.7);
    go(done => { place(b, 80, H/2 + rr(-14, 14)); passTo(b, 0.8, {end: () => { receive(b); st.hold = 9; done(); }}); });
    go(done => { place(s, 93, H/2 + rr(-7, 7)); st.wait = 0.25; st.waitDone = done; });
    go(done => { passTo(s, 0.6, {end: () => { receive(s); st.hold = 9; st.wait = 0.2; st.waitDone = done; }}); });
    finish(0.3, R() < 0.3 ? 1.2 : 0.3, 'strike');
  }
  st.script = {g, steps, k: 0, t, s, el: 0, eta: LEAD[g.type] || 4.4};
  st.phase = 'script';
  nextStep();
}
function nextStep(){
  const sc = st.script; if(!sc) return;
  if(sc.k >= sc.steps.length){ st.script = null; return; }
  const f = sc.steps[sc.k++];
  f(() => nextStep());
}

function scoreGoal(t, s, g, kind){
  st.score[t.side]++; st.gi++;
  const el = t.side === 0 ? $('hs') : $('as');
  if(!skipping){ el.textContent = st.score[t.side]; el.classList.remove('pop'); void el.offsetWidth; el.classList.add('pop'); }
  const how = {penalty: 'sends the keeper the wrong way from the spot', freekick: 'curls the free kick over the wall and in',
               corner: 'meets the corner and finishes', header: 'rises to head it home', strike: 'finishes clinically'}[kind] || 'scores';
  say(g.minute, `GOAL! ${s.name || s.short} (${t.name}) ${how}. ${M.home.name} ${st.score[0]}–${st.score[1]} ${M.away.name}.`, 'goal');
  if(!skipping){
    $('bannerW').textContent = `${g.minute}'  ${s.name || s.short} · ${t.name}`; $('banner').style.setProperty('--k', t.kit);
    $('banner').classList.add('show');
  }
  (st.gclk = st.gclk || []).push([g.minute, +(st.clock + GOAL_AT).toFixed(2), g.type, st.script ? +st.script.el.toFixed(2) : -1]);
  st.clock = Math.max(st.clock, g.minute - GOAL_AT);
  st.phase = 'celebrate'; st.timer = 2.6; st.script = null; ball.owner = null; ball.fl = null;
  const flagq = A(t, W - 2, s.y < H/2 ? 3 : H - 3);
  P.forEach(p => { p.ov = null; });
  s.ov = {x: flagq.x, y: flagq.y, sprint: true};
  t.players.forEach(p => { if(p !== s && p !== t.gk && R() < 0.7) p.ov = {x: flagq.x + rr(-4, 4) - t.dir*rr(1, 6), y: flagq.y + rr(-4, 4), sprint: true}; });
  st.concede = 1 - t.side;
  updateStats();
}

/* ---------------- main step ---------------- */
function step(dt){
  if(st.done) return;
  if(st.phase === 'pre'){ st.phase = 'kickoff'; }
  const clockRuns = st.phase === 'play' || st.phase === 'script' || st.phase === 'dead' || st.phase === 'dead-script';
  if(clockRuns){
    // the clock may never pass the next goal's real minute, and during a goal's
    // build-up it runs at whatever rate lands the goal exactly on that minute
    const halfEnd = st.half === 1 ? 45 : 90, ng = M.goals[st.gi];
    const cap = (ng && (st.half === 2 || ng.minute <= 45)) ? Math.min(halfEnd, ng.minute - GOAL_AT) : halfEnd;
    let rate = MPS;
    if(st.script){ st.script.el += dt; const left = Math.max(0.35, st.script.eta - st.script.el);
      rate = clamp((st.script.g.minute - GOAL_AT - st.clock) / left, 0.08 * MPS, 3 * MPS); }
    st.clock = Math.max(st.clock, Math.min(st.clock + dt * rate, cap));
  }

  if(st.wait !== undefined && st.wait !== null){ st.wait -= dt; if(st.wait <= 0){ const d = st.waitDone; st.wait = null; st.waitDone = null; if(d) d(); } }

  if(st.phase === 'kickoff'){
    st.timer -= dt;
    if(st.timer <= 0){
      const kt = T[st.kick], taker = ball.taker; taker.ov = null;
      ball.owner = taker; ball.last = kt; st.phase = 'play';
      const back = kt.players.filter(p => p.pos === 'MF'); passTo(pick(back.length ? back : kt.players.slice(1)), 0.7);
    }
  } else if(st.phase === 'celebrate'){
    st.timer -= dt;
    if(st.timer <= 0){ $('banner').classList.remove('show'); st.phase = 'reset'; st.timer = 1.3; P.forEach(p => p.ov = null); kickoffSetup(st.concede); st.phase = 'kickoff'; st.timer = 1.6; }
  } else if(st.phase === 'dead'){
    st.timer -= dt; if(st.timer <= 0 && st.after){ const a = st.after; st.after = null; a(); }
  } else if(st.phase === 'halftime'){
    st.timer -= dt;
    if(st.timer <= 0){ $('overlay').classList.remove('show'); st.half = 2; st.clock = 45; flip = true; kickoffSetup(1); say(46, 'The second half is under way.', 'hl'); }
  } else if(st.phase === 'play'){
    const g = M.goals[st.gi];
    if(g && (st.half === 2 || g.minute <= 45) && st.clock >= g.minute - leadMin(g)) startScript(g);
    else if(st.half === 1 && st.clock >= 45 && !(g && g.minute <= 45)) halfTime();
    else if(st.half === 2 && st.clock >= 90 && !g) fullTime();
    else openPlay(dt);
  }
  teamTargets();
  movePlayers(dt);
  updateBall(dt);
}
function halfTime(){
  st.phase = 'halftime'; st.timer = 2.2; ball.fl = null; ball.owner = null;
  say(45, `Half-time: ${M.home.name} ${st.score[0]}–${st.score[1]} ${M.away.name}.`, 'hl');
  if(!skipping){ $('ovT').textContent = 'HALF-TIME'; $('ovS').textContent = `${st.score[0]} – ${st.score[1]}`; $('ovBtn').style.display = 'none'; $('overlay').classList.add('show'); }
  P.forEach(p => { p.ov = null; const m = frame(p.team, 20, H/2 + (p.num - 6)*2); p.tx = m.x; p.ty = m.y; });
}
function fullTime(){
  st.done = true; st.phase = 'fulltime';
  say(90, `Full-time: ${M.home.name} ${st.score[0]}–${st.score[1]} ${M.away.name}.`, 'goal');
  $('ovT').textContent = 'FULL-TIME'; $('ovS').textContent = `${st.score[0]} – ${st.score[1]}`; $('ovBtn').style.display = '';
  $('overlay').classList.add('show'); updateStats(); setPlaying(false);
}

/* ---------------- draw ---------------- */
let showNames = false;
function draw(){
  ctx.clearRect(0,0,CW,CH);
  if(pitchImg) ctx.drawImage(pitchImg, 0, 0, CW, CH);
  const r = Math.max(5, S * 1.05);
  // shadows
  ctx.fillStyle = 'rgba(0,0,0,.28)';
  for(const p of P){ ctx.beginPath(); ctx.ellipse(px(p.x) + r*.25, py(p.y) + r*.55, r*.95, r*.45, 0, 0, Math.PI*2); ctx.fill(); }
  // players
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  for(const p of P){
    const isGk = p === p.team.gk, X = px(p.x), Y = py(p.y);
    ctx.beginPath(); ctx.arc(X, Y, r, 0, Math.PI*2);
    ctx.fillStyle = isGk ? (p.team.side === 0 ? '#c6ff00' : '#ff80ab') : p.team.kit; ctx.fill();
    ctx.lineWidth = ball.owner === p ? 2.6 : 1.4; ctx.strokeStyle = ball.owner === p ? '#ffb627' : 'rgba(0,0,0,.55)'; ctx.stroke();
    ctx.fillStyle = isGk ? '#111' : p.team.num; ctx.font = `700 ${Math.round(r*1.05)}px "IBM Plex Mono",monospace`;
    ctx.fillText(p.num, X, Y + 0.5);
    if(showNames || ball.owner === p || (st.phase === 'celebrate' && p.ov && p.ov.sprint && p === lastScorer())){
      ctx.font = `600 ${Math.max(10, Math.round(r*0.95))}px "IBM Plex Mono",monospace`;
      const label = p.short, w = ctx.measureText(label).width + 8;
      ctx.fillStyle = 'rgba(5,8,6,.72)'; ctx.fillRect(X - w/2, Y - r - 15, w, 13);
      ctx.fillStyle = '#fff'; ctx.fillText(label, X, Y - r - 8.5);
    }
  }
  // ball
  const bx = px(ball.x), by = py(ball.y), bz = ball.z * S * 0.55, br = Math.max(3, S*0.42) * (1 + ball.z*0.07);
  ctx.fillStyle = 'rgba(0,0,0,.35)'; ctx.beginPath(); ctx.ellipse(bx + bz*0.3, by + 1, br*0.9, br*0.45, 0, 0, Math.PI*2); ctx.fill();
  ctx.beginPath(); ctx.arc(bx, by - bz, br, 0, Math.PI*2); ctx.fillStyle = '#fff'; ctx.fill(); ctx.lineWidth = 1; ctx.strokeStyle = '#222'; ctx.stroke();
  ctx.fillStyle = '#222'; ctx.beginPath(); ctx.arc(bx - br*0.2, by - bz - br*0.15, br*0.32, 0, Math.PI*2); ctx.fill();
  // clock + stats
  const mm = Math.floor(st.clock), ss = Math.floor((st.clock - mm) * 60);
  const lbl = st.phase === 'halftime' ? 'HALF-TIME' : st.phase === 'fulltime' ? 'FULL-TIME' : `${String(mm).padStart(2,'0')}:${String(ss).padStart(2,'0')} · ${st.half === 1 ? '1ST' : '2ND'} HALF`;
  $('clock').innerHTML = (st.phase === 'fulltime' ? '' : '<span class="live"></span>') + lbl;
}
function lastScorer(){ return st.script ? st.script.s : P.find(p => p.ov && p.ov.sprint); }
let statTick = 0;
function updateStats(){
  const tot = st.poss[0] + st.poss[1], h = Math.round(st.poss[0] / tot * 100);
  $('sPh').textContent = h + '%'; $('sPa').textContent = (100 - h) + '%';
  $('pbH').style.width = h + '%'; $('pbA').style.width = (100 - h) + '%';
  $('sSh').textContent = st.shots[0]; $('sSa').textContent = st.shots[1];
  $('sTh').textContent = st.ont[0]; $('sTa').textContent = st.ont[1];
}

/* ---------------- loop & controls ---------------- */
let playing = true, speed = 1, last = 0, acc = 0, skipping = false;
function setPlaying(v){ playing = v; $('play').innerHTML = v ? '&#10073;&#10073; Pause' : '&#9654; Play'; }
function loop(ts){
  const el = last ? Math.min(0.1, (ts - last) / 1000) : 0; last = ts;
  if(playing && !st.done){ acc += el * speed; let n = 0; while(acc >= DT && n < 40){ step(DT); acc -= DT; n++; } }
  draw();
  if(++statTick % 20 === 0) updateStats();
  requestAnimationFrame(loop);
}
function restart(){ load(+$('pick').value); setPlaying(true); }
function skipToGoal(k){
  // fast-forward (no drawing) until goal k's build-up starts
  if(k < st.gi) load(+$('pick').value);
  skipping = true; let n = 0;
  while(!st.done && n < 200000 && !(st.script && M.goals.indexOf(st.script.g) === k)){ step(DT); n++; }
  skipping = false;
  $('hs').textContent = st.score[0]; $('as').textContent = st.score[1];
  $('feed').innerHTML = st.msgs.slice().reverse().map(m => `<li class="${m.cls||''}"><span class="m">${m.min}'</span>${esc(m.text)}</li>`).join('');
  flip = st.half === 2; $('overlay').classList.remove('show'); updateStats(); setPlaying(true);
}
$('play').onclick = () => { if(st.done){ restart(); return; } setPlaying(!playing); };
$('restart').onclick = restart;
$('ovBtn').onclick = restart;
$('pick').onchange = restart;
$('nextGoal').onclick = () => { if(st.gi < M.goals.length) skipToGoal(st.gi); };
$('names').onchange = e => { showNames = e.target.checked; };
document.querySelectorAll('.sp .btn').forEach(b => b.onclick = () => { speed = +b.dataset.s; document.querySelectorAll('.sp .btn').forEach(x => x.classList.toggle('on', x === b)); });
$('tl').onclick = e => { const li = e.target.closest('li[data-g]'); if(li){ skipToGoal(+li.dataset.g); $('stage').scrollIntoView({behavior: 'smooth', block: 'center'}); } };
window.addEventListener('resize', resize);

window.__replay = {check(i){ $('pick').value = String(i); load(i); skipping = true; let n = 0; while(!st.done && n < 400000){ step(DT); n++; } skipping = false; return {late: (st.gclk||[]).map(a => [a[0], +(a[1]-a[0]).toFixed(1), a[2], a[3]]), score: st.score.slice(), goals: st.gi, want: [M.hg, M.ag], ngoals: M.goals.length, steps: n, clock: st.clock}; }};
$('pick').value = String(DEFAULT);
resize(); load(DEFAULT);
requestAnimationFrame(loop);
})();
</script>
</body>
</html>'''


if __name__ == "__main__":
    config = load_json("league_config.json")
    matches = load_json("matches.json")
    html = render(config, matches)
    out_dir = os.path.join(BASE, "matchday-replay")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(html)
    print(f"Rendered -> {out_dir}/index.html")
