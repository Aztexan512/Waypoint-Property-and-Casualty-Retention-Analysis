# Pattern Log
**Project:** waypoint-retention-analytics
**Archetype:** Custom (Hybrid A/B)
**Date:** 2026-05-02
**Author:** Luciano Casillas

---

## How to Use This File

Drop this file into a new Claude conversation alongside other PATTERN_LOG.md
files from previous projects before Gate 3. The agent reads all pattern logs
before proposing a new tab structure, reusing proven patterns and flagging
novel ones for addition here after approval.

---

## Tab 1: Retention Overview

**Archetype:** Custom (Hybrid A/B)
**Project:** waypoint-retention-analytics
**Business questions answered:** Q01 (cohort retention curves), Q09 (claims
and renewal relationship)

### Layout
Full-width cohort retention heatmap above the fold.
Two-column paired charts below: cohort line chart (left) + claims severity
bar chart (right).
Full-width dual-axis chart at the bottom of the tab.

### Charts

| Chart | Type | Notes |
|---|---|---|
| Cohort Retention Heatmap | HTML table (not canvas) | Rows = cohort quarters; columns = months 1-12; blue gradient cells; white text above 78%, black at or below; null cells grey with "--"; 0.5px STEEL_300 gridlines |
| 12-Month Renewal Rate by Cohort Quarter | Line + markers | BLUE_700 line; ORANGE_700 dashed trend line; STEEL_700 dashed reference at book average; text labels top center; paired with claims severity bar |
| Renewal Rate by Claims Severity Band | Bar | Value hierarchy: highest bar BLUE_700, others BLUE_500; STEEL_700 dashed reference at book average; paired with cohort line |
| Renewal Rate vs. Claim Payout Amount | Dual-axis line + bar | Bars BLUE_500 (policy count, left axis); ORANGE_700 line with white-ring markers (renewal rate, right axis); full width |

### Reuse Notes
The cohort retention heatmap (HTML table with blue-gradient cells) is the
right choice for any analysis where you need to track a population across
a time dimension (months, quarters) from a fixed start event. It is more
readable than a Plotly heatmap for this shape of data because cell values
and colors can be computed independently in JavaScript, and null cells
render as "--" without breaking the color scale. Use whenever the question
is "how does a cohort behave over time?"

The dual-axis renewal rate vs. claim amount chart is reusable for any
tab that needs to simultaneously show population volume (bars) and an
outcome rate (line) across a segmentation variable. The key is that the
right y-axis should start at 0 and extend to 105% to leave room for
line labels.

---

## Tab 2: Channel and Value

**Archetype:** Custom (Hybrid A/B)
**Project:** waypoint-retention-analytics
**Business questions answered:** Q07 (channel retention), Q04 (CLTV by
channel and tier)

### Charts

| Chart | Type | X | Y | Color Logic | Notes |
|---|---|---|---|---|---|
| 12-Month Renewal Rate by Acquisition Channel | Bar | Channel | Renewal rate % | Highest BLUE_700, others BLUE_500 | STEEL_700 dashed reference at book avg; paired with CLTV bar; shared conceptual y-max |
| Average 36-Month CLTV by Acquisition Channel | Bar | Channel | Avg CLTV ($) | Highest BLUE_700, others BLUE_500 | Paired with renewal rate bar |
| AQX vs. Non-AQX Renewal Rate by Cohort Quarter | Dual-axis line | Cohort quarter | Renewal rate % | BLUE_700 AQX, STEEL_700 dashed Non-AQX; RED_SOFT vertical reference at launch | Full width; white-ring markers; legend below |
| Average 36-Month CLTV by Coverage Tier | Bar | Coverage tier | Avg CLTV ($) | Value hierarchy | Paired with agency/tenure grouped bar |
| Renewal Rate by Agency Type and Tenure Band | Grouped bar | Agency type | Renewal rate % | NAVY/BLUE_700/BLUE_500/STEEL_300 per tenure band | 4-dataset grouped; legend below |

### Reuse Notes
Pairing a renewal rate bar with a CLTV bar on the same row is the standard
two-axis quality-and-value display for any channel or segment analysis. The
two bars should share a conceptual scale when possible (both show %) but
can use different y-axes when units differ. The AQX vs. Non-AQX trend with
a vertical launch reference line is the standard "event impact" pattern --
identical to the meridian AQX adoption overlay. Use for any platform launch,
policy change, or campaign where you need to show before/after behavior.

