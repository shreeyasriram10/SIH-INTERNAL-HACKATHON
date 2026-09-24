from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import get_db
from routers.decision import _reference_data
from services import alerts, sos

router = APIRouter()


@router.get("/alerts")
def alert_feed(
    cargo_type: str = Query("coking_coal", max_length=80),
    plant: str = Query("rourkela", max_length=80),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Weather, congestion, market-timing and supply alerts for the next three
    months."""
    _, ports = _reference_data(db)
    return alerts.build_alerts(ports=ports, cargo_type=cargo_type, plant=plant)


@router.get("/emergency", response_model=list[schemas.EmergencyContact])
def list_contacts(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    return (db.query(models.EmergencyContact)
            .order_by(models.EmergencyContact.sort_order, models.EmergencyContact.id).all())


@router.post("/emergency", response_model=schemas.EmergencyContact, status_code=201)
def add_contact(
    contact: schemas.EmergencyContactIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_roles(auth.ROLE_ADMIN)),
):
    row = models.EmergencyContact(**contact.model_dump())
    db.add(row)
    db.add(models.AuditLog(action="EMERGENCY_CONTACT_ADD", user_email=user.email,
                           details=f"{contact.category}: {contact.name}"))
    db.commit()
    db.refresh(row)
    return row


@router.put("/emergency/{contact_id}", response_model=schemas.EmergencyContact)
def update_contact(
    contact_id: int,
    contact: schemas.EmergencyContactIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_roles(auth.ROLE_ADMIN)),
):
    row = db.get(models.EmergencyContact, contact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    for field, value in contact.model_dump().items():
        setattr(row, field, value)
    db.add(models.AuditLog(action="EMERGENCY_CONTACT_UPDATE", user_email=user.email,
                           details=f"#{contact_id} {contact.name}"))
    db.commit()
    db.refresh(row)
    return row


@router.delete("/emergency/{contact_id}", status_code=204)
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_roles(auth.ROLE_ADMIN)),
):
    row = db.get(models.EmergencyContact, contact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    db.delete(row)
    db.add(models.AuditLog(action="EMERGENCY_CONTACT_DELETE", user_email=user.email,
                           details=f"#{contact_id} {row.name}"))
    db.commit()


# ---------------------------------------------------------------------------
# SOS - raised on any dashboard, shown on every dashboard
# ---------------------------------------------------------------------------
class SosRaise(BaseModel):
    category: str = Field(min_length=1, max_length=40)
    message: str = Field(min_length=3, max_length=300)
    location: str = Field(default="", max_length=120)


class SosResolve(BaseModel):
    note: str = Field(default="", max_length=300)


@router.get("/sos")
def sos_list(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Active alerts first, then recent resolved ones. Polled by every
    dashboard, so any role sees an SOS within seconds of it being raised."""
    items = sos.list_alerts(db)
    return {"store": sos.store_name(), "active": [a for a in items if a["status"] == "ACTIVE"],
            "recent": [a for a in items if a["status"] != "ACTIVE"][:10], "categories": sos.CATEGORIES}


@router.post("/sos", status_code=201)
def sos_raise(
    body: SosRaise,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    if body.category not in sos.CATEGORIES:
        raise HTTPException(status_code=422, detail=f"Category must be one of: {', '.join(sos.CATEGORIES)}.")
    item = sos.raise_alert(db, user, body.category, body.message.strip(), body.location.strip())
    db.add(models.AuditLog(action="SOS_RAISED", user_email=user.email,
                           details=f"[{body.category}] {body.message[:200]}"))
    db.commit()
    return item


@router.post("/sos/{alert_id}/ack")
def sos_ack(
    alert_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    item = sos.acknowledge(db, alert_id, user)
    if item is None:
        raise HTTPException(status_code=404, detail="SOS not found.")
    db.add(models.AuditLog(action="SOS_ACKNOWLEDGED", user_email=user.email, details=alert_id))
    db.commit()
    return item


@router.post("/sos/{alert_id}/resolve")
def sos_resolve(
    alert_id: str,
    body: SosResolve,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Only an Admin or the officer who raised it can stand an SOS down."""
    current = next((a for a in sos.list_alerts(db) if a["id"] == alert_id), None)
    if current is None:
        raise HTTPException(status_code=404, detail="SOS not found.")
    if user.role != auth.ROLE_ADMIN and current["raised_by"]["email"] != user.email:
        raise HTTPException(status_code=403, detail="Only an Admin or the person who raised this SOS can resolve it.")
    item = sos.resolve(db, alert_id, user, body.note.strip())
    db.add(models.AuditLog(action="SOS_RESOLVED", user_email=user.email,
                           details=f"{alert_id}: {body.note[:200]}"))
    db.commit()
    return item
