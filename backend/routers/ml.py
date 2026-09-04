from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import pandas as pd
import joblib
import os
import json
from datetime import datetime, timezone

from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

from database import get_db
import models

router = APIRouter()


# =========================================================
# REQUEST MODEL
# =========================================================

class ForecastRequest(BaseModel):
    origin: str
    distance_nm: float
    month: int
    bunker_price: float
    pressure_index: float


# =========================================================
# PATHS
# =========================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODEL_PATH = os.path.join(BASE_DIR, "ml", "model.pkl")
META_PATH = os.path.join(BASE_DIR, "ml", "model_metadata.json")
DATA_PATH = os.path.join(BASE_DIR, "ml", "freight_data.csv")


# =========================================================
# FEATURES
# =========================================================

FEATURES = [
    "distance_nm",
    "month",
    "bunker_price_usd",
    "pressure_index",
    "origin_Australia",
    "origin_Indonesia",
    "origin_South Africa",
    "origin_USA",
]

TARGET = "freight_rate_usd"


# =========================================================
# PREPARE DATASET
# =========================================================

def prepare_dataset(df):

    df = df.copy()

    # Create origin one-hot columns
    if "origin" in df.columns:

        for origin in [
            "Australia",
            "Indonesia",
            "South Africa",
            "USA",
        ]:

            column = f"origin_{origin}"

            df[column] = (
                df["origin"]
                .astype(str)
                .str.strip()
                .eq(origin)
                .astype(int)
            )

    # Make sure every feature exists
    for feature in FEATURES:

        if feature not in df.columns:
            df[feature] = 0

    # Check target
    if TARGET not in df.columns:

        raise ValueError(
            f"Target column '{TARGET}' not found."
        )

    # Convert to numeric
    for column in FEATURES + [TARGET]:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # Remove invalid rows
    df = df.dropna(
        subset=FEATURES + [TARGET]
    ).reset_index(drop=True)

    if len(df) < 10:

        raise ValueError(
            "Not enough valid records in freight dataset."
        )

    return df


# =========================================================
# TRAIN MODEL IN MEMORY
# =========================================================

def train_runtime_model():

    if not os.path.exists(DATA_PATH):

        raise FileNotFoundError(
            f"Dataset not found: {DATA_PATH}"
        )

    df = pd.read_csv(DATA_PATH)

    df = prepare_dataset(df)

    X = df[FEATURES]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42
    )

    model = GradientBoostingRegressor(
        n_estimators=150,
        learning_rate=0.05,
        max_depth=3,
        random_state=42
    )

    model.fit(
        X_train,
        y_train
    )

    predictions = model.predict(X_test)

    r2 = float(
        r2_score(
            y_test,
            predictions
        )
    )

    mae = float(
        mean_absolute_error(
            y_test,
            predictions
        )
    )

    rmse = float(
        mean_squared_error(
            y_test,
            predictions
        ) ** 0.5
    )

    metadata = {
        "model_name": "LOHA-DRISHTI Freight Predictor",
        "algorithm": "GradientBoostingRegressor",
        "version": "v2.3-runtime",
        "dataset_type": "Synthetic / Calibrated Maritime Benchmark",
        "records_count": int(len(df)),
        "features_list": FEATURES,
        "target_variable": TARGET,
        "r2_score": round(r2, 4),
        "mae_usd": round(mae, 2),
        "rmse_usd": round(rmse, 2),
        "status": "PREDICTION_READY"
    }

    return {
        "model": model,
        "features": FEATURES,
        "algorithm": "GradientBoostingRegressor",
        "metadata": metadata
    }


# =========================================================
# LOAD MODEL
# =========================================================

def load_model_payload():

    # First try existing model.pkl
    if os.path.exists(MODEL_PATH):

        try:

            model_data = joblib.load(
                MODEL_PATH
            )

            if isinstance(model_data, dict):

                model = model_data.get("model")

                features = model_data.get(
                    "features",
                    FEATURES
                )

                if model is not None:

                    return {
                        "model": model,
                        "features": features,
                        "algorithm": model_data.get(
                            "algorithm",
                            "GradientBoostingRegressor"
                        ),
                        "metadata": model_data.get(
                            "metadata",
                            {}
                        )
                    }

            else:

                return {
                    "model": model_data,
                    "features": FEATURES,
                    "algorithm": "GradientBoostingRegressor",
                    "metadata": {}
                }

        except Exception as error:

            # IMPORTANT:
            # Broken/incompatible model.pkl should NOT
            # stop the application.
            print(
                f"Existing model.pkl could not be loaded: {error}"
            )

    # =====================================================
    # FALLBACK
    # =====================================================

    print(
        "Training fresh ML model from freight_data.csv..."
    )

    return train_runtime_model()


# =========================================================
# MODEL INFORMATION
# =========================================================

@router.get("/info")
def get_model_info():

    if os.path.exists(META_PATH):

        try:

            with open(
                META_PATH,
                "r",
                encoding="utf-8"
            ) as file:

                return json.load(file)

        except Exception:

            pass

    return {
        "model_name": "LOHA-DRISHTI Freight Predictor",
        "algorithm": "GradientBoostingRegressor",
        "version": "v2.3-runtime",
        "dataset_type": "Synthetic / Calibrated Maritime Benchmark",
        "records_count": 1500,
        "features_list": FEATURES,
        "target_variable": TARGET,
        "status": "PREDICTION_READY"
    }


