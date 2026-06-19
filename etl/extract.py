"""
etl/extract.py
──────────────
Reads raw CSVs from data/raw/ (generated locally or downloaded from a
real source such as MIMIC-IV / CMS / Kaggle) and returns DataFrames.

The function signatures stay the same regardless of data source, so
swapping in real data only requires placing new files in data/raw/.
"""

from pathlib import Path

import pandas as pd
from loguru import logger

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

_DTYPE_PATIENTS = {
    "patient_id":     str,
    "gender":         str,
    "ethnicity":      str,
    "language":       str,
    "marital_status": str,
    "insurance":      str,
}

_DTYPE_ADMISSIONS = {
    "admission_id":           str,
    "patient_id":             str,
    "admission_type":         str,
    "admission_location":     str,
    "discharge_location":     str,
    "insurance":              str,
    "primary_diagnosis_text": str,
    "hospital_expire_flag":   "Int8",
}

_DTYPE_DIAGNOSES = {
    "diagnosis_id": "Int64",
    "admission_id": str,
    "patient_id":   str,
    "icd_code":     str,
    "icd_version":  "Int8",
    "seq_num":      "Int8",
}

_DTYPE_ICU = {
    "icustay_id":     str,
    "admission_id":   str,
    "patient_id":     str,
    "first_careunit": str,
    "last_careunit":  str,
}

_DTYPE_ICD_REF = {
    "icd_code":    str,
    "icd_version": "Int8",
    "long_title":  str,
    "short_title": str,
    "category":    str,
}


def _read_csv(filename: str, dtypes: dict, parse_dates: list | None = None) -> pd.DataFrame:
    path = RAW_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Raw file not found: {path}\n"
            "Run `python data/generate_synthetic_data.py` to create sample data."
        )
    df = pd.read_csv(path, dtype=dtypes, parse_dates=parse_dates or [])
    logger.info(f"Extracted {len(df):,} rows from {filename}")
    return df


def extract_patients() -> pd.DataFrame:
    return _read_csv("patients.csv", _DTYPE_PATIENTS, parse_dates=["date_of_birth"])


def extract_admissions() -> pd.DataFrame:
    return _read_csv(
        "admissions.csv",
        _DTYPE_ADMISSIONS,
        parse_dates=["admit_time", "discharge_time", "death_time"],
    )


def extract_diagnoses() -> pd.DataFrame:
    return _read_csv("diagnoses.csv", _DTYPE_DIAGNOSES)


def extract_icu_stays() -> pd.DataFrame:
    return _read_csv(
        "icu_stays.csv",
        _DTYPE_ICU,
        parse_dates=["intime", "outtime"],
    )


def extract_icd_reference() -> pd.DataFrame:
    return _read_csv("icd_codes.csv", _DTYPE_ICD_REF)
