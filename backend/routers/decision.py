from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import get_db
from services import decision_engine

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
    user: models.User | None = Depends(auth.get_optional_user),
):
    """Score every feasible vessel-class x port pairing and return the ranked
    shortlist with a full cost and risk breakdown."""
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


@router.post("/simulate")
def simulate_scenario(
    request: schemas.ScenarioRequest,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(auth.get_optional_user),
):
    """Run the optimizer twice - once on baseline market/fleet conditions and
    once under a disruption - and report the delta plus a mitigation."""
    vessels, ports = _reference_data(db)
    month = _resolve_month(request.month)

    baseline, _ = decision_engine.evaluate(
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
        top_n=1,
    )
    if not baseline:
        raise HTTPException(status_code=422, detail="No feasible baseline option.")

    shocked = _apply_shock(request, vessels, ports, month)

    disrupted, context = decision_engine.evaluate(
        vessels=shocked["vessels"],
        ports=shocked["ports"],
        parcel_size=request.parcel_size,
        cargo_type=request.cargo_type,
        origin=request.origin,
        plant=request.plant,
        window_days=request.window_days,
        month=shocked["month"],
        bunker_price=shocked["bunker_price"],
        pressure_index=shocked["pressure_index"],
        top_n=3,
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
        mitigation_action=shocked["mitigation"],
    ))
    db.add(models.AuditLog(
        action="SCENARIO_SIMULATE",
        user_email=user.email if user else "anonymous",
        details=f"{request.scenario}: delta ${diff:,.0f} "
                f"({shocked['mitigation']})",
    ))
    db.commit()

    return {
        "status": "SUCCESS",
        "scenario": request.scenario,
        "shock_applied": shocked["description"],
        "mitigation_action": shocked["mitigation"],
        "context": context,
        "baseline": base_best.as_dict(),
        "disrupted": shock_best.as_dict(),
        "delta_usd": round(diff, 2),
        "delta_usd_mt": round(
            shock_best.landed_cost_usd_mt - base_best.landed_cost_usd_mt, 2
        ),
        "delta_pct": round(
            (diff / base_best.landed_cost_usd * 100.0) if base_best.landed_cost_usd else 0.0, 2
        ),
        "alternatives": [option.as_dict() for option in disrupted],
    }


def _apply_shock(request: schemas.ScenarioRequest, vessels, ports, month: int) -> dict:
    """Translate a scenario name into perturbed inputs. Ports and vessels are
    filtered/copied in memory only - nothing is written back to the database."""
    shocked = {
        "vessels": list(vessels),
        "ports": list(ports),
        "month": month,
        "bunker_price": request.bunker_price,
        "pressure_index": request.pressure_index,
        "description": "No change.",
        "mitigation": "Maintain the baseline charter plan.",
    }
    scenario = request.scenario

    if scenario == "cyclone":
        shocked["month"] = 11  # peak Bay of Bengal cyclone month
        shocked["pressure_index"] = min(100.0, request.pressure_index * 1.35)
        shocked["ports"] = [_port_with_wait(p, p.avg_wait_days + 4.0) for p in ports]
        shocked["description"] = "Cyclone alert: +4 days berth wait, market pressure +35%."
        shocked["mitigation"] = "Shift the laycan and pre-position at a deeper alternate berth."

    elif scenario == "monsoon":
        shocked["month"] = 7
        shocked["ports"] = [_port_with_wait(p, p.avg_wait_days + 1.8) for p in ports]
        shocked["description"] = "South-west monsoon: +1.8 days berth wait."
        shocked["mitigation"] = "Front-load tonnage into the pre-monsoon window."

    elif scenario == "port_blocked":
        target = (request.blocked_port or ports[0].name).strip().lower()
        remaining = [p for p in ports if p.name.strip().lower() != target]
        if not remaining:
            raise HTTPException(status_code=422, detail="Cannot block every port.")
        shocked["ports"] = remaining
        shocked["description"] = f"{request.blocked_port or ports[0].name} unavailable."
        shocked["mitigation"] = "Divert to the next-best berth and re-book rail evacuation."

    elif scenario == "freight_spike":
        shocked["pressure_index"] = min(100.0, request.pressure_index * 1.5)
        shocked["description"] = "Freight market pressure index +50%."
        shocked["mitigation"] = "Lock a period charter to cap exposure to spot rates."

    elif scenario == "bunker_spike":
        shocked["bunker_price"] = request.bunker_price * 1.4
        shocked["description"] = "Bunker price +40%."
        shocked["mitigation"] = "Negotiate a bunker-adjustment clause and slow-steam."

    elif scenario == "vessel_unavail":
        target = (request.unavailable_class or "Capesize").strip().lower()
        remaining = [v for v in vessels if v.class_type.strip().lower() != target]
        if not remaining:
            raise HTTPException(status_code=422, detail="Cannot remove every vessel class.")
        shocked["vessels"] = remaining
        shocked["description"] = f"{request.unavailable_class or 'Capesize'} tonnage unavailable."
        shocked["mitigation"] = "Split the parcel across smaller available tonnage."

    return shocked


class _PortView:
    """Lightweight stand-in so a scenario can perturb a port without touching
    the ORM row (and therefore without risking a write on commit)."""

    __slots__ = ("name", "code", "draft_m", "max_loa", "avg_wait_days",
                 "mech_rate_mt_d", "rail_evac_km")

    def __init__(self, port, avg_wait_days):
        self.name = port.name
        self.code = port.code
        self.draft_m = port.draft_m
        self.max_loa = port.max_loa
        self.avg_wait_days = avg_wait_days
        self.mech_rate_mt_d = port.mech_rate_mt_d
        self.rail_evac_km = port.rail_evac_km


def _port_with_wait(port, avg_wait_days: float):
    return _PortView(port, avg_wait_days)


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
