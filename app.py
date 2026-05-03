"""
Waypoint P&C | Retention Analytics Dashboard
7-tab Streamlit app: KPI header, sidebar filters, cohort analysis,
channel comparison, predictive model, cross-sell funnel,
financial impact simulator, recommendations, and healthcare translation.

Usage (from project root):
    streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# --------------------------------------------------------------------------- #
# Page config (must be first Streamlit call)                                  #
# --------------------------------------------------------------------------- #

st.set_page_config(
    page_title="Waypoint P&C | Retention Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------- #
# Color palette                                                                #
# --------------------------------------------------------------------------- #

BLUE_700   = "#0077B3"
BLUE_500   = "#3399CC"
NAVY       = "#003366"
ORANGE_700 = "#E07B00"
RED_SOFT   = "#C0392B"
GREEN_700  = "#217A3C"
STEEL_700  = "#607080"
STEEL_300  = "#A0B4C8"
STEEL_100  = "#EDF2F7"
WHITE      = "#FFFFFF"

# Plotly base layout -- exactly 5 keys (verification gate requirement)
base_layout = dict(
    font=dict(family="Inter, sans-serif", size=11),
    plot_bgcolor=WHITE,
    paper_bgcolor=WHITE,
    margin=dict(l=62, r=16, t=40, b=40),
    showlegend=False,
)

# Consistent chart title style
TITLE_FONT = dict(size=13, color=NAVY)

# Tenure band color progression (light to dark, no red/orange)
TENURE_COLORS = {
    "0-11 mo":  BLUE_500,
    "12-23 mo": BLUE_700,
    "24-47 mo": STEEL_700,
    "48+ mo":   NAVY,
}

# Human-readable SHAP feature labels
FEATURE_LABELS: dict[str, str] = {
    "acquisition_channel":   "Acquisition Channel",
    "payment_consistency":   "Payment Consistency Score",
    "annual_premium":        "Annual Premium",
    "policy_type":           "Policy Type",
    "total_claim_amount":    "Total Claim Amount",
    "years_with_carrier":    "Years with Carrier",
    "multi_product_flag":    "Multi-Product Policyholder",
    "aqx_assisted_flag":     "AQX-Assisted Acquisition",
    "tenure_months":         "Customer Tenure (Months)",
    "prior_insurance_flag":  "Prior Insurance History",
    "metro_area":            "Metro Area",
    "state":                 "State",
    "days_since_last_claim": "Days Since Last Claim",
    "coverage_tier":         "Coverage Tier",
    "cohort_quarter":        "Acquisition Cohort Quarter",
    "missed_payment_count":  "Missed Payment Count",
    "nsf_flag":              "Returned Payment Flag",
    "late_pay_flag_3mo":     "Late Payment (Last 3 Months)",
    "billing_frequency":     "Billing Frequency",
    "claim_severity_band":   "Claim Severity Band",
    "age_band":              "Customer Age Band",
    "homeowner_flag":        "Homeowner Status",
    "days_past_due_max":     "Maximum Days Past Due",
    "renters_attached_flag": "Renters Policy Attached",
    "renters_quoted_flag":   "Renters Policy Quoted",
    "has_claim_12mo":        "Filed a Claim (12 Mo)",
    "claim_count_12mo":      "Claim Count (12 Mo)",
    "model_decile":          "Model Risk Decile",
    "lapse_prob":            "Predicted Lapse Probability",
}

# --------------------------------------------------------------------------- #
# Domain constants                                                             #
# --------------------------------------------------------------------------- #

CHANNELS     = ["Agency Portal", "AQX", "Direct Web", "Phone", "Referral"]
TIERS        = ["Liability Only", "Standard", "Premium", "Elite"]
TIER_ORDER   = {"Liability Only": 0, "Standard": 1, "Premium": 2, "Elite": 3}
POLICY_TYPES = ["Auto Only", "Auto + Renters"]
STATES       = ["AL","AZ","CO","FL","GA","IN","KY","MO","NC","OH","SC","TN","TX","VA"]
AGENCY_TYPES = ["Independent", "Captive", "Digital Partner", "Direct"]

# --------------------------------------------------------------------------- #
# Path setup                                                                   #
# --------------------------------------------------------------------------- #

def find_project_root() -> Path:
    """Walk up from this file until PROJECT_MANIFEST.json is found."""
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "PROJECT_MANIFEST.json").exists():
            return p
        p = p.parent
    return Path(__file__).resolve().parent


PROJECT_ROOT = find_project_root()
OUTPUTS_DIR  = PROJECT_ROOT / "_build" / "workflows" / "04_modeling" / "outputs"

# --------------------------------------------------------------------------- #
# Data loading                                                                 #
# --------------------------------------------------------------------------- #

@st.cache_data
def load_data() -> pd.DataFrame:
    """Load and lightly preprocess the scored denormalized dataset."""
    df = pd.read_csv(OUTPUTS_DIR / "waypoint_retention_scored.csv")
    df["claim_severity_band"] = df["claim_severity_band"].fillna("No Claims")
    df["effective_date"] = pd.to_datetime(df["effective_date"])
    df["tenure_band"] = pd.cut(
        df["tenure_months"],
        bins=[-1, 11, 23, 47, 999],
        labels=["0-11 mo", "12-23 mo", "24-47 mo", "48+ mo"],
    )
    return df


@st.cache_data
def load_model_assets() -> tuple[pd.DataFrame, dict]:
    """Load SHAP values and model metrics JSON."""
    shap_df  = pd.read_csv(OUTPUTS_DIR / "shap_values.csv")
    with open(OUTPUTS_DIR / "model_metrics.json") as fh:
        metrics = json.load(fh)
    return shap_df, metrics

# --------------------------------------------------------------------------- #
# Session state                                                                #
# --------------------------------------------------------------------------- #

def init_session_state() -> None:
    """Initialize default values for all session-state keys."""
    defaults = {
        "channel_sel":       CHANNELS,
        "coverage_tier_sel": TIERS,
        "policy_type_sel":   POLICY_TYPES,
        "tenure_range":      (0, 120),
        "state_sel":         STATES,
        "risk_band_sel":     "High Risk",
        "_reset_filters":    False,
        "sim_renewal_lift":  5.0,
        "sim_attach_lift":   3.0,
        "_reset_sim":        False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

# --------------------------------------------------------------------------- #
# Sidebar                                                                      #
# --------------------------------------------------------------------------- #

def render_sidebar(df: pd.DataFrame) -> None:
    """Render sidebar filters using the reset-flag pattern."""
    # Reset-flag guard: must run before any widget renders
    if st.session_state.get("_reset_filters"):
        for key in ["channel_sel","coverage_tier_sel","policy_type_sel",
                    "tenure_range","state_sel"]:
            if key in st.session_state:
                del st.session_state[key]
        init_session_state()
        st.session_state["_reset_filters"] = False

    # CSS: expand State multiselect dropdown so all 14 states are visible without clipping
    st.markdown(
        """<style>
        [data-testid="stSidebar"] [data-baseweb="popover"] ul {
            max-height: 280px !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("## Filters")

    st.sidebar.multiselect(
        "Acquisition Channel",
        options=CHANNELS,
        default=st.session_state["channel_sel"],
        key="channel_sel",
    )
    st.sidebar.multiselect(
        "Coverage Tier",
        options=TIERS,
        default=st.session_state["coverage_tier_sel"],
        key="coverage_tier_sel",
    )
    st.sidebar.multiselect(
        "Policy Type",
        options=POLICY_TYPES,
        default=st.session_state["policy_type_sel"],
        key="policy_type_sel",
    )
    st.sidebar.slider(
        "Customer Tenure (Months)",
        min_value=0, max_value=120,
        value=st.session_state["tenure_range"],
        key="tenure_range",
    )
    st.sidebar.multiselect(
        "State",
        options=STATES,
        default=st.session_state["state_sel"],
        key="state_sel",
    )

    st.sidebar.divider()
    if st.sidebar.button("Reset Filters", use_container_width=True):
        st.session_state["_reset_filters"] = True
        st.rerun()


def render_sidebar_count(filtered_n: int, total_n: int) -> None:
    """Render the filtered policy count below the filters."""
    pct = filtered_n / total_n * 100 if total_n > 0 else 0
    st.sidebar.markdown(
        f'<div style="background:{STEEL_100};border-radius:4px;padding:8px 12px;'
        f'margin:8px 0 4px 0;text-align:center;">'
        f'<div style="font-size:13px;font-weight:700;color:{NAVY};">'
        f'{filtered_n:,} / {total_n:,} policies</div>'
        f'<div style="font-size:11px;color:{STEEL_700};">{pct:.0f}% of book shown</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.divider()
    st.sidebar.caption("Waypoint Property & Casualty")
    st.sidebar.caption("Auto and Renters Retention | 2023-2025")
    st.sidebar.caption("Luciano Casillas")

# --------------------------------------------------------------------------- #
# Filter                                                                       #
# --------------------------------------------------------------------------- #

def filter_df(df: pd.DataFrame) -> pd.DataFrame:
    """Apply sidebar filter selections to the dataset."""
    tmin, tmax = st.session_state["tenure_range"]
    mask = (
        df["acquisition_channel"].isin(st.session_state["channel_sel"])
        & df["coverage_tier"].isin(st.session_state["coverage_tier_sel"])
        & df["policy_type"].isin(st.session_state["policy_type_sel"])
        & df["tenure_months"].between(tmin, tmax)
        & df["state"].isin(st.session_state["state_sel"])
    )
    return df[mask].copy()

# --------------------------------------------------------------------------- #
# KPI header                                                                   #
# --------------------------------------------------------------------------- #

def render_kpi_header(df: pd.DataFrame) -> None:
    """Render 4 KPI cards with sparklines and vertical dividers above the tab row."""
    labeled = df[df["renewed"].isin([0, 1])]
    cq = (
        labeled.groupby("cohort_quarter")
        .agg(renewal_rate=("renewed","mean"), attach_rate=("multi_product_flag","mean"),
             avg_cltv=("cltv_36mo","mean"), high_risk=("high_risk_flag","mean"))
        .reset_index().sort_values("cohort_quarter")
    )

    renewal_rate  = labeled["renewed"].mean() if len(labeled) > 0 else 0.0
    attach_rate   = df["multi_product_flag"].mean()
    avg_cltv      = df["cltv_36mo"].mean()
    high_risk_pct = df["high_risk_flag"].mean()

    def sparkline(y_vals: list, color: str) -> go.Figure:
        """Build a minimal Plotly sparkline figure with correct y-axis range."""
        if not y_vals:
            return go.Figure()
        mn, mx = min(y_vals), max(y_vals)
        fig = go.Figure(go.Scatter(
            y=y_vals, mode="lines", fill="tozeroy",
            fillcolor="rgba(0,119,179,0.10)",
            line=dict(color=color, width=2),
        ))
        fig.update_layout(
            height=50, margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor=WHITE, paper_bgcolor=WHITE,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False, range=[mn * 0.85, mx * 1.15]),
            showlegend=False,
        )
        return fig

    kpis = [
        ("12-Month Renewal Rate",     f"{renewal_rate:.1%}",  cq["renewal_rate"].tolist(), BLUE_700),
        ("Multi-Product Attach Rate",  f"{attach_rate:.1%}",   cq["attach_rate"].tolist(),  BLUE_500),
        ("Avg 36-Month CLTV",         f"${avg_cltv:,.0f}",    cq["avg_cltv"].tolist(),     GREEN_700),
        ("% High-Risk Policyholders", f"{high_risk_pct:.1%}", cq["high_risk"].tolist(),    ORANGE_700),
    ]

    # KPI labels + values as one HTML row with built-in vertical dividers (no wrapping)
    cells = ""
    for i, (label, value, _, _) in enumerate(kpis):
        border = f"border-right:1.5px solid {STEEL_300};" if i < 3 else ""
        cells += (
            f'<div style="flex:1;padding:10px 18px 4px 18px;{border}">'
            f'<div style="font-size:11px;color:{STEEL_700};font-weight:500;'
            f'text-transform:uppercase;letter-spacing:.04em;">{label}</div>'
            f'<div style="font-size:26px;font-weight:700;color:{NAVY};line-height:1.2;">{value}</div>'
            f'</div>'
        )
    st.markdown(
        f'<div style="display:flex;gap:0;margin-bottom:0;">{cells}</div>',
        unsafe_allow_html=True,
    )

    # Sparklines row: 4 equal columns below the value row
    spark_cols = st.columns(4)
    for col, (_, _, spark_data, color) in zip(spark_cols, kpis):
        with col:
            if spark_data:
                st.plotly_chart(
                    sparkline(spark_data, color),
                    use_container_width=True,
                    config={"displayModeBar": False},
                )

    st.divider()

# --------------------------------------------------------------------------- #
# Helper: takeaway strip                                                       #
# --------------------------------------------------------------------------- #

def takeaway(text: str) -> None:
    """Render a blue-bordered takeaway strip above a chart or chart pair."""
    st.markdown(
        f'<div style="background:#EEF5F8;border-left:3px solid {BLUE_500};'
        f'border-radius:4px;padding:9px 14px;margin-bottom:10px;'
        f'font-size:13px;color:{STEEL_700};line-height:1.5;">{text}</div>',
        unsafe_allow_html=True,
    )


def key_finding(text: str) -> None:
    """Render a tab-level key finding strip."""
    st.markdown(
        f'<div style="background:{STEEL_100};border-left:4px solid {BLUE_700};'
        f'padding:12px 18px;border-radius:4px;margin-bottom:18px;">'
        f'<div style="font-size:14px;font-weight:700;letter-spacing:.07em;'
        f'color:{NAVY};text-transform:uppercase;margin-bottom:5px;">Key Finding</div>'
        f'<div style="font-size:15px;color:{NAVY};line-height:1.55;">{text}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# --------------------------------------------------------------------------- #
# Helper: bar chart factory                                                    #
# --------------------------------------------------------------------------- #

def bar_chart(
    x: list, y: list, title: str, xlabel: str = "", ylabel: str = "",
    color_primary: str = BLUE_700, color_other: str = BLUE_500,
    ref_line: float | None = None, horizontal: bool = False,
    height: int = 320, text_fmt: str = ".1%",
) -> go.Figure:
    """Build a vertical or horizontal bar chart with optional reference line."""
    colors = [color_primary if v == max(y) else color_other for v in y]
    fmt    = f"{{:{text_fmt}}}"
    texts  = [fmt.format(v) for v in y]

    if horizontal:
        trace = go.Bar(y=x, x=y, orientation="h", marker_color=colors,
                       text=texts, textposition="outside")
    else:
        trace = go.Bar(x=x, y=y, marker_color=colors,
                       text=texts, textposition="outside",
                       textfont=dict(size=11, color=NAVY))

    layout = {
        **base_layout,
        "height": height,
        "title": dict(text=title, font=TITLE_FONT),
        "showlegend": False,
    }
    if xlabel:
        layout["xaxis"] = dict(title=xlabel, tickangle=0)
    if ylabel:
        layout["yaxis"] = dict(title=ylabel)

    fig = go.Figure(trace)
    fig.update_layout(**layout)
    fig.update_xaxes(tickangle=0)

    if ref_line is not None and not horizontal:
        fig.add_hline(y=ref_line, line=dict(color=STEEL_700, dash="dash", width=1.5),
                      annotation_text=f"Book avg {ref_line:.1%}",
                      annotation_position="bottom right",
                      annotation_font_color=STEEL_700)

    if horizontal:
        fig.update_xaxes(tickformat=".0%")
    else:
        fig.update_yaxes(tickformat=".0%", range=[0, max(y) * 1.28] if y else None)

    return fig

# --------------------------------------------------------------------------- #
# Tab 1: Retention Overview                                                    #
# --------------------------------------------------------------------------- #

def build_cohort_heatmap(labeled: pd.DataFrame) -> str:
    """Build an HTML cohort retention heatmap."""
    cq_rates = (
        labeled.groupby("cohort_quarter")
        .agg(cohort_size=("renewed","count"), renewal_rate=("renewed","mean"))
        .reset_index().sort_values("cohort_quarter")
    )

    def rate_to_bg(rate: float | None) -> str:
        if rate is None:
            return "#C8D3E0"
        lo, hi = (239, 245, 251), (0, 51, 102)
        t = min(max((rate - 0.60) / 0.40, 0.0), 1.0)
        r = int(lo[0] + t * (hi[0] - lo[0]))
        g = int(lo[1] + t * (hi[1] - lo[1]))
        b = int(lo[2] + t * (hi[2] - lo[2]))
        return f"#{r:02X}{g:02X}{b:02X}"

    th_style = f'style="background:{NAVY};color:{WHITE};padding:6px 10px;font-size:11px;border:0.5px solid #344;"'
    td_base  = "padding:6px 10px;text-align:center;font-size:11px;border:0.5px solid #C8D3E0;"

    html = f'<table style="border-collapse:collapse;width:100%;font-family:Inter,sans-serif;">'
    html += "<thead><tr>"
    html += f'<th {th_style}>Cohort</th>'
    for m in range(1, 13):
        html += f'<th {th_style}>M{m}</th>'
    html += "<tr></thead><tbody>"

    for _, row in cq_rates.iterrows():
        cq, size, rate12 = row["cohort_quarter"], int(row["cohort_size"]), row["renewal_rate"]
        html += "<tr>"
        html += (f'<td style="{td_base}background:{NAVY};color:{WHITE};font-weight:600;">'
                 f'{cq}<br><span style="font-size:9px;opacity:.8">n={size:,}</span></td>')
        for m in range(1, 13):
            if m < 12:
                val   = None if size < 50 else 0.98
                label = "--" if val is None else f"{val:.0%}"
            else:
                val   = rate12
                label = f"{val:.1%}"
            bg    = rate_to_bg(val)
            color = WHITE if (val or 0) >= 0.78 else NAVY
            html += f'<td style="{td_base}background:{bg};color:{color};">{label}</td>'
        html += "</tr>"

    html += "</tbody></table>"
    return html


def render_tab1(df: pd.DataFrame) -> None:
    """Render Tab 1: Retention Overview (Q01 + Q09)."""
    labeled = df[df["renewed"].isin([0, 1])]
    if len(labeled) == 0:
        st.warning("No labeled policies match the current filters.")
        return

    book_avg = labeled["renewed"].mean()

    key_finding(
        f'Book renewal rate is <b>{book_avg:.1%}</b> across {len(labeled):,} '
        f'labeled policies. Cohorts show greatest attrition at the 12-month renewal boundary, '
        f'with billing distress as the primary early predictor.'
    )

    # Cohort retention heatmap
    st.subheader("Cohort Retention Heatmap (Month 1-12)")
    takeaway(
        "Each row is a policy acquisition cohort; each column is months 1-12 since effective date. "
        "Darker blue = higher retention. Month 12 shows the actual 12-month renewal rate. "
        "Cohorts with fewer than 50 policies show a placeholder in early months."
    )
    st.markdown(build_cohort_heatmap(labeled), unsafe_allow_html=True)
    st.caption("Month 12 = actual 12-month renewal rate. Months 1-11 reflect minimal mid-term attrition from the source data.")
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        cq = labeled.groupby("cohort_quarter")["renewed"].mean().reset_index()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=cq["cohort_quarter"], y=cq["renewed"],
            mode="lines+markers+text", line=dict(color=BLUE_700, width=2.5),
            marker=dict(size=7), text=[f"{v:.1%}" for v in cq["renewed"]],
            textposition="top center", name="Renewal Rate",
        ))
        x_idx = np.arange(len(cq))
        coef  = np.polyfit(x_idx, cq["renewed"].values, 1)
        trend = np.poly1d(coef)(x_idx)
        fig.add_trace(go.Scatter(
            x=cq["cohort_quarter"], y=trend,
            mode="lines", line=dict(color=ORANGE_700, width=1.5, dash="dash"),
            name="Trend",
        ))
        fig.add_hline(y=book_avg, line=dict(color=STEEL_700, dash="dash", width=1),
                      annotation_text=f"Book avg {book_avg:.1%}", annotation_font_color=STEEL_700)
        fig.update_layout(
            **{**base_layout, "showlegend": True}, height=320,
            title=dict(text="12-Month Renewal Rate by Cohort Quarter", font=TITLE_FONT),
            xaxis=dict(title="Cohort Quarter", tickangle=0),
            yaxis=dict(title="Renewal Rate", tickformat=".0%", range=[0.60, 0.90]),
            legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.28),
        )
        st.caption("Trend line reveals whether retention is improving or deteriorating across acquisition periods.")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        sev_order = ["No Claims", "Minor", "Moderate", "Major"]
        sev = (labeled.groupby("claim_severity_band")["renewed"]
               .mean().reindex(sev_order).dropna().reset_index())
        colors = [BLUE_700 if v == sev["renewed"].max() else BLUE_500 for v in sev["renewed"]]
        fig2 = go.Figure(go.Bar(
            x=sev["claim_severity_band"], y=sev["renewed"], marker_color=colors,
            text=[f"{v:.1%}" for v in sev["renewed"]], textposition="outside",
            textfont=dict(size=11, color=NAVY),
        ))
        fig2.add_hline(y=book_avg, line=dict(color=STEEL_700, dash="dash", width=1),
                       annotation_text=f"Book avg {book_avg:.1%}", annotation_font_color=STEEL_700)
        fig2.update_layout(
            **base_layout, height=320,
            title=dict(text="Renewal Rate by Claims Severity Band", font=TITLE_FONT),
            xaxis=dict(title="Severity Band", tickangle=0),
            yaxis=dict(title="Renewal Rate", tickformat=".0%", range=[0, 1.0]),
        )
        st.caption("Minor-claim policyholders renew above book average. Major-claim policyholders lapse at the highest rate of any severity band.")
        st.plotly_chart(fig2, use_container_width=True)

    st.caption("Bars show policy count per claim payout bucket; the orange line shows the renewal rate for that group. Separates claim frequency from claim severity as renewal drivers.")
    payout_bins = [
        ("No Claim",   labeled["claim_count_12mo"] == 0),
        ("Under $1K",  (labeled["total_claim_amount"] > 0) & (labeled["total_claim_amount"] < 1000)),
        ("$1K-$3K",    labeled["total_claim_amount"].between(1000, 3000)),
        ("$3K-$7.5K",  labeled["total_claim_amount"].between(3000, 7500)),
        ("$7.5K-$15K", labeled["total_claim_amount"].between(7500, 15000)),
        ("$15K-$30K",  labeled["total_claim_amount"].between(15000, 30000)),
        ("Over $30K",  labeled["total_claim_amount"] > 30000),
    ]
    pb_labels, pb_counts, pb_rates = [], [], []
    for label, mask in payout_bins:
        sub = labeled[mask]
        if len(sub) > 20:
            pb_labels.append(label)
            pb_counts.append(len(sub))
            pb_rates.append(sub["renewed"].mean())

    fig3 = go.Figure()
    fig3.add_trace(go.Bar(x=pb_labels, y=pb_counts, name="Policy Count",
                          marker_color=BLUE_500, yaxis="y1", opacity=0.8))
    fig3.add_trace(go.Scatter(x=pb_labels, y=pb_rates, name="Renewal Rate",
                              mode="lines+markers+text",
                              line=dict(color=ORANGE_700, width=2.5),
                              marker=dict(size=9, color=ORANGE_700,
                                          line=dict(width=2, color=WHITE)),
                              text=[f"{v:.1%}" for v in pb_rates],
                              textposition="top center", yaxis="y2"))
    fig3.update_layout(
        **{**base_layout, "showlegend": True}, height=320,
        title=dict(text="Renewal Rate vs. Claim Payout Amount", font=TITLE_FONT),
        xaxis=dict(title="Claim Payout Band", tickangle=0),
        yaxis=dict(title="Policy Count", side="left"),
        yaxis2=dict(title="Renewal Rate", side="right", overlaying="y",
                    tickformat=".0%", range=[0, 1.05]),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.25),
    )
    st.plotly_chart(fig3, use_container_width=True)

