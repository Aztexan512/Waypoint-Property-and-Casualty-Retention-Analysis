# Waypoint Property & Casualty -- Entity Relationship Diagram

**Project:** waypoint-retention-analytics
**Author:** Luciano Casillas
**Date:** 2026-05-02
**Schema:** WAYPOINT_ANALYTICS

---

## Relationships

| Parent Table | Child Table | Join Key | Cardinality |
|---|---|---|---|
| dim_customer | fact_policies | customer_id | 1 to many |
| fact_policies | fact_renewals | policy_id | 1 to 0-or-1 |
| fact_policies | fact_billing_summary | policy_id | 1 to 1 |
| fact_policies | fact_claims | policy_id | 1 to many |

---

## Mermaid Diagram

```mermaid
erDiagram

    dim_customer {
        VARCHAR customer_id PK
        VARCHAR age_band
        VARCHAR state
        VARCHAR metro_area
        INTEGER homeowner_flag
        INTEGER prior_insurance_flag
        FLOAT   years_with_carrier
        VARCHAR acquisition_channel
        VARCHAR agency_type
        INTEGER aqx_assisted_flag
    }

    fact_policies {
        VARCHAR policy_id PK
        VARCHAR customer_id FK
        VARCHAR policy_type
        VARCHAR coverage_tier
        FLOAT   annual_premium
        DATE    effective_date
        VARCHAR cohort_quarter
        INTEGER tenure_months
        INTEGER multi_product_flag
        INTEGER renters_quoted_flag
        INTEGER renters_attached_flag
        INTEGER renewed
    }

    fact_renewals {
        VARCHAR renewal_id PK
        VARCHAR policy_id FK
        VARCHAR customer_id FK
        DATE    renewal_decision_date
        INTEGER renewed
        INTEGER days_to_decision
        FLOAT   renewal_premium_change_pct
        INTEGER outreach_contact_flag
        VARCHAR renewal_month_label
    }

    fact_billing_summary {
        VARCHAR policy_id PK
        VARCHAR payment_method
        VARCHAR billing_frequency
        INTEGER missed_payment_count_12mo
        INTEGER days_past_due_max
        FLOAT   payment_consistency_score
        INTEGER nsf_flag
        INTEGER late_pay_flag_last_3mo
    }

    fact_claims {
        VARCHAR claim_id PK
        VARCHAR policy_id FK
        VARCHAR customer_id FK
        DATE    claim_date
        VARCHAR claim_type
        FLOAT   claim_amount
        VARCHAR claim_severity_band
        INTEGER at_fault_flag
        VARCHAR claim_status
        INTEGER days_to_close
    }

    dim_customer       ||--o{ fact_policies        : "customer_id"
    fact_policies      ||--o| fact_renewals         : "policy_id"
    fact_policies      ||--|| fact_billing_summary  : "policy_id"
    fact_policies      ||--o{ fact_claims           : "policy_id"
```

---

## Notes

- **fact_billing_summary** is a strict 1-to-1 extension of fact_policies. Every policy has exactly one billing summary row.
- **fact_renewals** only covers policies with a known renewal outcome (~72,000 rows). Policies effective after 2024-12-31 do not have a renewal row.
- **fact_claims** is sparse. Only ~21% of policies have at least one claim row.
- **customer_id** is denormalized onto fact_renewals and fact_claims for query convenience. The authoritative source is dim_customer.
- Snowflake does not enforce FOREIGN KEY constraints at runtime, but all FKs are declared for documentation and lineage purposes.
