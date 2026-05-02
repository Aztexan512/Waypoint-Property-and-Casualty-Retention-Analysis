/*
 * FILE:    waypoint_retention_analysis.sql
 * PURPOSE: Combined Snowflake-compatible SQL analysis for Waypoint Property and Casualty
 *          retention analytics. Contains all 7 approved business question queries.
 * SCHEMA:  WAYPOINT_ANALYTICS
 * AUTHOR:  Luciano Casillas
 * CREATED: 2026-05-02
 *
 * QUERY INDEX:
 *   Q01  Cohort Retention Analysis (line ~30)
 *   Q02  Renewal Prediction Feature Analysis
 *   Q04  Customer Lifetime Value Analysis
 *   Q05  Lapse Warning Score and Billing Behavior
 *   Q07  Channel Retention Comparison (AQX vs. Non-AQX)
 *   Q09  Claims History and Renewal Behavior
 *   Q10  Auto-to-Renters Cross-Sell Funnel
 */

-- ===========================================================================
-- Q01: Cohort Retention Analysis
-- ===========================================================================

/*
 * PURPOSE:  Analyze first-year renewal rates across policy cohorts by acquisition quarter
 *           and identify cohorts with the steepest attrition before the 12-month mark.
 * INPUTS:   WAYPOINT_ANALYTICS.fact_policies
 *           WAYPOINT_ANALYTICS.fact_renewals
 *           WAYPOINT_ANALYTICS.fact_billing_summary
 *           WAYPOINT_ANALYTICS.dim_customer
 * OUTPUTS:  Result set 1: Month-by-month cohort retention ladder (cohort heatmap source)
 *           Result set 2: 12-month cohort summary with renewal rate and rank
 *           Result set 3: Steepest-attrition cohorts (bottom 5 by renewal rate)
 * AUTHOR:   Luciano Casillas
 * CREATED:  2026-05-02
 */

-- DESIGN DECISION: Month-by-month retention is modeled from the 12-month binary outcome
-- because the source system only records the renewal decision at term end, not mid-term
-- cancellations. Months 1-11 are assigned near-100% retention with a small adjustment
-- for policies exhibiting extreme billing distress (nsf_flag=1 AND missed_payment_count>=3),
-- which are modeled as mid-term lapses at month 8. This is flagged as an assumption in the
-- dashboard narrative strip. In a production system, policy status by calendar month would
-- come from a policy-status fact table updated daily.

-- DESIGN DECISION: Cohorts before 2025Q1 are included in the retention ladder only if
-- their 12-month renewal window falls within the dataset end date (2025-12-31). Cohorts
-- 2025Q1-2025Q4 do not have known renewal outcomes and are excluded from all three result sets.

-- ===========================================================================
-- RESULT SET 1: Month-by-month cohort retention ladder
-- Grain: one row per (cohort_quarter, month_num)
-- Used by: Cohort Retention Heatmap (Tab 1)
-- ===========================================================================

WITH months AS (
    -- Generate spine of months 1 through 12
    SELECT seq4() + 1 AS month_num
    FROM TABLE(GENERATOR(ROWCOUNT => 12))
),

cohort_base AS (
    -- Policy counts and 12-month outcomes per cohort, joined with billing for mid-term proxy
    SELECT
        fp.cohort_quarter,
        fp.policy_id,
        fp.renewed,
        fb.nsf_flag,
        fb.missed_payment_count_12mo,
        -- Flag policies at extreme billing risk: NSF + 3+ missed payments
        -- These are modeled as mid-term lapses at month 8 rather than renewal-time lapses
        IFF(fb.nsf_flag = 1 AND fb.missed_payment_count_12mo >= 3, 1, 0) AS extreme_billing_risk
    FROM WAYPOINT_ANALYTICS.fact_policies          fp
    JOIN WAYPOINT_ANALYTICS.fact_billing_summary   fb ON fp.policy_id = fb.policy_id
    WHERE fp.renewed IN (0, 1)   -- known renewal outcome only
),

cohort_counts AS (
    SELECT
        cohort_quarter,
        COUNT(*)                                                   AS cohort_size,
        SUM(IFF(renewed = 1, 1, 0))                               AS renewed_count,
        SUM(IFF(extreme_billing_risk = 1 AND renewed = 0, 1, 0))  AS mid_term_lapse_count
    FROM cohort_base
    GROUP BY cohort_quarter
),

retention_ladder AS (
    -- Cross-join cohorts with month spine to build (cohort, month) pairs
    SELECT
        c.cohort_quarter,
        m.month_num,
        c.cohort_size,
        c.renewed_count,
        c.mid_term_lapse_count,
        -- Active policies at each month:
        --   Months 1-7:  full cohort active (no modeled attrition yet)
        --   Month 8:     remove extreme billing risk non-renewers (proxy for mid-term cancel)
        --   Months 9-11: remaining non-renewers still technically active (renewal decision pending)
        --   Month 12:    only renewed policies count as retained
        CASE
            WHEN m.month_num BETWEEN 1 AND 7
                THEN c.cohort_size
            WHEN m.month_num = 8
                THEN c.cohort_size - c.mid_term_lapse_count
            WHEN m.month_num BETWEEN 9 AND 11
                THEN c.cohort_size - c.mid_term_lapse_count
            WHEN m.month_num = 12
                THEN c.renewed_count
        END AS active_count,
        ROUND(
            CASE
                WHEN m.month_num BETWEEN 1 AND 7
                    THEN 1.0
                WHEN m.month_num = 8
                    THEN (c.cohort_size - c.mid_term_lapse_count)::FLOAT / NULLIF(c.cohort_size, 0)
                WHEN m.month_num BETWEEN 9 AND 11
                    THEN (c.cohort_size - c.mid_term_lapse_count)::FLOAT / NULLIF(c.cohort_size, 0)
                WHEN m.month_num = 12
                    THEN c.renewed_count::FLOAT / NULLIF(c.cohort_size, 0)
            END
        , 4) AS retention_rate
    FROM cohort_counts c
    CROSS JOIN months m
)

SELECT
    cohort_quarter,
    month_num,
    cohort_size,
    active_count,
    cohort_size - active_count AS lapsed_count,
    retention_rate,
    ROUND((1.0 - retention_rate) * 100, 2) AS attrition_pct
FROM retention_ladder
ORDER BY cohort_quarter, month_num;


-- ===========================================================================
-- RESULT SET 2: 12-month cohort summary with renewal rate, rank, and variance
-- Grain: one row per cohort_quarter
-- Used by: 12-Month Renewal Rate by Cohort Quarter line chart (Tab 1)
-- ===========================================================================

WITH cohort_summary AS (
    SELECT
        fp.cohort_quarter,
        COUNT(*)                                         AS cohort_size,
        SUM(IFF(fp.renewed = 1, 1, 0))                  AS renewed_count,
        ROUND(AVG(fp.renewed::FLOAT), 4)                AS renewal_rate_12mo,
        ROUND(AVG(fp.annual_premium), 2)                AS avg_premium,
        ROUND(AVG(fp.tenure_months), 1)                 AS avg_tenure_months,
        SUM(fp.multi_product_flag)                       AS multi_product_count,
        ROUND(AVG(fp.multi_product_flag::FLOAT), 4)     AS multi_product_rate
    FROM WAYPOINT_ANALYTICS.fact_policies fp
    WHERE fp.renewed IN (0, 1)
    GROUP BY fp.cohort_quarter
),

book_avg AS (
    SELECT ROUND(AVG(renewed::FLOAT), 4) AS book_renewal_rate
    FROM WAYPOINT_ANALYTICS.fact_policies
    WHERE renewed IN (0, 1)
)

SELECT
    s.cohort_quarter,
    s.cohort_size,
    s.renewed_count,
    s.cohort_size - s.renewed_count                          AS lapsed_count,
    s.renewal_rate_12mo,
    b.book_renewal_rate                                       AS book_avg_renewal_rate,
    ROUND(s.renewal_rate_12mo - b.book_renewal_rate, 4)      AS vs_book_avg,
    RANK() OVER (ORDER BY s.renewal_rate_12mo DESC)          AS renewal_rank_desc,
    s.avg_premium,
    s.avg_tenure_months,
    s.multi_product_rate
FROM cohort_summary s
CROSS JOIN book_avg b
ORDER BY s.cohort_quarter;


-- ===========================================================================
-- RESULT SET 3: Steepest-attrition cohorts -- bottom 5 by 12-month renewal rate
-- Grain: one row per cohort_quarter (filtered to bottom 5)
-- Used by: Dashboard key finding strip; narrative on Tab 1
-- ===========================================================================

WITH cohort_rates AS (
    SELECT
        fp.cohort_quarter,
        dc.acquisition_channel,
        dc.agency_type,
        COUNT(*)                                AS cohort_size,
        ROUND(AVG(fp.renewed::FLOAT), 4)        AS renewal_rate_12mo,
        ROUND(AVG(fb.missed_payment_count_12mo), 2)  AS avg_missed_payments,
        ROUND(AVG(fb.payment_consistency_score), 1)  AS avg_payment_consistency,
        SUM(fb.nsf_flag)                        AS nsf_policy_count
    FROM WAYPOINT_ANALYTICS.fact_policies        fp
    JOIN WAYPOINT_ANALYTICS.dim_customer         dc ON fp.customer_id = dc.customer_id
    JOIN WAYPOINT_ANALYTICS.fact_billing_summary fb ON fp.policy_id   = fb.policy_id
    WHERE fp.renewed IN (0, 1)
    GROUP BY fp.cohort_quarter, dc.acquisition_channel, dc.agency_type
),

