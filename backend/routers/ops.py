from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import get_db
from routers.decision import _reference_data
from services import alerts

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
