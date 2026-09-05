import os

app_file = r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\static\app.html"

with open(app_file, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update Navigation menu label
content = content.replace('<a id="nav-copilot" onclick="openCopilot()">🧠 AI Copilot</a>', '<a id="nav-copilot" onclick="openCopilot()">❓ Questions &amp; AI Copilot</a>')

# 2. Update Copilot Drawer HTML with custom input box and rich question pills
old_copilot_drawer = """<!-- AI COPILOT DRAWER (RIGHT) -->
<div class="drawer-right" id="copilotDrawer">
  <div class="drawer-header">
    <div style="font-weight:700;font-family:'Space Grotesk';">Ask LOHA DRISHTI AI 🧠</div>
    <button class="close-btn" style="color:#FFF;" onclick="closeDrawerById('copilotDrawer')">✕</button>
  </div>
  <div class="drawer-body" id="copilotBody">
    <div class="copilot-msg bot">
      Namaste! I am the Loha Drishti AI assistant. I can explain the current recommendation, port constraints, risk scores, or how the Minimax-Regret engine works. Run optimization first for best answers.
    </div>
  </div>
  <div id="copilotTyping" class="copilot-typing">AI is thinking...</div>
  <div class="copilot-prompts">
    <button class="prompt-btn" onclick="askCopilot('Why this vessel?')">Why was this vessel class selected?</button>
    <button class="prompt-btn" onclick="askCopilot('Why not Paradip?')">Why not Paradip port?</button>
    <button class="prompt-btn" onclick="askCopilot('What if freight spikes?')">What if freight spikes by 20%?</button>
    <button class="prompt-btn" onclick="askCopilot('Explain lowest regret')">Explain lowest-regret strategy</button>
    <button class="prompt-btn" onclick="askCopilot('Risk index explanation')">How is the Risk Index calculated?</button>
    <button class="prompt-btn" onclick="askCopilot('Supply continuity')">What is Supply Continuity score?</button>
  </div>
</div>"""

new_copilot_drawer = """<!-- AI COPILOT & QUESTIONS DRAWER (RIGHT) -->
<div class="drawer-right" id="copilotDrawer">
  <div class="drawer-header">
    <div>
      <div style="font-weight:700;font-family:'Space Grotesk';font-size:15px;">❓ Questions &amp; AI Copilot 🧠</div>
      <div style="font-size:11px;color:rgba(255,255,255,0.8);">Ask Any Maritime, Cost, Port, Vessel, or Strategy Question</div>
    </div>
    <button class="close-btn" style="color:#FFF;" onclick="closeDrawerById('copilotDrawer')">✕</button>
  </div>
  <div class="drawer-body" id="copilotBody" style="flex:1;overflow-y:auto;padding:14px;">
    <div class="copilot-msg bot">
      <b>Namaste! I am the LOHA-DRISHTI Decision &amp; Strategy AI Assistant.</b><br>
      You can type any question below or click the quick prompt pills to understand:
      <ul style="margin:6px 0 0 16px;padding:0;font-size:11.5px;">
        <li>Why a specific route or vessel class was selected</li>
        <li>How demurrage, port queues, and monsoon factors are calculated</li>
        <li>What happens during disruptions (Cyclone, Freight Spike)</li>
        <li>Minimax-Regret mathematical logic and risk exposure</li>
      </ul>
    </div>
  </div>
  <div id="copilotTyping" class="copilot-typing" style="display:none;padding:4px 14px;font-size:11px;color:var(--saffron-dark);">⚡ AI Copilot is analyzing logistics parameters...</div>
  
  <!-- INTERACTIVE INPUT AREA -->
  <div style="padding:10px 14px;border-top:1px solid var(--steel-border);background:var(--bg-main);display:flex;gap:8px;">
    <input type="text" id="copilotCustomInput" placeholder="Type your question here (e.g. Why Dhamra over Haldia?)..." style="flex:1;padding:9px 12px;border:1px solid var(--steel-border);border-radius:6px;font-size:12px;box-sizing:border-box;" onkeydown="if(event.key==='Enter') submitCustomCopilotQuery()">
    <button class="btn-optimize" style="padding:9px 14px;font-size:12px;justify-content:center;" onclick="submitCustomCopilotQuery()">Ask ➔</button>
  </div>

  <!-- QUICK QUESTION PILLS -->
  <div class="copilot-prompts" style="padding:10px 14px;border-top:1px solid var(--steel-border);max-height:160px;overflow-y:auto;">
    <div style="font-size:10.5px;font-weight:700;color:var(--steel-muted);text-transform:uppercase;margin-bottom:6px;">Suggested Questions:</div>
    <button class="prompt-btn" onclick="askCopilot('Why this vessel class?')">🚢 Why was this vessel class selected?</button>
    <button class="prompt-btn" onclick="askCopilot('Why not Paradip port?')">⚓ Why not Paradip port?</button>
    <button class="prompt-btn" onclick="askCopilot('Why not Haldia port?')">🏗️ Why is Haldia draft restricted?</button>
    <button class="prompt-btn" onclick="askCopilot('What if freight spikes by 20%?')">📈 What if freight spikes by 20%?</button>
    <button class="prompt-btn" onclick="askCopilot('How does Minimax-Regret work?')">📐 How does the Minimax-Regret math work?</button>
    <button class="prompt-btn" onclick="askCopilot('How is the Risk Index calculated?')">🛡️ How is the Risk Index calculated?</button>
    <button class="prompt-btn" onclick="askCopilot('What is Supply Continuity score?')">📦 What is Supply Continuity confidence?</button>
    <button class="prompt-btn" onclick="askCopilot('How is Demurrage computed?')">⏳ How is Demurrage cost calculated?</button>
    <button class="prompt-btn" onclick="askCopilot('What is the best route for Rourkela?')">🏭 What is the optimal route for Rourkela?</button>
  </div>
</div>"""

if old_copilot_drawer in content:
    content = content.replace(old_copilot_drawer, new_copilot_drawer)
    print("Enhanced Copilot Drawer HTML replaced.")

# 3. Enhanced askCopilot function supporting custom queries and dynamic intelligent answers
old_ask_copilot = """function askCopilot(query){
  const body=document.getElementById('copilotBody');
  const typingEl=document.getElementById('copilotTyping');
  body.innerHTML+=`<div class="copilot-msg user">${query}</div>`;
  typingEl.style.display='block';
  body.scrollTop=body.scrollHeight;

  let reply="Please run the optimization first so I have the current recommendation to reference.";

  if(activeResult && activeInputs){
    const w=activeResult.winner;
    const vc=VESSEL_CLASSES[activeResult.vesselClassKey];
    const p=PORTS[w.portKey];
    const o=ORIGINS[w.originKey];

    if(query.includes('vessel')){
      reply=`<b>${vc.name}</b> class was selected because it's the optimal size for your ${fmt(activeInputs.qty)} MT parcel — it clears all feasible port draft limits while maximizing cargo efficiency. Smaller vessels would require multiple voyages; larger ones may face draft restrictions.`;
    } else if(query.includes('Paradip')){
      const pd=PORTS.paradip;
      reply=`Paradip (${pd.draft}m draft, ${pd.waitDays}d avg wait) was not selected as the primary port because it currently has a higher demurrage exposure due to wait times, and the monsoon window applies additional delay. Gangavaram or Dhamra scored better in the Minimax-Regret matrix.`;
    } else if(query.includes('spikes')){
      reply=`If freight spikes +20% from the current ${usd(w.base.freight)}/MT, the total landed cost would increase by approximately <b>${usd(w.base.freight*0.20)}/MT</b>. Our recommendation is a 3-voyage forward contract to lock in current rates and limit this upside risk exposure.`;
    } else if(query.includes('regret')){
      reply=`The Minimax-Regret algorithm evaluates <b>every origin-port combination across 4 scenarios</b> (Normal, Monsoon, Congestion, Freight Spike). For each strategy, it calculates the <b>maximum regret</b> — how much worse it performs vs. the best alternative in that scenario. The strategy with the <b>smallest maximum regret</b> (${usd(w.maxRegret)}/MT for our winner) is selected, ensuring best robustness against disruptions.`;
    } else if(query.includes('Risk')||query.includes('risk')){
      reply=`The Risk Index (0-100) for the current recommendation is <b>${activeResult.risk}/100</b>. It combines: Freight Volatility from ${o.short} (${(o.vol*100).toFixed(0)}%), Port Congestion at ${p.name} (${p.waitDays}d wait), Monsoon exposure, and Evacuation distance (${p.evacKm}km). Lower is better. Click "Breakdown ℹ" on the Risk Gauge for the full factor breakdown.`;
    } else if(query.includes('continuity')||query.includes('Supply')){
      reply=`Supply Continuity score <b>${activeResult.continuity}/100</b> estimates the probability of uninterrupted raw material delivery to <b>${PLANT_LABEL[activeInputs.plant]}</b>. It accounts for port queue risk, monsoon windows, freight regret margin, and rail evacuation capacity. Above 80 indicates high confidence in plant delivery without stock-outs.`;
    } else {
      reply=`Current recommendation: <b>${o.short} → ${p.name}</b> via ${vc.name} at <b>${usd(w.base.total)}/MT</b>. Risk: ${activeResult.risk}/100. Supply Continuity: ${activeResult.continuity}/100. Ask me about vessel selection, port choice, freight spikes, or the Minimax-Regret methodology.`;
    }
  }

  setTimeout(()=>{
    typingEl.style.display='none';
    body.innerHTML+=`<div class="copilot-msg bot">${reply}</div>`;
    body.scrollTop=body.scrollHeight;
  },600);
}"""

new_ask_copilot = """function submitCustomCopilotQuery(){
  const input = document.getElementById('copilotCustomInput');
  const query = input.value.trim();
  if(!query) return;
  input.value = '';
  askCopilot(query);
}

function askCopilot(query){
  const body=document.getElementById('copilotBody');
  const typingEl=document.getElementById('copilotTyping');
  body.innerHTML+=`<div class="copilot-msg user">${query}</div>`;
  typingEl.style.display='block';
  body.scrollTop=body.scrollHeight;

  const q = query.toLowerCase();
  let reply = "I am evaluating your query against live logistics parameters and port constraints.";

  const inputs = activeInputs || { qty: 80000, cargoType: 'coking_coal', plant: 'rourkela', days: 30, origin: 'any' };
  const res = activeResult || runDecisionEngine(inputs);
  const w = res.winner;
  const vc = VESSEL_CLASSES[res.vesselClassKey];
  const p = PORTS[w.portKey];
  const o = ORIGINS[w.originKey];

  if(q.includes('vessel') || q.includes('size') || q.includes('capesize') || q.includes('panamax') || q.includes('handysize')){
    reply = `<b>${vc.name} Class</b> (${fmt(vc.dwtMin)}–${fmt(vc.dwtMax)} MT DWT) was selected because your parcel size is <b>${fmt(inputs.qty)} MT</b>. It provides the maximum cargo payload while clearing ${p.name}'s draft limit (${p.draft}m port draft vs ${vc.draft}m vessel draft, giving a safe <b>+${(p.draft - vc.draft).toFixed(1)}m under-keel buffer</b>).`;
  } else if(q.includes('paradip')){
    const pd = PORTS.paradip;
    reply = `<b>Paradip Port (INPRT)</b> has a 18.1m draft and 38,000 MT/day mechanised handling rate with 2.8 days average queue. It is an excellent backup, but for the current window, <b>${p.name}</b> was selected because it offers lower pre-berthing wait times (${p.waitDays}d) and lower demurrage exposure.`;
  } else if(q.includes('haldia') || q.includes('river') || q.includes('shallow')){
    const hal = PORTS.haldia;
    reply = `<b>Haldia Port (INHAL)</b> has a restricted riverine draft of only <b>${hal.draft}m</b> and max LOA of 180m. It can only accommodate Handysize vessels (up to 40,000 MT). For your ${fmt(inputs.qty)} MT shipment, Haldia is physically incapable of berthing a ${vc.name} vessel and was excluded by the draft feasibility filter.`;
  } else if(q.includes('dhamra') || q.includes('gangavaram')){
    reply = `<b>${p.name} Port</b> is a premier deep-water all-weather port on the Indian East Coast (${p.draft}m draft). It boasts high-speed mechanized unloaders (${fmt(p.mechRate)} MT/day), quick vessel turnaround (${p.waitDays}d avg queue), and direct rail connectivity to ${PLANT_LABEL[inputs.plant].split('(')[0].trim()}.`;
  } else if(q.includes('spike') || q.includes('20%') || q.includes('freight')){
    const spikeAmount = w.base.freight * 0.20;
    reply = `If dry-bulk freight rates spike by +20%, ocean freight increases from ${usd(w.base.freight)}/MT to <b>${usd(w.base.freight*1.20)}/MT</b> (+${usd(spikeAmount)}/MT). For your ${fmt(inputs.qty)} MT parcel, this adds <b>${usd(spikeAmount*inputs.qty)}</b> to procurement cost. We recommend executing a <b>3-voyage forward contract (COA)</b> to lock in current rates.`;
  } else if(q.includes('regret') || q.includes('minimax') || q.includes('how decided') || q.includes('methodology')){
    reply = `The <b>Minimax-Regret Engine</b> evaluates all feasible origin-port combinations across 4 scenarios: <i>Normal Market, Monsoon Delay, Port Congestion Spike, and Freight Spike (+20%)</i>. For each route, it computes the worst-case financial regret. The winning strategy (<b>${o.short} ➔ ${p.name}</b>) has the <b>lowest maximum regret of ${usd(w.maxRegret)}/MT</b>, ensuring maximum resilience against market shocks.`;
  } else if(q.includes('risk') || q.includes('index')){
    reply = `The <b>Operational Risk Index is ${res.risk}/100</b> (${res.risk<40?'Low Risk ✓':'Moderate Risk'}). It is computed across 5 weighted dimensions: Freight Volatility (25%), Port Queue (30%), Monsoon Exposure (20%), Draft Buffer (15%), and Inland Evacuation Distance (10%). Click <b>Breakdown ℹ</b> on the Risk Gauge for the full breakdown.`;
  } else if(q.includes('continuity') || q.includes('supply') || q.includes('plant') || q.includes('buffer')){
    reply = `The <b>Supply Continuity Confidence is ${res.continuity}/100</b>. It models the certainty of uninterrupted delivery to the blast furnace silos at <b>${PLANT_LABEL[inputs.plant]}</b>. We recommend maintaining a <b>15-day raw material yard buffer</b> during active voyages.`;
  } else if(q.includes('demurrage') || q.includes('queue') || q.includes('wait')){
    const freeTime = 3;
    const excess = Math.max(0, p.waitDays - freeTime);
    reply = `<b>Demurrage Breakdown:</b> Standard free laytime is <b>${freeTime} days</b>. At ${p.name}, the average pre-berthing wait is <b>${p.waitDays} days</b>. With a charterparty demurrage rate of <b>${usd(p.demurrage)}/day</b>, estimated demurrage risk is only <b>${usd(w.base.demurrageExpected)}/MT</b>.`;
  } else if(q.includes('rourkela') || q.includes('bhilai') || q.includes('bokaro') || q.includes('durgapur') || q.includes('burnpur')){
    reply = `For <b>${PLANT_LABEL[inputs.plant]}</b>, the engine calculated an inland rail haulage of <b>${p.evacKm} km</b> from ${p.name}. Freight is hauled via Indian Railways FOIS Class 140 trainloads at an evacuation cost of <b>${usd(w.base.evac)}/MT</b>.`;
  } else {
    reply = `Here is the current operational brief:<br>
    • <b>Winning Strategy:</b> ${o.short} ➔ ${p.name} via ${vc.name}<br>
    • <b>Landed Cost:</b> ${usd(w.base.total)}/MT (₹${fmt(((w.base.total*inputs.qty*83.5)/10000000))} Cr total)<br>
    • <b>Risk Index:</b> ${res.risk}/100 &nbsp;|&nbsp; <b>Supply Continuity:</b> ${res.continuity}/100<br>
    Feel free to ask specific questions about port depths, freight spikes, vessel fit, or rail evacuation.`;
  }

  setTimeout(()=>{
    typingEl.style.display='none';
    body.innerHTML+=`<div class="copilot-msg bot">${reply}</div>`;
    body.scrollTop=body.scrollHeight;
  }, 400);
}"""

if old_ask_copilot in content:
    content = content.replace(old_ask_copilot, new_ask_copilot)
    print("Enhanced askCopilot function applied.")

with open(app_file, "w", encoding="utf-8") as f:
    f.write(content)
print("app.html saved successfully.")
