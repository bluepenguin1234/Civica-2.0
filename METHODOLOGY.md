# Civica Scoring Methodology
*Complete technical reference — scoring engine v1.2, May 2026*

---

## Table of Contents

1. [What Civica Measures and Why](#1-what-civica-measures-and-why)
2. [The Scoring Architecture](#2-the-scoring-architecture)
3. [How Percentile Normalization Works](#3-how-percentile-normalization-works)
4. [Dimension 1 — Affordability & Value (25 pts)](#4-dimension-1--affordability--value-25-pts)
5. [Dimension 2 — Economic Vitality (22 pts)](#5-dimension-2--economic-vitality-22-pts)
6. [Dimension 3 — Housing Market Dynamics (20 pts)](#6-dimension-3--housing-market-dynamics-20-pts)
7. [Dimension 4 — Quality of Place (15 pts)](#7-dimension-4--quality-of-place-15-pts)
8. [Dimension 5 — Physical Risk (12 pts)](#8-dimension-5--physical-risk-12-pts)
9. [Dimension 6 — Population Momentum (6 pts)](#9-dimension-6--population-momentum-6-pts)
10. [Total Score & Market Labels](#10-total-score--market-labels)
11. [The 8 Derived Metrics](#11-the-8-derived-metrics)
12. [Data Sources — All 14 Datasets](#12-data-sources--all-14-datasets)
13. [Coverage, Filters & Missing Data](#13-coverage-filters--missing-data)
14. [Design Decisions & Tradeoffs](#14-design-decisions--tradeoffs)
15. [Known Limitations](#15-known-limitations)

---

## 1. What Civica Measures and Why

Civica answers one question: **Is this county a good place to buy a home right now?**

That question has six distinct components:

- **Is the price defensible?** (Affordability & Value)
- **Is the economy healthy and growing?** (Economic Vitality)
- **What is the housing market itself doing?** (Market Dynamics)
- **Is it actually a good place to live?** (Quality of Place)
- **What are the climate and hazard costs?** (Physical Risk)
- **Are the right people moving in?** (Population Momentum)

Each component is scored separately, weighted by its importance to a homebuyer's long-term return, and added into a single 0–100 composite score. The score is derived entirely from free federal government data — no agent opinions, no listing algorithms, no advertising.

**Why federal data only?** Because federal data is:
- Collected consistently across all 3,143 US counties using the same methodology
- Published publicly with no commercial motive to distort
- Auditable — every number can be traced to its source file
- Updated regularly on a published schedule

The one exception is Zillow ZHVI, used only for county-level median home values and active inventory counts. No federal dataset provides both of those at county granularity with monthly updates. All price *appreciation* signals use FHFA, not Zillow.

---

## 2. The Scoring Architecture

### Dimension weights

| # | Dimension | Points | Weight |
|---|---|---|---|
| 1 | Affordability & Value | 25 | 25% |
| 2 | Economic Vitality | 22 | 22% |
| 3 | Housing Market Dynamics | 20 | 20% |
| 4 | Quality of Place | 15 | 15% |
| 5 | Physical Risk | 12 | 12% |
| 6 | Population Momentum | 6 | 6% |
| | **Total** | **100** | **100%** |

### Why these weights?

**Affordability (25%)** is the largest weight because price relative to rent and income is the primary determinant of long-term homebuyer financial outcomes. An overpriced market produces poor returns regardless of how good everything else is.

**Economic Vitality (22%)** drives both rent levels and future price appreciation. A county where workers earn more over time is one where housing demand and values will grow. It is the fundamental engine underneath price trends.

**Market Dynamics (20%)** captures what the market is actually doing right now — not what it should do based on fundamentals, but what it is doing. A market can have good fundamentals but still be turning; this dimension catches that.

**Quality of Place (15%)** matters because homebuyers don't just buy financial assets — they buy places to live. Safety, urban access, and amenity density directly affect daily life and resale demand.

**Physical Risk (12%)** is weighted at roughly half of affordability because climate and hazard costs are partially transferable (insurance, hardening) but represent a real and growing financial tail risk. Counties with high wildfire or flood exposure have higher carrying costs and future insurance uncertainty.

**Population Momentum (6%)** is a leading indicator but a weaker one — migration can reverse quickly and is correlated with economic vitality. It gets meaningful weight because in-mover income quality (who is moving in, not just how many) is a signal no other platform publishes.

### Processing pipeline

```
14 raw datasets
       ↓
  Merge on FIPS code (left join, Census population as universe)
       ↓
  Filter: population ≥ 5,000
       ↓
  Fill remaining nulls with national median per column
       ↓
  Score each dimension (percentile normalization)
       ↓
  Sum 6 dimension scores → total_score (clipped 0–100)
       ↓
  Apply market label thresholds
       ↓
  Output: county_scores.csv (2,820 rows × 35 columns)
```

---

## 3. How Percentile Normalization Works

Every metric inside each dimension is converted to a **national percentile rank** before being weighted. This is the most important design decision in the model, and understanding it explains why the score distribution looks the way it does.

### The two normalization functions

```python
def pct(s):
    # Higher raw value → higher score
    return s.rank(pct=True, na_option='keep') * 100

def pct_inv(s):
    # Lower raw value → higher score (used for risk/cost metrics)
    return (1 - s.rank(pct=True, na_option='keep')) * 100
```

`pct()` is used for metrics where more is better: wages, appreciation, migration rate.

`pct_inv()` is used for metrics where less is better: crime rate, breakeven years, physical risk, price-to-rent ratio.

### What this means in practice

When we rank all 2,820 counties on, say, average annual wage, the result is a number between 0 and 100 for each county — its percentile position in the national distribution. The county with the highest wages gets ~100; the lowest gets ~0; the median county gets ~50.

Percentile normalization has three important properties:

1. **Units cancel.** You can combine wages (dollars/year) with crime rates (offenses/100k) and appreciation (percent/year) without any unit conversion. Every input to the weighted sum is in 0–100 space.

2. **Outliers are compressed.** A county with crime 10× the national average doesn't score 10× worse — it scores near 0 on that metric, same as a county with crime 5× the average. This prevents a single extreme value from dominating the total score.

3. **The total score is mathematically bounded.** Because each metric percentile is 0–100, and dimension scores are scaled to their maximum point value, the theoretical maximum score is 100 and minimum is 0. In practice, no county achieves either extreme — the empirical range is approximately 27–70 (mean 50, std 6.2).

### Why the range is 27–70, not 0–100

The answer is correlation. Metrics within dimensions — and dimensions with each other — are positively correlated. A county with high wages also tends to have high income growth. A county with low crime also tends to have better urban access. Because the inputs are correlated, no county consistently ranks near 0 or 100 on all metrics simultaneously. The math forces the composite toward the center.

This is by design. A 0–100 range that used all 100 points would require manufactured spread (ranking counties against each other on completely uncorrelated metrics). Percentile normalization produces an honest distribution. The label thresholds are calibrated to this empirical range.

---

## 4. Dimension 1 — Affordability & Value (25 pts)

**Question: Is the current price defensible relative to what the buyer gets?**

### Metrics and weights

| Metric | Weight | Direction | Source |
|---|---|---|---|
| Price-to-Rent Ratio | 30% | Lower = better | Zillow ZHVI ÷ HUD FMR |
| Price-to-Income Ratio | 30% | Lower = better | Zillow ZHVI ÷ BEA income |
| Buy vs. Rent Breakeven | 25% | Shorter = better | Derived (see below) |
| Appreciation Quality | 15% | Closer to 5% = better | FHFA HPI 3-yr avg |

### Formula

```
dim1 = (pct_inv(pr_ratio)    × 0.30
      + pct_inv(price_income) × 0.30
      + pct_inv(breakeven_yrs)× 0.25
      + pct_inv(appr_deviation)×0.15) / 100 × 25
```

### Metric definitions

**Price-to-Rent Ratio (P/R)**
```
pr_ratio = median_home_value / (fmr_2br × 12)
```
The number of years of rent it would take to equal the purchase price. National historical norm: 15–18x. Below 15x = strong buy case relative to renting. Above 22x = renting is increasingly competitive. This metric uses HUD Fair Market Rents (FMR) for the 2-bedroom unit as the rent baseline — federal data, published annually, covers every county.

**Price-to-Income Ratio (P/I)**
```
price_income = median_home_value / per_capita_income
```
How many years of per-capita income equals the home price. Historical US norm: 4.2x. Above 6x is generally considered stretched; above 8x is crisis territory. Uses BEA per capita personal income (CAINC1), which includes wages, proprietor income, investment income, and transfer payments — a more complete measure than median household income.

**Buy vs. Rent Breakeven**
```
r = 0.07 / 12  # monthly rate, 7% 30yr fixed (2024 national average)
mortgage_factor = r / (1 − (1 + r)^−360)

monthly_piti = (home_value × 0.80 × mortgage_factor)  # 80% LTV mortgage
             + (home_value × 0.012 / 12)               # 1.2% property tax
             + (home_value × 0.005 / 12)               # 0.5% homeowner's insurance

monthly_excess = max(monthly_piti − fmr_2br, 1)       # extra cost of owning vs. renting
breakeven_yrs  = (home_value × 0.20) / (monthly_excess × 12)  # capped at 30 years
```

The breakeven horizon is the number of years it takes for ownership to become financially superior to renting, assuming: 20% down payment, 7% 30yr fixed mortgage rate, 1.2% annual property tax rate, 0.5% homeowner's insurance, and that appreciation makes up the cost difference. A shorter breakeven means buying wins sooner — under 4 years is generally considered a strong buy signal; over 8 years suggests renting is a better financial decision.

The 7% rate is fixed at the 2024 national average. This creates a consistent comparison across all counties (rather than adjusting for local rate variation, which is minimal) and can be updated when the model is re-run with new data.

**Appreciation Quality**
```
appr_deviation = |hpi_3yr_avg − 5.0|   # deviation from the healthy midpoint
```
This metric does not reward the highest appreciation — it rewards *healthy* appreciation. The model defines healthy as 3–7% annual real appreciation. The midpoint of this range (5%) is used as the target.

Why penalize high appreciation? Because extreme appreciation (>7%/yr sustained) typically signals a market approaching an affordability ceiling, which constrains future demand. Counties appreciating at 12%/yr look great until they stop, and the correction is usually sharp. Appreciation of 3–7% is empirically associated with sustainable, fundamentals-driven markets.

The raw metric is clipped to –5% to +25% before computing deviation, to prevent extreme outliers from distorting the percentile ranking.

---

## 5. Dimension 2 — Economic Vitality (22 pts)

**Question: Is the local economy growing in real terms?**

### Metrics and weights

| Metric | Weight | Direction | Source |
|---|---|---|---|
| Wage Level | 35% | Higher = better | BLS QCEW avg annual wage |
| Sector Quality Score | 25% | Higher = better | BLS QCEW NAICS quality weighting |
| Economic Diversity (HHI) | 25% | Lower HHI = better | BLS QCEW NAICS Herfindahl Index |
| Income Growth | 15% | Higher = better | BEA CAINC1 4-yr growth |

### Formula

```
dim2 = (pct(avg_annual_wage)    × 0.35
      + pct(sector_quality)     × 0.25
      + pct_inv(hhi)            × 0.25
      + pct(income_4yr_growth)  × 0.15) / 100 × 22
```

### Metric definitions

**Wage Level**
The average annual wage paid to private-sector workers in the county (BLS QCEW own_code=5, industry_code='10' = total private). Higher wages indicate stronger labor market fundamentals and support both current affordability (workers can afford homes) and future price appreciation (rising purchasing power).

**Sector Quality Score**
```
sector_quality = Σ(employment_share_in_sector × sector_weight)
               across all 2-digit NAICS sectors
```

Not all jobs are equal. A county dominated by professional services and finance has a fundamentally different economic trajectory than one dominated by retail and legacy manufacturing. Sector quality weights are applied to the share of private employment in each sector:

| NAICS Code | Sector | Weight | Rationale |
|---|---|---|---|
| 54 | Professional, Scientific & Technical Services | 1.30 | High-wage, recession-resilient, supports high home values |
| 52 | Finance & Insurance | 1.30 | High-wage, income-stable, drives urban core premiums |
| 62 | Healthcare & Social Assistance | 1.00 | Recession-proof demand, stable employment |
| 61 | Educational Services | 1.00 | Stable, publicly funded, anchors community |
| All others | Other private sectors | 1.00 | Neutral — no premium or penalty |
| 23 | Construction | 0.80 | Leading indicator but highly cyclical |
| 44-45 | Retail Trade | 0.60 | Secular decline risk from e-commerce |
| 31-33 | Manufacturing (legacy) | 0.60 | Long-term employment contraction trend |

A county with 30% of employment in Professional Services and Finance scores meaningfully higher on this metric than one with 30% in retail and manufacturing, even if total employment is identical.

**Economic Diversity (Herfindahl-Hirschman Index)**
```
HHI = Σ(employment_share_in_sector²) × 10,000
     across all 2-digit NAICS sectors
```

The HHI is a standard measure of market concentration, applied here to employment rather than market share. It ranges from near 0 (perfectly diversified) to 10,000 (one sector employs everyone).

A highly diversified economy (HHI < 1,500) is resilient to sector-specific downturns. A concentrated economy (HHI > 3,000) — like a county with one major employer or one dominant industry — is vulnerable: when that sector contracts, the entire housing market suffers. Detroit (auto), coal county Appalachia, and single-university towns are all examples of high-HHI markets.

Lower HHI = better, so `pct_inv()` is applied.

**Income Growth**
```
income_4yr_growth = (per_capita_income_latest / per_capita_income_4yr_ago − 1) × 100
```
Four-year growth in BEA per capita personal income. This measures real improvement in the local economy, not just the current level. A county with high wages but flat income growth is stagnating; a county with average wages but 15% income growth over 4 years is improving. Both matter, which is why wage level and income growth are scored separately.

---

## 6. Dimension 3 — Housing Market Dynamics (20 pts)

**Question: What is the housing market actually doing?**

### Metrics and weights

| Metric | Weight | Direction | Source |
|---|---|---|---|
| 3-Year Appreciation Trend | 35% | Higher = better | FHFA HPI avg of last 3 years |
| Current Momentum | 15% | Higher = better | FHFA HPI latest annual change |
| Supply Tightness | 30% | Lower inventory = better | Zillow active listings (latest month) |
| Permit Pipeline | 20% | Higher = better | Census BPS 2022 annual permits |

### Formula

```
dim3 = (pct(hpi_3yr_avg)    × 0.35
      + pct(hpi_latest)     × 0.15
      + pct_inv(inventory)  × 0.30
      + pct(total_permits)  × 0.20) / 100 × 20
```

### Metric definitions

**3-Year Appreciation Trend (FHFA)**
Average annual HPI change over the three most recent available years in the FHFA county-level HPI file. This is the primary momentum signal. Three years of data is long enough to filter out single-year spikes or crashes and short enough to reflect the current market regime.

FHFA HPI is a repeat-sales index — it measures price change for the same properties over time, which eliminates compositional bias (the mix of homes sold changing). It covers ~2,800 of 3,143 counties; the rest receive median imputation.

**Current Momentum (FHFA)**
The most recent single year's annual HPI change. Used as a cross-validation signal: if 3yr trend is strong and current momentum is accelerating, the trend is intact. If current momentum is weakening while the 3yr trend looks good, the market may be topping.

These two metrics are scored independently so the model doesn't double-count a high 3yr trend that is simply being pulled up by a recent spike.

**Supply Tightness (Zillow)**
Active for-sale listings in the county (latest month available). Lower inventory means a seller's market — more buyers competing for fewer homes, which supports price appreciation. High inventory means softening demand or oversupply.

This is the only metric where lower is better for buyers in the long run (tighter supply supports the value of what they're buying). `pct_inv()` is applied: the county with the fewest listings per capita scores highest.

Note: inventory is used in absolute terms, not per-capita, to match how buyers actually experience market tightness. A major metro will always have more total listings than a rural county, but that's reflected in the national percentile rank.

**Permit Pipeline (Census BPS)**
Total new housing units permitted in 2022 (all unit sizes: 1-unit, 2-unit, 3-4 unit, 5+). Building permits are a forward-looking supply signal — they predict future inventory. A county issuing large numbers of permits is responding to demand; the question is whether supply growth will outpace or lag demand growth.

Higher permits score higher in this dimension (more supply activity = stronger market response). This is intentional: permit activity signals that the market is healthy enough to attract builders, which is a positive demand signal even though it adds supply.

---

## 7. Dimension 4 — Quality of Place (15 pts)

**Question: Is this actually a good place to live?**

### Metrics and weights

| Metric | Weight | Direction | Source |
|---|---|---|---|
| Crime Rate | 35% | Lower = better | FBI NIBRS 2024 |
| Urban Access | 40% | Lower RUCC = better | USDA RUCC 2023 |
| Amenity Density | 25% | Higher = better | Census CBP 2022 |

### Formula

```
dim4 = (pct_inv(violent_per100k) × 0.35
      + pct_inv(rucc)            × 0.40
      + pct(est_per_1k)          × 0.25) / 100 × 15
```

### Metric definitions

**Crime Rate — FBI NIBRS 2024**
```
violent_per100k = violent_offenses / max(population, 100) × 100,000
```

Violent offenses per 100,000 residents. "Violent offense" is defined using the FBI's NIBRS Group A offense codes:

| Code | Offense |
|---|---|
| 09A | Murder / Non-negligent Manslaughter |
| 09B | Negligent Manslaughter |
| 100 | Kidnapping / Abduction |
| 11A | Rape (except Statutory Rape) |
| 11B | Sodomy |
| 11C | Sexual Assault With An Object |
| 11D | Fondling |
| 120 | Robbery |
| 13A | Aggravated Assault |
| 13B | Simple Assault |
| 13C | Intimidation |

This data is parsed directly from the 5.8 GB FBI NIBRS 2024 National Master File — a fixed-width text file containing every incident reported by every NIBRS-participating law enforcement agency in the US. The format was decoded empirically:
- **BH (Agency Header) records**: state abbreviation at chars 4–6 (embedded in ORI), county 3-digit FIPS at chars 269–272
- **02 (Offense) records**: NIBRS offense code at chars 33–36

Coverage: 21,068 agencies across 49 states and 2,869 counties.

**Imputation for non-reporting counties:** Many rural law enforcement agencies do not participate in NIBRS. A county with zero reported offenses might be genuinely safe, or might simply not report. To avoid penalizing non-reporters, counties with no NIBRS data receive their RUCC-tier median violent crime rate:

| RUCC tier | Counties included | Imputation source |
|---|---|---|
| Metro (RUCC 1–3) | Large to medium metro | Median of reporting metro counties |
| Micro (RUCC 4–6) | Small metro / micropolitan | Median of reporting micro counties |
| Rural (RUCC 7–9) | Small town to remote rural | Median of reporting rural counties |

Any remaining nulls after tier imputation receive the overall national median.

**Urban Access — USDA RUCC 2023**
The USDA Rural-Urban Continuum Code (RUCC) classifies every US county on a 1–9 scale:

| Code | Description |
|---|---|
| 1 | Metro: county in a metro area of ≥1 million population |
| 2 | Metro: county in a metro area of 250k–1 million |
| 3 | Metro: county in a metro area of < 250k |
| 4 | Non-metro: urban population ≥20k, adjacent to metro area |
| 5 | Non-metro: urban population ≥20k, not adjacent |
| 6 | Non-metro: urban population 2,500–19,999, adjacent to metro |
| 7 | Non-metro: urban population 2,500–19,999, not adjacent |
| 8 | Non-metro: completely rural, adjacent to metro area |
| 9 | Non-metro: completely rural, not adjacent to metro area |

RUCC is the dominant metric in Dim4 (40% weight) because urban proximity captures a cluster of quality-of-life factors that no other dataset measures at county level: access to major hospitals, airport proximity, cultural amenities, specialized retail, and the density of service infrastructure. It is the best available proxy for "how easy is daily life here" using federal data.

Lower RUCC = more urban = higher score. `pct_inv()` applied.

**Amenity Density — Census CBP 2022**
```
est_per_1k = total_establishments / max(population, 100) × 1,000
```

Private business establishments per 1,000 residents from the Census County Business Patterns (CBP). This is a direct count of the retail stores, restaurants, healthcare practices, gyms, professional services, and other establishments that constitute daily quality of life infrastructure.

Establishments per capita rather than raw count is used to prevent large metros from automatically dominating (they have more establishments but also more people to serve).

---

## 8. Dimension 5 — Physical Risk (12 pts)

**Question: What are the climate and natural hazard costs?**

Lower risk = higher score. All three metrics use `pct_inv()`.

### Metrics and weights

| Metric | Weight | Direction | Source |
|---|---|---|---|
| Flood Loss per Capita | 40% | Lower = better | FEMA NFIP (10-year window) |
| Storm Damage per Capita | 35% | Lower = better | NOAA Storm Events (5-year window) |
| Wildfire Exposure | 25% | Lower rank = better | USFS Wildfire Risk to Communities |

### Formula

```
nfip_per_cap  = nfip_claims  / max(population, 100)
storm_per_cap = storm_damage / max(population, 100)

dim5 = (pct_inv(nfip_per_cap)   × 0.40
      + pct_inv(storm_per_cap)  × 0.35
      + pct_inv(wildfire_rank)  × 0.25) / 100 × 12
```

### Metric definitions

**Flood Loss per Capita — FEMA NFIP**
Total FEMA National Flood Insurance Program paid claims (building + contents) from 2014–2023 (10-year window), divided by 2023 population. This measures *realized* flood loss, not theoretical flood zone risk. A county in a FEMA AE flood zone that has never filed a claim scores well; a county with chronic flooding and repeated payouts scores poorly, regardless of its official flood zone designation.

The 10-year window smooths year-to-year variation from single major events while capturing recent climate trends. Only paid claims are counted (not just filed claims), which represents actual economic damage.

**Storm Damage per Capita — NOAA Storm Events**
Total property damage from all NOAA-classified severe weather events (2019–2023, 5-year window), divided by 2023 population. NOAA Storm Events covers all federally-tracked weather: hurricanes, tornadoes, hail, severe thunderstorms, winter storms, flooding, and more.

Damage values in the raw data are encoded as strings ("5.00K", "1.50M") — the engine parses these to dollar amounts. Only "C" (county zone) events are included, not forecast zone events, to ensure precise county attribution.

The 5-year window (shorter than NFIP's 10 years) is used because storm patterns are more volatile and recent events are more predictive of near-term risk.

**Wildfire Exposure — USFS Wildfire Risk to Communities**
The USFS publishes a county-level wildfire risk score (`RISK_NATIONAL_RANK`) representing each county's wildfire risk percentile nationally (0 = safest, 1 = highest risk). This is based on the potential for wildfire to damage residential structures, accounting for fire probability, fire intensity, housing density, and vegetation.

This is the most forward-looking of the three risk metrics — it reflects structural exposure to future wildfire, not just historical claims. For states like California, Oregon, Colorado, and Texas, this is increasingly the dominant risk factor as insurance markets contract.

### Why these three hazards?

These are the three hazard types causing the most widespread financial harm to US homeowners right now:

1. **Flooding** — ~40% of FEMA disaster declarations; expanding beyond traditional flood zones due to changing rainfall patterns
2. **Severe storms** — tornadoes, hail, and convective weather cause billions annually; shifting geographically northward
3. **Wildfire** — expanding "wildland-urban interface" exposure; insurance non-renewal already affecting property values in CA, CO, OR

Earthquake and hurricane risks exist but are geographically concentrated; the three hazards above affect every region of the country.

---

## 9. Dimension 6 — Population Momentum (6 pts)

**Question: Are the right people moving in?**

### Metrics and weights

| Metric | Weight | Direction | Source |
|---|---|---|---|
| Net Migration Rate | 60% | Higher = better | Census Population Estimates 2023 |
| In-Mover Income Quality | 40% | Higher ratio = better | IRS SOI Migration 2022–23 |

### Formula

```
dim6 = (pct(RNETMIG2023)          × 0.60
      + pct(inmover_income_ratio) × 0.40) / 100 × 6
```

### Metric definitions

**Net Migration Rate**
```
RNETMIG2023 = (international_in + domestic_in − domestic_out) / population × 1,000
```

Net migration rate per 1,000 residents from Census Population Estimates 2023. This is not just domestic migration — it includes international in-migration. A positive net migration rate means the county is gaining residents; negative means it is losing them.

Net migration is the strongest leading indicator of future housing demand. People move toward opportunity; money follows people; housing demand follows money.

**In-Mover Income Quality**
```
inmover_income_ratio = in_mover_avg_AGI / out_mover_avg_AGI
```

The ratio of the average adjusted gross income (AGI) of households moving *into* the county to the average AGI of households moving *out* of the county. Source: IRS Statistics of Income Migration Data (2022–23 tax year).

- Ratio > 1.0: higher-income people are moving in than are leaving. This is a demand quality signal — wealthier in-movers support higher home prices and local spending.
- Ratio = 1.0: the income profile of arrivals matches departures.
- Ratio < 1.0: lower-income people are moving in, higher-income people are leaving. This is a warning sign — it often precedes economic softening and price stagnation.

This metric is unique to Civica. No other consumer real estate platform publishes who is moving in, only how many.

IRS migration data excludes filers with AGI > $200,000 in destination states where disclosure would identify individuals, and also excludes international movers. Special codes (96, 97, 98, 99) representing state totals, foreign origin, and non-migrants are filtered out.

---

## 10. Total Score & Market Labels

### Total score

```
total_score = dim1 + dim2 + dim3 + dim4 + dim5 + dim6
            (clipped to range 0–100)
```

Scores are not rounded before label assignment — the full floating-point value is used.

### Empirical score distribution (current run)

| Statistic | Value |
|---|---|
| Counties scored | 2,820 |
| Mean | 50.0 |
| Standard deviation | 6.24 |
| Minimum | 26.85 |
| Maximum | 69.48 |

The mean of exactly 50.0 is expected: because every metric is percentile-normalized, and every county receives the same imputation procedure for missing data, the system is mathematically balanced around the midpoint.

### Market labels

| Label | Threshold | Count | Meaning |
|---|---|---|---|
| ACCELERATING | ≥ 68 | 2 | All signals aligned; prices still fundamentally defensible |
| PEAKING | ≥ 62 | 57 | Strong momentum approaching affordability ceiling |
| ESTABLISHED | ≥ 55 | 563 | Healthy balanced market; sustainable fundamentals |
| EMERGING | ≥ 46 | 1,463 | Improving fundamentals; early-mover opportunity |
| FRONTIER | ≥ 38 | 634 | Below-average market; higher uncertainty |
| TURNING | ≥ 30 | 97 | Softening demand; watch for continued weakness |
| SPECULATIVE | ≥ 26 | 4 | Poor fundamentals; momentum-only pricing risk |
| AVOID | < 26 | 0 | Systemic weakness across multiple dimensions |

**Why AVOID has 0 counties:** The empirical score floor with FBI NIBRS crime data integrated is 26.85 — just above the AVOID threshold of 26. The 4 SPECULATIVE counties (scores 26.85–29.x) are the genuinely worst-performing markets. AVOID becomes active if the score floor drops below 26 in a future run (e.g., if a county's crime rate or physical risk worsens significantly relative to peers).

**Why these thresholds?** The percentile normalization produces a score distribution with mean ~50 and std ~6. The original spec used thresholds of 78/68/58/48/38/28/18/0 — designed for a 0–100 distribution that never materializes in practice. The current thresholds are calibrated to the empirical range:

- ACCELERATING starts at 68 ≈ mean + 2.9 std (genuinely exceptional)
- PEAKING starts at 62 ≈ mean + 1.9 std (strong upper tail)
- ESTABLISHED starts at 55 ≈ mean + 0.8 std (above average)
- EMERGING starts at 46 ≈ mean − 0.6 std (slightly below average, but improving)
- FRONTIER starts at 38 ≈ mean − 1.9 std (clearly below average)
- TURNING starts at 30 ≈ mean − 3.2 std (lower tail)
- SPECULATIVE starts at 26 ≈ mean − 3.8 std (near the floor)

### Verdict mapping (county report pages)

| Score range | Verdict | Display |
|---|---|---|
| ≥ 58 | BUY | Green badge |
| 38–57 | HOLD | Yellow badge |
| < 38 | AVOID | Red badge |

---

## 11. The 8 Derived Metrics

These metrics are computed from raw federal data and are unique to Civica — they don't appear in any federal dataset directly, and no consumer real estate platform publishes them.

### 1. Price-to-Rent Ratio
```
pr_ratio = median_home_value / (fmr_2br × 12)
```
National norm: 15–18x. Below 15x: buy strongly favored. Above 22x: renting is increasingly competitive.

### 2. Price-to-Income Ratio
```
price_income = median_home_value / per_capita_income
```
Historical US norm: 4.2x. Above 6x: stretched. Above 8x: crisis territory.

### 3. Buy vs. Rent Breakeven Horizon
```
breakeven_yrs = (home_value × 0.20) / ((monthly_piti − fmr_2br) × 12)
```
Assumptions: 20% down, 7% 30yr fixed, 1.2% property tax, 0.5% insurance. Capped at 30 years. Under 4 years = strong buy; 4–8 years = neutral; over 8 years = rent.

### 4. Appreciation Quality Score
```
appr_deviation = |hpi_3yr_avg − 5.0|
```
Deviation from the 5% healthy midpoint. Lower deviation = healthier appreciation profile.

### 5. Sector Quality Score
```
sector_quality = Σ(employment_share_in_sector × NAICS_weight)
```
1.30 for Professional/Finance; 1.00 for Healthcare/Education/Other; 0.80 for Construction; 0.60 for Retail/Manufacturing. Score > 1.0 = premium mix; < 1.0 = below-average mix.

### 6. Employment Concentration (HHI)
```
HHI = Σ(employment_share_in_sector²) × 10,000
```
< 1,500 = well-diversified. 1,500–2,500 = moderate concentration. > 2,500 = high risk from sector-specific downturns. > 5,000 = dangerously concentrated (company towns).

### 7. In-Mover Income Quality Ratio
```
inmover_income_ratio = in_mover_avg_AGI / out_mover_avg_AGI
```
> 1.0 = higher-income arrivals than departures. National median ≈ 1.03. Ratios above 1.15 indicate unusually strong demand quality.

### 8. Violent Crime Rate
```
violent_per100k = violent_offenses / population × 100,000
```
FBI-defined violent crime (murder, rape, robbery, assault, kidnapping). Imputed from RUCC-tier median for non-NIBRS counties.

---

## 12. Data Sources — All 14 Datasets

| # | Dataset | File | Vintage | Used For |
|---|---|---|---|---|
| 1 | Census Population Estimates | co-est2023-alldata.csv | 2023 | Base county universe, population denominators, migration rates |
| 2 | BEA Local Area Income (CAINC1) | CAINC1__ALL_AREAS_1969_2024.csv | 2024 | Per capita income, 4-yr income growth |
| 3 | Zillow ZHVI | County_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv | Latest month | Median home value |
| 4 | Zillow Inventory | County_invt_fs_uc_sfrcondo_sm_month.csv | Latest month | Active for-sale listings |
| 5 | HUD Fair Market Rents | FY26_FMRs_revised.xlsx | FY2026 | 2BR rent baseline for P/R ratio and breakeven |
| 6 | FHFA HPI County | hpi_at_county.xlsx | Latest available | 3yr appreciation trend, current momentum |
| 7 | BLS QCEW | 2023.annual.singlefile.csv | 2023 | Wages, sector mix, HHI diversification |
| 8 | Census CBP | cbp22co.txt | 2022 | Establishment count for amenity density |
| 9 | Census BPS | co2022a.txt | 2022 | Building permits for supply pipeline |
| 10 | IRS SOI Migration | countyinflow2223.csv, countyoutflow2223.csv | 2022–23 | In-mover income quality ratio |
| 11 | FEMA NFIP Claims | fema_nfip_claims.csv | 2014–2023 | Flood loss per capita |
| 12 | NOAA Storm Events | 5 CSV files | 2019–2023 | Storm damage per capita |
| 13 | USFS Wildfire Risk | wrc_download_20260415.xlsx | 2026 | Wildfire national risk rank |
| 14 | FBI NIBRS | 2024_NIBRS_NATIONAL_MASTER_FILE.txt | 2024 | Violent crime rate per 100k |

**Not used (and why):**

| Dataset | Reason not used |
|---|---|
| USDA RUCC 2023 | *(Is used — Dim4 Urban Access metric)* |
| EIA Form 861 (electricity) | Maps to utility service territories, not county FIPS; spatial join required |
| EIA Natural Gas prices | State-level only; no county decomposition available |
| Census STC (state/local finances) | State-level only; no county FIPS in the file |
| NOAA Climate Normals | Weather station points; spatial aggregation to county level not implemented |
| FEMA NRI | Was not downloadable; reconstructed from its component datasets (NFIP, NOAA, USFS) |

---

## 13. Coverage, Filters & Missing Data

### Population filter

```python
df = df[df['POPESTIMATE2023'] >= 5_000]
```

Counties with fewer than 5,000 residents are excluded from scoring. Reason: these counties have insufficient data across multiple dimensions:
- Zillow ZHVI coverage is effectively zero below ~5,000 population
- BLS QCEW suppresses employment figures for small counties to protect business confidentiality
- FHFA HPI requires enough home sales to build a repeat-sales index — impossible in thin markets
- Any score produced would be nearly 100% median imputation, conveying no real information

**324 counties are excluded.** The largest excluded county is Oneida County, ID (pop. 4,953). The smallest is Loving County, TX (pop. 43).

The score output covers **2,820 of 3,144 US counties** — 89.7% of the county universe, representing over 99% of the US population.

### Missing data imputation

After the population filter, remaining missing values are filled with the **national median** for each numeric column:

```python
num_cols = df.select_dtypes(include=[np.number]).columns
medians  = df[num_cols].median()
df[num_cols] = df[num_cols].fillna(medians)
```

This is the most conservative imputation choice available. It assigns a county with missing data the exact middle score on that metric — neither rewarding nor penalizing it for the data gap. The practical effect is that heavily imputed counties gravitate toward the mean score (~50) rather than the extremes.

Specific imputation cases:

| Dataset gap | Counties affected | Method |
|---|---|---|
| FHFA HPI (no HPI history) | ~340 rural counties | National median appreciation |
| Zillow ZHVI (no home value data) | Some rural counties | National median home value |
| FEMA NFIP (no claims on file) | Counties with no flood insurance policies | 0 (no claims = no flood loss) |
| FBI NIBRS (no participating agency) | ~251 counties | RUCC-tier median violent crime rate |
| BPS (no permits filed) | Some counties | 0 (no permits = no new supply) |

The FBI NIBRS imputation is an exception to the national-median rule — RUCC-tier median is used instead because non-reporting is strongly correlated with rurality, and rural counties genuinely have lower violent crime rates than the national median.

### Dataset linkage

All datasets are joined using the 5-digit FIPS code (zero-padded state + county code). Census population serves as the base table; all other datasets are left-joined onto it. This means:
- Every county in the Census file appears in the output (subject to the pop filter)
- Counties not covered by a particular dataset receive NaN for that dataset's columns, then median imputation
- No county is excluded due to missing data in a single dataset

---

## 14. Design Decisions & Tradeoffs

### Why percentile normalization instead of absolute thresholds?

The alternative is to define absolute cutoffs: "P/R ratio below 15x scores full points, above 25x scores zero." This fails because:
1. The "correct" threshold changes over time (as national prices move, the norm shifts)
2. Absolute thresholds create cliffs — tiny changes near the threshold cause large score jumps
3. The model can't be compared across different vintages without re-calibrating every threshold

Percentile normalization self-calibrates: the threshold is always "how does this county compare to all other US counties right now." The score always means "what percentile nationally" regardless of what year the model is run.

### Why not use ACS (American Community Survey) data?

The American Community Survey is the most widely cited source for county-level demographics. Civica deliberately excludes it for three reasons:
1. ACS estimates for small counties have very wide margins of error (sometimes ±30% for a 5-year estimate in a county of 10,000)
2. ACS is a sample survey, not a census — at county level, the uncertainty is too large for scoring use
3. ACS data is already partially incorporated into BEA and BLS products (which use it as a denominator), so excluding it doesn't mean ignoring its signal

### Why use 2BR Fair Market Rents as the rent baseline?

HUD FMR is a conservative rent baseline — it represents the 40th percentile of gross rents in a market. This means the breakeven calculation uses a rent that 60% of renters pay more than. The breakeven horizon is therefore conservative (it will take longer to break even against a lower rent baseline), making the BUY verdict harder to achieve and more credible when it is.

Alternative: median market rent from a private source (Zillow, Apartment List). Rejected because these sources have coverage gaps, are not standardized across counties, and introduce private data into an otherwise pure federal-data model.

### Why doesn't the model use school quality data?

School quality (NCES EDFacts or F-33 data) is on the roadmap but not in the current model for a practical reason: the data requires significant cleaning and grade-level aggregation to produce a meaningful county-level score, and the downloaded files were not included in the initial data pipeline. When added, school quality would most likely replace part of the Amenity Density metric in Dim4 or add a 4th metric to that dimension.

### Why are permits scored as higher = better?

Building permits are a supply signal, and more supply typically means more competition for existing homes (bad for price appreciation). The decision to score permits as higher = better reflects the view that permit activity is primarily a demand indicator: builders only build when they expect buyers. High permit activity means the market is strong enough to attract capital investment, which is a positive signal. The supply effect is already captured elsewhere — in the inventory tightness metric.

---

## 15. Known Limitations

| Limitation | Impact | Current handling |
|---|---|---|
| FHFA covers only ~2,800 of 3,143 counties | ~340 rural counties receive median HPI imputation | Documented; score reliability lower for these counties |
| BLS QCEW has 18-month publication lag | Economic vitality scores reflect 2023 employment | Accepted; no alternative real-time county-level source |
| Census CBP has 18-month publication lag | Amenity density reflects 2022 establishment counts | Same; CBP is the only federal county-level establishment dataset |
| Census BPS also 2022 vintage | Permit pipeline is 2 years behind | Accepted; directionally correct for identifying supply-active markets |
| NIBRS participation is voluntary | ~251 counties lack crime data; rural coverage is lower | RUCC-tier median imputation; non-reporters are not penalized |
| Zillow ZHVI is not federal data | One non-federal source in an otherwise federal model | Only alternative would be FHFA HPI for price level — but FHFA is an index (change), not a price level |
| Small county distortion | In counties with 5,000–15,000 pop, one employer can swing wages and HHI significantly | Pop ≥ 5,000 filter catches worst cases; scores for 5k–15k counties should be treated with caution |
| Single-year IRS migration data | Migration patterns from 2022–23 may not reflect post-COVID normalization | Acknowledged; IRS releases annually and model can be updated |
| Breakeven assumes fixed 7% rate | A county at 5.5% rates vs. 7% rates has a different breakeven | Rate is standardized nationally for comparability; users should adjust the breakeven output for their actual rate |

---

*Civica Scoring Engine v1.2 · All data from free US federal government sources · No financial advice — for informational purposes only*
