-- models/staging/stg_diagnoses.sql

with source as (
    select * from {{ source('raw', 'diagnoses') }}
),

cleaned as (
    select
        admission_id,
        patient_id,
        upper(trim(icd_code))               as icd_code,
        icd_version::smallint               as icd_version,
        coalesce(seq_num, 1)::smallint      as seq_num,
        (seq_num = 1)                       as is_primary_diagnosis,
        _loaded_at
    from source
    where admission_id is not null
      and icd_code     is not null
      and icd_version in (9, 10)
)

select * from cleaned
