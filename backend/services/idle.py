"""Idle vessel repositioning: what to do with a ship that has no cargo booked.

The six disruption scenarios all start from "a cargo needs a route and Plan A
broke". This one starts from the opposite state - a vessel has discharged, has
nothing fixed, and is burning hire while it sits. The question is whether to
wait where it is or ballast to a berth where a cargo is likely to appear
sooner.

WHAT IS COMPUTED FROM DATA THE PLATFORM ALREADY HOLDS
  - Vessel economics: daily hire, service speed and capacity come from the
    seeded fleet (models.Vessel) - the same daily_cost_usd that builds the
    "Vessel hire" line in the cost waterfall.
  - Berth feasibility: laden draft against each berth's draft and LOA limits,
    using the same under-keel clearance and lightering limits as the routing
    engine, so a class that cannot work a berth is never offered one.
  - Cargo opportunity rate: each berth's own mechanised discharge rate and
    berth count give the tonnage it turns over per day; a vessel needs roughly
    its own capacity in cargo, so the bigger the berth and the smaller the
    ship, the sooner a suitable parcel appears.
  - Seasonality: each berth's own monsoon months.
  - Market direction: the trained freight model, scored across all four export
    origins at a 5-day and a 30-day horizon. A market pricing higher forward
    than spot is tightening, which shortens the expected wait. This is the same
    model and the same horizon-walk the Freight Intelligence curve uses - there
    is no second forecasting path.
  - Risk: the same four weighted components as every other scenario
    (congestion 30, seasonal 25, freight volatility 25, under-keel 20).

WHAT DOES NOT EXIST IN THE PLATFORM, AND IS THEREFORE CALIBRATED HERE
  Everything in this block is a planning assumption, not a measurement. It is
  reported in the API response under "data_basis" and tagged in the UI, in
  keeping with the SYNTHETIC / CALIBRATED labelling used on the Freight
  Intelligence and Data Governance pages.

  1. Inter-port distances. The platform had no port-to-port distance table at
     all - only ocean distances from the four export origins and rail
     kilometres inland. Coastwise chainage below is an approximation of
     steaming distance along the eastern seaboard, not a routed passage plan.
  2. Ballast bunker consumption. No consumption figures were held for any
     class; the routing engine prices fuel implicitly, inside the freight rate
     the model predicts, and never as tonnes per day.
  3. Spot liquidity. What share of a berth's throughput is open to a spot
     fixture rather than committed to contract tonnage is not recorded
     anywhere.
  4. Demand by port by month. THIS DOES NOT EXIST. FreightHistory is empty and
     the freight model carries no discharge-port or vessel-class dimension, so
     there is no historical demand curve to fit. Expected waiting time is
     derived from berth throughput, class fit, seasonality and market
     direction, as described above. It is a structural proxy, not a demand
     forecast, and must not be presented as one.
"""

from services import decision_engine, model_registry

# --- 1. CALIBRATED: coastwise chainage, nautical miles ----------------------
# Distance along the coast from Haldia, following the seaboard north to south.
# Pair distances are the difference between two chainages, which approximates a
# coastal passage without pretending to be a routed track.
COASTWISE_CHAINAGE_NM = {
    "INHAL": 0.0,     # Haldia (up the Hooghly)
    "INSAG": 60.0,    # Sagar / Sandheads, at the river mouth
    "INDHM": 190.0,   # Dhamra
    "INPRT": 250.0,   # Paradip
    "INGOP": 390.0,   # Gopalpur
    "INVTZ": 570.0,   # Visakhapatnam
    "INGGV": 578.0,   # Gangavaram, just south of Visakhapatnam
}

# --- 2. CALIBRATED: ballast fuel burn, tonnes per day at service speed ------
BALLAST_BUNKER_T_PER_DAY = {
    "Handysize": 16.0,
    "Supramax": 20.0,
    "Panamax": 26.0,
    "Capesize": 34.0,
}
DEFAULT_BUNKER_T_PER_DAY = 22.0