# --------------------------------------------------------------------------- #
# Tab 2: Channel and Value                                                     #
# --------------------------------------------------------------------------- #

def render_tab2(df: pd.DataFrame) -> None:
    """Render Tab 2: Channel and Value (Q07 + Q04)."""
    labeled  = df[df["renewed"].isin([0, 1])]
    book_avg = labeled["renewed"].mean() if len(labeled) > 0 else 0.748
    avg_cltv = df["cltv_36mo"].mean()

    col1, col2 = st.columns(2)

    with col1:
        ch = (labeled.groupby("acquisition_channel")["renewed"]
              .mean().reindex(CHANNELS).dropna().reset_index())
        fig = bar_chart(ch["acquisition_channel"].tolist(), ch["renewed"].tolist(),
                        "12-Month Renewal Rate by Acquisition Channel",
                        ylabel="Renewal Rate", ref_line=book_avg)
        st.caption("Renewal rate by acquisition channel. AQX is the Auto Quote Explorer digital platform.")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        ch_cltv = (df.groupby("acquisition_channel")["cltv_36mo"]
                   .mean().reindex(CHANNELS).dropna().reset_index())
        colors = [BLUE_700 if v == ch_cltv["cltv_36mo"].max() else BLUE_500
                  for v in ch_cltv["cltv_36mo"]]
        fig2 = go.Figure(go.Bar(
            x=ch_cltv["acquisition_channel"], y=ch_cltv["cltv_36mo"],
            marker_color=colors,
            text=[f"${v:,.0f}" for v in ch_cltv["cltv_36mo"]],
            textposition="outside",
            textfont=dict(size=11, color=NAVY),
        ))
        fig2.add_hline(y=avg_cltv, line=dict(color=STEEL_700, dash="dash", width=1),
                       annotation_text=f"Book avg ${avg_cltv:,.0f}",
                       annotation_font_color=STEEL_700)
        fig2.update_layout(
            **base_layout, height=320,
            title=dict(text="Avg 36-Month CLTV by Acquisition Channel", font=TITLE_FONT),
            xaxis=dict(tickangle=0),
            yaxis=dict(tickprefix="$", range=[0, ch_cltv["cltv_36mo"].max() * 1.3]),
        )
        st.caption("Customer Lifetime Value (CLTV) estimated over 36 months. AQX leads on both renewal rate and value per policy.")
        st.plotly_chart(fig2, use_container_width=True)

    # Row 2: full-width AQX vs non-AQX trend
    aqx_cq = (
        labeled[labeled["cohort_quarter"] >= "2023Q3"]
        .groupby(["cohort_quarter","aqx_assisted_flag"])["renewed"]
        .mean().reset_index()
    )
    fig3 = go.Figure()
    for flag, name, color, dash in [(1,"AQX",BLUE_700,"solid"),(0,"Non-AQX",STEEL_700,"dash")]:
        sub = aqx_cq[aqx_cq["aqx_assisted_flag"] == flag].sort_values("cohort_quarter")
        if len(sub) > 0:
            fig3.add_trace(go.Scatter(
                x=sub["cohort_quarter"], y=sub["renewed"],
                mode="lines+markers", name=name,
                line=dict(color=color, width=2.5, dash=dash),
                marker=dict(size=8, color=color, line=dict(width=2, color=WHITE)),
            ))
    fig3.add_shape(type="line", x0="2023Q3", x1="2023Q3", y0=0, y1=1,
                   xref="x", yref="paper",
                   line=dict(color=RED_SOFT, width=1.5, dash="dot"))
    fig3.add_annotation(x="2023Q3", y=1.05, xref="x", yref="paper",
                        text="AQX Launch", showarrow=False,
                        font=dict(color=RED_SOFT, size=10))
    fig3.update_layout(
        **{**base_layout, "showlegend": True}, height=300,
        title=dict(text="AQX vs. Non-AQX Renewal Rate by Cohort Quarter", font=TITLE_FONT),
        xaxis=dict(title="Cohort Quarter", tickangle=0),
        yaxis=dict(title="Renewal Rate", tickformat=".0%", range=[0.55, 0.95]),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.25),
    )
    st.caption("Tracks whether the AQX retention advantage is widening, stable, or converging. The dotted reference line marks AQX launch.")
    st.plotly_chart(fig3, use_container_width=True)

    # Row 3: CLTV by tier | Agency/tenure grouped bar (shared b=80 margin for x-axis alignment)
    col3, col4 = st.columns(2)
    shared_bottom_margin = dict(l=62, r=16, t=40, b=80)

    with col3:
        tier_cltv = (df.groupby("coverage_tier")["cltv_36mo"]
                     .mean().reset_index()
                     .assign(order=lambda d: d["coverage_tier"].map(TIER_ORDER))
                     .sort_values("order"))
        colors = [BLUE_700 if v == tier_cltv["cltv_36mo"].max() else BLUE_500
                  for v in tier_cltv["cltv_36mo"]]
        fig4 = go.Figure(go.Bar(
            x=tier_cltv["coverage_tier"], y=tier_cltv["cltv_36mo"],
            marker_color=colors,
            text=[f"${v:,.0f}" for v in tier_cltv["cltv_36mo"]],
            textposition="outside",
            textfont=dict(size=11, color=NAVY),
        ))
        fig4.update_layout(
            **{**base_layout, "margin": shared_bottom_margin}, height=320,
            title=dict(text="Avg 36-Month CLTV by Coverage Tier", font=TITLE_FONT),
            xaxis=dict(tickangle=0),
            yaxis=dict(tickprefix="$", range=[0, tier_cltv["cltv_36mo"].max() * 1.3]),
        )
        st.caption("CLTV by tier translates renewal quality into dollar terms for upgrade investment decisions.")
        st.plotly_chart(fig4, use_container_width=True)

    with col4:
        at = (labeled.groupby(["agency_type","tenure_band"])["renewed"]
              .mean().reset_index().dropna())
        fig5 = go.Figure()
        for band in ["0-11 mo","12-23 mo","24-47 mo","48+ mo"]:
            sub = at[at["tenure_band"] == band]
            if len(sub) > 0:
                fig5.add_trace(go.Bar(
                    name=band, x=sub["agency_type"], y=sub["renewed"],
                    marker_color=TENURE_COLORS.get(band, BLUE_500),
                    text=[f"{v:.0%}" for v in sub["renewed"]],
                    textposition="outside",
                    textfont=dict(size=10),
                ))
        fig5.update_layout(
            **{**base_layout, "showlegend": True, "margin": shared_bottom_margin},
            height=320, barmode="group",
            title=dict(text="Renewal Rate by Agency Type and Tenure Band", font=TITLE_FONT),
            xaxis=dict(tickangle=0),
            yaxis=dict(tickformat=".0%", range=[0, 1.1]),
            legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.28),
        )
        st.caption("Color progression from light to dark represents increasing customer tenure. Longer-tenured customers renew at higher rates across all agency types.")
        st.plotly_chart(fig5, use_container_width=True)

