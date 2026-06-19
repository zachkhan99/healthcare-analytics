# Healthcare Analytics Platform

End-to-end healthcare analytics platform simulating hospital operations using a modern data stack.
Built to demonstrate production-grade ETL, dimensional modeling, and automated KPI reporting for clinical decision-making.
Focused on admissions, readmissions, mortality, and ICU utilization analytics.

Built with Python · PostgreSQL · dbt · Apache Airflow · Docker

---

## Architecture

```
Raw CSVs / MIMIC-IV / CMS data
          │
          ▼
┌─────────────────────┐
│  Python ETL         │   extract.py → transform.py → load.py
│  (data validation,  │   Pandas · SQLAlchemy · Great Expectations
│  missing-value      │
│  handling, upsert)  │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  PostgreSQL         │   raw.*       – landing zone
│  Healthcare DB      │   staging.*   – dbt views
│  port 5433          │   marts.*     – dimensional models
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  dbt                │   Staging → Dimension tables → Fact table
│  Transformations    │   → Readmission analysis → KPI aggregates
│  + Tests            │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Apache Airflow     │   Daily DAG at 06:00 UTC
│  Orchestration      │   Ingest → ETL → dbt run → dbt test
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Power BI / Tableau │   Connects to marts.mart_kpis
│  Dashboard          │   KPIs: admissions, LOS, mortality,
│                     │   readmissions, ICU utilization
└─────────────────────┘
```

---

## Tech Stack

| Layer | Tool | Purpose |
|---|---|---|
| Language | Python 3.11 | ETL scripting |
| Data manipulation | Pandas, NumPy | Cleaning, transformation |
| Database | PostgreSQL 15 | Data warehouse |
| ORM / connections | SQLAlchemy 2 | Database abstraction |
| Transformations | dbt-core 1.8 | SQL models, tests, docs |
| Orchestration | Apache Airflow 2.9 | Scheduling, monitoring |
| Containerization | Docker + Compose | Reproducible environment |
| BI | Power BI / Tableau | KPI dashboard |
| Version control | Git + GitHub | Source control |

---

## Data Model

### Raw Schema (landing zone)

```
raw.patients     ─────┐
raw.admissions   ──┐  │
raw.diagnoses    ──┤  │ foreign keys
raw.icu_stays    ──┤  │
raw.icd_codes    ──┘  │
                      │
```

### Dimensional Model (marts schema)

```
               ┌─────────────────────┐
               │   dim_patients      │
               │   dim_diagnoses     │
               └────────┬────────────┘
                        │
                        ▼
               ┌─────────────────────┐
               │   fact_admissions   │   ◄── central fact
               │   (grain: 1/admit)  │
               └────────┬────────────┘
                        │
               ┌────────┴────────────┐
               │                     │
               ▼                     ▼
    mart_readmissions          mart_kpis
    (30-day readmit)       (pre-agg for BI)
```

---

## KPIs Tracked

| KPI | Description |
|---|---|
| Total admissions | Volume by month / type / category |
| Average length of stay | Days per admission |
| Median length of stay | Robust LOS metric |
| In-hospital mortality rate | % of admissions ending in death |
| 30-day readmission rate | Industry-standard quality measure |
| ICU utilization | % of admissions with ICU stay |
| Average ICU hours | Intensity-of-care metric |
| Long-stay rate | % of stays > 7 days |

All KPIs are sliceable by: month, admission type, diagnosis category, insurance, gender, age group.

---

## Quickstart

### Prerequisites

- Docker Desktop
- Python 3.11+
- Git

### 1. Clone & configure

```bash
git clone https://github.com/YOUR_USERNAME/healthcare-analytics.git
cd healthcare-analytics
cp .env.example .env          # review and edit if needed
```

### 2. Start infrastructure

```bash
docker compose up -d
```

Services started:

| Service | URL | Credentials |
|---|---|---|
| Airflow | http://localhost:8080 | admin / admin |
| pgAdmin | http://localhost:5050 | admin@healthcare.local / admin |
| PostgreSQL | localhost:5433 | analytics / analytics |

