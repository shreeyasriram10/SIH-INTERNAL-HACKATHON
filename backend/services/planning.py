"""Procurement planning: from one parcel to a charter programme.

The decision engine answers "which ship, which berth, what cost" for a single
parcel in a single month. A steel plant does not buy one parcel; it needs a
tonnage over months, and the real chartering questions are about that
programme:

  MULTI-VOYAGE OPTIMIZER   when should each voyage sail, given that every month
                           has its own freight rate, berth queue and weather,
                           the plant must never run short, and cargo that
                           arrives early costs money to hold
  CHARTER STRUCTURE        pay spot voyage by voyage, or fix a short- or
                           medium-term contract that buys certainty at a
                           premium
  SHORT-TERM COST          what the next three months will cost, with a band
  MARKET ENTRY TIMING      is spot cheap or dear against the forward curve
  FINAL RECOMMENDATION     one plan an officer can sign

Every monthly figure is a real engine run for that month - the same ranking,
cost stack and risk index as the Command Centre - so nothing here is priced by
a second, simpler model.

WHAT IS A PLANNING ASSUMPTION (stated so it can be challenged)
  * Monthly freight volatility grows with market pressure: 4% a month on a
    calm market up to 12% on a stressed one, widening with the square root of
    the months ahead. The model's hold-out RMSE is the floor.
  * A period contract is priced at the mean forward rate over its term plus a
    term premium (2.5% for three months, 4% for six) - the owner's price for
    taking the market risk off the charterer.
  * Holding cargo that arrives ahead of need costs 1% of its FOB value a
    month (working capital and stockyard).
  * Risk aversion 0.5: an option's score is its expected cost plus half its
    cost-at-risk (P90 minus expected).
"""

import math
from datetime import datetime, timezone

from services import decision_engine, model_registry, network

Z_P90 = 1.2816                     # one-sided 90% normal quantile
HOLDING_RATE_PER_MONTH = 0.01      # of FOB value, per tonne held a month
RISK_AVERSION = 0.5
TIMING_BAND = 0.04                 # spot within +/-4% of the forward mean = HOLD

CONTRACTS = [
    {"key": "spot", "label": "Spot (voyage by voyage)", "months": 0, "premium": 0.0},
    {"key": "short", "label": "Short-term contract (3 months)", "months": 3, "premium": 0.025},
    {"key": "medium", "label": "Medium-term contract (6 months)", "months": 6, "premium": 0.04},
]


def _month_at(offset: int, start: int | None = None) -> int:
    start = start or datetime.now(timezone.utc).month
    return ((start - 1 + offset) % 12) + 1


def monthly_volatility(pressure_index: float) -> float:
    return 0.04 + 0.08 * max(0.0, min(100.0, pressure_index)) / 100.0


def _rate_sigma(rate: float, months_ahead: int, pressure_index: float) -> float:
    rmse = float(model_registry.get_payload().get("metadata", {}).get("rmse_usd") or 0.9)
    return max(rmse, rate * monthly_volatility(pressure_index) * math.sqrt(months_ahead + 1))


def month_runs(*, vessels, ports, request, horizon: int, start_month: int | None = None) -> list:
    """The engine's best option for this parcel in each month of the horizon."""
    runs = []
    for offset in range(horizon):
        month = _month_at(offset, start_month)
        options, _ = decision_engine.evaluate(
            vessels=vessels, ports=ports, parcel_size=request.parcel_size,
            cargo_type=request.cargo_type, origin=request.origin, plant=request.plant,
            window_days=request.window_days, month=month, bunker_price=request.bunker_price,
            pressure_index=request.pressure_index, top_n=1,
        )
        if not options:
            runs.append({"offset": offset, "month": month, "feasible": False})
            continue
        best = options[0]
        rate = best.freight_rate_usd_mt
        sigma = _rate_sigma(rate, offset, request.pressure_index)
        runs.append({
            "offset": offset,
            "month": month,
            "feasible": True,
            "vessel_class": best.vessel_class,
            "port_name": best.port_name,
            "load_port": best.load_port,
            "shipments": best.shipments,
            "freight_rate_usd_mt": rate,
            "freight_p10_usd_mt": round(max(0.0, rate - Z_P90 * sigma), 2),
            "freight_p90_usd_mt": round(rate + Z_P90 * sigma, 2),
            "freight_sigma_usd_mt": round(sigma, 2),
            "landed_cost_usd_mt": best.landed_cost_usd_mt,
            "non_freight_usd_mt": round(best.landed_cost_usd_mt - rate, 2),
            "risk_index": best.risk_index,
            "risk_adjusted_usd_mt": round(
                best.landed_cost_usd_mt * (1 + decision_engine.RISK_WEIGHT * best.risk_index / 100.0), 2),
            "supply_continuity": best.supply_continuity,
            "wait_days": best.wait_days,
            "congestion_basis": best.congestion_basis,
            "total_cycle_days": best.total_cycle_days,
        })
    return runs


