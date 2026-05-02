#!/usr/bin/env python3
"""
Phase 2 data generator for Waypoint Property & Casualty retention analytics.

Generates all five source tables and the denormalized analysis-ready CSV:
  - dim_customer.csv          (~72,000 rows)
  - fact_policies.csv         (90,000 rows)
  - fact_billing_summary.csv  (90,000 rows)
  - fact_claims.csv           (~19,000 rows)
  - fact_renewals.csv         (~72,000 rows)
  - waypoint_retention.csv    (90,000 rows, denormalized)
  - waypoint_retention_metadata.json

Usage (from project root):
    python _build/workflows/02_data_generation/generators/01_generate_data.py

Outputs:
    _build/tools/raw_tables/                      source table CSVs (gitignored)
    _build/workflows/02_data_generation/outputs/  all CSVs + metadata JSON
"""

from __future__ import annotations

import json
import sys
import uuid
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

warnings.filterwarnings("ignore")


# --------------------------------------------------------------------------- #
# Paths                                                                        #
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = (
    PROJECT_ROOT
    / "_build" / "workflows" / "02_data_generation" / "config"
    / "generation_config.yaml"
)
RAW_DIR  = PROJECT_ROOT / "_build" / "tools" / "raw_tables"
OUT_DIR  = PROJECT_ROOT / "_build" / "workflows" / "02_data_generation" / "outputs"


# --------------------------------------------------------------------------- #
# Metro area lookup (one list per state)                                       #
# --------------------------------------------------------------------------- #

METRO_AREAS: dict[str, list[str]] = {
    "TX": ["Austin", "Dallas", "Houston", "San Antonio", "Rural TX"],
    "FL": ["Jacksonville", "Miami", "Orlando", "Tampa", "Rural FL"],
    "OH": ["Cincinnati", "Cleveland", "Columbus", "Rural OH"],
    "GA": ["Atlanta", "Savannah", "Rural GA"],
    "NC": ["Charlotte", "Raleigh", "Rural NC"],
    "VA": ["Northern Virginia", "Richmond", "Virginia Beach", "Rural VA"],
    "TN": ["Memphis", "Nashville", "Rural TN"],
    "IN": ["Indianapolis", "Rural IN"],
    "KY": ["Louisville", "Rural KY"],
    "MO": ["Kansas City", "St. Louis", "Rural MO"],
    "SC": ["Charleston", "Columbia", "Rural SC"],
    "AL": ["Birmingham", "Huntsville", "Rural AL"],
    "AZ": ["Phoenix", "Tucson", "Rural AZ"],
    "CO": ["Denver", "Colorado Springs", "Rural CO"],
}

# Agency type derived from acquisition channel
CHANNEL_TO_AGENCY: dict[str, str] = {
    "Agency Portal": "Independent",  # overridden to Captive for 40% of Agency Portal
    "AQX":           "Digital Partner",
    "Direct Web":    "Direct",
    "Phone":         "Direct",
    "Referral":      "Direct",
}

# Per-channel base renewal rates (calibrated to hit overall 74.8%)
CHANNEL_BASE_RENEWAL: dict[str, float] = {
    "Agency Portal": 0.754,
    "AQX":           0.830,
    "Direct Web":    0.680,
    "Phone":         0.720,
    "Referral":      0.770,
}

# Coverage tier premium adjustment on renewal probability
TIER_RENEWAL_ADJ: dict[str, float] = {
    "Liability Only": -0.035,
    "Standard":       -0.010,
    "Premium":         0.010,
    "Elite":           0.025,
}


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def load_config(path: Path) -> dict:
    """Load and return the YAML generation config."""
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def new_ids(n: int) -> list[str]:
    """Return a list of n UUID4 strings."""
    return [str(uuid.uuid4()) for _ in range(n)]


def weighted_sample(
    rng: np.random.Generator,
    values: list,
    weights: list,
    n: int,
) -> np.ndarray:
    """Draw n samples with replacement from values using normalized weights."""
    probs = np.array(weights, dtype=float)
    probs /= probs.sum()
    return rng.choice(values, size=n, p=probs)


def to_quarter(dates: pd.Series) -> pd.Series:
    """Convert a date Series to YYYYQN cohort label strings (e.g., 2023Q1)."""
    return dates.dt.to_period("Q").astype(str)


def calibrate(arr: np.ndarray, target_mean: float) -> np.ndarray:
    """Scale an array so its mean equals target_mean."""
    current = arr.mean()
    if current == 0:
        return arr
    return arr * (target_mean / current)


# --------------------------------------------------------------------------- #
# Step 1: dim_customer                                                         #
# --------------------------------------------------------------------------- #

