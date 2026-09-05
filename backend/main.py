import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import models
import seed_data
from database import engine, ensure_columns
from routers import auth, cargo, decision, ml, ports, system, vessels, waterways

logging.basicConfig(
    level=os.environ.get("LOHA_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("lohadrishti")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# The dashboard is served from the same origin as the API, so the default
# allow-list only needs to cover local dev front ends. Override in deployment
# with LOHA_CORS_ORIGINS="https://a.example,https://b.example".
_origins_env = os.environ.get("LOHA_CORS_ORIGINS", "").strip()
CORS_ORIGINS = (
    [origin.strip() for origin in _origins_env.split(",") if origin.strip()]
    if _origins_env
    else ["http://localhost:5173", "http://localhost:8000", "http://127.0.0.1:8000"]
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    models.Base.metadata.create_all(bind=engine)
    try:
        ensure_columns(models.Base)
    except Exception:
        logger.exception("Schema reconciliation failed")
    try:
        seed_data.seed_database()
    except Exception:
        # Seeding must never block startup, but the traceback has to be visible
        # rather than silently swallowed.
        logger.exception("Initial seeding failed; continuing with an empty database")
    yield


app = FastAPI(
    title="LOHA DRISHTI API",
    version="2.3.0",
    description=(
        "Maritime Cargo Chartering & Decision Intelligence Platform - "
        "Steel Authority of India Limited (SAIL) / Ministry of Steel"
    ),
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(ports.router, prefix="/api/ports", tags=["ports"])
app.include_router(vessels.router, prefix="/api/vessels", tags=["vessels"])
app.include_router(cargo.router, prefix="/api/cargo", tags=["cargo"])
app.include_router(ml.router, prefix="/api/ml", tags=["ml"])
app.include_router(decision.router, prefix="/api/decision", tags=["decision"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(waterways.router, prefix="/api/waterways", tags=["waterways"])

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


_PAGE_CACHE: dict[str, str] = {}


def _page(filename: str) -> HTMLResponse:
    """Serve an HTML shell with caching switched off.

    FileResponse sends Last-Modified from the file's mtime, and Vercel freezes
    deployed mtimes to a fixed timestamp for reproducible builds. That value is
    therefore identical across every deployment, so a browser revalidating with
    If-Modified-Since gets a 304 and keeps showing the previous build's HTML
    indefinitely - a redeploy never reaches anyone who already loaded the page.

    Returning the body directly sends no Last-Modified or ETag, so there is
    nothing to revalidate against and the client always receives current
    markup. The file is read once per process; these shells change only on
    deploy, and each new deployment starts fresh containers.
    """
    body = _PAGE_CACHE.get(filename)
    if body is None:
        with open(os.path.join(STATIC_DIR, filename), "r", encoding="utf-8") as handle:
            body = handle.read()
        _PAGE_CACHE[filename] = body

    return HTMLResponse(
        content=body,
        headers={
            "Cache-Control": "no-store, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@app.get("/healthz", tags=["system"])
def healthz():
    return {"status": "ok", "version": app.version}


# 1. Sign-in / registration gateway
@app.get("/", include_in_schema=False)
@app.get("/login", include_in_schema=False)
@app.get("/signin", include_in_schema=False)
def serve_login():
    return _page("login.html")


# 2. Executive dashboard
@app.get("/app", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    return _page("app.html")


# 3. ML model & training console
@app.get("/ml-training", include_in_schema=False)
@app.get("/ml", include_in_schema=False)
def serve_ml_page():
    return _page("ml_training.html")


# 4. System verification / live test battery
@app.get("/verification", include_in_schema=False)
@app.get("/system-verification", include_in_schema=False)
def serve_verification_page():
    return _page("verification.html")
