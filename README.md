# Civica

Research-grade housing market intelligence for all 3,143 US counties — built entirely on free federal government data.

## What it does

Civica scores every US county on a 100-point scale using a Harvard-style 6-dimension research model. Each score is derived exclusively from federal government sources: no agents, no listings, no advertising, no conflict of interest.

### The 6 Dimensions

| Dimension | Weight | Key Metrics |
|---|---|---|
| Affordability & Value | 25 pts | Price-to-rent ratio, price-to-income, buy-rent breakeven, appreciation quality |
| Economic Vitality | 22 pts | Wage level, sector quality, HHI diversity, income growth |
| Housing Market Dynamics | 20 pts | FHFA 3-yr appreciation trend (50%), FHFA current momentum (20%), permit pipeline (30%) |
| Quality of Place | 15 pts | Violent crime rate (FBI NIBRS), urban access (USDA RUCC), amenity density (Census CBP) |
| Physical Risk | 12 pts | Flood claims per capita, storm damage per capita, wildfire exposure rank |
| Population Momentum | 6 pts | Net migration rate, income quality of in-movers |

### Market Labels

`ACCELERATING` · `PEAKING` · `ESTABLISHED` · `EMERGING` · `FRONTIER` · `TURNING` · `SPECULATIVE` · `AVOID`

## Data Sources

All data is free and publicly available from US federal agencies.

| Dataset | Source | Used For |
|---|---|---|
| Median home value | ACS 5-year (B25077) | Dim1: median home value, P/R ratio, breakeven |
| Home price appreciation | FHFA HPI (county) | Dim1: appreciation quality; Dim3: 3-yr trend + current momentum |
| Fair market rents | HUD FMR FY2026 | Dim1: rent baseline, P/R ratio, breakeven |
| Per capita income | BEA CAINC1 | Dim1: price-to-income; Dim2: income growth |
| Employment & wages | BLS QCEW 2023 | Dim2: wage level, sector quality score, HHI diversification |
| Business establishments | Census CBP 2022 | Dim4: amenity density (establishments per 1,000 residents) |
| Building permits | Census BPS 2022 | Dim3: new housing supply pipeline |
| Migration flows & income | IRS SOI Migration 2022–23 | Dim6: in-mover income quality ratio |
| Flood insurance claims | FEMA NFIP | Dim5: flood loss per capita (10-yr window) |
| Storm property damage | NOAA Storm Events 2019–2023 | Dim5: storm damage per capita (5-yr window) |
| Wildfire risk | USFS Wildfire Risk to Communities | Dim5: wildfire national risk rank |
| Rural-urban classification | USDA RUCC 2023 | Dim4: urban access continuum |
| Population estimates | Census Population Estimates 2023 | Base county universe, migration rates, per-capita denominators |
| Violent crime | FBI NIBRS 2024 National Master File | Dim4: violent offenses per 100k residents (21,068 agencies, 49 states) |

## Project Structure

```
Civica-2.0/
├── scoring_engine.py          # Scores all 3,143 counties → county_scores.csv
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
python scoring_engine.py
```
Runtime: ~4 minutes. Output: `county_scores.csv` (2,820 counties, 36 columns).

## Score Distribution (current run)

| Metric | Value |
|---|---|
| Counties scored | 2,820 |
| Mean score | 50.0 |
| Std deviation | 6.24 |
| Range | 26.9 – 69.5 |
| Top county | Hamilton County IN (69.5 — ACCELERATING) |
| Labels active | ACCELERATING (2), PEAKING (57), ESTABLISHED (563), EMERGING (1,463), FRONTIER (634), TURNING (97), SPECULATIVE (4), AVOID (0) |

## Status

- [x] Data pipeline — all 14 datasets loading (13 original + FBI NIBRS)
- [x] Scoring engine — `scoring_engine.py`
- [ ] County page generator — `county_generator.py`
- [ ] Front page integration

## License

MIT — see [LICENSE](LICENSE)
