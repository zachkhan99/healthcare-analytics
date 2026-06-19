-- models/marts/dim_patients.sql
-- Patient dimension table: one row per patient, with latest demographics.

with patients as (
    select * from {{ ref('stg_patients') }}
),

-- Latest admission per patient to pick up current insurance/marital status
latest_admission as (
    select distinct on (patient_id)
        patient_id,
        insurance       as latest_insurance,
        admission_type  as latest_admission_type
    from {{ ref('stg_admissions') }}
    order by patient_id, admit_time desc
),

admission_counts as (
    select
        patient_id,
        count(*)                            as total_admissions,
        sum(hospital_expire_flag)           as total_inhosp_deaths,
        min(admit_time)                     as first_admit_time,
        max(admit_time)                     as last_admit_time,
        avg(los_days)                       as avg_los_days
    from {{ ref('stg_admissions') }}
    group by patient_id
)

select
    p.patient_id,
    p.gender,
    p.date_of_birth,
    p.age_years,
    p.age_group,
    p.ethnicity,
    p.language,
    p.marital_status,
    coalesce(la.latest_insurance, p.insurance) as insurance,

    -- Admission statistics
    coalesce(ac.total_admissions, 0)        as total_admissions,
    coalesce(ac.total_inhosp_deaths, 0)     as total_inhosp_deaths,
    ac.first_admit_time,
    ac.last_admit_time,
    round(coalesce(ac.avg_los_days, 0)::numeric, 2)  as avg_los_days

from patients              p
left join latest_admission la using (patient_id)
left join admission_counts ac using (patient_id)
