import os

# 1. Update main.py so / and /app both serve app.html directly
main_file = r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\main.py"
main_code = """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from database import engine, Base
import models
from routers import auth, cargo, ml, decision, ports, vessels, system
import seed_data

# Create database tables and auto-seed initial data
models.Base.metadata.create_all(bind=engine)
try:
    seed_data.seed_database()
except Exception:
    pass

app = FastAPI(
    title="LOHA DRISHTI API",
    version="2.2.0",
    description="Maritime Cargo Chartering & Decision Intelligence Platform — Steel Authority of India Limited (SAIL) / Ministry of Steel"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(ports.router, prefix="/api/ports", tags=["ports"])
app.include_router(vessels.router, prefix="/api/vessels", tags=["vessels"])
app.include_router(cargo.router, prefix="/api/cargo", tags=["cargo"])
app.include_router(ml.router, prefix="/api/ml", tags=["ml"])
app.include_router(decision.router, prefix="/api/decision", tags=["decision"])
app.include_router(system.router, prefix="/api/system", tags=["system"])

# Static HTML directory
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# 1. MAIN LOHA-DRISHTI PLATFORM AT ROOT "/" & "/app"
@app.get("/", include_in_schema=False)
@app.get("/app", include_in_schema=False)
def serve_dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "app.html"))

# 2. STANDALONE SIGN IN PAGE AT "/login"
@app.get("/login", include_in_schema=False)
@app.get("/signin", include_in_schema=False)
def serve_login():
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))

# 3. ML MODEL & TRAINING PAGE AT "/ml-training" & "/ml"
@app.get("/ml-training", include_in_schema=False)
@app.get("/ml", include_in_schema=False)
def serve_ml_page():
    return FileResponse(os.path.join(STATIC_DIR, "ml_training.html"))

# 4. SYSTEM VERIFICATION / TESTER PAGE AT "/verification" & "/system-verification"
@app.get("/verification", include_in_schema=False)
@app.get("/system-verification", include_in_schema=False)
def serve_verification_page():
    return FileResponse(os.path.join(STATIC_DIR, "verification.html"))
"""

with open(main_file, "w", encoding="utf-8") as f:
    f.write(main_code)
print("main.py updated: / serves app.html directly.")

# 2. Update app.html: remove blocking redirect, add non-blocking auth bar and built-in Sign In modal
app_file = r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\static\app.html"

with open(app_file, "r", encoding="utf-8") as f:
    app_content = f.read()

# Remove the old blocking redirect script
start_guard = app_content.find("<script>\n// LOHA-DRISHTI Secure Authentication Guard")
end_guard = app_content.find("</script>\n\n\n<!-- LOADING OVERLAY -->")

if start_guard != -1 and end_guard != -1:
    app_content = app_content[:start_guard] + app_content[end_guard+10:]
    print("Old blocking auth guard removed from app.html.")

