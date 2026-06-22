"""
dashboard/app.py
Healthcare Analytics Dashboard  —  Streamlit + Plotly
"""

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

st.set_page_config(
    page_title="Healthcare Analytics",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Professional CSS — Power BI inspired ──────────────────────────────────────

st.markdown("""
<style>
html, body, [class*="css"] {
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
}
.stApp { background-color: #f4f5f7; }

[data-testid="stSidebar"] {
    background-color: #1e2433;
    border-right: none;
}
[data-testid="stSidebar"] * { color: #c8cdd8 !important; }
[data-testid="stSidebar"] .stRadio label {
    font-size: 0.85rem;
    font-weight: 500;
    padding: 6px 0;
    letter-spacing: 0.02em;
}
[data-testid="stSidebar"] .stMultiSelect label,
[data-testid="stSidebar"] .stSelectbox label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: #8a93a6 !important;
}
[data-testid="stSidebar"] hr { border-color: #2e3650; }

.dash-header {
    background: #ffffff;
    border-bottom: 1px solid #dde1ea;
    padding: 14px 28px 12px;
    margin: -1rem -1rem 1.5rem;
    display: flex;
    align-items: baseline;
    gap: 16px;
}
.dash-header h1 { font-size: 1.25rem; font-weight: 600; color: #1a2035; margin: 0; }
.dash-header span { font-size: 0.78rem; color: #8a93a6; font-weight: 400; }

.section-title {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: #8a93a6;
    margin: 1.4rem 0 0.6rem;
}

.kpi-card {
    background: #ffffff;
    border: 1px solid #e4e7ef;
    border-radius: 4px;
    padding: 16px 20px;
    min-height: 90px;
}
.kpi-label {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #8a93a6;
    margin-bottom: 6px;
}
.kpi-value { font-size: 1.85rem; font-weight: 700; line-height: 1.1; color: #1a2035; }
.kpi-sub { font-size: 0.72rem; color: #aab0bf; margin-top: 4px; }
.kpi-accent-bar { height: 3px; border-radius: 2px; margin-bottom: 10px; }

.chart-card {
    background: #ffffff;
    border: 1px solid #e4e7ef;
    border-radius: 4px;
    padding: 16px 18px 8px;
    margin-bottom: 12px;
}
.chart-title { font-size: 0.78rem; font-weight: 600; color: #1a2035; margin-bottom: 4px; }

#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Colour palette ────────────────────────────────────────────────────────────

PALETTE = {
    "blue":    "#2563EB",
    "indigo":  "#4F46E5",
    "red":     "#DC2626",
    "amber":   "#D97706",
    "emerald": "#059669",
    "slate":   "#64748B",
    "violet":  "#7C3AED",
}

CATEGORY_COLORS = {
    "Cardiovascular":   "#DC2626",
    "Respiratory":      "#2563EB",
    "Endocrine":        "#D97706",
    "Renal":            "#7C3AED",
    "Gastrointestinal": "#059669",
    "Infectious":       "#0891B2",
    "Neurological":     "#DB2777",
}

PLOTLY_LAYOUT = dict(
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
    font=dict(family="Segoe UI, Helvetica Neue, Arial", size=11, color="#374151"),
    margin=dict(t=12, b=8, l=8, r=8),
    xaxis=dict(gridcolor="#f0f0f0", linecolor="#e5e7eb", zeroline=False),
    yaxis=dict(gridcolor="#f0f0f0", linecolor="#e5e7eb", zeroline=False),
    legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0, font=dict(size=11)),
    hoverlabel=dict(bgcolor="#1e2433", font_color="#ffffff",
                    font_size=12, bordercolor="#1e2433"),
)


def apply_layout(fig, **kwargs):
    fig.update_layout(**{**PLOTLY_LAYOUT, **kwargs})
    return fig


# ── Database ──────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def get_engine():
    host = os.getenv("APP_DB_HOST", "localhost")
    port = os.getenv("APP_DB_PORT", "5432")
    db   = os.getenv("APP_DB_NAME", "healthcare")
    user = os.getenv("APP_DB_USER", "analytics")
    pw   = os.getenv("APP_DB_PASSWORD", "analytics")
    return create_engine(
        f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}",
        pool_pre_ping=True,
    )


@st.cache_data(ttl=300, show_spinner="Querying database...")
def load_kpis() -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(
            text("SELECT * FROM staging_marts.mart_kpis ORDER BY month"), conn)


@st.cache_data(ttl=300, show_spinner=False)
def load_fact_sample() -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(text("""
            SELECT admission_id, patient_id, admit_time, los_days,
                   hospital_expire_flag, had_icu_stay, age_at_admission,
                   gender, ethnicity, insurance, admission_type,
                   primary_diagnosis_category, age_group_at_admission
            FROM staging_marts.fact_admissions
        """), conn)


@st.cache_data(ttl=300, show_spinner=False)
def load_readmissions() -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(
            text("SELECT * FROM staging_marts.mart_readmissions"), conn)


# ── UI helpers ────────────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str = ""):
    sub = f"<span>{subtitle}</span>" if subtitle else ""
    st.markdown(
        f'<div class="dash-header"><h1>{title}</h1>{sub}</div>',
        unsafe_allow_html=True)


def section_label(text: str):
    st.markdown(
        f'<div class="section-title">{text}</div>',
        unsafe_allow_html=True)


def kpi_card(label: str, value: str, sub: str = "", accent: str = "#2563EB"):
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-accent-bar" style="background:{accent};width:32px;"></div>
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)


def chart_wrap(title: str, fig, height: int = 300):
    st.markdown(
        f'<div class="chart-card"><div class="chart-title">{title}</div></div>',
        unsafe_allow_html=True)
    fig.update_layout(height=height)
    st.plotly_chart(fig, width="stretch")


# ── Sidebar ───────────────────────────────────────────────────────────────────

def sidebar_filters(df: pd.DataFrame):
    st.sidebar.markdown(
        "<div style='padding:20px 16px 4px;font-size:0.7rem;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.1em;color:#5a6278;'>Navigation</div>",
        unsafe_allow_html=True)

    page = st.sidebar.radio(
        "nav",
        ["Overview", "Length of Stay & ICU", "Readmissions", "Demographics", "Data Explorer"],
        label_visibility="collapsed")

    st.sidebar.markdown(
        "<hr style='border-color:#2e3650;margin:12px 0;'>",
        unsafe_allow_html=True)
    st.sidebar.markdown(
        "<div style='padding:0 0 4px;font-size:0.7rem;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.1em;color:#5a6278;'>Filters</div>",
        unsafe_allow_html=True)

    years    = sorted(df["admit_year"].dropna().unique().astype(int).tolist())
    cats     = sorted(df["primary_diagnosis_category"].dropna().unique().tolist())
    types    = sorted(df["admission_type"].dropna().unique().tolist())
    insurers = sorted(df["insurance"].dropna().unique().tolist())

    sel_years = st.sidebar.multiselect("Year",               years,    default=years)
    sel_cats  = st.sidebar.multiselect("Diagnosis Category", cats,     default=cats)
    sel_types = st.sidebar.multiselect("Admission Type",     types,    default=types)
    sel_ins   = st.sidebar.multiselect("Insurance",          insurers, default=insurers)

    st.sidebar.markdown(
        "<hr style='border-color:#2e3650;margin:12px 0;'>",
        unsafe_allow_html=True)
    st.sidebar.markdown(
        "<div style='font-size:0.68rem;color:#5a6278;padding:0 0 8px;'>"
        "Source: staging_marts &nbsp;&middot;&nbsp; Refreshes every 5 min</div>",
        unsafe_allow_html=True)

    mask = (
        df["admit_year"].isin(sel_years) &
        df["primary_diagnosis_category"].isin(sel_cats) &
        df["admission_type"].isin(sel_types) &
        df["insurance"].isin(sel_ins)
    )
    return page, df[mask]


# ── Page: Overview ────────────────────────────────────────────────────────────

def page_overview(kpis: pd.DataFrame, facts: pd.DataFrame):
    page_header(
        "Clinical Operations Overview",
        "Admission volume, outcomes, and payer mix  |  Synthetic hospital dataset")

    readm_df   = load_readmissions()
    total_adm  = int(kpis["total_admissions"].sum())
    unique_pts = facts["patient_id"].nunique()
    avg_los    = round(facts["los_days"].mean(), 1)
    mortality  = round(facts["hospital_expire_flag"].mean() * 100, 1)
    icu_rate   = round(facts["had_icu_stay"].mean() * 100, 1)
    readm_rate = round(readm_df["is_30day_readmission"].mean() * 100, 1)

    section_label("Key Performance Indicators")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: kpi_card("Total Admissions",     f"{total_adm:,}",  accent=PALETTE["blue"])
    with c2: kpi_card("Unique Patients",       f"{unique_pts:,}", accent=PALETTE["indigo"])
    with c3: kpi_card("Avg Length of Stay",    f"{avg_los}d",
                       sub="days per admission",  accent=PALETTE["amber"])
    with c4: kpi_card("In-Hospital Mortality", f"{mortality}%",
                       sub="of all admissions",   accent=PALETTE["red"])
    with c5: kpi_card("ICU Admission Rate",    f"{icu_rate}%",
                       sub="required ICU care",   accent=PALETTE["emerald"])
    with c6: kpi_card("30-Day Readmission",    f"{readm_rate}%",
                       sub="within 30 days",      accent=PALETTE["violet"])

    section_label("Volume & Trends")
    col_left, col_right = st.columns([2, 1])

    with col_left:
        monthly = (kpis.groupby("month", as_index=False)
                   .agg(total_admissions=("total_admissions", "sum"),
                        readmissions_30d=("readmissions_30d", "sum")))
        monthly["readmission_rate"] = (
            monthly["readmissions_30d"] / monthly["total_admissions"] * 100).round(1)

        fig = go.Figure()
        fig.add_bar(x=monthly["month"], y=monthly["total_admissions"],
                    name="Admissions", marker_color=PALETTE["blue"],
                    marker_line_width=0, opacity=0.85, yaxis="y1")
        fig.add_scatter(x=monthly["month"], y=monthly["readmission_rate"],
                        name="30-Day Readmission %", mode="lines+markers",
                        line=dict(color=PALETTE["red"], width=2),
                        marker=dict(size=4), yaxis="y2")
        apply_layout(fig,
            yaxis=dict(title="Admissions", gridcolor="#f0f0f0",
                       linecolor="#e5e7eb", zeroline=False),
            yaxis2=dict(title="Readmission %", overlaying="y", side="right",
                        range=[0, 20], zeroline=False),
            legend=dict(orientation="h", y=1.08, x=0,
                        bgcolor="rgba(0,0,0,0)", borderwidth=0))
        chart_wrap("Monthly Admissions vs. 30-Day Readmission Rate", fig, height=310)

    with col_right:
        by_cat = (kpis.groupby("primary_diagnosis_category", as_index=False)
                  ["total_admissions"].sum()
                  .sort_values("total_admissions", ascending=True)
                  .dropna(subset=["primary_diagnosis_category"]))
        fig2 = px.bar(by_cat, x="total_admissions", y="primary_diagnosis_category",
                      orientation="h", color="primary_diagnosis_category",
                      color_discrete_map=CATEGORY_COLORS,
                      labels={"total_admissions": "Admissions",
                              "primary_diagnosis_category": ""})
        apply_layout(fig2, showlegend=False)
        chart_wrap("Admissions by Diagnosis Category", fig2, height=310)

    section_label("Payer Mix & Outcomes")
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        payer = kpis.groupby("insurance", as_index=False)["total_admissions"].sum()
        fig3 = px.pie(payer, names="insurance", values="total_admissions", hole=0.5,
                      color_discrete_sequence=[
                          PALETTE["blue"], PALETTE["indigo"], PALETTE["emerald"],
                          PALETTE["amber"], PALETTE["violet"]])
        fig3.update_traces(textposition="inside", textinfo="percent", textfont_size=11)
        apply_layout(fig3, legend=dict(orientation="v", x=1.02, y=0.5))
        chart_wrap("Payer Mix", fig3, height=270)

    with col_b:
        los_age = (facts.groupby("age_group_at_admission", as_index=False)["los_days"]
                   .mean().round(1).sort_values("los_days", ascending=False))
        fig4 = px.bar(los_age, x="age_group_at_admission", y="los_days",
                      color="los_days",
                      color_continuous_scale=["#dbeafe", "#1d4ed8"],
                      labels={"age_group_at_admission": "Age Group",
                              "los_days": "Avg LOS (days)"})
        apply_layout(fig4, coloraxis_showscale=False)
        chart_wrap("Avg Length of Stay by Age Group", fig4, height=270)

    with col_c:
        mort_cat = (kpis.groupby("primary_diagnosis_category", as_index=False)
                    .agg(deaths=("inhosp_deaths", "sum"), admits=("total_admissions", "sum"))
                    .dropna(subset=["primary_diagnosis_category"]))
        mort_cat["mortality_pct"] = (
            mort_cat["deaths"] / mort_cat["admits"] * 100).round(1)
        mort_cat = mort_cat.sort_values("mortality_pct", ascending=True)
        fig5 = px.bar(mort_cat, x="mortality_pct", y="primary_diagnosis_category",
                      orientation="h", color="primary_diagnosis_category",
                      color_discrete_map=CATEGORY_COLORS,
                      labels={"mortality_pct": "Mortality (%)",
                              "primary_diagnosis_category": ""})
        apply_layout(fig5, showlegend=False)
        chart_wrap("In-Hospital Mortality by Category", fig5, height=270)


# ── Page: LOS & ICU ───────────────────────────────────────────────────────────

def page_los(facts: pd.DataFrame):
    page_header("Length of Stay & ICU Utilization")

    col1, col2 = st.columns(2)
    with col1:
        los_capped = facts[facts["los_days"] <= 30]
        fig = px.histogram(los_capped, x="los_days", nbins=60,
                           color_discrete_sequence=[PALETTE["blue"]],
                           labels={"los_days": "Length of Stay (days)",
                                   "count": "Admissions"})
        fig.update_traces(marker_line_width=0)
        apply_layout(fig, bargap=0.04)
        chart_wrap("LOS Distribution (capped at 30 days)", fig, height=300)

    with col2:
        fig2 = px.box(facts[facts["los_days"] <= 30],
                      x="admission_type", y="los_days",
                      color="admission_type",
                      color_discrete_sequence=[
                          PALETTE["blue"], PALETTE["indigo"],
                          PALETTE["emerald"], PALETTE["amber"]],
                      labels={"los_days": "LOS (days)", "admission_type": ""})
        apply_layout(fig2, showlegend=False)
        chart_wrap("LOS Distribution by Admission Type", fig2, height=300)

    col3, col4 = st.columns(2)
    with col3:
        icu_cat = (facts.groupby("primary_diagnosis_category", as_index=False)
                   .agg(icu=("had_icu_stay", "mean")).dropna())
        icu_cat["icu_pct"] = (icu_cat["icu"] * 100).round(1)
        icu_cat = icu_cat.sort_values("icu_pct", ascending=True)
        fig3 = px.bar(icu_cat, x="icu_pct", y="primary_diagnosis_category",
                      orientation="h", color="primary_diagnosis_category",
                      color_discrete_map=CATEGORY_COLORS,
                      labels={"icu_pct": "ICU Rate (%)",
                              "primary_diagnosis_category": ""})
        apply_layout(fig3, showlegend=False)
        chart_wrap("ICU Admission Rate by Diagnosis Category", fig3, height=300)

    with col4:
        icu_los = (facts.groupby(
            ["primary_diagnosis_category", "had_icu_stay"], as_index=False)
            ["los_days"].mean().round(1).dropna())
        icu_los["icu_label"] = icu_los["had_icu_stay"].map(
            {True: "ICU", False: "Non-ICU"})
        fig4 = px.bar(icu_los, x="primary_diagnosis_category", y="los_days",
                      color="icu_label", barmode="group",
                      color_discrete_map={"ICU": PALETTE["red"],
                                          "Non-ICU": PALETTE["blue"]},
                      labels={"los_days": "Avg LOS (days)",
                              "primary_diagnosis_category": ""})
        apply_layout(fig4, xaxis_tickangle=-30,
                     legend=dict(orientation="h", y=1.05))
        chart_wrap("Avg LOS — ICU vs. Non-ICU by Category", fig4, height=300)


# ── Page: Readmissions ────────────────────────────────────────────────────────

def page_readmissions():
    page_header("30-Day Readmission Analysis")

    readm    = load_readmissions()
    total    = len(readm)
    readm_30 = int(readm["is_30day_readmission"].sum())
    rate     = round(readm_30 / total * 100, 1) if total else 0
    avg_days = round(readm["days_to_readmission"].dropna().mean(), 1)

    section_label("Summary")
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi_card("Index Admissions",    f"{total:,}",
                       accent=PALETTE["blue"])
    with c2: kpi_card("30-Day Readmissions", f"{readm_30:,}",
                       accent=PALETTE["red"])
    with c3: kpi_card("Readmission Rate",    f"{rate}%",
                       sub="benchmark: <15%",     accent=PALETTE["amber"])
    with c4: kpi_card("Avg Days to Readmit", f"{avg_days}",
                       sub="days post-discharge", accent=PALETTE["violet"])

    section_label("Distribution & Category Breakdown")
    col1, col2 = st.columns(2)
    with col1:
        within_90 = readm[readm["days_to_readmission"] <= 90]
        fig = px.histogram(within_90, x="days_to_readmission", nbins=45,
                           color_discrete_sequence=[PALETTE["amber"]],
                           labels={"days_to_readmission": "Days to Readmission"})
        fig.update_traces(marker_line_width=0)
        fig.add_vline(x=30, line_dash="dot", line_color=PALETTE["red"],
                      line_width=1.5, annotation_text="30-day threshold",
                      annotation_font_size=10,
                      annotation_font_color=PALETTE["red"])
        apply_layout(fig, bargap=0.04)
        chart_wrap("Days to Readmission (within 90 days)", fig, height=290)

    with col2:
        by_cat = (readm.groupby("primary_diagnosis_category", as_index=False)
                  .agg(total=("index_admission_id", "count"),
                       readmitted=("is_30day_readmission", "sum")).dropna())
        by_cat["rate"] = (by_cat["readmitted"] / by_cat["total"] * 100).round(1)
        by_cat = by_cat.sort_values("rate", ascending=True)
        fig2 = px.bar(by_cat, x="rate", y="primary_diagnosis_category",
                      orientation="h", color="primary_diagnosis_category",
                      color_discrete_map=CATEGORY_COLORS,
                      labels={"rate": "Readmission Rate (%)",
                              "primary_diagnosis_category": ""})
        apply_layout(fig2, showlegend=False)
        chart_wrap("30-Day Readmission Rate by Diagnosis", fig2, height=290)

    section_label("Insurance & Age Stratification")
    col3, col4 = st.columns(2)
    with col3:
        by_ins = (readm.groupby("insurance", as_index=False)
                  .agg(total=("index_admission_id", "count"),
                       readmitted=("is_30day_readmission", "sum")).dropna())
        by_ins["rate"] = (by_ins["readmitted"] / by_ins["total"] * 100).round(1)
        fig3 = px.bar(by_ins.sort_values("rate", ascending=False),
                      x="insurance", y="rate", color="insurance",
                      color_discrete_sequence=[
                          PALETTE["blue"], PALETTE["indigo"], PALETTE["emerald"],
                          PALETTE["amber"], PALETTE["violet"]],
                      labels={"rate": "30-Day Rate (%)", "insurance": ""})
        apply_layout(fig3, showlegend=False)
        chart_wrap("30-Day Readmission Rate by Payer", fig3, height=270)

    with col4:
        by_age = (readm.groupby("age_group_at_admission", as_index=False)
                  .agg(total=("index_admission_id", "count"),
                       readmitted=("is_30day_readmission", "sum")).dropna())
        by_age["rate"] = (by_age["readmitted"] / by_age["total"] * 100).round(1)
        age_order = ["<30", "30-44", "45-59", "60-74", "75+"]
        by_age["age_group_at_admission"] = pd.Categorical(
            by_age["age_group_at_admission"], categories=age_order, ordered=True)
        by_age = by_age.sort_values("age_group_at_admission")
        fig4 = px.line(by_age, x="age_group_at_admission", y="rate",
                       markers=True,
                       color_discrete_sequence=[PALETTE["violet"]],
                       labels={"rate": "30-Day Rate (%)",
                               "age_group_at_admission": "Age Group"})
        fig4.update_traces(line_width=2, marker_size=6)
        apply_layout(fig4)
        chart_wrap("30-Day Readmission Rate by Age Group", fig4, height=270)


# ── Page: Demographics ────────────────────────────────────────────────────────

def page_demographics(facts: pd.DataFrame):
    page_header("Patient Demographics & Mortality")

    col1, col2 = st.columns(2)
    with col1:
        fig = px.histogram(facts, x="age_at_admission", nbins=40,
                           color_discrete_sequence=[PALETTE["indigo"]],
                           labels={"age_at_admission": "Age at Admission",
                                   "count": "Patients"})
        fig.update_traces(marker_line_width=0)
        apply_layout(fig, bargap=0.04)
        chart_wrap("Patient Age Distribution at Admission", fig, height=290)

    with col2:
        gen_type = (facts.groupby(["gender", "admission_type"], as_index=False)
                    .size().rename(columns={"size": "count"}))
        fig2 = px.bar(gen_type, x="admission_type", y="count",
                      color="gender", barmode="group",
                      color_discrete_map={"M": PALETTE["blue"],
                                          "F": PALETTE["red"]},
                      labels={"count": "Admissions", "admission_type": ""})
        apply_layout(fig2, legend=dict(orientation="h", y=1.05))
        chart_wrap("Admissions by Gender and Admission Type", fig2, height=290)

    col3, col4 = st.columns(2)
    with col3:
        eth = facts["ethnicity"].value_counts().reset_index()
        eth.columns = ["ethnicity", "count"]
        fig3 = px.pie(eth.head(8), names="ethnicity", values="count", hole=0.48,
                      color_discrete_sequence=[
                          PALETTE["blue"], PALETTE["indigo"], PALETTE["emerald"],
                          PALETTE["amber"], PALETTE["violet"], PALETTE["red"],
                          PALETTE["slate"], "#0891B2"])
        fig3.update_traces(textposition="inside", textinfo="percent",
                           textfont_size=11)
        apply_layout(fig3, legend=dict(orientation="v", x=1.02, y=0.5))
        chart_wrap("Patient Ethnicity Breakdown", fig3, height=290)

    with col4:
        age_order = ["<30", "30-44", "45-59", "60-74", "75+"]
        mort_age = (facts.groupby(
            ["age_group_at_admission", "gender"], as_index=False)
            .agg(rate=("hospital_expire_flag", "mean")))
        mort_age["rate_pct"] = (mort_age["rate"] * 100).round(1)
        mort_age["age_group_at_admission"] = pd.Categorical(
            mort_age["age_group_at_admission"], categories=age_order, ordered=True)
        mort_age = mort_age.sort_values("age_group_at_admission")
        fig4 = px.line(mort_age, x="age_group_at_admission", y="rate_pct",
                       color="gender", markers=True,
                       color_discrete_map={"M": PALETTE["blue"],
                                           "F": PALETTE["red"]},
                       labels={"rate_pct": "Mortality Rate (%)",
                               "age_group_at_admission": "Age Group"})
        fig4.update_traces(line_width=2, marker_size=6)
        apply_layout(fig4, legend=dict(orientation="h", y=1.05))
        chart_wrap("In-Hospital Mortality Rate by Gender and Age Group",
                   fig4, height=290)


# ── Page: Data Explorer ───────────────────────────────────────────────────────

def page_data(kpis: pd.DataFrame):
    page_header("Data Explorer", "mart_kpis — filtered view")
    section_label("Dataset Preview")
    st.dataframe(kpis, width="stretch", height=460)
    col_info, col_dl = st.columns([3, 1])
    with col_info:
        st.markdown(
            f"<span style='font-size:0.75rem;color:#8a93a6;'>"
            f"{len(kpis):,} rows &nbsp;&middot;&nbsp; {len(kpis.columns)} columns"
            f"</span>",
            unsafe_allow_html=True)
    with col_dl:
        st.download_button(
            "Download as CSV",
            kpis.to_csv(index=False).encode("utf-8"),
            file_name="mart_kpis_filtered.csv",
            mime="text/csv")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    try:
        kpis  = load_kpis()
        facts = load_fact_sample()
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.info("Make sure Postgres.app is running and the ETL has been executed.")
        st.stop()

    page, kpis_filtered = sidebar_filters(kpis)

    if page == "Overview":
        page_overview(kpis_filtered, facts)
    elif page == "Length of Stay & ICU":
        page_los(facts)
    elif page == "Readmissions":
        page_readmissions()
    elif page == "Demographics":
        page_demographics(facts)
    elif page == "Data Explorer":
        page_data(kpis_filtered)


if __name__ == "__main__":
    main()
