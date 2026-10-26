/**
 * SPM261.01 Soccer League -- submission backend.
 *
 * Bound to the "SPM261.01 Soccer League — Submissions" Google Sheet.
 * Paste this into that Sheet's Extensions > Apps Script, then Deploy >
 * New deployment > Web app (Execute as: Me, Who has access: Anyone),
 * and send the resulting /exec URL back so it can be wired into
 * assets/config.js. Redeploying later (this file changed): Deploy >
 * Manage deployments > edit the existing deployment > New version --
 * keeps the same /exec URL, no config.js change needed.
 *
 * AI COACH SETUP (this version, 2026-10-26; coach tuned for performance
 *   and strategy questions):
 *   1. Replace ALL code in the Apps Script editor with this file.
 *   2. Project Settings > Script Properties > Add property:
 *      GEMINI_API_KEY = your key from aistudio.google.com (never put
 *      the key in this file, the repo or Discord).
 *   3. Pick testCoachKey in the function dropdown > Run. The log should
 *      say "OK via gemini-3.5-flash-lite: ...".
 *   4. Deploy > Manage deployments > edit > New version > Deploy.
 *
 * PIN CHECKING IS REAL HERE, unlike the Claude-artifact version this
 * replaced -- this runs server-side, so a wrong/missing PIN is
 * actually rejected, not just a client-side hash comparison a student
 * could bypass with devtools.
 *
 * Sheets used (auto-created + seeded on first request if missing):
 *   Teams        -- id | name | owner | pin   (seeded from SEED_TEAMS, then
 *                    "name" is the live, renameable value)
 *   DraftBoards  -- team_id | player_ids_json | submitted_at
 *   Lineups      -- team_id | round | formation | strategy | gk | df | mf | fw
 *                    | ticket_price | rationale | submitted_at
 *   SponsorshipDeals -- team_id | category | brand | final_revenue | final_clause
 *                    | rep_team_id | submitted_at
 *   LocalTVDeals -- team_id | final_revenue | final_clause | rep_team_id | submitted_at
 *   Coach Log    -- timestamp | team_id | team_name | question | answer | model
 *                    (AI Coach exchanges, see handleCoachChat_; needs the
 *                    GEMINI_API_KEY script property)
 *   HealthTreatments -- team_id | round | player_id | player_name | treatment | submitted_at
 *                    (Player Health Hub requests; engine/health.py applies or voids them)
 *                    (one row per team, ever -- a Local TV Deal is negotiated once)
 *
 * ADMIN EXPORT (?admin_key=...): the scheduled GitHub Actions job (see
 * .github/workflows/auto-resolve.yml) pulls Teams/DraftBoards/Lineups
 * through this every run so the site can resolve itself -- nobody
 * needs to be in a live conversation with Claude for a round to
 * resolve on time. ADMIN_KEY must match the ADMIN_KEY repo secret
 * used by that workflow. This is a shared secret in a script property,
 * not real security -- good enough to keep it off a public GET, not
 * good enough for anything more sensitive than "who ranked which
 * players."
 */
var ADMIN_KEY = "afkib6IOV1gCxGzR0Q16n0IBAD3HCeXi";

var SEED_TEAMS = [
  {id:0,name:"Team 1",owner:"Bianca Biagini",pin:"3062"},
  {id:1,name:"Team 2",owner:"Carlos Brito-Mezon",pin:"4302"},
  {id:2,name:"Team 3",owner:"Allison Dieckmann",pin:"5357"},
  {id:3,name:"Team 4",owner:"Jake Dunphy",pin:"1829"},
  {id:4,name:"Team 5",owner:"Jayden Geerders",pin:"3635"},
  {id:5,name:"Team 6",owner:"Yonelisa Hamusten",pin:"3206"},
  {id:6,name:"Team 7",owner:"Denim Horsford",pin:"6183"},
  {id:7,name:"Team 8",owner:"Max Lebisky",pin:"6019"},
  {id:8,name:"Team 9",owner:"Jordan Long",pin:"2947"},
  {id:9,name:"Team 10",owner:"Parker Miles",pin:"7901"},
  {id:10,name:"Team 11",owner:"Kyle Miller",pin:"5411"},
  {id:11,name:"Team 12",owner:"Maggie O'Shea",pin:"2793"},
  {id:12,name:"Team 13",owner:"Sawyer Ostroff",pin:"1149"},
  {id:13,name:"Team 14",owner:"Anthony Pope",pin:"8514"},
  {id:14,name:"Team 15",owner:"Jovanni Romeo",pin:"7902"},
  {id:15,name:"Team 16",owner:"Mason Walls",pin:"5049"},
  {id:16,name:"Team 17",owner:"Sydney Weathers",pin:"7581"},
  {id:17,name:"Team 18",owner:"Andre Yared",pin:"4936"},
];

