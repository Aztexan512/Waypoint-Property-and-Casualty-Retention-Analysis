# Waypoint Property & Casualty -- Project Overview

**Author:** Luciano Casillas
**Date:** 2026-05-02
**Role target:** Data Analyst II -- Insurance Analytics (Progressive Insurance)

---

## 1. Business Context

Waypoint Property & Casualty is a fictional regional direct-to-consumer auto and renters
insurer operating across 14 states with approximately 290,000 active policies and $380M
in written premium. The company is growing its agency channel through a new digital
quoting platform (the Auto Quote Explorer, or AQX) and managing a hybrid direct/agency
distribution model with four agency types: Independent, Captive, Digital Partner, and Direct.

As the Data Analyst II on the Direct Analytics team, I was asked to analyze policyholder
retention behavior and household lifetime value across a 36-month book of 90,000 auto
and renters policies. The mandate: identify at-risk renewal segments, quantify the revenue
impact of the multi-product attachment gap and digital channel quality differential, and
deliver a predictive lapse-warning score deployable before the 60-day renewal window.

---

## 2. Data Design

**Source tables (5):** `dim_customer`, `fact_policies`, `fact_renewals`,
`fact_billing_summary`, `fact_claims`. These reflect how retention data lives in a real
insurance system -- normalized, multi-table, not analysis-ready by default.

**Denormalized output:** `data/waypoint_retention.csv` -- 90,000 rows, 39 columns, one
row per policy. Claims are aggregated from the sparse `fact_claims` table (19,000+
claim rows) to policy-level summary columns.

**Key parameters:**
- Time window: 2023-01-01 to 2025-12-31 (36 months)
- Renewal outcome known for ~60,000 policies (effective on or before 2024-12-31)
- Target: `renewed` (1 = renewed at 12 months, 0 = lapsed or cancelled, -1 = unknown)
- Seed: 42 for full reproducibility

**Leakage guardrails:** Four columns are excluded from model training:
`cltv_36mo` (full 36-month outcome), `renewal_premium_change_pct` (known after offer
generation), `post_renewal_coverage_tier` (known after renewal), and
`outreach_contact_flag` (conditional leakage without strict date guard).

---

## 3. SQL Analysis (Phase 3)

Seven Snowflake-compatible queries, each answering one approved business question.
Written against the 5 source tables (not the denormalized CSV) to demonstrate
multi-table join proficiency.

**Q01 -- Cohort Retention:** Builds a month-by-month cohort retention ladder using a
row-generator CROSS JOIN (`TABLE(GENERATOR(ROWCOUNT => 12))`). Identifies bottom-5
cohorts by 12-month renewal rate with a weighted billing distress analysis.

**Q02 -- Renewal Prediction:** Stacks all feature segments into a single unified result
set using `UNION ALL`, then ranks by absolute renewal rate lift vs. book average. Serves
as a human-readable complement to the SHAP values from Phase 4.

**Q04 -- CLTV Analysis:** Computes average 36-month CLTV by acquisition channel and
coverage tier. Includes a three-scenario revenue opportunity model using CROSS JOIN with
a static values table (Baseline / +5pp lift / +10pp lift).

**Q05 -- Lapse Warning:** Builds a rules-based billing risk score (0-100) from five
billing features weighted by empirical lapse lift. Creates a decile lift table using
`NTILE(10)` and computes a three-tier at-risk profile (Low/Medium/High Risk).

**Q07 -- Channel Retention:** Isolates the AQX launch effect using a
`cohort_quarter >= '2023Q3'` date guard. Computes a rolling 2-quarter average renewal
rate per channel using `AVG(...) OVER (PARTITION BY channel ORDER BY cohort ROWS BETWEEN
1 PRECEDING AND CURRENT ROW)`.

**Q09 -- Claims and Renewal:** Uses a `LEFT JOIN` subquery to aggregate claims to policy
grain before the main join. Creates a multi-segment result using `UNION ALL` across
severity, at-fault status, and has-claim segments in a single pass.

**Q10 -- Cross-Sell Funnel:** Implements a 4-stage funnel (`UNION ALL` of stage counts)
where bar widths represent percentage of Stage 1 population (not prior stage), a critical
design rule for visually honest funnel charts.

---

## 4. Predictive Model (Phase 4)

**Algorithm:** XGBoost gradient boosting classifier (`xgb.XGBClassifier`)
**Target:** `renewed` (binary: 1 = renewed, 0 = lapsed)
**Training split:** Time-based -- train on policies effective before 2024-07-01 (45,002
rows), test on 2024-07-01 to 2024-12-31 (15,079 rows).

**Feature engineering:**
- 29 features after excluding leakage and metadata columns
- Categorical features (acquisition_channel, coverage_tier, state, etc.) encoded with
  `OrdinalEncoder` -- avoids dimensionality explosion from one-hot encoding on
  high-cardinality features like `state` (14 values) and `metro_area` (30+ values)
- XGBoost handles ordinal-encoded categoricals natively via optimal tree splits

**Hyperparameters:** `n_estimators=400`, `max_depth=4`, `learning_rate=0.05`,
`subsample=0.80`, `colsample_bytree=0.75`, `min_child_weight=15`, `gamma=1.0`.
Conservative regularization chosen to prevent overfitting on a 45K training set.

