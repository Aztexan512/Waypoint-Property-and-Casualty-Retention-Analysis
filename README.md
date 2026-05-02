# Waypoint Property & Casualty | Retention Analytics

Analyzes 90,000 synthetic auto and renters insurance policies to predict first-year lapse
risk, quantify a $1.2M+ near-term retention opportunity, and map the auto-to-renters
cross-sell funnel across agency segments -- achieving 1.59x lift in the top lapse-risk
decile with a gradient boosting model.

**Live dashboard:** [PLACEHOLDER -- add after deployment]
**Author:** Luciano Casillas
**Target role:** Data Analyst II -- Insurance Analytics

---

## Key Findings

| Finding | Metric |
|---|---|
| Book renewal rate (2023-2025) | 74.8% |
| AQX digital channel vs. Direct Web renewal gap | 82% vs. 68% (+14pp) |
| Multi-product (Auto + Renters) attach rate | 28.3% |
| Policies quoted for renters but not attached | 28,000+ |
| Est. missed renters premium from unattached quotes | $7.8M |
| Top decile lapse lift (model vs. book) | 1.59x |
| High-risk policyholders (top 2 score deciles) | 20% of book |
| Model ROC-AUC (XGBoost, test set) | 0.61 |

---

## Business Questions Answered

| ID | Question | Approach |
|---|---|---|
| Q01 | Which acquisition cohorts show the steepest first-year attrition? | Cohort retention heatmap (SQL) |
| Q02 | Which characteristics predict non-renewal at 12 months? | Feature importance + SHAP (Python) |
| Q04 | How does 36-month CLTV vary by channel and coverage tier? | CLTV segmentation (SQL + Python) |
| Q05 | Which billing behaviors correlate with early lapse? | Billing risk scoring (SQL + Python) |
| Q07 | Does AQX produce higher-quality, better-retained customers? | Channel cohort comparison (SQL) |
| Q09 | What is the relationship between claims history and renewal? | Multi-table join analysis (SQL) |
| Q10 | Where does the auto-to-renters cross-sell funnel drop off? | Funnel stage aggregation (SQL) |

---

## Project Structure

```
waypoint-retention-analytics/
├── app.py                        Streamlit dashboard (7 tabs)
├── requirements.txt              Python dependencies
├── README.md                     This file
├── portfolio_page.html           Standalone portfolio page
├── .streamlit/
│   └── config.toml              Streamlit theme
├── data/
│   ├── waypoint_retention.csv   90,000-row denormalized dataset (synthetic)
│   ├── data_dictionary.md       Column reference
│   └── schema/
│       ├── erd.md               Entity-relationship diagram (Mermaid)
│       └── table_definitions.md Per-table schema documentation
├── scripts/
│   └── 01_generate_data.py      Synthetic data generator
├── sql/
│   └── waypoint_retention_analysis.sql   7 Snowflake-compatible queries
├── notebooks/
│   └── waypoint_retention_analysis.ipynb  EDA + GBM modeling notebook
└── docs/
    └── PROJECT_OVERVIEW.md      Full methodology and findings
```

---

## Dashboard Tabs

| Tab | Contents |
|---|---|
| Retention Overview | Cohort heatmap, renewal trend by quarter, claims severity impact |
| Channel and Value | AQX vs. non-AQX trends, CLTV by channel and tier, agency/tenure comparison |
| Predictive Model | Lift/gain curves, SHAP feature importance, confusion matrix, lapse risk explorer |
| Cross-Sell Funnel | Renters attachment funnel, cross-sell rate by agency type and tenure |
| Financial Impact | Interactive simulator: renewal rate lift and renters attach rate sliders |
| Recommendations | 6 tiered action recommendations with revenue sizing |
| Healthcare Application | Cross-industry signal translation: insurance retention to healthcare |

---

## Data

**Synthetic dataset:** 90,000 auto and renters policies across 14 states (2023-2025).
Generated with `scripts/01_generate_data.py` (seed 42) from 5 normalized source tables
reflecting how data lives in a real insurance system.

Source tables: `dim_customer`, `fact_policies`, `fact_renewals`, `fact_billing_summary`,
`fact_claims`. Denormalized into `data/waypoint_retention.csv` at policy grain.

No real policyholder data is used. All company names, policy IDs, and customer records
are synthetic.

---

## Tech Stack

| Layer | Tools |
|---|---|
| Data generation | Python 3.12, NumPy, Pandas, PyYAML |
| SQL analysis | Snowflake-compatible ANSI SQL (7 queries) |
| Modeling | XGBoost 3.2, SHAP 0.51, scikit-learn 1.8 |
| Dashboard | Streamlit, Plotly |
| Visualization | Plotly Graph Objects, custom HTML/CSS components |

---

## Running Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

To regenerate the dataset from scratch:
```bash
python scripts/01_generate_data.py
```

To retrain the model:
```bash
python _build/workflows/04_modeling/modeling/run_phase4.py
```

---

## About

Built as an analytics portfolio project targeting Data Analyst II roles in insurance and
adjacent industries. Demonstrates end-to-end analytical capability: data modeling,
synthetic data generation, multi-table SQL, gradient boosting classification, SHAP
attribution, and an interactive Streamlit dashboard.

See `docs/PROJECT_OVERVIEW.md` for full methodology documentation.
