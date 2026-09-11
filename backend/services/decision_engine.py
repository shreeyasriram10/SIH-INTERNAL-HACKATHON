"""Chartering decision engine.

Scores every feasible (vessel class x discharge port) pairing for a cargo
parcel and ranks them on risk-adjusted landed cost. Freight rates come from the
trained model; vessel and port characteristics come from the database, so the
recommendation moves when the reference data moves.

Cost stack per candidate, all in USD:

    ocean freight      predicted USD/MT  x  parcel tonnage
    deadfreight        booked-but-unused space beyond a 10% tolerance
    vessel hire        (sea days + port days) x daily hire, per shipment
    port dues          flat rate per tonne discharged
    demurrage          waiting beyond free laytime, at the berth's own rate
    lightering         only when the berth cannot take the laden draft
    inland evacuation  rail km to plant x tariff x tonnage
"""

import math
from dataclasses import dataclass, field, asdict

from services import model_registry, network

# ---------------------------------------------------------------------------
# Tariffs and physical constants
# ---------------------------------------------------------------------------

UNDER_KEEL_CLEARANCE_M = 0.6      # minimum water under the keel at the berth
MAX_LIGHTERABLE_GAP_M = 4.0       # beyond this the berth is simply unusable
LIGHTERING_USD_PER_MT = 2.20      # transhipment via barge / floating crane
PORT_DUES_USD_PER_MT = 0.85       # harbour dues, pilotage, berth hire
FREE_LAYTIME_DAYS = 3.0           # customary laytime before demurrage accrues
RAIL_USD_PER_MT_KM = 0.019        # ~INR 1.6 per tonne-km at 84 INR/USD
USD_TO_INR = 84.0

# Reference class for economies of scale (a 75k DWT Panamax).
REFERENCE_DWT = 75000.0
SCALE_EXPONENT = 0.18

# Deadfreight: a voyage charter pays for the booked space whether or not it is
# filled. Charge the unused slot beyond a 10% tolerance, at a fraction of the
# freight rate, so the engine stops recommending a half-empty large ship.
DEADFREIGHT_TOLERANCE = 0.10
DEADFREIGHT_RATE_FACTOR = 0.35

# Bay of Bengal seasonality. South-west monsoon runs Jun-Sep; Oct-Dec is the
# post-monsoon cyclone window on the east coast.
MONSOON_RISK_BY_MONTH = {
    1: 8, 2: 8, 3: 12, 4: 18, 5: 30,
    6: 62, 7: 70, 8: 68, 9: 55,
    10: 48, 11: 52, 12: 25,
}

# How hard a unit of risk is penalised when ranking. 0 = pure lowest cost.
RISK_WEIGHT = 0.35


@dataclass
class Candidate:
    vessel_class: str
    vessel_name: str
    port_name: str
    port_code: str
    origin: str
    plant: str

    parcel_mt: float
    shipments: int
    utilisation_pct: float

    freight_rate_usd_mt: float
    ocean_freight_usd: float
    deadfreight_usd: float
    vessel_hire_usd: float
    port_dues_usd: float
    demurrage_usd: float
    lightering_usd: float
    inland_rail_usd: float
    landed_cost_usd: float
    landed_cost_usd_mt: float
    landed_cost_inr_cr: float

    sea_days: float
    wait_days: float
    discharge_days: float
    total_cycle_days: float

    congestion_score: float
    monsoon_risk_score: float
    freight_volatility_score: float
    draft_risk_score: float
    risk_index: float

    supply_continuity: float
    schedule_headroom_pct: float
    continuity_risk_factor_pct: float
    execution_factor_pct: float
    confidence: float
    feasible: bool
    requires_lightering: bool
    explanation: str
    warnings: list = field(default_factory=list)
    rail_km: float = 0.0
    effective_capacity_mt: float = 0.0
    stowage_limit: str = "weight"
    fob_usd_mt: float = 0.0
    delivered_cost_usd_mt: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)


def ranking_score(candidate) -> float:
    """What every option is ranked on: cargo price plus risk-adjusted logistics.

    The risk loading applies to the logistics cost only - risk is about the
    voyage, the port and the rail leg, not about the price of the coal. Within
    one origin the cargo price is the same for every option, so it only decides
    between origins."""
    return candidate.fob_usd_mt + candidate.landed_cost_usd_mt * (
        1.0 + RISK_WEIGHT * candidate.risk_index / 100.0
    )


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


