from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import get_db

router = APIRouter()


@router.post("/", response_model=schemas.CargoRequest, status_code=201)
def create_cargo_request(
    request: schemas.CargoRequestCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    db_request = models.CargoRequest(**request.model_dump(), user_id=user.id)
    db.add(db_request)
    db.add(models.AuditLog(
        action="CARGO_REQUEST_CREATED",
        user_email=user.email,
        details=f"{request.parcel_size:,.0f} MT {request.cargo_type} from {request.origin}",
    ))
    db.commit()
    db.refresh(db_request)
    return db_request


@router.get("/", response_model=List[schemas.CargoRequest])
def read_cargo_requests(
    skip: int = 0,
    limit: int = 100,
    mine_only: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    query = db.query(models.CargoRequest)
    if mine_only:
        query = query.filter(models.CargoRequest.user_id == user.id)
    return (
        query.order_by(models.CargoRequest.created_at.desc())
        .offset(skip)
        .limit(min(limit, 200))
        .all()
    )
