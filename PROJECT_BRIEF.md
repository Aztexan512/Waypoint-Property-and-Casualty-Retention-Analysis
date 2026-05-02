# Waypoint Retention Analytics -- Project Brief
**Company:** Waypoint Property & Casualty
**Role Target:** Data Analyst II -- Direct Agency Advancement
**Author:** Luciano Casillas
**Date:** 2026-05-02
**Project Path:** C:\Users\lucia\OneDrive\Portfolio Projects\waypoint-retention-analytics

---

## 1. Business Context

Waypoint Property & Casualty is a regional direct-to-consumer auto and renters insurer
operating across 14 states with approximately 290,000 active policies and $380M in written
premium. The company is growing its agency channel through a new digital quoting platform
(the Auto Quote Explorer, or AQX) and managing a hybrid direct/agency distribution model
with four agency types: Independent, Captive, Digital Partner, and Direct.

As the Data Analyst II on the Direct Analytics team, I have been asked to analyze
policyholder retention behavior and household lifetime value across a 36-month book of
90,000 auto and renters policies. The analytical mandate is to identify at-risk renewal
segments, quantify the revenue impact of the multi-product attachment gap and digital
channel quality differential, and support the agency channel's customer quality strategy
by delivering a predictive lapse-warning score deployable before the 60-day renewal window.

---

## 2. Approved Business Questions

**Q01.** What do first-year renewal rates look like across policy cohorts by acquisition
quarter, and which cohorts show the steepest attrition before the 12-month mark?
- Business problem: Where should retention investment be concentrated across the lifecycle?

**Q02.** Which policyholder characteristics are most predictive of non-renewal at 12 months,
and how early in the policy term can a lapse be predicted?
- Business problem: Who should receive proactive retention outreach, and when?

**Q04.** How does policyholder lifetime value vary by acquisition channel and coverage tier,
and which segments generate the most revenue per policy over a 36-month window?
- Business problem: Where should customer acquisition and retention investment be concentrated?

**Q05.** Which billing and payment behaviors correlate most strongly with early lapse, and
can a lapse warning score be built from them?
- Business problem: Can we intervene before a lapse becomes a cancellation?

**Q07.** Do policyholders acquired through the digital quoting channel show different
first-year retention curves than those acquired through traditional agency channels?
- Business problem: Does the AQX channel produce higher-quality, more-retained customers?

**Q09.** What is the relationship between claims history and renewal behavior, and does it
differ by coverage tier and acquisition channel?
- Business problem: Should retention strategy differ for policyholders with prior claims?

**Q10.** What is the auto-to-renters cross-sell conversion rate by agency type and customer
tenure band, and where does the cross-sell funnel drop off?
- Business problem: Which agency segments and customer cohorts represent the highest-yield
  cross-sell opportunity?

---

## 3. Data Design

- **Row count:** 90,000 policies
- **Time window:** 36 months (2023-01-01 to 2025-12-31)
- **Renewal window:** 12 months from effective date; target applies to policies effective
  on or before 2024-12-31 (~72,000 policies with known renewal outcome)
- **Target column:** renewed (1 = renewed at 12 months, 0 = lapsed or cancelled)
- **Seed:** 42

**Source tables:** 5 tables reflecting how data actually lives in a real insurance system.
Joined into one denormalized analysis-ready CSV at policy grain.

---

## 4. Source Table Schema

### dim_customer
- Grain: One row per policyholder account (~72,000 rows)
- Key columns: customer_id, age_band, state, metro_area, homeowner_flag,
  prior_insurance_flag, years_with_carrier, acquisition_channel, agency_type,
  aqx_assisted_flag
- Joins to: fact_policies on customer_id

### fact_policies
- Grain: One row per issued policy (90,000 rows) -- primary analysis table
- Key columns: policy_id, customer_id, policy_type, coverage_tier, annual_premium,
  effective_date, cohort_quarter, tenure_months, multi_product_flag, renters_quoted_flag,
  renters_attached_flag, renewed (target)
- Joins to: dim_customer, fact_renewals, fact_billing_summary, fact_claims on policy_id

### fact_renewals
- Grain: One row per 12-month renewal event (~72,000 rows)
- Key columns: renewal_id, policy_id, customer_id, renewal_decision_date, renewed,
  days_to_decision, renewal_premium_change_pct, outreach_contact_flag, renewal_month_label
