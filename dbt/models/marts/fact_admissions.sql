-- models/marts/fact_admissions.sql
-- Central fact table: one row per admission with all KPI columns.

with admissions as (
    select * from {{ ref('stg_admissions') }}
),

patients as (
    select
        patient_id,
        gender,
        age_years,
        age_group,
        ethnicity,
        date_of_birth
    from {{ ref('stg_patients') }}
),

-- Primary diagnosis per admission
primary_dx as (
    select
        admission_id,
        icd_code        as primary_icd_code,
        icd_version     as primary_icd_version
    from {{ ref('stg_diagnoses') }}
    where is_primary_diagnosis
),

-- ICD reference for label
icd_ref as (
    select icd_code, icd_version, short_title, category
    from {{ ref('dim_diagnoses') }}
),

-- ICU flag & duration per admission
icu as (
    select
        admission_id,
        true                    as had_icu_stay,
        sum(icu_los_hours)      as total_icu_hours,
        count(*)                as icu_stay_count
    from {{ ref('stg_icu_stays') }}
    group by admission_id
),

-- Age at admission
aged as (
    select
        a.admission_id,
        a.patient_id,
        a.admit_time,
        a.discharge_time,
        a.death_time,
        a.admission_type,
        a.admission_location,
        a.discharge_location,
        a.insurance,
        a.primary_diagnosis_text,
        a.hospital_expire_flag,
        a.los_hours,
        a.los_days,
        a.admit_year,
        a.admit_quarter,
        a.admit_month,
        a.admit_dow,
        p.gender,
        p.ethnicity,
        p.date_of_birth,
        date_part('year', age(a.admit_time::date, p.date_of_birth))::int  as age_at_admission,
        case
            when date_part('year', age(a.admit_time::date, p.date_of_birth)) < 30  then '<30'
            when date_part('year', age(a.admit_time::date, p.date_of_birth)) < 45  then '30-44'
            when date_part('year', age(a.admit_time::date, p.date_of_birth)) < 60  then '45-59'
            when date_part('year', age(a.admit_time::date, p.date_of_birth)) < 75  then '60-74'
            else '75+'
        end                                                               as age_group_at_admission
    from admissions a
    left join patients p using (patient_id)
)

select
    a.admission_id,
    a.patient_id,
    a.admit_time,
    a.discharge_time,
    a.death_time,
    a.admission_type,
    a.admission_location,
    a.discharge_location,
    a.insurance,
    a.hospital_expire_flag,

    -- Time metrics
    round(a.los_hours::numeric, 2)          as los_hours,
    round(a.los_days::numeric,  2)          as los_days,
    a.admit_year,
    a.admit_quarter,
    a.admit_month,
    a.admit_dow,

    -- Patient demographics at admission
    a.gender,
    a.ethnicity,
    a.age_at_admission,
    a.age_group_at_admission,

    -- Primary diagnosis
    dx.primary_icd_code,
    dx.primary_icd_version,
    ref.short_title                         as primary_diagnosis_short,
    ref.category                            as primary_diagnosis_category,

    -- ICU
    coalesce(icu.had_icu_stay, false)               as had_icu_stay,
    coalesce(icu.icu_stay_count, 0)::smallint       as icu_stay_count,
    coalesce(icu.total_icu_hours, 0)                as total_icu_hours,

    -- Flags
    (a.los_days > 7)                        as is_long_stay,
    (a.hospital_expire_flag = 1)            as is_inhosp_death

from aged                       a
left join primary_dx            dx  using (admission_id)
left join icd_ref               ref on dx.primary_icd_code    = ref.icd_code
                                    and dx.primary_icd_version = ref.icd_version
left join icu                   using (admission_id)
