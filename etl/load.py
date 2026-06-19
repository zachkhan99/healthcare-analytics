"""
etl/load.py
───────────
Loads cleaned DataFrames into PostgreSQL raw schema using upsert semantics
so the pipeline is safely re-runnable (idempotent).
"""

from __future__ import annotations

import pandas as pd
from loguru import logger
from sqlalchemy import text
from sqlalchemy.engine import Engine


# ── Generic upsert helper ─────────────────────────────────────────────────────

def upsert(
    df: pd.DataFrame,
    table: str,
    schema: str,
    conflict_cols: list[str],
    engine: Engine,
    chunksize: int = 5_000,
) -> int:
    """
    Upsert a DataFrame into `schema.table`.
    Uses a temp table + INSERT ... ON CONFLICT DO UPDATE pattern so it works
    cleanly with Postgres 15 and SQLAlchemy 2.x.
    """
    if df.empty:
        logger.warning(f"load.upsert: empty DataFrame for {schema}.{table}, skipping")
        return 0

    total_loaded = 0
    tmp_table = f"_tmp_{table}"
    non_conflict = [c for c in df.columns if c not in conflict_cols]
    update_set   = ", ".join(f"{c} = EXCLUDED.{c}" for c in non_conflict) if non_conflict else None

    with engine.begin() as conn:
        # Recreate temp table each run
        conn.execute(text(f"DROP TABLE IF EXISTS {tmp_table}"))
        conn.execute(
            text(
                f"CREATE TEMP TABLE {tmp_table} "
                f"(LIKE {schema}.{table} INCLUDING ALL) ON COMMIT DROP"
            )
        )

        # Bulk load into temp table in chunks
        for chunk_start in range(0, len(df), chunksize):
            chunk = df.iloc[chunk_start : chunk_start + chunksize]
            chunk.to_sql(
                tmp_table,
                conn,
                if_exists="append",
                index=False,
                method="multi",
            )
            total_loaded += len(chunk)

        # Merge into target
        conflict_clause = ", ".join(conflict_cols)
        if update_set:
            merge_sql = (
                f"INSERT INTO {schema}.{table} "
                f"SELECT * FROM {tmp_table} "
                f"ON CONFLICT ({conflict_clause}) DO UPDATE SET {update_set}"
            )
        else:
            merge_sql = (
                f"INSERT INTO {schema}.{table} "
                f"SELECT * FROM {tmp_table} "
                f"ON CONFLICT ({conflict_clause}) DO NOTHING"
            )
        conn.execute(text(merge_sql))

    logger.info(f"Upserted {total_loaded:,} rows → {schema}.{table}")
    return total_loaded


# ── Table-specific loaders ────────────────────────────────────────────────────

def load_patients(df: pd.DataFrame, engine: Engine) -> int:
    # Add _loaded_at if not present
    df = df.copy()
    if "_loaded_at" in df.columns:
        df = df.drop(columns=["_loaded_at"])
    return upsert(df, "patients", "raw", ["patient_id"], engine)


def load_admissions(df: pd.DataFrame, engine: Engine) -> int:
    df = df.copy()
    # Drop derived columns computed in transform — not part of raw schema
    derived = ["_loaded_at", "los_hours", "los_days",
               "admit_year", "admit_quarter", "admit_month", "admit_dow"]
    df = df.drop(columns=[c for c in derived if c in df.columns])
    return upsert(df, "admissions", "raw", ["admission_id"], engine)


def load_diagnoses(df: pd.DataFrame, engine: Engine) -> int:
    df = df.copy()
    if "_loaded_at" in df.columns:
        df = df.drop(columns=["_loaded_at"])
    # Drop generated diagnosis_id – Postgres auto-assigns via BIGSERIAL
    if "diagnosis_id" in df.columns:
        df = df.drop(columns=["diagnosis_id"])
    return upsert(
        df, "diagnoses", "raw",
        ["admission_id", "icd_code", "icd_version"],
        engine,
    )


def load_icu_stays(df: pd.DataFrame, engine: Engine) -> int:
    df = df.copy()
    derived = ["_loaded_at", "icu_los_hours"]
    df = df.drop(columns=[c for c in derived if c in df.columns])
    return upsert(df, "icu_stays", "raw", ["icustay_id"], engine)


def load_icd_reference(df: pd.DataFrame, engine: Engine) -> int:
    df = df.copy()
    if "_loaded_at" in df.columns:
        df = df.drop(columns=["_loaded_at"])
    return upsert(df, "icd_codes", "raw", ["icd_code", "icd_version"], engine)
