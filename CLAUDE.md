# Civica — Harvard Research Model
*Project bible for Claude Code. Read this before touching anything.*
*Last updated: May 2026*

---

## NEXT TASK — Build county_generator.py

**`scoring_engine.py` is COMPLETE. `county_scores.csv` has 2,820 counties scored.**

### Coverage Decision (intentional — do not change)
- **2,820 of 3,144 counties are scored.** The 324 excluded counties all have population < 5,000.
- The threshold is `pop >= 5,000` in `scoring_engine.py` — this is a deliberate data quality decision.
- Counties under 5,000 have no Zillow data, suppressed QCEW employment figures, and often no FHFA HPI history. Their scores would be entirely median imputation — meaningless.
- Largest excluded county: Oneida County, ID (pop 4,953). Smallest: Loving County, TX (pop 43).
- On the front page, display: **"2,820 counties scored"** — not "all 3,143". Don't claim coverage you don't have.
- If a user searches for an unscored county, show: "This county has fewer than 5,000 residents. Civica requires sufficient housing market data to produce a reliable score."

### Scoring Engine Results (v1.2 — current, includes FBI NIBRS Dim4)
- Runtime: ~4 minutes; output: `county_scores.csv` (2,820 rows × 35 columns)
- Distribution: mean=50.0, std=6.24, range 26.85–69.48
- Top: Hamilton County IN (69.48 ACCELERATING)
- Labels: ACCELERATING (2), PEAKING (57), ESTABLISHED (563), EMERGING (1,463), FRONTIER (634), TURNING (97), SPECULATIVE (4), AVOID (0)
- Note: AVOID has 0 counties — FBI NIBRS crime data raised the score floor to 26.85, above the AVOID threshold of 26. The 4 SPECULATIVE counties are the genuinely worst-performing counties.

### Next Step: `county_generator.py`

This script reads `county_scores.csv` and produces one HTML file per county using `harvard_county_profile.html` as the template. It uses Python string replacement (no Jinja2 needed — just replace placeholder tokens in the HTML).

**Steps:**
1. Read `county_scores.csv` with `dtype={'fips': str}` to preserve leading zeros
2. Get county names by joining with USDA RUCC (`civica_data/usda_rucc/ruralurbancodes2023.xlsx`, columns `FIPS` + `County_Name` + `State`)
3. For each row, replace tokens in the HTML template with real values
4. Write each file to `output/counties/{fips}.html` (create the folder if needed)
5. Write `output/index.json` — array of `{fips, name, state, score, label, dim1–dim6, median_home_value, avg_annual_wage}` for every county, sorted by score descending — the front page will load this to build the search/map

**Token map — replace these strings in the template:**

| Token | Value from CSV |
|---|---|
| `Jefferson County, CO` (h1) | `{county_name}, {state_abbr}` |
| `Metro Denver · RUCC Code 1 (Large Metro) · Pop. 582,910` | `RUCC {rucc} · Pop. {POPESTIMATE2023:,}` |
| `80` (score ring sh-num) | `{total_score:.0f}` |
| `stroke-dashoffset="52.02"` (hero ring) | computed: `289.02 * (1 - score/100)` |
| `stroke-dashoffset="57.8"` (banner ring) | same formula |
| `80` (banner ring SVG text) | `{total_score:.0f}` |
| `Top 14% Nationally` | `Top {pct:.0f}% Nationally` (derived from national_rank / 2820 * 100) |
| `vb-buy">BUY` | `vb-{verdict_class}">{verdict_text}` |
| `22.2x` (P/R pill) | `{pr_ratio:.1f}x` |
| `2.1 years` (breakeven pill) | `{breakeven_yrs:.1f} years` |
| `+3.7% / yr` (appreciation pill) | `{hpi_3yr_avg:+.1f}% / yr` |
| `$3,040` (monthly cost pill) | `${monthly_piti:,.0f}` |
| `+4,200 HH` (net migration pill) | `{NETMIG2023:+,.0f} HH` |
| `Strong structural buy...` (thesis text) | generated from label + top signals |
| dim score values in sbb-items (72, 84, 88...) | `{dim1/25*100:.0f}`, etc. (convert to 0–100 sub-scores) |
| `$527,000` (home value) | `${median_home_value:,.0f}` |
| `$1,980` (rent) | `${fmr_2br:,.0f}` |
| `5-Year Scenarios` values | bull=value×1.63, base=value×1.27, bear=value×0.93 |
| `County Research Report · 2025` (eyebrow) | `County Research Report · 2026` |
| `<title>Jefferson County, CO` | `<title>{county_name}, {state_abbr}` |

