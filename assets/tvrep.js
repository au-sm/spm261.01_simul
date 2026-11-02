// AI TV Rep (tv-rep/index.html). Sign-in reuses the coach_chat hello (PIN
// check + team snapshot); the negotiation is type "tv_negotiation" with
// action start / offer / accept / leave. Every offer amount comes back from
// backend.gs -- this page never computes one.
(function () {
  const $ = id => document.getElementById(id);
  const money = n => '$' + Math.round(Number(n)).toLocaleString('en-US');
  const clauseText = c => c === 'none' ? 'no performance clause' : 'a ' + c + ' clause';
  const ordinal = n => n + ({ 1: 'st', 2: 'nd', 3: 'rd' }[(n % 100 > 10 && n % 100 < 14) ? 0 : n % 10] || 'th');
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const setMsg = (el, text, kind) => { el.textContent = text || ''; el.className = 'msg' + (kind ? ' ' + kind : ''); };
  const teamSel = $('tr-team'), pinIn = $('tr-pin');
  const NOT_ON = 'The AI TV Rep is not switched on yet. Please check back soon.';
  let session = null, table = null, busy = false;

  teamSel.innerHTML = '<option value="">Select your team</option>' +
    TR_TEAMS.map(t => `<option value="${t.id}">${esc(t.name)}${t.owner ? ' (' + esc(t.owner) + ')' : ''}</option>`).join('');

  async function post(body) {
    const res = await fetch(BACKEND_URL, {
      method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' },
      body: JSON.stringify(Object.assign({ team_id: session ? session.team_id : teamSel.value,
                                           pin: session ? session.pin : pinIn.value.trim() }, body)),
    });
    return res.json();
  }
  const friendly = err => /unknown submission type/.test(err || '') ? NOT_ON : err;

  async function loadStatus() {
    try {
      const data = await (await fetch(BACKEND_URL + '?catalog=1')).json();
      const t = (data.local_tv_base || {})[session.team_id];
      if (t) $('tr-s-tier').textContent = t.tier;
      const signed = (data.local_tv_deals || []).some(d => String(d.team_id) === String(session.team_id));
      $('tr-s-deal').textContent = signed ? 'Signed' : 'Not signed';
      $('tr-pick').hidden = signed;
      if (signed) setMsg($('tr-pick-msg'), '');
    } catch (e) { /* the backend re-checks when the meeting starts */ }
  }

  $('tr-signin-btn').addEventListener('click', async () => {
    const msg = $('tr-signin-msg');
    if (!teamSel.value || !pinIn.value.trim()) return setMsg(msg, 'Choose your team and enter your PIN.', 'err');
    $('tr-signin-btn').disabled = true; setMsg(msg, 'Checking…');
    try {
      const r = await post({ type: 'coach_chat', hello: true });
      if (!r.ok) { setMsg(msg, r.error, 'err'); $('tr-signin-btn').disabled = false; return; }
      session = { team_id: teamSel.value, pin: pinIn.value.trim(), leverage: r.leverage };
      $('tr-s-name').textContent = r.team_name;
      $('tr-s-pos').textContent = ordinal(r.position) + ' of ' + TR_TEAMS.length;
      $('tr-s-lev').textContent = r.leverage != null ? r.leverage + ' / 100' : 'see Rulebook 11';
      $('tr-signin').hidden = true; $('tr-desk').hidden = false;
      await loadStatus();
    } catch (e) {
      setMsg(msg, 'Could not reach the league server. Please try again.', 'err'); $('tr-signin-btn').disabled = false;
    }
  });
  pinIn.addEventListener('keydown', e => { if (e.key === 'Enter') $('tr-signin-btn').click(); });

  function bubble(role, text, extra) {
    const el = document.createElement('div');
    el.className = 'bubble ' + role + (extra ? ' ' + extra : '');
    if (role === 'rep') el.dataset.who = 'Network rep';
    el.textContent = text;
    $('tr-chat').appendChild(el);
    $('tr-chat').scrollTop = $('tr-chat').scrollHeight;
    return el;
  }

  function showSession(s) {
    table = s;
    $('tr-offer').textContent = money(s.offer);
    $('tr-clause').textContent = s.clause === 'none' ? 'no' : s.clause;
    $('tr-left').textContent = s.status === 'final' ? 'final offer' : s.status === 'agreed' ? 'agreed' : s.turns_left + ' offers left';
    const closed = s.status === 'walked';
    $('tr-accept').disabled = closed;
    $('tr-accept').textContent = 'Sign for ' + money(s.offer);
    $('tr-composer').hidden = closed || s.status === 'final' || s.status === 'agreed';
  }

  const CLAUSES = ['strict', 'standard', 'loose', 'none'], STEP_LEVERAGE = [0, 20, 50, 80];
  function buildClauseOptions(opening) {
    const base = CLAUSES.indexOf(opening), lev = session.leverage != null ? Number(session.leverage) : null;
    let html = `<option value="keep">Keep the ${esc(opening)} clause</option>`;
    for (let i = base + 1; i < CLAUSES.length; i++) {
      const need = STEP_LEVERAGE[i - base], short = lev != null && lev < need;
      const name = CLAUSES[i] === 'none' ? 'No performance clause' : 'Ask for a ' + CLAUSES[i] + ' clause';
      html += `<option value="${CLAUSES[i]}"${short ? ' disabled' : ''}>${name} (${short ? 'needs ' : ''}leverage ${need}+)</option>`;
    }
    $('tr-clause-ask').innerHTML = html;
    $('tr-clause-ask').value = 'keep';
  }

  function openTable(on) {
    $('tr-table').hidden = !on; $('tr-pick').hidden = on;
    if (!on) { $('tr-chat').innerHTML = ''; table = null; setMsg($('tr-msg'), ''); }
  }

  $('tr-start').addEventListener('click', async () => {
    const msg = $('tr-pick-msg');
    if (busy) return;
    busy = true; $('tr-start').disabled = true; setMsg(msg, 'Setting up the meeting…');
    try {
      const r = await post({ type: 'tv_negotiation', action: 'start' });
      if (!r.ok) { setMsg(msg, friendly(r.error), 'err'); return; }
      setMsg(msg, '');
      openTable(true);
      $('tr-ask').value = ''; $('tr-pitch').value = '';
      buildClauseOptions(r.session.opening_clause);
      bubble('rep', r.reply);
      showSession(r.session);
    } catch (e) {
      setMsg(msg, 'Could not reach the league server. Please try again.', 'err');
    } finally { busy = false; $('tr-start').disabled = false; }
  });

  $('tr-send').addEventListener('click', async () => {
    if (busy || !table) return;
    const ask = Number($('tr-ask').value), pitch = $('tr-pitch').value.trim(), clauseAsk = $('tr-clause-ask').value;
    if (!(ask > 0)) return setMsg($('tr-msg'), 'Enter the yearly rate you are asking for.', 'err');
    if (pitch.length < 15) return setMsg($('tr-msg'), 'Write your pitch first: why should the network pay that?', 'err');
    if (ask < table.opening_offer && !confirm('Your ask of ' + money(ask) + ' is BELOW the opening offer of ' + money(table.opening_offer) + '. You could simply sign the opening offer instead. Send this lower ask anyway?')) return;
    busy = true; $('tr-send').disabled = true; setMsg($('tr-msg'), '');
    bubble('owner', 'Ask: ' + money(ask) + (clauseAsk !== 'keep' ? ' · clause: ' + $('tr-clause-ask').selectedOptions[0].text.toLowerCase() : '') + '\n' + pitch);
    const wait = bubble('rep', 'The rep is considering your offer…', 'wait');
    try {
      const r = await post({ type: 'tv_negotiation', action: 'offer', ask, pitch, clause_target: clauseAsk === 'keep' ? '' : clauseAsk });
      wait.remove();
      if (!r.ok) { setMsg($('tr-msg'), friendly(r.error), 'err'); return; }
      bubble('rep', r.reply);
      showSession(r.session);
      $('tr-pitch').value = '';
      if (r.decision === 'walk') setMsg($('tr-msg'), 'The network walked away for today. Come back tomorrow.', 'err');
      if (r.decision === 'agree') setMsg($('tr-msg'), 'The rep agreed to your number. Sign it to make it official.', 'ok');
    } catch (e) {
      wait.remove(); setMsg($('tr-msg'), 'Lost the connection to the league server. Try that offer again.', 'err');
    } finally { busy = false; $('tr-send').disabled = false; }
  });

  $('tr-accept').addEventListener('click', async () => {
    if (busy || !table) return;
    if (!confirm('Sign your Local TV Deal for ' + money(table.offer) + ' per season with ' + clauseText(table.clause) + '? This is final, one time only.')) return;
    busy = true; $('tr-accept').disabled = true;
    try {
      const r = await post({ type: 'tv_negotiation', action: 'accept' });
      if (!r.ok) { setMsg($('tr-msg'), friendly(r.error), 'err'); $('tr-accept').disabled = false; return; }
      openTable(false);
      $('tr-pick').hidden = true; $('tr-s-deal').textContent = 'Signed';
      setMsg($('tr-done'), `Signed: ${money(r.final_revenue)} per season, ${clauseText(r.final_clause)}. The money posts on TV Revenue Day, together with your national TV money.`, 'ok');
    } catch (e) {
      setMsg($('tr-msg'), 'Could not reach the league server. Check the TV Rights page before trying again.', 'err');
      $('tr-accept').disabled = false;
    } finally { busy = false; }
  });

  $('tr-leave').addEventListener('click', async () => {
    if (busy || !table) return;
    openTable(false);
    try { await post({ type: 'tv_negotiation', action: 'leave' }); } catch (e) { /* nothing to undo */ }
  });
})();