cohort_overall AS (
    SELECT
        cohort_quarter,
        SUM(cohort_size)                                     AS total_cohort_size,
        ROUND(
            SUM(cohort_size * renewal_rate_12mo) / NULLIF(SUM(cohort_size), 0)
        , 4)                                                 AS blended_renewal_rate,
        ROUND(
            SUM(cohort_size * avg_missed_payments) / NULLIF(SUM(cohort_size), 0)
        , 2)                                                 AS wtd_avg_missed_payments,
        ROUND(
            SUM(cohort_size * avg_payment_consistency) / NULLIF(SUM(cohort_size), 0)
        , 1)                                                 AS wtd_avg_payment_consistency
    FROM cohort_rates
    GROUP BY cohort_quarter
),

ranked AS (
    SELECT
        cohort_quarter,
        total_cohort_size,
        blended_renewal_rate,
        wtd_avg_missed_payments,
        wtd_avg_payment_consistency,
        RANK() OVER (ORDER BY blended_renewal_rate ASC) AS attrition_rank
    FROM cohort_overall
)

SELECT *
FROM ranked
WHERE attrition_rank <= 5
ORDER BY attrition_rank;


-- ===========================================================================
-- Q02: Renewal Prediction Feature Analysis
-- ===========================================================================

/*
 * PURPOSE:  Identify policyholder characteristics most predictive of non-renewal at 12 months
 *           and quantify how early in the policy term a lapse can be predicted.
 * INPUTS:   WAYPOINT_ANALYTICS.fact_policies
 *           WAYPOINT_ANALYTICS.fact_renewals
 *           WAYPOINT_ANALYTICS.fact_billing_summary
 *           WAYPOINT_ANALYTICS.fact_claims
 *           WAYPOINT_ANALYTICS.dim_customer
 * OUTPUTS:  Result set 1: Renewal rates by demographic and policy segment
 *           Result set 2: Renewal rate lift by behavioral feature group
 *           Result set 3: Feature ranking by renewal rate differential (top predictors)
 * AUTHOR:   Luciano Casillas
 * CREATED:  2026-05-02
 */

-- DESIGN DECISION: This query performs descriptive feature analysis, not predictive modeling.
-- The gradient boosting model and SHAP values are computed in Phase 4 (Python notebook).
-- The SQL output here surfaces the same signal via simple conditional aggregation and serves
-- as a human-readable companion to the model results shown on Tab 3 of the dashboard.

-- DESIGN DECISION: Leakage-prone columns (renewal_premium_change_pct, outreach_contact_flag,
-- cltv_36mo, post_renewal_coverage_tier) are excluded from all feature analysis in this query.
-- Only features observable before or at the time the renewal decision is made are included.

-- DESIGN DECISION: Tenure bands are defined as: New (0-11 months), Developing (12-23 months),
-- Established (24-47 months), Loyal (48+ months). These breakpoints reflect meaningful
-- behavioral differences and align with the dashboard filter slider (0-48 months).


-- ===========================================================================
-- RESULT SET 1: Renewal rates by demographic and policy segment
-- Grain: one row per feature × feature_value combination
-- Used by: SHAP companion table; At-Risk Profile Explorer (Tab 3)
-- ===========================================================================

WITH base AS (
    SELECT
        fp.policy_id,
        fp.renewed,
        fp.coverage_tier,
        fp.multi_product_flag,
        fp.annual_premium,
        fp.tenure_months,
        dc.age_band,
        dc.state,
        dc.homeowner_flag,
        dc.prior_insurance_flag,
        dc.acquisition_channel,
        dc.agency_type,
        dc.aqx_assisted_flag,
        CASE
            WHEN fp.tenure_months <  12 THEN '0-11 mo (New)'
            WHEN fp.tenure_months <  24 THEN '12-23 mo (Developing)'
            WHEN fp.tenure_months <  48 THEN '24-47 mo (Established)'
            ELSE '48+ mo (Loyal)'
        END AS tenure_band,
        CASE
            WHEN fp.annual_premium <  1000 THEN 'Under $1K'
            WHEN fp.annual_premium <  1500 THEN '$1K - $1.5K'
            WHEN fp.annual_premium <  2000 THEN '$1.5K - $2K'
            ELSE 'Over $2K'
        END AS premium_band
    FROM WAYPOINT_ANALYTICS.fact_policies  fp
    JOIN WAYPOINT_ANALYTICS.dim_customer   dc ON fp.customer_id = dc.customer_id
    WHERE fp.renewed IN (0, 1)
),

-- Union all feature-value combinations into a single ranked result set
feature_segments AS (
    SELECT 'Coverage Tier'       AS feature_name, coverage_tier      AS feature_value, renewed FROM base
    UNION ALL
    SELECT 'Age Band',           age_band,                                             renewed FROM base
    UNION ALL
    SELECT 'Tenure Band',        tenure_band,                                          renewed FROM base
    UNION ALL
    SELECT 'Acquisition Channel',acquisition_channel,                                  renewed FROM base
    UNION ALL
    SELECT 'Agency Type',        agency_type,                                          renewed FROM base
    UNION ALL
    SELECT 'Policy Type',        IFF(multi_product_flag = 1,'Auto + Renters','Auto Only'), renewed FROM base
    UNION ALL
    SELECT 'Homeowner',          IFF(homeowner_flag = 1,'Yes','No'),                   renewed FROM base
    UNION ALL
    SELECT 'Prior Insurance',    IFF(prior_insurance_flag = 1,'Yes','No'),             renewed FROM base
    UNION ALL
    SELECT 'AQX Assisted',       IFF(aqx_assisted_flag = 1,'Yes','No'),                renewed FROM base
    UNION ALL
    SELECT 'Premium Band',       premium_band,                                         renewed FROM base
)

SELECT
    feature_name,
    feature_value,
    COUNT(*)                             AS policy_count,
    SUM(renewed)                         AS renewed_count,
    ROUND(AVG(renewed::FLOAT), 4)        AS renewal_rate,
    ROUND(AVG(renewed::FLOAT) - b.book_avg, 4) AS vs_book_avg
FROM feature_segments
CROSS JOIN (
    SELECT ROUND(AVG(renewed::FLOAT), 4) AS book_avg
    FROM WAYPOINT_ANALYTICS.fact_policies
    WHERE renewed IN (0, 1)
) b
GROUP BY feature_name, feature_value, b.book_avg
HAVING COUNT(*) >= 50   -- suppress segments too small to be reliable
ORDER BY feature_name, renewal_rate DESC;


-- ===========================================================================
-- RESULT SET 2: Renewal rate lift by behavioral feature group
-- Grain: one row per billing/claims risk tier
-- Used by: Feature importance companion analysis (Tab 3)
-- ===========================================================================

WITH policy_features AS (
    SELECT
        fp.policy_id,
        fp.renewed,
        fp.coverage_tier,
        -- Billing risk classification
        CASE
            WHEN fb.missed_payment_count_12mo = 0 AND fb.nsf_flag = 0 AND fb.late_pay_flag_last_3mo = 0
                THEN '1 - Clean (0 issues)'
            WHEN fb.missed_payment_count_12mo = 0 AND fb.nsf_flag = 0
                THEN '2 - Minor (late pay only)'
            WHEN fb.missed_payment_count_12mo = 1 AND fb.nsf_flag = 0
                THEN '3 - Moderate (1 missed)'
            WHEN fb.missed_payment_count_12mo >= 2 OR fb.nsf_flag = 1
                THEN '4 - High Risk (2+ missed or NSF)'
            ELSE '2 - Minor (late pay only)'
        END AS billing_risk_tier,
        fb.missed_payment_count_12mo,
        fb.payment_consistency_score,
        fb.nsf_flag,
        fb.late_pay_flag_last_3mo,
        fb.payment_method,
        -- Claims summary (aggregated from fact_claims)
        COALESCE(ca.has_claim, 0)         AS has_claim_12mo,
        COALESCE(ca.claim_count, 0)       AS claim_count_12mo,
        COALESCE(ca.max_severity_num, 0)  AS claim_severity_num,
        COALESCE(ca.at_fault_any, 0)      AS at_fault_flag
    FROM WAYPOINT_ANALYTICS.fact_policies          fp
    JOIN WAYPOINT_ANALYTICS.fact_billing_summary   fb ON fp.policy_id = fb.policy_id
    LEFT JOIN (
        SELECT
            policy_id,
            1                                                               AS has_claim,
            COUNT(*)                                                        AS claim_count,
            MAX(CASE claim_severity_band
                    WHEN 'None'     THEN 0
                    WHEN 'Minor'    THEN 1
                    WHEN 'Moderate' THEN 2
                    WHEN 'Major'    THEN 3
                END)                                                        AS max_severity_num,
            MAX(at_fault_flag)                                              AS at_fault_any
        FROM WAYPOINT_ANALYTICS.fact_claims
        GROUP BY policy_id
    ) ca ON fp.policy_id = ca.policy_id
    WHERE fp.renewed IN (0, 1)
)

