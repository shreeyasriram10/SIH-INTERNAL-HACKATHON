import re
import os

app_file = r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\static\app.html"

with open(app_file, "r", encoding="utf-8") as f:
    content = f.read()

print("Original app.html length:", len(content))

# 1. Update Navigation Menu and Actions
old_nav = """  <div class="nav-menu">
    <a id="nav-command" class="active" onclick="switchPanel('command')">⚙ Command Center</a>
    <a id="nav-intelligence" onclick="switchPanel('intelligence')">📊 Intelligence</a>
    <a id="nav-scenarios" onclick="switchPanel('scenarios')">⚡ Scenarios</a>
    <a id="nav-ports" onclick="switchPanel('ports')">🚢 Port &amp; Vessel DNA</a>
    <a id="nav-copilot" onclick="openCopilot()">🧠 AI Copilot</a>
  </div>"""

new_nav = """  <div class="nav-menu">
    <a id="nav-command" class="active" onclick="switchPanel('command')">⚙ Command Center</a>
    <a id="nav-intelligence" onclick="switchPanel('intelligence')">📊 Intelligence</a>
    <a id="nav-scenarios" onclick="switchPanel('scenarios')">⚡ Scenarios</a>
    <a id="nav-ports" onclick="switchPanel('ports')">🚢 Port &amp; Vessel DNA</a>
    <a id="nav-ml" onclick="switchPanel('ml')">🤖 Forecast Engine</a>
    <a id="nav-verification" onclick="switchPanel('verification')">🧪 Verification</a>
    <a id="nav-systemstatus" onclick="switchPanel('systemstatus')">🟢 System Status</a>
    <a id="nav-advisor" onclick="openStrategicAdvisor()">🏛️ Strategic Advisor</a>
  </div>"""

if old_nav in content:
    content = content.replace(old_nav, new_nav)
    print("Navigation menu updated.")

# Topbar actions - add Platform Overview button
old_actions = """    <button class="icon-btn" id="openNotifyBtn">🔔 Alerts <span class="badge-num">2</span></button>"""
new_actions = """    <button class="icon-btn" id="openOverviewBtn" onclick="openPlatformOverview()" style="background:var(--saffron-bg);border-color:var(--saffron-border);color:var(--saffron-dark);font-weight:700;">🎬 Platform Overview</button>
    <button class="icon-btn" id="openNotifyBtn">🔔 Alerts <span class="badge-num">2</span></button>"""

if old_actions in content:
    content = content.replace(old_actions, new_actions)
    print("Overview button added to topbar.")

# Section tabs switcher
old_tabs = """<div class="section-tabs" id="sectionTabs">
  <button class="tab-btn active" id="tab-command" onclick="switchPanel('command')">Command Center</button>
  <button class="tab-btn" id="tab-intelligence" onclick="switchPanel('intelligence')">Freight Intelligence</button>
  <button class="tab-btn" id="tab-scenarios" onclick="switchPanel('scenarios')">What-If Simulator</button>
  <button class="tab-btn" id="tab-ports" onclick="switchPanel('ports')">Port DNA</button>
  <button class="tab-btn" id="tab-vessels" onclick="switchPanel('vessels')">Vessel Fit</button>
</div>"""

new_tabs = """<div class="section-tabs" id="sectionTabs">
  <button class="tab-btn active" id="tab-command" onclick="switchPanel('command')">Command Center</button>
  <button class="tab-btn" id="tab-intelligence" onclick="switchPanel('intelligence')">Freight Intelligence</button>
  <button class="tab-btn" id="tab-scenarios" onclick="switchPanel('scenarios')">What-If Simulator</button>
  <button class="tab-btn" id="tab-ports" onclick="switchPanel('ports')">Port DNA</button>
  <button class="tab-btn" id="tab-vessels" onclick="switchPanel('vessels')">Vessel Fit</button>
  <button class="tab-btn" id="tab-ml" onclick="switchPanel('ml')">🤖 Forecast Engine</button>
  <button class="tab-btn" id="tab-verification" onclick="switchPanel('verification')">🧪 System Verification</button>
  <button class="tab-btn" id="tab-systemstatus" onclick="switchPanel('systemstatus')">🟢 System Status</button>
</div>"""

if old_tabs in content:
    content = content.replace(old_tabs, new_tabs)
    print("Section tabs updated.")

# Write updated file
with open(app_file, "w", encoding="utf-8") as f:
    f.write(content)
print("Saved base modifications.")