**Verdict logic:**
- score ≥ 58 → `vb-buy` / `BUY`
- score 38–57 → `vb-hold` / `HOLD`
- score < 38 → `vb-avoid` / `AVOID`

**Thesis text — one sentence per label:**
- PEAKING: `"Strong momentum market near its affordability ceiling. Best for buyers with short-to-medium hold horizons."`
- ESTABLISHED: `"Solid, balanced market with sustainable fundamentals and moderate appreciation."`
- EMERGING: `"Improving fundamentals with early-mover upside. Demand is building ahead of prices."`
- FRONTIER: `"Thin market data. Fundamentals are mixed — conduct additional local due diligence."`
- TURNING: `"Softening demand signals. Monitor for continued weakness before committing."`
- SPECULATIVE: `"Poor fundamentals. Current prices appear disconnected from underlying economics."`

**Dimension sub-scores for the banner (convert to 0–100):**
- dim1 raw is 0–25 pts → sub-score = `dim1 / 25 * 100`
- dim2 raw is 0–22 pts → sub-score = `dim2 / 22 * 100`
- dim3 raw is 0–20 pts → sub-score = `dim3 / 20 * 100`
- dim4 raw is 0–15 pts → sub-score = `dim4 / 15 * 100`
- dim5 raw is 0–12 pts → sub-score = `dim5 / 12 * 100`
- dim6 raw is 0–6 pts  → sub-score = `dim6 / 6  * 100`

After that: wire the front page (`civica.html` or a new `civica-v2.html`) to load `output/index.json` and link to the county reports.

---

## What Civica Is

Civica is an unbiased, data-driven platform that scores all 3,143 US counties for homebuyers. No agents, no listings, no advertising. Every score comes exclusively from free federal government data. This is the core brand promise — never compromise it.

**The one-paragraph pitch:**
Civica is the only platform where a homebuyer can look up any US county and get objective, data-backed answers to the questions that actually matter: Is this a good place? Are smart buyers choosing it? Is it getting better or worse? Every score is derived from free federal government data — no agents, no listings, no advertising, no conflict of interest. The first consumer real estate tool whose scores cannot be bought.

---

## The Chosen Model — Harvard-Style 6-Dimension Research Framework

**This is the locked-in design direction.** After exploring multiple UI/model approaches (simple 4-question buyer card, comprehensive 4-pillar v2, and the Harvard research model), the Harvard model was selected. Do not revert to earlier designs.

**Why this model was chosen:**
1. Uses 8 derived metrics (P/R ratio, breakeven horizon, real appreciation, permit gap) that no competitor publishes
2. Treats homebuyers like sophisticated investors — shows the WHY behind every score
3. The $95k+ target demographic wants analytical depth, not just stoplight colors
4. Bull/base/bear scenario analysis and risk matrix are genuinely differentiated features
5. 6-dimension breakdown provides more signal nuance than 4 pillars
6. The vs. Zillow/Redfin comparison table is a trust-building feature unique to Civica

---

## Design System — Lock These Values

### CSS Variables (use exactly these)
```css
--blue:   #1a7ff0;   /* primary brand blue — CTAs, links, highlights */
--navy:   #1a3a5c;   /* headings, hero background, logo text */
--green:  #16a34a;   /* positive signals, BUY verdict, ACCELERATING badge */
--yellow: #d97706;   /* caution signals, PEAKING/SPECULATIVE */
--red:    #dc2626;   /* negative signals, AVOID verdict */
--bg:     #f0f2f5;   /* page background */
--white:  #ffffff;   /* card backgrounds */
```

### Typography
- Font stack: `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
- Score numbers: font-size 48px+, font-weight 900
- Section headings: font-weight 800, color var(--navy)
- Body text: 14-15px, color #374151, line-height 1.55
- Labels/caps: 11-12px, letter-spacing .07em, text-transform uppercase

### Logo Spec — Never Alter
- 30×30 blue SVG icon (A-shaped path with crossbar)
- Logotype: `civi<em>ca</em>` — "ca" in `#1a7ff0` blue, "civi" in `#1a3a5c` navy
- Apply consistently on every page, every version

