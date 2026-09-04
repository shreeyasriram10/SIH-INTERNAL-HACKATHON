import os
import json
import time
import joblib
import pandas as pd

from sklearn.ensemble import (
    RandomForestRegressor,
    GradientBoostingRegressor,
    ExtraTreesRegressor,
)
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    r2_score,
    mean_absolute_error,
    mean_squared_error,
)


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.join(BASE_DIR, "freight_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")
META_PATH = os.path.join(BASE_DIR, "model_metadata.json")

IS_VERCEL = os.environ.get("VERCEL") == "1"


# ---------------------------------------------------------
# FEATURES
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# LOAD DATASET
# ---------------------------------------------------------

def load_dataset():
    """
    Load the committed dataset.

    IMPORTANT:
    We ONLY READ the dataset.
    We never modify it during production execution.
    """

    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"Freight dataset not found: {DATA_PATH}"
        )

    return pd.read_csv(DATA_PATH)


# ---------------------------------------------------------
# PREPARE DATA
# ---------------------------------------------------------

def prepare_dataset(df):
    """
    Convert the raw dataset into the exact feature structure
    expected by ml.py.
    """

    df = df.copy()

    # -----------------------------------------------------
    # Handle origin column
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Ensure all required feature columns exist
    # -----------------------------------------------------

    for feature in FEATURES:
        if feature not in df.columns:
            df[feature] = 0

    # -----------------------------------------------------
    # Ensure target exists
    # -----------------------------------------------------

    if TARGET not in df.columns:
        raise ValueError(
            f"Target column '{TARGET}' not found in dataset. "
            f"Available columns: {list(df.columns)}"
        )

    # -----------------------------------------------------
    # Numeric conversion
    # -----------------------------------------------------

    for column in FEATURES + [TARGET]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # -----------------------------------------------------
    # Remove invalid rows
    # -----------------------------------------------------

    df = df.dropna(
        subset=FEATURES + [TARGET]
    ).reset_index(drop=True)

    if len(df) < 10:
        raise ValueError(
            "Dataset contains too few valid records for training."
        )

    return df


# ---------------------------------------------------------
# TRAIN MODEL
# ---------------------------------------------------------

def train_model():

    start_time = time.time()

    # -----------------------------------------------------
    # Load + prepare data
    # -----------------------------------------------------

    df = load_dataset()
    df = prepare_dataset(df)

    X = df[FEATURES]
    y = df[TARGET]

    # -----------------------------------------------------
    # Train / validation split
    # -----------------------------------------------------

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42
    )

    # -----------------------------------------------------
    # Candidate models
    # -----------------------------------------------------

    candidates = {
        "RandomForestRegressor": RandomForestRegressor(
            n_estimators=150,
            random_state=42,
            n_jobs=-1
        ),

        "GradientBoostingRegressor": GradientBoostingRegressor(
            n_estimators=150,
            learning_rate=0.05,
            max_depth=3,
            random_state=42
        ),

        "ExtraTreesRegressor": ExtraTreesRegressor(
            n_estimators=150,
            random_state=42,
            n_jobs=-1
        ),

        "Ridge": Ridge(
            alpha=1.0
        ),
    }

    # -----------------------------------------------------
    # Select best model using R²
    # -----------------------------------------------------

    best_model = None
    best_algorithm = None
    best_r2 = float("-inf")

    for algorithm, model in candidates.items():

        model.fit(X_train, y_train)

        predictions = model.predict(X_test)

        score = r2_score(
            y_test,
            predictions
        )

        if score > best_r2:
            best_r2 = score
            best_model = model
            best_algorithm = algorithm

    # -----------------------------------------------------
    # Final evaluation
    # -----------------------------------------------------

    predictions = best_model.predict(X_test)

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

    # -----------------------------------------------------
    # MAPE
    # -----------------------------------------------------

    non_zero = y_test != 0

    if non_zero.any():

        mape = float(
            (
                abs(
                    (
                        y_test[non_zero]
                        - predictions[non_zero]
                    )
                    / y_test[non_zero]
                )
            ).mean()
            * 100
        )

    else:
        mape = 0.0

    duration = round(
        time.time() - start_time,
        3
    )

    # -----------------------------------------------------
    # Metadata
    # -----------------------------------------------------

    metadata = {
        "model_name": "LOHA-DRISHTI Freight Predictor",

        "algorithm": best_algorithm,

        "version": "v2.2-production",

        "dataset_type":
            "Synthetic / Calibrated Maritime Benchmark",

        "records_count": int(len(df)),

        "features_list": FEATURES,

        "target_variable": TARGET,

        "r2_score": round(r2, 4),

        "mae_usd": round(mae, 2),

        "rmse_usd": round(rmse, 2),

        "mape_pct": round(mape, 2),

        "training_duration_sec": duration,

        "status": "PREDICTION_READY"
    }

    # -----------------------------------------------------
    # IMPORTANT VERCEL FIX
    # -----------------------------------------------------
    #
    # Vercel's deployed filesystem is READ-ONLY.
    #
    # Therefore:
    #
    # LOCAL:
    #   Save the newly trained model.
    #
    # VERCEL:
    #   DO NOT overwrite model.pkl or metadata files.
    #
    # The committed model.pkl is used by /predict.
    #
    # -----------------------------------------------------

    if not IS_VERCEL:

        payload = {
            "model": best_model,
            "features": FEATURES,
            "algorithm": best_algorithm,
            "metadata": metadata
        }

        joblib.dump(
            payload,
            MODEL_PATH
        )

        with open(
            META_PATH,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                metadata,
                f,
                indent=2
            )

    else:

        print(
            "VERCEL detected: "
            "Skipping model artifact write because "
            "the deployment filesystem is read-only."
        )

    # -----------------------------------------------------
    # Return metadata
    # -----------------------------------------------------

    return metadata


# ---------------------------------------------------------
# OPTIONAL DIRECT EXECUTION
# ---------------------------------------------------------

if __name__ == "__main__":

    result = train_model()

    print(
        json.dumps(
            result,
            indent=2
        )
    )