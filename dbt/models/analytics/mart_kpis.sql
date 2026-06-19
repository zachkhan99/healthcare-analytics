-- models/analytics/mart_kpis.sql
-- Aggregated KPIs for the Power BI dashboard.
-- Grain: calendar month × admission_type × diagnosis_category

with facts as (
    select * from {{ ref('fact_admissions') }}
),

readmissions as (
    select
        index_admission_id,
        is_30day_readmission
    from {{ ref('mart_readmissions') }}
),

joined as (
    select
        f.*,
        coalesce(r.is_30day_readmission, false) as is_30day_readmission
    from facts f
    left join readmissions r on r.index_admission_id = f.admission_id
)

select
    date_trunc('month', admit_time)::date       as month,
    admit_year,
    admit_quarter,
    admit_month,
    admission_type,
    primary_diagnosis_category,
    insurance,
    gender,
    age_group_at_admission,

    -- Volume
    count(*)                                    as total_admissions,
    count(distinct patient_id)                  as unique_patients,

    -- Length of stay
    round(avg(los_days)::numeric, 2)            as avg_los_days,
    round(percentile_cont(0.5) within group (order by los_days)::numeric, 2)
                                                as median_los_days,
    count(*) filter (where is_long_stay)        as long_stay_count,

    -- ICU
    count(*) filter (where had_icu_stay)        as icu_admissions,
    round(avg(total_icu_hours) filter (where had_icu_stay)::numeric, 2)
                                                as avg_icu_hours,

    -- Mortality
    count(*) filter (where is_inhosp_death)     as inhosp_deaths,
    round(
        100.0 * count(*) filter (where is_inhosp_death) / nullif(count(*), 0),
        2
    )                                           as mortality_rate_pct,

    -- Readmissions
    count(*) filter (where is_30day_readmission)    as readmissions_30d,
    round(
        100.0 * count(*) filter (where is_30day_readmission) / nullif(count(*), 0),
        2
    )                                               as readmission_rate_30d_pct

from joined
group by 1,2,3,4,5,6,7,8,9
