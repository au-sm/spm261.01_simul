// SPM261.01 Soccer League -- shared submission frontend, mounted directly
// on Dashboard (Rename Team / Draft Board / Weekly Lineup), Sponsorship
// Marketplace (Sponsorship Deal), and TV Rights Marketplace (Local TV
// Deal) -- there is no separate Submit page anymore. Talks to backend.gs
// (Apps Script Web App) at BACKEND_URL (assets/config.js). PIN checks
// happen server-side in backend.gs; this file never embeds or checks
// PINs itself. Each host page loads this file, then calls only the
// init*Form() functions for the forms it actually has on the page.

let TEAMS = [];
let PLAYERS = [];
let SPONSOR_CATALOG = [];
let LOCAL_TV_BASE = {};
let EXISTING_SPONSORSHIP_DEALS = []; // {team_id, category, brand} -- no revenue, not other teams' business
let EXISTING_LOCAL_TV_DEALS = []; // {team_id} -- just "has negotiated"
let EXISTING_TRADE_PROPOSALS = []; // full proposal objects, status: pending/accepted/rejected -- public, same as deal data

async function loadPlayers() {
  const res = await fetch('../players.json');
  PLAYERS = await res.json();
}

async function loadTeams() {
  if (!BACKEND_URL) {
    document.querySelectorAll('.sub-backend-warning').forEach(el => el.hidden = false);
    return;
  }
  const res = await fetch(BACKEND_URL);
  const data = await res.json();
  if (data.ok) TEAMS = data.teams;
}

async function loadCatalog() {
  if (!BACKEND_URL) return;
  const res = await fetch(BACKEND_URL + '?catalog=1');
  const data = await res.json();
  if (data.ok) {
    SPONSOR_CATALOG = data.sponsor_catalog;
    LOCAL_TV_BASE = data.local_tv_base;
    EXISTING_SPONSORSHIP_DEALS = data.sponsorship_deals;
    EXISTING_LOCAL_TV_DEALS = data.local_tv_deals;
    EXISTING_TRADE_PROPOSALS = data.trade_proposals || [];
  }
}

function populateTeamSelects() {
  document.querySelectorAll('.sub-team-select').forEach(sel => {
    sel.innerHTML = TEAMS.map(t => `<option value="${t.id}">${t.name} (${t.owner})</option>`).join('');
  });
}

async function postSubmission(body) {
  const res = await fetch(BACKEND_URL, {
    method: 'POST',
    // Apps Script Web Apps don't handle a preflighted application/json
    // request from a cross-origin page well; text/plain avoids the
    // CORS preflight and Apps Script still reads e.postData.contents fine.
    headers: { 'Content-Type': 'text/plain;charset=utf-8' },
    body: JSON.stringify(body),
  });
  return res.json();
}

// ---------------- Rename Your Team (Dashboard) ----------------
function initRenameForm() {
  const teamSel = document.getElementById('rn-team');
  const pinInput = document.getElementById('rn-pin');
  const nameInput = document.getElementById('rn-name');
  const btn = document.getElementById('rn-submit');
  const msg = document.getElementById('rn-msg');

  btn.addEventListener('click', async () => {
    const teamId = teamSel.value;
    const pin = pinInput.value.trim();
    const newName = nameInput.value.trim();
    if (!pin || pin.length !== 4) { msg.textContent = 'Enter your 4-digit PIN.'; msg.className = 'sub-msg'; return; }
    if (!newName) { msg.textContent = 'Type your new team name.'; msg.className = 'sub-msg'; return; }

    btn.disabled = true;
    msg.textContent = 'Submitting...';
    msg.className = 'sub-msg';
    try {
      const result = await postSubmission({ type: 'rename_team', team_id: teamId, pin, new_name: newName });
      if (result.ok) {
        msg.textContent = `Saved -- your team is now "${result.name}".`;
        msg.className = 'sub-msg ok';
        pinInput.value = '';
        nameInput.value = '';
        await loadTeams();
        populateTeamSelects();
        teamSel.value = teamId;
      } else {
        msg.textContent = result.error || 'Something went wrong.';
        msg.className = 'sub-msg';
      }
    } catch (e) {
      msg.textContent = 'Could not reach the server -- check your connection and try again.';
      msg.className = 'sub-msg';
    }
    btn.disabled = false;
  });
}