// Sponsorship catalog -- read-only reference data, matches
// data/deals.json's sponsorship_categories exactly (kept in sync by
// hand; if the catalog ever changes there, regenerate this array the
// same way SEED_TEAMS was built). Used to validate slot availability
// and compute commissions server-side, same as engine/resolve_sponsorship_pick.py.
var SPONSOR_CATALOG = [
  {category:"Kit / Apparel",name:"Nike",base_revenue:3500000,base_clause:"strict",qty:4},
  {category:"Kit / Apparel",name:"Adidas",base_revenue:3000000,base_clause:"strict",qty:4},
  {category:"Kit / Apparel",name:"Under Armour",base_revenue:2200000,base_clause:"standard",qty:5},
  {category:"Kit / Apparel",name:"Puma",base_revenue:1800000,base_clause:"standard",qty:5},
  {category:"Kit / Apparel",name:"New Balance",base_revenue:1500000,base_clause:"loose",qty:6},
  {category:"Beverage",name:"Red Bull",base_revenue:2800000,base_clause:"strict",qty:3},
  {category:"Beverage",name:"Gatorade",base_revenue:2000000,base_clause:"standard",qty:5},
  {category:"Beverage",name:"Coca-Cola",base_revenue:1800000,base_clause:"standard",qty:5},
  {category:"Beverage",name:"Pepsi",base_revenue:1600000,base_clause:"standard",qty:5},
  {category:"Beverage",name:"Monster Energy",base_revenue:1200000,base_clause:"loose",qty:6},
  {category:"Financial Services",name:"Visa",base_revenue:2500000,base_clause:"strict",qty:4},
  {category:"Financial Services",name:"Mastercard",base_revenue:2200000,base_clause:"strict",qty:4},
  {category:"Financial Services",name:"American Express",base_revenue:1800000,base_clause:"standard",qty:5},
  {category:"Financial Services",name:"PayPal",base_revenue:1000000,base_clause:"loose",qty:7},
  {category:"Airline",name:"Emirates",base_revenue:3000000,base_clause:"strict",qty:3},
  {category:"Airline",name:"Qatar Airways",base_revenue:2400000,base_clause:"strict",qty:4},
  {category:"Airline",name:"Delta",base_revenue:1600000,base_clause:"standard",qty:6},
  {category:"Airline",name:"American Airlines",base_revenue:1300000,base_clause:"loose",qty:7},
  {category:"Automotive",name:"BMW",base_revenue:2600000,base_clause:"strict",qty:3},
  {category:"Automotive",name:"Toyota",base_revenue:2000000,base_clause:"standard",qty:5},
  {category:"Automotive",name:"Ford",base_revenue:1400000,base_clause:"standard",qty:6},
  {category:"Automotive",name:"Hyundai",base_revenue:1000000,base_clause:"loose",qty:6},
  {category:"Technology",name:"Samsung",base_revenue:2400000,base_clause:"strict",qty:4},
  {category:"Technology",name:"Sony",base_revenue:2000000,base_clause:"standard",qty:5},
  {category:"Technology",name:"AT&T",base_revenue:1500000,base_clause:"standard",qty:5},
  {category:"Technology",name:"Verizon",base_revenue:1100000,base_clause:"loose",qty:6},
];

// Local TV market-tier base rates + base clauses per team, matches
// data/local_tv_deals.json (base_clause follows the same higher-value-
// market = stricter-clause pattern as the Sponsorship catalog above:
// Major/Large Market -> strict, Mid/Small Market -> standard, Micro Market -> loose).
var LOCAL_TV_BASE = {
  "0":{tier:"Large Market",base_revenue:1000000,base_clause:"strict"}, "1":{tier:"Major Market",base_revenue:1200000,base_clause:"strict"},
  "2":{tier:"Mid Market",base_revenue:850000,base_clause:"standard"}, "3":{tier:"Small Market",base_revenue:700000,base_clause:"standard"},
  "4":{tier:"Mid Market",base_revenue:850000,base_clause:"standard"}, "5":{tier:"Micro Market",base_revenue:550000,base_clause:"loose"},
  "6":{tier:"Micro Market",base_revenue:550000,base_clause:"loose"}, "7":{tier:"Mid Market",base_revenue:850000,base_clause:"standard"},
  "8":{tier:"Small Market",base_revenue:700000,base_clause:"standard"}, "9":{tier:"Major Market",base_revenue:1200000,base_clause:"strict"},
  "10":{tier:"Major Market",base_revenue:1200000,base_clause:"strict"}, "11":{tier:"Small Market",base_revenue:700000,base_clause:"standard"},
  "12":{tier:"Large Market",base_revenue:1000000,base_clause:"strict"}, "13":{tier:"Large Market",base_revenue:1000000,base_clause:"strict"},
  "14":{tier:"Major Market",base_revenue:1200000,base_clause:"strict"}, "15":{tier:"Mid Market",base_revenue:850000,base_clause:"standard"},
  "16":{tier:"Micro Market",base_revenue:550000,base_clause:"loose"}, "17":{tier:"Large Market",base_revenue:1000000,base_clause:"strict"},
};

function ensureSheets_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  var teams = ss.getSheetByName("Teams");
  if (!teams) {
    teams = ss.insertSheet("Teams");
    teams.appendRow(["id", "name", "owner", "pin"]);
    SEED_TEAMS.forEach(function (t) {
      teams.appendRow([t.id, t.name, t.owner, t.pin]);
    });
  }

  var boards = ss.getSheetByName("DraftBoards");
  if (!boards) {
    boards = ss.insertSheet("DraftBoards");
    boards.appendRow(["team_id", "player_ids_json", "submitted_at"]);
  }

  var lineups = ss.getSheetByName("Lineups");
  if (!lineups) {
    lineups = ss.insertSheet("Lineups");
    lineups.appendRow(["team_id", "round", "formation", "strategy", "gk", "df", "mf", "fw",
                        "ticket_price", "rationale", "submitted_at"]);
  }

  var sponsorships = ss.getSheetByName("SponsorshipDeals");
  if (!sponsorships) {
    sponsorships = ss.insertSheet("SponsorshipDeals");
    sponsorships.appendRow(["team_id", "category", "brand", "final_revenue", "final_clause",
                             "rep_team_id", "submitted_at"]);
  }

  var localTv = ss.getSheetByName("LocalTVDeals");
  if (!localTv) {
    localTv = ss.insertSheet("LocalTVDeals");
    localTv.appendRow(["team_id", "final_revenue", "final_clause", "rep_team_id", "submitted_at"]);
  }

  var trades = ss.getSheetByName("TradeProposals");
  if (!trades) {
    trades = ss.insertSheet("TradeProposals");
    trades.appendRow(["proposal_id", "timestamp", "proposer_team_id", "receiver_team_id",
                       "players_out_json", "players_in_json", "cash_from_proposer", "cash_from_receiver",
                       "rationale", "status", "responded_at"]);
  }

  var health = ss.getSheetByName("HealthTreatments");
  if (!health) {
    health = ss.insertSheet("HealthTreatments");
    health.appendRow(["team_id", "round", "player_id", "player_name", "treatment", "submitted_at"]);
  }

  // remove the default blank "Sheet1" left by spreadsheet creation, if still present and empty
  var sheet1 = ss.getSheetByName("Sheet1");
  if (sheet1 && sheet1.getLastRow() === 0) ss.deleteSheet(sheet1);

  return { teams: teams, boards: boards, lineups: lineups, sponsorships: sponsorships, localTv: localTv, trades: trades, health: health };
}

