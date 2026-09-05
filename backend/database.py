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


def ensure_columns(base) -> None:
    """Add columns that exist on the models but not yet in an older SQLite file.

    create_all() only creates missing *tables*, so a database carried over from
    an earlier version keeps its old shape and every query on a new column
    fails. SQLite can only ADD COLUMN, which is all a forward-only schema like
    this one needs.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table in base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                ddl = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type.compile(engine.dialect)}"
                if column.default is not None and column.default.is_scalar:
                    value = column.default.arg
                    literal = f"'{value}'" if isinstance(value, str) else value
                    ddl += f" DEFAULT {literal}"
                connection.execute(text(ddl))