// ---------------- Draft Board submission (Dashboard) ----------------
let boardPicks = []; // array of player objects, in ranked order

function renderBoard() {
  const list = document.getElementById('db-board');
  if (boardPicks.length === 0) {
    list.innerHTML = '<li class="sub-empty">Your ranked board is empty -- search below and add players.</li>';
  } else {
    list.innerHTML = boardPicks.map((p, i) => `
      <li>
        <span class="sub-rank">${i + 1}</span>
        <span class="sub-pos sub-pos-${p.position}">${p.position}</span>
        <span class="sub-name">${p.name}</span>
        <span class="sub-ovr">OVR ${p.ovr}</span>
        <button type="button" class="sub-up" data-i="${i}" ${i === 0 ? 'disabled' : ''}>&uarr;</button>
        <button type="button" class="sub-down" data-i="${i}" ${i === boardPicks.length - 1 ? 'disabled' : ''}>&darr;</button>
        <button type="button" class="sub-remove" data-i="${i}">remove</button>
      </li>`).join('');
  }
  document.getElementById('db-count').textContent =
    `${boardPicks.length} player${boardPicks.length === 1 ? '' : 's'} ranked (at least 25 recommended)`;

  list.querySelectorAll('.sub-up').forEach(b => b.addEventListener('click', () => {
    const i = parseInt(b.dataset.i, 10);
    [boardPicks[i - 1], boardPicks[i]] = [boardPicks[i], boardPicks[i - 1]];
    renderBoard();
  }));
  list.querySelectorAll('.sub-down').forEach(b => b.addEventListener('click', () => {
    const i = parseInt(b.dataset.i, 10);
    [boardPicks[i + 1], boardPicks[i]] = [boardPicks[i], boardPicks[i + 1]];
    renderBoard();
  }));
  list.querySelectorAll('.sub-remove').forEach(b => b.addEventListener('click', () => {
    boardPicks.splice(parseInt(b.dataset.i, 10), 1);
    renderBoard();
  }));
}

function renderSearchResults() {
  const q = document.getElementById('db-search').value.trim().toLowerCase();
  const posFilter = document.getElementById('db-pos-filter').value;
  const results = document.getElementById('db-results');
  if (!q && posFilter === 'ALL') { results.innerHTML = ''; return; }

  const pickedIds = new Set(boardPicks.map(p => p.id));
  const matches = PLAYERS.filter(p =>
    (posFilter === 'ALL' || p.position === posFilter) &&
    (!q || p.name.toLowerCase().includes(q)) &&
    !pickedIds.has(p.id)
  ).sort((a, b) => b.ovr - a.ovr).slice(0, 30);

  results.innerHTML = matches.map(p => `
    <li>
      <span class="sub-pos sub-pos-${p.position}">${p.position}</span>
      <span class="sub-name">${p.name}</span>
      <span class="sub-ovr">OVR ${p.ovr}</span>
      <button type="button" class="sub-add" data-id="${p.id}">add</button>
    </li>`).join('');

  results.querySelectorAll('.sub-add').forEach(b => b.addEventListener('click', () => {
    const player = PLAYERS.find(p => p.id === parseInt(b.dataset.id, 10));
    if (player) boardPicks.push(player);
    renderBoard();
    renderSearchResults();
  }));
}

function initDraftBoardForm() {
  document.getElementById('db-search').addEventListener('input', renderSearchResults);
  document.getElementById('db-pos-filter').addEventListener('change', renderSearchResults);
  renderBoard();

  document.getElementById('db-submit').addEventListener('click', async () => {
    const teamSel = document.getElementById('db-team');
    const pinInput = document.getElementById('db-pin');
    const msg = document.getElementById('db-msg');
    const btn = document.getElementById('db-submit');
    const pin = pinInput.value.trim();

    if (!pin || pin.length !== 4) { msg.textContent = 'Enter your 4-digit PIN.'; msg.className = 'sub-msg'; return; }
    if (boardPicks.length === 0) { msg.textContent = 'Add at least one player to your board first.'; msg.className = 'sub-msg'; return; }

    btn.disabled = true;
    msg.textContent = 'Submitting...';
    msg.className = 'sub-msg';
    try {
      const result = await postSubmission({
        type: 'draft_board', team_id: teamSel.value, pin,
        player_ids: boardPicks.map(p => p.id),
      });
      if (result.ok) {
        msg.textContent = `Saved -- ${result.count} players ranked. You can keep editing and resubmit any time before Draft Day.`;
        msg.className = 'sub-msg ok';
        pinInput.value = '';
      } else {
        msg.textContent = result.error || 'Something went wrong.';
        msg.className = 'sub-msg';
      }
    } catch (e) {
      msg.textContent = 'Could not reach the server -- check your connection and try again.';
      msg.className = 'sub-msg';
    }
    btn.disabled = false;
  });
}