function readTeams_(teamsSheet) {
  var rows = teamsSheet.getDataRange().getValues();
  var out = [];
  for (var i = 1; i < rows.length; i++) {
    out.push({ id: rows[i][0], name: rows[i][1], owner: rows[i][2], pin: String(rows[i][3]) });
  }
  return out;
}

function findTeamRow_(teamsSheet, teamId) {
  var rows = teamsSheet.getDataRange().getValues();
  for (var i = 1; i < rows.length; i++) {
    if (String(rows[i][0]) === String(teamId)) return i + 1; // 1-indexed sheet row
  }
  return -1;
}

function checkPin_(teams, teamId, pin) {
  var team = null;
  for (var i = 0; i < teams.length; i++) {
    if (String(teams[i].id) === String(teamId)) { team = teams[i]; break; }
  }
  if (!team) return { ok: false, error: "unknown team_id" };
  if (String(pin || "").trim() !== team.pin) return { ok: false, error: "incorrect PIN" };
  return { ok: true, team: team };
}

function jsonOut_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function readDraftBoards_(boardsSheet) {
  var rows = boardsSheet.getDataRange().getValues();
  var out = [];
  for (var i = 1; i < rows.length; i++) {
    if (rows[i][0] === "" || rows[i][0] == null) continue;
    var ids;
    try { ids = JSON.parse(rows[i][1]); } catch (e) { ids = []; }
    out.push({ team_id: rows[i][0], player_ids: ids, submitted_at: rows[i][2] });
  }
  return out;
}

function readLineups_(lineupsSheet) {
  var rows = lineupsSheet.getDataRange().getValues();
  var out = [];
  for (var i = 1; i < rows.length; i++) {
    if (rows[i][0] === "" || rows[i][0] == null) continue;
    out.push({
      team_id: rows[i][0], round: rows[i][1], formation: rows[i][2], strategy: rows[i][3],
      gk: rows[i][4], df: rows[i][5], mf: rows[i][6], fw: rows[i][7],
      ticket_price: rows[i][8], rationale: rows[i][9], submitted_at: rows[i][10],
    });
  }
  return out;
}

function readSponsorshipDeals_(sheet) {
  var rows = sheet.getDataRange().getValues();
  var out = [];
  for (var i = 1; i < rows.length; i++) {
    if (rows[i][0] === "" || rows[i][0] == null) continue;
    out.push({
      team_id: rows[i][0], category: rows[i][1], brand: rows[i][2],
      final_revenue: rows[i][3], final_clause: rows[i][4],
      rep_team_id: rows[i][5], submitted_at: rows[i][6],
    });
  }
  return out;
}

function readLocalTVDeals_(sheet) {
  var rows = sheet.getDataRange().getValues();
  var out = [];
  for (var i = 1; i < rows.length; i++) {
    if (rows[i][0] === "" || rows[i][0] == null) continue;
    out.push({
      team_id: rows[i][0], final_revenue: rows[i][1], final_clause: rows[i][2],
      rep_team_id: rows[i][3], submitted_at: rows[i][4],
    });
  }
  return out;
}

function readTradeProposals_(sheet) {
  var rows = sheet.getDataRange().getValues();
  var out = [];
  for (var i = 1; i < rows.length; i++) {
    if (rows[i][0] === "" || rows[i][0] == null) continue;
    var playersOut, playersIn;
    try { playersOut = JSON.parse(rows[i][4]); } catch (e) { playersOut = []; }
    try { playersIn = JSON.parse(rows[i][5]); } catch (e) { playersIn = []; }
    out.push({
      proposal_id: rows[i][0], timestamp: rows[i][1],
      proposer_team_id: rows[i][2], receiver_team_id: rows[i][3],
      players_out: playersOut, players_in: playersIn,
      cash_from_proposer: rows[i][6], cash_from_receiver: rows[i][7],
      rationale: rows[i][8], status: rows[i][9], responded_at: rows[i][10],
    });
  }
  return out;
}

function readHealthTreatments_(sheet) {
  var rows = sheet.getDataRange().getValues();
  var out = [];
  for (var i = 1; i < rows.length; i++) {
    if (rows[i][0] === "" || rows[i][0] == null) continue;
    out.push({ team_id: rows[i][0], round: rows[i][1], player_id: rows[i][2], player_name: rows[i][3],
               treatment: rows[i][4], submitted_at: rows[i][5] });
  }
  return out;
}

// Player Health Hub -- must match engine/health.py (CATALOG keys, START_ROUND, MAX_PER_ROUND).
// Prices/effects are enforced by the engine; this only screens the request.
var HEALTH_TREATMENTS = ["rehab_standard", "rehab_accelerated", "rehab_elite", "recovery", "sports_science"];
var HEALTH_START_ROUND = 3;
var HEALTH_MAX_PER_ROUND = 4;

// Sum of players this team has already committed to give away across
// every trade that isn't yet a settled decline -- pending AND accepted
// both count, since an accepted trade is expected to apply. This is a
// courtesy pre-check only (rejects an obviously-over-the-limit proposal
// immediately instead of making a student wait for the next cron cycle);
// engine/resolve_trade.py is the real, final authority on the 3-player
// season limit once a trade is actually accepted.
function committedOutgoingCount_(trades, teamId) {
  var total = 0;
  trades.forEach(function (t) {
    if (t.status !== "pending" && t.status !== "accepted") return;
    if (String(t.proposer_team_id) === String(teamId)) total += (t.players_out || []).length;
    if (String(t.receiver_team_id) === String(teamId)) total += (t.players_in || []).length;
  });
  return total;
}

