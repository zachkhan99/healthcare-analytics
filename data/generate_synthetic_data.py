"""
generate_synthetic_data.py
──────────────────────────
Produces realistic synthetic hospital data that mirrors the MIMIC-IV schema.
Writes four CSVs to data/raw/:
    patients.csv   admissions.csv   diagnoses.csv   icu_stays.csv

Usage:
    python data/generate_synthetic_data.py              # default 5 000 patients
    python data/generate_synthetic_data.py --patients 20000
"""

import argparse
import random
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker()
fake.seed_instance(SEED)

OUT_DIR = Path(__file__).parent / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Reference data ────────────────────────────────────────────────────────────

GENDERS = ["M", "F"]
GENDER_WEIGHTS = [0.48, 0.52]

ETHNICITIES = [
    "WHITE", "BLACK/AFRICAN AMERICAN", "HISPANIC/LATINO", "ASIAN",
    "AMERICAN INDIAN/ALASKA NATIVE", "OTHER", "UNKNOWN",
]
ETHNICITY_WEIGHTS = [0.55, 0.18, 0.12, 0.07, 0.01, 0.04, 0.03]

LANGUAGES = ["ENGLISH", "SPANISH", "PORTUGUESE", "CHINESE", "OTHER"]
LANGUAGE_WEIGHTS = [0.75, 0.10, 0.04, 0.03, 0.08]

MARITAL = ["SINGLE", "MARRIED", "DIVORCED", "WIDOWED", "UNKNOWN"]
MARITAL_WEIGHTS = [0.35, 0.40, 0.12, 0.08, 0.05]

INSURANCE = ["Medicare", "Medicaid", "Private", "Self Pay", "Government"]
INSURANCE_WEIGHTS = [0.38, 0.22, 0.28, 0.07, 0.05]

ADMISSION_TYPES = ["EMERGENCY", "ELECTIVE", "URGENT", "NEWBORN", "OBSERVATION ADMIT"]
ADMISSION_TYPE_WEIGHTS = [0.55, 0.25, 0.12, 0.04, 0.04]

ADMISSION_LOCATIONS = [
    "EMERGENCY ROOM", "PHYSICIAN REFERRAL", "TRANSFER FROM HOSPITAL",
    "CLINIC REFERRAL", "WALK-IN/SELF REFERRAL",
]
DISCHARGE_LOCATIONS = [
    "HOME", "HOME HEALTH CARE", "SKILLED NURSING FACILITY",
    "REHAB / DISTINCT PART HOSP", "DIED", "HOSPICE",
    "SHORT TERM HOSPITAL", "AGAINST ADVICE",
]

CARE_UNITS = ["MICU", "SICU", "CCU", "CSRU", "NICU", "TSICU"]

# Simplified ICD-10 codes with categories
ICD_CODES = [
    # Cardiovascular
    ("I10",   10, "Essential (primary) hypertension",                    "Hypertension",      "Cardiovascular"),
    ("I21.9", 10, "Acute myocardial infarction, unspecified",            "Acute MI",          "Cardiovascular"),
    ("I50.9", 10, "Heart failure, unspecified",                          "Heart failure",     "Cardiovascular"),
    ("I48.91",10, "Unspecified atrial fibrillation",                     "Atrial fibrillation","Cardiovascular"),
    ("I63.9", 10, "Cerebral infarction, unspecified",                    "Stroke",            "Cardiovascular"),
    # Respiratory
    ("J18.9", 10, "Pneumonia, unspecified organism",                     "Pneumonia",         "Respiratory"),
    ("J44.1", 10, "Chronic obstructive pulmonary disease with exacerbation","COPD exacerbation","Respiratory"),
    ("J96.00",10, "Acute respiratory failure, unspecified",              "Resp failure",      "Respiratory"),
    # Endocrine
    ("E11.9", 10, "Type 2 diabetes mellitus without complications",      "T2DM",              "Endocrine"),
    ("E11.65",10, "Type 2 diabetes mellitus with hyperglycemia",         "T2DM hyperglycemia","Endocrine"),
    ("E87.1", 10, "Hypo-osmolality and hyponatremia",                   "Hyponatremia",      "Endocrine"),
    # Renal
    ("N17.9", 10, "Acute kidney failure, unspecified",                   "AKI",               "Renal"),
    ("N18.9", 10, "Chronic kidney disease, unspecified",                 "CKD",               "Renal"),
    ("N39.0", 10, "Urinary tract infection, site not specified",         "UTI",               "Renal"),
    # Gastrointestinal
    ("K92.1", 10, "Melena",                                              "GI bleed",          "Gastrointestinal"),
    ("K72.90",10, "Hepatic failure, unspecified without coma",           "Liver failure",     "Gastrointestinal"),
    ("K80.20",10, "Calculus of gallbladder without cholecystitis",       "Cholelithiasis",    "Gastrointestinal"),
    # Infectious
    ("A41.9", 10, "Sepsis, unspecified organism",                        "Sepsis",            "Infectious"),
    ("B97.89",10, "Other viral agents as cause of diseases",             "Viral infection",   "Infectious"),
    # Neurological
    ("G93.1", 10, "Anoxic brain damage, not elsewhere classified",       "Anoxic brain damage","Neurological"),
    ("G40.909",10,"Epilepsy, unspecified, not intractable",              "Epilepsy",          "Neurological"),
]
ICD_WEIGHTS = [
    0.09, 0.07, 0.07, 0.05, 0.04,   # cardiovascular
    0.07, 0.05, 0.04,                # respiratory
    0.08, 0.04, 0.02,                # endocrine
    0.06, 0.04, 0.03,                # renal
    0.04, 0.03, 0.02,                # GI
    0.09, 0.02,                      # infectious
    0.02, 0.02,                      # neurological
]


