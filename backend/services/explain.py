"""Why the freight model predicts what it predicts.

The decision engine already explains its ranking (cost waterfall, risk
breakdown, reasons). The model inside it was a black box: it returned a rate
with no account of where the number came from. Two views close that gap.

LOCAL - exact Shapley values for one prediction. The model's inputs are
grouped into four drivers a chartering desk recognises (the lane, the month,
bunker price, market pressure). With four players there are only 16
coalitions, so the values are computed exactly rather than sampled: for each
coalition the drivers inside it are set to the query's values and the rest
are drawn from a background sample of the training data (interventional
Shapley). The attributions add up exactly to the prediction minus the
model's average prediction over that background.

GLOBAL - permutation importance on the untouched hold-out split: how much the
mean absolute error grows when one driver is shuffled. Cached per model.
"""

import itertools
import math

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from services import model_registry

GROUPS = {
    "Lane (origin & distance)": ["distance_nm", *[f"origin_{o}" for o in model_registry.ORIGINS]],
    "Month / season": ["month"],
    "Bunker price": ["bunker_price_usd"],
    "Market pressure": ["pressure_index"],
}
BACKGROUND_ROWS = 120

_cache = {"key": None, "background": None, "holdout": None, "importance": None}


def _data():
    payload = model_registry.get_payload()
    key = id(payload["model"])
    if _cache["key"] != key:
        df = model_registry.prepare_dataset(pd.read_csv(model_registry.DATA_PATH))
        features = payload["features"]
        X, y = df[features], df[model_registry.TARGET]
        _, X_test, _, y_test = train_test_split(X, y, test_size=0.20, random_state=42)
        _cache.update(key=key, importance=None,
                      background=X.sample(n=min(BACKGROUND_ROWS, len(X)), random_state=7).reset_index(drop=True),
                      holdout=(X_test.reset_index(drop=True), y_test.reset_index(drop=True)))
    return payload, _cache["background"], _cache["holdout"]


def shapley(row: dict) -> dict:
    payload, background, _ = _data()
    features = payload["features"]
    query = model_registry.build_feature_frame([row], features).iloc[0]
    players = list(GROUPS)

    # One batch: every coalition x every background row.
    coalitions = [frozenset(c) for r in range(len(players) + 1) for c in itertools.combinations(players, r)]
    frames = []
    for coalition in coalitions:
        frame = background.copy()
        for player in coalition:
            for column in GROUPS[player]:
                if column in frame.columns:
                    frame[column] = query[column]
        frames.append(frame)
    predictions = payload["model"].predict(pd.concat(frames, ignore_index=True))
    n = len(background)
    value = {c: float(predictions[i * n:(i + 1) * n].mean()) for i, c in enumerate(coalitions)}

    total = len(players)
    contributions = {}
    for player in players:
        phi = 0.0
        for coalition in coalitions:
            if player in coalition:
                continue
            weight = math.factorial(len(coalition)) * math.factorial(total - len(coalition) - 1) / math.factorial(total)
            phi += weight * (value[coalition | {player}] - value[coalition])
        contributions[player] = phi

    base = value[frozenset()]
    prediction = value[frozenset(players)]
    drivers = sorted(
        ({"driver": p, "contribution_usd_mt": round(v, 3),
          "value": _describe(p, query)} for p, v in contributions.items()),
        key=lambda d: -abs(d["contribution_usd_mt"]))
    return {
        "prediction_usd_mt": round(prediction, 2),
        "baseline_usd_mt": round(base, 2),
        "drivers": drivers,
        "check": round(base + sum(contributions.values()) - prediction, 6),
        "method": "Exact interventional Shapley values over 4 driver groups "
                  f"(16 coalitions x {n} background rows from the training data).",
    }


def _describe(player: str, query) -> str:
    if player.startswith("Lane"):
        origin = next((o for o in model_registry.ORIGINS if query.get(f"origin_{o}", 0) == 1), "unknown")
        return f"{origin}, {query['distance_nm']:,.0f} nm"
    if player.startswith("Month"):
        return f"month {int(query['month'])}"
    if player.startswith("Bunker"):
        return f"${query['bunker_price_usd']:,.0f}/t"
    return f"{query['pressure_index']:.1f} / 100"


def permutation_importance(repeats: int = 5) -> dict:
    payload, _, (X_test, y_test) = _data()
    if _cache["importance"] is not None:
        return _cache["importance"]
    model = payload["model"]
    base_error = float(np.mean(np.abs(model.predict(X_test) - y_test)))
    rng = np.random.default_rng(42)
    rows = []
    for group, columns in GROUPS.items():
        increases = []
        for _ in range(repeats):
            shuffled = X_test.copy()
            order = rng.permutation(len(shuffled))
            for column in columns:
                if column in shuffled.columns:
                    shuffled[column] = shuffled[column].to_numpy()[order]
            increases.append(float(np.mean(np.abs(model.predict(shuffled) - y_test))) - base_error)
        rows.append({"driver": group, "mae_increase_usd_mt": round(float(np.mean(increases)), 3),
                     "std": round(float(np.std(increases)), 3)})
    total = sum(max(0.0, r["mae_increase_usd_mt"]) for r in rows) or 1.0
    for row in rows:
        row["share_pct"] = round(max(0.0, row["mae_increase_usd_mt"]) / total * 100, 1)
    rows.sort(key=lambda r: -r["mae_increase_usd_mt"])
    result = {"baseline_mae_usd_mt": round(base_error, 3), "drivers": rows,
              "method": f"Permutation importance on the {len(X_test)}-row hold-out split, "
                        f"{repeats} shuffles per driver group."}
    _cache["importance"] = result
    return result