# --- 3. CALIBRATED: market structure assumptions ----------------------------
SPOT_LIQUIDITY_SHARE = 0.25      # share of berth throughput open to spot fixtures
MONSOON_FIXTURE_MULTIPLIER = 1.35  # fixtures thin out in a berth's monsoon months
IDLE_EVIDENCE_PRIOR_DAYS = 30.0  # strength of the prior on the arrival rate
MAX_MARKET_MULTIPLIER = 1.5
MIN_MARKET_MULTIPLIER = 0.65
FORECAST_HORIZONS = (5, 30)

DATA_BASIS = {
    "tag": "SYNTHETIC (CALIBRATED)",
    "computed_from_platform_data": [
        "Vessel daily hire, service speed and capacity (seeded fleet)",
        "Berth draft, LOA, berth count and mechanised discharge rate",
        "Each berth's own monsoon months",
        "Trained freight model, scored across all four origins at 5 and 30 days",
        "Risk scored on the same four weighted components as every other scenario",
    ],
    "calibrated_not_measured": [
        "Coastwise distances between the seven berths - the platform held no "
        "port-to-port distance table, only origin ocean distances and inland rail",
        "Ballast bunker consumption per vessel class - never recorded; the routing "
        "engine prices fuel inside the predicted freight rate",
        "Share of berth throughput open to spot fixtures, and its equal split "
        "across the classes a berth can work",
    ],
    "does_not_exist": (
        "Historical demand by port by month. FreightHistory holds no rows and the "
        "freight model has no discharge-port or vessel-class dimension, so no demand "
        "curve can be fitted. Expected waiting time here is a structural proxy built "
        "from berth throughput, class fit, seasonality and market direction - it is "
        "not a demand forecast."
    ),
}


def coastal_distance_nm(from_code: str, to_code: str) -> float | None:
    """Coastwise distance between two berths, or None if either is unknown."""
    start, end = COASTWISE_CHAINAGE_NM.get(from_code), COASTWISE_CHAINAGE_NM.get(to_code)
    if start is None or end is None:
        return None
    return round(abs(start - end), 1)


def _monsoon_months(port) -> list:
    return [
        int(part) for part in str(getattr(port, "monsoon_months", "") or "").split(",")
        if part.strip().isdigit()
    ]


def market_direction(month: int, bunker_price: float, pressure_index: float) -> dict:
    """Where the freight market is heading, from the trained model.

    Scored across every export origin at a near and a forward horizon, walking
    the calendar the same way the Freight Intelligence curve does. Forward
    above spot means a tightening market, which brings cargo forward.
    """
    rows = []
    for horizon in FORECAST_HORIZONS:
        offset_month = ((month - 1 + round(horizon / 30.0)) % 12) + 1
        for origin in model_registry.ORIGINS:
            rows.append({
                "origin": origin,
                "distance_nm": model_registry.ORIGIN_DISTANCE_NM.get(origin, 4500.0),
                "month": offset_month,
                "bunker_price": bunker_price,
                "pressure_index": pressure_index,
            })

    rates = model_registry.predict_rates(rows)
    per_origin = len(model_registry.ORIGINS)
    near = rates[:per_origin]
    forward = rates[per_origin:]
    near_mean = sum(near) / max(len(near), 1)
    forward_mean = sum(forward) / max(len(forward), 1)

    momentum = forward_mean / near_mean if near_mean else 1.0
    multiplier = max(MIN_MARKET_MULTIPLIER, min(MAX_MARKET_MULTIPLIER, 1.0 / momentum))

    if momentum > 1.02:
        direction = "tightening"
    elif momentum < 0.98:
        direction = "softening"
    else:
        direction = "flat"

    return {
        "spot_rate_usd_mt": round(near_mean, 2),
        "forward_rate_usd_mt": round(forward_mean, 2),
        "momentum": round(momentum, 4),
        "direction": direction,
        "wait_multiplier": round(multiplier, 4),
        "horizons_days": list(FORECAST_HORIZONS),
        "model": model_registry.get_payload()["metadata"].get("algorithm", "unknown"),
    }