### Key Components
- **Score ring**: SVG circle, circumference 289.02, stroke-dashoffset = (1 - score/100) × 289.02
- **Tab navigation**: `.tab-btn.active` + `showTab(name)` JS pattern
- **Verdict badges**: ACCELERATING=green, PEAKING=yellow, AVOID=red (see full 8-label table)
- **Score banner**: horizontal strip showing all 6 dimension scores at a glance
- **Meter bars**: visual 0-100 range bars with national median marker line
- **Signal cards**: icon + metric name + value + benchmark comparison

---

## The 6 Dimensions

### 1. Affordability & Value — 25 points
*Is the price defensible relative to what you're getting?*

| Metric | Weight | Source | Formula |
|---|---|---|---|
| Price-to-Rent Ratio | 30% | Zillow ZHVI ÷ HUD FMR×12 | National norm: 15–18x |
| Price-to-Income Ratio | 30% | Zillow ZHVI ÷ BEA per capita income | Historical norm: 4.2x |
| Buy vs. Rent Breakeven | 25% | Down payment (20%) ÷ (monthly PITI − HUD FMR) × 12 | Shorter = stronger buy case |
| Appreciation Quality | 15% | FHFA 3-yr avg annual HPI change | Penalizes deviation from 3–7% healthy range |

**Note:** Utility Burden (EIA) was the original spec'd metric for the 15% slot. The EIA data maps to utility territories, not county FIPS — a spatial join would be needed to aggregate to county level. Appreciation Quality from FHFA is used instead as a defensible federal-data substitute. The breakeven assumes 7% 30-yr fixed (2024 national rate), 1.2% property tax, 0.5% insurance, 20% down; capped at 30 years.

### 2. Economic Vitality — 22 points
*Is the local economy growing in real terms?*

| Metric | Weight | Source | Formula |
|---|---|---|---|
| Wage Level | 35% | BLS QCEW avg annual wage | Higher wage = stronger labor market |
| Sector Quality | 25% | BLS QCEW employment-weighted NAICS quality score | Professional/Finance premium |
| Economic Diversity (HHI) | 25% | BLS QCEW NAICS Herfindahl Index | Lower HHI = more diversified |
| Income Growth | 15% | BEA CAINC1 per-capita income, 4-yr growth | Rising = improving real incomes |

**Note:** Business Formation Rate (Census CBP CAGR) and Fiscal Capacity (Census STC) were the original spec'd metrics for the 25%/15% slots. Census STC is published at the state level only — county-level fiscal capacity cannot be derived from it. CBP is a point-in-time count without a prior-year comparison in the downloaded file. BLS QCEW Sector Quality and BEA Income Growth are used as defensible federal-data substitutes.

**Sector quality weights by NAICS (applied to employment share in sector_quality score):**
- Professional/Scientific/Technical (NAICS 54): × 1.30
- Finance & Insurance (NAICS 52): × 1.30
- Healthcare (NAICS 62): × 1.00
- Education (NAICS 61): × 1.00
- All other private sectors: × 1.00 (neutral)
- Construction (NAICS 23): × 0.80 (leading indicator but cyclical)
- Retail (NAICS 44-45): × 0.60 (secular decline risk)
- Legacy Manufacturing (NAICS 31-33): × 0.60

### 3. Housing Market Dynamics — 20 points
*What is the market actually doing?*

| Metric | Weight | Source | Formula |
|---|---|---|---|
| 3-Year Appreciation Trend | 35% | FHFA HPI 3-yr avg annual change | Sustained appreciation = strong underlying demand |
| Current Momentum | 15% | FHFA HPI latest annual change | Cross-validates trend; rising = acceleration |
| Supply Tightness | 30% | Zillow active inventory (latest month) | Lower inventory = seller's market |
| Permit Pipeline | 20% | Census BPS new housing units permitted | Higher = supply responding to demand |

**Note:** Original spec called for Permit Gap Ratio (permits ÷ net new households), Supply Elasticity (permit trend vs. price trend), and Rent Trend (HUD FMR YoY change). HUD FMR is a single vintage file (FY2026) with no prior-year comparison in the download. The four metrics above use all available downloaded data and two independent FHFA price signals (trend + momentum) to cross-validate appreciation.

### 4. Quality of Place — 15 points
*Is it a good place to actually live?*

