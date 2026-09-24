"""
Renders trade-site/index.html -- the Trade Center: propose a trade,
respond to one sent to your team, and see the season's real trade log.

Reads data/deals.json (trade_rules), data/league_config.json (team
names), and data/trades.json (the FINAL applied/voided outcomes --
written by engine/resolve_trade.py after it re-checks roster ownership
and the salary cap for real; a trade both teams accepted can still show
up here as VOIDED with a reason if something about the rosters changed
in between). The live pending/accepted/declined negotiation itself
happens client-side against the Sheet (assets/submissions.js's
initTradeProposeForm/initTradeRespondForm, via ?catalog=1) -- this page
only server-renders the settled history, same division of labor as
every other marketplace page on this site.

Run after every resolve_trade.py call (engine/auto_resolve.py already
does this as part of its regular regenerate step), then republish.
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


def render(config, deals, trades, calendar):
    tr = deals["trade_rules"]
    team_map = {t["team_id"]: t["name"] for t in config["teams"]}

    def side_label(entry):
        return ", ".join(p["name"] for p in entry) if entry else "&mdash;"

    log_rows = []
    for t in sorted(trades.get("applied", []) + trades.get("voided", []),
                     key=lambda t: t.get("applied_at") or t.get("voided_at") or "", reverse=True):
        outcome = "applied" if "applied_at" in t else "voided"
        proposer = team_map.get(int(t["proposer_team_id"]), f"Team {t['proposer_team_id']}")
        receiver = team_map.get(int(t["receiver_team_id"]), f"Team {t['receiver_team_id']}")
        cash_out = int(t.get("cash_from_proposer") or 0)
        cash_in = int(t.get("cash_from_receiver") or 0)
        give = side_label(t.get("players_out", [])) + (f" + {money(cash_out)}" if cash_out else "")
        get = side_label(t.get("players_in", [])) + (f" + {money(cash_in)}" if cash_in else "")
        detail = t.get("void_reason", "") if outcome == "voided" else t.get("rationale", "")
        log_rows.append(f'''
        <tr>
          <td>{proposer} &harr; {receiver}</td>
          <td>{give}<br><span class="trade-arrow">for</span><br>{get}</td>
          <td><span class="sub-status sub-status-{outcome}">{outcome}</span></td>
          <td class="trade-detail">{detail}</td>
          <td>{t.get("applied_at") or t.get("voided_at") or ""}</td>
        </tr>''')
    log_html = "".join(log_rows) or '<tr><td colspan="5" class="sub-empty">No trades have been finalized yet.</td></tr>'

    trade_count_rows = "".join(
        f'<tr><td>{t["name"]}</td><td class="num">{trades.get("team_trade_count", {}).get(str(t["team_id"]), 0)}/3 players traded</td></tr>'
        for t in sorted(config["teams"], key=lambda t: t["team_id"])
    )

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trade Center</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;700;800&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<link rel="stylesheet" href="../assets/submissions.css">
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
.how-it-works p{{margin:0 0 10px;}}
.how-it-works p:last-child{{margin-bottom:0;}}

table{{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--surface);border:1px solid var(--line);border-radius:3px;box-shadow:var(--shadow);}}
thead th{{background:var(--navy);color:var(--navy-ink);text-align:left;padding:9px 10px;font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;}}
thead th.num{{text-align:right;}}
tbody td{{padding:7px 10px;border-top:1px solid var(--line);vertical-align:top;}}
.trade-arrow{{font-family:"IBM Plex Mono",monospace;font-size:10px;color:var(--muted);text-transform:uppercase;}}
.trade-detail{{font-size:12.5px;color:var(--muted);max-width:320px;}}

footer{{max-width:1180px;margin:0 auto;padding:0 clamp(16px,4vw,48px) 50px;color:var(--muted);font-size:12px;font-family:"IBM Plex Mono",monospace;}}
{NAV_CSS}
</style>
</head>
<body>
{render_nav("trade")}
<div class="masthead">
  <div class="masthead-inner">
    <h1>Trade Center</h1>
    <p>{config["league_name"]} &middot; propose a trade, respond to one sent to you, deadline before Round 7</p>
  </div>
</div>

<div class="wrap">
  <section>
    <div class="section-head"><h2>How It Works</h2></div>
    <div class="how-it-works">
      <p><b>Deadline.</b> {tr["deadline"]}</p>
      <p><b>How many players.</b> {tr["player_limits"]}</p>
      <p><b>Voluntary.</b> {tr["voluntary"]}</p>
      <p><b>Salary cap.</b> {tr["salary_cap"]}</p>
      <p><b>Cash considerations.</b> {tr["cash_considerations"]}</p>
      <p><b>Approval.</b> {tr["approval"]}</p>
      <p><b>Trade Day.</b> {tr["mid_season_trade_day"]}</p>
    </div>
  </section>

  <section>
    <div class="section-head"><h2>Players Traded This Season</h2><span class="section-note">3-player season limit, per team</span></div>
    <table>
      <thead><tr><th>Team</th><th class="num">Traded so far</th></tr></thead>
      <tbody>{trade_count_rows}</tbody>
    </table>
  </section>

  <section>
    <p class="sub-backend-warning" hidden>Backend not configured yet &mdash; submissions are disabled until BACKEND_URL is set in assets/config.js.</p>
    <div class="sub-card">
      <h2>Propose a Trade</h2>
      <p class="sub-sub">Pick who you're giving and who you want back -- both sides must be the same count (1-3 players). Add cash on either side to bridge a value gap. Nothing moves until the other team accepts.</p>
      <div class="sub-grid">
        <div class="sub-field"><label for="tp-team">Your Team</label><select id="tp-team" class="sub-team-select"></select></div>
        <div class="sub-field"><label for="tp-pin">Team PIN</label><input type="password" inputmode="numeric" maxlength="4" id="tp-pin" class="sub-pin" placeholder="4-digit PIN"></div>
        <div class="sub-field"><label for="tp-partner">Trade Partner</label><select id="tp-partner" class="sub-team-select"></select></div>
      </div>

      <h3 style="font-size:14px;margin:18px 0 8px;">You Give Up</h3>
      <div class="sub-search-row">
        <input type="text" id="tp-give-search" placeholder="Search your roster by name...">
        <select id="tp-give-pos">
          <option value="ALL">All positions</option>
          <option value="GK">GK</option><option value="DF">DF</option>
          <option value="MF">MF</option><option value="FW">FW</option>
        </select>
      </div>
      <ul class="sub-results" id="tp-give-results"></ul>
      <p class="sub-count-note" id="tp-give-count"></p>
      <ul class="sub-board" id="tp-give-list"></ul>
      <div class="sub-field" style="max-width:280px;margin-top:10px;"><label for="tp-cash-give">Cash you add ($, optional)</label><input type="number" id="tp-cash-give" placeholder="0" min="0"></div>

      <h3 style="font-size:14px;margin:22px 0 8px;">You Want Back</h3>
      <div class="sub-search-row">
        <input type="text" id="tp-want-search" placeholder="Search the partner's roster by name...">
        <select id="tp-want-pos">
          <option value="ALL">All positions</option>
          <option value="GK">GK</option><option value="DF">DF</option>
          <option value="MF">MF</option><option value="FW">FW</option>
        </select>
      </div>
      <ul class="sub-results" id="tp-want-results"></ul>
      <p class="sub-count-note" id="tp-want-count"></p>
      <ul class="sub-board" id="tp-want-list"></ul>
      <div class="sub-field" style="max-width:280px;margin-top:10px;"><label for="tp-cash-want">Cash you want back ($, optional)</label><input type="number" id="tp-cash-want" placeholder="0" min="0"></div>

      <div class="sub-field" style="margin-top:16px;"><label for="tp-rationale">Rationale (2-4 sentences -- graded)</label><textarea id="tp-rationale" rows="3"></textarea></div>
      <button class="sub-btn" id="tp-submit" style="margin-top:10px;">Send Trade Proposal</button>
      <p class="sub-msg" id="tp-msg"></p>
    </div>
  </section>

  <section>
    <div class="sub-card">
      <h2>Respond to a Trade</h2>
      <p class="sub-sub">Pick your team to see any trades sent to you, then accept or decline.</p>
      <div class="sub-grid">
        <div class="sub-field"><label for="tr-team">Your Team</label><select id="tr-team" class="sub-team-select"></select></div>
        <div class="sub-field"><label for="tr-pin">Team PIN</label><input type="password" inputmode="numeric" maxlength="4" id="tr-pin" class="sub-pin" placeholder="4-digit PIN"></div>
      </div>
      <ul class="sub-board" id="tr-inbox" style="margin-top:10px;"></ul>
      <p class="sub-msg" id="tr-msg"></p>
    </div>
  </section>

  <section>
    <div class="section-head"><h2>Live Proposals</h2><span class="section-note">pending / accepted / declined -- updates as teams respond</span></div>
    <table>
      <thead><tr><th>Teams</th><th>Trade</th><th>Status</th><th>Proposed</th></tr></thead>
      <tbody id="tp-live-log"><tr><td colspan="4" class="sub-empty">Loading...</td></tr></tbody>
    </table>
  </section>

  <section>
    <div class="section-head"><h2>Final Trade Log</h2><span class="section-note">applied or voided, after roster/cap re-check -- the official record</span></div>
    <table>
      <thead><tr><th>Teams</th><th>Trade</th><th>Result</th><th>Detail</th><th>Date</th></tr></thead>
      <tbody>{log_html}</tbody>
    </table>
  </section>
</div>

<footer>{config["league_name"]} &middot; Trade Center &mdash; roster and salary-cap checks match engine/resolve_trade.py exactly</footer>

<script src="../assets/config.js"></script>
<script src="../assets/submissions.js"></script>
<script>
(async function initTradeCenter() {{
  await Promise.all([loadPlayers(), loadTeams(), loadCatalog()]);
  populateTeamSelects();
  initTradeProposeForm();
  initTradeRespondForm();
  renderTradeLog();
}})();
</script>
</body>
</html>'''


if __name__ == "__main__":
    config = load_json("league_config.json")
    deals = load_json("deals.json")
    calendar = load_json("season_calendar.json")
    trades_path = os.path.join(BASE, "data", "trades.json")
    trades = load_json("trades.json") if os.path.exists(trades_path) else {"applied": [], "voided": [], "team_trade_count": {}, "team_cash_net": {}}
    html = render(config, deals, trades, calendar)
    out_dir = os.path.join(BASE, "trade-site")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Rendered -> {out_path}")
