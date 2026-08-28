import re

app_file = r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\static\app.html"

with open(app_file, "r", encoding="utf-8") as f:
    content = f.read()

# Pattern for copilot drawer
copilot_pattern = re.compile(r'<!-- AI COPILOT DRAWER \(RIGHT\) -->\s*<div class="drawer-right" id="copilotDrawer">.*?</div>\s*</div>', re.DOTALL)

new_advisor = """<!-- LOHA-DRISHTI STRATEGIC ADVISOR DRAWER (RIGHT) -->
<div class="drawer-right" id="copilotDrawer" style="width:420px;max-width:92vw;">
  <div class="drawer-header" style="background:linear-gradient(135deg,var(--navy-deep),var(--navy-surface));color:#FFF;padding:16px;">
    <div>
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="font-size:18px;">🏛️</span>
        <h3 style="margin:0;font-size:16px;font-family:'Space Grotesk';color:#FFF;">LOHA-DRISHTI Strategic Advisor</h3>
      </div>
      <p style="margin:3px 0 0;font-size:11px;color:#94A3B8;">Intelligent Freight &amp; Procurement Decision Support</p>
      <div style="margin-top:6px;display:inline-block;background:rgba(217,119,6,0.2);border:1px solid var(--saffron-border);color:var(--saffron-gold);font-size:9.5px;font-weight:700;padding:2px 8px;border-radius:10px;font-family:'IBM Plex Mono';">
        [DEMO / SYNTHETIC DATA ENGINE — BDI CALIBRATED]
      </div>
    </div>
    <button class="close-btn" style="color:#FFF;" onclick="closeDrawerById('copilotDrawer')">✕</button>
  </div>
  <div class="drawer-body" id="copilotBody" style="height:calc(100vh - 280px);overflow-y:auto;padding:16px;background:#F8FAFC;">
    <div class="copilot-msg bot">
      <strong>Welcome to the LOHA-DRISHTI Strategic Advisor.</strong><br>
      I am specialized in maritime raw material procurement for SAIL steel plants. You can type any strategic question below or select from the prompt chips.
    </div>
  </div>
  <div id="copilotTyping" class="copilot-typing" style="display:none;padding:6px 14px;font-size:11px;color:var(--steel-muted);font-style:italic;">
    <span class="spinner-inline" style="width:10px;height:10px;border-width:1.5px;border-color:var(--steel-muted);border-top-color:var(--saffron);display:inline-block;margin-right:6px;"></span> Strategic Advisor is synthesizing corridor parameters &amp; regret matrices...
  </div>
  <!-- Interactive typing input -->
  <div style="padding:10px 14px;background:#FFF;border-top:1px solid var(--steel-border);display:flex;gap:8px;">
    <input type="text" id="advisorUserInput" placeholder="Ask about the current freight strategy…" style="flex:1;padding:9px 12px;border:1px solid var(--steel-border);border-radius:6px;font-size:12.5px;font-family:'IBM Plex Sans';" onkeydown="if(event.key==='Enter') sendAdvisorInput()">
    <button class="btn-optimize" style="padding:8px 14px;font-size:12px;" onclick="sendAdvisorInput()">Ask</button>
  </div>
  <!-- Prompt chips -->
  <div class="copilot-prompts" style="padding:10px 14px;background:#F1F5F9;border-top:1px solid var(--steel-border);display:flex;flex-wrap:wrap;gap:6px;">
    <button class="prompt-btn" onclick="askCopilot('Why is this strategy recommended?')">Why is this strategy recommended?</button>
    <button class="prompt-btn" onclick="askCopilot('Which origin is most cost-effective?')">Which origin is most cost-effective?</button>
    <button class="prompt-btn" onclick="askCopilot('Compare available vessel options.')">Compare available vessel options.</button>
    <button class="prompt-btn" onclick="askCopilot('Explain the current market risk.')">Explain the current market risk.</button>
    <button class="prompt-btn" onclick="askCopilot('What happens if freight rates increase?')">What happens if freight rates increase?</button>
    <button class="prompt-btn" onclick="askCopilot('Summarise the current procurement decision.')">Summarise the current procurement decision.</button>
  </div>
</div>"""

if copilot_pattern.search(content):
    content = copilot_pattern.sub(new_advisor, content)
    print("Strategic Advisor Drawer replaced using regex.")
else:
    print("Regex not matched, looking for direct string.")
    if '<div class="drawer-right" id="copilotDrawer">' in content:
        start_idx = content.find('<!-- AI COPILOT DRAWER (RIGHT) -->')
        if start_idx == -1:
            start_idx = content.find('<div class="drawer-right" id="copilotDrawer">')
        end_idx = content.find('<!-- SEARCH MODAL -->')
        if start_idx != -1 and end_idx != -1:
            content = content[:start_idx] + new_advisor + "\n\n" + content[end_idx:]
            print("Direct slice replacement succeeded.")

with open(app_file, "w", encoding="utf-8") as f:
    f.write(content)
print("Saved.")
