// AI Sponsor Rep (negotiate/index.html). Sign-in reuses the coach_chat
// hello (PIN check + team snapshot); the negotiation itself is type
// "sponsor_negotiation" with action start / offer / accept / leave. Every
// offer amount comes back from backend.gs -- this page never computes one.
// Top-level names are ng-prefixed.
(function () {
  const $ = id => document.getElementById(id);
  const money = n => '$' + Math.round(Number(n)).toLocaleString('en-US');
  const ordinal = n => n + ({ 1: 'st', 2: 'nd', 3: 'rd' }[(n % 100 > 10 && n % 100 < 14) ? 0 : n % 10] || 'th');
  const teamSel = $('ng-team'), pinIn = $('ng-pin');
  const catSel = $('ng-cat'), brandSel = $('ng-brand');
  let session = null, table = null, busy = false, catalog = { slots: {}, deals: [] };

  teamSel.innerHTML = '<option value="">Select your team</option>' +
    NG_TEAMS.map(t => `<option value="${t.id}">${esc(t.name)}${t.owner ? ' (' + esc(t.owner) + ')' : ''}</option>`).join('');

  function esc(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function setMsg(el, text, kind) { el.textContent = text || ''; el.className = 'msg' + (kind ? ' ' + kind : ''); }

  async function post(body) {
    const res = await fetch(BACKEND_URL, {
      method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' },
      body: JSON.stringify(Object.assign({ team_id: session ? session.team_id : teamSel.value,
                                           pin: session ? session.pin : pinIn.value.trim() }, body)),
    });
    return res.json();
  }

  async function loadCatalog() {
    try {
      const res = await fetch(BACKEND_URL + '?catalog=1');
      const data = await res.json();
      const slots = {};
      (data.sponsor_catalog || []).forEach(b => { slots[b.name] = { qty: b.qty, clause: b.base_clause, taken: 0 }; });
      (data.sponsorship_deals || []).forEach(d => { if (slots[d.brand]) slots[d.brand].taken++; });
      catalog = { slots, deals: data.sponsorship_deals || [] };
    } catch (e) { /* the backend re-checks slots at every step anyway */ }
    renderDesk();
  }

  function myCategories() {
    return catalog.deals.filter(d => String(d.team_id) === String(session.team_id));
  }

  function renderDesk() {
    if (!session) return;
    const mine = myCategories();
    $('ng-s-cats').textContent = mine.length + ' / ' + NG_REQUIRED;
    $('ng-filled').textContent = mine.length ? 'Signed: ' + mine.map(d => d.brand + ' (' + d.category + ')').join(', ') : 'No sponsors signed yet.';
    const done = new Set(mine.map(d => d.category));
    const cats = [...new Set(NG_BRANDS.map(b => b.category))];
    const keep = catSel.value;
    catSel.innerHTML = cats.map(c => `<option value="${esc(c)}"${done.has(c) ? ' disabled' : ''}>${esc(c)}${done.has(c) ? ' (signed)' : ''}</option>`).join('');
    const firstOpen = cats.find(c => !done.has(c));
    catSel.value = keep && !done.has(keep) ? keep : (firstOpen || cats[0]);
    renderBrands();
  }

  function renderBrands() {
    const keep = brandSel.value;
    const list = NG_BRANDS.filter(b => b.category === catSel.value);
    brandSel.innerHTML = list.map(b => {
      const s = catalog.slots[b.name];
      const open = s ? s.qty - s.taken : null;
      const locked = b.min_leverage && session.leverage != null && session.leverage < b.min_leverage;
      const label = (s ? `${b.name} (${s.clause} clause, ${Math.max(0, open)}/${s.qty} open)` : b.name) +
        (b.min_leverage ? ` · leverage ${b.min_leverage}+` : '');
      return `<option value="${esc(b.name)}"${open === 0 || locked ? ' disabled' : ''}>${esc(label)}</option>`;
    }).join('');
    const enabled = [...brandSel.options].filter(o => !o.disabled).map(o => o.value);
    brandSel.value = enabled.includes(keep) ? keep : (enabled[0] || '');
    showFlavor();
  }

  function showFlavor() {
    const b = NG_BRANDS.find(x => x.name === brandSel.value);
    $('ng-flavor').textContent = b && b.flavor ? b.flavor : '';
  }

  catSel.addEventListener('change', renderBrands);
  brandSel.addEventListener('change', showFlavor);

  $('ng-signin-btn').addEventListener('click', async () => {
    const msg = $('ng-signin-msg');
    if (!teamSel.value || !pinIn.value.trim()) return setMsg(msg, 'Choose your team and enter your PIN.', 'err');
    $('ng-signin-btn').disabled = true; setMsg(msg, 'Checking…');
    try {
      const r = await post({ type: 'coach_chat', hello: true });
      if (!r.ok) { setMsg(msg, r.error, 'err'); $('ng-signin-btn').disabled = false; return; }
      session = { team_id: teamSel.value, pin: pinIn.value.trim(), leverage: r.leverage };
      $('ng-s-name').textContent = r.team_name;
      $('ng-s-pos').textContent = ordinal(r.position) + ' of ' + NG_TEAMS.length;
      $('ng-s-lev').textContent = r.leverage != null ? r.leverage + ' / 100' : 'see Rulebook 11';
      $('ng-signin').hidden = true; $('ng-desk').hidden = false;
      await loadCatalog();
    } catch (e) {
      setMsg(msg, 'Could not reach the league server. Please try again.', 'err'); $('ng-signin-btn').disabled = false;
    }
  });
  pinIn.addEventListener('keydown', e => { if (e.key === 'Enter') $('ng-signin-btn').click(); });

  function bubble(role, text, extra) {
    const el = document.createElement('div');
    el.className = 'bubble ' + role + (extra ? ' ' + extra : '');
    if (role === 'rep') el.dataset.who = table ? table.brand + ' rep' : 'Rep';
    el.textContent = text;
    $('ng-chat').appendChild(el);
    $('ng-chat').scrollTop = $('ng-chat').scrollHeight;
    return el;
  }

  function showSession(s) {
    table = s;
    $('ng-offer').textContent = money(s.offer);
    $('ng-clause').textContent = s.clause;
    $('ng-left').textContent = s.status === 'final' ? 'final offer' : s.status === 'agreed' ? 'agreed' : s.turns_left + ' offers left';
    const closed = s.status === 'walked';
    $('ng-accept').disabled = closed;
    $('ng-accept').textContent = 'Sign for ' + money(s.offer);
    $('ng-composer').hidden = closed || s.status === 'final' || s.status === 'agreed';
  }

  function openTable(on) {
    $('ng-table').hidden = !on; $('ng-pick').hidden = on;
    if (!on) { $('ng-chat').innerHTML = ''; table = null; setMsg($('ng-msg'), ''); }
  }

  $('ng-start').addEventListener('click', async () => {
    const msg = $('ng-pick-msg');
    if (!brandSel.value || busy) return;
    busy = true; $('ng-start').disabled = true; setMsg(msg, 'Setting up the meeting…');
    try {
      const r = await post({ type: 'sponsor_negotiation', action: 'start', brand: brandSel.value });
      if (!r.ok) { setMsg(msg, r.error, 'err'); return; }
      setMsg(msg, '');
      openTable(true);
      table = r.session;
      $('ng-table-title').textContent = r.session.brand + ' · ' + r.session.category;
      $('ng-ask').value = ''; $('ng-pitch').value = ''; $('ng-clause-ask').value = 'keep';
      bubble('rep', r.reply);
      showSession(r.session);
    } catch (e) {
      setMsg(msg, 'Could not reach the league server. Please try again.', 'err');
    } finally { busy = false; $('ng-start').disabled = false; }
  });

  $('ng-send').addEventListener('click', async () => {
    if (busy || !table) return;
    const ask = Number($('ng-ask').value), pitch = $('ng-pitch').value.trim(), clauseAsk = $('ng-clause-ask').value;
    if (!(ask > 0)) return setMsg($('ng-msg'), 'Enter the yearly revenue you are asking for.', 'err');
    if (pitch.length < 15) return setMsg($('ng-msg'), 'Write your pitch first: why should ' + table.brand + ' pay that?', 'err');
    if (ask < table.opening_offer && !confirm('Your ask of ' + money(ask) + ' is BELOW the opening offer of ' + money(table.opening_offer) + '. You could simply sign the opening offer instead. Send this lower ask anyway?')) return;
    busy = true; $('ng-send').disabled = true; setMsg($('ng-msg'), '');
    bubble('owner', 'Ask: ' + money(ask) + (clauseAsk !== 'keep' ? ' · clause: ' + $('ng-clause-ask').selectedOptions[0].text.toLowerCase() : '') + '\n' + pitch);
    const wait = bubble('rep', 'The rep is considering your offer…', 'wait');
    try {
      const r = await post({ type: 'sponsor_negotiation', action: 'offer', brand: table.brand, ask, pitch, clause_ask: clauseAsk });
      wait.remove();
      if (!r.ok) { setMsg($('ng-msg'), r.error, 'err'); return; }
      bubble('rep', r.reply);
      showSession(r.session);
      $('ng-pitch').value = '';
      if (r.decision === 'walk') setMsg($('ng-msg'), table.brand + ' walked away. Leave the table and try another brand in this category.', 'err');
      if (r.decision === 'agree') setMsg($('ng-msg'), 'The rep agreed to your number. Sign it to make it official.', 'ok');
    } catch (e) {
      wait.remove(); setMsg($('ng-msg'), 'Lost the connection to the league server. Try that offer again.', 'err');
    } finally { busy = false; $('ng-send').disabled = false; }
  });

  $('ng-accept').addEventListener('click', async () => {
    if (busy || !table) return;
    if (!confirm('Sign ' + table.brand + ' for ' + money(table.offer) + ' per season with a ' + table.clause + ' clause? This is final.')) return;
    busy = true; $('ng-accept').disabled = true;
    try {
      const r = await post({ type: 'sponsor_negotiation', action: 'accept', brand: table.brand });
      if (!r.ok) { setMsg($('ng-msg'), r.error, 'err'); $('ng-accept').disabled = false; return; }
      openTable(false);
      setMsg($('ng-pick-msg'), `Signed: ${r.brand} (${r.category}), ${money(r.final_revenue)} per season, ${r.final_clause} clause` +
        (r.vs_opening ? ` (${r.vs_opening > 0 ? '+' : '−'}${money(Math.abs(r.vs_opening))} vs. the opening offer).` : '.') +
        (r.league_update === 'ok' ? ' Team Progress and your budget update in about 3 minutes.' : ' It reaches your budget on the next league update.'), 'ok');
      await loadCatalog();
    } catch (e) {
      setMsg($('ng-msg'), 'Could not reach the league server. Check the Sponsorship Marketplace before trying again.', 'err');
      $('ng-accept').disabled = false;
    } finally { busy = false; }
  });

  $('ng-leave').addEventListener('click', async () => {
    if (busy || !table) return;
    const brand = table.brand;
    openTable(false);
    try { await post({ type: 'sponsor_negotiation', action: 'leave', brand }); } catch (e) { /* nothing to undo */ }
    loadCatalog();
  });
})();
