from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from typing import List

router = APIRouter()

@router.post("/", response_model=schemas.CargoRequest)
def create_cargo_request(request: schemas.CargoRequestCreate, db: Session = Depends(get_db)):
    # Assuming user_id=1 for now (to be updated with actual auth)
    db_request = models.CargoRequest(**request.dict(), user_id=1)
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    return db_request

@router.get("/", response_model=List[schemas.CargoRequest])
def read_cargo_requests(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    requests = db.query(models.CargoRequest).offset(skip).limit(limit).all()
    return requests
