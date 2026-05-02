# Waypoint Property & Casualty -- Table Definitions

**Project:** waypoint-retention-analytics
**Schema:** WAYPOINT_ANALYTICS
**Author:** Luciano Casillas
**Date:** 2026-05-02

---

## Overview

Five source tables reflect how retention data lives in a real insurance system. They are joined
into one denormalized analysis-ready CSV (`data/waypoint_retention.csv`) at policy grain for
SQL analysis and machine learning.

| Table | Grain | Approx Rows | Role |
|---|---|---|---|
| dim_customer | One row per policyholder account | ~72,000 | Dimension |
| fact_policies | One row per issued policy | 90,000 | Primary fact (central join hub) |
| fact_renewals | One row per 12-month renewal event | ~72,000 | Renewal event fact |
| fact_billing_summary | One row per policy (billing summary) | 90,000 | 1-to-1 policy extension |
| fact_claims | One row per claim filed | ~19,000 | Sparse claims fact |

---

## dim_customer

**Grain:** One row per policyholder account
**Approx rows:** ~72,000
**Primary key:** customer_id
**Joins to:** fact_policies on customer_id

| Column | Type | Nullable | Description |
|---|---|---|---|
| customer_id | VARCHAR(36) | NOT NULL | Policyholder account identifier (UUID) |
| age_band | VARCHAR(10) | NOT NULL | Age group: 18-25, 26-35, 36-45, 46-55, 56-65, 65+ |
| state | VARCHAR(2) | NOT NULL | State of residence (2-letter code); 14 operating states |
| metro_area | VARCHAR(100) | NOT NULL | Metro area name or Rural designation |
| homeowner_flag | INTEGER | NOT NULL | 1 = owns home at time of policy bind |
| prior_insurance_flag | INTEGER | NOT NULL | 1 = had prior insurance at bind |
| years_with_carrier | FLOAT | NOT NULL | Tenure in years at policy effective date |
| acquisition_channel | VARCHAR(20) | NOT NULL | Agency Portal, AQX, Direct Web, Phone, Referral |
| agency_type | VARCHAR(20) | NOT NULL | Independent, Captive, Digital Partner, Direct |
| aqx_assisted_flag | INTEGER | NOT NULL | 1 = quote completed via AQX platform |

**Allowed values:**
- age_band: `18-25`, `26-35`, `36-45`, `46-55`, `56-65`, `65+`
- state: `TX`, `FL`, `OH`, `GA`, `NC`, `VA`, `TN`, `IN`, `KY`, `MO`, `SC`, `AL`, `AZ`, `CO`
- acquisition_channel: `Agency Portal`, `AQX`, `Direct Web`, `Phone`, `Referral`
- agency_type: `Independent`, `Captive`, `Digital Partner`, `Direct`

---

## fact_policies

**Grain:** One row per issued policy
**Approx rows:** 90,000
**Primary key:** policy_id
**Foreign keys:** customer_id -> dim_customer
**Joins to:** fact_renewals, fact_billing_summary, fact_claims on policy_id

| Column | Type | Nullable | Description |
|---|---|---|---|
| policy_id | VARCHAR(36) | NOT NULL | Policy identifier (UUID) |
| customer_id | VARCHAR(36) | NOT NULL | FK to dim_customer |
| policy_type | VARCHAR(20) | NOT NULL | Auto Only, Auto + Renters |
| coverage_tier | VARCHAR(20) | NOT NULL | Liability Only, Standard, Premium, Elite |
| annual_premium | FLOAT | NOT NULL | Annual premium at effective date (USD) |
| effective_date | DATE | NOT NULL | Policy start date |
| cohort_quarter | VARCHAR(7) | NOT NULL | Acquisition cohort in YYYYQN format (e.g., 2023Q1) |
| tenure_months | INTEGER | NOT NULL | Months since customer's first policy with carrier |
| multi_product_flag | INTEGER | NOT NULL | 1 = customer holds both auto and renters policies |
| renters_quoted_flag | INTEGER | NOT NULL | 1 = renters coverage was offered at quote |
| renters_attached_flag | INTEGER | NOT NULL | 1 = renters policy was bound |
| renewed | INTEGER | NULLABLE | TARGET: 1 = renewed, 0 = lapsed/cancelled, NULL = window not reached |

**Allowed values:**
- policy_type: `Auto Only`, `Auto + Renters`
- coverage_tier: `Liability Only`, `Standard`, `Premium`, `Elite`
- cohort_quarter: `2023Q1` through `2025Q4`

**Note on renewed:** Policies effective after 2024-12-31 have `renewed = NULL` because the
12-month renewal window extends beyond the dataset end date of 2025-12-31. Approximately
18,000 rows are expected to have NULL renewed. Analysis and modeling should filter to
`renewed IS NOT NULL` or `effective_date <= '2024-12-31'`.