| Metric | Weight | Source | Formula |
|---|---|---|---|
| Crime Rate | 35% | FBI NIBRS 2024 | Violent offenses per 100k residents (lower = better); counties without NIBRS coverage receive their RUCC-tier median |
| Urban Access | 40% | USDA RUCC 2023 | Percentile rank of continuum: 1 (large metro) → 9 (most rural) |
| Amenity Density | 25% | Census CBP 2022 | Private establishments per 1,000 residents |

**Note:** Original spec also called for School Adequacy (NCES — not downloaded) and Service Efficiency (Census STC — state-level only, no county FIPS). FBI NIBRS 2024 National Master File (5.8 GB fixed-width) was successfully parsed by empirically decoding the record layout: BH (agency header) segments contain state alpha at positions 4–6 (chars 3-4 of ORI) and county 3-digit FIPS at positions 269–272; 02 (offense) segments carry the NIBRS offense code at positions 33–36. This covers 21,068 agencies across 49 states and 2,869 counties. Counties not covered by participating agencies (predominantly rural) are imputed with their RUCC-tier median violent crime rate so non-reporting isn't mistaken for low crime.

### 5. Physical Risk — 12 points
*What are the climate and natural hazard costs?*

**Note: FEMA NRI was not downloadable. Physical Risk is scored using the three proxy datasets below — the same underlying data FEMA uses to build its NRI.**

| Metric | Weight | Source | Formula |
|---|---|---|---|
| Flood Loss Proxy | 40% | FEMA NFIP paid claims ÷ Census population | 10-yr avg claims per capita |
| Storm Damage Proxy | 35% | NOAA Storm Events property damage ÷ population | 5-yr avg damage per capita |
| Wildfire Exposure | 25% | USFS Wildfire Risk to Communities score | County-level exposure index |

**Composite Physical Risk Index (for scoring engine):**
```
Physical Risk Index =
  NFIP loss ratio percentile (inverted)    × 0.40
+ NOAA storm damage per household pct      × 0.35
+ Wildfire risk score percentile           × 0.25
```
Lower score = safer. Invert the percentile so high-risk counties score low.

**Insurance cost output (for monthly cost model):**
National median homeowners insurance ≈ $159/mo. Apply county risk multiplier:
- Low-risk county (score 85): $159 × 0.72 = ~$115/mo
- High-risk county (score 22): $159 × 2.10 = ~$334/mo

### 6. Population Momentum — 6 points
*Are the right people moving in?*

| Metric | Weight | Source | Formula |
|---|---|---|---|
| Net Migration Rate | 60% | Census Population Estimates 2023 | RNETMIG2023: net migration per 1,000 residents |
| Income Quality of In-Movers | 40% | IRS SOI Migration 2022-2023 | in-mover avg AGI ÷ out-mover avg AGI; ratio > 1.0 = higher-income arrivals |

---

## The 8 Derived Metrics

These are Civica's proprietary analytical layer — computed from raw federal data, not available on any other consumer platform.

| Metric | Formula | National Norm | Source Data |
|---|---|---|---|
| **Price-to-Rent Ratio** | Zillow ZHVI ÷ (HUD FMR × 12) | 15–18x | Zillow + HUD |
| **Buy vs. Rent Breakeven** | Down payment (20%) ÷ ((monthly PITI − HUD 2BR FMR) × 12) | 3–7 years | Zillow + HUD; assumes 7% 30yr, 1.2% tax, 0.5% insurance; cap 30yr |
| **Appreciation Quality** | \|FHFA 3-yr avg annual HPI − 5%\| (deviation from healthy midpoint) | 0 deviation = ideal | FHFA HPI county |
| **Supply Tightness** | Zillow active inventory, latest month (percentile-inverted nationally) | Lower = tighter | Zillow |
| **Sector Quality Score** | Σ(employment share × NAICS quality weight) across private supersectors | 1.00 = neutral mix | BLS QCEW |
| **Employment Concentration (HHI)** | Σ(industry employment share²) × 10,000 across NAICS codes | <1,500 = diversified | BLS QCEW |
| **In-Mover Income Quality** | IRS in-mover avg AGI ÷ IRS out-mover avg AGI | 1.0 = neutral | IRS SOI Migration |
| **Physical Risk Score** | NFIP claims/capita (40%) + NOAA storm damage/capita (35%) + USFS wildfire rank (25%); all percentile-inverted | Lower = safer | FEMA NFIP + NOAA + USFS + Census |

---

## The 8 Market Labels

Every county gets exactly one label based on its 6-dimension score profile.