def generate_dim_customer(cfg: dict, rng: np.random.Generator) -> pd.DataFrame:
    """
    Generate the customer dimension table.

    Returns one row per policyholder account. Homeowner and prior-insurance
    rates are age-stratified to produce realistic correlations.
    """
    n    = cfg["dataset"]["customer_count"]
    dist = cfg["distributions"]

    customer_ids = new_ids(n)

    age_bands   = list(dist["age_band"].keys())
    age_weights = list(dist["age_band"].values())
    age_band    = weighted_sample(rng, age_bands, age_weights, n)

    states        = list(dist["states"].keys())
    state_weights = list(dist["states"].values())
    state         = weighted_sample(rng, states, state_weights, n)

    metro_area = np.array([rng.choice(METRO_AREAS[s]) for s in state])

    # Homeowner rate increases with age band
    age_homeowner_rate = {
        "18-25": 0.10, "26-35": 0.28, "36-45": 0.46,
        "46-55": 0.57, "56-65": 0.64, "65+":   0.70,
    }
    homeowner_prob  = np.array([age_homeowner_rate[a] for a in age_band])
    homeowner_flag  = rng.binomial(1, homeowner_prob).astype(int)

    # Prior insurance rate: lower for youngest band
    age_prior_rate = {
        "18-25": 0.66, "26-35": 0.82, "36-45": 0.89,
        "46-55": 0.92, "56-65": 0.94, "65+":   0.95,
    }
    prior_prob           = np.array([age_prior_rate[a] for a in age_band])
    prior_insurance_flag = rng.binomial(1, prior_prob).astype(int)

    # DESIGN DECISION: years_with_carrier uses exponential(mean=2) to model
    # the realistic pattern of mostly new customers with a long tail of loyal ones.
    years_with_carrier = np.clip(rng.exponential(scale=2.0, size=n), 0.0, 12.0).round(1)

    channels        = list(dist["acquisition_channel"].keys())
    ch_weights      = list(dist["acquisition_channel"].values())
    acq_channel     = weighted_sample(rng, channels, ch_weights, n)

    # Agency type: Agency Portal splits 60% Independent / 40% Captive
    agency_type = np.where(
        acq_channel == "Agency Portal",
        np.where(rng.random(n) < 0.60, "Independent", "Captive"),
        np.vectorize(CHANNEL_TO_AGENCY.get)(acq_channel),
    )

    aqx_assisted_flag = (acq_channel == "AQX").astype(int)

    return pd.DataFrame({
        "customer_id":          customer_ids,
        "age_band":             age_band,
        "state":                state,
        "metro_area":           metro_area,
        "homeowner_flag":       homeowner_flag,
        "prior_insurance_flag": prior_insurance_flag,
        "years_with_carrier":   years_with_carrier,
        "acquisition_channel":  acq_channel,
        "agency_type":          agency_type,
        "aqx_assisted_flag":    aqx_assisted_flag,
    })


# --------------------------------------------------------------------------- #
# Step 2: fact_policies                                                        #
# --------------------------------------------------------------------------- #