# Confidence ceiling. No chartering plan is certain, so the score must never
# read as a guarantee.
MAX_CONTINUITY = 97.0


def _schedule_headroom(cycle_days: float, window_days: int) -> float:
    """How comfortably the voyage cycle fits the laycan window, 0..1.

    Piecewise rather than linear because the risk of missing a window is not
    proportional to time used: consuming half the window is comfortable,
    consuming 90% of it is precarious, and the curve has to fall away sharply
    in that last stretch instead of degrading evenly.
    """
    if window_days <= 0:
        return 0.5
    ratio = cycle_days / window_days

    if ratio <= 0.5:            # comfortable
        return 1.0 - 0.20 * (ratio / 0.5)
    if ratio <= 0.8:            # tightening
        return 0.80 - 0.35 * ((ratio - 0.5) / 0.3)
    if ratio < 1.0:             # precarious
        return 0.45 - 0.35 * ((ratio - 0.8) / 0.2)
    return max(0.02, 0.10 - 0.08 * (ratio - 1.0))   # overruns the window


def _supply_continuity(
    *, cycle_days: float, window_days: int, risk_index: float,
    shipments: int, requires_lightering: bool,
) -> tuple:
    """Confidence that the parcel reaches the plant inside the window.

    The previous version was `50 + slack x 100`, clamped. Any cycle shorter
    than half the window therefore scored a flat 100/100 - which happened in
    42% of combinations - and it ignored disruption risk entirely, so a calm
    lane and a cyclone-exposed one scored identically. Three things actually
    govern whether the cargo lands on time:

      schedule   how much of the window the cycle consumes
      risk       congestion, weather and volatility exposure
      execution  each extra shipment is another chance to slip, and
                 lightering adds a transhipment that can stall

    They compound rather than add: a comfortable schedule cannot rescue a
    high-risk lane, which is exactly the judgement the previous score missed.
    """
    schedule = _schedule_headroom(cycle_days, window_days)
    risk_factor = 1.0 - 0.45 * (_clamp(risk_index) / 100.0)
    execution = 1.0 - 0.05 * max(0, shipments - 1) - (0.06 if requires_lightering else 0.0)
    execution = max(0.5, execution)

    score = 100.0 * schedule * risk_factor * execution
    return (
        round(_clamp(score, 3.0, MAX_CONTINUITY), 1),
        round(schedule * 100.0, 1),
        round(risk_factor * 100.0, 1),
        round(execution * 100.0, 1),
    )


def _laden_draft(vessel, utilisation: float) -> float:
    """A part-loaded ship floats higher. Approximate the sailing draft between
    a nominal ballast draft (55% of scantling) and the full laden draft."""
    return vessel.draft_m * (0.55 + 0.45 * utilisation)


def nearest_by_rail(candidates, ports, plant):
    """The berth closest to the plant by rail, and how its best option fared.

    That is the berth a planner looking at the map expects to win. When it
    does not, the page has to say why - otherwise the recommendation reads as
    if the plant was ignored. `candidates` must be ranked best-first.
    """
    key = network.plant_key(plant)
    if not key:
        return None
    distances = {code: km[key] for code, km in network.PLANT_RAIL_KM.items() if key in km}
    if not distances:
        return None
    code = min(distances, key=distances.get)
    port = next((p for p in ports if p.code == code), None)
    option = next((c for c in candidates if c.port_code == code), None)
    winner = candidates[0] if candidates else None

    result = {
        "port_code": code,
        "port_name": option.port_name if option else (port.name if port else code),
        "rail_km": float(distances[code]),
        "feasible": option is not None,
        "is_recommended": bool(option and winner and option is winner),
    }
    if option is None or winner is None:
        result["reasons"] = ["no vessel class that fits this parcel can berth there"]
        return result

    reasons = []
    if option.requires_lightering:
        reasons.append("draft-restricted, so part of the cargo must be lightered")
    if option.congestion_score >= 60:
        reasons.append(f"{option.wait_days:.1f} days of expected berth queue")
    if option.monsoon_risk_score >= 50:
        reasons.append("monsoon or cyclone season at that berth")
    if option.draft_risk_score >= 50 and not option.requires_lightering:
        reasons.append("tight under-keel clearance")

    result.update({
        "vessel_class": option.vessel_class,
        "landed_cost_usd_mt": option.landed_cost_usd_mt,
        "risk_index": option.risk_index,
        "cost_vs_recommended_usd_mt": round(
            option.delivered_cost_usd_mt - winner.delivered_cost_usd_mt, 2),
        "risk_vs_recommended": round(option.risk_index - winner.risk_index, 1),
        "recommended_rail_km": winner.rail_km,
        "reasons": reasons,
    })
    return result


