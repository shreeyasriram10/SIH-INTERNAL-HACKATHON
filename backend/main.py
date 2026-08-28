from fastapi import FastAPI
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

# 1. ROOT "/" & "/login" SERVES THE SIGN IN & REGISTRATION GATEWAY
@app.get("/", include_in_schema=False)
@app.get("/login", include_in_schema=False)
@app.get("/signin", include_in_schema=False)
def serve_login():
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))

# 2. MAIN EXECUTIVE DASHBOARD AT "/app"
@app.get("/app", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
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