def weighted_choice(population, weights, size=1):
    indices = np.random.choice(len(population), size=size, p=weights)
    return [population[i] for i in indices]


# ── Generators ────────────────────────────────────────────────────────────────

def generate_patients(n: int) -> pd.DataFrame:
    print(f"  Generating {n:,} patients …")
    rows = []
    for i in range(n):
        dob = fake.date_of_birth(minimum_age=18, maximum_age=95)
        rows.append({
            "patient_id":     f"P{i+1:07d}",
            "gender":         weighted_choice(GENDERS, GENDER_WEIGHTS)[0],
            "date_of_birth":  dob,
            "ethnicity":      weighted_choice(ETHNICITIES, ETHNICITY_WEIGHTS)[0],
            "language":       weighted_choice(LANGUAGES, LANGUAGE_WEIGHTS)[0],
            "marital_status": weighted_choice(MARITAL, MARITAL_WEIGHTS)[0],
            "insurance":      weighted_choice(INSURANCE, INSURANCE_WEIGHTS)[0],
        })
    return pd.DataFrame(rows)


def generate_admissions(patients: pd.DataFrame) -> pd.DataFrame:
    print("  Generating admissions …")
    rows = []
    adm_id = 1

    for _, pat in patients.iterrows():
        # Each patient has 1–5 admissions
        n_admits = np.random.choice([1, 2, 3, 4, 5], p=[0.50, 0.25, 0.13, 0.08, 0.04])
        admit_time = fake.date_time_between(start_date="-5y", end_date="-1d")

        for _ in range(n_admits):
            adm_type  = weighted_choice(ADMISSION_TYPES, ADMISSION_TYPE_WEIGHTS)[0]
            los_days  = max(0.5, np.random.exponential(scale=5.5))    # length of stay
            discharge = admit_time + timedelta(days=los_days)

            # In-hospital mortality ~4 %
            expire = 1 if random.random() < 0.04 else 0
            death_time = discharge if expire else None

            ins = pat["insurance"]
            rows.append({
                "admission_id":           f"A{adm_id:08d}",
                "patient_id":             pat["patient_id"],
                "admit_time":             admit_time,
                "discharge_time":         discharge,
                "death_time":             death_time,
                "admission_type":         adm_type,
                "admission_location":     random.choice(ADMISSION_LOCATIONS),
                "discharge_location":     "DIED" if expire else random.choice(DISCHARGE_LOCATIONS[:-1]),
                "insurance":              ins,
                "primary_diagnosis_text": fake.sentence(nb_words=6),
                "hospital_expire_flag":   expire,
            })
            adm_id += 1
            # Next admission starts 30–730 days after previous discharge
            gap = timedelta(days=random.randint(30, 730))
            admit_time = discharge + gap

    return pd.DataFrame(rows)


