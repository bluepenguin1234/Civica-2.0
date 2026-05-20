# Civica Scoring Methodology
*Technical reference for the Harvard-style 6-dimension county scoring model.*  
*Version 1.2 — May 2026 · Includes FBI NIBRS Dim4*

---

## Table of Contents

1. [Model Overview](#1-model-overview)
2. [Scoring Architecture](#2-scoring-architecture)
3. [Why the Score Range Is 27–70, Not 0–100](#3-why-the-score-range-is-27-70)
4. [Normalization Method](#4-normalization-method)
5. [Dimension 1 — Affordability & Value (25 pts)](#5-dimension-1--affordability--value)
6. [Dimension 2 — Economic Vitality (22 pts)](#6-dimension-2--economic-vitality)
7. [Dimension 3 — Housing Market Dynamics (20 pts)](#7-dimension-3--housing-market-dynamics)
8. [Dimension 4 — Quality of Place (15 pts)](#8-dimension-4--quality-of-place)
9. [Dimension 5 — Physical Risk (12 pts)](#9-dimension-5--physical-risk)
10. [Dimension 6 — Population Momentum (6 pts)](#10-dimension-6--population-momentum)
11. [Market Labels](#11-market-labels)
12. [Monthly Cost Model](#12-monthly-cost-model)
13. [Data Sources and Vintage](#13-data-sources-and-vintage)
14. [Design Decisions and Known Tradeoffs](#14-design-decisions-and-known-tradeoffs)
15. [Update Cadence](#15-update-cadence)

---

## 1. Model Overview

Civica scores every US county with a population ≥ 5,000 on a 100-point composite scale. The model is structured around six research dimensions drawn from housing economics literature, each measuring a distinct aspect of county-level market quality. As of v1.3, all inputs are free federal government data. Median home values use ACS 5-year (B25077) — the only federal source for county-level home values. ACS is otherwise excluded from the model where administrative equivalents exist.

**Core design principles:**

- **Federal data only.** No agent-affiliated listings, no proprietary indexes, no survey estimates (ACS excluded — administrative equivalents are used for every metric that ACS would otherwise provide).
- **No advertising, no conflict of interest.** Scores cannot be bought or influenced by any party.
- **Percentile normalization.** Every metric is normalized relative to the national distribution of scored counties. A county is not judged against an absolute standard — it is judged relative to where it actually stands in the US.
- **Transparent weights.** Every dimension weight and intra-dimension weight is published. The scoring algorithm is fully reproducible from publicly available federal data.

**What the model does not do:**

- Forecast future prices.
- Replace local due diligence (neighborhood, school, employer proximity).
- Predict individual property outcomes.

The score is a composite signal for county-level market quality at a point in time. It answers: *relative to every other US county right now, how does this one perform across the six dimensions that most affect a homebuyer's financial outcome?*

---

## 2. Scoring Architecture

### Dimension Weights

| Dimension | Points | Share |
|---|---|---|
| Affordability & Value | 25 | 25% |
| Economic Vitality | 22 | 22% |
| Housing Market Dynamics | 20 | 20% |
| Quality of Place | 15 | 15% |
| Physical Risk | 12 | 12% |
| Population Momentum | 6 | 6% |
| **Total** | **100** | **100%** |

### Intra-Dimension Weights

Each dimension is composed of 3–4 metrics. Metric scores are expressed as national percentile ranks (0–100), weighted by their intra-dimension share, then scaled to the dimension's point value.

**Example — Dim1 (25 pts):**
```
dim1 = (pct_inv(P/R) × 0.30
      + pct_inv(P/I) × 0.30
      + pct_inv(breakeven) × 0.25
      + pct_inv(|hpi_avg − 5|) × 0.15) / 100 × 25
```

The `/100` converts the 0–100 percentile composite back to a 0–1 fraction before multiplying by the dimension's point value.

### County Universe

- **3,144 total counties** in the US (including county-equivalents: parishes, boroughs, independent cities)
- **2,820 scored** (population ≥ 5,000 — Census 2023 estimates)
- **324 excluded** (population < 5,000 — insufficient data; any score would be nearly pure imputation)

---

## 3. Why the Score Range Is 27–70

The theoretical scale is 0–100. The empirical distribution from v1.2 is:

| Statistic | Value |
|---|---|
| Mean | 50.0 |
| Standard deviation | 6.24 |
| Minimum (Clinch County GA) | 26.85 |
| Maximum (Hamilton County IN) | 69.48 |
| AVOID counties (score < 26) | 0 |

**The compression is by design, not a bug.** The six dimensions are positively correlated in the real world. Counties with strong economies also tend to have lower crime, tighter housing markets, and positive migration. The national percentile normalization captures each metric's relative standing, but the correlations between dimensions mean that a county at the 90th percentile on Dim1 is likely also near the 70th–80th percentile on Dim2 and Dim3. There is no county that is simultaneously the best in the country on all six dimensions and the worst on zero — such a county does not exist.

The practical result: the model correctly identifies *relative* differences among counties (Hamilton County IN vs. Clinch County GA is a 43-point spread), but the absolute values do not map to the labels in a naïve way. ACCELERATING does not mean "near 100" — it means "top of the actual distribution."

The score range also reflects the FBI NIBRS integration added in v1.2. Before NIBRS, the lowest-scoring counties could fall to ~23. NIBRS imputation (RUCC-tier median for non-reporting counties) set a higher floor for rural counties that previously scored near zero on crime simply from the absence of NIBRS data.

---

## 4. Normalization Method

All metrics use national percentile rank normalization:

```python
def pct(s):
    return s.rank(pct=True, na_option='keep') * 100

def pct_inv(s):
    return (1 - s.rank(pct=True, na_option='keep')) * 100
```

`pct()` is used when higher raw value = better (wages, appreciation, in-mover income quality).  
`pct_inv()` is used when lower raw value = better (P/R ratio, crime rate, flood claims).

**NaN handling:** Counties missing a metric due to data gaps receive NaN for that percentile. NaN propagates through the dimension calculation, reducing the county's total score proportionally to the weight of the missing metric. There is no artificial imputation of the *score* — only the *raw metric* is imputed (national median or RUCC-tier median, depending on the variable).

**Missing raw data imputation:**
- Numeric metrics (home value, wage, income, etc.): national median of scored counties
- Crime rate (FBI NIBRS): RUCC-tier median (rural non-reporters not penalized relative to similar rural counties)

---

## 5. Dimension 1 — Affordability & Value

**Weight: 25 points**  
*Is the price defensible relative to fundamentals?*

| Metric | Intra-weight | Direction | Source |
|---|---|---|---|
| Price-to-Rent Ratio | 30% | Lower = better | ACS 5-yr home value ÷ (HUD FMR 2BR × 12) |
| Price-to-Income Ratio | 30% | Lower = better | ACS 5-yr home value ÷ BEA per capita income |
| Buy vs. Rent Breakeven | 25% | Shorter = better | Computed from ACS home value + HUD FMR (see §12) |
| Appreciation Quality | 15% | Closer to 5% = better | \|FHFA 3-yr avg annual HPI − 5%\| |

### Price-to-Rent Ratio

National norm: 15–18x. Above 20x, ownership cost premium over renting grows meaningfully. The ratio uses HUD Fair Market Rents (2BR, FY2026) as the rent baseline — a federal benchmark for the local rental cost of a standard 2-bedroom unit.

### Price-to-Income Ratio

The ratio uses BEA per capita personal income (2024 estimate), not household income. This is deliberate: per capita income is available at county level from a federal administrative source (BEA) with no sampling error. ACS median household income would require survey data and has high margins of error for small counties.

**Important — benchmark mismatch:** The commonly cited "4.2x historical norm" for price-to-income ratios is based on median *household* income, not per capita income. BEA per capita income is roughly 40–45% lower than median household income nationally (~$67k per capita vs. ~$80k household). As a result, Civica P/I ratios will display roughly 1.5–1.8x higher than the commonly cited benchmark — a county at a normal 4.2x household-income P/I may show 6–7x in Civica's calculation. The *scoring* is unaffected (all counties use the same income base, so relative rankings are valid), but displayed ratios on county report pages must carry a footnote: "P/I uses BEA per capita personal income; the commonly cited 4.2× historical norm uses median household income." The equivalent per-capita historical norm is approximately 2.5–3.0×.

### Buy vs. Rent Breakeven

The number of years a buyer must hold to recoup the cost premium of ownership over renting:

```
down_payment = median_home_value × 0.20
monthly_PITI = P&I (7%, 30yr, 80% LTV) + (home_value × 0.012 / 12) + (home_value × 0.005 / 12)
monthly_excess = max(monthly_PITI − HUD_2BR_FMR, 1)
breakeven_years = min(down_payment / (monthly_excess × 12), 30)
```

Capped at 30 years. Markets where PITI < rent score immediately positive (breakeven ≤ 0 → clipped to 0).

**Known limitation:** Property tax is hardcoded at 1.2% (national median effective rate). Actual effective rates range from 0.28% (Hawaii) to 2.23% (Illinois, New Jersey, Vermont). This systematically underestimates carrying costs in high-tax states and overstates them in low-tax states. State-level average effective rates are available from the Lincoln Institute of Land Policy. This is a documented improvement for a future version.

### Appreciation Quality

`|FHFA_3yr_avg_annual_HPI − 5.0|`

Penalizes deviation from the target in either direction: stagnation (<3%) and froth (>7%) both score lower. Counties near 5% annual appreciation score highest.

**Known limitation:** The 5% target is nominal. At 3% long-run inflation, 5% nominal ≈ 2% real appreciation — a reasonable target. During high-inflation periods (2021–2022 when CPI exceeded 8%), 5% nominal implied negative real appreciation. A county at 8% nominal in 2022 was actually closer to the healthy real target than this formula suggests. The model does not adjust for the inflation environment of the measurement period. This is a deliberate simplification — CPI-adjusting HPI would require time-period-matched inflation data that complicates the pipeline considerably.

---

## 6. Dimension 2 — Economic Vitality

**Weight: 22 points**  
*Is the local economy growing in real terms?*

| Metric | Intra-weight | Direction | Source |
|---|---|---|---|
| Wage Level | 35% | Higher = better | BLS QCEW avg annual wage, 2023 |
| Sector Quality Score | 25% | Higher = better | BLS QCEW employment × NAICS quality weights |
| Economic Diversity (HHI) | 25% | Lower = better | Herfindahl-Hirschman Index, BLS QCEW NAICS |
| Income Growth | 15% | Higher = better | BEA CAINC1 per capita income, 4-yr growth |

### Wage Level

Avg annual wage from BLS QCEW 2023 (total private + government). Higher wage counties score higher. This captures both the current economic standard of living and the attractiveness of the labor market to in-movers.

### Sector Quality Score

```python
sector_quality = sum(employment_share_i × quality_weight_i for all NAICS supersectors)
```

**NAICS quality weights (Civica editorial judgments):**

| NAICS | Sector | Weight | Rationale |
|---|---|---|---|
| 54 | Professional, Scientific, Technical | 1.30 | Above-median wages; historically strong growth |
| 52 | Finance & Insurance | 1.30 | Above-median wages; relatively low cyclicality |
| 62 | Health Care & Social Assistance | 1.00 | Stable; median wages |
| 61 | Educational Services | 1.00 | Stable; median wages |
| All others | — | 1.00 | Neutral |
| 23 | Construction | 0.80 | Leading indicator but highly cyclical |
| 44-45 | Retail Trade | 0.60 | Secular headwinds from e-commerce |
| 31-33 | Manufacturing | 0.60 | Secular US employment decline |

**Important note:** These weights are Civica editorial judgments, not sourced from a specific academic study or BLS dataset. Finance at 1.30 reflects historically above-median wages and lower cyclicality than manufacturing. Manufacturing at 0.60 reflects 40 years of secular US employment decline. They are defensible as general proxies but should be understood as choices, not facts.

### Economic Diversity (HHI)

```python
HHI = sum((employment_share_i × 100) ** 2 for all NAICS codes)
```

Standard Herfindahl-Hirschman Index. HHI < 1,500 = diversified; HHI > 2,500 = concentrated. Single-industry towns (coal mining, oil extraction) score at the low end of this metric. `pct_inv()` is applied so lower HHI (more diversified) = higher percentile = better score.

### Income Growth

BEA per capita personal income growth over 4 years (latest available year vs. 4 years prior). Captures whether real economic conditions are improving. Counties with rising per capita incomes attract both workers and buyers.

---

## 7. Dimension 3 — Housing Market Dynamics

**Weight: 20 points**  
*What is the market actually doing?*

| Metric | Intra-weight | Direction | Source |
|---|---|---|---|
| 3-Year Appreciation Trend | 50% | Higher = better | FHFA HPI 3-yr avg annual change |
| Current Momentum | 20% | Higher = better | FHFA HPI latest annual change |
| Permit Pipeline | 30% | Higher = better | Census BPS total units permitted 2022 |

**v1.3 change:** Supply Tightness (Zillow active inventory, 30%) was removed. The 30% was redistributed: +15% to the 3yr trend (→ 50%), +5% to current momentum (→ 20%), +10% to permits (→ 30%). This makes Dim3 fully federal and eliminates the raw-count-vs-months-of-supply limitation.

### 3-Year Appreciation Trend and Current Momentum

Both metrics come from FHFA HPI — the 3-yr trend is the mean of the three most recent annual percentage changes; current momentum is the latest annual change. They are correlated by construction (a county with strong sustained appreciation almost always shows positive current momentum), with a typical inter-metric correlation of ~0.7–0.9. They are not two independent signals — they are two time-horizon views of the same underlying FHFA trend. The combined 70% weight in Dim3 (50% + 20%) should be understood as a single FHFA appreciation signal with strong emphasis on the sustained trend.

The two-horizon structure is still useful: a county with a strong 3-yr average but decelerating current momentum is a different risk profile from one accelerating on both. But do not describe them as "independent cross-validation" — that overstates their independence.

**Note on interaction with Dim1:** There is a deliberate tension between Dim1's Appreciation Quality metric (which penalizes deviation from 5% in either direction) and Dim3's Appreciation Trend (which rewards raw appreciation magnitude). A market at 10% annual appreciation will score well on Dim3 and be penalized on Dim1. The model does not resolve this tension — it captures both signals and lets them compete with different weights (Dim3 trend 50%×20% = 10% of total vs. Dim1 quality 15%×25% = 3.75% of total). The net result is that the model *slightly favors momentum over stability*, but with a ceiling imposed by the affordability penalty. This is by design: a hot market should score higher on market dynamics; a buyer should see the full picture of both the momentum and the stretched affordability.

### Permit Pipeline

Census BPS total housing units authorized 2022. The supply-side counter-signal: measures whether new construction is responding to demand. At 30% of Dim3, it provides a genuine counterweight to the 70% FHFA appreciation signals.

**Known limitation:** Higher permits = better is a demand-response proxy, not a supply-adequacy measure. It can inflate scores for Sun Belt build-heavy counties (Phoenix, Houston suburbs, Boise) if volume exceeds genuine household absorption. The theoretically correct metric is a permit-gap ratio (permitted units ÷ projected household formation), which requires ACS household formation projections — a candidate improvement for v1.4.

---

## 8. Dimension 4 — Quality of Place

**Weight: 15 points**  
*Is it a good place to actually live?*

| Metric | Intra-weight | Direction | Source |
|---|---|---|---|
| Crime Rate | 35% | Lower = better | FBI NIBRS 2024 — violent offenses per 100k |
| Urban Access | 40% | Lower RUCC = better | USDA Rural-Urban Continuum Codes 2023 |
| Amenity Density | 25% | Higher = better | Census CBP 2022 — establishments per 1,000 |

### Crime Rate (FBI NIBRS)

Violent offenses per 100,000 residents, derived from the FBI NIBRS 2024 National Master File (5.8 GB, fixed-width format). Offense counts are aggregated from 02 (offense) record segments by county, then divided by Census 2023 population estimates.

**Coverage:** 21,068 agencies across 49 states (New York does not participate). 2,869 of 3,144 counties have at least one reporting agency.

**Imputation for non-reporting counties:** Counties with no NIBRS-participating agency receive their RUCC-tier median violent crime rate. This prevents rural non-reporters from appearing artificially safe. The imputation is clearly flagged in the `county_scores.csv` output column `nibrs_imputed`.

**Offense code scope:** All NIBRS Group A violent offense codes are included (09A–09C homicide, 11A–11D sex offenses, 120 robbery, 13A–13C assault). Property crimes are excluded.

### Urban Access (USDA RUCC)

RUCC codes 1–9: 1 = metro area ≥ 1 million; 9 = completely rural, not adjacent to a metro area. `pct_inv()` applied so metro counties score higher. The 40% weight reflects that urban access is the single strongest predictor of long-term real estate liquidity and buyer pool depth.

### Amenity Density

Census CBP 2022: total private business establishments ÷ county population × 1,000. Higher density = more restaurants, services, employers, retail — a proxy for the economic texture of daily life. Note: CBP has an 18-month publication lag; 2022 data was the latest available.

---

## 9. Dimension 5 — Physical Risk

**Weight: 12 points** *(lower raw risk = higher score)*  
*What are the real climate and natural hazard costs?*

FEMA's National Risk Index (NRI) was not downloadable despite multiple attempts (direct download and manual fallback both blocked). Physical Risk is scored using the three datasets FEMA itself uses to build the NRI.

| Metric | Intra-weight | Direction | Source |
|---|---|---|---|
| Flood Loss Proxy | 40% | Lower = better | FEMA NFIP paid claims ÷ Census pop (10-yr avg) |
| Storm Damage Proxy | 35% | Lower = better | NOAA Storm Events property damage ÷ pop (5-yr avg) |
| Wildfire Exposure | 25% | Lower = better | USFS Wildfire Risk to Communities score |

**Composite:**
```
Physical Risk Score = pct_inv(flood_loss_per_cap) × 0.40
                    + pct_inv(storm_damage_per_cap) × 0.35
                    + pct_inv(wildfire_rank) × 0.25
```

Higher composite = lower physical risk = higher Dim5 score.

**Note on NFIP coverage:** NFIP only captures insured flood losses. Uninsured flood damage (common in lower-income counties and areas outside Special Flood Hazard Areas) is not reflected. NOAA Storm Events covers all storm types regardless of insurance status and partially offsets this gap.

**Homeowners insurance cost model (county report cards):**  
National median homeowners insurance ≈ $159/mo. County risk multiplier:
- Low-risk county (Physical Risk Score ≥ 85): × 0.72 → ~$115/mo
- Average county: × 1.00 → $159/mo
- High-risk county (Physical Risk Score ≤ 22): × 2.10 → ~$334/mo

---

## 10. Dimension 6 — Population Momentum

**Weight: 6 points**  
*Are people choosing this county, and what does that tell us?*

| Metric | Intra-weight | Direction | Source |
|---|---|---|---|
| Net Migration Rate | 60% | Higher = better | Census Population Estimates 2023 (RNETMIG2023) |
| Income Quality of In-Movers | 40% | Higher = better | IRS SOI Migration 2022-23 |

**Net Migration Rate:** RNETMIG2023 — net migration per 1,000 residents. Combines domestic and international net migration. A positive rate means more people are choosing to move in than out.

**Income Quality of In-Movers:**
```python
inmover_income_ratio = in_mover_avg_AGI / out_mover_avg_AGI
```
Ratio > 1.0 = higher-income households arriving than leaving. A ratio of 1.15 means incoming households earn on average 15% more than outgoing households — a positive signal for future tax base growth and housing demand quality.

**Why only 6%:** Migration is a *corroborating* signal, not a primary one. A county with strong economic fundamentals (Dim2) and strong market dynamics (Dim3) that also shows positive net migration is a high-conviction outcome — migration confirms what the other signals already establish. The 6% weight reflects this role: migration adds confirmation value at the margin, not independent analytical weight. A county should not score near the top on migration alone; if the economy is weak and prices are stretched, temporary in-migration (driven by relative affordability, not fundamentals) should not rescue the score.

**What this is not:** Migration is not a leading indicator in this model. It is a trailing confirmation signal. The description "strongest leading indicator" that may appear in earlier versions of this document is incorrect and should be disregarded.

---

## 11. Market Labels

Every county receives exactly one label based on total score.

| Label | Score Threshold | Guidance |
|---|---|---|
| ACCELERATING | ≥ 68 | All signals positive. Window still open, but monitor affordability trajectory. |
| PEAKING | ≥ 62 | Strong momentum; fundamentals show ceiling pressure. Best for shorter hold horizons. |
| ESTABLISHED | ≥ 55 | Solid, balanced market. Buy for stability and lifestyle, not appreciation upside. |
| EMERGING | ≥ 46 | Improving fundamentals with early-mover upside. Risk is real. |
| FRONTIER | ≥ 38 | Thin market. Fundamentals mixed — requires additional local due diligence. |
| TURNING | ≥ 30 | Softening demand signals. Monitor for continued weakness before committing. |
| SPECULATIVE | ≥ 26 | Poor fundamentals. Prices appear disconnected from underlying economics. |
| AVOID | < 26 | No dimension is working. (0 counties in v1.2 — empirical floor is 26.85.) |

**Label calibration:** Thresholds were set so that each label covers a meaningful, non-trivial fraction of the county distribution. ACCELERATING and PEAKING are intentionally rare (top ~2%); ESTABLISHED and EMERGING cover the core of the distribution. AVOID has 0 counties in v1.2 — the NIBRS integration raised the score floor above the 26-point threshold.

**v1.2 distribution:**
```
ACCELERATING:   2 counties    (0.1%)
PEAKING:       57 counties    (2.0%)
ESTABLISHED:  563 counties   (20.0%)
EMERGING:   1,463 counties   (51.9%)
FRONTIER:     634 counties   (22.5%)
TURNING:       97 counties    (3.4%)
SPECULATIVE:    4 counties    (0.1%)
AVOID:          0 counties    (0.0%)
```

---

## 12. Monthly Cost Model

The scoring engine computes `monthly_piti` for each county — the all-in ownership carrying cost used in the Dim1 breakeven calculation.

```python
r = 0.07 / 12  # 7% annual rate, monthly
mortgage_factor = r / (1 - (1 + r) ** -360)  # 30-year amortization factor

monthly_PITI = (
    median_home_value × 0.80 × mortgage_factor   # principal & interest (80% LTV)
  + median_home_value × 0.012 / 12               # property tax (1.2% annual)
  + median_home_value × 0.005 / 12               # homeowners insurance (0.5% annual)
)
```

**Known limitation — property tax:** The 1.2% effective rate is the national median. Actual effective property tax rates span 0.28% (Hawaii) to 2.23% (New Jersey, Illinois, Vermont). At a $400,000 home value, this creates a monthly cost error of $315/mo (Hawaii overstated by $300; NJ understated by $340). State-level average effective rates are published by the Lincoln Institute of Land Policy and could replace the hardcoded rate in a future version. Until then, users in high-tax states (IL, NJ, TX, WI, NH) should mentally adjust the displayed breakeven horizon upward.

**Rate assumption:** 7% reflects the approximate national 30-year fixed rate through 2024. This will be updated as rates change in future scoring runs.

---

## 13. Data Sources and Vintage

| # | Dataset | Vintage | Used For |
|---|---|---|---|
| 1 | ACS 5-year (B25077, median home value) | 2019–2023 | Dim1: P/R, P/I, breakeven — sole home-value source; no federal administrative equivalent exists |
| 2 | FHFA HPI (county-level) | Annual through 2024 | Dim1: appreciation quality; Dim3: trend + momentum |
| 3 | HUD Fair Market Rents | FY2026 | Dim1: rent baseline, P/R, breakeven |
| 4 | BEA CAINC1 (per capita income) | 2024 estimate | Dim1: P/I; Dim2: income growth |
| 5 | BLS QCEW (wages, employment) | 2023 annual | Dim2: wages, sector quality, HHI |
| 6 | Census Building Permits Survey | 2022 | Dim3: permit pipeline |
| 7 | Census CBP (business establishments) | 2022 | Dim4: amenity density |
| 8 | USDA Rural-Urban Continuum Codes | 2023 | Dim4: urban access |
| 9 | FBI NIBRS National Master File | 2024 | Dim4: violent crime per 100k |
| 10 | FEMA NFIP (flood insurance claims) | 10-yr avg through 2023 | Dim5: flood loss per capita |
| 11 | NOAA Storm Events | 2019–2023 | Dim5: storm damage per capita |
| 12 | USFS Wildfire Risk to Communities | 2022 | Dim5: wildfire exposure |
| 13 | Census Population Estimates | 2023 | Base universe; migration rates; denominators |
| 14 | IRS SOI Migration | 2022–2023 | Dim6: in-mover income quality |

**v1.3 note:** As of v1.3, Civica uses no proprietary data sources. ACS 5-year (B25077) provides median home values — the only metric for which no federal administrative equivalent exists at county level. ACS is otherwise excluded from the model where administrative equivalents exist (BEA for income, QCEW for employment). All appreciation signals use FHFA HPI only. Inventory (Zillow) was removed from Dim3 in v1.3.

**FHFA coverage:** FHFA HPI covers approximately 2,800 of 3,143 counties. The remaining ~340 rural counties receive national median imputation for all FHFA-derived metrics.

**Known data vintage gaps:** CBP is 18 months behind (2022 data, used in 2026); BPS is similarly lagged. These are the latest vintages available; no alternative county-level sources exist.

---

## 14. Design Decisions and Known Tradeoffs

This section documents the major methodological choices, including honest acknowledgment of known limitations and alternative approaches considered.

### 14.1 Permits Scored Higher = Better (Known Limitation)

The permit pipeline metric treats higher new construction as a positive signal ("demand response"). The valid critique is threefold:

1. **Double-counting:** Strong permit activity in a county already shows up in Dim3's appreciation trend (rising prices attract builders) and inventory tightness (builders respond to low supply). Permits adds a third read on the same demand signal.
2. **Sun Belt inflation:** High-permit-volume metros like Phoenix, Austin, Houston suburbs, and Boise score well on this metric regardless of whether their permit volume reflects genuine household absorption or speculative overbuilding.
3. **The correct metric** is a permit-gap ratio (permits ÷ projected household formation). A county under-building relative to its household formation has genuine supply constraint. A county over-building relative to its household formation is accumulating future price headwind. That ratio requires ACS household formation projections, which conflict with the no-survey-data policy.

The current implementation is an acknowledged simplification. Users analyzing Sun Belt markets should check permits against net migration (Dim6 net migration rate) — if permits substantially exceed net household formation, the county may be over-building.

### 14.2 The Appreciation Tension: Dim1 vs. Dim3

Dim1 Appreciation Quality penalizes deviation from 5% annual appreciation. Dim3 Appreciation Trend rewards raw appreciation magnitude. A market at 10% annual appreciation gets a Dim1 penalty (deviation of 5 pts from target) and a Dim3 bonus (strong trend). The net effect is that the model slightly favors momentum over stability.

This is intentional, not an error. A hot market *should* score well on market dynamics; a buyer *should* simultaneously see the stretched affordability penalty. The two signals compete with different weights (Dim3 trend drives ~7% of the total vs. Dim1 appreciation quality ~3.75%), so the model gives more credit to momentum than to stability — reflecting the empirical reality that buyers benefit from market direction.

The alternative — deviation-based scoring in both Dim1 and Dim3 — would penalize fast-appreciating markets twice and systematically favor slow-growth markets regardless of whether that stability reflects health or stagnation. The current approach is the more informative of the two.

### 14.3 ZHVI Imputation Bias (Known Limitation)

When Zillow has no home value for a county, the national median home value (~$350k as of 2025) is imputed. This creates systematic ratio bias:

A rural county with $600/mo FMR rents gets:
- Imputed P/R = $350,000 / ($600 × 12) = 48.6x (extreme; scores near Dim1 floor)
- Actual P/R may be $130,000 / ($600 × 12) = 18.1x (national norm)

The correct fix is to impute the P/R ratio directly from comparable counties (same RUCC tier, same state), rather than imputing the numerator alone and letting the ratio distort. This is documented as a future improvement. Counties with imputed ZHVI are flagged in the output; their Dim1 scores should be interpreted with caution.

### 14.4 Nominal Appreciation Target (Known Limitation)

The Appreciation Quality target (5% annual) is nominal. The real implication changes with the inflation environment:

| Inflation | 5% nominal implies | Notes |
|---|---|---|
| 3% | +2% real | Reasonable long-run target |
| 6% | -1% real | Penalizes counties that are barely keeping up |
| 8% (2022) | -3% real | Severely penalizes counties during high inflation |

The model does not adjust for the inflation environment of the measurement period. During the 2021–2022 inflation episode, a county at 8–9% nominal appreciation was closer to a healthy real target than a county at 5% nominal — but the formula scored them in the opposite direction. A CPI-adjusted version using Federal Reserve H.15 or BLS CPI data would resolve this. The pipeline cost is moderate; this is a candidate for v1.3.

### 14.5 Property Tax Hardcoded at 1.2% (Known Limitation)

See §12 Monthly Cost Model. The national median effective property tax rate is used as a universal constant. The $315/mo error range (Hawaii vs. NJ at $400k home value) is material and affects the breakeven horizon significantly.

At a $400k home:
- Hawaii (0.28%): actual monthly tax = $93; model uses $400 → breakeven understated by $307/mo
- NJ (2.23%): actual monthly tax = $743; model uses $400 → breakeven overstated by $343/mo

**Immediate workaround for users:** The displayed monthly cost and breakeven on county report pages should include a disclaimer for high-tax states.

### 14.6 Sector Quality Weights Are Editorial

The NAICS quality multipliers reflect Civica's judgment, not a sourced academic framework. Finance and Professional Services at 1.30 reflects historical US wage data (both sectors are consistently above median wage in BLS OEWS) and relatively stable long-term employment share. Manufacturing at 0.60 reflects 40 years of secular US employment decline as a share of total employment.

These weights have not been validated against county-level outcome data (e.g., does a county with more Professional Services workers actually see stronger price appreciation over 10 years?). They are reasonable priors but should be clearly labeled as Civica's analytical choices in all external communication.

### 14.7 Migration Weight vs. Its Corroborating Role

Population Momentum is weighted 6% — the lowest dimension weight. This is correct. Migration is a confirming signal: it tells you that people are already acting on the fundamentals that Dim1–Dim3 describe. It does not predict future fundamentals independently.

The framing to avoid: "migration is the strongest leading indicator." It is not. It is a trailing signal. A county with collapsing affordability and declining wages that still shows positive net migration (perhaps driven by relative affordability vs. an adjacent coastal market) will correctly show mild Dim6 credit while being penalized on Dim1 and Dim2. The model handles this correctly. The 6% weight reflects that migration alone cannot rescue a county with weak fundamentals.

### 14.8 No ACS Survey Data

All metrics use federal administrative data (BEA, BLS, Census population estimates, FHFA, HUD, IRS, FBI, FEMA, NOAA, USFS) rather than ACS sample survey data. This is deliberate: ACS has high margins of error for small counties (population < 20,000) and introduces a survey sampling layer that administrative data avoids. Administrative equivalents exist for every metric that ACS would otherwise provide.

### 14.9 No School Data

School quality is not scored. The best county-level school data sources (NCES Common Core of Data, Stanford Education Data Archive) are not in the data pipeline. More importantly, school quality is highly intra-county variable — the county-level average would obscure the school district variation that actually matters to buyers. A county with one top-performing and one low-performing district would show a middling average that is meaningless to any individual buyer. School quality is better addressed at the school district or ZIP level, which Civica does not currently score.

### 14.10 Why Two-Bedroom FMR

HUD Fair Market Rents are published for 0BR, 1BR, 2BR, 3BR, and 4BR. Civica uses 2BR FMR as the rent baseline for all ratio calculations. This is the standard HUD reference unit for housing affordability analysis and approximates the relevant unit size for a median buyer household (2+ person household). Using studio or 1BR FMR would understate the rent-equivalent for buyers with families; using 3BR+ would overstate it for singles and couples.

### 14.11 IRS AGI Retirement Destination Bias

The in-mover income quality metric (Dim6) uses average IRS AGI for households filing in a destination county that previously filed in a different county. AGI includes capital gains, which are often realized in the year of a major life transition such as retirement — selling appreciated employer stock, liquidating a portfolio, or converting a primary residence. Retirees moving to FL, AZ, NV, and SC frequently show very high AGI in their move year for this reason, making those counties appear to attract far wealthier households than their earned income would suggest.

The correct fix is to use wage-and-salary income only from the IRS SOI migration file (the data does include this breakout). However, this would exclude the legitimate economic value of retirees with genuinely high investment income. The current implementation is a known upward bias for warm-climate retirement destinations and should be noted when interpreting Dim6 scores for FL, AZ, NV, and SC counties.

### 14.12 v1.3: Removal of Zillow Data (Source Concentration Resolved)

In v1.2, Zillow ZHVI was the only non-federal source and drove approximately 27% of every county's score. v1.3 removes it entirely.

- **Home values** → ACS 5-year B25077: the only federal county-level home value source. Stable 5-year rolling average; slower to reflect recent price movements than Zillow's monthly index, but eliminates proprietary data dependency.
- **Active inventory** (Zillow, Dim3 30%) → removed. Redistributed: 3yr FHFA trend +15% (→ 50%), current momentum +5% (→ 20%), permit pipeline +10% (→ 30%).

Remaining concentration: ACS B25077 now drives ~21% of total score via Dim1. For counties where ACS is missing, RUCC-tier median imputation applies; flagged via `home_value_imputed = True`.

---

## 15. Update Cadence

| Dataset | Vintage in Model | Next Expected Release | Update Priority |
|---|---|---|---|
| FHFA HPI (county) | Annual through 2024 | Q1 2026 | High — core Dim1/Dim3 signals |
| BLS QCEW | 2023 annual | Q2 2026 | High — Dim2 wages and sector quality |
| BEA CAINC1 | 2024 estimate | Q3 2026 | High — Dim1 P/I, Dim2 income growth |
| FBI NIBRS | 2024 | Q4 2026 | High — Dim4 crime rate |
| IRS SOI Migration | 2022–23 | Q4 2026 | Medium — Dim6 in-mover quality |
| FEMA NFIP Claims | 10-yr avg | Annually | Medium — Dim5 flood proxy |
| NOAA Storm Events | 2019–2023 | Annually | Medium — Dim5 storm proxy |
| ACS 5-yr (B25077) | 2019–2023 | ~Dec 2025 (2020–2024 release) | High — home values drive Dim1 ratios |
| HUD FMR | FY2026 | FY2027 (Oct 2026) | High — affects all Dim1 ratios |
| Census Population Estimates | 2023 | Q3 2026 | Medium — denominators |
| Census BPS | 2022 | 2023 data in 2025 | Low — permits lag ~18 months |
| Census CBP | 2022 | 2023 data in 2025 | Low — CBP lag ~18 months |
| USDA RUCC | 2023 (10-yr cycle) | ~2033 | None until next cycle |
| USFS Wildfire Risk | 2022 | ~2027 | Low |

**Recommended re-score trigger:** When FHFA HPI, BLS QCEW, and BEA CAINC1 all have fresh annual releases — approximately Q3/Q4 of each calendar year. A full re-score takes ~4 minutes on a standard laptop. All 2,820 county scores are recomputed from scratch each run; there is no incremental update.