**Model performance:**

| Metric | Value |
|---|---|
| Test ROC-AUC | 0.61 |
| 5-Fold CV AUC | 0.61 +/- 0.007 |
| Top decile lapse rate | 40.0% vs. 25.2% book average |
| Top decile lift | 1.59x |
| High-risk pct (deciles 1-2) | 20% of book |

**Top 5 SHAP features (mean absolute SHAP value):**
1. `acquisition_channel` (0.2027) -- channel quality is the dominant predictor
2. `payment_consistency` (0.1638) -- composite billing health score
3. `annual_premium` (0.0864) -- premium level correlates with coverage commitment
4. `policy_type` (0.0656) -- Auto + Renters policies show higher retention
5. `total_claim_amount` (0.0530) -- claim payout history influences renewal

**SHAP computation:** Computed on a 5,000-row random sample of the training set using
`shap.TreeExplainer`. Full-dataset computation is available but was omitted from the
notebook for runtime efficiency.

**Lapse scoring:** All 90,000 policies are scored. `lapse_prob = 1 - P(renewed=1)`.
Decile 1 = highest lapse risk (negated qcut: `pd.qcut(-lapse_prob, q=10, ...)`).

**Interpretation:** The 0.61 AUC reflects the challenge of predicting individual renewal
decisions from aggregate billing and demographic features when the true signal is
compressed by the channel-based renewal rate structure. The model is most useful for
ranking policyholders by relative risk (the lift curve) rather than for absolute
probability calibration.

---

## 5. Dashboard (Phase 5)

Seven-tab Streamlit application with global sidebar filters (channel, coverage tier,
policy type, tenure range, state) and a 4-card KPI header with sparklines.

**Tab 1 -- Retention Overview:** HTML cohort retention heatmap (blue gradient cells,
months 1-12 on columns, cohort quarters on rows). Paired line chart and claims severity
bar with a full-width dual-axis claim payout vs. renewal rate chart below.

**Tab 2 -- Channel and Value:** Paired renewal rate and CLTV bars by channel. AQX vs.
non-AQX dual-line trend with a vertical AQX launch reference marker. Coverage tier
CLTV bar and agency type / tenure band grouped bar.

**Tab 3 -- Predictive Model:** Lift by lapse propensity decile, cumulative gain curve,
SHAP horizontal bar chart (l=185 left margin for long feature labels), confusion matrix
(NAVY for correct / RED_SOFT for error cells), CSS lapse risk score histogram, and an
at-risk profile explorer with radio-driven metric tiles.

**Tab 4 -- Cross-Sell Funnel:** CSS div funnel (bar widths = % of Stage 1, labels = %
of prior stage). Paired agency type and tenure band conversion bars.

**Tab 5 -- Financial Impact:** Two-slider simulator (renewal rate lift, renters attach
lift). Results card (green border) and scenario comparison bar. Two reactive downstream
charts that update with slider values.

**Tab 6 -- Recommendations:** 3-tier action plan (Immediate 0-30 days, Short-Term
30-90 days, Strategic 90+ days), 2 cards per tier with revenue sizing.

**Tab 7 -- Healthcare Application:** 8-row signal translation table mapping insurance
analytics concepts to healthcare analogues (patient retention, readmission prevention).
Three lever cards and a full-width portability strip.

---

## 6. Key Recommendations

**Immediate (0-30 days):**
Deploy a billing-based lapse alert routing policies with `missed_payment_count >= 1`
or `nsf_flag = 1` to a 15-day outreach queue before the 60-day renewal window. Estimated
impact: $1.2M+ in retained premium from the high-risk segment.

AQX channel delivers 82% renewal vs. 68% Direct Web. Accelerating AQX onboarding for
independent agency partners is the highest-ROI channel investment.

**Short-term (30-90 days):**
28,000+ policies were quoted for renters but did not attach. A month 3-6 cross-sell
campaign targeting this segment represents $7.8M in unearned renters premium at the
$280/yr average renters price.

Build a cohort-level early warning that flags billing distress at month 8, enabling
intervention before the month-11 renewal offer cycle begins.

**Strategic (90+ days):**
Bundling incentives (waived fees, discounted renters) should increase the 28.3% attach
rate. Each 1pp improvement in attach rate represents approximately $2.8M in additional
multi-year CLTV.

Deploy the lapse warning score to a real-time scoring endpoint for CRM integration.
The top decile (40% lapse rate vs. 25.2% book) provides actionable prioritization for
retention outreach even at the current model accuracy level.

---

## 7. Skills Demonstrated

| Skill | Where |
|---|---|
| Multi-table SQL (window functions, CTEs, conditional aggregation) | Phase 3: 7 query files |
| Snowflake-compatible ANSI SQL | All Phase 3 queries |
| Synthetic data generation at scale | Phase 2: 90K rows, 5 source tables |
| Gradient boosting classification | Phase 4: XGBoost |
| SHAP feature attribution | Phase 4: TreeExplainer |
| Decile lift / gain curve analysis | Phase 4: model evaluation |
| Streamlit dashboard development | Phase 5: 7 tabs, 1,168 lines |
| Plotly custom visualization | Phase 5: 15+ chart types |
| Insurance analytics domain knowledge | All phases |
| Cross-industry translation | Phase 5: Tab 7 (healthcare) |
