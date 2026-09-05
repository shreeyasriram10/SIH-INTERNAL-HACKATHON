"""Rolling freight-rate horizon for the dashboard chart.

Produces a day-indexed series spanning a recent history window and a forward
forecast window, both anchored to the server's current date at request time -
nothing here is pinned to a stored or hardcoded date.

Two problems this module exists to solve:

1. Rolling window. Day 1 of the forecast always means "tomorrow relative to
   whenever this runs". The whole window is derived from `date.today()` on
   every call, so it shifts forward on its own as the calendar advances.

2. Day-1 continuity. Each day used to be predicted independently, so the first
   forecast point could disagree with the last historical point and leave a
   visible step at the TODAY divider. The forecast is now anchored: the offset
   between the model's raw first prediction and the last historical value is
   applied in full on day 1 and decays to zero across the horizon, so the join
   is exact while the far end keeps the model's own level.

The model's only time feature is `month`, so a naive daily series would be a
stair-step that only moves at month boundaries. `_seasonal_rates` interpolates
between the model's response for adjacent months to get a smooth daily curve
without touching the model or its features.
"""

import calendar
from datetime import date, timedelta

from services import model_registry

MAX_HISTORY_DAYS = 180
MAX_HORIZON_DAYS = 365


def _fractional_month(day: date) -> float:
    """Map a date onto a continuous month axis where the integer value sits at
    the middle of the month. 15 March -> ~3.0, 1 April -> ~3.5."""
    days_in_month = calendar.monthrange(day.year, day.month)[1]
    position = (day.day - 1) / days_in_month  # 0.0 at the 1st, ~1.0 at month end
    return day.month + (position - 0.5)


def _wrap_month(month: int) -> int:
    """Fold a month index back into 1..12 so December blends into January."""
    return ((month - 1) % 12) + 1


def _seasonal_rates(days, *, origin, distance_nm, bunker_price, pressure_index):
    """Predict a smooth daily rate for each date.

    For every day the model is evaluated at the two months bracketing that
    date's position in the year and the results are blended, which turns the
    model's month-granular response into a continuous daily curve. Both
    evaluations for every day go out as one batch.
    """
    if not days:
        return []

    rows, weights = [], []
    for day in days:
        coordinate = _fractional_month(day)
        lower = int(coordinate // 1)
        weight = coordinate - lower
        for month in (_wrap_month(lower), _wrap_month(lower + 1)):
            rows.append({
                "origin": origin,
                "distance_nm": distance_nm,
                "month": month,
                "bunker_price": bunker_price,
                "pressure_index": pressure_index,
            })
        weights.append(weight)

    predictions = model_registry.predict_rates(rows)

    rates = []
    for index, weight in enumerate(weights):
        low = predictions[index * 2]
        high = predictions[index * 2 + 1]
        rates.append(max(0.0, low * (1 - weight) + high * weight))
    return rates


def build_horizon(
    *,
    origin: str,
    distance_nm: float,
    bunker_price: float,
    pressure_index: float,
    horizon_days: int = 30,
    history_days: int = 14,
    today: date | None = None,
):
    """Build the anchored rolling window.

    `today` is injectable purely so tests can advance the calendar; callers in
    the application leave it unset and get the real current date.
    """
    today = today or date.today()
    horizon_days = max(1, min(int(horizon_days), MAX_HORIZON_DAYS))
    history_days = max(1, min(int(history_days), MAX_HISTORY_DAYS))

    # History runs up to and including today; the forecast starts tomorrow.
    history_dates = [today - timedelta(days=offset)
                     for offset in range(history_days - 1, -1, -1)]
    forecast_dates = [today + timedelta(days=offset)
                      for offset in range(1, horizon_days + 1)]

    market = {
        "origin": origin,
        "distance_nm": distance_nm,
        "bunker_price": bunker_price,
        "pressure_index": pressure_index,
    }
    history_rates = _seasonal_rates(history_dates, **market)
    raw_forecast_rates = _seasonal_rates(forecast_dates, **market)

    # --- day-1 anchoring -----------------------------------------------------
    # Shift the forecast so its first point lands exactly on the last known
    # historical value, then fade the shift out so the tail is the model's own
    # view rather than a permanently displaced copy of it.
    last_historical = history_rates[-1]
    raw_day_one = raw_forecast_rates[0]
    offset = last_historical - raw_day_one

    span = max(len(raw_forecast_rates) - 1, 1)
    forecast_rates = [
        max(0.0, rate + offset * (1 - index / span))
        for index, rate in enumerate(raw_forecast_rates)
    ]
    # Floating-point drift would leave a hairline step at the divider.
    forecast_rates[0] = last_historical

    metadata = model_registry.get_payload().get("metadata") or {}
    rmse = float(metadata.get("rmse_usd") or 0.9)

    history = [
        {
            "date": day.isoformat(),
            "day_offset": -(len(history_dates) - 1 - index),
            "rate_usd": round(rate, 2),
            "segment": "historical",
        }
        for index, (day, rate) in enumerate(zip(history_dates, history_rates))
    ]

    forecast = []
    for index, (day, rate) in enumerate(zip(forecast_dates, forecast_rates)):
        # Uncertainty widens with distance from today.
        margin = max(rate * 0.05, rmse * 1.96) * (1 + index / span)
        forecast.append({
            "date": day.isoformat(),
            "day_offset": index + 1,
            "rate_usd": round(rate, 2),
            "ci_lower_usd": round(max(0.0, rate - margin), 2),
            "ci_upper_usd": round(rate + margin, 2),
            "segment": "forecast",
        })

    return {
        "today": today.isoformat(),
        "origin": origin,
        "history_days": history_days,
        "horizon_days": horizon_days,
        "history": history,
        "forecast": forecast,
        "anchor": {
            "last_historical_usd": round(last_historical, 2),
            "model_day_one_raw_usd": round(raw_day_one, 2),
            "offset_applied_usd": round(offset, 2),
            "method": "day1-equals-last-historical, offset decayed to zero over the horizon",
        },
        # The stored FreightHistory table is empty, so the historical leg is the
        # model's own response for past dates rather than observed market data.
        "data_source": "SYNTHETIC (BDI-Calibrated); historical leg is model-implied",
    }
