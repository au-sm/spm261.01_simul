// Player Health Hub request form (health/index.html). Data comes from the
// HH_DATA blob the page generator embeds (engine/render_health_site.py);
// requests go to backend.gs (type "health_treatment"), which checks the PIN,
// the per-round limit, and duplicates. engine/health.py applies or voids
// each request on the next auto-resolve cycle. Top-level names are hh-
// prefixed so this file can't collide with assets/submissions.js.
(function () {
  const D = HH_DATA;
  const $ = id => document.getElementById(id);
  const money = n => '$' + Number(n).toLocaleString('en-US');
  const teamSel = $('hh-team'), pinIn = $('hh-pin'), playerSel = $('hh-player'),
        treatSel = $('hh-treat'), btn = $('hh-submit'), msg = $('hh-msg');

  function setMsg(text, cls) { msg.textContent = text; msg.className = 'hh-msg ' + (cls || ''); }

  function fillTeams(list) {
    teamSel.innerHTML = '<option value="">Select your team</option>' +
      list.map(t => `<option value="${t.id}">${t.name}${t.owner ? ' (' + t.owner + ')' : ''}</option>`).join('');
  }

  function playerById(id) { return D.players.find(p => String(p.id) === String(id)); }

  function fillPlayers() {
    const tid = teamSel.value;
    const roster = D.players.filter(p => p.team_id === tid);
    playerSel.innerHTML = '<option value="">Select a player</option>' + roster.map(p =>
      `<option value="${p.id}">${p.pos} · ${p.name} (${p.ovr}) · ${p.injured_until ? 'Injured through R' + p.injured_until : p.cond}</option>`).join('');
    const t = D.teams[tid];
    $('hh-cash').textContent = t ? `Cash available: ${money(t.cash)} · Treatments used for Round ${D.next_round}: ${t.used} / ${D.max_per_round}` : '';
    fillTreatments();
  }

  function fillTreatments() {
    const p = playerById(playerSel.value);
    $('hh-player-info').textContent = p
      ? (p.injured_until ? `${p.name} is injured through Round ${p.injured_until}. Rehab options are shown.`
                         : `${p.name}'s condition for Round ${D.next_round}: ${p.cond}.`)
      : '';
    if (!p) { treatSel.innerHTML = ''; return; }
    const kind = p.injured_until ? 'injury' : 'form';
    const opts = Object.entries(D.catalog).filter(([, t]) => t.kind === kind)
      .filter(([, t]) => !(kind === 'form' && p.cond === 'Excellent'));
    treatSel.innerHTML = opts.length
      ? opts.map(([k, t]) => `<option value="${k}">${t.label} · ${money(t.cost)} · ${t.effect}</option>`).join('')
      : '<option value="">Already Excellent — no treatment needed</option>';
  }

  teamSel.addEventListener('change', fillPlayers);
  playerSel.addEventListener('change', fillTreatments);

  if (!D.open) {
    btn.disabled = true;
    setMsg(D.next_round < D.start_round ? `Requests open for Round ${D.start_round}.` : 'The season is over.');
  }

  btn.addEventListener('click', async () => {
    const tid = teamSel.value, pin = pinIn.value.trim(), p = playerById(playerSel.value), treat = treatSel.value;
    if (!tid || !pin || !p || !treat) { setMsg('Choose your team, enter your PIN, and pick a player and treatment.', 'err'); return; }
    const t = D.teams[tid], cost = D.catalog[treat].cost;
    if (t && t.cash < cost) { setMsg('Not enough cash on hand for this treatment.', 'err'); return; }
    btn.disabled = true; setMsg('Submitting…');
    try {
      const res = await fetch(BACKEND_URL, {
        method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' },
        body: JSON.stringify({ type: 'health_treatment', team_id: tid, pin, round: D.next_round,
                               player_id: p.id, player_name: p.name, treatment: treat }),
      });
      const r = await res.json();
      if (r.ok) {
        setMsg(`Booked: ${D.catalog[treat].label} for ${p.name} (Round ${D.next_round}). It will be applied within about 30 minutes; the Dashboard condition report and this page will update then.`, 'ok');
        pinIn.value = '';
      } else {
        setMsg('Not accepted: ' + r.error, 'err');
      }
    } catch (e) {
      setMsg('Could not reach the league server. Please try again.', 'err');
    }
    btn.disabled = !D.open;
  });

  if (typeof BACKEND_URL === 'undefined' || !BACKEND_URL) {
    document.querySelectorAll('.sub-backend-warning').forEach(el => el.hidden = false);
    btn.disabled = true;
    fillTeams(Object.entries(D.teams).map(([id, t]) => ({ id, name: t.name })));
  } else {
    fetch(BACKEND_URL).then(r => r.json()).then(d => fillTeams(d.ok ? d.teams : []))
      .catch(() => fillTeams(Object.entries(D.teams).map(([id, t]) => ({ id, name: t.name }))));
  }
})();
