# Civica Scoring Model — Adversarial Peer Review
*External reviewer perspective: quant analyst / Fed economist / journal peer reviewer*  
*Scope: METHODOLOGY.md, CLAUDE.md, README.md, scoring_engine.py, county_scores.csv, site HTML*  
*Date: May 2026 · Based on v1.2 codebase*

---

## Executive Summary — Top 5 Issues

1. **Label threshold stale code.** Current `scoring_engine.py` uses thresholds (61/57/51/45/37/29/24) that diverge from every documentation source. Re-running the scorer today would relabel ~1,000+ counties — ACCELERATING expands from 2 to 89 counties. The CSV and the live code are out of sync.

2. **Breakeven inversion bug.** 386 counties (13.7% of all scored) where PITI < FMR receive the *worst* possible breakeven score (30 years) instead of the best (0 years). The code clips `monthly_excess` to 1 when buying beats renting, producing a nonsensical multi-thousand-year breakeven that caps to 30. The methodology doc explicitly says these counties should score "immediately positive."

3. **Triple label system with no mapping.** Three incompatible label vocabularies exist across the product: the engine (8 labels: ACCELERATING → AVOID), the site methodology page (5 labels: STRONG BUY → AVOID), and the planned county report cards (3 labels: BUY / HOLD / AVOID). None maps to another.

4. **NaN handling is misrepresented.** METHODOLOGY.md §4 says NaN "propagates through the dimension calculation, reducing the county's total score proportionally." The code fills *all* NaN with national medians before any scoring function runs. NaN never reaches the dimension calculations. Counties with missing data do not receive reduced scores — they receive the median score for each missing metric.

5. **"14 federal datasets / built entirely on federal data" is false.** Zillow ZHVI — explicitly acknowledged as non-federal — is listed as dataset #1 and drives approximately 27% of every county's total score. README.md states "All data is free and publicly available from US federal agencies" and then includes Zillow in the table below. This is a material factual error in public-facing copy.

---

## Critical Issues

### C1. Label Thresholds: Code vs. CSV vs. Docs — Three-Way Conflict

**What:** `scoring_engine.py` `LABELS` list uses thresholds `(61,'ACCELERATING'), (57,'PEAKING'), (51,'ESTABLISHED'), (45,'EMERGING'), (37,'FRONTIER'), (29,'TURNING'), (24,'SPECULATIVE')`. METHODOLOGY.md §11 and CLAUDE.md both document thresholds `68 / 62 / 55 / 46 / 38 / 30 / 26`. The `county_scores.csv` on disk was generated with thresholds matching the docs (confirmed by actual label boundaries in the data: ACCELERATING min=68.48, ESTABLISHED min=55.01, EMERGING min=46.03, etc.). The code and the CSV are inconsistent.

**Where:** `scoring_engine.py` lines 567–576 (LABELS constant), METHODOLOGY.md §11, county_scores.csv.

**Quantitative impact:** Running the scorer with current code on the existing score distribution produces 89 ACCELERATING, 268 PEAKING, 924 ESTABLISHED, 956 EMERGING — versus the current CSV's 2, 57, 563, 1,463. County 01085 (Jefferson County AL, score 61.04) is currently labeled ESTABLISHED but would be labeled ACCELERATING under the current code. This is not a labeling nuance — it is a 44× expansion of the "top-tier" label.

**The code comments make the confusion worse:** The LABELS block says `# top ~4%: ~100 counties` for ACCELERATING, but the actual output has 2. The comment was written for a different threshold.

**Fix:** Decide on one set of thresholds. Update code to match docs (68/62/55/46/38/30/26) OR update docs to match code (61/57/51/45/37/29/24) and re-run. Re-generate county_scores.csv from the agreed code.

---

### C2. Breakeven Inversion Bug — 386 Counties Penalized for Being Affordable

**What:** When PITI < FMR (buying is immediately cheaper than renting), `monthly_excess = (monthly_piti - fmr_2br).clip(lower=1)` clips to 1. Then `breakeven_yrs = (home_value * 0.20 / (1 * 12)).clip(0, 30)` produces, for a $90k home, 1,499 years → clipped to 30. These counties receive the maximum possible breakeven (worst score on this metric). The methodology document explicitly states: "Markets where PITI < rent score immediately positive (breakeven ≤ 0 → clipped to 0)."

