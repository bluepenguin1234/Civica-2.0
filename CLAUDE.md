# Civica — Harvard Research Model
*Project bible for Claude Code. Read this before touching anything.*
*Last updated: May 2026*

---

## NEXT TASK — Build county_generator.py

**`scoring_engine.py` is COMPLETE. `county_scores.csv` has 2,820 counties scored.**

### Scoring Engine Results (for reference)
- Runtime: ~4 minutes; output: `county_scores.csv` (711 KB, 36 columns)
- Distribution: mean=50.0, std=7.67, range 22.85–73.09
- Top: Palm Beach FL (73.09 PEAKING), Hamilton County IN, Williamson County TN
- Major metros: Manhattan 66.1, Cook IL 62.5, LA 61.4, Dallas 60.3, Phoenix 59.7 (all ESTABLISHED)
- Labels active: PEAKING (13), ESTABLISHED (428), EMERGING (1,254), FRONTIER (948), TURNING (171), SPECULATIVE (6)

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
| Price-to-Rent Ratio | 30% | FHFA HPI ÷ HUD FMR×12 | National norm: 15x |
| Price-to-Income Ratio | 30% | FHFA HPI ÷ BEA per capita income | Historical norm: 4.2x |
| Buy vs. Rent Breakeven | 25% | Transaction costs (11%) ÷ (Annual appr − Ownership premium) | Under 3 years = strong |
| Utility Burden | 15% | EIA electricity + gas ÷ county median income | Lower % = better |

### 2. Economic Vitality — 22 points
*Is the local economy growing in real terms?*

| Metric | Weight | Source | Formula |
|---|---|---|---|
| Real Wage Growth | 35% | BLS QCEW CAGR − CPI | Positive = real gains |
| Employment Concentration (HHI) | 25% | BLS QCEW NAICS Herfindahl Index | Lower HHI = more diversified |
| Business Formation Rate | 25% | Census CBP establishment CAGR | Rising = entrepreneurial activity |
| Fiscal Capacity | 15% | Census STC tax revenue ÷ population | Higher = more government capacity |

**Job Acceleration formula (for scoring engine):**
```
Job Acceleration Delta =
  current 4-quarter employment growth rate
− trailing 8-quarter average employment growth rate
```
A positive delta = gaining momentum. Negative delta = decelerating (warning signal even if growth is still positive).

**Sector weighting by NAICS (apply to growth rates before scoring):**
- Professional/Scientific/Technical (NAICS 54): × 1.30
- Finance & Insurance (NAICS 52): × 1.30
- Healthcare (NAICS 62): × 1.00
- Education (NAICS 61): × 1.00
- Construction (NAICS 23): × 0.80 (leading indicator but cyclical)
- Retail (NAICS 44-45): × 0.60 (secular decline)
- Legacy Manufacturing (NAICS 31-33): × 0.60

### 3. Housing Market Dynamics — 20 points
*What is the market actually doing?*

| Metric | Weight | Source | Formula |
|---|---|---|---|
| Real Appreciation | 35% | FHFA HPI CAGR − CPI | Strip out inflation |
| Permit Gap Ratio | 30% | Census BPS permits ÷ net new households | <1.0 = supply shortage |
| Supply Elasticity | 20% | Permit trend over 5yr vs. price trend | Rising permits = healthy response |
| Rent Trend | 15% | HUD FMR year-over-year change | Rising = landlords see demand |

### 4. Quality of Place — 15 points
*Is it a good place to actually live?*

| Metric | Weight | Source | Formula |
|---|---|---|---|
| School Adequacy | 40% | NCES Finance (per-pupil spend) + EDFacts (proficiency) | Combined adequacy score |
| Crime vs. Peers | 35% | FBI NIBRS violent crime rate vs. USDA RUCC tier | Compare within rural/urban tier |
| Service Efficiency | 25% | Census STC expenditure ÷ service output proxies | Per-capita efficiency ratio |

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
| Net Migration Rate | 60% | IRS SOI (in-households − out-households) ÷ total HH | 3-year average |
| Income Quality of Movers | 40% | (IRS in-mover AGI − out-mover AGI) ÷ county median AGI | Positive = upgrading |

---

## The 8 Derived Metrics

