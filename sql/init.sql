-- =============================================================================
-- Healthcare Analytics Warehouse – Raw Schema
-- Mirrors the structure of MIMIC-IV / CMS / synthetic datasets.
-- Run once on first startup via docker-entrypoint-initdb.d.
-- =============================================================================

-- ── Schemas ───────────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS raw;       -- landing zone for ingested CSVs
CREATE SCHEMA IF NOT EXISTS staging;   -- lightly cleaned by dbt
CREATE SCHEMA IF NOT EXISTS marts;     -- analytics-ready dimensional models

-- ── raw.patients ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.patients (
    patient_id      VARCHAR(20)  PRIMARY KEY,
    gender          CHAR(1),
    date_of_birth   DATE,
    ethnicity       VARCHAR(80),
    language        VARCHAR(40),
    marital_status  VARCHAR(40),
    insurance       VARCHAR(40),
    _loaded_at      TIMESTAMPTZ  DEFAULT NOW()
);

-- ── raw.admissions ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.admissions (
    admission_id            VARCHAR(20)  PRIMARY KEY,
    patient_id              VARCHAR(20),
    admit_time              TIMESTAMPTZ,
    discharge_time          TIMESTAMPTZ,
    death_time              TIMESTAMPTZ,
    admission_type          VARCHAR(50),
    admission_location      VARCHAR(80),
    discharge_location      VARCHAR(80),
    insurance               VARCHAR(40),
    primary_diagnosis_text  TEXT,
    hospital_expire_flag    SMALLINT,   -- 1 = died in hospital
    _loaded_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ── raw.diagnoses ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.diagnoses (
    diagnosis_id    BIGSERIAL    PRIMARY KEY,
    admission_id    VARCHAR(20),
    patient_id      VARCHAR(20),
    icd_code        VARCHAR(20),
    icd_version     SMALLINT,    -- 9 or 10
    seq_num         SMALLINT,    -- 1 = principal diagnosis
    _loaded_at      TIMESTAMPTZ  DEFAULT NOW()
);

-- ── raw.icu_stays ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.icu_stays (
    icustay_id      VARCHAR(20)  PRIMARY KEY,
    admission_id    VARCHAR(20),
    patient_id      VARCHAR(20),
    intime          TIMESTAMPTZ,
    outtime         TIMESTAMPTZ,
    first_careunit  VARCHAR(50),
    last_careunit   VARCHAR(50),
    _loaded_at      TIMESTAMPTZ  DEFAULT NOW()
);

-- ── raw.icd_codes (reference) ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.icd_codes (
    icd_code        VARCHAR(20),
    icd_version     SMALLINT,
    long_title      TEXT,
    short_title     VARCHAR(100),
    category        VARCHAR(100),
    PRIMARY KEY (icd_code, icd_version)
);

-- ── Unique constraint for upsert support ────────────────────────────────────────
ALTER TABLE raw.diagnoses
    ADD CONSTRAINT uq_diagnoses_admission_icd
    UNIQUE (admission_id, icd_code, icd_version);

-- ── Indexes for join performance ──────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_admissions_patient   ON raw.admissions (patient_id);
CREATE INDEX IF NOT EXISTS idx_diagnoses_admission  ON raw.diagnoses  (admission_id);
CREATE INDEX IF NOT EXISTS idx_diagnoses_patient    ON raw.diagnoses  (patient_id);
CREATE INDEX IF NOT EXISTS idx_icu_admission        ON raw.icu_stays  (admission_id);
CREATE INDEX IF NOT EXISTS idx_icu_patient          ON raw.icu_stays  (patient_id);
