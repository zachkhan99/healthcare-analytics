-- models/staging/stg_patients.sql
-- Lightly clean and type-cast the raw patients table.

with source as (
    select * from {{ source('raw', 'patients') }}
),

renamed as (
    select
        patient_id,
        gender,
        date_of_birth::date                                         as date_of_birth,
        date_part('year', age(current_date, date_of_birth::date))   as age_years,
        case
            when date_part('year', age(current_date, date_of_birth::date)) < 18  then '<18'
            when date_part('year', age(current_date, date_of_birth::date)) < 30  then '18-29'
            when date_part('year', age(current_date, date_of_birth::date)) < 45  then '30-44'
            when date_part('year', age(current_date, date_of_birth::date)) < 60  then '45-59'
            when date_part('year', age(current_date, date_of_birth::date)) < 75  then '60-74'
            else '75+'
        end                                                         as age_group,
        upper(trim(ethnicity))                                      as ethnicity,
        upper(trim(language))                                       as language,
        upper(trim(marital_status))                                 as marital_status,
        upper(trim(insurance))                                      as insurance,
        _loaded_at
    from source
    where patient_id is not null
)

select * from renamed