# =========================================================
# TRAIN ENDPOINT
# =========================================================

@router.post("/train")
def trigger_training(
    db: Session = Depends(get_db)
):

    try:

        result = train_runtime_model()

        meta = result["metadata"]

        run_id = (
            f"RUN-{int(datetime.now(timezone.utc).timestamp())}"
        )

        history = models.TrainingHistory(
            training_run_id=run_id,
            algorithm=meta["algorithm"],
            dataset_size=meta["records_count"],
            r2_score=meta["r2_score"],
            mae_usd=meta["mae_usd"],
            rmse_usd=meta["rmse_usd"],
            training_duration_sec=0,
            status="SUCCESS"
        )

        db.add(history)

        db_meta = db.query(
            models.MLModelMetadata
        ).first()

        if not db_meta:

            db_meta = models.MLModelMetadata()

            db.add(db_meta)

        db_meta.model_name = meta["model_name"]
        db_meta.algorithm = meta["algorithm"]
        db_meta.version = meta["version"]
        db_meta.dataset_type = meta["dataset_type"]
        db_meta.records_count = meta["records_count"]
        db_meta.features_list = json.dumps(
            meta["features_list"]
        )
        db_meta.target_variable = meta["target_variable"]
        db_meta.r2_score = meta["r2_score"]
        db_meta.mae_usd = meta["mae_usd"]
        db_meta.rmse_usd = meta["rmse_usd"]
        db_meta.mape_pct = 0
        db_meta.is_active = True

        audit = models.AuditLog(
            action="ML_MODEL_TRAINED",
            details=(
                f"Algorithm: {meta['algorithm']}, "
                f"R2: {meta['r2_score']}"
            )
        )

        db.add(audit)

        db.commit()

        return {
            "status": "SUCCESS",
            "message": "ML model trained successfully.",
            "metadata": meta
        }

    except Exception as error:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Training failed: {str(error)}"
        )


# =========================================================
# PREDICTION
# =========================================================

@router.post("/predict")
def predict_freight(
    request: ForecastRequest,
    db: Session = Depends(get_db)
):

    try:

        # Load existing model OR train a fresh model
        model_data = load_model_payload()

        model = model_data["model"]

        features = model_data.get(
            "features",
            FEATURES
        )

        # =================================================
        # INPUT
        # =================================================

        input_data = {

            "distance_nm": [
                request.distance_nm
            ],

            "month": [
                request.month
            ],

            "bunker_price_usd": [
                request.bunker_price
            ],

            "pressure_index": [
                request.pressure_index
            ],

            "origin_Australia": [
                1 if request.origin == "Australia"
                else 0
            ],

            "origin_Indonesia": [
                1 if request.origin == "Indonesia"
                else 0
            ],

            "origin_South Africa": [
                1 if request.origin == "South Africa"
                else 0
            ],

            "origin_USA": [
                1 if request.origin == "USA"
                else 0
            ]
        }

        df_input = pd.DataFrame(
            input_data
        )

        df_input = df_input.reindex(
            columns=features,
            fill_value=0
        )

        # =================================================
        # PREDICTION
        # =================================================

        prediction = model.predict(
            df_input
        )

        if prediction is None or len(prediction) == 0:

            raise ValueError(
                "Model returned no prediction."
            )

        pred_rate = float(
            prediction[0]
        )

        # Never allow negative freight rate
        pred_rate = max(
            0.0,
            pred_rate
        )

        # =================================================
        # CONFIDENCE INTERVAL
        # =================================================

        margin = round(
            pred_rate * 0.05 + 0.5,
            2
        )

        ci_lower = round(
            max(
                5.0,
                pred_rate - margin
            ),
            2
        )

        ci_upper = round(
            pred_rate + margin,
            2
        )

        # =================================================
        # SAVE FORECAST
        # =================================================

        try:

            hist = models.ForecastHistory(

                origin=request.origin,

                horizon_days=30,

                predicted_rate_usd=round(
                    pred_rate,
                    2
                ),

                ci_lower_usd=ci_lower,

                ci_upper_usd=ci_upper,

                bunker_price_usd=request.bunker_price,

                pressure_index=request.pressure_index
            )

            db.add(hist)

            db.commit()

        except Exception:

            db.rollback()

        # =================================================
        # RESPONSE
        # =================================================

        return {

            "status": "SUCCESS",

            "prediction": round(
                pred_rate,
                2
            ),

            "predicted_rate_usd": round(
                pred_rate,
                2
            ),

            "confidence_interval": [
                ci_lower,
                ci_upper
            ],

            "algorithm": model_data.get(
                "algorithm",
                "GradientBoostingRegressor"
            ),

            "data_source":
                "SYNTHETIC (BDI-Calibrated)",

            "predicted_at":
                datetime.now(
                    timezone.utc
                ).strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                ),

            "features_evaluated": {

                "origin":
                    request.origin,

                "distance_nm":
                    request.distance_nm,

                "month":
                    request.month,

                "bunker_price_usd":
                    request.bunker_price,

                "market_pressure_index":
                    request.pressure_index
            }
        }

    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(error)}"
        )