**Where:** `scoring_engine.py` lines 437–438, METHODOLOGY.md §5.

**Quantitative impact:** 386 of 2,820 scored counties (13.7%) are affected. Cross-referenced: all 386 have `breakeven_yrs = 30.0` in the CSV and computed `PITI < FMR`. Example — Escambia County AL (FIPS 01047): home value $89,933, FMR $836, PITI ≈ $603. Buying saves $233/month from day 1. This county receives a breakeven score at the 0th percentile (worst possible) when it should receive a score at the 100th percentile (best possible). The `pct_inv()` function applied downstream treats this county as if it has the longest breakeven nationally.

**Systematic bias:** The 386 affected counties are disproportionately rural, low-cost markets — precisely the markets where the "buy vs. rent" case is strongest. The bug systematically depresses Dim1 scores for affordable rural markets and inflates scores for urban markets where PITI safely exceeds FMR.

**Fix:** Replace `clip(lower=1)` on `monthly_excess` with explicit handling:
```python
d['breakeven_yrs'] = np.where(
    d['monthly_piti'] <= d['fmr_2br'],
    0.0,
    (d['median_home_value'] * 0.20 / ((d['monthly_piti'] - d['fmr_2br']) * 12)).clip(0, 30)
)
```

---

### C3. Triple Label System — Engine / Site / County Cards Are Incompatible

**What:** Three label vocabularies exist with no documented mapping between them:

| Context | Labels | Source |
|---|---|---|
| Scoring engine output | ACCELERATING, PEAKING, ESTABLISHED, EMERGING, FRONTIER, TURNING, SPECULATIVE, AVOID | `scoring_engine.py` |
| Methodology page (site) | STRONG BUY, BUY, WATCH, CAUTION, AVOID | `harvard_model.html` Market Signals accordion |
| County report cards (planned) | BUY, HOLD, AVOID | `CLAUDE.md` county_generator spec |

The site methodology page describes a direction-based label system that uses two signals not computed by the scoring engine (FHFA HPI momentum vs. 3-year average deviation > 1pp, and Census net migration vs. ±1.0/1000). This system and its county count estimates (~75 STRONG BUY, ~629 BUY, ~1,199 WATCH) are fictional relative to the current codebase — no code produces these labels or applies this direction logic.

**Where:** `scoring_engine.py` lines 567–583, `harvard_model.html` lines 287–327, `CLAUDE.md` county_generator verdict logic.

**Impact:** When `county_generator.py` is built and applied to `county_scores.csv`, county report cards will show BUY/HOLD/AVOID; the methodology page shows STRONG BUY/BUY/WATCH/CAUTION/AVOID; and the underlying data column says EMERGING or ESTABLISHED. A user reading the methodology and then viewing a county report will see different label systems with no bridge.

**Fix:** Pick one label system. The engine's 8-label system has the most granularity and internal logic. Redesign the site UI to use it, or create an explicit documented mapping from 8-label → 5-label and implement it.

---

### C4. NaN Handling Misrepresented in Documentation

**What:** METHODOLOGY.md §4 states: "NaN propagates through the dimension calculation, reducing the county's total score proportionally to the weight of the missing metric." This is false. The code at `scoring_engine.py` line 648 fills all numeric NaN values with column medians before any dimension scoring function is called: `df[num_cols] = df[num_cols].fillna(medians)`. All dimension functions receive non-NaN data.

**Where:** `scoring_engine.py` lines 645–648, METHODOLOGY.md §4.

**Impact:** A county missing FHFA HPI data (which covers ~340 rural counties) does not receive a "reduced score" as the docs claim. It receives the national median for `hpi_3yr_avg` and `hpi_latest`, which scores at approximately the 50th percentile on those metrics — neither a penalty nor a reward. Counties with imputed FHFA data are not identifiably different from counties with real FHFA data in the output. The methodology's description of how missing data is handled is incorrect.

