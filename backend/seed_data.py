from database import SessionLocal, engine
import models
import auth

# Ensure tables exist
models.Base.metadata.create_all(bind=engine)

def seed_database():
    db = SessionLocal()
    try:
        # Check if users already exist
        if not db.query(models.User).filter(models.User.email == "admin@sail.gov.in").first():
            admin = models.User(
                name="Chief Logistics Officer",
                email="admin@sail.gov.in",
                hashed_password=auth.get_password_hash("12345"),
                role="Admin"
            )
            analyst = models.User(
                name="SAIL Procurement Analyst",
                email="analyst@sail.gov.in",
                hashed_password=auth.get_password_hash("12345"),
                role="Analyst"
            )
            db.add_all([admin, analyst])
            print("Users seeded.")

        # Seed ports if empty
        if db.query(models.Port).count() == 0:
            ports_data = [
                {"name": "Paradip", "code": "INPRT", "draft_m": 14.5, "max_loa": 300.0, "avg_wait_days": 3.2, "mech_rate_mt_d": 45000.0, "rail_evac_km": 380.0},
                {"name": "Dhamra", "code": "INDMA", "draft_m": 18.0, "max_loa": 350.0, "avg_wait_days": 1.5, "mech_rate_mt_d": 60000.0, "rail_evac_km": 420.0},
                {"name": "Haldia", "code": "INHAL", "draft_m": 8.0, "max_loa": 230.0, "avg_wait_days": 4.0, "mech_rate_mt_d": 25000.0, "rail_evac_km": 340.0},
                {"name": "Gangavaram", "code": "INGGV", "draft_m": 19.5, "max_loa": 365.0, "avg_wait_days": 1.2, "mech_rate_mt_d": 65000.0, "rail_evac_km": 540.0},
                {"name": "Vizag", "code": "INVTZ", "draft_m": 16.5, "max_loa": 320.0, "avg_wait_days": 2.5, "mech_rate_mt_d": 40000.0, "rail_evac_km": 560.0}
            ]
            for pd in ports_data:
                db.add(models.Port(**pd))
            print("Ports seeded.")

        # Seed vessels if empty
        if db.query(models.Vessel).count() == 0:
            vessels_data = [
                {"name": "MV Bulk Trader", "class_type": "Panamax", "capacity_mt": 75000, "draft_m": 13.5, "speed_knots": 14.0, "daily_cost_usd": 15000},
                {"name": "MV Ocean Giant", "class_type": "Capesize", "capacity_mt": 170000, "draft_m": 17.5, "speed_knots": 13.5, "daily_cost_usd": 22000},
                {"name": "MV Coastal Star", "class_type": "Supramax", "capacity_mt": 55000, "draft_m": 11.5, "speed_knots": 14.5, "daily_cost_usd": 12000},
                {"name": "MV Bengal Pioneer", "class_type": "Handysize", "capacity_mt": 35000, "draft_m": 9.5, "speed_knots": 13.0, "daily_cost_usd": 9500}
            ]
            for vd in vessels_data:
                db.add(models.Vessel(**vd))
            print("Vessels seeded.")

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