These are Civica's proprietary analytical layer — computed from raw federal data, not available on any other consumer platform.

| Metric | Formula | National Norm | Source Data |
|---|---|---|---|
| **Price-to-Rent Ratio** | FHFA HPI ÷ (HUD FMR × 12) | 15–18x | FHFA + HUD |
| **Buy vs. Rent Breakeven** | Transaction costs (11%) ÷ (Annual appr − Annual ownership premium) | 2–4 years | FHFA + HUD + EIA |
| **Real Appreciation** | FHFA HPI 5yr CAGR − CPI 5yr avg | 1.5–2.5% | FHFA + BLS CPI |
| **Permit Gap Ratio** | Census BPS annual permits ÷ net new households | 1.0 = balanced | Census BPS + IRS SOI |
| **Real Wage Growth** | BLS QCEW avg wage CAGR − CPI | 0.5–1.5% | BLS QCEW + BLS CPI |
| **Employment Concentration (HHI)** | Sum of (industry share²) across NAICS codes | <1,500 = diversified | BLS QCEW |
| **In-Mover Income Quality** | (IRS in AGI − out AGI) ÷ county median AGI | 0 = neutral | IRS SOI |
| **Physical Risk Score** | Weighted avg: NFIP claims/capita (40%) + NOAA storm damage/capita (35%) + USFS wildfire score (25%) | Lower = safer | FEMA NFIP + NOAA + USFS + Census |

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

**Label trigger thresholds are conceptually defined but exact numeric cutoffs are PENDING.** See "Scoring Algorithm — Pending" below.

---

## True Monthly Cost Model

Every county report shows a complete all-in monthly ownership cost — not just mortgage.

| Component | Source | Method |
|---|---|---|
| Mortgage (P&I) | FHFA HPI (median value) | 30-yr fixed at current national rate, 20% down |
| Property Tax | Census STC effective rate | (Home value × effective rate) ÷ 12 |
| Homeowner Insurance | FEMA NFIP + NOAA Storm Events + USFS Wildfire | Base national avg adjusted by composite hazard proxy per capita |
| Electricity | EIA Form 861 actual billing | County utility territory median residential bill |
| Natural Gas | EIA residential NG prices | State rate × median county heating days |
| Maintenance | USDA RUCC + housing age | Urban: 0.8% of value/yr; Rural: 1.1% of value/yr |

**Total = all 6 components. Every number is from federal administrative data — no surveys, no estimates.**

---

## Data Sources (15 Datasets — All Free Federal, All On Disk)

| # | Dataset | File | Used For |
|---|---|---|---|
| 1 | IRS SOI Migration | irs_migration/ | Net migration, income quality of movers |
| 2 | FHFA HPI County | fhfa_hpi/hpi_at_county.xlsx | Home price index, appreciation, P/R ratio |
| 3 | BLS QCEW | bls_qcew/2023.annual.singlefile.csv | Wages, employment, HHI concentration |
| 4 | BEA Local Area (CAINC1) | bea_income/CAINC1__ALL_AREAS_1969_2024.csv | Per capita income, real income growth |
| 5 | FBI NIBRS | fbi_crime/2024_NIBRS_NATIONAL_MASTER_FILE.txt | Violent + property crime rates |
| 6 | FEMA NFIP Claims | fema_nfip/fema_nfip_claims.csv | Flood risk proxy (Physical Risk dimension) |
| 7 | NOAA Storm Events | noaa_storm_events/ (5 CSVs) | Storm damage proxy (Physical Risk dimension) |
| 8 | USFS Wildfire Risk | usfs_wildfire/wrc_download_20260415.xlsx | Wildfire exposure (Physical Risk dimension) |
| 9 | EIA Form 861 | eia_electricity/ (3 files) | Residential electricity by county/utility |
| 10 | EIA Natural Gas | eia_gas/NG_PRI_SUM_DCU_NUS_A.xls | Residential NG prices by state |
| 11 | Census STC | census_stc/STC-Historical-DB.xlsx | Property tax rates, fiscal capacity |
| 12 | Census Population Estimates | census_population/co-est2023-alldata.csv | County population (risk per capita denominator) |
| 13 | Census BPS | census_bps/co2022a.txt | Permit gap ratio, supply elasticity |
| 14 | Census CBP | census_cbp/cbp22co.txt | Business formation rate |
| 15 | USDA RUCC | usda_rucc/ruralurbancodes2023.xlsx | Urban/rural peer comparison for crime scoring |
| 16 | HUD Fair Market Rents | hud_fmr/FY26_FMRs_revised.xlsx | P/R ratio + rent trend metric |
| 17 | NOAA Climate Normals | noaa_climate_normals/ | Heating/cooling degree days for utility cost |
| 18 | Zillow ZHVI | zillow/ | Supplemental price trend validation |

