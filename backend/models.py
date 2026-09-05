from sqlalchemy import Boolean, Column, Integer, String, Float, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base

def utc_now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="Analyst") # Admin, Analyst, Procurement Officer
    created_at = Column(DateTime, default=utc_now)

class Port(Base):
    __tablename__ = "ports"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    code = Column(String, unique=True, index=True)
    draft_m = Column(Float)
    max_loa = Column(Float)
    avg_wait_days = Column(Float)
    mech_rate_mt_d = Column(Float)
    rail_evac_km = Column(Float, default=380.0)

class Vessel(Base):
    __tablename__ = "vessels"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    class_type = Column(String) # Panamax, Supramax, Capesize, Handysize, Post-Panamax
    capacity_mt = Column(Float)
    draft_m = Column(Float)
    speed_knots = Column(Float)
    daily_cost_usd = Column(Float)

class FreightHistory(Base):
    __tablename__ = "freight_history"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=utc_now)
    origin = Column(String, index=True)
    destination = Column(String, index=True)
    rate_usd = Column(Float)
    bunker_price_usd = Column(Float)
    pressure_index = Column(Float)

class CargoRequest(Base):
    __tablename__ = "cargo_requests"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    parcel_size = Column(Float)
    cargo_type = Column(String)
    origin = Column(String)
    plant = Column(String)
    window_days = Column(Integer)
    created_at = Column(DateTime, default=utc_now)

class Recommendation(Base):
    __tablename__ = "recommendations"
    id = Column(Integer, primary_key=True, index=True)
    cargo_request_id = Column(Integer, ForeignKey("cargo_requests.id"), nullable=True)
    vessel_class = Column(String)
    origin_name = Column(String)
    port_name = Column(String)
    landed_cost_usd = Column(Float)
    confidence = Column(Float)
    risk_index = Column(Float)
    supply_continuity = Column(Float)
    explanation = Column(Text)
    created_at = Column(DateTime, default=utc_now)

class ForecastHistory(Base):
    __tablename__ = "forecast_history"
    id = Column(Integer, primary_key=True, index=True)
    origin = Column(String, index=True)
    horizon_days = Column(Integer)
    predicted_rate_usd = Column(Float)
    ci_lower_usd = Column(Float)
    ci_upper_usd = Column(Float)
    bunker_price_usd = Column(Float)
    pressure_index = Column(Float)
    model_version = Column(String, default="v2.1-ensemble")
    created_at = Column(DateTime, default=utc_now)

class SimulationHistory(Base):
    __tablename__ = "simulation_history"
    id = Column(Integer, primary_key=True, index=True)
    scenario_type = Column(String, index=True) # cyclone, port_blocked, freight_spike, bunker_spike, vessel_unavail, monsoon
    baseline_cost = Column(Float)
    disrupted_cost = Column(Float)
    diff_amount = Column(Float)
    mitigation_action = Column(String)
    timestamp = Column(DateTime, default=utc_now)

class RiskAssessmentHistory(Base):
    __tablename__ = "risk_assessments"
    id = Column(Integer, primary_key=True, index=True)
    origin = Column(String)
    port = Column(String)
    freight_volatility_score = Column(Float)
    congestion_score = Column(Float)
    monsoon_risk_score = Column(Float)
    overall_risk_index = Column(Float)
    timestamp = Column(DateTime, default=utc_now)

class SavedReport(Base):
    __tablename__ = "saved_reports"
    id = Column(Integer, primary_key=True, index=True)
    report_title = Column(String)
    cargo_summary = Column(String)
    recommended_strategy = Column(String)
    total_cost_inr_cr = Column(Float)
    generated_by = Column(String, default="SAIL Procurement Officer")
    content_html = Column(Text)
    created_at = Column(DateTime, default=utc_now)

class MLModelMetadata(Base):
    __tablename__ = "ml_model_metadata"
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String)
    algorithm = Column(String)
    version = Column(String)
    dataset_type = Column(String)
    records_count = Column(Integer)
    features_list = Column(String)
    target_variable = Column(String)
    r2_score = Column(Float)
    mae_usd = Column(Float)
    rmse_usd = Column(Float)
    mape_pct = Column(Float)
    is_active = Column(Boolean, default=True)
    trained_at = Column(DateTime, default=utc_now)

class TrainingHistory(Base):
    __tablename__ = "training_history"
    id = Column(Integer, primary_key=True, index=True)
    training_run_id = Column(String, unique=True)
    algorithm = Column(String)
    dataset_size = Column(Integer)
    r2_score = Column(Float)
    mae_usd = Column(Float)
    rmse_usd = Column(Float)
    training_duration_sec = Column(Float)
    status = Column(String, default="SUCCESS")
    timestamp = Column(DateTime, default=utc_now)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, index=True)
    user_email = Column(String, default="system")
    details = Column(String)
    ip_address = Column(String, default="127.0.0.1")
    timestamp = Column(DateTime, default=utc_now)