// ---------------------------------------------------------------------------
// AI COACH (type "coach_chat", page /coach/). The model call happens HERE,
// server-side, so the API key never reaches a browser or the public repo:
// it lives in Project Settings > Script Properties as GEMINI_API_KEY
// (optional GEMINI_MODEL overrides the first model tried). The team
// briefing comes from data/coach_context.json on GitHub Pages (built by
// engine/build_coach_context.py every auto-resolve cycle) and is looked
// up by the PIN-checked team_id, never taken from the request body, so a
// student can't feed the coach another team's data. That file carries no
// PINs, grades, forfeit reasons or sponsor base prices.
// Every exchange is logged to the "Coach Log" tab for the instructor.
// ---------------------------------------------------------------------------
var COACH_CONTEXT_URL = "https://au-sm.github.io/spm261.01_simul/data/coach_context.json";
// Tried in order. 3.5 Flash-Lite has the largest free daily quota; Google
// limited 2.5 access on 2026-09-18 to keys that used it recently, so a new
// key may only reach the 3.x models -- 2.5 stays last as a fallback.
var COACH_MODELS = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash"];
var COACH_MAX_PER_HOUR = 40;      // per team -- keeps one team from burning the free quota
var COACH_MAX_MESSAGE = 800;      // characters per student message
var COACH_MAX_HISTORY = 10;       // earlier turns resent for continuity

var COACH_INSTRUCTIONS = [
  "You are the AI Coach for the {LEAGUE}, a front-office simulation in SPM261 Introduction to Sport Management at Arcadia University.",
  "Each student is the owner and general manager of one club. You are their front-office advisor, talking to the owner of {TEAM}.",
  "Your job is to help them understand how their team is performing and why, and to think through strategy so they make better decisions.",
  "",
  "HOW TO ANSWER",
  "- Lead with analysis, not a question. Say what the numbers show, explain the likely reason using how the league actually works (rulebook section 9 for match results, section 8 for formations and strategy, section 10 for tickets and attendance), then give 2-3 concrete options with the tradeoff of each.",
  "- Performance questions: compare them with the league (their attack and defense ranks, home vs away form, the league table), look at the formations and strategies they used and how those went, who is scoring and starting, and player condition and injuries.",
  "- Strategy questions: use the OPPONENT SCOUTING report and LEAGUE TRENDS. Match their strengths (OVR by player and line, ATT/DEF/PACE/PHY) against the opponent's, and say which data supports each option. Note when a league trend is based on only a few matches.",
  "- Business questions (tickets, sponsors, TV, cash, payroll, health spending): use their finance lines and tie the answer to sport management concepts by name, such as price elasticity, demand drivers, sponsorship fit and activation, broadcast rights value, payroll efficiency, risk and opportunity cost, fan identification.",
  "- Quote their actual numbers and players by name. Cite the rulebook section when a rule matters.",
  "- Keep it readable: under 200 words, short sentences, at most 4 bullets. Finish with one short question that pushes them toward their own decision, unless they only asked a factual rule question.",
  "",
  "LIMITS",
  "- The final call is theirs. You may say which option the data favors and why, but never hand them a finished lineup, ticket price or deal as 'the answer'.",
  "- Never write a decision rationale, lineup justification or any graded text for them. If asked, say that part has to be in their own words and offer to react to their own draft ideas instead.",
  "- Never guess or reveal sponsors' hidden base prices or other teams' private negotiations. If you don't know a number, say so.",
  "- You know nothing about any student's course grade. Don't speculate about grades or points earned.",
  "- If the briefing doesn't contain something, say it isn't in your data rather than inventing it.",
  "- If a question has nothing to do with the league or the course, steer back in one sentence.",
].join("\n");

function coachLogSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var log = ss.getSheetByName("Coach Log");
  if (!log) {
    log = ss.insertSheet("Coach Log");
    log.appendRow(["timestamp", "team_id", "team_name", "question", "answer", "model"]);
    log.getRange(1, 1, 1, 6).setFontWeight("bold");
    log.setFrozenRows(1);
  }
  return log;
}

function coachContext_() {
  var cache = CacheService.getScriptCache();
  var hit = cache.get("coach_ctx_meta");
  if (hit) {
    var meta = JSON.parse(hit);
    var parts = cache.getAll(meta.keys);
    if (meta.keys.every(function (k) { return parts[k] !== undefined && parts[k] !== null; })) {
      return JSON.parse(meta.keys.map(function (k) { return parts[k]; }).join(""));
    }
  }
  var resp = UrlFetchApp.fetch(COACH_CONTEXT_URL + "?t=" + Date.now(), { muteHttpExceptions: true });
  if (resp.getResponseCode() !== 200) throw new Error("coach context unavailable (" + resp.getResponseCode() + ")");
  var text = resp.getContentText();
  // CacheService caps one value at 100KB, so the file is stored in chunks
  var keys = [], chunks = {};
  for (var i = 0, n = 0; i < text.length; i += 45000, n++) {
    keys.push("coach_ctx_" + n);
    chunks["coach_ctx_" + n] = text.substring(i, i + 45000);
  }
  try {
    cache.putAll(chunks, 600);
    cache.put("coach_ctx_meta", JSON.stringify({ keys: keys }), 600);
  } catch (err) { /* cache is an optimisation only */ }
  return JSON.parse(text);
}

function coachRateOk_(teamId) {
  var cache = CacheService.getScriptCache();
  var key = "coach_rate_" + teamId + "_" + Math.floor(Date.now() / 3600000);
  var used = Number(cache.get(key) || 0);
  if (used >= COACH_MAX_PER_HOUR) return false;
  cache.put(key, String(used + 1), 3700);
  return true;
}