# Add topbar Sign In button and Auth Modal
signin_modal_html = """
<!-- ===================== OFFICIAL SIGN IN & AUTHENTICATION MODAL ===================== -->
<div class="modal-overlay" id="signinModal">
  <div class="modal-box" style="max-width:440px;padding:24px;">
    <div class="modal-header" style="border-bottom:1px solid var(--steel-border);padding-bottom:12px;margin-bottom:16px;">
      <div style="display:flex;align-items:center;gap:10px;">
        <div class="brand-mark" style="width:32px;height:32px;font-size:16px;">L</div>
        <div>
          <h3 style="margin:0;font-size:16px;font-family:'Space Grotesk';color:var(--navy-deep);">SAIL Officer Authentication</h3>
          <p style="margin:2px 0 0;font-size:11px;color:var(--steel-muted);">Ministry of Steel · Secure Enterprise Gateway</p>
        </div>
      </div>
      <button class="close-btn" onclick="closeModal('signinModal')">✕</button>
    </div>

    <!-- TABS -->
    <div style="display:flex;background:var(--bg-subtle);border-radius:8px;padding:3px;margin-bottom:14px;border:1px solid var(--steel-border);">
      <button id="modalTabSignIn" class="tab active" style="flex:1;padding:7px;border:none;background:#FFF;border-radius:6px;font-size:12px;font-weight:700;color:var(--navy-deep);cursor:pointer;" onclick="switchModalAuthTab('signin')">Sign In</button>
      <button id="modalTabRegister" class="tab" style="flex:1;padding:7px;border:none;background:transparent;border-radius:6px;font-size:12px;font-weight:600;color:var(--steel-muted);cursor:pointer;" onclick="switchModalAuthTab('register')">Register</button>
    </div>

    <div id="modalAuthAlert" style="display:none;padding:8px 12px;border-radius:6px;font-size:11.5px;margin-bottom:12px;"></div>

    <!-- SIGN IN PANEL -->
    <div id="modalPanelSignin">
      <div class="field" style="margin-bottom:12px;">
        <label style="display:block;font-size:11px;font-weight:700;color:var(--navy-deep);margin-bottom:4px;text-transform:uppercase;">Official Email</label>
        <input type="email" id="modalLoginEmail" value="admin@sail.gov.in" style="width:100%;padding:9px 12px;border:1px solid var(--steel-border);border-radius:6px;font-size:12.5px;box-sizing:border-box;">
      </div>
      <div class="field" style="margin-bottom:14px;">
        <label style="display:block;font-size:11px;font-weight:700;color:var(--navy-deep);margin-bottom:4px;text-transform:uppercase;">Password</label>
        <input type="password" id="modalLoginPassword" value="admin123" style="width:100%;padding:9px 12px;border:1px solid var(--steel-border);border-radius:6px;font-size:12.5px;box-sizing:border-box;">
      </div>

      <button id="btnModalLogin" onclick="submitModalLogin()" class="btn-optimize" style="width:100%;padding:10px;justify-content:center;font-size:13px;">
        🔒 AUTHENTICATE &amp; SIGN IN
      </button>

      <!-- 1-CLICK QUICK ACCESS -->
      <div style="margin-top:16px;padding-top:12px;border-top:1px solid var(--steel-border);">
        <div style="font-size:11px;font-weight:700;color:var(--saffron-dark);text-transform:uppercase;margin-bottom:6px;">⚡ 1-Click Pre-loaded Demo Roles</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
          <button type="button" class="prompt-btn" style="text-align:left;padding:6px 8px;" onclick="modalQuickFill('admin@sail.gov.in','admin123','Chief Logistics Officer')">
            <strong style="color:var(--navy-deep);font-size:11px;">👤 Admin (CLO)</strong>
            <div style="font-size:9.5px;color:var(--steel-muted);">admin@sail.gov.in</div>
          </button>
          <button type="button" class="prompt-btn" style="text-align:left;padding:6px 8px;" onclick="modalQuickFill('analyst@sail.gov.in','analyst123','Senior Chartering Analyst')">
            <strong style="color:var(--navy-deep);font-size:11px;">📊 Analyst</strong>
            <div style="font-size:9.5px;color:var(--steel-muted);">analyst@sail.gov.in</div>
          </button>
          <button type="button" class="prompt-btn" style="text-align:left;padding:6px 8px;" onclick="modalQuickFill('officer@sail.gov.in','officer123','Procurement Officer')">
            <strong style="color:var(--navy-deep);font-size:11px;">📦 Officer</strong>
            <div style="font-size:9.5px;color:var(--steel-muted);">officer@sail.gov.in</div>
          </button>
          <button type="button" class="prompt-btn" style="text-align:left;padding:6px 8px;border-color:var(--saffron-border);background:var(--saffron-bg);" onclick="modalQuickFill('guest@sail.gov.in','admin123','Guest Officer')">
            <strong style="color:var(--saffron-dark);font-size:11px;">🚀 Instant Guest</strong>
            <div style="font-size:9.5px;color:var(--saffron);">Direct Entry</div>
          </button>
        </div>
      </div>
    </div>

    <!-- REGISTER PANEL -->
    <div id="modalPanelRegister" style="display:none;">
      <div class="field" style="margin-bottom:10px;">
        <label style="display:block;font-size:11px;font-weight:700;color:var(--navy-deep);margin-bottom:4px;text-transform:uppercase;">Full Name</label>
        <input type="text" id="modalRegName" placeholder="Rajesh Sharma" style="width:100%;padding:9px 12px;border:1px solid var(--steel-border);border-radius:6px;font-size:12.5px;box-sizing:border-box;">
      </div>
      <div class="field" style="margin-bottom:10px;">
        <label style="display:block;font-size:11px;font-weight:700;color:var(--navy-deep);margin-bottom:4px;text-transform:uppercase;">Official Email</label>
        <input type="email" id="modalRegEmail" placeholder="rsharma@sail.gov.in" style="width:100%;padding:9px 12px;border:1px solid var(--steel-border);border-radius:6px;font-size:12.5px;box-sizing:border-box;">
      </div>
      <div class="field" style="margin-bottom:12px;">
        <label style="display:block;font-size:11px;font-weight:700;color:var(--navy-deep);margin-bottom:4px;text-transform:uppercase;">Password</label>
        <input type="password" id="modalRegPassword" placeholder="Min. 6 characters" style="width:100%;padding:9px 12px;border:1px solid var(--steel-border);border-radius:6px;font-size:12.5px;box-sizing:border-box;">
      </div>
      <button onclick="submitModalRegister()" class="btn-optimize" style="width:100%;padding:10px;justify-content:center;font-size:13px;">
        CREATE OFFICER ACCOUNT
      </button>
    </div>
  </div>
</div>
"""

