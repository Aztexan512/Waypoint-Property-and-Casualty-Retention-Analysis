# Waypoint Property & Casualty -- Data Dictionary

**Project:** waypoint-retention-analytics
**File:** data/waypoint_retention.csv
**Grain:** One row per issued policy
**Rows:** 90,000
**Author:** Luciano Casillas
**Date:** 2026-05-02

---

## Overview

`waypoint_retention.csv` is the denormalized analysis-ready dataset. It flattens all five source
tables (dim_customer, fact_policies, fact_renewals, fact_billing_summary, fact_claims) into a
single policy-grain CSV. Claims are aggregated from fact_claims (many rows per policy) into
summary columns. Leakage-prone columns are included in the file but excluded from model training.

---

## Column Reference

### Customer Dimensions (from dim_customer)

| Column | Type | Source Table | Allowed Values | Description |
|---|---|---|---|---|
| customer_id | string | dim_customer | UUID | Policyholder account identifier |
| age_band | string | dim_customer | 18-25, 26-35, 36-45, 46-55, 56-65, 65+ | Age group at policy effective date |
| state | string | dim_customer | TX, FL, OH, GA, NC, VA, TN, IN, KY, MO, SC, AL, AZ, CO | State of residence (2-letter code) |
| metro_area | string | dim_customer | See state_list.csv | Metro area name or Rural designation |
| homeowner_flag | int | dim_customer | 0, 1 | 1 = owns home at time of policy bind |
| prior_insurance_flag | int | dim_customer | 0, 1 | 1 = had prior insurance coverage at bind |
| years_with_carrier | float | dim_customer | >= 0 | Customer tenure in years at policy effective date |
| acquisition_channel | string | dim_customer | Agency Portal, AQX, Direct Web, Phone, Referral | Channel through which the customer was acquired |
| agency_type | string | dim_customer | Independent, Captive, Digital Partner, Direct | Agency distribution type |
| aqx_assisted_flag | int | dim_customer | 0, 1 | 1 = quote completed via Auto Quote Explorer (AQX) digital platform |

### Policy Attributes (from fact_policies)

| Column | Type | Source Table | Allowed Values | Description |
|---|---|---|---|---|
| policy_id | string | fact_policies | UUID | Policy identifier; primary key of the denormalized dataset |
| policy_type | string | fact_policies | Auto Only, Auto + Renters | Coverage type bound at policy effective date |
| coverage_tier | string | fact_policies | Liability Only, Standard, Premium, Elite | Coverage tier at policy effective date |
| annual_premium | float | fact_policies | > 0 | Annual premium at policy effective date (USD) |
| effective_date | date | fact_policies | 2023-01-01 to 2025-12-31 | Policy start date |
| cohort_quarter | string | fact_policies | 2023Q1 to 2025Q4 | Acquisition cohort label in YYYYQN format |
| tenure_months | int | fact_policies | >= 0 | Months since customer's first policy with carrier at effective date |
| multi_product_flag | int | fact_policies | 0, 1 | 1 = customer holds both auto and renters policies |
| renters_quoted_flag | int | fact_policies | 0, 1 | 1 = renters coverage was offered at quote |
| renters_attached_flag | int | fact_policies | 0, 1 | 1 = renters policy was bound alongside auto policy |

### Billing and Payment Behavior (from fact_billing_summary)

| Column | Type | Source Table | Allowed Values | Description |
|---|---|---|---|---|
| payment_method | string | fact_billing_summary | Credit Card, Bank Draft, Check, Digital Wallet | Primary payment method on file |
| billing_frequency | string | fact_billing_summary | Monthly, Semi-Annual, Annual | Billing cycle selected at policy effective date |
| missed_payment_count | int | fact_billing_summary | >= 0 | Number of missed payments in the first 12 months of the policy term |
| days_past_due_max | int | fact_billing_summary | >= 0 | Maximum days past due on any single payment in the first 12 months |
| payment_consistency | float | fact_billing_summary | 0 to 100 | Payment regularity score (100 = no missed payments). Composite of missed_payment_count, days_past_due_max, nsf_flag. |
| nsf_flag | int | fact_billing_summary | 0, 1 | 1 = at least one returned or NSF payment event in the policy term |
| late_pay_flag_3mo | int | fact_billing_summary | 0, 1 | 1 = at least one late payment in the most recent 3 months of the term |