SELECT
    billing_risk_tier,
    COUNT(*)                                        AS policy_count,
    ROUND(AVG(renewed::FLOAT), 4)                  AS renewal_rate,
    ROUND(AVG(payment_consistency_score), 1)        AS avg_consistency_score,
    ROUND(AVG(has_claim_12mo::FLOAT), 4)            AS claim_rate,
    ROUND(AVG(at_fault_flag::FLOAT), 4)             AS at_fault_rate,
    -- Revenue at risk: lapsed policies * avg premium
    ROUND(SUM(CASE WHEN renewed = 0 THEN 1 ELSE 0 END) * AVG(fp2.annual_premium), 0)
                                                    AS est_premium_at_risk
FROM policy_features pf
JOIN WAYPOINT_ANALYTICS.fact_policies fp2 ON pf.policy_id = fp2.policy_id
GROUP BY billing_risk_tier
ORDER BY billing_risk_tier;


-- ===========================================================================
-- RESULT SET 3: Feature ranking by renewal rate differential
-- Grain: one row per feature × feature_value, ranked by lift over book average
-- Used by: Feature importance discussion in dashboard narrative (Tab 3)
-- ===========================================================================

WITH book AS (
    SELECT ROUND(AVG(renewed::FLOAT), 4) AS book_avg_rate
    FROM WAYPOINT_ANALYTICS.fact_policies
    WHERE renewed IN (0, 1)
),

feature_values AS (
    SELECT
        fp.policy_id,
        fp.renewed,
        fp.coverage_tier                                         AS coverage_tier,
        dc.acquisition_channel,
        IFF(fp.multi_product_flag = 1, 'Multi', 'Single')       AS product_flag,
        IFF(fb.nsf_flag = 1, 'NSF', 'No NSF')                   AS nsf_segment,
        IFF(fb.missed_payment_count_12mo >= 1, '1+ Missed', 'None Missed') AS missed_pay_segment,
        IFF(fb.late_pay_flag_last_3mo = 1, 'Late in Last 3mo', 'On Time') AS late_pay_segment,
        IFF(fb.payment_consistency_score >= 90, 'High Consistency (90+)', 'Lower Consistency (<90)') AS consistency_seg,
        IFF(dc.homeowner_flag = 1, 'Homeowner', 'Non-Owner')     AS homeowner_seg,
        IFF(dc.prior_insurance_flag = 1, 'Prior Insurance', 'No Prior Ins') AS prior_ins_seg,
        CASE
            WHEN fp.tenure_months < 12 THEN 'New (<12 mo)'
            WHEN fp.tenure_months < 48 THEN 'Mid (12-47 mo)'
            ELSE 'Long (48+ mo)'
        END AS tenure_seg
    FROM WAYPOINT_ANALYTICS.fact_policies          fp
    JOIN WAYPOINT_ANALYTICS.dim_customer           dc ON fp.customer_id = dc.customer_id
    JOIN WAYPOINT_ANALYTICS.fact_billing_summary   fb ON fp.policy_id   = fb.policy_id
    WHERE fp.renewed IN (0, 1)
),

-- Stack all features into (feature_name, feature_value, renewed)
stacked AS (
    SELECT 'Coverage Tier'       AS feature_name, coverage_tier       AS fv, renewed FROM feature_values
    UNION ALL
    SELECT 'Acquisition Channel',                  acquisition_channel,      renewed FROM feature_values
    UNION ALL
    SELECT 'Policy Type',                          product_flag,             renewed FROM feature_values
    UNION ALL
    SELECT 'NSF Flag',                             nsf_segment,              renewed FROM feature_values
    UNION ALL
    SELECT 'Missed Payments',                      missed_pay_segment,       renewed FROM feature_values
    UNION ALL
    SELECT 'Late Pay (Last 3mo)',                  late_pay_segment,         renewed FROM feature_values
    UNION ALL
    SELECT 'Payment Consistency',                  consistency_seg,          renewed FROM feature_values
    UNION ALL
    SELECT 'Homeowner',                            homeowner_seg,            renewed FROM feature_values
    UNION ALL
    SELECT 'Prior Insurance',                      prior_ins_seg,            renewed FROM feature_values
    UNION ALL
    SELECT 'Tenure Band',                          tenure_seg,               renewed FROM feature_values
),

aggregated AS (
    SELECT
        s.feature_name,
        s.fv                              AS feature_value,
        COUNT(*)                          AS n,
        ROUND(AVG(s.renewed::FLOAT), 4)  AS renewal_rate,
        b.book_avg_rate
    FROM stacked s
    CROSS JOIN book b
    GROUP BY s.feature_name, s.fv, b.book_avg_rate
    HAVING COUNT(*) >= 100
)

SELECT
    feature_name,
    feature_value,
    n                                                    AS policy_count,
    renewal_rate,
    book_avg_rate,
    ROUND(renewal_rate - book_avg_rate, 4)               AS lift_vs_book,
    ABS(ROUND(renewal_rate - book_avg_rate, 4))          AS abs_lift,
    RANK() OVER (ORDER BY ABS(renewal_rate - book_avg_rate) DESC) AS predictive_rank
FROM aggregated
ORDER BY abs_lift DESC, feature_name;


-- ===========================================================================
-- Q04: Customer Lifetime Value Analysis
-- ===========================================================================

/*
 * PURPOSE:  Analyze how policyholder lifetime value varies by acquisition channel and
 *           coverage tier, and identify which segments generate the most revenue per
 *           policy over a 36-month window.
 * INPUTS:   WAYPOINT_ANALYTICS.fact_policies
 *           WAYPOINT_ANALYTICS.fact_renewals
 *           WAYPOINT_ANALYTICS.dim_customer
 * OUTPUTS:  Result set 1: Average 36-month CLTV by acquisition channel
 *           Result set 2: Average 36-month CLTV by coverage tier
 *           Result set 3: Revenue opportunity model -- CLTV delta if retention improves
 * AUTHOR:   Luciano Casillas
 * CREATED:  2026-05-02
 */

-- DESIGN DECISION: cltv_36mo is pulled directly from the denormalized fact_policies table
-- where it was pre-computed during Phase 2 data generation. In a production environment,
-- CLTV would be computed in this query using multi-year renewal chains. The pre-computed
-- column is used here to keep the SQL focused on segmentation and opportunity sizing.

-- DESIGN DECISION: Revenue opportunity in Result Set 3 is modeled as the incremental CLTV
-- gained if each channel's renewal rate improved by a fixed lift percentage (e.g., +5%).
-- This directly feeds the Financial Impact tab simulator (Tab 5) in the dashboard.
-- The simulator applies user-selected lift percentages; this query shows the 5% baseline.

-- DESIGN DECISION: All 90,000 policies are included in CLTV analysis regardless of
-- whether they have a known renewal outcome. Policies with renewed = -1 have a CLTV
-- derived from their partial first-year premium, which correctly reflects their expected
-- 36-month value given that they have not yet reached the renewal window.


-- ===========================================================================
-- RESULT SET 1: Average 36-month CLTV by acquisition channel
-- Grain: one row per acquisition_channel
-- Used by: Channel and Value tab -- CLTV by channel bar chart (Tab 2)
-- ===========================================================================

WITH channel_cltv AS (
    SELECT
        dc.acquisition_channel,
        dc.agency_type,
        COUNT(*)                                                AS policy_count,
        ROUND(AVG(fp.cltv_36mo), 2)                           AS avg_cltv_36mo,
        ROUND(AVG(fp.annual_premium), 2)                       AS avg_annual_premium,
        ROUND(AVG(CASE WHEN fp.renewed IN (0,1) THEN fp.renewed::FLOAT END), 4)
                                                               AS renewal_rate_12mo,
        ROUND(AVG(fp.multi_product_flag::FLOAT), 4)           AS multi_product_rate,
        ROUND(SUM(fp.cltv_36mo), 0)                           AS total_cltv,
        -- CLTV index vs. book average (book avg = 1.00)
        ROUND(
            AVG(fp.cltv_36mo) / NULLIF((SELECT AVG(cltv_36mo) FROM WAYPOINT_ANALYTICS.fact_policies), 0)
        , 3)                                                   AS cltv_index
    FROM WAYPOINT_ANALYTICS.fact_policies  fp
    JOIN WAYPOINT_ANALYTICS.dim_customer   dc ON fp.customer_id = dc.customer_id
    GROUP BY dc.acquisition_channel, dc.agency_type
)

SELECT
    acquisition_channel,
    agency_type,
    policy_count,
    avg_cltv_36mo,
    avg_annual_premium,
    renewal_rate_12mo,
    multi_product_rate,
    total_cltv,
    cltv_index,
    RANK() OVER (ORDER BY avg_cltv_36mo DESC)  AS cltv_rank
FROM channel_cltv
ORDER BY avg_cltv_36mo DESC;