// ---------------- Local TV Deal (TV Rights Marketplace) ----------------
function initTvForm() {
  const teamSel = document.getElementById('tv-team');
  const pinInput = document.getElementById('tv-pin');
  const tierNote = document.getElementById('tv-tier-note');
  const modeSel = document.getElementById('tv-mode');
  const negotiateFields = document.getElementById('tv-negotiate-fields');
  const repSel = document.getElementById('tv-rep');
  const btn = document.getElementById('tv-submit');
  const msg = document.getElementById('tv-msg');

  repSel.innerHTML = TEAMS.map(t => `<option value="${t.id}">${t.name} (${t.owner})</option>`).join('');

  function updateTierNote() {
    const base = LOCAL_TV_BASE[teamSel.value];
    const already = EXISTING_LOCAL_TV_DEALS.some(d => String(d.team_id) === teamSel.value);
    if (!base) { tierNote.textContent = ''; return; }
    tierNote.textContent = already
      ? `This team's Local TV Deal is already negotiated -- it's a one-time deal, resubmitting will be rejected.`
      : `Market tier: ${base.tier} -- ${base.base_clause} clause. Base rate is not posted here -- your network rep tells you the number face to face.`;
  }
  function updateModeFields() {
    negotiateFields.hidden = modeSel.value !== 'negotiate';
  }
  teamSel.addEventListener('change', updateTierNote);
  modeSel.addEventListener('change', updateModeFields);
  updateTierNote();
  updateModeFields();

  btn.addEventListener('click', async () => {
    const pin = pinInput.value.trim();
    if (!pin || pin.length !== 4) { msg.textContent = 'Enter your 4-digit PIN.'; msg.className = 'sub-msg'; return; }
    const body = { type: 'local_tv_deal', team_id: teamSel.value, pin, mode: modeSel.value };
    if (modeSel.value === 'negotiate') {
      const revenue = parseInt(document.getElementById('tv-revenue').value, 10);
      const clause = document.getElementById('tv-clause').value;
      if (!revenue) { msg.textContent = 'Enter the final agreed rate.'; msg.className = 'sub-msg'; return; }
      body.final_revenue = revenue;
      body.final_clause = clause;
      // LOCAL_TV_BASE no longer carries base_revenue client-side (the
      // backend deliberately strips it from ?catalog=1), so there's no
      // way to tell locally whether this lands exactly on base. Always
      // attach rep_team_id in negotiate mode -- backend.gs only actually
      // uses it (and only requires it) when the final rate truly differs
      // from the server-side base, so sending it when unneeded is harmless.
      body.rep_team_id = repSel.value;
    }

    btn.disabled = true;
    msg.textContent = 'Submitting...';
    msg.className = 'sub-msg';
    try {
      const result = await postSubmission(body);
      if (result.ok) {
        msg.textContent = `Saved -- $${result.final_revenue.toLocaleString()}/season, ${result.final_clause} clause` +
          (result.commission ? `. $${result.commission.toLocaleString()} commission credited to the rep.` : '.');
        msg.className = 'sub-msg ok';
        pinInput.value = '';
        await loadCatalog();
        updateTierNote();
      } else {
        msg.textContent = result.error || 'Something went wrong.';
        msg.className = 'sub-msg';
      }
    } catch (e) {
      msg.textContent = 'Could not reach the server -- check your connection and try again.';
      msg.className = 'sub-msg';
    }
    btn.disabled = false;
  });
}