**Fix:** Update METHODOLOGY.md §4 to accurately describe the behavior: "Counties with missing raw inputs receive the national median for that metric and score at approximately the national average for the affected metrics. No dimension score is reduced to zero for data absence."

---

### C5. "Federal Data Only" Marketing Claims Are False

**What:** Multiple public-facing sources make false claims about data provenance:

- `harvard_model.html` hero pill: **"Federal Datasets: 14"** — Zillow ZHVI is dataset #1 and is not federal.
- `harvard_model.html` hero text: "Every number traces back to a government source you can verify yourself." — Zillow data cannot be verified from a government source.
- `README.md` §Data Sources header: **"All data is free and publicly available from US federal agencies."** — The table immediately below includes Zillow ZHVI.
- `index.html` OG description: "built entirely on federal government data" — false.

**Where:** `harvard_model.html` lines 178–186, `README.md` lines 27–44, `index.html` meta tags.

**Impact:** This is the model's core trust claim. Zillow ZHVI drives P/R ratio (30% of Dim1), P/I ratio (30% of Dim1), the breakeven numerator (25% of Dim1), and raw inventory (30% of Dim3). The METHODOLOGY.md itself calculates this as ~27% of every county's total score coming from a single private company's proprietary data. Claiming "federal data only" while using a source that accounts for over one-quarter of the score is not a rounding error — it is a substantively false claim.

The Terms of Service (section 1, 5) and the METHODOLOGY.md are accurate on this point. The site marketing copy is not.

**Fix:** Change "14 federal datasets" to "13 federal datasets + Zillow ZHVI." Remove "built entirely on federal government data" from the OG description and any hero text. The accurate framing is "13 federal datasets + Zillow ZHVI for county home values, the only metric without a federal equivalent."

---

### C6. `nibrs_imputed` Flag: Documented, Never Created

**What:** METHODOLOGY.md §8 states: "The imputation is clearly flagged in the `county_scores.csv` output column `nibrs_imputed`." This column does not exist. It is not created anywhere in `scoring_engine.py`. It is not in the `out_cols` list. It does not appear in the CSV.

**Where:** `scoring_engine.py` lines 665–679 (`out_cols`), METHODOLOGY.md §8, confirmed by column inspection of `county_scores.csv`.

**Impact:** Users (and `county_generator.py`) cannot distinguish counties where crime rate is observed vs. imputed from RUCC-tier median. All counties appear to have measured crime data. 

**Fix:** Add `df['nibrs_imputed'] = mask.astype(int)` in `score_dim4()` before returning, and add `'nibrs_imputed'` to `out_cols`.

---

## Significant Issues

### S1. NIBRS "Violent Crime" Includes Simple Assault and Intimidation

**What:** The NIBRS offense codes classified as "violent" in the model include `13B` (Simple Assault) and `13C` (Intimidation). FBI UCR Part 1 violent crimes are: murder/non-negligent manslaughter, rape, robbery, and aggravated assault (`13A`). Simple assault is the most commonly committed violent offense in NIBRS-participating jurisdictions and substantially outnumbers aggravated assaults in most jurisdictions. Including it makes Civica "violent crime" rates incomparable to published FBI violent crime statistics.

**Where:** `scoring_engine.py` line 364: `VIOLENT = {'09A','09B','100','11A','11B','11C','11D','120','13A','13B','13C'}`, METHODOLOGY.md §8 offense code list.

**Impact:** Simple assault and intimidation likely represent 40–60% of offenses coded in this set in most jurisdictions. A county with 500 violent offenses under Civica's definition might have only 200 under the FBI's definition. This inflates crime rates more in urban counties (where simple assault reporting is higher) relative to rural ones — systematically biasing the within-metro crime rankings. Displaying the metric as "violent crime rate" without disclosing 13B/13C inclusion is misleading.

**Fix (choose one):** Remove 13B and 13C from `VIOLENT` to match UCR Part 1 definition, OR add explicit disclosure in METHODOLOGY.md and on county pages: "Includes simple assault and intimidation, which are broader than the FBI's published violent crime rate."

---

### S2. Income Growth Is Nominal — Documented as Real