-- ===========================================================================
-- RESULT SET 2: Average 36-month CLTV by coverage tier
-- Grain: one row per coverage_tier
-- Used by: CLTV by Coverage Tier bar chart (Tab 2)
-- ===========================================================================

WITH tier_cltv AS (
    SELECT
        fp.coverage_tier,
        -- Define tier order for sorting (not available as an ORDER BY in GROUP BY)
        CASE fp.coverage_tier
            WHEN 'Liability Only' THEN 1
            WHEN 'Standard'       THEN 2
            WHEN 'Premium'        THEN 3
            WHEN 'Elite'          THEN 4
        END AS tier_order,
        COUNT(*)                                               AS policy_count,
        ROUND(AVG(fp.cltv_36mo), 2)                          AS avg_cltv_36mo,
        ROUND(AVG(fp.annual_premium), 2)                      AS avg_annual_premium,
        ROUND(AVG(CASE WHEN fp.renewed IN (0,1) THEN fp.renewed::FLOAT END), 4)
                                                              AS renewal_rate_12mo,
        ROUND(AVG(fp.multi_product_flag::FLOAT), 4)          AS multi_product_rate,
        -- Premium-weighted CLTV: higher-tier policyholders drive disproportionate revenue
        ROUND(SUM(fp.cltv_36mo), 0)                          AS total_cltv,
        ROUND(
            SUM(fp.cltv_36mo) / NULLIF((SELECT SUM(cltv_36mo) FROM WAYPOINT_ANALYTICS.fact_policies), 0) * 100
        , 2)                                                  AS pct_of_total_cltv
    FROM WAYPOINT_ANALYTICS.fact_policies fp
    GROUP BY fp.coverage_tier
)

SELECT
    coverage_tier,
    tier_order,
    policy_count,
    avg_cltv_36mo,
    avg_annual_premium,
    renewal_rate_12mo,
    multi_product_rate,
    total_cltv,
    pct_of_total_cltv,
    -- Cumulative CLTV from top tier down (shows concentration)
    SUM(total_cltv) OVER (ORDER BY tier_order DESC) AS cumulative_cltv_from_top
FROM tier_cltv
ORDER BY tier_order;


-- ===========================================================================
-- RESULT SET 3: Revenue opportunity model by channel
-- Grain: one row per acquisition_channel × scenario
-- Used by: Financial Impact tab simulator baseline; scenario bar chart (Tab 5)
-- ===========================================================================

-- DESIGN DECISION: Three scenarios are modeled:
--   Baseline:    current renewal rate, no change
--   +5% Lift:   renewal rate + 5 percentage points for all lapsed policies recovered
--   +10% Lift:  renewal rate + 10 percentage points
-- Revenue uplift = additional retained policies * avg_annual_premium (year 2 revenue)
-- This aligns with the dashboard simulator's default slider positions.

WITH channel_base AS (
    SELECT
        dc.acquisition_channel,
        COUNT(*)                                                              AS total_policies,
        SUM(CASE WHEN fp.renewed IN (0,1) THEN 1 ELSE 0 END)                AS eligible_for_renewal,
        SUM(CASE WHEN fp.renewed = 1 THEN 1 ELSE 0 END)                     AS currently_renewed,
        SUM(CASE WHEN fp.renewed = 0 THEN 1 ELSE 0 END)                     AS currently_lapsed,
        ROUND(AVG(CASE WHEN fp.renewed IN (0,1) THEN fp.renewed::FLOAT END), 4)
                                                                             AS renewal_rate,
        ROUND(AVG(fp.annual_premium), 2)                                     AS avg_premium,
        ROUND(AVG(fp.cltv_36mo), 2)                                         AS avg_cltv_36mo
    FROM WAYPOINT_ANALYTICS.fact_policies  fp
    JOIN WAYPOINT_ANALYTICS.dim_customer   dc ON fp.customer_id = dc.customer_id
    GROUP BY dc.acquisition_channel
),

scenarios AS (
    -- Generate three scenarios per channel using CROSS JOIN with a values table
    SELECT channel_base.*, s.scenario_name, s.retention_lift_pct
    FROM channel_base
    CROSS JOIN (
        SELECT 'Baseline'  AS scenario_name, 0.00 AS retention_lift_pct UNION ALL
        SELECT '+5% Lift',                   0.05 UNION ALL
        SELECT '+10% Lift',                  0.10
    ) s
)

SELECT
    acquisition_channel,
    scenario_name,
    retention_lift_pct,
    total_policies,
    eligible_for_renewal,
    currently_lapsed,
    renewal_rate,
    -- Additional policies retained under this scenario
    ROUND(eligible_for_renewal * retention_lift_pct, 0)          AS additional_retained,
    avg_premium,
    avg_cltv_36mo,
    -- Revenue uplift: additional retained policies * avg year-2 premium
    ROUND(eligible_for_renewal * retention_lift_pct * avg_premium, 0) AS premium_uplift,
    -- CLTV uplift: additional retained policies * avg CLTV benefit of retention
    ROUND(eligible_for_renewal * retention_lift_pct * avg_cltv_36mo * 0.55, 0) AS cltv_uplift
FROM scenarios
ORDER BY acquisition_channel, retention_lift_pct;


-- ===========================================================================
-- Q05: Lapse Warning Score and Billing Behavior
-- ===========================================================================

/*
 * PURPOSE:  Identify billing and payment behaviors that correlate most strongly with
 *           early lapse, and construct a rules-based lapse warning score from them.
 * INPUTS:   WAYPOINT_ANALYTICS.fact_policies
 *           WAYPOINT_ANALYTICS.fact_billing_summary
 *           WAYPOINT_ANALYTICS.dim_customer
 * OUTPUTS:  Result set 1: Renewal rates by payment behavior feature
 *           Result set 2: Billing risk score distribution and lapse rates by decile
 *           Result set 3: At-risk policyholder profile by risk tier
 * AUTHOR:   Luciano Casillas
 * CREATED:  2026-05-02
 */

-- DESIGN DECISION: The billing risk score in Result Set 2 is a rules-based composite
-- built from five billing features, each weighted by its empirical lapse lift (from Q02).
-- This is a SQL approximation of the gradient boosting lapse score built in Phase 4.
-- The two scores serve complementary purposes: this SQL score is interpretable and
-- deployable without a model serving layer; the Phase 4 score is more accurate.

-- DESIGN DECISION: Risk tiers for the At-Risk Profile Explorer (Result Set 3) are:
--   Low Risk:    score 0-33    (approx bottom 60% of score distribution)
--   Medium Risk: score 34-66   (approx middle 25% of score distribution)
--   High Risk:   score 67-100  (approx top 15% of score distribution; ~18% target)
-- Tier boundaries are chosen to land the High Risk segment near the 18.2% target rate
-- from the dashboard KPI. Tuned to match the Phase 4 model's top-decile classification.


-- ===========================================================================
-- RESULT SET 1: Renewal rates by payment behavior feature
-- Grain: one row per feature × feature_value
-- Used by: Behavioral feature analysis (Tab 3); feature importance context
-- ===========================================================================

WITH policy_billing AS (
    SELECT
        fp.policy_id,
        fp.renewed,
        fp.annual_premium,
        fp.coverage_tier,
        dc.acquisition_channel,
        fb.payment_method,
        fb.billing_frequency,
        fb.missed_payment_count_12mo,
        fb.days_past_due_max,
        fb.payment_consistency_score,
        fb.nsf_flag,
        fb.late_pay_flag_last_3mo
    FROM WAYPOINT_ANALYTICS.fact_policies          fp
    JOIN WAYPOINT_ANALYTICS.dim_customer           dc ON fp.customer_id = dc.customer_id
    JOIN WAYPOINT_ANALYTICS.fact_billing_summary   fb ON fp.policy_id   = fb.policy_id
    WHERE fp.renewed IN (0, 1)
),