def berth_fit(port, vessel) -> dict:
    """Whether this class can work this berth, on the routing engine's rules."""
    usable_draft = (port.draft_m or 0.0) - decision_engine.UNDER_KEEL_CLEARANCE_M
    draft_gap = (vessel.draft_m or 0.0) - usable_draft
    requires_lightering = draft_gap > 0
    feasible = draft_gap <= decision_engine.MAX_LIGHTERABLE_GAP_M
    reason = None

    if not feasible:
        reason = (f"{port.name} carries {port.draft_m:.1f} m against a laden draft of "
                  f"{vessel.draft_m:.1f} m - beyond what lightering can bridge")
    elif (port.max_loa or 0) and (vessel.capacity_mt or 0) > 150000 and port.max_loa < 300:
        feasible = False
        reason = f"{port.name} LOA limit {port.max_loa:.0f} m cannot accept a {vessel.class_type}"

    return {
        "feasible": feasible,
        "requires_lightering": requires_lightering and feasible,
        "draft_gap_m": round(draft_gap, 2),
        "usable_draft_m": round(usable_draft, 2),
        "reason": reason,
    }


def workable_classes(port, fleet) -> list:
    """The classes this berth can physically work, on the routing engine's
    draft and LOA rules."""
    return [v for v in fleet if berth_fit(port, v)["feasible"]]


def expected_days_to_cargo(port, vessel, fleet, month: int, market_multiplier: float,
                           evidence_multiplier: float) -> dict:
    """Expected days before a parcel this vessel can carry comes open here.

    A berth turning over more tonnes a day generates suitable parcels more
    often, and a larger ship needs a larger parcel. The tonnage open to spot is
    shared among the classes the berth can actually accept, so a shallow berth
    that only Handysize can work offers a Handysize all of it, while a deep
    berth splits between four classes. That is what makes the answer depend on
    the class and not only on the size of the port. Not a demand forecast - see
    the module docstring.
    """
    berths = int(getattr(port, "berths", 1) or 1)
    throughput_mt_d = max((port.mech_rate_mt_d or 0.0) * berths, 1.0)
    classes = workable_classes(port, fleet) or [vessel]
    class_share = 1.0 / len(classes)
    spot_mt_d = max(throughput_mt_d * SPOT_LIQUIDITY_SHARE * class_share, 1.0)
    base_days = (vessel.capacity_mt or 1.0) / spot_mt_d

    monsoon = month in _monsoon_months(port)
    days = base_days
    if monsoon:
        days *= MONSOON_FIXTURE_MULTIPLIER
    days *= market_multiplier
    days *= evidence_multiplier

    return {
        "days": round(days, 2),
        "base_days": round(base_days, 2),
        "berth_throughput_mt_d": round(throughput_mt_d, 0),
        "spot_throughput_mt_d": round(spot_mt_d, 0),
        "workable_classes": [v.class_type for v in classes],
        "monsoon_at_berth": monsoon,
    }


def risk_for(port, month: int, pressure_index: float, fit: dict) -> dict:
    """The same four weighted components every other scenario is scored on."""
    berths = int(getattr(port, "berths", 2) or 2)
    congestion = decision_engine._clamp(
        (port.avg_wait_days or 0.0) / 6.0 * 100.0 + (12.0 if berths <= 1 else 0.0)
    )
    monsoon = float(decision_engine.MONSOON_RISK_BY_MONTH.get(month, 30))
    if month in _monsoon_months(port):
        monsoon = decision_engine._clamp(monsoon * 1.25 + 10.0)
    volatility = decision_engine._clamp(pressure_index)

    if fit["requires_lightering"]:
        draft_risk = decision_engine._clamp(
            (fit["draft_gap_m"] / decision_engine.MAX_LIGHTERABLE_GAP_M) * 100.0)
    else:
        draft_risk = decision_engine._clamp(max(0.0, 25.0 + fit["draft_gap_m"] * 12.0))

    index = round(0.30 * congestion + 0.25 * monsoon + 0.25 * volatility + 0.20 * draft_risk, 1)
    return {
        "risk_index": index,
        "congestion_score": round(congestion, 1),
        "monsoon_risk_score": round(monsoon, 1),
        "freight_volatility_score": round(volatility, 1),
        "draft_risk_score": round(draft_risk, 1),
    }


def _confidence(risk_index: float, decisiveness: float) -> float:
    """Model accuracy, how clear-cut the margin is, and how risky the berth is -
    the same shape as the routing engine's confidence."""
    model_r2 = float(model_registry.get_payload()["metadata"].get("r2_score", 0.95) or 0.95)
    return round(decision_engine._clamp(
        (model_r2 * 100.0) * 0.55 + decisiveness * 0.25 + (100.0 - risk_index) * 0.20,
        0.0, 99.0), 1)