- Joins to: fact_policies on policy_id

### fact_billing_summary
- Grain: One row per policy, billing behavior summary over term (90,000 rows)
- Key columns: policy_id, payment_method, billing_frequency, missed_payment_count_12mo,
  days_past_due_max, payment_consistency_score, nsf_flag, late_pay_flag_last_3mo
- Joins to: fact_policies on policy_id

### fact_claims
- Grain: One row per claim filed (~19,000 rows)
- Key columns: claim_id, policy_id, customer_id, claim_date, claim_type, claim_amount,
  claim_severity_band, at_fault_flag, claim_status, days_to_close
- Joins to: fact_policies on policy_id

---

## 5. Denormalized CSV Column Reference

**File:** data/waypoint_retention.csv | **Grain:** one row per policy | **Rows:** 90,000

| Column | Type | Description |
|--------|------|-------------|
| customer_id | string | Policyholder account identifier |
| age_band | string | Age group (18-25, 26-35, 36-45, 46-55, 56-65, 65+) |
| state | string | State of residence (14 states) |
| metro_area | string | Metro area or Rural designation |
| homeowner_flag | int | 1 = owns home |
| prior_insurance_flag | int | 1 = had prior insurance at bind |
| years_with_carrier | float | Tenure in years at policy effective date |
| acquisition_channel | string | Agency Portal, AQX, Direct Web, Phone, Referral |
| agency_type | string | Independent, Captive, Digital Partner, Direct |
| aqx_assisted_flag | int | 1 = quote completed via AQX platform |
| policy_id | string | Policy identifier |
| policy_type | string | Auto Only, Auto + Renters |
| coverage_tier | string | Liability Only, Standard, Premium, Elite |
| annual_premium | float | Premium at policy effective date ($) |
| effective_date | date | Policy start date |
| cohort_quarter | string | Acquisition cohort (2023Q1-2025Q4) |
| tenure_months | int | Months since customer's first policy with carrier |
| multi_product_flag | int | 1 = holds both auto and renters |
| renters_quoted_flag | int | 1 = renters was offered at quote |
| renters_attached_flag | int | 1 = renters policy bound |
| payment_method | string | Credit Card, Bank Draft, Check, Digital Wallet |
| billing_frequency | string | Monthly, Semi-Annual, Annual |
| missed_payment_count | int | Missed payments in first 12 months |
| days_past_due_max | int | Longest days past due in first 12 months |
| payment_consistency | float | Score 0-100 (100 = no missed payments) |
| nsf_flag | int | 1 = had a returned payment |
| late_pay_flag_3mo | int | 1 = late payment in last 3 months |
| has_claim_12mo | int | 1 = filed at least one claim |
| claim_count_12mo | int | Number of claims in first 12 months |
| total_claim_amount | float | Total claim payout in first 12 months ($) |
| claim_severity_band | string | None, Minor, Moderate, Major |
| days_since_last_claim | int | Days since most recent claim (null if no claims) |
| renewed | int | TARGET: 1 = renewed, 0 = lapsed |
| renewal_month_label | string | YYYYMM of renewal decision |
| days_to_decision | int | Days from renewal offer to decision |

**Leakage-prone columns (exclude from model training):**
- cltv_36mo: HIGH -- derived from full 36-month outcome
- renewal_premium_change_pct: HIGH -- only known after renewal decision
- post_renewal_coverage_tier: HIGH -- only known after renewal decision
- outreach_contact_flag: CONDITIONAL -- legitimate only with strict date guard

---

## 6. Dashboard Spec

- **Archetype:** Custom (Hybrid A/B)
- **Title:** Waypoint Property and Casualty | Retention Analytics
- **Subtitle:** Auto and Renters Policyholder Renewal | 2023-2025 | 90,000 Policies

**KPI Header (4 cards, above all tabs):**
1. 12-Month Renewal Rate | sparkline over cohort_quarter
2. Multi-Product Attach Rate | sparkline over cohort_quarter
3. Avg 36-Month CLTV | sparkline over cohort_quarter
4. % Policyholders High-Risk | sparkline over cohort_quarter