def evaluate(
    *,
    vessels,
    ports,
    parcel_size: float,
    cargo_type: str,
    origin: str,
    plant: str,
    window_days: int,
    month: int,
    bunker_price: float,
    pressure_index: float,
    top_n: int = 5,
):
    """Return candidates ranked best-first, plus the context used to score them."""
    parcel_size = max(float(parcel_size), 1.0)
    distance_nm = model_registry.ORIGIN_DISTANCE_NM.get(origin, 4500.0)
    # Cargo density decides whether a ship fills by weight or by volume.
    profile = network.cargo_profile(cargo_type)
    fob = network.fob_usd_mt(cargo_type, origin)

    # One model call covers the whole grid. The rate depends on the lane and
    # market inputs rather than the berth, so it is predicted once per vessel
    # class and reused across that class's port options.
    rate_by_class = {}
    if vessels:
        rows = [
            {
                "origin": origin,
                "distance_nm": distance_nm,
                "month": month,
                "bunker_price": bunker_price,
                "pressure_index": pressure_index,
            }
            for _ in vessels
        ]
        base_rates = model_registry.predict_rates(rows)
        for vessel, base_rate in zip(vessels, base_rates):
            # Bigger *lifts* move a tonne more cheaply. Scale on the tonnage
            # actually carried per shipment, not on nominal capacity, so a
            # part-loaded ship does not collect a discount it has not earned.
            lift_cap = network.effective_capacity(vessel.capacity_mt, profile)
            shipments = max(1, math.ceil(parcel_size / lift_cap))
            lift_mt = max(parcel_size / shipments, 1.0)
            scale = (REFERENCE_DWT / lift_mt) ** SCALE_EXPONENT
            rate_by_class[vessel.id] = max(base_rate * scale, 1.0)

    candidates = []
    for vessel in vessels:
        # Space is booked by what the ship can actually lift of this cargo;
        # draft follows the weight aboard, not the space used.
        eff_cap = network.effective_capacity(vessel.capacity_mt, profile)
        shipments = max(1, math.ceil(parcel_size / eff_cap))
        booked_mt = shipments * eff_cap
        utilisation = parcel_size / booked_mt
        weight_fraction = parcel_size / (shipments * max(vessel.capacity_mt, 1.0))
        laden_draft = _laden_draft(vessel, weight_fraction)
        rate = rate_by_class.get(vessel.id, 25.0)

        # Space booked but not filled, beyond the customary tolerance.
        deadfreight_mt = max(
            0.0, (booked_mt - parcel_size) - DEADFREIGHT_TOLERANCE * booked_mt
        )
        deadfreight = deadfreight_mt * rate * DEADFREIGHT_RATE_FACTOR

        for port in ports:
            warnings = []

            usable_draft = (port.draft_m or 0.0) - UNDER_KEEL_CLEARANCE_M
            draft_gap = laden_draft - usable_draft
            requires_lightering = draft_gap > 0
            feasible = draft_gap <= MAX_LIGHTERABLE_GAP_M

            if (port.max_loa or 0) and vessel.capacity_mt > 150000 and port.max_loa < 300:
                feasible = False
                warnings.append(
                    f"{port.name} LOA limit {port.max_loa:.0f} m cannot accept a {vessel.class_type}."
                )

            if not feasible:
                continue

            # --- schedule -------------------------------------------------
            sea_days = distance_nm / (max(vessel.speed_knots, 1.0) * 24.0)
            discharge_days = parcel_size / max(port.mech_rate_mt_d * profile["handling"], 1.0)
            wait_days = (port.avg_wait_days or 0.0) * shipments
            port_days = wait_days + discharge_days
            total_cycle_days = sea_days + port_days

            # --- cost stack -----------------------------------------------
            ocean_freight = rate * parcel_size
            vessel_hire = (sea_days + port_days) * (vessel.daily_cost_usd or 0.0)
            port_dues = PORT_DUES_USD_PER_MT * parcel_size

            # Demurrage is owed to the owner once agreed laytime is exceeded, at
            # the berth's own rate - it is not the same money as vessel hire.
            demurrage_days = max(0.0, wait_days - FREE_LAYTIME_DAYS * shipments)
            demurrage = demurrage_days * float(getattr(port, "demurrage_usd_day", 9000.0) or 0.0)

            lightered_mt = 0.0
            if requires_lightering:
                # Roughly the tonnage that has to come off to float the ship in.
                lightered_mt = parcel_size * min(draft_gap / max(laden_draft, 1.0), 0.45)
                warnings.append(
                    f"Laden draft {laden_draft:.1f} m exceeds usable draft "
                    f"{usable_draft:.1f} m; {lightered_mt:,.0f} MT needs lightering."
                )
            lightering = lightered_mt * LIGHTERING_USD_PER_MT

            rail = network.rail_km(port, plant)
            inland_rail = rail * RAIL_USD_PER_MT_KM * parcel_size

            landed = (
                ocean_freight + deadfreight + vessel_hire
                + port_dues + demurrage + lightering + inland_rail
            )
            landed_per_mt = landed / parcel_size

            if deadfreight_mt > 0:
                warnings.append(
                    f"{deadfreight_mt:,.0f} MT of booked space unused - "
                    f"${deadfreight:,.0f} deadfreight at {utilisation * 100:.0f}% utilisation."
                )

            # --- risk -----------------------------------------------------
            # Wait time dominates, with a penalty for single-berth ports where
            # one occupied berth means the queue has nowhere to go.
            berths = int(getattr(port, "berths", 2) or 2)
            congestion = _clamp(
                (port.avg_wait_days or 0.0) / 6.0 * 100.0 + (12.0 if berths <= 1 else 0.0)
            )

            # Seasonal baseline, raised when this specific berth lists the month
            # as monsoon- or cyclone-affected.
            monsoon = float(MONSOON_RISK_BY_MONTH.get(month, 30))
            port_monsoon_months = [
                int(m) for m in str(getattr(port, "monsoon_months", "") or "").split(",")
                if m.strip().isdigit()
            ]
            if month in port_monsoon_months:
                monsoon = _clamp(monsoon * 1.25 + 10.0)
            volatility = _clamp(pressure_index)
            draft_risk = _clamp((draft_gap / MAX_LIGHTERABLE_GAP_M) * 100.0) if requires_lightering else _clamp(
                max(0.0, 25.0 - (usable_draft - laden_draft) * 12.0)
            )
            risk_index = round(
                0.30 * congestion + 0.25 * monsoon + 0.25 * volatility + 0.20 * draft_risk, 1
            )

            # --- fit against the laycan window ----------------------------
            (supply_continuity, schedule_headroom_pct,
             continuity_risk_factor_pct, execution_factor_pct) = _supply_continuity(
                cycle_days=total_cycle_days,
                window_days=window_days,
                risk_index=risk_index,
                shipments=shipments,
                requires_lightering=requires_lightering,
            )
            if total_cycle_days > window_days > 0:
                warnings.append(
                    f"Cycle of {total_cycle_days:.1f} days overruns the "
                    f"{window_days}-day window."
                )

            # --- confidence -----------------------------------------------
            model_r2 = float(
                model_registry.get_payload()["metadata"].get("r2_score", 0.95) or 0.95
            )
            confidence = round(
                _clamp(
                    (model_r2 * 100.0) * 0.55
                    + utilisation * 100.0 * 0.25
                    + (100.0 - risk_index) * 0.20,
                    0.0,
                    99.0,
                ),
                1,
            )

            candidates.append(
                Candidate(
                    vessel_class=vessel.class_type,
                    vessel_name=vessel.name,
                    port_name=port.name,
                    port_code=port.code,
                    origin=origin,
                    plant=plant,
                    parcel_mt=round(parcel_size, 1),
                    shipments=shipments,
                    utilisation_pct=round(utilisation * 100.0, 1),
                    freight_rate_usd_mt=round(rate, 2),
                    ocean_freight_usd=round(ocean_freight, 2),
                    deadfreight_usd=round(deadfreight, 2),
                    vessel_hire_usd=round(vessel_hire, 2),
                    port_dues_usd=round(port_dues, 2),
                    demurrage_usd=round(demurrage, 2),
                    lightering_usd=round(lightering, 2),
                    inland_rail_usd=round(inland_rail, 2),
                    landed_cost_usd=round(landed, 2),
                    landed_cost_usd_mt=round(landed_per_mt, 2),
                    landed_cost_inr_cr=round(landed * USD_TO_INR / 1e7, 2),
                    sea_days=round(sea_days, 1),
                    wait_days=round(wait_days, 1),
                    discharge_days=round(discharge_days, 1),
                    total_cycle_days=round(total_cycle_days, 1),
                    congestion_score=round(congestion, 1),
                    monsoon_risk_score=round(monsoon, 1),
                    freight_volatility_score=round(volatility, 1),
                    draft_risk_score=round(draft_risk, 1),
                    risk_index=risk_index,
                    supply_continuity=supply_continuity,
                    schedule_headroom_pct=schedule_headroom_pct,
                    continuity_risk_factor_pct=continuity_risk_factor_pct,
                    execution_factor_pct=execution_factor_pct,
                    confidence=confidence,
                    feasible=True,
                    requires_lightering=requires_lightering,
                    explanation="",
                    warnings=warnings,
                    rail_km=round(rail, 1),
                    effective_capacity_mt=round(eff_cap, 0),
                    stowage_limit=network.binding_limit(vessel.capacity_mt, profile),
                    fob_usd_mt=fob,
                    delivered_cost_usd_mt=round(fob + landed_per_mt, 2),
                )
            )

    # Rank on cargo price plus risk-adjusted logistics cost per tonne.
    candidates.sort(key=ranking_score)

    if candidates:
        best_cost = candidates[0].delivered_cost_usd_mt
        for rank, candidate in enumerate(candidates, start=1):
            delta = candidate.delivered_cost_usd_mt - best_cost
            candidate.explanation = _explain(candidate, rank, delta, cargo_type)

    context = {
        "origin": origin,
        "distance_nm": distance_nm,
        "month": month,
        "bunker_price_usd": round(bunker_price, 2),
        "pressure_index": round(pressure_index, 1),
        "parcel_mt": round(parcel_size, 1),
        "cargo_type": cargo_type,
        "cargo_profile": profile,
        "fob_usd_mt": fob,
        "fob_basis": network.FOB_BASIS,
        "plant": plant,
        "nearest_by_rail": nearest_by_rail(candidates, ports, plant),
        "window_days": window_days,
        "candidates_evaluated": len(candidates),
        "model_version": model_registry.get_payload()["metadata"].get("version", "runtime"),
    }
    return candidates[:top_n], context


