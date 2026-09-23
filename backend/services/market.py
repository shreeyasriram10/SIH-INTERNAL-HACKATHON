"""Market view: congestion forecast, demand/supply balance, seasonal calendar.

All three read the same reference data and the same freight model the
decision engine uses, month by month over a rolling twelve-month window that
starts in the current month.

DEMAND is modelled, not observed. It is each SAIL plant's crude-steel
capacity at a planning utilisation, converted to the imported tonnage of the
selected cargo with a consumption intensity and an import share. Those three
figures are representative planning values - replace them with the plant's
own procurement plan in production.

SUPPLY is the east-coast discharge capacity realistically available to SAIL
for that cargo each month (berth handling rate x days, less weather downtime,
at a planning share of each berth), plus freight-market tightness from the
trained model's forward curve.
"""

from datetime import datetime, timezone

from services import decision_engine, model_registry, network

# Crude-steel capacity, million tonnes a year (representative).
PLANT_CAPACITY_MTPA = {
    "bhilai": 7.0, "bokaro": 4.6, "rourkela": 4.5, "durgapur": 2.2, "burnpur": 2.5,
}
PLANT_LABELS = {
    "bhilai": "Bhilai Steel Plant", "bokaro": "Bokaro Steel Plant",
    "rourkela": "Rourkela Steel Plant", "durgapur": "Durgapur Steel Plant",
    "burnpur": "IISCO Steel Plant (Burnpur)",
}
PLANNING_UTILISATION = 0.88

# Tonnes of cargo per tonne of crude steel, and the share of it imported.
CARGO_INTENSITY = {
    "coking_coal":    {"t_per_t_steel": 0.80, "import_share": 0.85},
    "thermal_coal":   {"t_per_t_steel": 0.15, "import_share": 0.30},
    "iron_ore_fines": {"t_per_t_steel": 1.55, "import_share": 0.03},
    "iron_ore_lumps": {"t_per_t_steel": 0.25, "import_share": 0.03},
}

SAIL_BERTH_SHARE = 0.20        # of a berth's throughput realistically available to SAIL
DOWNTIME = {"monsoon": 0.25, "normal": 0.05}

DEMAND_BASIS = ("Modelled: plant crude-steel capacity x 88% utilisation x cargo intensity x "
                "import share. Representative planning values, not SAIL procurement data.")


def _months(start: int | None = None, count: int = 12) -> list:
    start = start or datetime.now(timezone.utc).month
    return [((start - 1 + i) % 12) + 1 for i in range(count)]


def congestion_forecast(ports, start: int | None = None) -> dict:
    months = _months(start)
    rows = []
    for port in ports:
        cells = []
        for month in months:
            wait = network.forecast_wait_days(port, month)
            factor, reason = network.congestion_factor(port, month)
            berths = int(getattr(port, "berths", 2) or 2)
            score = min(100.0, wait / 6.0 * 100.0 + (12.0 if berths <= 1 else 0.0))
            cells.append({"month": month, "wait_days": round(wait, 2), "factor": factor,
                          "reason": reason, "congestion_score": round(score, 1)})
        peak = max(cells, key=lambda c: c["wait_days"])
        rows.append({"port_name": port.name, "port_code": port.code,
                     "base_wait_days": port.avg_wait_days, "months": cells,
                     "peak_month": peak["month"], "peak_wait_days": peak["wait_days"]})
    return {"months": months, "ports": rows, "factors": network.CONGESTION_FACTORS,
            "basis": "Base queue per berth x seasonal factor (monsoon downtime, post-monsoon "
                     "backlog, financial-year-end rush). Planning assumptions, not berth-occupancy data."}


def plant_demand_mt_month(plant: str, cargo_type: str) -> tuple:
    key = network.plant_key(plant)
    plants = [key] if key in PLANT_CAPACITY_MTPA else list(PLANT_CAPACITY_MTPA)
    capacity = sum(PLANT_CAPACITY_MTPA[p] for p in plants)
    intensity = CARGO_INTENSITY[network.cargo_key(cargo_type)]
    monthly = (capacity * 1e6 * PLANNING_UTILISATION / 12.0
               * intensity["t_per_t_steel"] * intensity["import_share"])
    label = PLANT_LABELS[plants[0]] if len(plants) == 1 else "All SAIL integrated plants"
    return monthly, label, capacity, intensity