// ---------------- Sponsorship Deal (Sponsorship Marketplace) ----------------
function initSponsorshipForm() {
  const teamSel = document.getElementById('sp-team');
  const pinInput = document.getElementById('sp-pin');
  const ownedNote = document.getElementById('sp-owned-note');
  const categorySel = document.getElementById('sp-category');
  const brandSel = document.getElementById('sp-brand');
  const modeSel = document.getElementById('sp-mode');
  const negotiateFields = document.getElementById('sp-negotiate-fields');
  const repSel = document.getElementById('sp-rep');
  const btn = document.getElementById('sp-submit');
  const msg = document.getElementById('sp-msg');

  repSel.innerHTML = TEAMS.map(t => `<option value="${t.id}">${t.name} (${t.owner})</option>`).join('');

  const categories = [...new Set(SPONSOR_CATALOG.map(b => b.category))];
  categorySel.innerHTML = categories.map(c => `<option value="${c}">${c}</option>`).join('');

  function slotsTaken(brandName) {
    return EXISTING_SPONSORSHIP_DEALS.filter(d => d.brand === brandName).length;
  }
  function updateBrands() {
    const brands = SPONSOR_CATALOG.filter(b => b.category === categorySel.value);
    brandSel.innerHTML = brands.map(b => {
      const taken = slotsTaken(b.name);
      const soldOut = taken >= b.qty;
      return `<option value="${b.name}" ${soldOut ? 'disabled' : ''}>${b.name} (${taken}/${b.qty} slots)${soldOut ? ' SOLD OUT' : ''}</option>`;
    }).join('');
  }
  function updateOwnedNote() {
    const owned = EXISTING_SPONSORSHIP_DEALS.filter(d => String(d.team_id) === teamSel.value);
    ownedNote.textContent = owned.length
      ? `Already signed: ${owned.map(d => `${d.category} (${d.brand})`).join(', ')}`
      : 'No sponsors signed yet.';
  }
  function updateModeFields() {
    negotiateFields.hidden = modeSel.value !== 'negotiate';
  }
  categorySel.addEventListener('change', updateBrands);
  teamSel.addEventListener('change', updateOwnedNote);
  modeSel.addEventListener('change', updateModeFields);
  updateBrands();
  updateOwnedNote();
  updateModeFields();

  btn.addEventListener('click', async () => {
    const pin = pinInput.value.trim();
    if (!pin || pin.length !== 4) { msg.textContent = 'Enter your 4-digit PIN.'; msg.className = 'sub-msg'; return; }
    const body = { type: 'sponsorship_deal', team_id: teamSel.value, pin, brand: brandSel.value, mode: modeSel.value };
    if (modeSel.value === 'negotiate') {
      const revenue = parseInt(document.getElementById('sp-revenue').value, 10);
      const clause = document.getElementById('sp-clause').value;
      if (!revenue) { msg.textContent = 'Enter the final agreed revenue.'; msg.className = 'sub-msg'; return; }
      body.final_revenue = revenue;
      body.final_clause = clause;
      // SPONSOR_CATALOG no longer carries base_revenue client-side (the
      // backend deliberately strips it from ?catalog=1). Always attach
      // rep_team_id in negotiate mode -- backend.gs only actually uses it
      // (and only requires it) when the final revenue truly differs from
      // the server-side base, so sending it when unneeded is harmless.
      body.rep_team_id = repSel.value;
    }

    btn.disabled = true;
    msg.textContent = 'Submitting...';
    msg.className = 'sub-msg';
    try {
      const result = await postSubmission(body);
      if (result.ok) {
        msg.textContent = `Saved -- ${result.brand} (${result.category}): $${result.final_revenue.toLocaleString()}, ${result.final_clause} clause` +
          (result.commission ? `. $${result.commission.toLocaleString()} commission credited to the rep.` : '.');
        msg.className = 'sub-msg ok';
        pinInput.value = '';
        await loadCatalog();
        updateBrands();
        updateOwnedNote();
      } else {
        msg.textContent = result.error || 'Something went wrong.';
        msg.className = 'sub-msg';
      }
    } catch (e) {
      msg.textContent = 'Could not reach the server -- check your connection and try again.';
      msg.className = 'sub-msg';
    }
    btn.disabled = false;
  });
}