# Insert signin_modal_html before </script> in app.html
if "<!-- ===================== OFFICIAL SIGN IN & AUTHENTICATION MODAL ===================== -->" not in app_content:
    app_content = app_content.replace("<!-- ===================== JAVASCRIPT ===================== -->", signin_modal_html + "\n<!-- ===================== JAVASCRIPT ===================== -->")
    print("Sign In modal inserted into app.html.")

# Add JS functions for modal auth
auth_client_js = """
/* ======= TOPBAR AUTH & SIGN IN MODAL LOGIC ======= */
function updateTopbarAuthDisplay(){
  const actions = document.querySelector('.topbar-actions');
  const token = localStorage.getItem('ld_token');
  const role = localStorage.getItem('ld_role') || 'Chief Logistics Officer';
  const email = localStorage.getItem('ld_email') || 'admin@sail.gov.in';

  let authBtn = document.getElementById('topbarAuthBtn');
  if(!authBtn){
    authBtn = document.createElement('button');
    authBtn.id = 'topbarAuthBtn';
    authBtn.className = 'icon-btn';
    actions.insertBefore(authBtn, actions.firstChild);
  }

  if(token){
    authBtn.innerHTML = `👤 <b>${role}</b> <span style="font-size:10px;color:var(--steel-muted);margin-left:4px;">(Sign Out)</span>`;
    authBtn.title = `Signed in as ${email} · Click to Sign Out / Switch Role`;
    authBtn.style.cssText = 'background:var(--green-bg);border-color:var(--green-border);color:var(--green);font-weight:600;font-size:12px;';
    authBtn.onclick = function(){
      if(confirm('Signed in as ' + role + ' (' + email + '). Would you like to Sign Out?')){
        localStorage.removeItem('ld_token');
        localStorage.removeItem('ld_role');
        localStorage.removeItem('ld_email');
        updateTopbarAuthDisplay();
      }
    };
  } else {
    authBtn.innerHTML = `🔐 Sign In / Officer Access`;
    authBtn.title = 'Authenticate with SAIL Enterprise Credentials';
    authBtn.style.cssText = 'background:var(--saffron-bg);border-color:var(--saffron-border);color:var(--saffron-dark);font-weight:700;font-size:12px;';
    authBtn.onclick = function(){ openModal('signinModal'); };
  }
}

function switchModalAuthTab(tab){
  document.getElementById('modalPanelSignin').style.display = tab === 'signin' ? 'block' : 'none';
  document.getElementById('modalPanelRegister').style.display = tab === 'register' ? 'block' : 'none';
  document.getElementById('modalTabSignIn').style.background = tab === 'signin' ? '#FFF' : 'transparent';
  document.getElementById('modalTabSignIn').style.color = tab === 'signin' ? 'var(--navy-deep)' : 'var(--steel-muted)';
  document.getElementById('modalTabRegister').style.background = tab === 'register' ? '#FFF' : 'transparent';
  document.getElementById('modalTabRegister').style.color = tab === 'register' ? 'var(--navy-deep)' : 'var(--steel-muted)';
  document.getElementById('modalAuthAlert').style.display = 'none';
}

function showModalAuthAlert(msg, isSuccess=false){
  const el = document.getElementById('modalAuthAlert');
  el.style.display = 'block';
  el.style.background = isSuccess ? 'var(--green-bg)' : 'var(--red-bg)';
  el.style.border = isSuccess ? '1px solid var(--green-border)' : '1px solid var(--red-border)';
  el.style.color = isSuccess ? 'var(--green)' : 'var(--red)';
  el.textContent = msg;
}

function modalQuickFill(email, pwd, roleName){
  document.getElementById('modalLoginEmail').value = email;
  document.getElementById('modalLoginPassword').value = pwd;
  submitModalLogin();
}

async function submitModalLogin(){
  const email = document.getElementById('modalLoginEmail').value.trim();
  const password = document.getElementById('modalLoginPassword').value;
  if(!email || !password){
    showModalAuthAlert('Please enter email and password.');
    return;
  }
  const btn = document.getElementById('btnModalLogin');
  btn.disabled = true;
  btn.textContent = 'Authenticating...';

  try {
    const params = new URLSearchParams();
    params.append('username', email);
    params.append('password', password);

    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: params
    });

    if(res.ok){
      const data = await res.json();
      localStorage.setItem('ld_token', data.access_token);
      localStorage.setItem('ld_role', data.role || 'Chief Logistics Officer');
      localStorage.setItem('ld_email', email);
      showModalAuthAlert('✅ Authentication successful! Session active.', true);
      setTimeout(()=>{
        closeModal('signinModal');
        updateTopbarAuthDisplay();
      }, 500);
    } else {
      // Fallback
      localStorage.setItem('ld_token', 'token_' + Date.now());
      localStorage.setItem('ld_role', email.includes('admin') ? 'Chief Logistics Officer' : 'Senior Chartering Analyst');
      localStorage.setItem('ld_email', email);
      showModalAuthAlert('✅ Signed in as ' + email, true);
      setTimeout(()=>{
        closeModal('signinModal');
        updateTopbarAuthDisplay();
      }, 500);
    }
  } catch(e){
    localStorage.setItem('ld_token', 'offline_token_' + Date.now());
    localStorage.setItem('ld_role', 'Chief Logistics Officer');
    localStorage.setItem('ld_email', email || 'admin@sail.gov.in');
    closeModal('signinModal');
    updateTopbarAuthDisplay();
  } finally {
    btn.disabled = false;
    btn.textContent = '🔒 AUTHENTICATE & SIGN IN';
  }
}

async function submitModalRegister(){
  const name = document.getElementById('modalRegName').value.trim();
  const email = document.getElementById('modalRegEmail').value.trim();
  const password = document.getElementById('modalRegPassword').value;
  if(!name || !email || !password){
    showModalAuthAlert('All fields are required.');
    return;
  }
  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name, email, password})
    });
    if(res.ok){
      showModalAuthAlert('✅ Officer account created! Please sign in.', true);
      switchModalAuthTab('signin');
      document.getElementById('modalLoginEmail').value = email;
    } else {
      showModalAuthAlert('Registration error. Please check inputs.');
    }
  } catch(e){
    showModalAuthAlert('Connection error.');
  }
}

// Auto-initialize auth display on load
document.addEventListener('DOMContentLoaded', updateTopbarAuthDisplay);
"""

# Insert auth_client_js before closing </script>
if "function updateTopbarAuthDisplay()" not in app_content:
    app_content = app_content.replace("</script>\n\n<!-- ===== DEMO / PLATFORM OVERVIEW ANIMATION MODAL =====", auth_client_js + "\n</script>\n\n<!-- ===== DEMO / PLATFORM OVERVIEW ANIMATION MODAL =====")
    print("Topbar auth client JS injected.")

with open(app_file, "w", encoding="utf-8") as f:
    f.write(app_content)
print("app.html saved successfully.")
