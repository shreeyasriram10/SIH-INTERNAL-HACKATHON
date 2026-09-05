import os
import shutil
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

db_dir = os.path.dirname(__file__)
default_db_path = os.path.join(db_dir, "lohadrishti.db")

if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    tmp_db_path = "/tmp/lohadrishti.db"
    if os.path.exists(default_db_path) and not os.path.exists(tmp_db_path):
        try:
            shutil.copyfile(default_db_path, tmp_db_path)
        except Exception:
            pass
    DB_PATH = tmp_db_path
else:
    DB_PATH = default_db_path

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