**What:** `income_4yr_growth = (per_capita_income / income_prior - 1) * 100` is 100% nominal BEA income growth, with no CPI adjustment. METHODOLOGY.md §6 describes this metric as capturing "whether real economic conditions are improving." The actual metric captures whether nominal income is growing faster than inflation — a very different thing.

**Where:** `scoring_engine.py` line 98, METHODOLOGY.md §6.

**Quantitative impact:** Over 2020–2024, cumulative CPI was approximately 21–23%. The CSV shows mean nominal 4-year income growth of 22.0% with σ = 7.2%. This means the national median county barely kept pace with inflation in real terms. A county with 17% nominal growth (25th percentile in the data) has negative real income growth of ~4% over 4 years — the model rewards it as below-average on a "real economic conditions" metric, when the correct characterization is "falling real incomes." The metric's discriminating power is in the tails; the framing as a "real" measure is wrong for the entire middle of the distribution.

**Fix:** Either CPI-adjust (divide by the 4-year CPI ratio for the matching period) or relabel in all documentation as "nominal per-capita income growth."

---

### S3. Inventory-Population Correlation = 0.83 — Metric Measures County Size, Not Tightness

**What:** Zillow active inventory (raw listing count) correlates with county population at r = 0.83. This means the Supply Tightness metric in Dim3 (30% weight, 6% of total score) is predominantly measuring county size, not market tightness. Los Angeles County with 15,000 listings and 6,000 monthly sales (seller's market) scores far worse than a small county with 15 listings and 5 monthly sales (buyer's market) — opposite of their actual tightness.

**Where:** `scoring_engine.py` line 473, METHODOLOGY.md §7.

**Impact:** The signal direction is plausibly correct in many cases (small tight markets do have fewer listings), but the magnitude is dominated by size not tightness. This is documented as a known limitation but the r=0.83 correlation confirms it is not a minor limitation — it is close to measuring the wrong thing entirely. At 30% of Dim3, this imposes a structural penalty on large metros regardless of actual supply conditions.

**Fix/document:** At minimum, document the correlation coefficient. Ideally, normalize by some size proxy (population, total housing units) to create a per-capita inventory measure, even if imperfect.

---

### S4. Urban Access (RUCC) Encodes Location Preference as Objective Quality

**What:** USDA RUCC 1–9 is coded as "higher urban access = higher quality of place" at 40% weight in Dim4 (6% of total score). This means every rural county receives a structural Dim4 penalty — not because the place is objectively worse to live in, but because the model defines urban access as a quality dimension. The stated rationale — "urban access is the single strongest predictor of long-term real estate liquidity and buyer pool depth" — is a real estate liquidity claim, not a quality-of-place claim.

**Where:** `scoring_engine.py` line 517, METHODOLOGY.md §8.

**Impact:** The 40% weight on RUCC is the single largest intra-dimension weight in the model. At 40% × 15% = 6% of total score, it systematically disadvantages all 1,500+ non-metro counties (RUCC 4–9). If this is intended as a liquidity signal, it should be disclosed as such, not embedded in a "Quality of Place" dimension. If it is intended as a quality signal, the rationale "liquidity" does not support it — and a buyer specifically seeking rural quality of life is being told their preference scores at the bottom of the quality distribution.

**Fix:** Rename Dim4 or rename the metric. "Liquidity Access" is more accurate than "Urban Access" in the context of how it's rationalized. Or reduce the weight to 20% (equal to amenity density) and explain that urban access is one signal among equals, not the dominant factor.

---

### S5. Wage Level Without Cost-of-Living Adjustment Creates Coastal Bias

**What:** Dim2 uses raw average annual wage (BLS QCEW) at 35% weight with "higher = better." High-wage counties are disproportionately coastal metros where those wages are consumed by high housing costs already captured in Dim1's affordability penalty. A nurse in San Francisco earning $130k in a county with a $1.5M median home value scores better on Dim2 than a nurse in Columbus OH earning $85k in a county with a $350k median home value — despite the latter having meaningfully higher purchasing power.

**Where:** `scoring_engine.py` line 457, METHODOLOGY.md §6.

