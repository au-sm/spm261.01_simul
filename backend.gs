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
 *   LocalTVDeals -- team_id | final_revenue | rep_team_id | submitted_at
 *                    (one row per team, ever -- a Local TV rate is negotiated once)
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
  {id:6,name:"Team 7",owner:"Denim Horsford",pin:"0163"},
  {id:7,name:"Team 8",owner:"Max Lebisky",pin:"6019"},
  {id:8,name:"Team 9",owner:"Jordan Long",pin:"0250"},
  {id:9,name:"Team 10",owner:"Parker Miles",pin:"7901"},
  {id:10,name:"Team 11",owner:"Kyle Miller",pin:"5411"},
  {id:11,name:"Team 12",owner:"Maggie O'Shea",pin:"2793"},
  {id:12,name:"Team 13",owner:"Sawyer Ostroff",pin:"1149"},
  {id:13,name:"Team 14",owner:"Anthony Pope",pin:"0910"},
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

// Local TV market-tier base rates per team, matches data/local_tv_deals.json.
var LOCAL_TV_BASE = {
  "0":{tier:"Major Market",base_revenue:1200000}, "1":{tier:"Major Market",base_revenue:1200000},
  "2":{tier:"Mid Market",base_revenue:700000}, "3":{tier:"Small Market",base_revenue:500000},
  "4":{tier:"Mid Market",base_revenue:700000}, "5":{tier:"Small Market",base_revenue:500000},
  "6":{tier:"Small Market",base_revenue:500000}, "7":{tier:"Mid Market",base_revenue:700000},
  "8":{tier:"Small Market",base_revenue:500000}, "9":{tier:"Major Market",base_revenue:1200000},
  "10":{tier:"Major Market",base_revenue:1200000}, "11":{tier:"Small Market",base_revenue:500000},
  "12":{tier:"Major Market",base_revenue:1200000}, "13":{tier:"Mid Market",base_revenue:700000},
  "14":{tier:"Major Market",base_revenue:1200000}, "15":{tier:"Mid Market",base_revenue:700000},
  "16":{tier:"Small Market",base_revenue:500000}, "17":{tier:"Mid Market",base_revenue:700000},
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
    localTv.appendRow(["team_id", "final_revenue", "rep_team_id", "submitted_at"]);
  }

  // remove the default blank "Sheet1" left by spreadsheet creation, if still present and empty
  var sheet1 = ss.getSheetByName("Sheet1");
  if (sheet1 && sheet1.getLastRow() === 0) ss.deleteSheet(sheet1);

  return { teams: teams, boards: boards, lineups: lineups, sponsorships: sponsorships, localTv: localTv };
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
      team_id: rows[i][0], final_revenue: rows[i][1],
      rep_team_id: rows[i][2], submitted_at: rows[i][3],
    });
  }
  return out;
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
    });
  }

  // public, non-admin reads used by the Sponsorship and TV Rights pages
  // to show live slot availability without needing the admin key
  if (params.catalog === "1") {
    return jsonOut_({
      ok: true,
      sponsor_catalog: SPONSOR_CATALOG,
      local_tv_base: LOCAL_TV_BASE,
      sponsorship_deals: readSponsorshipDeals_(sheets.sponsorships).map(function (d) {
        return { team_id: d.team_id, category: d.category, brand: d.brand }; // no revenue/clause -- not other teams' business
      }),
      local_tv_deals: readLocalTVDeals_(sheets.localTv).map(function (d) {
        return { team_id: d.team_id }; // just "has this team negotiated yet"
      }),
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

  var pinCheck = checkPin_(teams, body.team_id, body.pin);
  if (!pinCheck.ok) return jsonOut_({ ok: false, error: pinCheck.error });

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
        return jsonOut_({ ok: false, error: "Revenue different from base ($" + brand.base_revenue + ") requires rep_team_id to credit the commission." });
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

    var tvFinalRevenue;
    if (body.mode === "base") {
      tvFinalRevenue = tvBase.base_revenue;
    } else if (body.mode === "negotiate") {
      tvFinalRevenue = Number(body.final_revenue);
      if (!tvFinalRevenue) return jsonOut_({ ok: false, error: "Negotiated deals need final_revenue." });
    } else {
      return jsonOut_({ ok: false, error: "mode must be 'base' or 'negotiate'" });
    }

    // Same either-direction rule as Sponsorship Deal above.
    var tvRepTeamId = null;
    if (tvFinalRevenue !== tvBase.base_revenue) {
      if (body.rep_team_id === undefined || body.rep_team_id === null || body.rep_team_id === "") {
        return jsonOut_({ ok: false, error: "Rate different from base ($" + tvBase.base_revenue + ") requires rep_team_id to credit the commission." });
      }
      tvRepTeamId = body.rep_team_id;
    }

    sheets.localTv.appendRow([body.team_id, tvFinalRevenue, tvRepTeamId, now]);
    return jsonOut_({
      ok: true, team_id: body.team_id, final_revenue: tvFinalRevenue,
      commission: tvRepTeamId ? Math.abs(tvFinalRevenue - tvBase.base_revenue) : 0,
    });
  }

  return jsonOut_({ ok: false, error: "unknown submission type: " + body.type });
}
