from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from typing import List

router = APIRouter()

class OptimizationRequest(schemas.CargoRequestBase):
    pass

@router.post("/optimize", response_model=List[schemas.RecommendationBase])
def optimize_route(request: OptimizationRequest, db: Session = Depends(get_db)):
    # Dummy logic for now. 
    # Will integrate with DB data and ML model later
    
    recs = [
        schemas.RecommendationBase(
            landed_cost_usd=120.5,
            confidence=0.85,
            risk_index=30.0,
            explanation="Optimal route using Panamax vessel to Paradip port."
        ),
        schemas.RecommendationBase(
            landed_cost_usd=125.0,
            confidence=0.80,
            risk_index=20.0,
            explanation="Alternative route with lower congestion risk."
        )
    ]
    return recs
