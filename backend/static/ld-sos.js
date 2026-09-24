/* =========================================================================
   LOHA DRISHTI - SOS
   Raised from any dashboard, shown on every dashboard. The state lives on the
   server (/api/ops/sos); every page polls it, so an SOS raised by a
   Procurement Officer appears on the Admin's and the Analyst's screens within
   one poll interval, and an acknowledgement or resolution travels back the
   same way. Self-contained (own styles) so the ML and verification pages can
   load it without the dashboard stylesheets.
   ========================================================================= */
(function(){
  'use strict';
  const POLL_MS = 8000;
  const S = {me:null, active:[], categories:[], seen:new Set(), timer:0, stopped:false, audio:null, titleTimer:0, baseTitle:document.title};
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const ago = iso => {
    const s = Math.max(0, (Date.now() - Date.parse(iso)) / 1000);
    return s < 60 ? 'just now' : s < 3600 ? Math.floor(s / 60) + ' min ago' : Math.floor(s / 3600) + ' h ago';
  };
  try { JSON.parse(localStorage.getItem('ld-sos-seen') || '[]').forEach(id => S.seen.add(id)); } catch(e){}

  async function call(path, opts){
    const res = await fetch(path, Object.assign({credentials:'same-origin', headers:{'Content-Type':'application/json'}}, opts || {}));
    if(res.status === 401){ S.stopped = true; throw new Error('signed out'); }
    if(!res.ok){ let d = res.statusText; try { d = (await res.json()).detail || d; } catch(e){} throw new Error(d); }
    return res.json();
  }

  /* ------------------------------------------------------------ styles */
  const css = `
  .sos-fab{position:fixed;left:18px;bottom:18px;z-index:9000;width:58px;height:58px;border-radius:50%;border:0;cursor:pointer;
    font:800 15px/1 "Nunito Sans",system-ui,sans-serif;letter-spacing:.06em;color:#fff;background:radial-gradient(circle at 35% 30%,#ff6b6b,#d7192b 60%,#a50d1c);
    box-shadow:0 10px 26px -8px rgba(215,25,43,.8),0 0 0 4px rgba(255,255,255,.9);}
  .sos-fab:hover{transform:scale(1.05);}
  .sos-fab.live{animation:sosPulse 1.2s ease-in-out infinite;}
  @keyframes sosPulse{0%,100%{box-shadow:0 0 0 4px rgba(255,255,255,.9),0 0 0 0 rgba(215,25,43,.7);}50%{box-shadow:0 0 0 4px rgba(255,255,255,.9),0 0 0 18px rgba(215,25,43,0);}}
  .sos-bar{position:fixed;top:0;left:0;right:0;z-index:8999;display:none;flex-direction:column;gap:6px;padding:10px 18px;
    background:linear-gradient(90deg,#8e0a17,#c8102e 45%,#8e0a17);color:#fff;font:14px/1.45 "Nunito Sans",system-ui,sans-serif;
    box-shadow:0 8px 24px -8px rgba(0,0,0,.5);}
  .sos-bar.on{display:flex;}
  body.sos-live{padding-top:var(--sos-h,0px);}
  /* Fixed-position chrome does not move with the page padding; shift it by the banner. */
  body.sos-live .sidenav{top:calc(var(--header-h,58px) + 14px + var(--sos-h,0px));max-height:calc(100vh - var(--header-h,58px) - 28px - var(--sos-h,0px));}
  @media(max-width:640px){body.sos-live .sidenav{top:auto;}}
  .sos-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap;}
  .sos-tag{font-weight:800;letter-spacing:.14em;padding:3px 9px;border-radius:4px;background:#fff;color:#c8102e;font-size:12px;animation:sosBlink 1s steps(2) infinite;}
  @keyframes sosBlink{50%{opacity:.35;}}
  .sos-txt{flex:1 1 380px;min-width:0;}
  .sos-txt b{font-weight:800;}
  .sos-meta{font-size:12px;opacity:.9;}
  .sos-btn{border:1px solid rgba(255,255,255,.75);background:rgba(255,255,255,.12);color:#fff;border-radius:6px;padding:6px 12px;
    font:700 12.5px "Nunito Sans",system-ui,sans-serif;cursor:pointer;white-space:nowrap;}
  .sos-btn:hover{background:rgba(255,255,255,.25);}
  .sos-btn.solid{background:#fff;color:#c8102e;border-color:#fff;}
  .sos-btn[disabled]{opacity:.6;cursor:default;}
  .sos-more{font-size:12px;opacity:.9;}
  .sos-modal-bg{position:fixed;inset:0;z-index:9100;background:rgba(5,12,20,.6);backdrop-filter:blur(4px);display:none;align-items:center;justify-content:center;padding:16px;}
  .sos-modal-bg.on{display:flex;}
  .sos-modal{width:min(520px,100%);background:var(--ld-overlay,#fff);color:var(--ld-text,#0a2540);border-radius:14px;border:2px solid #c8102e;
    box-shadow:0 30px 70px -20px rgba(0,0,0,.6);font:14px/1.5 "Nunito Sans",system-ui,sans-serif;overflow:hidden;}
  .sos-modal h3{margin:0;padding:16px 20px;background:#c8102e;color:#fff;font:800 18px "Nunito Sans",system-ui,sans-serif;letter-spacing:.02em;}
  .sos-modal form{display:flex;flex-direction:column;gap:12px;padding:18px 20px 20px;}
  .sos-modal label{display:flex;flex-direction:column;gap:5px;font-size:11px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--ld-mute,#5f7a92);}
  .sos-modal select,.sos-modal input,.sos-modal textarea{font:500 14px "Nunito Sans",system-ui,sans-serif;letter-spacing:0;text-transform:none;padding:9px 11px;
    border:1px solid var(--ld-hair-strong,#c9d6e2);border-radius:8px;background:var(--ld-input,#fff);color:var(--ld-text,#0a2540);}
  .sos-modal textarea{min-height:84px;resize:vertical;}
  .sos-note{font-size:12px;color:var(--ld-mute,#5f7a92);}
  .sos-actions{display:flex;gap:10px;justify-content:flex-end;}
  .sos-actions button{padding:10px 18px;border-radius:8px;font:800 13.5px "Nunito Sans",system-ui,sans-serif;cursor:pointer;border:1px solid var(--ld-hair-strong,#c9d6e2);background:transparent;color:var(--ld-text,#0a2540);}
  .sos-actions .go{background:#c8102e;border-color:#c8102e;color:#fff;}
  .sos-err{color:#c8102e;font-size:12.5px;min-height:1em;}
  @media(max-width:640px){.sos-fab{bottom:86px;left:12px;width:52px;height:52px;font-size:13px;}}
  @media(prefers-reduced-motion:reduce){.sos-fab.live,.sos-tag{animation:none;}}`;
  const style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  /* ------------------------------------------------------------- markup */
  const bar = document.createElement('div');
  bar.className = 'sos-bar'; bar.setAttribute('role', 'alert'); bar.setAttribute('aria-live', 'assertive');
  const fab = document.createElement('button');
  fab.className = 'sos-fab'; fab.type = 'button'; fab.textContent = 'SOS'; fab.title = 'Raise an SOS - every dashboard is alerted';
  const modal = document.createElement('div');
  modal.className = 'sos-modal-bg';
  modal.innerHTML = `<div class="sos-modal" role="dialog" aria-modal="true" aria-labelledby="sosTitle">
    <h3 id="sosTitle">Raise SOS</h3>
    <form id="sosForm">
      <label>Type of emergency<select name="category" id="sosCat"></select></label>
      <label>What is happening<textarea name="message" required minlength="3" maxlength="300" placeholder="e.g. MV Coastal Star lost propulsion 12 nm off Paradip, drifting towards shoal"></textarea></label>
      <label>Vessel / port / location<input name="location" maxlength="120" placeholder="e.g. Paradip outer anchorage"></label>
      <p class="sos-note">Every signed-in dashboard - Admin, Analyst and Procurement Officer - sees this immediately with an alarm. For danger to life at sea, also call the Indian Coast Guard on <b>1554</b>.</p>
      <div class="sos-err" id="sosErr"></div>
      <div class="sos-actions"><button type="button" id="sosCancel">Cancel</button><button type="submit" class="go">Send SOS to all dashboards</button></div>
    </form></div>`;
  document.body.append(bar, fab, modal);

  function openModal(){
    const sel = modal.querySelector('#sosCat');
    sel.innerHTML = (S.categories.length ? S.categories : ['Vessel incident', 'Port closure', 'Cargo emergency', 'Medical', 'Security', 'Weather', 'Other'])
      .map(c => `<option>${esc(c)}</option>`).join('');
    modal.querySelector('#sosErr').textContent = '';
    modal.classList.add('on');
    setTimeout(() => modal.querySelector('textarea').focus(), 50);
    primeAudio();
  }
  window.ldOpenSos = openModal;
  fab.addEventListener('click', openModal);
  modal.querySelector('#sosCancel').addEventListener('click', () => modal.classList.remove('on'));
  modal.addEventListener('click', e => { if(e.target === modal) modal.classList.remove('on'); });
  document.addEventListener('keydown', e => { if(e.key === 'Escape') modal.classList.remove('on'); });
  modal.querySelector('#sosForm').addEventListener('submit', async e => {
    e.preventDefault();
    const f = new FormData(e.target), btn = e.target.querySelector('.go');
    btn.disabled = true;
    try{
      const item = await call('/api/ops/sos', {method:'POST', body: JSON.stringify(
        {category: f.get('category'), message: String(f.get('message') || ''), location: String(f.get('location') || '')})});
      markSeen(item.id);               // the sender does not need the alarm
      e.target.reset();
      modal.classList.remove('on');
      if('Notification' in window && Notification.permission === 'default') Notification.requestPermission();
      poll();
    }catch(err){ modal.querySelector('#sosErr').textContent = 'Could not send: ' + err.message; }
    finally{ btn.disabled = false; }
  });

  /* ----------------------------------------------------------- alarm */
  function primeAudio(){
    try { S.audio = S.audio || new (window.AudioContext || window.webkitAudioContext)(); if(S.audio.state === 'suspended') S.audio.resume(); } catch(e){}
  }
  document.addEventListener('pointerdown', primeAudio, {once:true});
  function alarm(){
    try{
      primeAudio();
      const ctx = S.audio; if(!ctx) return;
      [0, .35, .7].forEach(t => {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.type = 'square'; o.frequency.setValueAtTime(880, ctx.currentTime + t); o.frequency.setValueAtTime(660, ctx.currentTime + t + .15);
        g.gain.setValueAtTime(.0001, ctx.currentTime + t); g.gain.exponentialRampToValueAtTime(.18, ctx.currentTime + t + .02);
        g.gain.exponentialRampToValueAtTime(.0001, ctx.currentTime + t + .3);
        o.connect(g).connect(ctx.destination); o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + .32);
      });
    }catch(e){}
  }
  function markSeen(id){
    S.seen.add(id);
    try { localStorage.setItem('ld-sos-seen', JSON.stringify([...S.seen].slice(-100))); } catch(e){}
  }
  function flashTitle(on){
    clearInterval(S.titleTimer);
    if(!on){ document.title = S.baseTitle; return; }
    let t = false;
    S.titleTimer = setInterval(() => { t = !t; document.title = t ? '🚨 SOS - LOHA DRISHTI' : S.baseTitle; }, 1000);
  }

  /* ----------------------------------------------------------- banner */
  function render(){
    const a = S.active;
    fab.classList.toggle('live', a.length > 0);
    const emergencyBtn = document.getElementById('openEmergencyBtn');
    if(emergencyBtn) emergencyBtn.classList.toggle('sos-on', a.length > 0);
    if(!a.length){
      bar.classList.remove('on'); document.body.classList.remove('sos-live'); flashTitle(false);
      return;
    }
    const top = a[0], me = S.me || {};
    const acked = top.acks.some(k => k.email === me.email) || top.raised_by.email === me.email;
    const canResolve = me.role === 'Admin' || top.raised_by.email === me.email;
    const ackNames = top.acks.map(k => `${esc(k.name || k.email)} (${esc(k.role)})`).join(', ');
    bar.innerHTML = `<div class="sos-row">
        <span class="sos-tag">SOS${a.length > 1 ? ' ×' + a.length : ''}</span>
        <div class="sos-txt"><b>${esc(top.category)}:</b> ${esc(top.message)}${top.location ? ` · <b>${esc(top.location)}</b>` : ''}
          <div class="sos-meta">Raised by ${esc(top.raised_by.name || top.raised_by.email)} (${esc(top.raised_by.role)}) · ${ago(top.raised_at)}
            · ${top.acks.length ? 'Acknowledged by ' + ackNames : 'Not yet acknowledged'}</div></div>
        ${acked ? '' : `<button class="sos-btn solid" data-ack="${esc(top.id)}">Acknowledge</button>`}
        ${canResolve ? `<button class="sos-btn" data-resolve="${esc(top.id)}">Resolve</button>` : ''}
        <button class="sos-btn" data-contacts>Emergency contacts</button>
      </div>
      ${a.length > 1 ? `<div class="sos-more">${a.slice(1).map(x => `+ ${esc(x.category)}: ${esc(x.message)} (${esc(x.raised_by.role)}, ${ago(x.raised_at)})`).join('<br>')}</div>` : ''}`;
    bar.classList.add('on');
    document.body.classList.add('sos-live');
    document.body.style.setProperty('--sos-h', bar.offsetHeight + 'px');
    bar.querySelectorAll('[data-ack]').forEach(b => b.onclick = async () => {
      b.disabled = true; try { await call(`/api/ops/sos/${b.dataset.ack}/ack`, {method:'POST'}); } catch(e){ alert(e.message); } poll();
    });
    bar.querySelectorAll('[data-resolve]').forEach(b => b.onclick = async () => {
      const note = prompt('Resolution note (what was done):', '');
      if(note === null) return;
      b.disabled = true; try { await call(`/api/ops/sos/${b.dataset.resolve}/resolve`, {method:'POST', body: JSON.stringify({note})}); } catch(e){ alert(e.message); } poll();
    });
    bar.querySelectorAll('[data-contacts]').forEach(b => b.onclick = () => {
      const btn = document.getElementById('openEmergencyBtn');
      if(btn) btn.click(); else window.location.href = '/app';
    });
  }

  function announce(fresh){
    if(!fresh.length) return;
    alarm();
    flashTitle(true);
    if('Notification' in window && Notification.permission === 'granted'){
      fresh.forEach(x => { try { new Notification(`SOS - ${x.category}`, {body: `${x.message}\nRaised by ${x.raised_by.name || x.raised_by.email} (${x.raised_by.role})`, tag: 'sos-' + x.id, requireInteraction: true}); } catch(e){} });
    }
  }

  /* ------------------------------------------------------------ polling */
  async function poll(){
    if(S.stopped) return;
    try{
      const d = await call('/api/ops/sos');
      S.categories = d.categories || S.categories;
      const fresh = d.active.filter(x => !S.seen.has(x.id));
      S.active = d.active;
      fresh.forEach(x => markSeen(x.id));
      render();
      announce(fresh);
    }catch(e){ /* offline or signed out: keep the last known state */ }
  }
  function schedule(){ clearInterval(S.timer); S.timer = setInterval(poll, POLL_MS); }
  document.addEventListener('visibilitychange', () => { if(!document.hidden){ poll(); flashTitle(false); } });
  window.addEventListener('focus', () => flashTitle(false));

  (async function start(){
    try { S.me = await call('/api/auth/me'); } catch(e){ if(S.stopped){ fab.remove(); return; } }
    poll();
    schedule();
  })();
})();