def optimise_schedule(runs: list, *, total_mt: float, parcel_mt: float, horizon: int,
                      fob_usd_mt: float, max_per_month: int) -> dict:
    """Choose how many voyages sail in each month.

    Dynamic programme over months with the number of voyages shipped so far
    as the state. Each month the plant consumes an equal share of the
    requirement; arrivals up to and including a month must cover consumption
    up to that month (no stock-out). A voyage costs its month's risk-adjusted
    landed cost; tonnes held past need cost HOLDING_RATE_PER_MONTH of FOB.
    Exact for this formulation - not a heuristic.
    """
    voyages = max(1, math.ceil(total_mt / parcel_mt))
    demand = total_mt / horizon
    hold_cost = fob_usd_mt * HOLDING_RATE_PER_MONTH
    inf = float("inf")

    # best[k] = (cost, schedule) after processing months so far with k voyages shipped
    best = {0: (0.0, [])}
    for index, run in enumerate(runs):
        needed = demand * (index + 1)
        nxt = {}
        for shipped, (cost, schedule) in best.items():
            limit = max_per_month if run["feasible"] else 0
            for extra in range(0, limit + 1):
                total = shipped + extra
                if total > voyages:
                    break
                arrived = min(total * parcel_mt, total_mt)
                if arrived + 1e-6 < needed:
                    continue
                voyage_cost = extra * parcel_mt * run["risk_adjusted_usd_mt"] if extra else 0.0
                holding = max(0.0, arrived - needed) * hold_cost
                value = cost + voyage_cost + holding
                if value < nxt.get(total, (inf,))[0]:
                    nxt[total] = (value, schedule + [extra])
        best = nxt
        if not best:
            break

    if voyages not in best:
        return {"feasible": False, "voyages": voyages,
                "reason": "No schedule covers the requirement inside the horizon at "
                          f"{max_per_month} voyages a month."}

    cost, plan = best[voyages]

    # The naive plan a desk would draw by hand: spread voyages evenly.
    even = [voyages // horizon + (1 if i < voyages % horizon else 0) for i in range(horizon)]
    even_cost, arrived_total = 0.0, 0.0
    for index, (run, count) in enumerate(zip(runs, even)):
        arrived_total = min(arrived_total + count * parcel_mt, total_mt)
        if run["feasible"]:
            even_cost += count * parcel_mt * run["risk_adjusted_usd_mt"]
        even_cost += max(0.0, arrived_total - demand * (index + 1)) * hold_cost

    rows, shipped = [], 0.0
    for index, (run, count) in enumerate(zip(runs, plan)):
        tonnes = max(0.0, min(count * parcel_mt, total_mt - shipped))
        shipped += tonnes
        rows.append({
            **run,
            "voyages": count,
            "tonnes": round(tonnes, 0),
            "consumption_mt": round(demand, 0),
            "stock_end_mt": round(shipped - demand * (index + 1), 0),
        })

    return {
        "feasible": True,
        "voyages": voyages,
        "schedule": rows,
        "objective_usd": round(cost, 0),
        "even_spread_usd": round(even_cost, 0),
        "saving_vs_even_usd": round(even_cost - cost, 0),
        "method": "Exact dynamic programme over months (state = voyages shipped); "
                  "no stock-out, holding cost on early arrivals.",
    }


def compare_contracts(schedule: list, *, parcel_mt: float) -> list:
    """Spot vs short- and medium-term contract on the optimised voyages."""
    voyages = [(row, row["voyages"]) for row in schedule if row.get("voyages")]
    options = []
    for spec in CONTRACTS:
        covered = [row for row in schedule if row["offset"] < spec["months"]]
        contract_rate = None
        if covered:
            weights = sum(r["voyages"] for r in covered) or len(covered)
            mean_rate = (sum(r["freight_rate_usd_mt"] * (r["voyages"] or 1) for r in covered) / weights
                         if weights else 0.0)
            contract_rate = mean_rate * (1 + spec["premium"])

        expected = p90 = 0.0
        fixed_tonnes = 0.0
        for row, count in voyages:
            tonnes = count * parcel_mt
            non_freight = row["non_freight_usd_mt"] * tonnes
            if contract_rate is not None and row["offset"] < spec["months"]:
                expected += contract_rate * tonnes + non_freight
                p90 += contract_rate * tonnes + non_freight
                fixed_tonnes += tonnes
            else:
                expected += row["freight_rate_usd_mt"] * tonnes + non_freight
                p90 += row["freight_p90_usd_mt"] * tonnes + non_freight
        total_tonnes = sum(count for _, count in voyages) * parcel_mt or 1.0
        cost_at_risk = p90 - expected
        options.append({
            "key": spec["key"],
            "label": spec["label"],
            "term_months": spec["months"],
            "term_premium_pct": round(spec["premium"] * 100, 1),
            "contract_rate_usd_mt": round(contract_rate, 2) if contract_rate is not None else None,
            "voyages": sum(count for _, count in voyages),
            "fixed_share_pct": round(fixed_tonnes / total_tonnes * 100, 1),
            "expected_cost_usd": round(expected, 0),
            "p90_cost_usd": round(p90, 0),
            "cost_at_risk_usd": round(cost_at_risk, 0),
            "expected_usd_mt": round(expected / total_tonnes, 2),
            "score_usd": round(expected + RISK_AVERSION * cost_at_risk, 0),
        })
    best = min(options, key=lambda o: o["score_usd"])
    spot = next(o for o in options if o["key"] == "spot")
    for option in options:
        option["recommended"] = option is best
        option["premium_vs_spot_usd"] = round(option["expected_cost_usd"] - spot["expected_cost_usd"], 0)
        option["risk_removed_usd"] = round(spot["cost_at_risk_usd"] - option["cost_at_risk_usd"], 0)
    return options


def timing_signal(runs: list) -> dict:
    """FIX / HOLD / DEFER from spot against the forward mean."""
    feasible = [r for r in runs if r["feasible"]]
    if not feasible:
        return {"signal": "HOLD", "reason": "No feasible month to compare."}
    spot = feasible[0]["freight_rate_usd_mt"]
    forward = sum(r["freight_rate_usd_mt"] for r in feasible) / len(feasible)
    gap = (spot - forward) / forward if forward else 0.0
    cheapest = min(feasible, key=lambda r: r["freight_rate_usd_mt"])
    if gap <= -TIMING_BAND:
        signal, reason = "FIX", (f"Spot ${spot:.2f}/MT is {abs(gap) * 100:.1f}% below the "
                                 f"{len(feasible)}-month forward mean - fix now.")
    elif gap >= TIMING_BAND:
        signal, reason = "DEFER", (f"Spot ${spot:.2f}/MT is {gap * 100:.1f}% above the forward mean; "
                                   f"the curve is cheapest in month {cheapest['month']}.")
    else:
        signal, reason = "HOLD", (f"Spot ${spot:.2f}/MT is within {TIMING_BAND * 100:.0f}% of the "
                                  f"forward mean ${forward:.2f}/MT - no timing edge either way.")
    return {"signal": signal, "reason": reason, "spot_usd_mt": round(spot, 2),
            "forward_mean_usd_mt": round(forward, 2), "gap_pct": round(gap * 100, 2),
            "cheapest_month": cheapest["month"], "rule": "Spot within +/-4% of the forward mean is HOLD."}


def short_term_costs(schedule: list, *, parcel_mt: float, months: int = 3) -> dict:
    rows = []
    total = total_p10 = total_p90 = 0.0
    for row in schedule[:months]:
        tonnes = row.get("voyages", 0) * parcel_mt
        expected = row["landed_cost_usd_mt"] * tonnes if row["feasible"] else 0.0
        spread = (row["freight_rate_usd_mt"] - row["freight_p10_usd_mt"]) * tonnes if row["feasible"] else 0.0
        upper = (row["freight_p90_usd_mt"] - row["freight_rate_usd_mt"]) * tonnes if row["feasible"] else 0.0
        total += expected
        total_p10 += expected - spread
        total_p90 += expected + upper
        rows.append({
            "month": row["month"],
            "voyages": row.get("voyages", 0),
            "tonnes": round(tonnes, 0),
            "landed_cost_usd_mt": row.get("landed_cost_usd_mt"),
            "freight_rate_usd_mt": row.get("freight_rate_usd_mt"),
            "freight_band_usd_mt": [row.get("freight_p10_usd_mt"), row.get("freight_p90_usd_mt")],
            "expected_usd": round(expected, 0),
            "p10_usd": round(expected - spread, 0),
            "p90_usd": round(expected + upper, 0),
        })
    return {"months": rows, "expected_usd": round(total, 0), "p10_usd": round(total_p10, 0),
            "p90_usd": round(total_p90, 0),
            "expected_inr_cr": round(total * decision_engine.USD_TO_INR / 1e7, 2)}


def build_plan(*, vessels, ports, request) -> dict:
    horizon = request.horizon_months
    total = request.total_requirement_mt or request.parcel_size * horizon
    runs = month_runs(vessels=vessels, ports=ports, request=request, horizon=horizon)
    fob = network.fob_usd_mt(request.cargo_type, request.origin)
    optimised = optimise_schedule(
        runs, total_mt=total, parcel_mt=request.parcel_size, horizon=horizon,
        fob_usd_mt=fob, max_per_month=request.max_voyages_per_month,
    )
    timing = timing_signal(runs)
    result = {
        "status": "SUCCESS",
        "inputs": {
            "cargo_type": request.cargo_type, "origin": request.origin, "plant": request.plant,
            "parcel_size": request.parcel_size, "total_requirement_mt": total,
            "horizon_months": horizon, "window_days": request.window_days,
        },
        "months": runs,
        "optimizer": optimised,
        "timing": timing,
        "assumptions": {
            "monthly_volatility_pct": round(monthly_volatility(request.pressure_index) * 100, 1),
            "holding_cost_usd_mt_month": round(fob * HOLDING_RATE_PER_MONTH, 2),
            "risk_aversion": RISK_AVERSION,
            "term_premiums_pct": {c["key"]: c["premium"] * 100 for c in CONTRACTS if c["months"]},
        },
        "data_source": "Engine runs per month on the trained freight model (SYNTHETIC, BDI-calibrated); "
                       "volatility, term premiums and holding cost are planning assumptions.",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    if not optimised["feasible"]:
        result["status"] = "INFEASIBLE"
        return result

    schedule = optimised["schedule"]
    contracts = compare_contracts(schedule, parcel_mt=request.parcel_size)
    short_term = short_term_costs(schedule, parcel_mt=request.parcel_size)
    result["contracts"] = contracts
    result["short_term"] = short_term
    result["recommendation"] = final_recommendation(
        request=request, schedule=schedule, contracts=contracts, timing=timing,
        optimised=optimised)
    return result


def final_recommendation(*, request, schedule, contracts, timing, optimised) -> dict:
    sailing = [r for r in schedule if r.get("voyages")]
    first = sailing[0] if sailing else schedule[0]
    chosen = next(c for c in contracts if c["recommended"])
    spot = next(c for c in contracts if c["key"] == "spot")
    classes = {}
    for row in sailing:
        classes[(row["vessel_class"], row["port_name"])] = classes.get(
            (row["vessel_class"], row["port_name"]), 0) + row["voyages"]
    (vessel_class, port_name), _ = max(classes.items(), key=lambda kv: kv[1]) if classes else (
        (first.get("vessel_class"), first.get("port_name")), 0)
    weighted = sum(r["supply_continuity"] * r["voyages"] for r in sailing)
    confidence = round(weighted / max(1, sum(r["voyages"] for r in sailing)), 1)

    months = ", ".join(f"{datetime(2000, r['month'], 1):%b} x{r['voyages']}" for r in sailing)
    reasons = [
        f"{chosen['label']} has the lowest expected cost plus half its cost-at-risk "
        f"(${chosen['score_usd']:,.0f}).",
        (f"It costs ${chosen['premium_vs_spot_usd']:,.0f} more than spot on expectation and removes "
         f"${chosen['risk_removed_usd']:,.0f} of P90 exposure."
         if chosen["key"] != "spot" else
         f"Contract premiums outweigh the ${spot['cost_at_risk_usd']:,.0f} of spot exposure they would remove."),
        (f"Parcels sail {months}; the optimiser saves ${optimised['saving_vs_even_usd']:,.0f} "
         f"against an even monthly spread."
         if optimised["saving_vs_even_usd"] > 0 else
         f"Parcels sail {months}. An even spread is already optimal: no month is cheap enough "
         f"to justify carrying cargo ahead of need."),
        timing["reason"],
        f"{vessel_class} via {port_name}, loading at {first.get('load_port') or 'the origin terminal'}.",
    ]
    return {
        "charter_type": chosen["key"],
        "charter_label": chosen["label"],
        "vessel_class": vessel_class,
        "discharge_port": port_name,
        "load_port": first.get("load_port"),
        "origin": request.origin,
        "plant": request.plant,
        "voyages": optimised["voyages"],
        # A parcel can need more than one ship (a Supramax lifts ~58k MT of
        # coal), so parcels and sailings are reported separately.
        "sailings": sum(r["voyages"] * r.get("shipments", 1) for r in sailing),
        "first_sailing_month": first["month"],
        "timing_signal": timing["signal"],
        "expected_cost_usd": chosen["expected_cost_usd"],
        "p90_cost_usd": chosen["p90_cost_usd"],
        "expected_cost_inr_cr": round(chosen["expected_cost_usd"] * decision_engine.USD_TO_INR / 1e7, 2),
        "confidence": confidence,
        "confidence_basis": "Voyage-weighted supply continuity of the scheduled sailings.",
        "reasons": reasons,
    }


def constraint_matrix(*, vessels, ports, cargo_type: str, origin: str, parcel_size: float) -> dict:
    """Every vessel class against the origin terminal and every discharge berth,
    with the same checks the engine applies."""
    profile = network.cargo_profile(cargo_type)
    terminal = network.load_port(origin, cargo_type)
    rows = []
    for vessel in vessels:
        fit = decision_engine.load_port_fit(vessel, profile, terminal)
        lift = fit["lift_mt"]
        shipments = max(1, math.ceil(parcel_size / max(lift, 1.0)))
        weight_fraction = parcel_size / (shipments * max(vessel.capacity_mt, 1.0))
        laden = decision_engine._laden_draft(vessel, weight_fraction)
        loa, beam = network.vessel_dimensions(vessel)
        berths = []
        for port in ports:
            feasible, lightering, checks, reason = decision_engine.berth_checks(
                vessel, port, laden, port.mech_rate_mt_d * profile["handling"])
            berths.append({"port_name": port.name, "port_code": port.code,
                           "feasible": feasible and fit["feasible"], "lightering": lightering,
                           "reason": reason or (fit["reason"] if not fit["feasible"] else ""),
                           "checks": checks})
        rows.append({
            "vessel_class": vessel.class_type,
            "capacity_mt": vessel.capacity_mt,
            "loa_m": loa, "beam_m": beam, "draft_m": vessel.draft_m,
            "lift_mt": round(lift, 0), "shipments": shipments,
            "laden_draft_m": round(laden, 2),
            "load_port": {"feasible": fit["feasible"], "part_loaded": fit["part_loaded"],
                          "reason": fit["reason"], "checks": fit["checks"]},
            "berths": berths,
        })
    return {"origin": origin, "cargo_type": cargo_type, "parcel_size": parcel_size,
            "load_port": terminal, "load_port_basis": network.LOAD_PORT_BASIS,
            "vessels": rows}