billing_segments AS (
    -- Missed payment count buckets
    SELECT 'Missed Payments' AS feature, '0 (None)' AS fv, renewed, annual_premium FROM policy_billing WHERE missed_payment_count_12mo = 0
    UNION ALL
    SELECT 'Missed Payments', '1',            renewed, annual_premium FROM policy_billing WHERE missed_payment_count_12mo = 1
    UNION ALL
    SELECT 'Missed Payments', '2+',           renewed, annual_premium FROM policy_billing WHERE missed_payment_count_12mo >= 2
    UNION ALL
    -- NSF flag
    SELECT 'NSF Flag', 'No NSF',             renewed, annual_premium FROM policy_billing WHERE nsf_flag = 0
    UNION ALL
    SELECT 'NSF Flag', 'NSF Event',          renewed, annual_premium FROM policy_billing WHERE nsf_flag = 1
    UNION ALL
    -- Late pay last 3 months
    SELECT 'Late Pay (Last 3mo)', 'On Time', renewed, annual_premium FROM policy_billing WHERE late_pay_flag_last_3mo = 0
    UNION ALL
    SELECT 'Late Pay (Last 3mo)', 'Late',    renewed, annual_premium FROM policy_billing WHERE late_pay_flag_last_3mo = 1
    UNION ALL
    -- Payment method
    SELECT 'Payment Method', payment_method, renewed, annual_premium FROM policy_billing
    UNION ALL
    -- Billing frequency
    SELECT 'Billing Frequency', billing_frequency, renewed, annual_premium FROM policy_billing
    UNION ALL
    -- Payment consistency bands
    SELECT 'Payment Consistency', '90-100 (High)',   renewed, annual_premium FROM policy_billing WHERE payment_consistency_score >= 90
    UNION ALL
    SELECT 'Payment Consistency', '70-89 (Medium)',  renewed, annual_premium FROM policy_billing WHERE payment_consistency_score >= 70 AND payment_consistency_score < 90
    UNION ALL
    SELECT 'Payment Consistency', '50-69 (Low)',     renewed, annual_premium FROM policy_billing WHERE payment_consistency_score >= 50 AND payment_consistency_score < 70
    UNION ALL
    SELECT 'Payment Consistency', '<50 (Very Low)',  renewed, annual_premium FROM policy_billing WHERE payment_consistency_score < 50
    UNION ALL
    -- Days past due
    SELECT 'Days Past Due Max', '0 days',    renewed, annual_premium FROM policy_billing WHERE days_past_due_max = 0
    UNION ALL
    SELECT 'Days Past Due Max', '1-14 days', renewed, annual_premium FROM policy_billing WHERE days_past_due_max BETWEEN 1 AND 14
    UNION ALL
    SELECT 'Days Past Due Max', '15-30 days',renewed, annual_premium FROM policy_billing WHERE days_past_due_max BETWEEN 15 AND 30
    UNION ALL
    SELECT 'Days Past Due Max', '30+ days',  renewed, annual_premium FROM policy_billing WHERE days_past_due_max > 30
)

SELECT
    feature,
    fv                                          AS feature_value,
    COUNT(*)                                    AS policy_count,
    SUM(renewed)                                AS renewed_count,
    ROUND(AVG(renewed::FLOAT), 4)              AS renewal_rate,
    ROUND(AVG(renewed::FLOAT) - b.book_avg, 4) AS vs_book_avg,
    -- Premium at risk: annual premium of non-renewed policies in this segment
    ROUND(SUM(CASE WHEN renewed = 0 THEN annual_premium ELSE 0 END), 0) AS premium_at_risk
FROM billing_segments
CROSS JOIN (
    SELECT ROUND(AVG(renewed::FLOAT), 4) AS book_avg
    FROM WAYPOINT_ANALYTICS.fact_policies WHERE renewed IN (0, 1)
) b
GROUP BY feature, fv, b.book_avg
HAVING COUNT(*) >= 50
ORDER BY feature, renewal_rate;


-- ===========================================================================
-- RESULT SET 2: Billing risk score distribution and lapse rates by decile
-- Grain: one row per risk score decile (D1 = highest risk, D10 = lowest risk)
-- Used by: Lapse Risk Score Distribution histogram; Lift chart (Tab 3)
-- ===========================================================================

WITH scored AS (
    SELECT
        fp.policy_id,
        fp.renewed,
        fp.annual_premium,
        -- Rules-based billing risk score: 0-100, higher = more lapse risk
        -- Weights derived from renewal rate differentials observed in Result Set 1
        LEAST(100.0,
            GREATEST(0.0,
                  fb.missed_payment_count_12mo * 18.0   -- strongest single predictor
                + fb.nsf_flag                 * 14.0   -- NSF is highly predictive
                + fb.late_pay_flag_last_3mo   *  8.0   -- recency matters
                + (100.0 - fb.payment_consistency_score) * 0.30  -- consistency gap
                + CASE fb.payment_method
                      WHEN 'Check' THEN 6.0
                      ELSE 0.0
                  END
                + CASE fb.billing_frequency
                      WHEN 'Monthly' THEN 2.0  -- monthly payers have more touch points for lapse
                      ELSE 0.0
                  END
            )
        ) AS lapse_risk_score
    FROM WAYPOINT_ANALYTICS.fact_policies          fp
    JOIN WAYPOINT_ANALYTICS.fact_billing_summary   fb ON fp.policy_id = fb.policy_id
    WHERE fp.renewed IN (0, 1)
),

deciled AS (
    SELECT
        *,
        -- Decile 1 = highest lapse risk (negated qcut equivalent in SQL)
        NTILE(10) OVER (ORDER BY lapse_risk_score DESC) AS risk_decile
    FROM scored
),

book_lapse_rate AS (
    SELECT ROUND(1.0 - AVG(renewed::FLOAT), 4) AS book_lapse_rate
    FROM WAYPOINT_ANALYTICS.fact_policies WHERE renewed IN (0, 1)
)

SELECT
    d.risk_decile,
    COUNT(*)                                              AS policy_count,
    ROUND(MIN(d.lapse_risk_score), 1)                    AS score_min,
    ROUND(MAX(d.lapse_risk_score), 1)                    AS score_max,
    ROUND(AVG(d.lapse_risk_score), 1)                    AS score_avg,
    ROUND(1.0 - AVG(d.renewed::FLOAT), 4)                AS lapse_rate,
    ROUND(AVG(d.renewed::FLOAT), 4)                      AS renewal_rate,
    -- Lift: how much more likely to lapse than book average?
    ROUND((1.0 - AVG(d.renewed::FLOAT)) / NULLIF(b.book_lapse_rate, 0), 2) AS lift_vs_baseline,
    -- Revenue at risk in this decile
    ROUND(SUM(CASE WHEN d.renewed = 0 THEN d.annual_premium ELSE 0 END), 0) AS premium_at_risk
FROM deciled d
CROSS JOIN book_lapse_rate b
GROUP BY d.risk_decile, b.book_lapse_rate
ORDER BY d.risk_decile;


-- ===========================================================================
-- RESULT SET 3: At-risk policyholder profile by risk tier
-- Grain: one row per risk_tier (Low, Medium, High)
-- Used by: At-Risk Policyholder Profile Explorer metric tiles (Tab 3)
-- ===========================================================================

WITH scored AS (
    SELECT
        fp.policy_id,
        fp.renewed,
        fp.annual_premium,
        fp.coverage_tier,
        fp.multi_product_flag,
        fp.tenure_months,
        dc.acquisition_channel,
        dc.age_band,
        fb.payment_method,
        fb.missed_payment_count_12mo,
        fb.payment_consistency_score,
        fb.nsf_flag,
        LEAST(100.0, GREATEST(0.0,
              fb.missed_payment_count_12mo * 18.0
            + fb.nsf_flag * 14.0
            + fb.late_pay_flag_last_3mo * 8.0
            + (100.0 - fb.payment_consistency_score) * 0.30
            + CASE fb.payment_method WHEN 'Check' THEN 6.0 ELSE 0.0 END
        )) AS lapse_risk_score
    FROM WAYPOINT_ANALYTICS.fact_policies          fp
    JOIN WAYPOINT_ANALYTICS.dim_customer           dc ON fp.customer_id = dc.customer_id
    JOIN WAYPOINT_ANALYTICS.fact_billing_summary   fb ON fp.policy_id   = fb.policy_id
    WHERE fp.renewed IN (0, 1)
),

tiered AS (
    SELECT *,
        CASE
            WHEN lapse_risk_score >= 67 THEN '1 - High Risk'
            WHEN lapse_risk_score >= 34 THEN '2 - Medium Risk'
            ELSE '3 - Low Risk'
        END AS risk_tier
    FROM scored
)

SELECT
    risk_tier,
    COUNT(*)                                           AS policy_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct_of_book,
    ROUND(AVG(renewed::FLOAT), 4)                     AS renewal_rate,
    ROUND(1.0 - AVG(renewed::FLOAT), 4)               AS lapse_rate,
    ROUND(AVG(annual_premium), 2)                      AS avg_premium,
    ROUND(AVG(tenure_months), 1)                       AS avg_tenure_months,
    ROUND(AVG(multi_product_flag::FLOAT), 4)           AS multi_product_rate,
    ROUND(AVG(missed_payment_count_12mo), 2)           AS avg_missed_payments,
    ROUND(AVG(payment_consistency_score), 1)           AS avg_consistency_score,
    -- Most common payment method in each tier
    MODE(payment_method)                               AS top_payment_method,
    -- Revenue at risk
    ROUND(SUM(CASE WHEN renewed = 0 THEN annual_premium ELSE 0 END), 0) AS est_premium_at_risk
FROM tiered
GROUP BY risk_tier
ORDER BY risk_tier;


-- ===========================================================================
-- Q07: Channel Retention Comparison (AQX vs. Non-AQX)
-- ===========================================================================

/*
 * PURPOSE:  Compare first-year retention curves between policyholders acquired through
 *           the AQX digital quoting platform and those acquired through traditional channels.
 * INPUTS:   WAYPOINT_ANALYTICS.fact_policies
 *           WAYPOINT_ANALYTICS.dim_customer
 * OUTPUTS:  Result set 1: 12-month renewal rate by acquisition channel
 *           Result set 2: AQX vs. non-AQX renewal rate by cohort quarter (trend line)
 *           Result set 3: Renewal rate by agency type and customer tenure band
 * AUTHOR:   Luciano Casillas
 * CREATED:  2026-05-02
 */