def generate_fact_policies(
    cfg: dict,
    rng: np.random.Generator,
    customers: pd.DataFrame,
) -> pd.DataFrame:
    """
    Generate the primary policy fact table.

    Customer IDs are assigned so each of the 72,000 customers has at least
    one policy, and 18,000 randomly selected customers get a second policy.
    The renewed column is initialized to -1 (sentinel) and updated after
    billing and claims are computed.
    """
    n          = cfg["dataset"]["row_count"]
    n_cust     = cfg["dataset"]["customer_count"]
    dist       = cfg["distributions"]
    prem_cfg   = cfg["premiums"]
    aqx_launch = pd.Timestamp(cfg["dataset"]["aqx_launch_date"])
    t_start    = pd.Timestamp(cfg["dataset"]["time_window_start"])
    t_end      = pd.Timestamp(cfg["dataset"]["time_window_end"])

    # Assign customer IDs: every customer gets one guaranteed policy;
    # remaining (n - n_cust) are drawn randomly to simulate multi-policy customers.
    # DESIGN DECISION: using shuffle rather than sort so multi-policy clusters are
    # not contiguous in the output, which would bias cohort-level aggregations.
    base_ids  = customers["customer_id"].values.copy()
    extra_ids = rng.choice(base_ids, size=n - n_cust, replace=True)
    cids      = np.concatenate([base_ids, extra_ids])
    rng.shuffle(cids)

    policy_ids = new_ids(n)

    # Effective dates: uniform over the 36-month window
    span_days     = (t_end - t_start).days
    offsets       = rng.integers(0, span_days + 1, size=n)
    eff_dates_ts  = pd.to_datetime([t_start + pd.Timedelta(days=int(d)) for d in offsets])
    cohort_quarter = to_quarter(pd.Series(eff_dates_ts))

    # Coverage tier
    tiers       = list(dist["coverage_tier"].keys())
    tier_wts    = list(dist["coverage_tier"].values())
    cov_tier    = weighted_sample(rng, tiers, tier_wts, n)

    # Annual premium: normal by tier, scaled by state, calibrated to target mean
    cust_state_map  = customers.set_index("customer_id")["state"].to_dict()
    pol_states      = np.array([cust_state_map.get(c, "TX") for c in cids])
    state_mult_map  = prem_cfg["state_multipliers"]
    state_mults     = np.array([state_mult_map.get(s, 1.0) for s in pol_states])

    base_prem = np.array([
        rng.normal(prem_cfg["tier_means"][t], prem_cfg["tier_std"][t]) for t in cov_tier
    ])
    annual_premium = np.clip(base_prem * state_mults, prem_cfg["min_premium"], prem_cfg["max_premium"])
    annual_premium = np.clip(
        calibrate(annual_premium, cfg["rates"]["avg_annual_premium"]),
        prem_cfg["min_premium"],
        prem_cfg["max_premium"],
    ).round(2)

    # Multi-product and renters flags
    multi_p              = cfg["rates"]["multi_product_attach_rate"]
    renters_attached     = rng.binomial(1, multi_p, size=n)
    multi_product_flag   = renters_attached.copy()
    policy_type          = np.where(renters_attached == 1, "Auto + Renters", "Auto Only")
    # Renters quoted: all who attached plus ~40% of auto-only
    renters_quoted_flag  = np.maximum(renters_attached, rng.binomial(1, 0.40, size=n))

    # Tenure months from customer's years_with_carrier, with small jitter
    cust_tenure_map = customers.set_index("customer_id")["years_with_carrier"].to_dict()
    years_vc        = np.array([cust_tenure_map.get(c, 0.0) for c in cids])
    tenure_months   = np.clip(
        (years_vc * 12 + rng.integers(-3, 4, size=n)).astype(int), 0, 120
    )

    # AQX assisted: inherit from customer, but zero out for policies before AQX launch
    cust_aqx_map      = customers.set_index("customer_id")["aqx_assisted_flag"].to_dict()
    aqx_assisted_flag = np.array([cust_aqx_map.get(c, 0) for c in cids])
    aqx_assisted_flag[eff_dates_ts < aqx_launch] = 0

    return pd.DataFrame({
        "policy_id":             policy_ids,
        "customer_id":           cids,
        "policy_type":           policy_type,
        "coverage_tier":         cov_tier,
        "annual_premium":        annual_premium,
        "effective_date":        eff_dates_ts.strftime("%Y-%m-%d"),
        "cohort_quarter":        cohort_quarter.values,
        "tenure_months":         tenure_months,
        "multi_product_flag":    multi_product_flag,
        "renters_quoted_flag":   renters_quoted_flag,
        "renters_attached_flag": renters_attached,
        "renewed":               -1,
        "aqx_assisted_flag":     aqx_assisted_flag,  # temp col; dropped before saving
    })


# --------------------------------------------------------------------------- #
# Step 3: fact_billing_summary                                                 #
# --------------------------------------------------------------------------- #

def generate_fact_billing_summary(
    cfg: dict,
    rng: np.random.Generator,
    policies: pd.DataFrame,
) -> pd.DataFrame:
    """
    Generate billing behavior summary for each policy.

    Missed payment count follows a Poisson distribution with lambda varying
    by payment method. NSF and late pay flags are correlated with missed
    payment count to ensure internal consistency.
    """
    n        = len(policies)
    dist     = cfg["distributions"]
    bill_cfg = cfg["billing"]

    pay_methods   = list(dist["payment_method"].keys())
    pay_wts       = list(dist["payment_method"].values())
    payment_method = weighted_sample(rng, pay_methods, pay_wts, n)

    freq_vals  = list(dist["billing_frequency"].keys())
    freq_wts   = list(dist["billing_frequency"].values())
    billing_frequency = weighted_sample(rng, freq_vals, freq_wts, n)

    # Missed payment count: Poisson, lambda by payment method
    miss_lambda   = np.array([bill_cfg["missed_payment_lambda_by_method"][m] for m in payment_method])
    missed_count  = rng.poisson(miss_lambda).astype(int)

    # NSF flag: correlated with missed payments
    nsf_base = np.array([bill_cfg["nsf_rate_by_method"][m] for m in payment_method])
    nsf_prob  = np.where(missed_count >= 2, np.minimum(nsf_base * 3.5, 0.60),
                np.where(missed_count == 1, nsf_base * 2.0, nsf_base))
    nsf_flag  = rng.binomial(1, nsf_prob).astype(int)

    # Late pay in last 3 months: correlated with missed payments
    late_base  = np.array([bill_cfg["late_pay_rate_by_method"][m] for m in payment_method])
    late_prob  = np.where(missed_count >= 1, np.minimum(late_base * 2.5, 0.55), late_base)
    late_pay   = rng.binomial(1, late_prob).astype(int)

    # Days past due max: 0 if no missed payments, else drawn from gamma
    days_pd_base = np.where(missed_count == 0, 0, rng.integers(1, 15, size=n))
    days_pd_extra = np.where(
        missed_count >= 2,
        rng.integers(10, 60, size=n),
        np.where(missed_count == 1, rng.integers(0, 30, size=n), 0),
    )
    days_past_due_max = (days_pd_base + days_pd_extra).astype(int)

    # Payment consistency score: 100 minus penalties
    consistency = (
        100.0
        - missed_count * 9.5
        - nsf_flag * 13.0
        - late_pay * 5.0
        - (days_past_due_max / 10.0)
    )
    consistency = np.clip(consistency, 0.0, 100.0).round(1)

    return pd.DataFrame({
        "policy_id":                  policies["policy_id"].values,
        "payment_method":             payment_method,
        "billing_frequency":          billing_frequency,
        "missed_payment_count_12mo":  missed_count,
        "days_past_due_max":          days_past_due_max,
        "payment_consistency_score":  consistency,
        "nsf_flag":                   nsf_flag,
        "late_pay_flag_last_3mo":     late_pay,
    })


