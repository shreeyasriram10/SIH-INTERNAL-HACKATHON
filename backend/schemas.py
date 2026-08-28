from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    name: str
    email: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    role: str

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

class TokenData(BaseModel):
    email: Optional[str] = None

class PortBase(BaseModel):
    name: str
    code: str
    draft_m: float
    max_loa: float
    avg_wait_days: float
    mech_rate_mt_d: float

class Port(PortBase):
    id: int

    class Config:
        orm_mode = True

class VesselBase(BaseModel):
    name: str
    class_type: str
    capacity_mt: float
    draft_m: float
    speed_knots: float
    daily_cost_usd: float

class Vessel(VesselBase):
    id: int

    class Config:
        orm_mode = True

class CargoRequestBase(BaseModel):
    parcel_size: float
    cargo_type: str
    origin: str
    plant: str
    window_days: int

class CargoRequestCreate(CargoRequestBase):
    pass

class CargoRequest(CargoRequestBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class RecommendationBase(BaseModel):
    landed_cost_usd: float
    confidence: float
    risk_index: float
    explanation: str

class Recommendation(RecommendationBase):
    id: int
    cargo_request_id: int
    vessel_id: int
    port_id: int

    class Config:
        orm_mode = True
