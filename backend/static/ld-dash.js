/* =========================================================================
   LOHA DRISHTI - DASHBOARDS
   The design handoff's three dashboards, bound to the real decision engine:

     Command Centre      a live decision surface - pick any berth on the chart,
                         any vessel class, or any ranked option, and the panel,
                         tiles and cost build-up show that pairing's engine
                         figures.
     Freight Intelligence twelve-month P50/P10-P90 horizon per lane from the
                         trained model, a timing signal and a lane table.
     Execution Brief     the recommendation in one sentence, its alerts and the
                         discharge berth's profile.

   Nothing here computes a cost, a rate or a risk score. Every figure is read
   from the engine's options (activeResult.candidates) or the model's forecast
   curve; the design prototype's own calculator was not carried over. The only
   local rule is which pairings the engine left out and why, read from the
   port and fleet reference tables.

   Loaded after app.html's scripts. It hooks renderDecisionCard, refreshAlerts,
   renderFreightOriginTable and switchPanel by wrapping them, so the engine
   code paths are untouched.
   ========================================================================= */
(function(){
  'use strict';

  /* ---------------------------------------------------------------- data */
  // Schematic chart positions (design handoff), keyed by UN/LOCODE.
  const PIN = {
    INHAL:[186,74,196,66],  INSAG:[206,92,218,96],  INDHM:[248,140,260,136],
    INPRT:[274,171,288,174], INGOP:[302,212,314,216], INGGV:[330,248,342,244],
    INVTZ:[352,270,364,282]
  };
  const ORIGIN_AT = {australia:[700,304], indonesia:[706,130], south_africa:[560,336], usa:[560,336]};
  const INR_PER_USD = 83.5;
  const UKC_M = 0.6, MAX_LIGHTER_GAP_M = 4.0;

  const PARTS = [
    ['fob','Cargo FOB price'], ['freight','Ocean freight'], ['vesselHire','Vessel hire'],
    ['deadfreight','Deadfreight'], ['lightering','Lightering'], ['loadPortCharge','Load port charges'],
    ['dischargePortCharge','Discharge port charges'], ['demurrageExpected','Demurrage risk'],
    ['insurance','Marine & war risk insurance'], ['evac','Inland rail evacuation'],
    ['financing','Working capital financing']
  ];
  const GROUPS = [
    ['Commodity (FOB)',  ['fob'],                                            'var(--navy-surface)'],
    ['Ocean leg',        ['freight','vesselHire','deadfreight','lightering'], 'var(--ld-accent)'],
    ['Port & delay',     ['loadPortCharge','dischargePortCharge','demurrageExpected'], 'var(--ld-warn)'],
    ['Inland & finance', ['insurance','evac','financing'],                   'var(--ld-mute)']
  ];
  const RISK = [
    ['Congestion','congestion_score'], ['Seasonal','monsoon_risk_score'],
    ['Freight volatility','freight_volatility_score'], ['Under-keel','draft_risk_score']
  ];

  const money = n => '$' + (Math.round(n * 100) / 100).toFixed(2);
  const signed = n => (n >= 0 ? '+' : '−') + money(Math.abs(n)).slice(0);
  const esc = s => escapeHtml(String(s == null ? '' : s));
  const $ = id => document.getElementById(id);
  const monthName = (offset, style) => {
    const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() + offset);
    return d.toLocaleString('en-IN', style === 'long' ? {month:'long', year:'numeric'} : {month:'short'});
  };
  const portKeys = () => Object.keys(PORTS).filter(k => PIN[PORTS[k].code]);
  const classKeys = () => Object.keys(VESSEL_CLASSES);
  const riskColor = r => r < 40 ? 'var(--ld-pos)' : r < 65 ? 'var(--ld-warn)' : 'var(--ld-crit)';
  const riskBand = r => r < 40 ? 'Low' : r < 65 ? 'Moderate' : 'High';
  const role = () => { try { return (localStorage.getItem('ld_role') || '').toLowerCase(); } catch(e) { return ''; } };

  function blockedReason(portKey, classKey){
    const p = PORTS[portKey], v = VESSEL_CLASSES[classKey];
    const gap = v.draft - (p.draft - UKC_M);
    if(gap > MAX_LIGHTER_GAP_M){
      return `${p.name} carries ${p.draft.toFixed(1)} m; a laden ${v.name} draws ${v.draft.toFixed(1)} m plus ${UKC_M} m under-keel - beyond what lightering can bridge.`;
    }
    if(v.dwtMax > 150000 && p.loa < 300){
      return `${p.name} accepts ${p.loa} m LOA; a ${v.name} needs ${v.loa} m.`;
    }
    return `The engine returned no ${v.name} option at ${p.name} for this parcel.`;
  }

  /* =========================================================== COMMAND */
  const C = {result:null, inputs:null, port:null, cls:null, hover:null, expanded:false, costShown:0, raf:0, mounted:false, model:null, runAt:null};

  function laneOf(result){ return result && result.winner ? result.winner.originKey : null; }
  function laneOptions(result){
    const lane = laneOf(result);
    return result ? result.candidates.filter(c => c.originKey === lane) : [];
  }
  function optionFor(portKey, classKey){
    return laneOptions(C.result).find(c => c.portKey === portKey && c.vesselClassKey === classKey) || null;
  }

  function mountCommand(){
    if(C.mounted) return;
    const panel = $('panel-command');
    const section = $('decisionSection');
    if(!panel || !section) return;
    C.mounted = true;

    const host = document.createElement('div');
    host.id = 'ldCommand';
    host.innerHTML = `
      <section class="ldc-hero" aria-label="Live decision surface">
        <svg class="ldc-map" viewBox="-20 20 740 332" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Schematic chart of India's east coast berths">
          <defs><pattern id="ldcSea" width="46" height="46" patternUnits="userSpaceOnUse"><path d="M0 0H46M0 0V46" fill="none" stroke="var(--ld-map-grid)" stroke-width="1"/></pattern></defs>
          <rect x="-60" y="-120" width="1000" height="480" fill="url(#ldcSea)"/>
          <path d="M-60 -120 L92 -120 L120 0 L150 30 L186 74 L206 92 L248 140 L274 171 L302 212 L330 248 L352 270 L372 300 L380 360 L-60 360 Z" fill="var(--ld-map-land)" stroke="var(--ld-map-land-bd)" stroke-width="1.5"/>
          <text x="96" y="248" fill="var(--ld-map-label)" font-size="14" letter-spacing="3" opacity=".8">INDIA</text>
          <text x="470" y="90" fill="var(--ld-map-faint)" font-size="14" letter-spacing="3">BAY OF BENGAL</text>
          <g id="ldcRoute"></g>
          <g id="ldcPins"></g>
          <g id="ldcTip" pointer-events="none"></g>
        </svg>
        <div class="ldc-intro">
          <div class="ld-kicker">Live decision surface</div>
          <div class="ld-h1">Executive Command Centre</div>
          <p class="ld-lede">Select any berth on the chart, any vessel class or any ranked option below. Every figure is the decision engine's own result for that pairing.</p>
        </div>
        <div class="ldc-legend">
          <span><i style="width:16px;height:2px;background:var(--ld-ink)"></i>Selected route</span>
          <span><i style="width:8px;height:8px;border-radius:50%;background:var(--ld-ink)"></i>Selected berth</span>
          <span><i style="width:8px;height:8px;border-radius:50%;background:var(--ld-accent)"></i>Offered for this vessel</span>
          <span><i style="width:8px;height:8px;border-radius:50%;background:var(--ld-map-faint)"></i>Not offered</span>
          <span>Schematic, not to scale</span>
        </div>
        <aside class="ldc-panel" id="ldcPanel" aria-live="polite">
          <div class="ldc-panel-head"><span class="ldc-verdict" id="ldcVerdict">Decision engine</span><span style="display:inline-flex;align-items:center;gap:8px"><span class="ldc-rank" id="ldcRank"></span><button class="ldc-min" id="ldcMin" type="button" aria-expanded="true" aria-controls="ldcPanelBody" title="Minimise panel"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 12h12"/></svg></button></span></div>
          <div class="ldc-panel-body" id="ldcPanelBody">
            <div class="ldc-title" id="ldcTitle">Running the decision engine</div>
            <div class="ldc-meta" id="ldcMeta">Scoring every origin, berth and vessel class for the cargo on file.</div>
            <div id="ldcFigures">
              <div class="ldc-costrow">
                <div><div class="ld-label">Landed cost / MT</div><div class="ld-num ldc-cost" id="ldcCost">&mdash;</div></div>
                <div style="padding-bottom:6px"><div class="ld-label">Total</div><div class="ld-num" style="font-size:19px" id="ldcTotal">&mdash;</div></div>
              </div>
              <div class="ldc-riskrow">
                <svg class="ldc-ring" viewBox="0 0 120 120" aria-label="Risk index">
                  <circle cx="60" cy="60" r="46" fill="none" stroke="var(--ld-track)" stroke-width="10"/>
                  <circle class="arc" id="ldcArc" cx="60" cy="60" r="46" fill="none" stroke="var(--ld-pos)" stroke-width="10" stroke-linecap="round" stroke-dasharray="289" stroke-dashoffset="289" transform="rotate(-90 60 60)"/>
                  <text id="ldcRiskNum" x="60" y="70" text-anchor="middle" font-size="30" font-weight="700" fill="var(--ld-text)">&mdash;</text>
                </svg>
                <div style="min-width:0;flex:1 1 auto">
                  <div class="ld-label" id="ldcRiskBand">Risk</div>
                  <div class="ldc-bars">${RISK.map((r, i) => `<div class="ldc-bar"><span>${r[0]}</span><span class="t"><i id="ldcB${i}" style="width:0%"></i></span><b id="ldcBv${i}">&mdash;</b></div>`).join('')}</div>
                </div>
              </div>
            </div>
            <div class="ldc-why" id="ldcWhy" hidden></div>
          </div>
        </aside>
      </section>

      <div class="ld-wrap">
        <div class="ldc-classbar">
          <span class="ld-label">Vessel class</span>
          <div class="ldc-classes" id="ldcClasses"></div>
          <div class="right">
            <span class="ld-tag">Synthetic</span>
            <button class="ld-btn pri" type="button" id="ldcBest">Show recommended</button>
          </div>
        </div>

        <div class="ldc-tiles">
          <div class="ld-card ldc-tile"><div class="ld-label">Supply continuity</div><div class="ld-num" id="ldcCont">&mdash;</div>
            <div class="ld-track"><i id="ldcContBar" style="width:0%;background:var(--ld-accent)"></i></div><div class="ld-note" id="ldcContNote">&nbsp;</div></div>
          <div class="ld-card ldc-tile"><div class="ld-label">Confidence</div><div class="ld-num" id="ldcConf">&mdash;</div>
            <div class="ld-track"><i id="ldcConfBar" style="width:0%;background:var(--ld-pos)"></i></div><div class="ld-note">Recommendation confidence from the engine</div></div>
          <div class="ld-card ldc-tile"><div class="ld-label">Delta vs recommended</div><div class="ld-num" id="ldcDelta">&mdash;</div>
            <div class="ld-note" id="ldcDeltaNote" style="margin-top:10px">&nbsp;</div></div>
          <div class="ld-card ldc-tile"><div class="ld-label">Voyage cycle</div><div class="ld-num" id="ldcCycle">&mdash;</div>
            <div class="ldc-seg"><i id="ldcSegSea" style="flex:1;background:var(--ld-accent)"></i><i id="ldcSegWait" style="flex:1;background:var(--ld-accent);opacity:.58"></i><i id="ldcSegDis" style="flex:1;background:var(--ld-accent);opacity:.3"></i></div>
            <div class="ld-note" id="ldcCycleNote">&nbsp;</div></div>
        </div>

        <div class="ldc-split">
          <div class="ld-card ldc-build">
            <div class="ldc-cardhead">
              <div><h4>Landed cost build-up</h4><p class="ld-card-sub" id="ldcBuildSub">&nbsp;</p></div>
              <button class="ld-btn" type="button" id="ldcExpand">Expand all eleven</button>
            </div>
            <div class="ldc-rows" id="ldcRows"></div>
            <div class="ldc-total"><span>Total landed procurement cost</span><b id="ldcRowsTotal">&mdash;</b></div>
          </div>
          <div class="ld-card ldc-ranked">
            <div style="margin-bottom:14px"><h4>Ranked options</h4><p class="ld-card-sub" id="ldcRankedSub">&nbsp;</p></div>
            <div class="ldc-list" id="ldcList" role="listbox" aria-label="Ranked berth and vessel pairings"></div>
            <p class="ldc-foot" id="ldcFoot">Feasibility follows the engine: berth draft against laden draft plus ${UKC_M} m under-keel, lightering up to ${MAX_LIGHTER_GAP_M} m, and LOA limits.</p>
          </div>
        </div>

        <div class="ld-analysis" id="ldAnalysis">
          <div class="ld-card ld-analysis-head">
            <div><h4>Full analysis</h4><p class="ld-card-sub">Cost waterfall, scenario regret matrix, explainable rationale and charter contract options for the recommended strategy.</p></div>
            <button class="ld-btn" type="button" id="ldAnalysisBtn" aria-expanded="false">Show analysis</button>
          </div>
          <div class="ld-analysis-body" id="ldAnalysisBody"></div>
        </div>
      </div>`;
    panel.insertBefore(host, section);

    // The existing detailed analysis moves inside the collapsible block; the
    // sections the new surface replaces are hidden but kept, so their ids and
    // renderers still work.
    const body = $('ldAnalysisBody');
    ['decisionCardHost', 'charterStrategyHost'].forEach(id => { const el = $(id); if(el) body.appendChild(el); });
    section.querySelector('.section-header')?.classList.add('ld-legacy');
    section.querySelector('.stepper-card')?.classList.add('ld-legacy');
    $('routemap')?.closest('.map-card')?.classList.add('ld-legacy');
    $('battle-section')?.classList.add('ld-legacy');
    section.classList.add('ld-legacy');

    $('ldcBest').addEventListener('click', () => {
      if(C.result) select(C.result.winner.portKey, C.result.winner.vesselClassKey);
    });
    $('ldcExpand').addEventListener('click', () => { C.expanded = !C.expanded; renderBuild(); });
    $('ldcMin').addEventListener('click', () => {
      const hero = host.querySelector('.ldc-hero');
      const min = !hero.classList.contains('panel-min');
      hero.classList.toggle('panel-min', min);
      $('ldcMin').setAttribute('aria-expanded', String(!min));
      $('ldcMin').title = min ? 'Expand panel' : 'Minimise panel';
      $('ldcMin').innerHTML = min
        ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 12h12M12 6v12"/></svg>'
        : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 12h12"/></svg>';
    });
    $('ldAnalysisBtn').addEventListener('click', () => {
      const box = $('ldAnalysis'), open = !box.classList.contains('open');
      box.classList.toggle('open', open);
      $('ldAnalysisBtn').textContent = open ? 'Hide analysis' : 'Show analysis';
      $('ldAnalysisBtn').setAttribute('aria-expanded', String(open));
    });

    renderPins();
    loadModelInfo();
  }

  function loadModelInfo(){
    api('/api/ml/info').then(m => {
      C.model = m;
      const foot = $('ldcFoot');
      if(foot && m && m.r2_score != null){
        foot.textContent = `Feasibility follows the engine: berth draft against laden draft plus ${UKC_M} m under-keel, lightering up to ${MAX_LIGHTER_GAP_M} m, and LOA limits. `
          + `Freight model ${m.algorithm}: hold-out R² ${m.r2_score}, MAE $${m.mae_usd}/MT.`;
      }
    }).catch(() => {});
  }

  function select(portKey, classKey){
    C.port = portKey || C.port;
    C.cls = classKey || C.cls;
    renderCommand();
  }

  /* Pins are rebuilt only when the selection changes. Hover used to rebuild
     them too: the hit target under the cursor was replaced on mouseenter, the
     replacement fired mouseenter again, and the press and release of a click
     never landed on the same element - so clicking a berth did nothing and
     the route never moved. Hover now only restyles the existing pins. */
  function renderPins(){
    const g = $('ldcPins');
    if(!g) return;
    g.innerHTML = portKeys().map(k => {
      const p = PORTS[k], [x, y, lx, ly] = PIN[p.code];
      return `<g class="pin" data-port="${k}">
        <circle class="ring" cx="${x}" cy="${y}" r="0" fill="none" stroke-width="1" opacity=".6"/>
        <circle class="dot" cx="${x}" cy="${y}" r="3.5"/>
        <text class="label" x="${lx}" y="${ly}" font-size="11">${esc(p.name)}</text>
        <circle class="pin-hit" data-port="${k}" cx="${x}" cy="${y}" r="17" fill="transparent" tabindex="0" role="button" aria-label="Select ${esc(p.name)}"/>
      </g>`;
    }).join('');
    g.querySelectorAll('.pin-hit').forEach(el => {
      const k = el.getAttribute('data-port');
      el.addEventListener('click', () => { if(C.result) select(k, null); });
      el.addEventListener('keydown', e => { if((e.key === 'Enter' || e.key === ' ') && C.result){ e.preventDefault(); select(k, null); } });
      el.addEventListener('mouseenter', () => setHover(k));
      el.addEventListener('focus', () => setHover(k));
      el.addEventListener('mouseleave', () => setHover(null));
      el.addEventListener('blur', () => setHover(null));
    });
    stylePins();
  }

  function stylePins(){
    const g = $('ldcPins');
    if(!g) return;
    g.querySelectorAll('.pin').forEach(pin => {
      const k = pin.getAttribute('data-port');
      const sel = k === C.port, hov = k === C.hover;
      const offered = C.result && C.cls ? !!optionFor(k, C.cls) : true;
      const ring = pin.querySelector('.ring'), dot = pin.querySelector('.dot'), label = pin.querySelector('.label');
      ring.setAttribute('r', sel ? 16 : hov ? 12 : 0);
      ring.setAttribute('stroke', sel ? 'var(--ld-ink)' : 'var(--ld-accent)');
      dot.setAttribute('r', sel ? 6 : hov ? 5 : 3.5);
      dot.setAttribute('fill', sel ? 'var(--ld-ink)' : offered ? 'var(--ld-accent)' : 'var(--ld-map-faint)');
      label.setAttribute('fill', sel || hov ? 'var(--ld-text)' : offered ? 'var(--ld-map-label)' : 'var(--ld-map-faint)');
      label.setAttribute('font-weight', sel ? 700 : 400);
      pin.querySelector('.pin-hit').setAttribute('aria-pressed', String(sel));
    });
  }

  function setHover(k){
    C.hover = k;
    stylePins();
    const tip = $('ldcTip');
    if(!tip) return;
    if(!k || !C.result || !C.cls){ tip.innerHTML = ''; return; }
    const hp = PORTS[k], [hx, hy] = PIN[hp.code];
    const ho = optionFor(k, C.cls);
    const line = ho
      ? `${VESSEL_CLASSES[C.cls].name}: ${money(ho.base.total)}/MT \u00b7 risk ${Math.round(ho.api.risk_index)}`
      : `${VESSEL_CLASSES[C.cls].name}: not offered`;
    const tx = Math.min(hx + 18, 520), ty = Math.max(hy - 46, 24);
    tip.innerHTML = `
      <rect x="${tx}" y="${ty}" width="196" height="40" rx="4" fill="var(--ld-map-card)" stroke="var(--ld-hair-strong)"/>
      <text x="${tx + 10}" y="${ty + 16}" fill="var(--ld-text)" font-size="12" font-weight="700">${esc(hp.name)}${k === C.port ? ' \u00b7 selected' : ' \u00b7 click to select'}</text>
      <text x="${tx + 10}" y="${ty + 31}" fill="${ho ? 'var(--ld-map-label)' : 'var(--ld-crit-ink)'}" font-size="10.5">${esc(line)}</text>`;
  }

  function renderRoute(){
    const g = $('ldcRoute');
    if(!g || !C.result) return;
    const lane = laneOf(C.result);
    const [ox, oy] = ORIGIN_AT[lane] || [862, 298];
    const [px, py] = PIN[PORTS[C.port].code];
    const best = PIN[PORTS[C.result.winner.portKey].code];
    const o = ORIGINS[lane];
    const place = (o.name.match(/\(([^)]+)\)/) || [, ''])[1];
    const bx = ox - 196, by = oy - 104;
    g.innerHTML = `
      <path d="M${ox} ${oy} C${ox - 140} ${oy + 24} ${Math.round((best[0] + 520) / 2)} ${best[1] + 55} ${best[0]} ${best[1]}" fill="none" stroke="var(--ld-map-faint)" stroke-width="1.5" stroke-dasharray="2 7" opacity=".5"/>
      <path class="route" pathLength="100" d="M${ox} ${oy} C${ox - 140} ${oy + 24} ${Math.round((px + 520) / 2)} ${py + 55} ${px} ${py}" fill="none" stroke="var(--ld-ink)" stroke-width="2.5" stroke-linecap="round"/>
      <path class="route-flow" pathLength="100" d="M${ox} ${oy} C${ox - 140} ${oy + 24} ${Math.round((px + 520) / 2)} ${py + 55} ${px} ${py}" fill="none" stroke="#FFD2C7" stroke-width="1.4" stroke-linecap="round"/>
      <line x1="${ox}" y1="${oy - 6}" x2="${ox}" y2="${by + 40}" stroke="var(--ld-hair-strong)" stroke-width="1"/>
      <circle cx="${ox}" cy="${oy}" r="6" fill="var(--ld-map-faint)"/>
      <rect x="${bx}" y="${by}" width="196" height="40" fill="var(--ld-map-card)" stroke="var(--ld-hair)"/>
      <text x="${bx + 10}" y="${by + 18}" fill="var(--ld-text)" font-size="15" font-weight="600">${esc(o.short.toUpperCase())}</text>
      <text x="${bx + 10}" y="${by + 33}" fill="var(--ld-map-label)" font-size="10">${esc(place)} &middot; load</text>`;
  }

  function tweenCost(target){
    cancelAnimationFrame(C.raf);
    const el = $('ldcCost');
    if(target == null){ el.textContent = '—'; C.costShown = 0; return; }
    const from = C.costShown || 0, start = performance.now(), dur = 700;
    const step = now => {
      const t = Math.min(1, (now - start) / dur), e = 1 - Math.pow(1 - t, 3);
      C.costShown = from + (target - from) * e;
      el.textContent = money(C.costShown);
      if(t < 1) C.raf = requestAnimationFrame(step);
    };
    if(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches){
      C.costShown = target; el.textContent = money(target); return;
    }
    C.raf = requestAnimationFrame(step);
  }

  function renderCommand(){
    if(!C.mounted || !C.result) return;
    const r = C.result, winner = r.winner, inputs = C.inputs;
    const port = PORTS[C.port], vc = VESSEL_CLASSES[C.cls];
    const opt = optionFor(C.port, C.cls);
    const lane = laneOptions(r);
    const total = portKeys().length * classKeys().length;
    const rank = opt ? lane.indexOf(opt) + 1 : 0;
    const isBest = opt === winner;
    const plantShort = (PLANT_LABEL[inputs.plant] || '').replace(/\s*\(.*\)/, '');

    /* ---- panel ---- */
    const panel = $('ldcPanel');
    panel.classList.toggle('best', isBest);
    panel.classList.toggle('blocked', !opt);
    $('ldcVerdict').textContent = !opt ? 'Not offered' : isBest ? 'Recommended strategy' : 'Alternative under review';
    $('ldcRank').textContent = opt ? `RANK ${rank} / ${lane.length}` : `${lane.length} OFFERED`;
    $('ldcTitle').textContent = `${port.name} · ${vc.name}`;
    $('ldcMeta').textContent = opt
      ? `${port.code} · ${port.draft.toFixed(1)} m draft · ${Math.round(opt.api.rail_km)} km rail to ${plantShort}${opt.api.shipments > 1 ? ' · ' + opt.api.shipments + ' shipments' : ''}`
      : `${port.code} · ${port.draft.toFixed(1)} m draft · ${vc.name} draws ${vc.draft.toFixed(1)} m`;
    $('ldcFigures').hidden = !opt;

    const why = $('ldcWhy');
    why.classList.remove('info');
    if(!opt){
      why.hidden = false;
      why.textContent = blockedReason(C.port, C.cls);
      tweenCost(null);
    }else{
      tweenCost(opt.base.total);
      $('ldcTotal').textContent = '₹' + (opt.base.total * inputs.qty * INR_PER_USD / 1e7).toFixed(1) + ' Cr';
      const a = opt.api;
      $('ldcArc').setAttribute('stroke-dashoffset', (289 * (1 - a.risk_index / 100)).toFixed(1));
      $('ldcArc').setAttribute('stroke', riskColor(a.risk_index));
      $('ldcRiskNum').textContent = Math.round(a.risk_index);
      $('ldcRiskBand').textContent = `Risk · ${riskBand(a.risk_index)}`;
      RISK.forEach((k, i) => {
        const v = Math.round(a[k[1]] || 0);
        $('ldcB' + i).style.width = v + '%';
        $('ldcBv' + i).textContent = v;
      });
      if(isBest){
        why.hidden = true;
      }else{
        const d = opt.base.total - winner.base.total;
        why.hidden = false;
        why.classList.add('info');
        why.textContent = d < 0
          ? `${money(-d)}/MT cheaper than the recommendation, but risk ${Math.round(a.risk_index)} against ${Math.round(winner.api.risk_index)} - it loses on the risk-adjusted ranking.`
          : `${money(d)}/MT above the recommended ${PORTS[winner.portKey].name} · ${VESSEL_CLASSES[winner.vesselClassKey].name}.`;
      }
    }

    /* ---- class bar ---- */
    $('ldcClasses').innerHTML = classKeys().map(k => {
      const v = VESSEL_CLASSES[k], on = k === C.cls, offered = !!optionFor(C.port, k);
      return `<button type="button" class="ldc-class ${on ? 'on' : offered ? '' : 'off'}" data-cls="${k}" aria-pressed="${on}">${esc(v.name)}<small>${Math.round(v.dwtMax / 1000)}k · ${v.draft.toFixed(1)} m</small></button>`;
    }).join('');
    $('ldcClasses').querySelectorAll('[data-cls]').forEach(b => b.addEventListener('click', () => select(null, b.getAttribute('data-cls'))));

    /* ---- tiles ---- */
    if(opt){
      const a = opt.api;
      $('ldcCont').textContent = Math.round(a.supply_continuity);
      $('ldcContBar').style.width = Math.round(a.supply_continuity) + '%';
      $('ldcContNote').textContent = `${a.discharge_days.toFixed(1)} d to discharge at ${fmt(port.mechRate)} MT/day`;
      $('ldcConf').textContent = Math.round(a.confidence) + '%';
      $('ldcConfBar').style.width = Math.round(a.confidence) + '%';
      if(isBest){
        $('ldcDelta').textContent = 'BEST';
        $('ldcDelta').style.color = 'var(--ld-pos-ink)';
        $('ldcDeltaNote').textContent = `Lowest risk-adjusted cost of ${lane.length} offered pairings on the ${ORIGINS[laneOf(r)].short} lane`;
      }else{
        const d = opt.base.total - winner.base.total;
        $('ldcDelta').textContent = signed(d);
        $('ldcDelta').style.color = d > 0 ? 'var(--ld-warn-ink)' : 'var(--ld-pos-ink)';
        $('ldcDeltaNote').textContent = `per MT vs ${PORTS[winner.portKey].name} · ${VESSEL_CLASSES[winner.vesselClassKey].name}`;
      }
      $('ldcCycle').textContent = a.total_cycle_days.toFixed(1) + ' d';
      $('ldcSegSea').style.flexGrow = Math.max(a.sea_days, 0.05);
      $('ldcSegWait').style.flexGrow = Math.max(a.wait_days, 0.05);
      $('ldcSegDis').style.flexGrow = Math.max(a.discharge_days, 0.05);
      $('ldcCycleNote').textContent = `${a.sea_days.toFixed(1)} sea · ${a.wait_days.toFixed(1)} wait · ${a.discharge_days.toFixed(1)} discharge`;
    }else{
      ['ldcCont','ldcConf','ldcDelta','ldcCycle'].forEach(id => { $(id).textContent = '—'; $(id).style.color = ''; });
      ['ldcContBar','ldcConfBar'].forEach(id => $(id).style.width = '0%');
      $('ldcContNote').textContent = 'Not offered by the engine';
      $('ldcDeltaNote').textContent = 'No figures for a pairing the engine did not offer';
      $('ldcCycleNote').textContent = ' ';
    }

    renderBuild();
    renderRanked();
    stylePins();
    renderRoute();
    if(C.hover) setHover(C.hover);
  }

  function renderBuild(){
    const opt = optionFor(C.port, C.cls);
    const rows = $('ldcRows');
    if(!rows) return;
    $('ldcExpand').textContent = C.expanded ? 'Group into four' : 'Expand all eleven';
    if(!opt){
      rows.innerHTML = `<div class="ld-note">No cost build-up: the engine did not offer ${esc(VESSEL_CLASSES[C.cls].name)} at ${esc(PORTS[C.port].name)}.</div>`;
      $('ldcBuildSub').textContent = ' ';
      $('ldcRowsTotal').textContent = '—';
      return;
    }
    const b = opt.base;
    const list = C.expanded
      ? PARTS.map(([k, label]) => [label, b[k] || 0, 'var(--ld-accent)', false])
      : GROUPS.map(([label, keys, color]) => [label, keys.reduce((s, k) => s + (b[k] || 0), 0), color, true]);
    const max = Math.max(...list.map(r => r[1]), 0.01);
    const html = list.map(([label, val, color, group]) => `
      <div class="ldc-row ${group ? 'group' : ''}">
        <div>${esc(label)}</div>
        <div class="t"><i style="width:0%;background:${color}" data-w="${val === 0 ? 0 : Math.max(1.2, val / max * 100)}"></i></div>
        <div class="v">${money(val)}</div>
        <div class="p">${(val / b.total * 100).toFixed(1)}%</div>
      </div>`).join('');
    const sameShape = rows.children.length === list.length && rows.dataset.mode === String(C.expanded);
    if(sameShape){
      [...rows.children].forEach((row, i) => {
        const [, val] = list[i];
        row.querySelector('.t i').style.width = (val === 0 ? 0 : Math.max(1.2, val / max * 100)) + '%';
        row.querySelector('.v').textContent = money(val);
        row.querySelector('.p').textContent = (val / b.total * 100).toFixed(1) + '%';
      });
    }else{
      rows.innerHTML = html;
      rows.dataset.mode = String(C.expanded);
      requestAnimationFrame(() => rows.querySelectorAll('.t i').forEach(i => { i.style.width = i.getAttribute('data-w') + '%'; }));
    }
    $('ldcBuildSub').textContent = `${C.expanded ? 'Eleven components' : 'Four groups of eleven components'} · ${money(b.total)}/MT · ${PORTS[C.port].name} · ${VESSEL_CLASSES[C.cls].name}`;
    $('ldcRowsTotal').textContent = money(b.total) + ' / MT';
  }

  function renderRanked(){
    const r = C.result, lane = laneOptions(r);
    const total = portKeys().length * classKeys().length;
    const blocked = [];
    portKeys().forEach(pk => classKeys().forEach(ck => {
      if(!lane.some(c => c.portKey === pk && c.vesselClassKey === ck)) blocked.push([pk, ck]);
    }));
    $('ldcRankedSub').textContent = `${lane.length} offered of ${total} berth × vessel pairings on the ${ORIGINS[laneOf(r)].short} lane - click to inspect`;
    const items = lane.map((c, i) => {
      const on = c.portKey === C.port && c.vesselClassKey === C.cls;
      return `<button type="button" class="ldc-opt ${on ? 'on' : ''}" data-p="${c.portKey}" data-c="${c.vesselClassKey}" aria-selected="${on}">
        <span class="r">${String(i + 1).padStart(2, '0')}</span><span class="n">${esc(PORTS[c.portKey].name)} · ${esc(VESSEL_CLASSES[c.vesselClassKey].name)}</span><span class="c">${money(c.base.total)}</span></button>`;
    }).concat(blocked.map(([pk, ck], i) => {
      const on = pk === C.port && ck === C.cls;
      return `<button type="button" class="ldc-opt off ${on ? 'on' : ''}" data-p="${pk}" data-c="${ck}" aria-selected="${on}" title="${esc(blockedReason(pk, ck))}">
        <span class="r">${String(lane.length + i + 1).padStart(2, '0')}</span><span class="n">${esc(PORTS[pk].name)} · ${esc(VESSEL_CLASSES[ck].name)}</span><span class="c">not offered</span></button>`;
    }));
    const list = $('ldcList');
    const keep = list.scrollTop;
    list.innerHTML = items.join('');
    list.scrollTop = keep;
    list.querySelectorAll('[data-p]').forEach(b => b.addEventListener('click', () => select(b.getAttribute('data-p'), b.getAttribute('data-c'))));
  }

  function onResult(result, inputs){
    if(!result || !result.winner) return;
    mountCommand();
    const fresh = C.result !== result;
    C.result = result;
    C.inputs = inputs || activeInputs;
    if(fresh) C.runAt = new Date();
    if(fresh) I.picked = false;
    if(fresh || !C.port){
      C.port = result.winner.portKey;
      C.cls = result.winner.vesselClassKey;
    }
    renderCommand();
    syncCopilotPrompts(C.inputs);
    if(isShown('intelligence')) renderIntel();
    if(isShown('approved')) renderBrief();
    landByRole();
  }

  // The quick prompt named Rourkela whatever plant was on screen.
  function syncCopilotPrompts(inputs){
    const plant = (PLANT_LABEL[inputs && inputs.plant] || '').replace(/\s*\(.*\)/, '');
    if(!plant) return;
    document.querySelectorAll('.prompt-btn').forEach(btn => {
      if(/best route for|optimal route for/i.test(btn.getAttribute('onclick') || '')){
        btn.textContent = `What is the optimal route for ${plant}?`;
        btn.onclick = () => askCopilot(`What is the best route for ${plant}?`);
        btn.removeAttribute('onclick');
        btn.dataset.routePrompt = '1';
      }else if(btn.dataset.routePrompt){
        btn.textContent = `What is the optimal route for ${plant}?`;
        btn.onclick = () => askCopilot(`What is the best route for ${plant}?`);
      }
    });
  }

  /* ============================================================= INTEL */
  const I = {origin:null, picked:false, curves:null, key:'', loading:false, mounted:false};

  function isShown(name){ return !!$('panel-' + name)?.classList.contains('active'); }

  function mountIntel(){
    if(I.mounted) return;
    const panel = $('panel-intelligence');
    if(!panel) return;
    I.mounted = true;
    panel.querySelector('.section')?.classList.add('ld-legacy');
    const host = document.createElement('div');
    host.id = 'ldIntel';
    host.className = 'ld-wrap';
    host.innerHTML = `
      <div class="ldi-head">
        <div>
          <div class="ld-kicker accent">Market analysis &middot; Freight intelligence</div>
          <div class="ld-h1">Freight Intelligence</div>
          <p class="ld-lede">Twelve-month forecast with P10-P90 confidence bands and the market timing signal, predicted by the trained freight model. The band is &plusmn;1.96 &times; hold-out RMSE.</p>
        </div>
        <div class="ldi-meta">
          <div><div class="ld-label">Trained lanes</div><div class="ld-num" id="ldiLanes">&mdash;</div></div>
          <div><div class="ld-label">Selected lane</div><div class="ld-num" id="ldiLaneName">&mdash;</div></div>
        </div>
      </div>
      <div class="ldi-tiles" id="ldiTiles"></div>
      <div class="ldi-grid">
        <div class="ld-card ldi-chart">
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
            <div><h4 id="ldiChartTitle">Dry-bulk rate horizon</h4><p class="ld-card-sub" id="ldiChartSub">&nbsp;</p></div>
            <span class="ld-tag">Synthetic</span>
          </div>
          <svg id="ldiChart" viewBox="0 0 640 270" role="img" aria-label="Twelve-month freight rate forecast"></svg>
          <div class="ldc-legend" style="position:static;margin-top:8px">
            <span><i style="width:16px;height:2px;background:var(--ld-accent)"></i>P50 forecast</span>
            <span><i style="width:14px;height:8px;background:var(--ld-accent-soft);border:1px solid var(--blue-border)"></i>P10-P90 band</span>
            <span><i style="width:8px;height:8px;border-radius:50%;background:var(--ld-pos)"></i>Seasonal trough</span>
          </div>
        </div>
        <div class="ld-card ldi-signal">
          <h4>Market timing signal</h4>
          <p class="ld-card-sub">Spot P50 against the model's own twelve-month mean for this lane.</p>
          <div class="ldi-word" id="ldiWord">&mdash;</div>
          <p class="ldi-why" id="ldiWhy">&nbsp;</p>
          <div class="ldi-rule">Rule: spot within &plusmn;4% of the twelve-month mean is HOLD.</div>
          <div class="ldi-comp" id="ldiComp">Composite risk index <b>&mdash;</b> /100</div>
          <div class="ldi-bars" id="ldiBars"></div>
        </div>
      </div>
      <div class="ld-card ldi-table">
        <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
          <div><h4>Freight rates by origin &mdash; P50, this month</h4><p class="ld-card-sub">Band is &plusmn;1.96 &times; hold-out RMSE. Swing is the model's twelve-month seasonal range. Click a lane to chart it.</p></div>
          <span class="ld-tag">Synthetic</span>
        </div>
        <div class="table-responsive"><table>
          <thead><tr><th>Origin</th><th style="text-align:right">P50</th><th style="text-align:right">Low 95%</th><th style="text-align:right">High 95%</th><th style="text-align:right">Swing</th><th style="text-align:right">Distance</th><th>Cargo</th></tr></thead>
          <tbody id="ldiRows"><tr><td colspan="7" style="text-align:center;padding:18px">Scoring each lane with the freight model...</td></tr></tbody>
        </table></div>
        <p class="ldc-foot">Origins are limited to the four the model was trained on.</p>
      </div>`;
    panel.insertBefore(host, panel.firstChild);
  }

  async function renderIntel(){
    mountIntel();
    if(!I.mounted) return;
    const inputs = activeInputs || {cargoType:'coking_coal'};
    const month = currentMonth();
    const keys = Object.keys(ORIGINS);
    const key = month + '|' + keys.map(k => lanePressure(k)).join(',');
    $('ldiLanes').textContent = String(keys.length).padStart(2, '0');

    const engineLane = laneOf(activeResult);
    if(engineLane && !I.picked) I.origin = engineLane;
    if(!I.origin){
      const lane = engineLane;
      I.origin = lane || keys.find(k => ORIGINS[k].cargo.includes(inputs.cargoType)) || keys[0];
    }

    if(I.key !== key || !I.curves){
      if(I.loading) return;
      I.loading = true;
      const horizons = Array.from({length:12}, (_, i) => i === 0 ? 1 : i * 30 + 1);
      try{
        const results = await Promise.all(keys.map(k => api('/api/ml/forecast-curve', {
          method:'POST',
          body: JSON.stringify({origin:ORIGINS[k].api, distance_nm:ORIGINS[k].distanceNm, month,
                                bunker_price:697, pressure_index:lanePressure(k), horizons})
        }).then(d => [k, d.points])));
        I.curves = Object.fromEntries(results);
        I.key = key;
      }catch(err){
        $('ldiRows').innerHTML = `<tr><td colspan="7" style="padding:14px;color:var(--ld-crit-ink)">The freight model could not be reached (${esc(err.message)}). No rates are shown rather than estimates.</td></tr>`;
        I.loading = false;
        return;
      }
      I.loading = false;
    }
    drawIntel();
  }

  function drawIntel(){
    const inputs = activeInputs || {cargoType:'coking_coal'};
    const k = I.origin, o = ORIGINS[k], pts = I.curves[k];
    const p50 = pts.map(p => p.predicted_rate_usd);
    const mean = p50.reduce((s, v) => s + v, 0) / p50.length;
    let peakI = 0, troughI = 0;
    p50.forEach((v, i) => { if(v > p50[peakI]) peakI = i; if(v < p50[troughI]) troughI = i; });
    const spot = pts[0];
    const band = (spot.ci_upper_usd - spot.ci_lower_usd) / 2;

    $('ldiLaneName').textContent = o.short;
    $('ldiTiles').innerHTML = `
      <div class="ld-card ldi-tile"><div class="ld-label">Spot P50 &middot; ${esc(o.short)}</div><div class="ld-num accent">${money(spot.predicted_rate_usd)}</div><div class="ld-note">per MT &middot; ${fmt(o.distanceNm)} nm lane</div></div>
      <div class="ld-card ldi-tile"><div class="ld-label">12-month peak</div><div class="ld-num">${money(p50[peakI])}</div><div class="ld-note">${monthName(peakI, 'long')}</div></div>
      <div class="ld-card ldi-tile"><div class="ld-label">12-month trough</div><div class="ld-num pos">${money(p50[troughI])}</div><div class="ld-note">${monthName(troughI, 'long')} &middot; seasonal low</div></div>
      <div class="ld-card ldi-tile"><div class="ld-label">Band width (95%)</div><div class="ld-num">&plusmn;${money(band)}</div><div class="ld-note">1.96 &times; hold-out RMSE</div></div>`;

    $('ldiChartTitle').textContent = `Dry-bulk rate horizon — ${o.short} lane`;
    $('ldiChartSub').textContent = `${CARGO_LABEL[inputs.cargoType] || 'Dry bulk'}, $/MT · 12 months from ${monthName(0, 'long')}`;
    drawCurve($('ldiChart'), pts, peakI, troughI);

    // timing signal
    const diff = (spot.predicted_rate_usd - mean) / mean * 100;
    const word = $('ldiWord');
    word.className = 'ldi-word';
    if(Math.abs(diff) <= 4){
      word.textContent = 'HOLD'; word.classList.add('hold');
      $('ldiWhy').textContent = `Spot sits ${Math.abs(diff).toFixed(1)}% ${diff >= 0 ? 'above' : 'below'} the twelve-month mean and the curve bottoms in ${monthName(troughI)}. No premium in fixing early.`;
    }else if(diff < 0){
      word.textContent = 'FIX NOW'; word.classList.add('fix');
      $('ldiWhy').textContent = `Spot is ${Math.abs(diff).toFixed(1)}% below the twelve-month mean. A period charter now locks in the dip before the ${monthName(peakI)} peak.`;
    }else{
      word.textContent = 'DEFER'; word.classList.add('defer');
      $('ldiWhy').textContent = `Spot is ${diff.toFixed(1)}% above the twelve-month mean and eases toward ${monthName(troughI)}. Fix short or wait.`;
    }
    const w = activeResult && activeResult.winner && activeResult.winner.api;
    if(w){
      $('ldiComp').innerHTML = `Composite risk index <b>${Math.round(w.risk_index)}</b>/100 for the recommended option`;
      const weights = ['Berth congestion 30%','Freight volatility 25%','Seasonal exposure 25%','Under-keel clearance 20%'];
      const fields = ['congestion_score','freight_volatility_score','monsoon_risk_score','draft_risk_score'];
      $('ldiBars').innerHTML = fields.map((f, i) => {
        const v = Math.round(w[f] || 0);
        return `<div><div class="ldi-bar-l"><span>${weights[i]}</span><b>${v}</b></div><div class="ld-track"><i style="width:${v}%;background:${riskColor(v)}"></i></div></div>`;
      }).join('');
    }else{
      $('ldiComp').textContent = 'Run a strategy to see the recommended option’s risk components.';
      $('ldiBars').innerHTML = '';
    }

    // lane table
    $('ldiRows').innerHTML = Object.keys(ORIGINS).map(key => {
      const lo = ORIGINS[key], lp = I.curves[key];
      const rates = lp.map(p => p.predicted_rate_usd);
      const carries = lo.cargo.includes(inputs.cargoType);
      return `<tr class="${key === k ? 'on' : ''} ${carries ? '' : 'dim'}" data-origin="${key}" tabindex="0">
        <td class="o">${esc(lo.short)} ${key === k ? '<span class="ld-tag" style="margin-left:6px">Selected</span>' : ''}</td>
        <td class="p50" style="text-align:right">${money(lp[0].predicted_rate_usd)}</td>
        <td style="text-align:right">${money(lp[0].ci_lower_usd)}</td>
        <td style="text-align:right">${money(lp[0].ci_upper_usd)}</td>
        <td style="text-align:right">${money(Math.max(...rates) - Math.min(...rates))}</td>
        <td style="text-align:right">${fmt(lo.distanceNm)} nm</td>
        <td>${lo.cargo.map(c => CARGO_LABEL[c]).join(', ')}${carries ? '' : ` <span style="color:var(--ld-mute)">&middot; no ${esc((CARGO_LABEL[inputs.cargoType] || '').toLowerCase())}</span>`}</td>
      </tr>`;
    }).join('');
    $('ldiRows').querySelectorAll('[data-origin]').forEach(tr => {
      const pickLane = () => { I.origin = tr.getAttribute('data-origin'); I.picked = true; drawIntel(); };
      tr.addEventListener('click', pickLane);
      tr.addEventListener('keydown', e => { if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); pickLane(); } });
    });
  }

  function drawCurve(svg, pts, peakI, troughI){
    const W = 640, H = 270, L = 46, R = 18, T = 30, B = 34;
    const lo = Math.min(...pts.map(p => p.ci_lower_usd)), hi = Math.max(...pts.map(p => p.ci_upper_usd));
    const pad = (hi - lo) * 0.12 || 1, y0 = lo - pad, y1 = hi + pad;
    const X = i => L + i * (W - L - R) / (pts.length - 1);
    const Y = v => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
    const ticks = Array.from({length:4}, (_, i) => y0 + (y1 - y0) * (i + 0.5) / 4);
    const up = pts.map((p, i) => `${X(i).toFixed(1)},${Y(p.ci_upper_usd).toFixed(1)}`);
    const dn = pts.map((p, i) => `${X(i).toFixed(1)},${Y(p.ci_lower_usd).toFixed(1)}`).reverse();
    const line = pts.map((p, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(p.predicted_rate_usd).toFixed(1)}`).join(' ');
    const pk = pts[peakI], tr = pts[troughI];
    svg.innerHTML = `
      ${ticks.map(t => `<line class="ldi-grid-line" x1="${L}" x2="${W - R}" y1="${Y(t).toFixed(1)}" y2="${Y(t).toFixed(1)}"/><text class="ldi-axis" x="${L - 8}" y="${(Y(t) + 3.5).toFixed(1)}" text-anchor="end">${t.toFixed(0)}</text>`).join('')}
      <polygon points="${up.concat(dn).join(' ')}" fill="var(--ld-accent-soft)" stroke="var(--blue-border)" stroke-width="1"/>
      <path d="${line}" fill="none" stroke="var(--ld-accent)" stroke-width="2.4" stroke-linejoin="round" style="filter:var(--ld-glow)"/>
      ${pts.map((p, i) => `<circle cx="${X(i).toFixed(1)}" cy="${Y(p.predicted_rate_usd).toFixed(1)}" r="${i === peakI || i === troughI ? 5 : 2.6}" fill="${i === troughI ? 'var(--ld-pos)' : 'var(--ld-accent)'}" stroke="${i === peakI || i === troughI ? 'var(--ld-text)' : 'none'}" stroke-width="1.5"><title>${monthName(i, 'long')}: ${money(p.predicted_rate_usd)} (${money(p.ci_lower_usd)}-${money(p.ci_upper_usd)})</title></circle>`).join('')}
      <text x="${X(peakI).toFixed(1)}" y="${(Y(pk.predicted_rate_usd) - 12).toFixed(1)}" text-anchor="middle" font-size="12" font-weight="700" fill="var(--ld-accent-ink)">${money(pk.predicted_rate_usd)} PEAK</text>
      <text x="${X(troughI).toFixed(1)}" y="${(Y(tr.predicted_rate_usd) + 22).toFixed(1)}" text-anchor="middle" font-size="12" font-weight="700" fill="var(--ld-pos-ink)">${money(tr.predicted_rate_usd)} TROUGH</text>
      ${pts.map((_, i) => `<text class="ldi-axis" x="${X(i).toFixed(1)}" y="${H - 10}" text-anchor="middle">${monthName(i)}</text>`).join('')}`;
  }

  /* ============================================================= BRIEF */
  function renderBrief(){
    const host = $('ldBrief');
    if(!host) return;
    const r = activeResult, inputs = activeInputs;
    if(!r || !r.winner){
      host.innerHTML = `<div class="ld-card" style="padding:28px;text-align:center"><h4>No strategy yet</h4><p class="ld-card-sub">The brief appears once the decision engine has run for the cargo on file.</p></div>`;
      return;
    }
    const w = r.winner, a = w.api, p = PORTS[w.portKey], v = VESSEL_CLASSES[w.vesselClassKey], o = ORIGINS[w.originKey];
    const place = (o.name.match(/\(([^)]+)\)/) || [, ''])[1];
    const plant = (PLANT_LABEL[inputs.plant] || '').replace(/\s*\(.*\)/, '');
    const cargo = (CARGO_LABEL[inputs.cargoType] || '').toLowerCase();
    const alerts = typeof buildAlerts === 'function' ? buildAlerts(r) : [];
    const month = currentMonth();
    const monsoon = (p.monsoon || []);
    const monsoonNow = monsoon.includes(month);
    const range = monsoon.length ? `${monthName(monsoon[0] - month)}–${monthName(monsoon[monsoon.length - 1] - month)}` : 'none listed';
    const needDraft = v.draft + UKC_M;
    const readOnly = role().includes('officer');
    const icon = {risk:'<path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h.01"/>',
                  warn:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
                  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>'};
    const stamp = C.runAt || new Date();

    host.innerHTML = `
      <div class="ldb-head">
        <div>
          <div class="ld-kicker accent">Execution &middot; Current strategy</div>
          <div class="ld-h1">Execution Brief</div>
          <p class="ld-lede">What the decision engine recommends for the cargo on file, what it costs, and what to watch.</p>
        </div>
        <div class="ldb-ref"><div class="ld-label">Engine run</div><div class="ld-num">${stamp.toLocaleString('en-IN', {day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit'})}</div></div>
      </div>

      <div class="ld-card ldb-main">
        <div class="ldb-status">
          <span class="ld-tag pos">Engine recommendation</span>
          <span>Generated from the current cargo parameters. Approval is recorded outside this system.</span>
          ${readOnly ? '<span class="ldb-readonly" style="margin-left:auto"><svg viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="10" rx="1"/><path d="M8 11V7a4 4 0 018 0v4"/></svg>Read-only &middot; parameters set by the chartering desk</span>' : ''}
        </div>
        <div class="ldb-sentence">Lift <b>${fmt(inputs.qty)} MT of ${esc(cargo)}</b> from <b>${esc(o.short)}</b> &mdash; ${esc(place)} &mdash; on ${a.shipments > 1 ? `<b>${a.shipments} ${esc(v.name)}</b> voyages` : `a <b>${esc(v.name)}</b> vessel`}, discharge at <b>${esc(p.name)}</b>, and rail ${Math.round(a.rail_km)} km to <b>${esc(plant)}</b>.</div>
        <div class="ldb-tiles">
          <div class="ldb-tile"><div class="ld-label">Landed cost</div><div class="ld-num accent">${money(w.base.total)}</div><div class="ld-note">per MT &middot; ₹${(w.base.total * inputs.qty * INR_PER_USD / 1e7).toFixed(1)} Cr total</div></div>
          <div class="ldb-tile"><div class="ld-label">Sea passage</div><div class="ld-num">${a.sea_days.toFixed(1)} d</div><div class="ld-note">${fmt(o.distanceNm)} nm lane</div></div>
          <div class="ldb-tile"><div class="ld-label">Berth wait</div><div class="ld-num">${a.wait_days.toFixed(1)} d</div><div class="ld-note">${esc(p.name)} average ${p.waitDays} d${a.shipments > 1 ? ' per shipment' : ''}</div></div>
          <div class="ldb-tile"><div class="ld-label">Discharge</div><div class="ld-num">${a.discharge_days.toFixed(1)} d</div><div class="ld-note">${fmt(p.mechRate)} MT/day mechanised</div></div>
        </div>
      </div>

      <div class="ldb-grid">
        <div class="ld-card ldb-alerts">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:10px"><h4>Alerts</h4><span class="ld-tag ${alerts.length ? 'ink' : 'pos'}">${alerts.length} open</span></div>
          ${alerts.length ? alerts.map(x => `
            <div class="ldb-alert ${x.tone}">
              <svg viewBox="0 0 24 24" aria-hidden="true">${icon[x.tone] || icon.info}</svg>
              <div><div class="t">${esc(x.title)}</div><p>${esc(x.text)}</p><div class="s">${esc(x.src)}</div></div>
            </div>`).join('') : '<p class="ld-card-sub" style="margin-top:12px">No alerts for the current plan.</p>'}
        </div>

        <div class="ld-card ldb-port">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:10px"><h4>Port profile &mdash; ${esc(p.name)}</h4><span class="ld-tag pos">Selected</span></div>
          <p class="ld-card-sub">${esc(p.code)} &middot; discharge berth for this strategy</p>
          <div class="ldb-specs">
            <div class="ldb-spec"><div class="ld-label">Max draft</div><div class="ld-num">${p.draft.toFixed(1)} m</div><div class="${p.draft >= needDraft ? 'ok' : 'bad'}">${esc(v.name)} needs ${needDraft.toFixed(1)} m${a.requires_lightering ? ' &middot; lightering' : ''}</div></div>
            <div class="ldb-spec"><div class="ld-label">Max LOA</div><div class="ld-num">${p.loa} m</div><div class="${p.loa >= v.loa ? 'ok' : 'bad'}">${esc(v.name)} ${v.loa} m</div></div>
            <div class="ldb-spec"><div class="ld-label">Max beam</div><div class="ld-num">${p.beam} m</div><div class="${p.beam >= v.beam ? 'ok' : 'bad'}">${esc(v.name)} ${v.beam} m</div></div>
            <div class="ldb-spec"><div class="ld-label">Berths</div><div class="ld-num">${p.berths}</div><div class="ld-note">Mechanised bulk</div></div>
            <div class="ldb-spec"><div class="ld-label">Discharge rate</div><div class="ld-num">${fmt(p.mechRate)}</div><div class="ld-note">MT per day</div></div>
            <div class="ldb-spec"><div class="ld-label">Rail to plant</div><div class="ld-num">${Math.round(a.rail_km)} km</div><div class="ld-note">To ${esc(plant)}</div></div>
          </div>
          <div class="ldb-chips">
            <span class="ldb-chip ${monsoonNow ? 'warn' : ''}">Monsoon exposure ${esc(range)}${monsoonNow ? ' &middot; now' : ''}</span>
            <span class="ldb-chip">Demurrage ${usd(p.demurrage)}/day</span>
            <span class="ldb-chip">Avg wait ${p.waitDays} d</span>
          </div>
          <div style="margin-top:16px"><button class="ld-btn" type="button" onclick="switchPanel('command')">Open in Command Centre</button></div>
        </div>
      </div>`;
  }

  /* ============================================================ ROLES */
  let landed = false;
  function landByRole(){
    if(landed) return;
    landed = true;
    if(!isShown('command')) return;
    const r = role();
    if(r.includes('analyst')) switchPanel('intelligence');
    else if(r.includes('officer')) switchPanel('approved');
  }

  /* ============================================================ HOOKS */
  if(typeof SECTIONS === 'object' && !SECTIONS.approved){
    SECTIONS.approved = {label:'Execution Brief', group:'Decision Support'};
  }

  const _renderDecisionCard = renderDecisionCard;
  renderDecisionCard = function(result, inputs, targetId){
    const out = _renderDecisionCard.apply(this, arguments);
    if((targetId || 'decisionCardHost') === 'decisionCardHost') onResult(result, inputs);
    return out;
  };

  const _refreshAlerts = refreshAlerts;
  refreshAlerts = function(result){
    const out = _refreshAlerts.apply(this, arguments);
    if(isShown('approved')) renderBrief();
    return out;
  };

  // The new lane table replaces the old one; keep a single set of model calls.
  renderFreightOriginTable = function(){ if(isShown('intelligence')) return renderIntel(); };

  const _switchPanel = switchPanel;
  switchPanel = function(name){
    const out = _switchPanel.apply(this, arguments);
    if(name === 'intelligence') renderIntel();
    if(name === 'approved') renderBrief();
    return out;
  };

  function mountLoader(){
    const overlay = $('loadingOverlay');
    const spinner = overlay && overlay.querySelector('.spinner');
    if(!spinner || overlay.querySelector('.ld-loader')) return;
    spinner.insertAdjacentHTML('afterend', `
      <svg class="ld-loader" viewBox="0 0 400 130" role="img" aria-label="A vessel steaming toward the freight forecast">
        <defs>
          <linearGradient id="ldLoaderWake" x1="0" x2="1"><stop offset="0" stop-color="#9BE3EF" stop-opacity="0"/><stop offset="1" stop-color="#9BE3EF" stop-opacity=".6"/></linearGradient>
        </defs>
        <path class="wave" d="M0 108 C40 102 80 114 120 108 S200 102 240 108 S320 114 360 108 S400 104 400 104" fill="none" stroke="rgba(234,243,246,.22)" stroke-width="1.5"/>
        <path class="wave w2" d="M0 120 C40 114 80 126 120 120 S200 114 240 120 S320 126 360 120 S400 116 400 116" fill="none" stroke="rgba(234,243,246,.12)" stroke-width="1.5"/>
        <path id="ldLoaderRoute" class="trail" d="M24 88 C96 72 170 100 238 82 S306 68 326 66" fill="none" stroke="#FF5436" stroke-width="2" stroke-linecap="round"/>
        <g transform="translate(352 60)">
          <circle r="26" fill="rgba(63,184,206,.14)" stroke="rgba(63,184,206,.45)"/>
          <line x1="-14" y1="12" x2="14" y2="12" stroke="rgba(234,243,246,.3)"/>
          <polyline points="-13,8 -5,1 2,5 12,-8" fill="none" stroke="#3FB8CE" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M5 -9 L12 -8 L11 -1" fill="none" stroke="#3FB8CE" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="12" cy="-8" r="3" fill="none" stroke="#9BE3EF" stroke-width="1.5" class="ld-anim">
            <animate attributeName="r" values="3;17" dur="1.6s" repeatCount="indefinite"/>
            <animate attributeName="opacity" values=".95;0" dur="1.6s" repeatCount="indefinite"/>
          </circle>
        </g>
        <g id="ldLoaderShip">
          <g transform="translate(0 -2)">
            <path d="M-60 -1 C-44 -4 -34 -4 -24 -2" fill="none" stroke="url(#ldLoaderWake)" stroke-width="3" stroke-linecap="round"/>
            <path d="M-24 -10 H26 L18 0 H-20 Z" fill="#EAF3F6"/>
            <rect x="-20" y="-22" width="9" height="12" fill="#EAF3F6"/>
            <rect x="-18" y="-19" width="5" height="3" fill="#0B2A3A"/>
            <rect x="-8" y="-16" width="8" height="6" fill="#3FB8CE"/>
            <rect x="1" y="-16" width="8" height="6" fill="#FF5436"/>
            <rect x="10" y="-16" width="8" height="6" fill="#3FB8CE"/>
          </g>
          <animateMotion class="ld-anim" dur="3.2s" repeatCount="indefinite" rotate="auto" keyPoints="0;1" keyTimes="0;1" calcMode="spline" keySplines="0.45 0 0.35 1"><mpath href="#ldLoaderRoute"/></animateMotion>
        </g>
      </svg>`);
    spinner.classList.add('ld-legacy');
    if(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches){
      overlay.querySelectorAll('.ld-loader animate, .ld-loader animateMotion').forEach(n => n.remove());
      $('ldLoaderShip').setAttribute('transform', 'translate(238 80)');
    }
  }

  function trackHeaderHeight(){
    const header = document.querySelector('.gov-header');
    if(!header) return;
    const apply = () => document.documentElement.style.setProperty('--header-h', header.offsetHeight + 'px');
    apply();
    if(window.ResizeObserver) new ResizeObserver(apply).observe(header);
    else window.addEventListener('resize', apply);
  }

  mountCommand();
  mountIntel();
  mountLoader();
  trackHeaderHeight();

  window.LDDash = {select, renderIntel, renderBrief, state:{command:C, intel:I}};
})();