# --------------------------------------------------------------------------- #
# Step 4: fact_claims                                                          #
# --------------------------------------------------------------------------- #

def generate_fact_claims(
    cfg: dict,
    rng: np.random.Generator,
    policies: pd.DataFrame,
    customers: pd.DataFrame,
) -> pd.DataFrame:
    """
    Generate the sparse claims fact table.

    Claim probability varies by coverage tier. A small proportion of
    claimant policies receive a second claim. Claim dates fall within the
    first 12 months of the policy effective date.
    """
    clm_cfg = cfg["claims"]
    n       = len(policies)

    # Per-policy claim probability by coverage tier
    tier_rate_map = clm_cfg["rate_by_tier"]
    claim_prob    = np.array([tier_rate_map[t] for t in policies["coverage_tier"]])
    has_claim     = rng.binomial(1, claim_prob).astype(bool)

    # Small proportion of claimants get a second claim
    second_claim  = rng.binomial(1, clm_cfg["multi_claim_rate"], size=n).astype(bool)
    second_claim  = second_claim & has_claim

    # Build index arrays for claim rows
    claim_policy_idx = np.concatenate([
        np.where(has_claim)[0],
        np.where(second_claim)[0],
    ])
    claim_policy_idx.sort()

    n_claims    = len(claim_policy_idx)
    claim_pols  = policies.iloc[claim_policy_idx].reset_index(drop=True)

    claim_custs = claim_pols["customer_id"].values

    # Claim dates: uniform in [effective_date, effective_date + 365 days]
    eff_ts      = pd.to_datetime(claim_pols["effective_date"])
    day_offsets = rng.integers(0, 365, size=n_claims)
    claim_dates = (eff_ts + pd.to_timedelta(day_offsets, unit="D")).dt.strftime("%Y-%m-%d")

    # Severity
    sev_vals = list(clm_cfg["severity_distribution"].keys())
    sev_wts  = list(clm_cfg["severity_distribution"].values())
    severity = weighted_sample(rng, sev_vals, sev_wts, n_claims)

    # Claim amount: log-normal centered on severity mean
    amounts = np.array([
        max(
            rng.normal(clm_cfg["amount_by_severity"][s]["mean"],
                       clm_cfg["amount_by_severity"][s]["std"]),
            100.0,
        )
        for s in severity
    ]).round(2)

    # Claim type
    type_keys = list(clm_cfg["types"].keys())
    type_wts  = list(clm_cfg["types"].values())
    claim_type = weighted_sample(rng, type_keys, type_wts, n_claims)

    at_fault_flag = rng.binomial(1, clm_cfg["at_fault_rate"], size=n_claims).astype(int)

    # Status: mostly Closed, some Open/Pending
    status_vals = ["Closed", "Open", "Pending"]
    status_wts  = [1.0 - clm_cfg["open_rate"] - clm_cfg["pending_rate"],
                   clm_cfg["open_rate"], clm_cfg["pending_rate"]]
    claim_status = weighted_sample(rng, status_vals, status_wts, n_claims)

    # Days to close: only for Closed claims
    close_mean_map = {s: clm_cfg["days_to_close"][s]["mean"] for s in sev_vals}
    close_std_map  = {s: clm_cfg["days_to_close"][s]["std"]  for s in sev_vals}
    days_to_close  = np.array([
        int(max(rng.normal(close_mean_map[s], close_std_map[s]), 1))
        if st == "Closed" else -1
        for s, st in zip(severity, claim_status)
    ])

    return pd.DataFrame({
        "claim_id":           new_ids(n_claims),
        "policy_id":          claim_pols["policy_id"].values,
        "customer_id":        claim_custs,
        "claim_date":         claim_dates.values,
        "claim_type":         claim_type,
        "claim_amount":       amounts,
        "claim_severity_band": severity,
        "at_fault_flag":      at_fault_flag,
        "claim_status":       claim_status,
        "days_to_close":      days_to_close,
    })


# --------------------------------------------------------------------------- #
# Step 5: assign renewed                                                       #
# --------------------------------------------------------------------------- #

