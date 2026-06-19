"""
etl/pipeline.py
───────────────
Orchestrates the full Extract → Transform → Load cycle.
Can be called directly (`python -m etl.pipeline`) or imported by Airflow.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from loguru import logger

from etl.db import get_engine
from etl.extract import (
    extract_admissions,
    extract_diagnoses,
    extract_icd_reference,
    extract_icu_stays,
    extract_patients,
)
from etl.load import (
    load_admissions,
    load_diagnoses,
    load_icd_reference,
    load_icu_stays,
    load_patients,
)
from etl.transform import (
    transform_admissions,
    transform_diagnoses,
    transform_icd_reference,
    transform_icu_stays,
    transform_patients,
)

REPORT_DIR = Path(__file__).resolve().parents[1] / "data" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def run_pipeline(save_report: bool = True) -> dict:
    """
    Run the full ETL pipeline.
    Returns a summary report dict.
    """
    logger.info("═" * 60)
    logger.info("Healthcare ETL pipeline starting …")
    engine = get_engine(schema="raw")
    reports = []

    steps = [
        ("patients",   extract_patients,     transform_patients,     load_patients),
        ("admissions", extract_admissions,   transform_admissions,   load_admissions),
        ("diagnoses",  extract_diagnoses,    transform_diagnoses,    load_diagnoses),
        ("icu_stays",  extract_icu_stays,    transform_icu_stays,    load_icu_stays),
        ("icd_codes",  extract_icd_reference, transform_icd_reference, load_icd_reference),
    ]

    for name, extract_fn, transform_fn, load_fn in steps:
        logger.info(f"── {name} ──")
        raw_df = extract_fn()
        clean_df, report = transform_fn(raw_df)
        rows_loaded = load_fn(clean_df, engine)
        report["rows_loaded"] = rows_loaded
        reports.append(report)

    summary = {"status": "success", "tables": reports}

    if save_report:
        import datetime
        ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        report_path = REPORT_DIR / f"etl_report_{ts}.json"
        report_path.write_text(json.dumps(summary, indent=2, default=str))
        logger.info(f"Report saved → {report_path}")

    logger.info("Pipeline complete ✓")
    logger.info("═" * 60)
    return summary


if __name__ == "__main__":
    result = run_pipeline()
    failed = [t for t in result["tables"] if t.get("rows_dropped", 0) > t.get("rows_out", 0) * 0.1]
    sys.exit(1 if failed else 0)