| Label | Score Profile | Buyer Guidance |
|---|---|---|
| **ACCELERATING** | Affd ≥60, Econ ≥65, MktDyn ≥70, QoP ≥60, Risk ≥50, Pop ≥65 | Strongest long-term hold. All signals positive. Window still open. |
| **PEAKING** | Strong scores but MktDyn declining (P/R >22x, permit gap <0.4) | Great now. Fundamentals softening. Buying the peak story. |
| **TURNING** | Affd + QoP strong, MktDyn + Pop reversing positively | Quality market that market hasn't re-discovered. Early signal. |
| **ESTABLISHED** | Strong Affd + QoP, low Momentum, stable | Solid and stable. Buy for lifestyle, not appreciation. |
| **EMERGING** | Econ + Pop strong, Affd + QoP below average | High-conviction early mover. Demand and fundamentals rising. Risk real. |
| **SPECULATIVE** | High MktDyn, weak fundamentals (P/R >25x, EAL high) | Demand outrunning quality. Classic trap. |
| **FRONTIER** | Pop + Econ signals early-positive, Affd + QoP weak | Everything early. High risk, high upside if fundamentals materialize. |
| **AVOID** | Multiple dimensions weak with no positive momentum | Nothing working in any direction. |

**Label trigger thresholds (total score cutoffs):** ACCELERATING ≥68, PEAKING ≥62, ESTABLISHED ≥55, EMERGING ≥46, FRONTIER ≥38, TURNING ≥30, SPECULATIVE ≥26, AVOID ≥0.

**Threshold calibration note:** Percentile normalization (mean≈50, std≈7.7, range 23–73) bounds scores within the actual data distribution. Original thresholds of 78 and 18 were unreachable: no county ever scored above 73.09 or below 22.85. The recalibrated thresholds above are derived from the empirical distribution and ensure all 8 labels fire with meaningful county counts.

---

## Monthly Cost Model (implemented in scoring engine)

The scoring engine computes `monthly_piti` for each county — the ownership cost used in the breakeven calculation.

| Component | Source | Method |
|---|---|---|
| Mortgage (P&I) | Zillow ZHVI median home value | 30-yr fixed at 7% (2024 national rate), 20% down |
| Property Tax | Hardcoded 1.2% annual rate | National median effective rate; not county-specific |
| Homeowner Insurance | Hardcoded 0.5% annual rate | National median; not risk-adjusted per county |

**Note:** Full all-in cost breakdown (electricity, gas, maintenance) is intended for county report cards via `county_generator.py` and is not yet implemented. EIA electricity maps to utility service territories, not county FIPS. NOAA Climate Normals (station-level, no county FIPS) would require a spatial join to derive heating/cooling degree days. Both are documented future enhancements.

---

## Data Sources (18 Datasets on Disk)

| # | Dataset | File | Status | Used For |
|---|---|---|---|---|
| 1 | IRS SOI Migration | irs_migration/ | ✓ Active | Dim6: in-mover income quality ratio |
| 2 | FHFA HPI County | fhfa_hpi/hpi_at_county.xlsx | ✓ Active | Dim1: appreciation quality; Dim3: 3-yr trend + current momentum |
| 3 | BLS QCEW | bls_qcew/2023.annual.singlefile.csv | ✓ Active | Dim2: wages, sector quality, HHI |
| 4 | BEA Local Area (CAINC1) | bea_income/CAINC1__ALL_AREAS_1969_2024.csv | ✓ Active | Dim1: price-to-income; Dim2: income growth |
| 5 | FBI NIBRS | fbi_crime/2024_NIBRS_NATIONAL_MASTER_FILE.txt | ✓ Active | Dim4: violent offenses per 100k (21,068 agencies, 49 states, 2,869 counties) |
| 6 | FEMA NFIP Claims | fema_nfip/fema_nfip_claims.csv | ✓ Active | Dim5: flood loss per capita (10-yr window) |
| 7 | NOAA Storm Events | noaa_storm_events/ (5 CSVs) | ✓ Active | Dim5: storm damage per capita (5-yr window) |
| 8 | USFS Wildfire Risk | usfs_wildfire/wrc_download_20260415.xlsx | ✓ Active | Dim5: wildfire national risk rank |
| 9 | EIA Form 861 | eia_electricity/ (3 files) | ✗ Not used | Maps to utility service territories, not county FIPS; spatial join required |
| 10 | EIA Natural Gas | eia_gas/NG_PRI_SUM_DCU_NUS_A.xls | ✗ Not used | State-level prices only; no county-level decomposition in file |
| 11 | Census STC | census_stc/STC-Historical-DB.xlsx | ✗ Not used | State-level data only — no county FIPS in file |
| 12 | Census Population Estimates | census_population/co-est2023-alldata.csv | ✓ Active | Base county universe; migration rates; per-capita denominators |
| 13 | Census BPS | census_bps/co2022a.txt | ✓ Active | Dim3: new housing supply pipeline |
| 14 | Census CBP | census_cbp/cbp22co.txt | ✓ Active | Dim4: amenity density (establishments per 1,000 residents) |
| 15 | USDA RUCC | usda_rucc/ruralurbancodes2023.xlsx | ✓ Active | Dim4: urban access continuum (1=large metro, 9=most rural) |
| 16 | HUD Fair Market Rents | hud_fmr/FY26_FMRs_revised.xlsx | ✓ Active | Dim1: rent baseline, P/R ratio, breakeven |
| 17 | NOAA Climate Normals | noaa_climate_normals/ | ✗ Not used | Station-level temperature; no county FIPS; spatial join required |
| 18 | Zillow ZHVI | zillow/ | ✓ Active | Dim1: median home value; Dim3: active inventory |