### 3. Install Python dependencies (local dev)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Generate synthetic data

```bash
python data/generate_synthetic_data.py --patients 10000
```

Or swap in real data by placing MIMIC-IV / CMS CSVs in `data/raw/` with matching column names.

### 5. Run the ETL

```bash
python -m etl.pipeline
```

### 6. Run dbt models and tests

```bash
cd dbt
dbt deps                    # install packages
dbt run                     # build all models
dbt test                    # run data quality tests
dbt docs generate && dbt docs serve   # browse lineage graph
```

### 7. Trigger the Airflow DAG

Open http://localhost:8080, enable the `healthcare_analytics_pipeline` DAG, and trigger a run.

---

## Using Real Data (MIMIC-IV)

1. Apply for access at https://physionet.org/content/mimiciv/
2. Download the MIMIC-IV CSV files
3. Map the MIMIC-IV column names to the schema in `sql/init.sql`
4. Place the mapped files in `data/raw/`
5. Run the pipeline as normal

---

## Project Structure

```
healthcare-analytics/
├── data/
│   ├── generate_synthetic_data.py   # synthetic data generator
│   ├── raw/                         # raw CSV landing zone
│   └── reports/                     # ETL validation reports (auto-generated)
├── etl/
│   ├── __init__.py
│   ├── db.py                        # database connection
│   ├── extract.py                   # CSV extraction
│   ├── transform.py                 # cleaning + validation
│   ├── load.py                      # upsert to PostgreSQL
│   └── pipeline.py                  # orchestration entry point
├── sql/
│   └── init.sql                     # raw schema DDL
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   └── models/
│       ├── staging/                 # stg_* views
│       ├── marts/                   # dim_*, fact_* tables
│       ├── analytics/               # mart_kpis, mart_readmissions
│       └── schema.yml               # sources + tests
├── airflow/
│   └── dags/
│       └── healthcare_pipeline.py   # daily DAG
├── docker-compose.yml
├── Dockerfile.airflow
├── requirements.txt
└── README.md
```

---

## Dashboard Setup (Power BI)

1. Open Power BI Desktop
2. **Get Data** → PostgreSQL database
3. Server: `localhost:5433` · Database: `healthcare`
4. Load the `marts.mart_kpis` table (and optionally `fact_admissions`, `dim_patients`)
5. Build visuals:
   - **Line chart**: Monthly admissions & readmission rate trend
   - **KPI cards**: Avg LOS · Mortality rate · 30-day readmission rate
   - **Bar chart**: Admissions by diagnosis category
   - **Donut chart**: Payer mix (insurance)
   - **Matrix**: Age group × admission type heatmap
   - **Scatter**: LOS vs. ICU hours by diagnosis category

---

## Data Quality

The pipeline enforces quality at two levels:

**ETL layer (Python)**
- Null primary key rejection
- Timestamp chronology validation (discharge > admit)
- Enum validation (gender, ICD version, admission type)
- Duplicate deduplication before load

**dbt layer (SQL)**
- `not_null` tests on all key columns
- `unique` tests on all primary keys
- `accepted_values` tests on categorical fields
- `relationships` test: fact_admissions.patient_id → dim_patients.patient_id
- Range tests: LOS ≥ 0

---

## Skills Demonstrated

- Python (pandas, SQLAlchemy, argparse, logging)
- SQL (window functions, CTEs, aggregations, upsert)
- PostgreSQL (schemas, indexes, constraints)
- dbt (sources, models, tests, documentation, variables)
- Apache Airflow (DAGs, operators, task dependencies)
- Docker (multi-service compose, custom Dockerfile)
- Data modeling (star schema, dimensional modeling)
- Data quality (validation, idempotent loads, test coverage)
- Healthcare analytics (LOS, mortality, 30-day readmissions)
- Git / GitHub (version control, documentation)