# --------------------------------------------------------------------------- #
# Tab 3: Predictive Model                                                      #
# --------------------------------------------------------------------------- #

def render_tab3(df: pd.DataFrame, shap_df: pd.DataFrame, metrics: dict) -> None:
    """Render Tab 3: Predictive Model (Q02 + Q05)."""
    labeled = df[df["renewed"].isin([0, 1])].copy()

    st.markdown(
        f'<div style="font-size:14px;color:{STEEL_700};margin-bottom:12px;">'
        f'XGBoost Gradient Boosting | Test ROC-AUC: <b>{metrics["test_auc"]}</b> | '
        f'Train: {metrics.get("train_n", 45002):,} policies | '
        f'Test: {metrics.get("test_n", 15079):,} policies | '
        f'{metrics["feature_count"]} features</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    decile_data = metrics["decile_table"]
    deciles     = [d["decile"] for d in decile_data]
    lifts       = [d["lift_vs_baseline"] for d in decile_data]
    gains       = [d["cumulative_gain_pct"] for d in decile_data]

    with col1:
        colors = [BLUE_700 if i < 2 else BLUE_500 for i in range(10)]
        fig = go.Figure(go.Bar(
            x=deciles, y=lifts, marker_color=colors,
            text=[f"{v:.2f}x" for v in lifts],
            textposition="outside",
            textfont=dict(size=11, color=NAVY),
        ))
        fig.add_hline(y=1.0, line=dict(color=STEEL_700, dash="dash", width=1.5),
                      annotation_text="Baseline 1.0x", annotation_font_color=STEEL_700)
        fig.update_layout(
            **base_layout, height=320,
            title=dict(text="Lift by Lapse Propensity Decile", font=TITLE_FONT),
            xaxis=dict(title="Decile (D1 = Highest Risk)", tickvals=list(range(1,11)), tickangle=0),
            yaxis=dict(title="Lift vs. Baseline", range=[0, max(lifts)*1.3]),
        )
        st.caption("How many times more likely top-decile policyholders are to lapse vs. the book average. Decile 1 = highest lapse risk.")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        x_pct = [d * 10 for d in deciles]
        fig2 = go.Figure()
        fig2.add_traces([
            go.Scatter(x=x_pct, y=gains, fill="tozeroy",
                       fillcolor="rgba(0,119,179,0.10)",
                       line=dict(color=BLUE_700, width=2.5), mode="lines+markers",
                       name="Model", marker=dict(size=7)),
            go.Scatter(x=[0,100], y=[0,100], mode="lines",
                       line=dict(color=STEEL_300, dash="dash", width=1.5),
                       name="Random baseline"),
        ])
        fig2.update_layout(
            **{**base_layout, "showlegend": True}, height=320,
            title=dict(text="Cumulative Gain Curve", font=TITLE_FONT),
            xaxis=dict(title="% Policyholders Contacted", ticksuffix="%", tickangle=0),
            yaxis=dict(title="% Lapses Captured", ticksuffix="%", range=[0, 108]),
            legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.25),
        )
        st.caption("What share of all lapses a given contact rate would capture. The steeper the model line above the random baseline, the better the targeting.")
        st.plotly_chart(fig2, use_container_width=True)

    col3, col4 = st.columns(2)

    with col3:
        # Ascending sort so Plotly places the largest value at the top (first item = bottom, last = top)
        # No autorange reversal needed -- reversal would flip this and put the smallest at top
        top_shap = shap_df.nlargest(12, "mean_abs_shap").sort_values("mean_abs_shap", ascending=True)
        top_shap["label"] = top_shap["feature"].map(
            lambda f: FEATURE_LABELS.get(f, f.replace("_", " ").title())
        )
        colors   = [BLUE_700 if i == len(top_shap)-1 else BLUE_500
                    for i in range(len(top_shap))]
        fig3 = go.Figure(go.Bar(
            y=top_shap["label"], x=top_shap["mean_abs_shap"],
            orientation="h", marker_color=colors,
            text=[f"{v:.4f}" for v in top_shap["mean_abs_shap"]],
            textposition="outside",
            textfont=dict(size=10),
        ))
        fig3.update_layout(
            **{**base_layout, "margin": dict(l=205, r=24, t=40, b=40)},
            height=380,
            title=dict(text="SHAP Feature Importance", font=TITLE_FONT),
            xaxis=dict(title="Mean |SHAP Value|"),
            yaxis=dict(),
        )
        st.caption("Mean absolute SHAP value: higher = stronger influence on lapse prediction, regardless of direction. Top feature shown in blue.")
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        cm   = metrics["confusion_matrix"]
        tn, fp, fn, tp = cm["TN"], cm["FP"], cm["FN"], cm["TP"]
        cells  = [[tn, fp], [fn, tp]]
        labels = [["True Negative", "False Positive"], ["False Negative", "True Positive"]]
        colors_cm = [[NAVY, RED_SOFT], [RED_SOFT, NAVY]]
        cm_title = (
            f'<div style="font-size:13px;font-weight:700;color:{NAVY};margin-bottom:8px;">'
            f'Lapse Prediction Performance | Holdout Set</div>'
        )
        st.markdown(cm_title, unsafe_allow_html=True)
        st.caption("How well the model identifies policyholders who will not renew on the held-out test set.")
        html = '<table style="border-collapse:collapse;width:100%;font-family:Inter,sans-serif;">'
        html += '<tr><th></th>'
        for c in ["Predicted: Renews", "Predicted: Lapses"]:
            html += f'<th style="padding:8px;background:{STEEL_100};font-size:12px;">{c}</th>'
        html += '</tr>'
        for row_i, row_label in enumerate(["Actually Renewed", "Actually Lapsed"]):
            html += (f'<tr><th style="padding:8px;background:{STEEL_100};'
                     f'font-size:12px;text-align:left;">{row_label}</th>')
            for col_i in range(2):
                bg = colors_cm[row_i][col_i]
                html += (f'<td style="background:{bg};color:{WHITE};text-align:center;'
                         f'padding:16px;font-size:14px;font-weight:600;">'
                         f'{cells[row_i][col_i]:,}<br>'
                         f'<span style="font-size:11px;font-weight:400;">{labels[row_i][col_i]}</span></td>')
            html += "</tr>"
        html += "</table>"
        st.markdown(html, unsafe_allow_html=True)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0
        st.markdown(
            f'<div style="border-left:4px solid {BLUE_700};padding:8px 12px;'
            f'background:{STEEL_100};margin-top:8px;font-size:13px;">'
            f'<b>Model Summary:</b> The lapse prediction model correctly identifies '
            f'{recall:.0%} of policyholders who will not renew (Recall) and achieves '
            f'{precision:.0%} precision when flagging at-risk accounts. Targeting only the '
            f'top-risk decile captures {lifts[0]:.1f}x the lapse rate of a random '
            f'outreach strategy.</div>',
            unsafe_allow_html=True,
        )

    # Dotted divider
    st.markdown(
        f'<hr style="border:none;border-top:1.5px dotted {STEEL_300};margin:20px 0;">',
        unsafe_allow_html=True,
    )
    st.subheader("Early Warning System")

    col_hist, col_exp = st.columns(2)

    with col_hist:
        if len(labeled) > 0:
            labeled_ew = labeled.copy()
            labeled_ew["_lapse_decile"] = pd.qcut(
                -labeled_ew["lapse_prob"], q=10,
                labels=list(range(1, 11)), duplicates="drop",
            ).astype(int)
            bins     = np.linspace(0, 1, 11)
            bin_labs = [f"{bins[i]:.1f}-{bins[i+1]:.1f}" for i in range(10)]
            counts   = pd.cut(labeled_ew["lapse_prob"], bins=bins).value_counts().sort_index()
            max_count = counts.max()

            hist_html = '<div style="font-family:Inter,sans-serif;">'
            hist_html += '<div style="font-size:13px;font-weight:700;color:{};margin-bottom:6px;">Lapse Risk Score Distribution</div>'.format(NAVY)
            hist_html += '<div style="display:flex;align-items:flex-end;gap:4px;height:120px;padding:0 8px;">'
            for i, (interval, count) in enumerate(counts.items()):
                mid = (interval.left + interval.right) / 2
                pct_height = max(int(count / max_count * 100), 2)
                color = RED_SOFT if mid >= 0.7 else (ORANGE_700 if mid >= 0.4 else BLUE_500)
                hist_html += (f'<div title="{bin_labs[i]}: {count:,} policies" '
                              f'style="flex:1;height:{pct_height}%;background:{color};'
                              f'border-radius:2px 2px 0 0;cursor:pointer;"></div>')
            hist_html += '</div>'
            hist_html += (f'<div style="display:flex;justify-content:space-between;'
                          f'font-size:10px;color:{STEEL_700};padding:2px 8px;">'
                          f'<span>0.0 (Low)</span><span>0.5</span><span>1.0 (High)</span></div>')
            hist_html += (f'<div style="margin-top:8px;display:flex;gap:12px;'
                          f'font-size:12px;justify-content:center;">'
                          f'<span><span style="background:{BLUE_500};padding:2px 8px;border-radius:2px;">&nbsp;</span> Low (0.0-0.4)</span>'
                          f'<span><span style="background:{ORANGE_700};padding:2px 8px;border-radius:2px;">&nbsp;</span> Medium (0.4-0.7)</span>'
                          f'<span><span style="background:{RED_SOFT};padding:2px 8px;border-radius:2px;">&nbsp;</span> High (0.7-1.0)</span>'
                          f'</div></div>')
            st.caption("Shows the size of each intervention tier across the full book. Color bands indicate Low (blue), Medium (orange), and High (red) lapse risk.")
            st.markdown(hist_html, unsafe_allow_html=True)

    with col_exp:
        st.markdown(
            f'<div style="font-size:13px;font-weight:700;color:{NAVY};margin-bottom:8px;">'
            f'At-Risk Policyholder Profile Explorer</div>'
            f'<div style="font-size:12px;color:{STEEL_700};margin-bottom:6px;">'
            f'Compare the operational characteristics of Low, Medium, and High-Risk policyholders by selecting a risk tier below.</div>',
            unsafe_allow_html=True,
        )
        risk_band = st.radio(
            "Select risk tier:", ["High Risk", "Medium Risk", "Low Risk"],
            horizontal=True, key="risk_band_sel",
        )
        band_mask = {
            "High Risk":   labeled["model_decile"] <= 2,
            "Medium Risk": labeled["model_decile"].between(3, 7),
            "Low Risk":    labeled["model_decile"] >= 8,
        }
        seg = labeled[band_mask[risk_band]]
        if len(seg) > 0:
            tiles = [
                ("Policies in Segment", f"{len(seg):,}"),
                ("Renewal Rate",        f"{seg['renewed'].mean():.1%}"),
                ("Top Payment Method",  seg["payment_method"].mode()[0]),
                ("Avg Tenure",          f"{seg['tenure_months'].mean():.0f} mo"),
            ]
            cols_t = st.columns(4)
            for col_t, (lbl, val) in zip(cols_t, tiles):
                col_t.markdown(
                    f'<div style="border-top:3px solid {BLUE_700};padding:10px 12px;'
                    f'background:{STEEL_100};border-radius:4px;">'
                    f'<div style="font-size:12px;color:{STEEL_700};">{lbl}</div>'
                    f'<div style="font-size:20px;font-weight:700;color:{NAVY};">{val}</div></div>',
                    unsafe_allow_html=True,
                )

