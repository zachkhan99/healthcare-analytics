"""
airflow/dags/healthcare_pipeline.py
────────────────────────────────────
Daily DAG that runs the full healthcare analytics pipeline:
  1. Generate / refresh raw data (synthetic mode or swap for real source)
  2. Python ETL  → raw schema
  3. dbt run     → staging + marts
  4. dbt test    → data quality validation

Schedule: 06:00 UTC daily
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago

# ── Paths (inside container) ──────────────────────────────────────────────────
PROJECT_ROOT = Path("/opt/airflow")
DATA_DIR     = PROJECT_ROOT / "data"
DBT_DIR      = PROJECT_ROOT / "dbt"

# ── Default args ──────────────────────────────────────────────────────────────
DEFAULT_ARGS = {
    "owner":            "data-team",
    "depends_on_past":  False,
    "email_on_failure": False,
    "email_on_retry":   False,
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
}

# ── Task functions ────────────────────────────────────────────────────────────

def generate_data(**context) -> None:
    """
    In synthetic mode, (re)generate the raw CSVs.
    In production, swap this out for a download / S3 fetch task.
    """
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, str(DATA_DIR / "generate_synthetic_data.py"), "--patients", "10000"],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(f"Data generation failed:\n{result.stderr}")


def run_etl(**context) -> None:
    """Run the Python ETL pipeline."""
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from etl.pipeline import run_pipeline
    result = run_pipeline(save_report=True)
    if result["status"] != "success":
        raise RuntimeError(f"ETL pipeline returned status: {result['status']}")


def check_row_counts(**context) -> None:
    """
    Basic post-load sanity checks.
    Fails if any raw table is empty after the load.
    """
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from etl.db import get_engine
    from sqlalchemy import text

    engine = get_engine(schema="raw")
    tables = ["patients", "admissions", "diagnoses", "icu_stays"]
    with engine.connect() as conn:
        for table in tables:
            count = conn.execute(text(f"SELECT count(*) FROM raw.{table}")).scalar()
            print(f"raw.{table}: {count:,} rows")
            if count == 0:
                raise ValueError(f"raw.{table} is empty after ETL load!")


# ── DAG ───────────────────────────────────────────────────────────────────────

with DAG(
    dag_id="healthcare_analytics_pipeline",
    description="Daily healthcare data pipeline: ingest → ETL → dbt → tests",
    schedule_interval="0 6 * * *",   # 06:00 UTC every day
    start_date=days_ago(1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["healthcare", "etl", "dbt"],
    doc_md="""
## Healthcare Analytics Pipeline

Runs daily at 06:00 UTC.

| Step | Description |
|---|---|
| `generate_raw_data` | Refresh synthetic CSVs (swap for real data in prod) |
| `run_etl` | Python ETL: extract → transform → load to `raw` schema |
| `check_row_counts` | Sanity-check that every raw table is non-empty |
| `dbt_run_staging` | dbt: materialize staging views |
| `dbt_run_marts` | dbt: materialize dimension + fact + analytic tables |
| `dbt_test` | dbt: run all data-quality tests |
    """,
) as dag:

    generate_raw_data = PythonOperator(
        task_id="generate_raw_data",
        python_callable=generate_data,
    )

    etl_task = PythonOperator(
        task_id="run_etl",
        python_callable=run_etl,
    )

    row_count_check = PythonOperator(
        task_id="check_row_counts",
        python_callable=check_row_counts,
    )

    dbt_run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command=(
            f"cd {DBT_DIR} && "
            "dbt run --select staging --profiles-dir . "
            "--vars '{\"readmission_days\": 30}'"
        ),
        env={**os.environ, "DBT_PROFILES_DIR": str(DBT_DIR)},
    )

    dbt_run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=(
            f"cd {DBT_DIR} && "
            "dbt run --select marts analytics --profiles-dir . "
            "--vars '{\"readmission_days\": 30}'"
        ),
        env={**os.environ, "DBT_PROFILES_DIR": str(DBT_DIR)},
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"cd {DBT_DIR} && "
            "dbt test --profiles-dir . "
            "--vars '{\"readmission_days\": 30}'"
        ),
        env={**os.environ, "DBT_PROFILES_DIR": str(DBT_DIR)},
    )

    # ── Dependencies ──────────────────────────────────────────────────────────
    (
        generate_raw_data
        >> etl_task
        >> row_count_check
        >> dbt_run_staging
        >> dbt_run_marts
        >> dbt_test
    )
