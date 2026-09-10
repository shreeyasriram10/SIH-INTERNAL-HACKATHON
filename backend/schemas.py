import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

ORM = ConfigDict(from_attributes=True)

# Kept as a local check rather than pydantic's EmailStr so the project does not
# need the optional email-validator dependency to boot.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


# ---------------------------------------------------------------------------
# Users / auth
# ---------------------------------------------------------------------------

class UserBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=5, max_length=254)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address.")
        return value


class UserCreate(UserBase):
    password: str = Field(min_length=5, max_length=128)


class User(UserBase):
    model_config = ORM

    id: int
    role: str


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str


class TokenData(BaseModel):
    email: Optional[str] = None


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

class PortBase(BaseModel):
    name: str
    code: str
    draft_m: float
    max_loa: float
    max_beam_m: float = 45.0
    berths: int = 2
    avg_wait_days: float
    mech_rate_mt_d: float
    rail_evac_km: float = 380.0
    demurrage_usd_day: float = 9000.0
    monsoon_months: str = "6,7,8,9"


class Port(PortBase):
    model_config = ORM

    id: int


class VesselBase(BaseModel):
    name: str
    class_type: str
    capacity_mt: float
    draft_m: float
    speed_knots: float
    daily_cost_usd: float


class Vessel(VesselBase):
    model_config = ORM

    id: int


# ---------------------------------------------------------------------------
# Cargo
# ---------------------------------------------------------------------------

class CargoRequestBase(BaseModel):
    parcel_size: float = Field(gt=0, le=1_000_000, description="Parcel tonnage (MT)")
    cargo_type: str = Field(min_length=1, max_length=80)
    origin: str = Field(min_length=1, max_length=80)
    plant: str = Field(min_length=1, max_length=80)
    window_days: int = Field(ge=1, le=365)


class CargoRequestCreate(CargoRequestBase):
    pass


class CargoRequest(CargoRequestBase):
    model_config = ORM

    id: int
    user_id: Optional[int] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Decision engine
# ---------------------------------------------------------------------------

class OptimizeRequest(CargoRequestBase):
    """Market inputs default to the dataset means so the endpoint is usable
    with cargo parameters alone."""

    month: int = Field(default=0, ge=0, le=12, description="0 = current month")
    bunker_price: float = Field(default=697.0, gt=0, le=5000)
    pressure_index: float = Field(default=52.5, ge=0, le=100)
    top_n: int = Field(default=5, ge=1, le=25)
    persist: bool = Field(default=True, description="Store the winning option")


class Lane(BaseModel):
    """One origin lane to evaluate, with the market pressure the dashboard uses
    for it - sent explicitly so a scenario is scored on exactly the inputs the
    Command Centre used, not on a server-side default."""

    origin: str = Field(min_length=1, max_length=80)
    pressure_index: float = Field(ge=0, le=100)


class ScenarioRequest(OptimizeRequest):
    lanes: Optional[list[Lane]] = Field(default=None, max_length=8)
    scenario: Literal[
        "baseline",
        "cyclone",
        "port_blocked",
        "freight_spike",
        "bunker_spike",
        "vessel_unavail",
        "monsoon",
    ] = "baseline"
    blocked_port: Optional[str] = None
    unavailable_class: Optional[str] = None


class RecommendationBase(BaseModel):
    landed_cost_usd: float
    confidence: float
    risk_index: float
    explanation: str


class Recommendation(RecommendationBase):
    model_config = ORM

    id: int
    cargo_request_id: Optional[int] = None
    vessel_class: Optional[str] = None
    origin_name: Optional[str] = None
    port_name: Optional[str] = None
    supply_continuity: Optional[float] = None
    created_at: datetime
