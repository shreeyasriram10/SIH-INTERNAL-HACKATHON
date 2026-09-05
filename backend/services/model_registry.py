"""Single owner of the freight-rate model.

Every consumer (the /api/ml endpoints and the decision engine) goes through
here, so the model is unpickled at most once per process and reused, instead
of being reloaded - or worse, retrained - on every request.
"""

import logging
import os
import threading

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "ml", "model.pkl")
META_PATH = os.path.join(BASE_DIR, "ml", "model_metadata.json")
DATA_PATH = os.path.join(BASE_DIR, "ml", "freight_data.csv")

ORIGINS = ["Australia", "Indonesia", "South Africa", "USA"]

FEATURES = [
    "distance_nm",
    "month",
    "bunker_price_usd",
    "pressure_index",
    *[f"origin_{origin}" for origin in ORIGINS],
]
TARGET = "freight_rate_usd"

# Canonical one-way voyage distances (nautical miles) to the Indian east coast.
# These match the distances present in the training set, so a prediction for an
# origin is evaluated at the same point in feature space the model learned.
ORIGIN_DISTANCE_NM = {
    "Australia": 4500.0,
    "Indonesia": 2200.0,
    "South Africa": 3800.0,
    "USA": 8500.0,
}

_lock = threading.Lock()
_cache: dict = {"payload": None, "signature": None}


# ---------------------------------------------------------------------------
# Dataset preparation
# ---------------------------------------------------------------------------

def prepare_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "origin" in df.columns:
        normalised = df["origin"].astype(str).str.strip()
        for origin in ORIGINS:
            df[f"origin_{origin}"] = normalised.eq(origin).astype(int)

    for feature in FEATURES:
        if feature not in df.columns:
            df[feature] = 0

    if TARGET not in df.columns:
        raise ValueError(f"Target column '{TARGET}' not found.")

    for column in FEATURES + [TARGET]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=FEATURES + [TARGET]).reset_index(drop=True)
    if len(df) < 10:
        raise ValueError("Not enough valid records in freight dataset.")
    return df


def build_feature_frame(rows, features=None) -> pd.DataFrame:
    """Turn plain dicts into a model-ready frame.

    Built once for a whole batch so the caller can score many candidates with a
    single model.predict call rather than one call per candidate.
    """
    records = []
    for row in rows:
        origin = str(row.get("origin", "")).strip()
        distance = row.get("distance_nm") or ORIGIN_DISTANCE_NM.get(origin, 4500.0)
        record = {
            "distance_nm": float(distance),
            "month": int(row.get("month", 1)),
            "bunker_price_usd": float(
                row.get("bunker_price", row.get("bunker_price_usd", 700.0))
            ),
            "pressure_index": float(row.get("pressure_index", 50.0)),
        }
        for known in ORIGINS:
            record[f"origin_{known}"] = 1 if origin == known else 0
        records.append(record)

    frame = pd.DataFrame(records)
    return frame.reindex(columns=features or FEATURES, fill_value=0)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_runtime_model() -> dict:
    """Train from the committed CSV.

    Used by /api/ml/train and as the cold-start fallback when model.pkl is
    absent (a fresh serverless container), so prediction never hard-fails on a
    missing artifact.
    """
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    df = prepare_dataset(pd.read_csv(DATA_PATH))
    X, y = df[FEATURES], df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )

    model = GradientBoostingRegressor(
        n_estimators=150, learning_rate=0.05, max_depth=3, random_state=42
    )
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    mape = float((abs((y_test - predictions) / y_test)).mean() * 100)

    metadata = {
        "model_name": "LOHA-DRISHTI Freight Predictor",
        "algorithm": "GradientBoostingRegressor",
        "version": "v2.3-runtime",
        "dataset_type": "Synthetic / Calibrated Maritime Benchmark",
        "records_count": int(len(df)),
        "features_list": FEATURES,
        "target_variable": TARGET,
        "r2_score": round(float(r2_score(y_test, predictions)), 4),
        "mae_usd": round(float(mean_absolute_error(y_test, predictions)), 2),
        "rmse_usd": round(float(mean_squared_error(y_test, predictions) ** 0.5), 2),
        "mape_pct": round(mape, 2),
        "status": "PREDICTION_READY",
    }
    return {
        "model": model,
        "features": FEATURES,
        "algorithm": "GradientBoostingRegressor",
        "metadata": metadata,
    }


# ---------------------------------------------------------------------------
# Cached access
# ---------------------------------------------------------------------------

def _disk_signature():
    try:
        stat = os.stat(MODEL_PATH)
        return (stat.st_mtime_ns, stat.st_size)
    except OSError:
        return None


def _normalise(raw) -> dict:
    if isinstance(raw, dict) and raw.get("model") is not None:
        return {
            "model": raw["model"],
            "features": raw.get("features", FEATURES),
            "algorithm": raw.get("algorithm", "GradientBoostingRegressor"),
            "metadata": raw.get("metadata", {}),
        }
    return {
        "model": raw,
        "features": FEATURES,
        "algorithm": "GradientBoostingRegressor",
        "metadata": {},
    }


def get_payload(force_reload: bool = False) -> dict:
    """Return the cached model payload.

    Reloads only when model.pkl changes on disk, so a /api/ml/train run is
    picked up without a restart while normal traffic pays no I/O cost.
    """
    signature = _disk_signature()

    cached = _cache["payload"]
    if cached is not None and not force_reload and _cache["signature"] == signature:
        return cached

    with _lock:
        # Re-check inside the lock: a concurrent request may have just filled it.
        cached = _cache["payload"]
        if cached is not None and not force_reload and _cache["signature"] == signature:
            return cached

        payload = None
        if signature is not None:
            try:
                payload = _normalise(joblib.load(MODEL_PATH))
            except Exception as error:
                # A broken or version-incompatible pickle must not take the API
                # down; fall through and train a fresh model in memory.
                logger.warning("Could not load %s: %s", MODEL_PATH, error)

        if payload is None:
            logger.info("Training a fresh ML model from freight_data.csv...")
            payload = train_runtime_model()
            signature = _disk_signature()

        _cache["payload"] = payload
        _cache["signature"] = signature
        return payload


def set_payload(payload: dict) -> None:
    """Publish a freshly trained model without a disk round-trip."""
    with _lock:
        _cache["payload"] = _normalise(payload)
        _cache["signature"] = _disk_signature()


def invalidate() -> None:
    with _lock:
        _cache["payload"] = None
        _cache["signature"] = None


def predict_rates(rows) -> list:
    """Batch-predict USD/MT freight rates with one model call for the batch."""
    if not rows:
        return []
    payload = get_payload()
    frame = build_feature_frame(rows, payload["features"])
    return [float(value) for value in payload["model"].predict(frame)]


def predict_rate(row: dict) -> float:
    return predict_rates([row])[0]