def evaluate_idle(*, vessels, ports, vessel_class: str, port_code: str, days_idle: float,
                  month: int, bunker_price: float, pressure_index: float) -> dict:
    """Compare waiting where the vessel lies against ballasting to every other
    berth it can work, and recommend the cheaper course."""
    vessel = next((v for v in vessels
                   if (v.class_type or "").lower() == (vessel_class or "").lower()), None)
    if vessel is None:
        raise ValueError(f"Unknown vessel class: {vessel_class}")

    current = next((p for p in ports if (p.code or "").upper() == (port_code or "").upper()), None)
    if current is None:
        raise ValueError(f"Unknown port code: {port_code}")

    daily_hire = float(vessel.daily_cost_usd or 0.0)
    bunker_t_per_day = BALLAST_BUNKER_T_PER_DAY.get(vessel.class_type, DEFAULT_BUNKER_T_PER_DAY)
    market = market_direction(month, bunker_price, pressure_index)

    # Elapsed idle time is evidence the arrival rate is slower than assumed
    # (a Gamma prior on an exponential wait), so the expected remaining wait
    # grows with it. The evidence is strongest where the vessel has actually
    # been sitting; elsewhere only the market-wide half carries over.
    days_idle = max(0.0, float(days_idle))
    local_evidence = 1.0 + days_idle / IDLE_EVIDENCE_PRIOR_DAYS
    market_evidence = 1.0 + 0.5 * days_idle / IDLE_EVIDENCE_PRIOR_DAYS

    # --- Option A: wait where she lies -------------------------------------
    fit_here = berth_fit(current, vessel)
    risk_here = risk_for(current, month, pressure_index, fit_here)
    queue_here = float(current.avg_wait_days or 0.0)

    if fit_here["feasible"]:
        wait_here = expected_days_to_cargo(current, vessel, vessels, month,
                                           market["wait_multiplier"], local_evidence)
        idle_days_here = wait_here["days"] + queue_here
        wait_option = {
            "option": "wait",
            "feasible": True,
            "port_code": current.code,
            "port_name": current.name,
            "expected_days_to_cargo": wait_here["days"],
            "berth_queue_days": round(queue_here, 2),
            "idle_days_total": round(idle_days_here, 2),
            "daily_hire_usd": round(daily_hire, 2),
            "total_cost_usd": round(idle_days_here * daily_hire, 2),
            "berth_throughput_mt_d": wait_here["berth_throughput_mt_d"],
            "workable_classes": wait_here["workable_classes"],
            "monsoon_at_berth": wait_here["monsoon_at_berth"],
            **risk_here,
        }
    else:
        wait_option = {
            "option": "wait",
            "feasible": False,
            "port_code": current.code,
            "port_name": current.name,
            "total_cost_usd": None,
            "reason": fit_here["reason"],
            **risk_here,
        }

    # --- Option B: ballast to a berth that can work her sooner --------------
    alternatives = []
    for port in ports:
        if port.code == current.code:
            continue
        distance = coastal_distance_nm(current.code, port.code)
        if distance is None:
            continue
        fit = berth_fit(port, vessel)
        if not fit["feasible"]:
            alternatives.append({
                "port_code": port.code, "port_name": port.name,
                "distance_nm": distance, "feasible": False,
                "reason": fit["reason"], "total_cost_usd": None,
            })
            continue

        ballast_days = distance / (max(vessel.speed_knots or 12.0, 1.0) * 24.0)
        ballast_hire = ballast_days * daily_hire
        bunker_tonnes = ballast_days * bunker_t_per_day
        bunker_cost = bunker_tonnes * float(bunker_price)

        wait_there = expected_days_to_cargo(port, vessel, vessels, month,
                                            market["wait_multiplier"], market_evidence)
        queue_there = float(port.avg_wait_days or 0.0)
        # Steaming burns part of the wait: only the remainder is idle time.
        idle_after_arrival = max(0.0, wait_there["days"] - ballast_days) + queue_there
        risk_there = risk_for(port, month, pressure_index, fit)

        alternatives.append({
            "port_code": port.code,
            "port_name": port.name,
            "feasible": True,
            "distance_nm": distance,
            "ballast_days": round(ballast_days, 2),
            "ballast_hire_usd": round(ballast_hire, 2),
            "bunker_tonnes": round(bunker_tonnes, 1),
            "bunker_cost_usd": round(bunker_cost, 2),
            "expected_days_to_cargo": wait_there["days"],
            "berth_queue_days": round(queue_there, 2),
            "idle_days_after_arrival": round(idle_after_arrival, 2),
            "berth_throughput_mt_d": wait_there["berth_throughput_mt_d"],
            "workable_classes": wait_there["workable_classes"],
            "monsoon_at_berth": wait_there["monsoon_at_berth"],
            "total_cost_usd": round(ballast_hire + bunker_cost + idle_after_arrival * daily_hire, 2),
            **risk_there,
        })

    feasible_alternatives = [a for a in alternatives if a["feasible"]]
    feasible_alternatives.sort(key=lambda a: a["total_cost_usd"])
    alternatives.sort(key=lambda a: (not a["feasible"], a["total_cost_usd"] or float("inf")))
    best_move = feasible_alternatives[0] if feasible_alternatives else None

    # --- Recommendation -----------------------------------------------------
    wait_cost = wait_option["total_cost_usd"] if wait_option["feasible"] else None
    move_cost = best_move["total_cost_usd"] if best_move else None

    if wait_cost is None and move_cost is None:
        raise ValueError(
            f"No berth on this coast can work a {vessel.class_type}, including {current.name}.")

    if wait_cost is None:
        choice, chosen = "reposition", best_move
        headline = (f"{current.name} cannot work a {vessel.class_type}, so she has to move. "
                    f"{best_move['port_name']} is the cheapest berth she can reach.")
    elif move_cost is None or wait_cost <= move_cost:
        choice, chosen = "wait", wait_option
        if best_move:
            headline = (f"Hold at {current.name}. Ballasting to {best_move['port_name']} costs "
                        f"${move_cost - wait_cost:,.0f} more than waiting here.")
        else:
            headline = f"Hold at {current.name}. No other berth on this coast can work her."
    else:
        choice, chosen = "reposition", best_move
        headline = (f"Ballast {best_move['distance_nm']:.0f} nm to {best_move['port_name']}: "
                    f"${wait_cost - move_cost:,.0f} cheaper than holding at {current.name}.")

    costs = [c for c in (wait_cost, move_cost) if c is not None]
    saving = round(abs(costs[0] - costs[1]), 2) if len(costs) == 2 else None
    best_total = chosen["total_cost_usd"]
    decisiveness = decision_engine._clamp(
        (saving / best_total) * 500.0 if saving and best_total else 0.0)
    confidence = _confidence(chosen["risk_index"], decisiveness)

    return {
        "status": "SUCCESS",
        "data_basis": DATA_BASIS,
        "vessel": {
            "class": vessel.class_type,
            "name": vessel.name,
            "capacity_mt": vessel.capacity_mt,
            "draft_m": vessel.draft_m,
            "speed_knots": vessel.speed_knots,
            "daily_hire_usd": round(daily_hire, 2),
            "ballast_bunker_t_per_day": bunker_t_per_day,
        },
        "inputs": {
            "vessel_class": vessel.class_type,
            "port_code": current.code,
            "port_name": current.name,
            "days_idle": days_idle,
            "month": month,
            "bunker_price_usd": bunker_price,
            "pressure_index": pressure_index,
        },
        "market": market,
        "sunk_cost_usd": round(days_idle * daily_hire, 2),
        "sunk_cost_note": ("Hire already spent over the idle days entered. It is excluded from "
                           "the comparison below, which counts only money still to be spent."),
        "wait_option": wait_option,
        "reposition_option": best_move,
        "alternatives": alternatives,
        "recommendation": {
            "choice": choice,
            "port_code": chosen["port_code"],
            "port_name": chosen["port_name"],
            "total_cost_usd": best_total,
            "saving_usd": saving,
            "headline": headline,
            "risk_index": chosen["risk_index"],
            "confidence": confidence,
        },
    }
