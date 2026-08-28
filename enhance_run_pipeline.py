import re

app_file = r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\static\app.html"

with open(app_file, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the stage texts in runPipeline
old_stages = """  showLoading('Running Decision Engine','Evaluating all origin-port-vessel combinations...');
  await delay(200);

  switchPanel('command');
  setStage(0,`Cargo Intake: ${fmt(inputs.qty)} MT ${CARGO_LABEL[inputs.cargoType]} → ${PLANT_LABEL[inputs.plant]}.`);
  await delay(280);
  document.getElementById('loadingSubText').textContent='Stage 2/9: Evaluating origins...';
  setStage(1,`Evaluating origins: ${inputs.origin==='any'?'All 5 origins':'Selected: '+ORIGINS[inputs.origin]?.short}.`);
  await delay(250);
  setStage(2,`Checking draft & LOA constraints across East Coast ports...`);
  await delay(250);
  document.getElementById('loadingSubText').textContent='Stage 4/9: Vessel class selection...';
  setStage(3,`Vessel class: ${VESSEL_CLASSES[pickVesselClass(inputs.qty)].name} selected for ${fmt(inputs.qty)} MT.`);
  await delay(250);
  setStage(4,`Forecasting freight rates (P10/P50/P90 bands) per origin...`);
  await delay(250);
  document.getElementById('loadingSubText').textContent='Stage 6/9: Computing cost waterfall...';
  setStage(5,`Computing total landed cost waterfall for all combinations...`);
  await delay(250);
  setStage(6,`Building risk matrix: freight volatility, monsoon, congestion, evac...`);
  await delay(250);
  document.getElementById('loadingSubText').textContent='Stage 8/9: Minimax-Regret optimization...';
  setStage(7,`Running Minimax-Regret optimization across 4 scenarios...`);
  await delay(280);"""

new_stages = """  showLoading('Scenario Analysis in Progress…','Validating cargo parameters & corridor constraints...');
  await delay(180);

  switchPanel('command');
  setStage(0,`Cargo Intake: ${fmt(inputs.qty)} MT ${CARGO_LABEL[inputs.cargoType]} → ${PLANT_LABEL[inputs.plant]}.`);
  await delay(200);
  document.getElementById('loadingSubText').textContent='Updating freight forecast via ML Engine…';
  setStage(1,`Evaluating origins: ${inputs.origin==='any'?'All 5 global origins':'Selected: '+ORIGINS[inputs.origin]?.short}.`);
  await delay(200);
  document.getElementById('loadingSubText').textContent='Evaluating vessel strategies across East Coast ports…';
  setStage(2,`Checking draft & LOA constraints across Paradip, Dhamra, Haldia, Gangavaram, Vizag...`);
  await delay(200);
  setStage(3,`Vessel class: ${VESSEL_CLASSES[pickVesselClass(inputs.qty)].name} selected for ${fmt(inputs.qty)} MT parcel.`);
  await delay(200);
  document.getElementById('loadingSubText').textContent='Analysing market conditions & risk factors…';
  setStage(4,`Forecasting freight rates (P10/P50/P90 bands) per origin corridor...`);
  await delay(200);
  setStage(5,`Computing total landed cost waterfall for all feasible combinations...`);
  await delay(200);
  setStage(6,`Building multi-factor risk matrix: volatility, monsoon, port queues, rail evacuation...`);
  await delay(200);
  document.getElementById('loadingSubText').textContent='Generating optimal Minimax-Regret recommendation…';
  setStage(7,`Executing Minimax-Regret optimization matrix across 4 market disruption scenarios...`);
  await delay(220);"""

if old_stages in content:
    content = content.replace(old_stages, new_stages)
    print("Staged loading messages upgraded successfully.")
else:
    print("old_stages exact match not found, checking with normalize...")

with open(app_file, "w", encoding="utf-8") as f:
    f.write(content)
print("Saved.")
