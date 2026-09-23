from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import auth
import models
from database import get_db
from routers.decision import _reference_data
from services import market

router = APIRouter()


@router.get("/congestion")
def congestion(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Twelve-month berth-queue forecast for every discharge port."""
    _, ports = _reference_data(db)
    return market.congestion_forecast(ports)


@router.get("/demand-supply")
def demand_supply(
    cargo_type: str = Query("coking_coal", max_length=80),
    plant: str = Query("rourkela", max_length=80),
    origin: str = Query("any", max_length=80),
    bunker_price: float = Query(697.0, gt=0, le=5000),
    pressure_index: float = Query(52.5, ge=0, le=100),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Plant import requirement against discharge capacity and freight
    tightness, month by month."""
    _, ports = _reference_data(db)
    return market.demand_supply(ports=ports, cargo_type=cargo_type, plant=plant, origin=origin,
                                bunker_price=bunker_price, pressure_index=pressure_index)


@router.get("/seasonal")
def seasonal(
    origin: str = Query("any", max_length=80),
    bunker_price: float = Query(697.0, gt=0, le=5000),
    pressure_index: float = Query(52.5, ge=0, le=100),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Freight, weather and berth queue for each calendar month, ranked."""
    _, ports = _reference_data(db)
    return market.seasonal_calendar(ports=ports, origin=origin, bunker_price=bunker_price,
                                    pressure_index=pressure_index)
