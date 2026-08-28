from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from typing import List

router = APIRouter()

@router.get("/", response_model=List[schemas.Vessel])
def read_vessels(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    vessels = db.query(models.Vessel).offset(skip).limit(limit).all()
    return vessels