---

## Tab 3: Predictive Model

**Archetype:** A (Discovery)
**Project:** waypoint-retention-analytics
**Business questions answered:** Q02 (renewal prediction), Q05 (lapse
warning score)

### Charts

| Chart | Type | X | Y | Color Logic | Notes |
|---|---|---|---|---|---|
| Lift by Lapse Propensity Decile | Bar | Decile (D1-D10) | Lift vs. baseline | D1-D2 BLUE_700, D3-D10 BLUE_500 | Decile 1 = highest risk (negated qcut); STEEL_700 dashed baseline at 1.0x |
| Cumulative Gain Curve | Line with fill | % contacted | % lapses captured | BLUE_700 model; STEEL_300 dashed random baseline | Gradient fill rgba(0,119,179,0.10); annotation at 20% contact rate |
| SHAP Feature Importance | Horizontal bar | Mean absolute SHAP | Feature name (Title Case) | Top feature BLUE_700, others BLUE_500 | l:185 margin override; autorange reversed; no raw column names |
| Confusion Matrix | 4-cell discrete | Actual vs. predicted | Counts | NAVY correct (TN, TP); RED_SOFT error (FP, FN); WHITE text | TN top-left, FP top-right, FN bottom-left, TP bottom-right; full-word counts below; "So What" strip below |
| Lapse Risk Score Distribution | CSS histogram | Score bins 0.0-1.0 | Policy count | BLUE_500 low (0-0.4); ORANGE_700 medium (0.4-0.7); RED_SOFT high (0.7-1.0) | CSS bars not canvas; three-color legend below |
| At-Risk Policyholder Profile Explorer | 4 metric tiles + radio | Risk band radio | Count, renewal rate, payment method, tenure | BLUE_700 top border on tiles | Radio switches tile values; narrative below tiles |

### Required Components
- Dotted divider (1.5px GRAY_300) between model performance and early warning sections
- "So What" strip below confusion matrix (BLUE_700 left border, uppercase label)
- SHAP subtitle in STEEL_700 explaining mean absolute SHAP in plain language

### Reuse Notes
This tab is Archetype A standard and should be copied verbatim on every
Discovery dashboard with a binary classification model. The only
project-specific elements are the feature names in the SHAP chart, the
"So What" copy in the confusion matrix strip, and the tile labels in the
at-risk explorer. Everything else is structural boilerplate.

Key difference from meridian Tab 3: the top features here are behavioral
(payment consistency, missed payment count) rather than agency-structural
(size tier, tenure). The SHAP chart ordering will reflect this.

---

## Tab 4: Cross-Sell Funnel

**Archetype:** Custom (Hybrid A/B)
**Project:** waypoint-retention-analytics
**Business question answered:** Q10 (auto-to-renters cross-sell funnel)

### Layout
Full-width two-column: CSS funnel left, narrative panel right.
Paired bar charts below.

### Charts

| Chart | Type | Notes |
|---|---|---|
| Renters Attachment Funnel | CSS/HTML div bars | 4 stages; bar WIDTH = % of original population (always narrows); label = count + "% of prior stage" ONLY; drop annotation in RED_SOFT between stages; narrative panel right with STEEL_700 left border |
| Renters Cross-Sell Rate by Agency Type | Bar | Value hierarchy; paired with tenure band; shared y-max |
| Renters Cross-Sell Rate by Customer Tenure Band | Bar | Value hierarchy; paired with agency type; shared y-max |

### Funnel Bar Width Rule (CRITICAL)
Bar widths must always be calculated as (stage_n / stage_1) * 100.
Never use "% of prior stage" for bar width -- this causes later bars
to appear wider than earlier bars when the prior-stage conversion rate
is high. The funnel visual contract is that bars always narrow.

Labels show: count on line 1, "X% of prior stage" on line 2.
Do NOT show "% of original population" in the label -- the bar width
already encodes this. Showing both is redundant and adds noise.
For the first bar, show "Starting Population" as the sub-label.

### Reuse Notes
This funnel pattern (CSS bars, always-narrowing, % of prior in label)
is directly reusable for any sequential conversion process: insurance
quote funnels (see meridian Tab 1), claims processing pipelines,
onboarding stage completion, patient referral pathways, e-commerce
checkout funnels. The key design rule is the same in all cases:
bar width = % of original, label = % of prior.