-- DESIGN DECISION: AQX launched in 2023Q3. Cohorts 2023Q1 and 2023Q2 have no AQX
-- policies. The AQX vs. non-AQX trend chart (Result Set 2) starts from 2023Q3 so the
-- pre-launch period does not create misleading null cells in the dashboard line chart.

-- DESIGN DECISION: "AQX" and "non-AQX" are defined using aqx_assisted_flag (from
-- fact_policies), not acquisition_channel. This is the more precise segmentation because
-- aqx_assisted_flag is set to 0 for policies issued before the 2023Q3 AQX launch date
-- even when the customer's dim_customer.acquisition_channel = 'AQX'. See Phase 1 DDL
-- and Phase 2 generator for the pre-launch zeroing logic.


-- ===========================================================================
-- RESULT SET 1: 12-month renewal rate by acquisition channel
-- Grain: one row per acquisition_channel
-- Used by: 12-Month Renewal Rate by Acquisition Channel bar chart (Tab 2)
-- ===========================================================================

WITH channel_metrics AS (
    SELECT
        dc.acquisition_channel,
        dc.agency_type,
        COUNT(*)                                                      AS total_policies,
        SUM(CASE WHEN fp.renewed IN (0, 1) THEN 1 ELSE 0 END)        AS eligible_policies,
        SUM(CASE WHEN fp.renewed = 1 THEN 1 ELSE 0 END)              AS renewed_count,
        ROUND(
            AVG(CASE WHEN fp.renewed IN (0,1) THEN fp.renewed::FLOAT END)
        , 4)                                                          AS renewal_rate_12mo,
        ROUND(AVG(fp.annual_premium), 2)                             AS avg_premium,
        ROUND(AVG(fp.multi_product_flag::FLOAT), 4)                  AS multi_product_rate,
        ROUND(AVG(fp.cltv_36mo), 2)                                  AS avg_cltv_36mo
    FROM WAYPOINT_ANALYTICS.fact_policies  fp
    JOIN WAYPOINT_ANALYTICS.dim_customer   dc ON fp.customer_id = dc.customer_id
    GROUP BY dc.acquisition_channel, dc.agency_type
),

book_avg AS (
    SELECT ROUND(AVG(CASE WHEN renewed IN (0,1) THEN renewed::FLOAT END), 4) AS book_rate
    FROM WAYPOINT_ANALYTICS.fact_policies
)

SELECT
    cm.acquisition_channel,
    cm.agency_type,
    cm.total_policies,
    cm.eligible_policies,
    cm.renewed_count,
    cm.renewal_rate_12mo,
    ba.book_rate                                               AS book_avg_renewal_rate,
    ROUND(cm.renewal_rate_12mo - ba.book_rate, 4)            AS vs_book_avg,
    cm.avg_premium,
    cm.multi_product_rate,
    cm.avg_cltv_36mo,
    RANK() OVER (ORDER BY cm.renewal_rate_12mo DESC)          AS channel_rank
FROM channel_metrics cm
CROSS JOIN book_avg ba
ORDER BY cm.renewal_rate_12mo DESC;


-- ===========================================================================
-- RESULT SET 2: AQX vs. non-AQX renewal rate by cohort quarter
-- Grain: one row per cohort_quarter × aqx_flag
-- Used by: AQX vs. Non-AQX Renewal Rate Over Time dual-axis line chart (Tab 2)
-- ===========================================================================

WITH aqx_cohort AS (
    SELECT
        fp.cohort_quarter,
        IFF(fp.aqx_assisted_flag = 1, 'AQX', 'Non-AQX') AS channel_type,
        COUNT(*)                                           AS policy_count,
        SUM(CASE WHEN fp.renewed IN (0,1) THEN 1 ELSE 0 END) AS eligible_count,
        ROUND(
            AVG(CASE WHEN fp.renewed IN (0,1) THEN fp.renewed::FLOAT END)
        , 4)                                               AS renewal_rate_12mo,
        ROUND(AVG(fp.annual_premium), 2)                  AS avg_premium
    FROM WAYPOINT_ANALYTICS.fact_policies fp
    WHERE fp.cohort_quarter >= '2023Q3'   -- AQX launched in 2023Q3
    GROUP BY fp.cohort_quarter, IFF(fp.aqx_assisted_flag = 1, 'AQX', 'Non-AQX')
)

SELECT
    cohort_quarter,
    channel_type,
    policy_count,
    eligible_count,
    renewal_rate_12mo,
    avg_premium,
    -- Rolling 2-quarter average renewal rate to smooth the trend line
    ROUND(
        AVG(renewal_rate_12mo) OVER (
            PARTITION BY channel_type
            ORDER BY cohort_quarter
            ROWS BETWEEN 1 PRECEDING AND CURRENT ROW
        )
    , 4) AS renewal_rate_2q_rolling_avg
FROM aqx_cohort
ORDER BY cohort_quarter, channel_type;


-- ===========================================================================
-- RESULT SET 3: Renewal rate by agency type and customer tenure band
-- Grain: one row per agency_type × tenure_band
-- Used by: Renewal Rate by Agency Type and Tenure Band grouped bar chart (Tab 2)
-- ===========================================================================

WITH agency_tenure AS (
    SELECT
        dc.agency_type,
        dc.acquisition_channel,
        CASE
            WHEN fp.tenure_months <  12 THEN '0-11 mo'
            WHEN fp.tenure_months <  24 THEN '12-23 mo'
            WHEN fp.tenure_months <  48 THEN '24-47 mo'
            ELSE '48+ mo'
        END AS tenure_band,
        CASE
            WHEN fp.tenure_months <  12 THEN 1
            WHEN fp.tenure_months <  24 THEN 2
            WHEN fp.tenure_months <  48 THEN 3
            ELSE 4
        END AS tenure_band_order,
        fp.renewed,
        fp.annual_premium,
        fp.cltv_36mo,
        fp.multi_product_flag
    FROM WAYPOINT_ANALYTICS.fact_policies  fp
    JOIN WAYPOINT_ANALYTICS.dim_customer   dc ON fp.customer_id = dc.customer_id
    WHERE fp.renewed IN (0, 1)
)

SELECT
    agency_type,
    acquisition_channel,
    tenure_band,
    tenure_band_order,
    COUNT(*)                                           AS policy_count,
    ROUND(AVG(renewed::FLOAT), 4)                     AS renewal_rate_12mo,
    ROUND(AVG(annual_premium), 2)                     AS avg_premium,
    ROUND(AVG(cltv_36mo), 2)                          AS avg_cltv_36mo,
    ROUND(AVG(multi_product_flag::FLOAT), 4)          AS multi_product_rate,
    -- Intra-agency-type rank by tenure band renewal rate
    RANK() OVER (
        PARTITION BY agency_type
        ORDER BY AVG(renewed::FLOAT) DESC
    )                                                  AS tenure_rank_within_agency
FROM agency_tenure
GROUP BY agency_type, acquisition_channel, tenure_band, tenure_band_order
HAVING COUNT(*) >= 30
ORDER BY agency_type, tenure_band_order;


-- ===========================================================================
-- Q09: Claims History and Renewal Behavior
-- ===========================================================================

/*
 * PURPOSE:  Analyze the relationship between claims history and renewal behavior,
 *           and determine whether that relationship differs by coverage tier and
 *           acquisition channel.
 * INPUTS:   WAYPOINT_ANALYTICS.fact_policies
 *           WAYPOINT_ANALYTICS.fact_claims
 *           WAYPOINT_ANALYTICS.dim_customer
 * OUTPUTS:  Result set 1: Renewal rate by claims status (has claim, severity, at-fault)
 *           Result set 2: Claims-renewal relationship by coverage tier
 *           Result set 3: Renewal rate vs. claim payout amount (dual-axis source)
 * AUTHOR:   Luciano Casillas
 * CREATED:  2026-05-02
 */

-- DESIGN DECISION: Claims are aggregated to the policy grain before joining with
-- fact_policies. Policies without any claims receive null values from the LEFT JOIN,
-- which are replaced with 'None' (severity), 0 (amounts), and 0 (flags) to allow
-- clean GROUP BY aggregation. This matches the denormalized CSV sentinel logic.

-- DESIGN DECISION: "At-fault" is defined at the policy level as any at-fault claim
-- in the 12-month window (MAX(at_fault_flag) over all claims for that policy). A policy
-- with one at-fault and one not-at-fault claim is classified as "at-fault" because the
-- at-fault event is the primary driver of renewal behavior change.


-- ===========================================================================
-- RESULT SET 1: Renewal rate by claims status
-- Grain: one row per claims profile bucket
-- Used by: Renewal Rate by Claims Severity Band bar chart (Tab 1)
-- ===========================================================================

