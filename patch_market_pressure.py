import os

app_file = r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\static\app.html"

with open(app_file, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add IDs to the pressure bars HTML
old_pressure_html = """          <div class="pressure-bars">
            <div class="p-bar-row">
              <span>Freight Volatility</span>
              <div class="p-bar-track"><div class="p-bar-fill" style="width:44%;background:var(--saffron);"></div></div>
              <span class="mono" style="font-size:11px;">44/100</span>
            </div>
            <div class="p-bar-row">
              <span>Vessel Availability</span>
              <div class="p-bar-track"><div class="p-bar-fill" style="width:38%;background:var(--green);"></div></div>
              <span class="mono" style="font-size:11px;">38/100</span>
            </div>
            <div class="p-bar-row">
              <span>Seasonal Demand</span>
              <div class="p-bar-track"><div class="p-bar-fill" style="width:52%;background:var(--saffron);"></div></div>
              <span class="mono" style="font-size:11px;">52/100</span>
            </div>
            <div class="p-bar-row">
              <span>Port Congestion</span>
              <div class="p-bar-track"><div class="p-bar-fill" style="width:35%;background:var(--green);"></div></div>
              <span class="mono" style="font-size:11px;">35/100</span>
            </div>
          </div>
        </div>
        <div style="background:var(--bg-subtle);padding:10px;border-radius:8px;font-size:12px;margin-top:12px;">
          <div style="font-weight:700;color:var(--navy-deep);margin-bottom:2px;">📈 Market Timing Signal</div>
          <div id="marketSignalText" style="color:var(--saffron-dark);font-weight:600;">3-VOYAGE CONTRACT RECOMMENDED</div>
          <div style="font-size:11px;color:var(--steel-muted);margin-top:3px;">Spot rate upside risk +12% over 60 days. Lock in contract to limit exposure.</div>
        </div>"""

new_pressure_html = """          <div class="pressure-bars">
            <div class="p-bar-row">
              <span>Freight Volatility</span>
              <div class="p-bar-track"><div class="p-bar-fill" id="pBarFillVol" style="width:44%;background:var(--saffron);"></div></div>
              <span class="mono" id="pBarTextVol" style="font-size:11px;">44/100</span>
            </div>
            <div class="p-bar-row">
              <span>Vessel Availability</span>
              <div class="p-bar-track"><div class="p-bar-fill" id="pBarFillVessel" style="width:38%;background:var(--green);"></div></div>
              <span class="mono" id="pBarTextVessel" style="font-size:11px;">38/100</span>
            </div>
            <div class="p-bar-row">
              <span>Seasonal Demand</span>
              <div class="p-bar-track"><div class="p-bar-fill" id="pBarFillSeason" style="width:52%;background:var(--saffron);"></div></div>
              <span class="mono" id="pBarTextSeason" style="font-size:11px;">52/100</span>
            </div>
            <div class="p-bar-row">
              <span>Port Congestion</span>
              <div class="p-bar-track"><div class="p-bar-fill" id="pBarFillCongest" style="width:35%;background:var(--green);"></div></div>
              <span class="mono" id="pBarTextCongest" style="font-size:11px;">35/100</span>
            </div>
          </div>
        </div>
        <div style="background:var(--bg-subtle);padding:10px;border-radius:8px;font-size:12px;margin-top:12px;">
          <div style="font-weight:700;color:var(--navy-deep);margin-bottom:2px;">📈 Market Timing Signal</div>
          <div id="marketSignalText" style="color:var(--saffron-dark);font-weight:600;">3-VOYAGE CONTRACT RECOMMENDED</div>
          <div id="marketSignalDesc" style="font-size:11px;color:var(--steel-muted);margin-top:3px;">Spot rate upside risk +12% over 60 days. Lock in contract to limit exposure.</div>
        </div>"""

if old_pressure_html in content:
    content = content.replace(old_pressure_html, new_pressure_html)
    print("Pressure bars HTML updated with IDs.")

# 2. Add dynamic market pressure function and hook into pipeline
gauge_js = """
/* ======= DYNAMIC MARKET PRESSURE GAUGE LOGIC ======= */
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
}
"""

# Insert gauge_js before closing </script>
content = content.replace("</script>", gauge_js + "\n</script>")

# Hook into runPipeline: after activeResult=result; call updateMarketPressureGauge(result, inputs)
content = content.replace("renderFreightOriginTable();", "renderFreightOriginTable();\n  updateMarketPressureGauge(result, inputs, activeScenarioType);")

# Hook into handleChallenge:
content = content.replace("renderBattleTable(newResult.candidates,'scenarioBattleBody');", "renderBattleTable(newResult.candidates,'scenarioBattleBody');\n    updateMarketPressureGauge(newResult, activeInputs, type);")

# Hook into resetBaseline:
content = content.replace("animateRouteBattle(baselineResult.candidates,baselineResult.winner);", "animateRouteBattle(baselineResult.candidates,baselineResult.winner);\n    updateMarketPressureGauge(baselineResult, activeInputs, null);")

with open(app_file, "w", encoding="utf-8") as f:
    f.write(content)
print("Market Pressure Gauge patched and connected dynamically.")
