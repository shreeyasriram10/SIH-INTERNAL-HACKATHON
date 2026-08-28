import os

# 1. Update login.html: ask password explicitly, show eye toggle, populate email on role click and focus password
login_file = r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\static\login.html"

login_html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LOHA DRISHTI — Ministry of Steel Secure Gateway</title>
<meta name="description" content="Secure login portal for LOHA DRISHTI Maritime Decision Intelligence Platform — Steel Authority of India Limited (SAIL) / Ministry of Steel">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --navy-deep:#0A1128;
    --navy-card:#0F1A36;
    --navy-surface:#1C294E;
    --steel-border:#2A3B66;
    --steel-muted:#8E9EB5;
    --saffron:#E8871E;
    --saffron-gold:#F59E0B;
    --saffron-bg:rgba(232,135,30,0.08);
    --saffron-border:rgba(232,135,30,0.3);
    --green:#10B981;
    --green-bg:rgba(16,185,129,0.1);
    --green-border:rgba(16,185,129,0.3);
    --red:#EF4444;
    --red-bg:rgba(239,68,68,0.1);
    --red-border:rgba(239,68,68,0.3);
    --gold-glow:0 0 30px rgba(245,158,11,0.25);
  }
  *{box-sizing:border-box;margin:0;padding:0;}
  body{
    font-family:'IBM Plex Sans',-apple-system,sans-serif;
    background:radial-gradient(circle at 50% 20%, #152244 0%, #080D1D 70%, #030712 100%);
    min-height:100vh;
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    padding:24px 20px;
    color:#F1F5F9;
  }
  .header-brand{
    display:flex;
    flex-direction:column;
    align-items:center;
    margin-bottom:24px;
    text-align:center;
  }
  .emblem-wrapper{
    position:relative;
    margin-bottom:12px;
  }
  .emblem-circle{
    width:68px;
    height:68px;
    border-radius:18px;
    background:linear-gradient(135deg,#1E293B 0%,#0F172A 100%);
    border:2px solid var(--saffron-gold);
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:32px;
    font-weight:700;
    font-family:'Space Grotesk';
    color:#FFF;
    box-shadow:var(--gold-glow);
  }
  .header-brand h1{
    font-family:'Space Grotesk';
    font-size:26px;
    font-weight:700;
    letter-spacing:0.04em;
    color:#FFF;
    margin-bottom:2px;
  }
  .header-brand p{
    font-size:12.5px;
    color:var(--steel-muted);
    font-weight:500;
  }
  .gov-badge{
    margin-top:8px;
    display:inline-flex;
    align-items:center;
    gap:6px;
    background:rgba(255,255,255,0.06);
    border:1px solid rgba(255,255,255,0.12);
    padding:3px 10px;
    border-radius:20px;
    font-size:11px;
    color:#CBD5E1;
    font-weight:500;
  }

  .login-card{
    width:100%;
    max-width:440px;
    background:var(--navy-card);
    border:1px solid var(--steel-border);
    border-radius:16px;
    padding:28px 24px;
    box-shadow:0 20px 40px rgba(0,0,0,0.5);
    position:relative;
  }
  .card-header{
    margin-bottom:18px;
  }
  .card-header h2{
    font-family:'Space Grotesk';
    font-size:18px;
    font-weight:700;
    color:#FFF;
    margin-bottom:2px;
  }
  .card-header p{
    font-size:12px;
    color:var(--steel-muted);
  }

  .tabs{
    display:flex;
    background:rgba(0,0,0,0.3);
    border-radius:8px;
    padding:3px;
    margin-bottom:18px;
    border:1px solid rgba(255,255,255,0.06);
  }
  .tab{
    flex:1;
    text-align:center;
    padding:8px 0;
    font-size:12px;
    font-weight:600;
    color:var(--steel-muted);
    background:transparent;
    border:none;
    border-radius:6px;
    cursor:pointer;
    transition:all 0.15s;
  }
  .tab.active{
    background:var(--navy-surface);
    color:#FFF;
    box-shadow:0 2px 4px rgba(0,0,0,0.3);
  }

  .field{
    margin-bottom:14px;
    position:relative;
  }
  .field label{
    display:block;
    font-size:11.5px;
    font-weight:600;
    color:#CBD5E1;
    margin-bottom:5px;
    text-transform:uppercase;
    letter-spacing:0.04em;
  }
  .field input{
    width:100%;
    padding:11px 14px;
    background:var(--navy-surface);
    border:1px solid var(--steel-border);
    border-radius:8px;
    color:#FFF;
    font-size:13px;
    font-family:'IBM Plex Sans';
    transition:all 0.15s;
  }
  .field input:focus{
    outline:none;
    border-color:var(--saffron-gold);
    box-shadow:0 0 0 3px rgba(245,158,11,0.15);
  }

  .pwd-wrapper{
    position:relative;
    display:flex;
    align-items:center;
  }
  .pwd-wrapper input{
    padding-right:40px;
  }
  .pwd-toggle{
    position:absolute;
    right:12px;
    background:transparent;
    border:none;
    color:var(--steel-muted);
    font-size:15px;
    cursor:pointer;
    padding:4px;
  }
  .pwd-toggle:hover{color:#FFF;}

  .btn-submit{
    width:100%;
    padding:12px;
    background:linear-gradient(135deg,var(--saffron) 0%,var(--saffron-gold) 100%);
    border:none;
    border-radius:8px;
    color:#FFF;
    font-weight:700;
    font-size:13px;
    font-family:'Space Grotesk';
    letter-spacing:0.03em;
    cursor:pointer;
    transition:all 0.2s;
    box-shadow:0 4px 14px rgba(232,135,30,0.35);
    margin-top:6px;
  }
  .btn-submit:hover{
    transform:translateY(-1px);
    box-shadow:0 6px 20px rgba(232,135,30,0.45);
  }
  .btn-submit:disabled{
    opacity:0.6;
    cursor:not-allowed;
    transform:none;
  }

  .process-box{
    display:none;
    margin-top:14px;
    background:rgba(0,0,0,0.35);
    border:1px solid var(--steel-border);
    border-radius:8px;
    padding:12px 14px;
    font-size:11.5px;
  }
  .process-box.active{display:block;}
  .process-stage{
    display:flex;
    align-items:center;
    gap:8px;
    margin-bottom:6px;
    color:var(--steel-muted);
  }
  .process-stage:last-child{margin-bottom:0;}
  .process-stage.running{color:var(--saffron-gold);font-weight:600;}
  .process-stage.done{color:var(--green);font-weight:600;}
  .dot-spin{
    width:10px;height:10px;border-radius:50%;
    border:2px solid var(--saffron-gold);
    border-top-color:transparent;
    animation:spin 0.6s linear infinite;
  }
  @keyframes spin{to{transform:rotate(360deg);}}

  .alert-box{
    display:none;
    padding:10px 12px;
    border-radius:7px;
    font-size:12px;
    margin-bottom:14px;
  }
  .alert-box.error{
    display:block;
    background:var(--red-bg);
    border:1px solid var(--red-border);
    color:#FCA5A5;
  }
  .alert-box.success{
    display:block;
    background:var(--green-bg);
    border:1px solid var(--green-border);
    color:#86EFAC;
  }

  .demo-access-panel{
    margin-top:18px;
    padding-top:16px;
    border-top:1px solid rgba(255,255,255,0.08);
  }
  .demo-pill-title{
    font-size:11px;
    font-weight:700;
    color:var(--saffron-gold);
    text-transform:uppercase;
    letter-spacing:0.05em;
    margin-bottom:8px;
    display:flex;
    align-items:center;
    gap:5px;
  }
  .demo-roles-grid{
    display:grid;
    grid-template-columns:1fr 1fr 1fr;
    gap:6px;
  }
  .btn-role-quick{
    padding:8px 8px;
    background:rgba(255,255,255,0.04);
    border:1px solid rgba(255,255,255,0.1);
    border-radius:6px;
    color:#E2E8F0;
    font-size:11px;
    cursor:pointer;
    text-align:left;
    transition:all 0.15s;
    display:flex;
    flex-direction:column;
  }
  .btn-role-quick:hover, .btn-role-quick.selected{
    background:var(--saffron-bg);
    border-color:var(--saffron-gold);
    color:var(--saffron-gold);
  }
  .btn-role-quick strong{font-size:10.5px;color:#FFF;}
  .btn-role-quick span{font-size:9px;color:var(--steel-muted);font-family:'IBM Plex Mono';}

  .footer-note{
    margin-top:20px;
    text-align:center;
    font-size:11px;
    color:#64748B;
    line-height:1.6;
  }
  .form-panel{display:none;}
  .form-panel.active{display:block;}
</style>
</head>
<body>
  <div class="header-brand">
    <div class="emblem-wrapper">
      <div class="emblem-circle">L</div>
    </div>
    <h1>LOHA DRISHTI</h1>
    <p>Maritime Cargo Chartering &amp; Decision Intelligence Platform<br>Steel Authority of India Limited (SAIL)</p>
    <div class="gov-badge">
      <span>🇮🇳 Ministry of Steel · Government of India</span>
    </div>
  </div>

  <div class="login-card">
    <div class="card-header">
      <h2>Secure Authentication</h2>
      <p>Select your authorized role and enter your secure password</p>
    </div>

    <div class="tabs">
      <button class="tab active" id="tabSignIn" onclick="showTab('signin')">Sign In</button>
      <button class="tab" id="tabRegister" onclick="showTab('register')">Register Account</button>
    </div>

    <div class="alert-box" id="alertBox"></div>

    <!-- SIGN IN PANEL -->
    <div class="form-panel active" id="panelSignin">
      <!-- DEMO ROLE SELECTOR -->
      <div style="margin-bottom:14px;">
        <div class="demo-pill-title">
          <span>👥</span> Select Official Account
        </div>
        <div class="demo-roles-grid">
          <button type="button" class="btn-role-quick selected" id="roleBtnAdmin" onclick="selectRole('admin@sail.gov.in', 'Chief Logistics Officer', 'admin123')">
            <strong>👤 CLO (Admin)</strong>
            <span>admin@sail.gov.in</span>
          </button>
          <button type="button" class="btn-role-quick" id="roleBtnAnalyst" onclick="selectRole('analyst@sail.gov.in', 'Senior Chartering Analyst', 'analyst123')">
            <strong>📊 Analyst</strong>
            <span>analyst@sail.gov.in</span>
          </button>
          <button type="button" class="btn-role-quick" id="roleBtnOfficer" onclick="selectRole('officer@sail.gov.in', 'Procurement Officer', 'officer123')">
            <strong>📦 Officer</strong>
            <span>officer@sail.gov.in</span>
          </button>
        </div>
      </div>

      <div class="field">
        <label>Official Email</label>
        <input type="email" id="loginEmail" value="admin@sail.gov.in" placeholder="officer@sail.gov.in" autocomplete="email">
      </div>

      <div class="field">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
          <label style="margin:0;">Secure Password</label>
          <span style="font-size:10.5px;color:var(--saffron-gold);cursor:pointer;" id="pwdHint" onclick="fillHintPassword()">💡 Demo pwd: <b id="hintText">admin123</b></span>
        </div>
        <div class="pwd-wrapper">
          <input type="password" id="loginPassword" placeholder="Enter secure password" autocomplete="current-password" autofocus>
          <button type="button" class="pwd-toggle" onclick="togglePasswordVisibility('loginPassword', this)" title="Show/Hide Password">👁</button>
        </div>
      </div>

      <button class="btn-submit" id="loginBtn" onclick="handleLogin()">AUTHENTICATE &amp; ENTER</button>

      <!-- LIVE PROCESS STATE BOX -->
      <div class="process-box" id="processBox">
        <div class="process-stage" id="stage1"><span class="dot-spin"></span> Secure authentication initiated...</div>
        <div class="process-stage" id="stage2"><span>○</span> Verifying cryptographic credentials...</div>
        <div class="process-stage" id="stage3"><span>○</span> Establishing secure JWT session...</div>
        <div class="process-stage" id="stage4"><span>○</span> Access granted. Redirecting to Executive Command Center...</div>
      </div>
    </div>

    <!-- REGISTER PANEL -->
    <div class="form-panel" id="panelRegister">
      <div class="field">
        <label>Officer Full Name</label>
        <input type="text" id="regName" placeholder="Rajesh Sharma">
      </div>
      <div class="field">
        <label>Official Email</label>
        <input type="email" id="regEmail" placeholder="rsharma@sail.gov.in">
      </div>
      <div class="field">
        <label>Password (Min. 6 Characters)</label>
        <div class="pwd-wrapper">
          <input type="password" id="regPassword" placeholder="Create secure password">
          <button type="button" class="pwd-toggle" onclick="togglePasswordVisibility('regPassword', this)">👁</button>
        </div>
      </div>
      <button class="btn-submit" id="regBtn" onclick="handleRegister()">CREATE OFFICER ACCOUNT</button>
    </div>
  </div>

  <p class="footer-note">
    🔒 256-Bit Encrypted Session · Role-Based Access Control · Ministry of Steel<br>
    This portal processes confidential bulk-cargo procurement logistics for SAIL.
  </p>

<script>
  const delay = ms => new Promise(r => setTimeout(r, ms));
  let currentExpectedPwd = 'admin123';

  function showTab(tab) {
    document.getElementById('panelSignin').classList.toggle('active', tab === 'signin');
    document.getElementById('panelRegister').classList.toggle('active', tab === 'register');
    document.getElementById('tabSignIn').classList.toggle('active', tab === 'signin');
    document.getElementById('tabRegister').classList.toggle('active', tab === 'register');
    clearAlert();
  }

  function showAlert(msg, type='error') {
    const box = document.getElementById('alertBox');
    box.textContent = msg;
    box.className = 'alert-box ' + type;
  }

  function clearAlert() {
    const box = document.getElementById('alertBox');
    box.className = 'alert-box';
    box.textContent = '';
  }

  function togglePasswordVisibility(fieldId, btn) {
    const input = document.getElementById(fieldId);
    if (input.type === 'password') {
      input.type = 'text';
      btn.style.color = 'var(--saffron-gold)';
    } else {
      input.type = 'password';
      btn.style.color = 'var(--steel-muted)';
    }
  }

  function selectRole(email, roleName, expectedPwd) {
    document.getElementById('loginEmail').value = email;
    currentExpectedPwd = expectedPwd;
    document.getElementById('hintText').textContent = expectedPwd;
    
    document.querySelectorAll('.btn-role-quick').forEach(b => b.classList.remove('selected'));
    if (email.includes('admin')) document.getElementById('roleBtnAdmin').classList.add('selected');
    if (email.includes('analyst')) document.getElementById('roleBtnAnalyst').classList.add('selected');
    if (email.includes('officer')) document.getElementById('roleBtnOfficer').classList.add('selected');

    const pwdInput = document.getElementById('loginPassword');
    pwdInput.value = '';
    pwdInput.focus();
    clearAlert();
    showAlert(`🔑 Selected ${roleName}. Please enter password (${expectedPwd}).`, 'success');
  }

  function fillHintPassword() {
    document.getElementById('loginPassword').value = currentExpectedPwd;
    clearAlert();
  }

  async function handleLogin() {
    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value;
    if (!email) {
      showAlert('Please enter your official email.');
      return;
    }
    if (!password) {
      showAlert('🔒 Password required. Please enter password (Hint: ' + currentExpectedPwd + ')');
      document.getElementById('loginPassword').focus();
      return;
    }

    const btn = document.getElementById('loginBtn');
    const procBox = document.getElementById('processBox');
    btn.disabled = true;
    clearAlert();
    procBox.classList.add('active');

    const s1 = document.getElementById('stage1');
    const s2 = document.getElementById('stage2');
    const s3 = document.getElementById('stage3');
    const s4 = document.getElementById('stage4');

    s1.className = 'process-stage running';
    s1.innerHTML = '<span class="dot-spin"></span> Secure authentication initiated...';

    await delay(200);

    s1.className = 'process-stage done';
    s1.innerHTML = '<span>✓</span> Authentication initiated';
    s2.className = 'process-stage running';
    s2.innerHTML = '<span class="dot-spin"></span> Verifying cryptographic credentials...';

    try {
      const params = new URLSearchParams();
      params.append('username', email);
      params.append('password', password);

      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: params
      });

      if (!res.ok) {
        procBox.classList.remove('active');
        btn.disabled = false;
        showAlert('❌ Incorrect password for ' + email + '. Expected: ' + currentExpectedPwd);
        document.getElementById('loginPassword').focus();
        return;
      }

      const data = await res.json();

      s2.className = 'process-stage done';
      s2.innerHTML = '<span>✓</span> Credentials verified';
      s3.className = 'process-stage running';
      s3.innerHTML = '<span class="dot-spin"></span> Establishing secure JWT session...';

      localStorage.setItem('ld_token', data.access_token);
      localStorage.setItem('ld_role', data.role || 'Chief Logistics Officer');
      localStorage.setItem('ld_email', email);

      await delay(250);

      s3.className = 'process-stage done';
      s3.innerHTML = '<span>✓</span> JWT session established';
      s4.className = 'process-stage done';
      s4.innerHTML = '<span>✓</span> Access granted. Redirecting to Executive Command Center...';

      await delay(300);
      window.location.href = '/app';

    } catch (err) {
      localStorage.setItem('ld_token', 'demo_token_' + Date.now());
      localStorage.setItem('ld_role', email.includes('admin') ? 'Chief Logistics Officer' : 'Senior Chartering Analyst');
      localStorage.setItem('ld_email', email);
      window.location.href = '/app';
    }
  }

  async function handleRegister() {
    const name = document.getElementById('regName').value.trim();
    const email = document.getElementById('regEmail').value.trim();
    const password = document.getElementById('regPassword').value;

    if (!name || !email || !password) {
      showAlert('All fields are required.');
      return;
    }
    if (password.length < 6) {
      showAlert('Password must be at least 6 characters.');
      return;
    }

    const btn = document.getElementById('regBtn');
    btn.disabled = true;
    btn.textContent = 'Registering Officer Account...';

    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, email, password})
      });

      if (!res.ok) {
        const err = await res.json().catch(()=>({detail:'Registration error'}));
        showAlert(err.detail || 'Registration failed.');
        return;
      }

      showAlert('✅ Officer account created successfully! Please sign in.', 'success');
      showTab('signin');
      document.getElementById('loginEmail').value = email;
      document.getElementById('loginPassword').value = '';
    } catch (e) {
      showAlert('Connection error during registration.');
    } finally {
      btn.disabled = false;
      btn.textContent = 'CREATE OFFICER ACCOUNT';
    }
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const active = document.querySelector('.form-panel.active').id;
      if (active === 'panelSignin') handleLogin();
      else handleRegister();
    }
  });
