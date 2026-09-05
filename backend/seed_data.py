import os

from database import SessionLocal, engine
import models
import auth

# Ensure tables exist
models.Base.metadata.create_all(bind=engine)

def seed_database():
    db = SessionLocal()
    try:
        # Seed the demo accounts. Each is an ordinary user row with a real
        # bcrypt hash - there is no bypass path in auth.verify_password.
        #
        # A previously shipped database carried demo rows whose stored hash did
        # not correspond to the documented password (sign-in used to succeed
        # only via a bypass branch), and whose role column held the person's
        # name instead of a role. Repair both here so the credentials printed in
        # the README actually authenticate. Guarded by an env flag and scoped to
        # the three known demo addresses, so it can never touch a real account.
        repair = os.environ.get("LOHA_REPAIR_DEMO_ACCOUNTS", "1") != "0"

        for email, (name, role) in auth.DEMO_ACCOUNTS.items():
            existing = db.query(models.User).filter(models.User.email == email).first()

            if existing is None:
                db.add(models.User(
                    name=name,
                    email=email,
                    hashed_password=auth.get_password_hash(auth.DEMO_PASSWORD),
                    role=role,
                ))
                print(f"Seeded user {email} ({role}).")
                continue

            if not repair:
                continue

            if not auth.verify_password(auth.DEMO_PASSWORD, existing.hashed_password):
                existing.hashed_password = auth.get_password_hash(auth.DEMO_PASSWORD)
                print(f"Repaired password hash for demo account {email}.")

            if existing.role != role:
                print(f"Corrected role for {email}: {existing.role!r} -> {role!r}.")
                existing.role = role

            if existing.name != name:
                existing.name = name

        # Ports: one authoritative dataset. The dashboard used to carry its own
        # copy of these figures that disagreed with the database (Paradip was
        # 14.5 m here and 18.1 m there); the UI now reads them from /api/ports.
        ports_data = [
            {"name": "Paradip", "code": "INPRT", "draft_m": 18.1, "max_loa": 290.0, "max_beam_m": 45.0,
             "berths": 4, "avg_wait_days": 2.8, "mech_rate_mt_d": 38000.0, "rail_evac_km": 210.0,
             "demurrage_usd_day": 9500.0, "monsoon_months": "6,7,8,9"},
            {"name": "Dhamra", "code": "INDHM", "draft_m": 18.5, "max_loa": 300.0, "max_beam_m": 48.0,
             "berths": 3, "avg_wait_days": 1.6, "mech_rate_mt_d": 42000.0, "rail_evac_km": 245.0,
             "demurrage_usd_day": 9800.0, "monsoon_months": "6,7,8"},
            {"name": "Gangavaram", "code": "INGGV", "draft_m": 18.9, "max_loa": 300.0, "max_beam_m": 48.0,
             "berths": 2, "avg_wait_days": 2.1, "mech_rate_mt_d": 40000.0, "rail_evac_km": 410.0,
             "demurrage_usd_day": 10200.0, "monsoon_months": "6,7,8,9"},
            {"name": "Visakhapatnam", "code": "INVTZ", "draft_m": 17.0, "max_loa": 270.0, "max_beam_m": 43.0,
             "berths": 5, "avg_wait_days": 3.4, "mech_rate_mt_d": 30000.0, "rail_evac_km": 380.0,
             "demurrage_usd_day": 9200.0, "monsoon_months": "6,7,8,9,10"},
            {"name": "Gopalpur", "code": "INGOP", "draft_m": 15.0, "max_loa": 230.0, "max_beam_m": 36.0,
             "berths": 1, "avg_wait_days": 1.2, "mech_rate_mt_d": 18000.0, "rail_evac_km": 520.0,
             "demurrage_usd_day": 8000.0, "monsoon_months": "6,7,8"},
            {"name": "Haldia", "code": "INHAL", "draft_m": 8.5, "max_loa": 180.0, "max_beam_m": 28.0,
             "berths": 2, "avg_wait_days": 4.6, "mech_rate_mt_d": 9000.0, "rail_evac_km": 60.0,
             "demurrage_usd_day": 7500.0, "monsoon_months": "6,7,8,9"},
            {"name": "Sagar/Sandheads", "code": "INSAG", "draft_m": 12.0, "max_loa": 200.0, "max_beam_m": 32.0,
             "berths": 1, "avg_wait_days": 5.2, "mech_rate_mt_d": 12000.0, "rail_evac_km": 130.0,
             "demurrage_usd_day": 7800.0, "monsoon_months": "6,7,8,9"},
        ]
        # Drop rows an older seed created under a different code/name before
        # upserting, so the unique constraints on name and code cannot collide.
        canonical_codes = {row["code"] for row in ports_data}
        canonical_names = {row["name"] for row in ports_data}
        for port in db.query(models.Port).all():
            if port.code not in canonical_codes and port.name not in canonical_names:
                db.delete(port)
        db.flush()

        for row in ports_data:
            port = (
                db.query(models.Port).filter(models.Port.code == row["code"]).first()
                or db.query(models.Port).filter(models.Port.name == row["name"]).first()
            )
            if port is None:
                db.add(models.Port(**row))
            else:
                # Refresh in place so an older database picks up corrected figures.
                for field, value in row.items():
                    setattr(port, field, value)
            db.flush()

        # Vessel classes, matching the dashboard's fleet definitions.
        vessels_data = [
            {"name": "MV Bengal Pioneer", "class_type": "Handysize", "capacity_mt": 40000,
             "draft_m": 10.0, "speed_knots": 13.0, "daily_cost_usd": 9500},
            {"name": "MV Coastal Star", "class_type": "Supramax", "capacity_mt": 60000,
             "draft_m": 12.6, "speed_knots": 14.5, "daily_cost_usd": 12000},
            {"name": "MV Bulk Trader", "class_type": "Panamax", "capacity_mt": 80000,
             "draft_m": 14.2, "speed_knots": 14.0, "daily_cost_usd": 15000},
            {"name": "MV Ocean Giant", "class_type": "Capesize", "capacity_mt": 180000,
             "draft_m": 18.0, "speed_knots": 13.5, "daily_cost_usd": 22000},
        ]
        for row in vessels_data:
            vessel = db.query(models.Vessel).filter(
                models.Vessel.class_type == row["class_type"]
            ).first()
            if vessel is None:
                db.add(models.Vessel(**row))
            else:
                for field, value in row.items():
                    setattr(vessel, field, value)

        # Seed initial audit log
        if db.query(models.AuditLog).count() == 0:
            db.add(models.AuditLog(
                action="SYSTEM_INIT",
                user_email="system@sail.gov.in",
                details="LOHA-DRISHTI Database initialized with ports, vessels, and roles"
            ))

        db.commit()
        print("Database verification & seeding completed.")
    except Exception as e:
        print(f"Error during seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
