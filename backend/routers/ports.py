from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import auth
import models
import schemas
from typing import List

router = APIRouter()

@router.get("/", response_model=List[schemas.Port])
def read_ports(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Berth draft, handling rates, waiting times and demurrage are negotiated
    commercial terms, not public reference data."""
    ports = db.query(models.Port).offset(skip).limit(limit).all()
    return ports