function coachCallModel_(system, contents) {
  var key = PropertiesService.getScriptProperties().getProperty("GEMINI_API_KEY");
  if (!key) return { ok: false, reason: "no_key" };
  var preferred = PropertiesService.getScriptProperties().getProperty("GEMINI_MODEL");
  var models = preferred ? [preferred].concat(COACH_MODELS.filter(function (m) { return m !== preferred; })) : COACH_MODELS;
  var lastErr = "";
  for (var i = 0; i < models.length; i++) {
    // 3.x models think by default and the thinking counts toward
    // maxOutputTokens, so they get more room and the default temperature
    var gen = { maxOutputTokens: 2048 };
    if (models[i].indexOf("2.5-flash") > -1) {
      gen = { temperature: 0.7, maxOutputTokens: 700, thinkingConfig: { thinkingBudget: 0 } };
    }
    var resp = UrlFetchApp.fetch(
      "https://generativelanguage.googleapis.com/v1beta/models/" + models[i] + ":generateContent",
      {
        method: "post", contentType: "application/json", muteHttpExceptions: true,
        headers: { "x-goog-api-key": key },
        payload: JSON.stringify({ system_instruction: { parts: [{ text: system }] }, contents: contents, generationConfig: gen }),
      });
    var code = resp.getResponseCode();
    if (code === 200) {
      var data = JSON.parse(resp.getContentText());
      var cand = (data.candidates || [])[0];
      var text = cand && cand.content && (cand.content.parts || []).map(function (p) { return p.text || ""; }).join("").trim();
      if (text) return { ok: true, text: text, model: models[i] };
      lastErr = "empty reply (" + ((cand && cand.finishReason) || "no candidate") + ")";
    } else {
      lastErr = code + " " + resp.getContentText().substring(0, 200);
    }
  }
  return { ok: false, reason: "model_error", detail: lastErr };
}

// Run this once from the Apps Script editor (select testCoachKey > Run)
// after setting GEMINI_API_KEY. The execution log shows which model
// answered, or the exact error if none did. Nothing is written to the Sheet.
function testCoachKey() {
  var r = coachCallModel_("You are a test. Reply with one short sentence.",
                          [{ role: "user", parts: [{ text: "Say hello to the SPM261 league." }] }]);
  Logger.log(r.ok ? "OK via " + r.model + ": " + r.text : "FAILED (" + r.reason + "): " + (r.detail || "GEMINI_API_KEY not set"));
}

function handleCoachChat_(body, team) {
  var ctx;
  try {
    ctx = coachContext_();
  } catch (err) {
    return jsonOut_({ ok: false, error: "The coach can't load your team data right now. Try again in a minute." });
  }
  var brief = (ctx.teams || {})[String(team.id)];
  if (!brief) return jsonOut_({ ok: false, error: "No coach briefing for this team yet." });

  // hello: PIN already checked by doPost -- just confirm the session, no model call
  if (body.hello) {
    return jsonOut_({ ok: true, team_id: team.id, team_name: brief.name, position: brief.position,
                      record: brief.record, points: brief.points, cash: brief.cash, next: brief.next,
                      generated_at: ctx.generated_at });
  }

  var message = String(body.message || "").trim();
  if (!message) return jsonOut_({ ok: false, error: "Type a question for your coach." });
  if (message.length > COACH_MAX_MESSAGE) message = message.substring(0, COACH_MAX_MESSAGE);
  if (!coachRateOk_(team.id)) {
    return jsonOut_({ ok: false, error: "Your team has used its " + COACH_MAX_PER_HOUR + " coach messages for this hour. Try again later." });
  }

  var system = COACH_INSTRUCTIONS.replace("{LEAGUE}", ctx.league_name).replace("{TEAM}", brief.name) +
    "\n\nTEAM BRIEFING (data as of " + ctx.generated_at + ")\n" + brief.briefing +
    "\n\nLEAGUE TABLE\n" + ctx.league_table +
    "\n\nRULEBOOK\n" + ctx.rulebook;

  var history = Array.isArray(body.history) ? body.history.slice(-COACH_MAX_HISTORY) : [];
  var contents = [];
  history.forEach(function (h) {
    var role = h && h.role === "coach" ? "model" : "user";
    var text = String((h && h.text) || "").substring(0, 1500);
    if (!text) return;
    if (contents.length && contents[contents.length - 1].role === role) {
      contents[contents.length - 1].parts[0].text += "\n" + text;
    } else {
      contents.push({ role: role, parts: [{ text: text }] });
    }
  });
  while (contents.length && contents[0].role !== "user") contents.shift();
  if (contents.length && contents[contents.length - 1].role === "user") contents.pop();
  contents.push({ role: "user", parts: [{ text: message }] });

  var result = coachCallModel_(system, contents);
  var answer, model;
  if (result.ok) {
    answer = result.text; model = result.model;
  } else if (result.reason === "no_key") {
    answer = "The AI Coach isn't switched on yet. Your instructor still needs to connect it. Check back soon!";
    model = "no_key";
  } else {
    answer = "Your coach is busy with other teams right now. Give it a minute and ask again.";
    model = "error: " + (result.detail || "");
  }
  try {
    coachLogSheet_().appendRow([new Date().toISOString(), team.id, brief.name, message, answer, model]);
  } catch (err) { /* logging must never block the reply */ }
  return jsonOut_({ ok: true, reply: answer, fallback: !result.ok });
}