**Impact:** This creates a bidirectional signal where expensive coastal markets are penalized in Dim1 AND rewarded in Dim2, partially canceling each other. The net effect is opaque to users. The correct Dim2 metric is real purchasing power (wage / local cost index), not nominal wage. This isn't wrong in isolation, but the interaction between Dim1 and Dim2 is not disclosed.

**Fix/document:** Add a note to METHODOLOGY.md §6 and §14: "Wage level is nominal and does not adjust for local cost of living. High-wage coastal markets receive both affordability penalties in Dim1 and wage-level rewards in Dim2. The net effect is that nominal wages partially offset affordability penalties for expensive markets."

---

### S6. FHFA HPI Data Drives Two Dimensions (Correlated Inputs)

**What:** `hpi_3yr_avg` from FHFA is used directly as the Appreciation Trend metric in Dim3 (35% × 20% = 7% of total score). The same value, transformed as `|hpi_3yr_avg - 5.0|`, is used as the Appreciation Quality metric in Dim1 (15% × 25% = 3.75% of total score). One data series from one source determines 10.75% of every county's total score. METHODOLOGY.md §7 acknowledges the "tension" between the two but does not flag the shared input.

**Where:** `scoring_engine.py` lines 441, 471, METHODOLOGY.md §14.2.

**Impact:** This is the most concrete instance of multicollinearity in the model. A county with exactly 5% HPI appreciation maximizes both its Dim1 appreciation quality score (deviation = 0, pct_inv = 100th percentile) AND earns a Dim3 trend score at the 50th percentile or better if 5% is near the median. A county with 12% appreciation earns a near-maximum Dim3 trend score and a lower Dim1 quality score. The net effect has a 7:3.75 weighting toward momentum (Dim3) over stability (Dim1), meaning the model systematically prefers faster-appreciating markets even if they are stretched on affordability. This is documented in §14.2 as intentional but should be presented to users as a feature, not buried.

---

## Moderate Issues

### M1. Sector Quality Weights — Undocumented and Unvalidated

**What:** NAICS quality multipliers (1.30 for Professional/Finance, 0.60 for Manufacturing/Retail) are described as "Civica editorial judgments" in the methodology. They have no cited source and have not been validated against any county-level outcome variable (e.g., does higher sector quality score predict price appreciation, lower unemployment, or population growth?).

**Where:** `scoring_engine.py` lines 204–215, METHODOLOGY.md §14.6.

**Assessment:** This is defensible as a prior but should be clearly labeled as such on county pages where sector quality is displayed, not just buried in §14.6. A manufacturing county scoring 0.60 will receive a Dim2 penalty that the county cannot investigate because no source is cited. More fundamentally: Finance at 1.30 reflects historical US national patterns; it may not hold at the county level (rural banking counties may have high finance employment shares from credit cooperatives with below-median wages).

**Triage:** Document. Not a bug, but not validated.

---

### M2. `scoring_engine.py` Version Is v1.0, All Docs Say v1.2

**What:** `scoring_engine.py` header docstring: "Civica Scoring Engine v1.0". `main()` prints: "Civica Harvard Scoring Engine v1.0". Every other document in the repo (METHODOLOGY.md, CLAUDE.md, county_scores.csv documentation) references v1.2.

**Where:** `scoring_engine.py` lines 2, 589.

**Triage:** Fix. Two-line change.

---

### M3. Breakeven Formula Ignores Equity Buildup — Systematically Conservative

**What:** The breakeven formula recovers only the down payment through monthly cost savings relative to rent. It ignores: (1) mortgage principal reduction (equity buildup), (2) price appreciation, (3) income tax deductibility of mortgage interest. Including just equity buildup would reduce the breakeven horizon for a $300k home at 7% from roughly 10 years to 5–6 years. The formula systematically overstates the time to break even, which understates the case for buying in all markets.

**Where:** METHODOLOGY.md §5, `scoring_engine.py` lines 430–438.

