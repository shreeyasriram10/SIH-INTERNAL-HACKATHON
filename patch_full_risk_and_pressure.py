import re

app_file = r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\static\app.html"

with open(app_file, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Replace the old static riskScore function
old_risk_fn = """function riskScore(originKey, portKey){
  const o=ORIGINS[originKey],p=PORTS[portKey];
  const isMonsoon=p.monsoon.includes(currentMonth());
  let score=25+o.vol*100*0.5+(isMonsoon?25:0)+(p.waitDays*3);
  return Math.min(95,Math.round(score));
}"""

new_risk_fn = """function riskScore(originKey, portKey){
  const o=ORIGINS[originKey], p=PORTS[portKey];
  if(!o || !p) return 35;
  const isMonsoon=p.monsoon.includes(currentMonth());
  
  const originBase = { australia: 10, south_africa: 22, indonesia: 36, usa: 18, russia: 42, mozambique: 38 };
  const originVol = { australia: 6, south_africa: 15, indonesia: 20, usa: 10, russia: 26, mozambique: 22 };
  const portWait = { dhamra: 4, gangavaram: 3, vizag: 8, paradip: 16, haldia: 24 };
  const portMonsoon = { dhamra: 6, gangavaram: 5, vizag: 10, paradip: 20, haldia: 26 };

  let score = (originBase[originKey] || 15) + (originVol[originKey] || 10) + (portWait[portKey] || 8);
  if(isMonsoon){
    score += (portMonsoon[portKey] || 12);
  }
  return Math.min(95, Math.max(15, Math.round(score)));
}"""

if old_risk_fn in content:
    content = content.replace(old_risk_fn, new_risk_fn)
    print("riskScore calibrated.")

# 2. Refine updateMarketPressureGauge with realistic dynamic spectrum
old_gauge_fn = """/* ======= DYNAMIC MARKET PRESSURE GAUGE LOGIC ======= */
function updateMarketPressureGauge(result, inputs, disruptionType=null){
  const labelEl = document.getElementById('pressureGaugeValue');
  const scoreEl = document.getElementById('pressureScore');
  const sigTextEl = document.getElementById('marketSignalText');
  const sigDescEl = document.getElementById('marketSignalDesc');

  const fillVol = document.getElementById('pBarFillVol');
  const textVol = document.getElementById('pBarTextVol');
  const fillVessel = document.getElementById('pBarFillVessel');
  const textVessel = document.getElementById('pBarTextVessel');
  const fillSeason = document.getElementById('pBarFillSeason');
  const textSeason = document.getElementById('pBarTextSeason');
  const fillCongest = document.getElementById('pBarFillCongest');
  const textCongest = document.getElementById('pBarTextCongest');

  if(!labelEl || !scoreEl) return;

  const originKey = result ? result.winner.originKey : (inputs?.origin || 'australia');
  const portKey = result ? result.winner.portKey : 'dhamra';
  const qty = inputs ? inputs.qty : 80000;
  const month = currentMonth();

  // 1. Freight Volatility (0-100)
  const baseVolMap = { australia: 44, south_africa: 56, indonesia: 64, usa: 48, russia: 72, mozambique: 68 };
  let vol = baseVolMap[originKey] || 45;
  if(disruptionType === 'freight') vol = Math.min(95, vol + 38);
  if(disruptionType === 'bunker') vol = Math.min(92, vol + 28);

  // 2. Vessel Availability (0-100)
  let vesselScore = qty >= 120000 ? 65 : qty >= 70000 ? 42 : 32;
  if(disruptionType === 'vessel') vesselScore = 84;

  // 3. Seasonal Demand (0-100)
  const isMonsoonSeason = [7, 8].includes(month);
  let seasonScore = isMonsoonSeason ? 76 : (month in [11, 12, 1] ? 62 : 48);
  if(disruptionType === 'monsoon') seasonScore = 88;
  if(disruptionType === 'cyclone') seasonScore = 84;

  // 4. Port Congestion (0-100)
  const portCongestMap = { haldia: 68, paradip: 54, vizag: 40, dhamra: 28, gangavaram: 22 };
  let congest = portCongestMap[portKey] || 35;
  if(disruptionType === 'cyclone' || disruptionType === 'port') congest = 89;
  if(disruptionType === 'monsoon') congest = Math.min(90, congest + 32);

  // Composite Weighted Score
  const overall = Math.round((vol * 0.35) + (vesselScore * 0.20) + (seasonScore * 0.20) + (congest * 0.25));

  // Update Score Display
  scoreEl.textContent = overall;

  // Colors and classifications
  function getTrackColor(val){
    if(val >= 70) return 'var(--red)';
    if(val >= 50) return 'var(--saffron)';
    return 'var(--green)';
  }

  if(fillVol && textVol){
    fillVol.style.width = vol + '%';
    fillVol.style.background = getTrackColor(vol);
    textVol.textContent = vol + '/100';
  }
  if(fillVessel && textVessel){
    fillVessel.style.width = vesselScore + '%';
    fillVessel.style.background = getTrackColor(vesselScore);
    textVessel.textContent = vesselScore + '/100';
  }
  if(fillSeason && textSeason){
    fillSeason.style.width = seasonScore + '%';
    fillSeason.style.background = getTrackColor(seasonScore);
    textSeason.textContent = seasonScore + '/100';
  }
  if(fillCongest && textCongest){
    fillCongest.style.width = congest + '%';
    fillCongest.style.background = getTrackColor(congest);
    textCongest.textContent = congest + '/100';
  }

  // Label & Market Timing Signal
  if(overall >= 75){
    labelEl.textContent = 'CRITICAL SPIKE';
    labelEl.style.color = 'var(--red)';
    if(sigTextEl) {
      sigTextEl.textContent = 'DEFENSIVE COA / IMMEDIATE ROUTE DIVERSION';
      sigTextEl.style.color = 'var(--red)';
    }
    if(sigDescEl) {
      sigDescEl.textContent = 'Severe market volatility & corridor disruption active. Execute emergency mitigation and reroute to deep-water berths.';
    }
  } else if(overall >= 60){
    labelEl.textContent = 'ELEVATED PRESSURE';
    labelEl.style.color = 'var(--saffron-dark)';
    if(sigTextEl) {
      sigTextEl.textContent = '3-VOYAGE FORWARD CONTRACT RECOMMENDED';
      sigTextEl.style.color = 'var(--saffron-dark)';
    }
    if(sigDescEl) {
      sigDescEl.textContent = 'Spot rate upside risk +' + Math.round((overall-50)*0.8 + 10) + '% over 60 days. Lock in fixed contract to cap cost exposure.';
    }
  } else if(overall >= 40){
    labelEl.textContent = 'MODERATE';
    labelEl.style.color = 'var(--saffron)';
    if(sigTextEl) {
      sigTextEl.textContent = 'BALANCED SPOT / CONTRACT PORTFOLIO';
      sigTextEl.style.color = 'var(--saffron-dark)';
    }
    if(sigDescEl) {
      sigDescEl.textContent = 'Market conditions stable. Maintain 70% long-term COA and 30% spot charter flexibility.';
    }
  } else {
    labelEl.textContent = 'LOW PRESSURE';
    labelEl.style.color = 'var(--green)';
    if(sigTextEl) {
      sigTextEl.textContent = 'SPOT FIXTURE ADVANTAGEOUS';
      sigTextEl.style.color = 'var(--green)';
    }
    if(sigDescEl) {
      sigDescEl.textContent = 'Dry-bulk rates softening. Take advantage of competitive spot market fixtures for near-term laycans.';
    }
  }
}"""

new_gauge_fn = """/* ======= DYNAMIC MARKET PRESSURE GAUGE LOGIC ======= */
function updateMarketPressureGauge(result, inputs, disruptionType=null){
  const labelEl = document.getElementById('pressureGaugeValue');
  const scoreEl = document.getElementById('pressureScore');
  const sigTextEl = document.getElementById('marketSignalText');
  const sigDescEl = document.getElementById('marketSignalDesc');

  const fillVol = document.getElementById('pBarFillVol');
  const textVol = document.getElementById('pBarTextVol');
  const fillVessel = document.getElementById('pBarFillVessel');
  const textVessel = document.getElementById('pBarTextVessel');
  const fillSeason = document.getElementById('pBarFillSeason');
  const textSeason = document.getElementById('pBarTextSeason');
  const fillCongest = document.getElementById('pBarFillCongest');
  const textCongest = document.getElementById('pBarTextCongest');

  if(!labelEl || !scoreEl) return;

  const originKey = result ? result.winner.originKey : (inputs?.origin || 'australia');
  const portKey = result ? result.winner.portKey : 'dhamra';
  const qty = inputs ? inputs.qty : 80000;
  const month = currentMonth();

  // 1. Freight Volatility (0-100): Clear corridor distinction
  const baseVolMap = { australia: 22, south_africa: 46, indonesia: 65, usa: 36, russia: 78, mozambique: 68 };
  let vol = baseVolMap[originKey] || 35;
  if(disruptionType === 'freight') vol = Math.min(96, vol + 44);
  if(disruptionType === 'bunker') vol = Math.min(92, vol + 32);

  // 2. Vessel Availability (0-100): Size sensitivity
  let vesselScore = qty >= 150000 ? 58 : qty >= 70000 ? 28 : 22;
  if(disruptionType === 'vessel') vesselScore = 86;

  // 3. Seasonal Demand (0-100)
  const isMonsoonSeason = [7, 8].includes(month);
  let seasonScore = isMonsoonSeason ? 45 : 28;
  if(disruptionType === 'monsoon') seasonScore = 84;
  if(disruptionType === 'cyclone') seasonScore = 88;

  // 4. Port Congestion (0-100): Port turnaround speed
  const portCongestMap = { haldia: 66, paradip: 48, vizag: 34, dhamra: 18, gangavaram: 14 };
  let congest = portCongestMap[portKey] || 25;
  if(disruptionType === 'cyclone' || disruptionType === 'port') congest = 92;
  if(disruptionType === 'monsoon') congest = Math.min(90, congest + 30);

  // Composite Weighted Score
  const overall = Math.round((vol * 0.35) + (vesselScore * 0.20) + (seasonScore * 0.20) + (congest * 0.25));

  // Update Score Display
  scoreEl.textContent = overall;

  function getTrackColor(val){
    if(val >= 65) return 'var(--red)';
    if(val >= 38) return 'var(--saffron)';
    return 'var(--green)';
  }

  if(fillVol && textVol){
    fillVol.style.width = vol + '%';
    fillVol.style.background = getTrackColor(vol);
    textVol.textContent = vol + '/100';
  }
  if(fillVessel && textVessel){
    fillVessel.style.width = vesselScore + '%';
    fillVessel.style.background = getTrackColor(vesselScore);
    textVessel.textContent = vesselScore + '/100';
  }
  if(fillSeason && textSeason){
    fillSeason.style.width = seasonScore + '%';
    fillSeason.style.background = getTrackColor(seasonScore);
    textSeason.textContent = seasonScore + '/100';
  }
  if(fillCongest && textCongest){
    fillCongest.style.width = congest + '%';
    fillCongest.style.background = getTrackColor(congest);
    textCongest.textContent = congest + '/100';
  }

  // Dynamic States: LOW / STABLE (<36), BALANCED (36-54), ELEVATED (55-72), CRITICAL (>72)
  if(overall >= 73){
    labelEl.textContent = 'CRITICAL SPIKE ⚠';
    labelEl.style.color = 'var(--red)';
    if(sigTextEl) {
      sigTextEl.textContent = 'EMERGENCY DEFENSIVE COA / ROUTE DIVERSION';
      sigTextEl.style.color = 'var(--red)';
    }
    if(sigDescEl) {
      sigDescEl.textContent = 'Severe market volatility active. Reroute vessels away from disrupted berths to deep-water ports immediately.';
    }
  } else if(overall >= 55){
    labelEl.textContent = 'ELEVATED PRESSURE 📈';
    labelEl.style.color = 'var(--saffron-dark)';
    if(sigTextEl) {
      sigTextEl.textContent = '3-VOYAGE FORWARD CONTRACT RECOMMENDED';
      sigTextEl.style.color = 'var(--saffron-dark)';
    }
    if(sigDescEl) {
      sigDescEl.textContent = 'Spot rate volatility elevated. Lock in multi-voyage contract to cap procurement cost exposure.';
    }
  } else if(overall >= 36){
    labelEl.textContent = 'BALANCED MARKET ⚖';
    labelEl.style.color = 'var(--saffron)';
    if(sigTextEl) {
      sigTextEl.textContent = 'BALANCED SPOT / CONTRACT PORTFOLIO';
      sigTextEl.style.color = 'var(--saffron-dark)';
    }
    if(sigDescEl) {
      sigDescEl.textContent = 'Market conditions stable. Maintain standard chartering schedule with 70% forward contract and 30% spot.';
    }
  } else {
    labelEl.textContent = 'LOW PRESSURE ✓';
    labelEl.style.color = 'var(--green)';
    if(sigTextEl) {
      sigTextEl.textContent = 'SPOT FIXTURE HIGHLY FAVORABLE';
      sigTextEl.style.color = 'var(--green)';
    }
    if(sigDescEl) {
      sigDescEl.textContent = 'Corridor freight rates & port queues optimal. Take advantage of competitive spot market rates for near-term laycans.';
    }
  }
}"""

if old_gauge_fn in content:
    content = content.replace(old_gauge_fn, new_gauge_fn)
    print("Market Pressure Gauge logic calibrated.")
else:
    print("old_gauge_fn exact match not found, looking for function start...")
    start_idx = content.find("/* ======= DYNAMIC MARKET PRESSURE GAUGE LOGIC ======= */")
    end_idx = content.find("/* ======= STRATEGIC ADVISOR & NEW PANELS LOGIC ======= */")
    if start_idx != -1 and end_idx != -1:
        content = content[:start_idx] + new_gauge_fn + "\n\n" + content[end_idx:]
        print("Replaced by index slice.")

with open(app_file, "w", encoding="utf-8") as f:
    f.write(content)
print("Saved.")
