/* =========================================================================
   LOHA DRISHTI - PLANNING, MARKET, ASSURANCE AND OPERATIONS
     Charter Planner      /api/planning/charter-plan + /api/planning/constraints
     Market & Congestion  /api/market/{demand-supply,congestion,seasonal}
     PS Alignment Check   /api/system/alignment
     Emergency contacts   /api/ops/emergency
     Alert centre         /api/ops/alerts, merged into the header drawer
     Offline mode         service worker + banner

   Like ld-dash.js this file computes nothing: every figure is read from an
   API response. It replaces the old in-browser Charter Contract Strategy,
   which priced contracts with invented multipliers.
   ========================================================================= */
(function(){
  'use strict';

  const $ = id => document.getElementById(id);
  const esc = s => escapeHtml(String(s == null ? '' : s));
  const MN = ['', 'Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const ORIGIN_NAME = {australia:'Australia', indonesia:'Indonesia', south_africa:'South Africa', usa:'USA'};
  const PLANTS = [['rourkela','Rourkela'],['bhilai','Bhilai'],['bokaro','Bokaro'],['durgapur','Durgapur'],['burnpur','IISCO Burnpur']];
  const usd0 = n => n == null ? '—' : '$' + Math.round(n).toLocaleString('en-IN');
  const usd2 = n => n == null ? '—' : '$' + Number(n).toFixed(2);
  const mt = n => Math.round(n).toLocaleString('en-IN') + ' MT';
  const cr = n => '₹' + (n * 83.5 / 1e7).toLocaleString('en-IN', {maximumFractionDigits:2}) + ' Cr';
  const statusColor = s => ({pass:'var(--ld-pos)', 'part-load':'var(--ld-warn)', lightering:'var(--ld-warn)', fail:'var(--ld-crit)'}[s] || 'var(--ld-mute)');
  const role = () => (document.body.dataset.role || '');

  function loading(host, what){
    host.innerHTML = `<div class="ld-card lp-empty"><div class="lp-spin"></div>${esc(what)}</div>`;
  }
  function failed(host, err, retry){
    host.innerHTML = `<div class="ld-card lp-empty"><b>Could not load.</b> ${esc(err.message || err)}
      ${retry ? '<button class="ld-btn" type="button" data-retry>Retry</button>' : ''}</div>`;
    const b = host.querySelector('[data-retry]'); if(b) b.onclick = retry;
  }

  /* The cargo the rest of the dashboard is working on. */
  function cargo(){
    const i = (typeof activeInputs === 'object' && activeInputs) || {};
    let origin = ORIGIN_NAME[i.origin] || null;
    if(!origin && typeof activeResult === 'object' && activeResult && activeResult.winner){
      origin = ORIGIN_NAME[activeResult.winner.originKey] || null;
    }
    return {cargo_type: i.cargoType || 'coking_coal', plant: i.plant || 'rourkela',
            origin: origin || 'Australia', parcel: i.qty || 75000, window: i.days || 30};
  }

  /* ======================================================= CHARTER PLANNER */
  const P = {mounted:false, plan:null, constraints:null, busy:false};

  function mountPlanner(){
    const host = $('ldPlanner');
    if(!host || P.mounted) return;
    P.mounted = true;
    const c = cargo();
    host.innerHTML = `
      <div class="ldi-head">
        <div>
          <div class="ld-kicker">Procurement programme</div>
          <div class="ld-h1">Charter Planner</div>
          <p class="ld-lede">From one parcel to a charter programme: the voyages the plant needs over the coming months,
            when each should sail, whether to pay spot or fix a contract, and what the next quarter will cost.
            Every month is a full decision-engine run.</p>
        </div>
      </div>
      <form class="ld-card lp-form" id="lpForm">
        <label>Origin<select id="lpOrigin">${Object.values(ORIGIN_NAME).map(o => `<option${o === c.origin ? ' selected' : ''}>${o}</option>`).join('')}</select></label>
        <label>Parcel per voyage (MT)<input id="lpParcel" type="number" min="10000" max="200000" step="1000" value="${c.parcel}"></label>
        <label>Horizon<select id="lpHorizon">${[3,6,9,12].map(h => `<option value="${h}"${h === 6 ? ' selected' : ''}>${h} months</option>`).join('')}</select></label>
        <label>Total requirement (MT)<input id="lpTotal" type="number" min="0" step="1000" placeholder="parcel × horizon"></label>
        <label>Max voyages / month<select id="lpMax">${[1,2,3,4].map(n => `<option${n === 3 ? ' selected' : ''}>${n}</option>`).join('')}</select></label>
        <button class="ld-btn pri" type="submit" id="lpRun"><svg viewBox="0 0 24 24"><path d="M7 5l12 7-12 7z"/></svg>Build plan</button>
      </form>
      <div id="lpBody"></div>`;
    $('lpForm').addEventListener('submit', e => { e.preventDefault(); runPlanner(); });
    runPlanner();
  }

  async function runPlanner(){
    if(P.busy) return;
    const body = $('lpBody');
    const c = cargo();
    const parcel = Number($('lpParcel').value) || c.parcel;
    const req = {
      cargo_type: c.cargo_type, plant: c.plant, origin: $('lpOrigin').value,
      parcel_size: parcel, horizon_months: Number($('lpHorizon').value),
      total_requirement_mt: Number($('lpTotal').value) || 0,
      max_voyages_per_month: Number($('lpMax').value), window_days: c.window
    };
    P.busy = true; $('lpRun').disabled = true;
    loading(body, 'Running the decision engine for every month of the horizon…');
    try{
      const [plan, constraints] = await Promise.all([
        api('/api/planning/charter-plan', {method:'POST', body: JSON.stringify(req)}),
        api('/api/planning/constraints', {method:'POST', body: JSON.stringify(
          {cargo_type:req.cargo_type, origin:req.origin, parcel_size:req.parcel_size})})
      ]);
      P.plan = plan; P.constraints = constraints;
      try { localStorage.setItem('ld-last-plan', JSON.stringify(plan)); } catch(e){}
      renderPlanner();
    }catch(err){
      let cached = null;
      try { cached = JSON.parse(localStorage.getItem('ld-last-plan') || 'null'); } catch(e){}
      if(cached && !navigator.onLine){ P.plan = cached; P.constraints = null; renderPlanner(true); }
      else failed(body, err, runPlanner);
    }finally{ P.busy = false; $('lpRun').disabled = false; }
  }

  function renderPlanner(fromCache){
    const p = P.plan, body = $('lpBody');
    if(p.status !== 'SUCCESS'){
      body.innerHTML = `<div class="ld-card lp-empty"><b>No feasible programme.</b> ${esc(p.optimizer && p.optimizer.reason)}</div>`;
      return;
    }
    const r = p.recommendation, t = p.timing;
    body.innerHTML = `
      ${fromCache ? '<div class="lp-note warn">Offline: showing the last plan built on this device.</div>' : ''}
      <section class="ld-card lp-final">
        <div class="lp-final-main">
          <div class="ld-kicker">Final charter recommendation</div>
          <div class="lp-final-title">${esc(r.charter_label)}</div>
          <div class="lp-route">
            <span><svg viewBox="0 0 24 24"><circle cx="12" cy="5" r="2"/><path d="M12 7v14M5 13a7 7 0 0014 0M8 11h8"/></svg>${esc(r.load_port || r.origin)}</span><i></i>
            <span class="ship"><svg viewBox="0 0 24 24"><path d="M3 15l2 5h14l2-5z"/><path d="M6 15V9h8v6M9 9V5h3"/></svg>${esc(r.vessel_class)} × ${r.sailings || r.voyages} sailings</span><i></i>
            <span><svg viewBox="0 0 24 24"><circle cx="12" cy="5" r="2"/><path d="M12 7v14M5 13a7 7 0 0014 0M8 11h8"/></svg>${esc(r.discharge_port)}</span><i class="rail"></i>
            <span><svg viewBox="0 0 24 24"><path d="M3 21V11l5 3V11l5 3V7l8 4v10z"/></svg>${esc(PLANTS.find(x => x[0] === r.plant)?.[1] || r.plant)}</span>
          </div>
          <ul class="lp-reasons">${r.reasons.map(x => `<li>${esc(x)}</li>`).join('')}</ul>
        </div>
        <div class="lp-final-side">
          <div class="lp-kv"><span class="ld-label">Expected programme cost</span><b class="ld-num">${usd0(r.expected_cost_usd)}</b><small>₹${r.expected_cost_inr_cr.toLocaleString('en-IN')} Cr · P90 ${usd0(r.p90_cost_usd)}</small></div>
          <div class="lp-kv"><span class="ld-label">Parcels · sailings</span><b class="ld-num">${r.voyages}<span class="lp-unit"> · ${r.sailings || r.voyages}</span></b><small>first sailing ${MN[r.first_sailing_month]}</small></div>
          <div class="lp-kv"><span class="ld-label">Market timing</span><b class="ld-num lp-sig ${t.signal.toLowerCase()}">${t.signal}</b><small>${esc(t.rule)}</small></div>
          <div class="lp-kv"><span class="ld-label">Confidence</span><b class="ld-num">${r.confidence}<span class="lp-unit">/100</span></b><small>${esc(r.confidence_basis)}</small></div>
        </div>
      </section>

      <h3 class="lp-h">Spot vs short- and medium-term contract</h3>
      ${contractChart(p.contracts)}
      <div class="lp-grid3">${p.contracts.map(contractCard).join('')}</div>
      <p class="lp-foot">Contract rate = mean forward rate over the term + term premium (${Object.entries(p.assumptions.term_premiums_pct).map(([k, v]) => `${k} ${v}%`).join(', ')}).
        Score = expected cost + ${p.assumptions.risk_aversion} × cost-at-risk (P90 − expected). Spot volatility ${p.assumptions.monthly_volatility_pct}% a month.</p>

      <div class="lp-split">
        <section class="ld-card lp-pad">
          <div class="lp-cardhead"><div><h4>Multi-voyage schedule</h4>
            <p class="ld-card-sub">${esc(p.optimizer.method)}</p></div>
            <span class="ld-tag pos">${p.optimizer.saving_vs_even_usd > 0 ? 'saves ' + usd0(p.optimizer.saving_vs_even_usd) + ' vs even spread' : 'even spread is optimal'}</span></div>
          ${scheduleChart(p)}
          <details class="lv-fold"><summary>Show the monthly detail</summary>${scheduleTable(p)}</details>
        </section>
        <section class="ld-card lp-pad">
          <div class="lp-cardhead"><div><h4>Short-term cost · next 3 months</h4>
            <p class="ld-card-sub">Expected ${usd0(p.short_term.expected_usd)} (₹${p.short_term.expected_inr_cr} Cr) · P10 ${usd0(p.short_term.p10_usd)} – P90 ${usd0(p.short_term.p90_usd)}</p></div></div>
          ${shortTermChart(p.short_term)}
          <h4 class="lp-mt">Market entry timing</h4>
          <p class="lp-timing"><b class="lp-sig ${t.signal.toLowerCase()}">${t.signal}</b> ${esc(t.reason)}</p>
          ${curveChart(p.months)}
        </section>
      </div>

      <section class="ld-card lp-pad lp-mt">
        <div class="lp-cardhead"><div><h4>Origin &amp; destination port constraints</h4>
          <p class="ld-card-sub">${P.constraints ? `Load port <b>${esc(P.constraints.load_port?.name || '—')}</b> · draft, LOA, beam and handling for every class at every berth — the checks the engine ranks with.` : 'Unavailable offline.'}</p></div></div>
        ${P.constraints ? constraintMatrix(P.constraints) : ''}
      </section>
      <p class="lp-foot">${esc(p.data_source)} Generated ${esc(p.generated_at)}.</p>`;
    body.querySelectorAll('.lp-cell[data-tip]').forEach(cell => cell.addEventListener('click', () => {
      body.querySelectorAll('.lp-cell.open').forEach(x => x !== cell && x.classList.remove('open'));
      cell.classList.toggle('open');
    }));
  }

  /* Expected cost as a bar, the P90 tail as a whisker, the ranking score as a
     tick. The axis starts near the cheapest expectation, not at zero, so the
     differences between structures are visible; every value is labelled. */
  function contractChart(options){
    const lo = Math.min(...options.map(o => o.expected_cost_usd)) * 0.985;
    const hi = Math.max(...options.map(o => o.p90_cost_usd)) * 1.005;
    const x = v => ((v - lo) / (hi - lo) * 100).toFixed(2) + '%';
    return `<section class="ld-card lp-pad lp-range">
      ${options.map(o => `<div class="lp-range-row${o.recommended ? ' on' : ''}">
        <span class="lp-range-name">${esc(o.label.replace(/ \(.*\)/, ''))}${o.recommended ? ' <span class="winner-badge">BEST</span>' : ''}</span>
        <div class="lp-range-track">
          <i class="exp" style="width:${x(o.expected_cost_usd)}"></i>
          <i class="tail" style="left:${x(o.expected_cost_usd)};width:calc(${x(o.p90_cost_usd)} - ${x(o.expected_cost_usd)})"></i>
          <em style="left:${x(o.score_usd)}" title="score"></em>
        </div>
        <span class="lp-range-val">${usd0(o.expected_cost_usd)}<small>P90 ${usd0(o.p90_cost_usd)}</small></span>
      </div>`).join('')}
      <div class="ldc-legend lp-legend"><span><i style="width:14px;height:8px;background:var(--ld-ink)"></i>Expected cost</span>
        <span><i style="width:14px;height:8px;background:repeating-linear-gradient(45deg,var(--ld-warn) 0 3px,transparent 3px 6px)"></i>Cost-at-risk to P90</span>
        <span><i style="width:2px;height:12px;background:var(--ld-text)"></i>Score (lower wins)</span>
        <span>Axis starts at ${usd0(lo)}</span></div>
    </section>`;
  }

  function contractCard(o){
    return `<div class="ld-card lp-contract${o.recommended ? ' on' : ''}">
      <div class="lp-cardhead"><h4>${esc(o.label)}</h4>${o.recommended ? '<span class="winner-badge">RECOMMENDED</span>' : ''}</div>
      <div class="lp-fixed"><div class="lp-fixed-bar"><i style="width:${o.fixed_share_pct}%"></i></div><span>${o.fixed_share_pct}% of freight fixed</span></div>
      <div class="lp-kvs">
        <div><span>Freight</span><b>${o.contract_rate_usd_mt != null ? usd2(o.contract_rate_usd_mt) + '/MT' : 'Spot'}</b></div>
        <div><span>vs spot</span><b>${o.key === 'spot' ? '—' : (o.premium_vs_spot_usd >= 0 ? '+' : '−') + usd0(Math.abs(o.premium_vs_spot_usd))}</b></div>
        <div><span>Risk removed</span><b>${o.key === 'spot' ? '—' : usd0(o.risk_removed_usd)}</b></div>
        <div><span>Cost-at-risk</span><b>${usd0(o.cost_at_risk_usd)}</b></div>
      </div></div>`;
  }

  function scheduleChart(p){
    const rows = p.optimizer.schedule, n = rows.length, W = 560, H = 150, pad = 30;
    const bw = (W - pad * 2) / n;
    const maxStock = Math.max(1, ...rows.map(r => Math.abs(r.stock_end_mt)));
    const maxV = Math.max(1, ...rows.map(r => r.voyages));
    const sy = v => 108 - (v / maxStock) * 40;
    return `<svg class="lp-sched" viewBox="0 0 ${W} ${H}" role="img" aria-label="Parcels per month and plant stock">
      ${rows.map((r, i) => {
        const cx = pad + i * bw + bw / 2;
        const ships = Array.from({length:r.voyages}, (_, k) =>
          `<g transform="translate(${cx - 13} ${96 - (k + 1) * (60 / maxV)})"><path d="M0 8 L26 8 L22 14 L3 14 Z" fill="var(--ld-ink)"/><rect x="3" y="3" width="5" height="5" fill="var(--ld-ink)"/></g>`).join('');
        return `${ships}<text x="${cx}" y="${H - 22}" text-anchor="middle" class="ldi-axis">${MN[r.month]}</text>
          <text x="${cx}" y="${H - 8}" text-anchor="middle" class="ldi-axis" fill="${r.risk_index >= 40 ? 'var(--ld-warn)' : 'var(--ld-mute)'}">risk ${Math.round(r.risk_index)}</text>`;
      }).join('')}
      <line x1="${pad}" x2="${W - pad}" y1="108" y2="108" stroke="var(--ld-hair-strong)"/>
      <path d="${rows.map((r, i) => `${i ? 'L' : 'M'}${pad + i * bw + bw / 2},${sy(r.stock_end_mt)}`).join('')}" fill="none" stroke="var(--ld-pos)" stroke-width="2"/>
      <text x="${W - pad}" y="12" text-anchor="end" class="ldi-axis">ship icons = parcels sailing · green line = plant stock at month end</text>
    </svg>`;
  }

  function scheduleTable(p){
    return `<div class="lp-scroll"><table class="lp-table"><thead><tr>
      <th>Month</th><th>Parcels</th><th>Vessel · berth</th><th>Freight $/MT (P10–P90)</th><th>Landed $/MT</th><th>Risk</th><th>Queue</th><th>Stock end</th></tr></thead><tbody>
      ${p.optimizer.schedule.map(r => r.feasible ? `<tr class="${r.voyages ? 'on' : 'dim'}">
        <td><b>${MN[r.month]}</b></td><td>${r.voyages || '—'}</td>
        <td>${esc(r.vessel_class)} · ${esc(r.port_name)}</td>
        <td>${usd2(r.freight_rate_usd_mt)} <small>(${usd2(r.freight_p10_usd_mt)}–${usd2(r.freight_p90_usd_mt)})</small></td>
        <td>${usd2(r.landed_cost_usd_mt)}</td><td>${Math.round(r.risk_index)}</td>
        <td title="${esc(r.congestion_basis)}">${r.wait_days.toFixed(1)} d</td>
        <td>${mt(r.stock_end_mt)}</td></tr>` : `<tr class="dim"><td>${MN[r.month]}</td><td colspan="7">No feasible option</td></tr>`).join('')}
      </tbody></table></div>
      <p class="lp-foot">Plant consumes ${mt(p.optimizer.schedule[0].consumption_mt)} a month; arrivals must cover consumption to date. Holding stock ahead of need costs ${usd2(p.assumptions.holding_cost_usd_mt_month)}/MT a month.</p>`;
  }

  function shortTermChart(st){
    const max = Math.max(...st.months.map(m => m.p90_usd), 1);
    return `<div class="lp-bars">${st.months.map(m => {
      const h = v => (v / max * 100).toFixed(1) + '%';
      return `<div class="lp-bar"><div class="lp-bar-col">
          <i class="band" style="bottom:${h(m.p10_usd)};height:calc(${h(m.p90_usd)} - ${h(m.p10_usd)})"></i>
          <i class="exp" style="height:${h(m.expected_usd)}"></i></div>
        <b>${usd0(m.expected_usd)}</b><span>${MN[m.month]} · ${m.voyages} voyage${m.voyages === 1 ? '' : 's'}</span></div>`;
    }).join('')}</div>`;
  }

  function curveChart(months){
    const pts = months.filter(m => m.feasible);
    if(pts.length < 2) return '';
    const W = 520, H = 130, pad = 28;
    const lo = Math.min(...pts.map(m => m.freight_p10_usd_mt)), hi = Math.max(...pts.map(m => m.freight_p90_usd_mt));
    const x = i => pad + i * (W - pad * 2) / (pts.length - 1);
    const y = v => H - 20 - (v - lo) / ((hi - lo) || 1) * (H - 40);
    const line = pts.map((m, i) => `${i ? 'L' : 'M'}${x(i)},${y(m.freight_rate_usd_mt)}`).join('');
    const band = pts.map((m, i) => `${i ? 'L' : 'M'}${x(i)},${y(m.freight_p90_usd_mt)}`).join('')
      + pts.slice().reverse().map((m, i) => `L${x(pts.length - 1 - i)},${y(m.freight_p10_usd_mt)}`).join('') + 'Z';
    return `<svg class="lp-curve" viewBox="0 0 ${W} ${H}" role="img" aria-label="Forward freight curve with P10-P90 band">
      <path d="${band}" fill="var(--ld-accent-soft)"/>
      <path d="${line}" fill="none" stroke="var(--ld-accent)" stroke-width="2"/>
      ${pts.map((m, i) => `<circle cx="${x(i)}" cy="${y(m.freight_rate_usd_mt)}" r="3" fill="var(--ld-accent)"/>
        <text x="${x(i)}" y="${H - 4}" text-anchor="middle" class="ldi-axis">${MN[m.month]}</text>
        <text x="${x(i)}" y="${y(m.freight_rate_usd_mt) - 8}" text-anchor="middle" class="ldi-axis">${m.freight_rate_usd_mt.toFixed(1)}</text>`).join('')}
    </svg>`;
  }

  function constraintMatrix(c){
    const berths = c.vessels[0] ? c.vessels[0].berths.map(b => b.port_name) : [];
    const cell = (status, label, checks, reason) => {
      const tip = (checks || []).map(k => `${k.check}: ${k.value} vs ${k.limit} — ${k.status}`).join('\n') + (reason ? '\n' + reason : '');
      return `<td><div class="lp-cell" data-tip="${esc(tip)}" style="--c:${statusColor(status)}"><i></i>${esc(label)}
        <div class="lp-tip">${esc(tip).replace(/\n/g, '<br>')}</div></div></td>`;
    };
    return `<div class="lp-scroll"><table class="lp-table lp-matrix"><thead><tr>
      <th>Class (LOA × beam, draft)</th><th>Load port</th>${berths.map(b => `<th>${esc(b)}</th>`).join('')}</tr></thead><tbody>
      ${c.vessels.map(v => {
        const lp = v.load_port;
        const lpStatus = !lp.feasible ? 'fail' : lp.part_loaded ? 'part-load' : 'pass';
        return `<tr><td><b>${esc(v.vessel_class)}</b><br><small>${v.loa_m} × ${v.beam_m} m, ${v.draft_m} m · lifts ${mt(v.lift_mt)}</small></td>
          ${cell(lpStatus, lpStatus === 'part-load' ? 'Part-load' : lpStatus === 'pass' ? 'Fits' : 'No', lp.checks, lp.reason)}
          ${v.berths.map(b => {
            const s = !b.feasible ? 'fail' : b.lightering ? 'lightering' : 'pass';
            return cell(s, s === 'pass' ? 'Fits' : s === 'lightering' ? 'Lighter' : 'No', b.checks, b.reason);
          }).join('')}</tr>`;
      }).join('')}</tbody></table></div>
      <p class="lp-foot">Click a cell for the individual checks. ${esc(c.load_port_basis)}</p>`;
  }

  /* ========================================================== MARKET VIEW */
  const M = {mounted:false};

  function mountMarket(){
    const host = $('ldMarket');
    if(!host || M.mounted) return;
    M.mounted = true;
    const c = cargo();
    host.innerHTML = `
      <div class="ldi-head"><div>
        <div class="ld-kicker">Supply side</div>
        <div class="ld-h1">Market &amp; Congestion</div>
        <p class="ld-lede">What the plant needs against what the coast can discharge, how berth queues move through the year,
          and which months are cheapest and calmest to ship in.</p></div>
        <form class="lp-inline" id="lmForm">
          <label>Plant<select id="lmPlant">${PLANTS.map(([k, n]) => `<option value="${k}"${k === c.plant ? ' selected' : ''}>${n}</option>`).join('')}<option value="all">All SAIL plants</option></select></label>
          <label>Origin<select id="lmOrigin"><option value="any">All lanes</option>${Object.values(ORIGIN_NAME).map(o => `<option>${o}</option>`).join('')}</select></label>
        </form></div>
      <div id="lmDemand"></div>
      <div class="lp-split lp-mt"><div id="lmCongestion"></div><div id="lmSeasonal"></div></div>`;
    $('lmPlant').onchange = $('lmOrigin').onchange = loadMarket;
    loadMarket();
  }

  async function loadMarket(){
    const c = cargo();
    const plant = $('lmPlant').value, origin = $('lmOrigin').value;
    ['lmDemand','lmCongestion','lmSeasonal'].forEach(id => loading($(id), 'Loading…'));
    const q = s => encodeURIComponent(s);
    api(`/api/market/demand-supply?cargo_type=${q(c.cargo_type)}&plant=${q(plant)}&origin=${q(origin)}`)
      .then(renderDemand).catch(e => failed($('lmDemand'), e, loadMarket));
    api('/api/market/congestion').then(renderCongestion).catch(e => failed($('lmCongestion'), e, loadMarket));
    api(`/api/market/seasonal?origin=${q(origin)}`).then(renderSeasonal).catch(e => failed($('lmSeasonal'), e, loadMarket));
  }

  function renderDemand(d){
    const W = 760, H = 210, pad = 36, n = d.months.length;
    const max = Math.max(...d.months.map(m => Math.max(m.demand_mt, m.discharge_capacity_mt))) * 1.08;
    const bw = (W - pad * 2) / n;
    const y = v => H - 26 - v / max * (H - 50);
    const tLo = Math.min(...d.months.map(m => m.freight_tightness_index)), tHi = Math.max(...d.months.map(m => m.freight_tightness_index));
    const ty = v => 16 + (1 - (v - tLo) / ((tHi - tLo) || 1)) * 50;
    const tone = {Comfortable:'var(--ld-pos)', Adequate:'var(--ld-warn)', Tight:'var(--ld-crit)'};
    $('lmDemand').innerHTML = `<section class="ld-card lp-pad">
      <div class="lp-cardhead"><div><h4>Demand / supply balance — ${esc(d.cargo_type)}</h4>
        <p class="ld-card-sub">${esc(d.summary)}</p></div>
        <span class="ld-tag">${mt(d.annual_import_requirement_mt)} / year</span></div>
      <svg class="lp-demand" viewBox="0 0 ${W} ${H}" role="img" aria-label="Monthly demand against discharge capacity">
        ${d.months.map((m, i) => {
          const x0 = pad + i * bw;
          return `<rect x="${x0 + bw * .14}" y="${y(m.discharge_capacity_mt)}" width="${bw * .34}" height="${H - 26 - y(m.discharge_capacity_mt)}" fill="var(--ld-accent)" opacity=".75" rx="2"><title>Capacity ${mt(m.discharge_capacity_mt)}</title></rect>
            <rect x="${x0 + bw * .52}" y="${y(m.demand_mt)}" width="${bw * .34}" height="${H - 26 - y(m.demand_mt)}" fill="var(--ld-ink)" rx="2"><title>Demand ${mt(m.demand_mt)}</title></rect>
            <circle cx="${x0 + bw / 2}" cy="${H - 8}" r="4" fill="${tone[m.balance]}"><title>${m.balance}: coverage ${m.coverage_ratio}×, freight ${m.freight_tightness_index}% of mean</title></circle>
            <text x="${x0 + bw / 2}" y="${H - 14}" text-anchor="middle" class="ldi-axis">${MN[m.month]}</text>`;
        }).join('')}
        <path d="${d.months.map((m, i) => `${i ? 'L' : 'M'}${pad + i * bw + bw / 2},${ty(m.freight_tightness_index)}`).join('')}" fill="none" stroke="var(--ld-warn)" stroke-width="2" stroke-dasharray="4 3"/>
      </svg>
      <div class="ldc-legend lp-legend"><span><i style="width:10px;height:10px;background:var(--ld-accent)"></i>Discharge capacity available to SAIL</span>
        <span><i style="width:10px;height:10px;background:var(--ld-ink)"></i>Plant import requirement</span>
        <span><i style="width:16px;border-top:2px dashed var(--ld-warn)"></i>Freight tightness (model)</span>
        <span><i style="width:8px;height:8px;border-radius:50%;background:var(--ld-crit)"></i>Tight month</span></div>
      <p class="lp-foot">${esc(d.demand_basis)} ${esc(d.supply_basis)}</p></section>`;
  }

  function renderCongestion(c){
    const max = Math.max(...c.ports.flatMap(p => p.months.map(m => m.wait_days)));
    const shade = v => `color-mix(in srgb, var(--ld-crit) ${Math.round(v / max * 70)}%, var(--ld-accent-soft))`;
    $('lmCongestion').innerHTML = `<section class="ld-card lp-pad">
      <div class="lp-cardhead"><div><h4>Congestion forecast — berth queue (days)</h4>
        <p class="ld-card-sub">${esc(c.basis)}</p></div></div>
      <div class="lp-scroll"><table class="lp-table lp-heat"><thead><tr><th>Berth</th>${c.months.map(m => `<th>${MN[m]}</th>`).join('')}</tr></thead><tbody>
      ${c.ports.map(p => `<tr><td><b>${esc(p.port_name)}</b></td>${p.months.map(m =>
        `<td style="background:${shade(m.wait_days)}" title="${esc(m.reason)} ×${m.factor}">${m.wait_days.toFixed(1)}</td>`).join('')}</tr>`).join('')}
      </tbody></table></div></section>`;
  }

  function renderSeasonal(s){
    $('lmSeasonal').innerHTML = `<section class="ld-card lp-pad">
      <div class="lp-cardhead"><div><h4>Seasonal analysis</h4>
        <p class="ld-card-sub">Best months: <b>${s.best_months.map(m => MN[m]).join(', ')}</b> · avoid: <b>${s.worst_months.map(m => MN[m]).join(', ')}</b></p></div></div>
      <div class="lp-season">${s.months.map(m => `<div class="lp-month ${s.best_months.includes(m.month) ? 'best' : s.worst_months.includes(m.month) ? 'worst' : ''}">
        <b>${MN[m.month]}</b><span class="lp-rank">#${m.rank}</span>
        <small>${usd2(m.freight_usd_mt)}/MT</small>
        <small>weather ${m.weather_risk}</small>
        <small>queue ${m.avg_wait_days.toFixed(1)} d</small>
        ${m.ports_affected.length ? `<small class="lp-wx">${m.ports_affected.length} berth${m.ports_affected.length > 1 ? 's' : ''} in monsoon</small>` : ''}
      </div>`).join('')}</div>
      <p class="lp-foot">${esc(s.basis)}</p></section>`;
  }

  /* ======================================================= ALIGNMENT CHECK */
  const A = {mounted:false};

  function mountAlignment(){
    const host = $('ldAlignment');
    if(!host || A.mounted) return;
    A.mounted = true;
    host.innerHTML = `<div class="ldi-head"><div>
        <div class="ld-kicker">Assurance</div>
        <div class="ld-h1">Problem-Statement Alignment Check</div>
        <p class="ld-lede">Every requirement mapped to the feature that meets it, and a live probe of that feature run on the server now.
          PARTIAL means it works with a stated limitation — never rounded up.</p></div>
        <button class="ld-btn pri" id="laRun" type="button"><svg viewBox="0 0 24 24"><path d="M7 5l12 7-12 7z"/></svg>Run check</button></div>
      <div id="laBody"></div>`;
    $('laRun').onclick = runAlignment;
    runAlignment();
  }

  async function runAlignment(){
    const body = $('laBody');
    loading(body, 'Probing every requirement…');
    try{
      const a = await api('/api/system/alignment');
      const chip = s => `<span class="lp-chip ${s === 'MET' ? 'pass' : s === 'PARTIAL' ? 'part' : 'fail'}">${s}</span>`;
      const cls = s => s === 'MET' ? 'pass' : s === 'PARTIAL' ? 'part' : 'fail';
      const C = 2 * Math.PI * 46, seg = n => n / a.total * C;
      const met = seg(a.counts.MET), part = seg(a.counts.PARTIAL), fail = seg(a.counts['NOT MET']);
      body.innerHTML = `<section class="ld-card lp-pad la-top">
          <svg viewBox="0 0 120 120" class="la-donut" role="img" aria-label="${a.counts.MET} met, ${a.counts.PARTIAL} partial, ${a.counts['NOT MET']} not met">
            <circle cx="60" cy="60" r="46" fill="none" stroke="var(--ld-track)" stroke-width="14"/>
            <circle cx="60" cy="60" r="46" fill="none" stroke="var(--ld-pos)" stroke-width="14" stroke-dasharray="${met} ${C}" transform="rotate(-90 60 60)"/>
            <circle cx="60" cy="60" r="46" fill="none" stroke="var(--ld-warn)" stroke-width="14" stroke-dasharray="${part} ${C}" stroke-dashoffset="${-met}" transform="rotate(-90 60 60)"/>
            <circle cx="60" cy="60" r="46" fill="none" stroke="var(--ld-crit)" stroke-width="14" stroke-dasharray="${fail} ${C}" stroke-dashoffset="${-(met + part)}" transform="rotate(-90 60 60)"/>
            <text x="60" y="60" text-anchor="middle" class="la-big">${a.coverage_pct}%</text>
            <text x="60" y="76" text-anchor="middle" class="ldi-axis">coverage</text>
          </svg>
          <div class="la-counts">
            <div><b class="pos">${a.counts.MET}</b><span>met</span></div>
            <div><b class="warn">${a.counts.PARTIAL}</b><span>partial</span></div>
            <div><b class="crit">${a.counts['NOT MET']}</b><span>not met</span></div>
            <p class="lp-foot">${a.total} requirements probed live in ${a.duration_ms} ms. Hover a tile for its evidence.</p>
          </div>
        </section>
        <div class="la-grid">${a.requirements.map(r => `<div class="la-tile ${cls(r.status)}" title="${esc(r.evidence)}">
            <span class="la-id">${r.id}</span><i></i><b>${esc(r.requirement)}</b><small>${esc(r.feature.split(';')[0])}</small></div>`).join('')}</div>
        <details class="lv-fold"><summary>Show the evidence table</summary>
        <section class="ld-card lp-pad"><div class="lp-scroll"><table class="lp-table lp-align"><thead><tr>
          <th>#</th><th>Requirement</th><th>Status</th><th>Where</th><th>Live evidence</th></tr></thead><tbody>
          ${a.requirements.map(r => `<tr><td>${r.id}</td><td><b>${esc(r.requirement)}</b></td><td>${chip(r.status)}</td>
            <td><small>${esc(r.feature)}</small></td><td>${esc(r.evidence)}</td></tr>`).join('')}
        </tbody></table></div><p class="lp-foot">${esc(a.problem_statement)}. ${esc(a.note)}</p></section></details>`;
    }catch(err){ failed(body, err, runAlignment); }
  }

  /* ============================================== COMMAND CENTRE CHARTER */
  /* The Command Centre used to price spot and period contracts in the browser
     with invented multipliers. It now shows the planner's own answer for the
     cargo on screen and links to the full comparison. */
  const planCache = {};
  renderCharterStrategy = async function(result, inputs){
    const host = $('charterStrategyHost');
    if(!host || !result || !result.winner) return;
    const origin = ORIGIN_NAME[result.winner.originKey] || 'Australia';
    const key = [inputs.cargoType, origin, inputs.plant, inputs.qty, inputs.days].join('|');
    host.innerHTML = `<section class="ld-card lp-pad lp-mini"><div class="lp-spin"></div>Pricing spot against short- and medium-term contracts…</section>`;
    try{
      const plan = planCache[key] || (planCache[key] = await api('/api/planning/charter-plan', {method:'POST', body: JSON.stringify({
        cargo_type: inputs.cargoType, origin, plant: inputs.plant, parcel_size: inputs.qty,
        window_days: inputs.days, horizon_months: 6})}));
      if(plan.status !== 'SUCCESS'){ host.innerHTML = ''; return; }
      const r = plan.recommendation;
      host.innerHTML = `<section class="ld-card lp-pad lp-mini">
        <div class="lp-cardhead"><div><div class="ld-kicker">Charter structure · 6-month programme</div>
          <h4>${esc(r.charter_label)}</h4>
          <p class="ld-card-sub">${esc(r.reasons[1])} Timing: <b>${r.timing_signal}</b>.</p></div>
          <button class="ld-btn" type="button" onclick="switchPanel('planner')">Open Charter Planner</button></div>
        <div class="lp-kvs lp-kvs-row">${plan.contracts.map(o => `<div class="${o.recommended ? 'on' : ''}"><span>${esc(o.label)}</span>
          <b>${usd0(o.expected_cost_usd)}</b><small>P90 ${usd0(o.p90_cost_usd)}</small></div>`).join('')}</div></section>`;
    }catch(err){ host.innerHTML = ''; }
  };

  /* ============================================================ EMERGENCY */
  function mountEmergency(){
    const btn = $('openEmergencyBtn');
    if(!btn) return;
    const box = document.createElement('div');
    box.className = 'drawer-right';
    box.id = 'emergencyDrawer';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-label', 'Emergency contacts');
    box.innerHTML = `<div class="drawer-header"><div style="font-weight:700;">Emergency contacts</div>
      <button class="close-btn" style="color:#FFF;" onclick="closeDrawerById('emergencyDrawer')">✕</button></div>
      <div class="drawer-body" id="emergencyBody"></div>`;
    document.body.appendChild(box);
    btn.addEventListener('click', () => { toggleDrawer('emergencyDrawer'); loadContacts(); });
  }

  async function loadContacts(){
    const body = $('emergencyBody');
    let rows = null, stale = false;
    try{
      rows = await api('/api/ops/emergency');
      try { localStorage.setItem('ld-emergency', JSON.stringify(rows)); } catch(e){}
    }catch(err){
      try { rows = JSON.parse(localStorage.getItem('ld-emergency') || 'null'); stale = true; } catch(e){}
      if(!rows){ body.innerHTML = `<p class="lp-foot">Contacts unavailable offline. In an emergency at sea call <b>1554</b> (Indian Coast Guard) or <b>112</b>.</p>`; return; }
    }
    const admin = role() === 'Admin';
    body.innerHTML = (stale ? '<div class="lp-note warn">Offline — showing contacts saved on this device.</div>' : '')
      + rows.map(c => {
        const dial = /^[+\d][\d\s-]*$/.test(c.phone);
        return `<div class="lp-contact${c.verified ? '' : ' pending'}" data-id="${c.id}">
          <div class="lp-contact-head"><span class="ld-label">${esc(c.category)}</span>${c.verified ? '<span class="lp-chip pass">verified</span>' : '<span class="lp-chip part">to configure</span>'}</div>
          <b>${esc(c.name)}</b>
          ${dial ? `<a class="lp-phone" href="tel:${esc(c.phone.replace(/\s/g, ''))}">${esc(c.phone)}</a>` : `<span class="lp-phone muted">${esc(c.phone)}</span>`}
          <small>${esc(c.available)}${c.notes ? ' · ' + esc(c.notes) : ''}</small>
          ${admin ? `<button class="ld-btn lp-edit" type="button" data-edit="${c.id}">Edit</button>` : ''}</div>`;
      }).join('')
      + (admin ? '<p class="lp-foot">Admin: edit a line to add the port, agent and SAIL duty numbers. Changes are audit-logged.</p>' : '');
    body.querySelectorAll('[data-edit]').forEach(b => b.onclick = () => editContact(rows.find(r => String(r.id) === b.dataset.edit)));
  }

  function editContact(c){
    const card = document.querySelector(`.lp-contact[data-id="${c.id}"]`);
    card.innerHTML = `<form class="lp-contact-form">
      <label>Name<input name="name" value="${esc(c.name)}" required></label>
      <label>Phone<input name="phone" value="${esc(c.phone)}" required></label>
      <label>Email<input name="email" value="${esc(c.email || '')}"></label>
      <label>Availability<input name="available" value="${esc(c.available || '')}"></label>
      <label>Notes<input name="notes" value="${esc(c.notes || '')}"></label>
      <label class="lp-check"><input type="checkbox" name="verified"${c.verified ? ' checked' : ''}> Verified number</label>
      <div class="lp-row"><button class="ld-btn pri" type="submit">Save</button><button class="ld-btn" type="button" data-cancel>Cancel</button></div></form>`;
    const form = card.querySelector('form');
    card.querySelector('[data-cancel]').onclick = loadContacts;
    form.onsubmit = async e => {
      e.preventDefault();
      const f = new FormData(form);
      const payload = {category: c.category, sort_order: c.sort_order, verified: f.get('verified') === 'on'};
      ['name','phone','email','available','notes'].forEach(k => payload[k] = String(f.get(k) || '').trim());
      try { await api(`/api/ops/emergency/${c.id}`, {method:'PUT', body: JSON.stringify(payload)}); loadContacts(); }
      catch(err){ alert('Could not save: ' + err.message); }
    };
  }

  /* ========================================================= ALERT CENTRE */
  const N = {alerts:[], timer:0};
  const seen = () => { try { return new Set(JSON.parse(localStorage.getItem('ld-alerts-seen') || '[]')); } catch(e){ return new Set(); } };
  const markSeen = ids => { try { localStorage.setItem('ld-alerts-seen', JSON.stringify([...new Set([...seen(), ...ids])].slice(-300))); } catch(e){} };

  async function pollAlerts(){
    const c = cargo();
    try{
      const feed = await api(`/api/ops/alerts?cargo_type=${encodeURIComponent(c.cargo_type)}&plant=${encodeURIComponent(c.plant)}`);
      const before = seen();
      const fresh = feed.alerts.filter(a => !before.has(a.id) && !N.alerts.some(x => x.id === a.id));
      N.alerts = feed.alerts;
      if(fresh.length && 'Notification' in window && Notification.permission === 'granted' && document.hidden){
        fresh.slice(0, 3).forEach(a => { try { new Notification('LOHA DRISHTI · ' + a.title, {body: a.text, tag: a.id, icon: '/static/loha-drishti-logo.svg'}); } catch(e){} });
      }
      drawServerAlerts();
    }catch(err){ /* the engine-derived alerts still show */ }
  }

  function drawServerAlerts(){
    const body = $('notifyBody');
    if(!body) return;
    let host = $('ldServerAlerts');
    if(!host){ host = document.createElement('div'); host.id = 'ldServerAlerts'; body.appendChild(host); }
    const read = seen();
    const tones = {warn:'saffron', risk:'red', info:'blue'};
    const canNotify = 'Notification' in window;
    host.innerHTML = `<div class="lp-alerts-head"><span class="ld-label">Forecast alerts · next 3 months</span>
        ${canNotify && Notification.permission !== 'granted' ? `<button class="ld-btn" type="button" id="lpNotifyOn">${Notification.permission === 'denied' ? 'Notifications blocked' : 'Enable desktop alerts'}</button>` : canNotify ? '<span class="lp-chip pass">desktop alerts on</span>' : ''}</div>`
      + (N.alerts.length ? N.alerts.map(a => { const t = tones[a.severity] || 'blue';
          return `<div class="lp-alert${read.has(a.id) ? '' : ' unread'}" style="background:var(--${t}-bg);border-color:var(--${t}-border)">
            <b style="color:var(--${t === 'saffron' ? 'saffron-dark' : t})">${esc(a.title)}</b><br>${esc(a.text)}
            <div class="lp-alert-src">${esc(a.category)}</div></div>`; }).join('')
        : '<div class="lp-foot">No forecast alerts.</div>');
    const on = $('lpNotifyOn');
    if(on) on.onclick = () => Notification.requestPermission().then(drawServerAlerts);
    updateBadge();
  }

  function updateBadge(){
    const badge = $('alertCount');
    if(!badge) return;
    const engine = document.querySelectorAll('#notifyBody > div:not(#ldServerAlerts)').length;
    const unread = N.alerts.filter(a => !seen().has(a.id)).length;
    const engineCount = (typeof activeResult === 'object' && activeResult) ? engine : 0;
    const total = engineCount + unread;
    badge.textContent = total;
    badge.hidden = total === 0;
  }

  const _refreshAlerts = refreshAlerts;
  refreshAlerts = function(){
    const out = _refreshAlerts.apply(this, arguments);
    drawServerAlerts();
    return out;
  };

  function mountAlerts(){
    const btn = $('openNotifyBtn');
    if(btn) btn.addEventListener('click', () => setTimeout(() => { markSeen(N.alerts.map(a => a.id)); updateBadge(); }, 1500));
    pollAlerts();
    N.timer = setInterval(pollAlerts, 10 * 60 * 1000);
  }

  /* ========================================================= OFFLINE MODE */
  function mountOffline(){
    const bar = document.createElement('div');
    bar.className = 'lp-offline';
    bar.setAttribute('role', 'status');
    bar.innerHTML = `<b>Offline.</b> Showing saved reference data and the last plan on this device; the engine falls back to a labelled estimate. Changes resume when the network returns.`;
    document.body.appendChild(bar);
    const sync = () => {
      bar.classList.toggle('on', !navigator.onLine);
      if(navigator.onLine && typeof setEngineSource === 'function' && ENGINE_SOURCE === 'OFFLINE' && REFERENCE_SYNCED) setEngineSource('BACKEND');
    };
    addEventListener('online', () => { sync(); pollAlerts(); });
    addEventListener('offline', sync);
    sync();
    if('serviceWorker' in navigator){
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    }
  }

  /* ================================================================ HOOKS */
  const _switch = switchPanel;
  switchPanel = function(name){
    const out = _switch.apply(this, arguments);
    const shown = document.querySelector('.panel.active');
    const id = shown ? shown.id : '';
    if(id === 'panel-planner') mountPlanner();
    if(id === 'panel-market') mountMarket();
    if(id === 'panel-alignment') mountAlignment();
    return out;
  };

  mountEmergency();
  mountAlerts();
  mountOffline();
})();