**Assessment:** This is a deliberate simplification (no stated rationale). Because it applies uniformly, the relative rankings are unaffected. But the displayed breakeven numbers on county report cards will consistently appear longer than a complete analysis would show. The methodology should acknowledge this: "The breakeven calculation reflects only the monthly cash-flow premium of ownership over renting and does not include equity buildup, appreciation, or tax benefits."

**Triage:** Document, not fix. The ranking-based scoring is unaffected.

---

### M4. NOAA Storm Events: Year Range Enforced by Downloaded Files, Not Code

**What:** `load_noaa_storm()` reads all `.csv` files in the `noaa_storm_events` directory without any year filter. The 5-year window (2019–2023) claimed in METHODOLOGY.md §9 depends entirely on which files were downloaded by `civica_data_downloader_v4.py`. If that directory contains files outside 2019–2023, they are silently included.

**Where:** `scoring_engine.py` lines 309–330, METHODOLOGY.md §9.

**Fix:** Add a year filter based on filename pattern or an explicit year-range check on the `BEGIN_YEARMONTH` column.

---

### M5. NFIP 10-Year Window Has No Upper-Bound Date Filter

**What:** `df = df[df['yr'] >= 2014]` applies a lower bound of 2014 but no upper bound. If the FEMA NFIP dataset includes claims from 2024 or later, they are included and the window is no longer the documented "10-year average through 2023."

**Where:** `scoring_engine.py` line 304.

**Fix:** Add `& (df['yr'] <= 2023)`.

---

### M6. ZHVI `home_appreciation_3yr` Is Not Annualized and Uses January Anchor

**What:** `home_value_3yr_ago = zhvi[yr3_back[0]]` selects the *first month* of the year 3 years prior (e.g., January 2022 if latest is December 2025). The total-return calculation spans ~3.9 years, not 3. The column is not annualized (`(current/past - 1) * 100` is total return, not per-year). The column name `home_appreciation_3yr` implies an annualized 3-year rate.

**Where:** `scoring_engine.py` lines 111–114.

**Impact on scoring:** None — this column is output to the CSV for display but the scoring engine uses FHFA `hpi_3yr_avg` instead. Impact on county report cards: displayed "3-year appreciation" will be ~1.3× the implied annual rate.

**Triage:** Fix the column name to `home_appreciation_total_3yr` or annualize before outputting.

---

### M7. Appreciated Target (5%) Does Not Adjust for Inflation Vintage

**What:** `appr_deviation = |hpi_3yr_avg - 5.0|` — a fixed 5% nominal target. As documented in §14.4: during 2021-2022 (CPI >8%), 5% nominal appreciation represented approximately -3% real appreciation. Counties with 8–10% appreciation in that period were penalized by Dim1 while being near the healthy real appreciation target. The 3-year average used in this model spans 2022–2024, catching the tail of the high-inflation period.

**Where:** `scoring_engine.py` line 441, METHODOLOGY.md §14.4.

**Assessment:** Documented. Impact is reduced as the high-inflation period exits the 3-year window. Not a priority fix, but the methodology should note the vintage dependency more prominently.

---

### M8. IRS Out-Mover AGI Clip Produces Nonsensical Ratios

**What:** `m['out_avg_agi'] = m['out_agi'] / m['out_hh'].clip(lower=1)` — if `out_hh` = 0 (no recorded outflows), `out_avg_agi = total_out_agi / 1 = out_agi_total`, not a per-household average. Then `inmover_income_ratio = in_avg_agi / out_avg_agi.clip(lower=1)` produces a ratio against a raw dollar amount. For a county with zero IRS-recorded outflows, `out_agi` is 0, `out_avg_agi` clips to 1, and the ratio = `in_avg_agi`. This is dimensionally incorrect but affects only counties with no recorded IRS outflows, which should be rare.

**Where:** `scoring_engine.py` line 286.

**Triage:** Add a check `np.where(m['out_hh'] < 10, np.nan, m['in_avg_agi'] / m['out_avg_agi'])` to exclude counties with too few outflows to compute a meaningful ratio.

---

## Minor Issues

### n1. README County Count Is Wrong

`README.md` project structure: `scoring_engine.py  # Scores all 3,143 counties → county_scores.csv`