def _explain(candidate: Candidate, rank: int, delta_per_mt: float, cargo_type: str) -> str:
    lead = "Lowest risk-adjusted landed cost." if rank == 1 else (
        f"Ranks #{rank}, +${delta_per_mt:.2f}/MT against the leader."
    )
    shipment_note = (
        f"{candidate.shipments} shipments at {candidate.utilisation_pct:.0f}% utilisation"
        if candidate.shipments > 1
        else f"single shipment at {candidate.utilisation_pct:.0f}% utilisation"
    )
    lightering_note = (
        " Requires lightering at the berth." if candidate.requires_lightering else ""
    )
    return (
        f"{lead} {candidate.vessel_class} into {candidate.port_name} for "
        f"{candidate.parcel_mt:,.0f} MT of {cargo_type} - {shipment_note}. "
        f"Ocean freight ${candidate.freight_rate_usd_mt:.2f}/MT, all-in "
        f"${candidate.landed_cost_usd_mt:.2f}/MT "
        f"(INR {candidate.landed_cost_inr_cr:.2f} Cr). "
        f"Cycle {candidate.total_cycle_days:.1f} days including "
        f"{candidate.wait_days:.1f} days expected waiting. "
        f"Risk index {candidate.risk_index:.0f}/100.{lightering_note}"
    )