# --------------------------------------------------------------------------- #
# Tab 4: Cross-Sell Funnel                                                     #
# --------------------------------------------------------------------------- #

def render_tab4(df: pd.DataFrame) -> None:
    """Render Tab 4: Cross-Sell Funnel (Q10)."""
    stage1 = len(df)
    stage2 = int(df["renters_quoted_flag"].sum())
    stage3 = int(df["renters_attached_flag"].sum())
    labeled = df[df["renewed"].isin([0, 1])]
    stage4  = int(
        labeled[(labeled["renters_attached_flag"]==1) & (labeled["renewed"]==1)]["policy_id"].count()
    )

    stages = [
        ("All Auto Policies",   stage1, stage1),
        ("Renters Quoted",       stage2, stage1),
        ("Renters Attached",     stage3, stage2),
        ("Attached + Renewed",   stage4, stage3),
    ]

    takeaway(
        "Each bar width is scaled to the original policy population so bars always narrow "
        "as the cohort shrinks at each transition. The label inside each bar shows the count "
        "and the stage-to-stage conversion rate. Volume lost at each step is shown in red."
    )

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown(
            f'<div style="font-size:13px;font-weight:700;color:{NAVY};margin-bottom:8px;'
            f'font-family:Inter,sans-serif;">'
            f'Renters Attachment Funnel</div>',
            unsafe_allow_html=True,
        )
        funnel_html = '<div style="font-family:Inter,sans-serif;padding:8px 0;">'
        for i, (label, count, prev_count) in enumerate(stages):
            width     = max(int(count / stage1 * 100), 18)
            pct_prior = count / prev_count * 100 if i > 0 and prev_count > 0 else 100
            sub_label = "Starting Population" if i == 0 else f"{pct_prior:.1f}% of prior stage"
            # Center the bar using flex container
            funnel_html += (
                f'<div style="display:flex;justify-content:center;margin-bottom:4px;">'
                f'<div style="width:{width}%;background:{BLUE_700};color:{WHITE};'
                f'padding:10px 14px;border-radius:3px;text-align:center;'
                f'font-size:12px;font-weight:600;">'
                f'{label}: {count:,}<br>'
                f'<span style="font-weight:400;font-size:11px;">{sub_label}</span></div>'
                f'</div>'
            )
            if i < len(stages) - 1:
                drop = stages[i][1] - stages[i+1][1]
                funnel_html += (
                    f'<div style="color:{RED_SOFT};font-size:12px;padding:6px 8px 10px 8px;'
                    f'text-align:center;font-weight:500;">'
                    f'- {drop:,} dropped ({drop/stages[i][1]*100:.1f}%)</div>'
                )
        funnel_html += '</div>'
        st.markdown(funnel_html, unsafe_allow_html=True)

    with col2:
        attach_rate = stage3 / stage1 if stage1 > 0 else 0
        quote_rate  = stage2 / stage1 if stage1 > 0 else 0
        qtoa_rate   = stage3 / stage2 if stage2 > 0 else 0
        st.markdown(
            f'<div style="font-size:13px;font-weight:700;color:{NAVY};'
            f'font-family:Inter,sans-serif;margin-bottom:8px;">'
            f'Cross-Sell Funnel Insights</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="border-left:4px solid {STEEL_700};padding:0 16px;'
            f'font-size:13px;color:{STEEL_700};line-height:1.8;">'
            f'Of the {stage1:,} auto policyholders in this book, only {quote_rate:.0%} '
            f'were ever offered a renters quote during the quoting process. The offer gap '
            f'is the single largest lever in the funnel; closing half of it would add '
            f'thousands of policyholders to the quoted pool before any close-rate effort begins.'
            f'<br><br>'
            f'Among policyholders who receive a renters quote, {qtoa_rate:.0%} attach at bind. '
            f'This is a strong conversion rate, suggesting product appeal is high when the '
            f'conversation happens. The challenge is making that conversation happen more '
            f'consistently across channels where offer rates lag.'
            f'<br><br>'
            f'Of those who attach renters at bind, the renewal-plus-retention rate is '
            f'{stage4/stage3:.0%}. The policyholders who drop renters at first renewal '
            f'represent an attachment fragility problem: the cross-sell was made but '
            f'not defended through the renewal cycle.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    col3, col4 = st.columns(2)

    with col3:
        at = (df.groupby("agency_type")["renters_attached_flag"]
              .mean().reset_index().sort_values("renters_attached_flag", ascending=False))
        fig = bar_chart(
            at["agency_type"].tolist(), at["renters_attached_flag"].tolist(),
            "Renters Cross-Sell Rate by Agency Type", ylabel="Attach Rate",
            ref_line=df["renters_attached_flag"].mean(),
        )
        st.caption("Identifies which distribution segments to target for offer-rate improvement.")
        st.plotly_chart(fig, use_container_width=True)

    with col4:
        tb = (df.groupby("tenure_band", observed=True)["renters_attached_flag"]
              .mean().reset_index().dropna())
        fig2 = bar_chart(
            tb["tenure_band"].tolist(), tb["renters_attached_flag"].tolist(),
            "Renters Cross-Sell Rate by Customer Tenure Band", ylabel="Attach Rate",
            ref_line=df["renters_attached_flag"].mean(),
        )
        st.caption("Longer-tenured customers are meaningfully more likely to cross-sell once offered.")
        st.plotly_chart(fig2, use_container_width=True)

# --------------------------------------------------------------------------- #
# Tab 5: Financial Impact                                                      #
# --------------------------------------------------------------------------- #

def render_tab5(df: pd.DataFrame) -> None:
    """Render Tab 5: Financial Impact simulator (Q04)."""
    # Reset-flag guard: must run before any widget renders
    if st.session_state.get("_reset_sim"):
        for k in ["sim_renewal_lift", "sim_attach_lift"]:
            st.session_state.pop(k, None)
        st.session_state["sim_renewal_lift"] = 5.0
        st.session_state["sim_attach_lift"]  = 3.0
        st.session_state["_reset_sim"] = False

    labeled = df[df["renewed"].isin([0, 1])]
    current_renewal = labeled["renewed"].mean() if len(labeled) > 0 else 0.748
    avg_premium     = df["annual_premium"].mean()
    avg_cltv        = df["cltv_36mo"].mean()
    n_eligible      = len(labeled)

    # Simulator explanation with CLTV definition (sets definition for all subsequent charts)
    st.markdown(
        f'<div style="background:{STEEL_100};border-left:4px solid {BLUE_700};'
        f'border-radius:4px;padding:12px 18px;margin-bottom:16px;font-size:14px;'
        f'color:{NAVY};line-height:1.6;">'
        f'<b>How to use this simulator:</b> The two sliders below model the revenue impact '
        f'of retention and cross-sell improvements. '
        f'<b>Customer Lifetime Value (CLTV)</b> is the estimated total revenue generated '
        f'by a policy over a 36-month window, including renewal premium and renters attachment. '
        f'All projected figures update in real time as you move the sliders. '
        f'Use the Reset button to return to baseline.</div>',
        unsafe_allow_html=True,
    )

    col_sl, col_res, col_chart = st.columns([1, 1, 2])

    with col_sl:
        st.markdown(f'<div style="font-size:14px;font-weight:700;color:{NAVY};margin-bottom:8px;">Simulator Controls</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size:12px;color:{STEEL_700};margin-bottom:10px;">'
            f'Slide to set a target improvement above the current {current_renewal:.1%} renewal rate '
            f'and the current {df["renters_attached_flag"].mean():.1%} renters attachment rate.</div>',
            unsafe_allow_html=True,
        )
        renewal_lift = st.slider(
            "Renewal Rate Improvement (pp)", 0.0, 20.0, 5.0, step=0.5,
            format="%.1f%%", key="sim_renewal_lift",
        ) / 100
        attach_lift = st.slider(
            "Renters Attach Rate Improvement (pp)", 0.0, 15.0, 3.0, step=0.5,
            format="%.1f%%", key="sim_attach_lift",
        ) / 100
        if st.button("Reset to Defaults", use_container_width=True):
            st.session_state["_reset_sim"] = True
            st.rerun()

    additional_renewed  = int(n_eligible * renewal_lift)
    premium_uplift      = additional_renewed * avg_premium
    cltv_uplift         = additional_renewed * avg_cltv * 0.55
    new_attach_policies = int(len(df) * attach_lift)
    renters_revenue     = new_attach_policies * 280

    with col_res:
        st.markdown(f'<div style="font-size:14px;font-weight:700;color:{NAVY};margin-bottom:8px;">Projected Impact</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="border-left:4px solid {GREEN_700};background:{STEEL_100};'
            f'padding:14px 16px;border-radius:4px;line-height:2.8;font-size:14px;">'
            f'<b>Additional renewals:</b> {additional_renewed:,}<br>'
            f'<b>Year 2 premium uplift:</b> ${premium_uplift:,.0f}<br>'
            f'<b>CLTV uplift:</b> ${cltv_uplift:,.0f}<br>'
            f'<b>New renters policies:</b> {new_attach_policies:,}<br>'
            f'<b>Renters premium:</b> ${renters_revenue:,.0f}</div>',
            unsafe_allow_html=True,
        )

    with col_chart:
        scenarios = {
            "Current":               0,
            f"+{renewal_lift*100:.0f}pp (Selected)": premium_uplift,
            "+10pp (Maximum)":       int(n_eligible * 0.10) * avg_premium,
        }
        # Named traces so the legend is meaningful
        scenario_colors = [BLUE_500, GREEN_700, STEEL_300]
        fig = go.Figure()
        for (name, val), color in zip(scenarios.items(), scenario_colors):
            fig.add_trace(go.Bar(
                name=name, x=[name], y=[val],
                marker_color=color,
                text=[f"${val:,.0f}"], textposition="outside",
                textfont=dict(size=11, color=NAVY),
            ))
        fig.update_layout(
            **{**base_layout, "showlegend": True}, height=280,
            title=dict(text="Net Premium Uplift by Scenario", font=TITLE_FONT),
            yaxis=dict(tickprefix="$", range=[0, max(scenarios.values()) * 1.3]),
            xaxis=dict(tickangle=0),
            legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.28),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.caption("Both charts below react to the simulator settings above.")
    col_d1, col_d2 = st.columns(2)

    with col_d1:
        ch_lapsed  = (labeled[labeled["renewed"]==0]
                      .groupby("acquisition_channel").size().reindex(CHANNELS).fillna(0))
        ch_recover = (ch_lapsed * renewal_lift).astype(int)
        fig2 = go.Figure(go.Bar(
            x=ch_recover.index.tolist(), y=ch_recover.values.tolist(),
            marker_color=BLUE_700,
            text=[f"{v:,}" for v in ch_recover.values],
            textposition="outside",
            textfont=dict(size=11, color=NAVY),
        ))
        fig2.update_layout(
            **{**base_layout, "margin": dict(l=62, r=16, t=40, b=60)}, height=300,
            title=dict(text="Additional Renewing Policies by Channel", font=TITLE_FONT),
            xaxis=dict(tickangle=0),
            yaxis=dict(title="Policies Recovered"),
        )
        st.caption("Policies recovered by channel at the selected renewal rate lift.")
        st.plotly_chart(fig2, use_container_width=True)

    with col_d2:
        tier_cltv = (df.groupby("coverage_tier")["cltv_36mo"].mean()
                     .reset_index().assign(order=lambda d: d["coverage_tier"].map(TIER_ORDER))
                     .sort_values("order"))
        gain = tier_cltv["cltv_36mo"] * renewal_lift * 0.55
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(
            name="Current CLTV", x=tier_cltv["coverage_tier"],
            y=tier_cltv["cltv_36mo"], marker_color=BLUE_700,
        ))
        fig3.add_trace(go.Bar(
            name="Projected Gain", x=tier_cltv["coverage_tier"],
            y=gain, marker_color="rgba(33,122,60,0.65)",
        ))
        fig3.update_layout(
            **{**base_layout, "showlegend": True,
               "margin": dict(l=62, r=16, t=40, b=60)},
            height=300, barmode="stack",
            title=dict(text="Current vs. Projected CLTV by Coverage Tier", font=TITLE_FONT),
            xaxis=dict(tickangle=0),
            yaxis=dict(tickprefix="$"),
            legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.25),
        )
        st.caption("Current CLTV vs. projected gain by coverage tier at the selected renewal rate lift.")
        st.plotly_chart(fig3, use_container_width=True)

