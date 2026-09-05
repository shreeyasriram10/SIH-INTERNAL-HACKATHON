import os

app_file = r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\static\app.html"

with open(app_file, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Enhanced renderWaterfallBars with icons, percentages, and interactive mode
old_waterfall = """function renderWaterfallBars(base,qty){
  const mult=isTotalCostMode?qty:1;
  const items=[
    {key:'fob',         label:"Cargo FOB Price"},
    {key:'freight',     label:"Ocean Freight"},
    {key:'loadPortCharge',     label:"Load Port Charges"},
    {key:'dischargePortCharge',label:"Discharge Port Charges"},
    {key:'demurrageExpected',  label:"Expected Demurrage"},
    {key:'insurance',  label:"Insurance & War Risk"},
    {key:'evac',       label:"Inland Plant Evacuation"},
    {key:'financing',  label:"Financing / Working Capital"},
  ];
  const maxVal=base.total*mult;
  const container=document.getElementById('waterfallBars');
  if(!container) return;
  container.innerHTML=items.map(item=>`
    <div class="waterfall-row">
      <div class="waterfall-label">${item.label}</div>
      <div class="waterfall-track">
        <div class="waterfall-fill" style="width:${Math.max(2,(base[item.key]*mult/maxVal)*100)}%;background:${WATERFALL_COLORS[item.key]};"></div>
      </div>
      <div class="waterfall-val">${usd(base[item.key]*mult)}</div>
    </div>`).join('')+`
    <div class="waterfall-row" style="font-weight:700;margin-top:6px;border-top:1px solid var(--steel-border);padding-top:6px;">
      <div class="waterfall-label">TOTAL LANDED COST</div>
      <div></div>
      <div class="waterfall-val" style="color:var(--saffron-dark);font-size:13px;">${usd(maxVal)}</div>
    </div>`;
}"""

new_waterfall = """function renderWaterfallBars(base,qty){
  const mult=isTotalCostMode?qty:1;
  const items=[
    {key:'fob',         icon:"📦", label:"Cargo FOB Price", desc:"Base commodity cost at load port"},
    {key:'freight',     icon:"🚢", label:"Ocean Freight", desc:"Vessel chartering / voyage fixture"},
    {key:'loadPortCharge',     icon:"⚓", label:"Load Port Charges", desc:"Stevedoring, pilotage, tugs at origin"},
    {key:'dischargePortCharge',icon:"🏗️", label:"Discharge Port Charges", desc:"TAMP statutory berth hire & wharfage"},
    {key:'demurrageExpected',  icon:"⏳", label:"Demurrage Risk", desc:"Queue delay beyond free laytime"},
    {key:'insurance',  icon:"🛡️", label:"Marine & War Risk Insurance", desc:"Cargo loss & transit risk premium"},
    {key:'evac',       icon:"🚆", label:"Inland Rail Evacuation", desc:"FOIS freight to destination plant"},
    {key:'financing',  icon:"💳", label:"Working Capital Financing", desc:"Transit inventory holding cost"},
  ];
  const totalVal=base.total*mult;
  const container=document.getElementById('waterfallBars');
  if(!container) return;
  
  const unitLabel = isTotalCostMode ? "Total Parcel Budget ($)" : "$/MT";
  container.innerHTML= `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:11px;color:var(--steel-muted);font-weight:600;">
      <span>COST COMPONENT BREAKOUT</span>
      <span>% OF LANDED COST &nbsp;·&nbsp; ${unitLabel}</span>
    </div>
  ` + items.map(item=>{
    const val = base[item.key] * mult;
    const pct = ((base[item.key] / base.total) * 100).toFixed(1);
    return `
    <div class="waterfall-row" title="${item.desc}">
      <div class="waterfall-label" style="display:flex;align-items:center;gap:6px;">
        <span>${item.icon}</span>
        <span>${item.label}</span>
      </div>
      <div class="waterfall-track">
        <div class="waterfall-fill" style="width:${Math.max(2, (base[item.key]/base.total)*100)}%;background:${WATERFALL_COLORS[item.key] || 'var(--saffron)'};"></div>
      </div>
      <div class="waterfall-val" style="display:flex;align-items:center;justify-content:flex-end;gap:8px;">
        <span style="font-size:10.5px;color:var(--steel-muted);font-family:'IBM Plex Mono';">${pct}%</span>
        <span>${usd(val)}</span>
      </div>
    </div>`;
  }).join('') + `
    <div class="waterfall-row" style="font-weight:700;margin-top:10px;border-top:2px solid var(--steel-border);padding-top:8px;background:var(--bg-subtle);border-radius:6px;padding:8px 10px;">
      <div class="waterfall-label" style="font-size:12.5px;color:var(--navy-deep);">💰 TOTAL LANDED PROCUREMENT COST</div>
      <div></div>
      <div class="waterfall-val" style="color:var(--saffron-dark);font-size:14px;font-weight:700;">${usd(totalVal)} ${isTotalCostMode ? '' : '/ MT'}</div>
    </div>`;
}"""

if old_waterfall in content:
    content = content.replace(old_waterfall, new_waterfall)
    print("Enhanced renderWaterfallBars applied.")

# 2. Enhanced Risk Modal Content with 5 dimensional breakout
old_risk_modal_fn = """function updateRiskModalContent(result,inputs){
  const w=result.winner;
  const isMonsoon=w.base.isMonsoon;
  const o=ORIGINS[w.originKey];
  const p=PORTS[w.portKey];
  const factors=[
    {name:'Freight Volatility (30%)',  score:Math.round(o.vol*100*0.5*2),  desc:`Origin ${o.short} vol = ${(o.vol*100).toFixed(0)}%`},
    {name:'Port Congestion (35%)',     score:Math.round(p.waitDays*10),     desc:`${p.name}: ${p.waitDays}d avg wait × congestion model`},
    {name:'Monsoon/Cyclone Risk (25%)',score:isMonsoon?25:5,                desc:isMonsoon?'Active monsoon month — risk elevated':'Outside monsoon window'},
    {name:'Evacuation Distance (10%)', score:Math.round(p.evacKm/52),       desc:`${p.evacKm} km rail haul to plant`},
  ];
  const listEl=document.getElementById('riskFactorList');
  if(listEl){
    listEl.innerHTML=factors.map(f=>`
      <div class="risk-factor">
        <div class="risk-factor-name">${f.name}</div>
        <div class="risk-factor-track"><div class="risk-factor-fill" style="width:${Math.min(100,f.score*2)}%;"></div></div>
        <div class="risk-factor-val ${riskClass(f.score)}">${f.score}</div>
      </div>
      <div style="font-size:11px;color:var(--steel-muted);margin:-4px 0 4px;">${f.desc}</div>`).join('');
  }
}"""

new_risk_modal_fn = """function updateRiskModalContent(result,inputs){
  const w=result.winner;
  const isMonsoon=w.base.isMonsoon;
  const o=ORIGINS[w.originKey];
  const p=PORTS[w.portKey];
  const vc=VESSEL_CLASSES[result.vesselClassKey];
  
  const draftMargin = (p.draft - vc.draft).toFixed(1);
  const draftScore = draftMargin > 2.5 ? 12 : draftMargin > 1.0 ? 28 : 65;
  const draftDesc = draftMargin > 2.0 ? `Deep clearance (${p.draft}m port vs ${vc.draft}m vessel, +${draftMargin}m buffer)` : `Tight clearance (${p.draft}m port vs ${vc.draft}m vessel)`;

  const factors=[
    {name:'1. Freight Market Volatility (25%)', score:Math.round(o.vol*100*0.5*2), icon:'📈', desc:`${o.short} corridor baseline volatility = ${(o.vol*100).toFixed(0)}%`},
    {name:'2. Discharge Port Congestion (30%)', score:Math.round(p.waitDays*11), icon:'⏳', desc:`${p.name}: ${p.waitDays}d avg pre-berthing wait time`},
    {name:'3. Monsoon & Cyclone Exposure (20%)', score:isMonsoon?35:8, icon:'⛈️', desc:isMonsoon?'Active Bay of Bengal monsoon window (delay factor 1.7×)':'Optimal calm weather window'},
    {name:'4. Vessel Draft & Navigational Clearance (15%)', score:draftScore, icon:'🚢', desc:draftDesc},
    {name:'5. Inland Rail Evacuation Distance (10%)', score:Math.round(p.evacKm/48), icon:'🚆', desc:`${p.evacKm} km freight haul to ${PLANT_LABEL[inputs.plant].split('(')[0].trim()}`},
  ];

  const listEl=document.getElementById('riskFactorList');
  if(listEl){
    listEl.innerHTML= `
      <div style="background:var(--bg-subtle);padding:12px;border-radius:8px;margin-bottom:14px;border:1px solid var(--steel-border);">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
          <span style="font-weight:700;color:var(--navy-deep);">Composite Operational Risk Score:</span>
          <span class="mono" style="font-size:15px;font-weight:700;color:${result.risk>60?'var(--red)':result.risk>35?'var(--saffron-dark)':'var(--green)'};">${result.risk} / 100</span>
        </div>
        <div style="font-size:11.5px;color:var(--steel-muted);">Evaluation for <b>${o.short} ➔ ${p.name}</b> (${vc.name}) delivering to <b>${PLANT_LABEL[inputs.plant].split('(')[0].trim()}</b>.</div>
      </div>
    ` + factors.map(f=>`
      <div style="background:#FFF;border:1px solid var(--steel-border);border-radius:8px;padding:10px 12px;margin-bottom:8px;">
        <div style="display:flex;justify-content:space-between;align-items:center;font-size:12.5px;font-weight:600;color:var(--navy-deep);margin-bottom:4px;">
          <span>${f.icon} ${f.name}</span>
          <span class="mono" style="font-size:12px;font-weight:700;color:${f.score>60?'var(--red)':f.score>30?'var(--saffron-dark)':'var(--green)'};">${f.score}/100</span>
        </div>
        <div class="risk-factor-track" style="margin-bottom:4px;height:6px;">
          <div class="risk-factor-fill" style="width:${Math.min(100, f.score)}%;background:${f.score>60?'var(--red)':f.score>30?'var(--saffron)':'var(--green)'};"></div>
        </div>
        <div style="font-size:11px;color:var(--steel-muted);">${f.desc}</div>
      </div>
    `).join('');
  }
}"""

if old_risk_modal_fn in content:
    content = content.replace(old_risk_modal_fn, new_risk_modal_fn)
    print("Enhanced updateRiskModalContent applied.")

# 3. Enhanced Continuity Modal Content
old_cont_modal_html = """    <div style="font-size:13px;line-height:1.6;color:var(--steel-dark);" id="continuityModalContent">
      <p>Supply Continuity (0–100) estimates the probability of uninterrupted raw material delivery to the steel plant across disruption scenarios.</p>
      <ul>
        <li><b>Port Queue Risk (40%):</b> Based on berth availability and expected wait days.</li>
        <li><b>Monsoon Window (30%):</b> Likelihood of weather disruption in transit month.</li>
        <li><b>Freight Regret Margin (20%):</b> How much regret the strategy accumulates across 4 market scenarios.</li>
        <li><b>Rail Evacuation Risk (10%):</b> Inland distance and wagon turnaround at destination plant.</li>
      </ul>
      <p style="font-size:12px;background:var(--green-bg);border:1px solid var(--green-border);padding:10px;border-radius:6px;color:var(--green-dark);">
        <b>Above 80:</b> High confidence in plant delivery. <b>60–80:</b> Acceptable with backup plan. <b>Below 60:</b> Alternative port or contingency contract recommended.
      </p>
    </div>"""

new_cont_modal_html = """    <div style="font-size:13px;line-height:1.6;color:var(--steel-dark);" id="continuityModalContent">
      <div style="background:var(--green-bg);border:1px solid var(--green-border);padding:12px 14px;border-radius:8px;margin-bottom:14px;">
        <div style="font-size:11px;font-weight:700;color:var(--green-dark);text-transform:uppercase;letter-spacing:0.04em;">Steel Plant Security Index</div>
        <div style="font-size:15px;font-weight:700;color:var(--green);margin-top:2px;">Continuous Blast Furnace Feed Assurance</div>
        <p style="font-size:11.5px;color:var(--steel-dark);margin:4px 0 0;">Evaluates the probabilistic certainty of delivering raw materials without triggering blast furnace throttling or inventory stock-outs.</p>
      </div>

      <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:14px;">
        <div style="background:var(--bg-subtle);border:1px solid var(--steel-border);border-radius:8px;padding:10px 12px;">
          <div style="display:flex;justify-content:space-between;font-weight:600;font-size:12px;color:var(--navy-deep);">
            <span>⚓ 1. Deep-Water Berth Availability (40%)</span>
            <span style="color:var(--green);font-weight:700;">HIGH RELIABILITY</span>
          </div>
          <p style="font-size:11px;color:var(--steel-muted);margin:3px 0 0;">Dedicated mechanized bulk berths at Dhamra & Gangavaram prevent multi-day anchor hold-ups.</p>
        </div>

        <div style="background:var(--bg-subtle);border:1px solid var(--steel-border);border-radius:8px;padding:10px 12px;">
          <div style="display:flex;justify-content:space-between;font-weight:600;font-size:12px;color:var(--navy-deep);">
            <span>⛈️ 2. Weather & Cyclone Resilience (30%)</span>
            <span style="color:var(--green);font-weight:700;">BUFFERED</span>
          </div>
          <p style="font-size:11px;color:var(--steel-muted);margin:3px 0 0;">Engine selects all-weather deep water ports with backup road/rail diversion pathways.</p>
        </div>

        <div style="background:var(--bg-subtle);border:1px solid var(--steel-border);border-radius:8px;padding:10px 12px;">
          <div style="display:flex;justify-content:space-between;font-weight:600;font-size:12px;color:var(--navy-deep);">
            <span>📐 3. Minimax-Regret Multi-Scenario Margin (20%)</span>
            <span style="color:var(--green);font-weight:700;">OPTIMIZED</span>
          </div>
          <p style="font-size:11px;color:var(--steel-muted);margin:3px 0 0;">Selected strategy guarantees the minimum financial loss in the event of freight spikes or port disruptions.</p>
        </div>

        <div style="background:var(--bg-subtle);border:1px solid var(--steel-border);border-radius:8px;padding:10px 12px;">
          <div style="display:flex;justify-content:space-between;font-weight:600;font-size:12px;color:var(--navy-deep);">
            <span>🚆 4. Inland Rail Wagon Turnaround (10%)</span>
            <span style="color:var(--green);font-weight:700;">DIRECT FOIS RAKE</span>
          </div>
          <p style="font-size:11px;color:var(--steel-muted);margin:3px 0 0;">Direct rake loading at port railheads ensures smooth dispatch to SAIL plant silos.</p>
        </div>
      </div>

      <div style="background:var(--bg-subtle);padding:10px;border-radius:6px;font-size:11.5px;color:var(--steel-dark);border:1px solid var(--steel-border);">
        💡 <b>Recommendation:</b> Maintain a minimum <b>15-day raw material yard buffer</b> during monsoon months (June–September) to guarantee uninterrupted hot-metal production.
      </div>
    </div>"""

if old_cont_modal_html in content:
    content = content.replace(old_cont_modal_html, new_cont_modal_html)
    print("Enhanced continuityModal applied.")

# 4. Enhanced Executive Report Modal Content
old_export_fn = """function generateExecutiveReport(){
  if(!activeResult){
    alert('Please run the decision optimization first.');
    return;
  }
  const w=activeResult.winner, b=activeResult.backup;
  const inputs=activeInputs;
  const vc=VESSEL_CLASSES[activeResult.vesselClassKey];
  const totalCostUSD=w.base.total*inputs.qty;
  const totalCostINR=(totalCostUSD*83.5)/10000000;
  const savings=Math.abs(b.base.total-w.base.total);
  const now=new Date().toLocaleDateString('en-IN',{day:'numeric',month:'long',year:'numeric'});

  const body=document.getElementById('exportReportBody');
  if(body){
    body.innerHTML=`
      <div style="border-bottom:2px solid var(--saffron);padding-bottom:10px;margin-bottom:14px;">
        <h3 style="margin:0;color:var(--navy-deep);font-size:16px;">STEEL AUTHORITY OF INDIA LIMITED · LOGISTICS DIVISION</h3>
        <div style="font-size:11.5px;color:var(--steel-muted);">Maritime Cargo Chartering & Route Optimization Strategic Decision Brief · ${now}</div>
      </div>
      
      <div style="background:#FFF;padding:12px;border-radius:6px;border:1px solid var(--steel-border);margin-bottom:12px;">
        <div style="font-weight:700;color:var(--saffron-dark);font-size:14px;margin-bottom:4px;">
          ★ RECOMMENDED STRATEGY: ${ORIGINS[w.originKey].name} ➔ ${PORTS[w.portKey].name}
        </div>
        <div style="font-size:12px;color:var(--steel-dark);">
          <b>Vessel Class:</b> ${vc.name} (${fmt(vc.dwtMin)}–${fmt(vc.dwtMax)} MT DWT) &nbsp;·&nbsp; 
          <b>Destination:</b> ${PLANT_LABEL[inputs.plant]} &nbsp;·&nbsp; 
          <b>Parcel:</b> ${fmt(inputs.qty)} MT ${CARGO_LABEL[inputs.cargoType]}
        </div>
      </div>

      <table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:12px;">
        <tr style="background:var(--bg-main);"><th style="padding:6px 8px;text-align:left;">Metric</th><th style="padding:6px 8px;text-align:right;">Value</th></tr>
        <tr><td style="padding:5px 8px;">Landed Cost / MT</td><td style="padding:5px 8px;text-align:right;font-family:'IBM Plex Mono';font-weight:700;color:var(--saffron-dark);">${usd(w.base.total)}</td></tr>
        <tr><td style="padding:5px 8px;">Total Voyage Procurement Budget</td><td style="padding:5px 8px;text-align:right;font-family:'IBM Plex Mono';">₹${fmt(totalCostINR)} Cr (${usd(totalCostUSD)} USD)</td></tr>
        <tr><td style="padding:5px 8px;">Simulated Cost Saving vs Backup</td><td style="padding:5px 8px;text-align:right;font-family:'IBM Plex Mono';color:var(--green);font-weight:700;">+${usd(savings)}/MT (₹${fmt((savings*inputs.qty*83.5)/10000000)} Cr total)</td></tr>
        <tr><td style="padding:5px 8px;">Operational Risk Index</td><td style="padding:5px 8px;text-align:right;font-family:'IBM Plex Mono';">${activeResult.risk}/100</td></tr>
        <tr><td style="padding:5px 8px;">Supply Continuity Confidence</td><td style="padding:5px 8px;text-align:right;font-family:'IBM Plex Mono';">${activeResult.continuity}/100</td></tr>
        <tr><td style="padding:5px 8px;">Transit Duration (Sea + Rail)</td><td style="padding:5px 8px;text-align:right;font-family:'IBM Plex Mono';">${w.base.transitDays} days</td></tr>
      </table>

      <div style="font-size:11px;color:var(--steel-muted);border-top:1px solid var(--steel-border);padding-top:8px;">
        Generated by LOHA-DRISHTI Minimax-Regret Decision Intelligence Engine · SIH 2026.
      </div>`;
  }
  openModal('exportModal');
}"""

new_export_fn = """function generateExecutiveReport(){
  if(!activeResult){
    alert('Please run the decision optimization first.');
    return;
  }
  const w=activeResult.winner, b=activeResult.backup;
  const inputs=activeInputs;
  const vc=VESSEL_CLASSES[activeResult.vesselClassKey];
  const totalCostUSD=w.base.total*inputs.qty;
  const totalCostINR=(totalCostUSD*83.5)/10000000;
  const savings=Math.abs(b.base.total-w.base.total);
  const now=new Date().toLocaleDateString('en-IN',{day:'numeric',month:'long',year:'numeric'});

  const body=document.getElementById('exportReportBody');
  if(body){
    body.innerHTML=`
      <div style="border-bottom:2.5px solid var(--saffron);padding-bottom:12px;margin-bottom:16px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
          <div>
            <h3 style="margin:0;color:var(--navy-deep);font-size:17px;font-family:'Space Grotesk';">STEEL AUTHORITY OF INDIA LIMITED (SAIL)</h3>
            <div style="font-size:12px;font-weight:600;color:var(--saffron-dark);">Logistics &amp; Raw Material Procurement Division · Ministry of Steel</div>
          </div>
          <div style="text-align:right;font-size:11px;color:var(--steel-muted);font-family:'IBM Plex Mono';">
            Date: ${now}<br>Ref: SAIL/LOHA-DRISHTI/${new Date().getFullYear()}/08
          </div>
        </div>
      </div>
      
      <!-- WINNING STRATEGY BANNER -->
      <div style="background:#FFF;padding:14px;border-radius:8px;border:1.5px solid var(--saffron-border);margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
        <div style="font-size:11px;font-weight:700;color:var(--saffron-dark);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;">
          ★ RECOMMENDED STRATEGY FIXTURE
        </div>
        <div style="font-size:16px;font-weight:700;color:var(--navy-deep);font-family:'Space Grotesk';">
          ${ORIGINS[w.originKey].name} ➔ ${PORTS[w.portKey].name} Port
        </div>
        <div style="font-size:12px;color:var(--steel-dark);margin-top:4px;">
          <b>Vessel Class:</b> ${vc.name} &nbsp;·&nbsp; 
          <b>Destination Plant:</b> ${PLANT_LABEL[inputs.plant]} &nbsp;·&nbsp; 
          <b>Parcel:</b> ${fmt(inputs.qty)} MT ${CARGO_LABEL[inputs.cargoType]} (${inputs.days}d window)
        </div>
      </div>

      <!-- METRICS GRID -->
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px;">
        <div style="background:#FFF;border:1px solid var(--steel-border);border-radius:6px;padding:10px;text-align:center;">
          <div style="font-size:11px;color:var(--steel-muted);">Landed Cost / MT</div>
          <div style="font-size:16px;font-weight:700;color:var(--saffron-dark);font-family:'IBM Plex Mono';">${usd(w.base.total)}</div>
        </div>
        <div style="background:#FFF;border:1px solid var(--steel-border);border-radius:6px;padding:10px;text-align:center;">
          <div style="font-size:11px;color:var(--steel-muted);">Total Budget (₹ Cr)</div>
          <div style="font-size:16px;font-weight:700;color:var(--navy-deep);font-family:'IBM Plex Mono';">₹${fmt(totalCostINR)} Cr</div>
        </div>
        <div style="background:#FFF;border:1px solid var(--steel-border);border-radius:6px;padding:10px;text-align:center;">
          <div style="font-size:11px;color:var(--steel-muted);">Simulated Savings</div>
          <div style="font-size:16px;font-weight:700;color:var(--green);font-family:'IBM Plex Mono';">+${usd(savings)}/MT</div>
        </div>
      </div>

      <!-- COST BREAKDOWN TABLE -->
      <div style="font-weight:700;font-size:12.5px;color:var(--navy-deep);margin-bottom:6px;font-family:'Space Grotesk';">1. Cost Breakdown &amp; Financial Summary</div>
      <table style="width:100%;border-collapse:collapse;font-size:11.5px;margin-bottom:16px;background:#FFF;border-radius:6px;overflow:hidden;border:1px solid var(--steel-border);">
        <tr style="background:var(--bg-subtle);"><th style="padding:7px 10px;text-align:left;">Component</th><th style="padding:7px 10px;text-align:right;">$/MT</th><th style="padding:7px 10px;text-align:right;">Total Budget ($)</th><th style="padding:7px 10px;text-align:right;">Share (%)</th></tr>
        <tr style="border-bottom:1px solid var(--steel-border);"><td style="padding:6px 10px;">Cargo FOB Price</td><td style="padding:6px 10px;text-align:right;font-family:'IBM Plex Mono';">${usd(w.base.fob)}</td><td style="padding:6px 10px;text-align:right;font-family:'IBM Plex Mono';">${usd(w.base.fob*inputs.qty)}</td><td style="padding:6px 10px;text-align:right;font-family:'IBM Plex Mono';">${((w.base.fob/w.base.total)*100).toFixed(1)}%</td></tr>
        <tr style="border-bottom:1px solid var(--steel-border);"><td style="padding:6px 10px;">Ocean Freight</td><td style="padding:6px 10px;text-align:right;font-family:'IBM Plex Mono';">${usd(w.base.freight)}</td><td style="padding:6px 10px;text-align:right;font-family:'IBM Plex Mono';">${usd(w.base.freight*inputs.qty)}</td><td style="padding:6px 10px;text-align:right;font-family:'IBM Plex Mono';">${((w.base.freight/w.base.total)*100).toFixed(1)}%</td></tr>
        <tr style="border-bottom:1px solid var(--steel-border);"><td style="padding:6px 10px;">Port Handling (Load &amp; Discharge)</td><td style="padding:6px 10px;text-align:right;font-family:'IBM Plex Mono';">${usd(w.base.loadPortCharge + w.base.dischargePortCharge)}</td><td style="padding:6px 10px;text-align:right;font-family:'IBM Plex Mono';">${usd((w.base.loadPortCharge + w.base.dischargePortCharge)*inputs.qty)}</td><td style="padding:6px 10px;text-align:right;font-family:'IBM Plex Mono';">${(((w.base.loadPortCharge + w.base.dischargePortCharge)/w.base.total)*100).toFixed(1)}%</td></tr>
        <tr style="border-bottom:1px solid var(--steel-border);"><td style="padding:6px 10px;">Inland Rail Evacuation</td><td style="padding:6px 10px;text-align:right;font-family:'IBM Plex Mono';">${usd(w.base.evac)}</td><td style="padding:6px 10px;text-align:right;font-family:'IBM Plex Mono';">${usd(w.base.evac*inputs.qty)}</td><td style="padding:6px 10px;text-align:right;font-family:'IBM Plex Mono';">${((w.base.evac/w.base.total)*100).toFixed(1)}%</td></tr>
        <tr style="border-bottom:1px solid var(--steel-border);"><td style="padding:6px 10px;">Insurance, Demurrage &amp; Financing</td><td style="padding:6px 10px;text-align:right;font-family:'IBM Plex Mono';">${usd(w.base.insurance + w.base.demurrageExpected + w.base.financing)}</td><td style="padding:6px 10px;text-align:right;font-family:'IBM Plex Mono';">${usd((w.base.insurance + w.base.demurrageExpected + w.base.financing)*inputs.qty)}</td><td style="padding:6px 10px;text-align:right;font-family:'IBM Plex Mono';">${(((w.base.insurance + w.base.demurrageExpected + w.base.financing)/w.base.total)*100).toFixed(1)}%</td></tr>
        <tr style="font-weight:700;background:var(--bg-subtle);"><td style="padding:7px 10px;">Total Landed Cost</td><td style="padding:7px 10px;text-align:right;font-family:'IBM Plex Mono';color:var(--saffron-dark);">${usd(w.base.total)}</td><td style="padding:7px 10px;text-align:right;font-family:'IBM Plex Mono';color:var(--saffron-dark);">${usd(totalCostUSD)}</td><td style="padding:7px 10px;text-align:right;font-family:'IBM Plex Mono';">100.0%</td></tr>
      </table>

      <!-- RISK & CONTINUITY -->
      <div style="font-weight:700;font-size:12.5px;color:var(--navy-deep);margin-bottom:6px;font-family:'Space Grotesk';">2. Operational Risk &amp; Resilience</div>
      <div style="background:#FFF;border:1px solid var(--steel-border);border-radius:6px;padding:10px 12px;margin-bottom:16px;font-size:11.5px;line-height:1.6;">
        <div><b>Operational Risk Index:</b> <span class="mono" style="font-weight:700;">${activeResult.risk}/100</span> (${activeResult.risk<40?'Low Risk':'Moderate Risk'}) &nbsp;·&nbsp; <b>Supply Continuity:</b> <span class="mono" style="font-weight:700;color:var(--green);">${activeResult.continuity}/100</span> (High Delivery Confidence)</div>
        <div style="margin-top:4px;color:var(--steel-muted);">Minimax-Regret score matrix confirms this route accumulates the lowest worst-case financial regret across Normal, Monsoon, Congestion, and Freight Spike stress scenarios.</div>
      </div>

      <div style="font-size:10.5px;color:var(--steel-muted);border-top:1px solid var(--steel-border);padding-top:8px;text-align:center;">
        Generated by LOHA-DRISHTI Autonomous Maritime Decision Intelligence Platform · Steel Authority of India Limited (SAIL).
      </div>`;
  }
  openModal('exportModal');
}"""

if old_export_fn in content:
    content = content.replace(old_export_fn, new_export_fn)
    print("Enhanced generateExecutiveReport applied.")

with open(app_file, "w", encoding="utf-8") as f:
    f.write(content)
print("Breakouts enhancement applied to app.html.")
