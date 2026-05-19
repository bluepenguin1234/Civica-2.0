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

| Dataset | Source | Use |
|---|---|---|
| Home values & inventory | Zillow Research | Median home value, supply signal |
| Home price appreciation | FHFA HPI | 3-year avg annual change |
| Fair market rents | HUD FMR FY2026 | Rent baseline, P/R ratio |
| Per capita income | BEA CAINC1 | Income level and growth |
| Employment & wages | BLS QCEW 2023 | Sector quality, wage level, HHI |
| Business establishments | Census CBP 2022 | Amenity density |
| Building permits | Census BPS 2022 | New supply pipeline |
| Migration flows & income | IRS SOI Migration | In-mover income quality |
| Flood insurance claims | FEMA NFIP | Flood risk proxy |
| Storm property damage | NOAA Storm Events 2019–2023 | Storm risk proxy |
| Wildfire risk | USFS Wildfire Risk | Wildfire risk rank |
| Rural-urban classification | USDA RUCC 2023 | Urban access score |
| Population estimates | Census Population 2023 | Base county universe |

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
| Std deviation | 7.67 |
| Range | 22.9 – 73.1 |
| Top county | Palm Beach FL (73.1 — PEAKING) |

## Status

- [x] Data pipeline — all 13 datasets loading
- [x] Scoring engine — `scoring_engine.py`
- [ ] County page generator — `county_generator.py`
- [ ] Front page integration

## License

MIT — see [LICENSE](LICENSE)