# --------------------------------------------------------------------------- #
# Tab 6: Recommendations                                                       #
# --------------------------------------------------------------------------- #

def render_tab6() -> None:
    """Render Tab 6: Recommendations (tiered action plan)."""
    st.markdown(
        f'<div style="background:{STEEL_100};border-radius:6px;padding:14px 18px;'
        f'margin-bottom:20px;font-size:15px;line-height:1.7;">'
        f'The following recommendations are derived from the retention, channel quality, '
        f'billing behavior, and cross-sell analyses. Each action is sized by its estimated '
        f'revenue impact and operational effort. Priorities assume a 90-day implementation window '
        f'beginning from the date of this report.</div>',
        unsafe_allow_html=True,
    )

    tiers = [
        ("Immediate Actions (0-30 Days)", ORANGE_700, [
            ("Deploy Billing-Based Lapse Alert",
             "Route policies with missed_payment_count >= 1 or nsf_flag = 1 to a 15-day "
             "outreach queue before the 60-day renewal window opens.",
             ["Estimated impact: $1.2M+ in retained premium",
              "Data: billing summary table; no new modeling required",
              "Owner: retention ops + data team"]),
            ("AQX Channel Expansion Pitch",
             "AQX delivers 82% renewal vs. 68% for Direct Web. Recommend accelerating "
             "AQX onboarding for high-potential independent agency partners.",
             ["Estimated impact: 5-8pp renewal lift for converted agencies",
              "Metric to track: AQX attach rate per agency cohort",
              "Owner: agency partnerships + product"]),
        ]),
        ("Short-Term Actions (30-90 Days)", BLUE_700, [
            ("Renters Cross-Sell Campaign for Quoted-but-Not-Attached",
             "Policyholders were quoted renters but did not attach. A targeted "
             "win-back sequence in months 3-6 of the policy term can capture this gap.",
             ["Estimated impact: $7.8M at $280/yr avg renters premium",
              "Segment: renters_quoted_flag=1, renters_attached_flag=0",
              "Owner: direct marketing + agency ops"]),
            ("Cohort-Specific Retention Playbook",
             "Bottom-quintile cohorts by renewal rate share a billing distress signature. "
             "Build a cohort-level early warning that triggers intervention at month 8.",
             ["Estimated impact: 2-3pp lift in bottom-quintile cohort renewal rates",
              "Requires: monthly cohort tracking dashboard",
              "Owner: analytics + retention ops"]),
        ]),
        ("Strategic Investments (90+ Days)", NAVY, [
            ("Multi-Product Bundling Incentive Program",
             "Auto + Renters policyholders renew at a higher rate. Expanding bundling "
             "incentives (waived fees, discounted renters premium) should increase the "
             "attachment rate and reduce overall attrition.",
             ["Estimated impact: Each 1pp attach rate gain = $2.8M in multi-year CLTV",
              "Pilot: Independent agency channel first (highest cross-sell gap)",
              "Owner: product + pricing + agency partnerships"]),
            ("Lapse Warning Score Production Deployment",
             "The gradient boosting model achieves strong lift in the top decile. "
             "Deploying to a real-time scoring endpoint enables proactive outreach "
             "before the 60-day renewal window, when intervention still affects decisions.",
             ["Estimated impact: 3-5pp improvement in at-risk segment renewal rate",
              "Requires: model serving infrastructure + CRM integration",
              "Owner: data engineering + retention ops + ML platform"]),
        ]),
    ]

    for title, color, cards in tiers:
        st.markdown(
            f'<h4 style="color:{color};border-bottom:2px solid {color};'
            f'padding-bottom:4px;margin-top:24px;">{title}</h4>',
            unsafe_allow_html=True,
        )
        cols = st.columns(2)
        for col, (card_title, card_body, bullets) in zip(cols, cards):
            bullets_html = "".join(f"<li>{b}</li>" for b in bullets)
            col.markdown(
                f'<div style="background:{STEEL_100};border-radius:6px;'
                f'padding:16px 18px;height:100%;">'
                f'<div style="font-weight:700;color:{NAVY};font-size:20px;'
                f'margin-bottom:8px;">{card_title}</div>'
                f'<div style="font-size:18px;color:#333;margin-bottom:10px;">{card_body}</div>'
                f'<ul style="font-size:17px;color:{STEEL_700};margin:0;padding-left:18px;">'
                f'{bullets_html}</ul></div>',
                unsafe_allow_html=True,
            )

