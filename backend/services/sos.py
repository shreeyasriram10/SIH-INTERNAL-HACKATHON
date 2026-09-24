"""SOS: an emergency raised on one dashboard, seen on every dashboard.

An SOS is shared state, so it cannot live in one browser. Two stores sit
behind the same functions:

  REDIS  when UPSTASH_REDIS_REST_URL / _TOKEN (or Vercel's KV_REST_API_URL /
         _TOKEN) are set. Serverless containers do not share a filesystem,
         so on Vercel this is what guarantees that an SOS raised through one
         container is seen through every other.
  DB     otherwise - the platform's own database. Correct for a single
         server (local, one container); on serverless each container has its
         own SQLite copy, which is why the status endpoint reports the store.

Alerts are small and rare, so the Redis store keeps the whole list under one
key rather than modelling it field by field.
"""

import json
import os
import urllib.request
import uuid
from datetime import datetime, timezone

import models

CATEGORIES = ("Vessel incident", "Port closure", "Cargo emergency", "Medical", "Security", "Weather", "Other")
KEY = "loha:sos"
KEEP_RESOLVED = 20


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _redis_config():
    url = os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN")
    return (url.rstrip("/"), token) if url and token else None


def store_name() -> str:
    return "redis" if _redis_config() else "database"


# ---------------------------------------------------------------- redis store
def _redis(command: list):
    url, token = _redis_config()
    req = urllib.request.Request(url, data=json.dumps(command).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode()).get("result")


def _redis_load() -> list:
    raw = _redis(["GET", KEY])
    return json.loads(raw) if raw else []


def _redis_save(items: list) -> None:
    _redis(["SET", KEY, json.dumps(items)])


# ------------------------------------------------------------------- db store
def _row_to_dict(row) -> dict:
    return {"id": row.uid, "category": row.category, "message": row.message, "location": row.location,
            "status": row.status, "raised_by": {"email": row.raised_by_email, "name": row.raised_by_name,
                                                 "role": row.raised_by_role},
            "raised_at": row.raised_at, "acks": json.loads(row.acks or "[]"),
            "resolved_by": json.loads(row.resolved_by) if row.resolved_by else None, "resolved_at": row.resolved_at or None,
            "resolution": row.resolution or ""}


def _db_load(db) -> list:
    rows = db.query(models.SosAlert).order_by(models.SosAlert.id.desc()).limit(KEEP_RESOLVED + 20).all()
    return [_row_to_dict(r) for r in rows]


# --------------------------------------------------------------------- facade
def list_alerts(db) -> list:
    items = _redis_load() if _redis_config() else _db_load(db)
    newest_first = sorted(items, key=lambda a: a["raised_at"], reverse=True)
    return sorted(newest_first, key=lambda a: a["status"] != "ACTIVE")   # stable: active on top


def raise_alert(db, user, category: str, message: str, location: str) -> dict:
    item = {"id": uuid.uuid4().hex[:12], "category": category, "message": message, "location": location,
            "status": "ACTIVE", "raised_by": {"email": user.email, "name": user.name, "role": user.role},
            "raised_at": _now(), "acks": [], "resolved_by": None, "resolved_at": None, "resolution": ""}
    if _redis_config():
        items = _redis_load()
        resolved = [a for a in items if a["status"] != "ACTIVE"][:KEEP_RESOLVED]
        _redis_save([item] + [a for a in items if a["status"] == "ACTIVE"] + resolved)
    else:
        db.add(models.SosAlert(uid=item["id"], category=category, message=message, location=location,
                               status="ACTIVE", raised_by_email=user.email, raised_by_name=user.name,
                               raised_by_role=user.role, raised_at=item["raised_at"], acks="[]"))
        db.commit()
    return item


def _update(db, alert_id: str, change) -> dict | None:
    if _redis_config():
        items = _redis_load()
        target = next((a for a in items if a["id"] == alert_id), None)
        if target is None:
            return None
        change(target)
        _redis_save(items)
        return target
    row = db.query(models.SosAlert).filter(models.SosAlert.uid == alert_id).first()
    if row is None:
        return None
    item = _row_to_dict(row)
    change(item)
    row.status, row.acks = item["status"], json.dumps(item["acks"])
    row.resolved_by = json.dumps(item["resolved_by"]) if item["resolved_by"] else ""
    row.resolved_at, row.resolution = item["resolved_at"] or "", item["resolution"]
    db.commit()
    return item


def acknowledge(db, alert_id: str, user) -> dict | None:
    def change(a):
        if not any(k["email"] == user.email for k in a["acks"]):
            a["acks"].append({"email": user.email, "name": user.name, "role": user.role, "at": _now()})
    return _update(db, alert_id, change)


def resolve(db, alert_id: str, user, note: str) -> dict | None:
    def change(a):
        a["status"] = "RESOLVED"
        a["resolved_by"] = {"email": user.email, "name": user.name, "role": user.role}
        a["resolved_at"] = _now()
        a["resolution"] = note
    return _update(db, alert_id, change)