def demand_supply(*, ports, cargo_type: str, plant: str, origin: str,
                  bunker_price: float, pressure_index: float, start: int | None = None) -> dict:
    months = _months(start)
    demand, label, capacity, intensity = plant_demand_mt_month(plant, cargo_type)
    profile = network.cargo_profile(cargo_type)

    origins = [origin] if origin in model_registry.ORIGIN_DISTANCE_NM else list(model_registry.ORIGIN_DISTANCE_NM)
    rows = [{"origin": o, "month": m, "bunker_price": bunker_price, "pressure_index": pressure_index}
            for m in months for o in origins]
    rates = model_registry.predict_rates(rows)
    by_month = {}
    for row, rate in zip(rows, rates):
        by_month.setdefault(row["month"], []).append(rate)
    curve = {m: sum(v) / len(v) for m, v in by_month.items()}
    mean_rate = sum(curve.values()) / len(curve)

    out = []
    for month in months:
        berth_capacity = 0.0
        for port in ports:
            weather = month in network._monsoon_months(port)
            downtime = DOWNTIME["monsoon" if weather else "normal"]
            berth_capacity += (port.mech_rate_mt_d * profile["handling"] * 30.0
                               * (1.0 - downtime) * SAIL_BERTH_SHARE)
        coverage = berth_capacity / demand if demand else 0.0
        tightness = curve[month] / mean_rate * 100.0 if mean_rate else 100.0
        status = ("Comfortable" if coverage >= 2.0 and tightness < 104
                  else "Tight" if coverage < 1.2 or tightness >= 108 else "Adequate")
        out.append({
            "month": month,
            "demand_mt": round(demand, 0),
            "discharge_capacity_mt": round(berth_capacity, 0),
            "coverage_ratio": round(coverage, 2),
            "freight_usd_mt": round(curve[month], 2),
            "freight_tightness_index": round(tightness, 1),
            "balance": status,
        })
    tight = [r["month"] for r in out if r["balance"] == "Tight"]
    return {
        "plant": label,
        "cargo_type": profile["label"],
        "plant_capacity_mtpa": capacity,
        "intensity": intensity,
        "annual_import_requirement_mt": round(demand * 12, 0),
        "months": out,
        "tight_months": tight,
        "summary": (f"{label} needs about {demand:,.0f} MT of imported {profile['label'].lower()} a month. "
                    + (f"Supply is tight in {len(tight)} of the next 12 months." if tight
                       else "No month in the next twelve is tight on berth capacity or freight.")),
        "demand_basis": DEMAND_BASIS,
        "supply_basis": (f"East-coast discharge capacity at a {SAIL_BERTH_SHARE:.0%} share of each berth, "
                         "less weather downtime; freight tightness = forward rate / 12-month mean (model)."),
        "data_source": "Modelled from reference data and the trained freight model (SYNTHETIC).",
    }


def seasonal_calendar(*, ports, origin: str, bunker_price: float, pressure_index: float) -> dict:
    months = list(range(1, 13))
    origins = [origin] if origin in model_registry.ORIGIN_DISTANCE_NM else list(model_registry.ORIGIN_DISTANCE_NM)
    rows = [{"origin": o, "month": m, "bunker_price": bunker_price, "pressure_index": pressure_index}
            for m in months for o in origins]
    rates = model_registry.predict_rates(rows)
    by_month = {}
    for row, rate in zip(rows, rates):
        by_month.setdefault(row["month"], []).append(rate)

    out = []
    for month in months:
        affected = [p.name for p in ports if month in network._monsoon_months(p)]
        waits = [network.forecast_wait_days(p, month) for p in ports]
        rate = sum(by_month[month]) / len(by_month[month])
        weather = decision_engine.MONSOON_RISK_BY_MONTH.get(month, 30)
        out.append({"month": month, "weather_risk": weather, "ports_affected": affected,
                    "avg_wait_days": round(sum(waits) / len(waits), 2) if waits else 0.0,
                    "freight_usd_mt": round(rate, 2)})

    # Rank months on a blend of normalised freight, weather and queue.
    def _norm(values):
        lo, hi = min(values), max(values)
        return [(v - lo) / (hi - lo) if hi > lo else 0.0 for v in values]
    f = _norm([r["freight_usd_mt"] for r in out])
    w = _norm([r["weather_risk"] for r in out])
    q = _norm([r["avg_wait_days"] for r in out])
    for row, a, b, c in zip(out, f, w, q):
        row["score"] = round(100 * (0.4 * a + 0.35 * b + 0.25 * c), 1)
    ranked = sorted(out, key=lambda r: r["score"])
    for rank, row in enumerate(ranked, start=1):
        row["rank"] = rank
    return {"months": out, "best_months": [r["month"] for r in ranked[:3]],
            "worst_months": [r["month"] for r in ranked[-3:]],
            "basis": "Score = 40% freight (model) + 35% weather risk + 25% berth queue, each "
                     "normalised across the year. Lower is better."}