**Note on column aliases:** `missed_payment_count` maps to `missed_payment_count_12mo` in
fact_billing_summary. `payment_consistency` maps to `payment_consistency_score`. `late_pay_flag_3mo`
maps to `late_pay_flag_last_3mo`. Aliases are used in the denormalized CSV for brevity.

### Claims Summary (aggregated from fact_claims)

| Column | Type | Source Table | Allowed Values | Description |
|---|---|---|---|---|
| has_claim_12mo | int | fact_claims (agg) | 0, 1 | 1 = policy had at least one claim filed in the first 12 months |
| claim_count_12mo | int | fact_claims (agg) | >= 0 | Number of claims filed in the first 12 months |
| total_claim_amount | float | fact_claims (agg) | >= 0 | Total claim payout across all claims in the first 12 months (USD) |
| claim_severity_band | string | fact_claims (agg) | None, Minor, Moderate, Major | Worst (highest) severity band across all claims; None if no claims |
| days_since_last_claim | int | fact_claims (agg) | >= 0, NULL | Days between most recent claim date and policy effective date; NULL if no claims |

**Aggregation logic:** Claims are filtered to `claim_date <= effective_date + 365 days` before
aggregation to enforce the 12-month window. `claim_severity_band` takes the maximum severity
using the order: None < Minor < Moderate < Major.

### Renewal Outcome and Metadata (from fact_renewals + fact_policies)

| Column | Type | Source Table | Allowed Values | Description |
|---|---|---|---|---|
| renewed | int | fact_policies | 0, 1, NULL | TARGET COLUMN: 1 = renewed at 12-month mark, 0 = lapsed or cancelled, NULL = renewal window not yet reached |
| renewal_month_label | string | fact_renewals | YYYYMM | Month in which the renewal decision was made |
| days_to_decision | int | fact_renewals | >= 0 | Days from renewal offer date to policyholder decision |

---

## Leakage-Prone Columns

These columns are included in the denormalized CSV for completeness and CLTV analysis but
**must be excluded from model training** for Q02 and Q05.

| Column | Leakage Risk | Reason |
|---|---|---|
| cltv_36mo | HIGH | Derived from the full 36-month policy outcome. Not available at renewal time. |
| renewal_premium_change_pct | HIGH | Generated when the renewal offer is created; only known after the renewal decision process begins. |
| post_renewal_coverage_tier | HIGH | Reflects the coverage tier on the renewed policy; only known after renewal decision. |
| outreach_contact_flag | CONDITIONAL | Legitimate feature only if the outreach contact date is confirmed to precede renewal_decision_date. Use with strict date guard. |

---

## Key Rates and Benchmarks

These rates are embedded in the data generation config and should be observable in the dataset.

| Metric | Target Value |
|---|---|
| Overall 12-month renewal rate | 74.8% |
| Multi-product attach rate | 28.3% |
| AQX channel renewal rate | 83.0% |
| Direct Web channel renewal rate | 68.0% |
| Policyholders classified as high-risk | 18.2% |
| Average annual premium | $1,580 |
| Average 36-month CLTV | $1,842 |

---

## Recommended Modeling Filters

For classification models (Q02, Q05):
```sql
WHERE renewed IS NOT NULL          -- exclude policies without a known renewal outcome
  AND effective_date <= '2024-12-31'  -- equivalent filter; ~72,000 rows
```

For CLTV analysis (Q04):
```sql
-- cltv_36mo is permissible in descriptive analysis; exclude from predictive features only
```

For cohort retention analysis (Q01):
```sql
-- Include all cohort_quarter values; null renewed rows plot as missing in heatmap cells
```