**FEMA NRI was not downloadable. Physical Risk uses datasets 6, 7, 8 — the same underlying hazard data FEMA uses to build its NRI.**

**Active datasets: 11 of 18 (datasets 1–4, 5, 6–8, 12–16, 18). Total data cost: $0. No ACS survey data.**

**Note on Zillow:** Zillow ZHVI is not federal data. It is the only non-federal source in the model, used because no federal dataset provides county-level median home values at monthly granularity. FHFA HPI is used for all appreciation signals; Zillow is used only for the price level and inventory count.

---

## Known Data Limitations

| Issue | Dataset | Impact | Current Handling |
|---|---|---|---|
| FHFA covers ~2,800 of 3,143 counties | FHFA HPI | ~340 rural counties missing appreciation data | National median imputed; reduces score slightly for FHFA-absent counties |
| CBP has 18-month publication lag | Census CBP | Establishment data ~2 years behind | Accepted; no alternative county-level source available |
| Small county distortion | All | 1 employer can swing all metrics | 324 counties under 5,000 pop excluded entirely — no imputed scores |
| Zillow coverage gaps | Zillow ZHVI | Some rural counties have no home value data | National median imputed via left-join merge |
| NIBRS coverage gaps | FBI NIBRS | ~251 counties lack a participating agency (rural) | RUCC-tier median violent crime rate imputed; non-reporters not penalized |
| NFIP only captures insured flood losses | FEMA NFIP | Uninsured flood damage not counted | NOAA Storm Events covers all storm types; combined with NFIP |
| EIA and Census STC not county-level | EIA, STC | Utility burden and fiscal capacity not scored | Documented as not implemented; appreciation quality and income growth used instead |

---

## Scoring Algorithm

### What Is Defined
- 6 dimensions with precise weights (25/22/20/15/12/6 = 100 total)
- All metrics within each dimension with intra-dimension weights
- Formulas for all 8 derived metrics
- 8 market labels with qualitative trigger conditions
- Monthly cost calculation methodology

### What Is Resolved (scoring engine v1.1 COMPLETE)

1. **Normalization method** — percentile rank: `pct(s) = s.rank(pct=True) * 100`, inverted where lower=better (`pct_inv`)
2. **Label trigger thresholds** — ACCELERATING ≥68, PEAKING ≥62, ESTABLISHED ≥55, EMERGING ≥46, FRONTIER ≥38, TURNING ≥30, SPECULATIVE ≥26, AVOID ≥0 (all 8 labels fire)
3. **National distribution** — mean≈50.0, std≈7.7 by construction of percentile normalization; empirical range 23–73
4. **Edge cases** — missing data filled via left join from population base; counties with no FHFA or QCEW data receive NaN for those dimensions, which reduces their total score proportionally
5. **Sector weights** — only NAICS codes specified in the model (54, 52, 62, 61, 23, 44-45, 31-33); all other sectors neutral (1.00×)
6. **Dim3** — uses two independent FHFA HPI signals (3yr trend + latest) plus Zillow inventory and Census permits; `inmover_income_ratio` moved exclusively to Dim6 where it belongs
7. **Dim6** — net migration rate 60% + in-mover income quality 40%, matching spec intent exactly