// ---------------- Weekly Lineup (Dashboard) ----------------
const SUB_FORMATIONS = {
  '4-4-2': { GK: 1, DF: 4, MF: 4, FW: 2 }, '4-3-3': { GK: 1, DF: 4, MF: 3, FW: 3 },
  '3-5-2': { GK: 1, DF: 3, MF: 5, FW: 2 }, '5-3-2': { GK: 1, DF: 5, MF: 3, FW: 2 },
  '4-5-1': { GK: 1, DF: 4, MF: 5, FW: 1 },
};

function initLineupForm() {
  const teamSel = document.getElementById('lu-team');
  const formationSel = document.getElementById('lu-formation');
  const roster_note = document.getElementById('lu-roster-note');
  const slotsEl = document.getElementById('lu-slots');
  const btn = document.getElementById('lu-submit');
  const msg = document.getElementById('lu-msg');

  function teamRoster() {
    return PLAYERS.filter(p => String(p.team_id) === teamSel.value);
  }
  function playerOptions(position) {
    const opts = teamRoster().filter(p => p.position === position)
      .map(p => `<option value="${p.name}">#${p.id} -- ${p.name} (OVR ${p.ovr})</option>`).join('');
    return opts || '<option value="" disabled selected>No players drafted at this position yet</option>';
  }
  function rebuildSlots() {
    const roster = teamRoster();
    roster_note.textContent = roster.length
      ? `${roster.length} players on this roster.`
      : 'No players drafted yet for this team -- the lineup form needs a completed draft first.';
    const counts = SUB_FORMATIONS[formationSel.value];
    slotsEl.innerHTML = ['GK', 'DF', 'MF', 'FW'].map(pos => {
      const n = counts[pos];
      const selects = Array.from({ length: n }, () =>
        `<select class="sub-lineup-slot" data-pos="${pos}">${playerOptions(pos)}</select>`
      ).join('');
      return `<div class="sub-slot-group"><h4>${pos} (${n})</h4>${selects}</div>`;
    }).join('');
  }
  teamSel.addEventListener('change', rebuildSlots);
  formationSel.addEventListener('change', rebuildSlots);
  rebuildSlots();

  btn.addEventListener('click', async () => {
    const pinInput = document.getElementById('lu-pin');
    const pin = pinInput.value.trim();
    const round = parseInt(document.getElementById('lu-round').value, 10);
    if (!pin || pin.length !== 4) { msg.textContent = 'Enter your 4-digit PIN.'; msg.className = 'sub-msg'; return; }
    if (!round || round < 1 || round > 17) { msg.textContent = 'Enter a valid round number (1-17).'; msg.className = 'sub-msg'; return; }

    const slots = Array.from(document.querySelectorAll('.sub-lineup-slot'));
    const chosen = slots.map(s => ({ pos: s.dataset.pos, name: s.value }));
    if (chosen.some(c => !c.name)) { msg.textContent = 'Fill every starting slot first.'; msg.className = 'sub-msg'; return; }
    const names = chosen.map(c => c.name);
    if (new Set(names).size !== names.length) { msg.textContent = 'The same player is selected in two slots.'; msg.className = 'sub-msg'; return; }

    const byPos = pos => chosen.filter(c => c.pos === pos).map(c => c.name);
    const rationale = document.getElementById('lu-rationale').value.trim();

    const body = {
      type: 'weekly_lineup', team_id: teamSel.value, pin, round,
      formation: formationSel.value, strategy: document.getElementById('lu-strategy').value,
      gk: byPos('GK')[0], df: byPos('DF'), mf: byPos('MF'), fw: byPos('FW'),
      ticket_price: document.getElementById('lu-price').value, rationale,
    };

    btn.disabled = true;
    msg.textContent = 'Submitting...';
    msg.className = 'sub-msg';
    try {
      const result = await postSubmission(body);
      if (result.ok) {
        msg.textContent = `Saved -- Round ${result.round} lineup submitted. You can resubmit any time before the deadline.`;
        msg.className = 'sub-msg ok';
        pinInput.value = '';
      } else {
        msg.textContent = result.error || 'Something went wrong.';
        msg.className = 'sub-msg';
      }
    } catch (e) {
      msg.textContent = 'Could not reach the server -- check your connection and try again.';
      msg.className = 'sub-msg';
    }
    btn.disabled = false;
  });
}

