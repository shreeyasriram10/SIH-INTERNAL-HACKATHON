import os

app_file = r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\static\app.html"

with open(app_file, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add subtle "🎬 Demo Video" button in topbar actions right next to Demo button
old_demo_btn = '<button class="icon-btn" id="demoBtn">🇮🇳 Demo</button>'
new_demo_btn = '<button class="icon-btn" id="demoAnimBtn" onclick="openDemoAnimation()" style="background:var(--saffron-bg);border-color:var(--saffron-border);color:var(--saffron-dark);font-weight:700;">🎬 Watch Demo</button>\n    <button class="icon-btn" id="demoBtn">🇮🇳 Demo</button>'

if old_demo_btn in content:
    content = content.replace(old_demo_btn, new_demo_btn)
    print("Added Watch Demo button.")

# 2. Add Demo Animation Modal right before </body>
demo_modal_html = """
<!-- ===== DEMO / PLATFORM OVERVIEW ANIMATION MODAL ===== -->
<div class="modal-overlay" id="demoAnimationModal">
  <div class="modal-box" style="max-width:720px;width:95%;">
    <div class="modal-header">
      <div>
        <h3 style="margin:0;font-size:16px;font-family:'Space Grotesk';">🎬 LOHA-DRISHTI — Decision Workflow Animation</h3>
        <p style="margin:2px 0 0;font-size:11px;color:var(--steel-muted);">Cargo Input ➔ Freight Analysis ➔ ML Forecasting ➔ Risk Analysis ➔ Strategy Recommendation</p>
      </div>
      <button class="close-btn" onclick="closeModal('demoAnimationModal')">✕</button>
    </div>
    
    <div style="padding:16px 20px;">
      <!-- ANIMATED STAGE -->
      <div style="background:#0F172A;border-radius:12px;padding:24px 20px;color:#FFF;position:relative;overflow:hidden;box-shadow:inset 0 2px 10px rgba(0,0,0,0.5);">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
          <span id="animStepBadge" style="background:rgba(217,119,6,0.25);color:var(--saffron);border:1px solid var(--saffron-border);font-size:11px;font-weight:700;padding:2px 10px;border-radius:12px;font-family:'IBM Plex Mono';">
            STAGE 1 / 5: CARGO INPUT
          </span>
          <span style="font-size:11px;color:#94A3B8;font-family:'IBM Plex Mono';">SAIL LOGISTICS WORKFLOW</span>
        </div>

        <div id="animStageBox" style="min-height:160px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;">
          <div id="animIcon" style="font-size:42px;margin-bottom:8px;">📦</div>
          <div id="animTitle" style="font-family:'Space Grotesk';font-size:20px;font-weight:700;color:#FFF;">1. Cargo Input Intake</div>
          <div id="animDesc" style="font-size:13px;color:#94A3B8;max-width:500px;margin-top:6px;line-height:1.6;">
            80,000 MT Coking Coal requirement specified for Rourkela Steel Plant with 30-day delivery window.
          </div>
        </div>

        <!-- Progress Indicator -->
        <div style="display:flex;gap:5px;margin-top:16px;">
          <div class="anim-bar" id="aBar0" style="flex:1;height:4px;background:var(--saffron);border-radius:2px;"></div>
          <div class="anim-bar" id="aBar1" style="flex:1;height:4px;background:rgba(255,255,255,0.15);border-radius:2px;"></div>
          <div class="anim-bar" id="aBar2" style="flex:1;height:4px;background:rgba(255,255,255,0.15);border-radius:2px;"></div>
          <div class="anim-bar" id="aBar3" style="flex:1;height:4px;background:rgba(255,255,255,0.15);border-radius:2px;"></div>
          <div class="anim-bar" id="aBar4" style="flex:1;height:4px;background:rgba(255,255,255,0.15);border-radius:2px;"></div>
        </div>
      </div>

      <!-- Controls -->
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:14px;flex-wrap:wrap;gap:10px;">
        <div style="display:flex;gap:8px;">
          <button id="btnPlayAnim" class="icon-btn" onclick="toggleAnimPlay()">⏸ Pause</button>
          <button class="icon-btn" onclick="restartAnim()">🔄 Replay</button>
          <button class="icon-btn" onclick="nextAnimStep()">Next Stage ➔</button>
        </div>
        <div style="font-size:11.5px;color:var(--steel-muted);font-weight:600;">
          ⏱ 20-Second Animated Presentation
        </div>
      </div>

      <div style="margin-top:14px;background:var(--saffron-bg);border:1px solid var(--saffron-border);border-radius:8px;padding:10px;text-align:center;">
        <p style="margin:0;font-size:12px;color:var(--saffron-dark);font-weight:600;font-style:italic;">
          “See how LOHA-DRISHTI transforms freight intelligence into actionable procurement decisions.”
        </p>
      </div>
    </div>
  </div>
</div>

<script>
/* ======= DEMO ANIMATION SCRIPT ======= */
let animStep = 0;
let animTimer = null;
let isAnimPlaying = false;

const animData = [
  { step: "STAGE 1 / 5: CARGO INPUT", icon: "📦", title: "1. Cargo Requirement Input", desc: "User inputs 80,000 MT Coking Coal for Rourkela Steel Plant with 30-day laycan delivery window." },
  { step: "STAGE 2 / 5: FREIGHT ANALYSIS", icon: "🌐", title: "2. Freight Corridor Analysis", desc: "Ingests voyage parameters across 4 global corridors (Australia, South Africa, Indonesia, USA) to 5 East Coast ports." },
  { step: "STAGE 3 / 5: ML FORECASTING", icon: "🤖", title: "3. ML Freight Rate Forecasting", desc: "GradientBoosting ML pipeline computes P10/P50/P90 rate projections calibrated on BDI and bunker price dynamics (R²=0.989)." },
  { step: "STAGE 4 / 5: RISK ANALYSIS", icon: "🛡️", title: "4. Multi-Factor Risk & Minimax Regret", desc: "Simulates 4 market disruption scenarios (Normal, Monsoon, Congestion, Freight Spike) to identify minimal worst-case regret." },
  { step: "STAGE 5 / 5: STRATEGY RECOMMENDATION", icon: "🏆", title: "5. Optimal Strategy Recommendation", desc: "Selected Winner: Australia ➔ Dhamra Port via Panamax ($38.40/MT) with ₹25.6 Cr voyage value and 88/100 Supply Continuity." }
];

function openDemoAnimation(){
  openModal('demoAnimationModal');
  restartAnim();
}

function updateAnimDisplay(){
  const cur = animData[animStep];
  document.getElementById('animStepBadge').textContent = cur.step;
  document.getElementById('animIcon').textContent = cur.icon;
  document.getElementById('animTitle').textContent = cur.title;
  document.getElementById('animDesc').textContent = cur.desc;

  for(let i=0; i<5; i++){
    const b = document.getElementById('aBar'+i);
    if(b){
      b.style.background = i <= animStep ? 'var(--saffron)' : 'rgba(255,255,255,0.15)';
    }
  }
}

function nextAnimStep(){
  animStep = (animStep + 1) % 5;
  updateAnimDisplay();
}

function restartAnim(){
  animStep = 0;
  updateAnimDisplay();
  startAnimLoop();
}

function startAnimLoop(){
  if(animTimer) clearInterval(animTimer);
  isAnimPlaying = true;
  document.getElementById('btnPlayAnim').textContent = '⏸ Pause';
  animTimer = setInterval(()=>{
    animStep = (animStep + 1) % 5;
    updateAnimDisplay();
  }, 4000);
}

function toggleAnimPlay(){
  if(isAnimPlaying){
    clearInterval(animTimer);
    isAnimPlaying = false;
    document.getElementById('btnPlayAnim').textContent = '▶ Play';
  } else {
    startAnimLoop();
  }
}
</script>
"""

content = content.replace("</body>", demo_modal_html + "\n</body>")

with open(app_file, "w", encoding="utf-8") as f:
    f.write(content)
print("app.html restored with Demo Animation added.")
