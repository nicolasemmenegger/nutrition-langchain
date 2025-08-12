from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .models import Base
from ..config import settings
import os

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    os.makedirs(settings.uploads_dir, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    # lightweight, dev-time schema evolution for SQLite: add missing columns
    try:
        with engine.connect() as conn:
            cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(food_logs)").fetchall()]
            if "meal_type" not in cols:
                conn.exec_driver_sql("ALTER TABLE food_logs ADD COLUMN meal_type VARCHAR(50) DEFAULT 'unspecified'")
    except Exception:
        # ignore if not sqlite or table doesn't exist yet
        pass