Actual: 2,820 counties (pop ≥ 5,000). Fix: "Scores 2,820 counties (pop ≥ 5,000) → county_scores.csv"

---

### n2. FHFA 3-Year Average Does Not Flag Partial Coverage

Counties with FHFA data for only 1 or 2 of the last 3 years receive a shorter average with no flag. The methodology claims "3-year average" uniformly. Add a `fhfa_years_available` count column to flag.

---

### n3. "PROPRIETARY" Label Applied to Standard Valuation Metrics

`harvard_model.html` labels Price-to-Rent Ratio, Buy vs. Rent Breakeven, and Sector Quality Score as "PROPRIETARY." P/R and buy-vs-rent breakeven are widely published metrics (Moody's Analytics, Harvard JCHS, and multiple consumer platforms compute them). Sector quality using NAICS weights is proprietary in the specific weights but not the concept. This label will invite scrutiny from anyone familiar with real estate finance.

---

### n4. RUCC fillna(5) in score_dim4 Conflicts with Prior Median Fill

`score_dim4` line 517: `pct_inv(d['rucc'].fillna(5))` — but the global median fill at line 648 has already replaced RUCC NaN with the column median before this function runs. The `.fillna(5)` is redundant. If the median RUCC happens not to be 5, there is a conflict in intent.

---

### n5. Dim4 crime imputation triggers on `violent_offenses == 0`

`mask = d['violent_offenses'].isna() | (d['violent_offenses'] == 0)` — counties with genuine zero violent offenses from participating NIBRS agencies receive RUCC-tier median imputation. A genuinely safe county (zero reported violent crimes) is assigned a higher crime rate than its actual data. This may be intentional (skepticism about zero-reporting), but it is not disclosed, and it systematically raises crime scores for the safest counties.

---

### n6. HHI Excludes Government Employment — Understates Concentration in Government-Dependent Counties

`_hhi()` operates only on `own_code == 5` (private sector). Counties where 40–60% of employment is government (federal installations, state capitals) appear more diversified than they are. Concentration risk from a single government employer is real (base closures, budget cuts) and not captured.

---

### n7. 13 vs. 14 Dataset Confusion

METHODOLOGY.md §13 data sources table has 14 rows. `scoring_engine.py` prints "[14/14]" for NIBRS load. The `main()` merge loop: `for ds in [bea, zil, fmr, hpi, qcew, cbp, bps, irs, nfip, noaa, usfs, rucc, nibrs]` — that's 13 dataset variables after `pop` (the base). `pop` is the 14th but is not in the merge loop (it's the left frame). This is just a counting inconsistency in comments; no functional impact.

---

## Open Questions

1. **What was the HUD FMR FIPS transformation validated against?** The formula `(hud_fips // 100000)` assumes a 9-digit format. HUD FMR areas include non-county geographies (Small Area FMRs, HUD Metro FMR Areas). What percentage of HUD areas actually map cleanly to a 5-digit county FIPS via this formula? How many FMR areas are silently dropped or averaged incorrectly?

2. **What are the empirically-discovered NIBRS field positions based on?** METHODOLOGY.md says "field positions discovered empirically." What was the crossvalidation? Was the county FIPS extraction validated against a known-good subset? A wrong field position at 269:272 could silently assign all offenses from one state's agencies to another county.

3. **What is the FHFA "annual_chg" column precisely?** Does it represent year-over-year change from the end of the calendar year, Q4-to-Q4, or some other period? The 3-year average computed from three calendar years of "annual_chg" values may not represent a clean 3-year annualized rate if the FHFA vintage is Q3-ended.

4. **How are multi-county HUD FMR areas handled?** HUD sometimes assigns the same FMR to multiple adjacent counties. After `df.groupby('fips')['fmr_2br'].mean()`, counties that share an FMR area are assigned the same value correctly, but counties in HUD metro areas that span county lines may get the same FMR regardless of their position within the metro. Is this the intended behavior?

5. **What is the USFS wildfire `RISK_NATIONAL_RANK` column scale?** The code loads it directly and inverts it via `pct_inv`. Is it already a national rank (0–2,820 or similar), or is it a risk score? If it's a 0–1 continuous score rather than a rank, applying `pct_inv` again produces a percentile of a score that may already be a percentile.