def generate_diagnoses(admissions: pd.DataFrame) -> pd.DataFrame:
    print("  Generating diagnoses …")
    rows = []
    diag_id = 1

    icd_list    = [(c[0], c[1]) for c in ICD_CODES]
    icd_weights = np.array(ICD_WEIGHTS) / sum(ICD_WEIGHTS)

    for _, adm in admissions.iterrows():
        n_diags = np.random.choice([1, 2, 3, 4, 5, 6], p=[0.20, 0.25, 0.22, 0.17, 0.10, 0.06])
        chosen = weighted_choice(icd_list, icd_weights.tolist(), size=n_diags)
        seen   = set()
        seq    = 1
        for code, ver in chosen:
            if code in seen:
                continue
            seen.add(code)
            rows.append({
                "diagnosis_id": diag_id,
                "admission_id": adm["admission_id"],
                "patient_id":   adm["patient_id"],
                "icd_code":     code,
                "icd_version":  ver,
                "seq_num":      seq,
            })
            diag_id += 1
            seq += 1

    return pd.DataFrame(rows)


def generate_icu_stays(admissions: pd.DataFrame) -> pd.DataFrame:
    print("  Generating ICU stays …")
    rows = []
    icu_id = 1

    # ~30 % of admissions have an ICU stay
    icu_admissions = admissions[admissions["hospital_expire_flag"] == 1].copy()
    other = admissions[admissions["hospital_expire_flag"] == 0].sample(frac=0.25, random_state=SEED)
    icu_admissions = pd.concat([icu_admissions, other])

    for _, adm in icu_admissions.iterrows():
        admit_ts    = pd.to_datetime(adm["admit_time"])
        discharge_ts = pd.to_datetime(adm["discharge_time"])
        total_hours  = max(1, (discharge_ts - admit_ts).total_seconds() / 3600)
        icu_start_offset = random.uniform(0, total_hours * 0.3)
        icu_hours        = min(random.expovariate(1 / 72), total_hours - icu_start_offset)
        icu_hours        = max(1, icu_hours)
        intime  = admit_ts + timedelta(hours=icu_start_offset)
        outtime = intime  + timedelta(hours=icu_hours)

        unit = random.choice(CARE_UNITS)
        rows.append({
            "icustay_id":     f"ICU{icu_id:08d}",
            "admission_id":   adm["admission_id"],
            "patient_id":     adm["patient_id"],
            "intime":         intime,
            "outtime":        min(outtime, discharge_ts),
            "first_careunit": unit,
            "last_careunit":  random.choice(CARE_UNITS) if random.random() > 0.7 else unit,
        })
        icu_id += 1

    return pd.DataFrame(rows)


def generate_icd_reference() -> pd.DataFrame:
    return pd.DataFrame(ICD_CODES, columns=["icd_code", "icd_version", "long_title", "short_title", "category"])


# ── Main ──────────────────────────────────────────────────────────────────────

def main(n_patients: int):
    print(f"\nGenerating synthetic healthcare data ({n_patients:,} patients) …\n")

    patients   = generate_patients(n_patients)
    admissions = generate_admissions(patients)
    diagnoses  = generate_diagnoses(admissions)
    icu_stays  = generate_icu_stays(admissions)
    icd_ref    = generate_icd_reference()

    patients.to_csv(OUT_DIR / "patients.csv",     index=False)
    admissions.to_csv(OUT_DIR / "admissions.csv", index=False)
    diagnoses.to_csv(OUT_DIR / "diagnoses.csv",   index=False)
    icu_stays.to_csv(OUT_DIR / "icu_stays.csv",   index=False)
    icd_ref.to_csv(OUT_DIR / "icd_codes.csv",     index=False)

    print(f"\n✓ Wrote to {OUT_DIR}/")
    print(f"  patients.csv   → {len(patients):>8,} rows")
    print(f"  admissions.csv → {len(admissions):>8,} rows")
    print(f"  diagnoses.csv  → {len(diagnoses):>8,} rows")
    print(f"  icu_stays.csv  → {len(icu_stays):>8,} rows")
    print(f"  icd_codes.csv  → {len(icd_ref):>8,} rows")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic hospital data")
    parser.add_argument("--patients", type=int, default=5_000,
                        help="Number of patients to generate (default: 5000)")
    args = parser.parse_args()
    main(args.patients)