---

## fact_renewals

**Grain:** One row per 12-month renewal event
**Approx rows:** ~72,000
**Primary key:** renewal_id
**Foreign keys:** policy_id -> fact_policies, customer_id -> dim_customer
**Joins to:** fact_policies on policy_id

| Column | Type | Nullable | Description |
|---|---|---|---|
| renewal_id | VARCHAR(36) | NOT NULL | Renewal event identifier (UUID) |
| policy_id | VARCHAR(36) | NOT NULL | FK to fact_policies |
| customer_id | VARCHAR(36) | NOT NULL | FK to dim_customer (denormalized) |
| renewal_decision_date | DATE | NOT NULL | Date the renewal or lapse decision was made |
| renewed | INTEGER | NOT NULL | 1 = renewed, 0 = lapsed or cancelled |
| days_to_decision | INTEGER | NOT NULL | Days from renewal offer to decision |
| renewal_premium_change_pct | FLOAT | NOT NULL | Premium change from prior term to renewal offer (%). LEAKAGE: exclude from model training. |
| outreach_contact_flag | INTEGER | NOT NULL | 1 = outreach contact made. LEAKAGE RISK: use only with date guard. |
| renewal_month_label | VARCHAR(6) | NOT NULL | YYYYMM of renewal decision month |

**Leakage warning:** `renewal_premium_change_pct` is known only after the renewal offer is
generated. `outreach_contact_flag` is legitimate only if the contact date is confirmed to
precede `renewal_decision_date`.

---

## fact_billing_summary

**Grain:** One row per policy (billing behavior summary over term)
**Approx rows:** 90,000
**Primary key:** policy_id (1-to-1 with fact_policies)
**Foreign keys:** policy_id -> fact_policies
**Joins to:** fact_policies on policy_id

| Column | Type | Nullable | Description |
|---|---|---|---|
| policy_id | VARCHAR(36) | NOT NULL | PK and FK to fact_policies |
| payment_method | VARCHAR(20) | NOT NULL | Credit Card, Bank Draft, Check, Digital Wallet |
| billing_frequency | VARCHAR(12) | NOT NULL | Monthly, Semi-Annual, Annual |
| missed_payment_count_12mo | INTEGER | NOT NULL | Missed payments in first 12 months |
| days_past_due_max | INTEGER | NOT NULL | Longest days past due in first 12 months |
| payment_consistency_score | FLOAT | NOT NULL | Payment regularity score 0-100 (100 = no missed payments) |
| nsf_flag | INTEGER | NOT NULL | 1 = had at least one returned/NSF payment |
| late_pay_flag_last_3mo | INTEGER | NOT NULL | 1 = late payment in most recent 3 months of term |

**Allowed values:**
- payment_method: `Credit Card`, `Bank Draft`, `Check`, `Digital Wallet`
- billing_frequency: `Monthly`, `Semi-Annual`, `Annual`

---

## fact_claims

**Grain:** One row per claim filed
**Approx rows:** ~19,000
**Primary key:** claim_id
**Foreign keys:** policy_id -> fact_policies, customer_id -> dim_customer
**Joins to:** fact_policies on policy_id

| Column | Type | Nullable | Description |
|---|---|---|---|
| claim_id | VARCHAR(36) | NOT NULL | Claim identifier (UUID) |
| policy_id | VARCHAR(36) | NOT NULL | FK to fact_policies |
| customer_id | VARCHAR(36) | NOT NULL | FK to dim_customer (denormalized) |
| claim_date | DATE | NOT NULL | Date the claim was filed |
| claim_type | VARCHAR(25) | NOT NULL | Collision, Comprehensive, Liability, Uninsured Motorist, Medical |
| claim_amount | FLOAT | NOT NULL | Total claim payout amount (USD) |
| claim_severity_band | VARCHAR(10) | NOT NULL | None, Minor, Moderate, Major |
| at_fault_flag | INTEGER | NOT NULL | 1 = policyholder was at fault |
| claim_status | VARCHAR(10) | NOT NULL | Open, Closed, Pending |
| days_to_close | INTEGER | NULLABLE | Days from filed to closed; NULL if Open or Pending |

**Allowed values:**
- claim_type: `Collision`, `Comprehensive`, `Liability`, `Uninsured Motorist`, `Medical`
- claim_severity_band: `None`, `Minor`, `Moderate`, `Major`
- claim_status: `Open`, `Closed`, `Pending`

**Note on sparsity:** ~21% of policies have at least one claim row. Denormalization aggregates
claims to the policy grain using `has_claim_12mo`, `claim_count_12mo`, `total_claim_amount`,
`claim_severity_band` (worst claim), and `days_since_last_claim`.
