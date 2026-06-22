"""
dashboard/app.py
────────────────
Healthcare Analytics Dashboard built with Streamlit + Plotly.
Connects directly to the PostgreSQL marts schema.

Run:
    streamlit run dashboard/app.py
"""

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

st.set_page_config(
    page_title="Healthcare Analytics",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Colour palette ────────────────────────────────────────────────────────────

BLUE   = "#1f77b4"
RED    = "#d62728"
GREEN  = "#2ca02c"
ORANGE = "#ff7f0e"
PURPLE = "#9467bd"

CATEGORY_COLORS = {
    "Cardiovascular":   "#d62728",
    "Respiratory":      "#1f77b4",
    "Endocrine":        "#ff7f0e",
    "Renal":            "#9467bd",
    "Gastrointestinal": "#2ca02c",
    "Infectious":       "#8c564b",
    "Neurological":     "#e377c2",
}

# ── Database ──────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def get_engine():
    host = os.getenv("APP_DB_HOST", "localhost")
    port = os.getenv("APP_DB_PORT", "5432")
    db   = os.getenv("APP_DB_NAME", "healthcare")
    user = os.getenv("APP_DB_USER", "analytics")
    pw   = os.getenv("APP_DB_PASSWORD", "analytics")
    return create_engine(f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}", pool_pre_ping=True)


@st.cache_data(ttl=300, show_spinner="Loading data…")
def load_kpis() -> pd.DataFrame:
    q = """
        SELECT * FROM staging_marts.mart_kpis
        ORDER BY month
    """
    with get_engine().connect() as conn:
        return pd.read_sql(text(q), conn)


@st.cache_data(ttl=300, show_spinner=False)
def load_fact_sample() -> pd.DataFrame:
    q = """
        SELECT admission_id, patient_id, admit_time, los_days,
               hospital_expire_flag, had_icu_stay, age_at_admission,
               gender, ethnicity, insurance, admission_type,
               primary_diagnosis_category, age_group_at_admission
        FROM staging_marts.fact_admissions
    """
    with get_engine().connect() as conn:
        return pd.read_sql(text(q), conn)


@st.cache_data(ttl=300, show_spinner=False)
def load_readmissions() -> pd.DataFrame:
    q = """
        SELECT * FROM staging_marts.mart_readmissions
    """
    with get_engine().connect() as conn:
        return pd.read_sql(text(q), conn)


# ── Helpers ───────────────────────────────────────────────────────────────────

def metric_card(label: str, value: str, delta: str = "", color: str = BLUE):
    st.markdown(
        f"""
        <div style="background:{color}18;border-left:4px solid {color};
                    padding:14px 18px;border-radius:6px;margin-bottom:8px;">
            <div style="font-size:0.78rem;color:#666;font-weight:600;
                        text-transform:uppercase;letter-spacing:0.05em">{label}</div>
            <div style="font-size:1.9rem;font-weight:700;color:{color};line-height:1.2">{value}</div>
            <div style="font-size:0.78rem;color:#888">{delta}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Sidebar filters ───────────────────────────────────────────────────────────

def sidebar_filters(df: pd.DataFrame):
    st.sidebar.header("Filters")

    years = sorted(df["admit_year"].dropna().unique().astype(int).tolist())
    sel_years = st.sidebar.multiselect("Year", years, default=years)

    cats = sorted(df["primary_diagnosis_category"].dropna().unique().tolist())
    sel_cats = st.sidebar.multiselect("Diagnosis Category", cats, default=cats)

    types = sorted(df["admission_type"].dropna().unique().tolist())
    sel_types = st.sidebar.multiselect("Admission Type", types, default=types)

    insurers = sorted(df["insurance"].dropna().unique().tolist())
    sel_ins = st.sidebar.multiselect("Insurance", insurers, default=insurers)

    st.sidebar.markdown("---")
    st.sidebar.caption("Data refreshes every 5 min · Source: `marts.mart_kpis`")

    mask = (
        df["admit_year"].isin(sel_years) &
        df["primary_diagnosis_category"].isin(sel_cats) &
        df["admission_type"].isin(sel_types) &
        df["insurance"].isin(sel_ins)
    )
    return df[mask]


# ── Page: Overview ────────────────────────────────────────────────────────────

def page_overview(kpis: pd.DataFrame, facts: pd.DataFrame):
    st.title("🏥 Healthcare Analytics Dashboard")
    st.caption("Interactive analytics platform · Synthetic hospital data · Built with Python + PostgreSQL + dbt")
    st.markdown("---")

    # ── Top KPI cards ─────────────────────────────────────────────────────────
    total_admits  = int(kpis["total_admissions"].sum())
    unique_pts    = facts["patient_id"].nunique()
    avg_los       = round(facts["los_days"].mean(), 1)
    mortality     = round(facts["hospital_expire_flag"].mean() * 100, 1)
    icu_rate      = round(facts["had_icu_stay"].mean() * 100, 1)

    readm_df = load_readmissions()
    readm_rate = round(readm_df["is_30day_readmission"].mean() * 100, 1)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: metric_card("Total Admissions",     f"{total_admits:,}",  color=BLUE)
    with c2: metric_card("Unique Patients",       f"{unique_pts:,}",    color=PURPLE)
    with c3: metric_card("Avg Length of Stay",    f"{avg_los} days",    color=ORANGE)
    with c4: metric_card("In-Hospital Mortality", f"{mortality}%",      color=RED)
    with c5: metric_card("ICU Admission Rate",    f"{icu_rate}%",       color=GREEN)
    with c6: metric_card("30-Day Readmission",    f"{readm_rate}%",     color="#8c564b")

    st.markdown("### ")

    # ── Row 1: Monthly trend + Diagnosis breakdown ─────────────────────────────
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("Monthly Admissions & Readmission Rate")
        monthly = (
            kpis.groupby("month", as_index=False)
            .agg(
                total_admissions=("total_admissions", "sum"),
                readmissions_30d=("readmissions_30d", "sum"),
            )
        )
        monthly["readmission_rate"] = (
            monthly["readmissions_30d"] / monthly["total_admissions"] * 100
        ).round(1)

        fig = go.Figure()
        fig.add_bar(
            x=monthly["month"], y=monthly["total_admissions"],
            name="Admissions", marker_color=BLUE, opacity=0.7,
            yaxis="y1",
        )
        fig.add_scatter(
            x=monthly["month"], y=monthly["readmission_rate"],
            name="30-Day Readmission %", mode="lines+markers",
            line=dict(color=RED, width=2), yaxis="y2",
        )
        fig.update_layout(
            yaxis=dict(title="Admissions"),
            yaxis2=dict(title="Readmission %", overlaying="y", side="right", range=[0, 20]),
            legend=dict(orientation="h", y=1.1),
            margin=dict(t=10, b=10), height=320,
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Admissions by Diagnosis")
        by_cat = (
            kpis.groupby("primary_diagnosis_category", as_index=False)["total_admissions"]
            .sum()
            .sort_values("total_admissions", ascending=True)
            .dropna(subset=["primary_diagnosis_category"])
        )
        fig2 = px.bar(
            by_cat, x="total_admissions", y="primary_diagnosis_category",
            orientation="h",
            color="primary_diagnosis_category",
            color_discrete_map=CATEGORY_COLORS,
            labels={"total_admissions": "Admissions", "primary_diagnosis_category": ""},
        )
        fig2.update_layout(showlegend=False, margin=dict(t=10, b=10), height=320,
                           plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

    # ── Row 2: Payer mix + LOS by age ─────────────────────────────────────────
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.subheader("Payer Mix")
        payer = kpis.groupby("insurance", as_index=False)["total_admissions"].sum()
        fig3 = px.pie(
            payer, names="insurance", values="total_admissions",
            hole=0.45, color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig3.update_layout(margin=dict(t=10, b=10), height=280, showlegend=True,
                           legend=dict(orientation="h", y=-0.2))
        fig3.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig3, use_container_width=True)

    with col_b:
        st.subheader("Avg LOS by Age Group")
        los_age = (
            facts.groupby("age_group_at_admission", as_index=False)["los_days"]
            .mean()
            .round(1)
            .sort_values("los_days", ascending=False)
        )
        fig4 = px.bar(
            los_age, x="age_group_at_admission", y="los_days",
            color="los_days", color_continuous_scale="Blues",
            labels={"age_group_at_admission": "Age Group", "los_days": "Avg LOS (days)"},
        )
        fig4.update_layout(coloraxis_showscale=False, margin=dict(t=10, b=10),
                           height=280, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig4, use_container_width=True)

    with col_c:
        st.subheader("Mortality Rate by Category")
        mort_cat = (
            kpis.groupby("primary_diagnosis_category", as_index=False)
            .agg(deaths=("inhosp_deaths", "sum"), admits=("total_admissions", "sum"))
            .dropna(subset=["primary_diagnosis_category"])
        )
        mort_cat["mortality_pct"] = (mort_cat["deaths"] / mort_cat["admits"] * 100).round(1)
        mort_cat = mort_cat.sort_values("mortality_pct", ascending=True)
        fig5 = px.bar(
            mort_cat, x="mortality_pct", y="primary_diagnosis_category",
            orientation="h",
            color="primary_diagnosis_category",
            color_discrete_map=CATEGORY_COLORS,
            labels={"mortality_pct": "Mortality %", "primary_diagnosis_category": ""},
        )
        fig5.update_layout(showlegend=False, margin=dict(t=10, b=10),
                           height=280, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig5, use_container_width=True)


# ── Page: LOS & ICU ───────────────────────────────────────────────────────────

def page_los(facts: pd.DataFrame):
    st.title("📊 Length of Stay & ICU Analysis")
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("LOS Distribution (capped at 30 days)")
        los_capped = facts[facts["los_days"] <= 30]
        fig = px.histogram(
            los_capped, x="los_days", nbins=60,
            color_discrete_sequence=[BLUE],
            labels={"los_days": "Length of Stay (days)", "count": "Admissions"},
        )
        fig.update_layout(bargap=0.05, margin=dict(t=10, b=10),
                          height=300, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("LOS by Admission Type")
        fig2 = px.box(
            facts[facts["los_days"] <= 30], x="admission_type", y="los_days",
            color="admission_type",
            labels={"los_days": "LOS (days)", "admission_type": ""},
        )
        fig2.update_layout(showlegend=False, margin=dict(t=10, b=10),
                           height=300, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

    col3, col4 = st.columns(2)

    with col3:
        st.subheader("ICU Rate by Diagnosis Category")
        icu_cat = (
            facts.groupby("primary_diagnosis_category", as_index=False)
            .agg(icu=("had_icu_stay", "mean"))
            .dropna()
        )
        icu_cat["icu_pct"] = (icu_cat["icu"] * 100).round(1)
        icu_cat = icu_cat.sort_values("icu_pct", ascending=True)
        fig3 = px.bar(
            icu_cat, x="icu_pct", y="primary_diagnosis_category",
            orientation="h",
            color="primary_diagnosis_category",
            color_discrete_map=CATEGORY_COLORS,
            labels={"icu_pct": "ICU Rate (%)", "primary_diagnosis_category": ""},
        )
        fig3.update_layout(showlegend=False, margin=dict(t=10, b=10),
                           height=300, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        st.subheader("Avg LOS: ICU vs Non-ICU")
        icu_los = (
            facts.groupby(["primary_diagnosis_category", "had_icu_stay"], as_index=False)["los_days"]
            .mean()
            .round(1)
            .dropna()
        )
        icu_los["icu_label"] = icu_los["had_icu_stay"].map({True: "ICU", False: "No ICU"})
        fig4 = px.bar(
            icu_los, x="primary_diagnosis_category", y="los_days",
            color="icu_label", barmode="group",
            color_discrete_map={"ICU": RED, "No ICU": BLUE},
            labels={"los_days": "Avg LOS (days)", "primary_diagnosis_category": ""},
        )
        fig4.update_layout(margin=dict(t=10, b=10), height=300,
                           plot_bgcolor="rgba(0,0,0,0)",
                           xaxis_tickangle=-30)
        st.plotly_chart(fig4, use_container_width=True)


# ── Page: Readmissions ────────────────────────────────────────────────────────

def page_readmissions():
    st.title("🔁 30-Day Readmission Analysis")
    st.markdown("---")

    readm = load_readmissions()

    total      = len(readm)
    readm_30   = readm["is_30day_readmission"].sum()
    rate       = round(readm_30 / total * 100, 1) if total else 0
    avg_days   = round(readm["days_to_readmission"].mean(), 1)

    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Index Admissions",    f"{total:,}",        color=BLUE)
    with c2: metric_card("30-Day Readmissions", f"{int(readm_30):,}", color=RED)
    with c3: metric_card("Readmission Rate",    f"{rate}%",           color=ORANGE)
    with c4: metric_card("Avg Days to Readmit", f"{avg_days}",        color=PURPLE)

    st.markdown("### ")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Days to Readmission Distribution")
        within_30 = readm[readm["days_to_readmission"] <= 90]
        fig = px.histogram(
            within_30, x="days_to_readmission", nbins=45,
            color_discrete_sequence=[ORANGE],
            labels={"days_to_readmission": "Days to Readmission"},
        )
        fig.add_vline(x=30, line_dash="dash", line_color=RED,
                      annotation_text="30-day threshold")
        fig.update_layout(bargap=0.05, margin=dict(t=10, b=10),
                          height=300, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("30-Day Readmission Rate by Diagnosis")
        by_cat = (
            readm.groupby("primary_diagnosis_category", as_index=False)
            .agg(total=("index_admission_id", "count"),
                 readmitted=("is_30day_readmission", "sum"))
            .dropna()
        )
        by_cat["rate"] = (by_cat["readmitted"] / by_cat["total"] * 100).round(1)
        by_cat = by_cat.sort_values("rate", ascending=True)
        fig2 = px.bar(
            by_cat, x="rate", y="primary_diagnosis_category",
            orientation="h",
            color="primary_diagnosis_category",
            color_discrete_map=CATEGORY_COLORS,
            labels={"rate": "Readmission Rate (%)", "primary_diagnosis_category": ""},
        )
        fig2.update_layout(showlegend=False, margin=dict(t=10, b=10),
                           height=300, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

    col3, col4 = st.columns(2)

    with col3:
        st.subheader("Readmission Rate by Insurance")
        by_ins = (
            readm.groupby("insurance", as_index=False)
            .agg(total=("index_admission_id", "count"),
                 readmitted=("is_30day_readmission", "sum"))
            .dropna()
        )
        by_ins["rate"] = (by_ins["readmitted"] / by_ins["total"] * 100).round(1)
        fig3 = px.bar(
            by_ins.sort_values("rate", ascending=False),
            x="insurance", y="rate",
            color="insurance",
            labels={"rate": "30-Day Rate (%)", "insurance": ""},
        )
        fig3.update_layout(showlegend=False, margin=dict(t=10, b=10),
                           height=280, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        st.subheader("Readmission Rate by Age Group")
        by_age = (
            readm.groupby("age_group_at_admission", as_index=False)
            .agg(total=("index_admission_id", "count"),
                 readmitted=("is_30day_readmission", "sum"))
            .dropna()
        )
        by_age["rate"] = (by_age["readmitted"] / by_age["total"] * 100).round(1)
        age_order = ["<30", "30-44", "45-59", "60-74", "75+"]
        by_age["age_group_at_admission"] = pd.Categorical(
            by_age["age_group_at_admission"], categories=age_order, ordered=True
        )
        by_age = by_age.sort_values("age_group_at_admission")
        fig4 = px.line(
            by_age, x="age_group_at_admission", y="rate",
            markers=True, line_shape="spline",
            color_discrete_sequence=[PURPLE],
            labels={"rate": "30-Day Rate (%)", "age_group_at_admission": "Age Group"},
        )
        fig4.update_layout(margin=dict(t=10, b=10), height=280,
                           plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig4, use_container_width=True)


# ── Page: Demographics ────────────────────────────────────────────────────────

def page_demographics(facts: pd.DataFrame):
    st.title("👥 Patient Demographics")
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Age Distribution")
        fig = px.histogram(
            facts, x="age_at_admission", nbins=40,
            color_discrete_sequence=[PURPLE],
            labels={"age_at_admission": "Age at Admission"},
        )
        fig.update_layout(bargap=0.05, margin=dict(t=10, b=10),
                          height=300, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Admissions by Gender × Admission Type")
        gen_type = (
            facts.groupby(["gender", "admission_type"], as_index=False)
            .size().rename(columns={"size": "count"})
        )
        fig2 = px.bar(
            gen_type, x="admission_type", y="count",
            color="gender", barmode="group",
            color_discrete_map={"M": BLUE, "F": RED},
            labels={"count": "Admissions", "admission_type": ""},
        )
        fig2.update_layout(margin=dict(t=10, b=10), height=300,
                           plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

    col3, col4 = st.columns(2)

    with col3:
        st.subheader("Ethnicity Breakdown")
        eth = facts["ethnicity"].value_counts().reset_index()
        eth.columns = ["ethnicity", "count"]
        fig3 = px.pie(
            eth.head(8), names="ethnicity", values="count",
            hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig3.update_layout(margin=dict(t=10, b=10), height=300,
                           legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        st.subheader("Mortality Rate by Gender & Age Group")
        age_order = ["<30", "30-44", "45-59", "60-74", "75+"]
        mort_age = (
            facts.groupby(["age_group_at_admission", "gender"], as_index=False)
            .agg(rate=("hospital_expire_flag", "mean"))
        )
        mort_age["rate_pct"] = (mort_age["rate"] * 100).round(1)
        mort_age["age_group_at_admission"] = pd.Categorical(
            mort_age["age_group_at_admission"], categories=age_order, ordered=True
        )
        mort_age = mort_age.sort_values("age_group_at_admission")
        fig4 = px.line(
            mort_age, x="age_group_at_admission", y="rate_pct",
            color="gender", markers=True, line_shape="spline",
            color_discrete_map={"M": BLUE, "F": RED},
            labels={"rate_pct": "Mortality Rate (%)", "age_group_at_admission": "Age Group"},
        )
        fig4.update_layout(margin=dict(t=10, b=10), height=300,
                           plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig4, use_container_width=True)


# ── Page: Raw data explorer ───────────────────────────────────────────────────

def page_data(kpis: pd.DataFrame):
    st.title("🔍 Data Explorer")
    st.markdown("---")
    st.subheader("mart_kpis — filtered data")
    st.dataframe(kpis, use_container_width=True, height=500)
    st.caption(f"{len(kpis):,} rows · {len(kpis.columns)} columns")

    csv = kpis.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download CSV", csv, "mart_kpis_filtered.csv", "text/csv")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Load base data
    try:
        kpis  = load_kpis()
        facts = load_fact_sample()
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.info("Make sure Postgres.app is running and the ETL has been executed.")
        st.stop()

    # Sidebar filters (applied to kpis only; facts keep full grain for charts)
    kpis_filtered = sidebar_filters(kpis)

    # Navigation
    page = st.sidebar.radio(
        "Navigation",
        ["📈 Overview", "🛏 LOS & ICU", "🔁 Readmissions", "👥 Demographics", "🔍 Data Explorer"],
        label_visibility="collapsed",
    )

    if page == "📈 Overview":
        page_overview(kpis_filtered, facts)
    elif page == "🛏 LOS & ICU":
        page_los(facts)
    elif page == "🔁 Readmissions":
        page_readmissions()
    elif page == "👥 Demographics":
        page_demographics(facts)
    elif page == "🔍 Data Explorer":
        page_data(kpis_filtered)


if __name__ == "__main__":
    main()