// ---------------- Trade Center: Propose a Trade ----------------
// A trade only ever completes with BOTH teams' consent -- this form just
// sends the OFFER (status "pending" in the TradeProposals sheet); nothing
// moves until the receiving team accepts it in initTradeRespondForm()
// below. Roster ownership and the salary cap are re-checked for real by
// engine/resolve_trade.py once accepted -- this form can only check what
// the client already knows (roster membership, matching counts), so a
// proposal that looks fine here can still come back voided later (shown
// in the trade log) if something about the rosters changed in between.
let tradeGivePicks = []; // players from your own roster, up to 3
let tradeWantPicks = []; // players from the partner's roster, up to 3

function tradeTeamRoster(teamId) {
  return PLAYERS.filter(p => String(p.team_id) === String(teamId));
}

function renderTradeSide(listId, picks, countLabelId) {
  const list = document.getElementById(listId);
  if (picks.length === 0) {
    list.innerHTML = '<li class="sub-empty">None selected yet -- search below and add players.</li>';
  } else {
    list.innerHTML = picks.map((p, i) => `
      <li>
        <span class="sub-pos sub-pos-${p.position}">${p.position}</span>
        <span class="sub-name">${p.name}</span>
        <span class="sub-ovr">OVR ${p.ovr} &middot; $${p.salary.toLocaleString()}</span>
        <button type="button" class="sub-remove" data-list="${listId}" data-i="${i}">remove</button>
      </li>`).join('');
  }
  document.getElementById(countLabelId).textContent = `${picks.length}/3 selected`;
}

function renderTradeSearch(resultsId, searchId, posFilterId, rosterFn, picks, listId, countLabelId) {
  const q = document.getElementById(searchId).value.trim().toLowerCase();
  const posFilter = document.getElementById(posFilterId).value;
  const results = document.getElementById(resultsId);
  const roster = rosterFn();
  const pickedIds = new Set(picks.map(p => p.id));
  const matches = roster.filter(p =>
    (posFilter === 'ALL' || p.position === posFilter) &&
    (!q || p.name.toLowerCase().includes(q)) &&
    !pickedIds.has(p.id)
  ).sort((a, b) => b.ovr - a.ovr).slice(0, 30);

  results.innerHTML = roster.length === 0
    ? '<li class="sub-empty">No roster yet -- this team has not been drafted.</li>'
    : matches.map(p => `
      <li>
        <span class="sub-pos sub-pos-${p.position}">${p.position}</span>
        <span class="sub-name">${p.name}</span>
        <span class="sub-ovr">OVR ${p.ovr} &middot; $${p.salary.toLocaleString()}</span>
        <button type="button" class="sub-add" data-id="${p.id}" ${picks.length >= 3 ? 'disabled' : ''}>add</button>
      </li>`).join('');

  results.querySelectorAll('.sub-add').forEach(b => b.addEventListener('click', () => {
    if (picks.length >= 3) return;
    const player = roster.find(p => p.id === parseInt(b.dataset.id, 10));
    if (player) picks.push(player);
    renderTradeSide(listId, picks, countLabelId);
    renderTradeSearch(resultsId, searchId, posFilterId, rosterFn, picks, listId, countLabelId);
  }));
}