---

## Tab 5: Financial Impact

**Archetype:** A (Discovery)
**Project:** waypoint-retention-analytics

### Simulator Pattern
Two sliders (target renewal rate, incremental renters attachment lift) +
results card + scenario comparison bar + two reactive downstream charts.
Results card: GREEN_700 left border, 16px font, line-height 2.8.
Scenario bar: selected GREEN_700, below selected BLUE_500, above selected STEEL_300.
HTML color legend below scenario bar (three swatches + labels).
Downstream charts labeled with italic reactive note above them.
Reactive stacked bar uses BLUE_700 current + GREEN_700 at 65% opacity projected gain.

### Reuse Notes
Identical pattern to meridian Tab 4 simulator. Reusable for any
financial impact tab. The only project-specific elements are the
slider labels, the results card metrics, and the downstream chart types.

---

## Tab 6: Recommendations

**Archetype:** A (Discovery) -- standard, always same structure

Three tiers: Immediate (ORANGE_700), Short-Term (BLUE_700), Strategic (NAVY).
2 cards per tier minimum. Context paragraph above all tiers (STEEL_100 background).
Card structure: title, badge row (GREEN value + STEEL effort), bulleted body, evidence line.

---

## Tab 7: Healthcare Application (Cross-Industry Translation)

**Archetype:** A (Discovery) -- always final tab

**Source domain:** Insurance (policyholder retention)
**Target domain:** Healthcare (patient retention, readmission prevention)

8-row signal translation table (dk-table, 0.5px STEEL_300 gridlines).
Three lever cards (number, title, body, green stat badge).
Full-width NAVY portability strip below.

Translation mappings established:
- 12-Month Renewal Rate to Annual Patient Retention Rate
- Lapse Risk Score to Early Readmission Risk Score
- Missed Payment Count to Missed Appointment Count
- Payment Consistency Score to Care Plan Adherence Score
- Multi-Product Attachment to Preventive Care Enrollment
- Coverage Tier Downgrade to Care Plan Downgrade or Step-Down
- Claims Severity Band to Procedure Complexity or Chronic Condition Burden
- AQX-Assisted Flag to Patient Portal Engagement Flag

---

## Novel Patterns Introduced in This Project

1. **Cohort retention heatmap (HTML table)** -- blue-gradient cells computed
   in JavaScript; column = month since effective date; null cells render "--".
   Reuse for any cohort-by-time retention or engagement analysis.

2. **Always-narrowing CSS funnel with % of prior label** -- bar width =
   % of original population; label = count + "% of prior stage" only.
   The bar encodes the cumulative story; the label encodes the stage story.
   These two dimensions should never be combined in a single label.

3. **KPI grid with min-width:0** -- CSS Grid containing Plotly sparklines
   requires min-width:0 on grid items and overflow:hidden on sparkline
   containers. Without this, Plotly inflates each cell to its natural
   chart width, blowing out the grid.

4. **BL() left margin standard** -- Default l:62 (not l:16). Applies to
   all charts with y-axis titles. Override to l:185 for SHAP charts with
   long feature name labels on the y-axis.

5. **base_layout showlegend override** -- base_layout includes showlegend=False
   as one of its 5 required keys. Passing showlegend=True as a separate keyword
   argument alongside **base_layout raises: "update_layout() got multiple values
   for keyword argument 'showlegend'". Fix: merge the override into the dict
   spread before unpacking: **{**base_layout, "showlegend": True}. Apply this
   pattern any time a base_layout key needs to be overridden at the call site.

6. **add_vline on categorical x-axis** -- Plotly's add_vline() requires a
   numeric x value. When the x-axis is categorical (e.g., cohort quarter strings
   like "2023Q3"), add_vline raises "unsupported operand type(s) for +: 'int'
   and 'str'" because it tries to compute a numeric mean to position the
   annotation. Fix: use add_shape(type="line", xref="x", x0=category,
   x1=category, y0=0, y1=1, yref="paper") for the line and add_annotation()
   for the label. This pattern applies to any vertical reference line on a
   time-series or cohort chart that uses string category labels on the x-axis.

---

*Pattern Log version 1.0 -- waypoint-retention-analytics*