---

## File Structure

```
Civica Harvard Model/
├── CLAUDE.md                          ← This file — project bible
├── LAUNCH_TODO.md                     ← Full launch checklist (security, SEO, features)
├── README.md                          ← GitHub readme
├── LICENSE                            ← MIT
├── .gitignore                         ← Excludes civica_data/ and county_scores.csv
├── harvard_county_profile.html        ← County report template (THE design)
├── harvard_model.html                 ← Methodology page (THE design)
├── civica_data_downloader_v4.py       ← Downloads all datasets to civica_data/
├── scoring_engine.py                  ← COMPLETE — scores all 2,820 counties
├── county_scores.csv                  ← COMPLETE — 2,820 rows × 36 cols (on disk, not in git)
├── civica_data/                       ← All datasets on disk (~7 GB, not in git)
│   ├── bea_income/
│   ├── bls_qcew/
│   ├── census_bps/
│   ├── census_cbp/
│   ├── census_population/
│   ├── census_stc/
│   ├── eia_electricity/
│   ├── eia_gas/
│   ├── fbi_crime/
│   ├── fema_nfip/
│   ├── fhfa_hpi/
│   ├── hud_fmr/
│   ├── irs_migration/
│   ├── noaa_climate_normals/
│   ├── noaa_storm_events/
│   ├── usda_rucc/
│   ├── usfs_wildfire/
│   └── zillow/
└── [next to build]
    ├── county_generator.py            ← Produces one HTML per county from template
    └── index.html                     ← Front page (search, filter, browse)
```

**Versioning rule:** Never overwrite existing HTML files. New versions get incremental names (county_profile_v2.html, etc.).

---

## The Data Pipeline

`civica_data_downloader_v4.py` was the final download run. All 18 datasets are on disk in `civica_data/`. No further downloads needed.

**All data is at:** `C:\Users\Brian\Desktop\Civica Harvard Model\civica_data\`

**FEMA NRI status:** Not downloaded — site blocked all automated and manual attempts. Physical Risk dimension uses FEMA NFIP + NOAA Storm Events + USFS Wildfire as proxies instead. These are the same source datasets FEMA uses internally to produce the NRI, so coverage is equivalent.

---

## Coding Rules

- Static HTML/CSS/JS — no backend required until payment layer
- Python for all data pipeline scripts
- Always set UTF-8 in Python: `sys.stdout.reconfigure(encoding='utf-8')`
- Never use `$matches` in PowerShell
- No mock data in production — every number must trace to a federal source
- Design system CSS variables must never be hardcoded inline
- Tab switching uses the `showTab(name)` pattern from harvard_county_profile.html

---

## Never Do These Things

- No agent advertising integrations — ever. This destroys the trust moat.
- No survey data (ACS excluded — administrative equivalents exist for everything)
- No proprietary data sources — every metric must be replicable from free federal data
- No overwriting existing versioned HTML files
- No Redfin, MLS, or agent-affiliated listing data — these introduce conflict of interest; Zillow ZHVI (home value index, not listings) is the sole exception and is used only where no federal equivalent exists at county level
- No hardcoded county-specific values in the template files (data must be injected)

---

## Competitive Positioning

| Feature | Civica | Zillow | Redfin | Niche |
|---|---|---|---|---|
| Federal-data-first (one non-federal source: Zillow ZHVI for price levels only) | Yes | No | No | Partial |
| No agent advertising | Yes | No | No | No |
| Price-to-rent ratio | Yes | No | No | No |
| Buy vs. rent breakeven | Yes | No | No | No |
| Real vs. nominal appreciation | Yes | No | No | No |
| Permit gap analysis | Yes | No | No | No |
| Bull/base/bear scenarios | Yes | No | No | No |
| Risk matrix with probabilities | Yes | No | No | No |
| All 3,143 US counties | Yes | Partial | Partial | Yes |

---

## Monetization (Do Not Deviate)

- Phase 1: Fully free. Build trust and reputation.
- Phase 2 (6-12 months): Lender referral partnerships. Transparent disclosure, no score influence.
- Phase 3 (12+ months): Premium tier — $99-149/yr or $9-14/report for full breakdown.
- Phase 4 (18+ months): B2B data licensing to relocation companies.

**Never:** Introduce agent advertising. It destroys the only thing that separates Civica from Zillow.
