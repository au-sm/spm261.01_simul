// SPM261.01 Soccer League -- submission frontend.
// Talks to backend.gs (Apps Script Web App) at BACKEND_URL (config.js).
// PIN checks happen server-side in backend.gs; this file never embeds
// or checks PINs itself.

let TEAMS = [];
let PLAYERS = [];

async function loadPlayers() {
  const res = await fetch('players.json');
  PLAYERS = await res.json();
}

async function loadTeams() {
  if (!BACKEND_URL) {
    document.querySelectorAll('.backend-warning').forEach(el => el.hidden = false);
    return;
  }
  const res = await fetch(BACKEND_URL);
  const data = await res.json();
  if (data.ok) TEAMS = data.teams;
}

function populateTeamSelects() {
  document.querySelectorAll('.team-select').forEach(sel => {
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

// ---------------- Rename Your Team ----------------
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
    if (!pin || pin.length !== 4) { msg.textContent = 'Enter your 4-digit PIN.'; msg.className = 'msg'; return; }
    if (!newName) { msg.textContent = 'Type your new team name.'; msg.className = 'msg'; return; }

    btn.disabled = true;
    msg.textContent = 'Submitting...';
    msg.className = 'msg';
    try {
      const result = await postSubmission({ type: 'rename_team', team_id: teamId, pin, new_name: newName });
      if (result.ok) {
        msg.textContent = `Saved -- your team is now "${result.name}".`;
        msg.className = 'msg ok';
        pinInput.value = '';
        nameInput.value = '';
        await loadTeams();
        populateTeamSelects();
        teamSel.value = teamId;
      } else {
        msg.textContent = result.error || 'Something went wrong.';
        msg.className = 'msg';
      }
    } catch (e) {
      msg.textContent = 'Could not reach the server -- check your connection and try again.';
      msg.className = 'msg';
    }
    btn.disabled = false;
  });
}

// ---------------- Draft Board ----------------
let boardPicks = []; // array of player objects, in ranked order

function renderBoard() {
  const list = document.getElementById('db-board');
  if (boardPicks.length === 0) {
    list.innerHTML = '<li class="empty">Your ranked board is empty -- search below and add players.</li>';
  } else {
    list.innerHTML = boardPicks.map((p, i) => `
      <li>
        <span class="rank">${i + 1}</span>
        <span class="pos pos-${p.position}">${p.position}</span>
        <span class="name">${p.name}</span>
        <span class="ovr">OVR ${p.ovr}</span>
        <button type="button" class="up" data-i="${i}" ${i === 0 ? 'disabled' : ''}>&uarr;</button>
        <button type="button" class="down" data-i="${i}" ${i === boardPicks.length - 1 ? 'disabled' : ''}>&darr;</button>
        <button type="button" class="remove" data-i="${i}">remove</button>
      </li>`).join('');
  }
  document.getElementById('db-count').textContent =
    `${boardPicks.length} player${boardPicks.length === 1 ? '' : 's'} ranked (at least 25 recommended)`;

  list.querySelectorAll('.up').forEach(b => b.addEventListener('click', () => {
    const i = parseInt(b.dataset.i, 10);
    [boardPicks[i - 1], boardPicks[i]] = [boardPicks[i], boardPicks[i - 1]];
    renderBoard();
  }));
  list.querySelectorAll('.down').forEach(b => b.addEventListener('click', () => {
    const i = parseInt(b.dataset.i, 10);
    [boardPicks[i + 1], boardPicks[i]] = [boardPicks[i], boardPicks[i + 1]];
    renderBoard();
  }));
  list.querySelectorAll('.remove').forEach(b => b.addEventListener('click', () => {
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
      <span class="pos pos-${p.position}">${p.position}</span>
      <span class="name">${p.name}</span>
      <span class="ovr">OVR ${p.ovr}</span>
      <button type="button" class="add" data-id="${p.id}">add</button>
    </li>`).join('');

  results.querySelectorAll('.add').forEach(b => b.addEventListener('click', () => {
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

    if (!pin || pin.length !== 4) { msg.textContent = 'Enter your 4-digit PIN.'; msg.className = 'msg'; return; }
    if (boardPicks.length === 0) { msg.textContent = 'Add at least one player to your board first.'; msg.className = 'msg'; return; }

    btn.disabled = true;
    msg.textContent = 'Submitting...';
    msg.className = 'msg';
    try {
      const result = await postSubmission({
        type: 'draft_board', team_id: teamSel.value, pin,
        player_ids: boardPicks.map(p => p.id),
      });
      if (result.ok) {
        msg.textContent = `Saved -- ${result.count} players ranked. You can keep editing and resubmit any time before Draft Day.`;
        msg.className = 'msg ok';
        pinInput.value = '';
      } else {
        msg.textContent = result.error || 'Something went wrong.';
        msg.className = 'msg';
      }
    } catch (e) {
      msg.textContent = 'Could not reach the server -- check your connection and try again.';
      msg.className = 'msg';
    }
    btn.disabled = false;
  });
}

(async function init() {
  await Promise.all([loadPlayers(), loadTeams()]);
  populateTeamSelects();
  initRenameForm();
  initDraftBoardForm();
})();
