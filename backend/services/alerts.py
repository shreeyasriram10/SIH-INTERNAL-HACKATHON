"""The alert feed behind the header bell.

Each alert is derived from data the platform already computes - the
congestion forecast, the berth weather calendar, the freight model's forward
curve and the demand/supply balance - for the coming months. Alert ids are
deterministic (type, subject, month), so the browser can remember which ones
a user has already seen without the server storing read state.
"""

from datetime import datetime, timezone

from services import market, model_registry, network, planning

MONTH = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def build_alerts(*, ports, cargo_type="coking_coal", plant="rourkela", bunker_price=697.0,
                 pressure_index=52.5, start: int | None = None) -> dict:
    now = start or datetime.now(timezone.utc).month
    upcoming = [((now - 1 + i) % 12) + 1 for i in range(3)]
    alerts = []

    for port in ports:
        months = network._monsoon_months(port)
        nxt = upcoming[1]
        if nxt in months and now not in months:
            alerts.append({
                "id": f"monsoon-{port.code}-{nxt}", "severity": "warn", "category": "Weather",
                "title": f"Monsoon season starts at {port.name} in {MONTH[nxt]}",
                "text": f"Queues are forecast at {network.forecast_wait_days(port, nxt):.1f} days "
                        f"(base {port.avg_wait_days:.1f}). Front-load parcels into {MONTH[now]}.",
            })
        for month in upcoming:
            wait = network.forecast_wait_days(port, month)
            if port.avg_wait_days and wait >= port.avg_wait_days * 1.25 and wait >= 3.0:
                _, reason = network.congestion_factor(port, month)
                alerts.append({
                    "id": f"congestion-{port.code}-{month}", "severity": "risk" if wait >= 5 else "warn",
                    "category": "Congestion",
                    "title": f"{port.name}: {wait:.1f}-day queue forecast for {MONTH[month]}",
                    "text": f"{reason.capitalize()} lifts the berth queue {wait / port.avg_wait_days - 1:.0%} "
                            f"above its average. Demurrage exposure rises accordingly.",
                })
                break

    for origin in model_registry.ORIGIN_DISTANCE_NM:
        rows = [{"origin": origin, "month": m, "bunker_price": bunker_price, "pressure_index": pressure_index}
                for m in [((now - 1 + i) % 12) + 1 for i in range(6)]]
        rates = model_registry.predict_rates(rows)
        runs = [{"feasible": True, "freight_rate_usd_mt": r, "month": row["month"]} for r, row in zip(rates, rows)]
        signal = planning.timing_signal(runs)
        if signal["signal"] != "HOLD":
            alerts.append({
                "id": f"timing-{origin}-{now}-{signal['signal']}", "category": "Market timing",
                "severity": "info" if signal["signal"] == "FIX" else "warn",
                "title": f"{origin} lane: {signal['signal']}",
                "text": signal["reason"],
            })

    balance = market.demand_supply(ports=ports, cargo_type=cargo_type, plant=plant, origin="any",
                                   bunker_price=bunker_price, pressure_index=pressure_index, start=now)
    for row in balance["months"][:3]:
        if row["balance"] == "Tight":
            alerts.append({
                "id": f"supply-{row['month']}", "severity": "risk", "category": "Demand / supply",
                "title": f"Supply tight in {MONTH[row['month']]}",
                "text": f"Discharge capacity covers {row['coverage_ratio']:.1f}x demand and freight runs at "
                        f"{row['freight_tightness_index']:.0f}% of its 12-month mean.",
            })

    order = {"risk": 0, "warn": 1, "info": 2}
    alerts.sort(key=lambda a: order.get(a["severity"], 3))
    return {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "count": len(alerts), "alerts": alerts,
            "data_source": "Derived from the congestion forecast, berth weather calendar, freight "
                           "model and demand/supply balance (SYNTHETIC)."}