---

## What the Model Does Well

The data engineering is genuinely impressive. Parsing a 5.8 GB fixed-width NIBRS master file without a published format spec, assembling 13+ federal datasets via FIPS join with appropriate handling for chunked files, computing NFIP 10-year loss ratios and NOAA 5-year storm damage — this is real work that produces real signal.

The documented limitations in METHODOLOGY.md §14 are unusually honest for a consumer product: the property tax simplification, the Zillow inventory flaw, the appreciation tension between Dim1 and Dim3, the NIBRS coverage gaps and imputation method, the IRS AGI retirement bias. Any model that documents its own flaws this specifically is doing something right.

The percentile normalization architecture is sound. It correctly produces a stable mean of ~50 regardless of vintage changes and makes inter-county comparisons valid as long as the county universe remains consistent. The decision to exclude counties under 5,000 population is defensible and well-explained.

---

## Overall Assessment

The model would not survive peer review in its current form — not because the underlying approach is wrong, but because the code diverges from the documentation on every critical consumer-facing output. The breakeven bug inverts the score direction for 386 counties, affecting 13.7% of the county universe. The label thresholds in code don't match METHODOLOGY.md or the CSV on disk, meaning re-running the scorer produces different labels than the published output. The site's five-label system doesn't correspond to anything the scoring engine computes. A consumer making a purchase decision in one of the 386 affected counties is receiving a score that says "worst case for buying" when the data shows "immediate cost advantage to buying." The NaN handling documentation is actively wrong. These are not edge cases or philosophical disagreements — they are implementation errors and documentation falsehoods that affect the validity of the consumer-facing output. The foundation is solid and the data engineering is genuinely strong; the path to a defensible model is fixing C1–C6, not rebuilding from scratch.

---

## Triage Summary

| ID | Issue | Action | Priority |
|---|---|---|---|
| C1 | Label threshold code/docs/CSV mismatch | Fix: reconcile thresholds, re-run | Blocker |
| C2 | Breakeven inversion bug (386 counties) | Fix: 3-line code change | Blocker |
| C3 | Triple label system, no mapping | Fix: choose one system | Blocker |
| C4 | NaN handling misrepresented | Fix: update METHODOLOGY.md §4 | High |
| C5 | "Federal data only" false marketing | Fix: update site copy | High |
| C6 | nibrs_imputed column missing | Fix: 2-line code change | High |
| S1 | Simple assault in violent crime | Fix or disclose | High |
| S2 | Nominal income growth labeled real | Fix or disclose | Medium |
| S3 | Inventory-population correlation 0.83 | Document correlation in §14 | Medium |
| S4 | RUCC as quality vs. liquidity | Rename metric, reduce weight or document | Medium |
| S5 | Nominal wage without CoL adjustment | Document in §14 | Medium |
| S6 | FHFA drives two dimensions (10.75%) | Document explicitly | Medium |
| M1 | Sector weights unvalidated | Document, acceptable as prior | Low |
| M2 | Version number mismatch | Fix: 2-line change | Low |
| M3 | Breakeven ignores equity buildup | Document | Low |
| M4 | NOAA year filter code-enforced | Fix: add year filter | Low |
| M5 | NFIP upper-bound date filter | Fix: add `<= 2023` | Low |
| M6 | ZHVI appreciation not annualized | Fix column name or annualize | Low |
| M7 | Appreciation target not inflation-adjusted | Document, note vintage dependency | Ignore for now |
| M8 | IRS outflow clip edge case | Fix: add min-HH threshold | Low |
| n1 | README county count wrong | Fix: 1-line change | Low |
| n2 | FHFA partial-year flag missing | Document / future improvement | Ignore |
| n3 | "Proprietary" label on standard metrics | Change label | Low |
| n4 | RUCC fillna(5) redundant | Fix or remove | Low |
| n5 | Genuine-zero NIBRS imputed | Document | Low |
| n6 | HHI excludes government employment | Document | Low |
| n7 | Dataset count inconsistency in comments | Fix comments | Ignore |
