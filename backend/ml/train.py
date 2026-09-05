"""Offline trainer for the freight-rate model.

Run it from the repo root to (re)build backend/ml/model.pkl:

    python backend/ml/train.py

The training logic itself lives in services.model_registry so the CLI, the
/api/ml/train endpoint, and the cold-start fallback all fit the same model on
the same features - there is only one definition to keep in step.
"""

import json
import os
import sys
import time

import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import model_registry  # noqa: E402


def train_model(persist: bool = True) -> dict:
    """Fit the model and, unless told otherwise, write the artifact + metadata."""
    started = time.perf_counter()
    result = model_registry.train_runtime_model()

    metadata = result["metadata"]
    metadata["training_duration_sec"] = round(time.perf_counter() - started, 2)
    metadata["trained_at"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    if persist:
        try:
            os.makedirs(os.path.dirname(model_registry.MODEL_PATH), exist_ok=True)
            joblib.dump(result, model_registry.MODEL_PATH)
            with open(model_registry.META_PATH, "w", encoding="utf-8") as file:
                json.dump(metadata, file, indent=2)
            metadata["persisted"] = True
        except OSError as error:
            # Read-only filesystems (serverless) are expected; the in-memory
            # model is still returned and usable.
            print(f"Could not persist artifact: {error}")
            metadata["persisted"] = False

    model_registry.set_payload(result)
    return metadata


if __name__ == "__main__":
    meta = train_model()
    print(json.dumps(meta, indent=2))
    print(
        f"\nR2 {meta['r2_score']}  |  MAE ${meta['mae_usd']}/MT  |  "
        f"RMSE ${meta['rmse_usd']}/MT  |  MAPE {meta['mape_pct']}%"
    )
