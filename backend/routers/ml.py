import json
import logging
import os
import time
from datetime import datetime, timezone

import joblib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import auth
import models
from database import get_db
from services import model_registry, rate_horizon
from services.model_registry import FEATURES, META_PATH, MODEL_PATH, TARGET

logger = logging.getLogger(__name__)
router = APIRouter()


class ForecastRequest(BaseModel):
    origin: str = Field(min_length=1, max_length=80)
    distance_nm: float = Field(gt=0, le=25000)
    month: int = Field(ge=1, le=12)
    bunker_price: float = Field(gt=0, le=5000)
    pressure_index: float = Field(ge=0, le=100)


class CurveRequest(ForecastRequest):
    horizons: list[int] = Field(default=[7, 14, 30, 60, 90], max_length=12)


class RateHorizonRequest(BaseModel):
    """The chart window. There is deliberately no month or start-date field:
    the window is derived from the server's current date on every call, so it
    rolls forward on its own instead of being pinned to a stored anchor."""

    origin: str = Field(min_length=1, max_length=80)
    distance_nm: float | None = Field(default=None, gt=0, le=25000)
    bunker_price: float = Field(default=697.0, gt=0, le=5000)
    pressure_index: float = Field(default=52.5, ge=0, le=100)
    horizon_days: int = Field(default=30, ge=1, le=365)
    history_days: int = Field(default=14, ge=1, le=180)


def _confidence_interval(rate: float) -> tuple[float, float]:
    """Widen the band with the model's own held-out error rather than a flat
    percentage, so the interval reflects measured accuracy."""
    metadata = model_registry.get_payload().get("metadata") or {}
    rmse = float(metadata.get("rmse_usd") or 0.9)
    margin = round(max(rate * 0.05, rmse * 1.96), 2)
    return round(max(0.0, rate - margin), 2), round(rate + margin, 2)


# ---------------------------------------------------------------------------
# Model information
# ---------------------------------------------------------------------------

@router.get("/info")
def get_model_info(user: models.User = Depends(auth.get_current_user)):
    """Model metrics and the feature registry describe how the platform prices
    freight, so they sit behind a session like the predictions themselves."""
    payload = model_registry.get_payload()
    metadata = dict(payload.get("metadata") or {})

    if os.path.exists(META_PATH):
        try:
            with open(META_PATH, "r", encoding="utf-8") as file:
                on_disk = json.load(file)
            # Disk metadata is authoritative when present; it carries the timing
            # and MAPE figures recorded at training time.
            metadata = {**metadata, **on_disk}
        except (OSError, json.JSONDecodeError) as error:
            logger.warning("Could not read %s: %s", META_PATH, error)

    metadata.setdefault("model_name", "LOHA-DRISHTI Freight Predictor")
    metadata.setdefault("algorithm", payload.get("algorithm", "GradientBoostingRegressor"))
    metadata.setdefault("version", "v2.3-runtime")
    metadata.setdefault("dataset_type", "Synthetic / Calibrated Maritime Benchmark")
    metadata.setdefault("features_list", FEATURES)
    metadata.setdefault("target_variable", TARGET)
    metadata.setdefault("status", "PREDICTION_READY")
    metadata["model_artifact_present"] = os.path.exists(MODEL_PATH)
    return metadata


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