**Sidebar Filters:**
1. Acquisition Channel (multiselect)
2. Coverage Tier (multiselect)
3. Policy Type (multiselect)
4. Customer Tenure (slider, 0-48 months)
5. State (multiselect, 14 states)

**Tabs:** 7 tabs (see approved spec)
1. Retention Overview (Q01 + Q09)
2. Channel and Value (Q07 + Q04)
3. Predictive Model (Q02 + Q05)
4. Cross-Sell Funnel (Q10)
5. Financial Impact (Q04 simulator)
6. Recommendations
7. Healthcare Application

---

## 7. Simulation Parameters

```yaml
dataset:
  row_count: 90000
  time_window_start: "2023-01-01"
  time_window_end: "2025-12-31"
  seed: 42
  target_column: renewed
  renewal_window_months: 12

company:
  name: "Waypoint Property & Casualty"
  states: 14
  agency_types: ["Independent", "Captive", "Digital Partner", "Direct"]
  channels: ["Agency Portal", "AQX", "Direct Web", "Phone", "Referral"]
  aqx_launch_quarter: "2023Q3"
  coverage_tiers: ["Liability Only", "Standard", "Premium", "Elite"]

key_rates:
  overall_renewal_rate: 0.748
  multi_product_attach_rate: 0.283
  aqx_renewal_rate: 0.83
  direct_web_renewal_rate: 0.68
  high_risk_pct: 0.182
  avg_annual_premium: 1580
  avg_cltv_36mo: 1842
```

---

## 8. WAT Folder Structure

```
waypoint-retention-analytics/
├── PROJECT_BRIEF.md
├── CLAUDE_CODE_KICKOFF_PROMPT.md
├── PATTERN_LOG.md
├── PROJECT_MANIFEST.json
├── _build/
│   ├── workflows/
│   │   ├── 01_data_model/
│   │   │   ├── ddl/
│   │   │   ├── erd/
│   │   │   └── docs/
│   │   ├── 02_data_generation/
│   │   │   ├── generators/
│   │   │   ├── config/
│   │   │   └── outputs/
│   │   ├── 03_sql_analysis/
│   │   │   ├── q01_cohort_retention/
│   │   │   ├── q02_renewal_prediction/
│   │   │   ├── q04_cltv_analysis/
│   │   │   ├── q05_lapse_warning/
│   │   │   ├── q07_channel_retention/
│   │   │   ├── q09_claims_renewal/
│   │   │   └── q10_crosssell_funnel/
│   │   └── 04_modeling/
│   │       ├── eda/
│   │       ├── modeling/
│   │       └── outputs/
│   ├── agents/
│   └── tools/
│       ├── raw_tables/
│       └── reference/
```

---

## 9. GitHub Repo Structure

```
waypoint-retention-analytics/          (repo root)
├── app.py
├── requirements.txt
├── README.md
├── portfolio_page.html
├── .gitignore
├── .streamlit/
│   └── config.toml
├── data/
│   ├── waypoint_retention.csv
│   ├── data_dictionary.md
│   └── schema/
│       ├── erd.md
│       └── table_definitions.md
├── scripts/
│   └── 01_generate_data.py
├── sql/
│   └── waypoint_retention_analysis.sql
├── notebooks/
│   └── waypoint_retention_analysis.ipynb
└── docs/
    └── PROJECT_OVERVIEW.md
```

---

## 10. Phase Roadmap

| Phase | Description | Produces |
|-------|-------------|---------|
| Phase 1 | Data Model | DDL for 5 source tables, ERD diagram, data dictionary, seed config |
| Phase 2 | Data Generation | 5 source table CSVs, denormalized waypoint_retention.csv, metadata JSON |
| Phase 3 | SQL Analysis | 7 query files (one per approved question), Snowflake-compatible |
| Phase 4 | Python Notebook | EDA, Gradient Boosting model, SHAP, decile analysis, IPYNB |
| Phase 5 | Streamlit Dashboard | app.py (7 tabs, KPI header, sidebar, simulator) |
| Phase 6 | Documentation | README.md, PROJECT_OVERVIEW.md, INTERVIEW_PREP.md, portfolio_page.html |
| Phase 7 | Git Init | Promote GitHub files to root, write .gitignore, run quality gates, push |
