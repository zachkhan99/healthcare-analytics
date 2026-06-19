"""
etl/db.py
─────────
Database connection utilities shared across the ETL package.
Reads credentials from environment / .env file.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Load .env from project root (two levels up from this file)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def get_engine(schema: str = "raw") -> Engine:
    """Return a SQLAlchemy engine pointed at the healthcare warehouse."""
    host     = os.getenv("APP_DB_HOST", "localhost")
    port     = os.getenv("APP_DB_PORT", "5432")
    dbname   = os.getenv("APP_DB_NAME", "healthcare")
    user     = os.getenv("APP_DB_USER", "analytics")
    password = os.getenv("APP_DB_PASSWORD", "analytics")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
    engine = create_engine(
        url,
        connect_args={"options": f"-csearch_path={schema},public"},
        pool_pre_ping=True,
    )
    return engine


def test_connection() -> bool:
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        print(f"Connection failed: {exc}")
        return False