function doGet(e) {
  var sheets = ensureSheets_();
  var params = (e && e.parameter) || {};

  if (params.admin_key && params.admin_key === ADMIN_KEY) {
    return jsonOut_({
      ok: true,
      teams: readTeams_(sheets.teams), // pins included -- admin-only export
      draft_boards: readDraftBoards_(sheets.boards),
      lineups: readLineups_(sheets.lineups),
      sponsorship_deals: readSponsorshipDeals_(sheets.sponsorships),
      local_tv_deals: readLocalTVDeals_(sheets.localTv),
      trade_proposals: readTradeProposals_(sheets.trades),
      health_treatments: readHealthTreatments_(sheets.health),
    });
  }

  // public, non-admin reads used by the Sponsorship and TV Rights pages
  // to show live slot availability without needing the admin key.
  // base_revenue is deliberately stripped from both catalogs below --
  // real price numbers must never leave the server to an unauthenticated
  // client, even inside a JSON response nobody's UI happens to display.
  // The full SPONSOR_CATALOG / LOCAL_TV_BASE constants (with base_revenue)
  // stay in memory here and are used directly by doPost's own handlers.
  if (params.catalog === "1") {
    return jsonOut_({
      ok: true,
      sponsor_catalog: SPONSOR_CATALOG.map(function (b) {
        return { name: b.name, category: b.category, base_clause: b.base_clause, qty: b.qty }; // no base_revenue -- not public
      }),
      local_tv_base: Object.keys(LOCAL_TV_BASE).reduce(function (out, teamId) {
        var t = LOCAL_TV_BASE[teamId];
        out[teamId] = { tier: t.tier, base_clause: t.base_clause }; // no base_revenue -- not public
        return out;
      }, {}),
      sponsorship_deals: readSponsorshipDeals_(sheets.sponsorships).map(function (d) {
        return { team_id: d.team_id, category: d.category, brand: d.brand }; // no revenue/clause -- not other teams' business
      }),
      local_tv_deals: readLocalTVDeals_(sheets.localTv).map(function (d) {
        return { team_id: d.team_id }; // just "has this team negotiated yet"
      }),
      // Trade proposals are shown in full (unlike the sponsor/TV catalogs
      // above) -- a trade is inherently a public fact about two named
      // teams' rosters, same as the standings or the match log, and the
      // Trade Center page needs the receiving team to actually see what
      // it's being offered.
      trade_proposals: readTradeProposals_(sheets.trades),
    });
  }

  var teams = readTeams_(sheets.teams).map(function (t) {
    return { id: t.id, name: t.name, owner: t.owner }; // never return pin on a public GET
  });
  return jsonOut_({ ok: true, teams: teams });
}

