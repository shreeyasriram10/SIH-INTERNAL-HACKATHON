from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import get_db
from services import decision_engine, idle

router = APIRouter()


def _reference_data(db: Session):
    vessels = db.query(models.Vessel).all()
    ports = db.query(models.Port).all()
    if not vessels or not ports:
        raise HTTPException(
            status_code=503,
            detail="Reference fleet/port data is not seeded. Run backend/seed_data.py.",
        )
    return vessels, ports


def _resolve_month(month: int) -> int:
    return month if month else datetime.now(timezone.utc).month


@router.post("/optimize")
def optimize_route(
    request: schemas.OptimizeRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Score every feasible vessel-class x port pairing and return the ranked
    shortlist with a full cost and risk breakdown.

    Authenticated: the response discloses landed cost, lane economics and
    procurement timing - the most commercially sensitive output here.
    """
    vessels, ports = _reference_data(db)
    month = _resolve_month(request.month)

    options, context = decision_engine.evaluate(
        vessels=vessels,
        ports=ports,
        parcel_size=request.parcel_size,
        cargo_type=request.cargo_type,
        origin=request.origin,
        plant=request.plant,
        window_days=request.window_days,
        month=month,
        bunker_price=request.bunker_price,
        pressure_index=request.pressure_index,
        top_n=request.top_n,
    )

    if not options:
        raise HTTPException(
            status_code=422,
            detail="No feasible vessel/port combination for this parcel. "
                   "Try a smaller parcel or a deeper-draft port.",
        )

    best = options[0]
    cargo_request_id = None

    if request.persist:
        cargo_row = models.CargoRequest(
            user_id=user.id if user else None,
            parcel_size=request.parcel_size,
            cargo_type=request.cargo_type,
            origin=request.origin,
            plant=request.plant,
            window_days=request.window_days,
        )
        db.add(cargo_row)
        db.flush()
        cargo_request_id = cargo_row.id

        db.add(models.Recommendation(
            cargo_request_id=cargo_request_id,
            vessel_class=best.vessel_class,
            origin_name=best.origin,
            port_name=best.port_name,
            landed_cost_usd=best.landed_cost_usd,
            confidence=best.confidence,
            risk_index=best.risk_index,
            supply_continuity=best.supply_continuity,
            explanation=best.explanation,
        ))
        db.add(models.RiskAssessmentHistory(
            origin=best.origin,
            port=best.port_name,
            freight_volatility_score=best.freight_volatility_score,
            congestion_score=best.congestion_score,
            monsoon_risk_score=best.monsoon_risk_score,
            overall_risk_index=best.risk_index,
        ))
        db.add(models.AuditLog(
            action="DECISION_OPTIMIZE",
            user_email=user.email if user else "anonymous",
            details=(
                f"{request.parcel_size:,.0f} MT {request.cargo_type} from "
                f"{request.origin} -> {best.vessel_class} via {best.port_name} "
                f"at ${best.landed_cost_usd_mt:.2f}/MT"
            ),
        ))
        db.commit()

    return {
        "status": "SUCCESS",
        "cargo_request_id": cargo_request_id,
        "context": context,
        "recommended": best.as_dict(),
        "options": [option.as_dict() for option in options],
    }


def _risk_adjusted(candidate) -> float:
    return decision_engine.ranking_score(candidate)


def _lanes(request: schemas.ScenarioRequest):
    """The origin lanes to score. The dashboard sends every lane it is comparing,
    each with the pressure index it used, so a scenario is evaluated on exactly
    the inputs behind the recommendation on screen."""
    if request.lanes:
        return [(lane.origin, lane.pressure_index) for lane in request.lanes]
    return [(request.origin, request.pressure_index)]


def _evaluate_lanes(*, vessels, ports, request, month, bunker_price,
                    pressure_mult=1.0, top_n):
    """Score every lane, merge, and rank the whole set on one scale."""
    merged, context = [], None
    for origin, pressure in _lanes(request):
        options, lane_context = decision_engine.evaluate(
            vessels=vessels,
            ports=ports,
            parcel_size=request.parcel_size,
            cargo_type=request.cargo_type,
            origin=origin,
            plant=request.plant,
            window_days=request.window_days,
            month=month,
            bunker_price=bunker_price,
            pressure_index=min(100.0, pressure * pressure_mult),
            top_n=25,
        )
        merged.extend(options)
        context = context or lane_context

    merged.sort(key=_risk_adjusted)
    if merged:
        # Explanations were ranked within each lane; re-rank them across the set.
        best_cost = merged[0].delivered_cost_usd_mt
        for rank, candidate in enumerate(merged, start=1):
            candidate.explanation = decision_engine._explain(
                candidate, rank, candidate.delivered_cost_usd_mt - best_cost, request.cargo_type
            )
    if context is not None:
        context = {**context, "lanes": [origin for origin, _ in _lanes(request)],
                   "candidates_evaluated": len(merged),
                   "nearest_by_rail": decision_engine.nearest_by_rail(
                       merged, ports, request.plant)}
    return merged[:top_n], context


@router.post("/simulate")
def simulate_scenario(
    request: schemas.ScenarioRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Score the current cargo on baseline conditions and under a disruption.

    Both legs come from this one call, on the same lanes and inputs, so the
    before/after comparison, the recommendation and the map drawn from them
    cannot disagree with each other or with what the user entered.
    """
    vessels, ports = _reference_data(db)
    month = _resolve_month(request.month)

    baseline, baseline_context = _evaluate_lanes(
        vessels=vessels, ports=ports, request=request, month=month,
        bunker_price=request.bunker_price, top_n=request.top_n,
    )
    if not baseline:
        raise HTTPException(status_code=422, detail="No feasible baseline option.")

    shock = _apply_shock(request, vessels, ports, month, baseline[0])

    disrupted, context = _evaluate_lanes(
        vessels=shock["vessels"], ports=shock["ports"], request=request,
        month=shock["month"], bunker_price=shock["bunker_price"],
        pressure_mult=shock["pressure_mult"], top_n=request.top_n,
    )
    if not disrupted:
        raise HTTPException(
            status_code=422,
            detail=f"Scenario '{request.scenario}' leaves no feasible option - "
                   "the lane is effectively closed.",
        )

    base_best, shock_best = baseline[0], disrupted[0]
    diff = shock_best.landed_cost_usd - base_best.landed_cost_usd

    db.add(models.SimulationHistory(
        scenario_type=request.scenario,
        baseline_cost=base_best.landed_cost_usd,
        disrupted_cost=shock_best.landed_cost_usd,
        diff_amount=diff,
        mitigation_action=shock["mitigation"],
    ))
    db.add(models.AuditLog(
        action="SCENARIO_SIMULATE",
        user_email=user.email,
        details=f"{request.scenario}: {request.parcel_size:,.0f} MT {request.cargo_type} "
                f"-> delta ${diff:,.0f} ({shock['mitigation']})",
    ))
    db.commit()

    return {
        "status": "SUCCESS",
        "scenario": request.scenario,
        "shock_applied": shock["description"],
        "mitigation_action": shock["mitigation"],
        "blocked_port": shock["blocked_port"],
        "unavailable_class": shock["unavailable_class"],
        "context": context,
        "baseline_context": baseline_context,
        "baseline": base_best.as_dict(),
        "disrupted": shock_best.as_dict(),
        "baseline_options": [option.as_dict() for option in baseline],
        "disrupted_options": [option.as_dict() for option in disrupted],
        "delta_usd": round(diff, 2),
        "delta_usd_mt": round(
            shock_best.landed_cost_usd_mt - base_best.landed_cost_usd_mt, 2
        ),
        # Ranking is on risk-adjusted cost, so a blocked berth can hand back a
        # fallback that is cheaper per tonne but riskier. This figure is the one
        # the ranking actually moved on.
        "delta_risk_adjusted_usd_mt": round(
            _risk_adjusted(shock_best) - _risk_adjusted(base_best), 2
        ),
        "delta_pct": round(
            (diff / base_best.landed_cost_usd * 100.0) if base_best.landed_cost_usd else 0.0, 2
        ),
        "alternatives": [option.as_dict() for option in disrupted[:3]],
    }


def _apply_shock(request: schemas.ScenarioRequest, vessels, ports, month: int, baseline_best) -> dict:
    """Translate a scenario into perturbed inputs. Ports and vessels are copied
    in memory only - nothing is written back to the reference data.

    Where a scenario targets "the" berth or "the" class, it means the one the
    current cargo was actually going to use, not the first row in the table.
    """
    shocked = {
        "vessels": list(vessels),
        "ports": list(ports),
        "month": month,
        "bunker_price": request.bunker_price,
        "pressure_mult": 1.0,
        "blocked_port": None,
        "unavailable_class": None,
        "description": "No change.",
        "mitigation": "Maintain the baseline charter plan.",
    }
    scenario = request.scenario

    if scenario == "cyclone":
        shocked["month"] = 11  # peak Bay of Bengal cyclone month
        shocked["pressure_mult"] = 1.35
        shocked["ports"] = [_port_with_wait(p, p.avg_wait_days + 4.0) for p in ports]
        shocked["description"] = "Cyclone alert: +4 days berth wait, market pressure +35%."
        shocked["mitigation"] = "Shift the laycan and pre-position at a deeper alternate berth."

    elif scenario == "monsoon":
        shocked["month"] = 7
        shocked["ports"] = [_port_with_wait(p, p.avg_wait_days + 1.8) for p in ports]
        shocked["description"] = "South-west monsoon: +1.8 days berth wait."
        shocked["mitigation"] = "Front-load tonnage into the pre-monsoon window."

    elif scenario == "port_blocked":
        name = request.blocked_port or baseline_best.port_name
        remaining = [p for p in ports if p.name.strip().lower() != name.strip().lower()]
        if not remaining:
            raise HTTPException(status_code=422, detail="Cannot block every port.")
        shocked["ports"] = remaining
        shocked["blocked_port"] = name
        shocked["description"] = f"{name} unavailable."
        shocked["mitigation"] = "Divert to the next-best berth and re-book rail evacuation."

    elif scenario == "freight_spike":
        shocked["pressure_mult"] = 1.5
        shocked["description"] = "Freight market pressure index +50%."
        shocked["mitigation"] = "Lock a period charter to cap exposure to spot rates."

    elif scenario == "bunker_spike":
        shocked["bunker_price"] = request.bunker_price * 1.4
        shocked["description"] = "Bunker price +40%, fed through the freight model."
        shocked["mitigation"] = "Negotiate a bunker-adjustment clause and slow-steam."

    elif scenario == "vessel_unavail":
        name = request.unavailable_class or baseline_best.vessel_class
        remaining = [v for v in vessels if v.class_type.strip().lower() != name.strip().lower()]
        if not remaining:
            raise HTTPException(status_code=422, detail="Cannot remove every vessel class.")
        shocked["vessels"] = remaining
        shocked["unavailable_class"] = name
        shocked["description"] = f"{name} tonnage unavailable."
        shocked["mitigation"] = "Split the parcel across the smaller tonnage still available."

    return shocked


class _PortView:
    """A port with one attribute overridden, so a scenario can perturb it
    without touching the ORM row (and therefore without risking a write).

    Every field the engine reads is copied. An earlier version copied only
    seven, so under cyclone and monsoon every berth silently fell back to the
    engine's defaults - two berths, $9,000/day demurrage, no monsoon months.
    """

    FIELDS = ("name", "code", "draft_m", "max_loa", "max_beam_m", "berths",
              "avg_wait_days", "mech_rate_mt_d", "rail_evac_km",
              "demurrage_usd_day", "monsoon_months")

    def __init__(self, port, **overrides):
        for attr in self.FIELDS:
            setattr(self, attr, overrides.get(attr, getattr(port, attr, None)))


def _port_with_wait(port, avg_wait_days: float):
    return _PortView(port, avg_wait_days=avg_wait_days)


@router.get("/history")
def recommendation_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    rows = (
        db.query(models.Recommendation)
        .order_by(models.Recommendation.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    # Who reads priced recommendations matters as much as who writes them.
    db.add(models.AuditLog(
        action="RECOMMENDATION_HISTORY_READ",
        user_email=user.email,
        details=f"Read {len(rows)} recommendation(s)",
    ))
    db.commit()
    return {"count": len(rows), "items": [
        {
            "id": row.id,
            "vessel_class": row.vessel_class,
            "origin": row.origin_name,
            "port": row.port_name,
            "landed_cost_usd": row.landed_cost_usd,
            "confidence": row.confidence,
            "risk_index": row.risk_index,
            "created_at": row.created_at,
        }
        for row in rows
    ]}


@router.post("/idle-reposition")
def idle_reposition(
    request: schemas.IdleVesselRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Wait or ballast, for a vessel sitting idle with no cargo fixed.

    The inverse of the six disruption scenarios: those re-route a cargo that
    has lost its plan, this one finds work for a ship that has none. Nothing
    in the routing path is touched.

    Authenticated: it discloses hire economics and where tonnage is expected to
    open up, which is commercially sensitive in the same way landed cost is.
    """
    vessels, ports = _reference_data(db)
    try:
        return idle.evaluate_idle(
            vessels=vessels,
            ports=ports,
            vessel_class=request.vessel_class,
            port_code=request.port_code,
            days_idle=request.days_idle,
            month=_resolve_month(request.month),
            bunker_price=request.bunker_price,
            pressure_index=request.pressure_index,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