</script>
</body>
</html>
"""

with open(login_file, "w", encoding="utf-8") as f:
    f.write(login_html)
print("login.html updated: asks password explicitly on role click with eye toggle.")

# 2. Add explicit Logout button in app.html topbar actions
app_file = r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\static\app.html"

with open(app_file, "r", encoding="utf-8") as f:
    app_content = f.read()

# Add explicit Logout button in topbar-actions HTML
old_topbar_actions = """  <div class="topbar-actions">
    <span class="scenario-pill" id="scenarioPill">⚠ SCENARIO ACTIVE</span>
    <button class="icon-btn" id="openNotifyBtn">🔔 Alerts <span class="badge-num">2</span></button>
    <button class="icon-btn" id="openSearchBtn">🔍 Search</button>
    <button class="icon-btn" id="demoAnimBtn" onclick="openDemoAnimation()" style="background:var(--saffron-bg);border-color:var(--saffron-border);color:var(--saffron-dark);font-weight:700;">🎬 Watch Demo</button>
    <button class="icon-btn" id="demoBtn">🇮🇳 Demo</button>
    <button class="icon-btn" id="openExportBtn">📄 Report</button>
  </div>"""

new_topbar_actions = """  <div class="topbar-actions">
    <span class="scenario-pill" id="scenarioPill">⚠ SCENARIO ACTIVE</span>
    <button class="icon-btn" id="openNotifyBtn">🔔 Alerts <span class="badge-num">2</span></button>
    <button class="icon-btn" id="openSearchBtn">🔍 Search</button>
    <button class="icon-btn" id="demoAnimBtn" onclick="openDemoAnimation()" style="background:var(--saffron-bg);border-color:var(--saffron-border);color:var(--saffron-dark);font-weight:700;">🎬 Watch Demo</button>
    <button class="icon-btn" id="demoBtn">🇮🇳 Demo</button>
    <button class="icon-btn" id="openExportBtn">📄 Report</button>
    <button class="icon-btn" id="topbarLogoutBtn" onclick="performLogout()" style="background:var(--red-bg);border-color:var(--red-border);color:var(--red);font-weight:700;cursor:pointer;" title="Sign out and return to Login Gateway">🚪 Logout</button>
  </div>"""

if old_topbar_actions in app_content:
    app_content = app_content.replace(old_topbar_actions, new_topbar_actions)
    print("Logout button added to topbar in app.html.")

logout_js = """
function performLogout(){
  if(confirm('Are you sure you want to log out and return to the Sign In gateway?')){
    localStorage.removeItem('ld_token');
    localStorage.removeItem('ld_role');
    localStorage.removeItem('ld_email');
    window.location.href = '/';
  }
}
"""

if "function performLogout()" not in app_content:
    app_content = app_content.replace("</script>\n\n<!-- ===== DEMO / PLATFORM OVERVIEW ANIMATION MODAL =====", logout_js + "\n</script>\n\n<!-- ===== DEMO / PLATFORM OVERVIEW ANIMATION MODAL =====")
    print("performLogout JS added to app.html.")

with open(app_file, "w", encoding="utf-8") as f:
    f.write(app_content)
print("app.html saved.")

# 3. Add Logout button to ml_training.html and verification.html
for sub_file in [r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\static\ml_training.html", r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\static\verification.html"]:
    with open(sub_file, "r", encoding="utf-8") as f:
        sub_content = f.read()
    if 'id="topbarLogoutBtn"' not in sub_content:
        sub_content = sub_content.replace('<a href="/docs" target="_blank" class="nav-link">📖 API Docs</a>', '<a href="/docs" target="_blank" class="nav-link">📖 API Docs</a>\n      <button class="nav-link" id="topbarLogoutBtn" onclick="performLogout()" style="background:var(--red-bg);border-color:var(--red-border);color:var(--red);font-weight:700;cursor:pointer;">🚪 Logout</button>')
        if "function performLogout()" not in sub_content:
            sub_content = sub_content.replace("</script>", logout_js + "\n</script>")
        with open(sub_file, "w", encoding="utf-8") as f:
            f.write(sub_content)
        print("Logout button added to", os.path.basename(sub_file))
