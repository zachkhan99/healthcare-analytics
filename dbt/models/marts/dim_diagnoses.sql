-- models/marts/dim_diagnoses.sql
-- ICD code dimension enriched with category labels.

with icd_ref as (
    select
        upper(trim(icd_code))   as icd_code,
        icd_version::smallint   as icd_version,
        long_title,
        short_title,
        category
    from {{ source('raw', 'icd_codes') }}
),

usage_counts as (
    select
        icd_code,
        icd_version,
        count(*)                as total_uses,
        count(distinct patient_id)  as unique_patients
    from {{ ref('stg_diagnoses') }}
    group by icd_code, icd_version
)

select
    r.icd_code,
    r.icd_version,
    r.short_title,
    r.long_title,
    r.category,
    coalesce(u.total_uses, 0)       as total_uses,
    coalesce(u.unique_patients, 0)  as unique_patients
from icd_ref        r
left join usage_counts u using (icd_code, icd_version)