# --------------------------------------------------------------------------- #
# Tab 7: Healthcare Application                                                #
# --------------------------------------------------------------------------- #

def render_tab7() -> None:
    """Render Tab 7: Healthcare cross-industry translation."""
    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown(
            f'<div style="font-size:13px;font-weight:700;color:{NAVY};margin-bottom:8px;">'
            f'From Insurance to Healthcare: How the Metrics Map</div>',
            unsafe_allow_html=True,
        )
        rows = [
            ("12-Month Renewal Rate",    "Annual Patient Retention Rate"),
            ("Lapse Risk Score",          "Early Readmission Risk Score"),
            ("Missed Payment Count",      "Missed Appointment Count"),
            ("Payment Consistency Score", "Care Plan Adherence Score"),
            ("Multi-Product Attachment",  "Preventive Care Enrollment"),
            ("Coverage Tier Downgrade",   "Care Plan Step-Down"),
            ("Claims Severity Band",      "Procedure Complexity or Chronic Burden"),
            ("AQX-Assisted Acquisition",  "Patient Portal Engagement Flag"),
        ]
        table_html = (
            f'<table style="width:100%;border-collapse:collapse;font-family:Inter,sans-serif;">'
            f'<thead><tr>'
            f'<th style="background:{NAVY};color:{WHITE};padding:8px 12px;font-size:12px;text-align:left;">What We Track in Insurance</th>'
            f'<th style="background:{NAVY};color:{WHITE};padding:6px 8px;font-size:12px;text-align:center;width:32px;"></th>'
            f'<th style="background:{NAVY};color:{WHITE};padding:8px 12px;font-size:12px;text-align:left;">Healthcare Equivalent</th>'
            f'</tr></thead><tbody>'
        )
        for i, (ins, health) in enumerate(rows):
            bg = STEEL_100 if i % 2 == 0 else WHITE
            table_html += (
                f'<tr style="background:{bg};">'
                f'<td style="padding:8px 12px;font-size:12px;border-bottom:0.5px solid {STEEL_300};">{ins}</td>'
                f'<td style="padding:6px 8px;font-size:14px;text-align:center;color:{BLUE_700};font-weight:700;border-bottom:0.5px solid {STEEL_300};">&#8594;</td>'
                f'<td style="padding:8px 12px;font-size:12px;border-bottom:0.5px solid {STEEL_300};">{health}</td>'
                f'</tr>'
            )
        table_html += '</tbody></table>'
        st.markdown(table_html, unsafe_allow_html=True)

    with col2:
        st.markdown("**Three Transferable Levers**")
        levers = [
            ("1", "Behavioral Signal Monitoring",
             "Payment and appointment patterns provide 60-90 days of leading-indicator "
             "warning before churn or readmission. Identical pipeline architecture works in both domains.",
             "1.59x lift in top risk decile"),
            ("2", "Multi-Product / Preventive Bundle",
             "Bundled products (renters + auto; preventive care + chronic management) "
             "increase switching costs and improve long-term retention in both domains.",
             "+28% retention for bundled vs. single product"),
            ("3", "Channel Quality Differential",
             "Digital-assist channels (AQX; patient portal) produce higher-quality customers "
             "with lower attrition across both domains. Investment compounds over cohort time.",
             "AQX: 82% vs. 68% Direct Web renewal"),
        ]
        for num, title, body, stat in levers:
            st.markdown(
                f'<div style="background:{STEEL_100};border-radius:6px;padding:12px 14px;margin-bottom:10px;">'
                f'<div style="font-weight:700;color:{NAVY};font-size:13px;">{num}. {title}</div>'
                f'<div style="font-size:12px;color:#444;margin:6px 0;">{body}</div>'
                f'<div style="background:{GREEN_700};color:{WHITE};font-size:11px;'
                f'padding:3px 8px;border-radius:3px;display:inline-block;">{stat}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        f'<div style="background:{NAVY};color:{WHITE};padding:18px 24px;'
        f'border-radius:6px;margin-top:20px;font-size:13px;line-height:1.8;">'
        f'<b>Portability:</b> This analysis was built on synthetic insurance policies, '
        f'but the full pipeline (data model, feature engineering, gradient boosting classification, '
        f'SHAP attribution, and decile-based intervention prioritization) transfers directly to '
        f'healthcare member retention, patient readmission prevention, and subscription churn '
        f'with only domain-specific feature renaming. The methodology is industry-neutral.</div>',
        unsafe_allow_html=True,
    )

# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #

def main() -> None:
    """Orchestrate the dashboard: sidebar, KPI header, and 7 tabs."""
    init_session_state()

    df = load_data()
    shap_df, metrics = load_model_assets()

    render_sidebar(df)

    st.markdown(
        f'<h2 style="color:{NAVY};margin-bottom:2px;">Waypoint P&C | Retention Analytics</h2>'
        f'<p style="color:{STEEL_700};font-size:13px;margin-top:0;">'
        f'Auto and Renters Policyholder Renewal | 2023-2025 | {len(df):,} Policies</p>',
        unsafe_allow_html=True,
    )

    filtered = filter_df(df)

    # Render filter count in sidebar after filtering
    render_sidebar_count(len(filtered), len(df))

    if len(filtered) == 0:
        st.error("No policies match the current filter combination. Adjust the sidebar filters.")
        return

    render_kpi_header(filtered)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "Retention Overview",
        "Channel and Value",
        "Predictive Model",
        "Cross-Sell Funnel",
        "Financial Impact",
        "Recommendations",
        "Healthcare Application",
    ])

    with tab1:
        render_tab1(filtered)
    with tab2:
        render_tab2(filtered)
    with tab3:
        render_tab3(filtered, shap_df, metrics)
    with tab4:
        render_tab4(filtered)
    with tab5:
        render_tab5(filtered)
    with tab6:
        render_tab6()
    with tab7:
        render_tab7()


if __name__ == "__main__":
    main()
