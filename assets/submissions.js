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

// ---------------- Local TV Rate (TV Rights Marketplace) ----------------
function initTvForm() {
  const teamSel = document.getElementById('tv-team');
  const pinInput = document.getElementById('tv-pin');
  const tierNote = document.getElementById('tv-tier-note');
  const modeSel = document.getElementById('tv-mode');
  const revenueField = document.getElementById('tv-revenue-field');
  const repField = document.getElementById('tv-rep-field');
  const repSel = document.getElementById('tv-rep');
  const btn = document.getElementById('tv-submit');
  const msg = document.getElementById('tv-msg');

  repSel.innerHTML = TEAMS.map(t => `<option value="${t.id}">${t.name} (${t.owner})</option>`).join('');

  function updateTierNote() {
    const base = LOCAL_TV_BASE[teamSel.value];
    const already = EXISTING_LOCAL_TV_DEALS.some(d => String(d.team_id) === teamSel.value);
    if (!base) { tierNote.textContent = ''; return; }
    tierNote.textContent = already
      ? `This team's Local TV rate is already negotiated -- it's a one-time deal, resubmitting will be rejected.`
      : `Market tier: ${base.tier} -- Base rate: $${base.base_revenue.toLocaleString()}/season`;
  }
  function updateModeFields() {
    const negotiating = modeSel.value === 'negotiate';
    revenueField.hidden = !negotiating;
    repField.hidden = !negotiating;
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
      if (!revenue) { msg.textContent = 'Enter the final agreed rate.'; msg.className = 'sub-msg'; return; }
      body.final_revenue = revenue;
      if (revenue !== (LOCAL_TV_BASE[teamSel.value]?.base_revenue || 0)) {
        body.rep_team_id = repSel.value;
      }
    }

    btn.disabled = true;
    msg.textContent = 'Submitting...';
    msg.className = 'sub-msg';
    try {
      const result = await postSubmission(body);
      if (result.ok) {
        msg.textContent = `Saved -- $${result.final_revenue.toLocaleString()}/season` +
          (result.commission ? `, $${result.commission.toLocaleString()} commission credited to the rep.` : '.');
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
    const brand = SPONSOR_CATALOG.find(b => b.name === brandSel.value);
    const body = { type: 'sponsorship_deal', team_id: teamSel.value, pin, brand: brandSel.value, mode: modeSel.value };
    if (modeSel.value === 'negotiate') {
      const revenue = parseInt(document.getElementById('sp-revenue').value, 10);
      const clause = document.getElementById('sp-clause').value;
      if (!revenue) { msg.textContent = 'Enter the final agreed revenue.'; msg.className = 'sub-msg'; return; }
      body.final_revenue = revenue;
      body.final_clause = clause;
      if (brand && revenue !== brand.base_revenue) body.rep_team_id = repSel.value;
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