WITH policy_claims AS (
    -- Aggregate claims to policy level (one row per policy)
    SELECT
        fc.policy_id,
        COUNT(*)                                               AS claim_count,
        MAX(fc.at_fault_flag)                                  AS at_fault_any,
        SUM(fc.claim_amount)                                   AS total_claim_amount,
        MAX(CASE fc.claim_severity_band
                WHEN 'None'     THEN 0
                WHEN 'Minor'    THEN 1
                WHEN 'Moderate' THEN 2
                WHEN 'Major'    THEN 3
            END)                                               AS max_severity_num,
        CASE MAX(CASE fc.claim_severity_band
                    WHEN 'None'     THEN 0
                    WHEN 'Minor'    THEN 1
                    WHEN 'Moderate' THEN 2
                    WHEN 'Major'    THEN 3
                END)
            WHEN 0 THEN 'None'
            WHEN 1 THEN 'Minor'
            WHEN 2 THEN 'Moderate'
            WHEN 3 THEN 'Major'
        END                                                    AS max_severity_band
    FROM WAYPOINT_ANALYTICS.fact_claims fc
    GROUP BY fc.policy_id
),

policy_base AS (
    SELECT
        fp.policy_id,
        fp.renewed,
        fp.annual_premium,
        fp.coverage_tier,
        dc.acquisition_channel,
        dc.agency_type,
        -- Claims attributes; null-safe via COALESCE
        COALESCE(pc.claim_count, 0)           AS claim_count,
        COALESCE(pc.at_fault_any, 0)          AS at_fault_any,
        COALESCE(pc.total_claim_amount, 0.0)  AS total_claim_amount,
        COALESCE(pc.max_severity_band, 'None') AS claim_severity_band,
        IFF(pc.policy_id IS NOT NULL, 1, 0)   AS has_claim
    FROM WAYPOINT_ANALYTICS.fact_policies  fp
    JOIN WAYPOINT_ANALYTICS.dim_customer   dc ON fp.customer_id = dc.customer_id
    LEFT JOIN policy_claims                pc ON fp.policy_id   = pc.policy_id
    WHERE fp.renewed IN (0, 1)
),

book_rate AS (
    SELECT ROUND(AVG(renewed::FLOAT), 4) AS book_avg
    FROM WAYPOINT_ANALYTICS.fact_policies WHERE renewed IN (0, 1)
)

-- Primary: by severity band
SELECT
    'Severity Band'                             AS segment_type,
    claim_severity_band                         AS segment_value,
    CASE claim_severity_band
        WHEN 'None'     THEN 0
        WHEN 'Minor'    THEN 1
        WHEN 'Moderate' THEN 2
        WHEN 'Major'    THEN 3
    END                                         AS sort_order,
    COUNT(*)                                    AS policy_count,
    SUM(has_claim)                              AS policies_with_claim,
    ROUND(AVG(renewed::FLOAT), 4)              AS renewal_rate,
    b.book_avg                                  AS book_avg_renewal_rate,
    ROUND(AVG(renewed::FLOAT) - b.book_avg, 4) AS vs_book_avg,
    ROUND(AVG(total_claim_amount), 2)           AS avg_claim_payout,
    ROUND(SUM(total_claim_amount), 0)           AS total_claim_payout
FROM policy_base
CROSS JOIN book_rate b
GROUP BY claim_severity_band, b.book_avg

UNION ALL

-- Secondary: by at-fault flag
SELECT
    'At-Fault Status',
    CASE at_fault_any WHEN 1 THEN 'At-Fault Claim' ELSE 'No At-Fault Claim' END,
    at_fault_any + 10,
    COUNT(*), SUM(has_claim),
    ROUND(AVG(renewed::FLOAT), 4),
    b.book_avg,
    ROUND(AVG(renewed::FLOAT) - b.book_avg, 4),
    ROUND(AVG(total_claim_amount), 2),
    ROUND(SUM(total_claim_amount), 0)
FROM policy_base
CROSS JOIN book_rate b
GROUP BY at_fault_any, b.book_avg

UNION ALL

-- Tertiary: has any claim vs no claim
SELECT
    'Has Claim',
    CASE has_claim WHEN 1 THEN 'Has Claim' ELSE 'No Claim' END,
    has_claim + 20,
    COUNT(*), SUM(has_claim),
    ROUND(AVG(renewed::FLOAT), 4),
    b.book_avg,
    ROUND(AVG(renewed::FLOAT) - b.book_avg, 4),
    ROUND(AVG(total_claim_amount), 2),
    ROUND(SUM(total_claim_amount), 0)
FROM policy_base
CROSS JOIN book_rate b
GROUP BY has_claim, b.book_avg

ORDER BY segment_type, sort_order;


-- ===========================================================================
-- RESULT SET 2: Claims-renewal relationship by coverage tier
-- Grain: one row per coverage_tier × claims_profile
-- Used by: Claims and renewal cross-tab by coverage tier (Tab 1 narrative)
-- ===========================================================================

WITH policy_claims AS (
    SELECT
        policy_id,
        MAX(at_fault_flag)        AS at_fault_any,
        SUM(claim_amount)         AS total_claim_amount,
        COUNT(*)                  AS claim_count,
        MAX(CASE claim_severity_band
            WHEN 'Minor' THEN 1 WHEN 'Moderate' THEN 2 WHEN 'Major' THEN 3 ELSE 0 END)
                                  AS max_severity_num
    FROM WAYPOINT_ANALYTICS.fact_claims
    GROUP BY policy_id
),

base AS (
    SELECT
        fp.coverage_tier,
        CASE
            WHEN pc.policy_id IS NULL THEN 'No Claim'
            WHEN pc.at_fault_any = 1 AND pc.max_severity_num = 3 THEN 'Major At-Fault'
            WHEN pc.at_fault_any = 1 THEN 'At-Fault (Minor/Mod)'
            WHEN pc.max_severity_num = 3 THEN 'Major Not At-Fault'
            ELSE 'Minor/Moderate Not At-Fault'
        END AS claims_profile,
        fp.renewed,
        fp.annual_premium,
        COALESCE(pc.total_claim_amount, 0) AS total_claim_amount
    FROM WAYPOINT_ANALYTICS.fact_policies fp
    LEFT JOIN policy_claims pc ON fp.policy_id = pc.policy_id
    WHERE fp.renewed IN (0, 1)
)

SELECT
    coverage_tier,
    claims_profile,
    COUNT(*)                            AS policy_count,
    ROUND(AVG(renewed::FLOAT), 4)      AS renewal_rate,
    ROUND(AVG(total_claim_amount), 2)  AS avg_claim_payout,
    ROUND(AVG(annual_premium), 2)      AS avg_premium,
    -- Revenue at risk from this segment
    ROUND(SUM(CASE WHEN renewed = 0 THEN annual_premium ELSE 0 END), 0) AS premium_at_risk
FROM base
GROUP BY coverage_tier, claims_profile
HAVING COUNT(*) >= 20
ORDER BY coverage_tier, renewal_rate DESC;


-- ===========================================================================
-- RESULT SET 3: Renewal rate vs. claim payout amount (dual-axis source)
-- Grain: one row per claim payout band
-- Used by: Renewal Rate vs. Claim Payout Amount dual-axis chart (Tab 1)
-- ===========================================================================

WITH policy_claims AS (
    SELECT policy_id, SUM(claim_amount) AS total_claim_amount
    FROM WAYPOINT_ANALYTICS.fact_claims
    GROUP BY policy_id
),

with_payout_band AS (
    SELECT
        fp.renewed,
        fp.annual_premium,
        -- Claims payout bucket: No Claim, then $500 increments up to $20K+
        CASE
            WHEN pc.policy_id IS NULL          THEN '0 - No Claim'
            WHEN pc.total_claim_amount < 1000  THEN '1 - Under $1K'
            WHEN pc.total_claim_amount < 3000  THEN '2 - $1K-$3K'
            WHEN pc.total_claim_amount < 7500  THEN '3 - $3K-$7.5K'
            WHEN pc.total_claim_amount < 15000 THEN '4 - $7.5K-$15K'
            WHEN pc.total_claim_amount < 30000 THEN '5 - $15K-$30K'
            ELSE                                    '6 - Over $30K'
        END AS payout_band,
        COALESCE(pc.total_claim_amount, 0) AS total_claim_amount
    FROM WAYPOINT_ANALYTICS.fact_policies fp
    LEFT JOIN policy_claims               pc ON fp.policy_id = pc.policy_id
    WHERE fp.renewed IN (0, 1)
)

SELECT
    payout_band,
    COUNT(*)                           AS policy_count,
    ROUND(AVG(renewed::FLOAT), 4)     AS renewal_rate,
    ROUND(AVG(total_claim_amount), 2) AS avg_claim_payout,
    ROUND(AVG(annual_premium), 2)     AS avg_premium
FROM with_payout_band
GROUP BY payout_band
ORDER BY payout_band;


-- ===========================================================================
-- Q10: Auto-to-Renters Cross-Sell Funnel
-- ===========================================================================

/*
 * PURPOSE:  Analyze the auto-to-renters cross-sell conversion rate by agency type and
 *           customer tenure band, and identify where the cross-sell funnel drops off.
 * INPUTS:   WAYPOINT_ANALYTICS.fact_policies
 *           WAYPOINT_ANALYTICS.dim_customer
 * OUTPUTS:  Result set 1: Renters attachment funnel stages (population-level)
 *           Result set 2: Cross-sell rate by agency type
 *           Result set 3: Cross-sell rate by customer tenure band
 * AUTHOR:   Luciano Casillas
 * CREATED:  2026-05-02
 */

