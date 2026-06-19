-- models/analytics/mart_readmissions.sql
-- 30-day all-cause readmission analysis.
-- One row per index admission showing the NEXT admission (if any).

with admissions as (
    select
        admission_id,
        patient_id,
        admit_time,
        discharge_time,
        los_days,
        admission_type,
        insurance,
        gender,
        ethnicity,
        age_group_at_admission,
        primary_diagnosis_category,
        is_inhosp_death
    from {{ ref('fact_admissions') }}
),

-- Self-join to find all subsequent admissions per patient
readmission_window as (
    select
        curr.admission_id                               as index_admission_id,
        curr.patient_id,
        curr.discharge_time                             as index_discharge_time,
        curr.admit_time                                 as index_admit_time,
        curr.los_days                                   as index_los_days,
        curr.admission_type                             as index_admission_type,
        curr.primary_diagnosis_category,
        curr.insurance,
        curr.gender,
        curr.ethnicity,
        curr.age_group_at_admission,

        next_adm.admission_id                           as readmit_admission_id,
        next_adm.admit_time                             as readmit_admit_time,
        extract(epoch from (next_adm.admit_time - curr.discharge_time))
            / 86400                                     as days_to_readmission,

        row_number() over (
            partition by curr.admission_id
            order by next_adm.admit_time
        )                                               as rn
    from admissions curr
    -- Only look at discharges that were NOT deaths
    inner join admissions next_adm
        on  curr.patient_id       = next_adm.patient_id
        and next_adm.admit_time   > curr.discharge_time
        and not curr.is_inhosp_death
)

-- Keep only the immediate next admission (rn = 1)
select
    index_admission_id,
    patient_id,
    index_admit_time,
    index_discharge_time,
    index_los_days,
    index_admission_type,
    primary_diagnosis_category,
    insurance,
    gender,
    ethnicity,
    age_group_at_admission,
    readmit_admission_id,
    readmit_admit_time,
    round(days_to_readmission::numeric, 1)                      as days_to_readmission,
    (days_to_readmission <= {{ var('readmission_days') }})      as is_30day_readmission
from readmission_window
where rn = 1
