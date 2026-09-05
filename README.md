# LOHA DRISHTI

Maritime cargo chartering and decision intelligence for **Steel Authority of India Limited (SAIL)** — Smart India Hackathon, Ministry of Steel.

Given a bulk parcel (coking coal, thermal coal, iron ore) the platform answers one question: **which vessel class, through which discharge port, at what cost and what risk.**

---

## Quick start

```bash
pip install -r requirements.txt
```

```bash
python backend/ml/train.py
```

```bash
python -m uvicorn main:app --reload --app-dir backend --port 8000
```

On Windows you can instead run `run.bat`, which does the same thing and prints the URLs.

| Page | URL |
|---|---|
| Sign-in gateway | http://localhost:8000/ |
| Executive dashboard | http://localhost:8000/app |
| ML model & training | http://localhost:8000/ml-training |
| System verification | http://localhost:8000/verification |
| OpenAPI / Swagger | http://localhost:8000/docs |

**Demo accounts** (seeded on first boot, real bcrypt hashes — there is no bypass):

| Email | Password | Role |
|---|---|---|
| admin@sail.gov.in | 12345 | Admin |
| analyst@sail.gov.in | 12345 | Analyst |
| officer@sail.gov.in | 12345 | Procurement Officer |

---

## Architecture

```
api/index.py            Vercel entrypoint (imports backend/main.py)
backend/
  main.py               FastAPI app: routers, static pages, startup lifespan
  auth.py               bcrypt hashing, JWT issue/verify, auth dependencies
  database.py           SQLAlchemy engine, session, forward-only column migration
  models.py             14 ORM tables
  schemas.py            Pydantic v2 request/response models
  seed_data.py          Idempotent reference-data + demo-account seeding
  routers/              auth, ports, vessels, cargo, ml, decision, system, waterways
  services/
    model_registry.py   Single cached owner of the freight model
    decision_engine.py  Vessel x port optimisation and risk scoring
  ml/train.py           Offline trainer -> model.pkl + model_metadata.json
  static/               The four served HTML pages
  tests/test_api.py     42 tests
```

The dashboard is a view over the API. Port and vessel figures are pulled from
`/api/ports` and `/api/vessels` at page load, and every recommendation comes
from `/api/decision/optimize`. A badge in the header reads **LIVE MODEL** when
the numbers came from the service and **OFFLINE ESTIMATE** when the API was
unreachable and the page fell back to its local approximation — an estimate is
never presented as a model output.

---

## The decision engine

`services/decision_engine.py` scores every feasible (vessel class × discharge
port) pairing and ranks them on **risk-adjusted landed cost**.

Cost stack, per candidate, in USD:

| Component | Source |
|---|---|
| Ocean freight | predicted USD/MT × parcel tonnage |
| Deadfreight | booked-but-unfilled space beyond a 10% tolerance |
| Vessel hire | (sea days + port days) × daily hire |
| Port dues | flat rate per tonne discharged |
| Demurrage | waiting beyond free laytime, at the berth's own rate |
| Lightering | only where the berth cannot take the laden draft |
| Inland evacuation | rail km to plant × tariff × tonnage |

Feasibility is a real filter: a candidate is dropped when the laden draft
exceeds the berth's usable draft by more than 4 m, or when the LOA limit cannot
take the class. Part-loaded ships float higher, so laden draft is scaled by
utilisation.

The risk index (0–100) is a weighted blend of berth congestion (30%), seasonal
exposure (25%), freight volatility (25%) and under-keel margin (20%). Ranking
minimises `cost_per_tonne × (1 + 0.35 × risk/100)`.

`POST /api/decision/simulate` runs the optimizer twice — baseline and shocked —
for cyclone, monsoon, port closure, freight spike, bunker spike and vessel
unavailability, and reports the delta with a mitigation.

## The model

Gradient-boosted regressor over 1,500 calibrated records, predicting
`freight_rate_usd` from distance, month, bunker price, market pressure index and
a one-hot origin.

```
R² 0.9906   MAE $0.65/MT   RMSE $0.84/MT   MAPE 2.90%
```

The dataset is **synthetic, calibrated against dry-bulk benchmarks** — every
response that carries a prediction says so in a `data_source` field. Origins are
Australia, Indonesia, South Africa and USA; adding one to the UI without
retraining would fall back to a default lane distance.

`services/model_registry.py` owns the model. It is unpickled once per process
and reloaded only when `model.pkl` changes on disk, and predictions are scored
as a single batch. If the artifact is missing or was written by an incompatible
scikit-learn build, the registry trains a fresh model in memory rather than
failing the request.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `LOHA_SECRET_KEY` | *(random per process)* | JWT signing key. **Set this in any deployment** — without it, sessions do not survive a restart. |
| `LOHA_TOKEN_TTL_MIN` | `720` | Access-token lifetime in minutes. |
| `LOHA_CORS_ORIGINS` | localhost dev origins | Comma-separated allow-list. |
| `LOHA_DEMO_PASSWORD` | `12345` | Password given to the seeded demo accounts. |
| `LOHA_REPAIR_DEMO_ACCOUNTS` | `1` | Reset the three demo accounts' hash/role on boot. Set `0` in production. |
| `LOHA_LOG_LEVEL` | `INFO` | Root log level. |

Copy `.env.example` and adjust.

---

## Tests

```bash
python -m pytest backend/tests -q
```

42 tests covering page routing, authentication and authorization (including
that the demo password is *not* a bypass), reference data, the ML pipeline and
caching, the decision engine's ranking, cost identity and vessel selection, the
disruption scenarios, and the live system battery.

`/api/system/run-tests` runs a subset in-process and is what the verification
page displays.

---

## Deployment notes

`vercel.json` routes everything to `api/index.py`. Two caveats:

- **SQLite does not persist on serverless.** `database.py` copies the file to
  `/tmp` on Vercel/Lambda; every cold start resets writes. Point
  `SQLALCHEMY_DATABASE_URL` at a managed Postgres for anything real.
- The model artifact may be absent in a fresh container; the registry trains in
  memory on first use, which costs about 0.2 s once.
