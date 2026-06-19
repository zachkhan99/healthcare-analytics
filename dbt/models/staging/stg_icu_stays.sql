-- models/staging/stg_icu_stays.sql

with source as (
    select * from {{ source('raw', 'icu_stays') }}
),

cleaned as (
    select
        icustay_id,
        admission_id,
        patient_id,
        intime::timestamptz                                                    as intime,
        outtime::timestamptz                                                   as outtime,
        upper(trim(first_careunit))                                            as first_careunit,
        upper(trim(last_careunit))                                             as last_careunit,
        extract(epoch from (outtime::timestamptz - intime::timestamptz))
            / 3600                                                             as icu_los_hours,
        _loaded_at
    from source
    where icustay_id   is not null
      and admission_id is not null
      and intime       is not null
      and outtime      is not null
      and outtime > intime
)

select * from cleaned
