import os

app_file = r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\static\app.html"

with open(app_file, "r", encoding="utf-8") as f:
    content = f.read()

auth_guard_script = """
<script>
// LOHA-DRISHTI Secure Authentication Guard
(function(){
  var token = localStorage.getItem('ld_token');
  if (!token) { 
    window.location.replace('/'); 
    return; 
  }
  document.addEventListener('DOMContentLoaded', function(){
    var role = localStorage.getItem('ld_role') || 'Chief Logistics Officer';
    var email = localStorage.getItem('ld_email') || 'admin@sail.gov.in';
    var actions = document.querySelector('.topbar-actions');
    if(actions && !document.getElementById('userRoleBadge')){
      var userBadge = document.createElement('span');
      userBadge.id = 'userRoleBadge';
      userBadge.className = 'icon-btn';
      userBadge.style.cssText = 'font-size:11.5px;cursor:default;background:var(--saffron-bg);border-color:var(--saffron-border);color:var(--saffron-dark);font-weight:700;';
      userBadge.innerHTML = '👤 ' + role;
      userBadge.title = email;
      
      var logoutBtn = document.createElement('button');
      logoutBtn.id = 'logoutBtn';
      logoutBtn.className = 'icon-btn';
      logoutBtn.innerHTML = '🚪 Logout';
      logoutBtn.onclick = function(){
        localStorage.removeItem('ld_token');
        localStorage.removeItem('ld_role');
        localStorage.removeItem('ld_email');
        window.location.replace('/');
      };
      actions.insertBefore(logoutBtn, actions.firstChild);
      actions.insertBefore(userBadge, actions.firstChild);
    }
  });
})();
</script>
"""

# Check if auth guard is already present
if "LOHA-DRISHTI Secure Authentication Guard" not in content:
    content = content.replace("<body>", "<body>\n" + auth_guard_script)
    print("Auth guard injected into app.html")

with open(app_file, "w", encoding="utf-8") as f:
    f.write(content)

# Update main.py
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

# 1. SECURE SIGN IN / REGISTRATION AT ROOT "/" & "/login"
@app.get("/", include_in_schema=False)
@app.get("/login", include_in_schema=False)
def serve_login():
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))

# 2. MAIN EXECUTIVE DASHBOARD AT "/app" (PROTECTED BY JWT SESSION)
@app.get("/app", include_in_schema=False)
def serve_dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "app.html"))

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
print("main.py updated to serve Sign In at / and Dashboard at /app.")