def assign_renewals(
    cfg: dict,
    rng: np.random.Generator,
    policies: pd.DataFrame,
    billing: pd.DataFrame,
    claims: pd.DataFrame,
    customers: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute renewal probability for each policy and assign the renewed column.

    Uses channel base rates with additive adjustments from billing behavior,
    claims history, and customer demographics. Per-channel calibration is
    applied to hit the AQX (83%) and Direct Web (68%) targets. A final
    global calibration step ensures the overall rate lands at 74.8%.

    Returns policies DataFrame with renewed column updated.
    -1 sentinel retained for policies with effective_date > renewal_cutoff_date.
    """
    rates      = cfg["rates"]
    cutoff     = pd.Timestamp(cfg["dataset"]["renewal_cutoff_date"])

    # Merge billing and claims into policies for feature access
    bil = billing.set_index("policy_id")
    pol = policies.set_index("policy_id")
    cust = customers.set_index("customer_id")

    # Claims aggregated to policy level
    if len(claims) > 0:
        clm_agg = claims.groupby("policy_id").agg(
            has_claim=("claim_id", "count"),
            at_fault_sum=("at_fault_flag", "sum"),
            max_severity=("claim_severity_band", lambda x: x.map(
                {"None": 0, "Minor": 1, "Moderate": 2, "Major": 3}).max()),
        )
        clm_agg["has_claim"]   = (clm_agg["has_claim"] > 0).astype(int)
        clm_agg["at_fault_any"] = (clm_agg["at_fault_sum"] > 0).astype(int)
    else:
        clm_agg = pd.DataFrame(
            columns=["has_claim", "at_fault_sum", "max_severity", "at_fault_any"]
        )

    n  = len(policies)
    idx = policies["policy_id"].values

    # Base probability from acquisition channel (via customer lookup)
    cust_channel_map = customers.set_index("customer_id")["acquisition_channel"].to_dict()
    pol_channel      = np.array([cust_channel_map.get(c, "Direct Web") for c in policies["customer_id"].values])
    base_prob        = np.array([CHANNEL_BASE_RENEWAL.get(ch, 0.748) for ch in pol_channel])

    # Billing adjustments
    miss = bil.reindex(idx)["missed_payment_count_12mo"].fillna(0).values
    nsf  = bil.reindex(idx)["nsf_flag"].fillna(0).values
    late = bil.reindex(idx)["late_pay_flag_last_3mo"].fillna(0).values

    # Claims adjustments
    at_fault = clm_agg.reindex(idx)["at_fault_any"].fillna(0).values
    max_sev  = clm_agg.reindex(idx)["max_severity"].fillna(0).values

    # Customer adjustments
    homeowner  = cust.reindex(policies["customer_id"].values)["homeowner_flag"].fillna(0).values
    prior_ins  = cust.reindex(policies["customer_id"].values)["prior_insurance_flag"].fillna(0).values
    years_vc   = cust.reindex(policies["customer_id"].values)["years_with_carrier"].fillna(0).values
    aqx_asst   = policies["aqx_assisted_flag"].values

    # Additive adjustments
    adj = (
          0.050 * policies["multi_product_flag"].values
        + np.vectorize(TIER_RENEWAL_ADJ.get)(policies["coverage_tier"].values, 0.0)
        - 0.100 * (miss == 1).astype(float)
        - 0.180 * (miss >= 2).astype(float)
        - 0.120 * nsf
        - 0.070 * late
        - 0.055 * at_fault
        - 0.045 * (max_sev == 3).astype(float)   # Major severity
        + 0.015 * homeowner
        + 0.020 * prior_ins
        + 0.030 * (years_vc >= 3).astype(float)
        + 0.020 * aqx_asst
    )

    prob = np.clip(base_prob + adj, 0.02, 0.99)

    # Per-channel calibration to hit AQX and Direct Web targets
    for channel, target in [
        ("AQX",        rates["aqx_renewal_rate"]),
        ("Direct Web", rates["direct_web_renewal_rate"]),
    ]:
        mask = pol_channel == channel
        if mask.sum() > 0:
            current = prob[mask].mean()
            if current > 0:
                prob[mask] = np.clip(prob[mask] * (target / current), 0.02, 0.99)

    # Global calibration to hit overall renewal rate (only on known-renewal policies)
    eff_dates  = pd.to_datetime(policies["effective_date"])
    known_mask = eff_dates <= cutoff
    if known_mask.sum() > 0:
        current_overall = prob[known_mask].mean()
        if current_overall > 0:
            scale = rates["overall_renewal_rate"] / current_overall
            prob[known_mask] = np.clip(prob[known_mask] * scale, 0.02, 0.99)

    # Sample binary renewed outcome
    renewed = rng.binomial(1, prob).astype(int)
    # Mark policies outside the renewal window as -1 (sentinel for unknown)
    renewed[~known_mask] = -1

    policies = policies.copy()
    policies["renewed"] = renewed
    return policies


# --------------------------------------------------------------------------- #
# Step 6: fact_renewals                                                        #
# --------------------------------------------------------------------------- #

def generate_fact_renewals(
    cfg: dict,
    rng: np.random.Generator,
    policies: pd.DataFrame,
) -> pd.DataFrame:
    """
    Generate the renewal event fact table.

    Only policies effective on or before renewal_cutoff_date receive a
    renewal record. Premium change is higher for lapsed policies to reflect
    the real-world pattern of price-sensitive non-renewal.
    """
    ren_cfg = cfg["renewal"]
    cutoff  = pd.Timestamp(cfg["dataset"]["renewal_cutoff_date"])

    eligible = policies[policies["renewed"].isin([0, 1])].copy()
    n        = len(eligible)
    eff_ts   = pd.to_datetime(eligible["effective_date"])

    # Renewal decision date: effective_date + 365 days + jitter (-15 to +15 days)
    jitter          = rng.integers(-15, 16, size=n)
    decision_dates  = (eff_ts + pd.Timedelta(days=365) + pd.to_timedelta(jitter, unit="D"))
    decision_dates  = decision_dates.dt.strftime("%Y-%m-%d")

    renewed = eligible["renewed"].values

    # Days to decision: faster for lapsing policyholders
    mean_days = np.where(
        renewed == 1,
        ren_cfg["days_to_decision_mean_renewed"],
        ren_cfg["days_to_decision_mean_lapsed"],
    )
    days_to_decision = np.clip(
        rng.normal(mean_days, ren_cfg["days_to_decision_std"], size=n).astype(int), 0, 90
    )

    # Premium change: higher for lapsed (price sensitivity drove non-renewal)
    pct_mean = np.where(
        renewed == 1,
        ren_cfg["premium_change_mean_renewed"],
        ren_cfg["premium_change_mean_lapsed"],
    )
    renewal_premium_change_pct = np.round(
        rng.normal(pct_mean, ren_cfg["premium_change_std"], size=n), 4
    )

    # Outreach contact flag: higher rate for high-risk policyholders
    # DESIGN DECISION: high-risk defined as missed_payment_count >= 1 OR nsf_flag = 1
    # This proxy is used only for generating outreach contact probability.
    # The actual lapse score is computed in Phase 4.
    high_risk_proxy = (
        ((eligible["renewed"].values == 0) & (rng.random(n) < 0.35))
        | (rng.random(n) < ren_cfg["outreach_contact_rate_base"])
    )
    outreach_base = np.where(
        high_risk_proxy,
        ren_cfg["outreach_contact_rate_high_risk"],
        ren_cfg["outreach_contact_rate_base"],
    )
    outreach_contact_flag = rng.binomial(1, outreach_base).astype(int)

    renewal_month_label = pd.to_datetime(decision_dates).dt.strftime("%Y%m")

    return pd.DataFrame({
        "renewal_id":                 new_ids(n),
        "policy_id":                  eligible["policy_id"].values,
        "customer_id":                eligible["customer_id"].values,
        "renewal_decision_date":      decision_dates.values,
        "renewed":                    renewed,
        "days_to_decision":           days_to_decision,
        "renewal_premium_change_pct": renewal_premium_change_pct,
        "outreach_contact_flag":      outreach_contact_flag,
        "renewal_month_label":        renewal_month_label.values,
    })


# --------------------------------------------------------------------------- #
# Step 7: build denormalized CSV                                               #
# --------------------------------------------------------------------------- #

def build_denormalized(
    cfg: dict,
    rng: np.random.Generator,
    customers: pd.DataFrame,
    policies: pd.DataFrame,
    billing: pd.DataFrame,
    claims: pd.DataFrame,
    renewals: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join all five source tables into the denormalized policy-grain CSV.

    Claims are aggregated to policy level before joining.
    Sentinel values used for missing data to ensure zero nulls:
      -1 for days_since_last_claim (no claims filed)
      -1 for renewed (renewal window not yet reached)
      0  for claim count/amount columns when no claims exist
    """
    rates = cfg["rates"]

    # Aggregate claims to policy level
    if len(claims) > 0:
        sev_rank = {"None": 0, "Minor": 1, "Moderate": 2, "Major": 3}
        rank_sev = {0: "None", 1: "Minor", 2: "Moderate", 3: "Major"}

        clm = claims.copy()
        clm["eff_dt"] = policies.set_index("policy_id").reindex(
            clm["policy_id"])["effective_date"].values
        clm["eff_ts"]   = pd.to_datetime(clm["eff_dt"])
        clm["claim_ts"] = pd.to_datetime(clm["claim_date"])
        clm["days_since"] = (clm["eff_ts"] - clm["claim_ts"]).dt.days.abs()

        sev_num = clm["claim_severity_band"].map(sev_rank).fillna(0).astype(int)
        clm["sev_num"] = sev_num

        clm_agg = clm.groupby("policy_id").agg(
            claim_count_12mo=("claim_id", "count"),
            total_claim_amount=("claim_amount", "sum"),
            sev_max=("sev_num", "max"),
            days_since_last_claim=("days_since", "min"),
        ).reset_index()
        clm_agg["has_claim_12mo"]      = 1
        clm_agg["total_claim_amount"]  = clm_agg["total_claim_amount"].round(2)
        clm_agg["claim_severity_band"] = clm_agg["sev_max"].map(rank_sev)
        clm_agg = clm_agg.drop(columns=["sev_max"])
    else:
        clm_agg = pd.DataFrame(columns=[
            "policy_id", "claim_count_12mo", "total_claim_amount",
            "has_claim_12mo", "claim_severity_band", "days_since_last_claim",
        ])

    # Renewal metadata (only for eligible policies)
    ren_meta = renewals[["policy_id", "renewal_month_label", "days_to_decision",
                          "renewal_premium_change_pct", "outreach_contact_flag"]].copy()

    # Build base: policies + customers
    df = policies.drop(columns=["aqx_assisted_flag"]).merge(
        customers, on="customer_id", how="left"
    )

    # Merge billing
    billing_renamed = billing.rename(columns={
        "missed_payment_count_12mo": "missed_payment_count",
        "payment_consistency_score": "payment_consistency",
        "late_pay_flag_last_3mo":    "late_pay_flag_3mo",
    })
    df = df.merge(billing_renamed, on="policy_id", how="left")

    # Merge claims aggregate (fill zeros/sentinels for no-claim policies)
    df = df.merge(clm_agg, on="policy_id", how="left")
    df["has_claim_12mo"]        = df["has_claim_12mo"].fillna(0).astype(int)
    df["claim_count_12mo"]      = df["claim_count_12mo"].fillna(0).astype(int)
    df["total_claim_amount"]    = df["total_claim_amount"].fillna(0.0).round(2)
    df["claim_severity_band"]   = df["claim_severity_band"].fillna("None")
    df["days_since_last_claim"] = df["days_since_last_claim"].fillna(-1).astype(int)

    # Merge renewal metadata
    df = df.merge(ren_meta, on="policy_id", how="left")
    df["renewal_month_label"]        = df["renewal_month_label"].fillna("Unknown")
    df["days_to_decision"]           = df["days_to_decision"].fillna(-1).astype(int)
    df["renewal_premium_change_pct"] = df["renewal_premium_change_pct"].fillna(0.0)
    df["outreach_contact_flag"]      = df["outreach_contact_flag"].fillna(0).astype(int)

    # Compute CLTV
    cltv_cfg   = cfg["cltv"]
    ren_col    = df["renewed"].values.astype(float)
    base_mult  = np.where(ren_col == 1, cltv_cfg["multiplier_renewed"],
                 np.where(ren_col == 0, cltv_cfg["multiplier_lapsed"],
                          cltv_cfg["multiplier_unknown"]))
    cltv_raw   = df["annual_premium"].values * base_mult + rng.normal(0, cltv_cfg["noise_std"], size=len(df))
    cltv_raw   = np.clip(cltv_raw, 200.0, 8000.0)
    cltv_36mo  = np.clip(
        calibrate(cltv_raw, rates["avg_cltv_36mo"]), 200.0, 8000.0
    ).round(2)
    df["cltv_36mo"] = cltv_36mo

    # Add post_renewal columns (leakage; included for completeness)
    tier_order   = ["Liability Only", "Standard", "Premium", "Elite"]
    tier_idx_map = {t: i for i, t in enumerate(tier_order)}
    post_tier    = []
    for tier, ren in zip(df["coverage_tier"], df["renewed"]):
        idx = tier_idx_map.get(tier, 1)
        if ren == 1 and rng.random() < 0.12 and idx < 3:
            post_tier.append(tier_order[idx + 1])
        else:
            post_tier.append(tier)
    df["post_renewal_coverage_tier"] = post_tier

    # Final column order (matches data_dictionary.md)
    col_order = [
        "customer_id", "age_band", "state", "metro_area", "homeowner_flag",
        "prior_insurance_flag", "years_with_carrier", "acquisition_channel",
        "agency_type", "aqx_assisted_flag",
        "policy_id", "policy_type", "coverage_tier", "annual_premium",
        "effective_date", "cohort_quarter", "tenure_months",
        "multi_product_flag", "renters_quoted_flag", "renters_attached_flag",
        "payment_method", "billing_frequency", "missed_payment_count",
        "days_past_due_max", "payment_consistency", "nsf_flag", "late_pay_flag_3mo",
        "has_claim_12mo", "claim_count_12mo", "total_claim_amount",
        "claim_severity_band", "days_since_last_claim",
        "renewed", "renewal_month_label", "days_to_decision",
        "renewal_premium_change_pct", "outreach_contact_flag",
        "cltv_36mo", "post_renewal_coverage_tier",
    ]
    df = df[col_order]

    assert df.isnull().sum().sum() == 0, (
        f"Null values found in denormalized CSV: {df.isnull().sum()[df.isnull().sum() > 0]}"
    )

    return df


# --------------------------------------------------------------------------- #
# Step 8: metadata JSON                                                        #
# --------------------------------------------------------------------------- #

def build_metadata(
    cfg: dict,
    customers: pd.DataFrame,
    policies: pd.DataFrame,
    billing: pd.DataFrame,
    claims: pd.DataFrame,
    renewals: pd.DataFrame,
    denorm: pd.DataFrame,
) -> dict:
    """Build a metadata JSON summarizing row counts and actual vs. target rates."""
    known = denorm[denorm["renewed"].isin([0, 1])]
    aqx   = known[known["acquisition_channel"] == "AQX"]
    dw    = known[known["acquisition_channel"] == "Direct Web"]

    high_risk = (
        (denorm["missed_payment_count"] >= 1) | (denorm["nsf_flag"] == 1)
    )

    actual_rates = {
        "overall_renewal_rate":      round(known["renewed"].mean(), 4)      if len(known) > 0 else None,
        "aqx_renewal_rate":          round(aqx["renewed"].mean(), 4)        if len(aqx)   > 0 else None,
        "direct_web_renewal_rate":   round(dw["renewed"].mean(), 4)         if len(dw)    > 0 else None,
        "multi_product_attach_rate": round(denorm["multi_product_flag"].mean(), 4),
        "high_risk_pct":             round(high_risk.mean(), 4),
        "avg_annual_premium":        round(denorm["annual_premium"].mean(), 2),
        "avg_cltv_36mo":             round(denorm["cltv_36mo"].mean(), 2),
    }

    return {
        "project":       "waypoint-retention-analytics",
        "generated_at":  datetime.now().isoformat(),
        "seed":          cfg["dataset"]["seed"],
        "row_counts": {
            "dim_customer":         len(customers),
            "fact_policies":        len(policies),
            "fact_billing_summary": len(billing),
            "fact_claims":          len(claims),
            "fact_renewals":        len(renewals),
            "waypoint_retention":   len(denorm),
        },
        "actual_rates":  actual_rates,
        "target_rates":  cfg["rates"],
        "columns": {
            "waypoint_retention": list(denorm.columns),
        },
    }


# --------------------------------------------------------------------------- #
# Save helpers                                                                 #
# --------------------------------------------------------------------------- #

def save_csv(df: pd.DataFrame, path: Path, label: str) -> None:
    """Write a DataFrame to CSV and print a confirmation line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"  Saved {label}: {len(df):,} rows  ->  {path.relative_to(PROJECT_ROOT)}")


def print_rate_check(metadata: dict) -> None:
    """Print a comparison of actual vs. target rates for quick validation."""
    actual  = metadata["actual_rates"]
    targets = metadata["target_rates"]
    print("\nRate check (actual vs. target):")
    keys = [
        "overall_renewal_rate", "aqx_renewal_rate", "direct_web_renewal_rate",
        "multi_product_attach_rate", "high_risk_pct",
        "avg_annual_premium", "avg_cltv_36mo",
    ]
    for k in keys:
        a = actual.get(k)
        t = targets.get(k)
        status = "OK" if a is not None and abs(a - t) / max(t, 0.001) < 0.05 else "WARN"
        print(f"  [{status}] {k:<35} actual={a}  target={t}")


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #

def main() -> None:
    """Orchestrate all generation steps and write outputs to disk."""
    print("Loading config...")
    cfg = load_config(CONFIG_PATH)
    rng = np.random.default_rng(cfg["dataset"]["seed"])

    print("\nStep 1: Generating dim_customer...")
    customers = generate_dim_customer(cfg, rng)

    print("Step 2: Generating fact_policies...")
    policies = generate_fact_policies(cfg, rng, customers)

    print("Step 3: Generating fact_billing_summary...")
    billing = generate_fact_billing_summary(cfg, rng, policies)

    print("Step 4: Generating fact_claims...")
    claims = generate_fact_claims(cfg, rng, policies, customers)

    print("Step 5: Assigning renewals...")
    policies = assign_renewals(cfg, rng, policies, billing, claims, customers)

    print("Step 6: Generating fact_renewals...")
    renewals = generate_fact_renewals(cfg, rng, policies)

    print("Step 7: Building denormalized CSV...")
    # Drop internal temp column before saving source table
    policies_out = policies.drop(columns=["aqx_assisted_flag"])
    denorm = build_denormalized(cfg, rng, customers, policies, billing, claims, renewals)

    print("Step 8: Writing outputs...\n")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Source tables -> raw_tables/ and outputs/
    for df, name in [
        (customers,    "dim_customer"),
        (policies_out, "fact_policies"),
        (billing,      "fact_billing_summary"),
        (claims,       "fact_claims"),
        (renewals,     "fact_renewals"),
    ]:
        save_csv(df, RAW_DIR / f"{name}.csv", name)
        save_csv(df, OUT_DIR / f"{name}.csv", name)

    # Denormalized CSV and metadata -> outputs/ only
    save_csv(denorm, OUT_DIR / "waypoint_retention.csv", "waypoint_retention")

    metadata = build_metadata(cfg, customers, policies_out, billing, claims, renewals, denorm)
    meta_path = OUT_DIR / "waypoint_retention_metadata.json"
    with open(meta_path, "w") as fh:
        json.dump(metadata, fh, indent=2)
    print(f"  Saved metadata  ->  {meta_path.relative_to(PROJECT_ROOT)}")

    print_rate_check(metadata)
    print("\nPhase 2 data generation complete.")


if __name__ == "__main__":
    main()
