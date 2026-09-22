/**
 * SPM261.01 Soccer League -- submission backend.
 *
 * Bound to the "SPM261.01 Soccer League — Submissions" Google Sheet.
 * Paste this into that Sheet's Extensions > Apps Script, then Deploy >
 * New deployment > Web app (Execute as: Me, Who has access: Anyone),
 * and send the resulting /exec URL back so it can be wired into
 * config.js.
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
 */

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

  // remove the default blank "Sheet1" left by spreadsheet creation, if still present and empty
  var sheet1 = ss.getSheetByName("Sheet1");
  if (sheet1 && sheet1.getLastRow() === 0) ss.deleteSheet(sheet1);

  return { teams: teams, boards: boards, lineups: lineups };
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

function doGet(e) {
  var sheets = ensureSheets_();
  var teams = readTeams_(sheets.teams).map(function (t) {
    return { id: t.id, name: t.name, owner: t.owner }; // never return pin on GET
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

  return jsonOut_({ ok: false, error: "unknown submission type: " + body.type });
}