function initTradeProposeForm() {
  const teamSel = document.getElementById('tp-team');
  const partnerSel = document.getElementById('tp-partner');
  const pinInput = document.getElementById('tp-pin');
  const btn = document.getElementById('tp-submit');
  const msg = document.getElementById('tp-msg');

  function refreshGive() {
    renderTradeSide('tp-give-list', tradeGivePicks, 'tp-give-count');
    renderTradeSearch('tp-give-results', 'tp-give-search', 'tp-give-pos', () => tradeTeamRoster(teamSel.value), tradeGivePicks, 'tp-give-list', 'tp-give-count');
  }
  function refreshWant() {
    renderTradeSide('tp-want-list', tradeWantPicks, 'tp-want-count');
    renderTradeSearch('tp-want-results', 'tp-want-search', 'tp-want-pos', () => tradeTeamRoster(partnerSel.value), tradeWantPicks, 'tp-want-list', 'tp-want-count');
  }
  function resetAndRebuild() {
    tradeGivePicks = [];
    tradeWantPicks = [];
    document.getElementById('tp-give-search').value = '';
    document.getElementById('tp-want-search').value = '';
    refreshGive();
    refreshWant();
  }

  teamSel.addEventListener('change', resetAndRebuild);
  partnerSel.addEventListener('change', resetAndRebuild);
  document.getElementById('tp-give-search').addEventListener('input', refreshGive);
  document.getElementById('tp-give-pos').addEventListener('change', refreshGive);
  document.getElementById('tp-want-search').addEventListener('input', refreshWant);
  document.getElementById('tp-want-pos').addEventListener('change', refreshWant);

  // event delegation on the (stable) parent <ul> elements -- survives
  // innerHTML rebuilds in renderTradeSide, unlike binding on the buttons
  // themselves would.
  document.getElementById('tp-give-list').addEventListener('click', (e) => {
    const b = e.target.closest('.sub-remove');
    if (!b) return;
    tradeGivePicks.splice(parseInt(b.dataset.i, 10), 1);
    refreshGive();
  });
  document.getElementById('tp-want-list').addEventListener('click', (e) => {
    const b = e.target.closest('.sub-remove');
    if (!b) return;
    tradeWantPicks.splice(parseInt(b.dataset.i, 10), 1);
    refreshWant();
  });

  resetAndRebuild();

  btn.addEventListener('click', async () => {
    const pin = pinInput.value.trim();
    if (!pin || pin.length !== 4) { msg.textContent = 'Enter your 4-digit PIN.'; msg.className = 'sub-msg'; return; }
    if (teamSel.value === partnerSel.value) { msg.textContent = 'Pick a different team to trade with.'; msg.className = 'sub-msg'; return; }
    if (tradeGivePicks.length === 0) { msg.textContent = 'Select at least one player to give up.'; msg.className = 'sub-msg'; return; }
    if (tradeGivePicks.length !== tradeWantPicks.length) {
      msg.textContent = `You're offering ${tradeGivePicks.length} player(s) for ${tradeWantPicks.length} -- both sides must match: 1-for-1, 2-for-2, or 3-for-3.`;
      msg.className = 'sub-msg';
      return;
    }
    const rationale = document.getElementById('tp-rationale').value.trim();
    if (!rationale) { msg.textContent = 'Add a short rationale for this trade (this is graded).'; msg.className = 'sub-msg'; return; }

    const body = {
      type: 'trade_proposal', team_id: teamSel.value, pin,
      receiver_team_id: partnerSel.value,
      players_out: tradeGivePicks.map(p => ({ id: p.id, name: p.name })),
      players_in: tradeWantPicks.map(p => ({ id: p.id, name: p.name })),
      cash_from_proposer: parseInt(document.getElementById('tp-cash-give').value, 10) || 0,
      cash_from_receiver: parseInt(document.getElementById('tp-cash-want').value, 10) || 0,
      rationale,
    };

    btn.disabled = true;
    msg.textContent = 'Submitting...';
    msg.className = 'sub-msg';
    try {
      const result = await postSubmission(body);
      if (result.ok) {
        msg.textContent = 'Trade proposed -- it now sits pending until the other team accepts or declines it below.';
        msg.className = 'sub-msg ok';
        pinInput.value = '';
        await loadCatalog();
        renderTradeLog();
        renderTradeInbox();
      } else {
        msg.textContent = result.error || 'Something went wrong.';
        msg.className = 'sub-msg';
      }
    } catch (e) {
      msg.textContent = 'Could not reach the server -- check your connection and try again.';
      msg.className = 'sub-msg';
    }
    btn.disabled = false;
  });
}