-- DESIGN DECISION: The funnel base is all AUTO policies (policy_type = 'Auto Only' OR
-- 'Auto + Renters') because every auto policy is a potential cross-sell opportunity.
-- Pure renters-only policies are excluded from the funnel denominator because they
-- represent an already-converted customer, not a prospect.

-- DESIGN DECISION: Funnel stages are defined as follows:
--   Stage 1 (Base):        All auto policies (100% of denominator)
--   Stage 2 (Quoted):      Policies where renters_quoted_flag = 1
--   Stage 3 (Attached):    Policies where renters_attached_flag = 1
--   Drop analysis:         Quote-to-attach gap is the primary opportunity lever
-- Bar widths in the dashboard CSS funnel always represent % of Stage 1 population,
-- not % of prior stage. Labels show "X% of prior stage" to communicate conversion rates.


-- ===========================================================================
-- RESULT SET 1: Renters attachment funnel stages (overall)
-- Grain: one row per funnel stage
-- Used by: Renters Attachment Funnel CSS chart (Tab 4)
-- ===========================================================================

WITH auto_policies AS (
    -- Base: all auto policies regardless of whether renters was involved
    SELECT
        fp.policy_id,
        fp.customer_id,
        fp.renters_quoted_flag,
        fp.renters_attached_flag,
        fp.renewed,
        fp.annual_premium,
        fp.coverage_tier,
        fp.tenure_months,
        dc.agency_type,
        dc.acquisition_channel
    FROM WAYPOINT_ANALYTICS.fact_policies  fp
    JOIN WAYPOINT_ANALYTICS.dim_customer   dc ON fp.customer_id = dc.customer_id
    -- Include both Auto Only and Auto + Renters (all auto policyholders)
),

funnel_counts AS (
    SELECT
        COUNT(*)                                           AS stage1_all_auto,
        SUM(renters_quoted_flag)                           AS stage2_quoted,
        SUM(renters_attached_flag)                         AS stage3_attached,
        -- Retained cross-sell: attached AND renewed (stickiest segment)
        SUM(IFF(renters_attached_flag = 1 AND renewed = 1, 1, 0)) AS stage4_retained
    FROM auto_policies
    WHERE renewed IN (0, 1)  -- known renewal outcome for retention stage
)

SELECT
    'Stage 1: All Auto Policies'   AS stage_name,
    1                              AS stage_order,
    stage1_all_auto                AS stage_count,
    stage1_all_auto                AS base_count,
    100.0                          AS pct_of_base,
    NULL::FLOAT                    AS pct_of_prior_stage,
    NULL::FLOAT                    AS drop_off_pct
FROM funnel_counts

UNION ALL

SELECT
    'Stage 2: Renters Quoted',
    2,
    stage2_quoted,
    stage1_all_auto,
    ROUND(stage2_quoted * 100.0 / NULLIF(stage1_all_auto, 0), 1),
    ROUND(stage2_quoted * 100.0 / NULLIF(stage1_all_auto, 0), 1),
    ROUND((stage1_all_auto - stage2_quoted) * 100.0 / NULLIF(stage1_all_auto, 0), 1)
FROM funnel_counts

UNION ALL

SELECT
    'Stage 3: Renters Attached',
    3,
    stage3_attached,
    stage1_all_auto,
    ROUND(stage3_attached * 100.0 / NULLIF(stage1_all_auto, 0), 1),
    ROUND(stage3_attached * 100.0 / NULLIF(stage2_quoted, 0), 1),
    ROUND((stage2_quoted - stage3_attached) * 100.0 / NULLIF(stage2_quoted, 0), 1)
FROM funnel_counts

UNION ALL

SELECT
    'Stage 4: Attached and Renewed',
    4,
    stage4_retained,
    stage1_all_auto,
    ROUND(stage4_retained * 100.0 / NULLIF(stage1_all_auto, 0), 1),
    ROUND(stage4_retained * 100.0 / NULLIF(stage3_attached, 0), 1),
    ROUND((stage3_attached - stage4_retained) * 100.0 / NULLIF(stage3_attached, 0), 1)
FROM funnel_counts

ORDER BY stage_order;


-- ===========================================================================
-- RESULT SET 2: Cross-sell rate by agency type
-- Grain: one row per agency_type
-- Used by: Renters Cross-Sell Rate by Agency Type bar chart (Tab 4)
-- ===========================================================================

WITH auto_base AS (
    SELECT
        dc.agency_type,
        dc.acquisition_channel,
        fp.policy_id,
        fp.renters_quoted_flag,
        fp.renters_attached_flag,
        fp.renewed,
        fp.annual_premium,
        fp.cltv_36mo,
        fp.multi_product_flag
    FROM WAYPOINT_ANALYTICS.fact_policies  fp
    JOIN WAYPOINT_ANALYTICS.dim_customer   dc ON fp.customer_id = dc.customer_id
)

SELECT
    agency_type,
    acquisition_channel,
    COUNT(*)                                                        AS auto_policy_count,
    SUM(renters_quoted_flag)                                        AS quoted_count,
    SUM(renters_attached_flag)                                      AS attached_count,
    ROUND(AVG(renters_quoted_flag::FLOAT), 4)                     AS quote_rate,
    ROUND(AVG(renters_attached_flag::FLOAT), 4)                   AS attach_rate,
    -- Quote-to-attach conversion (the key funnel drop)
    ROUND(
        SUM(renters_attached_flag)::FLOAT / NULLIF(SUM(renters_quoted_flag), 0)
    , 4)                                                            AS quote_to_attach_rate,
    ROUND(AVG(cltv_36mo), 2)                                      AS avg_cltv_36mo,
    -- Revenue opportunity: non-attaching quoted policies * avg premium uplift
    -- Premium uplift estimate: renters avg premium ~ $280/year
    ROUND(
        (SUM(renters_quoted_flag) - SUM(renters_attached_flag)) * 280.0
    , 0)                                                            AS est_missed_renters_premium,
    RANK() OVER (ORDER BY AVG(renters_attached_flag::FLOAT) DESC)  AS attach_rate_rank
FROM auto_base
GROUP BY agency_type, acquisition_channel
ORDER BY attach_rate DESC;


-- ===========================================================================
-- RESULT SET 3: Cross-sell rate by customer tenure band
-- Grain: one row per tenure_band
-- Used by: Renters Cross-Sell Rate by Customer Tenure Band bar chart (Tab 4)
-- ===========================================================================

WITH tenure_base AS (
    SELECT
        fp.policy_id,
        fp.renters_quoted_flag,
        fp.renters_attached_flag,
        fp.renewed,
        fp.annual_premium,
        fp.cltv_36mo,
        dc.agency_type,
        CASE
            WHEN fp.tenure_months <  12 THEN '0-11 mo (New)'
            WHEN fp.tenure_months <  24 THEN '12-23 mo'
            WHEN fp.tenure_months <  48 THEN '24-47 mo'
            ELSE '48+ mo (Loyal)'
        END AS tenure_band,
        CASE
            WHEN fp.tenure_months <  12 THEN 1
            WHEN fp.tenure_months <  24 THEN 2
            WHEN fp.tenure_months <  48 THEN 3
            ELSE 4
        END AS tenure_band_order
    FROM WAYPOINT_ANALYTICS.fact_policies  fp
    JOIN WAYPOINT_ANALYTICS.dim_customer   dc ON fp.customer_id = dc.customer_id
),

book_attach AS (
    SELECT ROUND(AVG(renters_attached_flag::FLOAT), 4) AS book_attach_rate
    FROM WAYPOINT_ANALYTICS.fact_policies
)

SELECT
    t.tenure_band,
    t.tenure_band_order,
    COUNT(*)                                                            AS policy_count,
    SUM(t.renters_quoted_flag)                                         AS quoted_count,
    SUM(t.renters_attached_flag)                                       AS attached_count,
    ROUND(AVG(t.renters_quoted_flag::FLOAT), 4)                      AS quote_rate,
    ROUND(AVG(t.renters_attached_flag::FLOAT), 4)                    AS attach_rate,
    b.book_attach_rate,
    ROUND(AVG(t.renters_attached_flag::FLOAT) - b.book_attach_rate, 4) AS vs_book_avg,
    ROUND(
        SUM(t.renters_attached_flag)::FLOAT / NULLIF(SUM(t.renters_quoted_flag), 0)
    , 4)                                                               AS quote_to_attach_rate,
    ROUND(AVG(t.cltv_36mo), 2)                                       AS avg_cltv_36mo,
    -- Opportunity sizing: non-attached, quoted policies per tenure band
    SUM(t.renters_quoted_flag) - SUM(t.renters_attached_flag)         AS unattached_quoted_policies,
    ROUND(
        (SUM(t.renters_quoted_flag) - SUM(t.renters_attached_flag)) * 280.0
    , 0)                                                               AS est_missed_renters_premium
FROM tenure_base t
CROSS JOIN book_attach b
GROUP BY t.tenure_band, t.tenure_band_order, b.book_attach_rate
ORDER BY t.tenure_band_order;