function doPost(e) {
  var sheets = ensureSheets_();
  var teams = readTeams_(sheets.teams);
  var body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return jsonOut_({ ok: false, error: "malformed request body" });
  }

  // Admin-only: write the "Players per Team" roster tab (no PINs involved).
  // generic admin-only tab writer (e.g. the instructor-only "Forfeits" tab)
  if (body.type === "admin_tab") {
    if (body.admin_key !== ADMIN_KEY) return jsonOut_({ ok: false, error: "unauthorized" });
    var trows = body.rows || [];
    var tname = String(body.tab_name || "").trim();
    if (!trows.length || !tname) return jsonOut_({ ok: false, error: "tab_name and rows required" });
    var ssT = SpreadsheetApp.getActiveSpreadsheet();
    var ttab = ssT.getSheetByName(tname) || ssT.insertSheet(tname);
    ttab.clear();
    ttab.getRange(1, 1, trows.length, trows[0].length).setValues(trows);
    ttab.getRange(1, 1, 1, trows[0].length).setFontWeight("bold").setBackground("#7A1F1F").setFontColor("#FFFFFF");
    ttab.setFrozenRows(1);
    ttab.autoResizeColumns(1, trows[0].length);
    return jsonOut_({ ok: true, tab: tname, rows_written: trows.length });
  }

  if (body.type === "admin_roster_tab") {
    if (body.admin_key !== ADMIN_KEY) return jsonOut_({ ok: false, error: "unauthorized" });
    var rows = body.rows || [];
    if (!rows.length) return jsonOut_({ ok: false, error: "no rows" });
    var ssR = SpreadsheetApp.getActiveSpreadsheet();
    var tab = ssR.getSheetByName("Players per Team") || ssR.insertSheet("Players per Team");
    tab.clear();
    tab.getRange(1, 1, rows.length, rows[0].length).setValues(rows);
    tab.getRange(1, 1, 1, rows[0].length).setFontWeight("bold").setBackground("#1F3864").setFontColor("#FFFFFF");
    tab.getRange(2, 6, rows.length - 1, 1).setNumberFormat("$#,##0");
    for (var ri = 2; ri <= rows.length; ri++) {
      if (String(rows[ri - 1][1]).indexOf(" total (") > -1) tab.getRange(ri, 1, 1, rows[0].length).setFontWeight("bold").setBackground("#EEF2F8");
    }
    tab.setFrozenRows(1);
    tab.autoResizeColumns(1, rows[0].length);
    return jsonOut_({ ok: true, rows_written: rows.length });
  }

  var pinCheck = checkPin_(teams, body.team_id, body.pin);
  if (!pinCheck.ok) return jsonOut_({ ok: false, error: pinCheck.error });

  if (body.type === "coach_chat") return handleCoachChat_(body, pinCheck.team);

  var now = new Date().toISOString();

  if (body.type === "rename_team") {
    var newName = String(body.new_name || "").trim();
    if (!newName) return jsonOut_({ ok: false, error: "new_name is required" });
    var dupe = teams.some(function (t) {
      return String(t.id) !== String(body.team_id) && t.name.toLowerCase() === newName.toLowerCase();
    });
    if (dupe) return jsonOut_({ ok: false, error: "'" + newName + "' is already taken by another team" });

    var row = findTeamRow_(sheets.teams, body.team_id);
    sheets.teams.getRange(row, 2).setValue(newName); // column B = name
    return jsonOut_({ ok: true, team_id: body.team_id, name: newName });
  }

  if (body.type === "draft_board") {
    var ids = body.player_ids;
    if (!Array.isArray(ids) || ids.length === 0) {
      return jsonOut_({ ok: false, error: "player_ids must be a non-empty array" });
    }
    // one row per team: overwrite if they already have a board (re-submission replaces it)
    var boardRows = sheets.boards.getDataRange().getValues();
    var existingRow = -1;
    for (var i = 1; i < boardRows.length; i++) {
      if (String(boardRows[i][0]) === String(body.team_id)) { existingRow = i + 1; break; }
    }
    var rowData = [body.team_id, JSON.stringify(ids), now];
    if (existingRow > 0) {
      sheets.boards.getRange(existingRow, 1, 1, 3).setValues([rowData]);
    } else {
      sheets.boards.appendRow(rowData);
    }
    return jsonOut_({ ok: true, team_id: body.team_id, count: ids.length });
  }

  if (body.type === "weekly_lineup") {
    var rowData2 = [
      body.team_id, body.round, body.formation, body.strategy,
      body.gk || "", (body.df || []).join("\n"), (body.mf || []).join("\n"), (body.fw || []).join("\n"),
      body.ticket_price || "", body.rationale || "", now,
    ];
    // one row per (team, round): overwrite if resubmitted before the deadline
    var lineupRows = sheets.lineups.getDataRange().getValues();
    var existingLineupRow = -1;
    for (var j = 1; j < lineupRows.length; j++) {
      if (String(lineupRows[j][0]) === String(body.team_id) && String(lineupRows[j][1]) === String(body.round)) {
        existingLineupRow = j + 1; break;
      }
    }
    if (existingLineupRow > 0) {
      sheets.lineups.getRange(existingLineupRow, 1, 1, rowData2.length).setValues([rowData2]);
    } else {
      sheets.lineups.appendRow(rowData2);
    }
    return jsonOut_({ ok: true, team_id: body.team_id, round: body.round });
  }

  if (body.type === "sponsorship_deal") {
    var brand = null;
    for (var bi = 0; bi < SPONSOR_CATALOG.length; bi++) {
      if (SPONSOR_CATALOG[bi].name === body.brand) { brand = SPONSOR_CATALOG[bi]; break; }
    }
    if (!brand) return jsonOut_({ ok: false, error: "unknown brand: " + body.brand });

    var existingDeals = readSponsorshipDeals_(sheets.sponsorships);
    var alreadyInCategory = existingDeals.some(function (d) {
      return String(d.team_id) === String(body.team_id) && d.category === brand.category;
    });
    if (alreadyInCategory) {
      return jsonOut_({ ok: false, error: "This team already has a " + brand.category + " sponsor. One brand per category." });
    }

    var slotsTaken = existingDeals.filter(function (d) { return d.brand === brand.name; }).length;
    if (slotsTaken >= brand.qty) {
      return jsonOut_({ ok: false, error: brand.name + " is sold out (" + brand.qty + "/" + brand.qty + " slots taken league-wide). Pick a different " + brand.category + " brand." });
    }

    var finalRevenue, finalClause;
    if (body.mode === "base") {
      finalRevenue = brand.base_revenue;
      finalClause = brand.base_clause;
    } else if (body.mode === "negotiate") {
      finalRevenue = Number(body.final_revenue);
      finalClause = body.final_clause;
      if (!finalRevenue || !finalClause) {
        return jsonOut_({ ok: false, error: "Negotiated deals need both final_revenue and final_clause." });
      }
    } else {
      return jsonOut_({ ok: false, error: "mode must be 'base' or 'negotiate'" });
    }

    // A rep is required whenever revenue differs from base, in EITHER
    // direction -- the rep's team earns a commission either for closing a
    // bigger deal (above base) or for talking the team down (below base,
    // a good deal for the sponsor). Only an exact match to base needs no
    // rep, since nobody negotiated anything.
    var repTeamId = null;
    if (finalRevenue !== brand.base_revenue) {
      if (body.rep_team_id === undefined || body.rep_team_id === null || body.rep_team_id === "") {
        // Deliberately does not echo brand.base_revenue back here -- an
        // error message is still a response to an unauthenticated client,
        // and a team could otherwise learn a brand's exact base price just
        // by submitting a mismatched revenue with no rep_team_id.
        return jsonOut_({ ok: false, error: "Revenue different from base requires rep_team_id to credit the commission." });
      }
      repTeamId = body.rep_team_id;
    }

    sheets.sponsorships.appendRow([body.team_id, brand.category, brand.name, finalRevenue, finalClause, repTeamId, now]);
    return jsonOut_({
      ok: true, team_id: body.team_id, category: brand.category, brand: brand.name,
      final_revenue: finalRevenue, final_clause: finalClause,
      commission: repTeamId ? Math.abs(finalRevenue - brand.base_revenue) : 0,
    });
  }

  if (body.type === "local_tv_deal") {
    var tvBase = LOCAL_TV_BASE[String(body.team_id)];
    if (!tvBase) return jsonOut_({ ok: false, error: "no market tier on file for this team" });

    var existingTv = readLocalTVDeals_(sheets.localTv);
    var already = existingTv.some(function (d) { return String(d.team_id) === String(body.team_id); });
    if (already) return jsonOut_({ ok: false, error: "This team's Local TV rate is already negotiated -- it's a one-time deal." });

    var tvFinalRevenue, tvFinalClause;
    if (body.mode === "base") {
      tvFinalRevenue = tvBase.base_revenue;
      tvFinalClause = tvBase.base_clause;
    } else if (body.mode === "negotiate") {
      tvFinalRevenue = Number(body.final_revenue);
      tvFinalClause = body.final_clause;
      if (!tvFinalRevenue || !tvFinalClause) {
        return jsonOut_({ ok: false, error: "Negotiated deals need both final_revenue and final_clause." });
      }
    } else {
      return jsonOut_({ ok: false, error: "mode must be 'base' or 'negotiate'" });
    }

    // Same either-direction rule as Sponsorship Deal above.
    var tvRepTeamId = null;
    if (tvFinalRevenue !== tvBase.base_revenue) {
      if (body.rep_team_id === undefined || body.rep_team_id === null || body.rep_team_id === "") {
        // Same reasoning as the sponsorship_deal handler above -- don't
        // echo tvBase.base_revenue back in an error message either.
        return jsonOut_({ ok: false, error: "Rate different from base requires rep_team_id to credit the commission." });
      }
      tvRepTeamId = body.rep_team_id;
    }

    sheets.localTv.appendRow([body.team_id, tvFinalRevenue, tvFinalClause, tvRepTeamId, now]);
    return jsonOut_({
      ok: true, team_id: body.team_id, final_revenue: tvFinalRevenue, final_clause: tvFinalClause,
      commission: tvRepTeamId ? Math.abs(tvFinalRevenue - tvBase.base_revenue) : 0,
    });
  }

  if (body.type === "health_treatment") {
    if (HEALTH_TREATMENTS.indexOf(body.treatment) < 0) return jsonOut_({ ok: false, error: "Unknown treatment." });
    var hRound = Number(body.round);
    if (!hRound || hRound < HEALTH_START_ROUND) {
      return jsonOut_({ ok: false, error: "The Health Hub opens for Round " + HEALTH_START_ROUND + "." });
    }
    if (body.player_id === undefined || body.player_id === null || body.player_id === "") {
      return jsonOut_({ ok: false, error: "Pick a player." });
    }
    var existingHealth = readHealthTreatments_(sheets.health).filter(function (h) {
      return String(h.team_id) === String(body.team_id) && String(h.round) === String(hRound);
    });
    if (existingHealth.length >= HEALTH_MAX_PER_ROUND) {
      return jsonOut_({ ok: false, error: "Your team has already booked " + HEALTH_MAX_PER_ROUND + " treatments for Round " + hRound + "." });
    }
    var dupePlayer = existingHealth.some(function (h) { return String(h.player_id) === String(body.player_id); });
    if (dupePlayer) return jsonOut_({ ok: false, error: "This player already has a treatment booked for Round " + hRound + "." });
    sheets.health.appendRow([body.team_id, hRound, String(body.player_id), String(body.player_name || ""), body.treatment, now]);
    return jsonOut_({ ok: true, team_id: body.team_id, round: hRound, player_id: body.player_id, treatment: body.treatment });
  }

  // NOTE ON TRADE VALIDATION: this Apps Script has NO roster data at all
  // (rosters live in data/players.csv on the engine side, never synced
  // here), so it can only check what it actually has -- team existence,
  // matching player counts, and (as a courtesy, not the final word) the
  // 3-player season limit counted off this sheet's own rows. Real roster
  // ownership and the salary cap are re-checked for real by
  // engine/resolve_trade.py once a trade is accepted -- see that
  // script's docstring. A proposal that looks fine here can still come
  // back VOIDED later (shown in the Trade Center's Final Trade Log) if
  // something about the rosters changed in between.
  if (body.type === "trade_proposal") {
    var receiverId = body.receiver_team_id;
    if (String(receiverId) === String(body.team_id)) {
      return jsonOut_({ ok: false, error: "Pick a different team to trade with." });
    }
    var receiverExists = teams.some(function (t) { return String(t.id) === String(receiverId); });
    if (!receiverExists) return jsonOut_({ ok: false, error: "Unknown receiving team." });

    var playersOut = body.players_out;
    var playersIn = body.players_in;
    if (!Array.isArray(playersOut) || !Array.isArray(playersIn) ||
        playersOut.length === 0 || playersOut.length !== playersIn.length || playersOut.length > 3) {
      return jsonOut_({ ok: false, error: "Both sides of a trade must send the same number of players -- 1-for-1, 2-for-2, or 3-for-3 only." });
    }
    var rationale = String(body.rationale || "").trim();
    if (!rationale) return jsonOut_({ ok: false, error: "A short rationale is required." });

    var existingTrades = readTradeProposals_(sheets.trades);
    var proposerCommitted = committedOutgoingCount_(existingTrades, body.team_id);
    var receiverCommitted = committedOutgoingCount_(existingTrades, receiverId);
    if (proposerCommitted + playersOut.length > 3) {
      return jsonOut_({ ok: false, error: "This would put your team over the 3-player season trade limit (" + proposerCommitted + " already committed)." });
    }
    if (receiverCommitted + playersIn.length > 3) {
      return jsonOut_({ ok: false, error: "This would put the receiving team over the 3-player season trade limit (" + receiverCommitted + " already committed)." });
    }

    var proposalId = Utilities.getUuid();
    sheets.trades.appendRow([
      proposalId, now, body.team_id, receiverId,
      JSON.stringify(playersOut), JSON.stringify(playersIn),
      Number(body.cash_from_proposer) || 0, Number(body.cash_from_receiver) || 0,
      rationale, "pending", "",
    ]);
    return jsonOut_({ ok: true, proposal_id: proposalId, status: "pending" });
  }

  if (body.type === "trade_response") {
    var tradeRows = sheets.trades.getDataRange().getValues();
    var targetRow = -1;
    for (var ti = 1; ti < tradeRows.length; ti++) {
      if (String(tradeRows[ti][0]) === String(body.proposal_id)) { targetRow = ti + 1; break; }
    }
    if (targetRow < 0) return jsonOut_({ ok: false, error: "Unknown trade proposal." });

    var rowReceiverId = tradeRows[targetRow - 1][3];
    if (String(rowReceiverId) !== String(body.team_id)) {
      return jsonOut_({ ok: false, error: "Only the receiving team can respond to this trade." });
    }
    var currentStatus = tradeRows[targetRow - 1][9];
    if (currentStatus !== "pending") {
      return jsonOut_({ ok: false, error: "This trade has already been " + currentStatus + " -- it can't be responded to again." });
    }
    if (body.decision !== "accept" && body.decision !== "reject") {
      return jsonOut_({ ok: false, error: "decision must be 'accept' or 'reject'" });
    }

    var newStatus = body.decision === "accept" ? "accepted" : "rejected";
    sheets.trades.getRange(targetRow, 10).setValue(newStatus);   // column J = status
    sheets.trades.getRange(targetRow, 11).setValue(now);         // column K = responded_at
    return jsonOut_({ ok: true, proposal_id: body.proposal_id, status: newStatus });
  }

  return jsonOut_({ ok: false, error: "unknown submission type: " + body.type });
}