// ---------------- Trade Center: Respond to a Trade ----------------
function renderTradeInbox() {
  const teamSel = document.getElementById('tr-team');
  const list = document.getElementById('tr-inbox');
  if (!teamSel || !list) return;
  const pending = EXISTING_TRADE_PROPOSALS.filter(p => String(p.receiver_team_id) === teamSel.value && p.status === 'pending');
  if (pending.length === 0) {
    list.innerHTML = '<li class="sub-empty">No pending trade offers for this team.</li>';
    return;
  }
  const teamName = id => (TEAMS.find(t => String(t.id) === String(id)) || {}).name || `Team ${id}`;
  list.innerHTML = pending.map(p => `
    <li class="sub-trade-offer">
      <p><b>${teamName(p.proposer_team_id)}</b> offers: ${p.players_out.map(pl => pl.name).join(', ')}${p.cash_from_proposer ? ` + $${Number(p.cash_from_proposer).toLocaleString()}` : ''}
      &nbsp;&rarr;&nbsp; for &nbsp;&rarr;&nbsp;
      ${p.players_in.map(pl => pl.name).join(', ')}${p.cash_from_receiver ? ` + $${Number(p.cash_from_receiver).toLocaleString()}` : ''}</p>
      <p class="sub-trade-rationale">&ldquo;${p.rationale}&rdquo;</p>
      <button type="button" class="sub-btn sub-trade-accept" data-id="${p.proposal_id}">Accept</button>
      <button type="button" class="sub-btn sub-trade-decline" data-id="${p.proposal_id}">Decline</button>
    </li>`).join('');

  list.querySelectorAll('.sub-trade-accept, .sub-trade-decline').forEach(b => b.addEventListener('click', async () => {
    const pinInput = document.getElementById('tr-pin');
    const msg = document.getElementById('tr-msg');
    const pin = pinInput.value.trim();
    if (!pin || pin.length !== 4) { msg.textContent = 'Enter your 4-digit PIN first.'; msg.className = 'sub-msg'; return; }
    const decision = b.classList.contains('sub-trade-accept') ? 'accept' : 'reject';
    list.querySelectorAll('button').forEach(x => x.disabled = true);
    msg.textContent = 'Submitting...';
    msg.className = 'sub-msg';
    try {
      const result = await postSubmission({ type: 'trade_response', team_id: teamSel.value, pin, proposal_id: b.dataset.id, decision });
      if (result.ok) {
        msg.textContent = decision === 'accept'
          ? 'Accepted -- this trade will apply automatically once the next league-office check confirms rosters and cap room (usually within the hour).'
          : 'Declined.';
        msg.className = 'sub-msg ok';
        pinInput.value = '';
        await loadCatalog();
        renderTradeInbox();
        renderTradeLog();
      } else {
        msg.textContent = result.error || 'Something went wrong.';
        msg.className = 'sub-msg';
        list.querySelectorAll('button').forEach(x => x.disabled = false);
      }
    } catch (e) {
      msg.textContent = 'Could not reach the server -- check your connection and try again.';
      msg.className = 'sub-msg';
      list.querySelectorAll('button').forEach(x => x.disabled = false);
    }
  }));
}

function initTradeRespondForm() {
  const teamSel = document.getElementById('tr-team');
  teamSel.addEventListener('change', renderTradeInbox);
  renderTradeInbox();
}

// ---------------- Trade Center: live pending/responded log ----------------
// Final APPLIED/VOIDED outcomes (after engine/resolve_trade.py's own
// roster + salary-cap re-check) are server-rendered separately, straight
// from data/trades.json, by engine/render_trade_site.py -- this table is
// only the live pending/accepted/declined status straight from the Sheet.
function renderTradeLog() {
  const el = document.getElementById('tp-live-log');
  if (!el) return;
  const teamName = id => (TEAMS.find(t => String(t.id) === String(id)) || {}).name || `Team ${id}`;
  const rows = EXISTING_TRADE_PROPOSALS.slice().reverse();
  if (rows.length === 0) {
    el.innerHTML = '<tr><td colspan="4" class="sub-empty">No trades proposed yet.</td></tr>';
    return;
  }
  el.innerHTML = rows.map(p => `
    <tr>
      <td>${teamName(p.proposer_team_id)} &rarr; ${teamName(p.receiver_team_id)}</td>
      <td>${p.players_out.map(pl => pl.name).join(', ')} for ${p.players_in.map(pl => pl.name).join(', ')}</td>
      <td><span class="sub-status sub-status-${p.status}">${p.status}</span></td>
      <td>${(p.timestamp || '').slice(0, 10)}</td>
    </tr>`).join('');
}
