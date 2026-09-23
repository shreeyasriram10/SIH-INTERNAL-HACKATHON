from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import get_db
from routers.decision import _reference_data
from services import planning

router = APIRouter()


@router.post("/charter-plan")
def charter_plan(
    request: schemas.PlanRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """The procurement programme behind a charter decision: month-by-month
    engine runs, the optimised voyage schedule, spot vs short- and
    medium-term contract, three-month cost, market timing and the final
    recommendation.

    Open to every signed-in role: it is the plan the Procurement Officer
    executes, and it changes nothing.
    """
    vessels, ports = _reference_data(db)
    plan = planning.build_plan(vessels=vessels, ports=ports, request=request)
    db.add(models.AuditLog(
        action="CHARTER_PLAN",
        user_email=user.email,
        details=(f"{request.cargo_type} {request.origin} -> {request.plant}: "
                 f"{plan['inputs']['total_requirement_mt']:,.0f} MT over {request.horizon_months} months"
                 + (f" -> {plan['recommendation']['charter_label']}" if plan.get("recommendation") else "")),
    ))
    db.commit()
    return plan


@router.post("/constraints")
def constraint_checks(
    request: schemas.ConstraintRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Draft, LOA, beam and handling checks for every vessel class at the
    origin terminal and at every discharge berth - the same checks the engine
    applies when it ranks."""
    vessels, ports = _reference_data(db)
    return planning.constraint_matrix(vessels=vessels, ports=ports, cargo_type=request.cargo_type,
                                      origin=request.origin, parcel_size=request.parcel_size)