**FEMA NRI was not downloadable (site blocks scripts + manual download unclear). Replaced by datasets 6, 7, 8 above — the same underlying hazard data FEMA uses to build its NRI.**

**Total data cost: $0. No survey data. No proprietary data. No ACS.**

---

## Known Data Limitations (Handle in Scoring Engine)

| Issue | Dataset | Impact | Fix |
|---|---|---|---|
| FHFA covers ~2,900 of 3,143 counties | FHFA HPI | ~240 rural counties missing price data | Use state HPI as proxy; flag lower confidence |
| CBP has 18-month publication lag | Census CBP | Business data is always ~2 years behind | Use QCEW as primary signal; CBP as confirmation |
| Small county distortion | All | 1 employer can swing all metrics | Apply minimum pop threshold of 50k for full scoring; flag below |
| FBI NIBRS coverage varies by state | FBI NIBRS | Some agencies don't report | Use state/RUCC-tier average for missing counties |
| NFIP only captures flood; not all hazards | FEMA NFIP | Wildfire/tornado counties underweighted | NOAA Storm Events + USFS Wildfire fills the gap |

---

## Scoring Algorithm

### What Is Defined
- 6 dimensions with precise weights (25/22/20/15/12/6 = 100 total)
- All metrics within each dimension with intra-dimension weights
- Formulas for all 8 derived metrics
- 8 market labels with qualitative trigger conditions
- Monthly cost calculation methodology

### What Is PENDING (next task)
The following need to be defined before a real scoring engine can be built:

1. **Normalization method** — how does a raw value (e.g., P/R ratio of 22.2x) become a score from 0–100?
   - Option A: Percentile rank within national distribution (P/R 22.2x = 34th percentile nationally = 34 pts)
   - Option B: Absolute breakpoints (P/R ≤12x = 100pts, 12-15x = 80pts, 15-20x = 60pts, 20-25x = 40pts, >25x = 20pts)
   - Option C: Z-score capped at ±2 standard deviations, rescaled to 0-100
   - **Recommendation: percentile normalization (Option A)** — self-corrects as national distribution changes, no arbitrary thresholds to maintain

2. **Exact label trigger thresholds** — precise score cutoffs that put a county in ACCELERATING vs. PEAKING (currently conceptual, need numbers)

3. **National baseline values** — running the full pipeline on all 3,143 counties to establish the actual distribution for percentile normalization

4. **Edge cases** — counties with missing data (FHFA HPI only covers ~2,900 counties, NIBRS coverage varies)

---

## File Structure

```
Civica Harvard Model/
├── CLAUDE.md                          ← This file — project bible
├── harvard_county_profile.html        ← County report template (THE design)
├── harvard_model.html                 ← Methodology page (THE design)
├── civica_data_downloader_v4.py       ← Downloaded the 5 Harvard-specific datasets
├── docs/
│   ├── Civica_Master_Overview.md      ← Full concept doc
│   ├── Momentum_Model.md
│   ├── Revealed_Preference_Model.md
│   └── True_Monthly_Cost_Model.md
├── civica_data/                       ← All 18 datasets on disk
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
    ├── scoring_engine.py              ← Normalization + scoring for all 3,143 counties
    ├── data_processor.py              ← Raw files → clean county-level tables
    └── county_generator.py            ← Produces HTML for every county
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
- No Redfin/Zillow/MLS data — commercial sources introduce conflict of interest
- No hardcoded county-specific values in the template files (data must be injected)

---

## Competitive Positioning

| Feature | Civica | Zillow | Redfin | Niche |
|---|---|---|---|---|
| 100% federal data | Yes | No | No | Partial |
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
