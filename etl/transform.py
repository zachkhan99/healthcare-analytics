"""
etl/transform.py
────────────────
Cleans and validates raw DataFrames before they are loaded into Postgres.

Each function:
  - enforces expected dtypes
  - handles missing values
  - applies business-rule validation
  - returns a cleaned DataFrame + a validation report dict
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from loguru import logger


# ── Helpers ───────────────────────────────────────────────────────────────────

def _report(name: str, original: int, after: int, issues: dict) -> dict:
    report = {
        "table":         name,
        "rows_in":       original,
        "rows_out":      after,
        "rows_dropped":  original - after,
        "issues":        issues,
        "run_at":        datetime.utcnow().isoformat(),
    }
    logger.info(
        f"[{name}] in={original:,}  out={after:,}  dropped={original - after:,}  issues={issues}"
    )
    return report


# ── Patients ──────────────────────────────────────────────────────────────────

VALID_GENDERS = {"M", "F"}

def transform_patients(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    original = len(df)
    issues: dict = {}

    # Drop rows without a patient_id
    null_ids = df["patient_id"].isna().sum()
    if null_ids:
        issues["null_patient_id"] = int(null_ids)
    df = df.dropna(subset=["patient_id"])

    # Normalise gender
    df["gender"] = df["gender"].str.strip().str.upper()
    invalid_gender = ~df["gender"].isin(VALID_GENDERS)
    if invalid_gender.any():
        issues["invalid_gender"] = int(invalid_gender.sum())
    df.loc[invalid_gender, "gender"] = "U"  # Unknown

    # Clip DOB to sensible range
    today = pd.Timestamp.today().normalize()
    df["date_of_birth"] = pd.to_datetime(df["date_of_birth"], errors="coerce")
    future_dob = df["date_of_birth"] > today
    if future_dob.any():
        issues["future_dob"] = int(future_dob.sum())
    df.loc[future_dob, "date_of_birth"] = pd.NaT

    # Fill categoricals
    for col in ["ethnicity", "language", "marital_status", "insurance"]:
        null_count = df[col].isna().sum()
        if null_count:
            issues[f"null_{col}"] = int(null_count)
        df[col] = df[col].fillna("UNKNOWN").str.strip().str.upper()

    df = df.drop_duplicates(subset=["patient_id"])
    return df, _report("patients", original, len(df), issues)


# ── Admissions ────────────────────────────────────────────────────────────────

VALID_ADMISSION_TYPES = {
    "EMERGENCY", "ELECTIVE", "URGENT", "NEWBORN", "OBSERVATION ADMIT",
}

def transform_admissions(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    original = len(df)
    issues: dict = {}

    df = df.dropna(subset=["admission_id", "patient_id"])

    # Parse timestamps
    for col in ["admit_time", "discharge_time"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # Drop rows where admit or discharge is null
    null_times = df[["admit_time", "discharge_time"]].isna().any(axis=1)
    issues["null_timestamps"] = int(null_times.sum())
    df = df[~null_times]

    # Discharge must be after admit
    inverted = df["discharge_time"] < df["admit_time"]
    issues["inverted_times"] = int(inverted.sum())
    df = df[~inverted]

    # Compute length of stay in hours
    df["los_hours"] = (df["discharge_time"] - df["admit_time"]).dt.total_seconds() / 3600
    df["los_days"]  = df["los_hours"] / 24

    # Validate admission type
    df["admission_type"] = df["admission_type"].str.strip().str.upper()
    bad_type = ~df["admission_type"].isin(VALID_ADMISSION_TYPES)
    if bad_type.any():
        issues["invalid_admission_type"] = int(bad_type.sum())
    df.loc[bad_type, "admission_type"] = "OTHER"

    # hospital_expire_flag must be 0 or 1
    df["hospital_expire_flag"] = pd.to_numeric(
        df["hospital_expire_flag"], errors="coerce"
    ).fillna(0).astype(int).clip(0, 1)

    df = df.drop_duplicates(subset=["admission_id"])
    return df, _report("admissions", original, len(df), issues)


# ── Diagnoses ─────────────────────────────────────────────────────────────────

def transform_diagnoses(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    original = len(df)
    issues: dict = {}

    df = df.dropna(subset=["admission_id", "icd_code"])

    # ICD version must be 9 or 10
    df["icd_version"] = pd.to_numeric(df["icd_version"], errors="coerce").astype("Int8")
    bad_ver = ~df["icd_version"].isin([9, 10])
    if bad_ver.any():
        issues["invalid_icd_version"] = int(bad_ver.sum())
    df = df[~bad_ver]

    # Normalise ICD code format
    df["icd_code"] = df["icd_code"].str.strip().str.upper()

    # seq_num must be positive
    df["seq_num"] = pd.to_numeric(df["seq_num"], errors="coerce").fillna(1).astype(int)
    df.loc[df["seq_num"] < 1, "seq_num"] = 1

    # Remove duplicates within an admission
    df = df.drop_duplicates(subset=["admission_id", "icd_code", "icd_version"])

    return df, _report("diagnoses", original, len(df), issues)


# ── ICU stays ─────────────────────────────────────────────────────────────────

def transform_icu_stays(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    original = len(df)
    issues: dict = {}

    df = df.dropna(subset=["icustay_id", "admission_id"])

    for col in ["intime", "outtime"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    null_times = df[["intime", "outtime"]].isna().any(axis=1)
    issues["null_timestamps"] = int(null_times.sum())
    df = df[~null_times]

    inverted = df["outtime"] < df["intime"]
    issues["inverted_times"] = int(inverted.sum())
    df = df[~inverted]

    df["icu_los_hours"] = (df["outtime"] - df["intime"]).dt.total_seconds() / 3600

    df = df.drop_duplicates(subset=["icustay_id"])
    return df, _report("icu_stays", original, len(df), issues)


# ── ICD reference ─────────────────────────────────────────────────────────────

def transform_icd_reference(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    original = len(df)
    df = df.dropna(subset=["icd_code", "icd_version"])
    df["icd_code"] = df["icd_code"].str.strip().str.upper()
    df = df.drop_duplicates(subset=["icd_code", "icd_version"])
    return df, _report("icd_codes", original, len(df), {})
