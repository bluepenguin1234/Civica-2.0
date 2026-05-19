# Civica

Research-grade housing market intelligence for all 3,143 US counties — built entirely on free federal government data.

## What it does

Civica scores every US county on a 100-point scale using a Harvard-style 6-dimension research model. Each score is derived exclusively from federal government sources: no agents, no listings, no advertising, no conflict of interest.

### The 6 Dimensions

| Dimension | Weight | Key Metrics |
|---|---|---|
| Affordability & Value | 25 pts | Price-to-rent ratio, breakeven horizon, price-to-income |
| Economic Vitality | 22 pts | Wages, sector quality, income growth, HHI diversity |
| Housing Market Dynamics | 20 pts | Price momentum, inventory, permits, in-mover income quality |
| Quality of Place | 15 pts | Urban access (RUCC), establishment density |
| Physical Risk | 12 pts | Flood claims, storm damage, wildfire risk |
| Population Momentum | 6 pts | Net migration rate, domestic migration, inflow volume |

### Market Labels

`ACCELERATING` · `PEAKING` · `ESTABLISHED` · `EMERGING` · `FRONTIER` · `TURNING` · `SPECULATIVE` · `AVOID`

## Data Sources

All data is free and publicly available from US federal agencies.

| Dataset | Source | Use | Status (v2) |
|---|---|---|---|
| Home values & inventory | Zillow Research | Median home value, supply signal | ✓ Active |
| Home price appreciation | FHFA HPI | 3-year avg annual change | ✓ Active |
| Fair market rents | HUD FMR FY2026 | Rent baseline, P/R ratio | ✓ Active |
| Per capita income | BEA CAINC1 | Income level and growth | ✓ Active |
| Employment & wages | BLS QCEW 2023 | Sector quality, wage level, HHI | ✓ Active |
| Business establishments | Census CBP 2022 | Business formation (level proxy) | ✓ Active |
| Building permits | Census BPS 2022 | Permit gap ratio | ✓ Active |
| Migration flows & income | IRS SOI Migration | Net migration + in-mover income quality | ✓ Active |
| Flood insurance claims | FEMA NFIP | Flood risk proxy | ✓ Active |
| Storm property damage | NOAA Storm Events 2019–2023 | Storm risk proxy | ✓ Active |
| Wildfire risk | USFS Wildfire Risk | Wildfire risk rank | ✓ Active |
| Rural-urban classification | USDA RUCC 2023 | Urban access, crime peer comparison | ✓ Active |
| Population estimates | Census Population 2023 | Base county universe | ✓ Active |
| **State/local finance** | **Census STC** | **Fiscal capacity, service efficiency** | **✓ Active (v2 — new)** |
| **Crime (offense records)** | **FBI NIBRS 2024** | **Crime rate vs RUCC peers** | **✓ State-level proxy (v2 — new); county-level parser TODO** |
| **Residential electricity** | **EIA Form 861** | **Utility burden component** | **✓ State-level (v2 — new)** |
| **Residential natural gas** | **EIA NG_PRI_SUM** | **Utility burden component** | **✓ State-level (v2 — new)** |

## Data Confidence

Every county in `county_scores_v2.csv` carries a `data_confidence` score (0–100)
reflecting the % of inputs that were directly observed, not proxied or missing.
Each of the six dimensions also has its own confidence column (`dim1_confidence`
through `dim6_confidence`).

A dimension is scored only when ≥75% of its inputs are present. Counties below
that threshold on a given dimension receive NaN for that dimension; the total
score is computed from available dimensions and scaled to a 0–100 range
proportionally. The market label `INSUFFICIENT_DATA` indicates a county that
couldn't be scored on any dimension.

This replaces v1's blanket median-imputation approach, which silently filled
missing inputs with national medians and treated them as observed data.

### Known proxies (will be upgraded as new datasets are downloaded)

| Spec metric | Current proxy | Upgrade path |
| --- | --- | --- |
| Real Wage Growth | BEA income growth − CPI | Add BLS QCEW 2018, 2020, 2022 |
| Business Formation | Establishment level per 1k pop | Add Census CBP 2019-2021 for CAGR |
| Supply Elasticity | Permits per 1k pop | Add Census BPS 2018-2021 |
| Rent Trend | HPI 3-yr avg | Add HUD FY24 + FY25 FMR |
| School Adequacy | Not yet wired (40% weight redistributed) | Add NCES F-33 + EDFacts |
| Crime Rate | State-level NIBRS proxy | Build proper county-level segment parser |

## Project Structure

```
Civica-2.0/
├── scoring_engine.py             # v1 baseline — scores → county_scores.csv
├── scoring_engine_v2.py          # v2 spec-aligned — scores → county_scores_v2.csv
├── validate_v2.py                # Compares v1 vs v2 output (top movers, spot checks)
├── civica_data_downloader_v4.py  # Downloads all datasets to civica_data/
├── harvard_county_profile.html   # County report template
├── harvard_model.html            # Methodology explainer page
├── CLAUDE.md                     # Full project spec (for AI-assisted development)
├── README.md
├── LICENSE
└── .gitignore
```

The `civica_data/` folder (~7 GB of raw federal data) and `county_scores.csv` are excluded from this repo via `.gitignore`. Run the downloader to obtain the source data.

## How to Run

**1. Install dependencies**
```bash
pip install pandas openpyxl xlrd python-calamine
```

**2. Download the datasets**
```bash
python civica_data_downloader_v4.py
```
Some datasets (USDA RUCC) require a manual download from [USDA ERS](https://www.ers.usda.gov/data-products/rural-urban-continuum-codes/).

**3. Run the scoring engine**
```bash
python scoring_engine_v2.py
```
Runtime: ~4 minutes. Output: `county_scores_v2.csv` — same schema as v1 plus
`data_confidence` and per-dimension `dim{N}_confidence` columns.

`scoring_engine.py` (v1) is preserved for comparison. To diff the two outputs,
run `python validate_v2.py`.

## Score Distribution (current run)

<!-- TODO: fill in from county_scores_v2.csv after running scoring_engine_v2.py locally.
     Use this snippet:
       import pandas as pd
       df = pd.read_csv('county_scores_v2.csv', dtype={'fips': str})
       print(df['total_score'].describe(), df['data_confidence'].median())
-->

| Metric                 | Value                |
| ---------------------- | -------------------- |
| Counties scored        | TODO (v2 run)        |
| Mean score             | TODO                 |
| Std deviation          | TODO                 |
| Range                  | TODO – TODO          |
| Top county             | TODO (FIPS, score, label) |
| Median data confidence | TODO%                |

*All scores derived from federal data only. Counties below 75% data confidence on
any dimension receive a partial score with that dimension flagged.*

## Status

- [x] Data pipeline — 17 federal datasets loading (13 county-level + 4 state-level)
- [x] Scoring engine v1 — `scoring_engine.py` (baseline)
- [x] Scoring engine v2 — `scoring_engine_v2.py` (spec-aligned, per-dimension confidence)
- [ ] County page generator — `county_generator.py` (must read v2 + surface confidence flags)
- [ ] Front page integration

## License

MIT — see [LICENSE](LICENSE)
