// AI Coach chat (coach/index.html). Sign-in sends a "coach_chat" hello to
// backend.gs, which checks the PIN and returns the team snapshot; every
// question then goes to the same type with the recent history. The model
// call and the team briefing both live server-side. Top-level names are
// co-prefixed so this file can't collide with assets/submissions.js.
(function () {
  const $ = id => document.getElementById(id);
  const money = n => '$' + Number(n).toLocaleString('en-US');
  const ordinal = n => n + ({ 1: 'st', 2: 'nd', 3: 'rd' }[(n % 100 > 10 && n % 100 < 14) ? 0 : n % 10] || 'th');
  const teamSel = $('co-team'), pinIn = $('co-pin'), startBtn = $('co-start'), signMsg = $('co-signin-msg');
  const chat = $('co-chat'), input = $('co-input'), sendBtn = $('co-send');
  let session = null, history = [], busy = false;

  teamSel.innerHTML = '<option value="">Select your team</option>' +
    CO_TEAMS.map(t => `<option value="${t.id}">${t.name}${t.owner ? ' (' + t.owner + ')' : ''}</option>`).join('');

  function esc(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // small markdown subset: **bold**, *italic*, "- " / "* " bullets, paragraphs
  function format(text) {
    const inline = s => esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<i>$2</i>');
    let out = '', list = false;
    text.split('\n').forEach(line => {
      const m = line.match(/^\s*[-*•]\s+(.*)$/);
      if (m) {
        if (!list) { out += '<ul>'; list = true; }
        out += '<li>' + inline(m[1]) + '</li>';
      } else {
        if (list) { out += '</ul>'; list = false; }
        if (line.trim()) out += '<p>' + inline(line) + '</p>';
      }
    });
    return out + (list ? '</ul>' : '');
  }

  function bubble(role, text, extra) {
    const el = document.createElement('div');
    el.className = 'bubble ' + role + (extra ? ' ' + extra : '');
    el.innerHTML = role === 'coach' ? format(text) : esc(text);
    chat.appendChild(el);
    chat.scrollTop = chat.scrollHeight;
    return el;
  }

  async function post(body) {
    const res = await fetch(BACKEND_URL, {
      method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' },
      body: JSON.stringify(Object.assign({ type: 'coach_chat', team_id: session ? session.team_id : teamSel.value,
                                           pin: session ? session.pin : pinIn.value.trim() }, body)),
    });
    return res.json();
  }

  function friendly(err) {
    if (/unknown submission type/i.test(err || '')) return 'The AI Coach isn\'t switched on yet. Your instructor still needs to connect it.';
    return err;
  }

  startBtn.addEventListener('click', async () => {
    if (!teamSel.value || !pinIn.value.trim()) { signMsg.textContent = 'Choose your team and enter your PIN.'; signMsg.className = 'co-msg err'; return; }
    startBtn.disabled = true; signMsg.textContent = 'Checking…'; signMsg.className = 'co-msg';
    try {
      const r = await post({ hello: true });
      if (!r.ok) { signMsg.textContent = friendly(r.error); signMsg.className = 'co-msg err'; startBtn.disabled = false; return; }
      session = { team_id: teamSel.value, pin: pinIn.value.trim() };
      $('co-s-name').textContent = r.team_name;
      $('co-s-pos').textContent = r.position + ' / ' + CO_TEAMS.length;
      $('co-s-rec').textContent = r.record + ' · ' + r.points + ' pts';
      $('co-s-cash').textContent = money(r.cash);
      $('co-s-next').textContent = 'Next: ' + r.next;
      $('co-signin').hidden = true; $('co-session').hidden = false;
      bubble('coach', `Hi, owner of **${r.team_name}**. I've got your numbers in front of me: you're ${ordinal(r.position)} with ${r.points} points and ${money(r.cash)} in cash. Ask me how your team is performing, what's behind your results, or how to approach your next match. What do you want to work on?`);
      input.focus();
    } catch (e) {
      signMsg.textContent = 'Could not reach the league server. Please try again.'; signMsg.className = 'co-msg err';
      startBtn.disabled = false;
    }
  });
  pinIn.addEventListener('keydown', e => { if (e.key === 'Enter') startBtn.click(); });

  async function send(text) {
    text = (text || '').trim();
    if (!text || busy || !session) return;
    busy = true; sendBtn.disabled = true; input.value = '';
    bubble('user', text);
    const wait = bubble('coach', 'Thinking…', 'thinking');
    try {
      // free-tier Gemini allows only so many answers a minute across the
      // whole class; when the backend says the model was busy, wait and
      // retry quietly (twice) instead of making the student resend
      let r = await post({ message: text, history });
      for (let tries = 0; r.ok && r.retry && tries < 2; tries++) {
        wait.textContent = 'Lots of teams are asking right now. Your coach will answer in a few seconds…';
        await new Promise(res => setTimeout(res, 20000));
        r = await post({ message: text, history });
      }
      wait.remove();
      if (r.ok) {
        bubble('coach', r.reply);
        if (!r.fallback) history.push({ role: 'user', text }, { role: 'coach', text: r.reply });
        history = history.slice(-10);
      } else {
        bubble('coach', friendly(r.error));
      }
    } catch (e) {
      wait.remove();
      bubble('coach', 'I lost the connection to the league server. Try that again.');
    }
    busy = false; sendBtn.disabled = false; input.focus();
  }

  sendBtn.addEventListener('click', () => send(input.value));
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input.value); } });
  document.querySelectorAll('.co-chip').forEach(c => c.addEventListener('click', () => send(c.textContent)));
})();
