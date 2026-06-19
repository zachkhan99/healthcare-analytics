-- models/staging/stg_admissions.sql
-- Clean admissions with derived length-of-stay and age-at-admission columns.

with source as (
    select * from {{ source('raw', 'admissions') }}
),

cleaned as (
    select
        admission_id,
        patient_id,
        admit_time::timestamptz                                                 as admit_time,
        discharge_time::timestamptz                                             as discharge_time,
        death_time::timestamptz                                                 as death_time,
        upper(trim(admission_type))                                             as admission_type,
        upper(trim(admission_location))                                         as admission_location,
        upper(trim(discharge_location))                                         as discharge_location,
        upper(trim(insurance))                                                  as insurance,
        primary_diagnosis_text,
        coalesce(hospital_expire_flag, 0)::smallint                             as hospital_expire_flag,

        -- Derived metrics
        extract(epoch from (discharge_time::timestamptz - admit_time::timestamptz))
            / 3600                                                              as los_hours,
        extract(epoch from (discharge_time::timestamptz - admit_time::timestamptz))
            / 86400                                                             as los_days,

        date_part('year', admit_time::timestamptz)::int                        as admit_year,
        date_part('quarter', admit_time::timestamptz)::int                     as admit_quarter,
        date_part('month', admit_time::timestamptz)::int                       as admit_month,
        date_part('dow', admit_time::timestamptz)::int                         as admit_dow,

        _loaded_at
    from source
    where admission_id is not null
      and patient_id   is not null
      and admit_time   is not null
      and discharge_time is not null
      and discharge_time > admit_time
)

select * from cleaned
