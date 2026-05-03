# 🏢 Waypoint P&C | Retention Analytics

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-deployed-brightgreen)
![SQL](https://img.shields.io/badge/SQL-Snowflake--compatible-lightgrey)
![Model](https://img.shields.io/badge/Model-XGBoost-orange)
![SHAP](https://img.shields.io/badge/SHAP-Explainability-blueviolet)
![Plotly](https://img.shields.io/badge/Plotly-Visualization-3F4F75)
![Jupyter](https://img.shields.io/badge/Jupyter-Notebook-F37626)

Analyzes 60,081 synthetic auto and renters insurance policies to identify a **$5.4M renters cross-sell opportunity**, quantify an **8.8pp AQX channel retention premium**, and predict first-year policyholder lapse risk with a gradient boosting model achieving **1.59x lift** in the top risk decile.

---

## 📋 Table of Contents

- [Project Background](#-project-background)h
- [Executive Summary](#-executive-summary)
- [Insights Deep Dive](#-insights-deep-dive)
- [Recommendations](#-recommendations)
- [Data Structure](#-data-structure)
- [Setup](#-setup)
- [Live Dashboard](#-live-dashboard)
- [File Structure](#-file-structure)
- [Assumptions and Caveats](#-assumptions-and-caveats)
- [Author](#-author)

---

## 🏢 Project Background

Waypoint Property and Casualty is a regional direct-to-consumer auto and renters insurer operating across 14 states with approximately 290,000 active policies and $380M in written premium. The company is growing its agency channel through the Auto Quote Explorer (AQX), a digital quoting platform launched in mid-2023 to reduce manual quoting errors and improve agency production health.

The Direct Analytics team was asked to answer a core question: are we retaining the right policyholders, and are we doing everything we can to keep them? That mandate covers three distinct problems. First, understanding which policyholders are most likely to lapse before the 12-month renewal window closes, and whether behavioral signals in billing history can predict that outcome early enough to intervene. Second, determining whether the AQX platform is producing higher-quality customers than traditional channels, and if so, how much the quality difference is worth over a 36-month policy lifecycle. Third, mapping the auto-to-renters cross-sell funnel to identify where the offer gap sits and what closing it would be worth in annual premium.

This project delivers a 7-tab interactive dashboard built on 60,081 synthetic policies, a gradient boosting lapse prediction model with SHAP attribution, 7 Snowflake-compatible SQL queries, and a financial impact simulator that lets stakeholders model the revenue effect of retention and cross-sell improvements in real time.

---

## 📊 Executive Summary

- Billing distress (missed payments or a returned payment) predicts lapse at **1.6x** the rate of clean billing histories, affecting **16%** of the policy book. A policyholder with billing distress and no claims still lapses at a higher rate than a clean-billing policyholder with a major claim.
- AQX-assisted policyholders renew at **81.8%** vs. **73.0%** for non-AQX policyholders, an **8.8pp gap** that has remained stable since platform launch, confirming a structural quality advantage rather than a selection effect.
- **43%** of auto policyholders (38,865) were never offered a renters quote. Of those offered, **49.6%** attach. Closing half the offer gap would generate approximately **$5.4M** in additional annual renters premium at the current close rate.
- Multi-product (auto and renters) policyholders renew at **78.4%** vs. **73.4%** for auto-only, a **5pp retention premium** that compounds across each renewal cycle, making each new renters attachment both a revenue event and a renewal rate investment.
- The lapse prediction model (AUC: **0.61**, XGBoost) captures **28%** of all lapses by contacting the top 20% of the book. At **$18** per outreach contact, the top-decile intervention cost is recovered by preventing fewer than 2 lapses at average annual premium.
- Cohort renewal rates are stable across all **8 acquisition cohorts** from 2023 through 2024, ranging from 74.3% to 75.7%, with no single quarter showing significant deterioration.

---

## 🔍 Insights Deep Dive

### 1. Billing Behavior Outpredicts Claims History as a Lapse Signal

Policyholders with billing distress lapse at 36% vs. 23% for those with clean billing histories, a 19pp spread. The same comparison across claims severity bands (No Claims to Major) produces only a 7pp spread. Billing distress is the actionable lever because it surfaces 60 or more days before the renewal window, when intervention can still influence the decision.

<!-- SCREENSHOT REQUIRED: screenshots/overview.png -->
<!-- Capture: Retention Overview tab -- 100% stacked bar pair (Billing Behavior left, Claims Severity right), both charts visible -->
![Renewed vs. Lapsed by Billing Behavior](screenshots/Renewed%20vs.%20Lapsed%20by%20Billing%20Behavior.png)![Renewed vs. Lapsed by Claims Severity](screenshots/Renewed%20vs.%20Lapsed%20by%20Claims%20Severity.png)

### 2. The AQX Channel Produces a Structural Quality Advantage

AQX-assisted policyholders carry $1,906 in average 36-month Customer Lifetime Value (CLTV), $131 above the lowest-performing channel. The 8.8pp renewal rate premium is not concentrated in early cohorts. It has widened consistently since AQX launch, which rules out a selection effect and confirms the platform itself drives better customer outcomes. Accelerating AQX onboarding is the single highest-ROI lever in the direct agency book.

<!-- SCREENSHOT REQUIRED: screenshots/channel_value.png -->
<!-- Capture: Channel and Value tab -- AQX vs. Non-AQX trend line chart and CLTV by channel bar chart visible -->
![AQX vs. Non-AQX Renewal Rate by Cohort Quarter](screenshots/AQX%20vs.%20Non-AQX%20Renewal%20Rate%20by%20Cohort%20Quarter.png)![Avg 36-Month CLTV by Acquisition Channel](screenshots/Avg%2036-Month%20CLTV%20by%20Acquisition%20Channel.png)

### 3. A 43% Offer-Rate Gap Drives the Renters Cross-Sell Opportunity

The renters attachment funnel drops at the offer stage, not the close stage. Of the 38,865 auto policyholders who were never quoted renters, approximately 19,277 would have attached at the current 49.6% close rate. Cross-sell rates are nearly uniform across agency types (27.9% to 28.6%), which means the opportunity is not concentrated in any one channel. Solving the offer rate is the priority, not improving the pitch.

<!-- SCREENSHOT REQUIRED: screenshots/crosssell_funnel.png -->
<!-- Capture: Cross-Sell Funnel tab -- CSS funnel and both cross-sell bar charts visible -->
![Renters Attachment Funnel](screenshots/Renters%20Attahchment%20Funnel.png)![Renters Cross-Sell Rate by Agency Type](screenshots/Renters%20Cross-Sell%20Rate%20by%20Agency%20Type.png)
![Renters Cross-Sell Rate by Tenure Band](screenshots/Renters%20Cross-Sell%20Rate%20by%20Tenure%20Band.png)

### 4. The Lapse Prediction Model Enables Cost-Effective Targeted Outreach

The gradient boosting model identifies the top-risk 10% of policyholders at 1.59x the book lapse rate. Payment Consistency Score and Acquisition Channel are the two strongest SHAP predictors, meaning lapse risk is driven by behavioral signals that can be monitored in real time rather than static demographic features. At $18 per contact, reaching the full top decile costs approximately $27,000, recovered by preventing fewer than 2 lapses at average annual premium of $1,580.

<!-- SCREENSHOT REQUIRED: screenshots/predictive_model.png -->
<!-- Capture: Predictive Model tab -- Lift chart (left) and SHAP Feature Importance (right) both visible -->
![Lift by Lapse Propensity Decile](screenshots/Lift%20by%20Lapse%20Propensity%20Decile.png)![SHAP Feature Importance](screenshots/SHAP%20Feature%20Importance.png)

---

## 💡 Recommendations

### Immediate Actions (0-30 Days)

**Deploy Billing-Based Lapse Alert**
Route policies with 1 or more missed payments or a returned payment to a 15-day outreach queue before the 60-day renewal window opens. Billing-distressed policyholders lapse at 1.6x the book rate and the signal is available in the billing summary table with no new modeling required.

**Build the AQX Business Case for Agency Onboarding**
AQX-assisted policyholders renew at 81.8% vs. 73.0% for non-AQX and carry $131 more CLTV per policy over 36 months. Beyond retention, AQX reduces manual quoting errors, lowering E&O exposure for appointed agents. Present this data to agency partnership teams to accelerate onboarding conversations.

### Short-Term Actions (30-90 Days)

**Renters Offer-Rate Campaign for Unquoted Auto Policyholders**
43% of auto policyholders were never offered renters coverage. The close rate among those offered is already 49.6%, so the bottleneck is in offer volume, not persuasion. Prioritize the 38,865 unquoted policyholders by coverage tier and tenure for a targeted outreach sequence in months 3-6 of the policy term.

**Cohort-Based Renewal Monitoring with Month-8 Alert**
Billing distress signals are detectable 4-5 months before the 12-month renewal window. Building a monthly cohort refresh that flags policyholders with deteriorating billing scores at month 8 enables early intervention before the renewal conversation becomes reactive.

### Strategic Investments (90+ Days)

**Multi-Product Bundling Incentive Program**
Multi-product policyholders renew at 78.4% vs. 73.4% for auto-only, a 5pp retention premium. Bundling incentives (waived fees, discounted renters premium) should be validated against Waypoint's own claims data before pricing, as multi-line households typically carry lower loss ratios than mono-line households.

**Lapse Warning Score Production Deployment**
The model achieves 1.59x lift in the top decile with payment behavior as the dominant predictor. Before deployment, review for compliance with NAIC guidelines on behavioral data use in customer-facing decisions. Payment history used for retention outreach (not underwriting) is generally permissible, but legal review is advisable before the score influences any policy continuation decision.

---

## 🗂️ Data Structure

All data in this project is synthetic. The analysis-ready dataset (`data/waypoint_retention.csv`) was generated from 5 source tables that reflect how this data actually lives in a real personal lines insurance system.

**Dataset:** 60,081 rows | Seed: 42 | Time window: 2023-01-01 to 2024-12-31 | Target: `renewed` (1 = renewed at 12 months)

| Column | Type | Description |
|---|---|---|
| `customer_id` | string | Policyholder account identifier |
| `age_band` | string | Customer age group (18-25 through 65+) |
| `state` | string | State of residence (14 states) |
| `acquisition_channel` | string | Agency Portal, AQX, Direct Web, Phone, Referral |
| `agency_type` | string | Independent, Captive, Digital Partner, Direct |
| `aqx_assisted_flag` | int | 1 = quote completed via AQX platform |
| `policy_type` | string | Auto Only, Auto + Renters |
| `coverage_tier` | string | Liability Only, Standard, Premium, Elite |
| `annual_premium` | float | Premium at policy effective date ($) |
| `cohort_quarter` | string | Acquisition cohort (2023Q1 to 2024Q4) |
| `tenure_months` | int | Months since customer's first policy |
| `multi_product_flag` | int | 1 = holds both auto and renters |
| `renters_quoted_flag` | int | 1 = renters was offered at quote |
| `renters_attached_flag` | int | 1 = renters policy bound |
| `payment_method` | string | Credit Card, Bank Draft, Check, Digital Wallet |
| `billing_frequency` | string | Monthly, Semi-Annual, Annual |
| `missed_payment_count` | int | Missed payments in first 12 months |
| `payment_consistency` | float | Score 0-100 (100 = no missed payments) |
| `nsf_flag` | int | 1 = had a returned payment |
| `has_claim_12mo` | int | 1 = filed at least one claim |
| `claim_severity_band` | string | No Claims, Minor, Moderate, Major |
| `renewed` | int | **TARGET:** 1 = renewed at 12 months, 0 = lapsed |

**Leakage-prone columns (excluded from model training):**

| Column | Risk | Reason |
|---|---|---|
| `cltv_36mo` | HIGH | Derived from full 36-month policy outcome |
| `renewal_premium_change_pct` | HIGH | Only known after renewal decision |
| `post_renewal_coverage_tier` | HIGH | Only known after renewal decision |
| `outreach_contact_flag` | CONDITIONAL | Legitimate only with a strict date guard |

**Source table schema:** See [`data/schema/erd.md`](data/schema/erd.md) for the entity-relationship diagram and [`data/schema/table_definitions.md`](data/schema/table_definitions.md) for source table grain and join logic.

---

## ⚙️ Setup

```bash
# 1. Clone the repo
git clone https://github.com/Aztexan512/waypoint-retention-analytics.git
cd waypoint-retention-analytics

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the dashboard
streamlit run app.py
```

> **Note:** The analysis-ready dataset is committed to this repo at `data/waypoint_retention.csv`. No data generation step is required to run the dashboard or notebook.

---

## 🚀 Live Dashboard

| Dashboard | Link |
|---|---|
| Waypoint P&C Retention Explorer | [![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://gtfycfxmeyq6tn6p85q7app.streamlit.app/) |

<!-- STREAMLIT URL REQUIRED: Replace PLACEHOLDER with deployed app URL after Streamlit Community Cloud deployment -->

---

## 📁 File Structure

```
waypoint-retention-analytics/
|-- README.md                          This file
|-- app.py                             Primary Streamlit dashboard (7 tabs)
|-- requirements.txt                   Pinned Python dependencies
|-- portfolio_page.html                Standalone shareable project page
|-- .streamlit/
|   |-- config.toml                    Dashboard theme configuration
|-- data/
|   |-- waypoint_retention.csv         Analysis-ready dataset (60,081 rows)
|   |-- waypoint_retention_metadata.json  Generation parameters and dataset summary
|   |-- data_dictionary.md             Column reference with leakage documentation
|   |-- schema/
|       |-- erd.md                     Entity-relationship diagram (Mermaid)
|       |-- table_definitions.md       Source table grain and join logic
|-- sql/
|   |-- waypoint_retention_analysis.sql  7 Snowflake-compatible queries
|-- notebooks/
|   |-- waypoint_retention_analysis.ipynb  EDA, modeling, SHAP, findings
|-- docs/
|   |-- PROJECT_OVERVIEW.md            Methodology, key findings, how to run
|-- screenshots/
    |-- [Dashboard screenshots added after deployment]
```

---

## ⚠️ Assumptions and Caveats

**Synthetic data:** All data in this project is synthetic. The dataset was generated using NumPy with seed 42 for reproducibility. It is designed to produce realistic analytical patterns but does not represent any real company, customer, or transaction.

**Modeling assumptions:**
- The lapse prediction model is trained only on policies with a completed 12-month renewal window. In-term policies (effective date after 2024-12-31) are excluded from model training and evaluation.
- CLTV is estimated as a function of annual premium and observed renewal probability per segment over a 36-month horizon. It is a dashboard metric only and is excluded from model training as a leakage risk.
- The model AUC of 0.61 reflects limited feature diversity in synthetic data. Real-world billing and claims data with richer longitudinal history would be expected to improve model performance.

**Business assumptions:**
- Outreach cost of $18 per contact is the default in the financial simulator and is used for ROI calculations. This figure should be replaced with Waypoint's actual cost-per-contact before operationalizing the model.
- The renters premium opportunity of $5.4M assumes a $280/yr average renters premium and the current 49.6% close rate applied to all 38,865 unquoted policyholders. Actual attachment rates for a reactivation campaign would likely be lower.
- The 8.8pp AQX retention premium is measured on policies in the 2023Q3 to 2024Q4 cohort window. It does not account for any self-selection of higher-quality agencies into the AQX program.

---

## 👤 Author

**Luciano Casillas**
Independent Analytics Consultant | Austin, TX

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue)](https://linkedin.com/in/luciano-casillas)
[![GitHub](https://img.shields.io/badge/GitHub-Aztexan512-lightgrey)](https://github.com/Aztexan512)

luciano.casillasjr@outlook.com