@router.post("/train")
def trigger_training(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_roles("Admin", "Analyst")),
):
    """Retrain from the committed dataset, persist the artifact, and publish it
    to the in-process cache so subsequent predictions use it immediately."""
    started = time.perf_counter()
    try:
        result = model_registry.train_runtime_model(select_model=True)
    except Exception as error:
        logger.exception("Training failed")
        raise HTTPException(status_code=500, detail=f"Training failed: {error}")

    meta = result["metadata"]
    meta["training_duration_sec"] = round(time.perf_counter() - started, 2)
    meta["trained_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Persisting is best-effort: serverless filesystems are read-only, and the
    # in-memory model is already usable without a saved artifact.
    try:
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump(result, MODEL_PATH)
        with open(META_PATH, "w", encoding="utf-8") as file:
            json.dump(meta, file, indent=2)
        meta["persisted"] = True
    except OSError as error:
        logger.warning("Could not persist model artifact: %s", error)
        meta["persisted"] = False

    model_registry.set_payload(result)

    try:
        db.add(models.TrainingHistory(
            training_run_id=f"RUN-{int(datetime.now(timezone.utc).timestamp())}",
            algorithm=meta["algorithm"],
            dataset_size=meta["records_count"],
            r2_score=meta["r2_score"],
            mae_usd=meta["mae_usd"],
            rmse_usd=meta["rmse_usd"],
            training_duration_sec=meta["training_duration_sec"],
            status="SUCCESS",
        ))

        db_meta = db.query(models.MLModelMetadata).first() or models.MLModelMetadata()
        db_meta.model_name = meta["model_name"]
        db_meta.algorithm = meta["algorithm"]
        db_meta.version = meta["version"]
        db_meta.dataset_type = meta["dataset_type"]
        db_meta.records_count = meta["records_count"]
        db_meta.features_list = json.dumps(meta["features_list"])
        db_meta.target_variable = meta["target_variable"]
        db_meta.r2_score = meta["r2_score"]
        db_meta.mae_usd = meta["mae_usd"]
        db_meta.rmse_usd = meta["rmse_usd"]
        db_meta.mape_pct = meta["mape_pct"]
        db_meta.is_active = True
        db_meta.trained_at = datetime.now(timezone.utc)
        db.add(db_meta)

        db.add(models.AuditLog(
            action="ML_MODEL_TRAINED",
            user_email=user.email,
            details=f"Algorithm: {meta['algorithm']}, R2: {meta['r2_score']}, "
                    f"MAE: ${meta['mae_usd']}",
        ))
        db.commit()
    except Exception as error:
        db.rollback()
        logger.warning("Could not record training run: %s", error)

    return {
        "status": "SUCCESS",
        "message": "ML model trained successfully.",
        "metadata": meta,
    }


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

@router.post("/predict")
def predict_freight(
    request: ForecastRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    try:
        rate = max(0.0, model_registry.predict_rate(request.model_dump()))
    except Exception as error:
        logger.exception("Prediction failed")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {error}")

    ci_lower, ci_upper = _confidence_interval(rate)
    payload = model_registry.get_payload()

    try:
        db.add(models.ForecastHistory(
            origin=request.origin,
            horizon_days=30,  # /predict is a single-point call; the chart uses /rate-horizon
            predicted_rate_usd=round(rate, 2),
            ci_lower_usd=ci_lower,
            ci_upper_usd=ci_upper,
            bunker_price_usd=request.bunker_price,
            pressure_index=request.pressure_index,
        ))
        db.commit()
    except Exception as error:
        db.rollback()
        logger.warning("Could not record forecast: %s", error)

    return {
        "status": "SUCCESS",
        "prediction": round(rate, 2),
        "predicted_rate_usd": round(rate, 2),
        "confidence_interval": [ci_lower, ci_upper],
        "algorithm": payload.get("algorithm", "GradientBoostingRegressor"),
        "data_source": "SYNTHETIC (BDI-Calibrated)",
        "predicted_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "features_evaluated": {
            "origin": request.origin,
            "distance_nm": request.distance_nm,
            "month": request.month,
            "bunker_price_usd": request.bunker_price,
            "market_pressure_index": request.pressure_index,
        },
    }


@router.post("/forecast-curve")
def forecast_curve(
    request: CurveRequest,
    user: models.User = Depends(auth.get_current_user),
):
    """Rate curve across several horizons in one round trip.

    Each horizon walks the calendar forward from the requested month, which is
    what makes the curve move: seasonality is a model input. Scored as a single
    batch rather than one request per point.
    """
    horizons = sorted({max(1, int(h)) for h in request.horizons})[:12]
    rows = []
    for horizon in horizons:
        offset_month = ((request.month - 1 + round(horizon / 30.0)) % 12) + 1
        rows.append({
            "origin": request.origin,
            "distance_nm": request.distance_nm,
            "month": offset_month,
            "bunker_price": request.bunker_price,
            "pressure_index": request.pressure_index,
        })

    try:
        rates = model_registry.predict_rates(rows)
    except Exception as error:
        logger.exception("Forecast curve failed")
        raise HTTPException(status_code=500, detail=f"Forecast failed: {error}")

    points = []
    for horizon, row, rate in zip(horizons, rows, rates):
        rate = max(0.0, rate)
        ci_lower, ci_upper = _confidence_interval(rate)
        points.append({
            "horizon_days": horizon,
            "month": row["month"],
            "predicted_rate_usd": round(rate, 2),
            "ci_lower_usd": ci_lower,
            "ci_upper_usd": ci_upper,
        })

    return {
        "status": "SUCCESS",
        "origin": request.origin,
        "data_source": "SYNTHETIC (BDI-Calibrated)",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "points": points,
    }


@router.post("/rate-horizon")
def rate_horizon_series(
    request: RateHorizonRequest,
    user: models.User = Depends(auth.get_current_user),
):
    """Daily rate series for the dashboard's freight-rate chart.

    The window is always [today - history_days + 1 ... today + horizon_days],
    computed from the server clock at request time, and the first forecast day
    is anchored to the last historical value so the two legs join cleanly at
    the TODAY divider.
    """
    distance = request.distance_nm or model_registry.ORIGIN_DISTANCE_NM.get(
        request.origin, 4500.0
    )
    try:
        window = rate_horizon.build_horizon(
            origin=request.origin,
            distance_nm=distance,
            bunker_price=request.bunker_price,
            pressure_index=request.pressure_index,
            horizon_days=request.horizon_days,
            history_days=request.history_days,
        )
    except Exception as error:
        logger.exception("Rate horizon failed")
        raise HTTPException(status_code=500, detail=f"Rate horizon failed: {error}")

    payload = model_registry.get_payload()
    window["status"] = "SUCCESS"
    window["distance_nm"] = distance
    window["algorithm"] = payload.get("algorithm", "GradientBoostingRegressor")
    window["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return window
